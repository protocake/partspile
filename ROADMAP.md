# Roadmap — autonomous loop state

The loop protocol lives in `CLAUDE.md`. Work the first unchecked milestone top to bottom. Do not reorder. Update checkboxes and the Blockers section as part of every iteration.

## Blockers

- [ ] **Ben: provide fixtures** — `fixtures/photos/` (multi-shot bins, `binNN_shotN.jpg`), `fixtures/truth.json`, `fixtures/holdout/`. Blocks M2+. See `fixtures/README.md` for the expected format.
  - 2026-09-05: review walkthrough done — 13 capture units staged, all IDs confirmed except 5 TODO_ values pending Ben's truth-reference close-ups (shot list in `fixtures_staging/REVIEW.md`). Then Ben fills the TODOs and runs `fixtures_staging/apply.sh`. Holdout still = future batch.
- [x] ~~Ben: `ANTHROPIC_API_KEY` in the environment~~ — not needed: default provider is now `claude_code` (headless Claude Code on Ben's Max subscription, smoke-tested 2026-09-05). API key only needed if switching provider to `anthropic`. See DECISIONS.md #19.

## Milestones

- [x] **M0 — Scaffolding**: repo, plan, decisions, loop protocol, stubs. *(this commit)*
- [x] **M1 — eval.py + tests** *(done 2026-09-05; live `--run` mode intentionally arrives with M2)*
  - `eval.py --from-json` scores saved pipeline outputs vs `fixtures/truth.json`; refuses holdout paths.
  - Reports precision, recall, high-confidence recall, lookalike-confusion count (`--lookalikes A::B`), `needs_reshoot` accuracy on hidden-spec cases; `--strict` exit code gates CI/loop.
  - Appends every run to `evals/log.md` (prompt version, provider, model, scores).
  - 19 unit tests on synthetic data (`python3 -m unittest discover -s tests`), all passing.
- [x] **M2 — Identification pipeline** *(built + tuned to p=0.864 / rh=0.800 / reshoot 7-8 / 0 confusions; PARKED at 3 of 8 iterations by Ben's momentum-over-perfection call — DECISIONS #32)*
  - Done: partspile package, 3 providers (claude_code default), prompts v1–v3, eval --run, 42 tests.
  - Banked: 5 tuning iterations, resumed after Ben's truth edits (HX1838 hidden_spec, ESP32 DevKit V1 30-pin, PM11 ruling). Threshold 0.95/0.85 deferred, not abandoned.
- [x] **M3 — Storage** *(done 2026-09-06, commit 690e969)*: SQLite layer; ident_runs-as-queue (atomic claim, stale adoption, retry); parts with spec_url/key_photo_id/resolution.
- [x] **M4 — Capture UI** *(done 2026-09-06, commit e14f452)*: phone PWA capture, multi-shot, non-blocking submit, live queue cards + retry. (`photo_feedback` photo-reject still deferred until tuning frozen — in the scanning-improvements ticket.)
- [x] **M5 — Review UI** *(done 2026-09-06, commit caa09c5)*: accept/edit/delete, can't-determine, add-another-angle re-scan, dupe warning, spec_url + datasheet search.
- [x] **M6 — Browse UI** *(done 2026-09-06, commit 3143deb)*: search-first with quantities, category/interface filters, optional location grouping, key-image thumbs, unverified badges, CSV export.
- [x] **M7 — Open-source prep** *(done 2026-09-12: repo public at github.com/protocake/partspile)*
  - [x] LICENSE — MIT, Ben's Asana ruling 2026-09-09.
  - [x] README: install story, vision backends, project background, license.
  - [x] `.env.example` complete; local-model benchmarks logged (iters 8–13 in `evals/log.md`).
  - [x] Repo scrub at HEAD: history secret-grep clean; design-canvas tracking bug fixed.
  - [x] Fixtures + eval log to private `partspile-fixtures` repo via fresh-copy split (DECISIONS #43); ElectronicsIdentifier kept as private archive.
- [ ] **M8 — Productization** *(Approach A approved by Ben 2026-09-11: minimal-diff, cloud-first onboarding)*
  - [x] Phase 0 — `~/.partspile` data dir (`paths.py`); config/db/photos/cutouts off repo-relative paths; legacy `./data` shim.
  - [x] Phase 1 — PyPI packaging: `pyproject` deps fixed (+`python-multipart`), `[project.scripts]`, prompts+swift as package data, wheel verified.
  - [x] Phase 2 — CLI (`partspile serve`, browser auto-open, cloud-first nudge) + `/setup` onboarding page (key → `~/.partspile/config` 0600); 100 tests green; live smoke passed.
  - [x] Phase 3 — fixtures split done 2026-09-12: `partspile` (public, single fresh commit) + `partspile-fixtures` (private) live on GitHub; eval sibling auto-detection verified.
  - [ ] Phase 4 — distribution:
    - [x] v0.2.0 tagged + GitHub release with wheel/sdist; wheel verified in a clean venv.
    - [x] Homebrew tap live (github.com/protocake/homebrew-partspile; release-tarball formula, pip-wheel deps, precompiled `partspile-cutout`).
    - [x] `brew install` verified end-to-end 2026-09-13 (48s build, partspile + precompiled partspile-cutout on PATH, fresh-install /setup flow boots from the Cellar).
    - [ ] PyPI publish (`partspile` name verified free) — blocked on Ben's PyPI token (task on board).
- [ ] **Holdout check (Ben, manual)** — Ben runs against `fixtures/holdout/` himself. Never automated.
