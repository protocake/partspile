"""Suggest a catalog image from a part's product page — stdlib only.

Fetches the page (size/time capped), extracts the most likely product image
(og:image → twitter:image → link rel=image_src → first sizeable <img>), downloads
it (capped, content-type checked) to the given path. The human confirms in the UI
before it is registered; nothing here writes to the database.
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path

PAGE_CAP = 2 * 1024 * 1024
IMAGE_CAP = 8 * 1024 * 1024
UA = {"User-Agent": "Mozilla/5.0 (PartsPile inventory; personal use)"}


def _get(url: str, cap: int) -> tuple[bytes, str]:
    if not url.startswith(("http://", "https://")):
        raise ValueError("only http(s) URLs")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read(cap + 1), resp.headers.get("Content-Type", "")


def find_image_url(html: str, base_url: str) -> str | None:
    """Best product-image URL in the page, absolute; None if nothing plausible."""
    patterns = [
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return urllib.parse.urljoin(base_url, m.group(1))
    # fallback: first <img> that looks like content (skip icons/sprites/pixels)
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
        src = m.group(1)
        low = src.lower()
        if any(x in low for x in ("logo", "icon", "sprite", "pixel", "badge", ".svg")):
            continue
        if low.startswith("data:"):
            continue
        return urllib.parse.urljoin(base_url, src)
    return None


def suggest_image_for_url(page_url: str, dest: Path) -> str | None:
    """Download the page's best image to dest; returns its source URL or None."""
    try:
        body, _ = _get(page_url, PAGE_CAP)
        img_url = find_image_url(body[:PAGE_CAP].decode("utf-8", "replace"), page_url)
        if not img_url:
            return None
        data, ctype = _get(img_url, IMAGE_CAP)
        if len(data) > IMAGE_CAP:
            return None
        if not (ctype.startswith("image/") or data[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0",
                                                           b"\xff\xd8\xff\xe1", b"RIFF")):
            return None
        dest.write_bytes(data)
        return img_url
    except Exception:
        return None
