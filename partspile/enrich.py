"""On-demand AI enrichment: best-guess serial number (from the photos) and product
page URL (via real web search) for a part. Human confirms each guess in the UI —
nothing is saved without confirmation (Ben, 2026-09-07).

Uses headless Claude Code like the claude_code provider (subscription auth, and it
brings web search — so spec_url guesses are URLs actually FOUND, never fabricated).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .config import Config

PROMPT = """You are enriching one inventory record for a hobbyist electronics part.

Part: {canonical} — {name} ({category})
Photos of this exact physical item (use your Read tool on each):
{photos}

Two tasks:
1. serial: Look closely at the photos for a serial number, date/lot code, or model
   suffix printed on a label or etched on the part — NOT the part designation
   "{canonical}" itself. Transcribe it EXACTLY, character by character, only if it is
   actually legible in a photo. If nothing legible qualifies, use null.
2. spec_url: Use web search to find the single best product page, datasheet, or
   official documentation URL for "{canonical}". Prefer the manufacturer or an
   authoritative source. The URL MUST come from an actual search result you saw —
   NEVER construct or guess a URL. If you find nothing good, use null.

Reply with ONLY this JSON object, no prose, no fences:
{{"serial": string or null, "serial_note": "where you read it / why null",
  "spec_url": string or null, "spec_url_note": "what the page is / why null"}}"""


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def guess_part_details(part: dict, photos: list[Path],
                       cfg: Config | None = None, runner=None) -> dict:
    """Returns {serial, serial_note, spec_url, spec_url_note} (values may be null)."""
    cfg = cfg or Config()
    runner = runner or _run
    prompt = PROMPT.format(
        canonical=part["canonical"], name=part["name"], category=part["category"],
        photos="\n".join(f"- {p.resolve()}" for p in photos))
    proc = runner([
        cfg.claude_bin, "-p", prompt,
        "--output-format", "json",
        "--model", cfg.model,
        "--allowedTools", "Read,WebSearch,WebFetch",
    ])
    if proc.returncode != 0:
        raise RuntimeError(f"enrichment failed (rc={proc.returncode}): {proc.stderr[:300]}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"enrichment error: {str(envelope)[:300]}")
    text = envelope["result"].strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    data = json.loads(text)
    out = {}
    for key in ("serial", "spec_url"):
        val = data.get(key)
        out[key] = val if isinstance(val, str) and val.strip() else None
        note = data.get(f"{key}_note")
        out[f"{key}_note"] = note if isinstance(note, str) else ""
    if out["spec_url"] and not out["spec_url"].startswith(("http://", "https://")):
        out["spec_url"] = None
    return out
