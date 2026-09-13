#!/usr/bin/env python3
"""Score identification pipeline output against fixtures/truth.json.

Usage:
    python eval.py --from-json path/to/predictions.json [options]

Predictions JSON format:
    {
      "meta": {"prompt_version": "v1", "provider": "anthropic", "model": "claude-opus-5"},
      "bins": {
        "bin03": {"parts": [{"canonical": "KY-015", "qty": 2, "confidence": "high",
                              "needs_reshoot": false, ...}, ...]},
        ...
      }
    }

Truth JSON format (fixtures/truth.json): per bin, {"parts": [{"canonical", "category",
"qty", optional "hidden_spec"}]}. A part with "hidden_spec" is one a photo cannot fully
resolve; the pipeline must set needs_reshoot=true on it.

Metric definitions (see DECISIONS.md):
- precision            = matched predicted instances / all predicted instances
- recall               = matched predicted instances / all truth instances
- recall_high          = non-hidden-spec truth instances matched by confidence=="high"
                         predictions / all non-hidden-spec truth instances (the KICKOFF
                         "recall on high confidence" gate). hidden_spec parts are excluded
                         from both sides: they are unresolvable by design and are scored by
                         the needs_reshoot metric instead — counting them here would reward
                         false high confidence on unresolvable parts.
- lookalike confusions = per bin and configured pair (A,B): predicted B (unmatched by a
                         real B in truth) while truth contains A, or vice versa
- needs_reshoot        = a hidden_spec truth part is correct iff it matched >=1 prediction
                         and every matching prediction has needs_reshoot=true; unmatched
                         hidden_spec parts count as incorrect

Thresholds (KICKOFF): precision >= 0.95, recall_high >= 0.85, confusions == 0,
needs_reshoot correct on every hidden_spec case. --strict exits 1 when any fails.

Every run appends a row to evals/log.md unless --no-log. NEVER point this tool at
fixtures/holdout/.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
DEFAULT_LOG = REPO / "evals" / "log.md"


def fixtures_dir() -> Path:
    """Fixture photos/truth live in the private partspile-fixtures repo.

    Resolution: $PARTS_PILE_FIXTURES_DIR > a partspile-fixtures clone next to
    this repo > this repo's own fixtures/ (bring-your-own, per fixtures/README.md).
    """
    env = os.environ.get("PARTS_PILE_FIXTURES_DIR")
    if env:
        return Path(env).expanduser()
    sibling = REPO.parent / "partspile-fixtures" / "fixtures"
    if (sibling / "truth.json").exists():
        return sibling
    return REPO / "fixtures"

THRESHOLDS = {"precision": 0.95, "recall_high": 0.85}

# Legitimate synonyms only (normalized alt -> normalized canonical). Never add an alias
# that would paper over a real confusion (especially the lookalike breakout pair).
ALIASES: dict[str, str] = {
    # buzzer type is a hidden spec in the fixture set; any buzzer naming matches
    "passive buzzer": "buzzer",
    "active buzzer": "buzzer",
    "piezo buzzer": "buzzer",
    "buzzer 12mm": "buzzer",
}

# hidden_spec truth parts are, by definition, unresolvable from the bin photo (the truth
# name comes from Ben's out-of-band close-ups). They match by name when the model does
# resolve them, but an unmatched hidden_spec part also matches any leftover same-bin
# prediction that sets needs_reshoot=true — counting the part and admitting uncertainty
# is the correct behavior and must not be penalized. See DECISIONS.md #26/#29.

# Unit-ish tokens carry no identity (voltage/current/size descriptors) — ignored in
# token matching so "28BYJ-48" matches "28BYJ-48 5V".
UNIT_TOKEN_RE = re.compile(r"^\d+(?:\.\d+)?(?:v|a|ma|mah|wh|w|mm|cm|ohm|k|uf|nf|pf)$")


def match_tokens(name: str) -> frozenset[str]:
    return frozenset(t for t in canon_key(name).split() if not UNIT_TOKEN_RE.match(t))


def _specific(token: str) -> bool:
    """A token that pins down identity: has a digit and enough length (esp32, dwm3001cdk,
    852030) — 'v1'/'x2'/'023' alone don't qualify."""
    return len(token) >= 4 and any(c.isdigit() for c in token)


def _root(token: str) -> str:
    """Strip a trailing alpha suffix so part-code variants share a root: 103040PL ->
    103040, 2N2222A -> 2N2222. Tokens ending in a digit (esp32, esp32s3) are unchanged,
    so different chip generations can never collapse together."""
    return re.sub(r"[a-z]+$", "", token)


def _specific_overlap(t: frozenset[str], p: frozenset[str]) -> set[str]:
    """Shared identity-token roots, tolerant of trailing-letter suffix variants."""
    troots = {_root(x) for x in t if _specific(x)}
    proots = {_root(x) for x in p if _specific(x)}
    return {r for r in troots & proots if len(r) >= 4}


def names_match(truth_name: str, pred_name: str) -> bool:
    """Exact normalized match, or token containment / strong specific-token overlap.

    Deliberately conservative: lookalike designations (KY-023 vs KY-040, GY-521 vs
    GY-273) differ in their digit tokens, so they can never fuzzy-match.
    """
    if canon_key(truth_name) == canon_key(pred_name):
        return True
    t, p = match_tokens(truth_name), match_tokens(pred_name)
    if not t or not p:
        return False
    small, large = (t, p) if len(t) <= len(p) else (p, t)
    if small <= large and (small == t or len(small) >= 2 or any(_specific(x) for x in small)):
        return True
    shared = _specific_overlap(t, p)
    # two shared identity tokens, or one long unambiguous part-code root (2n2222,
    # dw3000-class; esp32's 5-char root deliberately does NOT qualify alone)
    if len(shared) >= 2 or any(len(r) >= 6 for r in shared):
        return True
    # a long, exactly-shared digit run (>=5 digits) is a part code: 103040 == 103040PL
    t_runs = {r for x in t for r in re.findall(r"\d{5,}", x)}
    p_runs = {r for x in p for r in re.findall(r"\d{5,}", x)}
    if t_runs & p_runs:
        return True
    return False


def normalize(name: str) -> str:
    """Case-, whitespace-, separator-, punctuation-, and dot-insensitive canonical key
    (dots are removed, not split: V10.4.6 == V1046; brackets/commas act as spaces)."""
    return re.sub(r"[\s\-_/()\[\],+~*]+", " ", name.strip().lower().replace(".", "")).strip()


def canon_key(name: str) -> str:
    n = normalize(name)
    return ALIASES.get(n, n)


def _qty(part: dict) -> int:
    q = part.get("qty", 1)
    return int(q) if q else 1


def match_bin(truth_parts: list[dict], pred_parts: list[dict]) -> dict:
    """Instance-level matching of predictions to truth within one bin.

    Pass 1 matches by name (exact canonical first, then the conservative fuzzy rules in
    names_match). Pass 2 lets still-unmatched hidden_spec truth parts consume leftover
    needs_reshoot predictions regardless of name (see module notes). Returns per-bin
    tallies, per-truth-part match records, and unmatched prediction keys (for lookalike
    confusion detection).
    """
    records = [{"truth": t, "matched": 0, "matched_high": 0, "matching_preds": []}
               for t in truth_parts]
    tally = {
        "truth_total": sum(_qty(t) for t in truth_parts),
        "pred_total": 0,
        "matched": 0,
        "truth_records": records,
        "unmatched_pred_keys": set(),
        "truth_keys": {canon_key(t["canonical"]) for t in truth_parts},
    }

    pred_leftovers = []
    for p in pred_parts:
        pred_name = p.get("canonical", "")
        pq = _qty(p)
        tally["pred_total"] += pq
        left = pq
        # exact-canonical candidates first so fuzzy never steals an exact slot
        candidates = sorted(
            (rec for rec in records if names_match(rec["truth"]["canonical"], pred_name)),
            key=lambda rec: canon_key(rec["truth"]["canonical"]) != canon_key(pred_name),
        )
        for rec in candidates:
            if left == 0:
                break
            cap = _qty(rec["truth"]) - rec["matched"]
            take = min(cap, left)
            if take > 0:
                rec["matched"] += take
                if p.get("confidence") == "high":
                    rec["matched_high"] += take
                rec["matching_preds"].append(p)
                left -= take
        tally["matched"] += pq - left
        if left > 0:
            pred_leftovers.append({"part": p, "left": left, "key": canon_key(pred_name)})

    # Wildcard pass: hidden_spec truth parts consume leftover needs_reshoot predictions.
    for rec in records:
        if not rec["truth"].get("hidden_spec"):
            continue
        need = _qty(rec["truth"]) - rec["matched"]
        for lo in pred_leftovers:
            if need == 0:
                break
            if lo["left"] > 0 and lo["part"].get("needs_reshoot"):
                take = min(lo["left"], need)
                lo["left"] -= take
                rec["matched"] += take
                rec["matching_preds"].append(lo["part"])
                tally["matched"] += take
                need -= take

    tally["unmatched_pred_keys"] = {lo["key"] for lo in pred_leftovers if lo["left"] > 0}
    return tally


def count_confusions(bin_tallies: dict[str, dict], lookalike_pairs: list[tuple[str, str]]) -> list[str]:
    """A confusion: in a bin, a lookalike twin was predicted (and not accounted for by
    real truth of that twin) while the other twin is present in truth."""
    events = []
    pairs = [(canon_key(a), canon_key(b)) for a, b in lookalike_pairs]
    for bin_id, t in bin_tallies.items():
        for a, b in pairs:
            for wrong, right in ((a, b), (b, a)):
                if wrong in t["unmatched_pred_keys"] and right in t["truth_keys"] and wrong not in t["truth_keys"]:
                    events.append(f"{bin_id}: predicted '{wrong}' where truth has '{right}'")
    return events


def score(truth: dict, predictions: dict, lookalike_pairs: list[tuple[str, str]]) -> dict:
    bin_tallies = {}
    totals = {"truth": 0, "pred": 0, "matched": 0,
              "truth_resolvable": 0, "matched_high_resolvable": 0}
    reshoot = {"total": 0, "correct": 0, "failures": []}

    for bin_id, tdata in truth.items():
        pred_parts = predictions.get(bin_id, {}).get("parts", [])
        t = match_bin(tdata.get("parts", []), pred_parts)
        bin_tallies[bin_id] = t
        totals["truth"] += t["truth_total"]
        totals["pred"] += t["pred_total"]
        totals["matched"] += t["matched"]
        for rec in t["truth_records"]:
            if not rec["truth"].get("hidden_spec"):
                totals["truth_resolvable"] += _qty(rec["truth"])
                totals["matched_high_resolvable"] += rec["matched_high"]
            if rec["truth"].get("hidden_spec"):
                reshoot["total"] += 1
                preds = rec["matching_preds"]
                ok = bool(preds) and all(p.get("needs_reshoot") for p in preds)
                if ok:
                    reshoot["correct"] += 1
                else:
                    why = "unmatched" if not preds else "matched but needs_reshoot not set"
                    reshoot["failures"].append(f"{bin_id}: {rec['truth']['canonical']} ({why})")

    extra_pred_bins = set(predictions) - set(truth)
    for bin_id in sorted(extra_pred_bins):
        for p in predictions[bin_id].get("parts", []):
            totals["pred"] += _qty(p)

    confusions = count_confusions(bin_tallies, lookalike_pairs)
    precision = totals["matched"] / totals["pred"] if totals["pred"] else 0.0
    recall = totals["matched"] / totals["truth"] if totals["truth"] else 0.0
    recall_high = (totals["matched_high_resolvable"] / totals["truth_resolvable"]
                   if totals["truth_resolvable"] else 1.0)

    passed = (
        precision >= THRESHOLDS["precision"]
        and recall_high >= THRESHOLDS["recall_high"]
        and not confusions
        and reshoot["correct"] == reshoot["total"]
    )
    return {
        "precision": precision,
        "recall": recall,
        "recall_high": recall_high,
        "confusions": confusions,
        "reshoot": reshoot,
        "totals": totals,
        "passed": passed,
        "extra_pred_bins": sorted(extra_pred_bins),
    }


def next_iteration(log_path: Path) -> int:
    if not log_path.exists():
        return 1
    rows = [
        ln for ln in log_path.read_text().splitlines()
        if ln.startswith("|") and not ln.startswith("| #") and not set(ln) <= {"|", "-", " "}
    ]
    return len(rows) + 1


def append_log(log_path: Path, meta: dict, result: dict, notes: str) -> int:
    n = next_iteration(log_path)
    r = result
    row = (
        f"| {n} | {datetime.date.today().isoformat()} | {meta.get('prompt_version', '?')} "
        f"| {meta.get('provider', '?')} | {meta.get('model', '?')} "
        f"| {r['precision']:.3f} | {r['recall_high']:.3f} | {len(r['confusions'])} "
        f"| {r['reshoot']['correct']}/{r['reshoot']['total']} | {notes} |"
    )
    with log_path.open("a") as f:
        f.write(row + "\n")
    return n


def parse_pairs(values: list[str]) -> list[tuple[str, str]]:
    pairs = []
    for v in values:
        if "::" not in v:
            raise SystemExit(f"--lookalikes expects 'A::B', got: {v}")
        a, b = v.split("::", 1)
        pairs.append((a, b))
    return pairs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-json", type=Path, help="Predictions JSON (see module docstring)")
    ap.add_argument("--run", action="store_true", help="Run the live pipeline over --photos and score it")
    ap.add_argument("--photos", type=Path, default=None,
                    help="Photo dir (default: <fixtures>/photos, see fixtures_dir())")
    ap.add_argument("--workers", type=int, default=3, help="--run only: concurrent bins")
    ap.add_argument("--provider", help="--run only: override PARTS_PILE_PROVIDER")
    ap.add_argument("--model", help="--run only: override PARTS_PILE_MODEL")
    ap.add_argument("--prompt-version", help="--run only: override prompt version")
    ap.add_argument("--glossary", type=Path,
                    help="--run only: JSON list of {canonical,name,category} to inject "
                         "(second-encounter eval mode; omit for first-encounter)")
    ap.add_argument("--truth", type=Path, default=None,
                    help="Truth JSON (default: <fixtures>/truth.json)")
    ap.add_argument("--lookalikes", action="append", default=[], metavar="A::B",
                    help="Lookalike pair to police (repeatable)")
    ap.add_argument("--notes", default="")
    ap.add_argument("--no-log", action="store_true", help="Skip appending to evals/log.md")
    ap.add_argument("--log-path", type=Path, default=DEFAULT_LOG)
    ap.add_argument("--strict", action="store_true", help="Exit 1 if thresholds not met")
    args = ap.parse_args(argv)

    fx = fixtures_dir()
    if args.truth is None:
        args.truth = fx / "truth.json"
    if args.photos is None:
        args.photos = fx / "photos"

    if "holdout" in str(args.truth) or "holdout" in str(args.photos):
        raise SystemExit("Refusing to eval against the holdout split (KICKOFF rule).")

    if not args.truth.exists():
        raise SystemExit(
            f"Truth file not found: {args.truth}\n"
            "No fixtures available. Either set PARTS_PILE_FIXTURES_DIR, clone the\n"
            "private partspile-fixtures repo next to this one, or supply your own\n"
            "fixtures/photos + fixtures/truth.json per fixtures/README.md.\n"
            "Zero-fixture smoke test of the scorer:\n"
            "  python eval.py --from-json evals/samples/demo_pass.json "
            "--truth evals/samples/demo_truth.json --no-log")

    if args.run:
        from partspile.config import Config
        from partspile.pipeline import run_all

        cfg = Config()
        if args.provider:
            cfg.provider = args.provider
        if args.model:
            cfg.model = args.model
        if args.prompt_version:
            cfg.prompt_version = args.prompt_version
        glossary_text = ""
        if args.glossary:
            from partspile.glossary import build_glossary_text
            glossary_text = build_glossary_text(json.loads(args.glossary.read_text()))
        data = run_all(cfg, args.photos, out_dir=REPO / "evals" / "runs",
                       workers=args.workers, glossary_text=glossary_text)
    elif args.from_json:
        data = json.loads(args.from_json.read_text())
    else:
        ap.error("Pass --run (live pipeline) or --from-json (saved predictions)")
    meta = data.get("meta", {})
    truth = json.loads(args.truth.read_text())
    result = score(truth, data.get("bins", {}), parse_pairs(args.lookalikes))

    r = result
    print(f"precision:    {r['precision']:.3f}  (threshold {THRESHOLDS['precision']})")
    print(f"recall:       {r['recall']:.3f}")
    print(f"recall_high:  {r['recall_high']:.3f}  (threshold {THRESHOLDS['recall_high']})")
    print(f"lookalike confusions: {len(r['confusions'])} (threshold 0)")
    for c in r["confusions"]:
        print(f"  CONFUSION {c}")
    print(f"needs_reshoot: {r['reshoot']['correct']}/{r['reshoot']['total']} hidden-spec cases correct")
    for fmsg in r["reshoot"]["failures"]:
        print(f"  RESHOOT-MISS {fmsg}")
    if r["extra_pred_bins"]:
        print(f"note: predictions include bins absent from truth: {', '.join(r['extra_pred_bins'])}")
    print("RESULT:", "PASS" if r["passed"] else "FAIL")

    if not args.no_log:
        n = append_log(args.log_path, meta, result, args.notes)
        print(f"logged as iteration {n} -> {args.log_path}")

    return 0 if (r["passed"] or not args.strict) else 1


if __name__ == "__main__":
    sys.exit(main())
