"""Integration tests for the /admin blueprint."""
import pytest

from app.models import BoatStatus, BoatType, Flag, UserRole
from tests.factories import make_boat, make_user


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestAdminAuth:
    def test_dashboard_requires_login(self, client):
        resp = client.get("/admin/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_login_page_renders(self, client):
        assert client.get("/admin/login").status_code == 200

    def test_login_with_wrong_password_returns_401(self, db, client, admin_user):
        resp = client.post("/admin/login", data={
            "email": admin_user.email,
            "password": "wrong-password",
        })
        assert resp.status_code == 401

    def test_login_with_inactive_user_returns_401(self, db, client):
        u = make_user(email="inactive@mg.com", password="pass123", active=False)
        db.session.add(u)
        db.session.commit()
        resp = client.post("/admin/login", data={
            "email": "inactive@mg.com",
            "password": "pass123",
        })
        assert resp.status_code == 401

    def test_login_success_redirects_to_dashboard(self, db, client, admin_user):
        resp = client.post("/admin/login", data={
            "email": admin_user.email,
            "password": "admin-pass",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin" in resp.headers["Location"]

    def test_logout_redirects_to_login(self, logged_in_admin):
        resp = logged_in_admin.post("/admin/logout", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_editor_cannot_access_users(self, db, client):
        editor = make_user(email="editor@mg.com", password="pass123", role=UserRole.EDITOR)
        db.session.add(editor)
        db.session.commit()
        client.post("/admin/login", data={"email": "editor@mg.com", "password": "pass123"})
        resp = client.get("/admin/users", follow_redirects=False)
        assert resp.status_code in (302, 403)


# ── Dashboard ─────────────────────────────────────────────────────────────────

class TestAdminDashboard:
    def test_dashboard_returns_200(self, logged_in_admin):
        assert logged_in_admin.get("/admin/").status_code == 200

    def test_dashboard_shows_stats(self, db, logged_in_admin):
        db.session.add(make_boat(slug="stat-boat"))
        db.session.commit()
        resp = logged_in_admin.get("/admin/")
        assert resp.status_code == 200
        assert b"1" in resp.data


# ── Boats CRUD ────────────────────────────────────────────────────────────────

class TestAdminBoats:
    def test_boats_list_returns_200(self, logged_in_admin):
        assert logged_in_admin.get("/admin/boats").status_code == 200

    def test_boats_new_form_renders(self, logged_in_admin):
        assert logged_in_admin.get("/admin/boats/new").status_code == 200

    def test_create_boat_redirects(self, db, logged_in_admin):
        resp = logged_in_admin.post("/admin/boats/new/complete", data={
            "slug": "nuevo-velero-admin",
            "title": "Velero creado vía admin",
            "description": "Descripción de prueba.",
            "price_usd": "35000",
            "boat_type": "sailboat",
            "flag": "AR",
            "status": "available",
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_create_boat_persists_to_db(self, db, app, logged_in_admin):
        logged_in_admin.post("/admin/boats/new/complete", data={
            "slug": "velero-persistido",
            "title": "Velero Persistido",
            "description": "Test.",
            "price_usd": "20000",
            "boat_type": "sailboat",
            "flag": "UY",
            "status": "available",
        })
        from app.models import Boat
        with app.app_context():
            boat = db.session.query(Boat).filter_by(slug="velero-persistido").one_or_none()
        assert boat is not None
        assert boat.title == "Velero Persistido"

    def test_create_boat_duplicate_slug_returns_400(self, db, logged_in_admin):
        db.session.add(make_boat(slug="slug-existente"))
        db.session.commit()
        resp = logged_in_admin.post("/admin/boats/new/complete", data={
            "slug": "slug-existente",
            "title": "Otro",
            "description": "",
            "price_usd": "10000",
            "boat_type": "sailboat",
            "flag": "AR",
            "status": "available",
        })
        assert resp.status_code == 400

    def test_edit_boat_form_renders(self, db, logged_in_admin, boat):
        resp = logged_in_admin.get(f"/admin/boats/{boat.id}/edit")
        assert resp.status_code == 200
        assert boat.title.encode() in resp.data

    def test_edit_boat_updates_title(self, db, app, logged_in_admin, boat):
        logged_in_admin.post(f"/admin/boats/{boat.id}/edit", data={
            "slug": boat.slug,
            "title": "Título Actualizado",
            "description": "Nueva descripción.",
            "price_usd": "50000",
            "boat_type": "sailboat",
            "flag": "AR",
            "status": "available",
        })
        from app.models import Boat
        with app.app_context():
            updated = db.session.get(Boat, boat.id)
        assert updated.title == "Título Actualizado"

    def test_delete_boat(self, db, app, logged_in_admin, boat):
        boat_id = boat.id
        logged_in_admin.post(f"/admin/boats/{boat_id}/delete")
        from app.models import Boat
        with app.app_context():
            assert db.session.get(Boat, boat_id) is None


# ── Users CRUD (admin-only) ───────────────────────────────────────────────────

class TestAdminUsers:
    def test_users_list_returns_200_for_admin(self, logged_in_admin):
        assert logged_in_admin.get("/admin/users").status_code == 200

    def test_create_user(self, db, app, logged_in_admin):
        logged_in_admin.post("/admin/users/new", data={
            "email": "nuevo@mg.com",
            "name": "Nuevo Usuario",
            "password": "securepass123",
            "role": "editor",
            "active": "1",
        })
        from app.models import User
        with app.app_context():
            user = db.session.query(User).filter_by(email="nuevo@mg.com").one_or_none()
        assert user is not None
        assert user.role == UserRole.EDITOR

    def test_cannot_delete_last_admin(self, db, logged_in_admin, admin_user):
        resp = logged_in_admin.post(f"/admin/users/{admin_user.id}/delete",
                                    follow_redirects=True)
        assert resp.status_code == 200
        from app.models import User
        assert db.session.get(User, admin_user.id) is not None
