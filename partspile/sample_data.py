"""First-run sample inventory (Ben's onboarding design, 2026-09-13).

A brand-new database gets a handful of accepted demo parts with drawn SVG
illustrations, so the first thing a user sees is the app partially populated —
not an empty grid asking for credentials. Samples are tagged bin='samples' and
removable in one call; seeding never runs again once the DB has any real scan.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent / "sample_photos"
SAMPLE_BIN = "samples"

# Real photos from Wikimedia Commons (see sample_photos/SOURCES.md for credits —
# each image keeps its own CC license; Ben's design call 2026-09-27: photos, not
# illustrations).
SAMPLE_PARTS = [
    dict(img="uno.jpg", name="Arduino Uno R3", canonical="UNO R3",
         category="board", interface="uart", voltage="5V"),
    dict(img="hcsr04.jpg", name="Ultrasonic distance sensor", canonical="HC-SR04",
         category="sensor", interface="digital", voltage="5V"),
    dict(img="stepper.jpg", name="Geared stepper motor with ULN2003 driver",
         canonical="28BYJ-48", category="actuator", interface="digital", voltage="5V"),
    dict(img="relay.jpg", name="1-channel 5V relay module", canonical="SRD-05VDC-SL-C",
         category="actuator", interface="digital", voltage="5V"),
    dict(img="battery.jpg", name="18650 Li-ion cell 3000mAh", canonical="18650",
         category="power", interface="unknown", voltage="3.7V"),
]


def seed_samples(db, photo_dir: Path) -> bool:
    """Seed once, only into a truly virgin DB. Returns True if seeded."""
    row = db.conn.execute("SELECT (SELECT COUNT(*) FROM parts) + "
                          "(SELECT COUNT(*) FROM scans) AS n").fetchone()
    if row["n"]:
        return False
    photo_dir.mkdir(parents=True, exist_ok=True)
    scan_id = db.create_scan("Sample data", location="")
    for p in SAMPLE_PARTS:
        dest = photo_dir / f"sample_{p['img']}"
        shutil.copyfile(SAMPLES_DIR / p["img"], dest)
        cur = db.conn.execute(
            "INSERT INTO parts (scan_id, source_run_id, name, canonical, category, "
            " interface, voltage, qty, confidence, needs_reshoot, reshoot_reason, "
            " bbox_json, status, bin, notes) "
            "VALUES (?, NULL, ?, ?, ?, ?, ?, 1, 'high', 0, '', ?, 'accepted', ?, ?)",
            (scan_id, p["name"], p["canonical"], p["category"], p["interface"],
             p["voltage"], json.dumps([]), SAMPLE_BIN,
             "Sample part — remove any time from the welcome note or Browse."))
        part_id = cur.lastrowid
        photo_id = db.add_part_photo(part_id, dest.name, kind="catalog")
        # direct SQL: update_part() would stamp status='edited'
        db.conn.execute("UPDATE parts SET key_photo_id = ? WHERE id = ?",
                        (photo_id, part_id))
    db.conn.commit()
    return True


def clear_samples(db, photo_dir: Path) -> int:
    """Delete the seeded sample parts (and their SVGs). Returns parts removed."""
    rows = db.conn.execute(
        "SELECT id FROM parts WHERE bin = ? AND source_run_id IS NULL",
        (SAMPLE_BIN,)).fetchall()
    for r in rows:
        for ph in db.photos_for_part(r["id"]):
            (photo_dir / Path(ph["path"]).name).unlink(missing_ok=True)
        db.conn.execute("UPDATE parts SET key_photo_id = NULL WHERE id = ?", (r["id"],))
        db.conn.execute("DELETE FROM photos WHERE part_id = ?", (r["id"],))
        db.conn.execute("DELETE FROM parts WHERE id = ?", (r["id"],))
    db.conn.execute("DELETE FROM scans WHERE label = 'Sample data' AND id NOT IN "
                    "(SELECT DISTINCT scan_id FROM parts WHERE scan_id IS NOT NULL)")
    db.conn.commit()
    return len(rows)
