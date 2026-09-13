"""Native Ollama provider tests — fake poster, no server."""

import json
import unittest
from pathlib import Path

from partspile.config import Config
from partspile.providers.ollama_native import OllamaNativeProvider

VALID = {"parts": [
    {"name": "DHT11 module", "canonical": "KY-015", "category": "sensor",
     "unit_type": "standalone_object", "legibility": "markings_read_clearly",
     "confidence": "high"},
    {"name": "ESP-32 module on the board", "canonical": "ESP-32",
     "category": "board", "unit_type": "component_attached_to_a_listed_object",
     "legibility": "markings_read_clearly", "confidence": "high"},
    {"name": "mystery IC", "canonical": "unknown DIP", "category": "bare_component",
     "unit_type": "standalone_object",
     "legibility": "markings_unreadable_or_hidden", "confidence": "high"}]}


class OllamaNativeTest(unittest.TestCase):
    def _provider(self, base_url="http://localhost:11434/v1"):
        calls = {}

        def poster(url, body):
            calls["url"] = url
            calls["body"] = body
            return {"message": {"content": json.dumps(VALID)}}

        prov = OllamaNativeProvider(
            Config(provider="ollama", base_url=base_url, model="partspile-qwen"),
            poster=poster)
        return prov, calls

    def test_native_endpoint_thinking_off_and_schema(self):
        prov, calls = self._provider()
        tmp = Path("/tmp/nonexistent-fake.jpg")
        tmp.write_bytes(b"fake")
        ident = prov.identify([tmp], "identify the part")
        # attached component dropped by enforcement
        self.assertEqual([p.canonical for p in ident.parts],
                         ["KY-015", "unknown DIP"])
        # illegible part forced to reshoot, confidence capped
        mystery = ident.parts[1]
        self.assertTrue(mystery.needs_reshoot)
        self.assertEqual(mystery.confidence, "medium")
        self.assertIn("unreadable", mystery.reshoot_reason)
        # clearly-read part untouched
        self.assertFalse(ident.parts[0].needs_reshoot)
        self.assertEqual(ident.parts[0].confidence, "high")
        self.assertEqual(calls["url"], "http://localhost:11434/api/chat")  # /v1 stripped
        body = calls["body"]
        self.assertIs(body["think"], False)
        self.assertEqual(body["model"], "partspile-qwen")
        self.assertIn("unit_type", json.dumps(body["format"]))  # forced decisions
        # field order: legibility must precede confidence in the grammar
        keys = list(body["format"]["$defs"]["LocalPart"]["properties"])
        self.assertLess(keys.index("legibility"), keys.index("confidence"))
        self.assertEqual(len(body["messages"][0]["images"]), 1)


if __name__ == "__main__":
    unittest.main()
