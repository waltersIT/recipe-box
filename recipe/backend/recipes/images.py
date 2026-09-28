"""Turning an uploaded photo into something a browser can display."""

import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 15 * 1024 * 1024
WEB_IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}


class BadImage(Exception):
    """The upload isn't an image we can store; the message is shown to the user."""


def prepare_web_image(upload, max_bytes: int = MAX_IMAGE_BYTES):
    """Return `(content, extension)` ready for `ImageField.save()`.

    Formats browsers can't display (e.g. HEIC photos from an iPhone) are
    converted to JPEG, honouring the EXIF orientation.
    """
    if upload.size > max_bytes:
        raise BadImage(f"Images must be under {max_bytes // (1024 * 1024)} MB.")
    try:
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise BadImage("That file isn't an image.") from exc
    extension = WEB_IMAGE_FORMATS.get(image.format)
    if extension:
        upload.seek(0)
        return upload, extension
    buffer = io.BytesIO()
    ImageOps.exif_transpose(image).convert("RGB").save(buffer, format="JPEG", quality=90)
    return ContentFile(buffer.getvalue()), ".jpg"
