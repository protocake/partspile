"""Automated part cut-out: refine a loose model bbox into a tight object box.

Vision models identify parts well but localize them poorly, so thumbnails cropped
straight to model bboxes often show desk instead of part (Ben, 2026-09-07). This
module segments the actual object: downsample the photo with `sips` (macOS builtin
— zero dependencies; an open-source Pillow path can come later), parse the BMP in
pure Python, mask pixels that differ from the border background, and return the
tight normalized bounding box of the foreground. The model bbox (grown) seeds the
search region; callers fall back to the model box, then to the full photo.
"""

from __future__ import annotations

import functools
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

from .paths import data_dir

CUTOUT_SRC = Path(__file__).resolve().parent / "native" / "cutout.swift"
CUTOUT_BIN = data_dir() / "bin" / "cutout"
CUTOUT_DIR = data_dir() / "cutouts"

MAX_DIM = 360          # analysis resolution — plenty for a thumbnail box
GROW = 0.8             # how much to grow the model bbox each side (fraction of its size)
COLOR_THRESHOLD = 60   # sum |dR|+|dG|+|dB| distance from background to count as object
MIN_RUN_FRAC = 0.02    # a row/col needs >2% object pixels to count (speckle rejection)
PAD = 0.08             # padding added around the tight box (fraction of box size)


def photo_to_rgb(path: Path) -> tuple[bytes, int, int]:
    """Downsampled RGB pixel buffer (row-major, top-down) via sips → BMP."""
    with tempfile.TemporaryDirectory() as td:
        bmp = Path(td) / "x.bmp"
        subprocess.run(
            ["sips", "-Z", str(MAX_DIM), "-s", "format", "bmp", str(path),
             "--out", str(bmp)],
            capture_output=True, check=True, timeout=30)
        return parse_bmp(bmp.read_bytes())


def parse_bmp(data: bytes) -> tuple[bytes, int, int]:
    """Minimal 24/32-bit uncompressed BMP parser → (rgb bytes top-down, w, h)."""
    if data[:2] != b"BM":
        raise ValueError("not a BMP")
    off = struct.unpack_from("<I", data, 10)[0]
    w = struct.unpack_from("<i", data, 18)[0]
    h_raw = struct.unpack_from("<i", data, 22)[0]
    bpp = struct.unpack_from("<H", data, 28)[0]
    comp = struct.unpack_from("<I", data, 30)[0]
    if bpp not in (24, 32) or comp not in (0, 3):
        raise ValueError(f"unsupported BMP (bpp={bpp}, comp={comp})")
    h = abs(h_raw)
    bottom_up = h_raw > 0
    step = bpp // 8
    row_bytes = (w * step + 3) & ~3
    out = bytearray(w * h * 3)
    for y in range(h):
        src_y = (h - 1 - y) if bottom_up else y
        row = off + src_y * row_bytes
        o = y * w * 3
        for x in range(w):
            p = row + x * step
            # BMP stores BGR(A)
            out[o] = data[p + 2]
            out[o + 1] = data[p + 1]
            out[o + 2] = data[p]
            o += 3
    return bytes(out), w, h


def refine_box(rgb: bytes, w: int, h: int,
               seed: dict | None) -> dict | None:
    """Tight normalized {x,y,w,h} of the object inside (grown) seed region, or None."""
    if seed and seed.get("w", 0) > 0 and seed.get("h", 0) > 0:
        gx = seed["w"] * GROW
        gy = seed["h"] * GROW
        x0 = max(0, int((seed["x"] - gx) * w))
        y0 = max(0, int((seed["y"] - gy) * h))
        x1 = min(w, int((seed["x"] + seed["w"] + gx) * w))
        y1 = min(h, int((seed["y"] + seed["h"] + gy) * h))
    else:
        x0, y0, x1, y1 = 0, 0, w, h
    if x1 - x0 < 8 or y1 - y0 < 8:
        x0, y0, x1, y1 = 0, 0, w, h

    # Background = median color of the region border strips.
    border: list[tuple[int, int, int]] = []
    strip = max(2, (y1 - y0) // 20)
    for y in list(range(y0, min(y0 + strip, y1))) + list(range(max(y1 - strip, y0), y1)):
        for x in range(x0, x1, 3):
            p = (y * w + x) * 3
            border.append((rgb[p], rgb[p + 1], rgb[p + 2]))
    for x in list(range(x0, min(x0 + strip, x1))) + list(range(max(x1 - strip, x0), x1)):
        for y in range(y0, y1, 3):
            p = (y * w + x) * 3
            border.append((rgb[p], rgb[p + 1], rgb[p + 2]))
    if not border:
        return None
    border.sort()
    bg = border[len(border) // 2]

    rw = x1 - x0
    col_hits = [0] * rw
    row_hits = [0] * (y1 - y0)
    total = 0
    for yi, y in enumerate(range(y0, y1)):
        base = y * w * 3
        for xi, x in enumerate(range(x0, x1)):
            p = base + x * 3
            d = (abs(rgb[p] - bg[0]) + abs(rgb[p + 1] - bg[1])
                 + abs(rgb[p + 2] - bg[2]))
            if d > COLOR_THRESHOLD:
                col_hits[xi] += 1
                row_hits[yi] += 1
                total += 1
    if total < 0.005 * rw * (y1 - y0):
        return None  # nothing clearly distinct from background

    min_col = max(2, int(MIN_RUN_FRAC * (y1 - y0)))
    min_row = max(2, int(MIN_RUN_FRAC * rw))
    xs = [i for i, v in enumerate(col_hits) if v >= min_col]
    ys = [i for i, v in enumerate(row_hits) if v >= min_row]
    if not xs or not ys:
        return None
    bx0, bx1 = x0 + xs[0], x0 + xs[-1] + 1
    by0, by1 = y0 + ys[0], y0 + ys[-1] + 1
    bw, bh = (bx1 - bx0) / w, (by1 - by0) / h
    box = {
        "x": max(0.0, bx0 / w - bw * PAD),
        "y": max(0.0, by0 / h - bh * PAD),
        "w": min(1.0, bw * (1 + 2 * PAD)),
        "h": min(1.0, bh * (1 + 2 * PAD)),
    }
    box["w"] = min(box["w"], 1.0 - box["x"])
    box["h"] = min(box["h"], 1.0 - box["y"])
    return box


@functools.lru_cache(maxsize=512)
def _cached(photo: str, mtime: float, seed_key: tuple | None) -> dict | None:
    seed = None
    if seed_key:
        seed = {"x": seed_key[0], "y": seed_key[1], "w": seed_key[2], "h": seed_key[3]}
    try:
        rgb, w, h = photo_to_rgb(Path(photo))
        return refine_box(rgb, w, h, seed)
    except Exception:
        return None


def ensure_cutout_binary() -> Path | None:
    """Locate or build the Apple subject-lifting helper (macOS only).

    A brew-precompiled `partspile-cutout` on PATH wins; otherwise compile the
    packaged Swift source on first use into the user data dir."""
    pre = shutil.which("partspile-cutout")
    if pre:
        return Path(pre)
    try:
        if CUTOUT_BIN.exists() and CUTOUT_BIN.stat().st_mtime >= CUTOUT_SRC.stat().st_mtime:
            return CUTOUT_BIN
        if not shutil.which("swiftc") or not CUTOUT_SRC.exists():
            return CUTOUT_BIN if CUTOUT_BIN.exists() else None
        CUTOUT_BIN.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(["swiftc", "-O", str(CUTOUT_SRC), "-o", str(CUTOUT_BIN)],
                              capture_output=True, timeout=300)
        return CUTOUT_BIN if proc.returncode == 0 else None
    except Exception:
        return None


_cutout_misses: set[tuple] = set()


def cutout_for(part_id: int, photo: Path, seed: dict | None) -> Path | None:
    """Transparent cut-out PNG for a part (cached on disk), or None → caller falls
    back to the rectangle crop. Crops to the refined box first so the subject the
    segmenter lifts is THIS part, not a neighbor."""
    try:
        mtime = int(photo.stat().st_mtime)
    except OSError:
        return None
    out = CUTOUT_DIR / f"part{part_id}_{mtime}.png"
    if out.exists():
        return out
    miss_key = (part_id, mtime)
    if miss_key in _cutout_misses:
        return None
    binary = ensure_cutout_binary()
    if binary is None:
        return None
    box = refined_box_for(photo, seed)
    args = [str(binary), str(photo), str(out)]
    if box:
        args += [f"{box['x']:.4f}", f"{box['y']:.4f}",
                 f"{box['w']:.4f}", f"{box['h']:.4f}"]
    CUTOUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(args, capture_output=True, timeout=60)
        if proc.returncode == 0 and out.exists():
            return out
    except Exception:
        pass
    _cutout_misses.add(miss_key)
    return None


def refined_box_for(photo: Path, seed: dict | None) -> dict | None:
    """Public entry: cached per (photo, mtime, seed)."""
    key = None
    if seed and seed.get("w") and seed.get("h"):
        key = (round(seed["x"], 3), round(seed["y"], 3),
               round(seed["w"], 3), round(seed["h"], 3))
    try:
        mtime = photo.stat().st_mtime
    except OSError:
        return None
    return _cached(str(photo), mtime, key)
