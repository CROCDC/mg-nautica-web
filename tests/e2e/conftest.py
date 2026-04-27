"""Shared fixtures for Playwright E2E tests.

Live server: Flask + SQLite file-based (thread-safe) con datos sembrados.
Viewports:   desktop (800×600), tablet (600×800), mobile (320×568).
Screenshots: tests/screenshots/{name}_{viewport}.jpg  — ignorados por git.
"""
import os
import threading
import time
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from app.factory import create_app
from app.factory import db as _db
from app.models import BoatPhoto, BoatType, Flag
from tests.factories import make_accessory, make_admin, make_boat, make_full_boat

# ── Paths ─────────────────────────────────────────────────────────────────────
SCREENSHOTS = Path(__file__).parent.parent / "screenshots"
TEST_DB     = "/tmp/mg_nautica_e2e.db"

# ── App config ────────────────────────────────────────────────────────────────
E2E_CONFIG = {
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": f"sqlite:///{TEST_DB}",
    "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"check_same_thread": False}},
    "SECRET_KEY": "e2e-test-secret-key",
    "SERVER_NAME": None,
    "WTF_CSRF_ENABLED": False,
}

VIEWPORTS = [
    pytest.param({"name": "desktop", "width": 800, "height": 600},  id="desktop"),
    pytest.param({"name": "tablet",  "width": 600, "height": 800},  id="tablet"),
    pytest.param({"name": "mobile",  "width": 320, "height": 568},  id="mobile"),
]


# ── Session-scoped: app + server + seed ───────────────────────────────────────

@pytest.fixture(scope="session")
def e2e_app():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    app = create_app(test_config=E2E_CONFIG)

    with app.app_context():
        _db.create_all()

        # 6 barcos con fotos (usa picsum como placeholder)
        boat_types = [BoatType.SAILBOAT, BoatType.MOTORBOAT, BoatType.CATAMARAN]
        flags      = [Flag.AR, Flag.UY, Flag.FOREIGN]
        for i in range(6):
            b = make_boat(
                slug=f"velero-test-{i}",
                title=f"Velero Test {i + 1}",
                price_usd=25000 + i * 8000,
                previous_price_usd=30000 + i * 8000 if i % 2 == 0 else None,
                boat_type=boat_types[i % 3],
                flag=flags[i % 3],
                featured=True,
                city_location="Buenos Aires",
                country_location="Argentina",
                year=2010 + i,
                length_m=9.5 + i,
            )
            _db.session.add(b)
            _db.session.flush()
            for j in range(5):
                _db.session.add(BoatPhoto(
                    boat_id=b.id,
                    url=f"https://picsum.photos/seed/boat{i}{j}/800/600",
                    position=j,
                    is_primary=(j == 0),
                ))

        # 1 barco con todos los campos completados (para screenshots ricos)
        full = make_full_boat()
        _db.session.add(full)
        _db.session.flush()
        for j in range(8):
            _db.session.add(BoatPhoto(
                boat_id=full.id,
                url=f"https://picsum.photos/seed/full{j}/800/600",
                position=j,
                is_primary=(j == 0),
            ))

        # 1 barco con muchas fotos (stress test de la galería)
        many = make_boat(
            slug="galeria-test",
            title="Galería Test 24",
            price_usd=50000,
            boat_type=BoatType.SAILBOAT,
            flag=Flag.AR,
            featured=False,
        )
        _db.session.add(many)
        _db.session.flush()
        for j in range(24):
            _db.session.add(BoatPhoto(
                boat_id=many.id,
                url=f"https://picsum.photos/seed/many{j}/800/600",
                position=j,
                is_primary=(j == 0),
            ))

        # 1 accesorio
        _db.session.add(make_accessory())

        # 1 admin
        _db.session.add(make_admin())

        _db.session.commit()

    return app


@pytest.fixture(scope="session")
def live_server_url(e2e_app):
    server = make_server("127.0.0.1", 0, e2e_app)
    port   = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.4)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(scope="session", autouse=True)
def _screenshots_dir():
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)


# ── Viewport fixture (parametrizado × 3) ─────────────────────────────────────

@pytest.fixture(params=VIEWPORTS)
def vp(request, browser, live_server_url):
    """Page a un viewport específico. Cada test que use `vp` corre × 3."""
    info    = request.param
    context = browser.new_context(
        viewport={"width": info["width"], "height": info["height"]},
        locale="es-AR",
    )
    page = context.new_page()
    yield page, live_server_url, info["name"]
    context.close()


# ── Desktop-only page (para tests de interacción) ────────────────────────────

@pytest.fixture
def desktop(browser, live_server_url):
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="es-AR",
    )
    page = context.new_page()
    yield page, live_server_url
    context.close()


@pytest.fixture
def mobile_page(browser, live_server_url):
    context = browser.new_context(
        viewport={"width": 375, "height": 812},
        locale="es-AR",
    )
    page = context.new_page()
    yield page, live_server_url
    context.close()


# ── Boat detail fixture ───────────────────────────────────────────────────────

@pytest.fixture
def boat_detail(browser, live_server_url):
    """Desktop page already navigated to the first boat's detail page.

    Yields (page, live_server_url, slug) so tests can build sub-URLs if needed.
    """
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="es-AR",
    )
    page = context.new_page()
    page.goto(live_server_url + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator("a.boat-card").first.get_attribute("href")
    slug = href.rstrip("/").split("/")[-1]
    page.goto(live_server_url + href)
    page.wait_for_load_state("networkidle")
    yield page, live_server_url, slug
    context.close()


@pytest.fixture(params=VIEWPORTS)
def boat_detail_vp(request, browser, live_server_url):
    """Boat detail page parametrizado × 3 viewports.

    Yields (page, live_server_url, slug, viewport_name).
    """
    info = request.param
    context = browser.new_context(
        viewport={"width": info["width"], "height": info["height"]},
        locale="es-AR",
    )
    page = context.new_page()
    page.goto(live_server_url + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator("a.boat-card").first.get_attribute("href")
    slug = href.rstrip("/").split("/")[-1]
    page.goto(live_server_url + href)
    page.wait_for_load_state("networkidle")
    yield page, live_server_url, slug, info["name"]
    context.close()


# ── Helper ────────────────────────────────────────────────────────────────────

def assert_no_visual_bugs(page) -> None:
    """Fail if common CSS bugs are detected on the current page."""
    # Unexpected strikethrough: any text outside .boat-card-price-old
    violations = page.evaluate("""() => {
        const results = [];
        for (const el of document.querySelectorAll('*')) {
            const cs = window.getComputedStyle(el);
            if (!cs.textDecorationLine.includes('line-through')) continue;
            if (el.closest('.boat-card-price-old, .sidebar-price-old')) continue;
            const text = [...el.childNodes]
                .filter(n => n.nodeType === 3)
                .map(n => n.textContent.trim())
                .join('');
            if (!text) continue;
            results.push({ tag: el.tagName, classes: el.className, text: text.slice(0, 60) });
        }
        return results;
    }""")
    assert violations == [], f"Strikethrough encontrado en elementos inesperados: {violations}"

    # Horizontal overflow: find elements wider than the viewport
    offenders = page.evaluate("""() => {
        const vw = window.innerWidth;
        if (document.documentElement.scrollWidth <= vw + 1) return [];
        const hits = [];
        for (const el of document.querySelectorAll('*')) {
            const r = el.getBoundingClientRect();
            if (r.right > vw + 1 || r.left < -1) {
                hits.push({
                    tag: el.tagName,
                    classes: el.className,
                    right: Math.round(r.right),
                    left: Math.round(r.left),
                    vw,
                });
                if (hits.length >= 5) break;
            }
        }
        return hits;
    }""")
    assert offenders == [], f"Overflow horizontal detectado: {offenders}"


def shot(page, name: str) -> None:
    """Guarda screenshot en tests/screenshots/{name}.png.

    1. Scroll to bottom → fires all IntersectionObserver scroll-reveal animations.
    2. Scroll back to top.
    3. Un-stick the header (position:static) so Playwright's internal scroll for
       full_page capture doesn't ghost it mid-page.
    4. Wait two rAF cycles so the browser reflows and repaints the unstuck header
       before the CDP screenshot is issued — without this the composited sticky
       layer position is still used and the header appears at the viewport offset
       in the stitched image.
    5. Capture, then restore.
    """
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(400)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(200)
    assert_no_visual_bugs(page)
    # Remove sticky from header; wait for layout + paint before screenshot.
    page.evaluate(
        "var h = document.querySelector('.site-header');"
        "if (h) h.dataset._pos = h.style.position || '';"
        "if (h) h.style.position = 'static';"
    )
    page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    path = SCREENSHOTS / f"{name}.jpg"
    page.screenshot(path=str(path), full_page=True, type="jpeg", quality=30, scale="css")
    page.evaluate(
        "var h = document.querySelector('.site-header');"
        "if (h) h.style.position = h.dataset._pos || '';"
    )


@pytest.fixture(params=VIEWPORTS)
def full_boat_vp(request, browser, live_server_url):
    """Bavaria 46 full-specs detail page × 3 viewports."""
    info = request.param
    context = browser.new_context(
        viewport={"width": info["width"], "height": info["height"]},
        locale="es-AR",
    )
    page = context.new_page()
    page.goto(live_server_url + "/boats/bavaria-46-full")
    page.wait_for_load_state("networkidle")
    yield page, live_server_url, info["name"]
    context.close()


@pytest.fixture(params=VIEWPORTS)
def many_photos_vp(request, browser, live_server_url):
    """Barco con 24 fotos × 3 viewports — stress test de la galería."""
    info = request.param
    context = browser.new_context(
        viewport={"width": info["width"], "height": info["height"]},
        locale="es-AR",
    )
    page = context.new_page()
    page.goto(live_server_url + "/boats/galeria-test")
    page.wait_for_load_state("networkidle")
    yield page, live_server_url, info["name"]
    context.close()


@pytest.fixture
def many_photos_detail(browser, live_server_url):
    """Barco con 24 fotos en desktop — tests de interacción."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="es-AR",
    )
    page = context.new_page()
    page.goto(live_server_url + "/boats/galeria-test")
    page.wait_for_load_state("networkidle")
    yield page, live_server_url
    context.close()
