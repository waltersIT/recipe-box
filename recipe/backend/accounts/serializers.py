from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Follow, Profile

User = get_user_model()

USERNAME_HELP = "Letters, numbers, and . _ - only."


class UserBriefSerializer(serializers.ModelSerializer):
    """How a recipe's uploader is shown on cards and recipe pages."""

    name = serializers.CharField(source="profile.name", read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["username", "name", "avatar"]

    def get_avatar(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.avatar.url if profile and profile.avatar else None


class ProfileSerializer(serializers.ModelSerializer):
    """A user's public page, with the numbers shown under their name."""

    username = serializers.CharField(source="user.username", read_only=True)
    name = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField()
    recipe_count = serializers.SerializerMethodField()
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    is_me = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "username", "name", "display_name", "bio", "avatar", "recipe_count",
            "follower_count", "following_count", "is_following", "is_me", "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_avatar(self, obj):
        return obj.avatar.url if obj.avatar else None

    def get_recipe_count(self, obj):
        return obj.user.recipes.count()

    def get_follower_count(self, obj):
        return obj.user.follower_set.count()

    def get_following_count(self, obj):
        return obj.user.following_set.count()

    def get_is_following(self, obj):
        viewer = self.context["request"].user
        if not viewer.is_authenticated:
            return False
        return Follow.objects.filter(follower=viewer, following=obj.user).exists()

    def get_is_me(self, obj):
        return self.context["request"].user == obj.user

    def validate_display_name(self, value):
        return " ".join(value.split())[:80]

    def validate_bio(self, value):
        return value.strip()


class MeSerializer(serializers.ModelSerializer):
    """The signed-in user, as the app needs them: identity plus their own profile."""

    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "profile"]


class RegisterSerializer(serializers.Serializer):
    username = serializers.RegexField(
        r"^[\w.-]+$", min_length=3, max_length=30, error_messages={"invalid": USERNAME_HELP}
    )
    password = serializers.CharField(write_only=True, max_length=128, style={"input_type": "password"})
    email = serializers.EmailField(required=False, allow_blank=True)
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=80)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is taken.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        display_name = " ".join(validated_data.pop("display_name", "").split())
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )
        if display_name:
            # The profile was created by a signal when the user was.
            profile = user.profile
            profile.display_name = display_name[:80]
            profile.save(update_fields=["display_name"])
        return user
