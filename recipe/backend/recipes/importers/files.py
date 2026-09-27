"""Importing recipes from PDFs, screenshots and photos."""

import io
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError

from . import llm
from .draft import ImportFailed, ImportResult
from .layout import Line, boxes_to_lines
from .ocr import engine_name, ocr_image
from .pdf import pdf_to_lines
from .text_parser import is_junk, parse_recipe_text

try:  # iPhone photos are HEIC.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass


@dataclass
class SourceFile:
    name: str
    kind: str  # "pdf" | "image"
    data: bytes
    image: Image.Image | None = None


def load_upload(upload) -> SourceFile:
    name = getattr(upload, "name", "file")
    if upload.size > settings.RECIPE_MAX_UPLOAD_BYTES:
        limit = settings.RECIPE_MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ImportFailed(f"{name} is larger than {limit} MB.")
    data = upload.read()
    if b"%PDF-" in data[:1024]:
        return SourceFile(name=name, kind="pdf", data=data)
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise ImportFailed(f"{name} isn't a PDF or an image format that can be read.")
    return SourceFile(name=name, kind="image", data=data, image=ImageOps.exif_transpose(image))


def _normal(text: str) -> str:
    # OCR confuses these between screenshots ("2 Ib" vs "2lb"), so treat them as equal.
    text = text.lower().translate(str.maketrans({"|": "l", "!": "l", "1": "l", "i": "l", "0": "o"}))
    return re.sub(r"[^a-z0-9]+", "", text)


def _same(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 8 and SequenceMatcher(None, a, b).ratio() >= 0.9)


def _drop_overlap(previous: list[Line], current: list[Line]) -> list[Line]:
    """Remove lines at the top of a screenshot that repeat the end of the previous one."""
    prev = [_normal(l.text) for l in previous if not is_junk(l.text.strip())][-40:]
    content = [l for l in current if not is_junk(l.text.strip())]
    cur = [_normal(l.text) for l in content[:45]]
    # The first line or two of a screenshot can be cut off mid-glyph, so allow a small offset.
    for offset in range(0, 3):
        for size in range(min(len(prev), len(cur) - offset), 1, -1):
            if all(_same(a, b) for a, b in zip(prev[-size:], cur[offset : offset + size])):
                return content[offset + size :]
    return content


def _local_lines(sources: list[SourceFile]) -> tuple[list[Line], bool]:
    lines: list[Line] = []
    used_ocr = False
    previous_image_lines: list[Line] | None = None
    for source in sources:
        if source.kind == "pdf":
            page_lines, ocr_pages = pdf_to_lines(source.data, source.name)
            used_ocr = used_ocr or ocr_pages > 0
            lines.extend(page_lines)
            previous_image_lines = None
        else:
            image_lines = boxes_to_lines(ocr_image(source.image))
            used_ocr = True
            if previous_image_lines:
                image_lines = _drop_overlap(previous_image_lines, image_lines)
            lines.extend(image_lines)
            previous_image_lines = image_lines or previous_image_lines
    return lines, used_ocr


def import_from_files(uploads) -> ImportResult:
    if not uploads:
        raise ImportFailed("Choose a PDF, screenshot or photo to import.")
    if len(uploads) > settings.RECIPE_MAX_UPLOAD_FILES:
        raise ImportFailed(f"Import up to {settings.RECIPE_MAX_UPLOAD_FILES} files at a time.")
    sources = [load_upload(upload) for upload in uploads]
    method = "pdf" if any(s.kind == "pdf" for s in sources) else "image"
    warnings: list[str] = []

    if llm.llm_enabled():
        try:
            draft = llm.extract_from_files([(s.kind, s.data, s.image) for s in sources])
            if not draft.is_empty():
                return ImportResult(draft=draft, method=method, parser="claude", warnings=warnings)
            warnings.append("Claude didn't find a recipe, so on-device text recognition was used instead.")
        except llm.LLMFailed as exc:
            warnings.append(f"Claude couldn't process this ({exc}), so on-device text recognition was used instead.")

    if engine_name() is None and any(s.kind == "image" for s in sources):
        raise ImportFailed(
            "Reading screenshots needs text recognition. Install Tesseract "
            "(`brew install tesseract` on a Mac, `apt install tesseract-ocr` on Ubuntu) or add an "
            "Anthropic API key to use Claude."
        )

    lines, used_ocr = _local_lines(sources)
    if not lines:
        raise ImportFailed("Couldn't find any text in that file.")

    draft, parse_warnings = parse_recipe_text(lines)
    if draft.is_empty():
        # Hand the recognised text back rather than nothing, so it can be pasted into place.
        draft.notes = "\n".join(line.text for line in lines)
        parse_warnings = [
            "Couldn't work out the recipe's structure. All the recognised text is in Notes "
            "so you can move it into the right fields."
        ]
    if used_ocr:
        warnings.append("Read with on-device text recognition. Double-check quantities and fractions.")
    return ImportResult(draft=draft, method=method, parser="text", warnings=warnings + parse_warnings)
