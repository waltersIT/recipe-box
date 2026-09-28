from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthz(request):
    """Liveness check for nginx/deploy.sh: the app is answering. Touches no database."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", healthz),
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("recipes.urls")),
    # Only active with DEBUG on; in production nginx serves /media/ directly.
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
