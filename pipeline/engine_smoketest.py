"""Engine smoke test: one MJ-waving image from canon + turnaround.

Run: python3 -m pipeline.engine_smoketest
Output: /tmp/opencode/engine_smoke.png (not committed). Prints its size.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pipeline import manuscript as ms
from pipeline.engine import generate_image

PROMPT = (
    "$imagegen The attached images are the character authority. Image 1 is "
    "MJ_CANON_01, the primary approved reference for the character MJ. "
    "Image 2 is the approved MJ turnaround sheet. Generate ONE image of "
    "this exact fluffy warm-orange compact pear-shaped creature MJ, "
    "standing and waving happily, on a plain light cream background, in "
    "the same soft painterly children's storybook style as the references. "
    "MJ must match the references exactly: short rounded arms and legs, "
    "freckles on both cheeks, upward hair tufts, large brown eyes with "
    "white sclera and catchlights. No text anywhere. Landscape aspect "
    "ratio approximately 1.414:1."
)


def main() -> None:
    dest = Path("/tmp/opencode/engine_smoke.png")
    generate_image(PROMPT, [ms.CANON, ms.TURNAROUND], dest)
    with Image.open(dest) as im:
        print(f"{dest} {im.width}x{im.height}")


if __name__ == "__main__":
    main()
