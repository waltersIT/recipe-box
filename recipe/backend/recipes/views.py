import io
import os
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from .importers import ImportFailed, import_from_files, import_from_html, import_from_url
from .importers.llm import llm_enabled
from .importers.ocr import engine_name
from .models import Attachment, Recipe, Tag
from .serializers import AttachmentSerializer, RecipeListSerializer, RecipeSerializer

MAX_IMAGE_BYTES = 15 * 1024 * 1024
WEB_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
# Original files kept with a recipe. Anything else (e.g. .html) could run script
# on this site's origin when opened, so it isn't stored.
ATTACHMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}


class RecipeViewSet(viewsets.ModelViewSet):
    ORDERINGS = {
        "newest": "-created_at",
        "oldest": "created_at",
        "title": "title",
        "rating": "-rating",
        "updated": "-updated_at",
    }

    def get_serializer_class(self):
        return RecipeListSerializer if self.action == "list" else RecipeSerializer

    def get_queryset(self):
        queryset = Recipe.objects.prefetch_related("tags")
        if self.action != "list":
            return queryset.prefetch_related("attachments")
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            for term in search.split():
                queryset = queryset.filter(
                    Q(title__icontains=term)
                    | Q(ingredients__icontains=term)
                    | Q(description__icontains=term)
                    | Q(notes__icontains=term)
                    | Q(tags__name__icontains=term)
                    | Q(source_name__icontains=term)
                )
        tag = params.get("tag", "").strip()
        if tag:
            queryset = queryset.filter(tags__name__iexact=tag)
        if params.get("favorite") in ("1", "true"):
            queryset = queryset.filter(is_favorite=True)
        ordering = self.ORDERINGS.get(params.get("ordering", ""), "-created_at")
        return queryset.distinct().order_by(ordering, "-id")

    @action(detail=True, methods=["post", "delete"], parser_classes=[MultiPartParser])
    def image(self, request, pk=None):
        recipe = self.get_object()
        if request.method == "DELETE":
            if recipe.image:
                recipe.image.delete(save=True)
            return Response(RecipeSerializer(recipe).data)

        upload = request.FILES.get("image")
        if upload is None:
            return Response({"detail": "Choose an image to upload."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_IMAGE_BYTES:
            return Response({"detail": "Images must be under 15 MB."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            image = Image.open(upload)
            image.load()
        except (UnidentifiedImageError, OSError):
            return Response({"detail": "That file isn't an image."}, status=status.HTTP_400_BAD_REQUEST)
        if image.format in WEB_IMAGE_FORMATS:
            upload.seek(0)
            content, extension = upload, WEB_IMAGE_FORMATS[image.format]
        else:
            # e.g. HEIC photos from an iPhone, which browsers can't display.
            buffer = io.BytesIO()
            ImageOps.exif_transpose(image).convert("RGB").save(buffer, format="JPEG", quality=90)
            content, extension = ContentFile(buffer.getvalue()), ".jpg"
        if recipe.image:
            recipe.image.delete(save=False)
        recipe.image.save(f"{uuid.uuid4().hex}{extension}", content, save=True)
        return Response(RecipeSerializer(recipe).data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def attachments(self, request, pk=None):
        recipe = self.get_object()
        uploads = request.FILES.getlist("file")
        if not uploads:
            return Response({"detail": "No files were uploaded."}, status=status.HTTP_400_BAD_REQUEST)
        created = []
        for upload in uploads[: settings.RECIPE_MAX_UPLOAD_FILES]:
            extension = os.path.splitext(upload.name)[1].lower()
            if upload.size > settings.RECIPE_MAX_UPLOAD_BYTES or extension not in ATTACHMENT_EXTENSIONS:
                continue
            attachment = Attachment(
                recipe=recipe,
                original_name=upload.name[:255],
                content_type=(upload.content_type or "")[:100],
            )
            attachment.file.save(f"{uuid.uuid4().hex}{extension}", upload, save=True)
            created.append(attachment)
        return Response(AttachmentSerializer(created, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"attachments/(?P<attachment_id>\d+)")
    def delete_attachment(self, request, pk=None, attachment_id=None):
        attachment = get_object_or_404(Attachment, pk=attachment_id, recipe_id=pk)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def tag_list(request):
    tags = Tag.objects.annotate(count=Count("recipes")).filter(count__gt=0).order_by("name")
    return Response([{"name": t.name, "count": t.count} for t in tags])


@api_view(["GET"])
def import_config(request):
    """Tells the UI which import engines are available on this machine."""
    return Response(
        {
            "llm_enabled": llm_enabled(),
            "llm_model": settings.RECIPE_LLM_MODEL if llm_enabled() else None,
            "ocr_engine": engine_name(),
            "max_files": settings.RECIPE_MAX_UPLOAD_FILES,
            "max_file_mb": settings.RECIPE_MAX_UPLOAD_BYTES // (1024 * 1024),
        }
    )


def _import_response(run):
    try:
        result = run()
    except ImportFailed as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    return Response(result.to_dict())


@api_view(["POST"])
def import_url(request):
    url = request.data.get("url", "")
    if not isinstance(url, str):
        return Response({"detail": "Expected a link."}, status=status.HTTP_400_BAD_REQUEST)
    return _import_response(lambda: import_from_url(url))


@api_view(["POST"])
def import_html(request):
    """Used by the bookmarklet: the page's HTML as your browser sees it."""
    url, html = request.data.get("url", ""), request.data.get("html", "")
    if not isinstance(url, str) or not isinstance(html, str):
        return Response({"detail": "Expected a url and html."}, status=status.HTTP_400_BAD_REQUEST)
    return _import_response(lambda: import_from_html(html, url, method="browser"))


@api_view(["POST"])
@parser_classes([MultiPartParser])
def import_files(request):
    uploads = request.FILES.getlist("files")
    return _import_response(lambda: import_from_files(uploads))
