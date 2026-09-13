"""Unit tests for eval.py using synthetic data only (never fixtures/)."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("evaltool", REPO / "eval.py")
evaltool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaltool)


def part(canonical, qty=1, confidence="high", needs_reshoot=False):
    return {"canonical": canonical, "qty": qty, "confidence": confidence,
            "needs_reshoot": needs_reshoot}


def truth_part(canonical, qty=1, hidden_spec=None):
    p = {"canonical": canonical, "category": "sensor", "qty": qty}
    if hidden_spec:
        p["hidden_spec"] = hidden_spec
    return p


class TestScoring(unittest.TestCase):
    def test_perfect_match(self):
        truth = {"bin01": {"parts": [truth_part("KY-015", 2), truth_part("ESP32-WROOM-32 devkit")]}}
        preds = {"bin01": {"parts": [part("KY-015", 2), part("ESP32-WROOM-32 devkit")]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["precision"], 1.0)
        self.assertEqual(r["recall"], 1.0)
        self.assertEqual(r["recall_high"], 1.0)
        self.assertTrue(r["passed"])

    def test_missed_part_hits_recall_not_precision(self):
        truth = {"bin01": {"parts": [truth_part("KY-015"), truth_part("KY-040")]}}
        preds = {"bin01": {"parts": [part("KY-015")]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["precision"], 1.0)
        self.assertEqual(r["recall_high"], 0.5)

    def test_extra_prediction_hits_precision(self):
        truth = {"bin01": {"parts": [truth_part("KY-015")]}}
        preds = {"bin01": {"parts": [part("KY-015"), part("HC-SR04")]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["precision"], 0.5)
        self.assertEqual(r["recall"], 1.0)

    def test_qty_partial_credit(self):
        truth = {"bin01": {"parts": [truth_part("1k resistor", qty=3)]}}
        preds = {"bin01": {"parts": [part("1k resistor", qty=2)]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["recall"], 2 / 3)
        self.assertEqual(r["precision"], 1.0)

    def test_overcount_hits_precision(self):
        truth = {"bin01": {"parts": [truth_part("1k resistor", qty=2)]}}
        preds = {"bin01": {"parts": [part("1k resistor", qty=5)]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["precision"], 2 / 5)
        self.assertEqual(r["recall"], 1.0)

    def test_normalization_matches_dash_case_variants(self):
        truth = {"bin01": {"parts": [truth_part("SRD-05VDC-SL-C")]}}
        preds = {"bin01": {"parts": [part("srd 05vdc sl c")]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["recall"], 1.0)

    def test_hidden_spec_excluded_from_recall_high(self):
        # A correctly-flagged hidden-spec part (medium confidence + needs_reshoot) must
        # not drag recall_high down — it is scored by the reshoot metric instead.
        truth = {"bin01": {"parts": [truth_part("KY-015"),
                                     truth_part("EC11 encoder", hidden_spec="pins hidden")]}}
        preds = {"bin01": {"parts": [part("KY-015", confidence="high"),
                                     part("EC11 encoder", confidence="medium",
                                          needs_reshoot=True)]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["recall_high"], 1.0)
        self.assertEqual(r["recall"], 1.0)
        self.assertTrue(r["passed"])

    def test_only_high_confidence_counts_toward_recall_high(self):
        truth = {"bin01": {"parts": [truth_part("KY-015"), truth_part("KY-040")]}}
        preds = {"bin01": {"parts": [part("KY-015", confidence="high"),
                                     part("KY-040", confidence="low")]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["recall"], 1.0)
        self.assertEqual(r["recall_high"], 0.5)

    def test_bins_missing_from_predictions_count_as_misses(self):
        truth = {"bin01": {"parts": [truth_part("KY-015")]},
                 "bin02": {"parts": [truth_part("KY-040")]}}
        preds = {"bin01": {"parts": [part("KY-015")]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["recall"], 0.5)

    def test_predictions_for_unknown_bin_hit_precision(self):
        truth = {"bin01": {"parts": [truth_part("KY-015")]}}
        preds = {"bin01": {"parts": [part("KY-015")]},
                 "bin99": {"parts": [part("HC-SR04")]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["precision"], 0.5)
        self.assertIn("bin99", r["extra_pred_bins"])


class TestNameMatching(unittest.TestCase):
    def _match(self, truth_name, pred_name):
        truth = {"bin01": {"parts": [truth_part(truth_name)]}}
        preds = {"bin01": {"parts": [part(pred_name)]}}
        return evaltool.score(truth, preds, [])["recall"] == 1.0

    def test_unit_suffix_variants_match(self):
        self.assertTrue(self._match("28BYJ-48 5V", "28BYJ-48"))

    def test_brand_prefix_variants_match(self):
        self.assertTrue(self._match("Qorvo DWM3001CDK", "DWM3001CDK"))
        self.assertTrue(self._match("Makerfabs ESP32 UWB DW3000",
                                    "ESP32 UWB DW3000 (ESP32-WROOM-32E + DW3000)"))

    def test_descriptor_tail_variants_match(self):
        self.assertTrue(self._match("USB LiPo charger 600mA x2 (drone type)",
                                    "USB LiPo charger 600mA x2"))
        self.assertTrue(self._match("buzzer", "passive piezo buzzer 12mm"))

    def test_lookalike_designations_never_fuzzy_match(self):
        self.assertFalse(self._match("KY-023", "KY-040"))
        self.assertFalse(self._match("GY-521", "GY-273"))
        self.assertFalse(self._match("KY-023 joystick module", "KY-040 rotary encoder"))

    def test_different_part_numbers_never_match(self):
        self.assertFalse(self._match("LiPo 852030 3.7V 150mAh", "FB652030 3.7V LiPo"))

    def test_dot_punctuation_variants_match(self):
        self.assertTrue(self._match("18650 Battery Shield V10.4.6",
                                    "18650 battery shield (V1046, dual-cell)"))

    def test_part_code_suffix_variants_match(self):
        self.assertTrue(self._match("LiPo 103040 3.7V 1200mAh", "103040PL"))
        self.assertTrue(self._match("2N2222A", "2N2222"))

    def test_chip_generations_never_collapse(self):
        self.assertFalse(self._match("ESP32", "ESP32S3"))
        self.assertFalse(self._match("LiPo 852030 3.7V 150mAh", "FB652030"))


class TestHiddenSpecWildcard(unittest.TestCase):
    def test_named_hidden_part_matches_generic_reshoot_prediction(self):
        # Truth knows it's an L293D (from out-of-band close-ups) but the photo can't
        # show that; "unknown DIP IC" + needs_reshoot is CORRECT behavior.
        truth = {"bin01": {"parts": [truth_part("L293D", hidden_spec="marking hidden")]}}
        preds = {"bin01": {"parts": [part("unknown 16-pin DIP IC", confidence="low",
                                          needs_reshoot=True)]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["precision"], 1.0)
        self.assertEqual(r["recall"], 1.0)
        self.assertEqual(r["reshoot"]["correct"], 1)
        self.assertTrue(r["passed"])

    def test_hidden_part_still_prefers_name_match(self):
        truth = {"bin01": {"parts": [truth_part("KY-023", hidden_spec="cap missing")]}}
        preds = {"bin01": {"parts": [part("KY-023", confidence="medium",
                                          needs_reshoot=True)]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["reshoot"]["correct"], 1)


class TestUnidentifiedWildcard(unittest.TestCase):
    def test_unidentified_matches_reshoot_flagged_prediction(self):
        # Nobody (including Ben) can name the part; the pipeline guesses SOME name but
        # flags needs_reshoot — that's correct behavior and must not cost precision.
        truth = {"bin01": {"parts": [truth_part("unidentified wrapped component",
                                                hidden_spec="unknowable")]}}
        preds = {"bin01": {"parts": [part("mystery inductor?", confidence="low",
                                          needs_reshoot=True)]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["precision"], 1.0)
        self.assertEqual(r["recall"], 1.0)
        self.assertEqual(r["reshoot"]["correct"], 1)
        self.assertTrue(r["passed"])

    def test_unidentified_does_not_match_confident_prediction(self):
        # A confident wrong guess on an unknowable part stays unmatched: precision hit
        # and reshoot miss.
        truth = {"bin01": {"parts": [truth_part("unidentified wrapped component",
                                                hidden_spec="unknowable")]}}
        preds = {"bin01": {"parts": [part("2N2222A", confidence="high",
                                          needs_reshoot=False)]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["precision"], 0.0)
        self.assertEqual(r["reshoot"]["correct"], 0)
        self.assertFalse(r["passed"])

    def test_wildcard_does_not_steal_name_matched_predictions(self):
        truth = {"bin01": {"parts": [truth_part("KY-015"),
                                     truth_part("unidentified wrapped component",
                                                hidden_spec="unknowable")]}}
        preds = {"bin01": {"parts": [part("KY-015", needs_reshoot=True),
                                     part("weird thing", confidence="low",
                                          needs_reshoot=True)]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["precision"], 1.0)
        self.assertEqual(r["recall"], 1.0)


class TestAliases(unittest.TestCase):
    def test_buzzer_variants_all_match_generic_buzzer(self):
        truth = {"bin01": {"parts": [truth_part("buzzer", hidden_spec="type unknown")]}}
        for name in ("passive buzzer", "active buzzer", "piezo buzzer", "buzzer"):
            preds = {"bin01": {"parts": [part(name, confidence="medium",
                                              needs_reshoot=True)]}}
            r = evaltool.score(truth, preds, [])
            self.assertEqual(r["recall"], 1.0, name)


class TestNeedsReshoot(unittest.TestCase):
    def test_hidden_spec_flagged_correctly(self):
        truth = {"bin01": {"parts": [truth_part("EC11 encoder", hidden_spec="pins hidden")]}}
        preds = {"bin01": {"parts": [part("EC11 encoder", needs_reshoot=True)]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["reshoot"]["correct"], 1)
        self.assertTrue(r["passed"])

    def test_hidden_spec_not_flagged_fails(self):
        truth = {"bin01": {"parts": [truth_part("EC11 encoder", hidden_spec="pins hidden")]}}
        preds = {"bin01": {"parts": [part("EC11 encoder", needs_reshoot=False)]}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["reshoot"]["correct"], 0)
        self.assertFalse(r["passed"])

    def test_unmatched_hidden_spec_counts_incorrect(self):
        truth = {"bin01": {"parts": [truth_part("EC11 encoder", hidden_spec="pins hidden")]}}
        preds = {"bin01": {"parts": []}}
        r = evaltool.score(truth, preds, [])
        self.assertEqual(r["reshoot"]["total"], 1)
        self.assertEqual(r["reshoot"]["correct"], 0)


class TestLookalikes(unittest.TestCase):
    PAIR = [("GY-521", "GY-273")]

    def test_confusion_detected(self):
        truth = {"bin01": {"parts": [truth_part("GY-521")]}}
        preds = {"bin01": {"parts": [part("GY-273")]}}
        r = evaltool.score(truth, preds, self.PAIR)
        self.assertEqual(len(r["confusions"]), 1)
        self.assertFalse(r["passed"])

    def test_no_confusion_when_twin_really_present(self):
        truth = {"bin01": {"parts": [truth_part("GY-521"), truth_part("GY-273")]}}
        preds = {"bin01": {"parts": [part("GY-521"), part("GY-273")]}}
        r = evaltool.score(truth, preds, self.PAIR)
        self.assertEqual(len(r["confusions"]), 0)

    def test_confusion_symmetric(self):
        truth = {"bin01": {"parts": [truth_part("GY-273")]}}
        preds = {"bin01": {"parts": [part("GY-521")]}}
        r = evaltool.score(truth, preds, self.PAIR)
        self.assertEqual(len(r["confusions"]), 1)


class TestLog(unittest.TestCase):
    HEADER = ("# Eval log\n\n"
              "| # | date | prompt ver | provider | model | precision | recall (high-conf) "
              "| lookalike confusions | needs_reshoot correct | notes |\n"
              "|---|------|-----------|----------|-------|-----------|--------------------"
              "|----------------------|-----------------------|-------|\n")

    def _result(self):
        truth = {"bin01": {"parts": [truth_part("KY-015")]}}
        preds = {"bin01": {"parts": [part("KY-015")]}}
        return evaltool.score(truth, preds, [])

    def test_append_and_iteration_counter(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "log.md"
            log.write_text(self.HEADER)
            meta = {"prompt_version": "v1", "provider": "anthropic", "model": "claude-opus-5"}
            n1 = evaltool.append_log(log, meta, self._result(), "first")
            n2 = evaltool.append_log(log, meta, self._result(), "second")
            self.assertEqual((n1, n2), (1, 2))
            self.assertEqual(evaltool.next_iteration(log), 3)
            lines = log.read_text().splitlines()
            self.assertIn("| 2 |", lines[-1])
            self.assertIn("anthropic", lines[-1])


class TestCli(unittest.TestCase):
    def test_refuses_holdout(self):
        with self.assertRaises(SystemExit) as cm:
            evaltool.main(["--from-json", "x.json", "--truth", "fixtures/holdout/truth.json"])
        self.assertIn("holdout", str(cm.exception))

    def test_end_to_end_from_json(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "truth.json").write_text(json.dumps(
                {"bin01": {"parts": [truth_part("KY-015")]}}))
            (d / "preds.json").write_text(json.dumps(
                {"meta": {"prompt_version": "v0", "provider": "test", "model": "none"},
                 "bins": {"bin01": {"parts": [part("KY-015")]}}}))
            log = d / "log.md"
            log.write_text(TestLog.HEADER)
            rc = evaltool.main(["--from-json", str(d / "preds.json"),
                                "--truth", str(d / "truth.json"),
                                "--log-path", str(log), "--strict"])
            self.assertEqual(rc, 0)
            self.assertIn("| v0 | test |", log.read_text())

    def test_strict_fails_below_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "truth.json").write_text(json.dumps(
                {"bin01": {"parts": [truth_part("KY-015"), truth_part("KY-040")]}}))
            (d / "preds.json").write_text(json.dumps(
                {"bins": {"bin01": {"parts": [part("KY-015")]}}}))
            rc = evaltool.main(["--from-json", str(d / "preds.json"),
                                "--truth", str(d / "truth.json"),
                                "--no-log", "--strict"])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
