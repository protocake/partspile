"""SQLite storage layer. The ident_runs table doubles as the job queue (DECISIONS #20).

Terminology (Ben, 2026-09-07): a SCAN is the set of photos captured together (was
"bin" pre-v3); BIN is a per-part user field naming the physical container it lives in.

Schema versioning: PRAGMA user_version + idempotent CREATE IF NOT EXISTS.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 5

# version-gated ALTERs applied to existing databases (idempotent via user_version)
MIGRATIONS: dict[int, list[str]] = {
    2: [
        "ALTER TABLE parts ADD COLUMN serial TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE parts ADD COLUMN notes TEXT NOT NULL DEFAULT ''",
    ],
    3: [
        "ALTER TABLE bins RENAME TO scans",
        "ALTER TABLE photos RENAME COLUMN bin_id TO scan_id",
        "ALTER TABLE ident_runs RENAME COLUMN bin_id TO scan_id",
        "ALTER TABLE parts RENAME COLUMN bin_id TO scan_id",
        "ALTER TABLE parts ADD COLUMN bin TEXT NOT NULL DEFAULT ''",
    ],
    4: [
        "ALTER TABLE photos ADD COLUMN part_id INTEGER REFERENCES parts(id)",
        "ALTER TABLE photos ADD COLUMN kind TEXT NOT NULL DEFAULT 'captured'",
    ],
    5: [
        "ALTER TABLE ident_runs ADD COLUMN photo_feedback_json TEXT NOT NULL DEFAULT '[]'",
    ],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY,
    label TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES scans(id),
    path TEXT NOT NULL,
    shot_index INTEGER NOT NULL DEFAULT 1,
    taken_at TEXT NOT NULL,
    part_id INTEGER REFERENCES parts(id),
    kind TEXT NOT NULL DEFAULT 'captured'
);
CREATE TABLE IF NOT EXISTS ident_runs (
    id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES scans(id),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'done', 'failed')),
    error TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    photo_feedback_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS parts (
    id INTEGER PRIMARY KEY,
    scan_id INTEGER NOT NULL REFERENCES scans(id),
    source_run_id INTEGER REFERENCES ident_runs(id),
    name TEXT NOT NULL,
    canonical TEXT NOT NULL,
    category TEXT NOT NULL,
    interface TEXT NOT NULL DEFAULT 'unknown',
    voltage TEXT NOT NULL DEFAULT 'unknown',
    qty INTEGER NOT NULL DEFAULT 1,
    confidence TEXT NOT NULL DEFAULT 'low',
    needs_reshoot INTEGER NOT NULL DEFAULT 0,
    reshoot_reason TEXT NOT NULL DEFAULT '',
    bbox_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'edited')),
    resolution TEXT NOT NULL DEFAULT 'identified'
        CHECK (resolution IN ('identified', 'undetermined')),
    spec_url TEXT NOT NULL DEFAULT '',
    key_photo_id INTEGER REFERENCES photos(id),
    serial TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    bin TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_runs_status ON ident_runs(status);
CREATE INDEX IF NOT EXISTS idx_parts_canonical ON parts(canonical);
CREATE INDEX IF NOT EXISTS idx_parts_scan ON parts(scan_id);
"""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Db:
    def __init__(self, path: Path | str):
        p = Path(path)
        if p.parent != Path("."):
            p.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(p, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        existing = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='parts'").fetchone()
        if existing:
            # migrations first, so renames happen before CREATE IF NOT EXISTS
            for v in range(version + 1, SCHEMA_VERSION + 1):
                for stmt in MIGRATIONS.get(v, []):
                    self.conn.execute(stmt)
        self.conn.executescript(SCHEMA)
        self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self.conn.commit()

    # --- capture ---------------------------------------------------------

    def create_scan(self, label: str, location: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO scans (label, location, created_at) VALUES (?, ?, ?)",
            (label, location, _now()))
        self.conn.commit()
        return cur.lastrowid

    def add_photo(self, scan_id: int, path: str, shot_index: int = 1) -> int:
        cur = self.conn.execute(
            "INSERT INTO photos (scan_id, path, shot_index, taken_at) VALUES (?, ?, ?, ?)",
            (scan_id, path, shot_index, _now()))
        self.conn.commit()
        return cur.lastrowid

    def update_scan(self, scan_id: int, location: str | None = None,
                    label: str | None = None) -> None:
        if location is not None:
            self.conn.execute("UPDATE scans SET location = ? WHERE id = ?",
                              (location, scan_id))
        if label is not None:
            self.conn.execute("UPDATE scans SET label = ? WHERE id = ?",
                              (label, scan_id))
        self.conn.commit()

    def photos_for_scan(self, scan_id: int,
                        captured_only: bool = False) -> list[sqlite3.Row]:
        q = "SELECT * FROM photos WHERE scan_id = ?"
        if captured_only:
            # identification / segmentation must never see catalog (web) images
            q += " AND kind = 'captured' AND part_id IS NULL"
        return self.conn.execute(q + " ORDER BY shot_index, id", (scan_id,)).fetchall()

    def add_part_photo(self, part_id: int, path: str, kind: str = "captured") -> int:
        part = self.conn.execute("SELECT scan_id FROM parts WHERE id = ?",
                                 (part_id,)).fetchone()
        cur = self.conn.execute(
            "INSERT INTO photos (scan_id, path, shot_index, taken_at, part_id, kind) "
            "VALUES (?, ?, 99, ?, ?, ?)",
            (part["scan_id"], path, _now(), part_id, kind))
        self.conn.commit()
        return cur.lastrowid

    def delete_photo(self, photo_id: int) -> str | None:
        """Remove a photo row; clears any key_photo references. Returns its path."""
        row = self.conn.execute("SELECT * FROM photos WHERE id = ?",
                                (photo_id,)).fetchone()
        if not row:
            return None
        with self.conn:
            self.conn.execute(
                "UPDATE parts SET key_photo_id = NULL WHERE key_photo_id = ?",
                (photo_id,))
            self.conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        return row["path"]

    def photos_for_part(self, part_id: int) -> list[sqlite3.Row]:
        """The part's photo pool: its scan's captured shots + its own attached photos."""
        part = self.conn.execute("SELECT scan_id FROM parts WHERE id = ?",
                                 (part_id,)).fetchone()
        return self.conn.execute(
            "SELECT * FROM photos WHERE (scan_id = ? AND part_id IS NULL) "
            "OR part_id = ? ORDER BY shot_index, id",
            (part["scan_id"], part_id)).fetchall()

    # --- queue (ident_runs) ---------------------------------------------

    def enqueue_run(self, scan_id: int, provider: str, model: str, prompt_version: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO ident_runs (scan_id, provider, model, prompt_version, created_at) "
            "VALUES (?, ?, ?, ?, ?)", (scan_id, provider, model, prompt_version, _now()))
        self.conn.commit()
        return cur.lastrowid

    def claim_next_run(self) -> sqlite3.Row | None:
        """Atomically flip the oldest queued run to running and return it."""
        cur = self.conn.execute(
            "UPDATE ident_runs SET status = 'running', started_at = ? "
            "WHERE id = (SELECT id FROM ident_runs WHERE status = 'queued' "
            "            ORDER BY id LIMIT 1) RETURNING *", (_now(),))
        row = cur.fetchone()
        self.conn.commit()
        return row

    def adopt_stale_running(self) -> int:
        """On worker startup: runs stuck 'running' from a crash go back to queued."""
        cur = self.conn.execute(
            "UPDATE ident_runs SET status = 'queued', started_at = NULL "
            "WHERE status = 'running'")
        self.conn.commit()
        return cur.rowcount

    def finish_run(self, run_id: int, raw_json: str, parts: list[dict],
                   photo_feedback_json: str = "[]") -> None:
        run = self.conn.execute("SELECT scan_id FROM ident_runs WHERE id = ?",
                                (run_id,)).fetchone()
        with self.conn:
            self.conn.execute(
                "UPDATE ident_runs SET status = 'done', raw_json = ?, finished_at = ?, "
                "photo_feedback_json = ? WHERE id = ?",
                (raw_json, _now(), photo_feedback_json, run_id))
            for p in parts:
                self.conn.execute(
                    "INSERT INTO parts (scan_id, source_run_id, name, canonical, category, "
                    " interface, voltage, qty, confidence, needs_reshoot, reshoot_reason, "
                    " bbox_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (run["scan_id"], run_id, p["name"], p["canonical"], p["category"],
                     p.get("interface", "unknown"), p.get("voltage", "unknown"),
                     p.get("qty", 1), p.get("confidence", "low"),
                     int(bool(p.get("needs_reshoot"))), p.get("reshoot_reason", ""),
                     json.dumps(p.get("bboxes", []))))

    def fail_run(self, run_id: int, error: str) -> None:
        self.conn.execute(
            "UPDATE ident_runs SET status = 'failed', error = ?, finished_at = ? "
            "WHERE id = ?", (error, _now(), run_id))
        self.conn.commit()

    def retry_run(self, run_id: int) -> None:
        self.conn.execute(
            "UPDATE ident_runs SET status = 'queued', error = '', started_at = NULL, "
            "finished_at = NULL WHERE id = ? AND status = 'failed'", (run_id,))
        self.conn.commit()

    def queue_overview(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT r.*, s.label AS scan_label, s.location AS scan_location "
            "FROM ident_runs r JOIN scans s ON s.id = r.scan_id "
            "ORDER BY r.id DESC LIMIT 50").fetchall()

    # --- review ----------------------------------------------------------

    def pending_parts(self, scan_id: int | None = None) -> list[sqlite3.Row]:
        q = "SELECT * FROM parts WHERE status = 'pending'"
        args: tuple = ()
        if scan_id is not None:
            q += " AND scan_id = ?"
            args = (scan_id,)
        return self.conn.execute(q + " ORDER BY scan_id, id", args).fetchall()

    def accept_part(self, part_id: int) -> None:
        self.conn.execute("UPDATE parts SET status = 'accepted' WHERE id = ?", (part_id,))
        self.conn.commit()

    def update_part(self, part_id: int, **fields) -> None:
        allowed = {"name", "canonical", "category", "interface", "voltage", "qty",
                   "spec_url", "key_photo_id", "needs_reshoot", "resolution",
                   "serial", "notes", "bin"}
        cols = {k: v for k, v in fields.items() if k in allowed}
        if not cols:
            return
        sets = ", ".join(f"{k} = ?" for k in cols)
        self.conn.execute(f"UPDATE parts SET {sets}, status = 'edited' WHERE id = ?",
                          (*cols.values(), part_id))
        self.conn.commit()

    def delete_part(self, part_id: int) -> None:
        self.conn.execute("DELETE FROM parts WHERE id = ?", (part_id,))
        self.conn.commit()

    def mark_undetermined(self, part_id: int) -> None:
        """Ben's give-up state: keep the best guess, stop the reshoot loop."""
        self.conn.execute(
            "UPDATE parts SET resolution = 'undetermined', needs_reshoot = 0 "
            "WHERE id = ?", (part_id,))
        self.conn.commit()

    # --- browse ----------------------------------------------------------

    def search_parts(self, q: str = "", category: str = "", interface: str = "",
                     location: str = "") -> list[sqlite3.Row]:
        sql = ("SELECT p.*, s.label AS scan_label, s.location FROM parts p "
               "JOIN scans s ON s.id = p.scan_id "
               "WHERE p.status IN ('accepted', 'edited')")
        args: list = []
        if q:
            sql += " AND (p.canonical LIKE ? OR p.name LIKE ? OR p.notes LIKE ? OR p.serial LIKE ? OR p.bin LIKE ?)"
            args += [f"%{q}%"] * 5
        if category:
            sql += " AND p.category = ?"
            args.append(category)
        if interface:
            sql += " AND p.interface = ?"
            args.append(interface)
        if location:
            sql += " AND s.location = ?"
            args.append(location)
        sql += " ORDER BY p.canonical"
        return self.conn.execute(sql, args).fetchall()

    def glossary(self, limit: int = 60) -> list[sqlite3.Row]:
        """Known inventory parts for prompt injection (house glossary, DECISIONS #31):
        distinct canonicals from human-vetted rows, newest first. Undetermined parts
        are excluded — never teach the model a guess."""
        return self.conn.execute(
            "SELECT canonical, name, category, MAX(id) AS latest FROM parts "
            "WHERE status IN ('accepted', 'edited') AND resolution = 'identified' "
            "GROUP BY canonical COLLATE NOCASE "
            "ORDER BY latest DESC LIMIT ?", (limit,)).fetchall()

    def have_count(self, canonical: str) -> int:
        """The killer query: how many of this do I already own? (DECISIONS #24)"""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(qty), 0) AS n FROM parts "
            "WHERE status IN ('accepted', 'edited') AND canonical = ? COLLATE NOCASE",
            (canonical,)).fetchone()
        return row["n"]

    def close(self) -> None:
        self.conn.close()
