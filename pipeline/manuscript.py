"""Locked manuscript access and the single reference-resolution rule.

Source of truth: docs/plans/mj-wobbly-days-production-pipeline.md §7, §8.1, Phase 1.

The ONE missing-ref rule (applies to validator and prompt builder alike):
  - `APPROVED(n)` resolves to 07_APPROVED/page_NN.png; n must be < the page
    using it. At resolution time the file must exist (pages are produced in
    ascending order) — a missing file is a hard error.
  - Any other key resolves by filename stem across 02_CHARACTER_CANON/,
    03_APPROVED_STYLE_ANCHORS/ and 05_POSE_LIBRARY/.
  - A `pose_*` key that resolves to no file is DROPPED with a warning (the
    scene brief carries the pose in words; the key stays in pages.yaml).
  - Any other unresolvable key is a hard error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION = REPO_ROOT / "MJ_BOOK_PRODUCTION"
PAGES_YAML = PRODUCTION / "01_MANUSCRIPT" / "pages.yaml"
CANON_DIR = PRODUCTION / "02_CHARACTER_CANON"
ANCHOR_DIR = PRODUCTION / "03_APPROVED_STYLE_ANCHORS"
POSE_DIR = PRODUCTION / "05_POSE_LIBRARY"
APPROVED_DIR = PRODUCTION / "07_APPROVED"

CANON = CANON_DIR / "MJ_CANON_01.jpeg"
TURNAROUND = CANON_DIR / "MJ_v1_turnaround_sheet.jpeg"

LIGHTING_CLASSES = {
    "title": "quiet warm cream, calm welcoming",
    "happy_outdoor": "warm sunlight, bright but soft, playful, not overexposed",
    "home": "warm indoor light, cosy, safe, soft shadows",
    "home_muted": (
        "home but slightly muted colours, gentle shadows, never frightening, "
        "never bleak"
    ),
    "hospital": (
        "cream and pale blue, clean but not cold, warm safety, no harsh "
        "clinical lighting"
    ),
    "art_room": "warm indoor, creative, bright orange accents",
    "classroom": "warm, soft, gentle daylight interior",
    "night": (
        "soft moonlight/starlight + warm indoor lamp glow, peaceful not spooky"
    ),
}

_APPROVED_RE = re.compile(r"^APPROVED\((\d+)\)$")
_STEM_DIRS = (CANON_DIR, ANCHOR_DIR, POSE_DIR)


def load_pages() -> list[dict]:
    """Load pages.yaml, sorted by page number."""
    with open(PAGES_YAML, encoding="utf-8") as f:
        pages = yaml.safe_load(f)
    return sorted(pages, key=lambda p: p["page"])


def approved_ref_page(key: str) -> int | None:
    """Return n for an APPROVED(n) key, else None."""
    m = _APPROVED_RE.match(key)
    return int(m.group(1)) if m else None


def resolve_key(key: str, page: int) -> Path | None:
    """Resolve one ref key per the single missing-ref rule.

    Returns the resolved Path, or None for a dropped pose_* key (warning
    printed to stderr). Raises ValueError on any hard error.
    """
    n = approved_ref_page(key)
    if n is not None:
        if n >= page:
            raise ValueError(
                f"page {page}: {key} must reference an earlier page (n < {page})"
            )
        path = APPROVED_DIR / f"page_{n:02d}.png"
        if not path.is_file():
            raise ValueError(
                f"page {page}: {key} -> {path} does not exist yet; pages must "
                f"be produced in ascending order"
            )
        return path

    for d in _STEM_DIRS:
        for candidate in sorted(d.glob(f"{key}.*")):
            if candidate.is_file():
                return candidate

    if key.startswith("pose_"):
        print(
            f"WARNING: page {page}: pose ref '{key}' has no library card — "
            f"dropped (scene brief carries the pose in words)",
            file=sys.stderr,
        )
        return None
    raise ValueError(f"page {page}: ref '{key}' does not resolve to any file")
