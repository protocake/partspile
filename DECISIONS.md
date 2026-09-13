# Decisions

Non-obvious choices, per `KICKOFF.md`. Newest first.

## 2026-09-12 — repo split by fresh copy, not history rewrite (Ben's call)

43. **Two brand-new single-commit repos instead of git filter-repo.** Ben: keep this dir+history as a private archive; create `partspile` (public, all code at HEAD, no history) and `partspile-fixtures` (private, all data: fixture photos, truth.json, staging, full eval log + raw runs, design/bin02_small.jpg). No purge, no force-push, no SHA rewrite — the personal data never enters the public repo's history at all. Ben also lifted the holdout READ restriction (he can reshoot a fresh holdout batch later); the never-EVAL-against-holdout rule stands. tools/split_fixtures.sh is obsolete, superseded by this. New public repo name `partspile` chosen to match product/PyPI/sibling-clone convention (DECISIONS #8 said naming is Ben's call — one `gh repo rename` if he disagrees).

## 2026-09-11 — productization Approach A (Ben's pick from two architect blueprints)

41. **Minimal-diff productization, cloud-first onboarding.** Ben chose the ship-soonest blueprint over the full clean-product one (8–9d): flat `~/.partspile/` data dir (not XDG/Application Support — matches `~/.ollama`-style sibling tools for the technical-maker audience), flat KEY=VALUE `~/.partspile/config` seeded into `os.environ` at import with env-always-wins precedence, `/setup` key-paste page gating `/` and `/capture` only for `provider=anthropic` with no key, `partspile` CLI whose fresh-install nudge to `anthropic` fires only when no config file and no provider/key env exist (dev checkouts running uvicorn keep the `claude_code` default, DECISIONS #19 intact). Legacy `./data/` CWD shim keeps Ben's existing DB/photos working with zero migration. One functional deviation from the pure blueprint: the worker resolves its provider lazily per run — building it at startup would crash the worker on a fresh install (the Anthropic SDK raises at client construction without a key) and the /setup flow would never take effect. `cutout.swift` moved into the package (`partspile/native/`) as package data; `ensure_cutout_binary()` prefers a brew-precompiled `partspile-cutout` on PATH. `python-multipart` + fastapi/uvicorn promoted from optional/undeclared to base deps — they were already required in practice (README installed them by hand), so this declares reality rather than adding a new dependency.

42. **Eval fixtures resolve via `PARTS_PILE_FIXTURES_DIR` > sibling `partspile-fixtures/fixtures` clone > `REPO/fixtures`.** Ben also ruled `evals/log.md` moves to the private repo at split time (it describes his photo set); the public log resets to its header and logs public-sample runs only. `fixtures/README.md` is NOT edited by Claude (hard rule: nothing under `fixtures/` is ever modified) — the bring-your-own docs live in the main README, and any fixtures/README change is on Ben's split checklist. History purge (git filter-repo + force push) is a Ben-executed step, never run by the loop.

## 2026-09-09 — photo-reject flow shipped (completes DECISIONS #30a)

40. **Whole-photo verdicts via an app-only schema variant.** AppBinIdentification adds photo_feedback (per-shot ok/retake + reason); claude_code gains identify_app() used by the worker (other providers fall back to plain identify). The EVAL schema is untouched — banked tuning iterations stay byte-comparable. Feedback stored on ident_runs (schema v5); capture queue and browse rail surface "📷 retake?" with the reason. The capture-time immediate-reshoot prompt UX can deepen later; the signal now exists end to end.

## 2026-09-09 — house glossary shipped (Layer 3 of novel-parts strategy)

39. **Every human-vetted part now teaches future scans.** The worker injects a glossary of accepted/edited parts (distinct canonicals, newest-first, capped at 60, undetermined and 'unidentified' excluded — never teach a guess) into the identification prompt for all providers. The fixture eval stays first-encounter by default; `eval.py --glossary file.json` enables the second-encounter mode so the lift is measurable, not assumed. Wording guards against force-matching ("never force a match onto a different-looking part") to protect lookalike safety.

## 2026-09-08 — schema-forced decisions (Ben approved) + local park

38. **Local-only schema enums shipped: LocalPart adds unit_type + legibility, ordered so the grammar answers legibility before confidence; the provider enforces consequences** (drops self-declared attached components; illegible → needs_reshoot forced, confidence capped). Claude's Part schema untouched for comparability. Result: best local precision (0.773) at the cost of recall_high (0.533) — the confidence cap converts bravado into visible caution. Local tuning parked at 5/8 iterations; no config dominates (see evals/log.md).

## 2026-09-08 — local model tuning outcome

37. **Local best: 0.708 precision / 0.667 recall_high / 7-8 reshoot (Qwen3.6-35b, 4 iterations).** Two harness bugs — not model weakness — caused the 0.119 baseline: Ollama's silent 4096-token head-truncation (the rules never reached the model) and thinking-on-by-default. Fixes: derived model `partspile-qwen` (num_ctx 16384), native `/api/chat` provider (`provider=ollama`) with think:false + grammar-enforced schema, and the v1-local honesty-heavy prompt (v2-local's single-first framing lifted recall but over-merged attached objects, e.g. strapped-on battery). Tuning budgets are per-provider (8 each); 4 local iterations banked. Recommended local config: PARTS_PILE_PROVIDER=ollama, PARTS_PILE_MODEL=partspile-qwen. Next levers if resumed: schema-forced decisions (unit_type/legibility enums — SCHEMA CHANGE, Ben's gate) or trying gemma4:26b.

## 2026-09-07 — single-item capture is the primary flow (Ben)

36. **Multi-part pile photos were an assumed requirement, not a real one.** Ben: since the KICKOFF the project has assumed one photo = many parts, but his actual usage is one item per photo (all real scans to date). The prompts' "identify EVERY distinct part" framing directly fuels the local model's decomposition failure. Correction: prompts now assume ONE part per photo as the common case ("count the physically separate objects; usually that's one") while still handling occasional multi-part shots — the fixture set keeps its two multi-part bins as the edge-case test. Not a schema change; the parts[] array stays.

## 2026-09-07 — scan/bin terminology settled (Ben, supersedes #34's naming)

35. **SCAN = the photo-group captured together; BIN = a per-part user field naming the physical container ("bin 12").** Ben: numbered-bin users are real; bin must be editable and belongs on the PART (one scan's parts can be sorted into different bins). Schema v3: tables/columns renamed bins→scans, bin_id→scan_id; parts gains `bin TEXT`. Migration order fix: version-gated ALTERs now run BEFORE the idempotent CREATEs on existing DBs (renames must precede table creation). UI: bin editable in modal + review edit; browse shows "bin · location", groups by bin, searches bin; CSV bin column now the real field. Live DB backed up before migration.

## 2026-09-07 — bins demoted to internal scan groups (Ben)

34. **"Bin" was a failed user-facing concept — auto-named at scan time, meaningless, uneditable (Ben).** Bins stay as the internal grouping for photos/scans (nothing migrates), but the UI now speaks only LOCATION: browse cards and review headers show location (or "no location"/"unfiled scan"), the scans rail shows location or "scan N", capture drops the label field, and the detail modal gains an editable location (PATCH /api/bins/{id}, applies to everything scanned together). Consistent with #23/#24: capture unit ≠ organization; the record is the product.

## 2026-09-07 — qrcode dependency (Ben approved)

33. **`qrcode` added (KICKOFF dependency gate: Ben approved 2026-09-07).** Pure-Python, BSD-licensed (initially reported as MIT — corrected), zero runtime sub-dependencies; SVG output only (no pillow). Powers the browse rail's phone-handoff QR to /capture. The endpoint still degrades to a URL-text fallback when the lib is absent, so the open-source install works without it.

## 2026-09-06 — M2 gate relaxed (Ben): momentum over perfection

32. **M2 ships at p=0.864 / rh=0.800 / reshoot 7-8 / 0 confusions; tuning parked with 5 of 8 iterations banked.** Ben's direct steer: stop noodling toward a perfect scanner — every layer improves later; run the loop to a complete state. The KICKOFF threshold gate (0.95/0.85) is deferred, not abandoned: banked iterations resume after Ben's pending truth edits land (HX1838 hidden_spec, ESP32 DevKit V1, PM11 ruling), each of which mechanically raises the score. From here the loop proceeds M3 → M6 without pausing for input except at KICKOFF hard gates.

## 2026-09-06 — novel parts (Ben's PM11 question)

31. **Post-training-cutoff parts are handled by review + house glossary, not by the model alone.** Layers: honest generic-description first contact (exists) → human teaches the name once in review (M5) → "house glossary" of known inventory parts injected into identification prompts so repeat encounters are named confidently (planned, post-M2; see PLAN "Novel-parts strategy"). Optional web-search boost in claude_code for readable-but-unknown markings. Implication for the eval: first-encounter truth for an unmarked novel part is properly a hidden_spec case; naming it is Layer-2/3's job. PM11's truth status remains Ben's call.

## 2026-09-06 — reshoot escalation features (Ben)

30. **Photo rejection + "can't be determined" state.** Ben's asks: (a) the app can reject a photo and request another (whole-photo verdict, not just per-part needs_reshoot) — lands in M4 as an optional `photo_feedback` block in the output schema, deferred until M2 tuning is frozen because schema text is embedded in prompts and changing it mid-tuning would contaminate iteration comparisons; (b) `parts.resolution = undetermined` — a terminal review state that keeps the best-guess name, stops the reshoot loop, and shows an "unverified" badge. The reshoot loop thus has three exits: resolved by reshoot, edited by human, or explicitly given up. DB-side in M3, UI in M5, zero model/eval impact today.

## 2026-09-06 — M2 iteration 1 findings (eval-side fixes)

28. **Matcher v2: conservative token matching, and re-scores don't burn tuning iterations.** Iteration 1 showed exact-string canonical matching scoring near-perfect IDs as misses ("28BYJ-48" vs "28BYJ-48 5V", "DWM3001CDK" vs "Qorvo DWM3001CDK"). New rules: normalize is punctuation/dot-insensitive (V10.4.6 == V1046); names match on exact equality, token-subset (with guards), or ≥2 shared digit-bearing "specific" tokens. Lookalike-safe by construction: confusable designations differ precisely in their digit tokens (KY-023 vs KY-040 can never fuzzy-match — tested). Interpretation of the KICKOFF 8-iteration cap: it counts LIVE runs with a changed prompt; re-scoring a saved predictions file (zero model calls) is eval development, logged with a "re-score" note. Live v1 run = iteration 1; next live run (v2 prompt) = 2 of 8.
29. **Hidden-spec wildcard now covers ALL hidden_spec truth parts, not just "unidentified" ones.** Truth knows the obscured DIP is an L293D only because of Ben's close-ups; the bin photo cannot reveal it. The model's "unknown 16-pin DIP IC" + needs_reshoot is the correct answer and was being triple-penalized (recall, precision, reshoot). Name matching still runs first; the wildcard only consumes leftover needs_reshoot predictions. Supersedes the #26 prefix-only rule.

## 2026-09-05 — truth completion + eval wildcard rule

26. **"Unidentified" truth parts match needs_reshoot predictions, not names.** Two fixture parts are unknowable even to Ben (the wrapped component; the buzzer's passive/active type). A truth part that nobody can name can never be name-matched, so a perfectly-behaving pipeline (counts the part, flags reshoot, guesses a name at low confidence) would lose precision through no fault of its own. Rule: truth canonicals starting with "unidentified" match any leftover same-bin prediction with `needs_reshoot=true` (after normal name matching; they never steal name-matched predictions). A confident wrong guess still takes the full precision + reshoot penalty — the rule rewards admitted uncertainty only. Buzzer handled via aliases instead (passive/active/piezo → "buzzer") since the part-kind IS knowable. Tested (tests 21–24).
27. **Photo 4 decoded as the KICKOFF overlap hard case.** Two DIP-16 ICs overlap in the shot (L293D + SN74HC595N, confirmed by close-ups, both hidden_spec) with the SW-520D lying across them. The close-up campaign also corrected KY-040→KY-023 (capless joystick), identified the QC module as an HX1838 IR receiver, the TO-92 as 2N2222A, and the Nano's MCU as ATmega328P. Truth-reference close-ups stay out of pipeline inputs.

## 2026-09-05 — capture path (Ben)

25. **Interim phone→repo path: `tools/photo_inbox.py`.** Ben's photo workflow (phone → iCloud sync → Photos.app → export) is too slow; the real fix is M4's capture PWA, but fixtures need photos now. The inbox is a stdlib-only LAN upload page (phone shoots → file lands in a chosen repo dir, prefix+timestamp named, refuses `fixtures/` targets). Explicitly scaffolding: M4 replaces it; it validates the M4 requirement (direct phone→server capture, no cloud round-trip) with zero dependencies.

## 2026-09-05 — product positioning (Ben)

24. **Core product = the photo-based part scanner; the record matters more than the organization.** Ben's framing: even if every scanned part goes back into one giant shoebox, the win is a searchable record of what he owns so he stops re-buying parts he already has. Consequences: (a) "do I already have this?" search is the killer query — M6 browse prioritizes search + qty over grouping polish; (b) location stays optional everywhere (a capture-form field, never required); (c) vs Binner: no pivot — they bet on organization/retrieval (incl. their light-up bin hardware), we bet on intake/identification; a Binner-format CSV export at M6 is the optional bridge (see research/landscape.md).

## 2026-09-05 — fixture review walkthrough (with Ben)

21. **No lookalike pair exists in the collection yet (Ben's call).** The KICKOFF "zero confusion between the two lookalike breakouts" criterion is deferred, not relaxed silently: eval.py's `--lookalikes` stays unwired until such parts arrive, and the M2 threshold reads precision/recall/needs_reshoot only for now.
22. **Truth-reference close-ups never enter the pipeline.** Photos 2, 4, and 10 have deliberately-unreadable details (mystery KY module, DIP-14 IC, cylinder, TO-92s, Nano MCU) that stay `hidden_spec` cases — the pipeline must answer `needs_reshoot`. Ben's close-up shots exist only to fill the answer key and live in `fixtures_staging/truth_reference/`, not `fixtures/photos/`. This preserves KICKOFF's bad-shot hard cases while making truth verifiable.
23. **"Bin" = capture unit, not physical organization.** Ben has no physical bins yet; binNN ids are synthetic per-photo groups. Physical bin/location assignment is an app feature (capture form field), not a fixture prerequisite.

## 2026-09-05 — non-blocking capture (Ben)

20. **Capture never waits on identification.** Submit enqueues an `ident_runs` row (`status=queued`) and returns instantly; a single in-process asyncio worker executes runs in order. SQLite-as-queue + in-process worker chosen over a real broker (Celery/Redis) deliberately: zero new dependencies, one process to run, durable across restarts, and worker concurrency of 1 is actually desirable while the provider is `claude_code` (Max usage-window politeness). `PARTS_PILE_WORKERS` exists if a future provider wants parallelism. The trade-off (queue throughput capped by one process) is irrelevant at one-household scale.

## 2026-09-05 — provider default

19. **`claude_code` provider is the build-phase default (Ben's call: no per-scan API billing).** Ben has a Claude Max subscription with spare quota; the pipeline's default backend shells out to headless Claude Code (`claude -p --output-format json`), which runs on that subscription — smoke-tested working on the LAN box. Zero new dependencies (subprocess to the installed CLI). Trade-offs accepted: slower per scan, Max usage-window limits, JSON enforced by prompt+validation+one retry instead of server-side structured output. The `anthropic` (API key) and `openai_compat` (local open-weight) backends stay first-class; the open-source release documents those two as the public paths since subscription auth is per-seat. The `ANTHROPIC_API_KEY` blocker is dropped — nothing blocks M2 now except fixtures.

## 2026-09-05 — post-M1 QA prep + Ben's additions

15. **`recall_high` excludes hidden-spec truth instances (numerator and denominator).** Found while building the QA demo: a correctly-handled hidden-spec part (medium confidence + needs_reshoot) was dragging recall_high below threshold, which would reward false high confidence on unresolvable parts. Hidden-spec parts are scored solely by the needs_reshoot metric. Supersedes the recall_high definition in #10.
16. **Spec-page links (Ben, 2026-09-05): `parts.spec_url`.** Human-entered or heuristic (review/browse UI offers a "search datasheet" link built from the canonical name). The vision model never emits URLs — LLM-fabricated links are worse than none. Distributor API lookup stays out of scope per KICKOFF.
17. **Key image (Ben, 2026-09-05): `parts.key_photo_id`** FK to photos; defaults to the bin's first shot; settable in review and browse.
18. **Holdout = a future photo batch.** Ben will shoot more photos later as the holdout; all 13 current photos become the tuning set, so Claude may view them once staged into `fixtures/photos/`. Supersedes the "don't view Photos/" caution in #14 for the current batch (still: only Ben populates `fixtures/`).

## 2026-09-05 — M1 (eval.py)

10. **Metric definitions.** `recall_high` = truth instances matched by `confidence=="high"` predictions / all truth instances (this is the KICKOFF 0.85 gate; plain recall is also reported). Lookalike confusion = predicted twin B (unmatched by real truth B) in a bin whose truth contains twin A, symmetric; pairs supplied via `--lookalikes A::B` once fixtures name them. Hidden-spec part correct only if matched AND every matching prediction sets `needs_reshoot` — an unmatched hidden-spec part counts as incorrect (missing the part entirely is not "correctly flagged").
11. **Tests use stdlib `unittest`** (runs under `python3 -m unittest` or pytest) — avoids adding any dependency before the KICKOFF dependency-approval gate matters; pytest isn't installed on the loop box.
12. **`eval.py --run` (live pipeline mode) deliberately stubs until M2** — eval-first build order means the scorer exists before the thing it scores; `--from-json` is the M1 interface and stays the replay/debug interface forever.
13. **Holdout guard in code**: eval.py hard-refuses any `--truth` path containing "holdout".
14. **`Photos/` (raw drops) is git-ignored and unviewed.** Ben stages raw photos there; Claude does not open them until Ben designates the holdout split, so the holdout stays untuned-on. Only Ben moves/renames photos into `fixtures/`.

## 2026-09-05 — Initial planning

1. **Provider abstraction from day one.** Ben added a requirement: eventual open-source release should support a local open-weight model. Rather than retrofit, the vision call goes behind a `VisionProvider` protocol with two backends — `anthropic` (official SDK, default) and `openai_compat` (one adapter covers Ollama/vLLM/LM Studio/llama.cpp, so no per-model code). Prompt, schema, and eval stay provider-neutral.
2. **Default model `claude-opus-5`**, overridable via `PARTS_PILE_MODEL`. Structured output via the SDK's `messages.parse()` with the pydantic schema.
3. **Eval matching on normalized canonical + explicit alias table.** Aliases handle legitimate synonyms only and live in eval code where they're reviewable; they must never mask the lookalike-breakout confusion check.
4. **Quantity-aware scoring**: truth qty N = N instances; credit min(predicted, truth).
5. **`ROADMAP.md` is the autonomous loop's durable state.** Each loop iteration picks the first unchecked item, works it, updates the file, commits on green. Blockers are recorded there, not silently waited on.
6. **Packaging: `pyproject.toml` + pip/venv.** Smallest standard thing; no poetry/uv requirement for contributors.
7. **License: MIT** planned for M7 — flagged for Ben's confirmation before publishing, not a today-decision.
8. **Repo name vs product name**: repo is `ElectronicsIdentifier`, product is "Parts Pile" per the brief. Keeping both; repo rename is Ben's call.
9. **Tests use synthetic data only.** `fixtures/` is Ben's, never modified, never used in unit tests; `fixtures/holdout/` is never read at all.
