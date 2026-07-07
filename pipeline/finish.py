"""Finish approved renders to the book's canonical page size."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import manuscript as ms  # noqa: E402
from pipeline import qa  # noqa: E402


TARGET_SIZE = (2048, 1448)
TARGET_RATIO = TARGET_SIZE[0] / TARGET_SIZE[1]
MAX_CROP_FRACTION = 0.08


def finish(src: Path, dst: Path) -> Path:
    """Center-crop to the target ratio, resize to 2048x1448, save PNG."""
    src = Path(src)
    dst = Path(dst)
    with Image.open(src) as im:
        width, height = im.size
        ratio = width / height

        if ratio > TARGET_RATIO:
            new_width = round(height * TARGET_RATIO)
            removed = width - new_width
            fraction = removed / width
            if fraction > MAX_CROP_FRACTION:
                raise ValueError(
                    f"LOUD FINISH FAILURE: refusing to crop {src}: width crop "
                    f"would remove {fraction:.1%} of pixels (> 8%)"
                )
            left = removed // 2
            crop_box = (left, 0, left + new_width, height)
        else:
            new_height = round(width / TARGET_RATIO)
            removed = height - new_height
            fraction = removed / height
            if fraction > MAX_CROP_FRACTION:
                raise ValueError(
                    f"LOUD FINISH FAILURE: refusing to crop {src}: height crop "
                    f"would remove {fraction:.1%} of pixels (> 8%)"
                )
            top = removed // 2
            crop_box = (0, top, width, top + new_height)

        finished = im.crop(crop_box).resize(TARGET_SIZE, Image.LANCZOS)

    dst.parent.mkdir(parents=True, exist_ok=True)
    finished.save(dst, format="PNG")
    return dst


def _latest_pass_render_paths(log_path: Path) -> dict[int, str]:
    latest: dict[int, str] = {}
    if not log_path.is_file():
        return latest
    with open(log_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("verdict") != "PASS":
                continue
            try:
                page = int(row.get("page", ""))
            except ValueError:
                continue
            if page == 0:
                continue
            if 1 <= page <= 32:
                latest[page] = row.get("render_path", "")
    return latest


def redo_all() -> int:
    latest = _latest_pass_render_paths(qa.APPROVAL_LOG)
    for page in range(1, 33):
        render_path = latest.get(page)
        if not render_path:
            print(f"WARNING: page {page:02d}: no PASS row; skipped", file=sys.stderr)
            continue
        src = ms.REPO_ROOT / render_path
        dst = ms.APPROVED_DIR / f"page_{page:02d}.png"
        finish(src, dst)
        print(f"page {page:02d}: finished {dst.relative_to(ms.REPO_ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finish approved MJ page renders.")
    parser.add_argument("--redo-all", action="store_true")
    args = parser.parse_args(argv)
    if not args.redo_all:
        parser.error("expected --redo-all")
    return redo_all()


if __name__ == "__main__":
    sys.exit(main())
