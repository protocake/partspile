"""Identification pipeline: discover bins, call the provider once per bin, save runs."""

from __future__ import annotations

import datetime
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import Config
from .providers import get_provider

BIN_RE = re.compile(r"^(?P<bin>[A-Za-z0-9]+)_shot\d+\.(jpe?g|png|webp)$", re.IGNORECASE)


def discover_bins(photos_dir: Path) -> dict[str, list[Path]]:
    """Group photos by bin prefix: binNN_shotN.jpg -> {binNN: [paths...]}."""
    bins: dict[str, list[Path]] = {}
    for p in sorted(photos_dir.iterdir()):
        m = BIN_RE.match(p.name)
        if m:
            bins.setdefault(m.group("bin"), []).append(p)
    return bins


def run_all(cfg: Config, photos_dir: Path, out_dir: Path | None = None,
            workers: int = 1, log=print, glossary_text: str = "") -> dict:
    """Identify every bin; return (and save) a predictions document eval.py can score.
    glossary_text (house glossary) is appended to the prompt when provided."""
    provider = get_provider(cfg)
    base_prompt = cfg.prompt_path().read_text() + glossary_text
    bins = discover_bins(photos_dir)
    if not bins:
        raise SystemExit(f"No binNN_shotN photos found in {photos_dir}")

    results: dict[str, dict] = {}
    errors: dict[str, str] = {}

    def work(item):
        bin_id, photos = item
        try:
            ident = provider.identify(photos, base_prompt)
            results[bin_id] = {"parts": [p.model_dump() for p in ident.parts]}
            log(f"  {bin_id}: {len(ident.parts)} part(s)")
        except Exception as e:  # a failed bin shouldn't kill the run
            errors[bin_id] = str(e)
            results[bin_id] = {"parts": []}
            log(f"  {bin_id}: ERROR {e}")

    items = sorted(bins.items())
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, items))
    else:
        for item in items:
            work(item)

    doc = {
        "meta": {
            "prompt_version": cfg.prompt_version,
            "provider": cfg.provider,
            "model": cfg.model,
            "errors": errors,
        },
        "bins": results,
    }
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = out_dir / f"run_{stamp}_{cfg.prompt_version}_{cfg.provider}.json"
        out.write_text(json.dumps(doc, indent=2))
        log(f"predictions saved: {out}")
    return doc
