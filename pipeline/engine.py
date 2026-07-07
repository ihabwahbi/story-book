"""The single image-generation engine: Codex CLI `$imagegen` (gpt-image-2).

One public function. If an OPENAI_API_KEY ever materializes, this module is
reimplemented against the raw Images API behind the same signature (plan OQ-1).
"""

from __future__ import annotations

import re
import subprocess
import shutil
import time
from pathlib import Path

from pipeline.manuscript import REPO_ROOT

GENERATED_ROOT = Path.home() / ".codex" / "generated_images"
_PATH_RE = re.compile(r"(/[^\s`'\"]*/\.codex/generated_images/[^\s`'\"]+)")


class GenerationError(RuntimeError):
    """Raised when Codex fails or no generated PNG can be harvested."""


def generate_image(
    prompt: str,
    ref_paths: list[Path],
    dest: Path,
    timeout_s: int = 600,
) -> Path:
    """Generate one image with gpt-image-2 via Codex, conditioned on refs.

    `prompt` must already begin with `$imagegen ` (prompts.py adds it).
    `ref_paths` order matters: canon first — Block A's indices depend on it.
    The harvested PNG is copied to `dest` (parents created); returns `dest`.
    """
    if not prompt.startswith("$imagegen "):
        raise ValueError("prompt must begin with '$imagegen '")
    for p in ref_paths:
        if not Path(p).is_file():
            raise GenerationError(f"reference image missing: {p}")

    start = time.time()
    argv = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--image",
        ",".join(str(p) for p in ref_paths),
        "--",
        prompt,
    ]
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        cwd=REPO_ROOT,
    )
    if proc.returncode != 0:
        raise GenerationError(
            f"codex exec exited {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )

    png = _harvest(proc.stdout, start)
    if png is None:
        raise GenerationError(
            "no generated PNG found in codex output or "
            f"{GENERATED_ROOT}\n--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}"
        )

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(png, dest)
    return dest


def _harvest(stdout: str, start: float) -> Path | None:
    """Find the generated PNG: parse stdout paths, else newest-mtime scan."""
    for match in reversed(_PATH_RE.findall(stdout)):
        p = Path(match)
        if p.is_file() and p.suffix == ".png":
            return p
        if p.is_dir():
            pngs = sorted(p.glob("*.png"), key=lambda f: f.stat().st_mtime)
            if pngs:
                return pngs[-1]
    if GENERATED_ROOT.is_dir():
        fresh = [
            f
            for f in GENERATED_ROOT.glob("**/*.png")
            if f.stat().st_mtime > start
        ]
        if fresh:
            return max(fresh, key=lambda f: f.stat().st_mtime)
    return None
