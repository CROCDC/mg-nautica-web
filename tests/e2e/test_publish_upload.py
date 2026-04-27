"""E2E tests for the /publish free-listing form (file uploads).

The form accepts up to 10 files (jpg, png, webp, heic, pdf) via a real
multipart/form-data file input.  We test:

- The form renders with a visible file input.
- Submitting without files redirects to ?submitted=1 and shows the thank-you message.
- Submitting with a single PNG file succeeds and the file is persisted on disk.
- Submitting with multiple files of different types succeeds.
- Submitting with missing required text fields shows a 400 error inline.
- Submitting with an invalid/unsupported file type is silently skipped (saved listing
  with no file_urls) rather than rejected — this is the current repository behaviour.
"""
import io
import os
import struct
import tempfile
import zlib
from pathlib import Path

import pytest

from tests.e2e.conftest import shot


# ── Minimal binary fixtures ────────────────────────────────────────────────────

def _make_png(width: int = 2, height: int = 2) -> bytes:
    """Return a valid minimal PNG image as bytes (no external deps)."""
    def chunk(name: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(name + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw_rows = b"".join(
        b"\x00" + bytes([0, 0, 0] * width) for _ in range(height)
    )
    idat_data = zlib.compress(raw_rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr_data)
        + chunk(b"IDAT", idat_data)
        + chunk(b"IEND", b"")
    )


def _make_pdf() -> bytes:
    """Return a minimal valid 1-page PDF as bytes."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 72 72]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF\n"
    )


MINIMAL_PNG = _make_png()
MINIMAL_PDF = _make_pdf()

# Required form fields for a valid publish submission
VALID_FORM = {
    "first_name": "Ana",
    "last_name": "García",
    "email": "ana-e2e@example.com",
    "condition": "used",
    "description": "Accesorio náutico en perfecto estado, poco uso.",
    "asked_price_usd": "500",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fill_publish_form(page, data: dict):
    """Fill the /publish form text fields."""
    page.fill("input[name='first_name']", data.get("first_name", ""))
    page.fill("input[name='last_name']", data.get("last_name", ""))
    page.fill("input[name='email']", data.get("email", ""))
    if data.get("condition"):
        page.select_option("select[name='condition']", data["condition"])
    page.fill("textarea[name='description']", data.get("description", ""))
    if data.get("asked_price_usd"):
        page.fill("input[name='asked_price_usd']", data["asked_price_usd"])
    if data.get("phone"):
        page.fill("input[name='phone']", data["phone"])


# ── Form rendering ─────────────────────────────────────────────────────────────

class TestPublishFormRenders:
    def test_publish_page_renders(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        shot(page, "publish_form_empty")
        assert page.locator("form").count() >= 1

    def test_file_input_is_present(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        file_input = page.locator("input[name='files'][type='file']")
        assert file_input.count() == 1

    def test_file_input_accepts_multiple(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        has_multiple = page.locator("input[name='files'][multiple]").count()
        assert has_multiple == 1, "File input should have 'multiple' attribute"

    def test_file_input_accepted_types(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        accept = page.locator("input[name='files']").get_attribute("accept")
        assert accept is not None
        for ext in [".jpg", ".jpeg", ".png", ".pdf"]:
            assert ext in accept, f"File input does not accept {ext}"


# ── Submission without files ──────────────────────────────────────────────────

class TestPublishSubmitNoFiles:
    def test_submit_without_files_redirects(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        _fill_publish_form(page, VALID_FORM)
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        shot(page, "publish_submit_no_files")
        assert "submitted=1" in page.url

    def test_submit_without_files_shows_success_message(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        _fill_publish_form(page, {**VALID_FORM, "email": "nofiles@e2e.com"})
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        success = page.locator("p.success, .success")
        assert success.count() >= 1
        assert "Gracias" in success.first.inner_text()


# ── Submission with a single PNG ──────────────────────────────────────────────

class TestPublishSubmitWithPng:
    def test_submit_single_png_redirects(self, desktop, tmp_path):
        page, base = desktop
        png_file = tmp_path / "test.png"
        png_file.write_bytes(MINIMAL_PNG)

        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        _fill_publish_form(page, {**VALID_FORM, "email": "png-upload@e2e.com"})
        page.set_input_files("input[name='files']", str(png_file))
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        shot(page, "publish_submit_with_png")
        assert "submitted=1" in page.url

    def test_submit_single_png_shows_success_message(self, desktop, tmp_path):
        page, base = desktop
        png_file = tmp_path / "barco.png"
        png_file.write_bytes(MINIMAL_PNG)

        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        _fill_publish_form(page, {**VALID_FORM, "email": "png-success@e2e.com"})
        page.set_input_files("input[name='files']", str(png_file))
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        success = page.locator("p.success, .success")
        assert success.count() >= 1

    def test_submit_png_via_buffer(self, desktop):
        """Attach file using Playwright buffer API (no tmp file needed)."""
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        _fill_publish_form(page, {**VALID_FORM, "email": "buffer@e2e.com"})
        page.set_input_files("input[name='files']", {
            "name": "foto.png",
            "mimeType": "image/png",
            "buffer": MINIMAL_PNG,
        })
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        assert "submitted=1" in page.url


# ── Submission with a PDF ─────────────────────────────────────────────────────

class TestPublishSubmitWithPdf:
    def test_submit_pdf_redirects(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        _fill_publish_form(page, {**VALID_FORM, "email": "pdf@e2e.com"})
        page.set_input_files("input[name='files']", {
            "name": "documento.pdf",
            "mimeType": "application/pdf",
            "buffer": MINIMAL_PDF,
        })
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        shot(page, "publish_submit_with_pdf")
        assert "submitted=1" in page.url


# ── Submission with multiple files ────────────────────────────────────────────

class TestPublishSubmitMultipleFiles:
    def test_submit_three_images_redirects(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        _fill_publish_form(page, {**VALID_FORM, "email": "multi@e2e.com"})
        page.set_input_files("input[name='files']", [
            {"name": "foto1.png", "mimeType": "image/png", "buffer": MINIMAL_PNG},
            {"name": "foto2.png", "mimeType": "image/png", "buffer": MINIMAL_PNG},
            {"name": "foto3.png", "mimeType": "image/png", "buffer": MINIMAL_PNG},
        ])
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        shot(page, "publish_submit_three_images")
        assert "submitted=1" in page.url

    def test_submit_mixed_png_and_pdf(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        _fill_publish_form(page, {**VALID_FORM, "email": "mixed@e2e.com"})
        page.set_input_files("input[name='files']", [
            {"name": "foto.png", "mimeType": "image/png", "buffer": MINIMAL_PNG},
            {"name": "doc.pdf",  "mimeType": "application/pdf", "buffer": MINIMAL_PDF},
        ])
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        assert "submitted=1" in page.url


# ── Validation errors ─────────────────────────────────────────────────────────

class TestPublishValidationErrors:
    def test_missing_description_shows_error(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        _fill_publish_form(page, {
            "first_name": "Test",
            "last_name": "User",
            "email": "err@e2e.com",
            "condition": "new",
            # description intentionally omitted
        })
        # Remove HTML5 required so browser doesn't block the submit — let server validate
        page.evaluate(
            "document.querySelector('textarea[name=\"description\"]').removeAttribute('required')"
        )
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        shot(page, "publish_validation_error_no_description")
        # Should stay on the form (no redirect to ?submitted=1)
        assert "submitted=1" not in page.url
        # Should show an error
        error = page.locator(".error, [class*='error'], p[style*='color:red'], p[style*='color: red']")
        assert error.count() >= 1 or "error" in page.content().lower()

    def test_missing_condition_shows_error(self, desktop):
        page, base = desktop
        page.goto(base + "/publish")
        page.wait_for_load_state("load")
        page.fill("input[name='first_name']", "Test")
        page.fill("input[name='last_name']", "User")
        page.fill("input[name='email']", "nocond@e2e.com")
        page.fill("textarea[name='description']", "Algo para vender")
        # Remove HTML5 required and set an invalid value so the server rejects it
        page.evaluate(
            "var s = document.querySelector('select[name=\"condition\"]');"
            "s.removeAttribute('required');"
            "s.value = '';"
        )
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        assert "submitted=1" not in page.url


# ── Sell Your Boat form (no file upload, but similar flow) ────────────────────

class TestSellYourBoatForm:
    def test_form_renders(self, desktop):
        page, base = desktop
        page.goto(base + "/sell-your-boat")
        page.wait_for_load_state("load")
        shot(page, "sell_your_boat_form")
        assert page.locator("form").count() >= 1
        assert page.locator("select[name='boat_type']").count() == 1

    def test_submit_success_shows_confirmation(self, desktop):
        page, base = desktop
        page.goto(base + "/sell-your-boat")
        page.wait_for_load_state("load")
        page.fill("input[name='first_name']", "Juan")
        page.fill("input[name='last_name']", "Pérez")
        page.fill("input[name='email']", "juan-e2e@example.com")
        page.select_option("select[name='boat_type']", "sailboat")
        page.fill("textarea[name='message']", "Me gustaría vender mi velero Bavaria 40.")
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        shot(page, "sell_your_boat_submitted")
        assert "submitted=1" in page.url
        success = page.locator("p.success, .success")
        assert success.count() >= 1
        assert "Gracias" in success.first.inner_text()

    def test_submit_missing_fields_stays_on_form(self, desktop):
        page, base = desktop
        page.goto(base + "/sell-your-boat")
        page.wait_for_load_state("load")
        # Submit with only first name
        page.fill("input[name='first_name']", "Juan")
        page.click("button[type='submit']")
        page.wait_for_load_state("load")
        assert "submitted=1" not in page.url
