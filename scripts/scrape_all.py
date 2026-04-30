"""Scrape mgnauticabroker.com and download all photos locally.

Run this on your local machine when listings change.

Usage (from project root):
    python scripts/scrape_all.py

Steps:
    1. Scrape boats       → scripts/data/products.json
    2. Scrape accessories → scripts/data/accessories.json
    3. Download boat photos      → uploads/boats/
    4. Download accessory photos → uploads/accessories/

Requires: pip install requests beautifulsoup4 lxml playwright
          playwright install chromium
"""

import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPTS_DIR / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
ACCESSORIES_FILE = DATA_DIR / "accessories.json"
BOATS_UPLOAD_DIR = ROOT / "uploads" / "boats"
ACC_UPLOAD_DIR = ROOT / "uploads" / "accessories"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

BOATS_BASE_URL = "https://www.mgnauticabroker.com"
ACCESSORIES_URL = "https://www.mgnauticabroker.com/home-1-1-1"
ARS_USD_RATE = 1200


# ── boat scraping ──────────────────────────────────────────────────────────────

def _extract_prices_from_text(text: str) -> list[int]:
    prices = []
    for m in re.finditer(r'\b(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+[.,]\d+|\d+)\b', text):
        raw = m.group(1)
        digits_only = re.sub(r"[.,]", "", raw)
        if len(digits_only) < 3:
            continue
        if "," in raw and "." in raw:
            last_comma = raw.rfind(",")
            last_dot = raw.rfind(".")
            if last_comma > last_dot:
                val = raw.replace(".", "").replace(",", ".")
            else:
                val = raw.replace(",", "")
        elif "," in raw:
            parts = raw.split(",")
            val = parts[0].replace(".", "") if len(parts) == 2 and len(parts[-1]) <= 2 else raw.replace(",", "")
        elif "." in raw:
            parts = raw.split(".")
            val = parts[0] if len(parts) == 2 and len(parts[-1]) <= 2 else raw.replace(".", "")
        else:
            val = raw
        try:
            prices.append(int(float(val)))
        except ValueError:
            pass
    return prices


def _parse_price(raw: str) -> Optional[int]:
    prices = _extract_prices_from_text(raw)
    return prices[0] if prices else None


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _find_nested(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = _find_nested(v, key)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_nested(item, key)
            if result is not None:
                return result
    return None


def _extract_wix_product(soup) -> Optional[dict[str, Any]]:
    for script in soup.find_all("script"):
        text = script.string or ""
        m = re.search(
            r'"product"\s*:\s*(\{[^<]{200,}?\})\s*,\s*"(?:relatedProducts|currency)',
            text, re.DOTALL,
        )
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});\s*</script>', text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                product = _find_nested(data, "product")
                if product and "name" in product:
                    return product
            except (json.JSONDecodeError, TypeError):
                pass
        m = re.search(
            r'\{"id"\s*:\s*"[0-9a-f\-]{36}"\s*,\s*"name"\s*:\s*"(.+?)"\s*,\s*"description"\s*:',
            text, re.DOTALL,
        )
        if m:
            start = text.rfind('{"id"', 0, m.start() + 10)
            if start == -1:
                start = m.start()
            depth = 0
            end = start
            for i, ch in enumerate(text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            try:
                return json.loads(text[start:end])
            except (json.JSONDecodeError, ValueError):
                pass
    return None


def _extract_from_page_html(url: str, soup) -> Optional[dict[str, Any]]:
    title = None
    for sel in ["h1", '[data-hook="product-title"]', ".wixui-rich-text h1"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            title = el.get_text(strip=True)
            break

    price_usd = None
    prev_price_usd = None
    for el in soup.select('[data-hook="product-price"], [data-hook="formatted-price-range"], .price'):
        text = el.get_text(strip=True)
        prices = _extract_prices_from_text(text)
        if len(prices) >= 2:
            prev_price_usd = prices[0]
            price_usd = prices[1]
        elif len(prices) == 1:
            price_usd = prices[0]
        if price_usd:
            break

    if prev_price_usd is None:
        for el in soup.select('[data-hook="formatted-compare-price"], .compare-price, .strike'):
            prev_price_usd = _parse_price(el.get_text(strip=True))
            if prev_price_usd:
                break

    description = ""
    for sel in ['[data-hook="product-description"]', ".wixui-rich-text", '[data-testid="product-description"]']:
        el = soup.select_one(sel)
        if el:
            description = el.get_text(separator="\n", strip=True)
            break

    photo_url = None
    for img in soup.find_all("img"):
        src = img.get("src", "") or img.get("data-src", "")
        if "wixstatic.com/media/" in src:
            photo_url = re.sub(r"/v1/fill/[^/]*/", "/", src).split("?")[0]
            break

    slug = url.rstrip("/").split("/")[-1]
    if not title or not price_usd:
        return None
    return {"slug": slug, "title": title, "description": description,
            "price_usd": price_usd, "previous_price_usd": prev_price_usd,
            "primary_photo_url": photo_url, "_source": "html"}


def _extract_from_json_ld(soup, url: str) -> Optional[dict[str, Any]]:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list):
            data = next((d for d in data if d.get("@type") == "Product"), None)
        if not data or data.get("@type") != "Product":
            continue
        name = data.get("name", "")
        description = data.get("description", "")
        offers = data.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price_raw = offers.get("price") or data.get("price")
        price_usd = _parse_price(str(price_raw)) if price_raw else None
        image = data.get("image")
        if isinstance(image, list):
            image = image[0]
        photo_url = image if isinstance(image, str) else None
        slug = url.rstrip("/").split("/")[-1]
        if name and price_usd:
            return {"slug": slug, "title": name, "description": description,
                    "price_usd": price_usd, "previous_price_usd": None,
                    "primary_photo_url": photo_url, "_source": "json-ld"}
    return None


def _extract_from_wix_json(item: dict) -> Optional[dict[str, Any]]:
    name = item.get("name") or item.get("title", "")
    if not name:
        return None
    description = item.get("description", "") or ""
    if isinstance(description, list):
        description = "\n".join(s.get("description", "") for s in description if s.get("description"))
    description = re.sub(r"<[^>]+>", " ", description).strip()
    price_data = item.get("priceData") or {}
    price = price_data.get("price") or item.get("price")
    compare_price = price_data.get("comparePrice") or item.get("comparePrice")
    price_usd = _parse_price(str(price)) if price else None
    prev_price_usd = _parse_price(str(compare_price)) if compare_price else None
    if not price_usd:
        return None
    slug = item.get("slug") or item.get("handle") or _slugify(name)
    photo_url = None
    media = item.get("media") or item.get("mediaItems") or []
    if isinstance(media, dict):
        items_list = media.get("items") or []
        main = media.get("mainMedia", {}).get("image", {})
        media = items_list or ([main] if main else [])
    if isinstance(media, list) and media:
        first = media[0]
        if isinstance(first, dict):
            src = (first.get("src") or first.get("url") or
                   first.get("image", {}).get("url", "") or first.get("image", {}).get("src", ""))
            if src and "wixstatic.com" in src:
                photo_url = src.split("?")[0].split("/v1/fill/")[0]
    return {"slug": slug, "title": name, "description": description,
            "price_usd": price_usd,
            "previous_price_usd": prev_price_usd if prev_price_usd and prev_price_usd != price_usd else None,
            "primary_photo_url": photo_url, "_source": "wix-json"}


def _scrape_product_page(url: str, session) -> Optional[dict[str, Any]]:
    from bs4 import BeautifulSoup
    try:
        r = session.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        if r.status_code == 404:
            return None
        r.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None
    soup = BeautifulSoup(r.text, "lxml")
    product = _extract_from_json_ld(soup, url)
    if product:
        return product
    wix_product = _extract_wix_product(soup)
    if wix_product:
        result = _extract_from_wix_json(wix_product)
        if result:
            return result
    return _extract_from_page_html(url, soup)


def _slug_matches_title(slug: str, title: str) -> bool:
    """Return False when the URL slug has no words in common with the product title.
    Catches Wix pages where an old URL now serves a completely different product."""
    slug_words = set(re.split(r"[-\s]+", slug.lower()))
    title_words = set(re.split(r"[-\s]+", _slugify(title).lower()))
    significant = {w for w in title_words if len(w) > 3}
    return bool(slug_words & significant)


def _deduplicate(products: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for p in products:
        slug = p.get("slug", "")
        if not slug:
            continue
        if slug not in seen or len(p.get("description", "")) > len(seen[slug].get("description", "")):
            seen[slug] = p
    return list(seen.values())


def scrape_boats() -> list[str]:
    """Returns list of URLs that failed requests-based scraping (Playwright fallback needed)."""
    import requests
    print("\n[1/4] Scraping boat listings …")
    session = requests.Session()
    session.headers.update(HEADERS)

    from bs4 import BeautifulSoup
    r = requests.get(f"{BOATS_BASE_URL}/store-products-sitemap.xml", headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml-xml")
    urls = [loc.get_text(strip=True) for loc in soup.find_all("loc")
            if "/product-page/" in loc.get_text(strip=True)]
    print(f"  Found {len(urls)} product URLs")

    products: list[dict[str, Any]] = []
    failed_urls: list[str] = []
    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url}")
        p = None
        for attempt in range(1, 4):
            p = _scrape_product_page(url, session)
            if p:
                break
            if attempt < 3:
                wait = attempt * 3
                print(f"    → retry {attempt}/2 in {wait}s …")
                time.sleep(wait)
        if p:
            url_slug = url.rstrip("/").split("/product-page/")[-1]
            if _slug_matches_title(url_slug, p.get("title", "")):
                p["slug"] = url_slug
            else:
                p["slug"] = _slugify(p["title"])
                print(f"    → URL slug mismatch ({url_slug!r}), using title slug: {p['slug']!r}")
            products.append(p)
            print(f"    '{p['title']}' ${p['price_usd']:,}")
        else:
            print("    → no data after 3 attempts, queued for Playwright retry")
            failed_urls.append(url)
        time.sleep(0.8)

    products = _deduplicate(products)
    for p in products:
        p.pop("_source", None)
    products.sort(key=lambda x: -(x.get("price_usd") or 0))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCTS_FILE.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {len(products)} boats saved to {PRODUCTS_FILE}")
    return failed_urls


# ── accessory scraping ─────────────────────────────────────────────────────────

def _acc_slugify(text: str) -> str:
    text = text.lower().strip()
    for src, dst in [("áàä","a"),("éèë","e"),("íìï","i"),("óòö","o"),("úùü","u"),("ñ","n")]:
        for c in src:
            text = text.replace(c, dst)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _acc_parse_price(price_text: str) -> tuple[int, str]:
    t = re.sub(r"^desde\s+", "", price_text.strip(), flags=re.IGNORECASE)
    if t.upper().startswith("ARG"):
        digits = re.sub(r"[^0-9]", "", t)
        return (round(int(digits) / ARS_USD_RATE), "ARS") if digits else (0, "ARS")
    t = re.sub(r"U\$S|US\$|USD", "", t, flags=re.IGNORECASE).strip()
    if "." in t and "," in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "." in t and all(len(p) == 3 for p in t.split(".")[1:]):
        t = t.replace(".", "")
    elif "," in t:
        t = t.replace(",", "")
    try:
        return (int(float(t.strip())), "USD")
    except ValueError:
        return (0, "USD")


def _classify_accessory_category(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["bota", "boot"]):
        return "boots"
    if any(k in t for k in ["chubasquero", "ropa", "chaleco", "indumentaria", "campera"]):
        return "clothing"
    return "onboard"


def scrape_accessories() -> None:
    from playwright.sync_api import sync_playwright
    print("\n[2/4] Scraping accessories …")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(ACCESSORIES_URL, wait_until="domcontentloaded", timeout=60000)
        for _ in range(6):
            page.evaluate("window.scrollBy(0, 600)")
            page.wait_for_timeout(500)
        page.wait_for_timeout(3000)

        raw_items = page.evaluate("""
            () => {
                const results = [];
                for (const h5 of document.querySelectorAll('h5')) {
                    const title = h5.textContent.trim();
                    if (!title) continue;
                    let container = h5.parentElement;
                    for (let i = 0; i < 5; i++) {
                        if (!container || !container.parentElement) break;
                        if (container.querySelector('img') && container.querySelector('p')) break;
                        container = container.parentElement;
                    }
                    if (!container) continue;
                    let photoUrl = '';
                    const wowImg = container.querySelector('wow-image');
                    if (wowImg) {
                        try {
                            const info = JSON.parse(wowImg.getAttribute('data-image-info') || '{}');
                            photoUrl = (info.imageData && info.imageData.url) ? info.imageData.url : '';
                        } catch(e) {}
                    }
                    if (!photoUrl) {
                        const img = container.querySelector('img');
                        if (img) photoUrl = img.src || '';
                    }
                    const paras = Array.from(container.querySelectorAll('p'))
                        .map(p => p.textContent.trim()).filter(t => t.length > 0);
                    const waLink = container.querySelector('a[href*="wa.me"]');
                    results.push({ title, paras, photoUrl, whatsapp: waLink ? waLink.href : '' });
                }
                return results;
            }
        """)
        browser.close()

    items = []
    for item in raw_items:
        title = item["title"]
        paras = item["paras"]
        price_usd, currency = _acc_parse_price(paras[0] if paras else "")
        location = paras[1] if len(paras) > 1 else ""
        description_parts = []
        if currency == "ARS":
            description_parts.append(f"Precio en pesos argentinos: {paras[0]}.")
        if location:
            description_parts.append(f"Ubicación: {location}.")
        if item["whatsapp"]:
            description_parts.append(f"Contacto: {item['whatsapp']}")
        items.append({
            "slug": _acc_slugify(title),
            "title": title,
            "description": " ".join(description_parts),
            "category": _classify_accessory_category(title),
            "price_usd": price_usd,
            "previous_price_usd": None,
            "stock": None,
            "photo_url": item["photoUrl"] or None,
            "active": True,
            "_location": location,
            "_whatsapp": item["whatsapp"],
        })

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACCESSORIES_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {len(items)} accessories saved to {ACCESSORIES_FILE}")


# ── photo download ─────────────────────────────────────────────────────────────

def _normalize_wix_url(url: str) -> str:
    if not url or "static.wixstatic.com/media/" not in url:
        return url
    if "/v1/" in url:
        return url
    parts = url.split("/media/", 1)
    filename = parts[1].split("/")[0]
    return f"{parts[0]}/media/{filename}/v1/fit/w_1920,h_1280,al_c,q_90,enc_auto/{filename}"


def _clean_wix_url(url: str) -> str:
    url = re.sub(r"/v1/fill/[^/]*/", "/", url).split("?")[0]
    return _normalize_wix_url(url)


def _download_to(url: str, dest_dir: Path, subpath: str) -> Optional[str]:
    if not url or url.startswith("/uploads/"):
        return url if url else None
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            ctype = resp.headers.get("Content-Type", "").lower()
    except Exception as e:
        print(f"    FAIL {url[:70]}: {e}")
        return None
    ext = ".jpg"
    for candidate in ("jpeg", "jpg", "png", "webp"):
        if candidate in ctype or f".{candidate}" in url.lower():
            ext = ".jpg" if candidate in ("jpeg", "jpg") else f".{candidate}"
            break
    fname = f"{hashlib.sha1(content).hexdigest()[:16]}{ext}"
    fpath = dest_dir / fname
    if not fpath.exists():
        fpath.write_bytes(content)
    return f"/uploads/{subpath}/{fname}"


def _extract_photos_playwright(page) -> list[str]:
    seen: set[str] = set()
    photos: list[str] = []
    for el in page.query_selector_all("wow-image[data-image-info]"):
        try:
            info = json.loads(el.get_attribute("data-image-info") or "")
            uri = info.get("imageData", {}).get("uri", "")
            if uri and not uri.startswith("http"):
                url = f"https://static.wixstatic.com/media/{uri}/v1/fit/w_1920,h_1280,al_c,q_90,enc_auto/{uri}"
                if url not in seen:
                    seen.add(url)
                    photos.append(url)
        except (json.JSONDecodeError, AttributeError):
            pass
    if not photos:
        for img in page.query_selector_all("img[src*='wixstatic.com/media']"):
            url = _clean_wix_url(img.get_attribute("src") or "")
            if url and url not in seen:
                seen.add(url)
                photos.append(url)
    return photos


def _extract_product_playwright(page, url: str) -> Optional[dict[str, Any]]:
    """Full product extraction from a JS-rendered Wix page."""
    title = page.evaluate("""
        () => {
            for (const sel of ['[data-hook="product-title"]', 'h1']) {
                const el = document.querySelector(sel);
                if (el && el.innerText.trim()) return el.innerText.trim();
            }
            return '';
        }
    """)
    price_text = page.evaluate("""
        () => {
            for (const sel of ['[data-hook="formatted-price-range"]', '[data-hook="product-price"]', '.price']) {
                const el = document.querySelector(sel);
                if (el && el.innerText.trim()) return el.innerText.trim();
            }
            return '';
        }
    """)
    description = page.evaluate("""
        () => {
            const el = document.querySelector('[data-hook="description"]');
            return el ? el.innerText.trim() : '';
        }
    """)
    prices = _extract_prices_from_text(price_text)
    price_usd = prices[0] if prices else None
    if not title or not price_usd:
        return None
    url_slug = url.rstrip("/").split("/product-page/")[-1]
    slug = url_slug if _slug_matches_title(url_slug, title) else _slugify(title)
    return {
        "slug": slug,
        "title": title,
        "description": description,
        "price_usd": price_usd,
        "previous_price_usd": None,
        "primary_photo_url": None,
        "_source": "playwright",
    }


def download_boat_photos(failed_urls: Optional[list[str]] = None) -> None:
    from playwright.sync_api import sync_playwright
    print("\n[3/4] Downloading boat gallery photos …")
    if not PRODUCTS_FILE.exists():
        print("  SKIP: products.json not found")
        return

    products = json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_context(user_agent=HEADERS["User-Agent"]).new_page()

        for i, product in enumerate(products, 1):
            slug = product["slug"]
            print(f"  [{i}/{len(products)}] {slug}")
            try:
                page.goto(f"{BOATS_BASE_URL}/product-page/{slug}", wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                time.sleep(1)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
                photos = _extract_photos_playwright(page)
                description = page.evaluate("""
                    () => {
                        const el = document.querySelector('[data-hook="description"]');
                        return el ? el.innerText.trim() : '';
                    }
                """)
                if description and len(description) > 20:
                    product["description"] = description
            except Exception as e:
                print(f"    scrape ERROR: {e}")
                photos = []

            if not photos and product.get("primary_photo_url"):
                photos = [_normalize_wix_url(product["primary_photo_url"])]

            local_paths = [lp for lp in (_download_to(u, BOATS_UPLOAD_DIR, "boats") for u in photos) if lp]
            if local_paths:
                product["photos"] = local_paths
                product["primary_photo_url"] = local_paths[0]
                print(f"    → {len(local_paths)} photos")
            else:
                print("    → no photos")
            time.sleep(0.3)

        # Playwright fallback for URLs that failed requests-based scraping
        if failed_urls:
            print(f"  Retrying {len(failed_urls)} failed URL(s) with Playwright …")
            for url in failed_urls:
                url_slug = url.rstrip("/").split("/product-page/")[-1]
                print(f"  [PW] {url_slug}")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(3)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    time.sleep(1)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)
                    p = _extract_product_playwright(page, url)
                    if not p:
                        print("    → no data from Playwright either")
                        continue
                    photos = _extract_photos_playwright(page)
                    if not photos and p.get("primary_photo_url"):
                        photos = [_normalize_wix_url(p["primary_photo_url"])]
                    local_paths = [lp for lp in (_download_to(u, BOATS_UPLOAD_DIR, "boats") for u in photos) if lp]
                    if local_paths:
                        p["photos"] = local_paths
                        p["primary_photo_url"] = local_paths[0]
                    p.pop("_source", None)
                    products.append(p)
                    print(f"    '{p['title']}' ${p['price_usd']:,} → {len(local_paths)} photos")
                except Exception as e:
                    print(f"    → Playwright ERROR: {e}")

        browser.close()

    # Re-deduplicate in case Playwright rescued any failed URLs
    products = _deduplicate(products)
    products.sort(key=lambda x: -(x.get("price_usd") or 0))
    PRODUCTS_FILE.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  → products.json updated")


def download_accessory_photos() -> None:
    print("\n[4/4] Downloading accessory photos …")
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
    print(f"  → {downloaded} accessory photos downloaded")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        from playwright.sync_api import sync_playwright as _  # noqa: F401
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        return 1

    failed_urls = scrape_boats()
    scrape_accessories()
    download_boat_photos(failed_urls=failed_urls)
    download_accessory_photos()
    print("\nDone. Commit scripts/data/ and uploads/ then deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
