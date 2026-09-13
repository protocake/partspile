"""User data dir + local config file: resolution order and permissions."""

import os
import tempfile
import unittest
from pathlib import Path

from partspile import paths


class TestPaths(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._old = os.environ.get("PARTS_PILE_DATA_DIR")
        os.environ["PARTS_PILE_DATA_DIR"] = self._td.name

    def tearDown(self):
        if self._old is None:
            os.environ.pop("PARTS_PILE_DATA_DIR", None)
        else:
            os.environ["PARTS_PILE_DATA_DIR"] = self._old
        self._td.cleanup()

    def test_data_dir_resolves_without_creating(self):
        sub = Path(self._td.name) / "nested" / "pp"
        os.environ["PARTS_PILE_DATA_DIR"] = str(sub)
        self.assertEqual(paths.data_dir(), sub)
        self.assertFalse(sub.exists())  # read-only-HOME safe: resolve never mkdirs

    def test_save_creates_data_dir(self):
        sub = Path(self._td.name) / "nested" / "pp"
        os.environ["PARTS_PILE_DATA_DIR"] = str(sub)
        paths.save_local_config({"K": "v"})
        self.assertTrue((sub / "config").exists())

    def test_load_tolerates_unreadable_dir(self):
        os.environ["PARTS_PILE_DATA_DIR"] = str(Path(self._td.name) / "missing")
        paths.load_local_config()  # must not raise

    def test_save_and_load_roundtrip(self):
        paths.save_local_config({"A_KEY": "v1"})
        os.environ.pop("A_KEY", None)
        paths.load_local_config()
        self.assertEqual(os.environ.pop("A_KEY"), "v1")

    def test_env_wins_over_file(self):
        paths.save_local_config({"B_KEY": "from-file"})
        os.environ["B_KEY"] = "from-env"
        paths.load_local_config()
        self.assertEqual(os.environ.pop("B_KEY"), "from-env")

    def test_merge_write_preserves_existing_keys(self):
        paths.save_local_config({"K1": "a"})
        paths.save_local_config({"K2": "b"})
        text = paths.config_file().read_text()
        self.assertIn("K1=a", text)
        self.assertIn("K2=b", text)

    def test_config_file_mode_0600(self):
        paths.save_local_config({"SECRET": "x"})
        mode = paths.config_file().stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_comments_and_blank_lines_ignored(self):
        paths.config_file().write_text("# comment\n\nC_KEY=ok\nbadline\n")
        os.environ.pop("C_KEY", None)
        paths.load_local_config()
        self.assertEqual(os.environ.pop("C_KEY"), "ok")


if __name__ == "__main__":
    unittest.main()
