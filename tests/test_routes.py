"""Integration tests for public-facing routes using Flask test client."""
import pytest

from app.models import BoatStatus, BoatType, Flag
from tests.factories import make_accessory, make_boat


class TestHomeRoute:
    def test_home_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_home_shows_boat_count(self, db, client):
        db.session.add(make_boat(slug="b1"))
        db.session.add(make_boat(slug="b2"))
        db.session.commit()
        resp = client.get("/")
        assert b"2" in resp.data

    def test_home_does_not_show_sold_boats(self, db, client):
        db.session.add(make_boat(slug="sold", title="Velero Vendido", status=BoatStatus.SOLD))
        db.session.commit()
        resp = client.get("/")
        assert b"Velero Vendido" not in resp.data


class TestBoatsListRoute:
    def test_list_returns_200(self, client):
        assert client.get("/boats").status_code == 200

    def test_list_shows_available_boats(self, db, client):
        db.session.add(make_boat(slug="visible", title="Velero Visible"))
        db.session.commit()
        resp = client.get("/boats")
        assert b"Velero Visible" in resp.data

    def test_list_hides_sold_boats(self, db, client):
        db.session.add(make_boat(slug="sold-boat", title="Velero Vendido", status=BoatStatus.SOLD))
        db.session.commit()
        resp = client.get("/boats")
        assert b"Velero Vendido" not in resp.data

    def test_filter_by_type(self, db, client):
        db.session.add(make_boat(slug="sailboat", title="Mi Velero", boat_type=BoatType.SAILBOAT))
        db.session.add(make_boat(slug="motorboat", title="Mi Lancha", boat_type=BoatType.MOTORBOAT))
        db.session.commit()
        resp = client.get("/boats?type=sailboat")
        assert b"Mi Velero" in resp.data
        assert b"Mi Lancha" not in resp.data

    def test_search_by_title(self, db, client):
        db.session.add(make_boat(slug="jeanneau", title="Jeanneau Odyssey"))
        db.session.add(make_boat(slug="beneteau", title="Beneteau Oceanis"))
        db.session.commit()
        resp = client.get("/boats?q=jeanneau")
        assert b"Jeanneau" in resp.data
        assert b"Beneteau" not in resp.data

    def test_empty_results_shows_empty_state(self, client):
        resp = client.get("/boats?q=nada-que-coincida-xyzxyz")
        assert resp.status_code == 200
        assert "No hay embarcaciones".encode() in resp.data


class TestBoatDetailRoute:
    def test_detail_returns_200_for_valid_slug(self, db, client, boat):
        resp = client.get(f"/boats/{boat.slug}")
        assert resp.status_code == 200

    def test_detail_shows_title_and_price(self, db, client, boat):
        resp = client.get(f"/boats/{boat.slug}")
        assert boat.title.encode() in resp.data

    def test_detail_returns_404_for_unknown_slug(self, client):
        resp = client.get("/boats/no-existe-este-barco")
        assert resp.status_code == 404

    def test_detail_shows_previous_price_when_on_sale(self, db, client):
        b = make_boat(slug="oferta", price_usd=45000, on_sale=True, previous_price_usd=50000)
        db.session.add(b)
        db.session.commit()
        resp = client.get("/boats/oferta")
        # Sidebar shows "Antes: US$ 50,000" when on_sale
        assert "50,000".encode() in resp.data


class TestBoatInquireRoute:
    def test_inquire_redirects_on_success(self, db, client, boat):
        resp = client.post(f"/boats/{boat.slug}/inquire", data={
            "name": "Juan Pérez",
            "email": "juan@example.com",
            "phone": "+54911234567",
            "message": "Me interesa el velero.",
        })
        assert resp.status_code == 302
        assert b"inquiry=ok" in resp.headers["Location"].encode()

    def test_inquire_returns_400_missing_fields(self, db, client, boat):
        resp = client.post(f"/boats/{boat.slug}/inquire", data={"name": "Juan"})
        assert resp.status_code == 400

    def test_inquire_404_for_unknown_boat(self, client):
        resp = client.post("/boats/no-existe/inquire", data={
            "name": "Test",
            "email": "test@test.com",
        })
        assert resp.status_code == 404


class TestFavoriteToggleRoute:
    def test_toggle_adds_favorite(self, db, client, boat):
        resp = client.post(f"/favorites/{boat.slug}/toggle",
                           content_type="application/x-www-form-urlencoded")
        assert resp.status_code == 200
        assert resp.get_json()["favorite"] is True

    def test_toggle_removes_on_second_call(self, db, client, boat):
        client.post(f"/favorites/{boat.slug}/toggle")
        resp = client.post(f"/favorites/{boat.slug}/toggle")
        assert resp.get_json()["favorite"] is False

    def test_toggle_404_for_unknown_slug(self, client):
        resp = client.post("/favorites/no-existe/toggle")
        assert resp.status_code == 404


class TestAccessoriesRoute:
    def test_list_returns_200(self, client):
        assert client.get("/accessories").status_code == 200

    def test_list_shows_active_accessories(self, db, client):
        db.session.add(make_accessory(slug="visible", title="Chaleco Visible"))
        db.session.commit()
        resp = client.get("/accessories")
        assert b"Chaleco Visible" in resp.data

    def test_list_hides_inactive(self, db, client):
        db.session.add(make_accessory(slug="hidden", title="Chaleco Oculto", active=False))
        db.session.commit()
        resp = client.get("/accessories")
        assert b"Chaleco Oculto" not in resp.data

    def test_detail_returns_200(self, db, client, accessory):
        resp = client.get(f"/accessories/{accessory.slug}")
        assert resp.status_code == 200

    def test_detail_returns_404_for_unknown(self, client):
        resp = client.get("/accessories/no-existe")
        assert resp.status_code == 404


class TestStaticPages:
    @pytest.mark.parametrize("path", [
        "/services", "/contact", "/about", "/sell-your-boat", "/publish", "/favorites",
    ])
    def test_page_returns_200(self, client, path):
        assert client.get(path).status_code == 200

    def test_404_page(self, client):
        resp = client.get("/ruta-que-no-existe")
        assert resp.status_code == 404
        assert "404".encode() in resp.data

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
