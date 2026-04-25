"""Seed initial data into the database.

Usage (from project root):
    python scripts/seed.py

Data source: scripts/data/products.json (67 products scraped from mgnauticabroker.com).
Idempotent: if a record with the same slug exists it is skipped.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app  # noqa: E402
from app.factory import db  # noqa: E402
from app.models import (  # noqa: E402
    Accessory,
    AccessoryCategory,
    Boat,
    BoatPhoto,
    BoatSpecs,
    BoatStatus,
    BoatType,
    Flag,
    User,
    UserRole,
)

DATA_FILE = Path(__file__).parent / "data" / "products.json"
ACCESSORIES_FILE = Path(__file__).parent / "data" / "accessories.json"

# Slugs from the scrape that are noise (mismatched Wix pages) — skip them entirely.
SKIP_SLUGS: set[str] = {"termo-acero-inoxidable", "cojín-asiento-impermeable"}


def _classify_boat_type(slug: str, title: str) -> BoatType:
    s = slug.lower()
    t = title.lower()
    # Sailboat prefix wins: slugs like "velero-clasico-hermosa-ballenera" are still sailboats.
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
    # Named models (dufour, jeanneau, custon-special): sailboats.
    return BoatType.SAILBOAT


def _classify_flag(slug: str, title: str, description: str) -> Flag:
    s = slug.lower()
    t = title.lower()
    d = description.lower()
    # Foreign markers
    foreign_kw = ["panama", "panamá", "caribe", "san-blas", "brasil", "polaca", "polaco"]
    for kw in foreign_kw:
        if kw in s or kw in t or kw in d:
            return Flag.FOREIGN
    # Uruguay markers
    uy_kw = ["uruguay", "piriapolis", "piriápolis", "montevideo", "punta-del-este", "bandera 🇺🇾", "🇺🇾"]
    for kw in uy_kw:
        if kw in s or kw in t or kw in d:
            # Concepción del Uruguay is AR (Entre Ríos), not UY
            if "concepción-del-uruguay" in s or "concepción del uruguay" in t.lower():
                return Flag.AR
            return Flag.UY
    return Flag.AR


def _location(flag: Flag, slug: str, title: str, description: str) -> tuple[Optional[str], Optional[str]]:
    """(country_location, city_location) best-effort from text."""
    s = slug.lower()
    d = description.lower()
    if "panama" in s or "panamá" in s or "panama" in d or "panamá" in d:
        city = None
        if "san-blas" in s or "san blas" in d:
            city = "San Blas"
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


# Rich technical specs for the flagship listing (Jeanneau Sun Odyssey 39 DS "Chiripa II").
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


def _get_or_create_boat(
    boat_data: dict[str, Any],
    specs_data: Optional[dict[str, Any]] = None,
    photos: Optional[list[str]] = None,
) -> Boat:
    existing: Optional[Boat] = (
        db.session.query(Boat).filter_by(slug=boat_data["slug"]).one_or_none()
    )
    if existing is not None:
        return existing
    boat = Boat(**boat_data)
    db.session.add(boat)
    db.session.flush()
    if specs_data:
        specs = BoatSpecs(boat_id=boat.id, **specs_data)
        db.session.add(specs)
    for i, url in enumerate(photos or []):
        photo = BoatPhoto(boat_id=boat.id, url=url, position=i, is_primary=(i == 0))
        db.session.add(photo)
    db.session.flush()
    return boat


def _get_or_create_accessory(data: dict[str, Any]) -> Accessory:
    existing: Optional[Accessory] = (
        db.session.query(Accessory).filter_by(slug=data["slug"]).one_or_none()
    )
    if existing is not None:
        return existing
    accessory = Accessory(**data)
    db.session.add(accessory)
    db.session.flush()
    return accessory


def _get_or_create_admin_user() -> tuple[User, bool]:
    """Ensure there is at least one admin user. Returns (user, created)."""
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


def seed() -> tuple[int, int, bool]:
    products = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    # Featured slugs: the 6 highest-priced boats for the home grid.
    valid_boats = [p for p in products if p["slug"] not in SKIP_SLUGS]
    featured_slugs = {
        p["slug"]
        for p in sorted(valid_boats, key=lambda x: x["price_usd"] or 0, reverse=True)[:6]
    }

    boats_created = 0
    accessories_created = 0

    # ── Scraped accessories ────────────────────────────────────────────────────
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
        _get_or_create_accessory(acc_data)
        after = db.session.query(Accessory).filter_by(slug=acc_data["slug"]).count()
        if before == 0 and after == 1:
            accessories_created += 1

    # ── Boats from scrape ──────────────────────────────────────────────────────
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
            # Pull structured fields from the flagship spec sheet.
            for k in ("year", "shipyard", "model_name"):
                if k in FLAGSHIP_SPECS:
                    boat_data[k] = FLAGSHIP_SPECS[k]
            for k in ("length_m", "beam_m", "draft_m", "displacement_t"):
                if k in FLAGSHIP_SPECS:
                    boat_data[k] = FLAGSHIP_SPECS[k]
            for k in ("last_refit", "last_careening"):
                if k in FLAGSHIP_SPECS:
                    boat_data[k] = FLAGSHIP_SPECS[k]
            specs_data = {
                k: v
                for k, v in FLAGSHIP_SPECS.items()
                if k
                not in (
                    "length_m",
                    "beam_m",
                    "draft_m",
                    "displacement_t",
                    "year",
                    "shipyard",
                    "model_name",
                    "last_refit",
                    "last_careening",
                )
            }

        before = db.session.query(Boat).filter_by(slug=slug).count()
        _get_or_create_boat(boat_data, specs_data=specs_data, photos=photos)
        after = db.session.query(Boat).filter_by(slug=slug).count()
        if before == 0 and after == 1:
            boats_created += 1

    _, admin_created = _get_or_create_admin_user()
    db.session.commit()
    return boats_created, accessories_created, admin_created


def sync_photos() -> int:
    """Re-sync BoatPhoto records from products.json for boats that already exist.

    Safe to run multiple times. Only touches boats whose photo count differs
    from what products.json says (or that have no photos at all).
    Returns the number of boats updated.
    """
    products = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    updated = 0
    for p in products:
        slug = p["slug"]
        if slug in SKIP_SLUGS:
            continue
        photos = p.get("photos") or (
            [p["primary_photo_url"]] if p.get("primary_photo_url") else []
        )
        if not photos:
            continue
        boat: Optional[Boat] = db.session.query(Boat).filter_by(slug=slug).one_or_none()
        if boat is None:
            continue
        existing = db.session.query(BoatPhoto).filter_by(boat_id=boat.id).count()
        if existing == len(photos):
            continue  # already in sync
        db.session.query(BoatPhoto).filter_by(boat_id=boat.id).delete()
        for i, url in enumerate(photos):
            db.session.add(BoatPhoto(boat_id=boat.id, url=url, position=i, is_primary=(i == 0)))
        updated += 1
    db.session.commit()
    return updated


def main() -> int:
    with app.app_context():
        db.create_all()
        boats, accessories, admin_created = seed()
        total_boats = db.session.query(Boat).count()
        total_accessories = db.session.query(Accessory).count()
        total_users = db.session.query(User).count()
    print(
        f"Seed OK: {boats} new boats ({total_boats} total), "
        f"{accessories} new accessories ({total_accessories} total), "
        f"{'1 new admin' if admin_created else '0 new admins'} ({total_users} users total)."
    )
    if admin_created:
        print(
            f"  Admin email:    {os.environ.get('ADMIN_EMAIL', 'admin@mgnautica.local')}"
        )
        print(
            f"  Admin password: {os.environ.get('ADMIN_PASSWORD', 'changeme-admin')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
