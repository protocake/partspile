"""Enrichment guess tests — fake runner, no real model calls, no network."""

import json
import unittest
from pathlib import Path

from partspile.config import Config
from partspile.enrich import guess_part_details

PART = {"canonical": "SRD-05VDC-SL-C", "name": "Songle relay", "category": "bare_component"}


def fake(result_obj, rc=0, is_error=False):
    class Proc:
        returncode = rc
        stderr = "boom" if rc else ""
        stdout = json.dumps({"is_error": is_error,
                             "result": result_obj if isinstance(result_obj, str)
                             else json.dumps(result_obj)})
    def runner(cmd):
        runner.cmd = cmd
        return Proc()
    return runner


class EnrichTest(unittest.TestCase):
    def test_happy_path(self):
        runner = fake({"serial": "MR07", "serial_note": "printed on label",
                       "spec_url": "https://example.com/srd", "spec_url_note": "datasheet"})
        out = guess_part_details(PART, [Path("/tmp/a.jpg")], Config(), runner)
        self.assertEqual(out["serial"], "MR07")
        self.assertEqual(out["spec_url"], "https://example.com/srd")
        self.assertIn("/tmp/a.jpg", " ".join(runner.cmd))
        self.assertIn("WebSearch", " ".join(runner.cmd))

    def test_nulls_pass_through(self):
        runner = fake({"serial": None, "serial_note": "nothing legible",
                       "spec_url": None, "spec_url_note": "no good result"})
        out = guess_part_details(PART, [Path("/tmp/a.jpg")], Config(), runner)
        self.assertIsNone(out["serial"])
        self.assertIsNone(out["spec_url"])
        self.assertEqual(out["serial_note"], "nothing legible")

    def test_non_url_spec_is_rejected(self):
        runner = fake({"serial": None, "serial_note": "",
                       "spec_url": "songle.com/datasheet", "spec_url_note": ""})
        out = guess_part_details(PART, [Path("/tmp/a.jpg")], Config(), runner)
        self.assertIsNone(out["spec_url"])

    def test_fenced_json_tolerated(self):
        payload = json.dumps({"serial": "X1", "serial_note": "", "spec_url": None,
                              "spec_url_note": ""})
        runner = fake(f"```json\n{payload}\n```")
        out = guess_part_details(PART, [Path("/tmp/a.jpg")], Config(), runner)
        self.assertEqual(out["serial"], "X1")

    def test_failure_raises(self):
        with self.assertRaises(RuntimeError):
            guess_part_details(PART, [Path("/tmp/a.jpg")], Config(), fake({}, rc=1))


if __name__ == "__main__":
    unittest.main()
