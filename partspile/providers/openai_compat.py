"""OpenAI-compatible endpoint provider: the local open-weight model path.

One adapter covers Ollama, vLLM, LM Studio, and llama.cpp server (all speak the
/chat/completions dialect). stdlib urllib only — no extra dependency.
"""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from ..config import Config
from ..schema import BinIdentification
from .base import parse_model_json

MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
               ".webp": "image/webp"}
MAX_EDGE = 1568  # vision-model sweet spot; big payloads slow local inference badly


def _prepped_bytes(path: Path) -> tuple[bytes, str]:
    """Downscaled JPEG bytes via sips when available; original bytes otherwise."""
    try:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "p.jpg"
            proc = subprocess.run(
                ["sips", "-Z", str(MAX_EDGE), "-s", "format", "jpeg",
                 "-s", "formatOptions", "85", str(path), "--out", str(out)],
                capture_output=True, timeout=30)
            if proc.returncode == 0 and out.exists():
                return out.read_bytes(), "image/jpeg"
    except Exception:
        pass
    return path.read_bytes(), MEDIA_TYPES.get(path.suffix.lower(), "image/jpeg")


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self, cfg: Config):
        if not cfg.base_url:
            raise ValueError("PARTS_PILE_BASE_URL is required for provider=openai_compat")
        self.cfg = cfg

    def identify(self, photos: list[Path], base_prompt: str) -> BinIdentification:
        content = []
        for p in photos:
            raw, media = _prepped_bytes(p)
            data = base64.standard_b64encode(raw).decode("utf-8")
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:{media};base64,{data}"}})
        content.append({"type": "text", "text": base_prompt})
        body = {
            "model": self.cfg.model,
            # generous budget: reasoning-mode models (e.g. Qwen 3.8 in LM Studio)
            # burn 1-2k tokens thinking before any content appears
            "max_tokens": 6000,
            "messages": [{"role": "user", "content": content}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "bin_identification",
                                "schema": BinIdentification.model_json_schema()},
            },
        }
        def call(b):
            req = urllib.request.Request(
                self.cfg.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(b).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                payload = json.load(resp)
            return (payload["choices"][0]["message"].get("content") or "").strip()

        text = call(body)
        if not text:
            # Reasoning-mode models on some servers (LM Studio + Qwen 3.8) emit empty
            # content when a json_schema grammar is active: drop the grammar and ask
            # for JSON by prompt instead (fence-tolerant parse + pydantic validation).
            from ..schema import json_schema_str

            body2 = {k: v for k, v in body.items() if k != "response_format"}
            body2["messages"] = [dict(body["messages"][0])]
            content2 = list(body2["messages"][0]["content"])
            content2[-1] = {"type": "text", "text": base_prompt
                            + "\n\nReply with ONLY a JSON object matching this schema, "
                              "no prose:\n" + json_schema_str()}
            body2["messages"][0]["content"] = content2
            text = call(body2)
        return parse_model_json(text)
