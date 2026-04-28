"""E2E tests for admin photo file upload management.

Covers:
- Boat edit page shows file-upload form to add photos.
- Uploading a photo file creates a thumbnail in the admin edit page.
- Deleting a photo from a boat removes the thumbnail.
- Creating a new boat with a photo file via the complete form.
- Uploading a photo file for an accessory.
- After uploading a photo, the public boat detail page shows the gallery.
"""
import struct
import zlib

import pytest

from tests.e2e.conftest import shot


def _make_stub_png() -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(name + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)
    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    raw  = b"".join(b"\x00" + bytes([0, 100, 200] * 2) for _ in range(2))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


_STUB_PNG = _make_stub_png()
_STUB_FILE = {"name": "test.png", "mimeType": "image/png", "buffer": _STUB_PNG}

ADMIN_EMAIL    = "admin@mgnautica.local"
ADMIN_PASSWORD = "admin-pass"


# ── Shared fixture ─────────────────────────────────────────────────────────────

@pytest.fixture
def admin_page(browser, live_server_url):
    """Desktop page pre-authenticated as admin."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="es-AR",
    )
    page = context.new_page()
    page.goto(live_server_url + "/admin/login")
    page.fill("input[name='email']", ADMIN_EMAIL)
    page.fill("input[name='password']", ADMIN_PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_url("**/admin/", timeout=5000)
    yield page, live_server_url
    context.close()


def _navigate_to_first_boat_edit(page, base):
    """Go to the first boat's edit page; return the boat edit URL."""
    page.goto(base + "/admin/boats")
    page.wait_for_load_state("load")
    edit_link = page.locator("a[href*='/admin/boats/'][href*='/edit']").first
    href = edit_link.get_attribute("href")
    edit_url = base + href
    page.goto(edit_url)
    page.wait_for_load_state("load")
    return edit_url


# ── Add photo via file upload ──────────────────────────────────────────────────

class TestBoatPhotoAdd:
    def test_add_photo_form_is_present_on_edit_page(self, admin_page):
        page, base = admin_page
        _navigate_to_first_boat_edit(page, base)
        shot(page, "admin_boat_edit_before_photo_add")
        assert page.locator("form[action*='photos/add']").count() == 1
        assert page.locator("form[action*='photos/add'] input[type='file']").count() == 1

    def test_add_photo_file_thumbnail_appears(self, admin_page):
        page, base = admin_page
        _navigate_to_first_boat_edit(page, base)
        page.set_input_files("form[action*='photos/add'] input[type='file']", _STUB_FILE)
        page.locator("form[action*='photos/add'] button[type='submit']").click()
        page.wait_for_load_state("load")
        shot(page, "admin_boat_edit_after_photo_add")
        assert page.locator(".admin-photos img").count() >= 1

    def test_add_photo_creates_local_path(self, admin_page):
        page, base = admin_page
        _navigate_to_first_boat_edit(page, base)
        page.set_input_files("form[action*='photos/add'] input[type='file']", _STUB_FILE)
        page.locator("form[action*='photos/add'] button[type='submit']").click()
        page.wait_for_load_state("load")
        # Uploaded photos have local /uploads/ paths, not external URLs
        imgs = page.locator(".admin-photos img")
        assert imgs.count() >= 1
        src = imgs.last.get_attribute("src")
        assert src and src.startswith("/uploads/"), f"Expected /uploads/ path, got: {src}"

    def test_added_photo_appears_on_public_detail(self, admin_page, browser, live_server_url):
        """After uploading a photo in admin, it renders on the public detail page."""
        page, base = admin_page

        page.goto(base + "/admin/boats")
        page.wait_for_load_state("load")
        edit_link = page.locator("a[href*='/admin/boats/'][href*='/edit']").first
        edit_href = edit_link.get_attribute("href")

        page.goto(base + edit_href)
        page.wait_for_load_state("load")
        page.set_input_files("form[action*='photos/add'] input[type='file']", _STUB_FILE)
        page.locator("form[action*='photos/add'] button[type='submit']").click()
        page.wait_for_load_state("load")

        pub_ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        pub_page = pub_ctx.new_page()
        pub_page.goto(base + "/boats")
        pub_page.wait_for_load_state("load")
        first_card = pub_page.locator("a.boat-card").first
        href = first_card.get_attribute("href")
        pub_page.goto(base + href)
        pub_page.wait_for_load_state("load")
        shot(pub_page, "public_boat_after_admin_photo_add")
        assert pub_page.locator("#gallery-main-img").count() == 1
        pub_ctx.close()


# ── Delete photo ───────────────────────────────────────────────────────────────

class TestBoatPhotoDelete:
    def test_delete_photo_removes_thumbnail(self, admin_page):
        page, base = admin_page
        _navigate_to_first_boat_edit(page, base)

        # Add a photo to delete
        page.set_input_files("form[action*='photos/add'] input[type='file']", _STUB_FILE)
        page.locator("form[action*='photos/add'] button[type='submit']").click()
        page.wait_for_load_state("load")
        count_before = page.locator(".admin-photos .admin-photo").count()
        assert count_before >= 1

        page.on("dialog", lambda d: d.accept())
        page.locator(".admin-photos .admin-photo").last.locator("button[type='submit']").click()
        page.wait_for_load_state("load")
        shot(page, "admin_boat_edit_after_photo_delete")

        assert page.locator(".admin-photos .admin-photo").count() < count_before

    def test_delete_all_added_photos_leaves_form_intact(self, admin_page):
        """Adding then deleting the only photo still leaves the add-photo form."""
        page, base = admin_page
        _navigate_to_first_boat_edit(page, base)

        page.set_input_files("form[action*='photos/add'] input[type='file']", _STUB_FILE)
        page.locator("form[action*='photos/add'] button[type='submit']").click()
        page.wait_for_load_state("load")

        page.on("dialog", lambda d: d.accept())
        page.locator(".admin-photos .admin-photo").last.locator("button[type='submit']").click()
        page.wait_for_load_state("load")

        assert page.locator("form[action*='photos/add']").count() == 1


# ── New boat with photo file ───────────────────────────────────────────────────

class TestNewBoatWithPhoto:
    def test_new_boat_photo_file_input_present(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/boats/new/complete")
        page.wait_for_load_state("load")
        assert page.locator("input[type='file'][name='photos']").count() == 1

    def test_create_boat_with_photo_file(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/boats/new/complete")
        page.wait_for_load_state("load")

        page.fill("input[name='slug']", "e2e-barco-con-foto")
        page.fill("input[name='title']", "Barco E2E con Foto")
        page.fill("input[name='price_usd']", "50000")
        page.select_option("select[name='boat_type']", "sailboat")
        page.select_option("select[name='flag']", "AR")
        page.select_option("select[name='status']", "available")
        page.set_input_files("input[type='file'][name='photos']", _STUB_FILE)
        page.locator("form.admin-form button[type='submit']").click()
        page.wait_for_load_state("load")
        assert "/edit" in page.url, f"Expected redirect to edit page, got: {page.url}"
        shot(page, "admin_new_boat_with_photo_after_create")

        assert page.locator(".admin-photos img").count() >= 1

    def test_new_boat_without_photo_has_empty_photos_section(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/boats/new/complete")
        page.wait_for_load_state("load")

        page.fill("input[name='slug']", "e2e-barco-sin-foto")
        page.fill("input[name='title']", "Barco E2E sin Foto")
        page.fill("input[name='price_usd']", "30000")
        page.select_option("select[name='boat_type']", "motorboat")
        page.select_option("select[name='flag']", "UY")
        page.select_option("select[name='status']", "available")
        page.locator("form.admin-form button[type='submit']").click()
        page.wait_for_load_state("load")
        assert "/edit" in page.url, f"Expected redirect to edit page, got: {page.url}"

        photos_heading = page.locator("h2:has-text('Fotos')")
        assert photos_heading.count() == 1
        assert "0" in photos_heading.inner_text()


# ── Accessory photo file upload ────────────────────────────────────────────────

class TestAccessoryPhoto:
    def test_photo_file_input_on_new_accessory_form(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/accessories/new")
        page.wait_for_load_state("load")
        assert page.locator("input[type='file'][name='photo']").count() == 1

    def test_create_accessory_with_photo_file(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/accessories/new")
        page.wait_for_load_state("load")

        page.fill("input[name='slug']", "e2e-accesorio-con-foto")
        page.fill("input[name='title']", "Accesorio E2E con Foto")
        page.fill("input[name='price_usd']", "250")
        page.fill("input[name='stock']", "5")
        page.select_option("select[name='category']", "onboard")
        page.set_input_files("input[type='file'][name='photo']", _STUB_FILE)
        page.locator("form.admin-form button[type='submit']").click()
        page.wait_for_load_state("load")
        assert "/edit" in page.url, f"Expected redirect to edit page, got: {page.url}"
        shot(page, "admin_new_accessory_with_photo")

        assert page.locator("img[src*='/uploads/']").count() >= 1

    def test_update_accessory_photo(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/accessories")
        page.wait_for_load_state("load")
        edit_link = page.locator("a[href*='/admin/accessories/'][href*='/edit']").first
        if edit_link.count() == 0:
            pytest.skip("No accessories in the database")
        href = edit_link.get_attribute("href")
        page.goto(base + href)
        page.wait_for_load_state("load")

        page.set_input_files("input[type='file'][name='photo']",
                             {"name": "updated.png", "mimeType": "image/png", "buffer": _STUB_PNG})
        page.locator("form.admin-form button[type='submit']").click()
        page.wait_for_load_state("load")
        assert "/edit" in page.url, f"Expected to stay on edit page, got: {page.url}"
        assert page.locator("img[src*='/uploads/']").count() >= 1
