"""Character-fidelity QA gate — implements plan §8.3.

A candidate page image is judged by a Codex vision call (gpt-5.5 reads
images natively) against MJ_CANON_01 + the turnaround sheet. Verdict = all
ten booleans true. Every attempt is logged to 09_NOTES/approval_log.csv.
"""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from pipeline import manuscript as ms

APPROVAL_LOG = ms.PRODUCTION / "09_NOTES" / "approval_log.csv"

BOOL_KEYS = [
    "mj_match",
    "proportions",
    "no_unapproved_clothing",
    "style_match",
    "no_text",
    "single_scene",
    "landscape",
    "text_safe_zone",
    "no_purple_ribbon",
    "child_safe",
]

LOG_COLUMNS = [
    "timestamp",
    "page",
    "attempt",
    "render_path",
    *BOOL_KEYS,
    "verdict",
    "failures",
]

MIN_RATIO = 1.25

QA_PROMPT = (
    "Image 1 is the approved canonical reference for the character MJ. "
    "Image 2 is the approved turnaround sheet. Image 3 is a candidate "
    "book-page illustration. Judge the candidate STRICTLY. Answer with ONLY "
    "a JSON object, no markdown fence, with keys: \"mj_match\" (bool: same "
    "face, eye style with white sclera and catchlights, freckles on both "
    "cheeks, upward hair tufts, warm orange colour, plush controlled fur), "
    "\"proportions\" (bool: compact pear-shaped body, SHORT rounded arms "
    "and legs — false if tall, slim, elongated or long-limbed), "
    "\"no_unapproved_clothing\" (bool — cream socks are permitted ONLY if "
    "the scene is a kitchen dance), \"style_match\" (bool: soft painterly "
    "storybook, not flat cartoon, not glossy 3D, not anime), \"no_text\" "
    "(bool: true if there is NO text, lettering, labels or signage "
    "anywhere), \"single_scene\" (bool: no collage, grid or panels), "
    "\"landscape\" (bool: clearly wider than tall), \"text_safe_zone\" "
    "(bool: the {side} ~35% of the image is low-detail and free of "
    "characters and faces), \"no_purple_ribbon\" (bool), \"child_safe\" "
    "(bool: emotionally gentle, nothing frightening), \"failures\" (array "
    "of short strings describing every false item, empty if all true)."
)


class QAError(RuntimeError):
    """Raised when the vision review cannot produce a parsable verdict."""


def review(
    candidate: Path,
    page_spec: dict,
    skip_ratio_precheck: bool = False,
    timeout_s: int = 600,
) -> dict:
    """Judge one candidate. Returns {ten bools..., verdict, failures}."""
    candidate = Path(candidate)
    if not skip_ratio_precheck:
        with Image.open(candidate) as im:
            ratio = im.width / im.height
        if ratio < MIN_RATIO:
            return {
                "landscape": False,
                "verdict": "FAIL",
                "failures": [
                    f"landscape: ratio {ratio:.3f} below {MIN_RATIO} "
                    f"(pre-check, no QA call)"
                ],
            }

    prompt = QA_PROMPT.format(side=page_spec["text_safe_side"])
    argv = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--image",
        f"{ms.CANON},{ms.TURNAROUND},{candidate}",
        "--",
        prompt,
    ]
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        cwd=ms.REPO_ROOT,
    )
    if proc.returncode != 0:
        raise QAError(
            f"codex QA call exited {proc.returncode}\n--- stdout ---\n"
            f"{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )

    data = _extract_json(proc.stdout)
    if data is None:
        raise QAError(f"no JSON verdict in QA output:\n{proc.stdout}")

    result = {k: bool(data.get(k, False)) for k in BOOL_KEYS}
    failures = [str(f) for f in data.get("failures", [])]
    ok = all(result.values())
    # Belt-and-braces: a false bool with no matching failure string still
    # needs a reason for the retry prompt.
    if not ok and not failures:
        failures = [f"{k}: judged false" for k, v in result.items() if not v]
    result["verdict"] = "PASS" if ok else "FAIL"
    result["failures"] = failures if not ok else []
    return result


def _extract_json(stdout: str) -> dict | None:
    """Find the verdict JSON object anywhere in Codex output."""
    text = stdout.replace("```json", "").replace("```", "")
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except ValueError:
            continue
        if isinstance(obj, dict) and "mj_match" in obj:
            return obj
    return None


def log_attempt(row: dict) -> None:
    """Append one attempt to approval_log.csv (header created if absent).

    Bool columns missing from `row` are logged empty (e.g. ERROR rows or
    ratio pre-check fails). `render_path` must be repo-relative. `failures`
    lists are serialized with '; '.
    """
    out = dict(row)
    out.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    if isinstance(out.get("failures"), list):
        out["failures"] = "; ".join(out["failures"])
    APPROVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not APPROVAL_LOG.exists()
    with open(APPROVAL_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS, extrasaction="ignore")
        if new:
            writer.writeheader()
        writer.writerow({c: out.get(c, "") for c in LOG_COLUMNS})
