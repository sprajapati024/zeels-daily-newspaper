"""Kindle-safe cover validation, shared by ``cover_tool.py`` (which produces
covers) and ``newspaper_epub_builder.py`` (which hard-fails on a bad one).

"Kindle-safe grayscale" here means the same thing the approved prototype
cover (`shirins-brief-cover-kindle.jpg`) is: a *baseline* JPEG, stored as
RGB (Kindle's cover pipeline is fussy about true single-channel JPEGs), but
with every pixel's R, G and B channels equal -- i.e. visually grayscale.
"""
from __future__ import annotations

import io

from PIL import Image, ImageChops

MAX_COVER_BYTES = 250 * 1024

TARGET_WIDTH = 600
TARGET_HEIGHT = 800
# "600x800-ish": tolerate covers that are close but not pixel-exact.
MIN_WIDTH, MAX_WIDTH = 560, 640
MIN_HEIGHT, MAX_HEIGHT = 760, 840

_SOF_BASELINE = 0xC0
_SOF_PROGRESSIVE = {0xC2, 0xC6, 0xCA, 0xCE}
_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
_STANDALONE_MARKERS = {0xD8, 0xD9, 0x01} | set(range(0xD0, 0xD8))


class CoverImageError(ValueError):
    """Raised when a cover image fails Kindle-safety validation."""


def _find_sof_marker(data: bytes) -> int | None:
    """Return the SOF marker byte (e.g. 0xC0 for baseline) or None if absent."""
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    n = len(data)
    while i + 1 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in _STANDALONE_MARKERS:
            i += 2
            continue
        if i + 3 >= n:
            break
        seg_len = (data[i + 2] << 8) + data[i + 3]
        if marker in _SOF_MARKERS:
            return marker
        i += 2 + seg_len
    return None


def is_baseline_jpeg(data: bytes) -> bool:
    return _find_sof_marker(data) == _SOF_BASELINE


def _is_visually_grayscale(im: Image.Image) -> bool:
    rgb = im.convert("RGB")
    r, g, b = rgb.split()
    return ImageChops.difference(r, g).getbbox() is None and ImageChops.difference(g, b).getbbox() is None


def validate_cover_jpeg(data: bytes) -> None:
    """Hard-fail (raise :class:`CoverImageError`) unless ``data`` is a
    Kindle-safe cover: baseline JPEG, ~600x800, visually grayscale, and no
    larger than :data:`MAX_COVER_BYTES`.
    """
    if len(data) > MAX_COVER_BYTES:
        raise CoverImageError(
            f"cover exceeds 250KB ({MAX_COVER_BYTES} bytes): {len(data)}"
        )
    if data[:2] != b"\xff\xd8":
        raise CoverImageError("cover is not a JPEG file (bad SOI marker)")

    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as exc:  # noqa: BLE001 - re-raised as a domain error
        raise CoverImageError(f"cover is not a decodable image: {exc}") from exc

    if im.format != "JPEG":
        raise CoverImageError(f"cover must be JPEG, got {im.format}")

    width, height = im.size
    if not (MIN_WIDTH <= width <= MAX_WIDTH and MIN_HEIGHT <= height <= MAX_HEIGHT):
        raise CoverImageError(
            f"cover size {width}x{height} is not ~{TARGET_WIDTH}x{TARGET_HEIGHT}"
        )

    if not _is_visually_grayscale(im):
        raise CoverImageError("cover must be grayscale (equal R/G/B channels)")

    sof = _find_sof_marker(data)
    if sof is None:
        raise CoverImageError("cover is missing a JPEG start-of-frame marker")
    if sof in _SOF_PROGRESSIVE:
        raise CoverImageError("cover must be a baseline JPEG, not progressive")
    if sof != _SOF_BASELINE:
        raise CoverImageError(f"cover must be a baseline sequential JPEG (SOF0), found marker 0x{sof:02X}")
