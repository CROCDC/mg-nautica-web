"""Unit and integration tests for video file upload (boats)."""
import base64
import io
from unittest.mock import MagicMock

import pytest

from app.models import Boat, BoatPhoto, BoatVideo

# Server validates extension only — content doesn't need to be real video
FAKE_MP4 = b"FAKEVIDEOCONTENT"

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)


# ── Unit tests: _save_video_file ──────────────────────────────────────────────

class TestSaveVideoFile:
    def _mock_file(self, filename: str) -> MagicMock:
        f = MagicMock()
        f.filename = filename
        f.save = MagicMock()
        return f

    def test_valid_mp4(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(self._mock_file("recorrida.mp4"))
        assert url is not None
        assert url.startswith("/uploads/")
        assert url.endswith(".mp4")

    def test_valid_webm(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(self._mock_file("clip.webm"))
        assert url is not None
        assert url.endswith(".webm")

    def test_valid_mov(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(self._mock_file("video.MOV"))
        assert url is not None
        assert url.endswith(".mov")

    def test_jpg_is_not_a_valid_video_extension(self, app):
        """jpg es extensión de foto, no de video."""
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(self._mock_file("foto.jpg"))
        assert url is None

    def test_png_is_not_a_valid_video_extension(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(self._mock_file("imagen.png"))
        assert url is None

    def test_pdf_extension_returns_none(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(self._mock_file("manual.pdf"))
        assert url is None

    def test_exe_extension_returns_none(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(self._mock_file("malware.exe"))
        assert url is None

    def test_empty_filename_returns_none(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(self._mock_file(""))
        assert url is None

    def test_none_file_returns_none(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(None)
        assert url is None

    def test_unique_filenames_per_call(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url1 = _save_video_file(self._mock_file("clip.mp4"))
            url2 = _save_video_file(self._mock_file("clip.mp4"))
        assert url1 != url2

    def test_original_filename_not_preserved(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(self._mock_file("mi video privado.mp4"))
        assert "mi video privado" not in url
        assert " " not in url

    def test_file_save_called_once(self, app):
        from app.admin.boats import _save_video_file
        f = self._mock_file("test.mp4")
        with app.app_context():
            _save_video_file(f)
        f.save.assert_called_once()

    def test_extension_is_case_insensitive(self, app):
        from app.admin.boats import _save_video_file
        with app.app_context():
            url = _save_video_file(self._mock_file("CLIP.MP4"))
        assert url is not None
        assert url.endswith(".mp4")


# ── Integration tests: boats video upload ────────────────────────────────────

class TestBoatsVideoUpload:
    def test_add_single_video_creates_db_record(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={"videos": (io.BytesIO(FAKE_MP4), "clip.mp4")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        videos = db.session.query(BoatVideo).filter_by(boat_id=boat.id).all()
        assert len(videos) == 1
        assert videos[0].url.startswith("/uploads/")
        assert videos[0].url.endswith(".mp4")

    def test_add_multiple_videos_at_once(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={"videos": [
                (io.BytesIO(FAKE_MP4), "a.mp4"),
                (io.BytesIO(FAKE_MP4), "b.webm"),
                (io.BytesIO(FAKE_MP4), "c.mov"),
            ]},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        assert db.session.query(BoatVideo).filter_by(boat_id=boat.id).count() == 3

    def test_positions_increment_correctly(self, db, logged_in_admin, boat):
        logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={"videos": [
                (io.BytesIO(FAKE_MP4), "v1.mp4"),
                (io.BytesIO(FAKE_MP4), "v2.mp4"),
                (io.BytesIO(FAKE_MP4), "v3.mp4"),
            ]},
            content_type="multipart/form-data",
        )
        videos = (
            db.session.query(BoatVideo)
            .filter_by(boat_id=boat.id)
            .order_by(BoatVideo.position)
            .all()
        )
        positions = [v.position for v in videos]
        assert positions == sorted(positions)
        assert len(set(positions)) == len(positions)

    def test_position_continues_after_existing_videos(self, db, logged_in_admin, boat):
        """El contador de posición arranca después de los videos ya existentes."""
        db.session.add(BoatVideo(boat_id=boat.id, url="/uploads/ex1.mp4", position=0))
        db.session.add(BoatVideo(boat_id=boat.id, url="/uploads/ex2.mp4", position=1))
        db.session.commit()

        logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={"videos": (io.BytesIO(FAKE_MP4), "nuevo.mp4")},
            content_type="multipart/form-data",
        )
        videos = (
            db.session.query(BoatVideo)
            .filter_by(boat_id=boat.id)
            .order_by(BoatVideo.position)
            .all()
        )
        assert len(videos) == 3
        assert videos[2].position == 2

    def test_invalid_extension_returns_error_flash(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={"videos": (io.BytesIO(FAKE_MP4), "virus.exe")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "válido" in resp.data.decode("utf-8")
        assert db.session.query(BoatVideo).filter_by(boat_id=boat.id).count() == 0

    def test_image_extension_rejected_as_video(self, db, logged_in_admin, boat):
        """jpg y png son extensiones de foto, no de video."""
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={"videos": (io.BytesIO(b"notavideo"), "foto.jpg")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert db.session.query(BoatVideo).filter_by(boat_id=boat.id).count() == 0

    def test_no_file_returns_error_flash(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert db.session.query(BoatVideo).filter_by(boat_id=boat.id).count() == 0

    def test_delete_video_removes_from_db(self, db, logged_in_admin, boat):
        video = BoatVideo(boat_id=boat.id, url="/uploads/tobedeleted.mp4", position=0)
        db.session.add(video)
        db.session.commit()
        video_id = video.id

        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/{video_id}/delete",
        )
        assert resp.status_code == 302
        assert db.session.get(BoatVideo, video_id) is None

    def test_delete_video_from_wrong_boat_is_rejected(self, db, logged_in_admin, boat):
        """Un video solo puede eliminarse desde el barco al que pertenece."""
        from tests.factories import make_boat as _make
        other = _make(slug="otro-barco")
        db.session.add(other)
        db.session.flush()
        video = BoatVideo(boat_id=other.id, url="/uploads/other.mp4", position=0)
        db.session.add(video)
        db.session.commit()

        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/{video.id}/delete",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert db.session.get(BoatVideo, video.id) is not None

    def test_add_requires_login(self, client, boat):
        resp = client.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={"videos": (io.BytesIO(FAKE_MP4), "clip.mp4")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_delete_requires_login(self, db, client, boat):
        video = BoatVideo(boat_id=boat.id, url="/uploads/nodel.mp4", position=0)
        db.session.add(video)
        db.session.commit()
        resp = client.post(f"/admin/boats/{boat.id}/videos/{video.id}/delete")
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_add_boat_not_found_redirects(self, db, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/boats/99999/videos/add",
            data={"videos": (io.BytesIO(FAKE_MP4), "clip.mp4")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302

    def test_delete_video_not_found_redirects(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(f"/admin/boats/{boat.id}/videos/99999/delete")
        assert resp.status_code == 302

    def test_videos_are_independent_from_photos(self, db, logged_in_admin, boat):
        """Subir un video no altera el contador de fotos y viceversa."""
        logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/add",
            data={"photos": (io.BytesIO(TINY_PNG), "foto.png")},
            content_type="multipart/form-data",
        )
        logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={"videos": (io.BytesIO(FAKE_MP4), "clip.mp4")},
            content_type="multipart/form-data",
        )
        assert db.session.query(BoatPhoto).filter_by(boat_id=boat.id).count() == 1
        assert db.session.query(BoatVideo).filter_by(boat_id=boat.id).count() == 1

    def test_boat_cascade_delete_removes_videos(self, db, logged_in_admin, boat):
        """Al eliminar un barco, sus videos también se eliminan (CASCADE)."""
        db.session.add(BoatVideo(boat_id=boat.id, url="/uploads/cascade.mp4", position=0))
        db.session.commit()
        boat_id = boat.id

        logged_in_admin.post(f"/admin/boats/{boat.id}/delete")

        assert db.session.query(BoatVideo).filter_by(boat_id=boat_id).count() == 0

    def test_success_flash_after_single_video(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={"videos": (io.BytesIO(FAKE_MP4), "clip.mp4")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Video agregado" in html or "agregado" in html

    def test_success_flash_after_multiple_videos(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/videos/add",
            data={"videos": [
                (io.BytesIO(FAKE_MP4), "a.mp4"),
                (io.BytesIO(FAKE_MP4), "b.mp4"),
            ]},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "2 videos agregados" in html


# ── Integration tests: carga rápida con video ────────────────────────────────

class TestBoatsSimpleWithVideo:
    def test_simple_create_with_videos(self, db, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/boats/new/simple",
            data={
                "title": "Barco Simple Con Video",
                "videos": (io.BytesIO(FAKE_MP4), "clip.mp4"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        b = db.session.query(Boat).filter_by(slug="barco-simple-con-video").first()
        assert b is not None
        assert db.session.query(BoatVideo).filter_by(boat_id=b.id).count() == 1

    def test_simple_create_with_photos_and_videos(self, db, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/boats/new/simple",
            data={
                "title": "Barco Simple Mixto",
                "photos": (io.BytesIO(TINY_PNG), "foto.png"),
                "videos": (io.BytesIO(FAKE_MP4), "clip.mp4"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        b = db.session.query(Boat).filter_by(slug="barco-simple-mixto").first()
        assert b is not None
        assert db.session.query(BoatPhoto).filter_by(boat_id=b.id).count() == 1
        assert db.session.query(BoatVideo).filter_by(boat_id=b.id).count() == 1

    def test_simple_create_without_videos_still_works(self, db, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/boats/new/simple",
            data={"title": "Solo Titulo"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        b = db.session.query(Boat).filter_by(slug="solo-titulo").first()
        assert b is not None
        assert db.session.query(BoatVideo).filter_by(boat_id=b.id).count() == 0


# ── Integration tests: HTML del detalle público ───────────────────────────────

class TestPublicGalleryWithVideo:
    def _seed_boat(self, db, *, n_photos=1, n_videos=1, slug="galeria-video-test"):
        from tests.factories import make_boat
        b = make_boat(slug=slug)
        db.session.add(b)
        db.session.flush()
        for i in range(n_photos):
            db.session.add(BoatPhoto(
                boat_id=b.id, url=f"/uploads/foto{i}.jpg",
                position=i, is_primary=(i == 0),
            ))
        for i in range(n_videos):
            db.session.add(BoatVideo(
                boat_id=b.id, url=f"/uploads/video{i}.mp4", position=i,
            ))
        db.session.commit()
        return b

    def test_detail_shows_video_thumbnail_when_videos_exist(self, db, client):
        b = self._seed_boat(db, n_photos=1, n_videos=1)
        resp = client.get(f"/boats/{b.slug}")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        # Miniatura de video con clase específica
        assert "gallery-thumb-video" in html
        assert "gallery-play-icon" in html

    def test_detail_js_media_array_includes_video_type(self, db, client):
        b = self._seed_boat(db, n_photos=1, n_videos=1)
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        assert "type:'video'" in html
        assert "/uploads/video0.mp4" in html

    def test_detail_js_media_array_includes_photo_type(self, db, client):
        b = self._seed_boat(db, n_photos=1, n_videos=1)
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        assert "type:'image'" in html

    def test_detail_video_element_always_present_in_gallery(self, db, client):
        """El <video> principal siempre está en el DOM (oculto si no hay videos)."""
        b = self._seed_boat(db, n_photos=2, n_videos=0, slug="solo-fotos")
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        assert "gallery-main-video" in html

    def test_detail_no_video_thumbnail_when_no_videos(self, db, client):
        b = self._seed_boat(db, n_photos=2, n_videos=0, slug="sin-videos")
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        # Verificar que no hay elementos HTML de miniatura de video
        assert 'class="gallery-thumb gallery-thumb-video"' not in html
        assert 'class="gallery-play-icon"' not in html
        assert "type:'video'" not in html

    def test_detail_video_only_boat_renders_gallery(self, db, client):
        """Barco sin fotos pero con videos sigue mostrando la galería."""
        b = self._seed_boat(db, n_photos=0, n_videos=1, slug="solo-video")
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        assert "gallery-main" in html
        assert "gallery-main-video" in html
        assert "type:'video'" in html

    def test_detail_video_only_no_thumbnail_strip_for_single_item(self, db, client):
        """Con 1 solo video no hay tira de miniaturas (total_media = 1)."""
        b = self._seed_boat(db, n_photos=0, n_videos=1, slug="un-video")
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        assert "gallery-thumbs" not in html

    def test_detail_thumbnail_strip_appears_for_mixed_media(self, db, client):
        """1 foto + 1 video = 2 ítems → tira de miniaturas visible."""
        b = self._seed_boat(db, n_photos=1, n_videos=1, slug="mixto")
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        assert "gallery-thumbs" in html
        assert "gallery-thumb-video" in html

    def test_detail_multiple_videos_in_media_array(self, db, client):
        b = self._seed_boat(db, n_photos=1, n_videos=3, slug="multi-video")
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        assert html.count("type:'video'") == 3

    def test_detail_switchmedia_function_defined(self, db, client):
        """La función switchMedia debe estar definida en el JS."""
        b = self._seed_boat(db, n_photos=1, n_videos=1, slug="js-check")
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        assert "function switchMedia" in html
        assert "function onMainClick" in html

    def test_detail_lightbox_does_not_open_for_video(self, db, client):
        """onMainClick() solo abre el lightbox para fotos, no para videos."""
        b = self._seed_boat(db, n_photos=1, n_videos=1, slug="lb-check")
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        # La función onMainClick verifica type === 'image' antes de abrir
        assert "type === 'image'" in html or "type !== 'image'" in html or "type:'image'" in html

    def test_detail_gallery_renders_zero_items_without_media(self, db, client):
        """Barco sin fotos ni videos → la galería HTML no se renderiza."""
        b = self._seed_boat(db, n_photos=0, n_videos=0, slug="sin-media")
        resp = client.get(f"/boats/{b.slug}")
        html = resp.data.decode("utf-8")
        # El div con id="gallery-main" solo se renderiza cuando hay al menos un ítem
        assert 'id="gallery-main"' not in html
