"""Scrape accessory listings from mgnauticabroker.com/home-1-1-1 (custom Wix page).

Unlike the boats page which uses a Wix Store widget, the accessories page is a
hand-built grid of Wix containers (image + rich-text title + price + location).
Playwright renders the JS-heavy page so we can query the DOM.

Usage (from project root):
    python scripts/scrape_accessories.py

Writes:  scripts/data/accessories.json
Requires: playwright  (pip install playwright && playwright install chromium)
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

ACCESSORIES_URL = "https://www.mgnauticabroker.com/home-1-1-1"
OUT_FILE = Path(__file__).parent / "data" / "accessories.json"

# ARS/USD approximate rate used when price is given in Argentine pesos
ARS_USD_RATE = 1200


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[áàä]", "a", text)
    text = re.sub(r"[éèë]", "e", text)
    text = re.sub(r"[íìï]", "i", text)
    text = re.sub(r"[óòö]", "o", text)
    text = re.sub(r"[úùü]", "u", text)
    text = re.sub(r"ñ", "n", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _parse_price(price_text: str) -> tuple[int, str]:
    """Return (price_usd, currency) from texts like 'U$S 430', 'ARG $350.000'."""
    t = price_text.strip()
    # Remove "Desde " prefix (means "from")
    t = re.sub(r"^desde\s+", "", t, flags=re.IGNORECASE)

    if t.upper().startswith("ARG"):
        # ARS price — convert to USD
        digits = re.sub(r"[^0-9]", "", t)
        if digits:
            ars = int(digits)
            return (round(ars / ARS_USD_RATE), "ARS")
        return (0, "ARS")

    # USD variants: "U$S 430", "US$ 430", etc.
    t = re.sub(r"U\$S|US\$|USD", "", t, flags=re.IGNORECASE).strip()
    # Remove dots used as thousand separators, replace comma decimal
    if "." in t and "," in t:
        last_dot = t.rfind(".")
        last_comma = t.rfind(",")
        if last_comma > last_dot:
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "." in t:
        # Could be European thousands separator (e.g. "4.500") or decimal
        parts = t.split(".")
        if all(len(p) == 3 for p in parts[1:]):
            t = t.replace(".", "")
    elif "," in t:
        t = t.replace(",", "")

    try:
        return (int(float(t.strip())), "USD")
    except ValueError:
        return (0, "USD")


def _classify_category(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["bota", "boot"]):
        return "boots"
    if any(k in t for k in ["chubasquero", "ropa", "chaleco", "indumentaria", "campera"]):
        return "clothing"
    return "onboard"


def scrape() -> list[dict]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        print(f"Loading {ACCESSORIES_URL} …")
        page.goto(ACCESSORIES_URL, wait_until="domcontentloaded", timeout=60000)

        # Scroll to trigger lazy-load of images
        for _ in range(6):
            page.evaluate("window.scrollBy(0, 600)")
            page.wait_for_timeout(500)
        page.wait_for_timeout(3000)

        products = page.evaluate("""
            () => {
                const h5Elements = document.querySelectorAll('h5');
                const products = [];

                for (const h5 of h5Elements) {
                    const title = h5.textContent.trim();
                    if (!title) continue;

                    // Walk up until we find a container that holds image + price
                    let container = h5.parentElement;
                    for (let i = 0; i < 5; i++) {
                        if (!container || !container.parentElement) break;
                        const img = container.querySelector('img');
                        const para = container.querySelector('p');
                        if (img && para) break;
                        container = container.parentElement;
                    }
                    if (!container) continue;

                    // Extract image URL from wow-image data-image-info (highest resolution)
                    let photoUrl = '';
                    const wowImg = container.querySelector('wow-image');
                    if (wowImg) {
                        const info = wowImg.getAttribute('data-image-info');
                        if (info) {
                            try {
                                const parsed = JSON.parse(info);
                                if (parsed.imageData && parsed.imageData.url) {
                                    photoUrl = parsed.imageData.url;
                                }
                            } catch(e) {}
                        }
                    }
                    if (!photoUrl) {
                        const img = container.querySelector('img');
                        if (img) photoUrl = img.src || '';
                    }

                    // All paragraph texts (first non-empty = price, second = location/note)
                    const paras = Array.from(container.querySelectorAll('p'))
                        .map(p => p.textContent.trim())
                        .filter(t => t.length > 0);

                    // WhatsApp contact link
                    const waLink = container.querySelector('a[href*="wa.me"]');
                    const whatsapp = waLink ? waLink.href : '';

                    products.push({ title, paras, photoUrl, whatsapp });
                }

                return products;
            }
        """)

        browser.close()

    results = []
    for item in products:
        title: str = item["title"]
        paras: list[str] = item["paras"]
        photo_url: str = item["photoUrl"]
        whatsapp: str = item["whatsapp"]

        price_text = paras[0] if paras else ""
        location = paras[1] if len(paras) > 1 else ""

        price_usd, currency = _parse_price(price_text)
        description_parts = []
        if currency == "ARS":
            description_parts.append(f"Precio en pesos argentinos: {price_text}.")
        if location:
            description_parts.append(f"Ubicación: {location}.")
        if whatsapp:
            description_parts.append(f"Contacto: {whatsapp}")

        results.append(
            {
                "slug": _slugify(title),
                "title": title,
                "description": " ".join(description_parts),
                "category": _classify_category(title),
                "price_usd": price_usd,
                "previous_price_usd": None,
                "stock": None,
                "photo_url": photo_url or None,
                "active": True,
                "_location": location,
                "_whatsapp": whatsapp,
            }
        )

    return results


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright as _  # noqa: F401
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        return 1

    items = scrape()
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(items)} accessories to {OUT_FILE}")
    for item in items:
        print(f"  [{item['price_usd']} USD] {item['title']} — {item['_location']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
