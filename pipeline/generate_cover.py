"""Generate text-free front/back cover art through the existing QA gate."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import engine, finish, manuscript as ms, qa  # noqa: E402


COVER_DIR = ms.PRODUCTION / "10_COVER"
REFERENCE = ms.REPO_ROOT / "General front cover design.jpeg"
MAX_ATTEMPTS = 4
LIMIT_ERROR_MARKERS = ("quota", "rate limit", "usage limit")
REVISION_ATTEMPT_STARTS = {"front": 1, "back": 1}

COMMON = (
    "The attached images are references. Image 1 is the strict MJ character "
    "canon and Image 2 is the strict MJ turnaround. MJ must exactly preserve "
    "the canon's warm orange colour, compact pear-shaped proportions, short "
    "rounded arms and legs, two arms, exactly two legs and two feet, large "
    "brown eyes with white sclera and catchlights, cheek freckles, upward "
    "hair tufts, and soft controlled fur. Image 3 is client cover direction "
    "for only the cheerful meadow, sunflowers, butterflies, colourful round "
    "stepping-stone path, bright blue sky, and joyful colour palette. Ignore "
    "and do not reproduce its title, words, typography, panels, border, "
    "barcode, ISBN, or off-model character. Use soft painterly children's "
    "storybook rendering consistent with the book interior, rounded forms, "
    "gentle brush texture, warm light, and a child-safe joyful tone. Full-"
    "bleed landscape composition approximately 1.414:1. Absolutely NO text, "
    "letters, words, logos, signs, labels, numbers, watermark, border, panel, "
    "barcode, or ISBN anywhere. No purple awareness ribbon."
)

FRONT_SCENE = (
    "Create clean FRONT COVER ART only. MJ is large and joyful in the right "
    "half/lower-right, walking toward the viewer and waving with one hand on "
    "the colourful stepping-stone path through a sunflower meadow. Show a few "
    "small butterflies and a bright friendly sky. Keep the entire left 56% "
    "calm, low-detail, and free of characters, faces, sunflowers, butterflies, "
    "and important objects so real title typography can be added later. Do "
    "not paint any placeholder sign or text panel."
)

BACK_SCENE = (
    "Create clean BACK COVER ART only that clearly belongs to the same cover. "
    "Use the same bright sky, flower meadow, sunflowers, butterflies, and "
    "colourful stepping-stone path. MJ is smaller but still correctly "
    "proportioned at mid-right, smiling gently and waving, with MJ's feet "
    "well above the lower-right corner reserved for an ISBN overlay. Keep the "
    "entire left 68% and upper-middle calm, low-detail, and free of characters, "
    "faces, sunflowers, butterflies, and important objects for real synopsis "
    "typography. Keep the lower-right corner behind MJ simple enough for a "
    "small ISBN-area overlay. Do not paint any placeholder sign or text panel."
)

SPECS = {
    "front": {
        "scene": FRONT_SCENE,
        "requirements": (
            "Front cover art: MJ is on-model, large on the right/lower-right, "
            "with exactly two legs/two feet; the left 56% is a clean title-safe "
            "zone; cheerful sunflower meadow, butterflies and colourful "
            "stepping-stone path are present; absolutely no text, letters, "
            "logos, borders, panels, barcodes, or ISBN."
        ),
    },
    "back": {
        "scene": BACK_SCENE,
        "requirements": (
            "Back cover art: MJ is on-model and smaller at mid-right with "
            "exactly two legs/two feet, with feet above the lower-right ISBN "
            "area; the left 68% is a clean synopsis-safe "
            "zone; the scene matches the front's sunflower meadow, butterflies "
            "and colourful stepping-stone path; absolutely no text, letters, "
            "logos, borders, panels, barcodes, or ISBN."
        ),
    },
}


def _next_attempt(kind: str) -> int:
    render_dir = COVER_DIR / "renders" / kind
    numbers: list[int] = []
    for path in render_dir.glob("attempt_*.png"):
        try:
            numbers.append(int(path.stem.removeprefix("attempt_")))
        except ValueError:
            continue
    if qa.APPROVAL_LOG.is_file():
        with open(qa.APPROVAL_LOG, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("page") != f"cover-{kind}":
                    continue
                try:
                    numbers.append(int(row.get("attempt", "")))
                except ValueError:
                    continue
    return max(numbers, default=0) + 1


def _refs(kind: str) -> list[Path]:
    refs = [ms.CANON, ms.TURNAROUND, REFERENCE]
    if kind == "back":
        front = COVER_DIR / "front_cover_art.png"
        if not front.is_file():
            raise FileNotFoundError(
                "front_cover_art.png must be approved before generating the back"
            )
        refs.append(front)
    return refs


def _prompt(kind: str, failures: list[str] | None) -> str:
    prompt = "$imagegen " + COMMON + " " + SPECS[kind]["scene"]
    if kind == "back":
        prompt += (
            " Image 4 is the approved text-free front cover art. Match its "
            "exact painterly treatment, sky, meadow palette, sunflowers, "
            "butterflies, stepping-stone path, lighting, and MJ appearance so "
            "the two covers clearly form one design system."
        )
    if failures:
        prompt += (
            " Previous attempt failed because: "
            + "; ".join(failures)
            + ". Correct every listed issue while preserving the rest."
        )
    return prompt


def generate(kind: str, force: bool = False) -> bool:
    art = COVER_DIR / f"{kind}_cover_art.png"
    if art.exists() and not force:
        print(f"cover {kind}: approved art exists; skipping")
        return True

    first = _next_attempt(kind)
    revision_stop = REVISION_ATTEMPT_STARTS[kind] + MAX_ATTEMPTS
    if first >= revision_stop:
        print(
            f"LOUD FAILURE: cover {kind} exhausted its "
            f"{MAX_ATTEMPTS}-attempt revision budget"
        )
        return False
    if force and art.exists():
        art.unlink()
    previous_failures: list[str] | None = None
    for attempt in range(first, revision_stop):
        dest = COVER_DIR / "renders" / kind / f"attempt_{attempt}.png"
        refs = _refs(kind)
        try:
            render = engine.generate_image(_prompt(kind, previous_failures), refs, dest)
            result = qa.review(
                render,
                {
                    "text_safe_side": "left",
                    "visual_requirements": SPECS[kind]["requirements"],
                    "qa_extra_refs": (
                        [COVER_DIR / "front_cover_art.png"] if kind == "back" else []
                    ),
                },
            )
            qa.log_attempt(
                {
                    "page": f"cover-{kind}",
                    "attempt": attempt,
                    "render_path": str(render.relative_to(ms.REPO_ROOT)),
                    **result,
                }
            )
        except Exception as exc:
            normalized = re.sub(r"[-_]+", " ", str(exc).lower())
            if any(marker in normalized for marker in LIMIT_ERROR_MARKERS):
                failures = [f"pipeline-error: {exc}"]
                qa.log_attempt(
                    {
                        "page": f"cover-{kind}",
                        "attempt": attempt,
                        "render_path": (
                            str(dest.relative_to(ms.REPO_ROOT))
                            if dest.is_file()
                            else ""
                        ),
                        "verdict": "ERROR",
                        "failures": failures,
                    }
                )
                raise RuntimeError(
                    f"ABORTING: quota/rate-limit/usage-limit error on cover "
                    f"{kind} attempt {attempt}: {exc}"
                ) from exc
            failures = [f"pipeline-error: {exc}"]
            qa.log_attempt(
                {
                    "page": f"cover-{kind}",
                    "attempt": attempt,
                    "render_path": (
                        str(dest.relative_to(ms.REPO_ROOT)) if dest.is_file() else ""
                    ),
                    "verdict": "ERROR",
                    "failures": failures,
                }
            )
            previous_failures = failures
            print(f"cover {kind} attempt {attempt}: ERROR; retrying", file=sys.stderr)
            continue

        if result["verdict"] == "PASS":
            finish.finish(render, art)
            print(f"cover {kind}: PASS on attempt {attempt}; wrote {art}")
            return True
        previous_failures = [str(f) for f in result.get("failures", [])]
        print(f"cover {kind} attempt {attempt}: FAIL; retrying")

    print(
        f"LOUD FAILURE: cover {kind} exhausted its "
        f"{MAX_ATTEMPTS}-attempt revision budget"
    )
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate front/back cover art.")
    parser.add_argument("kind", choices=("front", "back", "all"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    kinds = ("front", "back") if args.kind == "all" else (args.kind,)
    for kind in kinds:
        if not generate(kind, force=args.force):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
