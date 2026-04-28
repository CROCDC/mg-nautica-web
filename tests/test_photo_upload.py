"""Unit and integration tests for photo file upload (boats and accessories)."""
import base64
import io
from unittest.mock import MagicMock

import pytest

from app.models import Accessory, BoatPhoto

# Minimal 1×1 PNG — no external dependencies needed
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)


# ── Unit tests: _save_photo_file ──────────────────────────────────────────────

class TestSavePhotoFile:
    def _mock_file(self, filename: str) -> MagicMock:
        f = MagicMock()
        f.filename = filename
        f.save = MagicMock()
        return f

    def test_valid_jpg(self, app):
        from app.admin.boats import _save_photo_file
        with app.app_context():
            url = _save_photo_file(self._mock_file("photo.jpg"))
        assert url is not None
        assert url.startswith("/uploads/")
        assert url.endswith(".jpg")

    def test_valid_png(self, app):
        from app.admin.boats import _save_photo_file
        with app.app_context():
            url = _save_photo_file(self._mock_file("imagen.PNG"))
        assert url is not None
        assert url.endswith(".png")

    def test_valid_webp(self, app):
        from app.admin.boats import _save_photo_file
        with app.app_context():
            url = _save_photo_file(self._mock_file("foto.webp"))
        assert url is not None
        assert url.endswith(".webp")

    def test_invalid_extension_returns_none(self, app):
        from app.admin.boats import _save_photo_file
        with app.app_context():
            url = _save_photo_file(self._mock_file("malware.exe"))
        assert url is None

    def test_pdf_extension_returns_none(self, app):
        from app.admin.boats import _save_photo_file
        with app.app_context():
            url = _save_photo_file(self._mock_file("doc.pdf"))
        assert url is None

    def test_empty_filename_returns_none(self, app):
        from app.admin.boats import _save_photo_file
        with app.app_context():
            url = _save_photo_file(self._mock_file(""))
        assert url is None

    def test_none_file_returns_none(self, app):
        from app.admin.boats import _save_photo_file
        with app.app_context():
            url = _save_photo_file(None)
        assert url is None

    def test_unique_filenames_per_call(self, app):
        from app.admin.boats import _save_photo_file
        with app.app_context():
            url1 = _save_photo_file(self._mock_file("a.jpg"))
            url2 = _save_photo_file(self._mock_file("a.jpg"))
        assert url1 != url2

    def test_original_filename_not_used(self, app):
        from app.admin.boats import _save_photo_file
        with app.app_context():
            url = _save_photo_file(self._mock_file("mi foto secreta.jpg"))
        assert "mi foto secreta" not in url
        assert " " not in url

    def test_file_save_called_once(self, app):
        from app.admin.boats import _save_photo_file
        f = self._mock_file("test.jpg")
        with app.app_context():
            _save_photo_file(f)
        f.save.assert_called_once()


# ── Integration tests: boats photo upload ────────────────────────────────────

class TestBoatsPhotoUpload:
    def test_add_single_photo_creates_db_record(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/add",
            data={"photos": (io.BytesIO(TINY_PNG), "foto.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        photos = db.session.query(BoatPhoto).filter_by(boat_id=boat.id).all()
        assert len(photos) == 1
        assert photos[0].url.startswith("/uploads/")
        assert photos[0].url.endswith(".png")

    def test_add_multiple_photos(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/add",
            data={"photos": [
                (io.BytesIO(TINY_PNG), "a.png"),
                (io.BytesIO(TINY_PNG), "b.png"),
                (io.BytesIO(TINY_PNG), "c.png"),
            ]},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        count = db.session.query(BoatPhoto).filter_by(boat_id=boat.id).count()
        assert count == 3

    def test_first_photo_is_primary_on_empty_boat(self, db, logged_in_admin, boat):
        logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/add",
            data={"photos": [
                (io.BytesIO(TINY_PNG), "first.png"),
                (io.BytesIO(TINY_PNG), "second.png"),
            ]},
            content_type="multipart/form-data",
        )
        photos = (
            db.session.query(BoatPhoto)
            .filter_by(boat_id=boat.id)
            .order_by(BoatPhoto.position)
            .all()
        )
        assert photos[0].is_primary is True
        assert photos[1].is_primary is False

    def test_positions_increment_correctly(self, db, logged_in_admin, boat):
        logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/add",
            data={"photos": [
                (io.BytesIO(TINY_PNG), "p1.png"),
                (io.BytesIO(TINY_PNG), "p2.png"),
            ]},
            content_type="multipart/form-data",
        )
        photos = (
            db.session.query(BoatPhoto)
            .filter_by(boat_id=boat.id)
            .order_by(BoatPhoto.position)
            .all()
        )
        positions = [p.position for p in photos]
        assert positions == sorted(positions)
        assert len(set(positions)) == len(positions)

    def test_invalid_extension_returns_error_flash(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/add",
            data={"photos": (io.BytesIO(b"not an image"), "virus.exe")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "válida" in resp.data.decode("utf-8")
        assert db.session.query(BoatPhoto).filter_by(boat_id=boat.id).count() == 0

    def test_no_file_returns_error_flash(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/add",
            data={},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert db.session.query(BoatPhoto).filter_by(boat_id=boat.id).count() == 0

    def test_new_boat_with_photos(self, db, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/boats/new/complete",
            data={
                "slug": "nuevo-con-fotos",
                "title": "Nuevo Con Fotos",
                "boat_type": "sailboat",
                "flag": "AR",
                "price_usd": "10000",
                "photos": [
                    (io.BytesIO(TINY_PNG), "foto1.png"),
                    (io.BytesIO(TINY_PNG), "foto2.png"),
                ],
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        from app.models import Boat
        b = db.session.query(Boat).filter_by(slug="nuevo-con-fotos").first()
        assert b is not None
        photos = db.session.query(BoatPhoto).filter_by(boat_id=b.id).all()
        assert len(photos) == 2
        assert photos[0].is_primary is True

    def test_new_boat_with_specs(self, db, logged_in_admin):
        from app.models import Boat, BoatSpecs
        resp = logged_in_admin.post(
            "/admin/boats/new/complete",
            data={
                "slug": "barco-con-specs",
                "title": "Barco Con Specs",
                "boat_type": "sailboat",
                "flag": "AR",
                "price_usd": "30000",
                "engine_brand": "Volvo Penta",
                "engine_hp": "55",
                "cabins_qty": "2",
                "electronics_starlink": "on",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        b = db.session.query(Boat).filter_by(slug="barco-con-specs").first()
        assert b is not None
        specs = db.session.query(BoatSpecs).filter_by(boat_id=b.id).first()
        assert specs is not None
        assert specs.engine_brand == "Volvo Penta"
        assert specs.engine_hp == 55
        assert specs.cabins_qty == 2
        assert specs.electronics_starlink is True

    def test_new_boat_without_specs_does_not_create_specs_record(self, db, logged_in_admin):
        from app.models import Boat, BoatSpecs
        logged_in_admin.post(
            "/admin/boats/new/complete",
            data={
                "slug": "barco-sin-specs",
                "title": "Barco Sin Specs",
                "boat_type": "motorboat",
                "flag": "UY",
                "price_usd": "5000",
            },
            content_type="multipart/form-data",
        )
        b = db.session.query(Boat).filter_by(slug="barco-sin-specs").first()
        assert db.session.query(BoatSpecs).filter_by(boat_id=b.id).first() is None

    def test_new_boat_auto_generates_slug_from_title(self, db, logged_in_admin):
        from app.models import Boat
        logged_in_admin.post(
            "/admin/boats/new/complete",
            data={"title": "Jeanneau Sun Odyssey", "boat_type": "sailboat", "flag": "AR", "price_usd": "0"},
            content_type="multipart/form-data",
        )
        b = db.session.query(Boat).filter_by(slug="jeanneau-sun-odyssey").first()
        assert b is not None

    def test_new_boat_slug_deduplication(self, db, logged_in_admin):
        from app.models import Boat
        for _ in range(3):
            logged_in_admin.post(
                "/admin/boats/new/complete",
                data={"title": "Velero Repetido", "boat_type": "sailboat", "flag": "AR", "price_usd": "0"},
                content_type="multipart/form-data",
            )
        slugs = [b.slug for b in db.session.query(Boat).all()]
        assert len(slugs) == len(set(slugs))

    def test_new_boat_without_photos(self, db, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/boats/new/complete",
            data={
                "slug": "sin-fotos",
                "title": "Sin Fotos",
                "boat_type": "motorboat",
                "flag": "UY",
                "price_usd": "5000",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        from app.models import Boat
        b = db.session.query(Boat).filter_by(slug="sin-fotos").first()
        assert b is not None
        assert db.session.query(BoatPhoto).filter_by(boat_id=b.id).count() == 0


# ── Integration tests: simple boat creation flow ─────────────────────────────

class TestBoatsSimpleFlow:
    def test_simple_create_only_requires_title(self, db, logged_in_admin):
        from app.models import Boat
        resp = logged_in_admin.post(
            "/admin/boats/new/simple",
            data={"title": "Velero Simple"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        b = db.session.query(Boat).filter_by(slug="velero-simple").first()
        assert b is not None
        assert b.boat_type is None
        assert b.flag is None

    def test_simple_create_with_all_fields(self, db, logged_in_admin):
        from app.models import Boat
        resp = logged_in_admin.post(
            "/admin/boats/new/simple",
            data={
                "title": "Bavaria 40",
                "description": "Barco en excelente estado.",
                "year": "2015",
                "length_m": "11.90",
                "draft_m": "1.80",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        b = db.session.query(Boat).filter_by(slug="bavaria-40").first()
        assert b is not None
        assert b.year == 2015
        assert float(b.length_m) == 11.90
        assert float(b.draft_m) == 1.80

    def test_simple_create_with_photos(self, db, logged_in_admin):
        from app.models import Boat
        resp = logged_in_admin.post(
            "/admin/boats/new/simple",
            data={
                "title": "Barco Con Fotos Simple",
                "photos": [
                    (io.BytesIO(TINY_PNG), "f1.png"),
                    (io.BytesIO(TINY_PNG), "f2.png"),
                ],
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        b = db.session.query(Boat).filter_by(slug="barco-con-fotos-simple").first()
        assert db.session.query(BoatPhoto).filter_by(boat_id=b.id).count() == 2

    def test_simple_create_missing_title_returns_400(self, db, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/boats/new/simple",
            data={"year": "2020"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_simple_create_autogenerates_slug(self, db, logged_in_admin):
        from app.models import Boat
        logged_in_admin.post(
            "/admin/boats/new/simple",
            data={"title": "Jeanneau 54 DS"},
            content_type="multipart/form-data",
        )
        assert db.session.query(Boat).filter_by(slug="jeanneau-54-ds").first() is not None

    def test_simple_redirects_to_edit(self, db, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/boats/new/simple",
            data={"title": "Redirect Test"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        assert "/edit" in resp.headers["Location"]


# ── Integration tests: accessories photo upload ───────────────────────────────

class TestAccessoriesPhotoUpload:
    def test_new_accessory_with_photo(self, db, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/accessories/new",
            data={
                "slug": "acc-con-foto",
                "title": "Accesorio Con Foto",
                "category": "onboard",
                "price_usd": "99",
                "stock": "5",
                "active": "on",
                "photo": (io.BytesIO(TINY_PNG), "foto.png"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        acc = db.session.query(Accessory).filter_by(slug="acc-con-foto").first()
        assert acc is not None
        assert acc.photo_url is not None
        assert acc.photo_url.startswith("/uploads/")

    def test_new_accessory_without_photo(self, db, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/accessories/new",
            data={
                "slug": "acc-sin-foto",
                "title": "Accesorio Sin Foto",
                "category": "onboard",
                "price_usd": "50",
                "stock": "1",
                "active": "on",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        acc = db.session.query(Accessory).filter_by(slug="acc-sin-foto").first()
        assert acc is not None
        assert acc.photo_url is None

    def test_edit_accessory_replaces_photo(self, db, logged_in_admin, accessory):
        accessory.photo_url = "/uploads/old-photo.jpg"
        db.session.commit()

        resp = logged_in_admin.post(
            f"/admin/accessories/{accessory.id}/edit",
            data={
                "slug": accessory.slug,
                "title": accessory.title,
                "category": accessory.category.value,
                "price_usd": str(accessory.price_usd),
                "stock": str(accessory.stock),
                "active": "on",
                "photo": (io.BytesIO(TINY_PNG), "nueva-foto.png"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        db.session.refresh(accessory)
        assert accessory.photo_url != "/uploads/old-photo.jpg"
        assert accessory.photo_url.startswith("/uploads/")

    def test_edit_accessory_keeps_photo_when_no_file(self, db, logged_in_admin, accessory):
        accessory.photo_url = "/uploads/existing-photo.jpg"
        db.session.commit()

        resp = logged_in_admin.post(
            f"/admin/accessories/{accessory.id}/edit",
            data={
                "slug": accessory.slug,
                "title": accessory.title,
                "category": accessory.category.value,
                "price_usd": str(accessory.price_usd),
                "stock": str(accessory.stock),
                "active": "on",
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        db.session.refresh(accessory)
        assert accessory.photo_url == "/uploads/existing-photo.jpg"

    def test_edit_accessory_invalid_extension_keeps_old_photo(self, db, logged_in_admin, accessory):
        accessory.photo_url = "/uploads/keep-me.jpg"
        db.session.commit()

        resp = logged_in_admin.post(
            f"/admin/accessories/{accessory.id}/edit",
            data={
                "slug": accessory.slug,
                "title": accessory.title,
                "category": accessory.category.value,
                "price_usd": str(accessory.price_usd),
                "stock": str(accessory.stock),
                "active": "on",
                "photo": (io.BytesIO(b"not an image"), "hack.exe"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302
        db.session.refresh(accessory)
        assert accessory.photo_url == "/uploads/keep-me.jpg"
