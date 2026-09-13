# Parts Pile

Photograph a pile of hobbyist electronics → a vision model identifies every part →
you review and correct on your phone → a searchable inventory that stops you buying
parts you already own.

## Install

```bash
uvx partspile            # zero-install run (uv)
# or
pipx install partspile && partspile
# (Homebrew tap coming: brew install <tap>/partspile)
```

`partspile` starts the server, opens your browser, and walks you through setup on
first run: paste an Anthropic API key (from
[console.anthropic.com](https://console.anthropic.com/settings/keys)) and you're
scanning. The key and all app data (SQLite DB, photos, cut-outs) live in
`~/.partspile/`. Prefer a local model? Skip the key and see **Vision backend**.

Open `http://<lan-ip>:8000` on your phone (same Wi-Fi; add to home screen for the
app feel — the desktop browse page shows a QR code that jumps your phone straight
to capture). Three pages: **capture** (shoot multi-angle, submit — scans queue in
the background so you keep shooting), **review** (accept/edit each identified
part, request another angle, or mark it "can't determine"), **browse** (search "do
I already have this", filters, CSV export).

### From a checkout

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/partspile serve --host 0.0.0.0 --port 8000
# or the classic: .venv/bin/uvicorn partspile.web.app:app --host 0.0.0.0 --port 8000
```

## Vision backend

Set `PARTS_PILE_PROVIDER` (see `.env.example`):

- `claude_code` (default) — shells out to headless Claude Code; uses your Claude
  subscription login, no API key. Personal-use path.
- `anthropic` — Anthropic API with `ANTHROPIC_API_KEY`.
- `ollama` — native Ollama (recommended local path): create the 16k-context model
  once (`ollama create partspile-qwen -f` a Modelfile with `FROM qwen3.6:35b` +
  `PARAMETER num_ctx 16384`), then `PARTS_PILE_PROVIDER=ollama`,
  `PARTS_PILE_MODEL=partspile-qwen`, `PARTS_PILE_PROMPT=v1-local`.
- `openai_compat` — any other OpenAI-compatible server (`PARTS_PILE_BASE_URL`),
  e.g. vLLM/LM Studio.

## Development

- Tests: `python3 -m unittest discover -s tests` (no fixtures needed).
- Eval: `python eval.py --run` scores the pipeline against a fixture set of
  photos + `truth.json`. The reference fixtures live in a private repo
  (`partspile-fixtures` — real photos of the maintainer's parts); point
  `PARTS_PILE_FIXTURES_DIR` at a clone, or bring your own set shaped per
  `fixtures/README.md`. Scorer smoke test with zero fixtures:
  `python eval.py --from-json evals/samples/demo_pass.json --truth evals/samples/demo_truth.json --no-log`.
  Every scored run logs to `evals/log.md`. Never eval against a holdout split.
- Architecture and decisions: `PLAN.md`, `DECISIONS.md`, `ROADMAP.md`.

## Project background

This app was built as an experiment in autonomous AI-driven development: Claude
Code ran the build loop (plan → implement → test → eval → ship) with the owner
steering through reviews and decisions. `DECISIONS.md` and `evals/log.md` are the
honest record of that process, including the dead ends.

## License

MIT — see `LICENSE`.
