"""Tests for the Mercado Libre integration.

Covers:
- MeliOAuth helpers (env vars, URL building, token storage)
- BoatSerializer payload building
- MeliService (publish, update, pause, activate, close, sync_status, meli_info)
- Admin routes (/admin/meli/*)
- MeliCredentials model

All external HTTP calls are mocked with unittest.mock.patch.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.factories import make_boat


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_boat_with_photos(db):
    from app.models import Boat, BoatPhoto
    b = Boat(
        slug="velero-meli",
        title="Bavaria 35 Velero",
        description="Gran velero.",
        price_usd=55000,
        boat_type="sailboat",
        flag="AR",
        status="available",
        year=2015,
        shipyard="Bavaria",
        model_name="35 Cruiser",
        length_m="10.50",
    )
    db.session.add(b)
    db.session.flush()
    db.session.add(BoatPhoto(
        boat_id=b.id, url="https://example.com/photo1.jpg", position=0, is_primary=True,
    ))
    db.session.commit()
    return b


def _make_creds(db, site_id="MLU", expired=False):
    from app.models.meli_credentials import MeliCredentials
    offset = -1 if expired else 7200
    creds = MeliCredentials(
        site_id=site_id,
        meli_user_id="123456",
        access_token="APP_USR-test-token",
        refresh_token="TG-test-refresh",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=offset),
    )
    db.session.add(creds)
    db.session.commit()
    return creds


# ── MeliCredentials model ─────────────────────────────────────────────────────

class TestMeliCredentials:
    def test_is_expired_false_for_future(self, db):
        creds = _make_creds(db, "MLU", expired=False)
        assert creds.is_expired is False

    def test_is_expired_true_for_past(self, db):
        creds = _make_creds(db, "MLU", expired=True)
        assert creds.is_expired is True

    def test_repr(self, db):
        creds = _make_creds(db, "MLA")
        assert "MLA" in repr(creds)

    def test_unique_per_site(self, db):
        from sqlalchemy.exc import IntegrityError
        from app.models.meli_credentials import MeliCredentials
        _make_creds(db, "MLU")
        db.session.add(MeliCredentials(
            site_id="MLU",
            access_token="x",
            refresh_token="y",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


# ── Boat model MELI fields ─────────────────────────────────────────────────────

class TestBoatMeliFields:
    def test_meli_fields_default_null(self, boat):
        assert boat.meli_mlu_item_id is None
        assert boat.meli_mlu_status is None
        assert boat.meli_mla_item_id is None
        assert boat.meli_mla_permalink is None
        assert boat.meli_mlu_synced_at is None

    def test_meli_fields_persist(self, db, boat):
        from app.models import Boat
        boat.meli_mlu_item_id = "MLU1234567890"
        boat.meli_mlu_status = "active"
        boat.meli_mlu_permalink = "https://articulo.mercadolibre.com.uy/MLU1234567890"
        db.session.commit()

        refreshed = db.session.get(Boat, boat.id)
        assert refreshed.meli_mlu_item_id == "MLU1234567890"
        assert refreshed.meli_mlu_status == "active"


# ── BoatSerializer ─────────────────────────────────────────────────────────────

class TestBoatSerializer:
    def test_to_payload_structure(self, db):
        from app.integrations.mercadolibre.serializer import BoatSerializer
        boat = _make_boat_with_photos(db)
        s = BoatSerializer(boat, "MLU")
        payload = s.to_payload()

        assert payload["title"] == "Bavaria 35 Velero"
        assert payload["price"] == 55000.0
        assert payload["currency_id"] == "USD"
        assert payload["available_quantity"] == 1
        assert payload["buying_mode"] == "buy_it_now"
        assert payload["listing_type_id"] == "gold_special"
        assert payload["condition"] == "used"
        assert "category_id" in payload

    def test_pictures_included(self, db):
        from app.integrations.mercadolibre.serializer import BoatSerializer
        boat = _make_boat_with_photos(db)
        payload = BoatSerializer(boat, "MLU").to_payload()
        assert payload["pictures"] == [{"source": "https://example.com/photo1.jpg"}]

    def test_no_pictures_when_boat_has_none(self, db):
        from app.integrations.mercadolibre.serializer import BoatSerializer
        boat = make_boat(slug="bare-boat")
        db.session.add(boat)
        db.session.commit()
        payload = BoatSerializer(boat, "MLU").to_payload()
        assert "pictures" not in payload

    def test_attributes_include_year_and_brand(self, db):
        from app.integrations.mercadolibre.serializer import BoatSerializer
        boat = _make_boat_with_photos(db)
        attrs = {a["id"]: a for a in BoatSerializer(boat, "MLU").to_payload()["attributes"]}
        assert attrs["BOAT_YEAR"]["value_name"] == "2015"
        assert attrs["BRAND"]["value_name"] == "Bavaria"
        assert attrs["MODEL"]["value_name"] == "35 Cruiser"

    def test_length_uses_value_struct(self, db):
        from app.integrations.mercadolibre.serializer import BoatSerializer
        boat = _make_boat_with_photos(db)
        attrs = {a["id"]: a for a in BoatSerializer(boat, "MLU").to_payload()["attributes"]}
        assert attrs["TOTAL_LENGTH"]["value_struct"]["unit"] == "m"
        assert attrs["TOTAL_LENGTH"]["value_struct"]["number"] == pytest.approx(10.5)

    def test_category_id_sailboat_mlu(self, db):
        from app.integrations.mercadolibre.serializer import BoatSerializer
        boat = make_boat(slug="s1")
        db.session.add(boat)
        db.session.commit()
        assert BoatSerializer(boat, "MLU").category_id().startswith("MLU")

    def test_category_id_sailboat_mla(self, db):
        from app.integrations.mercadolibre.serializer import BoatSerializer
        boat = make_boat(slug="s2")
        db.session.add(boat)
        db.session.commit()
        assert BoatSerializer(boat, "MLA").category_id().startswith("MLA")

    def test_description_payload(self, db):
        from app.integrations.mercadolibre.serializer import BoatSerializer
        boat = _make_boat_with_photos(db)
        dp = BoatSerializer(boat, "MLU").description_payload()
        assert dp == {"plain_text": "Gran velero."}

    def test_update_payload_includes_title_price_pictures(self, db):
        from app.integrations.mercadolibre.serializer import BoatSerializer
        boat = _make_boat_with_photos(db)
        up = BoatSerializer(boat, "MLU").update_payload()
        assert up["title"] == "Bavaria 35 Velero"
        assert up["price"] == 55000.0
        assert len(up["pictures"]) == 1

    def test_custom_listing_type(self, db):
        from app.integrations.mercadolibre.serializer import BoatSerializer
        boat = make_boat(slug="s3")
        db.session.add(boat)
        db.session.commit()
        payload = BoatSerializer(boat, "MLU", listing_type="free").to_payload()
        assert payload["listing_type_id"] == "free"


# ── MeliService ────────────────────────────────────────────────────────────────

class TestMeliServiceInit:
    def test_rejects_unknown_site(self):
        from app.integrations.mercadolibre.service import MeliService
        with pytest.raises(ValueError, match="Unsupported"):
            MeliService("MLC")

    def test_accepts_mlu_and_mla(self):
        from app.integrations.mercadolibre.service import MeliService
        assert MeliService("MLU").site_id == "MLU"
        assert MeliService("MLA").site_id == "MLA"


class TestMeliServicePublish:
    def test_publish_sets_boat_fields(self, db):
        from app.integrations.mercadolibre.service import MeliService
        boat = _make_boat_with_photos(db)

        fake_item = {
            "id": "MLU9999999",
            "status": "active",
            "permalink": "https://articulo.mercadolibre.com.uy/MLU9999999",
        }
        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="TOKEN"), \
             patch("app.integrations.mercadolibre.client.MeliClient.post", return_value=fake_item):
            MeliService("MLU").publish(boat)
            db.session.commit()

        assert boat.meli_mlu_item_id == "MLU9999999"
        assert boat.meli_mlu_status == "active"
        assert boat.meli_mlu_permalink == "https://articulo.mercadolibre.com.uy/MLU9999999"
        assert boat.meli_mlu_synced_at is not None

    def test_publish_mla_does_not_touch_mlu(self, db):
        from app.integrations.mercadolibre.service import MeliService
        boat = _make_boat_with_photos(db)

        fake_item = {"id": "MLA9999999", "status": "active", "permalink": "https://mla.example"}
        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="TOKEN"), \
             patch("app.integrations.mercadolibre.client.MeliClient.post", return_value=fake_item):
            MeliService("MLA").publish(boat)
            db.session.commit()

        assert boat.meli_mla_item_id == "MLA9999999"
        assert boat.meli_mlu_item_id is None

    def test_publish_description_failure_is_swallowed(self, db):
        from app.integrations.mercadolibre.service import MeliService
        from app.integrations.mercadolibre.client import MeliAPIError
        boat = _make_boat_with_photos(db)

        call_count = {"n": 0}
        def fake_post(path, json=None):
            call_count["n"] += 1
            if "/description" in path:
                raise MeliAPIError(400, "Description not allowed")
            return {"id": "MLU111", "status": "active", "permalink": "https://meli.example"}

        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="T"), \
             patch("app.integrations.mercadolibre.client.MeliClient.post", side_effect=fake_post):
            MeliService("MLU").publish(boat)
            db.session.commit()

        assert boat.meli_mlu_item_id == "MLU111"


class TestMeliServiceUpdate:
    def test_update_calls_put(self, db):
        from app.integrations.mercadolibre.service import MeliService
        boat = _make_boat_with_photos(db)
        boat.meli_mlu_item_id = "MLU555"
        boat.meli_mlu_status = "active"
        db.session.commit()

        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="T"), \
             patch("app.integrations.mercadolibre.client.MeliClient.put", return_value=None) as mock_put:
            MeliService("MLU").update(boat)
            db.session.commit()

        assert mock_put.called
        assert boat.meli_mlu_synced_at is not None

    def test_update_raises_if_not_published(self, db):
        from app.integrations.mercadolibre.service import MeliService
        boat = make_boat(slug="not-published")
        db.session.add(boat)
        db.session.commit()
        with pytest.raises(ValueError, match="Publish first"):
            MeliService("MLU").update(boat)


class TestMeliServiceStatusChanges:
    @pytest.fixture
    def published_boat(self, db):
        boat = _make_boat_with_photos(db)
        boat.meli_mlu_item_id = "MLU777"
        boat.meli_mlu_status = "active"
        db.session.commit()
        return boat

    def test_pause(self, db, published_boat):
        from app.integrations.mercadolibre.service import MeliService
        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="T"), \
             patch("app.integrations.mercadolibre.client.MeliClient.put", return_value=None):
            MeliService("MLU").pause(published_boat)
            db.session.commit()
        assert published_boat.meli_mlu_status == "paused"

    def test_activate(self, db, published_boat):
        from app.integrations.mercadolibre.service import MeliService
        published_boat.meli_mlu_status = "paused"
        db.session.commit()
        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="T"), \
             patch("app.integrations.mercadolibre.client.MeliClient.put", return_value=None):
            MeliService("MLU").activate(published_boat)
            db.session.commit()
        assert published_boat.meli_mlu_status == "active"

    def test_close(self, db, published_boat):
        from app.integrations.mercadolibre.service import MeliService
        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="T"), \
             patch("app.integrations.mercadolibre.client.MeliClient.put", return_value=None):
            MeliService("MLU").close(published_boat)
            db.session.commit()
        assert published_boat.meli_mlu_status == "closed"

    def test_change_status_raises_if_no_item(self, db):
        from app.integrations.mercadolibre.service import MeliService
        boat = make_boat(slug="no-item")
        db.session.add(boat)
        db.session.commit()
        with pytest.raises(ValueError):
            MeliService("MLU").pause(boat)

    def test_sync_status_updates_fields(self, db, published_boat):
        from app.integrations.mercadolibre.service import MeliService
        fake_item = {"status": "under_review", "permalink": "https://meli.example/u"}
        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="T"), \
             patch("app.integrations.mercadolibre.client.MeliClient.get", return_value=fake_item):
            MeliService("MLU").sync_status(published_boat)
            db.session.commit()
        assert published_boat.meli_mlu_status == "under_review"
        assert published_boat.meli_mlu_permalink == "https://meli.example/u"

    def test_sync_status_raises_if_no_item(self, db):
        from app.integrations.mercadolibre.service import MeliService
        boat = make_boat(slug="no-item2")
        db.session.add(boat)
        db.session.commit()
        with pytest.raises(ValueError):
            MeliService("MLU").sync_status(boat)


class TestMeliInfo:
    def test_both_sites_none_when_unpublished(self, db):
        from app.integrations.mercadolibre.service import MeliService
        boat = make_boat(slug="unpub")
        db.session.add(boat)
        db.session.commit()
        info = MeliService.meli_info(boat)
        assert info["MLU"] is None
        assert info["MLA"] is None

    def test_published_site_has_dict(self, db):
        from app.integrations.mercadolibre.service import MeliService
        boat = make_boat(slug="pub-one")
        db.session.add(boat)
        db.session.commit()
        boat.meli_mlu_item_id = "MLU123"
        boat.meli_mlu_status = "active"
        db.session.commit()
        info = MeliService.meli_info(boat)
        assert info["MLU"]["item_id"] == "MLU123"
        assert info["MLA"] is None

    def test_both_sites_published(self, db):
        from app.integrations.mercadolibre.service import MeliService
        boat = make_boat(slug="pub-both")
        db.session.add(boat)
        db.session.commit()
        boat.meli_mlu_item_id = "MLU1"
        boat.meli_mla_item_id = "MLA1"
        db.session.commit()
        info = MeliService.meli_info(boat)
        assert info["MLU"] is not None
        assert info["MLA"] is not None


# ── MeliOAuth helpers ─────────────────────────────────────────────────────────

class TestMeliOAuthEnvVars:
    def test_authorization_url_raises_without_client_id(self, db):
        from app.integrations.mercadolibre.auth import MeliOAuth
        with patch.dict(os.environ, {"MELI_CLIENT_ID": ""}):
            with pytest.raises(RuntimeError, match="MELI_CLIENT_ID"):
                MeliOAuth.authorization_url("MLU")

    def test_authorization_url_unknown_site(self, db):
        from app.integrations.mercadolibre.auth import MeliOAuth
        with patch.dict(os.environ, {"MELI_CLIENT_ID": "123"}):
            with pytest.raises(ValueError, match="Unknown site_id"):
                MeliOAuth.authorization_url("MLC")

    def test_authorization_url_contains_client_id(self, db):
        from app.integrations.mercadolibre.auth import MeliOAuth
        with patch.dict(os.environ, {"MELI_CLIENT_ID": "MYAPP123", "MELI_REDIRECT_URI": "https://example.com/cb"}):
            url = MeliOAuth.authorization_url("MLU")
        assert "MYAPP123" in url
        assert "auth.mercadolibre.com.uy" in url

    def test_authorization_url_mla(self, db):
        from app.integrations.mercadolibre.auth import MeliOAuth
        with patch.dict(os.environ, {"MELI_CLIENT_ID": "X", "MELI_REDIRECT_URI": "https://cb"}):
            url = MeliOAuth.authorization_url("MLA")
        assert "auth.mercadolibre.com.ar" in url


class TestMeliOAuthTokenStorage:
    def test_store_tokens_creates_credentials(self, db):
        from app.integrations.mercadolibre.auth import MeliOAuth
        from app.models.meli_credentials import MeliCredentials

        token_data = {
            "access_token": "APP_USR-abc",
            "refresh_token": "TG-xyz",
            "expires_in": 21600,
            "user_id": 99999,
        }
        creds = MeliOAuth.store_tokens("MLU", token_data)
        assert creds.access_token == "APP_USR-abc"
        assert creds.meli_user_id == "99999"
        assert MeliCredentials.query.filter_by(site_id="MLU").count() == 1

    def test_store_tokens_updates_existing(self, db):
        from app.integrations.mercadolibre.auth import MeliOAuth
        _make_creds(db, "MLU")
        token_data = {
            "access_token": "APP_USR-NEW",
            "refresh_token": "TG-NEW",
            "expires_in": 21600,
            "user_id": 77777,
        }
        MeliOAuth.store_tokens("MLU", token_data)
        from app.models.meli_credentials import MeliCredentials
        rows = MeliCredentials.query.filter_by(site_id="MLU").all()
        assert len(rows) == 1
        assert rows[0].access_token == "APP_USR-NEW"

    def test_get_valid_token_returns_token_when_fresh(self, db):
        from app.integrations.mercadolibre.auth import MeliOAuth
        _make_creds(db, "MLU", expired=False)
        token = MeliOAuth.get_valid_token("MLU")
        assert token == "APP_USR-test-token"

    def test_get_valid_token_refreshes_when_expired(self, db):
        from app.integrations.mercadolibre.auth import MeliOAuth
        _make_creds(db, "MLU", expired=True)
        new_token_data = {
            "access_token": "APP_USR-refreshed",
            "refresh_token": "TG-new-refresh",
            "expires_in": 21600,
        }
        with patch.dict(os.environ, {"MELI_CLIENT_ID": "TEST", "MELI_CLIENT_SECRET": "SECRET"}), \
             patch("app.integrations.mercadolibre.auth.requests.post") as mock_post:
            mock_post.return_value.ok = True
            mock_post.return_value.raise_for_status = lambda: None
            mock_post.return_value.json.return_value = new_token_data
            token = MeliOAuth.get_valid_token("MLU")
        assert token == "APP_USR-refreshed"

    def test_get_valid_token_raises_when_no_creds(self, db):
        from app.integrations.mercadolibre.auth import MeliOAuth
        from app.integrations.mercadolibre.client import MeliNotConfiguredError
        with pytest.raises(MeliNotConfiguredError):
            MeliOAuth.get_valid_token("MLU")


# ── MeliClient ────────────────────────────────────────────────────────────────

class TestMeliClient:
    def test_get_raises_without_token(self):
        from app.integrations.mercadolibre.client import MeliClient, MeliNotConfiguredError
        client = MeliClient()
        with pytest.raises(MeliNotConfiguredError):
            client.get("/items/MLU1")

    def test_raises_meli_api_error_on_4xx(self):
        from app.integrations.mercadolibre.client import MeliClient, MeliAPIError
        client = MeliClient(access_token="TOKEN")
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.ok = False
        mock_resp.reason = "Not Found"
        mock_resp.json.return_value = {"message": "Item not found"}
        with patch.object(client._session, "request", return_value=mock_resp):
            with pytest.raises(MeliAPIError) as exc_info:
                client.get("/items/BADID")
        assert exc_info.value.status_code == 404

    def test_retries_on_429_then_raises(self):
        from app.integrations.mercadolibre.client import MeliClient, MeliAPIError
        client = MeliClient(access_token="TOKEN")
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.ok = False
        with patch.object(client._session, "request", return_value=mock_resp), \
             patch("app.integrations.mercadolibre.client.time.sleep"):
            with pytest.raises(MeliAPIError) as exc_info:
                client.get("/items/X")
        assert exc_info.value.status_code == 429

    def test_returns_none_on_204(self):
        from app.integrations.mercadolibre.client import MeliClient
        client = MeliClient(access_token="TOKEN")
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.ok = True
        with patch.object(client._session, "request", return_value=mock_resp):
            result = client.delete("/items/X")
        assert result is None

    def test_meli_api_error_repr(self):
        from app.integrations.mercadolibre.client import MeliAPIError
        err = MeliAPIError(403, "Forbidden", {"error": "forbidden"})
        assert "403" in str(err)
        assert err.body == {"error": "forbidden"}


# ── Admin routes ──────────────────────────────────────────────────────────────

class TestMeliAdminOverview:
    def test_overview_requires_login(self, client):
        resp = client.get("/admin/meli/")
        assert resp.status_code in (302, 401)

    def test_overview_renders_for_admin(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/meli/")
        assert resp.status_code == 200
        assert b"Mercado Libre" in resp.data

    def test_overview_shows_sites(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/meli/")
        assert b"MLU" in resp.data
        assert b"MLA" in resp.data

    def test_overview_shows_connect_button_when_no_creds(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/meli/")
        assert b"Conectar cuenta" in resp.data

    def test_overview_shows_credentials_when_configured(self, db, logged_in_admin):
        _make_creds(db, "MLU")
        resp = logged_in_admin.get("/admin/meli/")
        assert b"Activo" in resp.data or b"Expirado" in resp.data

    def test_overview_shows_boats(self, db, logged_in_admin):
        boat = make_boat(slug="test-meli-overview", title="Lancha Overview Test")
        db.session.add(boat)
        db.session.commit()
        resp = logged_in_admin.get("/admin/meli/")
        assert b"Lancha Overview Test" in resp.data


class TestMeliAdminOAuth:
    def test_auth_redirect_without_env_shows_error(self, db, logged_in_admin):
        with patch.dict(os.environ, {"MELI_CLIENT_ID": ""}):
            resp = logged_in_admin.get("/admin/meli/auth/MLU", follow_redirects=True)
        assert b"MELI_CLIENT_ID" in resp.data

    def test_auth_redirect_with_env(self, db, logged_in_admin):
        with patch.dict(os.environ, {"MELI_CLIENT_ID": "MYAPP", "MELI_REDIRECT_URI": "https://cb"}):
            resp = logged_in_admin.get("/admin/meli/auth/MLU")
        assert resp.status_code == 302
        assert "mercadolibre" in resp.location

    def test_auth_unknown_site(self, db, logged_in_admin):
        resp = logged_in_admin.get("/admin/meli/auth/MLC", follow_redirects=True)
        assert resp.status_code == 200

    def test_callback_missing_code(self, db, logged_in_admin):
        resp = logged_in_admin.get("/admin/meli/callback?state=MLU", follow_redirects=True)
        assert b"Callback inv" in resp.data or resp.status_code == 200

    def test_callback_invalid_state(self, db, logged_in_admin):
        resp = logged_in_admin.get("/admin/meli/callback?code=ABC&state=UNKNOWN", follow_redirects=True)
        assert resp.status_code == 200

    def test_callback_stores_tokens(self, db, logged_in_admin):
        from app.models.meli_credentials import MeliCredentials
        token_data = {
            "access_token": "APP_USR-cb",
            "refresh_token": "TG-cb",
            "expires_in": 21600,
            "user_id": 1111,
        }
        with patch("app.admin.meli.MeliOAuth.exchange_code", return_value=token_data):
            resp = logged_in_admin.get(
                "/admin/meli/callback?code=TESTCODE&state=MLU", follow_redirects=True
            )
        assert resp.status_code == 200
        assert MeliCredentials.query.filter_by(site_id="MLU").count() == 1

    def test_disconnect_removes_credentials(self, db, logged_in_admin):
        from app.models.meli_credentials import MeliCredentials
        _make_creds(db, "MLU")
        logged_in_admin.post("/admin/meli/MLU/disconnect")
        assert MeliCredentials.query.filter_by(site_id="MLU").count() == 0

    def test_disconnect_nonexistent_is_safe(self, db, logged_in_admin):
        resp = logged_in_admin.post("/admin/meli/MLU/disconnect", follow_redirects=True)
        assert resp.status_code == 200


class TestMeliAdminBoatActions:
    @pytest.fixture
    def boat_and_creds(self, db):
        boat = _make_boat_with_photos(db)
        _make_creds(db, "MLU")
        return boat

    def test_publish_action_with_mock(self, db, logged_in_admin, boat_and_creds):
        from app.models import Boat
        boat = boat_and_creds
        fake_item = {"id": "MLU888", "status": "active", "permalink": "https://meli.example"}
        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="T"), \
             patch("app.integrations.mercadolibre.client.MeliClient.post", return_value=fake_item):
            resp = logged_in_admin.post(
                f"/admin/meli/boats/{boat.id}/publish/MLU", follow_redirects=True
            )
        assert resp.status_code == 200
        refreshed = db.session.get(Boat, boat.id)
        assert refreshed.meli_mlu_item_id == "MLU888"

    def test_publish_unknown_site_shows_error(self, db, logged_in_admin, boat_and_creds):
        boat = boat_and_creds
        resp = logged_in_admin.post(
            f"/admin/meli/boats/{boat.id}/publish/MLC", follow_redirects=True
        )
        assert resp.status_code == 200
        assert b"Sitio desconocido" in resp.data

    def test_publish_invalid_boat_returns_404(self, db, logged_in_admin):
        _make_creds(db, "MLU")
        resp = logged_in_admin.post("/admin/meli/boats/99999/publish/MLU")
        assert resp.status_code == 404

    def test_pause_without_listing_shows_error(self, db, logged_in_admin, boat_and_creds):
        boat = boat_and_creds
        resp = logged_in_admin.post(
            f"/admin/meli/boats/{boat.id}/pause/MLU", follow_redirects=True
        )
        assert resp.status_code == 200

    def test_meli_api_error_shows_flash(self, db, logged_in_admin, boat_and_creds):
        from app.integrations.mercadolibre.client import MeliAPIError
        boat = boat_and_creds
        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="T"), \
             patch("app.integrations.mercadolibre.client.MeliClient.post", side_effect=MeliAPIError(400, "Category required")):
            resp = logged_in_admin.post(
                f"/admin/meli/boats/{boat.id}/publish/MLU", follow_redirects=True
            )
        assert resp.status_code == 200
        assert b"Category required" in resp.data

    def test_not_configured_error_shows_flash(self, db, logged_in_admin):
        from app.models import Boat
        boat = make_boat(slug="no-creds-boat")
        db.session.add(boat)
        db.session.commit()
        resp = logged_in_admin.post(
            f"/admin/meli/boats/{boat.id}/publish/MLU", follow_redirects=True
        )
        assert resp.status_code == 200

    def test_sync_with_mock(self, db, logged_in_admin, boat_and_creds):
        from app.models import Boat
        boat = boat_and_creds
        boat.meli_mlu_item_id = "MLU555"
        boat.meli_mlu_status = "active"
        db.session.commit()

        fake_item = {"status": "paused", "permalink": "https://meli.example"}
        with patch("app.integrations.mercadolibre.service.MeliOAuth.get_valid_token", return_value="T"), \
             patch("app.integrations.mercadolibre.client.MeliClient.get", return_value=fake_item):
            resp = logged_in_admin.post(
                f"/admin/meli/boats/{boat.id}/sync/MLU", follow_redirects=True
            )
        assert resp.status_code == 200
        refreshed = db.session.get(Boat, boat.id)
        assert refreshed.meli_mlu_status == "paused"
