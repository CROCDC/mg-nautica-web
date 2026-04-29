"""Scan all MercadoLibre listings owned by the authenticated seller account
and associate them with boats in the database using fuzzy title matching.

Requires ML OAuth credentials configured in Admin → Mercado Libre.
Falls back to Playwright page scraping if no credentials are stored.

Usage (from project root):
    python scripts/scan_meli.py           # dry-run — shows matches, writes nothing
    python scripts/scan_meli.py --apply   # persist associations to DB
    python scripts/scan_meli.py --site MLA --apply --min-score 0.4

Options:
    --apply             Save associations to DB (default: dry-run)
    --site SITE         ML site to scan: MLA or MLU (default: MLA)
    --min-score FLOAT   Minimum F1 score to auto-link (default: 0.50)
    --no-scrape-fallback  Fail instead of falling back to Playwright when no credentials
    --listings-file     Cache path for a previous run (default: scripts/data/meli_listings_<site>.json)
    --from-cache        Load from cache instead of hitting the API
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA_DIR = Path(__file__).resolve().parent / "data"

PLAYWRIGHT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Marketing noise words stripped before title comparison
_NOISE = {
    "en", "venta", "para", "listo", "navegar", "oportunidad", "impecable",
    "nuevo", "precio", "muy", "completo", "cuidado", "excelente", "estado",
    "con", "orza", "bandera", "motor", "interno", "version",
    "ron",   # "Ron Holland" designer name — "holland" kept as it's also a boat model
    "ideal", "primer", "barco", "hermosa",
    "pies", "sin", "de", "la", "el", "los", "las", "del", "y",
    "a", "un", "una", "al", "e", "su",
}


# ── normalisation / similarity ─────────────────────────────────────────────────

def _normalize(title: str) -> set[str]:
    """Return meaningful token set from a boat title."""
    # Strip emojis and non-Latin symbol blocks
    title = re.sub(
        r"[\U00010000-\U0010FFFF\U00002600-\U000027FF\U00002300-\U000023FF"
        r"\U0001F300-\U0001FAFF\U0000FE00-\U0000FEFF●]",
        " ", title,
    )
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    tokens = title.split()

    # Bigrams from non-noise tokens
    bigrams = {
        f"{tokens[i]}_{tokens[i+1]}"
        for i in range(len(tokens) - 1)
        if len(tokens[i]) > 2 and len(tokens[i + 1]) > 2
        and tokens[i] not in _NOISE and tokens[i + 1] not in _NOISE
    }
    unigrams = {t for t in tokens if len(t) > 1 and t not in _NOISE}
    return unigrams | bigrams


def _f1(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    precision = inter / len(a)
    recall = inter / len(b)
    return 2 * precision * recall / (precision + recall)


# ── fetch listings via authenticated API ──────────────────────────────────────

def _fetch_all_item_ids(client, user_id: str) -> list[str]:
    """Page through /users/{user_id}/items/search to collect every item ID."""
    ids: list[str] = []
    limit = 100
    offset = 0
    while True:
        data = client.get(
            f"/users/{user_id}/items/search",
            params={"limit": limit, "offset": offset},
        )
        batch = data.get("results", [])
        ids.extend(batch)
        paging = data.get("paging", {})
        total = paging.get("total", 0)
        offset += limit
        if offset >= total or not batch:
            break
    return ids


def _fetch_item_details(client, item_ids: list[str]) -> list[dict]:
    """Batch-fetch item details (50 per call is the ML limit for multiget)."""
    details: list[dict] = []
    chunk = 50
    attrs = "id,title,status,permalink,price"
    for i in range(0, len(item_ids), chunk):
        batch = item_ids[i : i + chunk]
        result = client.get("/items", params={"ids": ",".join(batch), "attributes": attrs})
        for entry in result:
            body = entry.get("body", {})
            if body:
                details.append(body)
    return details


def fetch_via_api(site: str) -> list[dict]:
    """Use authenticated ML API to get all seller items (including paused)."""
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


# ── fallback: Playwright scraping (public listings only) ──────────────────────

def fetch_via_playwright(seller_id: int) -> list[dict]:
    """Scrape public seller page (active listings only — no auth needed)."""
    from playwright.sync_api import sync_playwright

    url = f"https://listado.mercadolibre.com.ar/_CustId_{seller_id}"
    print(f"  ⚠  No credentials — scraping public page: {url}")
    print("     (only active listings visible; authorize in Admin → ML for full access)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=PLAYWRIGHT_UA)
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


# ── greedy 1-to-1 matching ────────────────────────────────────────────────────

def match_listings(listings: list[dict], boats: list) -> list[dict]:
    """Greedy 1-to-1: sort all pairs by score desc, assign without repetition.

    Uses Python object identity (id(boat)) so unsaved models with id=None
    are handled correctly in tests and in-memory use.
    """
    boat_tokens = {id(b): (_normalize(b.title), b) for b in boats}

    candidates = []
    for listing in listings:
        ml_tokens = _normalize(listing["title"])
        for obj_id, (db_tokens, boat) in boat_tokens.items():
            score = _f1(ml_tokens, db_tokens)
            if score > 0:
                candidates.append((score, listing, boat))

    candidates.sort(key=lambda x: -x[0])

    claimed_boats: set[int] = set()   # Python id(boat)
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


# ── report ─────────────────────────────────────────────────────────────────────

def _trunc(s: str, n: int) -> str:
    return s[:n] + "…" if len(s) > n else s


def print_report(matches: list[dict], min_score: float) -> None:
    auto     = [m for m in matches if m["boat"] and m["score"] >= min_score
                and not m["boat"].meli_mla_item_id]
    already  = [m for m in matches if m["boat"] and m["boat"].meli_mla_item_id]
    low      = [m for m in matches if m["boat"] and m["score"] < min_score
                and not m["boat"].meli_mla_item_id]
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

    print(f"\n✅  AUTO-LINK ({len(auto)}) — score ≥ {min_score}")
    for m in sorted(auto, key=lambda x: -x["score"]):
        print(row(m))

    if already:
        print(f"\n🔗  ALREADY LINKED ({len(already)})")
        for m in already:
            print(
                f"       {_trunc(m['listing']['title'], 42):<44}"
                f"→  {_trunc(m['boat'].title, 42):<44}"
                f"  {m['boat'].meli_mla_item_id}  [{m['score']:.2f}]"
            )

    if low:
        print(f"\n⚠️   LOW CONFIDENCE ({len(low)}) — score < {min_score} — NOT linked")
        for m in sorted(low, key=lambda x: -x["score"]):
            print(row(m))

    if no_match:
        print(f"\n❌  NO MATCH ({len(no_match)})")
        for m in no_match:
            print(f"       {m['listing']['title']}  {m['listing']['meli_id']}")

    print()


# ── apply ──────────────────────────────────────────────────────────────────────

def apply_matches(matches: list[dict], min_score: float) -> int:
    from app.factory import db

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


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan MercadoLibre and link listings to boats in DB."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Persist associations to DB (default: dry-run)")
    parser.add_argument("--site", default="MLA", choices=["MLA", "MLU"],
                        help="ML site to scan (default: MLA)")
    parser.add_argument("--min-score", type=float, default=0.50, metavar="FLOAT",
                        help="Min F1 score for auto-link (default: 0.50)")
    parser.add_argument("--no-scrape-fallback", action="store_true",
                        help="Fail if no OAuth credentials instead of falling back")
    parser.add_argument("--listings-file", type=Path, default=None,
                        help="Override cache file path")
    parser.add_argument("--from-cache", action="store_true",
                        help="Load listings from cache file instead of API")
    args = parser.parse_args()

    cache_file = args.listings_file or (DATA_DIR / f"meli_listings_{args.site.lower()}.json")

    # 1. Load / fetch listings
    from app import app
    from app.factory import db
    from app.models import Boat

    with app.app_context():

        if args.from_cache:
            if not cache_file.exists():
                print(f"ERROR: cache file not found: {cache_file}")
                return 1
            listings = json.loads(cache_file.read_text(encoding="utf-8"))
            print(f"Loaded {len(listings)} listings from cache: {cache_file}")
        else:
            print(f"Fetching {args.site} listings …")
            try:
                from app.integrations.mercadolibre.client import MeliNotConfiguredError
                listings = fetch_via_api(args.site)
                source = "api"
            except Exception as exc:
                if args.no_scrape_fallback:
                    print(f"ERROR: {exc}")
                    return 1
                print(f"  API unavailable ({exc})")
                # fallback: Playwright scrape of public page (MLA seller 431049699)
                SELLER_IDS = {"MLA": 431049699, "MLU": None}
                seller_id = SELLER_IDS.get(args.site)
                if not seller_id:
                    print(f"No fallback seller ID for {args.site}.")
                    return 1
                try:
                    from playwright.sync_api import sync_playwright as _  # noqa
                except ImportError:
                    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
                    return 1
                listings = fetch_via_playwright(seller_id)
                source = "playwright"

            DATA_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(listings, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            print(f"  Listings cached → {cache_file}")

        # 2. Match against DB boats
        boats = db.session.query(Boat).all()
        print(f"Loaded {len(boats)} boats from DB")

        matches = match_listings(listings, boats)
        print_report(matches, args.min_score)

        if args.apply:
            updated = apply_matches(matches, args.min_score)
            print(f"✅  {updated} boats updated in DB.")
        else:
            auto_count = sum(
                1 for m in matches
                if m["boat"] and m["score"] >= args.min_score
                and not m["boat"].meli_mla_item_id
            )
            print(f"Dry-run: {auto_count} would be linked. Run with --apply to save.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
