import uuid

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from recipes.images import BadImage, prepare_web_image
from recipes.models import Recipe
from recipes.serializers import RecipeListSerializer

from .models import Follow, Profile
from .serializers import MeSerializer, ProfileSerializer, RegisterSerializer

User = get_user_model()

AVATAR_MAX_BYTES = 5 * 1024 * 1024


def _me(request):
    return Response(MeSerializer(request.user, context={"request": request}).data)


@api_view(["GET"])
@ensure_csrf_cookie
def me(request):
    """The signed-in user, or null. Also hands the browser its CSRF cookie."""
    if not request.user.is_authenticated:
        return Response(None)
    return _me(request)


@api_view(["POST"])
@csrf_protect
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    login(request, user)
    return Response(MeSerializer(user, context={"request": request}).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@csrf_protect
def sign_in(request):
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str):
        return Response({"detail": "Expected a username and password."}, status=status.HTTP_400_BAD_REQUEST)
    user = authenticate(request, username=username.strip(), password=password)
    if user is None:
        return Response({"detail": "That username and password don't match."}, status=status.HTTP_400_BAD_REQUEST)
    login(request, user)
    return _me(request)


@api_view(["POST"])
def sign_out(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_me(request):
    profile = Profile.objects.get_or_create(user=request.user)[0]
    serializer = ProfileSerializer(profile, data=request.data, partial=True, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return _me(request)


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def avatar(request):
    profile = Profile.objects.get_or_create(user=request.user)[0]
    if request.method == "DELETE":
        if profile.avatar:
            profile.avatar.delete(save=True)
        return _me(request)

    upload = request.FILES.get("avatar")
    if upload is None:
        return Response({"detail": "Choose an image to upload."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        content, extension = prepare_web_image(upload, max_bytes=AVATAR_MAX_BYTES)
    except BadImage as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if profile.avatar:
        profile.avatar.delete(save=False)
    profile.avatar.save(f"{uuid.uuid4().hex}{extension}", content, save=True)
    return _me(request)


def _profile_or_404(username: str) -> Profile:
    user = get_object_or_404(User.objects.select_related("profile"), username__iexact=username, is_active=True)
    return Profile.objects.get_or_create(user=user)[0]


@api_view(["GET"])
def profile_detail(request, username):
    profile = _profile_or_404(username)
    return Response(ProfileSerializer(profile, context={"request": request}).data)


@api_view(["GET"])
def profile_recipes(request, username):
    """Everything this user has uploaded. Public, like the recipes themselves."""
    profile = _profile_or_404(username)
    recipes = Recipe.objects.for_listing(request.user).filter(owner=profile.user)
    ordering = Recipe.ORDERINGS.get(request.query_params.get("ordering", ""), "-created_at")
    recipes = recipes.order_by(ordering, "-id")
    return Response(RecipeListSerializer(recipes, many=True, context={"request": request}).data)


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def follow(request, username):
    profile = _profile_or_404(username)
    if profile.user == request.user:
        return Response({"detail": "You can't follow yourself."}, status=status.HTTP_400_BAD_REQUEST)
    if request.method == "DELETE":
        Follow.objects.filter(follower=request.user, following=profile.user).delete()
    else:
        try:
            Follow.objects.get_or_create(follower=request.user, following=profile.user)
        except IntegrityError:  # pragma: no cover - a double click racing itself
            pass
    return Response(ProfileSerializer(profile, context={"request": request}).data)


@api_view(["GET"])
def following_list(request, username):
    """Who this user follows, for the list on their profile."""
    profile = _profile_or_404(username)
    profiles = Profile.objects.filter(user__follower_set__follower=profile.user).select_related("user")
    return Response(ProfileSerializer(profiles, many=True, context={"request": request}).data)


@api_view(["GET"])
def follower_list(request, username):
    profile = _profile_or_404(username)
    profiles = Profile.objects.filter(user__following_set__following=profile.user).select_related("user")
    return Response(ProfileSerializer(profiles, many=True, context={"request": request}).data)
