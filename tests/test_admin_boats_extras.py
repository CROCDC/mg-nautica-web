"""Integration tests for admin boat photo and specs endpoints."""
import base64
import io

import pytest

from app.models import Boat, BoatPhoto, BoatSpecs
from tests.factories import make_boat

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)

_VALID_BOAT_DATA = {
    "slug": "velero-cobertura",
    "title": "Velero Cobertura",
    "description": "",
    "price_usd": "45000",
    "boat_type": "sailboat",
    "flag": "AR",
    "status": "available",
}


# ── Boat Photos ────────────────────────────────────────────────────────────────

class TestAdminBoatPhotoAdd:
    def test_add_photo_persists_to_db(self, db, app, logged_in_admin, boat):
        logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/add",
            data={"photos": (io.BytesIO(_TINY_PNG), "nueva-foto.png")},
            content_type="multipart/form-data",
        )
        b = db.session.get(Boat, boat.id)
        assert len(b.photos) == 1
        assert b.photos[0].url.startswith("/uploads/")

    def test_first_photo_is_marked_primary(self, db, app, logged_in_admin, boat):
        logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/add",
            data={"photos": (io.BytesIO(_TINY_PNG), "primaria.png")},
            content_type="multipart/form-data",
        )
        b = db.session.get(Boat, boat.id)
        assert b.photos[0].is_primary is True

    def test_second_photo_is_not_primary(self, db, app, logged_in_admin, boat_with_photo):
        logged_in_admin.post(
            f"/admin/boats/{boat_with_photo.id}/photos/add",
            data={"photos": (io.BytesIO(_TINY_PNG), "segunda.png")},
            content_type="multipart/form-data",
        )
        b = db.session.get(Boat, boat_with_photo.id)
        new_photo = next(p for p in b.photos if p.url.startswith("/uploads/"))
        assert new_photo.is_primary is False

    def test_add_photo_redirects_to_edit(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/add",
            data={"photos": (io.BytesIO(_TINY_PNG), "foto.png")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert f"/admin/boats/{boat.id}/edit" in resp.headers["Location"]

    def test_empty_url_redirects_without_adding(self, db, app, logged_in_admin, boat):
        logged_in_admin.post(f"/admin/boats/{boat.id}/photos/add", data={"url": ""})
        with app.app_context():
            b = db.session.get(Boat, boat.id)
            assert len(b.photos) == 0

    def test_boat_not_found_redirects_to_list(self, logged_in_admin):
        resp = logged_in_admin.post("/admin/boats/99999/photos/add", data={
            "url": "https://example.com/foto.jpg",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/boats" in resp.headers["Location"]

    def test_photo_positions_increment(self, db, app, logged_in_admin, boat_with_photo):
        logged_in_admin.post(f"/admin/boats/{boat_with_photo.id}/photos/add", data={
            "url": "https://example.com/pos1.jpg",
        })
        with app.app_context():
            b = db.session.get(Boat, boat_with_photo.id)
            positions = sorted(p.position for p in b.photos)
            assert positions == list(range(len(positions)))


class TestAdminBoatPhotoDelete:
    def test_delete_removes_photo(self, db, app, logged_in_admin, boat_with_photo):
        photo_id = boat_with_photo.photos[0].id
        logged_in_admin.post(
            f"/admin/boats/{boat_with_photo.id}/photos/{photo_id}/delete",
        )
        with app.app_context():
            assert db.session.get(BoatPhoto, photo_id) is None

    def test_delete_redirects_to_edit(self, db, logged_in_admin, boat_with_photo):
        photo_id = boat_with_photo.photos[0].id
        resp = logged_in_admin.post(
            f"/admin/boats/{boat_with_photo.id}/photos/{photo_id}/delete",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert f"/admin/boats/{boat_with_photo.id}/edit" in resp.headers["Location"]

    def test_delete_wrong_boat_id_does_not_delete(self, db, app, logged_in_admin, boat_with_photo):
        other = make_boat(slug="otro-barco-foto")
        db.session.add(other)
        db.session.commit()
        photo_id = boat_with_photo.photos[0].id
        logged_in_admin.post(
            f"/admin/boats/{other.id}/photos/{photo_id}/delete",
        )
        with app.app_context():
            assert db.session.get(BoatPhoto, photo_id) is not None

    def test_delete_not_found_redirects(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/photos/99999/delete",
            follow_redirects=False,
        )
        assert resp.status_code == 302


# ── Boat Specs ─────────────────────────────────────────────────────────────────

class TestAdminBoatSpecsSave:
    def test_creates_new_specs(self, db, app, logged_in_admin, boat):
        logged_in_admin.post(f"/admin/boats/{boat.id}/specs", data={
            "engine_brand": "Volvo Penta D2-75",
            "engine_hp": "75",
            "cabins_qty": "3",
            "bathrooms_qty": "2",
        })
        with app.app_context():
            b = db.session.get(Boat, boat.id)
            assert b.specs is not None
            assert b.specs.engine_brand == "Volvo Penta D2-75"
            assert b.specs.engine_hp == 75
            assert b.specs.cabins_qty == 3

    def test_updates_existing_specs(self, db, app, logged_in_admin, boat):
        specs = BoatSpecs(boat_id=boat.id, engine_brand="Motor Viejo", engine_hp=50)
        db.session.add(specs)
        db.session.commit()
        logged_in_admin.post(f"/admin/boats/{boat.id}/specs", data={
            "engine_brand": "Motor Nuevo",
            "engine_hp": "120",
        })
        with app.app_context():
            b = db.session.get(Boat, boat.id)
            assert b.specs.engine_brand == "Motor Nuevo"
            assert b.specs.engine_hp == 120

    def test_bool_fields_on(self, db, app, logged_in_admin, boat):
        logged_in_admin.post(f"/admin/boats/{boat.id}/specs", data={
            "bow_thruster": "on",
            "electronics_starlink": "on",
        })
        with app.app_context():
            b = db.session.get(Boat, boat.id)
            assert b.specs.bow_thruster is True
            assert b.specs.electronics_starlink is True

    def test_bool_fields_off_when_absent(self, db, app, logged_in_admin, boat):
        logged_in_admin.post(f"/admin/boats/{boat.id}/specs", data={
            "engine_brand": "Motor",
        })
        with app.app_context():
            b = db.session.get(Boat, boat.id)
            assert b.specs.bow_thruster is False
            assert b.specs.electronics_starlink is False

    def test_empty_string_fields_stored_as_none(self, db, app, logged_in_admin, boat):
        logged_in_admin.post(f"/admin/boats/{boat.id}/specs", data={
            "engine_brand": "   ",
            "propeller": "",
        })
        with app.app_context():
            b = db.session.get(Boat, boat.id)
            assert b.specs.engine_brand is None
            assert b.specs.propeller is None

    def test_redirects_to_edit_on_success(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(
            f"/admin/boats/{boat.id}/specs", data={}, follow_redirects=False,
        )
        assert resp.status_code == 302
        assert f"/admin/boats/{boat.id}/edit" in resp.headers["Location"]

    def test_boat_not_found_redirects_to_list(self, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/boats/99999/specs", data={}, follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/admin/boats" in resp.headers["Location"]


# ── Boats list search ──────────────────────────────────────────────────────────

class TestAdminBoatsList:
    def test_list_returns_200(self, db, logged_in_admin):
        assert logged_in_admin.get("/admin/boats").status_code == 200

    def test_search_filters_results(self, db, logged_in_admin):
        db.session.add(make_boat(slug="bavaria", title="Bavaria 46"))
        db.session.add(make_boat(slug="beneteau", title="Beneteau 40"))
        db.session.commit()
        resp = logged_in_admin.get("/admin/boats?q=Bavaria")
        assert b"Bavaria 46" in resp.data
        assert b"Beneteau 40" not in resp.data

    def test_empty_search_returns_all(self, db, logged_in_admin):
        db.session.add(make_boat(slug="b1", title="Velero Uno"))
        db.session.add(make_boat(slug="b2", title="Velero Dos"))
        db.session.commit()
        resp = logged_in_admin.get("/admin/boats?q=")
        assert b"Velero Uno" in resp.data
        assert b"Velero Dos" in resp.data


# ── boats_new validation ───────────────────────────────────────────────────────

class TestAdminBoatsNewValidation:
    def test_missing_required_fields_returns_400(self, db, logged_in_admin):
        resp = logged_in_admin.post("/admin/boats/new/complete", data={
            "slug": "",
            "title": "",
            "price_usd": "10000",
            "boat_type": "sailboat",
            "flag": "AR",
            "status": "available",
        })
        assert resp.status_code == 400

    def test_missing_boat_type_returns_400(self, db, logged_in_admin):
        resp = logged_in_admin.post("/admin/boats/new/complete", data={
            "slug": "sin-tipo",
            "title": "Sin Tipo",
            "price_usd": "10000",
            "boat_type": "",
            "flag": "AR",
            "status": "available",
        })
        assert resp.status_code == 400

    def test_with_photo_file_creates_photo(self, db, logged_in_admin):
        data = {**_VALID_BOAT_DATA, "slug": "con-foto-file",
                "photos": (io.BytesIO(_TINY_PNG), "foto.png")}
        logged_in_admin.post("/admin/boats/new/complete", data=data,
                             content_type="multipart/form-data")
        b = db.session.query(Boat).filter_by(slug="con-foto-file").one_or_none()
        assert b is not None
        assert len(b.photos) == 1
        assert b.photos[0].url.startswith("/uploads/")

    def test_without_photo_url_creates_no_photos(self, db, app, logged_in_admin):
        data = {**_VALID_BOAT_DATA, "slug": "sin-foto-url"}
        logged_in_admin.post("/admin/boats/new/complete", data=data)
        with app.app_context():
            b = db.session.query(Boat).filter_by(slug="sin-foto-url").one_or_none()
            assert b is not None
            assert len(b.photos) == 0


# ── boats_edit coverage ────────────────────────────────────────────────────────

class TestAdminBoatsEditCoverage:
    def test_not_found_redirects(self, db, logged_in_admin):
        resp = logged_in_admin.get("/admin/boats/99999/edit")
        assert resp.status_code == 302
        assert "/admin/boats" in resp.headers["Location"]

    def test_post_not_found_redirects(self, db, logged_in_admin):
        resp = logged_in_admin.post("/admin/boats/99999/edit", data=_VALID_BOAT_DATA)
        assert resp.status_code == 302
        assert "/admin/boats" in resp.headers["Location"]

    def test_missing_required_fields_returns_400(self, db, logged_in_admin, boat):
        resp = logged_in_admin.post(f"/admin/boats/{boat.id}/edit", data={
            "slug": "",
            "title": "",
            "price_usd": "10000",
            "boat_type": "sailboat",
            "flag": "AR",
            "status": "available",
        })
        assert resp.status_code == 400

    def test_duplicate_slug_returns_400(self, db, logged_in_admin, boat):
        other = make_boat(slug="otro-slug")
        db.session.add(other)
        db.session.commit()
        resp = logged_in_admin.post(f"/admin/boats/{boat.id}/edit", data={
            **_VALID_BOAT_DATA,
            "slug": "otro-slug",
        })
        assert resp.status_code == 400


# ── boats_delete coverage ──────────────────────────────────────────────────────

class TestAdminBoatsDeleteCoverage:
    def test_not_found_redirects(self, db, logged_in_admin):
        resp = logged_in_admin.post("/admin/boats/99999/delete", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/boats" in resp.headers["Location"]
