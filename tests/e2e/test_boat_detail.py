"""E2E tests specifically for the boat detail page.

Uses the `boat_detail` fixture (desktop, pre-navigated) and
`boat_detail_vp` (× 3 viewports) from conftest.
"""
from tests.e2e.conftest import shot


# ── Screenshots × 3 viewports ─────────────────────────────────────────────────

def test_detail_screenshot(boat_detail_vp):
    page, base, slug, vp_name = boat_detail_vp
    shot(page, f"boat_detail_{slug}_{vp_name}")
    assert page.locator(".detail-title").count() == 1


def test_detail_gallery_renders(boat_detail_vp):
    page, base, slug, vp_name = boat_detail_vp
    shot(page, f"boat_detail_gallery_{vp_name}")
    assert page.locator("#gallery-main-img").count() >= 1
    assert page.locator(".gallery-thumb").count() >= 1


def test_detail_price_visible(boat_detail_vp):
    page, base, slug, vp_name = boat_detail_vp
    assert page.locator(".price, .detail-price, [class*='price']").count() >= 1


def test_detail_inquiry_form_visible(boat_detail_vp):
    page, base, slug, vp_name = boat_detail_vp
    shot(page, f"boat_detail_form_{vp_name}")
    assert page.locator("form[action*='inquire']").count() >= 1


def test_detail_sidebar_specs(boat_detail_vp):
    page, base, slug, vp_name = boat_detail_vp
    shot(page, f"boat_detail_sidebar_{vp_name}")
    assert page.locator(".detail-sidebar, .spec-block, .spec-grid").count() >= 1


# ── Interaction tests (desktop fixture) ──────────────────────────────────────

def test_detail_thumbnail_click_changes_main(boat_detail):
    page, base, slug = boat_detail
    thumbs = page.locator(".gallery-thumb")
    if thumbs.count() < 2:
        return
    before = page.locator("#gallery-main-img").get_attribute("src")
    thumbs.nth(1).click()
    page.wait_for_timeout(300)
    after = page.locator("#gallery-main-img").get_attribute("src")
    shot(page, "boat_detail_thumb_switch")
    assert after != before


def test_detail_next_arrow(boat_detail):
    page, base, slug = boat_detail
    if page.locator(".gallery-thumb").count() < 2:
        return
    before = page.locator("#gallery-main-img").get_attribute("src")
    page.locator("button.gallery-nav.next").click()
    page.wait_for_timeout(300)
    after = page.locator("#gallery-main-img").get_attribute("src")
    shot(page, "boat_detail_arrow_next")
    assert after != before


def test_detail_prev_arrow_wraps(boat_detail):
    page, base, slug = boat_detail
    if page.locator(".gallery-thumb").count() < 2:
        return
    # From index 0, prev should wrap to last
    page.locator("button.gallery-nav.prev").click()
    page.wait_for_timeout(300)
    last_thumb = page.locator(".gallery-thumb").last
    shot(page, "boat_detail_arrow_wrap")
    assert "active" in (last_thumb.get_attribute("class") or "")


def test_detail_lightbox_opens_on_click(boat_detail):
    page, base, slug = boat_detail
    page.locator("#gallery-main-img").click()
    page.wait_for_timeout(400)
    shot(page, "boat_detail_lightbox_open")
    assert page.locator(".lightbox.open").count() == 1


def test_detail_lightbox_close_button(boat_detail):
    page, base, slug = boat_detail
    page.locator("#gallery-main-img").click()
    page.wait_for_timeout(300)
    page.locator(".lb-close").click()
    page.wait_for_timeout(300)
    shot(page, "boat_detail_lightbox_close_btn")
    assert page.locator(".lightbox.open").count() == 0


def test_detail_lightbox_esc(boat_detail):
    page, base, slug = boat_detail
    page.locator("#gallery-main-img").click()
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    shot(page, "boat_detail_lightbox_esc")
    assert page.locator(".lightbox.open").count() == 0


def test_detail_lightbox_arrow_right(boat_detail):
    page, base, slug = boat_detail
    if page.locator(".gallery-thumb").count() < 2:
        return
    page.locator("#gallery-main-img").click()
    page.wait_for_timeout(300)
    before = page.locator("#lb-img").get_attribute("src")
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(300)
    after = page.locator("#lb-img").get_attribute("src")
    shot(page, "boat_detail_lightbox_arrow_right")
    assert after != before


def test_detail_lightbox_arrow_left(boat_detail):
    page, base, slug = boat_detail
    if page.locator(".gallery-thumb").count() < 2:
        return
    # Navigate to second photo first
    page.locator(".gallery-thumb").nth(1).click()
    page.wait_for_timeout(200)
    page.locator("#gallery-main-img").click()
    page.wait_for_timeout(300)
    before = page.locator("#lb-img").get_attribute("src")
    page.keyboard.press("ArrowLeft")
    page.wait_for_timeout(300)
    after = page.locator("#lb-img").get_attribute("src")
    shot(page, "boat_detail_lightbox_arrow_left")
    assert after != before


def test_detail_lightbox_counter_updates(boat_detail):
    page, base, slug = boat_detail
    if page.locator(".gallery-thumb").count() < 2:
        return
    page.locator("#gallery-main-img").click()
    page.wait_for_timeout(300)
    counter_before = page.locator("#lb-counter").text_content()
    page.locator("button.lb-arrow.next").click()
    page.wait_for_timeout(300)
    counter_after = page.locator("#lb-counter").text_content()
    shot(page, "boat_detail_lightbox_counter")
    assert counter_before != counter_after


# ── Galería con muchas fotos (stress test) ───────────────────────────────────

def test_many_photos_screenshot(many_photos_vp):
    page, base, vp_name = many_photos_vp
    shot(page, f"many_photos_{vp_name}")
    assert page.locator(".detail-title").count() == 1


def test_many_photos_thumb_count(many_photos_vp):
    page, base, vp_name = many_photos_vp
    assert page.locator(".gallery-thumb").count() == 24


def test_many_photos_lightbox_counter(many_photos_detail):
    page, base = many_photos_detail
    page.locator("#gallery-main-img").click()
    page.wait_for_timeout(400)
    counter = page.locator("#lb-counter").text_content()
    shot(page, "many_photos_lightbox")
    assert "24" in counter


def test_many_photos_arrow_wraps_to_last(many_photos_detail):
    page, base = many_photos_detail
    # Desde la primera foto, prev debe ir a la 24
    page.locator("button.gallery-nav.prev").click()
    page.wait_for_timeout(300)
    assert "active" in (page.locator(".gallery-thumb").last.get_attribute("class") or "")


def test_detail_inquiry_form_submit(boat_detail):
    page, base, slug = boat_detail
    page.fill("input[name='name']", "Ana García")
    page.fill("input[name='email']", "ana@example.com")
    page.fill("input[name='phone']", "+54 9 11 5555-1234")
    page.fill("textarea[name='message']", "Me interesa el barco, quisiera más información.")
    page.click("form[action*='inquire'] button[type='submit']")
    page.wait_for_load_state("networkidle")
    shot(page, "boat_detail_inquiry_submitted")
    # Should redirect back to detail or show flash
    assert slug in page.url or page.locator(".flash, .alert, [class*='flash']").count() >= 1
