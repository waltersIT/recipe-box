from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Tag(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Recipe(models.Model):
    """A saved recipe.

    `ingredients` and `instructions` are ordered lists of strings. An item that
    starts with "# " is a section heading ("# For the frosting").
    """

    class ImportMethod(models.TextChoices):
        MANUAL = "manual", "Typed in"
        URL = "url", "Web link"
        BROWSER = "browser", "Browser bookmarklet"
        PDF = "pdf", "PDF"
        IMAGE = "image", "Screenshot or photo"

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
    is_favorite = models.BooleanField(default=False)
    import_method = models.CharField(
        max_length=20, choices=ImportMethod.choices, default=ImportMethod.MANUAL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


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


@receiver(post_delete, sender=Recipe)
def _delete_recipe_image(sender, instance, **kwargs):
    if instance.image:
        instance.image.delete(save=False)


@receiver(post_delete, sender=Attachment)
def _delete_attachment_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
