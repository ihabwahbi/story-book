"""Validate MJ_BOOK_PRODUCTION/01_MANUSCRIPT/pages.yaml against the plan's rules.

Checks (plan Phase 1):
  - exactly 32 entries, pages 1..32 exactly once
  - odd pages have text_safe_side: right, even pages: left
  - every lighting value is one of the 8 classes
  - every ref key resolves per the single missing-ref rule in
    pipeline.manuscript (APPROVED(n) with n < page counts as resolvable by
    CONTRACT here — the file itself only exists once production reaches it).

Exit 0 and print "32 pages OK" on success.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import manuscript as ms  # noqa: E402


def main() -> int:
    pages = ms.load_pages()
    errors: list[str] = []

    if len(pages) != 32:
        errors.append(f"expected 32 entries, found {len(pages)}")
    numbers = [p["page"] for p in pages]
    if numbers != list(range(1, 33)):
        errors.append(f"pages are not exactly 1..32 once each: {numbers}")

    for p in pages:
        n = p["page"]
        want_side = "right" if n % 2 else "left"
        if p.get("text_safe_side") != want_side:
            errors.append(
                f"page {n}: text_safe_side must be '{want_side}', "
                f"got {p.get('text_safe_side')!r}"
            )
        if p.get("lighting") not in ms.LIGHTING_CLASSES:
            errors.append(f"page {n}: unknown lighting {p.get('lighting')!r}")
        if not isinstance(p.get("text"), str) or not p["text"].strip():
            errors.append(f"page {n}: missing/empty text")
        for key in p.get("refs", []):
            approved_n = ms.approved_ref_page(key)
            if approved_n is not None:
                # Validation-time contract check only; the PNG appears later.
                if approved_n >= n:
                    errors.append(
                        f"page {n}: {key} must reference an earlier page"
                    )
                continue
            try:
                ms.resolve_key(key, n)  # None (dropped pose) is acceptable
            except ValueError as e:
                errors.append(str(e))

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print("32 pages OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
