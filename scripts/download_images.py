"""Download remote photo URLs (boats + accessories) to uploads/ and rewrite DB.

All images currently stored in the DB as https://static.wixstatic.com/... URLs
are fetched and saved under uploads/{kind}/{hash}.{ext}; the DB is updated to
point to /uploads/{kind}/{hash}.{ext} so images are served from our own server.

Idempotent: already-local URLs are skipped.

Usage (from project root):
    docker compose exec web python scripts/download_images.py
"""

import hashlib
import os
import sys
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app  # noqa: E402
from app.factory import db  # noqa: E402
from app.models import Accessory, BoatPhoto  # noqa: E402

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _ext_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"):
        if ext in path:
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def _normalize_wix_url(url: str) -> str:
    """Wix refuses raw /media/<name>/<name> URLs (403). Insert a transform path."""
    if "static.wixstatic.com/media/" not in url:
        return url
    # Already has a transform (e.g. /v1/fill/...)
    if "/v1/" in url:
        return url
    # Shape: https://.../media/<file>/<file>   →   https://.../media/<file>/v1/fit/w_1920,h_1280,al_c,q_90,enc_auto/<file>
    parts = url.split("/media/", 1)
    if len(parts) != 2:
        return url
    after = parts[1].split("/")
    if len(after) < 2:
        return url
    filename = after[0]
    return (
        f"{parts[0]}/media/{filename}"
        f"/v1/fit/w_1920,h_1280,al_c,q_90,enc_auto/{filename}"
    )


def _download(url: str, dest_dir: Path) -> Optional[str]:
    """Download url to dest_dir, return path relative to uploads root or None on failure."""
    url = _normalize_wix_url(url)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            ctype = resp.headers.get("Content-Type", "").lower()
    except Exception as e:
        print(f"    FAIL {url[:80]}: {e}")
        return None

    ext = _ext_from_url(url)
    # Detect content-type overrides
    if "jpeg" in ctype or "jpg" in ctype:
        ext = ".jpg"
    elif "png" in ctype:
        ext = ".png"
    elif "webp" in ctype:
        ext = ".webp"

    digest = hashlib.sha1(content).hexdigest()[:16]
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{digest}{ext}"
    fpath = dest_dir / fname
    if not fpath.exists():
        fpath.write_bytes(content)
    return fname


def main() -> int:
    upload_root = Path(app.config["UPLOAD_FOLDER"])
    cache: dict[str, str] = {}  # url -> new local path

    with app.app_context():
        # ── Accessories ────────────────────────────────────────────────────────
        accs = db.session.query(Accessory).all()
        acc_dir = upload_root / "accessories"
        print(f"Accessories: {len(accs)}")
        for a in accs:
            url = a.photo_url or ""
            if not url or url.startswith("/uploads/"):
                continue
            if url in cache:
                a.photo_url = cache[url]
                continue
            print(f"  {a.slug}  <-  {url[:70]}")
            fname = _download(url, acc_dir)
            if fname:
                new_path = f"/uploads/accessories/{fname}"
                a.photo_url = new_path
                cache[url] = new_path

        # ── Boat photos ────────────────────────────────────────────────────────
        photos = db.session.query(BoatPhoto).all()
        boat_dir = upload_root / "boats"
        print(f"Boat photos: {len(photos)}")
        for ph in photos:
            url = ph.url or ""
            if not url or url.startswith("/uploads/"):
                continue
            if url in cache:
                ph.url = cache[url]
                continue
            print(f"  boat#{ph.boat_id}  <-  {url[:70]}")
            fname = _download(url, boat_dir)
            if fname:
                new_path = f"/uploads/boats/{fname}"
                ph.url = new_path
                cache[url] = new_path

        db.session.commit()

    print(f"Done. {len(cache)} unique images downloaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
