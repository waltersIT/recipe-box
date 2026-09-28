import os
import uuid

from django.conf import settings
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .images import BadImage, prepare_web_image
from .importers import ImportFailed, import_from_files, import_from_html, import_from_url
from .importers.llm import llm_enabled
from .importers.ocr import engine_name
from .models import Attachment, Like, Recipe, Tag
from .permissions import ReadAnyWriteOwn
from .serializers import AttachmentSerializer, RecipeListSerializer, RecipeSerializer

# How many recipes each section of the landing page shows.
HOME_SECTION_SIZE = 12
# Recipe ids kept in the session so refreshing a page doesn't count again.
VIEWED_SESSION_KEY = "viewed_recipes"
VIEWED_SESSION_MAX = 200
# Original files kept with a recipe. Anything else (e.g. .html) could run script
# on this site's origin when opened, so it isn't stored.
ATTACHMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}


class RecipeViewSet(viewsets.ModelViewSet):
    """Recipes are public to read. Adding one needs an account, and only the
    person who uploaded a recipe can edit or delete it."""

    permission_classes = [ReadAnyWriteOwn]

    def get_serializer_class(self):
        return RecipeListSerializer if self.action == "list" else RecipeSerializer

    def get_queryset(self):
        viewer = self.request.user
        queryset = Recipe.objects.for_listing(viewer)
        if self.action != "list":
            return queryset.prefetch_related("attachments")
        params = self.request.query_params
        # "mine", "following" and "liked" are about the person reading, so
        # signed out they have nothing to show rather than everything.
        if params.get("mine") in ("1", "true"):
            if not viewer.is_authenticated:
                return queryset.none()
            queryset = queryset.filter(owner=viewer)
        if params.get("following") in ("1", "true"):
            if not viewer.is_authenticated:
                return queryset.none()
            queryset = queryset.filter(owner__follower_set__follower=viewer)
        author = params.get("user", "").strip()
        if author:
            queryset = queryset.filter(owner__username__iexact=author)
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
        if params.get("liked") in ("1", "true"):
            if not viewer.is_authenticated:
                return queryset.none()
            queryset = queryset.filter(likes__user=viewer)
        queryset = queryset.distinct()
        if params.get("ordering") == "popular":
            return queryset.popular()
        ordering = Recipe.ORDERINGS.get(params.get("ordering", ""), "-created_at")
        return queryset.order_by(ordering, "-id")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        recipe = self.get_object()
        self._count_view(recipe)
        return Response(self.get_serializer(recipe).data)

    def _count_view(self, recipe):
        """One view per recipe per browser session, and never your own."""
        request = self.request
        if recipe.owner_id and recipe.owner_id == request.user.id:
            return
        seen = request.session.get(VIEWED_SESSION_KEY, [])
        if recipe.pk in seen:
            return
        Recipe.objects.filter(pk=recipe.pk).update(view_count=F("view_count") + 1)
        recipe.view_count += 1
        request.session[VIEWED_SESSION_KEY] = [*seen[-(VIEWED_SESSION_MAX - 1):], recipe.pk]

    @action(detail=True, methods=["post", "delete"], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        recipe = self.get_object()
        if request.method == "DELETE":
            Like.objects.filter(recipe=recipe, user=request.user).delete()
        else:
            Like.objects.get_or_create(recipe=recipe, user=request.user)
        recipe.refresh_from_db(fields=["like_count"])
        recipe.liked_by_viewer = request.method == "POST"
        return Response({"id": recipe.pk, "like_count": recipe.like_count, "liked": recipe.liked_by_viewer})

    @action(detail=True, methods=["post", "delete"], parser_classes=[MultiPartParser])
    def image(self, request, pk=None):
        recipe = self.get_object()
        if request.method == "DELETE":
            if recipe.image:
                recipe.image.delete(save=True)
            return Response(self.get_serializer(recipe).data)

        upload = request.FILES.get("image")
        if upload is None:
            return Response({"detail": "Choose an image to upload."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            content, extension = prepare_web_image(upload)
        except BadImage as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if recipe.image:
            recipe.image.delete(save=False)
        recipe.image.save(f"{uuid.uuid4().hex}{extension}", content, save=True)
        return Response(self.get_serializer(recipe).data)

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
        recipe = self.get_object()  # also checks that this recipe is yours
        attachment = get_object_or_404(Attachment, pk=attachment_id, recipe=recipe)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def home(request):
    """The landing page: recipes from the people you follow, then what's popular.

    "Popular" is most viewed and liked (see `RecipeQuerySet.popular`). Recipes
    already shown in the following section aren't repeated below it.
    """
    viewer = request.user
    recipes = Recipe.objects.for_listing(viewer)
    following, following_count = [], 0
    if viewer.is_authenticated:
        following_count = viewer.following_set.count()
        if following_count:
            following = list(
                recipes.filter(owner__follower_set__follower=viewer).distinct().order_by("-created_at", "-id")[
                    :HOME_SECTION_SIZE
                ]
            )
    popular = recipes.exclude(pk__in=[r.pk for r in following]).popular()[:HOME_SECTION_SIZE]
    serialize = lambda items: RecipeListSerializer(items, many=True, context={"request": request}).data
    return Response(
        {
            "following": serialize(following),
            "following_count": following_count,
            "recommended": serialize(popular),
            "recipe_count": Recipe.objects.count(),
        }
    )


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
@permission_classes([IsAuthenticated])
def import_url(request):
    url = request.data.get("url", "")
    if not isinstance(url, str):
        return Response({"detail": "Expected a link."}, status=status.HTTP_400_BAD_REQUEST)
    return _import_response(lambda: import_from_url(url))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_html(request):
    """Used by the bookmarklet: the page's HTML as your browser sees it."""
    url, html = request.data.get("url", ""), request.data.get("html", "")
    if not isinstance(url, str) or not isinstance(html, str):
        return Response({"detail": "Expected a url and html."}, status=status.HTTP_400_BAD_REQUEST)
    return _import_response(lambda: import_from_html(html, url, method="browser"))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def import_files(request):
    uploads = request.FILES.getlist("files")
    return _import_response(lambda: import_from_files(uploads))
