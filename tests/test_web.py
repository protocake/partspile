"""Web app tests: worker disabled, provider never called."""

import importlib
import os
import tempfile
import unittest
from pathlib import Path

os.environ["PARTS_PILE_WORKER"] = "0"


class WebTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["PARTS_PILE_DB_PATH"] = str(Path(self.tmp.name) / "t.sqlite3")
        os.environ["PARTS_PILE_PHOTO_DIR"] = str(Path(self.tmp.name) / "photos")
        import partspile.web.app as appmod
        importlib.reload(appmod)
        self.appmod = appmod
        from fastapi.testclient import TestClient
        self.client = TestClient(appmod.app)

    def tearDown(self):
        if self.appmod.db:
            self.appmod.db.close()
        self.tmp.cleanup()

    def test_root_is_browse(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Do I already have this", r.text)
        self.assertIn("SCAN WITH YOUR PHONE", r.text)

    def test_capture_page_serves(self):
        r = self.client.get("/capture")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Take photo", r.text)
        self.assertIn("manifest.json", r.text)

    def test_manifest(self):
        r = self.client.get("/manifest.json")
        self.assertEqual(r.json()["name"], "Parts Pile")

    def test_submit_bin_enqueues_and_returns_immediately(self):
        r = self.client.post(
            "/api/scans",
            data={"label": "test box", "location": "desk"},
            files=[("photos", ("a.jpg", b"fakejpeg1", "image/jpeg")),
                   ("photos", ("b.jpg", b"fakejpeg2", "image/jpeg"))])
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "queued")
        q = self.client.get("/api/queue").json()
        self.assertEqual(len(q), 1)
        self.assertEqual(q[0]["status"], "queued")
        self.assertEqual(q[0]["location"], "desk")
        saved = list((Path(self.tmp.name) / "photos").iterdir())
        self.assertEqual(len(saved), 2)

    def test_retry_route(self):
        r = self.client.post("/api/scans", data={},
                             files=[("photos", ("a.jpg", b"x", "image/jpeg"))])
        run_id = r.json()["run_id"]
        d = self.appmod.get_db()
        d.claim_next_run()
        d.fail_run(run_id, "boom")
        self.client.post(f"/api/runs/{run_id}/retry")
        self.assertEqual(self.client.get("/api/queue").json()[0]["status"], "queued")

    def _seed_reviewable_bin(self):
        r = self.client.post("/api/scans", data={"label": "rev box"},
                             files=[("photos", ("a.jpg", b"x", "image/jpeg"))])
        body = r.json()
        d = self.appmod.get_db()
        d.claim_next_run()
        d.finish_run(body["run_id"], "{}", [
            {"name": "DHT11 module", "canonical": "KY-015", "category": "sensor",
             "confidence": "high"},
            {"name": "mystery", "canonical": "unknown blob", "category": "other",
             "confidence": "low", "needs_reshoot": True, "reshoot_reason": "blurry"}])
        return body["scan_id"]

    def test_review_flow_accept_edit_undetermined(self):
        scan_id = self._seed_reviewable_bin()
        data = self.client.get("/api/review").json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["scan_id"], scan_id)
        self.assertEqual(len(data[0]["parts"]), 2)
        p1, p2 = data[0]["parts"]
        self.client.post(f"/api/parts/{p1['id']}/accept")
        self.client.post(f"/api/parts/{p2['id']}/undetermined")
        self.client.patch(f"/api/parts/{p2['id']}",
                          json={"canonical": "unknown wrapped part", "qty": 1})
        self.assertEqual(self.client.get("/api/review").json(), [])
        d = self.appmod.get_db()
        row = d.search_parts("wrapped")[0]
        self.assertEqual(row["resolution"], "undetermined")

    def test_reshoot_appends_and_requeues(self):
        scan_id = self._seed_reviewable_bin()
        r = self.client.post(f"/api/scans/{scan_id}/photos",
                             files=[("photos", ("more.jpg", b"y", "image/jpeg"))])
        self.assertEqual(r.json()["status"], "queued")
        d = self.appmod.get_db()
        self.assertEqual(len(d.photos_for_scan(scan_id)), 2)
        self.assertEqual(d.photos_for_scan(scan_id)[1]["shot_index"], 2)
        q = [row for row in self.client.get("/api/queue").json()
             if row["status"] == "queued"]
        self.assertEqual(len(q), 1)

    def test_review_page_serves(self):
        r = self.client.get("/review")
        self.assertIn("Review", r.text)

    def test_browse_search_and_csv(self):
        scan_id = self._seed_reviewable_bin()
        for p in self.client.get("/api/review").json()[0]["parts"]:
            self.client.post(f"/api/parts/{p['id']}/accept")
        rows = self.client.get("/api/parts", params={"q": "KY-015"}).json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["scan_label"], "rev box")
        self.assertTrue(rows[0]["photo"].startswith(f"scan{scan_id}_shot"))
        self.assertEqual(
            len(self.client.get("/api/parts", params={"category": "sensor"}).json()), 1)
        csv_text = self.client.get("/api/export.csv").text
        self.assertIn("KY-015", csv_text)
        self.assertIn("canonical,name,category", csv_text)

    def test_browse_page_serves(self):
        self.assertIn("Do I already have this", self.client.get("/browse").text)

    def test_scan_location_editable(self):
        scan_id = self._seed_reviewable_bin()
        r = self.client.patch(f"/api/scans/{scan_id}", json={"location": "attic shelf"})
        self.assertEqual(r.status_code, 200)
        pid = self.client.get("/api/review").json()[0]["parts"][0]["id"]
        ctx = self.client.get(f"/api/parts/{pid}/context").json()
        self.assertEqual(ctx["scan"]["location"], "attic shelf")
        self.assertIn("id", ctx["scan"])
        self.assertEqual(self.client.patch("/api/scans/999999",
                                           json={"location": "x"}).status_code, 404)

    def test_photo_feedback_surfaces_retake_on_queue(self):
        import json as _json
        r = self.client.post("/api/scans", data={"location": "desk"},
                             files=[("photos", ("a.jpg", b"x", "image/jpeg"))])
        run_id = r.json()["run_id"]
        d = self.appmod.get_db()
        d.claim_next_run()
        d.finish_run(run_id, "{}", [], _json.dumps(
            [{"shot": "scan1_shot1.jpg", "verdict": "retake",
              "reason": "too blurry - hold the phone steadier"}]))
        row = self.client.get("/api/queue").json()[0]
        self.assertTrue(row["retake"])
        self.assertIn("blurry", row["retake_reason"])

    def test_queue_reports_pending_review_counts(self):
        self._seed_reviewable_bin()
        row = self.client.get("/api/queue").json()[0]
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["pending"], 2)
        for p in self.client.get("/api/review").json()[0]["parts"]:
            self.client.post(f"/api/parts/{p['id']}/accept")
        self.assertEqual(self.client.get("/api/queue").json()[0]["pending"], 0)

    def test_add_part_photo_and_pool(self):
        self._seed_reviewable_bin()
        pid = self.client.get("/api/review").json()[0]["parts"][0]["id"]
        r = self.client.post(f"/api/parts/{pid}/photos",
                             files=[("photos", ("closeup.jpg", b"xx", "image/jpeg"))])
        self.assertEqual(len(r.json()["added"]), 1)
        ctx = self.client.get(f"/api/parts/{pid}/context").json()
        kinds = [ph["kind"] for ph in ctx["photos"]]
        self.assertEqual(kinds.count("captured"), 2)  # scan shot + attached
        # identification pool must exclude part-attached photos
        d = self.appmod.get_db()
        scan_id = ctx["part"]["scan_id"]
        self.assertEqual(len(d.photos_for_scan(scan_id, captured_only=True)), 1)

    def test_delete_photo_clears_key_and_file(self):
        self._seed_reviewable_bin()
        pid = self.client.get("/api/review").json()[0]["parts"][0]["id"]
        self.client.post(f"/api/parts/{pid}/photos",
                         files=[("photos", ("x.jpg", b"xx", "image/jpeg"))])
        ctx = self.client.get(f"/api/parts/{pid}/context").json()
        attached = next(ph for ph in ctx["photos"] if not ph["shared"])
        self.client.patch(f"/api/parts/{pid}", json={"key_photo_id": attached["id"]})
        r = self.client.delete(f"/api/photos/{attached['id']}")
        self.assertEqual(r.status_code, 200)
        ctx2 = self.client.get(f"/api/parts/{pid}/context").json()
        self.assertNotIn(attached["id"], [ph["id"] for ph in ctx2["photos"]])
        self.assertIsNone(ctx2["part"]["key_photo_id"])  # star cleared
        self.assertEqual(self.client.delete("/api/photos/999999").status_code, 404)

    def test_suggest_image_requires_spec_url(self):
        self._seed_reviewable_bin()
        pid = self.client.get("/api/review").json()[0]["parts"][0]["id"]
        self.assertEqual(
            self.client.post(f"/api/parts/{pid}/suggest-image").status_code, 400)
        self.assertEqual(
            self.client.post(f"/api/parts/{pid}/adopt-suggestion").status_code, 404)

    def test_cutout_endpoint_falls_back_gracefully(self):
        # fake photo bytes can't be segmented -> 404, client falls back to crop
        self._seed_reviewable_bin()
        pid = self.client.get("/api/review").json()[0]["parts"][0]["id"]
        self.assertEqual(self.client.get(f"/api/cutouts/{pid}.png").status_code, 404)
        self.assertEqual(self.client.get("/api/cutouts/999999.png").status_code, 404)

    def test_lan_url_and_qr_fallback(self):
        j = self.client.get("/api/lan-url").json()
        self.assertTrue(j["url"].startswith("http://"))
        r = self.client.get("/api/qr.svg")
        self.assertIn(r.status_code, (200, 404))  # 404 until qrcode lib approved

    def test_part_context_for_modal(self):
        self._seed_reviewable_bin()
        pid = self.client.get("/api/review").json()[0]["parts"][0]["id"]
        ctx = self.client.get(f"/api/parts/{pid}/context").json()
        self.assertIn("id", ctx["scan"])
        self.assertEqual(len(ctx["photos"]), 1)
        self.assertIn("prompt", ctx["provenance"])
        self.assertEqual(self.client.get("/api/parts/999999/context").status_code, 404)

    def test_photo_route_traversal_blocked(self):
        r = self.client.get("/photos/../../etc/passwd")
        self.assertIn(r.status_code, (404, 422))


if __name__ == "__main__":
    unittest.main()
