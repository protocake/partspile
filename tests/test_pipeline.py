"""Unit tests for the partspile package — no network, no real model calls."""

import json
import tempfile
import unittest
from pathlib import Path

from partspile.config import Config
from partspile.pipeline import discover_bins, run_all
from partspile.providers.base import parse_model_json
from partspile.providers.claude_code import ClaudeCodeProvider
from partspile.schema import BinIdentification

VALID_JSON = json.dumps({
    "parts": [{"name": "DHT11 module", "canonical": "KY-015", "category": "sensor",
               "interface": "digital", "voltage": "3.3-5V", "qty": 1,
               "confidence": "high", "needs_reshoot": False, "reshoot_reason": "",
               "bboxes": []}]
})


class TestSchema(unittest.TestCase):
    def test_valid_document_parses(self):
        ident = BinIdentification.model_validate(json.loads(VALID_JSON))
        self.assertEqual(ident.parts[0].canonical, "KY-015")

    def test_bad_category_rejected(self):
        doc = json.loads(VALID_JSON)
        doc["parts"][0]["category"] = "widget"
        with self.assertRaises(Exception):
            BinIdentification.model_validate(doc)

    def test_fences_tolerated(self):
        ident = parse_model_json(f"```json\n{VALID_JSON}\n```")
        self.assertEqual(len(ident.parts), 1)


class TestDiscoverBins(unittest.TestCase):
    def test_grouping_by_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for name in ["bin01_shot1.jpg", "bin01_shot2.jpg", "bin02_shot1.JPG",
                         "notes.txt", "IMG_1234.jpg"]:
                (d / name).write_bytes(b"x")
            bins = discover_bins(d)
            self.assertEqual(set(bins), {"bin01", "bin02"})
            self.assertEqual(len(bins["bin01"]), 2)


def fake_runner_factory(outputs):
    """Build a subprocess.run stand-in yielding queued claude -p envelopes."""
    calls = []

    class Proc:
        def __init__(self, stdout):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return Proc(json.dumps({"is_error": False, "result": outputs[min(len(calls) - 1, len(outputs) - 1)]}))

    runner.calls = calls
    return runner


class TestClaudeCodeProvider(unittest.TestCase):
    def _cfg(self):
        return Config(provider="claude_code", model="claude-opus-5")

    def test_happy_path(self):
        p = ClaudeCodeProvider(self._cfg(), runner=fake_runner_factory([VALID_JSON]))
        ident = p.identify([Path("/tmp/x.jpg")], "identify parts")
        self.assertEqual(ident.parts[0].canonical, "KY-015")

    def test_retry_on_garbage_then_valid(self):
        runner = fake_runner_factory(["not json at all", VALID_JSON])
        p = ClaudeCodeProvider(self._cfg(), runner=runner)
        ident = p.identify([Path("/tmp/x.jpg")], "identify parts")
        self.assertEqual(len(runner.calls), 2)
        self.assertEqual(ident.parts[0].canonical, "KY-015")
        self.assertIn("could not be parsed", runner.calls[1][2])

    def test_prompt_contains_photos_and_schema(self):
        runner = fake_runner_factory([VALID_JSON])
        p = ClaudeCodeProvider(self._cfg(), runner=runner)
        p.identify([Path("/tmp/a.jpg"), Path("/tmp/b.jpg")], "BASE")
        prompt = runner.calls[0][2]
        self.assertIn("BASE", prompt)
        self.assertIn("/tmp/a.jpg", prompt)
        self.assertIn("/tmp/b.jpg", prompt)
        self.assertIn("json", prompt.lower())


class TestIdentifyApp(unittest.TestCase):
    def test_app_mode_parses_photo_feedback(self):
        app_json = json.dumps({
            "parts": json.loads(VALID_JSON)["parts"],
            "photo_feedback": [{"shot": "a.jpg", "verdict": "retake",
                                "reason": "overlapping parts"}]})
        runner = fake_runner_factory([app_json])
        p = ClaudeCodeProvider(Config(provider="claude_code"), runner=runner)
        ident = p.identify_app([Path("/tmp/a.jpg")], "BASE")
        self.assertEqual(ident.parts[0].canonical, "KY-015")
        self.assertEqual(ident.photo_feedback[0].verdict, "retake")
        self.assertIn("photo_feedback", runner.calls[0][2])  # schema in prompt


class TestRunAll(unittest.TestCase):
    def test_run_all_with_fake_provider(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "photos").mkdir()
            (d / "photos" / "bin01_shot1.jpg").write_bytes(b"x")
            (d / "photos" / "bin02_shot1.jpg").write_bytes(b"x")
            cfg = Config(provider="claude_code")
            import partspile.pipeline as pl
            orig = pl.get_provider
            try:
                pl.get_provider = lambda c: ClaudeCodeProvider(c, runner=fake_runner_factory([VALID_JSON]))
                doc = pl.run_all(cfg, d / "photos", out_dir=d / "runs", log=lambda *_: None)
            finally:
                pl.get_provider = orig
            self.assertEqual(set(doc["bins"]), {"bin01", "bin02"})
            self.assertEqual(doc["meta"]["provider"], "claude_code")
            self.assertEqual(doc["meta"]["errors"], {})
            self.assertTrue(list((d / "runs").glob("run_*.json")))


if __name__ == "__main__":
    unittest.main()
