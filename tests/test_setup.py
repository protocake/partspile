"""Deferred onboarding: welcome-first pages, connect endpoints, sample seeding."""

import importlib
import os
import tempfile
import unittest
from pathlib import Path

os.environ["PARTS_PILE_WORKER"] = "0"
os.environ["PARTS_PILE_SAMPLES"] = "0"

_MANAGED = ["PARTS_PILE_DB_PATH", "PARTS_PILE_PHOTO_DIR", "PARTS_PILE_DATA_DIR",
            "PARTS_PILE_PROVIDER", "PARTS_PILE_MODEL", "PARTS_PILE_BASE_URL",
            "ANTHROPIC_API_KEY"]


class OnboardingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = {k: os.environ.get(k) for k in _MANAGED}
        os.environ["PARTS_PILE_DB_PATH"] = str(Path(self.tmp.name) / "t.sqlite3")
        os.environ["PARTS_PILE_PHOTO_DIR"] = str(Path(self.tmp.name) / "photos")
        os.environ["PARTS_PILE_DATA_DIR"] = str(Path(self.tmp.name) / "dd")
        os.environ["PARTS_PILE_PROVIDER"] = "anthropic"  # fresh-install marker
        os.environ.pop("ANTHROPIC_API_KEY", None)
        import partspile.web.app as appmod
        importlib.reload(appmod)
        self.appmod = appmod
        from fastapi.testclient import TestClient
        self.client = TestClient(appmod.app)

    def tearDown(self):
        if self.appmod.db:
            self.appmod.db.close()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_pages_open_without_backend(self):
        for path in ("/", "/capture", "/setup"):
            r = self.client.get(path, follow_redirects=False)
            self.assertEqual(r.status_code, 200, path)
        self.assertIn("Welcome to Parts Pile", self.client.get("/").text)
        self.assertIn("connect-banner", self.client.get("/capture").text)

    def test_status_reports_not_ready_then_ready_after_key(self):
        s = self.client.get("/api/setup/status").json()
        self.assertFalse(s["ready"])
        self.assertIn("detect", s)
        r = self.client.post("/api/setup", data={"api_key": "sk-ant-test123"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        cfg_file = Path(self.tmp.name) / "dd" / "config"
        self.assertIn("ANTHROPIC_API_KEY=sk-ant-test123", cfg_file.read_text())
        self.assertEqual(cfg_file.stat().st_mode & 0o777, 0o600)
        self.assertTrue(self.client.get("/api/setup/status").json()["ready"])

    def test_local_connect_saves_config(self):
        r = self.client.post("/api/setup/local", json={
            "provider": "openai_compat", "model": "qwen/qwen3.8-27b",
            "base_url": "http://localhost:1234/v1"})
        self.assertEqual(r.status_code, 200)
        text = (Path(self.tmp.name) / "dd" / "config").read_text()
        self.assertIn("PARTS_PILE_PROVIDER=openai_compat", text)
        self.assertIn("PARTS_PILE_PROMPT=v1-local", text)
        self.assertTrue(self.appmod.backend_ready(self.appmod.cfg))

    def test_local_connect_validates(self):
        r = self.client.post("/api/setup/local", json={"provider": "bogus", "model": ""})
        self.assertEqual(r.status_code, 400)

    def test_sample_seed_and_clear(self):
        from partspile.db import Db
        from partspile.sample_data import clear_samples, seed_samples
        photo_dir = Path(self.tmp.name) / "photos"
        d = Db(Path(self.tmp.name) / "s.sqlite3")
        self.assertTrue(seed_samples(d, photo_dir))
        parts = d.conn.execute("SELECT * FROM parts").fetchall()
        self.assertEqual(len(parts), 5)
        self.assertTrue(all(p["status"] == "accepted" for p in parts))
        self.assertTrue(all(p["bin"] == "samples" for p in parts))
        self.assertTrue(all(p["key_photo_id"] for p in parts))
        self.assertEqual(len(list(photo_dir.glob("sample_*.svg"))), 5)
        self.assertFalse(seed_samples(d, photo_dir))  # idempotent
        self.assertEqual(clear_samples(d, photo_dir), 5)
        self.assertEqual(d.conn.execute("SELECT COUNT(*) c FROM parts").fetchone()["c"], 0)
        self.assertEqual(list(photo_dir.glob("sample_*.svg")), [])
        # a used DB never gets re-seeded
        d.create_scan("real scan")
        self.assertFalse(seed_samples(d, photo_dir))
        d.close()


if __name__ == "__main__":
    unittest.main()
