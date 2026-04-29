"""Unified import: scrape → download photos → wipe DB → seed.

Usage (from project root):
    python scripts/import_all.py

Flags:
    --skip-scrape       Skip scraping (use existing JSON files)
    --skip-download     Skip photo download (use URLs already in JSON)
    --skip-seed         Skip DB wipe + seed
    --skip-wipe         Seed without wiping existing data first

Steps:
    1. Scrape boats          → scripts/data/products.json
    2. Scrape accessories    → scripts/data/accessories.json
    3. Download boat photos  → uploads/boats/,   updates products.json
    4. Download acc. photos  → uploads/accessories/, updates accessories.json
    5. Wipe boats + accessories from DB
    6. Seed DB from JSON files
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Optional

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPTS_DIR / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
ACCESSORIES_FILE = DATA_DIR / "accessories.json"
BOATS_UPLOAD_DIR = ROOT / "uploads" / "boats"
ACC_UPLOAD_DIR = ROOT / "uploads" / "accessories"

sys.path.insert(0, str(ROOT))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}


# ── step 1: scrape boats ───────────────────────────────────────────────────────

def step_scrape_boats() -> None:
    print("\n[STEP 1/4] Scraping boat listings …")
    import scripts.scrape as _s
    session = __import__("requests").Session()
    session.headers.update(HEADERS)
    try:
        urls = _s._get_product_urls()
    except Exception as e:
        print(f"  ERROR fetching URLs: {e}")
        sys.exit(1)

    products: list[dict[str, Any]] = []
    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url}")
        p = _s.scrape_product_page(url, session)
        if p:
            slug = url.rstrip("/").split("/product-page/")[-1]
            p["slug"] = slug
            products.append(p)
            print(f"    '{p['title']}' ${p['price_usd']:,}")
        else:
            print("    → no data")
        time.sleep(0.8)

    products = _s._deduplicate(products)
    for p in products:
        p.pop("_source", None)
    products.sort(key=lambda x: -(x.get("price_usd") or 0))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCTS_FILE.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {len(products)} boats saved to {PRODUCTS_FILE}")


# ── step 2: scrape accessories ─────────────────────────────────────────────────

def step_scrape_accessories() -> None:
    print("\n[STEP 2/4] Scraping accessories …")
    import scripts.scrape_accessories as _sa
    items = _sa.scrape()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACCESSORIES_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {len(items)} accessories saved to {ACCESSORIES_FILE}")


# ── shared download helpers ────────────────────────────────────────────────────

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


def _download_to(url: str, dest_dir: Path, subpath: str) -> Optional[str]:
    """Download url to dest_dir. Returns local path like /uploads/<subpath>/xxx.jpg or None."""
    if not url:
        return None
    if url.startswith("/uploads/"):
        return url
    dest_dir.mkdir(parents=True, exist_ok=True)
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
    fpath = dest_dir / fname
    if not fpath.exists():
        fpath.write_bytes(content)
    return f"/uploads/{subpath}/{fname}"


# ── step 3: download boat photos ───────────────────────────────────────────────

def _extract_photos_from_page(page) -> list[str]:
    seen: set[str] = set()
    photos: list[str] = []
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
    if not photos:
        for img in page.query_selector_all("img[src*='wixstatic.com/media']"):
            src = img.get_attribute("src") or ""
            url = _clean_wix_url(src)
            if url and url not in seen:
                seen.add(url)
                photos.append(url)
    return photos


def step_download_boat_photos() -> None:
    print("\n[STEP 3/4] Downloading boat gallery photos …")
    if not PRODUCTS_FILE.exists():
        print("  SKIP: products.json not found")
        return

    from playwright.sync_api import sync_playwright

    products = json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    base_url = "https://www.mgnauticabroker.com/product-page"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_context(user_agent=HEADERS["User-Agent"]).new_page()

        for i, product in enumerate(products, 1):
            slug = product["slug"]
            print(f"  [{i}/{len(products)}] {slug}")
            try:
                page.goto(f"{base_url}/{slug}", wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                time.sleep(1)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
                wix_urls = _extract_photos_from_page(page)
            except Exception as e:
                print(f"    scrape ERROR: {e}")
                wix_urls = []

            if not wix_urls and product.get("primary_photo_url"):
                wix_urls = [_normalize_wix_url(product["primary_photo_url"])]

            local_paths: list[str] = []
            for url in wix_urls:
                local = _download_to(url, BOATS_UPLOAD_DIR, "boats")
                if local:
                    local_paths.append(local)

            if local_paths:
                product["photos"] = local_paths
                product["primary_photo_url"] = local_paths[0]
                print(f"    → {len(local_paths)} photos")
            else:
                print("    → no photos")
            time.sleep(0.3)

        browser.close()

    PRODUCTS_FILE.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → products.json updated")


# ── step 4: download accessory photos ─────────────────────────────────────────

def step_download_accessory_photos() -> None:
    print("\n[STEP 4/4] Downloading accessory photos …")
    if not ACCESSORIES_FILE.exists():
        print("  SKIP: accessories.json not found")
        return

    items = json.loads(ACCESSORIES_FILE.read_text(encoding="utf-8"))
    downloaded = 0
    for item in items:
        url = item.get("photo_url") or ""
        if not url or url.startswith("/uploads/"):
            continue
        local = _download_to(url, ACC_UPLOAD_DIR, "accessories")
        if local:
            item["photo_url"] = local
            downloaded += 1
            print(f"    {item['slug']} → {local}")
        else:
            print(f"    {item['slug']} → FAIL")

    ACCESSORIES_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {downloaded} accessory photos downloaded, accessories.json updated")


# ── step 5: wipe + seed ───────────────────────────────────────────────────────

def step_wipe_and_seed(skip_wipe: bool) -> None:  # noqa: C901
    from app import app
    from app.factory import db
    from app.models import Accessory, Boat, BoatPhoto, BoatSpecs

    with app.app_context():
        db.create_all()

        if not skip_wipe:
            print("\n[WIPE] Deleting all boats and accessories …")
            db.session.query(BoatPhoto).delete()
            db.session.query(BoatSpecs).delete()
            db.session.query(Boat).delete()
            db.session.query(Accessory).delete()
            db.session.commit()
            print("  → done")

        print("\n[SEED] Inserting from JSON …")
        import scripts.seed as _seed
        boats, accessories, admin_created = _seed.seed()
        total_boats = db.session.query(Boat).count()
        total_accessories = db.session.query(Accessory).count()

    print(
        f"  → {boats} boats inserted ({total_boats} total), "
        f"{accessories} accessories inserted ({total_accessories} total)"
    )
    if admin_created:
        print(
            f"  Admin email:    {os.environ.get('ADMIN_EMAIL', 'admin@mgnautica.local')}\n"
            f"  Admin password: {os.environ.get('ADMIN_PASSWORD', 'changeme-admin')}"
        )


# ── step 6: associate ML listings ─────────────────────────────────────────────

def _fetch_listings(site: str) -> list[dict]:
    """Fetch ML listings: authenticated API first, Playwright public page as fallback."""
    import scripts.scan_meli as _scan

    try:
        listings = _scan.fetch_via_api(site)
        print(f"  {len(listings)} items via API (including paused)")
        return listings
    except Exception as exc:
        print(f"  API unavailable ({exc})")

    SELLER_IDS = {"MLA": 431049699, "MLU": None}
    seller_id = SELLER_IDS.get(site)
    if not seller_id:
        print(f"  No fallback seller ID for {site} — skipping")
        return []
    try:
        from playwright.sync_api import sync_playwright as _  # noqa
    except ImportError:
        print("  playwright not installed — skipping ML association")
        return []

    listings = _scan.fetch_via_playwright(seller_id)
    print(f"  {len(listings)} public active listings (no credentials)")
    return listings


def step_associate_meli(site: str, min_score: float) -> None:
    """Fetch all ML listings and associate them with boats in the DB.

    Creates its own Flask app context so it can be called standalone.
    Testable: patch _fetch_listings and/or the app to inject a test context.
    """
    print(f"\n[STEP 6] Associating MercadoLibre {site} listings …")
    import scripts.scan_meli as _scan
    from app import app
    from app.factory import db
    from app.models import Boat

    listings = _fetch_listings(site)
    if not listings:
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache = DATA_DIR / f"meli_listings_{site.lower()}.json"
    cache.write_text(json.dumps(listings, ensure_ascii=False, indent=2), encoding="utf-8")

    with app.app_context():
        boats = db.session.query(Boat).all()
        matches = _scan.match_listings(listings, boats)
        _scan.print_report(matches, min_score)
        updated = _scan.apply_matches(matches, min_score)
        print(f"  → {updated} boats linked to {site}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape + download + wipe + seed + associate ML in one shot."
    )
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping (use existing JSON)")
    parser.add_argument("--skip-download", action="store_true", help="Skip photo downloads")
    parser.add_argument("--skip-seed", action="store_true", help="Skip DB wipe + seed")
    parser.add_argument("--skip-wipe", action="store_true", help="Seed without wiping first")
    parser.add_argument("--skip-meli", action="store_true", help="Skip ML association step")
    parser.add_argument("--meli-site", default="MLA", choices=["MLA", "MLU"],
                        help="ML site for association (default: MLA)")
    parser.add_argument("--meli-min-score", type=float, default=0.50, metavar="FLOAT",
                        help="Min match score for ML auto-link (default: 0.50)")
    args = parser.parse_args()

    if not args.skip_scrape:
        step_scrape_boats()
        step_scrape_accessories()
    else:
        print("\n[STEP 1-2] Scraping skipped — using existing JSON")

    if not args.skip_download:
        try:
            from playwright.sync_api import sync_playwright as _  # noqa: F401
        except ImportError:
            print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
            return 1
        step_download_boat_photos()
        step_download_accessory_photos()
    else:
        print("\n[STEP 3-4] Photo download skipped")

    if not args.skip_seed:
        step_wipe_and_seed(skip_wipe=args.skip_wipe)
    else:
        print("\n[SEED] Skipped")

    if not args.skip_meli:
        step_associate_meli(args.meli_site, args.meli_min_score)
    else:
        print("\n[STEP 6] ML association skipped")

    print("\nAll done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
