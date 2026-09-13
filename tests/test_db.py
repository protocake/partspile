"""Storage-layer tests: full capture -> queue -> review -> browse lifecycle."""

import tempfile
import unittest
from pathlib import Path

from partspile.db import Db


def sample_part(canonical="KY-015", **over):
    p = {"name": "DHT11 module", "canonical": canonical, "category": "sensor",
         "interface": "digital", "voltage": "5V", "qty": 1, "confidence": "high",
         "needs_reshoot": False, "reshoot_reason": "", "bboxes": []}
    p.update(over)
    return p


class DbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Db(Path(self.tmp.name) / "t.sqlite3")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _scan_with_run(self):
        scan_id = self.db.create_scan("shoebox", "desk")
        self.db.add_photo(scan_id, "photos/x1.jpg", 1)
        self.db.add_photo(scan_id, "photos/x2.jpg", 2)
        run_id = self.db.enqueue_run(scan_id, "claude_code", "claude-opus-5", "v3")
        return scan_id, run_id

    def test_queue_lifecycle(self):
        _, run_id = self._scan_with_run()
        claimed = self.db.claim_next_run()
        self.assertEqual(claimed["id"], run_id)
        self.assertEqual(claimed["status"], "running")
        self.assertIsNone(self.db.claim_next_run())  # nothing else queued
        self.db.finish_run(run_id, "{}", [sample_part(), sample_part("KY-040")])
        rows = self.db.pending_parts()
        self.assertEqual([r["canonical"] for r in rows], ["KY-015", "KY-040"])

    def test_failed_run_retry(self):
        _, run_id = self._scan_with_run()
        self.db.claim_next_run()
        self.db.fail_run(run_id, "boom")
        self.assertIsNone(self.db.claim_next_run())
        self.db.retry_run(run_id)
        self.assertEqual(self.db.claim_next_run()["id"], run_id)

    def test_stale_running_adopted_on_restart(self):
        _, run_id = self._scan_with_run()
        self.db.claim_next_run()
        self.assertEqual(self.db.adopt_stale_running(), 1)
        self.assertEqual(self.db.claim_next_run()["id"], run_id)

    def test_review_accept_edit_delete(self):
        _, run_id = self._scan_with_run()
        self.db.claim_next_run()
        self.db.finish_run(run_id, "{}", [sample_part(), sample_part("junk")])
        p1, p2 = self.db.pending_parts()
        self.db.accept_part(p1["id"])
        self.db.update_part(p2["id"], canonical="NULLLAB PM11",
                            spec_url="https://github.com/nulllaborg/pm11-module")
        self.assertEqual(len(self.db.pending_parts()), 0)
        found = self.db.search_parts("pm11")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["status"], "edited")
        self.db.delete_part(p1["id"])
        self.assertEqual(len(self.db.search_parts("KY-015")), 0)

    def test_undetermined_stops_reshoot_loop(self):
        _, run_id = self._scan_with_run()
        self.db.claim_next_run()
        self.db.finish_run(run_id, "{}", [sample_part(
            "unknown wrapped thing", needs_reshoot=True, confidence="low")])
        part = self.db.pending_parts()[0]
        self.db.mark_undetermined(part["id"])
        self.db.accept_part(part["id"])
        row = self.db.search_parts("wrapped")[0]
        self.assertEqual(row["resolution"], "undetermined")
        self.assertEqual(row["needs_reshoot"], 0)

    def test_have_count_across_bins(self):
        for label in ("box a", "box b"):
            scan_id = self.db.create_scan(label)
            run_id = self.db.enqueue_run(scan_id, "claude_code", "m", "v3")
            self.db.claim_next_run()
            self.db.finish_run(run_id, "{}", [sample_part(qty=2)])
            self.db.accept_part(self.db.pending_parts()[0]["id"])
        self.assertEqual(self.db.have_count("ky-015"), 4)  # case-insensitive
        self.assertEqual(self.db.have_count("GY-521"), 0)

    def test_serial_notes_roundtrip_and_search(self):
        _, run_id = self._scan_with_run()
        self.db.claim_next_run()
        self.db.finish_run(run_id, "{}", [sample_part()])
        pid = self.db.pending_parts()[0]["id"]
        self.db.update_part(pid, serial="SN-0042",
                            notes="the one with the bent pin from the drone crash")
        self.db.accept_part(pid)
        self.assertEqual(self.db.search_parts("bent pin")[0]["serial"], "SN-0042")
        self.assertEqual(len(self.db.search_parts("SN-0042")), 1)

    def test_v1_database_migrates_to_current(self):
        import sqlite3
        path = Path(self.tmp.name) / "old.sqlite3"
        conn = sqlite3.connect(path)
        # simulate a v1 database: parts table without serial/notes
        conn.executescript("""
            CREATE TABLE bins (id INTEGER PRIMARY KEY, label TEXT NOT NULL,
              location TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
            CREATE TABLE photos (id INTEGER PRIMARY KEY,
              bin_id INTEGER NOT NULL, path TEXT NOT NULL,
              shot_index INTEGER NOT NULL DEFAULT 1, taken_at TEXT NOT NULL);
            CREATE TABLE ident_runs (id INTEGER PRIMARY KEY,
              bin_id INTEGER NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
              prompt_version TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
              error TEXT NOT NULL DEFAULT '', raw_json TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT);
            CREATE TABLE parts (id INTEGER PRIMARY KEY,
              bin_id INTEGER NOT NULL, source_run_id INTEGER, name TEXT NOT NULL,
              canonical TEXT NOT NULL, category TEXT NOT NULL,
              interface TEXT NOT NULL DEFAULT 'unknown',
              voltage TEXT NOT NULL DEFAULT 'unknown', qty INTEGER NOT NULL DEFAULT 1,
              confidence TEXT NOT NULL DEFAULT 'low',
              needs_reshoot INTEGER NOT NULL DEFAULT 0,
              reshoot_reason TEXT NOT NULL DEFAULT '', bbox_json TEXT NOT NULL DEFAULT '[]',
              status TEXT NOT NULL DEFAULT 'pending',
              resolution TEXT NOT NULL DEFAULT 'identified',
              spec_url TEXT NOT NULL DEFAULT '', key_photo_id INTEGER);
            INSERT INTO bins (label, created_at) VALUES ('old box', 'x');
            INSERT INTO parts (bin_id, name, canonical, category, status)
              VALUES (1, 'old part', 'KY-015', 'sensor', 'accepted');
            PRAGMA user_version = 1;
        """)
        conn.commit()
        conn.close()
        db2 = Db(path)
        row = db2.search_parts("KY-015")[0]
        self.assertEqual(row["serial"], "")   # v2 column exists post-migration
        self.assertEqual(row["bin"], "")      # v3 column exists post-migration
        self.assertEqual(row["scan_label"], "old box")  # bins table renamed to scans
        db2.update_part(row["id"], serial="ABC", bin="bin 12")
        self.assertEqual(db2.search_parts("ABC")[0]["canonical"], "KY-015")
        self.assertEqual(db2.search_parts("bin 12")[0]["canonical"], "KY-015")
        db2.close()

    def test_search_filters(self):
        scan_id = self.db.create_scan("box", "attic")
        run_id = self.db.enqueue_run(scan_id, "claude_code", "m", "v3")
        self.db.claim_next_run()
        self.db.finish_run(run_id, "{}", [
            sample_part(), sample_part("SRD-05VDC-SL-C", category="bare_component")])
        for p in self.db.pending_parts():
            self.db.accept_part(p["id"])
        self.assertEqual(len(self.db.search_parts(category="sensor")), 1)
        self.assertEqual(len(self.db.search_parts(location="attic")), 2)
        self.assertEqual(len(self.db.search_parts(location="basement")), 0)


if __name__ == "__main__":
    unittest.main()
