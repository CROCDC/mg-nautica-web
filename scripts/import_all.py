"""Unified import: scrape → download photos → wipe DB → seed.

Usage (from project root):
    python scripts/import_all.py

Flags:
    --skip-scrape       Skip scraping (use existing JSON files)
    --skip-download     Skip photo download (use URLs already in JSON)
    --skip-seed         Skip DB wipe + seed
    --skip-wipe         Seed without wiping existing data first
    --skip-meli         Skip ML association step
    --meli-site         ML site: MLA or MLU (default: MLA)
    --meli-min-score    Min match score for ML auto-link (default: 0.50)

Steps:
    1. Scrape boats          → scripts/data/products.json
    2. Scrape accessories    → scripts/data/accessories.json
    3. Download boat photos  → uploads/boats/,   updates products.json
    4. Download acc. photos  → uploads/accessories/, updates accessories.json
    5. Wipe boats + accessories from DB
    6. Seed DB from JSON files
    7. Associate MercadoLibre listings with boats
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
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

ACCESSORIES_URL = "https://www.mgnauticabroker.com/home-1-1-1"
ARS_USD_RATE = 1200
BOATS_BASE_URL = "https://www.mgnauticabroker.com"


# ── boat scraping helpers ──────────────────────────────────────────────────────

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
    prices = _extract_prices_from_text(raw)
    return prices[0] if prices else None


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _get_product_urls() -> list[str]:
    import requests
    print("Fetching store products sitemap …")
    from bs4 import BeautifulSoup
    r = requests.get(f"{BOATS_BASE_URL}/store-products-sitemap.xml", headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml-xml")
    urls = [
        loc.get_text(strip=True)
        for loc in soup.find_all("loc")
        if "/product-page/" in loc.get_text(strip=True)
    ]
    print(f"  Found {len(urls)} product URLs")
    return urls


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
    from bs4 import BeautifulSoup  # noqa: F401 (already imported at call site)
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
    for sel in [
        '[data-hook="product-description"]',
        ".wixui-rich-text",
        '[data-testid="product-description"]',
    ]:
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
    return {
        "slug": slug,
        "title": title,
        "description": description,
        "price_usd": price_usd,
        "previous_price_usd": prev_price_usd,
        "primary_photo_url": photo_url,
        "_source": "html",
    }


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
        price_usd = None
        prev_price_usd = None
        offers = data.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price_raw = offers.get("price") or data.get("price")
        if price_raw:
            price_usd = _parse_price(str(price_raw))
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


def scrape_product_page(url: str, session) -> Optional[dict[str, Any]]:
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


def _deduplicate(products: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for p in products:
        slug = p.get("slug", "")
        if not slug:
            continue
        if slug not in seen:
            seen[slug] = p
        else:
            existing = seen[slug]
            if len(p.get("description", "")) > len(existing.get("description", "")):
                seen[slug] = p
    return list(seen.values())


# ── accessory scraping helpers ─────────────────────────────────────────────────

def _acc_slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[áàä]", "a", text)
    text = re.sub(r"[éèë]", "e", text)
    text = re.sub(r"[íìï]", "i", text)
    text = re.sub(r"[óòö]", "o", text)
    text = re.sub(r"[úùü]", "u", text)
    text = re.sub(r"ñ", "n", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _acc_parse_price(price_text: str) -> tuple[int, str]:
    t = price_text.strip()
    t = re.sub(r"^desde\s+", "", t, flags=re.IGNORECASE)
    if t.upper().startswith("ARG"):
        digits = re.sub(r"[^0-9]", "", t)
        if digits:
            ars = int(digits)
            return (round(ars / ARS_USD_RATE), "ARS")
        return (0, "ARS")
    t = re.sub(r"U\$S|US\$|USD", "", t, flags=re.IGNORECASE).strip()
    if "." in t and "," in t:
        last_dot = t.rfind(".")
        last_comma = t.rfind(",")
        if last_comma > last_dot:
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "." in t:
        parts = t.split(".")
        if all(len(p) == 3 for p in parts[1:]):
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


def scrape_accessories_from_web() -> list[dict]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        print(f"Loading {ACCESSORIES_URL} …")
        page.goto(ACCESSORIES_URL, wait_until="domcontentloaded", timeout=60000)
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
                    let container = h5.parentElement;
                    for (let i = 0; i < 5; i++) {
                        if (!container || !container.parentElement) break;
                        const img = container.querySelector('img');
                        const para = container.querySelector('p');
                        if (img && para) break;
                        container = container.parentElement;
                    }
                    if (!container) continue;
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
                    const paras = Array.from(container.querySelectorAll('p'))
                        .map(p => p.textContent.trim())
                        .filter(t => t.length > 0);
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
        price_usd, currency = _acc_parse_price(price_text)
        description_parts = []
        if currency == "ARS":
            description_parts.append(f"Precio en pesos argentinos: {price_text}.")
        if location:
            description_parts.append(f"Ubicación: {location}.")
        if whatsapp:
            description_parts.append(f"Contacto: {whatsapp}")
        results.append({
            "slug": _acc_slugify(title),
            "title": title,
            "description": " ".join(description_parts),
            "category": _classify_accessory_category(title),
            "price_usd": price_usd,
            "previous_price_usd": None,
            "stock": None,
            "photo_url": photo_url or None,
            "active": True,
            "_location": location,
            "_whatsapp": whatsapp,
        })
    return results


# ── seed helpers ───────────────────────────────────────────────────────────────

SKIP_SLUGS: set[str] = {"termo-acero-inoxidable", "cojín-asiento-impermeable"}

FLAGSHIP_SLUG = "velero-jeanneau-sun-odyssey-39-ds"
FLAGSHIP_SPECS: dict[str, Any] = {
    "length_m": 11.62,
    "beam_m": 3.88,
    "draft_m": 2.00,
    "displacement_t": 9.0,
    "year": 2007,
    "shipyard": "Jeanneau",
    "model_name": "Sun Odyssey 39 DS",
    "last_refit": "Mayo 2023",
    "last_careening": "Septiembre 2024",
    "engine_brand": "Yanmar",
    "engine_hp": 39,
    "engine_hours": 3000,
    "propeller": "3 palas con eje",
    "bow_thruster": True,
    "fuel_liters": 130,
    "fresh_water_liters": 300,
    "sails": "Mayor, Genoa y Trinqueta enrollables (UK) + Tormentín + Twin",
    "furlers": "SELDEN (3)",
    "poles": "2 tangones (1 SELDEN telescópico + 1 fijo 4 m)",
    "bowsprit": "SELDEN para twin o gennaker",
    "mast_rig": "SELDEN (2019)",
    "electronics_plotter": "SIMRAD cockpit + RAYMARINE C80 mesa de cartas",
    "electronics_ais": "Transreceptor",
    "electronics_radar": "B&G",
    "electronics_wind": "Tridata & Wind Raymarine ST60+",
    "electronics_autopilot": "Raymarine ST6002",
    "electronics_charts": "NAVIONICS en ambos plotters",
    "electronics_vhf": "VHF 25W interior + VHF 25W cockpit + 2 handys",
    "electronics_satellite": "Garmin 86i + Inmarsat voz",
    "electronics_starlink": True,
    "batteries_config": "5 baterías servicio 140 Ah (700 Ah total) + 110 Ah proa + 75 Ah arranque",
    "solar_watts": 600,
    "inverter_watts": 1500,
    "chargers": "2 cargadores 220 V",
    "generator": "Caterpillar 2000 W portátil",
    "cabins_qty": 2,
    "bathrooms_qty": 1,
    "saloon": "Deck Saloon",
    "galley": "Cocina a gas (2 hornallas + horno)",
    "fridge": "Nevera con hielera",
    "tv": 'TV 32" Smart',
    "air_conditioning": "Portátil",
    "water_heater": "Termotanque 40 L (motor / 220V)",
    "ground_tackle": (
        "Ancla arado 20 kg + 60 m cadena 10 mm; Danforth 17 kg; "
        "Almirantazgo plegable 15 kg; Ancla de mar / capa; Ancla plegable 2 kg (tender)"
    ),
    "chain_meters": 60,
    "chain_mm": 10,
    "extra_inventory": "Agua de mar en cocina y bañera; ducha de popa agua dulce; gran pañol; luces LED; faro de maniobras en proa",
}


def _classify_boat_type(slug: str, title: str):
    from app.models import BoatType
    s = slug.lower()
    t = title.lower()
    if s.startswith("velero") or s.startswith("veero") or t.startswith("velero"):
        return BoatType.SAILBOAT
    if s.startswith("lancha") or t.startswith("lancha"):
        return BoatType.MOTORBOAT
    if s.startswith("catamaran") or "catamarán" in t:
        return BoatType.CATAMARAN
    if s.startswith("ballenera") or t.startswith("ballenera"):
        return BoatType.WHALER
    if s.startswith("crucero") or t.startswith("crucero") or "sea-ray" in s or "trento" in s:
        return BoatType.CRUISER
    return BoatType.SAILBOAT


def _classify_flag(slug: str, title: str, description: str):
    from app.models import Flag
    s = slug.lower()
    t = title.lower()
    d = description.lower()
    for kw in ["panama", "panamá", "caribe", "san-blas", "brasil", "polaca", "polaco"]:
        if kw in s or kw in t or kw in d:
            return Flag.FOREIGN
    for kw in ["uruguay", "piriapolis", "piriápolis", "montevideo", "punta-del-este", "bandera 🇺🇾", "🇺🇾"]:
        if kw in s or kw in t or kw in d:
            if "concepción-del-uruguay" in s or "concepción del uruguay" in t.lower():
                return Flag.AR
            return Flag.UY
    return Flag.AR


def _location(flag, slug: str, title: str, description: str) -> tuple[Optional[str], Optional[str]]:
    from app.models import Flag
    s = slug.lower()
    d = description.lower()
    if "panama" in s or "panamá" in s or "panama" in d or "panamá" in d:
        city = "San Blas" if ("san-blas" in s or "san blas" in d) else None
        return ("Panamá", city)
    if "caribe" in s or "caribe" in d:
        return ("Caribe", None)
    if "brasil" in d or "brasil" in s:
        return ("Brasil", None)
    if "piriapolis" in s or "piriápolis" in s or "piriápolis" in d:
        return ("Uruguay", "Piriápolis")
    if "montevideo" in s or "montevideo" in d:
        return ("Uruguay", "Montevideo")
    if "punta-del-este" in s or "punta del este" in d:
        return ("Uruguay", "Punta del Este")
    if "uruguay" in s or "uruguay" in d:
        if "concepción" in s or "concepción" in d:
            return ("Argentina", "Concepción del Uruguay")
        return ("Uruguay", None)
    if flag == Flag.AR:
        return ("Argentina", None)
    if flag == Flag.UY:
        return ("Uruguay", None)
    return (None, None)


def _get_or_create_boat(db, boat_data: dict[str, Any], specs_data: Optional[dict[str, Any]] = None, photos: Optional[list[str]] = None):
    from app.models import Boat, BoatPhoto, BoatSpecs
    existing = db.session.query(Boat).filter_by(slug=boat_data["slug"]).one_or_none()
    if existing is not None:
        return existing
    boat = Boat(**boat_data)
    db.session.add(boat)
    db.session.flush()
    if specs_data:
        db.session.add(BoatSpecs(boat_id=boat.id, **specs_data))
    for i, url in enumerate(photos or []):
        db.session.add(BoatPhoto(boat_id=boat.id, url=url, position=i, is_primary=(i == 0)))
    db.session.flush()
    return boat


def _get_or_create_accessory(db, data: dict[str, Any]):
    from app.models import Accessory
    existing = db.session.query(Accessory).filter_by(slug=data["slug"]).one_or_none()
    if existing is not None:
        return existing
    accessory = Accessory(**data)
    db.session.add(accessory)
    db.session.flush()
    return accessory


def _get_or_create_admin_user(db) -> tuple[Any, bool]:
    from app.models import User, UserRole
    email = os.environ.get("ADMIN_EMAIL", "admin@mgnautica.local").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "changeme-admin")
    existing = db.session.query(User).filter_by(email=email).one_or_none()
    if existing is not None:
        return existing, False
    user = User(
        email=email,
        name=os.environ.get("ADMIN_NAME", "Admin"),
        role=UserRole.ADMIN,
        active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user, True


def seed(db) -> tuple[int, int, bool]:
    from app.models import Accessory, AccessoryCategory, Boat, BoatStatus

    products = json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    valid_boats = [p for p in products if p["slug"] not in SKIP_SLUGS]
    featured_slugs = {
        p["slug"]
        for p in sorted(valid_boats, key=lambda x: x["price_usd"] or 0, reverse=True)[:6]
    }

    boats_created = 0
    accessories_created = 0

    accessories_raw: list[dict] = (
        json.loads(ACCESSORIES_FILE.read_text(encoding="utf-8"))
        if ACCESSORIES_FILE.exists()
        else []
    )
    for raw in accessories_raw:
        acc_data = {
            "slug": raw["slug"],
            "title": raw["title"],
            "description": raw.get("description") or "",
            "category": AccessoryCategory(raw["category"]),
            "price_usd": raw.get("price_usd") or 0,
            "previous_price_usd": raw.get("previous_price_usd"),
            "stock": raw.get("stock") or 0,
            "photo_url": raw.get("photo_url"),
            "active": raw.get("active", True),
        }
        before = db.session.query(Accessory).filter_by(slug=acc_data["slug"]).count()
        _get_or_create_accessory(db, acc_data)
        after = db.session.query(Accessory).filter_by(slug=acc_data["slug"]).count()
        if before == 0 and after == 1:
            accessories_created += 1

    for p in products:
        slug = p["slug"]
        if slug in SKIP_SLUGS:
            continue
        title = p["title"]
        description = p["description"] or ""
        price = int(p["price_usd"] or 0)
        prev_price = p["previous_price_usd"]
        on_sale = prev_price is not None
        photos = p.get("photos") or ([p["primary_photo_url"]] if p.get("primary_photo_url") else [])
        boat_type = _classify_boat_type(slug, title)
        flag = _classify_flag(slug, title, description)
        country, city = _location(flag, slug, title, description)
        boat_data: dict[str, Any] = {
            "slug": slug,
            "title": title,
            "description": description,
            "boat_type": boat_type,
            "flag": flag,
            "country_location": country,
            "city_location": city,
            "price_usd": price,
            "previous_price_usd": prev_price,
            "on_sale": on_sale,
            "commission_pct": 4.00 if price >= 20000 else None,
            "commission_flat_usd": 500 if price < 20000 else None,
            "status": BoatStatus.AVAILABLE,
            "featured": slug in featured_slugs,
        }
        specs_data: Optional[dict[str, Any]] = None
        if slug == FLAGSHIP_SLUG:
            for k in ("year", "shipyard", "model_name", "length_m", "beam_m", "draft_m", "displacement_t", "last_refit", "last_careening"):
                if k in FLAGSHIP_SPECS:
                    boat_data[k] = FLAGSHIP_SPECS[k]
            specs_data = {
                k: v for k, v in FLAGSHIP_SPECS.items()
                if k not in ("length_m", "beam_m", "draft_m", "displacement_t", "year", "shipyard", "model_name", "last_refit", "last_careening")
            }
        before = db.session.query(Boat).filter_by(slug=slug).count()
        _get_or_create_boat(db, boat_data, specs_data=specs_data, photos=photos)
        after = db.session.query(Boat).filter_by(slug=slug).count()
        if before == 0 and after == 1:
            boats_created += 1

    _, admin_created = _get_or_create_admin_user(db)
    db.session.commit()
    return boats_created, accessories_created, admin_created


# ── ML scan helpers ────────────────────────────────────────────────────────────

_MELI_NOISE = {
    "en", "venta", "para", "listo", "navegar", "oportunidad", "impecable",
    "nuevo", "precio", "muy", "completo", "cuidado", "excelente", "estado",
    "con", "orza", "bandera", "motor", "interno", "version",
    "ron", "ideal", "primer", "barco", "hermosa",
    "pies", "sin", "de", "la", "el", "los", "las", "del", "y",
    "a", "un", "una", "al", "e", "su",
}


def _meli_normalize(title: str) -> set[str]:
    title = re.sub(
        r"[\U00010000-\U0010FFFF\U00002600-\U000027FF\U00002300-\U000023FF"
        r"\U0001F300-\U0001FAFF\U0000FE00-\U0000FEFF●]",
        " ", title,
    )
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    tokens = title.split()
    bigrams = {
        f"{tokens[i]}_{tokens[i+1]}"
        for i in range(len(tokens) - 1)
        if len(tokens[i]) > 2 and len(tokens[i + 1]) > 2
        and tokens[i] not in _MELI_NOISE and tokens[i + 1] not in _MELI_NOISE
    }
    unigrams = {t for t in tokens if len(t) > 1 and t not in _MELI_NOISE}
    return unigrams | bigrams


def _meli_f1(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    precision = inter / len(a)
    recall = inter / len(b)
    return 2 * precision * recall / (precision + recall)


def _fetch_all_item_ids(client, user_id: str) -> list[str]:
    ids: list[str] = []
    limit = 100
    offset = 0
    while True:
        data = client.get(f"/users/{user_id}/items/search", params={"limit": limit, "offset": offset})
        batch = data.get("results", [])
        ids.extend(batch)
        paging = data.get("paging", {})
        total = paging.get("total", 0)
        offset += limit
        if offset >= total or not batch:
            break
    return ids


def _fetch_item_details(client, item_ids: list[str]) -> list[dict]:
    details: list[dict] = []
    attrs = "id,title,status,permalink,price"
    for i in range(0, len(item_ids), 50):
        batch = item_ids[i: i + 50]
        result = client.get("/items", params={"ids": ",".join(batch), "attributes": attrs})
        for entry in result:
            body = entry.get("body", {})
            if body:
                details.append(body)
    return details


def fetch_via_api(site: str) -> list[dict]:
    from app.integrations.mercadolibre.auth import MeliOAuth
    from app.integrations.mercadolibre.client import MeliClient

    token = MeliOAuth.get_valid_token(site)
    client = MeliClient(access_token=token)
    me = client.get("/users/me")
    user_id = str(me["id"])
    print(f"  Authenticated as: {me.get('nickname')} (ID {user_id})")
    print("  Fetching item IDs …")
    item_ids = _fetch_all_item_ids(client, user_id)
    print(f"  Found {len(item_ids)} items total")
    print("  Fetching item details …")
    items = _fetch_item_details(client, item_ids)
    return [
        {
            "title": it.get("title", ""),
            "meli_id": it.get("id", ""),
            "meli_url": it.get("permalink", ""),
            "status": it.get("status", ""),
            "price_raw": str(it.get("price", "")),
        }
        for it in items
        if it.get("title") and it.get("id")
    ]


def fetch_via_playwright(seller_id: int) -> list[dict]:
    from playwright.sync_api import sync_playwright

    url = f"https://listado.mercadolibre.com.ar/_CustId_{seller_id}"
    print(f"  No credentials — scraping public page: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)

        total_el = page.query_selector(".ui-search-search-result__quantity-results")
        total_txt = total_el.inner_text() if total_el else "?"
        print(f"  Total: {total_txt}")

        items = page.query_selector_all("li.ui-search-layout__item")
        results = []
        for item in items:
            title_el = item.query_selector("h2.ui-search-item__title, .poly-component__title")
            link_el = item.query_selector("a.poly-component__title, a.ui-search-link")
            price_el = item.query_selector(".andes-money-amount__fraction")
            title = title_el.inner_text().strip() if title_el else ""
            href = link_el.get_attribute("href") if link_el else ""
            mla_m = re.search(r"MLA-?(\d+)", href or "")
            price_txt = price_el.inner_text().strip() if price_el else ""
            if title and mla_m:
                results.append({
                    "title": title,
                    "meli_id": f"MLA{mla_m.group(1)}",
                    "meli_url": href.split("#")[0] if href else "",
                    "status": "active",
                    "price_raw": price_txt,
                })
        browser.close()

    print(f"  {len(results)} listings scraped")
    return results


def match_listings(listings: list[dict], boats: list) -> list[dict]:
    boat_tokens = {id(b): (_meli_normalize(b.title), b) for b in boats}
    candidates = []
    for listing in listings:
        ml_tokens = _meli_normalize(listing["title"])
        for obj_id, (db_tokens, boat) in boat_tokens.items():
            score = _meli_f1(ml_tokens, db_tokens)
            if score > 0:
                candidates.append((score, listing, boat))
    candidates.sort(key=lambda x: -x[0])

    claimed_boats: set[int] = set()
    claimed_listings: set[str] = set()
    result_map: dict[str, dict] = {}

    for score, listing, boat in candidates:
        meli_id = listing["meli_id"]
        boat_obj_id = id(boat)
        if meli_id in claimed_listings or boat_obj_id in claimed_boats:
            continue
        result_map[meli_id] = {"listing": listing, "boat": boat, "score": score}
        claimed_listings.add(meli_id)
        claimed_boats.add(boat_obj_id)

    for listing in listings:
        if listing["meli_id"] not in result_map:
            result_map[listing["meli_id"]] = {"listing": listing, "boat": None, "score": 0.0}

    return list(result_map.values())


def _trunc(s: str, n: int) -> str:
    return s[:n] + "…" if len(s) > n else s


def print_meli_report(matches: list[dict], min_score: float) -> None:
    auto = [m for m in matches if m["boat"] and m["score"] >= min_score and not m["boat"].meli_mla_item_id]
    already = [m for m in matches if m["boat"] and m["boat"].meli_mla_item_id]
    low = [m for m in matches if m["boat"] and m["score"] < min_score and not m["boat"].meli_mla_item_id]
    no_match = [m for m in matches if not m["boat"]]

    def row(m: dict) -> str:
        status = m["listing"].get("status", "")
        status_tag = f" [{status}]" if status and status != "active" else ""
        return (
            f"  [{m['score']:.2f}] {_trunc(m['listing']['title'], 40):<42}"
            f"→  {_trunc(m['boat'].title, 42):<44}"
            f"  {m['listing']['meli_id']}{status_tag}"
        )

    print(f"\n{'='*116}")
    print(f"MercadoLibre scan — {len(matches)} listings")
    print(f"{'='*116}")
    print(f"\nAUTO-LINK ({len(auto)}) — score >= {min_score}")
    for m in sorted(auto, key=lambda x: -x["score"]):
        print(row(m))
    if already:
        print(f"\nALREADY LINKED ({len(already)})")
        for m in already:
            print(
                f"       {_trunc(m['listing']['title'], 42):<44}"
                f"→  {_trunc(m['boat'].title, 42):<44}"
                f"  {m['boat'].meli_mla_item_id}  [{m['score']:.2f}]"
            )
    if low:
        print(f"\nLOW CONFIDENCE ({len(low)}) — score < {min_score} — NOT linked")
        for m in sorted(low, key=lambda x: -x["score"]):
            print(row(m))
    if no_match:
        print(f"\nNO MATCH ({len(no_match)})")
        for m in no_match:
            print(f"       {m['listing']['title']}  {m['listing']['meli_id']}")
    print()


def apply_matches(matches: list[dict], min_score: float, db) -> int:
    now = datetime.now(timezone.utc)
    updated = 0
    for m in matches:
        if not m["boat"] or m["score"] < min_score:
            continue
        if m["boat"].meli_mla_item_id:
            continue
        boat = m["boat"]
        boat.meli_mla_item_id = m["listing"]["meli_id"]
        boat.meli_mla_permalink = m["listing"]["meli_url"]
        boat.meli_mla_status = m["listing"].get("status", "active")
        boat.meli_mla_synced_at = now
        updated += 1
    db.session.commit()
    return updated


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


# ── step 1: scrape boats ───────────────────────────────────────────────────────

def step_scrape_boats() -> None:
    import requests
    print("\n[STEP 1/4] Scraping boat listings …")
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        urls = _get_product_urls()
    except Exception as e:
        print(f"  ERROR fetching URLs: {e}")
        sys.exit(1)

    products: list[dict[str, Any]] = []
    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url}")
        p = scrape_product_page(url, session)
        if p:
            slug = url.rstrip("/").split("/product-page/")[-1]
            p["slug"] = slug
            products.append(p)
            print(f"    '{p['title']}' ${p['price_usd']:,}")
        else:
            print("    → no data")
        time.sleep(0.8)

    products = _deduplicate(products)
    for p in products:
        p.pop("_source", None)
    products.sort(key=lambda x: -(x.get("price_usd") or 0))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCTS_FILE.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {len(products)} boats saved to {PRODUCTS_FILE}")


# ── step 2: scrape accessories ─────────────────────────────────────────────────

def step_scrape_accessories() -> None:
    print("\n[STEP 2/4] Scraping accessories …")
    items = scrape_accessories_from_web()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACCESSORIES_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {len(items)} accessories saved to {ACCESSORIES_FILE}")


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
    print("  → products.json updated")


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

def step_wipe_and_seed(skip_wipe: bool) -> None:
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
        boats, accessories, admin_created = seed(db)
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

def _fetch_meli_listings(site: str) -> list[dict]:
    try:
        listings = fetch_via_api(site)
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

    listings = fetch_via_playwright(seller_id)
    print(f"  {len(listings)} public active listings (no credentials)")
    return listings


def step_associate_meli(site: str, min_score: float) -> None:
    print(f"\n[STEP 6] Associating MercadoLibre {site} listings …")
    from app import app
    from app.factory import db
    from app.models import Boat

    listings = _fetch_meli_listings(site)
    if not listings:
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache = DATA_DIR / f"meli_listings_{site.lower()}.json"
    cache.write_text(json.dumps(listings, ensure_ascii=False, indent=2), encoding="utf-8")

    with app.app_context():
        boats = db.session.query(Boat).all()
        matches = match_listings(listings, boats)
        print_meli_report(matches, min_score)
        updated = apply_matches(matches, min_score, db)
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
