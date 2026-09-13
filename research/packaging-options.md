# Packaging & distribution options for Parts Pile (researched 2026-09-11)

Scope: free, open-source, macOS-first FastAPI+SQLite app with browser UI + LAN phone page,
driving a local vision LLM (Ollama / LM Studio, Qwen-class 16–22GB), `sips` + compiled Swift
subject-lift helper. Target user: hobbyist makers — will install apps, won't touch venvs/uvicorn.

## Comparison table

| Route | Effort | Install UX for makers | Update story | Model-handling fit | Cross-platform path |
|---|---|---|---|---|---|
| **1. Homebrew tap** (`brew install ben.../tap/partspile`) | Low. Own tap = a GitHub repo + Ruby formula; `virtualenv_install_with_resources` (or a formula that shells to `uv`) is the standard Python pattern. Swift helper compiles in the formula or ships as a bottle. | Good *if* they have brew (many Mac makers do; many don't). One command, then `partspile` opens the browser. **No Gatekeeper pain** — brew-built/bottled binaries carry no quarantine attribute. | Excellent: `brew upgrade`. | Neutral — pairs naturally with "install Ollama, we detect it". | Linux via brew/apt docs; Windows needs a separate route (winget/scoop or an installer). |
| **2. uv one-liner** (`uv tool install partspile` / `uvx partspile`) | Trivial once on PyPI. uv is mainstream for *developers* in 2026 (~89k stars, replaced pipx/poetry for most teams) — but makers must first install uv itself. | Borderline. Two terminal steps, no .app icon, nothing in /Applications. Fine as the "power user" lane, not the front door. | Good: `uv tool upgrade`. | Neutral. | Same command on Win/Linux — best cross-platform *terminal* story. |
| **3. Real Mac .app** (PyInstaller or Briefcase bundle: server + menubar icon + auto-open browser) | High. PyInstaller+hardened-runtime needs entitlements (`allow-unsigned-executable-memory`) and per-binary signing; Briefcase now automates sign+notarize by default and is the smoother 2026 choice. | Best-in-class: drag to /Applications, click icon. **But only if signed+notarized** — macOS 15+ removed the right-click-Open bypass; unsigned downloads route users through System Settings multi-click, which kills maker onboarding. Notarization requires the $99/yr Apple Developer Program (no open-source waiver; waivers only for nonprofits/edu/gov). | Roll your own (Sparkle, or "download new DMG"). | Neutral; menubar app can run the Ollama health-check + model-pull UI nicely. | Briefcase targets Windows/Linux too; PyInstaller per-OS builds. |
| **4. Tauri (or Electron) shell + Python sidecar** | Medium-high. Proven 2026 pattern: Tauri v2 spawns a PyInstaller-built FastAPI binary as a sidecar over localhost HTTP; multiple maintained templates exist. No rewrite — existing HTMX UI loads in the webview. ComfyUI Desktop validates the sibling approach (Electron + bundled `uv` that installs/updates the Python env on first run). | Same as route 3 (real installer, dock icon) — same signing/notarization requirement and cost. Tauri bundles are ~10× smaller than Electron. | Built-in updater (Tauri updater / electron-updater) — best update UX of all routes. | Good: native shell can own first-run flow (detect runtime, download model with progress). | **Strongest**: one codebase → .dmg/.msi/.deb. |
| **5. Docker / OrbStack image** | Low for the app itself. | Poor fit. Requires Docker Desktop/OrbStack install + concepts; and **Apple Silicon GPU cannot be passed into Linux containers** (no Metal path through the VM, still true on M5 in 2026), so the model must run natively on the host anyway. Docker Model Runner / vLLM-Metal run *outside* the VM and don't change this for Ollama-in-container. | `docker pull`. | Bad: forces the split "app in container, model on host" — all of Docker's isolation cost, none of the benefit. | Good on Linux servers; keep as a homelab option only. |

## Model side — what comparable local-AI apps do in 2026

Three tiers, all with working precedents:

1. **Detect-and-guide (cheapest, v1):** hit `http://localhost:11434` (Ollama) and
   `localhost:1234` (LM Studio); both expose OpenAI-compatible APIs. If absent, show a
   one-screen "Install Ollama → we'll take it from here" guide. Once Ollama is present,
   the app can drive `POST /api/pull` itself and stream download progress into its own UI —
   first-run model download *without* bundling a runtime. Ollama/LM Studio already solve the
   16–22GB download, resume, quantization, and Metal GPU problems; don't re-solve them.
2. **Managed engines (mid):** Msty bundles a renamed Ollama plus managed llama.cpp/MLX
   services; AnythingLLM ships a built-in engine with a model-picker on first boot.
3. **Fully bundled (heaviest):** Jan embeds llama.cpp, serves its own OpenAI-compatible API
   (port 1337), downloads GGUFs from Hugging Face with in-app progress — the best open-source
   example of first-run model download done well. ComfyUI Desktop is the best example on the
   Python side (bundled `uv` + model manager).

For 16–22GB Qwen-class VLMs, tier 1 is the right v1: the runtime install is one .app the
target user already understands, and the glossary/eval stack already speaks OpenAI-compat HTTP.

## Precedent apps worth imitating

- **ComfyUI Desktop** (Comfy-Org/Comfy-Desktop): Electron shell + bundled `uv` that creates the
  Python env on first launch and self-updates — the closest architectural match (Python server
  + local web UI + big model files) that ships to non-technical users.
- **Jan** (jan.ai): open-source, Tauri-family desktop app, bundled llama.cpp, exemplary
  first-run model-download UX.
- **Open WebUI**: the cautionary tale — pip/Docker-only install keeps it a tinkerer tool.
- **Msty / AnythingLLM**: managed-engine UX patterns (model picker on first boot).
- **LM Studio / Ollama** themselves: the "install one .app, it owns the models" bar makers expect.

## Code-signing / notarization reality (2026)

- Notarization = Developer ID signing + hardened runtime + Apple's automated scan; required
  for anything distributed outside the App Store as a download. Free once you're in the
  $99/yr Apple Developer Program; no open-source exemption.
- **Unsigned .app downloads are no longer practical**: since macOS 15 Sequoia the
  Control-click "Open anyway" shortcut is gone; users must dig through System Settings →
  Privacy & Security per launch attempt. Do not ship an unsigned DMG to makers.
- **The brew escape hatch is real**: binaries installed by Homebrew (built from source or
  bottled) don't get the quarantine xattr, so a formula sidesteps Gatekeeper entirely —
  this is why the tap route needs no Apple account. (Casks of prebuilt .apps still quarantine
  unless the user passes `--no-quarantine`; ship a formula, not a cask, until the app is signed.)
- Briefcase automates sign+notarize (incl. CI resume support); PyInstaller works but expect
  entitlements fiddling (`com.apple.security.cs.allow-unsigned-executable-memory`, no
  `--deep` shortcuts, sign every nested binary — including our Swift helper).

## Recommendation

**v1 (now, $0, ~days of work): Homebrew tap + PyPI, with `uvx partspile` as the alternate lane.**
- Publish to PyPI; `partspile` entry point starts uvicorn, prints/opens `http://localhost:8000`,
  shows the LAN QR for the phone page.
- Own tap (`homebrew-partspile`): formula via `virtualenv_install_with_resources`
  (generate resources with `brew-python-resources`), Swift helper built by the formula
  (or bottled). README install block: two copy-paste lines.
- First-run screen does Ollama/LM Studio detection + guided model pull via `/api/pull`
  with progress bar (tier-1 model handling). No Apple account, no Gatekeeper friction.

**Growth path (when there are real users): Tauri v2 + Python sidecar .app, signed + notarized.**
- Keeps the FastAPI/HTMX code untouched (sidecar over localhost); menubar icon,
  auto-open browser, built-in updater; same codebase later emits Windows/Linux installers —
  which also answers the "Windows later" requirement better than brew can.
- Budget the $99/yr at that point; use Briefcase instead only if adding a Rust toolchain is
  unacceptable. Skip Electron (size) and Docker (no Apple-GPU passthrough; wrong audience) —
  a Dockerfile can exist for homelab/Linux users but must point at a host-native model runtime.

## Sources

- Homebrew Python formula docs: https://github.com/Homebrew/brew/blob/master/docs/Python-for-Formula-Authors.md
- Simon Willison, packaging a Python CLI for Homebrew: https://til.simonwillison.net/homebrew/packaging-python-cli-for-homebrew
- brew-python-resources: https://pypi.org/p/brew-python-resources
- uv tools / distribution: https://docs.astral.sh/uv/guides/integration/fastapi/ · https://thisdavej.com/packaging-python-command-line-apps-the-modern-way-with-uv/ (uv adoption: ~89k stars, replaces pipx/poetry)
- Tauri v2 sidecar docs: https://v2.tauri.app/develop/sidecar/
- Tauri + FastAPI sidecar templates: https://github.com/dieharders/example-tauri-v2-python-server-sidecar · https://github.com/AlanSynn/vue-tauri-fastapi-sidecar-template
- Tauri/FastAPI/PyInstaller LLM-app writeup: https://aiechoes.substack.com/p/building-production-ready-desktop
- Briefcase macOS (sign+notarize by default, CI resume): https://briefcase.beeware.org/en/stable/reference/platforms/macOS/ · https://beeware.org/news/buzz/2026/june-2026-status-update/
- PyInstaller hardened-runtime issues: https://github.com/pyinstaller/pyinstaller/issues/4629 · https://haim.dev/posts/2020-08-08-python-macos-app
- Sequoia Gatekeeper change (right-click-open removed): https://www.gamineai.com/blog/macos-notarization-stapling-ninety-minute-pass-unity-godot-steam-builds-2026 · https://support.apple.com/en-us/102445
- Apple $99 program, no OSS waiver: https://developer.apple.com/forums/thread/121113 · https://ambsandigital.com/apple-developer-program-fee-2026/
- Apple Silicon GPU vs containers: https://chariotsolutions.com/blog/post/apple-silicon-gpus-docker-and-ollama-pick-two/ · https://insiderllm.com/guides/docker-local-ai-ollama-open-webui-gpu-passthrough/ · https://github.com/apple/container/discussions/62
- ComfyUI Desktop architecture (Electron + bundled uv): https://github.com/Comfy-Org/Comfy-Desktop
- Local-AI app model-handling survey: https://modelpiper.com/blog/local-ai-platforms-compared-mac · https://docs.anythingllm.com/setup/llm-configuration/local/built-in · https://machinelearningmastery.com/ollama-vs-lm-studio-vs-llama-cpp-which-local-ai-runtime-should-you-use-in-2026/
- Ollama API / detection (localhost:11434, OpenAI-compat, /api/pull): https://stacknotice.com/blog/ollama-complete-guide-2026 · https://hybrid-llm.com/tutorial/ollama/ollama-setup-guide-2026/
