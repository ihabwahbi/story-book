"""Composite real cover typography onto approved text-free cover art."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import manuscript as ms  # noqa: E402


SIZE = (2048, 1448)
COVER_DIR = ms.PRODUCTION / "10_COVER"
FRONT_ART = COVER_DIR / "front_cover_art.png"
BACK_ART = COVER_DIR / "back_cover_art.png"
FRONT = COVER_DIR / "front_cover.png"
BACK = COVER_DIR / "back_cover.png"
PROOF = COVER_DIR / "MJ_and_the_Wobbly_Days_cover_proof.pdf"

FONT_DIR = ms.REPO_ROOT / "assets" / "fonts"
REGULAR = FONT_DIR / "Andika-Regular.ttf"
BOLD = FONT_DIR / "Andika-Bold.ttf"

BROWN = "#4A3426"
CREAM = "#FFF8E8"
PURPLE = "#7046A6"
TEAL = "#078D9B"
ORANGE = "#F47B20"
PINK = "#E94580"
YELLOW = "#F5B82E"
OUTER_SAFE_MARGIN = 60

FRONT_SUBTITLE = "A story about courage, difference, and living with MS"
AUTHOR = "Written by MJ Donnellan"
BACK_COPY = (
    "Imagine loving to run, jump, and dance…\n"
    "until one day your body feels a little wobbly.\n\n"
    "Join MJ on a brave and heartwarming journey as she learns what it means "
    "to live with MS—and discovers that even on wobbly days, you can still "
    "shine bright."
)
TAGLINE = (
    "To every wobbly day, there is courage.\n"
    "To every challenge, there is light."
)


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    width: int,
) -> list[str]:
    lines: list[str] = []
    for source in text.split("\n"):
        if source == "":
            lines.append("")
            continue
        current = ""
        for word in source.split():
            candidate = word if not current else f"{current} {word}"
            if current and draw.textlength(candidate, font=font) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    fill: str,
    spacing: float = 1.28,
    anchor: str | None = None,
    stroke_width: int = 0,
    stroke_fill: str | None = None,
) -> int:
    x, y = xy
    advance = math.ceil(font.size * spacing)
    for line in lines:
        if line:
            draw.text(
                (x, y),
                line,
                font=font,
                fill=fill,
                anchor=anchor,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
            )
        y += advance
    return y


def _draw_coloured_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    centre_x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    colours: tuple[str, ...],
    stroke_width: int = 7,
    max_width: int | None = None,
) -> None:
    widths = [draw.textlength(ch, font=font) for ch in text]
    total_width = sum(widths)
    if max_width is not None and total_width + 2 * stroke_width > max_width:
        raise ValueError(
            f"cover title overflows horizontally: {total_width:.1f}px > {max_width}px"
        )
    x = centre_x - round(total_width / 2)
    colour_idx = 0
    for ch, width in zip(text, widths, strict=True):
        colour = colours[colour_idx % len(colours)]
        if ch != " ":
            colour_idx += 1
        draw.text(
            (x, y),
            ch,
            font=font,
            fill=colour,
            stroke_width=stroke_width,
            stroke_fill="#FFFFFF",
        )
        x += width


def _load(path: Path) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"missing approved cover art: {path}")
    image = Image.open(path).convert("RGBA")
    if image.size != SIZE:
        raise ValueError(f"{path}: expected {SIZE}, got {image.size}")
    return image


def _require_outer_margin(rect: tuple[int, int, int, int], label: str) -> None:
    left, top, right, bottom = rect
    width, height = SIZE
    margins = (left, top, width - right, height - bottom)
    if min(margins) < OUTER_SAFE_MARGIN:
        raise ValueError(
            f"{label} violates {OUTER_SAFE_MARGIN}px outer safe margin: {margins}"
        )


def compose_front() -> Path:
    image = _load(FRONT_ART)
    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    panel = (70, 60, 1120, 1065)
    _require_outer_margin(panel, "front copy panel")
    odraw.rounded_rectangle(
        panel,
        radius=48,
        fill=(255, 248, 232, 232),
        outline=(255, 255, 255, 245),
        width=8,
    )
    image.alpha_composite(overlay)
    draw = ImageDraw.Draw(image)

    centre = (panel[0] + panel[2]) // 2
    _draw_coloured_centered(
        draw, "MJ", centre, 105, _font(BOLD, 180), (ORANGE, PURPLE), 9, 900
    )
    draw.text(
        (centre, 330),
        "and the",
        font=_font(BOLD, 58),
        fill=BROWN,
        anchor="ma",
    )
    _draw_coloured_centered(
        draw,
        "Wobbly Days",
        centre,
        425,
        _font(BOLD, 91),
        (TEAL, ORANGE, PURPLE, PINK, YELLOW),
        7,
        900,
    )

    subtitle_font = _font(REGULAR, 43)
    subtitle = _wrap(draw, FRONT_SUBTITLE, subtitle_font, 830)
    y = _draw_lines(draw, (centre, 610), subtitle, subtitle_font, BROWN, anchor="ma")
    if y + 150 > panel[3]:
        raise ValueError(f"front cover copy overflows panel: bottom {y + 150}")
    author_panel = (170, y + 35, 1020, y + 150)
    _require_outer_margin(author_panel, "front author panel")
    draw.rounded_rectangle(
        author_panel, radius=38, fill=PURPLE, outline="#FFFFFF", width=5
    )
    draw.text(
        (centre, y + 92),
        AUTHOR,
        font=_font(REGULAR, 38),
        fill="#FFFFFF",
        anchor="mm",
    )

    image.convert("RGB").save(FRONT, format="PNG", dpi=(250, 250))
    return FRONT


def compose_back() -> Path:
    image = _load(BACK_ART)
    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    panel = (75, 70, 1385, 1105)
    tagline_panel = (95, 1150, 1450, 1380)
    isbn_panel = (1580, 1190, 1970, 1380)
    _require_outer_margin(panel, "back copy panel")
    _require_outer_margin(tagline_panel, "back tagline panel")
    _require_outer_margin(isbn_panel, "back ISBN panel")
    odraw.rounded_rectangle(
        panel,
        radius=52,
        fill=(255, 248, 232, 235),
        outline=(255, 255, 255, 245),
        width=8,
    )
    odraw.rounded_rectangle(
        tagline_panel,
        radius=42,
        fill=(112, 70, 166, 235),
        outline=(255, 255, 255, 245),
        width=6,
    )
    odraw.rounded_rectangle(
        isbn_panel,
        radius=20,
        fill=(255, 255, 255, 245),
        outline=(74, 52, 38, 220),
        width=4,
    )
    image.alpha_composite(overlay)
    draw = ImageDraw.Draw(image)

    centre = (panel[0] + panel[2]) // 2
    _draw_coloured_centered(
        draw, "MJ and the Wobbly Days", centre, 125, _font(BOLD, 73),
        (ORANGE, PURPLE, TEAL, PINK, YELLOW), 5, 1160
    )

    copy_font = _font(REGULAR, 39)
    copy_lines = _wrap(draw, BACK_COPY, copy_font, 1110)
    copy_bottom = _draw_lines(
        draw, (165, 285), copy_lines, copy_font, BROWN, spacing=1.35
    )
    if copy_bottom > panel[3] - 45:
        raise ValueError(
            f"back cover synopsis overflows panel: bottom {copy_bottom}"
        )

    tagline_font = _font(BOLD, 35)
    tagline_lines = _wrap(draw, TAGLINE, tagline_font, 1180)
    tagline_bottom = _draw_lines(
        draw,
        (772, 1192),
        tagline_lines,
        tagline_font,
        "#FFFFFF",
        spacing=1.35,
        anchor="ma",
    )
    if tagline_bottom > 1360:
        raise ValueError(
            f"back cover tagline overflows panel: bottom {tagline_bottom}"
        )

    draw.text(
        (1775, 1285),
        "ISBN /\nbarcode area",
        font=_font(REGULAR, 28),
        fill=BROWN,
        anchor="mm",
        align="center",
    )

    image.convert("RGB").save(BACK, format="PNG", dpi=(250, 250))
    return BACK


def assemble_pdf(front: Path, back: Path) -> Path:
    first = Image.open(front).convert("RGB")
    second = Image.open(back).convert("RGB")
    try:
        first.save(PROOF, save_all=True, append_images=[second], resolution=250)
    finally:
        first.close()
        second.close()
    return PROOF


def main() -> int:
    front = compose_front()
    back = compose_back()
    proof = assemble_pdf(front, back)
    print(f"front: {front.relative_to(ms.REPO_ROOT)}")
    print(f"back: {back.relative_to(ms.REPO_ROOT)}")
    print(f"proof: {proof.relative_to(ms.REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
