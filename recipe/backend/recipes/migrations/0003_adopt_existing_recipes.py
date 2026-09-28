"""Carries a pre-accounts recipe box over to the new model.

Before accounts existed, the app was single-user: recipes had no owner and
"favorite" was a flag on the recipe itself. If the database already has a user
(the account the admin was set up with), the existing recipes become theirs and
each favorite becomes a like from them. With no user to adopt them, recipes stay
ownerless — still public to read, and editable from the admin.
"""

from django.db import migrations


def adopt(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Recipe = apps.get_model("recipes", "Recipe")
    Like = apps.get_model("recipes", "Like")

    owner = User.objects.filter(is_superuser=True).order_by("pk").first() or User.objects.order_by("pk").first()
    if owner is None:
        return
    Recipe.objects.filter(owner__isnull=True).update(owner=owner)
    for recipe in Recipe.objects.filter(is_favorite=True):
        Like.objects.get_or_create(recipe=recipe, user=owner)
        Recipe.objects.filter(pk=recipe.pk).update(like_count=1)


def unadopt(apps, schema_editor):
    """Reversible: hand the recipes back and turn the likes into favorites."""
    Recipe = apps.get_model("recipes", "Recipe")
    Like = apps.get_model("recipes", "Like")
    Recipe.objects.filter(pk__in=Like.objects.values("recipe_id")).update(is_favorite=True)
    Like.objects.all().delete()
    Recipe.objects.update(owner=None, like_count=0)


class Migration(migrations.Migration):
    dependencies = [("recipes", "0002_recipe_owner_likes_and_counts")]

    operations = [migrations.RunPython(adopt, unadopt)]
