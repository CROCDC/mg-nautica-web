"""E2E tests for photo file upload in the admin panel (boats and accessories).

Uses Playwright's set_input_files() to simulate real browser file selection.
The `admin_page` fixture is defined in conftest.py.
"""
import base64

import pytest

from tests.e2e.conftest import shot

# Minimal 1×1 PNG — valid image file, no external deps
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)


def _fake_png(name: str = "test.png") -> dict:
    return {"name": name, "mimeType": "image/png", "buffer": TINY_PNG}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _go_to_first_boat_edit(page, base: str) -> str | None:
    page.goto(base + "/admin/boats")
    page.wait_for_load_state("networkidle")
    link = page.locator("a[href*='/admin/boats/'][href*='/edit']").first
    if link.count() == 0:
        return None
    href = link.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")
    return href


def _go_to_first_accessory_edit(page, base: str) -> str | None:
    page.goto(base + "/admin/accessories")
    page.wait_for_load_state("networkidle")
    link = page.locator("a[href*='/admin/accessories/'][href*='/edit']").first
    if link.count() == 0:
        return None
    href = link.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")
    return href


# ── New boat selection screen ────────────────────────────────────────────────

def test_choose_screen_renders(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats/new")
    page.wait_for_load_state("networkidle")
    shot(page, "boats_new_choose")
    assert page.locator(".choose-card").count() == 2


def test_choose_screen_simple_link(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats/new")
    page.wait_for_load_state("networkidle")
    cards = page.locator(".choose-card")
    hrefs = [cards.nth(i).get_attribute("href") for i in range(cards.count())]
    assert any("/new/simple" in (h or "") for h in hrefs)


def test_choose_screen_complete_link(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats/new")
    page.wait_for_load_state("networkidle")
    cards = page.locator(".choose-card")
    hrefs = [cards.nth(i).get_attribute("href") for i in range(cards.count())]
    assert any("/new/complete" in (h or "") for h in hrefs)


def test_choose_simple_card_navigates(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats/new")
    page.wait_for_load_state("networkidle")
    page.locator(".choose-card[href*='/new/simple']").click()
    page.wait_for_load_state("networkidle")
    assert "/new/simple" in page.url
    assert page.locator("input[name='title']").count() == 1


def test_choose_complete_card_navigates(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats/new")
    page.wait_for_load_state("networkidle")
    page.locator(".choose-card[href*='/new/complete']").click()
    page.wait_for_load_state("networkidle")
    assert "/new/complete" in page.url
    assert page.locator("select[name='boat_type']").count() == 1


def test_list_new_button_goes_to_choose_screen(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats")
    page.wait_for_load_state("networkidle")
    page.locator("a[href*='/admin/boats/new']").first.click()
    page.wait_for_load_state("networkidle")
    assert page.locator(".choose-card").count() == 2


# ── Boat photo upload ─────────────────────────────────────────────────────────

def test_boat_upload_single_photo_increases_count(admin_page):
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    before = page.locator(".admin-photo").count()
    page.set_input_files("input[name='photos']", [_fake_png("single.png")])
    page.locator("form[action*='photos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")
    shot(page, "boat_upload_single")

    assert page.locator(".admin-photo").count() == before + 1


def test_boat_upload_multiple_photos(admin_page):
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    before = page.locator(".admin-photo").count()
    page.set_input_files("input[name='photos']", [
        _fake_png("a.png"),
        _fake_png("b.png"),
        _fake_png("c.png"),
    ])
    page.locator("form[action*='photos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")
    shot(page, "boat_upload_multiple")

    assert page.locator(".admin-photo").count() == before + 3


def test_boat_uploaded_photo_served_from_uploads(admin_page):
    """Photo uploaded must have src pointing to /uploads/."""
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    page.set_input_files("input[name='photos']", [_fake_png("url-check.png")])
    page.locator("form[action*='photos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    upload_imgs = page.locator(".admin-photo img[src^='/uploads/']")
    assert upload_imgs.count() >= 1


def test_boat_uploaded_photo_is_accessible(admin_page):
    """The /uploads/ URL returned by the server must be reachable (HTTP 200)."""
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    page.set_input_files("input[name='photos']", [_fake_png("access-check.png")])
    page.locator("form[action*='photos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    # Find an upload src and verify it returns 200
    upload_img = page.locator(".admin-photo img[src^='/uploads/']").first
    if upload_img.count() == 0:
        pytest.skip("No se encontró imagen subida")
    src = upload_img.get_attribute("src")
    response = page.request.get(base + src)
    assert response.status == 200


def test_boat_upload_shows_success_flash(admin_page):
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    page.set_input_files("input[name='photos']", [_fake_png("flash-test.png")])
    page.locator("form[action*='photos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    flash = page.locator(".flash, .alert, [class*='flash'], [class*='alert']")
    assert flash.count() >= 1


# ── New boat with photos ──────────────────────────────────────────────────────

def test_new_boat_created_with_photos(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats/new/complete")
    page.wait_for_load_state("networkidle")

    page.fill("input[name='slug']", "e2e-foto-upload")
    page.fill("input[name='title']", "E2E Foto Upload")
    page.select_option("select[name='boat_type']", "sailboat")
    page.select_option("select[name='flag']", "AR")
    page.fill("input[name='price_usd']", "20000")
    page.set_input_files("input[name='photos']", [
        _fake_png("foto1.png"),
        _fake_png("foto2.png"),
    ])

    page.locator("form.admin-form button[type='submit']").first.click()
    page.wait_for_load_state("networkidle")
    shot(page, "new_boat_with_photos")

    assert "/edit" in page.url
    assert page.locator(".admin-photo").count() >= 2


def test_new_boat_without_photos_is_still_created(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/boats/new/complete")
    page.wait_for_load_state("networkidle")

    page.fill("input[name='slug']", "e2e-sin-fotos")
    page.fill("input[name='title']", "E2E Sin Fotos")
    page.select_option("select[name='boat_type']", "motorboat")
    page.select_option("select[name='flag']", "UY")
    page.fill("input[name='price_usd']", "8000")

    page.locator("form.admin-form button[type='submit']").first.click()
    page.wait_for_load_state("networkidle")

    assert "/edit" in page.url
    assert page.locator(".admin-photo").count() == 0


# ── Accessory photo upload ────────────────────────────────────────────────────

def test_accessory_upload_shows_preview_after_save(admin_page):
    page, base = admin_page
    href = _go_to_first_accessory_edit(page, base)
    if href is None:
        pytest.skip("No hay accesorios para editar")

    page.set_input_files("input[name='photo']", [_fake_png("accesorio.png")])
    page.locator("form.admin-form button[type='submit']").click()
    page.wait_for_load_state("networkidle")
    shot(page, "accessory_photo_upload")

    # Reload edit page — photo preview should appear
    page.goto(base + href)
    page.wait_for_load_state("networkidle")
    preview = page.locator("label img[src*='/uploads/']")
    assert preview.count() >= 1


def test_accessory_upload_photo_is_accessible(admin_page):
    """Uploaded photo URL for accessory must return HTTP 200."""
    page, base = admin_page
    href = _go_to_first_accessory_edit(page, base)
    if href is None:
        pytest.skip("No hay accesorios para editar")

    page.set_input_files("input[name='photo']", [_fake_png("acc-access.png")])
    page.locator("form.admin-form button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    page.goto(base + href)
    page.wait_for_load_state("networkidle")

    img = page.locator("label img[src*='/uploads/']").first
    if img.count() == 0:
        pytest.skip("No se encontró preview de imagen")
    src = img.get_attribute("src")
    resp = page.request.get(base + src)
    assert resp.status == 200


def test_new_accessory_with_photo(admin_page):
    page, base = admin_page
    page.goto(base + "/admin/accessories/new")
    page.wait_for_load_state("networkidle")

    page.fill("input[name='slug']", "e2e-acc-con-foto")
    page.fill("input[name='title']", "E2E Accesorio Con Foto")
    page.select_option("select[name='category']", index=0)
    page.fill("input[name='price_usd']", "75")
    page.fill("input[name='stock']", "3")
    page.set_input_files("input[name='photo']", [_fake_png("acc-nueva.png")])

    page.locator("form.admin-form button[type='submit']").click()
    page.wait_for_load_state("networkidle")
    shot(page, "new_accessory_with_photo")

    # Redirect to edit, photo preview visible
    assert "/edit" in page.url
    preview = page.locator("label img[src*='/uploads/']")
    assert preview.count() >= 1
