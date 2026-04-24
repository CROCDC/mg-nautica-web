"""Scrape all gallery photos for each boat and download them to uploads/.

Steps:
  1. Visit each product page with Playwright and extract all gallery image URLs.
  2. Download each image to uploads/boats/ (skips already-downloaded files).
  3. Update products.json with local /uploads/boats/... paths.

Usage (from project root):
    python scripts/scrape_and_download_photos.py

Requires: playwright  (pip install playwright && playwright install chromium)
Updates:  scripts/data/products.json
"""

import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "products.json"
UPLOAD_DIR = Path(__file__).parent.parent / "uploads" / "boats"
BASE_URL = "https://www.mgnauticabroker.com/product-page"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _normalize_wix_url(url: str) -> str:
    if not url or "static.wixstatic.com/media/" not in url:
        return url
    if "/v1/" in url:
        return url
    parts = url.split("/media/", 1)
    filename = parts[1].split("/")[0]
    return f"{parts[0]}/media/{filename}/v1/fit/w_1920,h_1280,al_c,q_90,enc_auto/{filename}"


def _clean_wix_url(url: str) -> str:
    url = re.sub(r"/v1/fill/[^/]*/", "/", url)
    url = url.split("?")[0]
    return _normalize_wix_url(url)


def _ext_from_content_type(ctype: str, url: str) -> str:
    if "jpeg" in ctype or "jpg" in ctype:
        return ".jpg"
    if "png" in ctype:
        return ".png"
    if "webp" in ctype:
        return ".webp"
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if ext in url.lower():
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def _download(url: str) -> str | None:
    """Download url to UPLOAD_DIR. Returns local path like /uploads/boats/xxx.jpg or None."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            ctype = resp.headers.get("Content-Type", "").lower()
    except Exception as e:
        print(f"    FAIL {url[:70]}: {e}")
        return None

    ext = _ext_from_content_type(ctype, url)
    digest = hashlib.sha1(content).hexdigest()[:16]
    fname = f"{digest}{ext}"
    fpath = UPLOAD_DIR / fname
    if not fpath.exists():
        fpath.write_bytes(content)
    return f"/uploads/boats/{fname}"


def _extract_photos_from_page(page) -> list[str]:
    """Return ordered unique Wix photo URLs from the current Playwright page."""
    seen: set[str] = set()
    photos: list[str] = []

    # Primary: wow-image data-image-info (most reliable on Wix)
    for el in page.query_selector_all("wow-image[data-image-info]"):
        try:
            info = json.loads(el.get_attribute("data-image-info") or "")
            uri = info.get("imageData", {}).get("uri", "")
            if uri:
                url = f"https://static.wixstatic.com/media/{uri}/v1/fit/w_1920,h_1280,al_c,q_90,enc_auto/{uri}"
                if url not in seen:
                    seen.add(url)
                    photos.append(url)
        except (json.JSONDecodeError, AttributeError):
            pass

    # Fallback: img tags
    if not photos:
        for img in page.query_selector_all("img[src*='wixstatic.com/media']"):
            src = img.get_attribute("src") or ""
            url = _clean_wix_url(src)
            if url and url not in seen:
                seen.add(url)
                photos.append(url)

    return photos


def scrape_and_download() -> None:
    from playwright.sync_api import sync_playwright

    products = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    total = len(products)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_context(user_agent=HEADERS["User-Agent"]).new_page()

        for i, product in enumerate(products, 1):
            slug = product["slug"]
            print(f"[{i}/{total}] {slug}")

            # 1. Scrape gallery URLs
            try:
                page.goto(f"{BASE_URL}/{slug}", wait_until="networkidle", timeout=30000)
                page.wait_for_selector(
                    "wow-image[data-image-info], img[src*='wixstatic.com/media']",
                    timeout=10000,
                )
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                time.sleep(0.8)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(0.8)
                wix_urls = _extract_photos_from_page(page)
            except Exception as e:
                print(f"  scrape ERROR: {e}")
                wix_urls = []

            if not wix_urls and product.get("primary_photo_url"):
                wix_urls = [_normalize_wix_url(product["primary_photo_url"])]

            # 2. Download each photo
            local_paths: list[str] = []
            for url in wix_urls:
                local = _download(url)
                if local:
                    local_paths.append(local)

            if local_paths:
                product["photos"] = local_paths
                product["primary_photo_url"] = local_paths[0]
                print(f"  → {len(local_paths)} photos downloaded")
            else:
                print(f"  → no photos")

            time.sleep(0.3)

        browser.close()

    # 3. Save updated JSON
    DATA_FILE.write_text(json.dumps(products, ensure_ascii=False, indent=2))
    print(f"\nDone. {DATA_FILE} updated.")


if __name__ == "__main__":
    scrape_and_download()
