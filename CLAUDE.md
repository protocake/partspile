# Parts Pile — project instructions

Read `KICKOFF.md` (the brief, authoritative), `PLAN.md` (architecture), `ROADMAP.md` (current state) before working.

## Asana (delegation + visibility)

```claude-tasks config
asana_team:     TODO   # Ben is transferring the board to its team; fill gid after transfer
queue_project:  1218225186084427   # the board itself is the lane (no separate Claude Queue)
signal:         field
claude_field:   1217475430513025   # "Claude" multi-select on the board
field_claude:   1217475430513027   # option "claude"
field_info:     1217475430513026   # option "info"
field_working:  1218225186084431   # option "claude - working" (claim state)
field_blocked:  1218225186084432   # option "blocked"
action_policy:  full
done_sections:  Done, Won't Fix
```

Board: https://app.asana.com/1/50325608721686/project/1218225186084427/list
Master ticket: 1218218967737040 (Admin section). Milestone tickets M1–M7 mirror `ROADMAP.md`.
Key section GIDs: Backlog 1218225186137933 · Current Sprint Backlog 1218225186137936 · In Progress 1218225186137939 · QA/Needs Review 1218225186137942 · Revision Needed 1218225186137945 · Done 1218225186137948.

**Decision Needed convention (Ben, 2026-09-06):** whenever the loop hits a choice only Ben can make, do NOT stall — create a ticket titled `Decision Needed - <topic>` (assigned to Ben, Ticket Type Task, no `claude` flag) with the options, trade-offs, and a recommendation in the description, then continue with other work. When Ben needs to test something, create a `Ben: ...` task with explicit step-by-step instructions.

Rules (per the claude-tasks skill — non-negotiable):
- Every Asana write Claude makes starts with `Claude-` (`Claude-done` / `Claude-draft` / `Claude-updated` / `Claude-note`). Never an unprefixed comment or description.
- Scope every task search to this project GID. Never act on tasks from other boards.
- Only action tasks whose Claude field = `claude` (skip `info`-only, Done/Won't Fix sections, and tasks already carrying a `Claude-done`/`Claude-draft` comment).

## Autonomous loop protocol

`ROADMAP.md` is the single source of truth for engineering state; the Asana board is its human-facing mirror plus Ben's steering channel. Each iteration:

1. **Check the board for steering**: incomplete tasks in *Current Sprint Backlog* or *Revision Needed* with Claude field = `claude` that aren't milestone mirrors — do those first (they're Ben's redirections).
2. Read `ROADMAP.md`. If a Blocker gates the first unchecked milestone, check whether it's resolved (files present, env var set). If still blocked, do any unblocked later-safe work that doesn't violate build order, or report and stop.
3. **Claim before working**: set the Claude field to `claude - working` (keep `claude`), move the ticket to *In Progress*, and comment `Claude-updated: claimed <UTC timestamp>, session <short id>`. Skip any ticket already carrying `claude - working` whose latest claim comment is < 4h old (multi-Claude guard); a stale claim may be taken over — say so in the comment. On finishing or abandoning a ticket, clear `claude - working`. Use `blocked` (plus a `Claude-updated: blocked on <what>` comment) when a ticket can't proceed; clear it when unblocked.
4. Work the **first unchecked milestone only**. Small, verifiable steps.
5. Verify: run `pytest`; for pipeline work, run `python eval.py` and confirm `evals/log.md` got the entry.
6. Update `ROADMAP.md` checkboxes, add non-obvious choices to `DECISIONS.md`.
7. Commit when the milestone (or a coherent sub-step) passes its checks. Meaningful message.
8. **Sync the board**: milestone done → move its ticket to *QA / Needs Review* with a `Claude-done` comment summarizing result + commit hash, **clear the Claude field entirely, and assign the ticket to Ben** (his rule, 2026-09-09: review-ready tickets are his, unlabeled). Ben moves to Done after checking. Blocked → comment `Claude-updated: blocked on <what>` and leave/move it appropriately. Never mark a milestone ticket complete yourself — completion of build milestones is Ben's review call.

To run continuously, Ben starts: `/loop work the next unchecked milestone in ROADMAP.md per CLAUDE.md` (self-paced).

## Hard rules (from KICKOFF.md — do not relax)

- **Never** modify anything under `fixtures/`. **Never** read `fixtures/holdout/` or eval/tune against it.
- Stop and ask Ben only for: output-schema changes, new third-party dependencies beyond Python/FastAPI/SQLite/Anthropic SDK/HTMX, anything touching the holdout.
- Prompt tuning capped at **8 eval iterations** total; then stop and write up in `evals/log.md`.
- Don't overfit to fixture photos — a change that only helps one photo is overfitting.
- API key from env only. Never in the repo.
- Log every eval run to `evals/log.md` with prompt version, provider, model, scores.

## Stack

Python 3.11+, FastAPI, SQLite, Anthropic SDK (structured output), HTMX, no frontend build step. Provider-agnostic vision backend per `PLAN.md` — keep Anthropic-specific code inside `partspile/providers/anthropic_.py`.

## Commands

- Tests: `python3 -m unittest discover -s tests` (pytest also works if installed)
- Eval: `python eval.py` (options documented in its `--help`)
- Serve: `uvicorn partspile.web.app:app --host 0.0.0.0 --port 8000`
