import json
from types import SimpleNamespace
from unittest import mock, skipUnless

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from recipes.importers import ImportFailed, import_from_files, import_from_html, import_from_url
from recipes.importers.fetch import FetchedPage, normalize_url
from recipes.importers.ocr import engine_name

from . import samples

JSON_LD_PAGE = """
<html><head>
<title>Test Kitchen</title>
<meta property="og:site_name" content="Test Kitchen">
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "WebPage", "name": "ignored"},
  {"@type": "Recipe",
   "name": "Sheet Pan Gnocchi",
   "description": "Crispy gnocchi with vegetables.",
   "image": ["/images/gnocchi.jpg"],
   "author": {"@type": "Person", "name": "Sam Cook"},
   "recipeYield": ["4", "4 servings"],
   "prepTime": "PT10M", "cookTime": "PT25M", "totalTime": "PT35M",
   "recipeCategory": "Dinner", "recipeCuisine": "Italian",
   "recipeIngredient": ["1 lb shelf-stable gnocchi", "1 pint cherry tomatoes", "2 tbsp olive oil"],
   "recipeInstructions": [
     {"@type": "HowToStep", "text": "Heat the oven to 450F."},
     {"@type": "HowToStep", "text": "Toss everything on a sheet pan and roast 25 minutes."}
   ],
   "nutrition": {"@type": "NutritionInformation", "calories": "320 kcal", "proteinContent": "8 g"}
  }
]}
</script></head>
<body><h1>Sheet Pan Gnocchi</h1><p>Story time...</p></body></html>
"""

PLAIN_PAGE = """
<html><head><title>Mom's Chili | A Family Blog</title></head><body>
<nav>Home About Recipes</nav>
<article>
  <h1>Mom's Chili</h1>
  <p>This is the chili we grew up on.</p>
  <h2>Ingredients</h2>
  <ul><li>1 lb ground beef</li><li>1 onion, <em>chopped</em></li><li>2 cans kidney beans</li></ul>
  <h2>Directions</h2>
  <ol><li>Brown the beef with the onion.</li><li>Add the beans and simmer for <strong>30 minutes</strong>.</li></ol>
</article>
<footer>Copyright</footer>
</body></html>
"""


def upload(name, data):
    return SimpleUploadedFile(name, data)


class UrlImportTests(SimpleTestCase):
    def test_normalize_url(self):
        self.assertEqual(normalize_url(" example.com/recipe "), "https://example.com/recipe")
        with self.assertRaises(ImportFailed):
            normalize_url("")
        with self.assertRaises(ImportFailed):
            normalize_url("ftp://example.com/file")

    def test_schema_org_recipe(self):
        result = import_from_html(JSON_LD_PAGE, "https://testkitchen.example/gnocchi", method="url")
        draft = result.draft
        self.assertEqual(result.parser, "schema.org")
        self.assertEqual(draft.title, "Sheet Pan Gnocchi")
        self.assertEqual(draft.ingredients, ["1 lb shelf-stable gnocchi", "1 pint cherry tomatoes", "2 tbsp olive oil"])
        self.assertEqual(len(draft.instructions), 2)
        self.assertEqual((draft.prep_time, draft.cook_time, draft.total_time), (10, 25, 35))
        self.assertEqual(draft.author, "Sam Cook")
        self.assertEqual(draft.image_url, "https://testkitchen.example/images/gnocchi.jpg")
        self.assertEqual(draft.tags, ["Dinner", "Italian"])
        self.assertEqual(draft.source_name, "Test Kitchen")
        self.assertEqual(draft.nutrition.get("Calories"), "320 kcal")
        self.assertEqual(draft.nutrition.get("Protein"), "8 g")

    @override_settings(RECIPE_LLM="off")
    def test_page_without_structured_data_falls_back_to_text(self):
        result = import_from_html(PLAIN_PAGE, "https://blog.example/chili")
        draft = result.draft
        self.assertEqual(result.parser, "text")
        self.assertEqual(result.method, "browser")
        self.assertEqual(draft.title, "Mom's Chili")
        self.assertEqual(draft.ingredients, ["1 lb ground beef", "1 onion, chopped", "2 cans kidney beans"])
        self.assertEqual(
            draft.instructions,
            ["Brown the beef with the onion.", "Add the beans and simmer for 30 minutes."],
        )
        self.assertEqual(draft.source_name, "blog.example")
        self.assertTrue(result.warnings)

    @override_settings(RECIPE_LLM="off")
    def test_page_without_a_recipe(self):
        with self.assertRaises(ImportFailed):
            import_from_html("<html><body><p>Hello there.</p></body></html>", "https://example.com")

    def test_import_from_url_uses_fetched_page(self):
        page = FetchedPage(url="https://testkitchen.example/gnocchi", html=JSON_LD_PAGE)
        with mock.patch("recipes.importers.url.fetch_html", return_value=page) as fetch:
            result = import_from_url("testkitchen.example/gnocchi")
        fetch.assert_called_once_with("https://testkitchen.example/gnocchi")
        self.assertEqual(result.method, "url")
        self.assertEqual(result.draft.title, "Sheet Pan Gnocchi")

    def test_private_addresses_are_refused(self):
        for url in ("http://127.0.0.1:8000/", "http://localhost/admin", "http://192.168.1.1/"):
            with self.subTest(url=url), self.assertRaises(ImportFailed):
                import_from_url(url)

    def test_blocked_site_message(self):
        response = mock.MagicMock(status_code=402, is_redirect=False, headers={})
        with mock.patch("recipes.importers.fetch._check_host"), mock.patch(
            "requests.Session.get", return_value=response
        ):
            with self.assertRaisesMessage(ImportFailed, "bookmarklet"):
                import_from_url("https://blocked.example/recipe")


@override_settings(RECIPE_LLM="off")
class FileImportTests(SimpleTestCase):
    def test_text_pdf_two_columns(self):
        result = import_from_files([upload("recipe.pdf", samples.text_pdf())])
        draft = result.draft
        self.assertEqual(result.method, "pdf")
        self.assertEqual(draft.title, samples.TITLE)
        self.assertEqual(draft.ingredients, samples.INGREDIENTS)
        self.assertEqual(len(draft.instructions), 3)
        self.assertTrue(draft.instructions[0].startswith("Season the chicken"))
        self.assertEqual((draft.prep_time, draft.cook_time, draft.servings), (15, 25, "4 servings"))

    def test_rejects_unknown_files(self):
        with self.assertRaises(ImportFailed):
            import_from_files([upload("notes.txt", b"just some text")])

    def test_requires_a_file(self):
        with self.assertRaises(ImportFailed):
            import_from_files([])

    @skipUnless(engine_name(), "no OCR engine on this machine")
    def test_screenshot_two_columns(self):
        result = import_from_files([upload("card.png", samples.image_bytes(samples.two_column_card()))])
        draft = result.draft
        self.assertEqual(result.method, "image")
        self.assertEqual(draft.title, samples.TITLE)
        self.assertEqual(draft.ingredients, samples.INGREDIENTS)
        self.assertEqual(len(draft.instructions), 3)

    @skipUnless(engine_name(), "no OCR engine on this machine")
    def test_scanned_pdf_uses_ocr(self):
        result = import_from_files([upload("scan.pdf", samples.scanned_pdf())])
        self.assertEqual(result.draft.ingredients, samples.INGREDIENTS)
        self.assertTrue(any("text recognition" in w for w in result.warnings))

    @skipUnless(engine_name(), "no OCR engine on this machine")
    def test_overlapping_phone_screenshots(self):
        shots = samples.phone_screenshots()
        result = import_from_files([upload(f"shot{i}.png", samples.image_bytes(s)) for i, s in enumerate(shots)])
        draft = result.draft
        self.assertEqual(draft.title, samples.TITLE)
        self.assertEqual(len(draft.ingredients), 6, draft.ingredients)
        self.assertIn("1/2 cup low-sodium chicken stock or dry white wine, at room temperature", draft.ingredients)
        self.assertEqual(len(draft.instructions), 3)
        self.assertEqual((draft.prep_time, draft.cook_time, draft.total_time), (15, 25, 40))
        self.assertEqual(draft.notes, "Leftovers keep for 3 days in the fridge.")


def fake_claude_response(payload, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
    )


CLAUDE_RECIPE = {
    "found_recipe": True, "title": "Claude Curry", "description": "", "servings": "4 servings",
    "prep_time_minutes": 15, "cook_time_minutes": 0, "total_time_minutes": 45,
    "ingredients": ["# For the paste", "2 shallots", ""], "instructions": ["Blend.", "Simmer."],
    "notes": "", "author": "", "source_name": "", "tags": ["Dinner"],
}


@override_settings(RECIPE_LLM="on", RECIPE_LLM_MODEL="claude-opus-5")
class ClaudeImportTests(SimpleTestCase):
    def patch_client(self, response=None, error=None):
        client = mock.MagicMock()
        if error:
            client.beta.messages.create.side_effect = error
        else:
            client.beta.messages.create.return_value = response
        return mock.patch("recipes.importers.llm.anthropic.Anthropic", return_value=client), client

    def test_files_are_sent_to_claude(self):
        patcher, client = self.patch_client(fake_claude_response(CLAUDE_RECIPE))
        with patcher:
            result = import_from_files([upload("a.pdf", samples.text_pdf())])
        self.assertEqual(result.parser, "claude")
        self.assertEqual(result.draft.title, "Claude Curry")
        self.assertEqual(result.draft.ingredients, ["# For the paste", "2 shallots"])
        self.assertEqual((result.draft.prep_time, result.draft.cook_time, result.draft.total_time), (15, None, 45))
        kwargs = client.beta.messages.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5")
        self.assertEqual(kwargs["fallbacks"], "default")
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")
        self.assertEqual([b["type"] for b in kwargs["messages"][0]["content"]], ["document", "text"])

    def test_tall_screenshots_are_sliced(self):
        patcher, client = self.patch_client(fake_claude_response(CLAUDE_RECIPE))
        from PIL import Image

        tall = Image.new("RGB", (400, 2000), "white")
        with patcher:
            import_from_files([upload("tall.png", samples.image_bytes(tall))])
        blocks = client.beta.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertGreater(sum(1 for b in blocks if b["type"] == "image"), 1)

    def test_falls_back_to_local_parsing_on_error(self):
        import anthropic

        error = anthropic.APIConnectionError(request=mock.MagicMock())
        patcher, _ = self.patch_client(error=error)
        with patcher:
            result = import_from_files([upload("a.pdf", samples.text_pdf())])
        self.assertEqual(result.parser, "text")
        self.assertEqual(result.draft.title, samples.TITLE)
        self.assertTrue(any("Claude couldn't" in w for w in result.warnings))

    def test_refusal_falls_back(self):
        patcher, _ = self.patch_client(fake_claude_response({}, stop_reason="refusal"))
        with patcher:
            result = import_from_files([upload("a.pdf", samples.text_pdf())])
        self.assertEqual(result.parser, "text")

    def test_pages_without_structured_data_use_claude(self):
        patcher, client = self.patch_client(fake_claude_response(CLAUDE_RECIPE))
        with patcher:
            result = import_from_html(PLAIN_PAGE, "https://blog.example/chili")
        self.assertEqual(result.parser, "claude")
        prompt = client.beta.messages.create.call_args.kwargs["messages"][0]["content"][0]["text"]
        self.assertIn("1 lb ground beef", prompt)
        self.assertNotIn("Copyright", prompt)

    def test_structured_data_skips_claude(self):
        patcher, client = self.patch_client(fake_claude_response(CLAUDE_RECIPE))
        with patcher:
            result = import_from_html(JSON_LD_PAGE, "https://testkitchen.example/gnocchi")
        self.assertEqual(result.parser, "schema.org")
        client.beta.messages.create.assert_not_called()
