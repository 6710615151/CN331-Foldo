"""
Share Kit (FOLDO-17): the public URL of a version and a QR code for it.

The URL always comes from ``Portfolio.public_path``, the same route the public page
(``portfolios:public``) is served on, so the copied link, the QR code and the page
itself can never disagree. Nothing here changes a portfolio.
"""
from __future__ import annotations

import io

import segno

QR_DARK = "#0a1230"
QR_LIGHT = "#ffffff"

CONTENT_TYPES = {"png": "image/png", "svg": "image/svg+xml"}


def is_shareable(portfolio) -> bool:
    """Only a published version has a working public page, so only it gets a link and QR."""
    return bool(portfolio.is_published)


def public_url(portfolio, request) -> str:
    """The absolute URL anyone can open (when the version is published)."""
    return request.build_absolute_uri(portfolio.public_path)


def _qr(url: str):
    # "m" error correction survives a slightly dirty screen or print.
    return segno.make(url, error="m")


def qr_svg_inline(url: str, *, title: str) -> str:
    """
    A ``<svg>`` element for embedding in the page (no extra request).

    ``omitsize`` drops the fixed width/height so the SVG carries only a ``viewBox`` and
    scales to whatever box CSS gives it. With a fixed size and no viewBox, a smaller
    box would crop the code and make it unscannable.
    """
    return _qr(url).svg_inline(
        scale=1, border=2, dark=QR_DARK, light=QR_LIGHT, title=title, desc=f"QR code for {url}",
        omitsize=True,
    )


def qr_file(url: str, fmt: str) -> bytes:
    """The downloadable QR image: ``png`` (large, for print) or ``svg``."""
    if fmt not in CONTENT_TYPES:
        raise ValueError(f"Unsupported QR format: {fmt!r}")
    buffer = io.BytesIO()
    options = {"scale": 12, "border": 4, "dark": QR_DARK, "light": QR_LIGHT}
    _qr(url).save(buffer, kind=fmt, **options)
    return buffer.getvalue()


def download_name(portfolio, fmt: str) -> str:
    return f"{portfolio.slug}-qr.{fmt}"
