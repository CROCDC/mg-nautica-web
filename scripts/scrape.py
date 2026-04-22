"""Scrape product listings from mgnauticabroker.com (Wix store).

Usage (from project root):
    python scripts/scrape.py

Writes:  scripts/data/products.json
"""
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.mgnauticabroker.com"
OUT_FILE = Path(__file__).parent / "data" / "products.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}


def _extract_prices_from_text(text: str) -> list[int]:
    """
    Extract all prices from a text that may contain European-format numbers
    like 'US$ 160.000,00' or '25.000' mixed with other text.
    Returns a list of integer prices found.
    """
    # Match European format: optional currency prefix, digits with dots/commas
    # e.g. "160.000,00" or "160.000" or "25,000.00"
    prices = []
    for m in re.finditer(r'\b(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+[.,]\d+|\d+)\b', text):
        raw = m.group(1)
        # Skip small numbers (not a price)
        digits_only = re.sub(r"[.,]", "", raw)
        if len(digits_only) < 3:
            continue
        # Parse
        if "," in raw and "." in raw:
            last_comma = raw.rfind(",")
            last_dot = raw.rfind(".")
            if last_comma > last_dot:
                # European: 160.000,00
                val = raw.replace(".", "").replace(",", ".")
            else:
                # US: 160,000.00
                val = raw.replace(",", "")
        elif "," in raw:
            parts = raw.split(",")
            if len(parts) == 2 and len(parts[-1]) <= 2:
                val = parts[0].replace(".", "")
            else:
                val = raw.replace(",", "")
        elif "." in raw:
            parts = raw.split(".")
            if len(parts) == 2 and len(parts[-1]) <= 2:
                val = parts[0]
            else:
                val = raw.replace(".", "")
        else:
            val = raw
        try:
            prices.append(int(float(val)))
        except ValueError:
            pass
    return prices


def _parse_price(raw: str) -> Optional[int]:
    """Parse the first price found in a string."""
    prices = _extract_prices_from_text(raw)
    return prices[0] if prices else None


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _get_product_urls() -> list[str]:
    """Get all product-page URLs from the Wix store products sitemap."""
    print("Fetching store products sitemap …")
    r = requests.get(
        f"{BASE_URL}/store-products-sitemap.xml", headers=HEADERS, timeout=30
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml-xml")
    urls = [
        loc.get_text(strip=True)
        for loc in soup.find_all("loc")
        if "/product-page/" in loc.get_text(strip=True)
    ]
    print(f"  Found {len(urls)} product URLs")
    return urls




def _extract_wix_product(soup: BeautifulSoup) -> Optional[dict[str, Any]]:
    """Try to extract product data from Wix embedded JSON blobs."""

    # Strategy 1: Look for window.Bolt.viewer or __VIEWER_MODEL__
    for script in soup.find_all("script"):
        text = script.string or ""

        # Wix embeds product data in various patterns. Try to find product JSON.
        # Pattern: "product":{"id":"...","name":"...","price":...}
        m = re.search(
            r'"product"\s*:\s*(\{[^<]{200,}?\})\s*,\s*"(?:relatedProducts|currency)',
            text,
            re.DOTALL,
        )
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # Pattern 2: window.__INITIAL_STATE__ or similar
        m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});\s*</script>', text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                # Traverse to find product object
                product = _find_nested(data, "product")
                if product and "name" in product:
                    return product
            except (json.JSONDecodeError, TypeError):
                pass

        # Pattern 3: applicationJson with name/price/description
        m = re.search(
            r'\{"id"\s*:\s*"[0-9a-f\-]{36}"\s*,\s*"name"\s*:\s*"(.+?)"\s*,\s*"description"\s*:',
            text,
            re.DOTALL,
        )
        if m:
            # Find the full object starting from this position
            start = text.rfind('{"id"', 0, m.start() + 10)
            if start == -1:
                start = m.start()
            # Try to parse the JSON object at this position
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


def _find_nested(obj: Any, key: str) -> Any:
    """Recursively search for a key in nested dicts/lists."""
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


def _extract_from_page_html(url: str, soup: BeautifulSoup) -> Optional[dict[str, Any]]:
    """
    Fallback: extract product info directly from rendered HTML.
    Wix renders the product title, price, description in known selectors.
    """
    # Title
    title = None
    for sel in ["h1", '[data-hook="product-title"]', ".wixui-rich-text h1"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            title = el.get_text(strip=True)
            break

    # Price — Wix renders as "$ 25.000,00" (European format) or "US$ 35,000"
    # When on sale the element text is: "US$ 160.000,00PrecioUS$ 150.000,00Precio de oferta"
    price_usd = None
    prev_price_usd = None
    for el in soup.select('[data-hook="product-price"], [data-hook="formatted-price-range"], .price'):
        text = el.get_text(strip=True)
        prices = _extract_prices_from_text(text)
        if len(prices) >= 2:
            # First is original price, second is sale price
            prev_price_usd = prices[0]
            price_usd = prices[1]
        elif len(prices) == 1:
            price_usd = prices[0]
        if price_usd:
            break

    # Standalone compare-price element (if not already found)
    if prev_price_usd is None:
        for el in soup.select('[data-hook="formatted-compare-price"], .compare-price, .strike'):
            prev_price_usd = _parse_price(el.get_text(strip=True))
            if prev_price_usd:
                break

    # Description
    description = ""
    for sel in [
        '[data-hook="product-description"]',
        ".wixui-rich-text",
        '[data-testid="product-description"]',
    ]:
        el = soup.select_one(sel)
        if el:
            description = el.get_text(separator="\n", strip=True)
            break

    # Photo — find the first wixstatic image that looks like a product image
    photo_url = None
    for img in soup.find_all("img"):
        src = img.get("src", "") or img.get("data-src", "")
        if "wixstatic.com/media/" in src:
            # Strip Wix resize transforms: keep only the base media URL
            photo_url = re.sub(r"/v1/fill/[^/]*/", "/", src).split("?")[0]
            break

    # Derive slug from URL
    slug = url.rstrip("/").split("/")[-1]

    if not title or not price_usd:
        return None

    return {
        "slug": slug,
        "title": title,
        "description": description,
        "price_usd": price_usd,
        "previous_price_usd": prev_price_usd,
        "primary_photo_url": photo_url,
        "_source": "html",
    }


def _extract_from_json_ld(soup: BeautifulSoup, url: str) -> Optional[dict[str, Any]]:
    """Extract from JSON-LD Product schema if present."""
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

        # Price
        price_usd = None
        prev_price_usd = None
        offers = data.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price_raw = offers.get("price") or data.get("price")
        if price_raw:
            price_usd = _parse_price(str(price_raw))

        # Photo
        image = data.get("image")
        if isinstance(image, list):
            image = image[0]
        photo_url = image if isinstance(image, str) else None

        slug = url.rstrip("/").split("/")[-1]

        if name and price_usd:
            return {
                "slug": slug,
                "title": name,
                "description": description,
                "price_usd": price_usd,
                "previous_price_usd": prev_price_usd,
                "primary_photo_url": photo_url,
                "_source": "json-ld",
            }
    return None


def _extract_from_wix_json(item: dict) -> Optional[dict[str, Any]]:
    """Convert a raw Wix product JSON dict to our schema."""
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
            src = (
                first.get("src") or first.get("url") or
                first.get("image", {}).get("url", "") or
                first.get("image", {}).get("src", "")
            )
            if src and "wixstatic.com" in src:
                photo_url = src.split("?")[0].split("/v1/fill/")[0]

    return {
        "slug": slug,
        "title": name,
        "description": description,
        "price_usd": price_usd,
        "previous_price_usd": prev_price_usd if prev_price_usd and prev_price_usd != price_usd else None,
        "primary_photo_url": photo_url,
        "_source": "wix-json",
    }


def scrape_product_page(url: str, session: requests.Session) -> Optional[dict[str, Any]]:
    """Scrape a single product page. Returns product dict or None."""
    try:
        r = session.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        if r.status_code == 404:
            return None
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return None

    soup = BeautifulSoup(r.text, "lxml")

    # Try JSON-LD first (most reliable)
    product = _extract_from_json_ld(soup, url)
    if product:
        return product

    # Try Wix embedded JSON
    wix_product = _extract_wix_product(soup)
    if wix_product:
        result = _extract_from_wix_json(wix_product)
        if result:
            return result

    # Fallback: HTML scraping
    return _extract_from_page_html(url, soup)


def _deduplicate(products: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for p in products:
        slug = p.get("slug", "")
        if not slug:
            continue
        if slug not in seen:
            seen[slug] = p
        else:
            # Prefer the one with more data
            existing = seen[slug]
            if len(p.get("description", "")) > len(existing.get("description", "")):
                seen[slug] = p
    return list(seen.values())


def main() -> int:
    session = requests.Session()
    session.headers.update(HEADERS)

    # Step 1: Get all product URLs from Wix store sitemap
    print("\n[1/2] Fetching product URLs …")
    try:
        product_urls = _get_product_urls()
    except Exception as e:
        print(f"  ERROR: {e}")
        return 1

    # Step 2: Scrape each product page (all are boats — accessories are managed separately)
    print(f"\n[2/2] Scraping {len(product_urls)} product pages …")
    all_products: list[dict[str, Any]] = []

    for i, url in enumerate(product_urls, 1):
        print(f"  [{i}/{len(product_urls)}] {url}")
        product = scrape_product_page(url, session)
        if product:
            slug = url.rstrip("/").split("/product-page/")[-1]
            product["slug"] = slug
            all_products.append(product)
            print(f"    '{product['title']}' ${product['price_usd']:,}")
        else:
            print("    → Could not extract product data")
        time.sleep(0.8)

    # Deduplicate & clean up
    all_products = _deduplicate(all_products)
    for p in all_products:
        p.pop("_source", None)

    # Sort by price desc
    all_products.sort(key=lambda x: -(x.get("price_usd") or 0))

    if not all_products:
        print("\nERROR: No products scraped.")
        return 1

    print(f"\nTotal: {len(all_products)} boat listings scraped")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(all_products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved → {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
