from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

# How much a like is worth against a view in the "popular" ordering.
LIKE_WEIGHT = 10


class Tag(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RecipeQuerySet(models.QuerySet):
    def for_listing(self, viewer=None):
        """Everything a recipe card shows, without a query per card."""
        return self.select_related("owner__profile").prefetch_related("tags").with_liked(viewer)

    def with_liked(self, viewer):
        """Adds `liked_by_viewer` so a list of cards needs no query per card."""
        if getattr(viewer, "is_authenticated", False):
            return self.annotate(
                liked_by_viewer=models.Exists(Like.objects.filter(recipe=models.OuterRef("pk"), user=viewer))
            )
        return self.annotate(liked_by_viewer=models.Value(False, output_field=models.BooleanField()))

    def popular(self):
        """Most viewed and liked first: what the landing page recommends.

        A like is a deliberate act and a view is barely one, so likes count for
        more. Both are stored counters, so this stays one cheap query.
        """
        return self.annotate(
            score=models.F("like_count") * LIKE_WEIGHT + models.F("view_count")
        ).order_by("-score", "-created_at", "-id")


class Recipe(models.Model):
    """A saved recipe.

    `ingredients` and `instructions` are ordered lists of strings. An item that
    starts with "# " is a section heading ("# For the frosting").
    """

    ORDERINGS = {
        "newest": "-created_at",
        "oldest": "created_at",
        "title": "title",
        "rating": "-rating",
        "updated": "-updated_at",
        "liked": "-like_count",
        "viewed": "-view_count",
    }

    class ImportMethod(models.TextChoices):
        MANUAL = "manual", "Typed in"
        URL = "url", "Web link"
        BROWSER = "browser", "Browser bookmarklet"
        PDF = "pdf", "PDF"
        IMAGE = "image", "Screenshot or photo"

    # Recipes are public to read; only their owner can change them. Recipes
    # imported before accounts existed have no owner.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipes", null=True, blank=True
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    ingredients = models.JSONField(default=list, blank=True)
    instructions = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    servings = models.CharField(max_length=100, blank=True)
    prep_time = models.PositiveIntegerField(null=True, blank=True, help_text="Minutes")
    cook_time = models.PositiveIntegerField(null=True, blank=True, help_text="Minutes")
    total_time = models.PositiveIntegerField(null=True, blank=True, help_text="Minutes")
    source_url = models.URLField(max_length=2000, blank=True)
    source_name = models.CharField(max_length=200, blank=True)
    author = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to="recipes/images/", blank=True)
    nutrition = models.JSONField(default=dict, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="recipes")
    rating = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(5)])
    # Kept up to date with the Like rows so the popular ordering is one query.
    like_count = models.PositiveIntegerField(default=0, db_index=True)
    view_count = models.PositiveIntegerField(default=0, db_index=True)
    import_method = models.CharField(
        max_length=20, choices=ImportMethod.choices, default=ImportMethod.MANUAL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RecipeQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Like(models.Model):
    """One person liking one recipe. Likes are public and count towards popularity."""

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["recipe", "user"], name="unique_like")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} ♥ {self.recipe}"


class Comment(models.Model):
    """Something a reader said about a recipe, or a reply to someone who did.

    Comments read like a conversation, so they're kept oldest first. Anyone can
    read them; an account is needed to leave one.

    Threads are one level deep: a reply hangs off a top-level comment, and
    replying to a reply joins that same thread rather than nesting further.
    Deep nesting is hard to read and harder to answer on a phone.

    When an author deletes their account, their comments stay so the
    conversation around them still makes sense, but `author` is cleared and
    they're shown as "[deleted]", like Reddit.
    """

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="comments", null=True, blank=True
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="replies", null=True, blank=True
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    # Set when the author rewrites the comment, so the UI can say "edited".
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.author or '[deleted]'} on {self.recipe}"

    @property
    def edited(self) -> bool:
        return self.edited_at is not None

    @property
    def thread(self) -> "Comment":
        """The top-level comment this belongs to (itself, for a top-level one)."""
        return self.parent or self


class Attachment(models.Model):
    """An original file a recipe was imported from (PDF, screenshot, photo)."""

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="recipes/sources/")
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.original_name or self.file.name


@receiver([post_save, post_delete], sender=Like)
def _sync_like_count(sender, instance, **kwargs):
    Recipe.objects.filter(pk=instance.recipe_id).update(
        like_count=Like.objects.filter(recipe_id=instance.recipe_id).count()
    )


@receiver(post_delete, sender=Recipe)
def _delete_recipe_image(sender, instance, **kwargs):
    if instance.image:
        instance.image.delete(save=False)


@receiver(post_delete, sender=Attachment)
def _delete_attachment_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
