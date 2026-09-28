"""Accounts: who can read, who can upload, profiles, following, and the feed."""

import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from accounts.models import Follow, Profile
from recipes.models import Like, Recipe

from . import samples

MEDIA = tempfile.mkdtemp()

PASSWORD = "a-good-password-1"


def make_user(username, **profile):
    user = User.objects.create_user(username, password=PASSWORD)
    if profile:
        Profile.objects.filter(user=user).update(**profile)
    return user


def make_recipe(owner, title="Pancakes", **fields):
    return Recipe.objects.create(owner=owner, title=title, **fields)


class SignUpTests(APITestCase):
    def test_register_signs_you_in(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "sam", "password": PASSWORD, "display_name": "Sam  Cook"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["username"], "sam")
        self.assertEqual(response.data["profile"]["name"], "Sam Cook")
        self.assertEqual(self.client.get("/api/auth/me/").data["username"], "sam")

    def test_register_rejects_taken_names_and_weak_passwords(self):
        make_user("sam")
        taken = self.client.post("/api/auth/register/", {"username": "SAM", "password": PASSWORD}, format="json")
        self.assertEqual(taken.status_code, 400)
        weak = self.client.post("/api/auth/register/", {"username": "kim", "password": "12345"}, format="json")
        self.assertEqual(weak.status_code, 400)
        self.assertIn("password", weak.data)

    def test_sign_in_and_out(self):
        make_user("sam")
        self.assertEqual(
            self.client.post("/api/auth/login/", {"username": "sam", "password": "wrong"}, format="json").status_code,
            400,
        )
        response = self.client.post("/api/auth/login/", {"username": "sam", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me/").data["username"], "sam")
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertIsNone(self.client.get("/api/auth/me/").data)


class CsrfTests(APITestCase):
    """The browser signs in with a cookie, so unsafe requests carry the CSRF
    token. `api_view` marks the view csrf_exempt, so the check has to be put
    back on — these fail loudly if that decorator moves."""

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        make_user("sam")

    def csrf_token(self):
        self.client.get("/api/auth/me/")
        return self.client.cookies["csrftoken"].value

    def test_signing_in_without_the_token_is_refused(self):
        credentials = {"username": "sam", "password": PASSWORD}
        self.assertEqual(self.client.post("/api/auth/login/", credentials, format="json").status_code, 403)
        response = self.client.post(
            "/api/auth/login/", credentials, format="json", headers={"x-csrftoken": self.csrf_token()}
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_registering_without_the_token_is_refused(self):
        new = {"username": "kim", "password": PASSWORD}
        self.assertEqual(self.client.post("/api/auth/register/", new, format="json").status_code, 403)
        response = self.client.post(
            "/api/auth/register/", new, format="json", headers={"x-csrftoken": self.csrf_token()}
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_a_signed_in_write_without_the_token_is_refused(self):
        token = self.csrf_token()
        self.client.post("/api/auth/login/", {"username": "sam", "password": PASSWORD}, format="json",
                         headers={"x-csrftoken": token})
        recipe = {"title": "Chili"}
        self.assertEqual(self.client.post("/api/recipes/", recipe, format="json").status_code, 403)
        # Signing in rotates the token, so read the new one.
        token = self.client.cookies["csrftoken"].value
        response = self.client.post("/api/recipes/", recipe, format="json", headers={"x-csrftoken": token})
        self.assertEqual(response.status_code, 201, response.data)


class AccessTests(APITestCase):
    def setUp(self):
        self.sam = make_user("sam")
        self.kim = make_user("kim")
        self.recipe = make_recipe(self.sam)

    def test_anyone_can_read_recipes(self):
        self.assertEqual(self.client.get("/api/recipes/").status_code, 200)
        detail = self.client.get(f"/api/recipes/{self.recipe.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["owner"]["username"], "sam")
        self.assertFalse(detail.data["liked"])
        self.assertEqual(self.client.get("/api/tags/").status_code, 200)
        self.assertEqual(self.client.get("/api/home/").status_code, 200)
        self.assertEqual(self.client.get("/api/users/sam/").status_code, 200)
        self.assertEqual(self.client.get("/api/users/sam/recipes/").status_code, 200)

    def test_uploading_needs_an_account(self):
        payload = {"title": "Chili"}
        self.assertEqual(self.client.post("/api/recipes/", payload, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/import/url/", {"url": "x"}, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/import/html/", {"url": "x", "html": ""}, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/import/files/", {}, format="multipart").status_code, 403)
        self.client.force_login(self.sam)
        self.assertEqual(self.client.post("/api/recipes/", payload, format="json").status_code, 201)

    def test_a_new_recipe_belongs_to_whoever_uploaded_it(self):
        self.client.force_login(self.kim)
        response = self.client.post("/api/recipes/", {"title": "Chili"}, format="json")
        self.assertEqual(response.data["owner"]["username"], "kim")
        self.assertEqual(Recipe.objects.get(pk=response.data["id"]).owner, self.kim)

    def test_only_the_owner_can_change_a_recipe(self):
        self.client.force_login(self.kim)
        url = f"/api/recipes/{self.recipe.pk}/"
        self.assertEqual(self.client.patch(url, {"title": "Mine now"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.assertEqual(self.client.post(f"{url}attachments/", {}, format="multipart").status_code, 403)
        self.client.force_login(self.sam)
        self.assertEqual(self.client.patch(url, {"title": "Mine"}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_you_cannot_post_a_recipe_as_someone_else(self):
        self.client.force_login(self.kim)
        response = self.client.post("/api/recipes/", {"title": "Chili", "owner": self.sam.pk}, format="json")
        self.assertEqual(Recipe.objects.get(pk=response.data["id"]).owner, self.kim)


class LikeTests(APITestCase):
    def setUp(self):
        self.sam = make_user("sam")
        self.kim = make_user("kim")
        self.recipe = make_recipe(self.sam)

    def test_liking_needs_an_account(self):
        self.assertEqual(self.client.post(f"/api/recipes/{self.recipe.pk}/like/").status_code, 403)

    def test_like_and_unlike(self):
        self.client.force_login(self.kim)
        url = f"/api/recipes/{self.recipe.pk}/like/"
        response = self.client.post(url)
        self.assertEqual((response.data["liked"], response.data["like_count"]), (True, 1))
        self.client.post(url)  # liking twice is still one like
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.like_count, 1)
        self.assertTrue(self.client.get(f"/api/recipes/{self.recipe.pk}/").data["liked"])
        response = self.client.delete(url)
        self.assertEqual((response.data["liked"], response.data["like_count"]), (False, 0))
        self.assertFalse(Like.objects.exists())

    def test_liked_filter_lists_only_your_own_likes(self):
        other = make_recipe(self.sam, title="Chili")
        Like.objects.create(recipe=other, user=self.kim)
        self.client.force_login(self.kim)
        self.assertEqual([r["title"] for r in self.client.get("/api/recipes/?liked=1").data], ["Chili"])
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get("/api/recipes/?liked=1").data, [])


class ViewCountTests(APITestCase):
    def setUp(self):
        self.sam = make_user("sam")
        self.recipe = make_recipe(self.sam)

    def test_a_visitor_counts_once_per_session(self):
        self.assertEqual(self.client.get(f"/api/recipes/{self.recipe.pk}/").data["view_count"], 1)
        self.assertEqual(self.client.get(f"/api/recipes/{self.recipe.pk}/").data["view_count"], 1)
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.view_count, 1)

    def test_looking_at_your_own_recipe_does_not_count(self):
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(f"/api/recipes/{self.recipe.pk}/").data["view_count"], 0)


@override_settings(MEDIA_ROOT=MEDIA)
class ProfileTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.sam = make_user("sam", display_name="Sam")
        self.kim = make_user("kim")

    def test_profile_shows_their_recipes_and_counts(self):
        make_recipe(self.sam, title="Pancakes")
        make_recipe(self.sam, title="Chili")
        make_recipe(self.kim, title="Soup")
        profile = self.client.get("/api/users/sam/").data
        self.assertEqual(profile["name"], "Sam")
        self.assertEqual(profile["recipe_count"], 2)
        self.assertFalse(profile["is_me"])
        titles = [r["title"] for r in self.client.get("/api/users/sam/recipes/").data]
        self.assertEqual(sorted(titles), ["Chili", "Pancakes"])

    def test_unknown_user_is_404(self):
        self.assertEqual(self.client.get("/api/users/nobody/").status_code, 404)

    def test_editing_your_own_profile(self):
        self.assertEqual(self.client.patch("/api/users/me/", {"bio": "hi"}, format="json").status_code, 403)
        self.client.force_login(self.sam)
        response = self.client.patch("/api/users/me/", {"display_name": "Sam  B", "bio": " Cooks. "}, format="json")
        self.assertEqual(response.data["profile"]["display_name"], "Sam B")
        self.assertEqual(response.data["profile"]["bio"], "Cooks.")
        self.assertTrue(self.client.get("/api/users/sam/").data["is_me"])

    def test_avatar_upload_and_removal(self):
        self.client.force_login(self.sam)
        photo = SimpleUploadedFile("me.png", samples.image_bytes(samples.two_column_card()), "image/png")
        response = self.client.post("/api/users/me/avatar/", {"avatar": photo}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["profile"]["avatar"].startswith("/media/avatars/"))
        bad = SimpleUploadedFile("me.png", b"not an image", "image/png")
        self.assertEqual(self.client.post("/api/users/me/avatar/", {"avatar": bad}, format="multipart").status_code, 400)
        self.assertIsNone(self.client.delete("/api/users/me/avatar/").data["profile"]["avatar"])


class FollowTests(APITestCase):
    def setUp(self):
        self.sam = make_user("sam")
        self.kim = make_user("kim")

    def test_following_needs_an_account(self):
        self.assertEqual(self.client.post("/api/users/sam/follow/").status_code, 403)

    def test_follow_and_unfollow(self):
        self.client.force_login(self.kim)
        response = self.client.post("/api/users/sam/follow/")
        self.assertTrue(response.data["is_following"])
        self.assertEqual(response.data["follower_count"], 1)
        self.client.post("/api/users/sam/follow/")  # following twice is still once
        self.assertEqual(Follow.objects.count(), 1)
        self.assertEqual(self.client.get("/api/users/kim/following/").data[0]["username"], "sam")
        self.assertEqual(self.client.get("/api/users/sam/followers/").data[0]["username"], "kim")
        self.assertFalse(self.client.delete("/api/users/sam/follow/").data["is_following"])

    def test_you_cannot_follow_yourself(self):
        self.client.force_login(self.sam)
        self.assertEqual(self.client.post("/api/users/sam/follow/").status_code, 400)


class HomeFeedTests(APITestCase):
    def setUp(self):
        self.sam = make_user("sam")
        self.kim = make_user("kim")

    def test_recommended_is_ordered_by_views_and_likes(self):
        quiet = make_recipe(self.sam, title="Quiet")
        viewed = make_recipe(self.sam, title="Viewed", view_count=15)
        liked = make_recipe(self.sam, title="Liked", view_count=1)
        Like.objects.create(recipe=liked, user=self.kim)
        Like.objects.create(recipe=liked, user=make_user("ash"))
        # Two likes (worth ten views each) beat fifteen views.
        titles = [r["title"] for r in self.client.get("/api/home/").data["recommended"]]
        self.assertEqual(titles, ["Liked", "Viewed", "Quiet"])
        self.assertEqual(self.client.get("/api/home/").data["recipe_count"], 3)
        self.assertEqual((quiet.like_count, viewed.like_count), (0, 0))

    def test_the_feed_is_empty_until_you_follow_someone(self):
        make_recipe(self.sam)
        data = self.client.get("/api/home/").data
        self.assertEqual((data["following"], data["following_count"]), ([], 0))
        self.client.force_login(self.kim)
        self.assertEqual(self.client.get("/api/home/").data["following"], [])

    def test_following_someone_puts_their_recipes_in_the_feed(self):
        make_recipe(self.sam, title="Pancakes")
        make_recipe(self.kim, title="Mine")
        make_user("ash")
        make_recipe(User.objects.get(username="ash"), title="Not followed")
        self.client.force_login(self.kim)
        self.client.post("/api/users/sam/follow/")
        data = self.client.get("/api/home/").data
        self.assertEqual([r["title"] for r in data["following"]], ["Pancakes"])
        self.assertEqual(data["following_count"], 1)
        # A recipe in the feed isn't repeated under "recommended".
        self.assertNotIn("Pancakes", [r["title"] for r in data["recommended"]])
        self.assertEqual([r["title"] for r in self.client.get("/api/recipes/?following=1").data], ["Pancakes"])

    def test_mine_and_user_filters(self):
        make_recipe(self.sam, title="Pancakes")
        make_recipe(self.kim, title="Mine")
        # The filters about "you" show nothing rather than everything when
        # there's nobody signed in.
        for query in ("mine=1", "following=1", "liked=1"):
            self.assertEqual(self.client.get(f"/api/recipes/?{query}").data, [], query)
        self.client.force_login(self.kim)
        self.assertEqual([r["title"] for r in self.client.get("/api/recipes/?mine=1").data], ["Mine"])
        self.assertEqual([r["title"] for r in self.client.get("/api/recipes/?user=sam").data], ["Pancakes"])
