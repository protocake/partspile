"""Env-driven configuration. API keys come from env only — never from the repo.

Resolution order for every setting: real env var > ~/.partspile/config file
(seeded into os.environ at import, setdefault only) > code default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .paths import data_dir, load_local_config

load_local_config()


def _default_db_path() -> Path:
    env = os.environ.get("PARTS_PILE_DB_PATH")
    if env:
        return Path(env)
    legacy = Path("data/partspile.sqlite3")  # pre-0.2 dev layout, CWD-relative
    if legacy.exists():
        return legacy
    return data_dir() / "partspile.sqlite3"


@dataclass
class Config:
    provider: str = field(default_factory=lambda: os.environ.get("PARTS_PILE_PROVIDER", "claude_code"))
    model: str = field(default_factory=lambda: os.environ.get("PARTS_PILE_MODEL", "claude-opus-5"))
    base_url: str = field(default_factory=lambda: os.environ.get("PARTS_PILE_BASE_URL", ""))
    db_path: Path = field(default_factory=_default_db_path)
    claude_bin: str = field(default_factory=lambda: os.environ.get("PARTS_PILE_CLAUDE_BIN", "claude"))
    prompt_version: str = field(default_factory=lambda: os.environ.get("PARTS_PILE_PROMPT", "v3"))

    def prompt_path(self) -> Path:
        # Package-relative: correct in a checkout AND in an installed wheel
        # (prompts/*.md ship as package data).
        return Path(__file__).resolve().parent / "prompts" / f"{self.prompt_version}.md"
