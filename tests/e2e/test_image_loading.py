"""E2E tests for image loading on public pages.

Checks that:
- The gallery main image on boat detail has a non-empty src.
- All thumbnails in the gallery have non-empty src attributes.
- Clicking a thumbnail updates the main image src (JS gallery behaviour).
- The boat list card images (if present) carry a non-empty src.
- Boat detail with all specs has all gallery thumbnails rendered.

Performance note: we intercept picsum.photos requests and respond with a tiny
PNG so the browser resolves images instantly without hitting the network.  This
keeps tests fast and deterministic while still validating HTML structure and JS
behaviour.
"""
import struct
import zlib

import pytest

from tests.e2e.conftest import shot


# ── Minimal inline PNG (2×2 pixels) ──────────────────────────────────────────

def _make_png() -> bytes:
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


STUB_PNG = _make_png()


# ── Helper: create a fast page with stubbed external images ────────────────────

def _stub_images(page) -> None:
    """Respond to every picsum.photos request with a tiny local PNG."""
    page.route(
        "**/picsum.photos/**",
        lambda route: route.fulfill(
            status=200,
            content_type="image/png",
            body=STUB_PNG,
        ),
    )


def _go_boat_detail(page, base: str) -> str:
    """Navigate to the first boat detail; return slug."""
    _stub_images(page)
    page.goto(base + "/boats")
    page.wait_for_load_state("load")
    href = page.locator("a.boat-card").first.get_attribute("href")
    slug = href.rstrip("/").split("/")[-1]
    page.goto(base + href)
    page.wait_for_load_state("load")
    return slug


def _go_full_boat(page, base: str) -> None:
    _stub_images(page)
    page.goto(base + "/boats/bavaria-46-full")
    page.wait_for_load_state("load")


# ── Gallery main image ────────────────────────────────────────────────────────

class TestGalleryMainImage:
    def test_main_image_element_present(self, desktop):
        page, base = desktop
        _go_boat_detail(page, base)
        assert page.locator("#gallery-main-img").count() == 1

    def test_main_image_has_non_empty_src(self, desktop):
        page, base = desktop
        _go_boat_detail(page, base)
        src = page.locator("#gallery-main-img").get_attribute("src")
        assert src and len(src) > 0, f"Main gallery image has empty src: {src!r}"

    def test_main_image_src_is_url(self, desktop):
        page, base = desktop
        _go_boat_detail(page, base)
        src = page.locator("#gallery-main-img").get_attribute("src")
        assert src.startswith("http") or src.startswith("/"), (
            f"Unexpected src format: {src!r}"
        )

    def test_main_image_is_visible(self, desktop):
        page, base = desktop
        _go_boat_detail(page, base)
        assert page.locator("#gallery-main-img").is_visible()

    def test_main_image_screenshot(self, desktop):
        page, base = desktop
        _go_boat_detail(page, base)
        shot(page, "gallery_main_image")


# ── Gallery thumbnails ────────────────────────────────────────────────────────

class TestGalleryThumbnails:
    def test_thumbnails_present(self, desktop):
        page, base = desktop
        _go_boat_detail(page, base)
        # Seeded boats have 5 photos each, so thumbnails should appear
        thumbs = page.locator(".gallery-thumb")
        assert thumbs.count() > 0, "No .gallery-thumb divs found"

    def test_each_thumbnail_has_img_with_src(self, desktop):
        page, base = desktop
        _go_boat_detail(page, base)
        thumb_imgs = page.locator(".gallery-thumb img")
        count = thumb_imgs.count()
        assert count > 0, "No <img> inside .gallery-thumb"
        for i in range(count):
            src = thumb_imgs.nth(i).get_attribute("src")
            assert src and len(src) > 0, f"Thumbnail img {i} has empty src"

    def test_thumbnail_click_changes_main_image(self, desktop):
        page, base = desktop
        _go_boat_detail(page, base)
        thumb_imgs = page.locator(".gallery-thumb img")
        if thumb_imgs.count() < 2:
            pytest.skip("Need at least 2 thumbnails")
        initial_src = page.locator("#gallery-main-img").get_attribute("src")
        # Click the second thumbnail (the <div> wrapper handles onclick)
        page.locator(".gallery-thumb").nth(1).click()
        page.wait_for_timeout(300)
        new_src = page.locator("#gallery-main-img").get_attribute("src")
        assert new_src != initial_src, (
            "Main image src did not change after thumbnail click"
        )

    def test_thumbnail_screenshot(self, desktop):
        page, base = desktop
        _go_boat_detail(page, base)
        shot(page, "gallery_thumbnails")


# ── Gallery at multiple viewports ────────────────────────────────────────────

class TestGalleryAllViewports:
    def test_gallery_main_img_src_desktop(self, browser, live_server_url):
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        _go_boat_detail(page, live_server_url)
        src = page.locator("#gallery-main-img").get_attribute("src")
        assert src and len(src) > 0
        shot(page, "gallery_desktop")
        ctx.close()

    def test_gallery_main_img_src_tablet(self, browser, live_server_url):
        ctx = browser.new_context(viewport={"width": 768, "height": 1024})
        page = ctx.new_page()
        _go_boat_detail(page, live_server_url)
        src = page.locator("#gallery-main-img").get_attribute("src")
        assert src and len(src) > 0
        shot(page, "gallery_tablet")
        ctx.close()

    def test_gallery_main_img_src_mobile(self, browser, live_server_url):
        ctx = browser.new_context(viewport={"width": 375, "height": 812})
        page = ctx.new_page()
        _go_boat_detail(page, live_server_url)
        src = page.locator("#gallery-main-img").get_attribute("src")
        assert src and len(src) > 0
        shot(page, "gallery_mobile")
        ctx.close()


# ── Full-spec boat (Bavaria 46 — 8 photos) ────────────────────────────────────

class TestFullBoatGallery:
    def test_has_multiple_thumbnails(self, desktop):
        page, base = desktop
        _go_full_boat(page, base)
        thumb_imgs = page.locator(".gallery-thumb img")
        assert thumb_imgs.count() >= 2, "Expected 8 thumbnails on Bavaria 46"

    def test_all_thumbnail_srcs_set(self, desktop):
        page, base = desktop
        _go_full_boat(page, base)
        thumb_imgs = page.locator(".gallery-thumb img")
        for i in range(thumb_imgs.count()):
            src = thumb_imgs.nth(i).get_attribute("src")
            assert src and len(src) > 0, f"Full boat thumbnail {i} has empty src"

    def test_main_img_src_set(self, desktop):
        page, base = desktop
        _go_full_boat(page, base)
        src = page.locator("#gallery-main-img").get_attribute("src")
        assert src and len(src) > 0

    def test_screenshot_full_boat(self, desktop):
        page, base = desktop
        _go_full_boat(page, base)
        shot(page, "gallery_full_boat")


# ── Boat list ─────────────────────────────────────────────────────────────────

class TestBoatListImages:
    def test_boat_cards_present(self, desktop):
        page, base = desktop
        _stub_images(page)
        page.goto(base + "/boats")
        page.wait_for_load_state("load")
        assert page.locator("a.boat-card").count() > 0

    def test_boat_card_imgs_have_src_if_present(self, desktop):
        page, base = desktop
        _stub_images(page)
        page.goto(base + "/boats")
        page.wait_for_load_state("load")
        card_imgs = page.locator("a.boat-card img")
        if card_imgs.count() == 0:
            pytest.skip("Boat cards use CSS backgrounds, no <img> elements")
        for i in range(card_imgs.count()):
            src = card_imgs.nth(i).get_attribute("src")
            assert src and len(src) > 0, f"Card img {i} has empty src"

    def test_navigable_to_boat_detail(self, desktop):
        page, base = desktop
        _stub_images(page)
        page.goto(base + "/boats")
        page.wait_for_load_state("load")
        href = page.locator("a.boat-card").first.get_attribute("href")
        page.goto(base + href)
        page.wait_for_load_state("load")
        assert page.locator("#gallery-main-img").count() == 1


# ── Accessory detail ──────────────────────────────────────────────────────────

class TestAccessoryDetailImages:
    def test_accessory_detail_renders(self, desktop):
        page, base = desktop
        _stub_images(page)
        page.goto(base + "/accessories")
        page.wait_for_load_state("load")
        link = page.locator("a[href*='/accessories/']").first
        if link.count() == 0:
            pytest.skip("No accessories in seeded data")
        href = link.get_attribute("href")
        page.goto(base + href)
        page.wait_for_load_state("load")
        assert page.locator("main").count() == 1


# ── No JS errors ──────────────────────────────────────────────────────────────

class TestNoBrokenImages:
    def test_boat_detail_no_js_errors(self, desktop):
        page, base = desktop
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        # Block third-party scripts that may have their own JS errors
        page.route("**nexttech.com.ar/**", lambda route: route.abort())
        _go_boat_detail(page, base)
        assert errors == [], f"JS errors on boat detail: {errors}"

    def test_boat_list_no_js_errors(self, desktop):
        page, base = desktop
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.route("**nexttech.com.ar/**", lambda route: route.abort())
        _stub_images(page)
        page.goto(base + "/boats")
        page.wait_for_load_state("load")
        assert errors == [], f"JS errors on /boats: {errors}"
