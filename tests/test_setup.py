"""First-run onboarding: /setup gate and key persistence."""

import importlib
import os
import tempfile
import unittest
from pathlib import Path

os.environ["PARTS_PILE_WORKER"] = "0"

_MANAGED = ["PARTS_PILE_DB_PATH", "PARTS_PILE_PHOTO_DIR", "PARTS_PILE_DATA_DIR",
            "PARTS_PILE_PROVIDER", "ANTHROPIC_API_KEY"]


class SetupFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = {k: os.environ.get(k) for k in _MANAGED}
        os.environ["PARTS_PILE_DB_PATH"] = str(Path(self.tmp.name) / "t.sqlite3")
        os.environ["PARTS_PILE_PHOTO_DIR"] = str(Path(self.tmp.name) / "photos")
        os.environ["PARTS_PILE_DATA_DIR"] = str(Path(self.tmp.name) / "dd")
        os.environ["PARTS_PILE_PROVIDER"] = "anthropic"
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

    def test_root_redirects_to_setup_without_key(self):
        r = self.client.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 307)
        self.assertEqual(r.headers["location"], "/setup")

    def test_setup_page_serves(self):
        r = self.client.get("/setup")
        self.assertEqual(r.status_code, 200)
        self.assertIn("api_key", r.text)

    def test_save_key_persists_and_unlocks(self):
        r = self.client.post("/api/setup", data={"api_key": "sk-ant-test123"},
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        cfg_file = Path(self.tmp.name) / "dd" / "config"
        self.assertIn("ANTHROPIC_API_KEY=sk-ant-test123", cfg_file.read_text())
        self.assertEqual(cfg_file.stat().st_mode & 0o777, 0o600)
        r = self.client.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 200)

    def test_claude_code_provider_never_gated(self):
        os.environ["PARTS_PILE_PROVIDER"] = "claude_code"
        importlib.reload(self.appmod)
        from fastapi.testclient import TestClient
        client = TestClient(self.appmod.app)
        r = client.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
