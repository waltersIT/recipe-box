from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("recipes", views.RecipeViewSet, basename="recipe")

urlpatterns = [
    path("", include(router.urls)),
    path("tags/", views.tag_list, name="tag-list"),
    path("import/config/", views.import_config, name="import-config"),
    path("import/url/", views.import_url, name="import-url"),
    path("import/html/", views.import_html, name="import-html"),
    path("import/files/", views.import_files, name="import-files"),
]
