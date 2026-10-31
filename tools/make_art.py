"""Draws Rated Arr's TV banner and launcher icons: a film rating box on aged newsprint, set in Anton.

Usage: uv run --with pillow python tools/make_art.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app/src/main/res"
FONT = RES / "font/anton.ttf"
PAPER_TOP, PAPER_BOTTOM = (243, 234, 214), (233, 220, 192)
INK = (26, 17, 12)
RED = (193, 18, 31)
CREAM = (246, 238, 219)


def paper(width: int, height: int) -> Image.Image:
    """The newsprint: a light-to-aged gradient under a faint halftone dot screen."""
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        draw.line([(0, y), (width, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(PAPER_TOP, PAPER_BOTTOM)))
    dots = Image.new("L", (width, height), 0)
    pitch = max(6, width // 90)
    dot_draw = ImageDraw.Draw(dots)
    for y in range(0, height, pitch):
        for x in range((y // pitch % 2) * pitch // 2, width, pitch):
            dot_draw.ellipse([x, y, x + pitch * 0.35, y + pitch * 0.35], fill=22)
    image.paste(Image.new("RGB", (width, height), INK), (0, 0), dots)
    return image


def rating_box(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float]) -> None:
    """An ink frame with "RATED" reversed out of an ink bar, and "ARR" in red below it."""
    left, top, right, bottom = box
    height = bottom - top
    frame = height * 0.05
    draw.rectangle(box, fill=INK)
    draw.rectangle([left + frame, top + frame, right - frame, bottom - frame], fill=CREAM)
    bar_bottom = top + height * 0.32
    draw.rectangle([left, top, right, bar_bottom], fill=INK)
    _fit_text(draw, "RATED", (left + frame * 2, top, right - frame * 2, bar_bottom), CREAM, 0.72)
    _fit_text(draw, "ARR", (left + frame * 2, bar_bottom, right - frame * 2, bottom - frame), RED, 0.86)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, box: tuple[float, float, float, float], colour: tuple,
              share: float) -> None:
    """Centres text in box at the largest size that fills share of its height and still fits its width."""
    left, top, right, bottom = box
    size = (bottom - top) * share
    font = ImageFont.truetype(str(FONT), round(size))
    while font.getlength(text) > right - left and size > 8:
        size *= 0.95
        font = ImageFont.truetype(str(FONT), round(size))
    draw.text(((left + right) / 2, (top + bottom) / 2), text, font=font, fill=colour, anchor="mm")


def banner() -> None:
    scale = 2
    width, height = 640 * scale, 360 * scale
    image = paper(width, height)
    box_height = height * 0.74
    box_width = box_height * 1.25
    left, top = (width - box_width) / 2, (height - box_height) / 2
    rating_box(ImageDraw.Draw(image), (left, top, left + box_width, top + box_height))
    image.resize((640, 360), Image.LANCZOS).save(RES / "drawable-xhdpi/banner.png", optimize=True)


def icon(size: int, folder: str) -> None:
    scale = 4
    big = size * scale
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    margin = big * 0.06
    rating_box(ImageDraw.Draw(image), (margin, margin * 2.5, big - margin, big - margin * 2.5))
    (RES / folder).mkdir(parents=True, exist_ok=True)
    image.resize((size, size), Image.LANCZOS).save(RES / folder / "ic_launcher.png", optimize=True)


if __name__ == "__main__":
    banner()
    icon(96, "mipmap-xhdpi")
    icon(192, "mipmap-xxxhdpi")
    print("banner and icons written")
