import io
import logging
import uuid

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from .importers import ImportFailed
from .importers.fetch import fetch_image
from .models import Attachment, Recipe, Tag

log = logging.getLogger(__name__)


class TagListField(serializers.Field):
    """Tags as a plain list of names; unknown names are created on save."""

    def to_representation(self, value):
        return [tag.name for tag in value.all()]

    def to_internal_value(self, data):
        if not isinstance(data, list):
            raise serializers.ValidationError("Expected a list of tag names.")
        names, seen = [], set()
        for item in data:
            if not isinstance(item, str):
                raise serializers.ValidationError("Tag names must be strings.")
            name = " ".join(item.split())[:60]
            if name and name.lower() not in seen:
                seen.add(name.lower())
                names.append(name)
        return names


class LinesField(serializers.ListField):
    """An ordered list of non-empty strings (ingredients or steps)."""

    child = serializers.CharField(allow_blank=True, trim_whitespace=True, max_length=5000)

    def to_internal_value(self, data):
        return [line for line in super().to_internal_value(data) if line]


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ["id", "url", "original_name", "content_type", "created_at"]

    def get_url(self, obj):
        return obj.file.url if obj.file else None


class RecipeListSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    tags = TagListField(read_only=True)

    class Meta:
        model = Recipe
        fields = [
            "id", "title", "image", "total_time", "prep_time", "cook_time", "servings",
            "rating", "is_favorite", "tags", "source_name", "created_at",
        ]

    def get_image(self, obj):
        return obj.image.url if obj.image else None


class RecipeSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    tags = TagListField(required=False)
    ingredients = LinesField(required=False)
    instructions = LinesField(required=False)
    attachments = AttachmentSerializer(many=True, read_only=True)
    # Write-only: a remote image (from an import) to download and store locally.
    image_url = serializers.URLField(write_only=True, required=False, allow_blank=True, max_length=2000)

    class Meta:
        model = Recipe
        fields = [
            "id", "title", "description", "ingredients", "instructions", "notes", "servings",
            "prep_time", "cook_time", "total_time", "source_url", "source_name", "author",
            "image", "image_url", "nutrition", "tags", "rating", "is_favorite", "import_method",
            "attachments", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_image(self, obj):
        return obj.image.url if obj.image else None

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Give the recipe a title.")
        return value

    def validate_nutrition(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Expected an object.")
        return {str(k)[:60]: str(v)[:60] for k, v in value.items()}

    @transaction.atomic
    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        image_url = validated_data.pop("image_url", "")
        recipe = Recipe.objects.create(**validated_data)
        _set_tags(recipe, tags)
        if image_url:
            _download_image(recipe, image_url)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        image_url = validated_data.pop("image_url", "")
        instance = super().update(instance, validated_data)
        if tags is not None:
            _set_tags(instance, tags)
        if image_url:
            _download_image(instance, image_url)
        return instance


def _set_tags(recipe: Recipe, names: list[str]) -> None:
    tags = []
    for name in names:
        tag = Tag.objects.filter(name__iexact=name).first() or Tag.objects.create(name=name)
        tags.append(tag)
    recipe.tags.set(tags)


RASTER_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif", "AVIF": ".avif"}


def _download_image(recipe: Recipe, url: str) -> None:
    """Best effort: a recipe still saves if its photo can't be downloaded."""
    try:
        data, _ = fetch_image(url)
    except ImportFailed as exc:
        log.info("Skipping recipe image %s: %s", url, exc)
        return
    # Trust the bytes, not the site's content type: only store real raster images
    # (an SVG "photo" could carry script that runs on this site's origin).
    try:
        with Image.open(io.BytesIO(data)) as image:
            extension = RASTER_FORMATS.get(image.format)
    except (UnidentifiedImageError, OSError):
        extension = None
    if extension is None:
        log.info("Skipping recipe image %s: not a supported image format", url)
        return
    if recipe.image:
        recipe.image.delete(save=False)
    recipe.image.save(f"{uuid.uuid4().hex}{extension}", ContentFile(data), save=True)
