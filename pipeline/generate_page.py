"""Per-page production driver: generate -> QA -> finish."""

from __future__ import annotations

import argparse
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
    text = message.lower()
    return any(marker in text for marker in LIMIT_ERROR_MARKERS)


def _page_spec(page_number: int) -> dict:
    for spec in ms.load_pages():
        if spec["page"] == page_number:
            return spec
    raise ValueError(f"page {page_number} is not in pages.yaml")


def generate_page(page_number: int) -> bool:
    """Generate one page. Returns True on approved/skipped, False on exhaustion."""
    spec = _page_spec(page_number)
    approved = ms.APPROVED_DIR / f"page_{page_number:02d}.png"
    if approved.exists():
        print(f"page {page_number:02d}: approved file exists; skipping")
        return True

    previous_failures: list[str] | None = None
    summaries: list[tuple[str, list[str]]] = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
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

    print(f"LOUD FAILURE: page {page_number:02d} exhausted {MAX_ATTEMPTS} attempts")
    for idx, (render_path, failures) in enumerate(summaries, start=1):
        print(f"  attempt {idx}: {render_path or '<no render>'}")
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
