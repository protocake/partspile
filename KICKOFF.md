# Parts Pile: Kickoff Brief

This is a starting brief, not a spec. Read it, then run Ultraplan to produce the actual plan. Where this brief is silent, decide and note the decision in `DECISIONS.md`.

## What we are building

A self-hosted tool that turns photos of a pile of hobbyist electronics (Arduino, ESP32, sensor modules, breakouts, bare components) into a structured, searchable inventory. Phase 1 is capture, identify, review, store, browse. Phase 2 (later, not now) is project recommendations from the inventory, ranked by fewest additional parts to buy.

## Why this project exists (two goals, both matter)

1. Ben wants the tool. Nothing on the market does bulk-photo-to-electronics-inventory (see `research/landscape.md` if present; summary: generic bin tools like OpenBin do photo-to-inventory but are not electronics-aware; electronics ID apps are single-part only).
2. Ben is using this build to test how far Claude Code gets running autonomously with minimal approval. Design your work so it is self-checking. Prefer measurable progress over asking.

## Fixture set (Ben provides, you never modify)

- `fixtures/photos/` with names like `bin03_shot1.jpg`. Multiple shots of the same bin share a prefix.
- `fixtures/truth.json`: per bin, the expected parts with `canonical`, `category`, `qty`, and optionally `hidden_spec` for cases where a single photo cannot resolve something (e.g. encoder photographed shaft-down, so pin count is unknown).
- `fixtures/holdout/` is a test split. Do not read it, do not eval against it, do not tune on it. Ben checks it manually at the end.
- Known hard cases in the set: a clear LED (color unresolvable optically), a bare Songle relay vs a relay module, a rotary encoder with pins hidden, two visually similar breakouts, one overlap shot, one bad-lighting shot.

## Build order (non-negotiable)

1. `eval.py` first. Scores pipeline output against `truth.json`. Report per-part precision and recall, plus a separate score for correctly setting `needs_reshoot` on hidden-spec cases. Log every run to `evals/log.md` with prompt version, model, and scores.
2. Identification pipeline until eval passes threshold: recall of at least 0.85 on parts with confidence high, precision of at least 0.95, zero confusion between the two lookalike breakouts, and correct `needs_reshoot` on every hidden-spec case.
3. Storage (SQLite).
4. Web UI: capture, review, browse.

## Identification output shape (starting point, refine in plan)

One call per bin, all shots of that bin passed together so the model can cross-reference angles. Structured output, roughly:

```
parts[]:
  name                  human-readable
  canonical             e.g. KY-015, SRD-05VDC-SL-C, ESP32-WROOM-32 devkit
  category              board | sensor | actuator | display | power | passive | connector | bare_component | other
  interface             i2c | spi | uart | analog | digital | onewire | pwm | none | unknown
  voltage               e.g. 3.3V, 5V, 3.3-5V, unknown
  qty
  confidence            high | medium | low
  needs_reshoot         bool
  reshoot_reason        what angle or detail would resolve it
  bbox                  optional, per shot, for later "highlight in photo"
```

Prompt should know to read passive markings (a 512 resistor is 5.1k), distinguish bare components from modules, and prefer canonical maker designations (KY-xxx, GY-xxx, common devkit names).

## UI (minimal, phone-first)

- Capture: PWA-installable page, camera input, bin/location field, "add another angle" button, submit.
- Review: parsed table beside the photos, one-tap accept, edit, delete per row, then commit. This step is where real accuracy comes from; do not skip it.
- Browse: search, filter by category and interface, group by location, CSV export.

## Stack constraints

- Python, FastAPI, SQLite, Anthropic SDK with structured output. Plain HTML plus HTMX or minimal JS. No frontend build step.
- Runs on a LAN box; phone hits it over Wi-Fi.
- API key from env only. Never in repo.

## Rules of engagement for the autonomous run

- Never modify anything under `fixtures/`.
- Commit after each milestone that passes eval. Meaningful commit messages.
- Stop and ask only for: schema changes to the output shape, new third-party dependencies beyond the stack above, or anything touching the holdout.
- Cap prompt-tuning at 8 eval iterations. If threshold is not met by then, stop, write up what failed and why in `evals/log.md`, and wait.
- Do not overfit the prompt to the fixture photos. If a change only helps one specific photo, it is probably overfitting.
- Record every non-obvious choice in `DECISIONS.md`.

## Out of scope for phase 1

Project recommendations, user accounts, cloud hosting, native apps, fine-tuned vision models, distributor API integration.

## First action

Read this file, inspect `fixtures/`, then run Ultraplan. Produce the plan, then start with `eval.py`.
