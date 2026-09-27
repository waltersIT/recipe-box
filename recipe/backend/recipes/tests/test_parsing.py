from django.test import SimpleTestCase

from recipes.importers.durations import format_minutes, parse_duration
from recipes.importers.layout import TextBox, boxes_to_lines, text_to_lines
from recipes.importers.text_parser import parse_recipe_text


class DurationTests(SimpleTestCase):
    def test_parses_common_formats(self):
        cases = {
            "PT1H30M": 90,
            "PT45M": 45,
            "P1DT2H": 1560,
            "1 hr 15 mins": 75,
            "1 hour and 30 minutes": 90,
            "1h30m": 90,
            "45 min": 45,
            "1 1/2 hours": 90,
            "1½ hours": 90,
            "20 to 25 minutes": 25,
            "10-12 mins": 12,
            "45": 45,
            30: 30,
        }
        for text, minutes in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_duration(text), minutes)

    def test_unparseable(self):
        for text in (None, "", "overnight", "PT0M", 0):
            with self.subTest(text=text):
                self.assertIsNone(parse_duration(text))

    def test_format(self):
        self.assertEqual(format_minutes(75), "1 hr 15 min")
        self.assertEqual(format_minutes(60), "1 hr")
        self.assertEqual(format_minutes(20), "20 min")
        self.assertEqual(format_minutes(None), "")


def parse(text):
    return parse_recipe_text(text_to_lines(text))


class TextParserTests(SimpleTestCase):
    def test_recipe_card_with_headings_and_metadata(self):
        draft, warnings = parse(
            """Chewy Brown Butter Cookies
            These cookies are rich, nutty and perfectly chewy.
            PREP TIME COOK TIME TOTAL TIME
            15 mins 12 mins 1 hr 27 mins
            Servings: 24 cookies
            Course: Dessert
            Ingredients
            1x 2x 3x
            ▢ 1 cup unsalted butter
            ▢ 2 1/4 cups all-purpose flour
            ▢ 2 large eggs, at room
            temperature
            Instructions
            Brown the butter and let it cool.
            Whisk the flour, then fold everything together.
            Notes
            Dough keeps for 3 days.
            Nutrition
            Calories: 180kcal | Protein: 2g
            """
        )
        self.assertEqual(draft.title, "Chewy Brown Butter Cookies")
        self.assertEqual(draft.description, "These cookies are rich, nutty and perfectly chewy.")
        self.assertEqual(
            draft.ingredients,
            ["1 cup unsalted butter", "2 1/4 cups all-purpose flour", "2 large eggs, at room temperature"],
        )
        self.assertEqual(len(draft.instructions), 2)
        self.assertEqual((draft.prep_time, draft.cook_time, draft.total_time), (15, 12, 87))
        self.assertEqual(draft.servings, "24 cookies")
        self.assertEqual(draft.tags, ["Dessert"])
        self.assertEqual(draft.notes, "Dough keeps for 3 days.")
        self.assertEqual(draft.nutrition, {"Calories": "180kcal", "Protein": "2g"})
        self.assertEqual(warnings, [])

    def test_no_headings_numbered_steps(self):
        draft, _ = parse(
            """Grandma's Tomato Soup
            Serves 4
            2 tbsp olive oil
            1 onion, diced
            salt and pepper to taste
            1. Heat the oil in a large pot and cook the onion until soft,
            about 8 minutes.
            2. Add the tomatoes and simmer for 20 minutes, then blend.
            """
        )
        self.assertEqual(draft.title, "Grandma's Tomato Soup")
        self.assertEqual(draft.servings, "4 servings")
        self.assertEqual(draft.ingredients, ["2 tbsp olive oil", "1 onion, diced", "salt and pepper to taste"])
        self.assertEqual(
            draft.instructions,
            [
                "Heat the oil in a large pot and cook the onion until soft, about 8 minutes.",
                "Add the tomatoes and simmer for 20 minutes, then blend.",
            ],
        )

    def test_sub_headings_and_step_labels(self):
        draft, _ = parse(
            """Lemon Layer Cake
            Prep Time: 30 minutes  Cook Time: 25 minutes  Serves 8
            Ingredients
            For the cake:
            2 cups flour
            For the frosting:
            8 oz cream cheese
            Directions
            Step 1
            Preheat the oven to 350F.
            Step 2
            Mix and bake 25 minutes.
            """
        )
        self.assertEqual(draft.ingredients, ["# For the cake", "2 cups flour", "# For the frosting", "8 oz cream cheese"])
        self.assertEqual(draft.instructions, ["Preheat the oven to 350F.", "Mix and bake 25 minutes."])
        self.assertEqual((draft.prep_time, draft.cook_time, draft.servings), (30, 25, "8 servings"))

    def test_drops_page_chrome(self):
        draft, _ = parse(
            """9:41
            example.com
            Pancakes
            ★★★★★ 4.8 from 120 votes
            Jump to Recipe
            Ingredients
            1 cup flour
            1 egg
            Instructions
            Mix and cook on a hot griddle.
            """
        )
        self.assertEqual(draft.title, "Pancakes")
        self.assertEqual(draft.description, "")
        self.assertEqual(draft.ingredients, ["1 cup flour", "1 egg"])

    def test_warns_when_nothing_found(self):
        draft, warnings = parse("Just a paragraph about my weekend.")
        self.assertTrue(draft.is_empty())
        self.assertTrue(any("ingredient" in w for w in warnings))

    def test_ocr_fixups(self):
        draft, _ = parse("Roast\nIngredients\n2 Ib potatoes\nl cup water\nInstructions\nRoast them.")
        self.assertEqual(draft.ingredients, ["2 lb potatoes", "1 cup water"])


class LayoutTests(SimpleTestCase):
    def box(self, text, x, y, width=200, height=20):
        return TextBox(text=text, x0=x, y0=y, x1=x + width, y1=y + height)

    def test_two_columns_read_left_then_right(self):
        boxes = [
            self.box("Big Title Across The Page", 10, 0, width=560, height=40),
            self.box("Ingredients", 10, 80),
            self.box("Instructions", 320, 80),
            self.box("1 cup flour", 10, 110),
            self.box("Mix everything together well.", 320, 110, width=250),
            self.box("2 eggs", 10, 140),
            self.box("Bake for twenty minutes.", 320, 140, width=250),
        ]
        texts = [line.text for line in boxes_to_lines(boxes)]
        self.assertEqual(
            texts,
            [
                "Big Title Across The Page",
                "Ingredients",
                "1 cup flour",
                "2 eggs",
                "Instructions",
                "Mix everything together well.",
                "Bake for twenty minutes.",
            ],
        )

    def test_quantity_table_is_not_split_into_columns(self):
        boxes = [
            self.box("2 cups", 10, 0, width=80),
            self.box("all-purpose flour", 200, 0),
            self.box("1 tsp", 10, 30, width=80),
            self.box("baking soda", 200, 30),
        ]
        self.assertEqual([l.text for l in boxes_to_lines(boxes)], ["2 cups all-purpose flour", "1 tsp baking soda"])

    def test_row_of_labels_above_a_list_is_not_a_column(self):
        boxes = [
            self.box("PREP TIME", 10, 0, width=100),
            self.box("TOTAL TIME", 400, 0, width=100),
            self.box("10 mins", 10, 25, width=100),
            self.box("40 mins", 400, 25, width=100),
        ] + [self.box(f"{n} cups flour", 10, 60 + n * 30, width=150) for n in range(1, 8)]
        texts = [l.text for l in boxes_to_lines(boxes)]
        self.assertEqual(texts[-1], "7 cups flour")
        self.assertLess(texts.index("40 mins"), texts.index("1 cups flour"))

    def test_title_uses_text_height(self):
        boxes = [
            self.box("Recipe Blog", 10, 0, height=15),
            self.box("Smoky Black Bean Chili", 10, 30, height=40),
            self.box("Ingredients", 10, 90),
            self.box("1 can black beans", 10, 120),
            self.box("2 tsp chili powder", 10, 150),
        ]
        draft, _ = parse_recipe_text(boxes_to_lines(boxes))
        self.assertEqual(draft.title, "Smoky Black Bean Chili")
