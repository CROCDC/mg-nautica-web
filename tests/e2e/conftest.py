"""Shared fixtures for Playwright E2E tests.

Live server: Flask + SQLite file-based (thread-safe) con datos sembrados.
Viewports:   desktop (1280×800), tablet (768×1024), mobile (375×812).
Screenshots: tests/screenshots/{name}_{viewport}.png  — ignorados por git.
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
from tests.factories import make_accessory, make_admin, make_boat

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
    pytest.param({"name": "desktop", "width": 1280, "height": 800},  id="desktop"),
    pytest.param({"name": "tablet",  "width": 768,  "height": 1024}, id="tablet"),
    pytest.param({"name": "mobile",  "width": 375,  "height": 812},  id="mobile"),
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

def shot(page, name: str) -> None:
    """Guarda screenshot en tests/screenshots/{name}.png.

    Scroll to bottom then back to top first so IntersectionObserver-based
    scroll-reveal animations fire and all cards become visible.
    """
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(400)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(200)
    path = SCREENSHOTS / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
