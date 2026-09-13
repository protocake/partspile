"""Anthropic API provider (API key). All Anthropic-specific code stays in this module."""

from __future__ import annotations

import base64
from pathlib import Path

from ..config import Config
from ..schema import BinIdentification

MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
               ".webp": "image/webp", ".gif": "image/gif"}


def _image_block(path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": MEDIA_TYPES.get(path.suffix.lower(), "image/jpeg"),
            "data": data,
        },
    }


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, cfg: Config):
        import anthropic  # lazy: claude_code deployments don't need the SDK

        self.cfg = cfg
        self.client = anthropic.Anthropic()

    def identify(self, photos: list[Path], base_prompt: str) -> BinIdentification:
        content = [_image_block(p) for p in photos]
        content.append({"type": "text", "text": base_prompt})
        response = self.client.messages.parse(
            model=self.cfg.model,
            max_tokens=16000,
            messages=[{"role": "user", "content": content}],
            output_format=BinIdentification,
        )
        return response.parsed_output
