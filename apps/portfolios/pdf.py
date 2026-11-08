"""
PDF export of a portfolio (FOLDO-11).

The PDF is the same HTML page the preview and public link show: it comes from
services.render_version_html, the single function every output goes through, and is
turned into a file with WeasyPrint. All rendering-app themes are built to print cleanly.

WeasyPrint needs system libraries (Pango). It is imported lazily so a machine without
them can still run the whole site; only the export button reports "not available".
"""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.contrib.staticfiles import finders

from .services import render_version_html

logger = logging.getLogger(__name__)

# Relative URLs in the page (/static/..., /media/...) are resolved against this fake host and
# served straight from disk by the fetcher below, so the server never has to call itself.
BASE_URL = "http://pdf.local/"
_BASE_HOST = urlparse(BASE_URL).netloc

# The only outside hosts the PDF renderer may contact (the page's web fonts).
ALLOWED_REMOTE_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com"}

# Page sizes offered on the export page (FOLDO-11). Anything else falls back to the default.
PAGE_SIZES = ("A4", "Letter")
DEFAULT_PAGE_SIZE = "A4"


def normalize_page_size(value) -> str:
    return value if value in PAGE_SIZES else DEFAULT_PAGE_SIZE


def print_css(page_size: str = DEFAULT_PAGE_SIZE) -> str:
    return f"""
@page {{ size: {normalize_page_size(page_size)}; margin: 10mm; }}
body.pf {{ background: #fff; }}
.pf-page {{ margin: 0; box-shadow: none; border-radius: 0; }}
"""


PRINT_CSS = print_css(DEFAULT_PAGE_SIZE)  # kept for code that imports it


class PdfUnavailable(Exception):
    """WeasyPrint or its system libraries are not installed on this machine."""


def _url_prefix(url_setting: str) -> str:
    return "/" + url_setting.strip("/") + "/"


def _local_file(path: str) -> Path | None:
    """Map a /static/ or /media/ URL path to a file on disk, or None if it isn't one we allow."""
    static_prefix = _url_prefix(settings.STATIC_URL)
    media_prefix = _url_prefix(settings.MEDIA_URL)

    if path.startswith(static_prefix):
        try:
            found = finders.find(path[len(static_prefix):])
        except Exception:  # e.g. a path that tries to escape the static folders
            return None
        if isinstance(found, (list, tuple)):
            found = found[0] if found else None
        return Path(found) if found else None

    if path.startswith(media_prefix):
        root = Path(settings.MEDIA_ROOT).resolve()
        candidate = (root / path[len(media_prefix):]).resolve()
        if candidate.is_file() and candidate.is_relative_to(root):
            return candidate
    return None


def _make_fetcher(default_fetcher):
    """Serve local files from disk; allow web fonts; block everything else."""

    def fetch(url, *args, **kwargs):
        parsed = urlparse(url)
        if parsed.scheme == "data":
            return default_fetcher(url, *args, **kwargs)
        if parsed.netloc == _BASE_HOST:
            path = _local_file(unquote(parsed.path))
            if path is None:
                raise ValueError(f"File not found: {url}")
            mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            return {"file_obj": open(path, "rb"), "mime_type": mime}
        if parsed.scheme in ("http", "https") and parsed.hostname in ALLOWED_REMOTE_HOSTS:
            return default_fetcher(url, *args, **kwargs)
        raise ValueError(f"Blocked resource: {url}")

    return fetch


def render_pdf(portfolio, *, request, page_size: str = DEFAULT_PAGE_SIZE) -> bytes:
    """Return the portfolio as PDF bytes. Raises PdfUnavailable if WeasyPrint can't be loaded."""
    try:
        from weasyprint import CSS, HTML, default_url_fetcher


    except (ImportError, OSError) as exc:  # OSError: Pango/GLib libraries missing
        raise PdfUnavailable(str(exc)) from exc

    # No owner toolbar and no noindex: the PDF is just the document itself.
    html = render_version_html(portfolio, request=request, preview=False, toolbar=False)

    document = HTML(string=html, base_url=BASE_URL, url_fetcher=_make_fetcher(default_url_fetcher))
    data = document.write_pdf(stylesheets=[CSS(string=print_css(page_size))])
    if not data.startswith(b"%PDF"):  # never hand out something that is not a PDF as a success
        raise RuntimeError("The PDF renderer returned no PDF data")
    return data
