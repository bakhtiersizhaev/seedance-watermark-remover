#!/usr/bin/env python3
# ruff: noqa: E501
"""Generate project icon assets from the canonical SVG design contract.

The PNG/ICO renderer uses Pillow drawing primitives so the asset pipeline works on a
plain Windows Python environment without native Cairo/ImageMagick dependencies.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
DOCS_ASSETS = ROOT / "docs" / "assets"
PNG_SIZES = [16, 32, 48, 64, 128, 256, 512]
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
SVG_NAME = "seedance-cleaner-icon.svg"

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" role="img" aria-labelledby="title desc">
  <title id="title">Seedance Watermark Remover icon</title>
  <desc id="desc">A minimal dark app mark with a clean video frame and removal spark.</desc>
  <defs>
    <linearGradient id="bg" x1="42" y1="20" x2="218" y2="236" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#182433"/>
      <stop offset="0.52" stop-color="#0c1118"/>
      <stop offset="1" stop-color="#111827"/>
    </linearGradient>
    <linearGradient id="accent" x1="72" y1="70" x2="190" y2="188" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#8ee8ff"/>
      <stop offset="0.5" stop-color="#58a6ff"/>
      <stop offset="1" stop-color="#7c5cff"/>
    </linearGradient>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="150%">
      <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#020817" flood-opacity="0.45"/>
    </filter>
  </defs>
  <rect width="256" height="256" rx="58" fill="url(#bg)"/>
  <path d="M42 74c0-18.8 15.2-34 34-34h104c18.8 0 34 15.2 34 34v108c0 18.8-15.2 34-34 34H76c-18.8 0-34-15.2-34-34V74Z" fill="#121a25" filter="url(#softShadow)"/>
  <path d="M60 84c0-13.3 10.7-24 24-24h88c13.3 0 24 10.7 24 24v84c0 13.3-10.7 24-24 24H84c-13.3 0-24-10.7-24-24V84Z" fill="#0b1118" stroke="#2b3a4d" stroke-width="4"/>
  <path d="M83 94h62" stroke="#304257" stroke-width="10" stroke-linecap="round" opacity="0.8"/>
  <path d="M83 124h90" stroke="#253448" stroke-width="10" stroke-linecap="round" opacity="0.72"/>
  <path d="M83 154h54" stroke="#253448" stroke-width="10" stroke-linecap="round" opacity="0.72"/>
  <path d="M161 88l8.6 26.4L197 123l-27.4 8.6L161 158l-8.6-26.4L125 123l27.4-8.6L161 88Z" fill="url(#accent)"/>
  <path d="M172 62l3.8 11.8L188 78l-12.2 4.2L172 94l-3.8-11.8L156 78l12.2-4.2L172 62Z" fill="#d8f7ff" opacity="0.95"/>
  <path d="M60 171c33-18 69-20 136-7v8c0 11-9 20-20 20H80c-11 0-20-9-20-20v-1Z" fill="url(#accent)" opacity="0.16"/>
</svg>
"""


def lerp(a: int, b: int, amount: float) -> int:
    return int(a + (b - a) * amount)


def gradient_rect(size: int, start: tuple[int, int, int], end: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            amount = (x + y) / (2 * size)
            pixels[x, y] = tuple(lerp(start[index], end[index], amount) for index in range(3)) + (255,)
    return img


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def draw_star(
    draw: ImageDraw.ImageDraw,
    center_x: float,
    center_y: float,
    outer: float,
    inner: float,
    fill: tuple[int, int, int, int],
) -> None:
    points = []
    for index in range(8):
        angle = -math.pi / 2 + index * math.pi / 4
        radius = outer if index % 2 == 0 else inner
        points.append((center_x + math.cos(angle) * radius, center_y + math.sin(angle) * radius))
    draw.polygon(points, fill=fill)


def make_icon(size: int) -> Image.Image:
    scale = size / 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.alpha_composite(gradient_rect(size, (24, 36, 51), (13, 17, 24)))
    img.putalpha(rounded_mask(size, int(58 * scale)))

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        tuple(int(value * scale) for value in (42, 48, 214, 220)),
        radius=int(34 * scale),
        fill=(2, 8, 23, 118),
    )
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(1, int(12 * scale)))))

    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        tuple(int(value * scale) for value in (42, 40, 214, 216)),
        radius=int(34 * scale),
        fill=(18, 26, 37, 255),
    )
    draw.rounded_rectangle(
        tuple(int(value * scale) for value in (60, 60, 196, 192)),
        radius=int(24 * scale),
        fill=(11, 17, 24, 255),
        outline=(43, 58, 77, 255),
        width=max(1, int(4 * scale)),
    )
    for y, x2, alpha in [(94, 145, 210), (124, 173, 180), (154, 137, 180)]:
        draw.line(
            tuple(int(value * scale) for value in (83, y, x2, y)),
            fill=(48, 66, 87, alpha),
            width=max(2, int(10 * scale)),
        )
    draw_star(draw, 161 * scale, 123 * scale, 36 * scale, 10 * scale, (88, 166, 255, 255))
    draw_star(draw, 172 * scale, 78 * scale, 17 * scale, 5 * scale, (216, 247, 255, 245))
    return img


def generate() -> None:
    ASSETS.mkdir(exist_ok=True)
    DOCS_ASSETS.mkdir(parents=True, exist_ok=True)

    svg_path = ASSETS / SVG_NAME
    svg_path.write_text(ICON_SVG, encoding="utf-8")
    (DOCS_ASSETS / "icon.svg").write_text(ICON_SVG, encoding="utf-8")

    for size in PNG_SIZES:
        make_icon(size).save(ASSETS / f"seedance-cleaner-icon-{size}.png")

    make_icon(256).save(DOCS_ASSETS / "icon.png")
    Image.open(ASSETS / "seedance-cleaner-icon-256.png").save(ASSETS / "seedance-cleaner.ico", sizes=ICO_SIZES)


if __name__ == "__main__":
    generate()
