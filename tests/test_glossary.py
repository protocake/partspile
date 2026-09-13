"""House glossary tests: db source, prompt text, pipeline injection."""

import tempfile
import unittest
from pathlib import Path

from partspile.config import Config
from partspile.db import Db
from partspile.glossary import build_glossary_text


def part(canonical, **over):
    p = {"name": canonical + " thing", "canonical": canonical, "category": "sensor",
         "confidence": "high"}
    p.update(over)
    return p


class GlossaryDbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Db(Path(self.tmp.name) / "t.sqlite3")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _add(self, canonical, accept=True, undetermined=False):
        scan = self.db.create_scan("s")
        run = self.db.enqueue_run(scan, "p", "m", "v")
        self.db.claim_next_run()
        self.db.finish_run(run, "{}", [part(canonical)])
        pid = self.db.pending_parts()[0]["id"]
        if undetermined:
            self.db.mark_undetermined(pid)
        if accept:
            self.db.accept_part(pid)
        return pid

    def test_only_vetted_identified_parts_dedup_case_insensitive(self):
        self._add("NULLLAB PM11")
        self._add("nulllab pm11")           # dupe, different case
        self._add("KY-015")
        self._add("pending part", accept=False)          # never vetted
        self._add("mystery blob", undetermined=True)     # given up — never teach
        rows = self.db.glossary()
        canonicals = sorted(r["canonical"].lower() for r in rows)
        self.assertEqual(canonicals, ["ky-015", "nulllab pm11"])

    def test_text_rendering_skips_unidentified(self):
        rows = [{"canonical": "NULLLAB PM11", "name": "USB-C LiPo power module",
                 "category": "power"},
                {"canonical": "unidentified wrapped component", "name": "x",
                 "category": "other"},
                {"canonical": "KY-015", "name": "ky-015", "category": "sensor"}]
        text = build_glossary_text(rows)
        self.assertIn("KNOWN PARTS", text)
        self.assertIn("NULLLAB PM11 — USB-C LiPo power module (power)", text)
        self.assertIn("- KY-015 (sensor)", text)          # no redundant name echo
        self.assertNotIn("unidentified", text)
        self.assertEqual(build_glossary_text([]), "")


class GlossaryPipelineTest(unittest.TestCase):
    def test_run_all_appends_glossary_to_prompt(self):
        from partspile import pipeline as pl

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "photos").mkdir()
            (d / "photos" / "bin01_shot1.jpg").write_bytes(b"x")
            seen = {}

            class FakeProv:
                def identify(self, photos, prompt):
                    seen["prompt"] = prompt
                    from partspile.schema import BinIdentification
                    return BinIdentification(parts=[])

            orig = pl.get_provider
            try:
                pl.get_provider = lambda c: FakeProv()
                pl.run_all(Config(), d / "photos", log=lambda *_: None,
                           glossary_text="\n\nKNOWN PARTS: - NULLLAB PM11 (power)\n")
            finally:
                pl.get_provider = orig
            self.assertIn("NULLLAB PM11", seen["prompt"])


if __name__ == "__main__":
    unittest.main()
