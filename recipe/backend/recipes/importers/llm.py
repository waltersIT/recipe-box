"""Optional recipe extraction with Claude.

When an Anthropic credential is configured, PDFs, screenshots and web pages
without structured recipe data are sent to Claude, which reads the layout the
way a person would and returns the recipe in a fixed JSON shape. Everything
here raises LLMFailed on any problem so callers can fall back to on-device
parsing.
"""

import base64
import io
import json
import logging
import os

import anthropic
from django.conf import settings
from PIL import Image, ImageOps

from .draft import RecipeDraft

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5"
# Anthropic's API accepts PDFs up to 32 MB per request (after base64 encoding).
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_IMAGE_BLOCKS = 20
_IMAGE_LONG_EDGE = 2000
_SLICE_RATIO = 2.0

SYSTEM_PROMPT = """\
You transcribe recipes from web pages, PDFs, and photos or screenshots into \
structured data for a personal recipe collection.

- Copy ingredient lines and instruction steps faithfully, keeping quantities, \
units and wording as written. Repair obvious scanning artifacts (a word split \
across lines, stray checkbox or bullet characters) but don't paraphrase.
- One ingredient per item. One step per item, without the step numbers.
- When ingredients or steps are grouped under sub-headings (like "For the \
sauce"), add the sub-heading as its own item starting with "# ".
- Don't add anything the source doesn't say. Leave text fields empty and \
times at 0 when they aren't stated.
- Ignore everything that isn't the recipe: navigation, ads, comments, \
ratings, share buttons, phone status bars and browser toolbars.
- Several images may be consecutive screenshots of one page with overlapping \
content. Merge them into one recipe without repeating lines.
- If there is no recipe, set found_recipe to false."""

RECIPE_SCHEMA = {
    "type": "object",
    "properties": {
        "found_recipe": {"type": "boolean"},
        "title": {"type": "string"},
        "description": {"type": "string", "description": "Short intro or summary, if the source has one."},
        "servings": {"type": "string", "description": "As written, e.g. '4 servings' or '12 cookies'."},
        "prep_time_minutes": {"type": "integer", "description": "0 if not stated."},
        "cook_time_minutes": {"type": "integer", "description": "0 if not stated."},
        "total_time_minutes": {"type": "integer", "description": "0 if not stated."},
        "ingredients": {"type": "array", "items": {"type": "string"}},
        "instructions": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string", "description": "Tips, substitutions, storage notes from the source."},
        "author": {"type": "string"},
        "source_name": {"type": "string", "description": "Website, publication or cookbook, if shown."},
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Course or cuisine categories the source states, e.g. 'Dessert'. At most 5.",
        },
    },
    "required": [
        "found_recipe", "title", "description", "servings", "prep_time_minutes",
        "cook_time_minutes", "total_time_minutes", "ingredients", "instructions",
        "notes", "author", "source_name", "tags",
    ],
    "additionalProperties": False,
}


class LLMFailed(Exception):
    pass


def llm_enabled() -> bool:
    mode = settings.RECIPE_LLM
    if mode == "off":
        return False
    if mode == "on":
        return True
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _image_blocks(image: Image.Image) -> list[dict]:
    """Encode an image for Claude, slicing very tall screenshots so text stays legible."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    slices = [image]
    if height > width * _SLICE_RATIO:
        step = int(width * 1.8)
        overlap = int(width * 0.2)
        slices = []
        top = 0
        while True:
            bottom = min(height, top + step + overlap)
            slices.append(image.crop((0, top, width, bottom)))
            if bottom >= height:
                break
            top += step
    blocks = []
    for piece in slices:
        piece.thumbnail((_IMAGE_LONG_EDGE, _IMAGE_LONG_EDGE))
        buffer = io.BytesIO()
        piece.save(buffer, format="JPEG", quality=88)
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(buffer.getvalue()).decode("ascii"),
                },
            }
        )
    return blocks


def _pdf_block(data: bytes) -> dict:
    if len(data) > MAX_PDF_BYTES:
        raise LLMFailed("the PDF is too large to send")
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.standard_b64encode(data).decode("ascii"),
        },
    }


def _extract(content: list[dict]) -> RecipeDraft:
    model = settings.RECIPE_LLM_MODEL
    extra = {}
    if model == DEFAULT_MODEL:
        # If Opus declines a request, let the API retry it on Anthropic's
        # recommended fallback model instead of failing the import.
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        client = anthropic.Anthropic(timeout=180.0, max_retries=2)
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            output_config={
                "effort": settings.RECIPE_LLM_EFFORT,
                "format": {"type": "json_schema", "schema": RECIPE_SCHEMA},
            },
            messages=[{"role": "user", "content": content}],
            **extra,
        )
    except anthropic.AuthenticationError:
        raise LLMFailed("the Anthropic API key was rejected")
    except anthropic.PermissionDeniedError:
        raise LLMFailed("the Anthropic API key isn't allowed to use this model")
    except anthropic.RateLimitError:
        raise LLMFailed("the Claude API is rate-limiting requests right now")
    except anthropic.BadRequestError as exc:
        log.warning("Claude rejected the request: %s", exc)
        raise LLMFailed("the Claude API couldn't read this input")
    except anthropic.APIStatusError as exc:
        raise LLMFailed(f"the Claude API returned an error ({exc.status_code})")
    except anthropic.APIConnectionError:
        raise LLMFailed("couldn't reach the Claude API")
    except Exception as exc:  # e.g. no credentials configured at all
        log.exception("Claude extraction failed")
        raise LLMFailed(str(exc) or exc.__class__.__name__)

    if response.stop_reason == "refusal":
        raise LLMFailed("Claude declined to process this input")
    if response.stop_reason == "max_tokens":
        raise LLMFailed("the recipe was too long to finish in one pass")
    text = next((block.text for block in response.content if block.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise LLMFailed("Claude's answer wasn't valid JSON")

    if not data.get("found_recipe", True):
        raise LLMFailed("Claude didn't find a recipe")

    def minutes(key):
        value = data.get(key) or 0
        return int(value) if isinstance(value, (int, float)) and value > 0 else None

    def strings(key):
        return [s.strip() for s in data.get(key) or [] if isinstance(s, str) and s.strip()]

    return RecipeDraft(
        title=(data.get("title") or "").strip(),
        description=(data.get("description") or "").strip(),
        ingredients=strings("ingredients"),
        instructions=strings("instructions"),
        notes=(data.get("notes") or "").strip(),
        servings=(data.get("servings") or "").strip(),
        prep_time=minutes("prep_time_minutes"),
        cook_time=minutes("cook_time_minutes"),
        total_time=minutes("total_time_minutes"),
        author=(data.get("author") or "").strip(),
        source_name=(data.get("source_name") or "").strip(),
        tags=strings("tags")[:5],
    )


def extract_from_text(text: str, url: str) -> RecipeDraft:
    content = [
        {
            "type": "text",
            "text": f"Extract the recipe from this web page ({url}).\n\n<page>\n{text}\n</page>",
        }
    ]
    return _extract(content)


def extract_from_files(files: list[tuple[str, bytes, Image.Image | None]]) -> RecipeDraft:
    """`files` is a list of (kind, raw bytes, PIL image or None) with kind "pdf" or "image"."""
    content: list[dict] = []
    for kind, data, image in files:
        if kind == "pdf":
            content.append(_pdf_block(data))
        else:
            content.extend(_image_blocks(image))
    if sum(1 for block in content if block["type"] == "image") > MAX_IMAGE_BLOCKS:
        raise LLMFailed("there are too many images to send at once")
    kinds = {kind for kind, _, _ in files}
    plural = len(files) > 1
    what = {frozenset({"pdf"}): "PDF", frozenset({"image"}): "image"}.get(frozenset(kinds), "file")
    content.append(
        {"type": "text", "text": f"Extract the recipe from {'these' if plural else 'this'} {what}{'s' if plural else ''}."}
    )
    return _extract(content)
