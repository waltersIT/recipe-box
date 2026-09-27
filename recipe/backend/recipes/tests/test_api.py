import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from recipes.importers import ImportFailed
from recipes.models import Attachment, Recipe

from . import samples

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA, RECIPE_LLM="off")
class RecipeApiTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def create(self, **overrides):
        payload = {
            "title": "Pancakes",
            "ingredients": ["1 cup flour", "", "1 egg"],
            "instructions": ["Mix.", "Cook."],
            "tags": ["Breakfast", "breakfast", " Quick  "],
            "prep_time": 5,
        }
        payload.update(overrides)
        return self.client.post("/api/recipes/", payload, format="json")

    def test_create_and_read(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["ingredients"], ["1 cup flour", "1 egg"])
        self.assertEqual(response.data["tags"], ["Breakfast", "Quick"])
        detail = self.client.get(f"/api/recipes/{response.data['id']}/")
        self.assertEqual(detail.data["title"], "Pancakes")
        self.assertEqual(detail.data["attachments"], [])

    def test_title_required(self):
        self.assertEqual(self.create(title="  ").status_code, 400)

    def test_search_filter_and_tags(self):
        self.create()
        self.create(title="Chili", ingredients=["1 lb beef", "2 cans beans"], tags=["Dinner"], is_favorite=True)
        titles = lambda r: [item["title"] for item in r.data]
        self.assertEqual(titles(self.client.get("/api/recipes/?search=beans")), ["Chili"])
        self.assertEqual(titles(self.client.get("/api/recipes/?search=FLOUR")), ["Pancakes"])
        self.assertEqual(titles(self.client.get("/api/recipes/?tag=dinner")), ["Chili"])
        self.assertEqual(titles(self.client.get("/api/recipes/?favorite=1")), ["Chili"])
        self.assertEqual(titles(self.client.get("/api/recipes/?ordering=title")), ["Chili", "Pancakes"])
        tags = self.client.get("/api/tags/").data
        self.assertEqual([t["name"] for t in tags], ["Breakfast", "Dinner", "Quick"])

    def test_update_tags(self):
        recipe_id = self.create().data["id"]
        response = self.client.patch(f"/api/recipes/{recipe_id}/", {"tags": ["Brunch"], "rating": 4}, format="json")
        self.assertEqual(response.data["tags"], ["Brunch"])
        self.assertEqual(response.data["rating"], 4)
        self.assertEqual(self.client.patch(f"/api/recipes/{recipe_id}/", {"rating": 9}, format="json").status_code, 400)

    def test_image_upload_and_delete(self):
        recipe_id = self.create().data["id"]
        image = SimpleUploadedFile("photo.png", samples.image_bytes(samples.two_column_card()), "image/png")
        response = self.client.post(f"/api/recipes/{recipe_id}/image/", {"image": image}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["image"].startswith("/media/recipes/images/"))
        bad = SimpleUploadedFile("photo.png", b"not an image", "image/png")
        self.assertEqual(
            self.client.post(f"/api/recipes/{recipe_id}/image/", {"image": bad}, format="multipart").status_code, 400
        )
        response = self.client.delete(f"/api/recipes/{recipe_id}/image/")
        self.assertIsNone(response.data["image"])

    def test_non_web_images_are_converted_to_jpeg(self):
        recipe_id = self.create().data["id"]
        tiff = SimpleUploadedFile("scan.tiff", samples.image_bytes(samples.two_column_card(), fmt="TIFF"), "image/tiff")
        response = self.client.post(f"/api/recipes/{recipe_id}/image/", {"image": tiff}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["image"].endswith(".jpg"))

    def test_image_url_is_downloaded(self):
        data = samples.image_bytes(samples.two_column_card(), fmt="JPEG")
        with mock.patch("recipes.serializers.fetch_image", return_value=(data, "image/jpeg")):
            response = self.create(image_url="https://example.com/photo.jpg")
        self.assertTrue(response.data["image"].endswith(".jpg"))

    def test_image_url_that_is_not_a_raster_image_is_skipped(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        with mock.patch("recipes.serializers.fetch_image", return_value=(svg, "image/svg+xml")):
            response = self.create(image_url="https://example.com/photo.svg")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["image"])

    def test_attachments_only_keep_pdfs_and_images(self):
        recipe_id = self.create().data["id"]
        files = [
            SimpleUploadedFile("page.html", b"<script>alert(1)</script>", "text/html"),
            SimpleUploadedFile("a.pdf", samples.text_pdf(), "application/pdf"),
        ]
        response = self.client.post(f"/api/recipes/{recipe_id}/attachments/", {"file": files}, format="multipart")
        self.assertEqual([a["original_name"] for a in response.data], ["a.pdf"])

    def test_image_url_failure_still_saves(self):
        with mock.patch("recipes.serializers.fetch_image", side_effect=ImportFailed("nope")):
            response = self.create(image_url="https://example.com/photo.jpg")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["image"])

    def test_attachments(self):
        recipe_id = self.create().data["id"]
        files = [SimpleUploadedFile("a.pdf", samples.text_pdf(), "application/pdf")]
        response = self.client.post(f"/api/recipes/{recipe_id}/attachments/", {"file": files}, format="multipart")
        self.assertEqual(response.status_code, 201)
        attachment_id = response.data[0]["id"]
        self.assertEqual(response.data[0]["original_name"], "a.pdf")
        detail = self.client.get(f"/api/recipes/{recipe_id}/")
        self.assertEqual(len(detail.data["attachments"]), 1)
        self.assertEqual(self.client.delete(f"/api/recipes/{recipe_id}/attachments/{attachment_id}/").status_code, 204)
        self.assertFalse(Attachment.objects.exists())

    def test_delete_recipe(self):
        recipe_id = self.create().data["id"]
        self.assertEqual(self.client.delete(f"/api/recipes/{recipe_id}/").status_code, 204)
        self.assertFalse(Recipe.objects.exists())


@override_settings(RECIPE_LLM="off")
class ImportApiTests(APITestCase):
    def test_config(self):
        data = self.client.get("/api/import/config/").data
        self.assertFalse(data["llm_enabled"])
        self.assertIn("ocr_engine", data)

    def test_import_file(self):
        response = self.client.post(
            "/api/import/files/",
            {"files": [SimpleUploadedFile("r.pdf", samples.text_pdf(), "application/pdf")]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["draft"]["title"], samples.TITLE)
        self.assertEqual(response.data["method"], "pdf")

    def test_import_html(self):
        from .test_importers import JSON_LD_PAGE

        response = self.client.post(
            "/api/import/html/", {"url": "https://testkitchen.example/g", "html": JSON_LD_PAGE}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["method"], "browser")
        self.assertEqual(response.data["parser"], "schema.org")

    def test_import_errors_are_readable(self):
        response = self.client.post("/api/import/url/", {"url": "http://127.0.0.1/"}, format="json")
        self.assertEqual(response.status_code, 422)
        self.assertIn("private", response.data["detail"])
