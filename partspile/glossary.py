"""House glossary: inject human-vetted inventory knowledge into identification
prompts (Layer 3 of the novel-parts strategy, DECISIONS #31).

Every part the human has accepted or corrected becomes a hint for future scans, so
a part taught once (e.g. "NULLLAB PM11") is recognized on every later encounter —
local learning without retraining, for every provider. The fixture EVAL never
injects this by default (it measures first-encounter behavior); eval.py --glossary
enables the second-encounter mode explicitly.
"""

from __future__ import annotations


def build_glossary_text(rows) -> str:
    """Prompt section from glossary rows ({canonical, name, category}); '' if none."""
    entries = []
    for r in rows:
        canonical = (r["canonical"] or "").strip()
        if not canonical or canonical.lower().startswith("unidentified"):
            continue
        name = (r["name"] or "").strip()
        desc = f" — {name}" if name and name.lower() != canonical.lower() else ""
        entries.append(f"- {canonical}{desc} ({r['category']})")
    if not entries:
        return ""
    return (
        "\n\nKNOWN PARTS ALREADY IN THIS INVENTORY (a human verified these names; "
        "if a photo shows the same product, use exactly this canonical — but never "
        "force a match onto a different-looking part):\n" + "\n".join(entries) + "\n")
