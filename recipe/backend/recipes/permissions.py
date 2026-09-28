from rest_framework import permissions


class ReadAnyWriteOwn(permissions.BasePermission):
    """Anyone can read a recipe; you need an account to add one, and only the
    person who uploaded a recipe can change or delete it."""

    message = "Only the person who uploaded this recipe can change it."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner_id == request.user.id
