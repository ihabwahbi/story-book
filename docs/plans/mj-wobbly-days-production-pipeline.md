# MJ and the Wobbly Days — AI Illustration Production Pipeline

## 1. Summary

This plan builds a complete, scripted production pipeline that generates all 32 interior page illustrations for the children's picture book *MJ and the Wobbly Days*, keeps the main character **MJ visually identical on every page**, and assembles the final book PDF with the manuscript text laid into reserved text-safe zones (each illustration keeps ~35% of its area low-detail and character-free so printed text can be placed there later; defined fully in §7). Generation uses **gpt-image-2 via the Codex CLI's built-in image-generation tool** (verified working in this environment with reference-image conditioning), gated by an automated character-fidelity QA loop. The plan is fully self-contained: the entire locked manuscript, character bible, style rules, prompt templates, asset triage table, and verified command syntax are embedded below. No external document is required to execute it.

---

## 2. Context

The repository `/workspace/projects/story-book` is a client production handoff, not a codebase. It contains:

- `MJ and the Wobbly Days Production Handoff.pdf` — the master spec: locked title/manuscript, character bible, 32-page structure, layout rules, approval process.
- `MJ and the Wobbly Days Illustration Style Bible.pdf` — the locked rendering style, prompt boilerplate, QA tests.
- `reference images/` — 36 WhatsApp-compressed JPEGs: the approved character canon, a turnaround sheet, approved page style anchors, a pose library from a previous production run, **and several rejected drift images mixed in**.

The client's previous attempt failed for one reason: **character drift**. AI tools kept changing MJ (taller, slimmer, yellow, glossy, clothed, different face) when generating full scenes. The client's stated rule: *"If MJ does not look like the approved MJ v1.0, the image fails, even if the scene is beautiful."* and *"Character fidelity first. Scene beauty second. Text layout third."*

The goal of this work: produce all 32 approved page illustrations plus the assembled book PDF, with zero character drift, using the tooling available in this environment.

**Key environment facts (all verified in this environment, July 2026):**

| Fact | Value |
|---|---|
| Repo path | `/workspace/projects/story-book` (NOT a git repo yet) |
| Codex CLI | v0.142.5 at `/home/linuxbrew/.linuxbrew/bin/codex`, authenticated via ChatGPT login (`~/.codex/auth.json`), default model `gpt-5.5` |
| Codex image generation | Feature `image_generation` is `stable true` (check: `codex features list \| grep image`). Invoked with `$imagegen` in the prompt. Uses **gpt-image-2**. Billed to the ChatGPT subscription. |
| `OPENAI_API_KEY` | **Not available** — neither in env nor in `~/.codex/auth.json`. The raw OpenAI Images API cannot be called. Codex is the only authenticated generation route. |
| Python | 3.14 with **Pillow 12.1.1** and **PyYAML** installed. `reportlab` NOT installed — do not use it. `pip` available if needed. |
| Network | Available (needed once, to download a font). |
| Generated image output | Codex saves generated images under `~/.codex/generated_images/<uuid>/ig_<hash>.png` and prints the path in its stdout. Codex's own sandboxed shell **cannot** copy/move files (bwrap failure in this environment) — the pipeline must harvest the file itself from the printed path. |
| Verified output size | A request for "~1.414:1 landscape" produced 1495×1052 (1.421:1). The built-in tool honors aspect ratio approximately, not exact pixel sizes. Output ≈1.5 MP. |

**Verified end-to-end proof** (already run successfully in this environment; the output was on-model MJ):

```bash
cd /tmp/opencode/mj-test   # contained MJ_CANON_01.jpeg and MJ_turnaround.jpeg
codex exec --skip-git-repo-check --image MJ_CANON_01.jpeg,MJ_turnaround.jpeg -- \
  '$imagegen Using the two attached reference images as the exact character authority ... generate ONE image of this exact fluffy warm-orange pear-shaped character MJ, standing and waving happily, on a plain light cream background. ... Landscape aspect ratio approximately 1.414:1.'
```

Command-syntax gotchas (all hit and resolved during verification — do not rediscover them):

1. `-i/--image` is **variadic** and will swallow the prompt if the prompt follows it directly. Always use the comma-separated form followed by `--`: `--image a.jpeg,b.jpeg -- '<prompt>'`.
2. `codex exec` refuses to run in a non-git, untrusted directory without `--skip-git-repo-check`. (After Phase 0 makes the repo a git repo this is belt-and-braces; keep the flag anyway.)
3. Wrap the prompt in **single quotes** so the shell does not expand `$imagegen`.
4. Do NOT ask Codex to save/copy/rename the image — its sandboxed shell fails (`bwrap: loopback: Operation not permitted`). Parse the generated-image path from stdout instead (it appears as `/home/<user>/.codex/generated_images/<uuid>/` and/or a full `.png` path inside a fenced block).

---

## 3. Principles for implementers

- **Character fidelity is the only definition of success.** A beautiful page with the wrong MJ is a failure. Every generated image passes the QA gate (§8.3) before it is accepted. Never hand-wave a borderline image through; regenerate instead.
- **Best long-term design over ease of implementation.** This is a production system, not a one-off script: manuscript as data, idempotent per-page regeneration, an audit trail, one canonical reference bundle.
- **One primary path.** The generation engine is Codex CLI `$imagegen` behind a single module boundary (`pipeline/engine.py`, one public function). Do not build a second engine, fallbacks, or compatibility shims. If an `OPENAI_API_KEY` materializes later, the same interface gets reimplemented — that is a future change, not scope here.
- **No band-aids.** If a page keeps failing QA, fix the prompt/reference bundle, don't photoshop the output.
- **The plan's embedded data is the source of truth.** Manuscript text in §7 is locked — copy it verbatim, never paraphrase. The title is exactly *MJ and the Wobbly Days* (never "MJ and her Wobbly Days" or any variant — that exact wrong title appears on rejected reference images).
- Commit at the end of every phase with a message naming the phase.

---

## 4. Current state of the repository (grounded walkthrough)

```
/workspace/projects/story-book/
├── MJ and the Wobbly Days Illustration Style Bible.pdf     (17 pp — style lock)
├── MJ and the Wobbly Days Production Handoff.pdf           (28 pp — master spec)
├── docs/plans/mj-wobbly-days-production-pipeline.md        (this file)
└── reference images/                                       (36 JPEGs, WhatsApp naming)
    ├── WhatsApp Image 2026-07-05 at 1.32.03 PM.jpeg        (no number)
    ├── WhatsApp Image 2026-07-05 at 1.32.03 PM (1).jpeg
    ├── ...                                                  ((1) through (34))
    └── WhatsApp Image 2026-07-05 at 1.32.04 PM.jpeg        (note: 1.32.04, no number)
```

There is no code, no git history, no build system. The PDFs' contents that matter for execution are fully transcribed into this plan (§6–§8); implementers do not need to parse the PDFs (they may open them to double-check, but this plan is authoritative for the work).

The 36 reference images are an **untriaged dump** from the previous production run. Verified by visual inspection: it contains the primary canon image, the official turnaround sheet, approved scene anchors, ~19 pose-library cards (three have baked-in labels like "POSE 15 — Afraid to cross a room" matching the client's pose list), and **at least 5 rejected images** exhibiting exactly the drift the project must avoid (wrong title text, elongated glossy MJ, slogans). The full triage mapping is in §8.1 — nothing may be used as a generation reference until triage is done.

---

## 5. Target design and rationale

### End state

```
/workspace/projects/story-book/                (git repo)
├── docs/plans/…                               (this plan)
├── MJ_BOOK_PRODUCTION/
│   ├── 01_MANUSCRIPT/pages.yaml               (32 page specs: text, scene, refs, layout — from §7)
│   ├── 02_CHARACTER_CANON/                    (MJ_CANON_01, turnaround, movement support)
│   ├── 03_APPROVED_STYLE_ANCHORS/             (approved scene-style images, renamed)
│   ├── 04_REJECTED_DO_NOT_USE/                (quarantined drift images)
│   ├── 05_POSE_LIBRARY/                       (pose cards, renamed)
│   ├── 06_RENDERS/page_NN/attempt_K.png       (every raw generation, kept)
│   ├── 07_APPROVED/page_NN.png                (exactly 32 finished images, 2048×1448, √2 ratio)
│   ├── 08_FINAL_LAYOUT/
│   │   ├── pages/page_NN_layout.png           (illustration + text composited)
│   │   └── MJ_and_the_Wobbly_Days_proof.pdf   (32-page book proof)
│   └── 09_NOTES/approval_log.csv              (one row per generation attempt, QA verdicts)
├── pipeline/
│   ├── engine.py        (generate_image(prompt, ref_paths) -> Path; Codex wrapper + harvest)
│   ├── prompts.py       (builds the full page prompt from pages.yaml entry + style-lock blocks)
│   ├── qa.py            (fidelity gate: Codex vision call -> verdict dict; logs to approval_log.csv)
│   ├── generate_page.py (CLI: python3 pipeline/generate_page.py <page_nn>; loop gen→QA→retry)
│   ├── finish.py        (center-crop to exact √2, resize to 2048×1448, write 07_APPROVED)
│   └── layout.py        (text layout into safe zones, assemble proof PDF with Pillow)
└── assets/fonts/Andika-Regular.ttf … (OFL font for layout)
```

### The generation strategy (the decision)

**Full-scene generation per page, conditioned on a fixed canon reference bundle, behind an automated fidelity gate.** For each page, the engine receives up to 4 reference images — always `MJ_CANON_01` + the turnaround sheet, plus the lighting-matched approved style anchor and (when useful) a matching pose card — and a prompt composed of: the style-lock block, the MJ character-lock block, the page scene brief, the text-safe-zone instruction, and the negative list (§8.2). Every output is judged by a vision QA pass against the canon (§8.3) before acceptance; failures regenerate with the failure reason appended to the prompt.

For **recurring supporting characters** (Mum, the Doctor, the Cousin), use *progressive canon*: the first approved page featuring that character becomes an additional reference image for every later page featuring them (mapping in §7).

### Why this design (and one deliberate deviation from the client's handoff)

The client's handoff §15 recommends a three-session pipeline: MJ pose cards → empty backgrounds → mechanical compositing ("Do not redraw MJ"). **This plan deliberately replaces that with reference-conditioned full-scene generation.** Reasons, all evidence-backed:

1. The compositing recommendation was written to work around older image models that drifted when drawing MJ inside scenes. That constraint is obsolete: gpt-image-2 (released 2026-04) processes all reference images at high input fidelity automatically, and a live test in this environment produced an on-model MJ from the canon references in one shot.
2. The client's own Style Bible §11 dooms mechanical compositing: *"A composite fails if MJ looks like a sticker placed on top of the scene"* — but fixing lighting/edge integration without "redrawing MJ" is precisely what raster compositing cannot do well. Full-scene generation gives one painting with one light by construction.
3. The client's own approved anchors (hospital scene with Mum, art-room scene with the Cousin — see §8.1) are themselves full-scene generations with on-model MJ, proving the approach passes their bar.
4. What the plan **keeps** from the handoff is its real insight: canon-first references, one page at a time, a hard fidelity gate, quarantined rejects, and an approval log.

### Alternatives rejected

- **Handoff-literal compositing pipeline** — rejected per above; weaker foundation, fights the style bible.
- **Raw OpenAI Images API (`images/edits`, up to 16 refs, exact sizes like 2896×2048)** — architecturally the cleanest engine, but there is **no API key in this environment** (verified). Not buildable now. The engine interface (`engine.generate_image`) is designed so this becomes a drop-in reimplementation later. Recorded as open question OQ-1.
- **3D/Unreal MJ asset** — the handoff itself scopes it out as too heavy for one book.

### Resolution / print note

Codex's built-in tool outputs ≈1.5 MP (verified 1495×1052). The pipeline standardizes finished pages at **2048×1448** (exact √2 within rounding; a mild ~1.37× Lanczos upscale), which is proof/digital quality (~250 dpi at A5 ≈ 210×148 mm). True 300+ dpi print masters require the raw API at 2896×2048 — deferred behind OQ-1. The `finish.py` stage isolates this: only that stage changes if/when print masters are regenerated.

---

## 6. Scope

**In scope**

1. Repo scaffolding, git init, asset triage of all 36 reference images.
2. `pages.yaml` manuscript data file (from §7, verbatim).
3. Pipeline code: engine, prompt builder, QA gate, per-page driver, finisher, layout/PDF assembler.
4. Pilot run (3 pages), then all 32 interior pages generated, QA-passed, finished at 2048×1448.
5. Final layout: manuscript text placed in text-safe zones; 32-page proof PDF.
6. Approval log covering every attempt.

**Out of scope**

- The **external book cover** (the handoff states "The external cover is separate"). Do not generate one.
- Print-master resolution regeneration (blocked on OQ-1 / API key).
- Any raw OpenAI API integration, second engine, or fallback path.
- 3D/Unreal asset work.
- Editing/rewriting manuscript text (it is locked).

---

## 7. The manuscript and page specifications (locked — source of truth)

Phase 1 converts this section verbatim into `MJ_BOOK_PRODUCTION/01_MANUSCRIPT/pages.yaml`.

**Global layout rule:** odd-numbered pages sit on the right of a spread → gutter left → **text-safe zone on the RIGHT ~35% of the image**. Even-numbered pages sit on the left → gutter right → **text-safe zone on the LEFT ~35%**. The text-safe zone must be low-detail, softly colored, free of MJ, faces, and important props.

**Lighting classes** (used by the prompt builder):
- `title` — quiet warm cream, calm welcoming.
- `happy_outdoor` — warm sunlight, bright but soft, playful, not overexposed.
- `home` — warm indoor light, cosy, safe, soft shadows.
- `home_muted` — home but slightly muted colours, gentle shadows, never frightening, never bleak.
- `hospital` — cream and pale blue, clean but not cold, warm safety, no harsh clinical lighting.
- `art_room` — warm indoor, creative, bright orange accents.
- `classroom` — warm, soft, gentle daylight interior.
- `night` — soft moonlight/starlight + warm indoor lamp glow, peaceful not spooky.

**Reference-bundle keys** map to files created in Phase 0 (§8.1): `CANON` = `02_CHARACTER_CANON/MJ_CANON_01.jpeg`, `TURN` = `02_CHARACTER_CANON/MJ_v1_turnaround_sheet.jpeg`, anchors as named in §8.1. `APPROVED(n)` means "the already-approved `07_APPROVED/page_nn.png`" (progressive canon for supporting characters — requires generating pages in numeric order).

| Pg | Text (verbatim, for layout stage — NEVER inside the image) | Scene brief | Lighting | Text-safe side | Refs beyond CANON+TURN | Notes |
|----|---|---|---|---|---|---|
| 1 | MJ and the Wobbly Days\nA story about courage, difference, and living with MS\nWritten by MJ Donnellan | Quiet title-page illustration. MJ standing calmly on the LEFT third. A soft warm orange ribbon motif flows horizontally. Large clean cream space on right for title. | title | right | anchor_page01_title | The canon image IS this composition; aim to match it closely. |
| 2 | MJ loved to move. | MJ joyful, energetic, mid-movement (leaping/dancing), soft warm abstract background, uncluttered. | happy_outdoor | left | anchor_joyful_sky | |
| 3 | She danced while breakfast cooked.\nShe spun across the kitchen floor in her socks. | Warm cosy kitchen, MJ dancing/spinning mid-twirl. MJ wears simple plain cream/off-white socks — the ONLY page with any clothing. | home | right | anchor_kitchen_socks | Socks: simple, no patterns, no shoes. |
| 4 | She ran barefoot through the grass.\nShe twirled until the world went dizzy and fell into giggles.\nMovement made MJ feel free. | Outdoor grass meadow, sky, flowers; MJ barefoot running/twirling, joyful freedom. | happy_outdoor | left | anchor_outdoor_meadow, MJ_CANON_SUPPORT_01_running | |
| 5 | Until one day…\nsomething changed. | MJ paused mid-step in a familiar warm home hallway, uncertain expression, subtle stillness. | home_muted | right | anchor_home_hallway, pose_paused_midstep | Page 5 drifted repeatedly in the previous run — expect extra retries. |
| 6 | Her legs felt strange.\nHeavy.\nWobbly. | MJ standing unsteadily, legs unstable/heavy, arms slightly out for balance. Gentle uncertainty, not slapstick. | home_muted | left | pose_wobbly_balance | |
| 7 | Her hands dropped things she was sure she was holding.\nAnd some mornings, MJ woke up tired before the day had even begun. | One single scene (no collage): MJ looking at a soft dropped object (e.g. a wooden toy) at her feet, tired eyes, morning bedroom light. | home_muted | right | pose_dropping_blocks, pose_tired_rubbing_eye | |
| 8 | At first, nobody understood.\nNot even MJ.\n'Maybe you just need more sleep,' people said.\n'Maybe you're doing too much.' | MJ small and quiet in a warm room, feeling misunderstood; other people implied (soft shadows/doorway), not shown. | home_muted | left | pose_confused_scratch | |
| 9 | But MJ knew.\nSomething didn't feel right. | MJ quiet, inward, sitting alone, knowing look, gentle stillness. | home_muted | right | pose_sad_seated | |
| 10 | Then one day, after her legs shook and her eyes went blurry, MJ found herself in a big hospital room, holding her mum's hand so tightly her fingers hurt. | Soft safe hospital room, MJ seated holding Mum's hand tightly. Mum: warm human woman, shoulder-length brown hair, cosy cardigan, gentle. Safe, not scary. NO hospital gown on MJ. | hospital | left | anchor_hospital_mum | Defines Mum's canon look — anchor_hospital_mum shows it. |
| 11 | That was the day the doctors said words MJ had never heard before:\nMultiple Sclerosis.\nMS. | Kind female doctor (short hair, warm smile, no scary tools) gently talking; MJ and Mum together listening. No scary medical imagery. | hospital | right | anchor_hospital_mum, APPROVED(10) | Defines Doctor's canon look. |
| 12 | Her mum rubbed circles on her hand.\n'What does that mean?' MJ whispered. | Close, intimate: Mum holding/rubbing MJ's hand, MJ looking up asking. | hospital | left | APPROVED(10), pose_reaching_hand | |
| 13 | The doctor smiled kindly.\n'It means the messages from your brain to your body sometimes get a little mixed up.' | Doctor kneeling/leaning to MJ's level explaining gently; optional soft visual metaphor (gentle swirling dotted line motif), no technical diagrams. | hospital | right | APPROVED(11) | |
| 14 | MJ blinked.\n'Like bad phone reception?'\nThe doctor laughed softly.\n'A little bit like that.' | MJ with curious brightening expression, doctor softly laughing. Child-friendly, warm. | hospital | left | APPROVED(11), pose_curious_thinking | |
| 15 | Sometimes MS made walking harder.\nSometimes it made MJ tired.\nSometimes sore.\nSometimes shaky.\nAnd sometimes scared. | MJ walking carefully across a warm home room, one careful step, concentrating. Safe and gentle. | home_muted | right | pose_careful_step | |
| 16 | 'Will I always be different?' MJ asked quietly.\nHer mum squeezed her hand.\n'Yes,' she said gently.\n'But different does not mean less.' | Quiet emotional moment: MJ and Mum close together (sofa/bedside), hand squeeze. | home_muted | left | APPROVED(10), pose_vulnerable_with_adult | |
| 17 | That didn't make everything easier.\nThere were still hard days.\nDays MJ fell over.\nDays her legs wouldn't listen.\nDays she cried because her body felt cross with her. | MJ sitting on the floor after a gentle stumble, small tears, hugging a knee. Gentle, not dramatic. | home_muted | right | pose_sad_curled | |
| 18 | Days people said things that hurt.\n'But you don't look sick.' | MJ hurt by words, looking down; other children implied softly (partial figures/shadows at edge), MJ the clear focus. | home_muted | left | pose_hurt_standing | |
| 19 | MJ wished they could see what she felt.\nThe aching in her legs.\nThe tiredness behind her smile.\nThe fear that came when she had to walk across a room by herself. | MJ at one side of a room, facing the long distance across it; hidden-symptom mood, brave-but-afraid. | home_muted | right | pose_afraid_to_cross | |
| 20 | But little by little…\nMJ learned something.\nShe was still MJ.\nStill funny.\nStill brave.\nStill full of colour.\nStill full of dreams. | Self-recognition: MJ seeing herself (mirror motif allowed), warm hopeful light and colour returning. | home | left | pose_self_recognition | |
| 21 | On wobbly days, she moved slower.\nOn tired days, she rested.\nOn hard days, she asked for help. | ONE strong restful image (no montage/collage): MJ resting cosily (blanket/cushion), calm and accepting. | home | right | pose_resting | |
| 22 | And one afternoon, while painting swirls of bright orange across a canvas, her little cousin asked:\n'What are you making?'\nMJ smiled.\n'My messy storm.' | Warm art room: MJ painting big orange swirls on a canvas/easel, paintbrush in hand; little Cousin (small human child, curious) watching. MJ dominant. | art_room | left | anchor_art_room | Defines Cousin's canon look. |
| 23 | Her cousin frowned.\n'It looks sunny too.'\nMJ grinned.\n'It can be both.' | Cousin and MJ looking at the swirl painting together; sunny/stormy duality visible in the painting. | art_room | right | APPROVED(22), anchor_painting_look | |
| 24 | That made her cousin think very hard.\nThen he smiled.\n'Oh.'\nAnd maybe life could be like that too. | Quiet reflective beat: Cousin thinking then softly smiling, MJ beside the painting. | art_room | left | APPROVED(22) | |
| 25 | Hard and beautiful.\nScary and brave.\nDifferent and wonderful. | Symbolic, simple, poetic: MJ peaceful amid soft orange swirls/light (echo of the painting), minimal scene. | art_room | right | APPROVED(22) | |
| 26 | Soon MJ began sharing her story.\nShe told children that some differences are easy to see…\nand some are hidden. | MJ gently speaking to a small group of listening children (diverse, simple, soft style); MJ the focus. | classroom | left | anchor_art_room | No classroom anchor exists; rely on style-lock + canon. |
| 27 | Some people use wheelchairs.\nSome wear hearing aids.\nSome need medicine.\nSome need extra rest.\nAnd everyone deserves kindness. | Inclusive, age-appropriate children/community scene (a child with a wheelchair, a hearing aid — gentle, simple); MJ present and warm. | classroom | right | APPROVED(26) | |
| 28 | One little girl raised her hand.\n'So being different isn't bad?'\nMJ smiled.\n'No.' | A little girl with raised hand asking; MJ smiling reassuringly. | classroom | left | APPROVED(26) | |
| 29 | She looked around the room.\n'Different just means we all have different stories.'\nA quiet voice whispered from the back:\n'That makes the world more interesting.' | Warm classroom/group scene, children listening, cosy togetherness. | classroom | right | APPROVED(26) | |
| 30 | MJ felt tears sting her eyes.\nBecause once, she thought being different meant something was wrong with her.\nBut maybe…\nit just meant her story looked different. | MJ emotionally moved, gentle glistening tears, warm light — moved, not despairing. | home | left | pose_moved_tears | Distinct from the night pages; warm indoor. |
| 31 | That night, MJ stood at her window looking at the stars.\nHer legs hurt.\nHer body was tired.\nBut her heart felt full. | MJ at her bedroom window at night, stars outside, warm lamp inside; tired but peaceful. | night | right | anchor_night_window | |
| 32 | Because even on the wobbly days…\nshe was still learning.\nStill growing.\nStill shining.\nAnd being different?\nThat was never something to hide.\nThat was something to honour. | Final hopeful image: MJ peaceful and quietly proud, stars or warm glow. NO magical cure imagery (MJ is not "fixed"). | night | left | APPROVED(31), pose_proud_peaceful | |

`pages.yaml` schema (one list, 32 entries):

```yaml
- page: 3
  text: "She danced while breakfast cooked.\nShe spun across the kitchen floor in her socks."
  scene: "Warm cosy kitchen, MJ dancing/spinning mid-twirl. MJ wears simple plain cream/off-white socks — the ONLY page with any clothing."
  lighting: home
  text_safe_side: right        # derived: odd page -> right, even page -> left
  refs: [anchor_kitchen_socks] # beyond the always-included CANON + TURN
  notes: "Socks: simple, no patterns, no shoes."
```

---

## 8. Embedded production rules (used by Phases 0, 2, 3)

### 8.1 Asset triage table (Phase 0 executes this)

Source directory: `/workspace/projects/story-book/reference images/`. All files named `WhatsApp Image 2026-07-05 at 1.32.03 PM (N).jpeg` — abbreviated to `(N)` below; two files have no number: `…1.32.03 PM.jpeg` and `…1.32.04 PM.jpeg`. **Copy (do not move) into the new structure; leave the original folder untouched as delivered-material record.** Verdicts marked ⚠ must be visually re-confirmed by the implementer at triage time (open the image; check against §8.4 checklist).

| Source | Destination under `MJ_BOOK_PRODUCTION/` | Content (verified) |
|---|---|---|
| `…1.32.03 PM.jpeg` (no number) | `02_CHARACTER_CANON/MJ_CANON_01.jpeg` **and** copy as `03_APPROVED_STYLE_ANCHORS/anchor_page01_title.jpeg` | THE primary canon: MJ left, cream bg, orange ribbon, 1024×718 (≈1.426) |
| `(2)` | `02_CHARACTER_CANON/MJ_v1_turnaround_sheet.jpeg` | Official turnaround: Front/Left/Right/Back/¾ + 7 labeled expressions, 1448×1086 |
| `(1)` ⚠ | `02_CHARACTER_CANON/MJ_CANON_SUPPORT_01_running.jpeg` | MJ joyful movement in meadow, near-square — matches the spec's "running/movement support reference". Use ONLY for movement energy, never to override proportions |
| `(11)` | `03_APPROVED_STYLE_ANCHORS/anchor_home_hallway.jpeg` | MJ walking carefully in warm hallway, 1024×718 |
| `(13)` | `03_APPROVED_STYLE_ANCHORS/anchor_hospital_mum.jpeg` | Hospital room, Mum comforting MJ (defines Mum's look), 954×1024 |
| `(14)` | `03_APPROVED_STYLE_ANCHORS/anchor_art_room.jpeg` | MJ painting orange swirls, Cousin watching (defines Cousin's look), 1024×768 |
| `(15)` | `03_APPROVED_STYLE_ANCHORS/anchor_night_window.jpeg` | MJ at night window with stars, 1024×768 |
| `(16)` | `03_APPROVED_STYLE_ANCHORS/anchor_outdoor_meadow.jpeg` | MJ in meadow with clean text-safe panel, 1024×718 |
| `(17)` | `03_APPROVED_STYLE_ANCHORS/anchor_kitchen_socks.jpeg` | Kitchen dancing in cream socks (socks are APPROVED here — page 3 exception), 1024×718 |
| `(18)` | `03_APPROVED_STYLE_ANCHORS/anchor_joyful_sky.jpeg` | MJ jumping against soft pastel sky, 1024×718 |
| `(21)` | `03_APPROVED_STYLE_ANCHORS/anchor_adult_hand.jpeg` | MJ worried beside adult hand, 1232×864 |
| `(22)` | `03_APPROVED_STYLE_ANCHORS/anchor_painting_look.jpeg` | MJ contemplating painting, 1376×768 (1.79:1 — style/content reference only, never a layout reference) |
| `(4)` | `05_POSE_LIBRARY/pose_waving.jpeg` | Waving, plain bg |
| `(7)` | `05_POSE_LIBRARY/pose_tired_rubbing_eye.jpeg` | Tired, rubbing eye |
| `(8)` | `05_POSE_LIBRARY/pose_dropping_blocks.jpeg` | Startled, blocks falling |
| `(9)` | `05_POSE_LIBRARY/pose_worried_small.jpeg` | Worried, small full body, landscape |
| `(10)` | `05_POSE_LIBRARY/pose_wobbly_balance.jpeg` | One foot lifted, balancing, worried |
| `(12)` | `05_POSE_LIBRARY/pose_wobbly_balance_b.jpeg` | Near-duplicate of (10) |
| `(19)` ⚠ | `05_POSE_LIBRARY/pose_determined_march.jpeg` | Marching/determined; proportions read slightly tall — re-check; quarantine if elongated |
| `(20)` | `05_POSE_LIBRARY/pose_resting.jpeg` | Lying resting; has baked label "POSE 18 — Resting / For Page 21" (fine for a reference, never for output) |
| `(23)` | `05_POSE_LIBRARY/pose_startled_blocks_b.jpeg` | Startled with falling toys |
| `(24)` | `05_POSE_LIBRARY/pose_sleepy.jpeg` | Sleepy, rubbing eye |
| `(25)` | `05_POSE_LIBRARY/pose_confused_scratch.jpeg` | Scratching head, confused |
| `(26)` | `05_POSE_LIBRARY/pose_curious_thinking.jpeg` | Finger on cheek, thinking |
| `(27)` | `05_POSE_LIBRARY/pose_reaching_hand.jpeg` | Reaching for adult hand |
| `(28)` | `05_POSE_LIBRARY/pose_frightened.jpeg` | Frightened, hand near mouth |
| `(29)` ⚠ | `05_POSE_LIBRARY/pose_thoughtful_smile.jpeg` | Thoughtful smile; slight tall-read — re-check |
| `(32)` | `05_POSE_LIBRARY/pose_sad_seated.jpeg` | Sad, seated, hugging knee |
| `(33)` | `05_POSE_LIBRARY/pose_sad_curled.jpeg` | Sad, curled in |
| `(34)` | `05_POSE_LIBRARY/pose_afraid_to_cross.jpeg` | Baked label "POSE 15 — Afraid to cross a room" |
| `…1.32.04 PM.jpeg` | `05_POSE_LIBRARY/pose_self_recognition.jpeg` | Baked label "POSE 16 — Still MJ / self-recognition"; MJ with hand mirror |
| `(3)` | `04_REJECTED_DO_NOT_USE/rejected_elongated_glossy.jpeg` | Off-model: taller/slimmer, longer humanlike limbs, glossy 3D finish |
| `(5)` | `04_REJECTED_DO_NOT_USE/rejected_back_cover_slogans.jpeg` | Baked title/slogans/ISBN ("MJ and her Wobbly Days.." etc.) |
| `(6)` | `04_REJECTED_DO_NOT_USE/rejected_wrong_title_cover.jpeg` | Wrong title "MJ and her wobbly days", baked text, off-model MJ |
| `(30)` ⚠ | `04_REJECTED_DO_NOT_USE/rejected_proportion_drift_a.jpeg` | Elongated limbs/proportion drift |
| `(31)` ⚠ | `04_REJECTED_DO_NOT_USE/rejected_proportion_drift_b.jpeg` | Tall/less-compact drift |

Some `pose_*` keys listed in §7 have no library card (`pose_paused_midstep`, `pose_careful_step`, `pose_vulnerable_with_adult`, `pose_hurt_standing`, `pose_moved_tears`, `pose_proud_peaceful`). This is expected: per the single missing-ref rule (Phase 1), unresolvable `pose_*` keys are dropped with a warning — the scene brief carries the pose in words. All non-pose keys in §7 WILL resolve after this triage; if one does not, triage was done wrong. Do NOT generate new pose cards; the pose library is reference-only in this design.

### 8.2 Prompt template (Phase 2 implements this in `pipeline/prompts.py`)

Every page prompt is assembled as: `$imagegen ` + blocks A+B+C+D+E joined with blank lines.

**Block A — reference declaration** (adjust indices to the actual attachment order):
> The attached images are the character and style authority. Image 1 is MJ_CANON_01, the primary approved reference for the character MJ — it controls face, body shape, orange colour, fur texture, freckles, eyes, hair tufts, hands, feet and proportions. Image 2 is the approved MJ turnaround sheet. {One sentence per additional attachment, chosen by its key type: `anchor_*` or `APPROVED(n)` → "Image N is an approved page from the same book showing the required scene style and supporting character appearance."; `pose_*` → "Image N is an approved pose reference for MJ's body attitude only."; `MJ_CANON_SUPPORT_01_running` → "Image N is an approved movement-energy reference only — never override Image 1's proportions with it."} MJ must match these references exactly.

**Block B — style lock (verbatim from the client's Style Bible):**
> Use the approved soft painterly children's storybook style. MJ must match the approved MJ v1.0 references exactly. Do not use flat cartoon, model-sheet, anime, glossy 3D, plastic toy, realistic, medical poster, or generic mascot style. Use warm soft digital painterly rendering, gentle brush texture, rounded forms, soft shadows, warm colour harmony, and child-safe emotional tone. MJ and the background must look painted in the same world, with the same light direction, warmth, softness and brush texture.

**Block C — character lock:**
> MJ is a warm orange, fluffy but not shaggy, compact pear-shaped creature with large expressive brown eyes with white sclera and catchlights, small curved eyebrows, freckles on both cheeks, upward orange hair tufts, soft controlled plush-like fur, a rounded pear-shaped body, short rounded arms and legs, and simple rounded hands and feet. MJ wears no clothing{ except: <per-page clothing note>}. MJ must NOT become tall, slim, elongated, bean-shaped, smooth, plastic, overly shaggy, yellow, baby-like, human-like, animal-like, or mascot-like.

**Block D — the page scene** (from `pages.yaml`): scene brief sentence(s) + the lighting sentence "Lighting: <the verbatim description for this class from §7's lighting-class list>." + this layout sentence with `{side}`/`{other}` filled from `text_safe_side`:
> Composition: single full-bleed scene, landscape aspect ratio approximately 1.414:1 (like 1456x1024). Place MJ and all scene interest in the {other} two-thirds of the image. Keep the {side} roughly 35% of the image as a clean, low-detail, softly coloured area with no characters, no faces and no important objects — it will hold printed text later.

**Block E — negatives (every page):**
> Absolutely no text, letters, words, titles, captions, labels, slogans, logos, watermarks, page numbers or signage anywhere in the image. No collage, no grid, no panels, no borders. Not square, not portrait. If any ribbon motif appears it must be orange, never purple. No purple awareness ribbons. No scary medical equipment. One single scene only.

On QA retry, append: `Previous attempt failed review because: <failure reasons>. Correct exactly these issues while keeping everything else consistent with the references.`

### 8.3 QA gate (Phase 3 implements this in `pipeline/qa.py`)

For each candidate image, run a **vision review via Codex** (model gpt-5.5 reads images natively):

```bash
codex exec --skip-git-repo-check \
  --image MJ_BOOK_PRODUCTION/02_CHARACTER_CANON/MJ_CANON_01.jpeg,MJ_BOOK_PRODUCTION/02_CHARACTER_CANON/MJ_v1_turnaround_sheet.jpeg,<candidate.png> -- \
  '<QA prompt below>'
```

QA prompt (verbatim; `{side}` from the page spec):

> Image 1 is the approved canonical reference for the character MJ. Image 2 is the approved turnaround sheet. Image 3 is a candidate book-page illustration. Judge the candidate STRICTLY. Answer with ONLY a JSON object, no markdown fence, with keys: "mj_match" (bool: same face, eye style with white sclera and catchlights, freckles on both cheeks, upward hair tufts, warm orange colour, plush controlled fur), "proportions" (bool: compact pear-shaped body, SHORT rounded arms and legs — false if tall, slim, elongated or long-limbed), "no_unapproved_clothing" (bool — cream socks are permitted ONLY if the scene is a kitchen dance), "style_match" (bool: soft painterly storybook, not flat cartoon, not glossy 3D, not anime), "no_text" (bool: true if there is NO text, lettering, labels or signage anywhere), "single_scene" (bool: no collage, grid or panels), "landscape" (bool: clearly wider than tall), "text_safe_zone" (bool: the {side} ~35% of the image is low-detail and free of characters and faces), "no_purple_ribbon" (bool), "child_safe" (bool: emotionally gentle, nothing frightening), "failures" (array of short strings describing every false item, empty if all true).

Parsing: strip any accidental code fences, `json.loads`, verdict = all ten booleans true. Any `false` → FAIL; log the row and regenerate with failures appended (§8.2). After **4 failed attempts** on a page, stop that page and surface it to the human operator with the four candidates and their failure lists — do not endlessly burn quota. Additionally, `landscape` is pre-checked in Python (width/height ≥ 1.25 else auto-fail without a QA call), since it's free.

`09_NOTES/approval_log.csv` columns:
`timestamp,page,attempt,render_path,mj_match,proportions,no_unapproved_clothing,style_match,no_text,single_scene,landscape,text_safe_zone,no_purple_ribbon,child_safe,verdict,failures`

### 8.4 Human-eye checklist (used at triage ⚠ marks and final review)

1. Does MJ match MJ_CANON_01 (face, eyes, freckles, tufts, fur, colour)? 2. Compact pear shape, short rounded limbs? 3. No unapproved clothing? 4. Same painterly storybook world as the anchors? 5. No baked-in text of any kind? 6. Clean text-safe zone on the correct side? 7. Feels safe and warm for a 3–6-year-old?

---

## 9. Implementation phases

Execute in order. Each phase ends with a git commit. All paths relative to `/workspace/projects/story-book`.

### Phase 0 — Scaffolding and asset triage

**Do:**
1. `git init`; add a `.gitignore` containing nothing for now (all assets are tracked; renders included — they are small and the audit trail matters). Initial commit of the existing files (PDFs, reference images, this plan).
2. Create the `MJ_BOOK_PRODUCTION/` tree exactly as in §5 (folders `01_…`–`09_…`, plus `06_RENDERS/`, `07_APPROVED/`, `08_FINAL_LAYOUT/pages/`).
3. Execute the triage table (§8.1): **copy** each source file to its destination name. For the five ⚠ rows, open each image (Read tool) and confirm the verdict with checklist §8.4; if any ⚠ item is actually off-model, send it to `04_REJECTED_DO_NOT_USE/` instead (and conversely, keep a ⚠-rejected item quarantined unless it clearly passes); note every ⚠ decision in `09_NOTES/change_log.txt`.
4. Verify every one of the 36 source files is accounted for: each of the 36 sources appears exactly once in the triage table, and the destination copies number **37** (the no-number canon file is intentionally copied to TWO destinations: `02_CHARACTER_CANON/MJ_CANON_01.jpeg` and `03_APPROVED_STYLE_ANCHORS/anchor_page01_title.jpeg`).
5. Create `assets/fonts/` and download the layout font: `curl -L -o assets/fonts/Andika-Regular.ttf "https://github.com/google/fonts/raw/main/ofl/andika/Andika-Regular.ttf"` and same pattern for `Andika-Bold.ttf`. Verify each file is a valid TTF: `python3 -c "from PIL import ImageFont; ImageFont.truetype('assets/fonts/Andika-Regular.ttf', 24)"`. (Andika is an SIL OFL font designed for young readers. If the URL 404s, any OFL rounded child-friendly font works — record the substitution in `09_NOTES/change_log.txt`.)

**Accept when:** tree exists; 36/36 files mapped; fonts load in Pillow; committed.

### Phase 1 — Manuscript as data

**Do:** Create `MJ_BOOK_PRODUCTION/01_MANUSCRIPT/pages.yaml` with all 32 entries, copying `text`, `scene`, `lighting`, `text_safe_side`, `refs`, `notes` **verbatim from the table in §7** (schema shown at the end of §7). Also write `MJ_BOOK_PRODUCTION/01_MANUSCRIPT/locked_manuscript.txt` for human proofreading: for each page, a line `--- Page N ---` followed by that page's text verbatim, then a blank line.
Write a validator `pipeline/validate_manuscript.py` that loads the YAML and asserts: 32 entries; pages 1–32 exactly once; every odd page has `text_safe_side: right` and every even page `left`; every `refs` key is either `APPROVED(n)` with n < page, or resolves by filename stem to an existing file in `02_CHARACTER_CANON/`, `03_APPROVED_STYLE_ANCHORS/`, or `05_POSE_LIBRARY/` (e.g. `anchor_kitchen_socks` → `03_APPROVED_STYLE_ANCHORS/anchor_kitchen_socks.jpeg`, `MJ_CANON_SUPPORT_01_running` → `02_CHARACTER_CANON/MJ_CANON_SUPPORT_01_running.jpeg`). **Missing-ref policy (single rule, applies everywhere): a `pose_*` key that resolves to no file is dropped with a warning; any other unresolvable key is a hard validation error.** Every `lighting` value must be one of the 8 classes in §7.

**Accept when:** `python3 pipeline/validate_manuscript.py` exits 0 and prints `32 pages OK`; committed.

### Phase 2 — Generation engine and prompt builder

**Do:** Implement:

- `pipeline/engine.py` — `generate_image(prompt: str, ref_paths: list[Path], dest: Path, timeout_s: int = 600) -> Path` (copies the harvested PNG to `dest`, creating parent dirs, and returns `dest`). Behavior:
  1. Record `start = time.time()`.
  2. Run via `subprocess.run` with an **argv list** (no shell): `["codex", "exec", "--skip-git-repo-check", "--image", "p1,p2,...", "--", prompt]`, capture stdout+stderr, cwd = repo root. **The single quotes shown in shell examples elsewhere in this plan are shell quoting only — never include literal quote characters in the argv prompt string.** The prompt string itself must begin with the literal characters `$imagegen ` (a token Codex parses, not an environment variable). The prompt string already begins with `$imagegen ` (prompts.py adds it). Pass refs in the order given (canon first — Block A's indices depend on it). Do not use `--sandbox` overrides; the default is fine because we never ask Codex to touch files.
  3. Harvest: regex stdout for `(/home/[^\s`'"]+/\.codex/generated_images/[^\s`'"]+)`. If a matched path is a `.png` file, use it; if it is a directory, glob `*.png` inside. Fallback: scan `~/.codex/generated_images/**/*.png` for files with mtime > start and take the newest. If nothing found, raise with the full stdout in the error.
  4. Copy the PNG to `dest` and return it.
- `pipeline/prompts.py` — `build_page_prompt(page_spec, ref_names_in_order, retry_failures=None) -> str` implementing §8.2 exactly (blocks A–E, lighting-class expansion per §7, `{side}` logic, retry suffix). Also `resolve_refs(page_spec) -> list[Path]`: always `[MJ_CANON_01, MJ_v1_turnaround_sheet]` first, then each key in `refs` resolved by the SAME rule as the Phase 1 validator — filename-stem search across `02_CHARACTER_CANON/`, `03_APPROVED_STYLE_ANCHORS/`, `05_POSE_LIBRARY/`; unresolvable `pose_*` keys dropped with a warning (they stay in `pages.yaml` untouched — dropping happens at resolution time in both validator and prompt builder); any other unresolvable key is a hard error; `APPROVED(n)` → `07_APPROVED/page_%02d.png` — hard error if that file doesn't exist yet, since pages must be produced in order. **Cap total refs at 4** (canon + turnaround + at most 2 more; prefer anchors/APPROVED over pose cards when trimming) — more attachments dilute conditioning and slow the call.
- Smoke test: `python3 -m pipeline.engine_smoketest` (small script) that generates one MJ-waving-on-cream image using canon+turnaround into `/tmp/opencode/engine_smoke.png` and prints its size. Visually confirm the character (checklist §8.4).

**Accept when:** smoke test produces a PNG ≥ 1024px wide, landscape, visually on-model; committed (smoke output not committed).

### Phase 3 — QA gate and approval log

**Do:** Implement `pipeline/qa.py`:
- `review(candidate: Path, page_spec) -> dict` — Python pre-check for landscape ratio (≥1.25), then the Codex vision call and JSON parse per §8.3 (canon, turnaround, candidate attached in that order).
- `log_attempt(row: dict)` — append to `MJ_BOOK_PRODUCTION/09_NOTES/approval_log.csv` (create with header if absent; columns per §8.3).
- Calibration check: run `review()` twice with this dummy page spec: `{"page": 0, "text": "", "scene": "calibration", "lighting": "title", "text_safe_side": "right", "refs": [], "notes": ""}` — (a) candidate = `02_CHARACTER_CANON/MJ_CANON_01.jpeg`: expect PASS, or at worst only `text_safe_zone` false; (b) candidate = `04_REJECTED_DO_NOT_USE/rejected_wrong_title_cover.jpeg`: expect FAIL with `no_text` and/or `proportions` false (it also fails the landscape pre-check — for this calibration only, bypass the Python ratio pre-check so the vision call itself is exercised). If (b) passes, the QA prompt is too lax — tighten wording ("Judge STRICTLY", enumerate failures) until it correctly rejects it.

**Accept when:** both calibration checks behave as stated; log file writes correctly; committed.

### Phase 4 — Finishing function, then page production (pilot, then all 32)

**Do — step 1, `pipeline/finish.py`** (implement this FIRST; the driver below depends on it):
- `finish(src: Path, dst: Path)`:
  1. Open with Pillow. Target ratio `2048/1448` (= 1.41436, √2 within rounding).
  2. Center-crop the long axis only (never crop >8% total; if the source is off by more, fail loudly — the QA gate should have caught gross ratio errors).
  3. `resize((2048, 1448), Image.LANCZOS)`, save PNG to `dst`.
- CLI `python3 pipeline/finish.py --redo-all`: for each page 1–32, re-run `finish()` from that page's **PASS render** — the `render_path` of the row with `verdict=PASS` in `09_NOTES/approval_log.csv` (if a page has multiple PASS rows, use the latest) — overwriting `07_APPROVED/page_NN.png`. Use this only if the finishing function itself changes.

**Do — step 2, `pipeline/generate_page.py`:**
- CLI: `python3 pipeline/generate_page.py <page_number>` and `--all`.
- Per page: skip immediately if `07_APPROVED/page_NN.png` exists (idempotent; to redo a page, delete that file). Loop up to 4 attempts: build prompt (attempt >1 appends prior failures) → `engine.generate_image(prompt, refs, dest=06_RENDERS/page_NN/attempt_K.png)` → `qa.review` → log. On PASS, call `finish(render, 07_APPROVED/page_NN.png)`. On 4 fails, print a loud summary and exit non-zero for that page.
- `--all` runs pages **in ascending order** (progressive canon requires it: e.g. page 11 attaches approved page 10), sequentially (no parallelism — subscription quota and harvest-race safety).

**Do — step 3, pilot (mandatory):** run pages **1, 10, 22** (title composition; hospital + Mum; art room + Cousin). After they pass automated QA, ALSO review each with your own vision against checklist §8.4 and compare side-by-side with `anchor_hospital_mum` / `anchor_art_room` for supporting-character resemblance. Only proceed when all three genuinely satisfy the checklist; otherwise adjust prompt blocks (record changes in `09_NOTES/change_log.txt`) and re-pilot.

**Do — step 4:** `python3 pipeline/generate_page.py --all` (expect roughly 1.5–3 min/page; budget for retries; if Codex returns a usage/rate-limit error, stop and report — see OQ-2).

**Accept when:** `07_APPROVED/` contains all 32 pages, each exactly 2048×1448 (verify with a 3-line Pillow loop printing sizes); `approval_log.csv` has a PASS row for each; every page spot-checked by eye (at minimum: 1, 3 [socks], 5 [historically drifty], 10–14 [Mum/Doctor recurrence], 22–25 [Cousin recurrence], 31–32 [night]); committed (renders + approved).

### Phase 5 — Layout and book assembly

**Do:** Implement `pipeline/layout.py`:
1. For each page: load `07_APPROVED/page_NN.png`, draw the page's `text` (verbatim from `pages.yaml`, preserving the `\n` line breaks) into the text-safe zone: a text block occupying the `text_safe_side` ~32% width (x margins 5% of page width, vertically centered).
2. Typography: Andika-Regular at ~54 px for body pages (auto-shrink to fit the block, floor 40 px, wrap on words, line-height 1.35); warm dark brown `#4A3426`; no boxes/frames — text sits directly on the low-detail zone. Page 1 is special: title in Andika-Bold ~96 px, subtitle ~48 px, author line ~40 px, all in the right-side zone.
3. Draw the page number small (~28 px, same brown, 3% from the outside bottom corner — right corner on odd pages, left on even).
4. Save each composite to `08_FINAL_LAYOUT/pages/page_NN_layout.png`, then assemble the proof PDF with Pillow: convert to RGB and `first.save("MJ_BOOK_PRODUCTION/08_FINAL_LAYOUT/MJ_and_the_Wobbly_Days_proof.pdf", save_all=True, append_images=rest, resolution=250)`.
5. Readability audit: before drawing, convert the text-block region to Pillow mode `"L"` (0–255 grayscale) and take its mean; if the mean is below 140 (on the 0–255 scale) the dark-brown text would sit on a dark area — render that page's text in `#FFFDF5` cream instead and note it in `change_log.txt`.

**Accept when:** PDF exists, 32 pages, opens correctly (`python3 -c "from PIL import Image; im=Image.open('...proof.pdf')"` is not sufficient — verify with `pdfinfo` if available or by re-reading page count via `pypdf` after `pip install pypdf`, or visually via extracted page images); text verbatim (spot-check pages 1, 16, 32 against §7 word-for-word); no text overlaps MJ or busy art on any page (eyeball all 32 layout PNGs); committed.

---

## 10. Cross-cutting concerns

- **Cost/quota:** every generation and QA call burns ChatGPT-subscription quota (~46K tokens per generation observed). Worst case ≈ 32 pages × 4 attempts × (gen + QA) — run sequentially, and stop on quota errors rather than thrashing (OQ-2).
- **Determinism/audit:** never delete renders or log rows; every attempt is traceable (page, attempt, verdict, failure reasons). The delivered `reference images/` folder is never modified.
- **Error handling:** engine raises with full Codex stdout on harvest failure; driver treats any engine/QA exception as a failed attempt and continues the retry loop. Such rows are logged with `verdict=ERROR`, all ten boolean columns empty, `render_path` empty if no image was produced, and `failures=["pipeline-error: <message>"]`. All `render_path` values in the log are **repo-relative** (e.g. `MJ_BOOK_PRODUCTION/06_RENDERS/page_05/attempt_2.png`) so `finish.py --redo-all` can read them back regardless of cwd.
- **Security:** no secrets exist in this pipeline; do not commit `~/.codex` contents; the two API keys visible in the ambient environment (`LINEAR_API_KEY`, `NEON_API_KEY`) are unrelated — never touch them.
- **Testing:** this pipeline's "tests" are the calibration checks (Phase 3), the smoke test (Phase 2), the manuscript validator (Phase 1), and the visual gates (Phases 4/5). No unit-test framework is warranted for ~400 lines of glue; correctness lives in the gates.

## 11. Verification (overall)

1. `python3 pipeline/validate_manuscript.py` → `32 pages OK`.
2. `ls MJ_BOOK_PRODUCTION/07_APPROVED | wc -l` → 32; Pillow loop → all 2048×1448.
3. `approval_log.csv` contains a PASS row for every page 1–32; no page has >4 attempts logged.
4. Final visual sweep (the client's own test, §8.4) on all 32 layout PNGs — MJ recognisably identical across the whole book; text verbatim; safe zones clean; title exactly *MJ and the Wobbly Days*.
5. Proof PDF: 32 pages, correct order, opens in a standard viewer.

## 12. Risks, edge cases, open questions

**Risks / edge cases**
- **Character drift remains possible** (gpt-image-2 docs warn recurring-character consistency can drift). Mitigated by canon-first refs + strict QA + retry-with-reasons + 4-attempt circuit breaker. Historically page 5 drifted; pages with humans (10–14, 22–29) are the next most likely to need retries.
- **Supporting-character drift** (Mum/Doctor/Cousin) is judged only by eye at the pilot and spot-checks — the automated QA gate covers MJ only. Progressive canon (`APPROVED(n)` refs) is the structural mitigation.
- **Codex output-size ceiling:** ~1.5 MP. Accepted for this deliverable (proof/digital ~250 dpi); print masters are OQ-1.
- **Harvest fragility:** Codex's stdout format may change; the mtime-scan fallback in `engine.py` covers it.
- **QA model leniency:** vision reviewers err lenient; the Phase 3 calibration against a known-rejected image is mandatory, and human spot-checks are non-negotiable.
- **`$imagegen` string:** must survive shell quoting (single quotes; it is a literal token Codex parses, not an env var).

**Open questions for the operator (do not block phases 0–5; note answers in `09_NOTES/`)**
- **OQ-1:** Will an `OPENAI_API_KEY` (platform billing) be provided? If yes, a follow-up work item reimplements `engine.generate_image` against `POST /v1/images/edits` with `model=gpt-image-2`, `size=2896x2048`, up to 16 refs, and regenerates print masters through the same QA gate. Nothing else in the pipeline changes.
- **OQ-2:** What is the ChatGPT plan's image-generation quota? If `--all` hits limits, production continues in batches across days — idempotency makes this safe.
- **OQ-3:** Can the client (Hasan) supply the original PNG canon files (`MJ_CANON_01_primary.png`, turnaround, approved pages)? The WhatsApp JPEGs are recompressed (canon is 48 KB); originals would improve conditioning. Swap-in is a file replacement in `02_CHARACTER_CANON/` + full regeneration decision by the operator.
- **OQ-4:** Does the client want the external cover produced later? (Out of scope here by their own spec.)

## 13. Reference

**Key paths**
- Spec PDFs: repo root (transcribed into §7–§8 of this plan; plan is authoritative).
- Source images: `reference images/` (read-only; triage map §8.1).
- Pipeline code: `pipeline/*.py`. Production tree: `MJ_BOOK_PRODUCTION/`.
- Codex binary: `codex` (v0.142.5); generated images land in `~/.codex/generated_images/<uuid>/`.

**Verified command shapes**
- Generate: `codex exec --skip-git-repo-check --image ref1.jpeg,ref2.jpeg -- '$imagegen <prompt>'`
- Feature check: `codex features list | grep image_generation` → `stable true`

**Terminology**
- *MJ_CANON_01* — the single highest character authority image. *Turnaround sheet* — 5 views + 7 expressions model sheet. *Style anchor* — an approved page image defining scene style. *Pose card* — MJ-only pose reference on cream. *Text-safe zone* — the ~35% low-detail area reserved for layout text. *Progressive canon* — using already-approved pages as references for later pages featuring the same supporting character. *Drift* — any deviation of MJ from canon; the project's failure mode.

**External docs**
- gpt-image-2 (model, sizes, reference images, limitations): https://developers.openai.com/api/docs/guides/image-generation and https://developers.openai.com/api/docs/models/gpt-image-2
- Codex CLI features (image inputs, `$imagegen`): https://developers.openai.com/codex/cli/features ; non-interactive mode: https://developers.openai.com/codex/noninteractive
- Andika font (SIL OFL): https://fonts.google.com/specimen/Andika
