"""Lay manuscript text into approved pages and assemble the proof PDF."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import manuscript as ms  # noqa: E402


TARGET_SIZE = (2048, 1448)
TEXT_BLOCK_WIDTH_FRACTION = 0.32
TEXT_MARGIN_X_FRACTION = 0.05
MAX_TEXT_HEIGHT_FRACTION = 0.90
LINE_HEIGHT = 1.35

BODY_SIZE = 54
BODY_FLOOR = 40
TITLE_SIZE = 96
SUBTITLE_SIZE = 48
AUTHOR_SIZE = 40
DEDICATION_SIZE = 28
PAGE_NUMBER_SIZE = 28

BROWN = "#4A3426"
CREAM = "#FFFDF5"
READABILITY_FLOOR = 140

FONT_DIR = ms.REPO_ROOT / "assets" / "fonts"
REGULAR_FONT = FONT_DIR / "Andika-Regular.ttf"
BOLD_FONT = FONT_DIR / "Andika-Bold.ttf"

FINAL_LAYOUT_DIR = ms.PRODUCTION / "08_FINAL_LAYOUT"
LAYOUT_PAGES_DIR = FINAL_LAYOUT_DIR / "pages"
PROOF_PDF = FINAL_LAYOUT_DIR / "MJ_and_the_Wobbly_Days_proof.pdf"
CHANGE_LOG = ms.PRODUCTION / "09_NOTES" / "change_log.txt"


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _text_width(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont
) -> float:
    return draw.textlength(text, font=font)


def _wrap_source_line(
    draw: ImageDraw.ImageDraw,
    line: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    if line == "":
        return [""]

    wrapped: list[str] = []
    current = ""
    for word in line.split(" "):
        candidate = word if current == "" else f"{current} {word}"
        if current and _text_width(draw, candidate, font) > max_width:
            wrapped.append(current)
            current = word
        else:
            current = candidate
    wrapped.append(current)
    return wrapped


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for source_line in text.split("\n"):
        lines.extend(_wrap_source_line(draw, source_line, font, max_width))
    return lines


def _line_advance(font: ImageFont.FreeTypeFont) -> int:
    return math.ceil(font.size * LINE_HEIGHT)


def _measure_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
) -> tuple[float, int]:
    if not lines:
        return 0, 0
    width = max(_text_width(draw, line, font) for line in lines)
    height = _line_advance(font) * len(lines)
    return width, height


def _fit_body_text(
    draw: ImageDraw.ImageDraw,
    page: int,
    text: str,
    block_width: int,
    max_height: int,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    floor_result: tuple[ImageFont.FreeTypeFont, list[str], float, int] | None = None
    for size in range(BODY_SIZE, BODY_FLOOR - 1, -1):
        font = _font(REGULAR_FONT, size)
        lines = _wrap_text(draw, text, font, block_width)
        width, height = _measure_lines(draw, lines, font)
        if size == BODY_FLOOR:
            floor_result = (font, lines, width, height)
        if width <= block_width and height <= max_height:
            return font, lines, height

    assert floor_result is not None
    _, _, width, height = floor_result
    if height > max_height:
        raise ValueError(
            f"page {page:02d}: text overflows vertically at {BODY_FLOOR}px "
            f"({height}px > {max_height}px)"
        )
    raise ValueError(
        f"page {page:02d}: text overflows horizontally at {BODY_FLOOR}px "
        f"({width:.1f}px > {block_width}px)"
    )


def _title_floor(size: int) -> int:
    return round(size * BODY_FLOOR / BODY_SIZE)


def _fit_title_text(
    draw: ImageDraw.ImageDraw,
    page: int,
    text: str,
    block_width: int,
    max_height: int,
) -> tuple[list[tuple[ImageFont.FreeTypeFont, list[str]]], int]:
    parts = text.split("\n")
    if len(parts) != 4:
        raise ValueError(f"page {page:02d}: title page text must have exactly 4 lines")

    title_floor = _title_floor(TITLE_SIZE)
    floor_result: tuple[
        list[tuple[ImageFont.FreeTypeFont, list[str]]], float, int
    ] | None = None
    for title_size in range(TITLE_SIZE, title_floor - 1, -1):
        scale = title_size / TITLE_SIZE
        sizes = (
            title_size,
            max(_title_floor(SUBTITLE_SIZE), round(SUBTITLE_SIZE * scale)),
            max(_title_floor(AUTHOR_SIZE), round(AUTHOR_SIZE * scale)),
            max(_title_floor(DEDICATION_SIZE), round(DEDICATION_SIZE * scale)),
        )
        fonts = (
            _font(BOLD_FONT, sizes[0]),
            _font(REGULAR_FONT, sizes[1]),
            _font(REGULAR_FONT, sizes[2]),
            _font(REGULAR_FONT, sizes[3]),
        )
        sections = [
            (font, _wrap_source_line(draw, part, font, block_width))
            for font, part in zip(fonts, parts, strict=True)
        ]
        spacing = math.ceil(22 * scale)
        widths: list[float] = []
        height = spacing * (len(sections) - 1)
        for font, lines in sections:
            width, section_height = _measure_lines(draw, lines, font)
            widths.append(width)
            height += section_height
        width = max(widths)
        if title_size == title_floor:
            floor_result = (sections, width, height)
        if width <= block_width and height <= max_height:
            return sections, height

    assert floor_result is not None
    _, width, height = floor_result
    if height > max_height:
        raise ValueError(
            f"page {page:02d}: title text overflows vertically at proportional floor "
            f"({height}px > {max_height}px)"
        )
    raise ValueError(
        f"page {page:02d}: title text overflows horizontally at proportional floor "
        f"({width:.1f}px > {block_width}px)"
    )


def _text_block(
    page_image: Image.Image, side: str, text_height: int
) -> tuple[int, int, int, int]:
    width, height = page_image.size
    block_width = round(width * TEXT_BLOCK_WIDTH_FRACTION)
    margin_x = round(width * TEXT_MARGIN_X_FRACTION)
    if side == "left":
        x = margin_x
    elif side == "right":
        x = width - margin_x - block_width
    else:
        raise ValueError(f"unknown text_safe_side {side!r}")
    y = round((height - text_height) / 2)
    return x, y, block_width, text_height


def _mean_luminance(image: Image.Image, x: int, y: int, width: int, height: int) -> float:
    crop = image.crop((x, y, x + width, y + height)).convert("L")
    return float(ImageStat.Stat(crop).mean[0])


def _draw_body(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    lines: list[str],
    colour: str,
) -> None:
    advance = _line_advance(font)
    for idx, line in enumerate(lines):
        draw.text((x, y + idx * advance), line, font=font, fill=colour)


def _draw_title(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    sections: list[tuple[ImageFont.FreeTypeFont, list[str]]],
    colour: str,
) -> None:
    title_font = sections[0][0]
    spacing = math.ceil(22 * title_font.size / TITLE_SIZE)
    cursor_y = y
    for section_idx, (font, lines) in enumerate(sections):
        advance = _line_advance(font)
        if section_idx == 3:
            section_width = max(_text_width(draw, line, font) for line in lines)
            section_height = advance * len(lines)
            pad_x = 18
            pad_y = 10
            draw.rounded_rectangle(
                (
                    x - pad_x,
                    cursor_y - pad_y,
                    x + math.ceil(section_width) + pad_x,
                    cursor_y + section_height + pad_y,
                ),
                radius=16,
                fill=(255, 248, 232, 225),
            )
        for line in lines:
            draw.text((x, cursor_y), line, font=font, fill=colour)
            cursor_y += advance
        if section_idx != len(sections) - 1:
            cursor_y += spacing


def _draw_page_number(
    draw: ImageDraw.ImageDraw,
    page: int,
    image_size: tuple[int, int],
    colour: str,
) -> None:
    width, height = image_size
    margin = round(width * 0.03)
    text = str(page)
    font = _font(REGULAR_FONT, PAGE_NUMBER_SIZE)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = width - margin - text_width if page % 2 else margin
    y = height - margin - text_height
    draw.text((x, y), text, font=font, fill=colour)


def _append_change_log_notes(notes: list[str]) -> None:
    if not notes:
        return
    CHANGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    existing = CHANGE_LOG.read_text(encoding="utf-8") if CHANGE_LOG.exists() else ""
    with open(CHANGE_LOG, "a", encoding="utf-8") as f:
        for note in notes:
            if note not in existing:
                f.write(note + "\n")


def layout_page(spec: dict) -> tuple[Path, bool, float]:
    page = int(spec["page"])
    src = ms.APPROVED_DIR / f"page_{page:02d}.png"
    if not src.is_file():
        raise FileNotFoundError(f"page {page:02d}: missing approved image {src}")

    with Image.open(src) as opened:
        image = opened.convert("RGBA")
    if image.size != TARGET_SIZE:
        raise ValueError(f"page {page:02d}: expected {TARGET_SIZE}, got {image.size}")

    draw = ImageDraw.Draw(image)
    block_width = round(image.size[0] * TEXT_BLOCK_WIDTH_FRACTION)
    max_height = round(image.size[1] * MAX_TEXT_HEIGHT_FRACTION)

    if page == 1:
        title_sections, text_height = _fit_title_text(
            draw, page, spec["text"], block_width, max_height
        )
        body_font = None
        body_lines: list[str] | None = None
    else:
        body_font, body_lines, text_height = _fit_body_text(
            draw, page, spec["text"], block_width, max_height
        )
        title_sections = None

    x, y, block_width, text_height = _text_block(
        image, spec["text_safe_side"], text_height
    )
    mean_l = _mean_luminance(image, x, y, block_width, text_height)
    use_cream = mean_l < READABILITY_FLOOR
    colour = CREAM if use_cream else BROWN

    if page == 1:
        assert title_sections is not None
        _draw_title(draw, x, y, title_sections, colour)
    else:
        assert body_font is not None and body_lines is not None
        _draw_body(draw, x, y, body_font, body_lines, colour)
    _draw_page_number(draw, page, image.size, colour)

    dst = LAYOUT_PAGES_DIR / f"page_{page:02d}_layout.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(dst, format="PNG")
    return dst, use_cream, mean_l


def assemble_pdf(page_paths: list[Path]) -> None:
    images: list[Image.Image] = []
    try:
        for path in page_paths:
            images.append(Image.open(path).convert("RGB"))
        if not images:
            raise ValueError("no layout pages to assemble")
        first, rest = images[0], images[1:]
        PROOF_PDF.parent.mkdir(parents=True, exist_ok=True)
        first.save(PROOF_PDF, save_all=True, append_images=rest, resolution=250)
    finally:
        for image in images:
            image.close()


def main() -> int:
    page_paths: list[Path] = []
    cream_notes: list[str] = []
    cream_pages: list[int] = []

    for spec in ms.load_pages():
        page_path, use_cream, mean_l = layout_page(spec)
        page_paths.append(page_path)
        page = int(spec["page"])
        colour_name = "cream" if use_cream else "brown"
        print(
            f"page {page:02d}: {colour_name} text (mean L={mean_l:.1f}); "
            f"wrote {page_path.relative_to(ms.REPO_ROOT)}"
        )
        if use_cream:
            cream_pages.append(page)
            cream_notes.append(
                f"layout: page {page:02d} text rendered cream "
                f"(dark zone, mean L={mean_l:.1f})"
            )

    _append_change_log_notes(cream_notes)
    assemble_pdf(page_paths)
    print(f"proof: wrote {PROOF_PDF.relative_to(ms.REPO_ROOT)}")
    print(
        "cream fallback pages: "
        + (", ".join(f"{page:02d}" for page in cream_pages) if cream_pages else "none")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
