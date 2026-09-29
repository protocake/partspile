"""Native Ollama provider — needed because Ollama's OpenAI-compat endpoint cannot
set num_ctx or disable thinking mode (research/local-models-round2.md): the default
4096 context silently truncates the HEAD of the prompt (the rules), and thinking-on
degrades instruction-following. Native /api/chat exposes both, plus grammar-enforced
JSON via `format`.
"""

from __future__ import annotations

import base64
import json
import subprocess
import urllib.request
from pathlib import Path

import re

from ..config import Config
from ..schema import (AppBinIdentification, AppLocalBinIdentification,
                      AppPart, BinIdentification, LocalBinIdentification, Part)
from .openai_compat import _prepped_bytes


class OllamaNativeProvider:
    name = "ollama"

    def __init__(self, cfg: Config, poster=None):
        self.cfg = cfg
        self.base = (cfg.base_url or "http://localhost:11434").rstrip("/")
        if self.base.endswith("/v1"):
            self.base = self.base[:-3]
        self._post = poster or self._http_post

    def _http_post(self, url: str, body: dict) -> dict:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.load(resp)

    def identify(self, photos: list[Path], base_prompt: str) -> BinIdentification:
        local = self._call(photos, base_prompt, LocalBinIdentification)
        return _enforce(local, Part, BinIdentification)

    def identify_app(self, photos: list[Path], base_prompt: str) -> AppBinIdentification:
        """App variant: parts carry source_shot (which photo the item is in)."""
        names = ", ".join(p.name for p in photos)
        prompt = (base_prompt
                  + f"\n\nThe photos, in order, are named: {names}. For every part, "
                    "set source_shot to the filename of the photo where that item "
                    "is most clearly visible.")
        local = self._call(photos, prompt, AppLocalBinIdentification)
        return _enforce(local, AppPart, AppBinIdentification)

    def _call(self, photos: list[Path], prompt: str, schema_cls):
        images = []
        for p in photos:
            raw, _ = _prepped_bytes(p)
            images.append(base64.standard_b64encode(raw).decode("utf-8"))
        body = {
            "model": self.cfg.model,
            "messages": [{"role": "user", "content": prompt, "images": images}],
            "stream": False,
            "think": False,
            "format": schema_cls.model_json_schema(),
            "options": {"temperature": 0.3},
        }
        payload = self._post(self.base + "/api/chat", body)
        text = payload["message"]["content"].strip()
        fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
        if fence:
            text = fence.group(1)
        return schema_cls.model_validate(json.loads(text))


def _enforce(local, part_cls=Part, container_cls=BinIdentification):
    """Deterministic consequences of the schema-forced decisions (DECISIONS #38):
    self-declared attached components are dropped; anything not clearly legible is
    forced to needs_reshoot with confidence capped at medium."""
    parts = []
    for lp in local.parts:
        if lp.unit_type == "component_attached_to_a_listed_object":
            continue
        d = lp.model_dump(exclude={"unit_type", "legibility"})
        if lp.legibility != "markings_read_clearly":
            d["needs_reshoot"] = True
            if not d.get("reshoot_reason"):
                d["reshoot_reason"] = f"markings {lp.legibility.replace('_', ' ')}"
            if d.get("confidence") == "high":
                d["confidence"] = "medium"
        parts.append(part_cls.model_validate(d))
    return container_cls(parts=parts)
