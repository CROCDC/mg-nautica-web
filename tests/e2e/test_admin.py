"""E2E tests for the admin panel (login-gated views).

All tests use the `admin_page` fixture which logs in as admin before yielding
the page, so individual tests don't need to repeat the login flow.
"""
import pytest

from tests.e2e.conftest import shot

ADMIN_EMAIL    = "admin@mgnautica.local"
ADMIN_PASSWORD = "admin-pass"


# ── Shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def admin_page(browser, live_server_url):
    """Desktop page pre-authenticated as admin."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="es-AR",
    )
    page = context.new_page()

    # Log in
    page.goto(live_server_url + "/admin/login")
    page.fill("input[name='email']", ADMIN_EMAIL)
    page.fill("input[name='password']", ADMIN_PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_url("**/admin/", timeout=5000)

    yield page, live_server_url
    context.close()


# ── Login page ────────────────────────────────────────────────────────────────

def test_admin_login_page_renders(browser, live_server_url):
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.goto(live_server_url + "/admin/login")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_login")
    assert page.locator("input[name='email']").count() == 1
    assert page.locator("input[name='password']").count() == 1
    context.close()


def test_admin_login_success(browser, live_server_url):
    """El login correcto redirige al dashboard y éste devuelve 200."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.goto(live_server_url + "/admin/login")
    page.fill("input[name='email']", ADMIN_EMAIL)
    page.fill("input[name='password']", ADMIN_PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_login_success")
    # Debe haber redirigido al dashboard, no quedarse en login ni tirar 500
    assert "/admin/login" not in page.url
    assert page.locator("main, .admin-content").count() >= 1
    context.close()


def test_admin_login_invalid_credentials(browser, live_server_url):
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.goto(live_server_url + "/admin/login")
    page.fill("input[name='email']", "wrong@example.com")
    page.fill("input[name='password']", "wrongpass")
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_login_invalid")
    # Should stay on login page with error
    assert "/admin/login" in page.url
    context.close()


def test_admin_login_redirects_unauthenticated(browser, live_server_url):
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    response = page.goto(live_server_url + "/admin/")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_unauthenticated_redirect")
    # Should redirect to login
    assert "login" in page.url
    context.close()


# ── Dashboard ─────────────────────────────────────────────────────────────────

def test_admin_dashboard(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_dashboard")
    assert page.locator(".admin-dashboard, main").count() >= 1
    # Stats should be visible
    assert page.locator("[class*='stat'], [class*='card'], [class*='metric']").count() >= 1


# ── Boats CRUD views ──────────────────────────────────────────────────────────

def test_admin_boats_list(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_boats_list")
    assert page.locator("table tbody tr, .boat-row, tr").count() >= 1


def test_admin_boats_new_form(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats/new")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_boats_new_form")
    # /admin/boats/new shows a choose page with links to quick and complete forms
    assert page.locator("a[href*='/admin/boats/new/simple']").count() >= 1
    assert page.locator("a[href*='/admin/boats/new/complete']").count() >= 1


def test_admin_boats_edit_form(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats")
    page.wait_for_load_state("networkidle")
    edit_link = page.locator("a[href*='/admin/boats/'][href*='/edit']").first
    if edit_link.count() == 0:
        return
    href = edit_link.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")
    shot(page, "admin_boats_edit_choose")
    # choose page: should offer simple and complete links
    assert page.locator("a[href*='/edit/simple']").count() >= 1
    assert page.locator("a[href*='/edit/complete']").count() >= 1
    # navigate to simple edit and verify form
    page.locator("a[href*='/edit/simple']").first.click()
    page.wait_for_load_state("networkidle")
    shot(page, "admin_boats_edit_simple")
    assert page.locator("form").count() >= 1


# ── Accessories CRUD views ────────────────────────────────────────────────────

def test_admin_accessories_list(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/accessories")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_accessories_list")
    assert page.locator("table tbody tr, tr, .accessory-row").count() >= 1


def test_admin_accessories_new_form(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/accessories/new")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_accessories_new_form")
    assert page.locator("form").count() >= 1


def test_admin_accessories_edit_form(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/accessories")
    page.wait_for_load_state("networkidle")
    edit_link = page.locator("a[href*='/admin/accessories/'][href*='/edit']").first
    if edit_link.count() == 0:
        return
    href = edit_link.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")
    shot(page, "admin_accessories_edit_form")
    assert page.locator("form").count() >= 1


# ── Users CRUD views ──────────────────────────────────────────────────────────

def test_admin_users_list(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/users")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_users_list")
    assert page.locator("table, .user-row, tr").count() >= 1


def test_admin_users_new_form(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/users/new")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_users_new_form")
    assert page.locator("form").count() >= 1
    assert page.locator("input[name='email']").count() >= 1


# ── Inquiries ─────────────────────────────────────────────────────────────────

def test_admin_sale_inquiries(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/sale-inquiries")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_sale_inquiries")
    assert page.locator("main").count() == 1


def test_admin_boat_inquiries(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boat-inquiries")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_boat_inquiries")
    assert page.locator("main").count() == 1


# ── Pending listings ──────────────────────────────────────────────────────────

def test_admin_pending_listings(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/pending-listings")
    page.wait_for_load_state("networkidle")
    shot(page, "admin_pending_listings")
    assert page.locator("main").count() == 1


# ── Logout ────────────────────────────────────────────────────────────────────

def test_admin_logout(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/")
    page.wait_for_load_state("networkidle")
    # Submit the logout form
    page.locator("form[action*='logout'] button, button[form*='logout']").first.click()
    page.wait_for_load_state("networkidle")
    shot(page, "admin_after_logout")
    assert "login" in page.url
