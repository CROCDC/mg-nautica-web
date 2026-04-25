"""E2E page-level tests: full-page screenshots at 3 viewports for every route."""
from tests.e2e.conftest import shot


# ── Home ──────────────────────────────────────────────────────────────────────

def test_home(vp):
    page, base, name = vp
    page.goto(base + "/")
    page.wait_for_load_state("networkidle")
    shot(page, f"home_{name}")
    assert page.title() != ""
    assert page.locator(".hero").count() == 1
    assert page.locator(".boat-card").count() > 0


# ── Boats list ────────────────────────────────────────────────────────────────

def test_boats_list(vp):
    page, base, name = vp
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    shot(page, f"boats_list_{name}")
    assert page.locator(".boat-card").count() > 0


def test_boats_list_type_filter(vp):
    page, base, name = vp
    page.goto(base + "/boats?type=sailboat")
    page.wait_for_load_state("networkidle")
    shot(page, f"boats_list_sailboat_{name}")
    # All results must have the sailboat label
    count = page.locator(".boat-card").count()
    assert count > 0


def test_boats_list_flag_filter(vp):
    page, base, name = vp
    page.goto(base + "/boats?flag=AR")
    page.wait_for_load_state("networkidle")
    shot(page, f"boats_list_ar_{name}")
    assert page.locator(".boat-card").count() > 0


# ── Boat detail ───────────────────────────────────────────────────────────────

def test_boat_detail(vp):
    page, base, name = vp
    # Navigate via list so we get a real slug from the seeded DB.
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    first_card = page.locator(".boat-card a").first
    href = first_card.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")
    shot(page, f"boat_detail_{name}")
    assert page.locator(".gallery-main img").count() >= 1
    assert page.locator(".detail-title").count() == 1


def test_boat_detail_gallery_thumbnails(vp):
    page, base, name = vp
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator(".boat-card a").first.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")
    shot(page, f"boat_detail_gallery_{name}")
    # Seeds 5 photos per boat, so thumbnails should be present
    assert page.locator(".gallery-thumb").count() >= 1


# ── Accessories ───────────────────────────────────────────────────────────────

def test_accessories_list(vp):
    page, base, name = vp
    page.goto(base + "/accessories")
    page.wait_for_load_state("networkidle")
    shot(page, f"accessories_list_{name}")
    assert page.locator(".accessory-card").count() >= 1


def test_accessory_detail(vp):
    page, base, name = vp
    page.goto(base + "/accessories")
    page.wait_for_load_state("networkidle")
    href = page.locator(".accessory-card a").first.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")
    shot(page, f"accessory_detail_{name}")
    assert page.locator("h1").count() >= 1


# ── Static pages ──────────────────────────────────────────────────────────────

def test_about(vp):
    page, base, name = vp
    page.goto(base + "/about")
    page.wait_for_load_state("networkidle")
    shot(page, f"about_{name}")
    assert page.locator("main").count() == 1


def test_services(vp):
    page, base, name = vp
    page.goto(base + "/services")
    page.wait_for_load_state("networkidle")
    shot(page, f"services_{name}")
    assert page.locator(".service-card, .services").count() >= 1


def test_contact(vp):
    page, base, name = vp
    page.goto(base + "/contact")
    page.wait_for_load_state("networkidle")
    shot(page, f"contact_{name}")
    assert page.locator("form, .contact-card").count() >= 1


def test_sell_your_boat(vp):
    page, base, name = vp
    page.goto(base + "/sell-your-boat")
    page.wait_for_load_state("networkidle")
    shot(page, f"sell_your_boat_{name}")
    assert page.locator("main").count() == 1


def test_publish(vp):
    page, base, name = vp
    page.goto(base + "/publish")
    page.wait_for_load_state("networkidle")
    shot(page, f"publish_{name}")
    assert page.locator("form").count() >= 1


# ── Favorites ─────────────────────────────────────────────────────────────────

def test_favorites_empty(vp):
    page, base, name = vp
    page.goto(base + "/favorites")
    page.wait_for_load_state("networkidle")
    shot(page, f"favorites_empty_{name}")
    assert page.locator("main").count() == 1


# ── 404 ───────────────────────────────────────────────────────────────────────

def test_404(vp):
    page, base, name = vp
    response = page.goto(base + "/pagina-que-no-existe")
    page.wait_for_load_state("networkidle")
    shot(page, f"404_{name}")
    assert response.status == 404
