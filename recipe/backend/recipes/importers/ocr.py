"""On-device text recognition for screenshots, photos and scanned PDFs.

Uses Apple's Vision framework on macOS (fast, accurate, nothing to install).
Elsewhere it falls back to the `tesseract` command if it's installed.
"""

import csv
import functools
import io
import platform
import shutil
import subprocess

from PIL import Image

from .draft import ImportFailed
from .layout import TextBox

# Very tall images (full-page screenshots) are recognised in slices so the
# text isn't shrunk into illegibility; slices overlap so no line is cut in two.
_SLICE_RATIO = 2.0
_SLICE_OVERLAP = 0.15


@functools.cache
def _vision_available() -> bool:
    if platform.system() != "Darwin":
        return False
    try:
        from ocrmac import ocrmac  # noqa: F401
    except Exception:
        return False
    return True


def engine_name() -> str | None:
    if _vision_available():
        return "Apple Vision"
    if shutil.which("tesseract"):
        return "Tesseract"
    return None


def ocr_image(image: Image.Image) -> list[TextBox]:
    """Recognise text in an image. Box coordinates are pixels, top-left origin."""
    engine = engine_name()
    if engine is None:
        raise ImportFailed(
            "No text recognition is available on this computer. Install Tesseract "
            "(`brew install tesseract` on a Mac, `apt install tesseract-ocr` on Ubuntu) or add an "
            "Anthropic API key to use Claude."
        )
    recognise = _vision if engine == "Apple Vision" else _tesseract
    image = image.convert("RGB")
    width, height = image.size
    if height <= width * _SLICE_RATIO:
        return recognise(image)

    slice_height = int(width * _SLICE_RATIO)
    overlap = int(slice_height * _SLICE_OVERLAP)
    boxes: list[TextBox] = []
    top = 0
    while top < height:
        bottom = min(height, top + slice_height)
        # Each slice "owns" the middle of the overlap on either side.
        own_top = top + overlap / 2 if top else 0
        own_bottom = bottom - overlap / 2 if bottom < height else height
        for box in recognise(image.crop((0, top, width, bottom))):
            box.y0 += top
            box.y1 += top
            if own_top <= box.cy < own_bottom:
                boxes.append(box)
        if bottom >= height:
            break
        top = bottom - overlap
    return boxes


def _vision(image: Image.Image) -> list[TextBox]:
    from ocrmac import ocrmac

    width, height = image.size
    boxes = []
    for text, confidence, (x, y, w, h) in ocrmac.text_from_image(image, recognition_level="accurate"):
        if confidence < 0.3 or not text.strip():
            continue
        # Vision uses normalised coordinates with a bottom-left origin.
        boxes.append(
            TextBox(
                text=text,
                x0=x * width,
                x1=(x + w) * width,
                y0=(1 - y - h) * height,
                y1=(1 - y) * height,
            )
        )
    return boxes


def _tesseract(image: Image.Image) -> list[TextBox]:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    try:
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "tsv"],
            input=buffer.getvalue(),
            capture_output=True,
            timeout=120,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        raise ImportFailed("Text recognition (Tesseract) failed on this image.")

    words: dict[tuple, list] = {}
    reader = csv.DictReader(
        io.StringIO(result.stdout.decode("utf-8", "replace")), delimiter="\t", quoting=csv.QUOTE_NONE
    )
    for row in reader:
        text = (row.get("text") or "").strip()
        if row.get("level") != "5" or not text:
            continue
        try:
            if float(row.get("conf") or -1) < 30:
                continue
            left, top = int(row["left"]), int(row["top"])
            right, bottom = left + int(row["width"]), top + int(row["height"])
        except (TypeError, ValueError):
            continue
        key = (row["block_num"], row["par_num"], row["line_num"])
        words.setdefault(key, []).append((left, top, right, bottom, text))

    boxes = []
    for line in words.values():
        line.sort()
        boxes.append(
            TextBox(
                text=" ".join(w[4] for w in line),
                x0=min(w[0] for w in line),
                y0=min(w[1] for w in line),
                x1=max(w[2] for w in line),
                y1=max(w[3] for w in line),
            )
        )
    return boxes
