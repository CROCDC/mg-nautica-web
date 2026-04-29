"""Wipe and re-seed the database from local JSON files.

Run this inside the Docker container after deploying.

Usage (from project root):
    docker exec mg-nautica-web python scripts/seed_db.py
    docker exec mg-nautica-web python scripts/seed_db.py --no-wipe
    docker exec mg-nautica-web python scripts/seed_db.py --meli-site MLA
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPTS_DIR / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
ACCESSORIES_FILE = DATA_DIR / "accessories.json"

sys.path.insert(0, str(ROOT))

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

_FLAGSHIP_BOAT_FIELDS = ("length_m", "beam_m", "draft_m", "displacement_t", "year",
                          "shipyard", "model_name", "last_refit", "last_careening")


# ── classification helpers ─────────────────────────────────────────────────────

def _classify_boat_type(slug: str, title: str):
    from app.models import BoatType
    s, t = slug.lower(), title.lower()
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
    s, t, d = slug.lower(), title.lower(), description.lower()
    for kw in ["panama", "panamá", "caribe", "san-blas", "brasil", "polaca", "polaco"]:
        if kw in s or kw in t or kw in d:
            return Flag.FOREIGN
    for kw in ["uruguay", "piriapolis", "piriápolis", "montevideo", "punta-del-este", "🇺🇾"]:
        if kw in s or kw in t or kw in d:
            if "concepción-del-uruguay" in s or "concepción del uruguay" in t:
                return Flag.AR
            return Flag.UY
    return Flag.AR


def _location(flag, slug: str, title: str, description: str) -> tuple[Optional[str], Optional[str]]:
    from app.models import Flag
    s, d = slug.lower(), description.lower()
    if "panama" in s or "panamá" in s or "panama" in d or "panamá" in d:
        return ("Panamá", "San Blas" if ("san-blas" in s or "san blas" in d) else None)
    if "caribe" in s or "caribe" in d:
        return ("Caribe", None)
    if "brasil" in s or "brasil" in d:
        return ("Brasil", None)
    if "piriapolis" in s or "piriápolis" in s or "piriápolis" in d:
        return ("Uruguay", "Piriápolis")
    if "montevideo" in s or "montevideo" in d:
        return ("Uruguay", "Montevideo")
    if "punta-del-este" in s or "punta del este" in d:
        return ("Uruguay", "Punta del Este")
    if "uruguay" in s or "uruguay" in d:
        return ("Argentina", "Concepción del Uruguay") if ("concepción" in s or "concepción" in d) else ("Uruguay", None)
    return ("Argentina", None) if flag == Flag.AR else ("Uruguay", None) if flag == Flag.UY else (None, None)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_or_create_boat(db, boat_data: dict, specs_data: Optional[dict] = None, photos: Optional[list] = None):
    from app.models import Boat, BoatPhoto, BoatSpecs
    existing = db.session.query(Boat).filter_by(slug=boat_data["slug"]).one_or_none()
    if existing:
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


def _get_or_create_accessory(db, data: dict):
    from app.models import Accessory
    existing = db.session.query(Accessory).filter_by(slug=data["slug"]).one_or_none()
    if existing:
        return existing
    accessory = Accessory(**data)
    db.session.add(accessory)
    db.session.flush()
    return accessory


def _get_or_create_admin(db) -> tuple[Any, bool]:
    from app.models import User, UserRole
    email = os.environ.get("ADMIN_EMAIL", "admin@mgnautica.local").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "changeme-admin")
    existing = db.session.query(User).filter_by(email=email).one_or_none()
    if existing:
        return existing, False
    user = User(email=email, name=os.environ.get("ADMIN_NAME", "Admin"), role=UserRole.ADMIN, active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user, True


def seed(db) -> tuple[int, int, bool]:
    from app.models import Accessory, AccessoryCategory, Boat, BoatStatus

    products = json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    valid = [p for p in products if p["slug"] not in SKIP_SLUGS]
    featured_slugs = {p["slug"] for p in sorted(valid, key=lambda x: x["price_usd"] or 0, reverse=True)[:6]}

    boats_created = accessories_created = 0

    accessories_raw = json.loads(ACCESSORIES_FILE.read_text(encoding="utf-8")) if ACCESSORIES_FILE.exists() else []
    for raw in accessories_raw:
        acc_data = {
            "slug": raw["slug"], "title": raw["title"],
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
        if before == 0:
            accessories_created += 1

    for p in products:
        slug = p["slug"]
        if slug in SKIP_SLUGS:
            continue
        title = p["title"]
        description = p["description"] or ""
        price = int(p["price_usd"] or 0)
        prev_price = p["previous_price_usd"]
        photos = p.get("photos") or ([p["primary_photo_url"]] if p.get("primary_photo_url") else [])
        flag = _classify_flag(slug, title, description)
        country, city = _location(flag, slug, title, description)
        boat_data: dict[str, Any] = {
            "slug": slug, "title": title, "description": description,
            "boat_type": _classify_boat_type(slug, title),
            "flag": flag, "country_location": country, "city_location": city,
            "price_usd": price, "previous_price_usd": prev_price, "on_sale": prev_price is not None,
            "commission_pct": 4.00 if price >= 20000 else None,
            "commission_flat_usd": 500 if price < 20000 else None,
            "status": BoatStatus.AVAILABLE, "featured": slug in featured_slugs,
        }
        specs_data = None
        if slug == FLAGSHIP_SLUG:
            for k in _FLAGSHIP_BOAT_FIELDS:
                if k in FLAGSHIP_SPECS:
                    boat_data[k] = FLAGSHIP_SPECS[k]
            specs_data = {k: v for k, v in FLAGSHIP_SPECS.items() if k not in _FLAGSHIP_BOAT_FIELDS}
        before = db.session.query(Boat).filter_by(slug=slug).count()
        _get_or_create_boat(db, boat_data, specs_data=specs_data, photos=photos)
        if before == 0:
            boats_created += 1

    _, admin_created = _get_or_create_admin(db)
    db.session.commit()
    return boats_created, accessories_created, admin_created


# ── ML association ─────────────────────────────────────────────────────────────

_MELI_NOISE = {
    "en", "venta", "para", "listo", "navegar", "oportunidad", "impecable",
    "nuevo", "precio", "muy", "completo", "cuidado", "excelente", "estado",
    "con", "orza", "bandera", "motor", "interno", "version", "ron",
    "ideal", "primer", "barco", "hermosa", "pies", "sin",
    "de", "la", "el", "los", "las", "del", "y", "a", "un", "una", "al", "e", "su",
}


def _meli_normalize(title: str) -> set[str]:
    title = re.sub(r"[\U00010000-\U0010FFFF\U00002600-\U000027FF\U00002300-\U000023FF"
                   r"\U0001F300-\U0001FAFF\U0000FE00-\U0000FEFF●]", " ", title)
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    tokens = title.split()
    bigrams = {f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)
               if len(tokens[i]) > 2 and len(tokens[i+1]) > 2
               and tokens[i] not in _MELI_NOISE and tokens[i+1] not in _MELI_NOISE}
    return {t for t in tokens if len(t) > 1 and t not in _MELI_NOISE} | bigrams


def _f1(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return 2 * (inter / len(a)) * (inter / len(b)) / (inter / len(a) + inter / len(b))


def _fetch_meli_listings(site: str) -> list[dict]:
    try:
        from app.integrations.mercadolibre.auth import MeliOAuth
        from app.integrations.mercadolibre.client import MeliClient
        token = MeliOAuth.get_valid_token(site)
        client = MeliClient(access_token=token)
        me = client.get("/users/me")
        user_id = str(me["id"])
        print(f"  Authenticated as: {me.get('nickname')} (ID {user_id})")
        ids: list[str] = []
        offset = 0
        while True:
            data = client.get(f"/users/{user_id}/items/search", params={"limit": 100, "offset": offset})
            batch = data.get("results", [])
            ids.extend(batch)
            paging = data.get("paging", {})
            offset += 100
            if offset >= paging.get("total", 0) or not batch:
                break
        print(f"  Found {len(ids)} items")
        details = []
        for i in range(0, len(ids), 50):
            result = client.get("/items", params={"ids": ",".join(ids[i:i+50]),
                                                   "attributes": "id,title,status,permalink,price"})
            for entry in result:
                body = entry.get("body", {})
                if body:
                    details.append(body)
        return [{"title": it.get("title", ""), "meli_id": it.get("id", ""),
                 "meli_url": it.get("permalink", ""), "status": it.get("status", ""),
                 "price_raw": str(it.get("price", ""))}
                for it in details if it.get("title") and it.get("id")]
    except Exception as exc:
        print(f"  ML API unavailable ({exc}) — skipping association")
        return []


def associate_meli(site: str, min_score: float, db) -> None:
    from app.models import Boat
    print(f"\n[ML] Associating MercadoLibre {site} listings …")
    listings = _fetch_meli_listings(site)
    if not listings:
        return

    boats = db.session.query(Boat).all()
    boat_tokens = {id(b): (_meli_normalize(b.title), b) for b in boats}
    candidates = []
    for listing in listings:
        ml_tokens = _meli_normalize(listing["title"])
        for _, (db_tokens, boat) in boat_tokens.items():
            score = _f1(ml_tokens, db_tokens)
            if score > 0:
                candidates.append((score, listing, boat))
    candidates.sort(key=lambda x: -x[0])

    claimed_boats: set[int] = set()
    claimed_listings: set[str] = set()
    matches: dict[str, dict] = {}
    for score, listing, boat in candidates:
        mid, bid = listing["meli_id"], id(boat)
        if mid in claimed_listings or bid in claimed_boats:
            continue
        matches[mid] = {"listing": listing, "boat": boat, "score": score}
        claimed_listings.add(mid)
        claimed_boats.add(bid)

    now = datetime.now(timezone.utc)
    updated = 0
    for m in matches.values():
        if m["score"] < min_score or m["boat"].meli_mla_item_id:
            continue
        boat = m["boat"]
        boat.meli_mla_item_id = m["listing"]["meli_id"]
        boat.meli_mla_permalink = m["listing"]["meli_url"]
        boat.meli_mla_status = m["listing"].get("status", "active")
        boat.meli_mla_synced_at = now
        updated += 1
    db.session.commit()
    print(f"  → {updated} boats linked to {site}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe and re-seed DB from JSON files.")
    parser.add_argument("--no-wipe", action="store_true", help="Insert without wiping existing data first")
    parser.add_argument("--meli-site", default=None, choices=["MLA", "MLU"],
                        help="Associate ML listings after seed (MLA or MLU)")
    parser.add_argument("--meli-min-score", type=float, default=0.50,
                        help="Min match score for ML auto-link (default: 0.50)")
    args = parser.parse_args()

    if not PRODUCTS_FILE.exists():
        print(f"ERROR: {PRODUCTS_FILE} not found. Run scrape_all.py first.")
        return 1

    from app import app
    from app.factory import db
    from app.models import Accessory, Boat, BoatPhoto, BoatSpecs

    with app.app_context():
        db.create_all()

        if not args.no_wipe:
            print("[WIPE] Deleting all boats and accessories …")
            db.session.query(BoatPhoto).delete()
            db.session.query(BoatSpecs).delete()
            db.session.query(Boat).delete()
            db.session.query(Accessory).delete()
            db.session.commit()
            print("  → done")

        print("[SEED] Inserting from JSON …")
        boats, accessories, admin_created = seed(db)
        total_boats = db.session.query(Boat).count()
        total_accessories = db.session.query(Accessory).count()
        print(f"  → {boats} boats inserted ({total_boats} total), "
              f"{accessories} accessories inserted ({total_accessories} total)")
        if admin_created:
            print(f"  Admin email:    {os.environ.get('ADMIN_EMAIL', 'admin@mgnautica.local')}")
            print(f"  Admin password: {os.environ.get('ADMIN_PASSWORD', 'changeme-admin')}")

        if args.meli_site:
            associate_meli(args.meli_site, args.meli_min_score, db)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
