from django.contrib import admin

from .models import Attachment, Recipe, Tag


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["title", "source_name", "import_method", "rating", "is_favorite", "created_at"]
    list_filter = ["import_method", "is_favorite", "tags"]
    search_fields = ["title", "description", "source_name"]
    filter_horizontal = ["tags"]
    inlines = [AttachmentInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ["name"]
