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
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import manuscript as ms  # noqa: E402

LOCKED_MANUSCRIPT = ms.PRODUCTION / "01_MANUSCRIPT" / "locked_manuscript.txt"


REVISION_ATTEMPT_STARTS = {
    9: 2,
    10: 3,
    11: 2,
    12: 2,
    13: 2,
    14: 2,
    16: 2,
    23: 2,
    31: 3,
    32: 2,
}

QA_COMPARISON_PAGES = {
    11: [10],
    12: [10],
    13: [11],
    14: [11],
    16: [10],
    23: [22, 24],
    32: [31],
}

LOCKED_TEXT_CORRECTIONS = {
    1: (
        "MJ and the Wobbly Days\n"
        "A story about courage, difference, and living with MS\n"
        "Written by MJ Donnellan\n"
        "To all the children I’ve had the privilege and joy of teaching over "
        "the years: never be afraid to be different. It’s our differences "
        "that make each of us unique, and they are what make the world a more "
        "beautiful, colourful, and interesting place."
    ),
    10: (
        "Then one day, after her legs shook and her eyes went blurry, MJ found "
        "herself in a big hospital room, holding her Mum's hand so tightly her "
        "fingers hurt."
    ),
    12: "Her Mum rubbed circles on her hand.\n'What does that mean?' MJ whispered.",
    16: (
        "'Will I always be different?' MJ asked quietly.\n"
        "Her Mum squeezed her hand.\n"
        "'Yes,' she said gently.\n"
        "'But different does not mean less.'"
    ),
    17: (
        "That didn't make everything easier.\n"
        "There were still hard days.\n"
        "Some days MJ fell over.\n"
        "Some days her legs wouldn't listen.\n"
        "Some days she cried because her body felt cross with her."
    ),
    18: "Some days people said things that hurt.\n'But you don't look sick.'",
    29: (
        "She looked around the room.\n"
        "'Different just means we all have different stories.'\n"
        "'That makes the world more interesting.'"
    ),
}


def main() -> int:
    pages = ms.load_pages()
    errors: list[str] = []

    locked_text = LOCKED_MANUSCRIPT.read_text(encoding="utf-8")
    expected_locked_text = "\n".join(
        f"--- Page {int(page['page'])} ---\n{page['text']}\n" for page in pages
    )
    if locked_text != expected_locked_text:
        errors.append(
            "locked_manuscript.txt is not an exact serialization of pages.yaml"
        )

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
        if re.search(r"\bmum\b", p.get("text", "")):
            errors.append(f"page {n}: prose contains lowercase 'mum'")
        expected_text = LOCKED_TEXT_CORRECTIONS.get(n)
        if expected_text is not None and p.get("text") != expected_text:
            errors.append(f"page {n}: text does not match locked client correction")
        expected_start = REVISION_ATTEMPT_STARTS.get(n)
        if expected_start is not None:
            if p.get("revision_attempt_start") != expected_start:
                errors.append(
                    f"page {n}: revision_attempt_start must be {expected_start}"
                )
            if not isinstance(p.get("visual_requirements"), str) or not p[
                "visual_requirements"
            ].strip():
                errors.append(f"page {n}: missing visual_requirements")
        elif "revision_attempt_start" in p:
            errors.append(f"page {n}: unexpected revision_attempt_start")
        if n not in REVISION_ATTEMPT_STARTS and "visual_requirements" in p:
            errors.append(f"page {n}: unexpected visual_requirements")
        expected_comparisons = QA_COMPARISON_PAGES.get(n)
        if expected_comparisons is not None:
            if p.get("qa_comparison_pages") != expected_comparisons:
                errors.append(
                    f"page {n}: qa_comparison_pages must be {expected_comparisons}"
                )
        elif "qa_comparison_pages" in p:
            errors.append(f"page {n}: unexpected qa_comparison_pages")
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
