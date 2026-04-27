"""Integration tests for admin user edit and delete endpoints."""
import pytest

from app.models import User, UserRole
from tests.factories import make_user


# ── New user form ──────────────────────────────────────────────────────────────

class TestAdminUsersNewExtended:
    def test_new_form_renders(self, logged_in_admin):
        assert logged_in_admin.get("/admin/users/new").status_code == 200

    def test_create_short_password_returns_400(self, db, logged_in_admin):
        resp = logged_in_admin.post("/admin/users/new", data={
            "email": "short@mg.com",
            "password": "abc123",  # less than 8 chars
            "role": "editor",
        })
        assert resp.status_code == 400

    def test_create_duplicate_email_returns_400(self, db, logged_in_admin, admin_user):
        resp = logged_in_admin.post("/admin/users/new", data={
            "email": admin_user.email,
            "password": "securepass123",
            "role": "editor",
        })
        assert resp.status_code == 400

    def test_create_missing_email_returns_400(self, logged_in_admin):
        resp = logged_in_admin.post("/admin/users/new", data={
            "password": "securepass123",
            "role": "editor",
        })
        assert resp.status_code == 400

    def test_create_redirects_to_users_list(self, db, logged_in_admin):
        resp = logged_in_admin.post("/admin/users/new", data={
            "email": "nuevo2@mg.com",
            "name": "Nuevo 2",
            "password": "securepass123",
            "role": "editor",
            "active": "1",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/users" in resp.headers["Location"]


# ── Edit user ──────────────────────────────────────────────────────────────────

class TestAdminUsersEdit:
    def test_edit_form_renders(self, db, logged_in_admin, admin_user):
        resp = logged_in_admin.get(f"/admin/users/{admin_user.id}/edit")
        assert resp.status_code == 200
        assert admin_user.email.encode() in resp.data

    def test_edit_not_found_redirects(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/users/99999/edit", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/users" in resp.headers["Location"]

    def test_update_name_persists(self, db, app, logged_in_admin):
        user = make_user(email="editar@mg.com", password="pass1234", role=UserRole.EDITOR)
        db.session.add(user)
        db.session.commit()
        logged_in_admin.post(f"/admin/users/{user.id}/edit", data={
            "email": "editar@mg.com",
            "name": "Nombre Actualizado",
            "role": "editor",
            "active": "on",
        })
        with app.app_context():
            updated = db.session.get(User, user.id)
        assert updated.name == "Nombre Actualizado"

    def test_update_role_persists(self, db, app, logged_in_admin):
        user = make_user(email="rol@mg.com", password="pass1234", role=UserRole.EDITOR)
        db.session.add(user)
        db.session.commit()
        logged_in_admin.post(f"/admin/users/{user.id}/edit", data={
            "email": "rol@mg.com",
            "role": "admin",
            "active": "on",
        })
        with app.app_context():
            updated = db.session.get(User, user.id)
        assert updated.role == UserRole.ADMIN

    def test_update_password_changes_login(self, db, app, logged_in_admin):
        user = make_user(email="pwd@mg.com", password="oldpass1")
        db.session.add(user)
        db.session.commit()
        logged_in_admin.post(f"/admin/users/{user.id}/edit", data={
            "email": "pwd@mg.com",
            "role": "editor",
            "active": "on",
            "password": "newpass99",
        })
        with app.app_context():
            updated = db.session.get(User, user.id)
        assert updated.check_password("newpass99")

    def test_update_empty_email_returns_400(self, db, logged_in_admin, admin_user):
        resp = logged_in_admin.post(f"/admin/users/{admin_user.id}/edit", data={
            "email": "",
            "role": "admin",
            "active": "on",
        })
        assert resp.status_code == 400

    def test_update_short_password_returns_400(self, db, logged_in_admin):
        user = make_user(email="pwdshort@mg.com", password="pass1234")
        db.session.add(user)
        db.session.commit()
        resp = logged_in_admin.post(f"/admin/users/{user.id}/edit", data={
            "email": "pwdshort@mg.com",
            "role": "editor",
            "active": "on",
            "password": "abc",
        })
        assert resp.status_code == 400

    def test_update_duplicate_email_returns_400(self, db, logged_in_admin, admin_user):
        other = make_user(email="otro@mg.com", password="pass1234")
        db.session.add(other)
        db.session.commit()
        resp = logged_in_admin.post(f"/admin/users/{other.id}/edit", data={
            "email": admin_user.email,
            "role": "editor",
            "active": "on",
        })
        assert resp.status_code == 400

    def test_update_success_redirects_to_users_list(self, db, logged_in_admin):
        user = make_user(email="redirect@mg.com", password="pass1234")
        db.session.add(user)
        db.session.commit()
        resp = logged_in_admin.post(f"/admin/users/{user.id}/edit", data={
            "email": "redirect@mg.com",
            "role": "editor",
            "active": "on",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/users" in resp.headers["Location"]


# ── Delete user ────────────────────────────────────────────────────────────────

class TestAdminUsersDelete:
    def test_delete_editor_removes_user(self, db, app, logged_in_admin):
        editor = make_user(email="editor-borrar@mg.com", password="pass1234", role=UserRole.EDITOR)
        db.session.add(editor)
        db.session.commit()
        editor_id = editor.id
        logged_in_admin.post(f"/admin/users/{editor_id}/delete")
        with app.app_context():
            assert db.session.get(User, editor_id) is None

    def test_delete_redirects_to_users_list(self, db, logged_in_admin):
        user = make_user(email="borrar-redir@mg.com", password="pass1234")
        db.session.add(user)
        db.session.commit()
        resp = logged_in_admin.post(
            f"/admin/users/{user.id}/delete", follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/admin/users" in resp.headers["Location"]

    def test_cannot_delete_self(self, db, logged_in_admin, admin_user):
        resp = logged_in_admin.post(
            f"/admin/users/{admin_user.id}/delete", follow_redirects=True,
        )
        assert resp.status_code == 200
        assert db.session.get(User, admin_user.id) is not None

    def test_cannot_delete_last_active_admin(self, db, logged_in_admin, admin_user):
        # admin_user is the only admin; must stay
        resp = logged_in_admin.post(
            f"/admin/users/{admin_user.id}/delete", follow_redirects=True,
        )
        assert resp.status_code == 200
        assert db.session.get(User, admin_user.id) is not None

    def test_can_delete_non_last_admin(self, db, app, logged_in_admin, admin_user):
        second_admin = make_user(
            email="second-admin@mg.com", password="pass1234", role=UserRole.ADMIN,
        )
        db.session.add(second_admin)
        db.session.commit()
        second_id = second_admin.id
        logged_in_admin.post(f"/admin/users/{second_id}/delete")
        with app.app_context():
            assert db.session.get(User, second_id) is None

    def test_delete_not_found_redirects(self, logged_in_admin):
        resp = logged_in_admin.post("/admin/users/99999/delete", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/users" in resp.headers["Location"]
