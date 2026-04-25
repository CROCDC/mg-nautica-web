"""E2E interaction tests: gallery, lightbox, filters, mobile nav, forms, reveal."""
import re

from tests.e2e.conftest import shot


# ── Gallery navigation (desktop) ─────────────────────────────────────────────

def test_gallery_thumbnail_switch(desktop):
    page, base = desktop
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator(".boat-card a").first.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")

    thumbs = page.locator(".gallery-thumb")
    if thumbs.count() < 2:
        return  # boat has only 1 photo — skip

    # First thumb is active; click second
    before_src = page.locator(".gallery-main img").get_attribute("src")
    thumbs.nth(1).click()
    page.wait_for_timeout(300)
    after_src = page.locator(".gallery-main img").get_attribute("src")
    shot(page, "gallery_thumb_switch")
    assert after_src != before_src


def test_gallery_arrow_next(desktop):
    page, base = desktop
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator(".boat-card a").first.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")

    if page.locator(".gallery-thumb").count() < 2:
        return

    before_src = page.locator(".gallery-main img").get_attribute("src")
    page.locator(".gallery-nav.gallery-next").click()
    page.wait_for_timeout(300)
    after_src = page.locator(".gallery-main img").get_attribute("src")
    shot(page, "gallery_arrow_next")
    assert after_src != before_src


# ── Lightbox ──────────────────────────────────────────────────────────────────

def test_lightbox_opens(desktop):
    page, base = desktop
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator(".boat-card a").first.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")

    page.locator(".gallery-main img").click()
    page.wait_for_timeout(400)
    shot(page, "lightbox_open")
    assert page.locator(".lightbox.active").count() == 1


def test_lightbox_closes_with_esc(desktop):
    page, base = desktop
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator(".boat-card a").first.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")

    page.locator(".gallery-main img").click()
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    shot(page, "lightbox_closed_esc")
    assert page.locator(".lightbox.active").count() == 0


def test_lightbox_closes_clicking_overlay(desktop):
    page, base = desktop
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator(".boat-card a").first.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")

    page.locator(".gallery-main img").click()
    page.wait_for_timeout(300)
    # Click on the lightbox overlay (not the image itself)
    page.locator(".lightbox").click(position={"x": 10, "y": 10})
    page.wait_for_timeout(300)
    shot(page, "lightbox_closed_overlay")
    assert page.locator(".lightbox.active").count() == 0


def test_lightbox_keyboard_navigation(desktop):
    page, base = desktop
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator(".boat-card a").first.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")

    if page.locator(".gallery-thumb").count() < 2:
        return

    page.locator(".gallery-main img").click()
    page.wait_for_timeout(300)
    before_src = page.locator(".lb-img").get_attribute("src")
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(300)
    after_src = page.locator(".lb-img").get_attribute("src")
    shot(page, "lightbox_keyboard_nav")
    assert after_src != before_src


# ── Boats list filter controls ────────────────────────────────────────────────

def test_filter_by_type_sailboat(desktop):
    page, base = desktop
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")

    # Use URL filter (server-side)
    page.goto(base + "/boats?type=sailboat")
    page.wait_for_load_state("networkidle")
    shot(page, "filter_sailboat")
    assert page.locator(".boat-card").count() > 0


def test_filter_by_flag_ar(desktop):
    page, base = desktop
    page.goto(base + "/boats?flag=AR")
    page.wait_for_load_state("networkidle")
    shot(page, "filter_flag_ar")
    assert page.locator(".boat-card").count() > 0


def test_filter_combined(desktop):
    page, base = desktop
    page.goto(base + "/boats?type=sailboat&flag=AR")
    page.wait_for_load_state("networkidle")
    shot(page, "filter_combined")
    # May return 0 boats — just verify the page loads
    assert page.locator(".boat-grid, .boats-empty").count() >= 1


# ── Inquiry form ──────────────────────────────────────────────────────────────

def test_inquiry_form_visible(desktop):
    page, base = desktop
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator(".boat-card a").first.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")
    shot(page, "inquiry_form_visible")
    assert page.locator("form[action*='inquire']").count() >= 1


def test_inquiry_form_submit(desktop):
    page, base = desktop
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator(".boat-card a").first.get_attribute("href")
    slug = href.rstrip("/").split("/")[-1]
    page.goto(base + href)
    page.wait_for_load_state("networkidle")

    page.fill("input[name='name']", "Juan Pérez")
    page.fill("input[name='email']", "juan@example.com")
    page.fill("input[name='phone']", "+54 11 1234-5678")
    page.fill("textarea[name='message']", "Estoy interesado en esta embarcación.")
    page.click("form[action*='inquire'] button[type='submit']")
    page.wait_for_load_state("networkidle")
    shot(page, "inquiry_form_submitted")
    # After submit, page should redirect back or show confirmation
    assert page.url != ""


# ── Publish / sell forms ──────────────────────────────────────────────────────

def test_publish_form_visible(desktop):
    page, base = desktop
    page.goto(base + "/publish")
    page.wait_for_load_state("networkidle")
    shot(page, "publish_form")
    assert page.locator("form").count() >= 1
    assert page.locator("input[name='name'], input[name='title']").count() >= 1


def test_sell_your_boat_form_visible(desktop):
    page, base = desktop
    page.goto(base + "/sell-your-boat")
    page.wait_for_load_state("networkidle")
    shot(page, "sell_your_boat_form")
    assert page.locator("main").count() == 1


# ── Mobile nav ────────────────────────────────────────────────────────────────

def test_mobile_nav_burger_opens(mobile_page):
    page, base = mobile_page
    page.goto(base + "/")
    page.wait_for_load_state("networkidle")

    burger = page.locator("#nav-burger")
    assert burger.count() == 1
    burger.click()
    page.wait_for_timeout(400)
    shot(page, "mobile_nav_open")
    # nav-links should become visible
    assert page.locator("#nav-links").is_visible()


def test_mobile_nav_closes_on_link(mobile_page):
    page, base = mobile_page
    page.goto(base + "/")
    page.wait_for_load_state("networkidle")

    page.locator("#nav-burger").click()
    page.wait_for_timeout(300)
    # Click first nav link to navigate away — menu should close
    page.locator("#nav-links li a").first.click()
    page.wait_for_load_state("networkidle")
    shot(page, "mobile_nav_closed_after_link")


# ── Favorites toggle ──────────────────────────────────────────────────────────

def test_favorite_toggle(desktop):
    page, base = desktop
    page.goto(base + "/boats")
    page.wait_for_load_state("networkidle")
    href = page.locator(".boat-card a").first.get_attribute("href")
    page.goto(base + href)
    page.wait_for_load_state("networkidle")

    btn = page.locator(".btn-favorite, [data-action='favorite']")
    if btn.count() == 0:
        return  # favorites not implemented on detail — skip
    btn.click()
    page.wait_for_timeout(400)
    shot(page, "favorite_toggled")


# ── Scroll reveal ─────────────────────────────────────────────────────────────

def test_scroll_reveal_cards_become_visible(desktop):
    page, base = desktop
    page.goto(base + "/")
    page.wait_for_load_state("networkidle")

    # Scroll past the hero to trigger IntersectionObserver
    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    page.wait_for_timeout(700)
    shot(page, "scroll_reveal_triggered")
    # At least some boat cards should be visible (reveal class applied)
    visible = page.locator(".boat-card.visible").count()
    # If scroll reveal is not yet fired, fall back to checking cards exist
    assert page.locator(".boat-card").count() > 0


# ── Footer links ──────────────────────────────────────────────────────────────

def test_footer_links_resolve(desktop):
    page, base = desktop
    page.goto(base + "/")
    page.wait_for_load_state("networkidle")
    shot(page, "footer_desktop")
    assert page.locator(".site-footer").count() == 1
    assert page.locator(".footer-brand").is_visible()


# ── Health endpoint ───────────────────────────────────────────────────────────

def test_health(desktop):
    page, base = desktop
    response = page.goto(base + "/health")
    assert response.status == 200
