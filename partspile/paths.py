"""Where app state lives: one flat user data dir, ~/.partspile by default.

Every location is overridable by the same env vars the app has always used
(PARTS_PILE_DB_PATH, PARTS_PILE_PHOTO_DIR); this module only changes what the
*default* is when nothing is set. A flat KEY=VALUE file at ~/.partspile/config
seeds os.environ for keys not already exported — real env vars always win.
"""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """Resolve only — never create. Writers (Db, photo saves, save_local_config)
    mkdir what they need; resolving at import must work on a read-only HOME."""
    return Path(os.environ.get("PARTS_PILE_DATA_DIR", str(Path.home() / ".partspile"))).expanduser()


def config_file() -> Path:
    return data_dir() / "config"


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def load_local_config() -> None:
    """Seed os.environ from the config file for keys not already set.
    Any filesystem problem degrades to 'no local config found'."""
    try:
        p = config_file()
        if not p.exists():
            return
        for k, v in _parse(p.read_text()).items():
            os.environ.setdefault(k, v)
    except OSError:
        pass


def save_local_config(values: dict[str, str]) -> None:
    """Merge-write the config file (mode 0600 — it may hold an API key)."""
    p = config_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    merged = _parse(p.read_text()) if p.exists() else {}
    merged.update(values)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(f"{k}={v}" for k, v in merged.items()) + "\n")
    p.chmod(0o600)
