# Parts Pile — Plan

Derived from `KICKOFF.md` (2026-09-05). Where this plan decides something the brief left open, the decision is logged in `DECISIONS.md`.

## Product summary

Self-hosted tool: photograph a bin of hobbyist electronics from multiple angles → vision model identifies every part with canonical designations → human reviews/corrects on phone → searchable SQLite inventory. **Core value (per Ben): the record, not the organization** — "do I already have this?" beats tidy shelving; a giant shoebox plus an accurate searchable inventory already stops duplicate purchases. Location is always optional. Phase 2 (out of scope now): project recommendations from inventory.

## Requirements

### Functional

- **FR1 Capture** — PWA-installable page; camera input; bin/location field; multiple shots per bin ("add another angle"); submit triggers identification. **Non-blocking**: submit enqueues and returns immediately so the user can start shooting the next bin right away — never wait for a scan to finish before capturing more.
- **FR2 Identify** — One model call per bin with *all* shots of that bin, so the model can cross-reference angles. Structured output per the schema below. Runs asynchronously off a queue (see architecture); each run has a visible status (queued → running → done/failed) and the review list updates as runs complete. Prompt knows passive markings (512 → 5.1k), bare component vs. module, canonical maker designations (KY-xxx, GY-xxx, devkit names), and when to flag `needs_reshoot` instead of guessing.
- **FR3 Review** — Parsed table beside photos; one-tap accept / edit / delete per row; commit writes to inventory. Per row: set the key image and add/edit a spec-page URL (with a one-click "search datasheet" helper that opens a search for the canonical name — the model itself never invents URLs). Two escalation paths (Ben, 2026-09-06):
  - **Retake flow**: reshoot-flagged rows (and photo-level rejects, below) show a "take another photo" action — new shots append to the bin and re-run identification as a new run. The review screen shows what specifically to photograph (the model's `reshoot_reason`).
  - **"Can't be determined"**: a per-part terminal state. When reshoots aren't worth it (or didn't help), one tap marks the part `undetermined`: the best-guess name is kept, the part stops asking for reshoots, and it displays with an "unverified" badge in browse. It's a first-class inventory row — searchable, countable — just honest about its identity. Editable later if the part is ever identified.
- **FR2a Photo rejection (M4)** — The pipeline can reject a photo outright, not just flag parts: blur, darkness, everything-overlapping. Design: an optional `photo_feedback` block in the identification output (per shot: ok/retake + reason), surfaced at capture time so the user reshoots before wasting a review pass. Deliberately NOT added to the output schema until M2 tuning is frozen — schema text is embedded in prompts, and changing it mid-tuning would contaminate iteration comparisons.
- **FR4 Store** — SQLite. Full provenance: which run, which model, which prompt version produced each row.
- **FR5 Browse** — Search; filter by category and interface; group by location; CSV export (includes spec_url). Each part shows its key image and links out to its spec page when set; key image and spec_url are editable here too.
- **FR6 Eval** — `eval.py` scores pipeline output against `fixtures/truth.json`: per-part precision/recall + separate `needs_reshoot` score on hidden-spec cases. Every run logged to `evals/log.md` with prompt version, provider, model, scores.

### Non-functional

- Python 3.11+, FastAPI, SQLite, plain HTML + HTMX. **No frontend build step.**
- Runs on a LAN box; phone hits it over Wi-Fi. Single process (`uvicorn`).
- API key from env only; never in repo.
- **Provider-agnostic vision backend** (see below) — required for the eventual open-source release to support local open-weight models.
- Open-source ready: no secrets, no personal data in code paths, permissive license, docs that let a stranger self-host.

## Architecture

```
partspile/
  config.py          env-driven settings (provider, model, base_url, db path)
  schema.py          pydantic models: Part, BinIdentification (the output shape)
  providers/
    base.py          VisionProvider protocol: identify(images, prompt_version) -> BinIdentification
    anthropic_.py    Anthropic SDK, structured output via client.messages.parse()
    openai_compat.py OpenAI-compatible endpoint (Ollama / vLLM / LM Studio / llama.cpp server)
  pipeline.py        image prep (resize/encode) + provider call + prompt versioning
  prompts/           versioned prompt files: v1.md, v2.md, ...
  db.py              SQLite schema + queries
  web/               FastAPI app, templates (capture / review / browse), PWA manifest
eval.py              CLI: run pipeline over fixtures/photos, score vs truth.json, append evals/log.md
tests/               unit tests with synthetic data (NEVER fixtures/holdout)
```

### Provider abstraction (open-weight path)

Three backends behind one protocol, selected by `PARTS_PILE_PROVIDER`:

1. **`claude_code`** (default during build-out) — shells out to headless Claude Code (`claude -p ... --output-format json --model $PARTS_PILE_MODEL`), which authenticates with Ben's Claude Max subscription: no per-scan API billing. The prompt instructs it to Read the shot files and emit only schema-conformant JSON; the provider validates against the pydantic schema and retries once on parse failure. Personal-use path only — subscription auth is per-seat, so the open-source release documents backends 2 and 3 for the public. Caveats: slower than the SDK, subject to Max usage windows, no server-enforced structured output.
2. **`anthropic`** — official Anthropic SDK with an API key, model from `PARTS_PILE_MODEL`, structured output validated against the pydantic schema. Verify current SDK shapes against the claude-api skill at implementation time. The switch for anyone (including future-Ben) who wants per-call billing and hard output guarantees.
3. **`openai_compat`** — any OpenAI-compatible server at `PARTS_PILE_BASE_URL` with JSON-schema response format. This one interface covers Ollama, vLLM, LM Studio, and llama.cpp server, i.e. all mainstream ways people run open-weight vision models (Qwen-VL family, Gemma 3, InternVL, Llama vision). No per-model code.

Rules that keep the abstraction honest:

- The prompt, the schema, and the eval are provider-neutral; only transport differs.
- `evals/log.md` records provider + model on every run, so open-weight candidates are benchmarked with the *same* eval and thresholds — the eval harness is the open-source story's proof that a local model is (or isn't) good enough.
- Anthropic-specific features (adaptive thinking config, etc.) live only inside `providers/anthropic_.py`.

### Identification output schema

As given in `KICKOFF.md` (name, canonical, category, interface, voltage, qty, confidence, needs_reshoot, reshoot_reason, bbox per shot). Schema changes require asking Ben. Represented once as pydantic models in `schema.py`; both providers and the DB serialize from it.

### Data model (SQLite)

- `bins(id, label, location, created_at)`
- `photos(id, bin_id, path, shot_index, taken_at)`
- `ident_runs(id, bin_id, provider, model, prompt_version, status, error, raw_json, created_at, started_at, finished_at)` — `status`: queued → running → done/failed. This doubles as the job queue: capture inserts a `queued` row and returns; a single in-process background worker (asyncio task in the FastAPI app — no new deps, no external broker) pulls the oldest queued run, executes the provider call, writes results. Worker concurrency 1 by default (`PARTS_PILE_WORKERS`) — scans are pipelined, not parallel, to stay polite to Max usage limits; the queue is what makes capture non-blocking. Failed runs are retryable from the review UI. Queued/running state survives restarts (it's in SQLite; the worker re-adopts stale `running` rows on startup).
- `parts(id, bin_id, source_run_id, name, canonical, category, interface, voltage, qty, confidence, needs_reshoot, reshoot_reason, bbox_json, status, spec_url, key_photo_id)` — `status`: pending → accepted/edited (review) — deleted rows removed. `spec_url` links a product/datasheet page (human-entered or heuristic; the vision model never fabricates URLs). `key_photo_id` FK → photos: the representative image for the part (defaults to its bin's first shot; settable in review/browse).

### UI pass v2 (Ben, 2026-09-06 — designed in the Parts Pile UI canvas)

- **Desktop-first**: the root page is Browse (mission control), with a QR-code panel that hands capture to the phone (QR encodes the server's LAN URL) and a scans-in-flight sidebar. Phone root can stay capture (user-agent or path split).
- **Review with part circles**: each part row gets a numbered ring overlaid on the photo from the model's bboxes (already captured in `bbox_json`); unclear parts get an amber dashed ring + spotlight dim + the reshoot ask naming the missing angle; selecting a row highlights its ring.
- **Part detail page** (click any browse entry): all fields inline-editable (serial, notes, qty, spec_url); photo strip keeps ALL captures; a **catalog photo** fetched from the part's product page may become the key image when better — original captures are never discarded (new photos.kind: captured | catalog).
- **Product-page lookup**: a "look up product page" action (and optionally an auto-enrich pass at accept time) web-searches the canonical name to fill `spec_url` and offer the catalog photo. Human confirms before anything is saved (no model-invented URLs — the lookup returns real search hits).

### Novel-parts strategy (parts newer than model training data)

New products will always outpace any model's training cutoff (case in point: NULLLAB PM11, 2026). Three layers:

1. **Honest first contact** (built): generic functional description + low confidence + needs_reshoot — never a hallucinated name. The eval rewards exactly this.
2. **Teach-once via review** (M5): the human overwrites the guess with the real canonical + spec_url. Each post-cutoff fact is supplied by the human exactly once.
3. **House glossary** (post-M2 / M5.5): at identification time, inject the inventory's known parts (canonical + one-line visual description, auto-drafted from the corrected entry and its key photo) into the prompt. Second encounter with any taught part → named with high confidence. Local learning, no retraining, compounds with inventory size. Optional booster: allow web search in the claude_code provider so a *readable but unknown* marking can be looked up live; unmarked novel parts rely on the glossary.

Eval note: the current fixture eval tests FIRST-encounter behavior (no glossary). When the glossary exists, a glossary-enabled eval mode can test second-encounter naming.

### Eval design

- Match predicted parts to truth per bin on normalized `canonical` (case/whitespace-insensitive; small alias table for legitimate synonyms, e.g. "SRD-05VDC-SL-C" vs "Songle 5V relay" — aliases live in eval, documented, and must not paper over real confusions).
- Quantity-aware: a bin with qty 3 of a part contributes 3 truth instances; credit `min(pred_qty, truth_qty)`.
- **Precision** = matched / predicted (target ≥ 0.95). **Recall on high-confidence parts** ≥ 0.85. **Zero** confusion between the two lookalike breakouts. `needs_reshoot` correct on **every** hidden-spec case (scored separately).
- Never reads `fixtures/holdout/`. Hard cap: 8 prompt-tuning iterations, then stop and write up.

## Milestones

Tracked with acceptance criteria in `ROADMAP.md` (the autonomous loop's state file). Order is non-negotiable per the brief: M1 eval → M2 pipeline to threshold → M3 storage → M4–M6 UI → M7 open-source prep.

## Open-source path (deferred work, non-deferred design)

Decisions that must be right *now* so open-sourcing later is cheap:

- Provider abstraction from day one (above).
- No secrets or Ben-specific paths outside env config; `.env.example` documents every variable.
- Fixtures stay Ben's private test set — the public repo ships with `eval.py` + truth-file format docs so others can build their own.
- At M7: LICENSE (MIT, pending Ben's confirmation), README quickstart (Anthropic path and local-model path), CONTRIBUTING notes.

## Risks / open items

- **Fixtures don't exist yet** — M2 onward is blocked until Ben adds `fixtures/photos/`, `fixtures/truth.json`, `fixtures/holdout/`. M1 (eval.py, tested with synthetic data in `tests/`) is not blocked.
- Local open-weight models may not hit the 0.95/0.85 thresholds; the eval log will show the gap honestly rather than lowering the bar.
- Phone camera → PWA capture has browser quirks (iOS Safari `capture` attribute behavior); mitigate with plain `<input type="file" accept="image/*" capture>` and manual testing at M4.
