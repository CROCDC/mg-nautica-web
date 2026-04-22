"""Unit tests for repository layer (runs against SQLite in-memory)."""
import pytest

from app.models import BoatStatus, BoatType, Flag
from app.repositories.accessory_repository import AccessoryRepository
from app.repositories.boat_repository import BoatRepository
from app.repositories.favorite_repository import FavoriteRepository
from tests.factories import make_accessory, make_boat


class TestBoatRepository:
    def test_get_by_slug_found(self, db, app, boat):
        with app.app_context():
            result = BoatRepository.get_by_slug(boat.slug)
        assert result is not None
        assert result.slug == boat.slug

    def test_get_by_slug_not_found(self, db, app):
        with app.app_context():
            assert BoatRepository.get_by_slug("no-existe") is None

    def test_list_available_returns_only_available(self, db, app):
        from app.models import Boat
        available = make_boat(slug="disponible")
        sold = make_boat(slug="vendido", status=BoatStatus.SOLD)
        reserved = make_boat(slug="reservado", status=BoatStatus.RESERVED)
        db.session.add_all([available, sold, reserved])
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available()
        assert len(results) == 1
        assert results[0].slug == "disponible"

    def test_list_available_filter_by_type(self, db, app):
        db.session.add(make_boat(slug="velero-1", boat_type=BoatType.SAILBOAT))
        db.session.add(make_boat(slug="lancha-1", boat_type=BoatType.MOTORBOAT))
        db.session.commit()
        with app.app_context():
            sailboats = BoatRepository.list_available(boat_type=BoatType.SAILBOAT)
        assert len(sailboats) == 1
        assert sailboats[0].boat_type == BoatType.SAILBOAT

    def test_list_available_filter_by_flag(self, db, app):
        db.session.add(make_boat(slug="ar-boat", flag=Flag.AR))
        db.session.add(make_boat(slug="uy-boat", flag=Flag.UY))
        db.session.commit()
        with app.app_context():
            uy_boats = BoatRepository.list_available(flag=Flag.UY)
        assert len(uy_boats) == 1
        assert uy_boats[0].flag == Flag.UY

    def test_list_available_filter_by_price(self, db, app):
        db.session.add(make_boat(slug="cheap", price_usd=10000))
        db.session.add(make_boat(slug="mid", price_usd=50000))
        db.session.add(make_boat(slug="expensive", price_usd=200000))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available(min_price_usd=20000, max_price_usd=100000)
        assert len(results) == 1
        assert results[0].slug == "mid"

    def test_list_available_search_by_title(self, db, app):
        db.session.add(make_boat(slug="jeanneau-39", title="Jeanneau Sun Odyssey 39"))
        db.session.add(make_boat(slug="beneteau-40", title="Beneteau Oceanis 40"))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available(search="jeanneau")
        assert len(results) == 1
        assert "Jeanneau" in results[0].title

    def test_list_available_sort_price_asc(self, db, app):
        db.session.add(make_boat(slug="b1", price_usd=30000))
        db.session.add(make_boat(slug="b2", price_usd=10000))
        db.session.add(make_boat(slug="b3", price_usd=20000))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available(sort="price_asc")
        prices = [r.price_usd for r in results]
        assert prices == sorted(prices)

    def test_list_available_sort_price_desc(self, db, app):
        db.session.add(make_boat(slug="b1", price_usd=30000))
        db.session.add(make_boat(slug="b2", price_usd=10000))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available(sort="price_desc")
        prices = [r.price_usd for r in results]
        assert prices == sorted(prices, reverse=True)

    def test_count_available(self, db, app):
        db.session.add(make_boat(slug="a1"))
        db.session.add(make_boat(slug="a2"))
        db.session.add(make_boat(slug="s1", status=BoatStatus.SOLD))
        db.session.commit()
        with app.app_context():
            assert BoatRepository.count_available() == 2

    def test_save_and_delete(self, db, app):
        b = make_boat(slug="to-delete")
        with app.app_context():
            BoatRepository.save(b)
            assert BoatRepository.get_by_slug("to-delete") is not None
            BoatRepository.delete(b)
            assert BoatRepository.get_by_slug("to-delete") is None

    def test_list_available_limit(self, db, app):
        for i in range(5):
            db.session.add(make_boat(slug=f"boat-{i}"))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available(limit=3)
        assert len(results) == 3


class TestAccessoryRepository:
    def test_list_active_returns_only_active(self, db, app):
        db.session.add(make_accessory(slug="active-acc", active=True))
        db.session.add(make_accessory(slug="inactive-acc", active=False))
        db.session.commit()
        with app.app_context():
            results = AccessoryRepository.list_active()
        assert len(results) == 1
        assert results[0].slug == "active-acc"

    def test_list_active_filter_by_category(self, db, app):
        from app.models import AccessoryCategory
        db.session.add(make_accessory(slug="onboard-acc", category=AccessoryCategory.ONBOARD))
        db.session.add(make_accessory(slug="boots-acc", category=AccessoryCategory.BOOTS))
        db.session.commit()
        with app.app_context():
            results = AccessoryRepository.list_active(category=AccessoryCategory.BOOTS)
        assert len(results) == 1
        assert results[0].slug == "boots-acc"

    def test_get_by_slug(self, db, app, accessory):
        with app.app_context():
            found = AccessoryRepository.get_by_slug(accessory.slug)
            assert found is not None
            assert found.title == accessory.title

    def test_get_by_slug_not_found(self, db, app):
        with app.app_context():
            assert AccessoryRepository.get_by_slug("no-existe") is None


class TestFavoriteRepository:
    def test_add_creates_favorite(self, db, app, boat):
        with app.app_context():
            fav = FavoriteRepository.add(boat.id, "session-1")
            assert fav.listed_object_id == boat.id
            assert fav.session_id == "session-1"

    def test_add_is_idempotent(self, db, app, boat):
        with app.app_context():
            fav1 = FavoriteRepository.add(boat.id, "session-1")
            fav2 = FavoriteRepository.add(boat.id, "session-1")
            assert fav1.id == fav2.id

    def test_get_returns_existing(self, db, app, boat):
        with app.app_context():
            FavoriteRepository.add(boat.id, "session-1")
            assert FavoriteRepository.get(boat.id, "session-1") is not None

    def test_get_returns_none_when_absent(self, db, app, boat):
        with app.app_context():
            assert FavoriteRepository.get(boat.id, "session-x") is None

    def test_remove_existing(self, db, app, boat):
        with app.app_context():
            FavoriteRepository.add(boat.id, "session-1")
            assert FavoriteRepository.remove(boat.id, "session-1") is True
            assert FavoriteRepository.get(boat.id, "session-1") is None

    def test_remove_nonexistent_returns_false(self, db, app, boat):
        with app.app_context():
            assert FavoriteRepository.remove(boat.id, "ghost-session") is False

    def test_list_for_session(self, db, app):
        b1 = make_boat(slug="boat-a")
        b2 = make_boat(slug="boat-b")
        b3 = make_boat(slug="boat-c")
        db.session.add_all([b1, b2, b3])
        db.session.commit()
        with app.app_context():
            FavoriteRepository.add(b1.id, "my-session")
            FavoriteRepository.add(b2.id, "my-session")
            FavoriteRepository.add(b3.id, "other-session")
            favs = FavoriteRepository.list_for_session("my-session")
            assert len(favs) == 2
            assert all(f.session_id == "my-session" for f in favs)
