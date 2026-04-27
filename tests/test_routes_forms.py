"""Integration tests for form-POST endpoints and remaining filter cases."""
import pytest

from app.models import (
    AccessoryCategory,
    BoatType,
    Flag,
    PendingListing,
    SaleInquiry,
)
from tests.factories import make_accessory, make_boat


class TestSellYourBoatPost:
    def test_success_redirects_with_submitted_flag(self, db, client):
        resp = client.post("/sell-your-boat", data={
            "first_name": "Juan",
            "last_name": "Pérez",
            "email": "juan@example.com",
            "phone": "+5491112345678",
            "boat_type": "sailboat",
            "message": "Me gustaría vender mi barco.",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "submitted=1" in resp.headers["Location"]

    def test_success_persists_sale_inquiry(self, db, client):
        client.post("/sell-your-boat", data={
            "first_name": "Juan",
            "last_name": "Pérez",
            "email": "juan@example.com",
            "boat_type": "sailboat",
        })
        inquiry = db.session.query(SaleInquiry).one_or_none()
        assert inquiry is not None
        assert inquiry.email == "juan@example.com"
        assert inquiry.boat_type == BoatType.SAILBOAT

    def test_missing_first_name_returns_400(self, db, client):
        resp = client.post("/sell-your-boat", data={
            "last_name": "Pérez",
            "email": "juan@example.com",
            "boat_type": "sailboat",
        })
        assert resp.status_code == 400

    def test_missing_email_returns_400(self, db, client):
        resp = client.post("/sell-your-boat", data={
            "first_name": "Juan",
            "last_name": "Pérez",
            "boat_type": "sailboat",
        })
        assert resp.status_code == 400

    def test_invalid_boat_type_returns_400(self, db, client):
        resp = client.post("/sell-your-boat", data={
            "first_name": "Juan",
            "last_name": "Pérez",
            "email": "juan@example.com",
            "boat_type": "submarine",
        })
        assert resp.status_code == 400

    def test_does_not_persist_on_validation_failure(self, db, client):
        client.post("/sell-your-boat", data={"first_name": "Solo nombre"})
        assert db.session.query(SaleInquiry).count() == 0


class TestPublishPost:
    def test_success_redirects_with_submitted_flag(self, db, client):
        resp = client.post("/publish", data={
            "first_name": "Ana",
            "last_name": "García",
            "email": "ana@example.com",
            "condition": "used",
            "description": "Accesorio náutico en perfecto estado.",
            "asked_price_usd": "800",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "submitted=1" in resp.headers["Location"]

    def test_success_persists_pending_listing(self, db, client):
        client.post("/publish", data={
            "first_name": "Ana",
            "last_name": "García",
            "email": "ana@example.com",
            "condition": "new",
            "description": "Producto nuevo en caja.",
        })
        listing = db.session.query(PendingListing).one_or_none()
        assert listing is not None
        assert listing.email == "ana@example.com"

    def test_missing_description_returns_400(self, db, client):
        resp = client.post("/publish", data={
            "first_name": "Ana",
            "last_name": "García",
            "email": "ana@example.com",
            "condition": "new",
        })
        assert resp.status_code == 400

    def test_missing_condition_returns_400(self, db, client):
        resp = client.post("/publish", data={
            "first_name": "Ana",
            "last_name": "García",
            "email": "ana@example.com",
            "description": "Accesorio en venta.",
        })
        assert resp.status_code == 400

    def test_missing_name_returns_400(self, db, client):
        resp = client.post("/publish", data={
            "email": "ana@example.com",
            "condition": "used",
            "description": "Algo para vender.",
        })
        assert resp.status_code == 400

    def test_does_not_persist_on_validation_failure(self, db, client):
        client.post("/publish", data={"first_name": "Solo"})
        assert db.session.query(PendingListing).count() == 0


class TestBoatsListFilters:
    def test_filter_by_flag_shows_matching(self, db, client):
        db.session.add(make_boat(slug="ar-boat", title="Barco Argentino", flag=Flag.AR))
        db.session.add(make_boat(slug="uy-boat", title="Barco Uruguayo", flag=Flag.UY))
        db.session.commit()
        resp = client.get("/boats?flag=AR")
        assert b"Barco Argentino" in resp.data
        assert b"Barco Uruguayo" not in resp.data

    def test_filter_by_min_price(self, db, client):
        db.session.add(make_boat(slug="barato", title="Barco Barato", price_usd=10000))
        db.session.add(make_boat(slug="caro", title="Barco Caro", price_usd=100000))
        db.session.commit()
        resp = client.get("/boats?min_price=50000")
        assert b"Barco Caro" in resp.data
        assert b"Barco Barato" not in resp.data

    def test_filter_by_max_price(self, db, client):
        db.session.add(make_boat(slug="barato2", title="Barco Barato2", price_usd=10000))
        db.session.add(make_boat(slug="caro2", title="Barco Caro2", price_usd=100000))
        db.session.commit()
        resp = client.get("/boats?max_price=20000")
        assert b"Barco Barato2" in resp.data
        assert b"Barco Caro2" not in resp.data

    def test_sort_price_asc(self, db, client):
        db.session.add(make_boat(slug="b1", title="Primero por precio", price_usd=5000))
        db.session.add(make_boat(slug="b2", title="Segundo por precio", price_usd=50000))
        db.session.commit()
        resp = client.get("/boats?sort=price_asc")
        assert resp.status_code == 200


class TestAccessoryCategoryFilter:
    def test_filter_shows_matching_category(self, db, client):
        db.session.add(make_accessory(slug="chaleco", title="Chaleco Marino", category=AccessoryCategory.ONBOARD))
        db.session.add(make_accessory(slug="bota", title="Botas de Goma", category=AccessoryCategory.BOOTS))
        db.session.commit()
        resp = client.get("/accessories?category=onboard")
        assert b"Chaleco Marino" in resp.data
        assert b"Botas de Goma" not in resp.data

    def test_filter_returns_200_with_no_results(self, client):
        resp = client.get("/accessories?category=clothing")
        assert resp.status_code == 200

    def test_filter_invalid_category_shows_all(self, db, client):
        db.session.add(make_accessory(slug="acc-visible", title="Accesorio Visible"))
        db.session.commit()
        resp = client.get("/accessories?category=invalid-cat")
        assert resp.status_code == 200
        assert b"Accesorio Visible" in resp.data


class TestFavoritesList:
    def test_shows_favorited_boat(self, db, client, boat):
        client.post(f"/favorites/{boat.slug}/toggle")
        resp = client.get("/favorites")
        assert resp.status_code == 200
        assert boat.title.encode() in resp.data

    def test_does_not_show_unfavorited_boat(self, db, client, boat):
        resp = client.get("/favorites")
        assert resp.status_code == 200
        assert boat.title.encode() not in resp.data

    def test_empty_page_renders(self, client):
        assert client.get("/favorites").status_code == 200
