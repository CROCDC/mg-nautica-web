"""Unit tests for repository layer (runs against SQLite in-memory)."""
import io
import tempfile

import pytest

from app.models import BoatStatus, BoatType, Flag, ModerationStatus, ProductCondition
from app.repositories.accessory_repository import AccessoryRepository
from app.repositories.boat_inquiry_repository import BoatInquiryRepository
from app.repositories.boat_repository import BoatRepository
from app.repositories.favorite_repository import FavoriteRepository
from app.repositories.pending_listing_repository import PendingListingRepository
from app.repositories.sale_inquiry_repository import SaleInquiryRepository
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

# ── BoatRepository ─────────────────────────────────────────────────────────────

class TestBoatRepositoryGetById:
    def test_found(self, db, app, boat):
        with app.app_context():
            result = BoatRepository.get_by_id(boat.id)
        assert result is not None
        assert result.id == boat.id

    def test_not_found(self, db, app):
        with app.app_context():
            assert BoatRepository.get_by_id(9999) is None


class TestBoatRepositoryLengthYearFilters:
    def test_filter_min_length(self, db, app):
        db.session.add(make_boat(slug="short", length_m=5.0))
        db.session.add(make_boat(slug="long", length_m=15.0))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available(min_length_m=10.0)
        assert len(results) == 1
        assert results[0].slug == "long"

    def test_filter_max_length(self, db, app):
        db.session.add(make_boat(slug="short", length_m=5.0))
        db.session.add(make_boat(slug="long", length_m=15.0))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available(max_length_m=10.0)
        assert len(results) == 1
        assert results[0].slug == "short"

    def test_filter_min_year(self, db, app):
        db.session.add(make_boat(slug="old", year=2000))
        db.session.add(make_boat(slug="new", year=2020))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available(min_year=2010)
        assert len(results) == 1
        assert results[0].slug == "new"

    def test_filter_max_year(self, db, app):
        db.session.add(make_boat(slug="old", year=2000))
        db.session.add(make_boat(slug="new", year=2020))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available(max_year=2010)
        assert len(results) == 1
        assert results[0].slug == "old"


class TestBoatRepositorySortAndOffset:
    def test_sort_oldest(self, db, app):
        db.session.add(make_boat(slug="first"))
        db.session.add(make_boat(slug="second"))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_available(sort="oldest")
        assert results[0].slug == "first"
        assert results[1].slug == "second"

    def test_offset(self, db, app):
        for i in range(5):
            db.session.add(make_boat(slug=f"b{i}"))
        db.session.commit()
        with app.app_context():
            all_results = BoatRepository.list_available(sort="oldest")
            offset_results = BoatRepository.list_available(sort="oldest", offset=2)
        assert len(offset_results) == len(all_results) - 2


class TestBoatRepositoryFeatured:
    def test_returns_featured_available_only(self, db, app):
        db.session.add(make_boat(slug="feat", featured=True))
        db.session.add(make_boat(slug="unfeat", featured=False))
        db.session.add(make_boat(slug="feat-sold", featured=True, status=BoatStatus.SOLD))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_featured()
        slugs = [r.slug for r in results]
        assert "feat" in slugs
        assert "unfeat" not in slugs
        assert "feat-sold" not in slugs

    def test_respects_limit(self, db, app):
        for i in range(10):
            db.session.add(make_boat(slug=f"f{i}", featured=True))
        db.session.commit()
        with app.app_context():
            results = BoatRepository.list_featured(limit=3)
        assert len(results) == 3


# ── AccessoryRepository ────────────────────────────────────────────────────────

class TestAccessoryRepositoryExtended:
    def test_get_by_id_found(self, db, app, accessory):
        with app.app_context():
            result = AccessoryRepository.get_by_id(accessory.id)
        assert result is not None
        assert result.id == accessory.id

    def test_get_by_id_not_found(self, db, app):
        with app.app_context():
            assert AccessoryRepository.get_by_id(9999) is None

    def test_save_persists_new(self, db, app):
        acc = make_accessory(slug="acc-to-save")
        with app.app_context():
            saved = AccessoryRepository.save(acc)
            assert saved.id is not None
            assert AccessoryRepository.get_by_id(saved.id) is not None


# ── BoatInquiryRepository ──────────────────────────────────────────────────────

class TestBoatInquiryRepository:
    def test_create_persists(self, db, app, boat):
        with app.app_context():
            inq = BoatInquiryRepository.create(
                boat_id=boat.id,
                name="Juan",
                email="juan@test.com",
                phone="11-1234",
                message="Me interesa",
            )
            assert inq.id is not None
            assert inq.boat_id == boat.id
            assert inq.email == "juan@test.com"

    def test_list_for_boat(self, db, app, boat):
        with app.app_context():
            BoatInquiryRepository.create(boat_id=boat.id, name="A", email="a@t.com", phone=None, message=None)
            BoatInquiryRepository.create(boat_id=boat.id, name="B", email="b@t.com", phone=None, message=None)
            results = BoatInquiryRepository.list_for_boat(boat.id)
        assert len(results) == 2

    def test_list_for_boat_empty(self, db, app, boat):
        with app.app_context():
            assert BoatInquiryRepository.list_for_boat(boat.id) == []


# ── SaleInquiryRepository ──────────────────────────────────────────────────────

class TestSaleInquiryRepository:
    def test_create_persists(self, db, app):
        with app.app_context():
            inq = SaleInquiryRepository.create(
                first_name="Ana",
                last_name="García",
                email="ana@test.com",
                phone=None,
                boat_type=BoatType.SAILBOAT,
                message="Quiero vender",
            )
            assert inq.id is not None
            assert inq.email == "ana@test.com"

    def test_list_recent(self, db, app):
        with app.app_context():
            SaleInquiryRepository.create("A", "B", "a@t.com", None, BoatType.SAILBOAT, None)
            SaleInquiryRepository.create("C", "D", "c@t.com", None, BoatType.MOTORBOAT, None)
            results = SaleInquiryRepository.list_recent()
        assert len(results) == 2

    def test_list_recent_limit(self, db, app):
        with app.app_context():
            for i in range(5):
                SaleInquiryRepository.create(f"U{i}", "L", f"u{i}@t.com", None, BoatType.SAILBOAT, None)
            results = SaleInquiryRepository.list_recent(limit=3)
        assert len(results) == 3


# ── PendingListingRepository ───────────────────────────────────────────────────

class TestPendingListingRepositoryIsAllowed:
    def test_valid_extensions(self, db, app):
        with app.app_context():
            for fname in ("foto.png", "doc.pdf", "img.jpg", "img.jpeg", "img.webp", "img.heic"):
                assert PendingListingRepository._is_allowed(fname) is True

    def test_no_dot_returns_false(self, db, app):
        with app.app_context():
            assert PendingListingRepository._is_allowed("nodot") is False

    def test_invalid_extension_returns_false(self, db, app):
        with app.app_context():
            assert PendingListingRepository._is_allowed("script.exe") is False
            assert PendingListingRepository._is_allowed("archive.zip") is False


class TestPendingListingRepositorySaveFiles:
    def test_skips_empty_filename(self, db, app):
        from werkzeug.datastructures import FileStorage
        with app.app_context():
            with tempfile.TemporaryDirectory() as tmpdir:
                app.config["UPLOAD_FOLDER"] = tmpdir
                result = PendingListingRepository._save_files(
                    [FileStorage(stream=io.BytesIO(b""), filename="")]
                )
        assert result == []

    def test_skips_invalid_extension(self, db, app):
        from werkzeug.datastructures import FileStorage
        with app.app_context():
            with tempfile.TemporaryDirectory() as tmpdir:
                app.config["UPLOAD_FOLDER"] = tmpdir
                result = PendingListingRepository._save_files(
                    [FileStorage(stream=io.BytesIO(b"data"), filename="virus.exe")]
                )
        assert result == []

    def test_saves_valid_file(self, db, app):
        from werkzeug.datastructures import FileStorage
        with app.app_context():
            with tempfile.TemporaryDirectory() as tmpdir:
                app.config["UPLOAD_FOLDER"] = tmpdir
                result = PendingListingRepository._save_files(
                    [FileStorage(stream=io.BytesIO(b"\x89PNG"), filename="foto.png")]
                )
        assert len(result) == 1
        assert result[0].startswith("/uploads/")
        assert result[0].endswith(".png")


class TestPendingListingRepositoryListPending:
    def test_returns_only_pending(self, db, app):
        from app.models import PendingListing
        db.session.add(PendingListing(
            first_name="P", last_name="B", email="p@b.com",
            condition=ProductCondition.USED, description="Algo",
            file_urls=[], moderation_status=ModerationStatus.PENDING,
        ))
        db.session.add(PendingListing(
            first_name="A", last_name="C", email="a@c.com",
            condition=ProductCondition.NEW, description="Otro",
            file_urls=[], moderation_status=ModerationStatus.APPROVED,
        ))
        db.session.commit()
        with app.app_context():
            results = PendingListingRepository.list_pending()
        assert len(results) == 1
        assert results[0].email == "p@b.com"

    def test_empty_when_none_pending(self, db, app):
        with app.app_context():
            assert PendingListingRepository.list_pending() == []
