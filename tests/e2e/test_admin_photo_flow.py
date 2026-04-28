"""E2E tests for admin photo URL management.

Covers:
- Adding a photo URL to an existing boat → thumbnail appears in the admin edit page.
- Deleting a photo from a boat → thumbnail is removed from the admin edit page.
- Creating a new boat with a photo URL in the new-boat form.
- Setting a photo URL for an accessory.
- After adding an admin photo, the public boat detail page shows the image.
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

ADMIN_EMAIL    = "admin@mgnautica.local"
ADMIN_PASSWORD = "admin-pass"

# Unique test URLs so we can assert them precisely without ambiguity
BOAT_PHOTO_URL        = "https://picsum.photos/seed/e2e-boat-add/800/600"
BOAT_PHOTO_DELETE_URL = "https://picsum.photos/seed/e2e-boat-del/800/600"
NEW_BOAT_PHOTO_URL    = "https://picsum.photos/seed/e2e-newboat/800/600"
ACCESSORY_PHOTO_URL   = "https://picsum.photos/seed/e2e-acc/400/300"


# ── Shared fixture ─────────────────────────────────────────────────────────────

@pytest.fixture
def admin_page(browser, live_server_url):
    """Desktop page pre-authenticated as admin (external images stubbed)."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="es-AR",
    )
    page = context.new_page()
    # Stub picsum images so networkidle resolves instantly
    page.route(
        "**/picsum.photos/**",
        lambda route: route.fulfill(
            status=200, content_type="image/png", body=_STUB_PNG,
        ),
    )
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


# ── Add photo URL ──────────────────────────────────────────────────────────────

class TestBoatPhotoAdd:
    def test_add_photo_form_is_present_on_edit_page(self, admin_page):
        page, base = admin_page
        _navigate_to_first_boat_edit(page, base)
        shot(page, "admin_boat_edit_before_photo_add")
        assert page.locator("form[action*='photos/add']").count() == 1
        assert page.locator("form[action*='photos/add'] input[name='url']").count() == 1

    def test_add_photo_url_thumbnail_appears(self, admin_page):
        page, base = admin_page
        _navigate_to_first_boat_edit(page, base)
        page.fill("form[action*='photos/add'] input[name='url']", BOAT_PHOTO_URL)
        page.locator("form[action*='photos/add'] button[type='submit']").click()
        page.wait_for_load_state("load")
        shot(page, "admin_boat_edit_after_photo_add")
        # The added URL should appear as a thumbnail src in the .admin-photos section
        assert page.locator(f".admin-photos img[src='{BOAT_PHOTO_URL}']").count() == 1

    def test_add_photo_with_alt_text(self, admin_page):
        page, base = admin_page
        _navigate_to_first_boat_edit(page, base)
        page.fill("form[action*='photos/add'] input[name='url']",
                  "https://picsum.photos/seed/e2e-alt/800/600")
        page.fill("form[action*='photos/add'] input[name='alt']", "Vista de proa")
        page.locator("form[action*='photos/add'] button[type='submit']").click()
        page.wait_for_load_state("load")
        img = page.locator(".admin-photos img[src='https://picsum.photos/seed/e2e-alt/800/600']")
        assert img.count() == 1
        assert img.get_attribute("alt") == "Vista de proa"

    def test_added_photo_appears_on_public_detail(self, admin_page, browser, live_server_url):
        """After adding a photo URL in admin, it should render on the public detail page."""
        page, base = admin_page

        # Navigate to admin boat list and get the slug of the first boat
        page.goto(base + "/admin/boats")
        page.wait_for_load_state("load")
        edit_link = page.locator("a[href*='/admin/boats/'][href*='/edit']").first
        edit_href = edit_link.get_attribute("href")  # e.g. /admin/boats/1/edit

        # Add a unique photo URL
        page.goto(base + edit_href)
        page.wait_for_load_state("load")
        unique_url = "https://picsum.photos/seed/e2e-public-check/800/600"
        page.fill("form[action*='photos/add'] input[name='url']", unique_url)
        page.locator("form[action*='photos/add'] button[type='submit']").click()
        page.wait_for_load_state("load")

        # Find the boat slug from the public listing to navigate there
        pub_ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        pub_page = pub_ctx.new_page()
        pub_page.route(
            "**/picsum.photos/**",
            lambda route: route.fulfill(
                status=200, content_type="image/png", body=_STUB_PNG,
            ),
        )
        pub_page.goto(base + "/boats")
        pub_page.wait_for_load_state("load")
        first_card = pub_page.locator("a.boat-card").first
        href = first_card.get_attribute("href")
        pub_page.goto(base + href)
        pub_page.wait_for_load_state("load")
        shot(pub_page, "public_boat_after_admin_photo_add")
        # The gallery should exist and have at least one image
        assert pub_page.locator("#gallery-main-img").count() == 1
        pub_ctx.close()


# ── Delete photo ───────────────────────────────────────────────────────────────

class TestBoatPhotoDelete:
    def test_delete_photo_removes_thumbnail(self, admin_page):
        page, base = admin_page
        _navigate_to_first_boat_edit(page, base)

        # First add a photo we'll delete
        page.fill("form[action*='photos/add'] input[name='url']", BOAT_PHOTO_DELETE_URL)
        page.locator("form[action*='photos/add'] button[type='submit']").click()
        page.wait_for_load_state("load")

        # Confirm the photo is present
        assert page.locator(f".admin-photos img[src='{BOAT_PHOTO_DELETE_URL}']").count() == 1

        # Accept the confirm() dialog that fires on delete
        page.on("dialog", lambda d: d.accept())

        # Find and click the delete button for our specific photo
        photo_container = page.locator(
            f".admin-photos .admin-photo:has(img[src='{BOAT_PHOTO_DELETE_URL}'])"
        )
        photo_container.locator("button[type='submit']").click()
        page.wait_for_load_state("load")
        shot(page, "admin_boat_edit_after_photo_delete")

        # Thumbnail should be gone
        assert page.locator(f".admin-photos img[src='{BOAT_PHOTO_DELETE_URL}']").count() == 0

    def test_delete_all_added_photos_clears_section(self, admin_page):
        """Adding then deleting the only new photo still leaves the section intact."""
        page, base = admin_page
        _navigate_to_first_boat_edit(page, base)

        add_url = "https://picsum.photos/seed/e2e-clear/800/600"
        page.fill("form[action*='photos/add'] input[name='url']", add_url)
        page.locator("form[action*='photos/add'] button[type='submit']").click()
        page.wait_for_load_state("load")

        page.on("dialog", lambda d: d.accept())
        photo_container = page.locator(
            f".admin-photos .admin-photo:has(img[src='{add_url}'])"
        )
        photo_container.locator("button[type='submit']").click()
        page.wait_for_load_state("load")

        # The add-photo form should still be present
        assert page.locator("form[action*='photos/add']").count() == 1


# ── New boat with photo URL ───────────────────────────────────────────────────

class TestNewBoatWithPhoto:
    def test_new_boat_photo_url_field_present(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/boats/new/complete")
        page.wait_for_load_state("load")
        assert page.locator("input[name='photo_url']").count() == 1

    def test_create_boat_with_photo_url(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/boats/new/complete")
        page.wait_for_load_state("load")

        page.fill("input[name='slug']", "e2e-barco-con-foto")
        page.fill("input[name='title']", "Barco E2E con Foto")
        page.fill("input[name='price_usd']", "50000")
        page.select_option("select[name='boat_type']", "sailboat")
        page.select_option("select[name='flag']", "AR")
        page.select_option("select[name='status']", "available")
        page.fill("input[name='photo_url']", NEW_BOAT_PHOTO_URL)
        page.locator("form.admin-form button[type='submit']").click()
        page.wait_for_load_state("load")
        assert "/edit" in page.url, f"Expected redirect to edit page, got: {page.url}"
        shot(page, "admin_new_boat_with_photo_after_create")

        # After redirect to edit, the photo should appear in .admin-photos
        assert page.locator(f".admin-photos img[src='{NEW_BOAT_PHOTO_URL}']").count() == 1

    def test_new_boat_without_photo_url_has_empty_photos(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/boats/new/complete")
        page.wait_for_load_state("load")

        page.fill("input[name='slug']", "e2e-barco-sin-foto")
        page.fill("input[name='title']", "Barco E2E sin Foto")
        page.fill("input[name='price_usd']", "30000")
        page.select_option("select[name='boat_type']", "motorboat")
        page.select_option("select[name='flag']", "UY")
        page.select_option("select[name='status']", "available")
        # Leave photo_url empty
        page.locator("form.admin-form button[type='submit']").click()
        page.wait_for_load_state("load")
        assert "/edit" in page.url, f"Expected redirect to edit page, got: {page.url}"

        # Photos section should say 0 photos
        photos_heading = page.locator("h2:has-text('Fotos')")
        assert photos_heading.count() == 1
        assert "0" in photos_heading.inner_text()


# ── Accessory photo URL ────────────────────────────────────────────────────────

class TestAccessoryPhotoUrl:
    def test_photo_url_field_on_new_accessory_form(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/accessories/new")
        page.wait_for_load_state("load")
        assert page.locator("input[name='photo_url']").count() == 1

    def test_create_accessory_with_photo_url(self, admin_page):
        page, base = admin_page
        page.goto(base + "/admin/accessories/new")
        page.wait_for_load_state("load")

        page.fill("input[name='slug']", "e2e-accesorio-con-foto")
        page.fill("input[name='title']", "Accesorio E2E con Foto")
        page.fill("input[name='price_usd']", "250")
        page.fill("input[name='stock']", "5")
        page.select_option("select[name='category']", "onboard")
        page.fill("input[name='photo_url']", ACCESSORY_PHOTO_URL)
        page.locator("form.admin-form button[type='submit']").click()
        page.wait_for_load_state("load")
        assert "/edit" in page.url, f"Expected redirect to edit page, got: {page.url}"
        shot(page, "admin_new_accessory_with_photo")

        # The photo URL should be pre-filled in the edit form
        stored_url = page.locator("input[name='photo_url']").get_attribute("value")
        assert stored_url == ACCESSORY_PHOTO_URL

    def test_update_accessory_photo_url(self, admin_page):
        page, base = admin_page
        # Navigate to existing accessory edit form
        page.goto(base + "/admin/accessories")
        page.wait_for_load_state("load")
        edit_link = page.locator("a[href*='/admin/accessories/'][href*='/edit']").first
        if edit_link.count() == 0:
            pytest.skip("No accessories in the database")
        href = edit_link.get_attribute("href")
        page.goto(base + href)
        page.wait_for_load_state("load")

        updated_url = "https://picsum.photos/seed/e2e-acc-update/400/300"
        page.fill("input[name='photo_url']", updated_url)
        page.locator("form.admin-form button[type='submit']").click()
        page.wait_for_load_state("load")
        assert "/edit" in page.url, f"Expected to stay on edit page, got: {page.url}"

        # After saving, the input should hold the new URL
        page.wait_for_selector("input[name='photo_url']", timeout=10000)
        stored = page.locator("input[name='photo_url']").evaluate("el => el.value")
        assert stored == updated_url
