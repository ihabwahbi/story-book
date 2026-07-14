# MJ and the Wobbly Days — Client Feedback Revision

## Authority and starting state

This document is the complete authority for the July 2026 correction run. It
authorizes the new cover, an eleven-boolean QA schema, and a fresh four-attempt
budget per named revision target. The already delivered 32-page production
remains unchanged except where this document explicitly names a correction,
dependency, pipeline module, or output.

Runtime manuscript data is
`MJ_BOOK_PRODUCTION/01_MANUSCRIPT/pages.yaml`; mirror every text change in
`MJ_BOOK_PRODUCTION/01_MANUSCRIPT/locked_manuscript.txt`. The table in
`docs/plans/mj-wobbly-days-production-pipeline.md` is updated for traceability
but is not a third runtime source. The current uncommitted edits in those
files and in `pipeline/{prompts,qa,layout,generate_page,generate_cover,cover}.py`
are implementation targets. Before any costly generation, inspect their
current diff, complete every item under “Pipeline changes,” run
`python3 -m py_compile pipeline/*.py`, and run the manuscript validator. Do not
reset partially implemented work merely because it is uncommitted.

The canonical MJ references are:

- `MJ_BOOK_PRODUCTION/02_CHARACTER_CANON/MJ_CANON_01.jpeg`
- `MJ_BOOK_PRODUCTION/02_CHARACTER_CANON/MJ_v1_turnaround_sheet.jpeg`

The supplied repository-root `General front cover design.jpeg` is a direction reference only.
Its wrong title, baked/generated text, and placeholder ISBN must not be copied.

Self-contained pipeline contracts for this revision:

- Approved page outputs are
  `MJ_BOOK_PRODUCTION/07_APPROVED/page_NN.png`; an existing approved output
  causes `generate_page.py NN` to skip, so remove only the current target.
- `APPROVED(n)` references require `n < current page` and require the earlier
  approved PNG to exist. Non-page references resolve by filename stem in
  `02_CHARACTER_CANON/`, `03_APPROVED_STYLE_ANCHORS/`, and `05_POSE_LIBRARY/`.
  Missing `pose_*` references are intentionally dropped with a warning because
  the written scene carries the pose; all other unresolved keys fail.
- The approval log is `MJ_BOOK_PRODUCTION/09_NOTES/approval_log.csv` with
  timestamp, page, attempt, render path, booleans, verdict, and failures.
- Cover attempt renders use
  `MJ_BOOK_PRODUCTION/10_COVER/renders/{front|back}/attempt_N.png`; shared-log
  page identifiers are `cover-front` and `cover-back`.
- The original booleans are `mj_match`, `proportions`,
  `no_unapproved_clothing`, `style_match`, `no_text`, `single_scene`,
  `landscape`, `text_safe_zone`, `no_purple_ribbon`, and `child_safe`; this
  revision adds `requirements_match` as the eleventh.
- Each target receives a fresh budget of at most four attempts for this
  client-revision run, regardless of historic attempt count. Attempt filenames
  and log numbers continue from the maximum historic render or log attempt.
- `revision_attempt_start` persists the first allowed revision attempt in each
  affected page spec and is validated exactly: page 9→2, 10→3, 11→2, 12→2,
  13→2, 14→2, 16→2, 23→2, 31→3, 32→2. The stop boundary is start+4 across all
  invocations; no silent default is allowed for these targets.
- Any quota, rate-limit, or usage-limit error aborts immediately rather than
  retrying.

## Locked interior corrections

Apply these exact results:

1. **Page 1:** keep the existing three title sections and add this exact fourth
   section in smaller type:

   > To all the children I’ve had the privilege and joy of teaching over the years: never be afraid to be different. It’s our differences that make each of us unique, and they are what make the world a more beautiful, colourful, and interesting place.

2. **Page 9:** MJ has a nervous, unsure, closed-mouth half-smile with worried
   raised inner eyebrows—not a happy or broad smile.
3. **Page 10:** text uses `Mum`; MJ looks worried and does not smile. Mum is a
   light-skinned warm woman with a short dark-brown pixie-bob ending above her
   ears and a rust cardigan. The old hospital anchor controls only composition
   and style, not Mum’s appearance.
4. **Page 11:** Mum matches page 10. Doctor is unmistakably different: a Black
   woman with deep brown skin, close-cropped natural black curls, teal blouse,
   and white coat.
5. **Pages 13–14:** Doctor exactly matches revised page 11.
6. **Page 12:** text uses `Mum`; Mum matches page 10 and MJ repeats page 10’s
   worried, non-smiling expression.
7. **Page 16:** text uses `Mum`; Mum matches page 10.
8. **Page 17:** exact text:

   ```text
   That didn't make everything easier.
   There were still hard days.
   Some days MJ fell over.
   Some days her legs wouldn't listen.
   Some days she cried because her body felt cross with her.
   ```

9. **Page 18:** exact text:

   ```text
   Some days people said things that hurt.
   'But you don't look sick.'
   ```

10. **Page 23:** MJ is approximately the cousin’s standing height, matching
    pages 22 and 24; MJ must not be miniaturized or much shorter than the child.
11. **Page 29:** exact text:

    ```text
    She looked around the room.
    'Different just means we all have different stories.'
    'That makes the world more interesting.'
    ```

12. **Pages 31–32:** MJ has exactly two short legs and two rounded feet, with
    no third leg, extra foot, tail, or ambiguous limb-like silhouette.
13. Every prose occurrence of the family name `Mum` uses a capital `M`.

## Pipeline changes

1. `pipeline/prompts.py` appends a hard mandatory `visual_requirements` block
   when present in a page spec.
2. `pipeline/qa.py` adds an explicit `requirements_match` boolean to the QA
   response and CSV schema. All eleven booleans must be true. Before appending
   the first revision row, migrate the old CSV header and rows without losing
   content; old rows may have blank `requirements_match` values.
   `requirements_match` is true only when every statement in the current
   page’s non-empty `visual_requirements` is visibly satisfied. QA always sees
   canon, turnaround, and candidate, plus these required comparison pages:
   page 11→10, 12→10, 13→11, 14→11, 16→10, 23→22+24, and 32→31. The fields are
   named `qa_comparison_pages` and are validated exactly. Pages 9, 10, 11, 12,
   13, 14, 16, 23, 31, and 32 must all have non-empty
   `visual_requirements`; every other page must omit all three revision markers:
   `revision_attempt_start`, `qa_comparison_pages`, and `visual_requirements`.
3. `pipeline/generate_page.py` chooses the next unused `attempt_N.png` number
   on rerun, preserving all prior renders and globally unique per-page attempt
   numbers.
4. `pipeline/layout.py` accepts exactly four page-1 sections at 96/48/40/28 px
   starting sizes, shrinking proportionally only if required; dedication is
   section four.
5. Add `pipeline/generate_cover.py` for the two front/back Codex `$imagegen`
   workflows (each with the same maximum-four-attempt retry gate)
   and `pipeline/cover.py` for deterministic real-text compositing and PDF
   assembly. Generated art must contain no baked text.
6. `pipeline/validate_manuscript.py` hard-checks exact parity between all 32
   `pages.yaml` texts and `locked_manuscript.txt`, plus exact revised text on pages 1,
   10, 12, 16, 17, 18, and 29; zero lowercase prose `mum`; the ten revision
   attempt starts; all required non-empty visual requirements; and the exact
   comparison-page map before generation can begin.

## Selective regeneration procedure

Only approved illustrations 9, 10, 11, 12, 13, 14, 16, 23, 31, and 32 may be
replaced. All other files under `07_APPROVED` must remain byte-identical.

From the repository root, first run:

```bash
python3 pipeline/validate_manuscript.py
```

Preserve old committed bytes through Git history. Handle exactly one page at a
time in dependency-safe order. For each number below, run the two-command pair
with `&&`, then stop and visually inspect before starting the next number:

Resume rule: before deleting a target, inspect the approval log. If its latest
row is already a revision-run `PASS`, keep the approved file, perform the human
visual check, record PASS/REJECT, and only delete/rerun after a recorded REJECT.

```text
09, 10, 11, 12, 13, 14, 16, 23, 31, 32
```

Command template (replace both `NN` and `N` with the listed page):

```bash
rm -f "MJ_BOOK_PRODUCTION/07_APPROVED/page_NN.png" && \
  python3 pipeline/generate_page.py N
```

Do not run `finish.py --redo-all`. The executor running this plan is the
engineering lead and owns the visual approval. After each PASS, use the image
viewer to inspect the approved PNG against that page’s locked correction before
moving on. A generic QA PASS does not override a visible correction failure;
delete that approved file and rerun if necessary. The remaining revision-
attempt budget is enforced across invocations.

Then rebuild all layouts and the proof:

```bash
python3 pipeline/layout.py
```

## Cover specification

Create two separate landscape cover pages, each **2048×1448 px**, matching the
interior trim. Final composited PNGs and the proof carry **250 dpi** metadata;
the clean art intermediates are required at 2048×1448 pixels but need not carry
DPI metadata. Outputs live under
`MJ_BOOK_PRODUCTION/10_COVER/`:

- `front_cover_art.png` — clean generated front art without typography.
- `back_cover_art.png` — clean generated back art without typography.
- `front_cover.png` — final composited front.
- `back_cover.png` — final composited back.
- `MJ_and_the_Wobbly_Days_cover_proof.pdf` — two pages, front then back.

Art direction from the supplied reference: cheerful blue sky, colourful flower
meadow, prominent sunflowers, small butterflies, and a path of colourful round
stepping stones. Use the same soft painterly storybook rendering as the
interior. Front: on-model MJ large and joyful on the right/lower half, waving
or walking, with the left 56% clear for the full copy panel. Back: matching meadow scene,
smaller on-model MJ at mid-right with feet above the lower-right ISBN area, and
a calm low-detail left 68% for the full copy panel. No baked text, logos, border,
panels, barcode, or ISBN.

Run the cover stages in this exact order:

```bash
python3 pipeline/generate_cover.py front
# visually approve front_cover_art.png before continuing
python3 pipeline/generate_cover.py back
# visually approve back_cover_art.png before continuing
python3 pipeline/cover.py
```

`pipeline/cover.py` is the deterministic typography contract: Andika
Bold/Regular; colourful `MJ` and `Wobbly Days` words with a white stroke (the
small `and the` connector is intentionally plain dark brown); translucent cream
rounded copy panels; dark-brown body copy; purple tagline panel; 60–75 px outer
safe margins; lower-right white ISBN box. Any changed coordinates or font sizes
must still satisfy these enforced overflow checks: each multicolour title stays
inside its panel width; front copy and author panel stay above y=1065; back
synopsis stays above y=1060; tagline stays above y=1360; all outer edges retain
at least 60 px. `pipeline/cover.py` raises instead of saving on a violation.

If either art file fails visual review, rerun that side with `--force` (for
example, `python3 pipeline/generate_cover.py front --force`). This deletes only
the approved cover-art copy, preserves every attempt render/log row, and uses
only the attempts remaining in that side’s four-attempt revision budget. If a
replacement front is approved, regenerate the back with `--force` so continuity
is checked against the new front.

Cover attempt baselines are explicitly front→1 and back→1. Each side’s stop
boundary is baseline+4 across all invocations; old or rejected art does not
reset the budget.

Composite these exact front strings as real text:

- `MJ and the Wobbly Days`
- `A story about courage, difference, and living with MS`
- `Written by MJ Donnellan`

Composite this exact back copy as real text:

```text
Imagine loving to run, jump, and dance…
until one day your body feels a little wobbly.

Join MJ on a brave and heartwarming journey as she learns what it means to live with MS—and discovers that even on wobbly days, you can still shine bright.
```

Use this exact back-cover tagline:

```text
To every wobbly day, there is courage.
To every challenge, there is light.
```

Do not invent an ISBN. Reserve a white lower-right box labelled
`ISBN / barcode area`.

## Verification and acceptance

1. `python3 pipeline/validate_manuscript.py` prints `32 pages OK`.
2. Check only runtime/human manuscript prose (not plan commentary) for lowercase
   `mum`; expected count is zero:

   ```bash
   python3 - <<'PY'
   import re
   from pathlib import Path
   import yaml
   pages = yaml.safe_load(Path('MJ_BOOK_PRODUCTION/01_MANUSCRIPT/pages.yaml').read_text())
   locked = Path('MJ_BOOK_PRODUCTION/01_MANUSCRIPT/locked_manuscript.txt').read_text()
   assert not any(re.search(r'\bmum\b', p['text']) for p in pages)
   assert not re.search(r'\bmum\b', locked)
   print('lowercase mum: 0')
   PY
   ```
3. Every regenerated page’s latest approval-log row is `PASS` and
   `requirements_match=True`.
4. The engineering lead uses the execution environment’s image `Read` viewer
   to check each of 9, 10, 11, 12, 13, 14, 16, 23, 31, and 32 against its
   specific numbered criterion above. Append one
   line per page to `MJ_BOOK_PRODUCTION/09_NOTES/change_log.txt` in this format:
   `feedback revision visual QA: page NN PASS — <criterion observed>`.
   Record a rejected machine PASS before rerunning as
   `feedback revision visual QA: page NN REJECT — <visible failure>`.
5. All 32 approved PNGs and 32 layout PNGs are 2048×1448; unaffected approved
   pages are byte-identical to commit `a4d5e6b`.
6. Interior proof has exactly 32 pages; cover proof has exactly two pages.
   Latest `cover-front` and `cover-back` approval-log rows are `PASS` with
   `requirements_match=True`.
7. Page 1 dedication is legible and inside the safe zone. Changed prose on
   pages 10, 12, 16, 17, 18, and 29 is verbatim and does not overlap art.
8. Both final cover PNGs are 2048×1448, all cover text is legible and complete,
   MJ is on-model, and no generated/baked text remains visible underneath.
9. Final working-tree changes are limited to this plan, the original plan,
   manuscript sources, affected render/approved/layout artifacts, approval and
   change logs, proof PDF, cover source/reference and deliverables, and the
   pipeline modules named above.
10. After all checks above pass, inspect the complete diff for unrelated files,
    commit the complete revision once, then push `main` to `origin`.
