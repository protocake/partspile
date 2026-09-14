"""FastAPI app: phone-first capture with a non-blocking scan queue (DECISIONS #20/#25).

Run: uvicorn partspile.web.app:app --host 0.0.0.0 --port 8000
Worker: an in-process asyncio task drains ident_runs; disable with PARTS_PILE_WORKER=0
(tests do this). Minimal vanilla JS, no build step, no CDNs.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from ..config import Config
from ..db import Db
from ..paths import data_dir, save_local_config
from ..providers import get_provider
from .browse_page import BROWSE_PAGE
from .pages import CAPTURE_PAGE, MANIFEST
from .review_page import REVIEW_PAGE
from .setup_page import SETUP_PAGE

cfg = Config()


def _default_photo_dir() -> Path:
    env = os.environ.get("PARTS_PILE_PHOTO_DIR")
    if env:
        return Path(env)
    legacy = Path("data/photos")  # pre-0.2 dev layout, CWD-relative
    if legacy.is_dir():
        return legacy
    return data_dir() / "photos"


PHOTO_DIR = _default_photo_dir()

app = FastAPI(title="Parts Pile")


@app.middleware("http")
async def no_store_html(request, call_next):
    resp = await call_next(request)
    if resp.headers.get("content-type", "").startswith("text/html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp
db: Db | None = None
_worker_task: asyncio.Task | None = None


def get_db() -> Db:
    global db
    if db is None:
        db = Db(cfg.db_path)
    return db


async def worker_loop():
    """Drain the scan queue one run at a time (Max-quota politeness)."""
    d = get_db()
    d.adopt_stale_running()
    # Provider is resolved lazily per run and rebuilt when /api/setup swaps cfg:
    # building it up front would kill the worker on a fresh install with no key.
    provider = None
    provider_cfg = None
    base_prompt = ""
    while True:
        if not backend_ready(cfg):
            # Deferred onboarding: scans queue up and WAIT — the capture UI
            # prompts the user to connect a backend; nothing fails.
            await asyncio.sleep(2)
            continue
        run = d.claim_next_run()
        if run is None:
            await asyncio.sleep(2)
            continue
        photos = [Path(p["path"]) for p in d.photos_for_scan(run["scan_id"], captured_only=True)]
        try:
            if provider is None or provider_cfg is not cfg:
                provider = get_provider(cfg)
                provider_cfg = cfg
                base_prompt = cfg.prompt_path().read_text()
            from ..glossary import build_glossary_text
            prompt = base_prompt + build_glossary_text(d.glossary())
            call = getattr(provider, "identify_app", provider.identify)
            ident = await asyncio.to_thread(call, photos, prompt)
            parts = [p.model_dump() for p in ident.parts]
            feedback = [f.model_dump() for f in getattr(ident, "photo_feedback", [])]
            d.finish_run(run["id"], json.dumps(parts), parts, json.dumps(feedback))
        except Exception as e:
            d.fail_run(run["id"], str(e)[:1000])


@app.on_event("startup")
async def startup():
    global _worker_task
    if os.environ.get("PARTS_PILE_SAMPLES", "1") != "0":
        from ..sample_data import seed_samples
        seed_samples(get_db(), PHOTO_DIR)
    else:
        get_db()
    if os.environ.get("PARTS_PILE_WORKER", "1") != "0":
        _worker_task = asyncio.create_task(worker_loop())


@app.on_event("shutdown")
async def shutdown():
    if _worker_task:
        _worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _worker_task


def backend_ready(c: Config) -> bool:
    """Can the worker actually identify scans with the current config?
    When False, queued scans wait (not fail) until the user connects a backend."""
    import shutil as _sh
    if c.provider == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if c.provider == "claude_code":
        return bool(_sh.which(c.claude_bin))
    if c.provider in ("ollama", "openai_compat"):
        return True  # local endpoints: per-run errors surface in the queue as before
    return False


def _probe(url: str, timeout: float = 1.5) -> dict:
    """Best-effort local model-server detection; never raises."""
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = json.load(r)
        if "models" in body:  # Ollama /api/tags
            models = [m.get("name", "") for m in body.get("models", [])]
        else:                 # OpenAI-compatible /v1/models
            models = [m.get("id", "") for m in body.get("data", [])]
        return {"found": True, "models": [m for m in models if m][:8]}
    except Exception:
        return {"found": False, "models": []}


@app.get("/", response_class=HTMLResponse)
async def root_page():
    """Desktop-first: the root is Browse (UI pass v2); phones get /capture via the QR.
    No setup gate — the welcome overlay orients, connect happens at first scan."""
    return HTMLResponse(BROWSE_PAGE)


@app.get("/capture", response_class=HTMLResponse)
async def capture_page():
    return HTMLResponse(CAPTURE_PAGE)


@app.get("/setup", response_class=HTMLResponse)
async def setup_page():
    return SETUP_PAGE


@app.get("/api/setup/status")
async def setup_status():
    import shutil as _sh
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "ready": backend_ready(cfg),
        "detect": {
            "claude_cli": bool(_sh.which(cfg.claude_bin)),
            "ollama": _probe("http://localhost:11434/api/tags"),
            "lm_studio": _probe("http://localhost:1234/v1/models"),
        },
    }


def _apply_config(values: dict[str, str]) -> None:
    global cfg
    save_local_config(values)
    os.environ.update(values)
    cfg = Config()


@app.post("/api/setup")
async def save_setup(api_key: str = Form(...)):
    key = api_key.strip()
    if not key:
        raise HTTPException(400, "empty API key")
    _apply_config({"PARTS_PILE_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": key})
    return RedirectResponse("/", status_code=303)


@app.post("/api/setup/claude-code")
async def setup_claude_code():
    import shutil as _sh
    if not _sh.which(cfg.claude_bin):
        raise HTTPException(400, "Claude Code CLI not found — install it and log in "
                                 "first (https://claude.com/claude-code)")
    _apply_config({"PARTS_PILE_PROVIDER": "claude_code"})
    return {"ok": True}


@app.post("/api/setup/local")
async def setup_local(payload: dict):
    provider = payload.get("provider", "")
    model = (payload.get("model") or "").strip()
    base_url = (payload.get("base_url") or "").strip()
    if provider not in ("ollama", "openai_compat") or not model:
        raise HTTPException(400, "provider (ollama|openai_compat) and model required")
    values = {"PARTS_PILE_PROVIDER": provider, "PARTS_PILE_MODEL": model,
              "PARTS_PILE_PROMPT": "v1-local"}
    if provider == "openai_compat":
        if not base_url:
            raise HTTPException(400, "base_url required for openai_compat")
        values["PARTS_PILE_BASE_URL"] = base_url
    _apply_config(values)
    return {"ok": True}


@app.post("/api/samples/clear")
async def samples_clear():
    from ..sample_data import clear_samples
    return {"removed": clear_samples(get_db(), PHOTO_DIR)}


def _lan_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


@app.get("/api/lan-url")
async def lan_url():
    port = os.environ.get("PARTS_PILE_PORT", "8000")
    return {"url": f"http://{_lan_ip()}:{port}"}


@app.get("/api/qr.svg")
async def qr_svg():
    """QR to the phone capture page. Needs the pure-Python 'qrcode' lib (pending Ben's
    dependency approval); until then 404s and the UI shows the URL as text."""
    try:
        import io

        import qrcode
        import qrcode.image.svg
    except ImportError:
        raise HTTPException(404, "qrcode library not installed")
    port = os.environ.get("PARTS_PILE_PORT", "8000")
    img = qrcode.make(f"http://{_lan_ip()}:{port}/capture",
                      image_factory=qrcode.image.svg.SvgPathFillImage)
    buf = io.BytesIO()
    img.save(buf)
    from fastapi.responses import Response
    return Response(buf.getvalue(), media_type="image/svg+xml")


@app.get("/api/refined-boxes")
async def refined_boxes(ids: str):
    """Batch: tight object boxes for part thumbnails (auto cut-out post-processing).
    Value is null when segmentation finds nothing — client falls back to model bbox."""
    from ..thumbs import refined_box_for

    d = get_db()
    jobs = []
    for sid in ids.split(",")[:64]:
        try:
            pid = int(sid)
        except ValueError:
            continue
        part = d.conn.execute("SELECT * FROM parts WHERE id = ?", (pid,)).fetchone()
        if not part:
            continue
        photos = d.photos_for_scan(part["scan_id"], captured_only=True)
        if not photos:
            continue
        try:
            seed = (json.loads(part["bbox_json"]) or [None])[0]
        except (json.JSONDecodeError, TypeError):
            seed = None
        jobs.append((pid, Path(photos[0]["path"]), seed))

    def work():
        return {pid: refined_box_for(path, seed) for pid, path, seed in jobs}

    return await asyncio.to_thread(work)


@app.post("/api/parts/{part_id}/guess")
async def guess_details(part_id: int):
    """AI best-guess for serial + product URL. Returns suggestions only — the human
    confirms each in the modal before anything is saved."""
    from .. import enrich

    d = get_db()
    part = d.conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()
    if not part:
        raise HTTPException(404)
    photos = [Path(p["path"]) for p in d.photos_for_scan(part["scan_id"])]
    if not photos:
        raise HTTPException(404, "no photos for this part")
    try:
        return await asyncio.to_thread(enrich.guess_part_details, dict(part), photos, cfg)
    except Exception as e:
        raise HTTPException(502, f"guess failed: {e}")


@app.post("/api/parts/{part_id}/photos")
async def add_part_photo(part_id: int, photos: list[UploadFile]):
    """Attach additional photos to an existing part (no re-scan)."""
    d = get_db()
    part = d.conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()
    if not part:
        raise HTTPException(404)
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    added = []
    for i, up in enumerate(photos, 1):
        ext = Path(up.filename or "shot.jpg").suffix.lower() or ".jpg"
        dest = PHOTO_DIR / f"part{part_id}_extra{int(asyncio.get_event_loop().time()*1000)}_{i}{ext}"
        dest.write_bytes(await up.read())
        added.append(d.add_part_photo(part_id, str(dest), "captured"))
    return {"added": added}


@app.post("/api/parts/{part_id}/suggest-image")
async def suggest_image(part_id: int):
    """Fetch the part's product page and propose its main image (human confirms)."""
    from ..webimage import suggest_image_for_url

    d = get_db()
    part = d.conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()
    if not part:
        raise HTTPException(404)
    if not part["spec_url"]:
        raise HTTPException(400, "no product page URL on this part yet")
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    pending = PHOTO_DIR / f"pending_part{part_id}.img"
    result = await asyncio.to_thread(suggest_image_for_url, part["spec_url"], pending)
    if not result:
        raise HTTPException(404, "no usable image found on that page")
    return {"source": result, "preview": f"/photos/{pending.name}"}


@app.post("/api/parts/{part_id}/adopt-suggestion")
async def adopt_suggestion(part_id: int):
    """Human confirmed the suggested catalog image: register it on the part."""
    d = get_db()
    part = d.conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()
    if not part:
        raise HTTPException(404)
    pending = PHOTO_DIR / f"pending_part{part_id}.img"
    if not pending.exists():
        raise HTTPException(404, "no pending suggestion")
    dest = PHOTO_DIR / f"part{part_id}_catalog{int(pending.stat().st_mtime)}.img"
    pending.rename(dest)
    photo_id = d.add_part_photo(part_id, str(dest), "catalog")
    return {"photo_id": photo_id, "file": dest.name}


@app.delete("/api/photos/{photo_id}")
async def delete_photo(photo_id: int):
    d = get_db()
    path = d.delete_photo(photo_id)
    if path is None:
        raise HTTPException(404)
    p = Path(path).resolve()
    try:
        if PHOTO_DIR.resolve() in p.parents and p.is_file():
            p.unlink()
    except OSError:
        pass
    return {"ok": True}


@app.get("/api/cutouts/{part_id}.png")
async def cutout_png(part_id: int):
    """Transparent part cut-out (Apple subject lifting). 404 = fall back to crop."""
    from ..thumbs import cutout_for

    d = get_db()
    part = d.conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()
    if not part:
        raise HTTPException(404)
    photos = d.photos_for_scan(part["scan_id"], captured_only=True)
    if not photos:
        raise HTTPException(404)
    try:
        seed = (json.loads(part["bbox_json"]) or [None])[0]
    except (json.JSONDecodeError, TypeError):
        seed = None
    p = await asyncio.to_thread(cutout_for, part_id, Path(photos[0]["path"]), seed)
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png")


@app.get("/api/parts/{part_id}/context")
async def part_context(part_id: int):
    """Everything the detail modal needs: the part, its bin, and all bin photos."""
    d = get_db()
    part = d.conn.execute("SELECT * FROM parts WHERE id = ?", (part_id,)).fetchone()
    if not part:
        raise HTTPException(404)
    b = d.conn.execute("SELECT * FROM scans WHERE id = ?", (part["scan_id"],)).fetchone()
    run = d.conn.execute("SELECT * FROM ident_runs WHERE id = ?",
                         (part["source_run_id"],)).fetchone()
    prov = (f"{run['model']} · prompt {run['prompt_version']} · {run['created_at'][:10]}"
            if run else "manual entry")
    return {"part": dict(part),
            "scan": {"id": b["id"], "location": b["location"]},
            "photos": [{"id": p["id"], "file": Path(p["path"]).name, "kind": p["kind"],
                        "shared": p["part_id"] is None}
                       for p in d.photos_for_part(part_id)],
            "provenance": prov}


@app.get("/manifest.json")
async def manifest():
    return JSONResponse(MANIFEST, media_type="application/manifest+json")


@app.post("/api/scans")
async def create_scan(photos: list[UploadFile], label: str = Form(""),
                      location: str = Form("")):
    """Submit a scan: save shots, enqueue identification, return immediately."""
    if not photos:
        raise HTTPException(400, "at least one photo required")
    d = get_db()
    scan_id = d.create_scan(label or f"scan {d.conn.execute('SELECT COUNT(*)+1 c FROM scans').fetchone()['c']}", location)
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    for i, up in enumerate(photos, 1):
        ext = Path(up.filename or "shot.jpg").suffix.lower() or ".jpg"
        dest = PHOTO_DIR / f"scan{scan_id}_shot{i}{ext}"
        dest.write_bytes(await up.read())
        d.add_photo(scan_id, str(dest), i)
    run_id = d.enqueue_run(scan_id, cfg.provider, cfg.model, cfg.prompt_version)
    return {"scan_id": scan_id, "run_id": run_id, "status": "queued"}


@app.get("/api/queue")
async def queue():
    d = get_db()
    out = []
    for r in d.queue_overview():
        counts = d.conn.execute(
            "SELECT COUNT(*) c, SUM(status = 'pending') p FROM parts "
            "WHERE source_run_id = ?", (r["id"],)).fetchone()
        try:
            fb = json.loads(r["photo_feedback_json"] or "[]")
        except json.JSONDecodeError:
            fb = []
        retakes = [f for f in fb if f.get("verdict") == "retake"]
        out.append({"run_id": r["id"], "scan_id": r["scan_id"],
                    "location": r["scan_location"],
                    "status": r["status"], "error": r["error"],
                    "parts": counts["c"], "pending": counts["p"] or 0,
                    "retake": bool(retakes),
                    "retake_reason": (retakes[0].get("reason", "") if retakes else "")})
    return out


@app.post("/api/runs/{run_id}/retry")
async def retry(run_id: int):
    get_db().retry_run(run_id)
    return {"run_id": run_id, "status": "queued"}


@app.get("/review", response_class=HTMLResponse)
async def review_page():
    return REVIEW_PAGE


@app.get("/api/review")
async def review_data():
    d = get_db()
    out = []
    for row in d.pending_parts():
        scan_id = row["scan_id"]
        entry = next((b for b in out if b["scan_id"] == scan_id), None)
        if entry is None:
            b = d.conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
            entry = {"scan_id": scan_id, "location": b["location"],
                     "photos": [{"file": Path(p["path"]).name}
                                for p in d.photos_for_scan(scan_id)],
                     "parts": []}
            out.append(entry)
        part = dict(row)
        part["have"] = d.have_count(row["canonical"])
        entry["parts"].append(part)
    return out


@app.post("/api/parts/{part_id}/accept")
async def accept_part(part_id: int):
    get_db().accept_part(part_id)
    return {"ok": True}


@app.post("/api/parts/{part_id}/undetermined")
async def undetermined(part_id: int):
    d = get_db()
    d.mark_undetermined(part_id)
    return {"ok": True}


@app.patch("/api/parts/{part_id}")
async def edit_part(part_id: int, fields: dict):
    get_db().update_part(part_id, **fields)
    return {"ok": True}


@app.delete("/api/parts/{part_id}")
async def delete_part(part_id: int):
    get_db().delete_part(part_id)
    return {"ok": True}


@app.patch("/api/scans/{scan_id}")
async def edit_scan(scan_id: int, fields: dict):
    """Edit a scan's location (applies to every part captured together)."""
    d = get_db()
    if not d.conn.execute("SELECT 1 FROM scans WHERE id = ?", (scan_id,)).fetchone():
        raise HTTPException(404)
    d.update_scan(scan_id, location=fields.get("location"), label=fields.get("label"))
    return {"ok": True}


@app.post("/api/scans/{scan_id}/photos")
async def add_photos(scan_id: int, photos: list[UploadFile]):
    """Reshoot flow: append shots to an existing scan and queue a fresh run."""
    d = get_db()
    existing = d.photos_for_scan(scan_id)
    if not d.conn.execute("SELECT 1 FROM scans WHERE id = ?", (scan_id,)).fetchone():
        raise HTTPException(404, "no such scan")
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    n = len(existing)
    for i, up in enumerate(photos, n + 1):
        ext = Path(up.filename or "shot.jpg").suffix.lower() or ".jpg"
        dest = PHOTO_DIR / f"scan{scan_id}_shot{i}{ext}"
        dest.write_bytes(await up.read())
        d.add_photo(scan_id, str(dest), i)
    run_id = d.enqueue_run(scan_id, cfg.provider, cfg.model, cfg.prompt_version)
    return {"scan_id": scan_id, "run_id": run_id, "status": "queued"}


@app.get("/browse", response_class=HTMLResponse)
async def browse_page():
    return BROWSE_PAGE  # legacy path; root serves the same page


def _thumb(d: Db, row) -> str:
    if row["key_photo_id"]:
        p = d.conn.execute("SELECT path FROM photos WHERE id = ?",
                           (row["key_photo_id"],)).fetchone()
        if p:
            return Path(p["path"]).name
    first = d.photos_for_scan(row["scan_id"])
    return Path(first[0]["path"]).name if first else ""


@app.get("/api/parts")
async def list_parts(q: str = "", category: str = "", interface: str = "",
                     location: str = ""):
    d = get_db()
    rows = d.search_parts(q=q, category=category, interface=interface, location=location)
    return [dict(r) | {"photo": _thumb(d, r)} for r in rows]


@app.get("/api/export.csv")
async def export_csv():
    import csv
    import io

    d = get_db()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["canonical", "name", "category", "interface", "voltage", "qty",
                "bin", "location", "resolution", "spec_url", "serial", "notes"])
    for r in d.search_parts():
        w.writerow([r["canonical"], r["name"], r["category"], r["interface"],
                    r["voltage"], r["qty"], r["bin"], r["location"],
                    r["resolution"], r["spec_url"], r["serial"], r["notes"]])
    from fastapi.responses import Response
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=partspile.csv"})


@app.post("/api/bins")
async def create_scan_legacy(photos: list[UploadFile], label: str = Form(""),
                             location: str = Form("")):
    """Legacy alias: pre-rename cached capture pages posted here."""
    return await create_scan(photos, label, location)


@app.post("/api/bins/{scan_id}/photos")
async def add_photos_legacy(scan_id: int, photos: list[UploadFile]):
    return await add_photos(scan_id, photos)


@app.get("/photos/{name}")
async def photo(name: str):
    p = (PHOTO_DIR / name).resolve()
    if not p.is_file() or PHOTO_DIR.resolve() not in p.parents:
        raise HTTPException(404)
    return FileResponse(p)
