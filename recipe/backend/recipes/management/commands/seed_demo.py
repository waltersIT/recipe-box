"""Fills an empty database with a few accounts and recipes to click around in.

    .venv/bin/python manage.py seed_demo

Everything it makes is obviously fake, including the passwords, so only run it
on a development database. `--reset` clears what a previous run created.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Follow, Profile
from recipes.models import Like, Recipe, Tag

User = get_user_model()

PASSWORD = "kitchen-table-42"

PEOPLE = [
    ("sam", "Sam Okafor", "Weeknight dinners and too much garlic."),
    ("ada", "Ada Lin", "Baking, mostly."),
    ("mira", "Mira Bell", "Learning to cook, one loaf at a time."),
]

RECIPES = [
    ("sam", "Garlic Butter Noodles", ["200 g spaghetti", "4 cloves garlic", "60 g butter", "Parmesan, to serve"],
     ["Boil the pasta in well-salted water.", "Melt the butter and soften the garlic in it.",
      "Toss the drained pasta through the butter with a splash of the cooking water."],
     ["Dinner", "Quick"], 140, 4),
    ("sam", "Charred Broccoli", ["1 head broccoli", "2 tbsp olive oil", "1 lemon"],
     ["Heat the oven to 230°C.", "Toss the florets in oil and spread them out.",
      "Roast for 20 minutes, until the edges blacken.", "Squeeze the lemon over."],
     ["Sides"], 30, 5),
    ("ada", "Brown Butter Banana Bread", ["3 very ripe bananas", "230 g flour", "115 g butter", "150 g brown sugar", "2 eggs"],
     ["Brown the butter and let it cool.", "Mash the bananas with the sugar and eggs.",
      "Fold in the flour.", "Bake at 175°C for 55 minutes."],
     ["Baking", "Breakfast"], 310, 5),
    ("ada", "Sourdough Focaccia", ["500 g bread flour", "400 g water", "100 g starter", "12 g salt", "Olive oil"],
     ["Mix and rest for an hour.", "Fold every 30 minutes, four times.", "Prove overnight in the fridge.",
      "Dimple into an oiled tray and bake at 230°C for 25 minutes."],
     ["Baking"], 95, 4),
    ("ada", "Cold Soba Salad", ["200 g soba", "1 cucumber", "2 tbsp soy sauce", "1 tbsp sesame oil"],
     ["Cook the soba and rinse it cold.", "Ribbon the cucumber.", "Toss everything together."],
     ["Lunch", "Quick"], 12, 0),
]

# Who follows whom, and who liked what.
FOLLOWS = [("mira", "ada"), ("mira", "sam"), ("sam", "ada")]
LIKES = [("sam", "Brown Butter Banana Bread"), ("ada", "Garlic Butter Noodles"), ("mira", "Charred Broccoli")]


class Command(BaseCommand):
    help = "Create demo accounts and recipes in a development database."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete the demo accounts and their recipes first.")

    @transaction.atomic
    def handle(self, *args, **options):
        usernames = [username for username, _, _ in PEOPLE]
        if options["reset"]:
            User.objects.filter(username__in=usernames).delete()
        elif User.objects.filter(username__in=usernames).exists():
            raise CommandError("The demo accounts already exist. Pass --reset to recreate them.")

        users = {}
        for username, name, bio in PEOPLE:
            user = User.objects.create_user(username, password=PASSWORD)
            Profile.objects.filter(user=user).update(display_name=name, bio=bio)
            users[username] = user

        for owner, title, ingredients, instructions, tags, views, rating in RECIPES:
            recipe = Recipe.objects.create(
                owner=users[owner], title=title, ingredients=ingredients, instructions=instructions,
                view_count=views, rating=rating, prep_time=10, cook_time=20, servings="2",
            )
            recipe.tags.set([Tag.objects.get_or_create(name=tag)[0] for tag in tags])

        for follower, following in FOLLOWS:
            Follow.objects.get_or_create(follower=users[follower], following=users[following])
        for username, title in LIKES:
            Like.objects.get_or_create(recipe=Recipe.objects.get(title=title), user=users[username])

        self.stdout.write(
            self.style.SUCCESS(
                f"Added {len(PEOPLE)} accounts and {len(RECIPES)} recipes. "
                f"Sign in as any of {', '.join(usernames)} with the password {PASSWORD!r}."
            )
        )
