"""Unit tests for SQLAlchemy models."""
import pytest

from app.models import (
    Accessory,
    AccessoryCategory,
    Boat,
    BoatPhoto,
    BoatSpecs,
    BoatStatus,
    BoatType,
    Flag,
    Favorite,
    ListedObject,
    User,
    UserRole,
)
from tests.factories import make_accessory, make_boat, make_user


class TestListedObjectInheritance:
    def test_boat_has_correct_discriminator(self, db):
        b = make_boat()
        db.session.add(b)
        db.session.commit()
        assert b.object_type == "boat"

    def test_accessory_has_correct_discriminator(self, db):
        a = make_accessory()
        db.session.add(a)
        db.session.commit()
        assert a.object_type == "accessory"

    def test_boat_and_accessory_share_listed_objects_table(self, db):
        b = make_boat()
        a = make_accessory()
        db.session.add_all([b, a])
        db.session.commit()

        all_objects = db.session.query(ListedObject).all()
        types = {o.object_type for o in all_objects}
        assert types == {"boat", "accessory"}

    def test_query_boat_does_not_return_accessories(self, db):
        db.session.add(make_boat())
        db.session.add(make_accessory())
        db.session.commit()

        boats = db.session.query(Boat).all()
        assert all(isinstance(b, Boat) for b in boats)
        assert len(boats) == 1

    def test_slug_is_unique_across_types(self, db):
        from sqlalchemy.exc import IntegrityError
        db.session.add(make_boat(slug="duplicate-slug"))
        db.session.commit()
        db.session.add(make_accessory(slug="duplicate-slug"))
        with pytest.raises(IntegrityError):
            db.session.commit()


class TestBoatModel:
    def test_create_minimal_boat(self, db):
        b = make_boat()
        db.session.add(b)
        db.session.commit()
        assert b.id is not None
        assert b.slug == "velero-test"
        assert b.price_usd == 45000
        assert b.status == BoatStatus.AVAILABLE

    def test_primary_photo_url_none_when_no_photos(self, db):
        b = make_boat()
        db.session.add(b)
        db.session.commit()
        assert b.primary_photo_url is None

    def test_primary_photo_url_returns_primary(self, db):
        b = make_boat()
        db.session.add(b)
        db.session.flush()
        db.session.add(BoatPhoto(boat_id=b.id, url="https://example.com/a.jpg", position=1, is_primary=False))
        db.session.add(BoatPhoto(boat_id=b.id, url="https://example.com/b.jpg", position=0, is_primary=True))
        db.session.commit()
        assert b.primary_photo_url == "https://example.com/b.jpg"

    def test_primary_photo_url_fallback_to_first(self, db):
        b = make_boat()
        db.session.add(b)
        db.session.flush()
        db.session.add(BoatPhoto(boat_id=b.id, url="https://example.com/first.jpg", position=0, is_primary=False))
        db.session.commit()
        assert b.primary_photo_url == "https://example.com/first.jpg"

    def test_to_dict_contains_required_keys(self, db):
        b = make_boat()
        db.session.add(b)
        db.session.commit()
        d = b.to_dict()
        for key in ("id", "slug", "title", "price_usd", "status", "boat_type", "flag", "featured"):
            assert key in d

    def test_to_dict_status_is_string(self, db):
        b = make_boat()
        db.session.add(b)
        db.session.commit()
        assert b.to_dict()["status"] == "available"

    def test_on_sale_flag(self, db):
        b = make_boat(previous_price_usd=50000, on_sale=True)
        db.session.add(b)
        db.session.commit()
        d = b.to_dict()
        assert d["on_sale"] is True
        assert d["previous_price_usd"] == 50000

    def test_specs_relationship(self, db):
        b = make_boat()
        db.session.add(b)
        db.session.flush()
        specs = BoatSpecs(boat_id=b.id, engine_brand="Yanmar", engine_hp=40)
        db.session.add(specs)
        db.session.commit()
        assert b.specs is not None
        assert b.specs.engine_brand == "Yanmar"

    def test_cascade_delete_photos(self, db):
        b = make_boat()
        db.session.add(b)
        db.session.flush()
        db.session.add(BoatPhoto(boat_id=b.id, url="https://x.com/p.jpg", position=0, is_primary=True))
        db.session.commit()
        db.session.delete(b)
        db.session.commit()
        assert db.session.query(BoatPhoto).count() == 0


class TestAccessoryModel:
    def test_create_accessory(self, db):
        a = make_accessory()
        db.session.add(a)
        db.session.commit()
        assert a.id is not None
        assert a.active is True
        assert a.stock == 3

    def test_to_dict(self, db):
        a = make_accessory()
        db.session.add(a)
        db.session.commit()
        d = a.to_dict()
        assert d["slug"] == "chaleco-test"
        assert d["price_usd"] == 150
        assert d["category"] == "onboard"
        assert d["active"] is True

    def test_inherits_listed_object_fields(self, db):
        a = make_accessory(price_usd=99)
        db.session.add(a)
        db.session.commit()
        # price_usd lives on listed_objects table but is accessible on Accessory
        fetched = db.session.query(Accessory).filter_by(slug="chaleco-test").one()
        assert fetched.price_usd == 99
        assert fetched.title == "Chaleco Test"


class TestFavoriteModel:
    def test_favorite_references_listed_object(self, db, boat):
        fav = Favorite(listed_object_id=boat.id, session_id="sess-abc")
        db.session.add(fav)
        db.session.commit()
        assert fav.listed_object_id == boat.id
        assert fav.listed_object.slug == boat.slug

    def test_unique_constraint_per_session(self, db, boat):
        from sqlalchemy.exc import IntegrityError
        db.session.add(Favorite(listed_object_id=boat.id, session_id="sess-xyz"))
        db.session.commit()
        db.session.add(Favorite(listed_object_id=boat.id, session_id="sess-xyz"))
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_different_sessions_can_favorite_same_boat(self, db, boat):
        db.session.add(Favorite(listed_object_id=boat.id, session_id="sess-1"))
        db.session.add(Favorite(listed_object_id=boat.id, session_id="sess-2"))
        db.session.commit()
        assert db.session.query(Favorite).count() == 2


class TestUserModel:
    def test_password_hashing(self, db):
        u = make_user()
        db.session.add(u)
        db.session.commit()
        assert u.check_password("test-password") is True
        assert u.check_password("wrong") is False

    def test_is_admin_property(self, db):
        editor = make_user(role=UserRole.EDITOR)
        admin = make_user(email="admin@x.com", role=UserRole.ADMIN)
        db.session.add_all([editor, admin])
        db.session.commit()
        assert editor.is_admin is False
        assert admin.is_admin is True

    def test_is_active_property(self, db):
        active = make_user(active=True)
        inactive = make_user(email="inactive@x.com", active=False)
        db.session.add_all([active, inactive])
        db.session.commit()
        assert active.is_active is True
        assert inactive.is_active is False

    def test_email_is_unique(self, db):
        from sqlalchemy.exc import IntegrityError
        db.session.add(make_user(email="dup@x.com"))
        db.session.commit()
        db.session.add(make_user(email="dup@x.com"))
        with pytest.raises(IntegrityError):
            db.session.commit()
