import io
import logging
import uuid

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from accounts.serializers import UserBriefSerializer

from .importers import ImportFailed
from .importers.fetch import fetch_image
from .models import Attachment, Comment, Like, Recipe, Tag

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


class CommentSerializer(serializers.ModelSerializer):
    # Null once the author has deleted their account; the UI shows "[deleted]".
    author = UserBriefSerializer(read_only=True)
    # Lets the UI show the author their own Edit and Delete without knowing the
    # rules (the recipe's owner can delete a comment left on their recipe).
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    # The comment being answered. Replying to a reply joins its thread rather
    # than nesting deeper, so this always comes back as a top-level comment.
    parent = serializers.PrimaryKeyRelatedField(queryset=Comment.objects.all(), required=False, allow_null=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id", "author", "body", "parent", "replies", "edited", "edited_at",
            "can_edit", "can_delete", "created_at",
        ]
        read_only_fields = ["edited_at", "created_at"]

    def get_replies(self, obj):
        # Only a top-level comment carries a thread, so this never recurses.
        if obj.parent_id:
            return []
        return CommentSerializer(obj.replies.all(), many=True, context=self.context).data

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Write something first.")
        return value

    def validate_parent(self, value):
        if value is None:
            return None
        recipe = self.context.get("recipe")
        if recipe is not None and value.recipe_id != recipe.pk:
            raise serializers.ValidationError("That comment is on a different recipe.")
        return value.thread

    def _viewer(self):
        return getattr(self.context.get("request"), "user", None)

    def get_can_edit(self, obj):
        viewer = self._viewer()
        return bool(viewer and viewer.is_authenticated and obj.author_id is not None and obj.author_id == viewer.id)

    def get_can_delete(self, obj):
        viewer = self._viewer()
        if not (viewer and viewer.is_authenticated):
            return False
        return (obj.author_id is not None and obj.author_id == viewer.id) or obj.recipe.owner_id == viewer.id

    def update(self, instance, validated_data):
        # Editing rewrites the words; it never moves a comment to another thread.
        validated_data.pop("parent", None)
        validated_data["edited_at"] = timezone.now()
        return super().update(instance, validated_data)


class LikedField(serializers.Field):
    """True when the person reading this has liked the recipe.

    Lists come from `RecipeQuerySet.with_liked()`, which answers this for the
    whole page in one query; a single recipe (e.g. the reply to a save) falls
    back to a lookup.
    """

    def __init__(self, **kwargs):
        super().__init__(source="*", read_only=True, **kwargs)

    def to_representation(self, obj):
        annotated = getattr(obj, "liked_by_viewer", None)
        if annotated is not None:
            return bool(annotated)
        user = getattr(self.context.get("request"), "user", None)
        if user is None or not user.is_authenticated:
            return False
        return Like.objects.filter(recipe=obj, user=user).exists()


class RecipeListSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    tags = TagListField(read_only=True)
    owner = UserBriefSerializer(read_only=True)
    liked = LikedField()

    class Meta:
        model = Recipe
        fields = [
            "id", "title", "image", "total_time", "prep_time", "cook_time", "servings",
            "rating", "like_count", "view_count", "liked", "owner", "tags", "source_name",
            "created_at",
        ]

    def get_image(self, obj):
        return obj.image.url if obj.image else None


class RecipeSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    owner = UserBriefSerializer(read_only=True)
    liked = LikedField()
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
            "image", "image_url", "nutrition", "tags", "rating", "like_count", "view_count",
            "liked", "owner", "import_method", "attachments", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "like_count", "view_count"]

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
