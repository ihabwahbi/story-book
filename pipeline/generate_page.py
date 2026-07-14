"""Per-page production driver: generate -> QA -> finish."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import engine, manuscript as ms, prompts, qa  # noqa: E402
from pipeline import finish as finisher  # noqa: E402


MAX_ATTEMPTS = 4
LIMIT_ERROR_MARKERS = ("quota", "rate limit", "usage limit")


class QuotaLimitAbort(RuntimeError):
    """Raised when Codex reports quota or rate limits."""


def _repo_relative(path: Path) -> str:
    return str(Path(path).resolve().relative_to(ms.REPO_ROOT))


def _is_limit_error(message: str) -> bool:
    text = re.sub(r"[-_]+", " ", message.lower())
    return any(marker in text for marker in LIMIT_ERROR_MARKERS)


def _page_spec(page_number: int) -> dict:
    for spec in ms.load_pages():
        if spec["page"] == page_number:
            return spec
    raise ValueError(f"page {page_number} is not in pages.yaml")


def _next_attempt_number(page_number: int) -> int:
    """Return the next unused attempt number so revisions never overwrite renders."""
    render_dir = ms.PRODUCTION / "06_RENDERS" / f"page_{page_number:02d}"
    numbers: list[int] = []
    for path in render_dir.glob("attempt_*.png"):
        match = re.fullmatch(r"attempt_(\d+)\.png", path.name)
        if match:
            numbers.append(int(match.group(1)))
    if qa.APPROVAL_LOG.is_file():
        with open(qa.APPROVAL_LOG, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("page") != str(page_number):
                    continue
                try:
                    numbers.append(int(row.get("attempt", "")))
                except ValueError:
                    continue
    return max(numbers, default=0) + 1


def generate_page(page_number: int) -> bool:
    """Generate one page. Returns True on approved/skipped, False on exhaustion."""
    spec = _page_spec(page_number)
    approved = ms.APPROVED_DIR / f"page_{page_number:02d}.png"
    if approved.exists():
        print(f"page {page_number:02d}: approved file exists; skipping")
        return True

    previous_failures: list[str] | None = None
    summaries: list[tuple[str, list[str]]] = []

    first_attempt = _next_attempt_number(page_number)
    revision_start = int(spec.get("revision_attempt_start", first_attempt))
    revision_stop = revision_start + MAX_ATTEMPTS
    if first_attempt >= revision_stop:
        print(
            f"LOUD FAILURE: page {page_number:02d} exhausted its "
            f"{MAX_ATTEMPTS}-attempt revision budget"
        )
        return False
    attempts = range(first_attempt, min(first_attempt + MAX_ATTEMPTS, revision_stop))
    for attempt in attempts:
        render_dest = (
            ms.PRODUCTION
            / "06_RENDERS"
            / f"page_{page_number:02d}"
            / f"attempt_{attempt}.png"
        )
        refs = prompts.resolve_refs(spec)
        prompt = prompts.build_page_prompt(
            spec, refs, retry_failures=previous_failures
        )
        try:
            render = engine.generate_image(prompt, refs, dest=render_dest)
            result = qa.review(render, spec)
            render_path = _repo_relative(render)
            qa.log_attempt(
                {
                    "page": page_number,
                    "attempt": attempt,
                    "render_path": render_path,
                    **result,
                }
            )
        except Exception as e:
            message = str(e)
            if _is_limit_error(message):
                failures = [f"pipeline-error: {message}"]
                render_path = (
                    _repo_relative(render_dest) if render_dest.is_file() else ""
                )
                qa.log_attempt(
                    {
                        "page": page_number,
                        "attempt": attempt,
                        "render_path": render_path,
                        "verdict": "ERROR",
                        "failures": failures,
                    }
                )
                raise QuotaLimitAbort(
                    f"ABORTING: quota/rate-limit/usage-limit error on "
                    f"page {page_number:02d} attempt {attempt}: {message}"
                ) from e
            failures = [f"pipeline-error: {message}"]
            render_path = _repo_relative(render_dest) if render_dest.is_file() else ""
            qa.log_attempt(
                {
                    "page": page_number,
                    "attempt": attempt,
                    "render_path": render_path,
                    "verdict": "ERROR",
                    "failures": failures,
                }
            )
            previous_failures = failures
            summaries.append((render_path, failures))
            print(
                f"page {page_number:02d} attempt {attempt}: ERROR; retrying",
                file=sys.stderr,
            )
            continue

        failures = [str(f) for f in result.get("failures", [])]
        summaries.append((render_path, failures))
        if result.get("verdict") == "PASS":
            finisher.finish(render, approved)
            print(
                f"page {page_number:02d}: PASS on attempt {attempt}; "
                f"finished {approved.relative_to(ms.REPO_ROOT)}"
            )
            return True

        previous_failures = failures
        print(f"page {page_number:02d} attempt {attempt}: FAIL; retrying")

    print(
        f"LOUD FAILURE: page {page_number:02d} exhausted its "
        f"{MAX_ATTEMPTS}-attempt revision budget"
    )
    for attempt, (render_path, failures) in zip(
        range(first_attempt, first_attempt + len(summaries)), summaries, strict=True
    ):
        print(f"  attempt {attempt}: {render_path or '<no render>'}")
        for failure in failures:
            print(f"    - {failure}")
    return False


def generate_all() -> bool:
    for page_number in range(1, 33):
        if not generate_page(page_number):
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate MJ book pages.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("page_number", nargs="?", type=int)
    group.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.all:
            return 0 if generate_all() else 1
        if not 1 <= args.page_number <= 32:
            parser.error("page_number must be 1..32")
        return 0 if generate_page(args.page_number) else 1
    except QuotaLimitAbort as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
