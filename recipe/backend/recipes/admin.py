from django.contrib import admin

from .models import Attachment, Like, Recipe, Tag


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "like_count", "view_count", "import_method", "created_at"]
    list_filter = ["import_method", "tags"]
    search_fields = ["title", "description", "source_name", "owner__username"]
    raw_id_fields = ["owner"]
    filter_horizontal = ["tags"]
    inlines = [AttachmentInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ["recipe", "user", "created_at"]
    raw_id_fields = ["recipe", "user"]
