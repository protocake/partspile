"""Cut-out segmentation tests: synthetic pixel buffers, no sips, no real photos."""

import struct
import unittest

from partspile.thumbs import parse_bmp, refine_box


def make_rgb(w, h, bg=(40, 40, 42), rect=None, color=(220, 60, 60)):
    """Row-major RGB buffer: background + optional bright rectangle (px coords)."""
    buf = bytearray(bg * (w * h))
    if rect:
        x0, y0, x1, y1 = rect
        for y in range(y0, y1):
            for x in range(x0, x1):
                p = (y * w + x) * 3
                buf[p:p + 3] = bytes(color)
    return bytes(buf)


def make_bmp(w, h, pixels_rgb):
    """Minimal bottom-up 24-bit BMP from a top-down RGB buffer."""
    row_bytes = (w * 3 + 3) & ~3
    body = bytearray()
    for y in range(h - 1, -1, -1):
        row = bytearray()
        for x in range(w):
            p = (y * w + x) * 3
            r, g, b = pixels_rgb[p], pixels_rgb[p + 1], pixels_rgb[p + 2]
            row += bytes((b, g, r))
        row += b"\x00" * (row_bytes - len(row))
        body += row
    off = 14 + 40
    header = b"BM" + struct.pack("<IHHI", off + len(body), 0, 0, off)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(body), 0, 0, 0, 0)
    return bytes(header + info + body)


class ParseBmpTest(unittest.TestCase):
    def test_roundtrip(self):
        rgb = make_rgb(10, 6, rect=(2, 1, 5, 4))
        out, w, h = parse_bmp(make_bmp(10, 6, rgb))
        self.assertEqual((w, h), (10, 6))
        self.assertEqual(out, rgb)


class RefineBoxTest(unittest.TestCase):
    def test_finds_object_without_seed(self):
        w, h = 120, 90
        rgb = make_rgb(w, h, rect=(30, 20, 80, 60))
        box = refine_box(rgb, w, h, None)
        self.assertIsNotNone(box)
        # tight around the rect (30/120=0.25 .. 80/120=0.667) with small padding
        self.assertAlmostEqual(box["x"], 0.25, delta=0.06)
        self.assertAlmostEqual(box["x"] + box["w"], 0.667, delta=0.06)
        self.assertAlmostEqual(box["y"], 0.222, delta=0.06)
        self.assertAlmostEqual(box["y"] + box["h"], 0.667, delta=0.06)

    def test_seed_region_excludes_other_objects(self):
        w, h = 200, 100
        rgb = bytearray(make_rgb(w, h, rect=(10, 10, 40, 40)))
        # second object far right; seed points at the left one
        for y in range(20, 50):
            for x in range(160, 190):
                p = (y * w + x) * 3
                rgb[p:p + 3] = bytes((80, 200, 90))
        seed = {"x": 0.05, "y": 0.1, "w": 0.15, "h": 0.3}
        box = refine_box(bytes(rgb), w, h, seed)
        self.assertIsNotNone(box)
        self.assertLess(box["x"] + box["w"], 0.6)  # never swallowed the right object

    def test_blank_photo_returns_none(self):
        w, h = 80, 80
        self.assertIsNone(refine_box(make_rgb(w, h), w, h, None))

    def test_degenerate_seed_falls_back_to_full_frame(self):
        w, h = 120, 90
        rgb = make_rgb(w, h, rect=(50, 40, 90, 70))
        box = refine_box(rgb, w, h, {"x": 0.9, "y": 0.9, "w": 0.0, "h": 0.0})
        self.assertIsNotNone(box)


if __name__ == "__main__":
    unittest.main()
