"""Prompt assembly for page generation — implements plan §8.2 exactly.

Every page prompt is `$imagegen ` + blocks A+B+C+D+E joined with blank lines.
"""

from __future__ import annotations

from pathlib import Path

from pipeline import manuscript as ms

MAX_REFS = 4  # canon + turnaround + at most 2 more

# Block B — style lock (verbatim from the client's Style Bible).
STYLE_LOCK = (
    "Use the approved soft painterly children's storybook style. MJ must "
    "match the approved MJ v1.0 references exactly. Do not use flat cartoon, "
    "model-sheet, anime, glossy 3D, plastic toy, realistic, medical poster, "
    "or generic mascot style. Use warm soft digital painterly rendering, "
    "gentle brush texture, rounded forms, soft shadows, warm colour harmony, "
    "and child-safe emotional tone. MJ and the background must look painted "
    "in the same world, with the same light direction, warmth, softness and "
    "brush texture."
)

# Block C — character lock ({clothing} filled per page).
CHARACTER_LOCK = (
    "MJ is a warm orange, fluffy but not shaggy, compact pear-shaped "
    "creature with large expressive brown eyes with white sclera and "
    "catchlights, small curved eyebrows, freckles on both cheeks, upward "
    "orange hair tufts, soft controlled plush-like fur, a rounded "
    "pear-shaped body, short rounded arms and legs, and simple rounded "
    "hands and feet. MJ wears no clothing{clothing}. MJ must NOT become "
    "tall, slim, elongated, bean-shaped, smooth, plastic, overly shaggy, "
    "yellow, baby-like, human-like, animal-like, or mascot-like."
)

# Page 3 is the manuscript's ONLY clothing exception (plain cream socks).
CLOTHING_EXCEPTIONS = {
    3: " except: simple plain cream/off-white socks, no patterns, no shoes"
}

# Block E — negatives (every page).
NEGATIVES = (
    "Absolutely no text, letters, words, titles, captions, labels, slogans, "
    "logos, watermarks, page numbers or signage anywhere in the image. No "
    "collage, no grid, no panels, no borders. Not square, not portrait. If "
    "any ribbon motif appears it must be orange, never purple. No purple "
    "awareness ribbons. No scary medical equipment. One single scene only."
)

COMPOSITION = (
    "Composition: single full-bleed scene, landscape aspect ratio "
    "approximately 1.414:1 (like 1456x1024). Place MJ and all scene "
    "interest in the {other} two-thirds of the image. Keep the {side} "
    "roughly 35% of the image as a clean, low-detail, softly coloured area "
    "with no characters, no faces and no important objects — it will hold "
    "printed text later."
)


def resolve_refs(page_spec: dict) -> list[Path]:
    """Reference bundle for a page: canon + turnaround first, then page refs.

    Same resolution rule as the validator (pipeline.manuscript.resolve_key).
    Capped at MAX_REFS; anchors/APPROVED are preferred over pose cards when
    trimming.
    """
    page = page_spec["page"]
    resolved: list[Path] = [ms.CANON, ms.TURNAROUND]
    extras: list[tuple[str, Path]] = []
    for key in page_spec.get("refs", []):
        path = ms.resolve_key(key, page)
        if path is not None:
            extras.append((key, path))

    room = MAX_REFS - len(resolved)
    if len(extras) > room:
        # Prefer anchors/APPROVED/support over pose cards when trimming.
        non_pose = [e for e in extras if not e[0].startswith("pose_")]
        pose = [e for e in extras if e[0].startswith("pose_")]
        extras = (non_pose + pose)[:room]
    resolved.extend(path for _, path in extras)
    return resolved


def _block_a(ref_paths: list[Path]) -> str:
    sentences = [
        "The attached images are the character and style authority. "
        "Image 1 is MJ_CANON_01, the primary approved reference for the "
        "character MJ — it controls face, body shape, orange colour, fur "
        "texture, freckles, eyes, hair tufts, hands, feet and proportions. "
        "Image 2 is the approved MJ turnaround sheet."
    ]
    for i, path in enumerate(ref_paths[2:], start=3):
        stem = Path(path).stem
        if stem == "MJ_CANON_SUPPORT_01_running":
            sentences.append(
                f"Image {i} is an approved movement-energy reference only — "
                f"never override Image 1's proportions with it."
            )
        elif stem.startswith("pose_"):
            sentences.append(
                f"Image {i} is an approved pose reference for MJ's body "
                f"attitude only."
            )
        else:  # anchor_* or APPROVED(n) page_NN.png
            sentences.append(
                f"Image {i} is an approved page from the same book showing "
                f"the required scene style and supporting character "
                f"appearance."
            )
    sentences.append("MJ must match these references exactly.")
    return " ".join(sentences)


def build_page_prompt(
    page_spec: dict,
    ref_paths: list[Path],
    retry_failures: list[str] | None = None,
) -> str:
    """Assemble the full `$imagegen` prompt for one page."""
    side = page_spec["text_safe_side"]
    other = "left" if side == "right" else "right"

    block_a = _block_a(ref_paths)
    block_c = CHARACTER_LOCK.format(
        clothing=CLOTHING_EXCEPTIONS.get(page_spec["page"], "")
    )
    scene = page_spec["scene"]
    lighting = ms.LIGHTING_CLASSES[page_spec["lighting"]]
    block_d = (
        f"{scene} Lighting: {lighting}. "
        + COMPOSITION.format(side=side, other=other)
    )

    blocks = [block_a, STYLE_LOCK, block_c, block_d, NEGATIVES]
    if retry_failures:
        blocks.append(
            "Previous attempt failed review because: "
            + "; ".join(retry_failures)
            + ". Correct exactly these issues while keeping everything else "
            "consistent with the references."
        )
    return "$imagegen " + "\n\n".join(blocks)
