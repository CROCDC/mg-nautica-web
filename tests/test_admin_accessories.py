"""Integration tests for admin /accessories CRUD endpoints."""
import pytest

from app.models import Accessory, AccessoryCategory
from tests.factories import make_accessory


class TestAdminAccessoriesList:
    def test_list_returns_200(self, logged_in_admin):
        assert logged_in_admin.get("/admin/accessories").status_code == 200

    def test_list_shows_accessories(self, db, logged_in_admin):
        db.session.add(make_accessory(slug="chaleco-listado", title="Chaleco Listado"))
        db.session.commit()
        resp = logged_in_admin.get("/admin/accessories")
        assert b"Chaleco Listado" in resp.data

    def test_list_requires_login(self, client):
        resp = client.get("/admin/accessories", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]


class TestAdminAccessoriesNew:
    def test_new_form_renders(self, logged_in_admin):
        assert logged_in_admin.get("/admin/accessories/new").status_code == 200

    def test_create_success_redirects_to_edit(self, db, logged_in_admin):
        resp = logged_in_admin.post("/admin/accessories/new", data={
            "slug": "nuevo-accesorio",
            "title": "Accesorio Nuevo",
            "category": "onboard",
            "price_usd": "200",
            "stock": "5",
            "active": "on",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/accessories/" in resp.headers["Location"]

    def test_create_persists_to_db(self, db, app, logged_in_admin):
        logged_in_admin.post("/admin/accessories/new", data={
            "slug": "acc-persistido",
            "title": "Accesorio Persistido",
            "category": "boots",
            "price_usd": "150",
            "stock": "3",
        })
        with app.app_context():
            acc = db.session.query(Accessory).filter_by(slug="acc-persistido").one_or_none()
        assert acc is not None
        assert acc.title == "Accesorio Persistido"
        assert acc.category == AccessoryCategory.BOOTS

    def test_create_missing_slug_returns_400(self, logged_in_admin):
        resp = logged_in_admin.post("/admin/accessories/new", data={
            "title": "Sin Slug",
            "category": "onboard",
        })
        assert resp.status_code == 400

    def test_create_missing_title_returns_400(self, logged_in_admin):
        resp = logged_in_admin.post("/admin/accessories/new", data={
            "slug": "sin-titulo",
            "category": "onboard",
        })
        assert resp.status_code == 400

    def test_create_missing_category_returns_400(self, logged_in_admin):
        resp = logged_in_admin.post("/admin/accessories/new", data={
            "slug": "sin-categoria",
            "title": "Sin Categoría",
        })
        assert resp.status_code == 400

    def test_create_duplicate_slug_returns_400(self, db, logged_in_admin):
        db.session.add(make_accessory(slug="slug-dup"))
        db.session.commit()
        resp = logged_in_admin.post("/admin/accessories/new", data={
            "slug": "slug-dup",
            "title": "Otro Accesorio",
            "category": "onboard",
        })
        assert resp.status_code == 400


class TestAdminAccessoriesEdit:
    def test_edit_form_renders(self, db, logged_in_admin, accessory):
        resp = logged_in_admin.get(f"/admin/accessories/{accessory.id}/edit")
        assert resp.status_code == 200
        assert accessory.title.encode() in resp.data

    def test_edit_not_found_redirects_to_list(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/accessories/99999/edit", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/accessories" in resp.headers["Location"]

    def test_update_success_persists(self, db, app, logged_in_admin, accessory):
        logged_in_admin.post(f"/admin/accessories/{accessory.id}/edit", data={
            "slug": accessory.slug,
            "title": "Título Actualizado",
            "category": "onboard",
            "price_usd": "300",
            "stock": "10",
            "active": "on",
        })
        with app.app_context():
            updated = db.session.get(Accessory, accessory.id)
        assert updated.title == "Título Actualizado"
        assert updated.price_usd == 300

    def test_update_success_redirects_to_edit(self, db, logged_in_admin, accessory):
        resp = logged_in_admin.post(f"/admin/accessories/{accessory.id}/edit", data={
            "slug": accessory.slug,
            "title": "X",
            "category": "onboard",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert f"/admin/accessories/{accessory.id}" in resp.headers["Location"]

    def test_update_missing_title_returns_400(self, db, logged_in_admin, accessory):
        resp = logged_in_admin.post(f"/admin/accessories/{accessory.id}/edit", data={
            "slug": accessory.slug,
            "category": "onboard",
        })
        assert resp.status_code == 400

    def test_update_duplicate_slug_returns_400(self, db, logged_in_admin, accessory):
        other = make_accessory(slug="otro-slug-distinto")
        db.session.add(other)
        db.session.commit()
        resp = logged_in_admin.post(f"/admin/accessories/{accessory.id}/edit", data={
            "slug": "otro-slug-distinto",
            "title": "X",
            "category": "onboard",
        })
        assert resp.status_code == 400

    def test_update_same_slug_does_not_conflict(self, db, logged_in_admin, accessory):
        resp = logged_in_admin.post(f"/admin/accessories/{accessory.id}/edit", data={
            "slug": accessory.slug,
            "title": "Mismo Slug OK",
            "category": "onboard",
        }, follow_redirects=False)
        assert resp.status_code == 302


class TestAdminAccessoriesDelete:
    def test_delete_removes_accessory(self, db, app, logged_in_admin, accessory):
        acc_id = accessory.id
        logged_in_admin.post(f"/admin/accessories/{acc_id}/delete")
        with app.app_context():
            assert db.session.get(Accessory, acc_id) is None

    def test_delete_redirects_to_list(self, db, logged_in_admin, accessory):
        resp = logged_in_admin.post(
            f"/admin/accessories/{accessory.id}/delete",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/admin/accessories" in resp.headers["Location"]

    def test_delete_not_found_redirects(self, logged_in_admin):
        resp = logged_in_admin.post("/admin/accessories/99999/delete", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/accessories" in resp.headers["Location"]
