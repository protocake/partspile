"""Default build-phase provider: headless Claude Code on the local subscription login.

Shells out to `claude -p` (no API key, no SDK). The prompt tells the agent to Read the
photo files; JSON is enforced by prompt + validation + one retry. See DECISIONS.md #19.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..config import Config
from ..schema import BinIdentification, json_schema_str
from .base import parse_model_json


class ClaudeCodeProvider:
    name = "claude_code"

    def __init__(self, cfg: Config, runner=subprocess.run):
        self.cfg = cfg
        self._run = runner

    def _invoke(self, prompt: str) -> str:
        cmd = [
            self.cfg.claude_bin, "-p", prompt,
            "--output-format", "json",
            "--model", self.cfg.model,
        ]
        proc = self._run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(f"claude -p failed (rc={proc.returncode}): {proc.stderr[:500]}")
        envelope = json.loads(proc.stdout)
        if envelope.get("is_error"):
            raise RuntimeError(f"claude -p error result: {str(envelope)[:500]}")
        return envelope["result"]

    def identify(self, photos: list[Path], base_prompt: str) -> BinIdentification:
        photo_list = "\n".join(f"- {p.resolve()}" for p in photos)
        prompt = (
            f"{base_prompt}\n\n"
            f"Photos of this bin (use your Read tool on each file before answering):\n"
            f"{photo_list}\n\n"
            f"Output JSON schema:\n{json_schema_str()}\n\n"
            f"Reply with ONLY the JSON object. No prose, no fences."
        )
        text = self._invoke(prompt)
        try:
            return parse_model_json(text)
        except Exception as first_err:
            retry_prompt = (
                f"{prompt}\n\nYour previous reply could not be parsed against the schema "
                f"({first_err}). Reply again with ONLY a valid JSON object."
            )
            return parse_model_json(self._invoke(retry_prompt))

    def identify_app(self, photos: list[Path], base_prompt: str):
        """App-runtime call: same identification plus per-photo verdicts (photo-reject
        feature). Kept separate from identify() so the eval schema never changes."""
        from ..schema import AppBinIdentification

        photo_list = "\n".join(f"- {p.resolve()}" for p in photos)
        schema = json.dumps(AppBinIdentification.model_json_schema(), indent=2)
        prompt = (
            f"{base_prompt}\n\n"
            f"Photos of this bin (use your Read tool on each file before answering):\n"
            f"{photo_list}\n\n"
            f"ALSO assess each photo itself in photo_feedback: verdict 'retake' when a "
            f"photo is too blurry, too dark, or so overlapping/cluttered that parts "
            f"cannot be separated — with a reason saying how to reshoot it; verdict "
            f"'ok' otherwise. Use the photo's filename as 'shot'.\n\n"
            f"Output JSON schema:\n{schema}\n\n"
            f"Reply with ONLY the JSON object. No prose, no fences."
        )
        text = self._invoke(prompt)
        try:
            return parse_model_json(text, cls=AppBinIdentification)
        except Exception as first_err:
            retry_prompt = (
                f"{prompt}\n\nYour previous reply could not be parsed against the schema "
                f"({first_err}). Reply again with ONLY a valid JSON object."
            )
            return parse_model_json(self._invoke(retry_prompt), cls=AppBinIdentification)
