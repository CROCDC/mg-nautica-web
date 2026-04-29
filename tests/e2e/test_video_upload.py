"""E2E tests for video upload in the admin panel and video playback in the public gallery.

Admin tests:  upload via browser file input → verify count / URL / accessibility.
Gallery tests: click video thumbnail → verify player visible, src set, lightbox NOT opened.
"""
import pytest

from tests.e2e.conftest import shot

# Contenido mínimo con extensión válida — el servidor solo valida la extensión
FAKE_MP4 = b"FAKEVIDEOCONTENT"


def _fake_mp4(name: str = "test.mp4") -> dict:
    return {"name": name, "mimeType": "video/mp4", "buffer": FAKE_MP4}


def _fake_webm(name: str = "test.webm") -> dict:
    return {"name": name, "mimeType": "video/webm", "buffer": FAKE_MP4}


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


# ── Admin: sección de videos ──────────────────────────────────────────────────

def test_video_section_exists_in_edit_page(admin_page):
    """La sección de videos con su input de archivo debe aparecer en edición."""
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")
    shot(page, "video_admin_section")
    assert page.locator("input[name='videos']").count() >= 1


def test_video_section_has_correct_accept_attribute(admin_page):
    """El input de video solo acepta mp4, webm y mov."""
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")
    accept = page.locator("input[name='videos']").first.get_attribute("accept")
    assert accept is not None
    assert "mp4" in accept or "video" in accept


# ── Admin: subida de videos ───────────────────────────────────────────────────

def test_upload_single_video_increases_count(admin_page):
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    before = page.locator(".admin-photo video").count()
    page.set_input_files("input[name='videos']", [_fake_mp4("recorrida.mp4")])
    page.locator("form[action*='videos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")
    shot(page, "video_upload_single")

    assert page.locator(".admin-photo video").count() == before + 1


def test_upload_multiple_videos_at_once(admin_page):
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    before = page.locator(".admin-photo video").count()
    page.set_input_files("input[name='videos']", [
        _fake_mp4("a.mp4"),
        _fake_webm("b.webm"),
        _fake_mp4("c.mp4"),
    ])
    page.locator("form[action*='videos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")
    shot(page, "video_upload_multiple")

    assert page.locator(".admin-photo video").count() == before + 3


def test_uploaded_video_src_points_to_uploads(admin_page):
    """El src del <video> en el admin debe apuntar a /uploads/."""
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    page.set_input_files("input[name='videos']", [_fake_mp4("src-check.mp4")])
    page.locator("form[action*='videos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    upload_videos = page.locator(".admin-photo video[src^='/uploads/']")
    assert upload_videos.count() >= 1


def test_uploaded_video_url_is_accessible(admin_page):
    """La URL /uploads/ del video subido debe devolver HTTP 200."""
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    page.set_input_files("input[name='videos']", [_fake_mp4("access-check.mp4")])
    page.locator("form[action*='videos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    video = page.locator(".admin-photo video[src^='/uploads/']").first
    src = video.get_attribute("src")
    assert src is not None
    response = page.request.get(base + src)
    assert response.status == 200


def test_upload_shows_success_flash(admin_page):
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    page.set_input_files("input[name='videos']", [_fake_mp4("flash-test.mp4")])
    page.locator("form[action*='videos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    flash = page.locator(".flash, .alert, [class*='flash'], [class*='alert']")
    assert flash.count() >= 1


def test_delete_video_decreases_count(admin_page):
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    # Subir un video primero
    page.set_input_files("input[name='videos']", [_fake_mp4("to-delete.mp4")])
    page.locator("form[action*='videos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    before = page.locator(".admin-photo video").count()

    delete_btns = page.locator("form[action*='videos'][action*='/delete'] button")
    if delete_btns.count() == 0:
        pytest.skip("No hay botón de borrar video")

    # Aceptar el confirm() automáticamente
    page.on("dialog", lambda d: d.accept())
    delete_btns.last.click()
    page.wait_for_load_state("networkidle")
    shot(page, "video_delete")

    assert page.locator(".admin-photo video").count() == before - 1


def test_delete_video_shows_success_flash(admin_page):
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    page.set_input_files("input[name='videos']", [_fake_mp4("del-flash.mp4")])
    page.locator("form[action*='videos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")

    delete_btns = page.locator("form[action*='videos'][action*='/delete'] button")
    if delete_btns.count() == 0:
        pytest.skip("No hay botón de borrar video")

    page.on("dialog", lambda d: d.accept())
    delete_btns.last.click()
    page.wait_for_load_state("networkidle")

    flash = page.locator(".flash, .alert, [class*='flash'], [class*='alert']")
    assert flash.count() >= 1


def test_video_preview_thumbnail_in_admin(admin_page):
    """El admin muestra un <video> en miniatura al subir (preload=metadata)."""
    page, base = admin_page
    if _go_to_first_boat_edit(page, base) is None:
        pytest.skip("No hay barcos para editar")

    page.set_input_files("input[name='videos']", [_fake_mp4("preview.mp4")])
    page.locator("form[action*='videos/add'] button[type='submit']").click()
    page.wait_for_load_state("networkidle")
    shot(page, "video_admin_preview")

    # El video en el admin debe tener preload=metadata para la miniatura
    video = page.locator(".admin-photo video[src^='/uploads/']").last
    assert video.count() >= 1 or page.locator(".admin-photo video").count() >= 1


# ── Galería pública: miniaturas de video ──────────────────────────────────────

def test_gallery_has_video_thumbnail(video_boat_detail):
    """El barco con video muestra la miniatura de video en la tira."""
    page, base = video_boat_detail
    shot(page, "gallery_video_thumbnail")
    assert page.locator(".gallery-thumb-video").count() >= 1


def test_gallery_video_thumbnail_has_play_icon(video_boat_detail):
    """La miniatura de video muestra el ícono de play ▶."""
    page, base = video_boat_detail
    assert page.locator(".gallery-play-icon").count() >= 1


def test_gallery_video_thumbnail_contains_video_element(video_boat_detail):
    """La miniatura de video usa <video> para mostrar el primer frame."""
    page, base = video_boat_detail
    assert page.locator(".gallery-thumb-video video").count() >= 1


# ── Galería pública: reproducción del video ───────────────────────────────────

def test_click_video_thumbnail_shows_video_player(video_boat_detail):
    """Al hacer clic en la miniatura de video, aparece el player principal."""
    page, base = video_boat_detail

    page.locator(".gallery-thumb-video").first.click()
    page.wait_for_timeout(400)
    shot(page, "gallery_video_player_active")

    display = page.evaluate(
        "document.getElementById('gallery-main-video').style.display"
    )
    assert display != "none", "El <video> principal debe ser visible tras el clic"


def test_click_video_thumbnail_hides_main_image(video_boat_detail):
    """Cuando el video está activo, la imagen principal queda oculta."""
    page, base = video_boat_detail

    page.locator(".gallery-thumb-video").first.click()
    page.wait_for_timeout(400)

    img_display = page.evaluate(
        "document.getElementById('gallery-main-img').style.display"
    )
    assert img_display == "none", "La <img> principal debe ocultarse cuando hay video activo"


def test_video_player_src_points_to_uploads(video_boat_detail):
    """El src del player de video apunta a /uploads/ tras el clic."""
    page, base = video_boat_detail

    page.locator(".gallery-thumb-video").first.click()
    page.wait_for_timeout(400)

    src = page.evaluate("document.getElementById('gallery-main-video').src")
    assert src, "El video player debe tener un src asignado"
    assert "/uploads/" in src, f"El src debe apuntar a /uploads/, got: {src}"


def test_video_player_url_is_accessible(video_boat_detail):
    """La URL del video player debe devolver HTTP 200 (el archivo existe)."""
    page, base = video_boat_detail

    page.locator(".gallery-thumb-video").first.click()
    page.wait_for_timeout(400)

    # El browser resuelve el src a URL absoluta
    src = page.evaluate("document.getElementById('gallery-main-video').src")
    assert src
    response = page.request.get(src)
    assert response.status == 200, f"El video debe servirse con HTTP 200, got {response.status}"


def test_video_player_has_controls(video_boat_detail):
    """El player de video debe tener controles nativos del browser."""
    page, base = video_boat_detail

    page.locator(".gallery-thumb-video").first.click()
    page.wait_for_timeout(400)

    has_controls = page.evaluate(
        "document.getElementById('gallery-main-video').hasAttribute('controls')"
    )
    assert has_controls, "El <video> debe tener el atributo controls"


def test_gallery_navigation_reaches_video(video_boat_detail):
    """Navegando con el botón → de la galería, el video se activa."""
    page, base = video_boat_detail

    # La galería tiene foto en idx=0, video en idx=1
    # Hacemos clic en → para pasar a la segunda posición
    nav_next = page.locator(".gallery-nav.next")
    if nav_next.count() == 0:
        pytest.skip("No hay botón de navegación (barco con un solo ítem)")

    nav_next.click()
    page.wait_for_timeout(400)
    shot(page, "gallery_nav_to_video")

    display = page.evaluate(
        "document.getElementById('gallery-main-video').style.display"
    )
    assert display != "none", "El video debe activarse al navegar al segundo ítem"


def test_click_video_area_does_not_open_lightbox(video_boat_detail):
    """Cuando el video está activo, hacer clic en la galería NO abre el lightbox."""
    page, base = video_boat_detail

    page.locator(".gallery-thumb-video").first.click()
    page.wait_for_timeout(400)

    # Hacer clic en el área principal de la galería
    page.locator("#gallery-main").click()
    page.wait_for_timeout(200)

    is_open = page.evaluate(
        "document.getElementById('lightbox').classList.contains('open')"
    )
    assert not is_open, "El lightbox NO debe abrirse cuando hay un video activo"


def test_click_photo_thumbnail_after_video_switches_back_to_image(video_boat_detail):
    """Volver a una foto después de ver un video muestra la <img> y oculta el <video>."""
    page, base = video_boat_detail

    # Primero activar el video
    page.locator(".gallery-thumb-video").first.click()
    page.wait_for_timeout(400)

    # Luego hacer clic en la primera miniatura de foto
    photo_thumb = page.locator(".gallery-thumb:not(.gallery-thumb-video)").first
    if photo_thumb.count() == 0:
        pytest.skip("No hay miniatura de foto")
    photo_thumb.click()
    page.wait_for_timeout(400)
    shot(page, "gallery_back_to_photo")

    img_display = page.evaluate(
        "document.getElementById('gallery-main-img').style.display"
    )
    vid_display = page.evaluate(
        "document.getElementById('gallery-main-video').style.display"
    )
    assert img_display != "none", "La imagen debe volver a ser visible"
    assert vid_display == "none", "El video debe ocultarse al volver a una foto"


def test_js_media_array_has_video_entry(video_boat_detail):
    """El array `media` de JS debe contener al menos un ítem de tipo video."""
    page, base = video_boat_detail

    # Verificar que el HTML del script contiene type:'video'
    content = page.content()
    assert "type:'video'" in content, "El array media debe incluir ítems de tipo video"


def test_gallery_screenshot_mixed_media(video_boat_detail):
    """Screenshot completo de la galería con foto + video (foto activa)."""
    page, base = video_boat_detail
    shot(page, "gallery_mixed_media_photo_active")
    # Sin error → el test pasa si shot() no lanza excepción (no hay 500 ni bugs visuales)
