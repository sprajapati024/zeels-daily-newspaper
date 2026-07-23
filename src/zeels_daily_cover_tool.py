#!/usr/bin/env python3
"""Zeel's Daily cover: monochrome abstract design elements over fresh MMX art.

Same Kindle-safe constraints as the Zeel's Daily cover helper, but the
overlay is composed of beautiful abstract design elements rather than a
traditional newspaper masthead. The resulting image is still converted to a
600x800 grayscale baseline JPEG under 250KB so Amazon's Personal Document
service ingests it without the PNG download stall we saw on the first
prototype.
"""
from __future__ import annotations

import argparse
import io
import math
import os
import random
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cover_image import MAX_COVER_BYTES, TARGET_HEIGHT, TARGET_WIDTH, validate_cover_jpeg

CANVAS_W, CANVAS_H = 1200, 1600
MASTHEAD_TITLE = "ZEEL'S DAILY"
DEFAULT_TAGLINE = "A PRIVATE MORNING DIGEST OF DESIGN"
DEFAULT_FOOTER = "SELECTED, WRITTEN AND DELIVERED FOR ZEEL BY HERMY"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

JPEG_QUALITY_LADDER = (90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30)


def _draw_centered(draw, text, font, canvas_width, y, *, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (canvas_width - (bbox[2] - bbox[0])) / 2
    draw.text((x, y), text, font=font, fill=fill)


def _encode_under_budget(rgb: Image.Image) -> bytes:
    data = b""
    for quality in JPEG_QUALITY_LADDER:
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=quality, optimize=True, progressive=False)
        data = buf.getvalue()
        if len(data) <= MAX_COVER_BYTES:
            return data
    return data


def _draw_concentric_arcs(draw, cx, cy, *, count, r_start, r_step, line_width, fill):
    for i in range(count):
        r = r_start + i * r_step
        for angle_deg in range(0, 180, 4):
            a0 = math.radians(angle_deg - 1.0)
            a1 = math.radians(angle_deg + 1.0)
            draw.arc(
                [(cx - r, cy - r), (cx + r, cy + r)],
                start=-math.degrees(a0),
                end=-math.degrees(a1),
                fill=fill,
                width=line_width,
            )


def _draw_grid_lines(draw, canvas_w, canvas_h, *, step, fill, width):
    for x in range(step, canvas_w, step):
        draw.line([(x, 0), (x, canvas_h)], fill=fill, width=width)
    for y in range(step, canvas_h, step):
        draw.line([(0, y), (canvas_w, y)], fill=fill, width=width)


def _draw_dotted_grid(draw, canvas_w, canvas_h, *, step, fill, radius=2):
    for x in range(step, canvas_w, step):
        for y in range(step, canvas_h, step):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _draw_type_columns(draw, fonts, *, x, y, width, line_height):
    body = ImageFont.truetype(fonts["serif"], 20)
    for offset in range(0, width, 6):
        for row in range(0, line_height, 8):
            draw.text((x + offset, y + row), "A", font=body, fill=30)


def _draw_isometric_blocks(draw, *, palette):
    for idx, (cx, cy, size) in enumerate([
        (220, 1280, 110),
        (440, 1240, 140),
        (700, 1300, 160),
        (960, 1240, 140),
    ]):
        shade = palette[idx % len(palette)]
        for i in range(size):
            draw.polygon([
                (cx, cy - size + i),
                (cx + size, cy - size // 2 + i),
                (cx, cy + i),
                (cx - size, cy - size // 2 + i),
            ], outline=shade, width=1)


def render_cover(
    art_bytes: bytes,
    *,
    day_label: str,
    volume: str,
    edition: str,
    seed: int,
    tagline: str = DEFAULT_TAGLINE,
    footer: str = DEFAULT_FOOTER,
) -> bytes:
    """Render Kindle-safe cover JPEG bytes for Zeel's Daily.

    Deterministic for a given (seed, day_label) pair so retries produce the
    same cover, while different days get genuinely different design
    compositions.
    """
    rng = random.Random(seed)
    canvas = Image.new("L", (CANVAS_W, CANVAS_H), 248)
    art = Image.open(io.BytesIO(art_bytes)).convert("L")
    art = ImageEnhance.Contrast(art).enhance(1.25)
    art = ImageOps.fit(art, (1080, 800), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    canvas.paste(art, (60, 80))

    d = ImageDraw.Draw(canvas)
    f_title = ImageFont.truetype(FONT_SERIF_BOLD, 96)
    f_tag = ImageFont.truetype(FONT_SERIF, 28)
    f_meta = ImageFont.truetype(FONT_SANS_BOLD, 22)
    f_small = ImageFont.truetype(FONT_SANS, 20)
    fonts = {"serif": FONT_SERIF, "sans": FONT_SANS}

    palette_grays = [10, 40, 70, 100, 130]
    rng.shuffle(palette_grays)

    style = rng.choice(["arcs", "grid", "isometric", "type-columns", "dots"])

    d.rectangle((60, 80, 1140, 880), outline=20, width=3)

    if style == "arcs":
        _draw_concentric_arcs(
            d,
            cx=600,
            cy=480,
            count=rng.randint(8, 14),
            r_start=rng.randint(140, 220),
            r_step=rng.randint(28, 42),
            line_width=rng.randint(1, 3),
            fill=rng.choice(palette_grays),
        )
    elif style == "grid":
        _draw_grid_lines(d, 1140, 880, step=rng.choice([28, 36, 44]), fill=rng.choice(palette_grays), width=1)
    elif style == "isometric":
        _draw_isometric_blocks(d, palette=palette_grays)
    elif style == "type-columns":
        for x in (170, 470, 770):
            _draw_type_columns(d, fonts, x=x, y=130, width=140, line_height=720)
    else:
        _draw_dotted_grid(d, 1140, 880, step=rng.choice([32, 44, 56]), fill=rng.choice(palette_grays))

    _draw_centered(d, MASTHEAD_TITLE, f_title, CANVAS_W, 940, fill=12)
    _draw_centered(d, tagline.upper(), f_tag, CANVAS_W, 1050, fill=35)

    d.line((82, 1110, 1118, 1110), fill=20, width=3)

    d.rectangle((60, 1130, 1140, 1180), fill=240)
    d.text((88, 1145), day_label.upper(), font=f_meta, fill=20)
    right = f"{volume.upper()}  ·  {edition.upper()}"
    rbox = d.textbbox((0, 0), right, font=f_small)
    d.text((1112 - (rbox[2] - rbox[0]), 1148), right, font=f_small, fill=20)

    accent_y = 1230
    for i in range(rng.randint(3, 6)):
        cx = rng.randint(120, 1080)
        cy = accent_y + rng.randint(-20, 20)
        r = rng.randint(18, 60)
        shade = rng.choice(palette_grays)
        if rng.random() < 0.5:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=shade, width=2)
        else:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=shade)

    d.rectangle((60, 1480, 1140, 1530), fill=18)
    _draw_centered(d, footer.upper(), f_small, CANVAS_W, 1491, fill=248)

    final_l = canvas.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    rgb = Image.merge("RGB", (final_l, final_l, final_l))

    jpeg_bytes = _encode_under_budget(rgb)
    validate_cover_jpeg(jpeg_bytes)
    return jpeg_bytes


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a Kindle-safe Zeel's Daily cover from existing artwork.")
    parser.add_argument("input_image", help="Path to source artwork (the output of `mmx image generate`).")
    parser.add_argument("--day-label", required=True)
    parser.add_argument("--volume", required=True)
    parser.add_argument("--edition", required=True)
    parser.add_argument("--seed", type=int, required=True, help="Integer seed that varies daily.")
    parser.add_argument("--tagline", default=DEFAULT_TAGLINE)
    parser.add_argument("--footer", default=DEFAULT_FOOTER)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    input_path = Path(args.input_image)
    try:
        art_bytes = input_path.read_bytes()
    except OSError as exc:
        print(f"zeels_daily_cover_tool: failed to read input image: {exc}", file=sys.stderr)
        return 1

    try:
        cover_bytes = render_cover(
            art_bytes,
            day_label=args.day_label,
            volume=args.volume,
            edition=args.edition,
            seed=args.seed,
            tagline=args.tagline,
            footer=args.footer,
        )
    except Exception as exc:
        print(f"zeels_daily_cover_tool: failed to render Kindle-safe cover: {exc}", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    try:
        _atomic_write(out_path, cover_bytes)
    except OSError as exc:
        print(f"zeels_daily_cover_tool: failed to write cover: {exc}", file=sys.stderr)
        return 1

    print(f"cover_written={out_path} bytes={len(cover_bytes)} style_seed={args.seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
