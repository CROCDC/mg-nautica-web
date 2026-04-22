"""Shared fixtures for the MG Náutica test suite.

All tests run against an in-memory SQLite database — no Docker required.
Each test function gets a fresh, isolated database via function-scoped fixtures.
"""
import pytest

from app.factory import create_app, db as _db
from app.models import BoatPhoto
from tests.factories import make_accessory, make_admin, make_boat


TEST_CONFIG = {
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "SECRET_KEY": "test-secret",
    "WTF_CSRF_ENABLED": False,
    "SERVER_NAME": None,
}


# ── App & DB fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """Application using SQLite in-memory — configured before db.init_app()."""
    return create_app(test_config=TEST_CONFIG)


@pytest.fixture(scope="function")
def db(app):
    """Fresh schema for every test; tears down after the test completes."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app, db):
    """Test client bound to the current clean database."""
    with app.test_client() as c:
        yield c


# ── Convenience fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def boat(db):
    b = make_boat()
    db.session.add(b)
    db.session.commit()
    return b


@pytest.fixture
def boat_with_photo(db):
    b = make_boat(slug="velero-con-foto")
    db.session.add(b)
    db.session.flush()
    db.session.add(BoatPhoto(
        boat_id=b.id, url="https://example.com/photo.jpg",
        position=0, is_primary=True,
    ))
    db.session.commit()
    return b


@pytest.fixture
def accessory(db):
    a = make_accessory()
    db.session.add(a)
    db.session.commit()
    return a


@pytest.fixture
def admin_user(db):
    u = make_admin()
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def logged_in_admin(client, admin_user):
    """Test client already authenticated as admin."""
    client.post("/admin/login", data={
        "email": admin_user.email,
        "password": "admin-pass",
    })
    return client
