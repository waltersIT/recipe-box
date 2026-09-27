"""Importing recipes from web pages.

Most recipe sites publish their recipes as schema.org "Recipe" structured data
(JSON-LD or microdata) so search engines can show recipe cards. We read that
first via the recipe-scrapers library, which also has tuned parsers for
hundreds of popular sites. Pages without it are reduced to their main text
and parsed by Claude (if configured) or the rule-based text parser.
"""

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from recipe_scrapers import scrape_html

from . import llm
from .draft import ImportFailed, ImportResult, RecipeDraft
from .durations import parse_duration
from .fetch import fetch_html, normalize_url
from .layout import text_to_lines
from .text_parser import parse_recipe_text

log = logging.getLogger(__name__)

MAX_LLM_TEXT_CHARS = 100_000

_BLOCK_TAGS = [
    "p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table",
    "section", "article", "header", "blockquote", "dd", "dt", "figcaption", "pre",
]
_RECIPE_CARD_SELECTORS = ", ".join(
    [
        ".wprm-recipe-container",
        ".tasty-recipes",
        ".mv-create-card",
        ".recipe-card",
        "[itemtype*='schema.org/Recipe']",
        "[class*='recipe-card']",
    ]
)


def import_from_url(raw_url: str) -> ImportResult:
    url = normalize_url(raw_url)
    page = fetch_html(url)
    return import_from_html(page.html, page.url, method="url")


def import_from_html(html: str, url: str, method: str = "browser") -> ImportResult:
    if not html or not html.strip():
        raise ImportFailed("The page was empty.")
    url = normalize_url(url)
    soup = BeautifulSoup(html, "lxml")

    draft = _from_structured_data(html, url)
    parser, warnings = "schema.org", []
    if draft is None or draft.is_empty():
        draft, parser, warnings = _from_page_text(soup, url)

    _fill_from_page(draft, soup, url)
    if draft.is_empty():
        raise ImportFailed(
            "Couldn't find a recipe on that page. If the recipe is there, save the page "
            "as a PDF or take a screenshot and import that instead."
        )
    return ImportResult(draft=draft, method=method, parser=parser, warnings=warnings)


# --- schema.org ---------------------------------------------------------------


def _safe(getter, default=None):
    try:
        value = getter()
    except Exception:
        return default
    return default if value in (None, "", [], {}) else value


def _clean_item(text) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return re.sub(r"^[▢□☐•·\-*]+\s*", "", text).strip()


def _nutrient_label(key: str) -> str:
    key = re.sub(r"Content$", "", key)
    return re.sub(r"(?<!^)(?=[A-Z])", " ", key).strip().title()


def _from_structured_data(html: str, url: str) -> RecipeDraft | None:
    try:
        scraper = scrape_html(html, org_url=url, supported_only=False)
    except Exception:
        return None

    ingredients: list[str] = []
    groups = _safe(scraper.ingredient_groups, [])
    if len(groups) > 1 or (groups and groups[0].purpose):
        for group in groups:
            if group.purpose:
                ingredients.append("# " + _clean_item(group.purpose))
            ingredients.extend(_clean_item(i) for i in group.ingredients)
    else:
        ingredients = [_clean_item(i) for i in _safe(scraper.ingredients, [])]

    instructions = [_clean_item(s) for s in _safe(scraper.instructions_list, [])]
    if not instructions:
        instructions = [_clean_item(s) for s in (_safe(scraper.instructions, "") or "").split("\n")]

    tags: list[str] = []
    for value in (_safe(scraper.category, ""), _safe(scraper.cuisine, "")):
        for name in str(value).split(","):
            name = name.strip()
            if name and len(name) <= 40 and name.lower() not in {t.lower() for t in tags}:
                tags.append(name)

    nutrition = {}
    for key, value in (_safe(scraper.nutrients, {}) or {}).items():
        if key.lower() != "servingsize" and value:
            nutrition[_nutrient_label(key)] = str(value)

    image = _safe(scraper.image, "")
    return RecipeDraft(
        title=_clean_item(_safe(scraper.title, "")),
        description=(_safe(scraper.description, "") or "").strip(),
        ingredients=[i for i in ingredients if i],
        instructions=[s for s in instructions if s],
        servings=_clean_item(_safe(scraper.yields, "")),
        prep_time=parse_duration(_safe(scraper.prep_time)),
        cook_time=parse_duration(_safe(scraper.cook_time)),
        total_time=parse_duration(_safe(scraper.total_time)),
        source_url=_safe(scraper.canonical_url, "") or url,
        source_name=_clean_item(_safe(scraper.site_name, "")),
        author=_clean_item(_safe(scraper.author, "")),
        image_url=urljoin(url, image) if image else "",
        tags=tags[:5],
        nutrition=nutrition,
    )


# --- plain page text ----------------------------------------------------------


def page_text(soup: BeautifulSoup) -> str:
    """Visible text of the page's main content, one block element per line."""
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "aside",
                     "form", "button", "template", "select", "input"]):
        tag.decompose()
    root = (
        soup.select_one(_RECIPE_CARD_SELECTORS)
        or soup.find("article")
        or soup.find("main")
        or soup.body
        or soup
    )
    for br in root.find_all("br"):
        br.replace_with("\n")
    for element in root.find_all(_BLOCK_TAGS):
        element.insert_before("\n")
        element.insert_after("\n")
    lines = [re.sub(r"[ \t\r\f\v\xa0]+", " ", line).strip() for line in root.get_text().split("\n")]
    text, blank = [], False
    for line in lines:
        if line:
            if blank and text:
                text.append("")
            text.append(line)
            blank = False
        else:
            blank = True
    return "\n".join(text)


def _from_page_text(soup: BeautifulSoup, url: str) -> tuple[RecipeDraft, str, list[str]]:
    heading = soup.find("h1")
    heading_text = heading.get_text(" ", strip=True) if heading else ""
    text = page_text(soup)
    if not text.strip():
        raise ImportFailed("That page doesn't have any readable text.")

    warnings: list[str] = []
    if llm.llm_enabled():
        try:
            clipped = text[:MAX_LLM_TEXT_CHARS]
            draft = llm.extract_from_text(clipped, url)
            if len(text) > MAX_LLM_TEXT_CHARS:
                warnings.append("The page was very long, so only the first part was read. Check the recipe is complete.")
            return draft, "claude", warnings
        except llm.LLMFailed as exc:
            warnings.append(f"Claude couldn't read the page ({exc}), so the basic text parser was used instead.")

    draft, parse_warnings = parse_recipe_text(text_to_lines(text))
    if heading_text and len(heading_text) <= 200:
        draft.title = heading_text
    warnings.insert(
        0,
        "This page doesn't publish structured recipe data, so it was read as plain text. "
        "Check the ingredients and steps before saving.",
    )
    return draft, "text", warnings + [w for w in parse_warnings if "title" not in w or not draft.title]


def _meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def _fill_from_page(draft: RecipeDraft, soup: BeautifulSoup, url: str) -> None:
    draft.source_url = draft.source_url or url
    if not draft.source_name:
        host = urlparse(draft.source_url).hostname or ""
        draft.source_name = _meta(soup, "og:site_name") or re.sub(r"^www\.", "", host)
    if not draft.image_url:
        image = _meta(soup, "og:image", "twitter:image")
        draft.image_url = urljoin(url, image) if image else ""
    if not draft.title:
        draft.title = _meta(soup, "og:title") or (soup.title.get_text(strip=True) if soup.title else "")
