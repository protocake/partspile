from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

from ..schema import BinIdentification


class VisionProvider(Protocol):
    def identify(self, photos: list[Path], base_prompt: str) -> BinIdentification:
        """One call per bin: all shots of the bin go in together."""
        ...


def parse_model_json(text: str, cls=BinIdentification) -> BinIdentification:
    """Parse model output into the schema, tolerating markdown fences."""
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    return cls.model_validate(json.loads(cleaned))
