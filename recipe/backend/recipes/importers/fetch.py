"""Fetching recipe pages and images from the web.

One request per user action, with size limits, a timeout, and a guard that
refuses to connect to private/loopback addresses (so a pasted link can't be
used to poke at services on your own network).
"""

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings

from .draft import ImportFailed

MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_REDIRECTS = 5

_BLOCKED_MESSAGE = (
    "{host} didn't let the importer read this page (HTTP {status}). Many large recipe "
    "sites block requests that don't come from a real browser. Use the Recipe Box "
    "bookmarklet from that page instead, or save the page as a PDF and import that."
)


@dataclass
class FetchedPage:
    url: str
    html: str


def normalize_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        raise ImportFailed("Paste a link to a recipe.")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ImportFailed("That doesn't look like a web link.")
    return url


def _check_host(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ImportFailed("Only http and https links can be imported.")
    if settings.RECIPE_ALLOW_PRIVATE_URLS:
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ImportFailed(f"Couldn't find the website {parsed.hostname}. Check the link.")
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise ImportFailed("Links to local or private network addresses can't be imported.")


def _headers(accept: str) -> dict:
    return {
        "User-Agent": settings.RECIPE_FETCH_USER_AGENT,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    }


def _get(url: str, accept: str, max_bytes: int) -> tuple[requests.Response, bytes]:
    """GET with manual redirect handling so every hop passes the host check."""
    session = requests.Session()
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        _check_host(current)
        try:
            response = session.get(
                current,
                headers=_headers(accept),
                timeout=(5, settings.RECIPE_FETCH_TIMEOUT),
                allow_redirects=False,
                stream=True,
            )
        except requests.Timeout:
            raise ImportFailed("The website took too long to respond. Try again in a moment.")
        except requests.RequestException:
            raise ImportFailed("Couldn't connect to that website. Check the link and your connection.")

        if response.is_redirect and "location" in response.headers:
            current = urljoin(current, response.headers["location"])
            response.close()
            continue
        break
    else:
        raise ImportFailed("That link redirected too many times.")

    host = urlparse(current).hostname or "The website"
    status = response.status_code
    if status in (401, 402, 403, 406, 429, 451, 503):
        response.close()
        raise ImportFailed(_BLOCKED_MESSAGE.format(host=host, status=status))
    if status == 404:
        response.close()
        raise ImportFailed("That page wasn't found (HTTP 404). Check the link.")
    if status >= 400:
        response.close()
        raise ImportFailed(f"{host} returned an error (HTTP {status}).")

    chunks, size = [], 0
    for chunk in response.iter_content(64 * 1024):
        size += len(chunk)
        if size > max_bytes:
            response.close()
            raise ImportFailed("That page is too large to import.")
        chunks.append(chunk)
    response.url = current
    return response, b"".join(chunks)


def _decode_html(response: requests.Response, body: bytes) -> str:
    content_type = response.headers.get("content-type", "")
    match = re.search(r"charset=([\w-]+)", content_type, re.I)
    if not match:
        match = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4096], re.I)
    encoding = match.group(1) if match else "utf-8"
    if isinstance(encoding, bytes):
        encoding = encoding.decode("ascii", "ignore")
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def fetch_html(url: str) -> FetchedPage:
    response, body = _get(
        url,
        accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        max_bytes=MAX_HTML_BYTES,
    )
    content_type = response.headers.get("content-type", "").lower()
    if content_type.startswith("application/pdf"):
        raise ImportFailed("That link is a PDF. Download it and import it as a file instead.")
    if content_type.startswith("image/"):
        raise ImportFailed("That link is an image. Save it and import it as a file instead.")
    return FetchedPage(url=response.url, html=_decode_html(response, body))


def fetch_image(url: str) -> tuple[bytes, str]:
    """Download an image; returns (bytes, content_type)."""
    response, body = _get(url, accept="image/avif,image/webp,image/*,*/*;q=0.8", max_bytes=MAX_IMAGE_BYTES)
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        raise ImportFailed("The recipe's image link didn't return an image.")
    return body, content_type
