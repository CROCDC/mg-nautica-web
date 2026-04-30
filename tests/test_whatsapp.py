"""Tests for the WhatsApp Business Catalog integration."""
from unittest.mock import MagicMock, patch

import pytest

from app.integrations.whatsapp.serializer import WhatsAppSerializer
from app.integrations.whatsapp.service import WhatsAppError, WhatsAppService


def _mock_response(json_data=None, ok=True, status=200):
    resp = MagicMock()
    resp.json.return_value = json_data or {}
    resp.ok = ok
    resp.status_code = status
    return resp


def _make_boat_with_photos(db, n_photos=2):
    from app.models import Boat, BoatPhoto
    boat = Boat(
        slug="velero-wa-jeanneau",
        title="Velero Jeanneau Sun Odyssey 54 DS",
        description="Velero impecable.",
        price_usd=130000,
        boat_type="sailboat",
        flag="UY",
        status="available",
        shipyard="Jeanneau",
        model_name="Sun Odyssey 54 DS",
        year=2006,
    )
    db.session.add(boat)
    db.session.flush()
    for i in range(n_photos):
        db.session.add(BoatPhoto(
            boat_id=boat.id,
            url=f"https://cdn.example.com/wa-photo{i}.jpg",
            position=i,
            is_primary=(i == 0),
        ))
    db.session.commit()
    return boat


# ── Serializer ───────────────────────────────────────────────────────────────


def test_retailer_id_uses_slug(db):
    boat = _make_boat_with_photos(db)
    assert WhatsAppSerializer(boat).retailer_id() == "boat-velero-wa-jeanneau"


def test_payload_required_fields(db):
    boat = _make_boat_with_photos(db, n_photos=1)
    payload = WhatsAppSerializer(boat).to_payload()

    assert payload["retailer_id"] == "boat-velero-wa-jeanneau"
    assert "U$S 130.000" in payload["name"]
    assert "VELERO EN VENTA" in payload["name"]
    assert "CONSULTAS" in payload["description"]
    assert payload["price"] == 13000000  # $130,000 in cents
    assert payload["currency"] == "USD"
    assert payload["image_url"] == "https://cdn.example.com/wa-photo0.jpg"
    assert payload["availability"] == "in stock"
    assert payload["condition"] == "used"
    assert "/boats/velero-wa-jeanneau" in payload["url"]
    assert payload["brand"] == "Jeanneau"


def test_payload_uses_publicsiteurl_env(db, monkeypatch):
    monkeypatch.setenv("PUBLIC_SITE_URL", "https://staging.mgnautica.com/")
    boat = _make_boat_with_photos(db, n_photos=1)
    payload = WhatsAppSerializer(boat).to_payload()
    assert payload["url"] == "https://staging.mgnautica.com/boats/velero-wa-jeanneau"


def test_payload_brand_falls_back_when_no_shipyard(db):
    from app.models import Boat, BoatPhoto
    boat = Boat(
        slug="b",
        title="X",
        description="x",
        price_usd=1000,
        boat_type="sailboat",
        flag="UY",
        status="available",
        shipyard=None,
    )
    db.session.add(boat)
    db.session.flush()
    db.session.add(BoatPhoto(boat_id=boat.id, url="https://x/p.jpg", is_primary=True))
    db.session.commit()

    payload = WhatsAppSerializer(boat).to_payload()
    assert payload["brand"] == "MG Náutica"


def test_payload_additional_images_capped_at_9(db):
    boat = _make_boat_with_photos(db, n_photos=15)
    payload = WhatsAppSerializer(boat).to_payload()
    assert len(payload["additional_image_urls"]) == 9
    # Primary photo should not be in additional_image_urls
    assert payload["image_url"] not in payload["additional_image_urls"]


def test_payload_no_additional_images_when_only_primary(db):
    boat = _make_boat_with_photos(db, n_photos=1)
    payload = WhatsAppSerializer(boat).to_payload()
    assert "additional_image_urls" not in payload


def test_payload_raises_when_no_photos(db):
    from app.models import Boat
    boat = Boat(
        slug="b",
        title="X",
        description="x",
        price_usd=1000,
        boat_type="sailboat",
        flag="UY",
        status="available",
    )
    db.session.add(boat)
    db.session.commit()

    with pytest.raises(ValueError, match="no tiene fotos"):
        WhatsAppSerializer(boat).to_payload()


def test_payload_name_truncated_at_150_chars(db):
    boat = _make_boat_with_photos(db, n_photos=1)
    boat.model_name = "X" * 200  # very long model name
    payload = WhatsAppSerializer(boat).to_payload()
    assert len(payload["name"]) <= 150


# ── Service ──────────────────────────────────────────────────────────────────


def test_sync_raises_when_credentials_missing(db, monkeypatch):
    monkeypatch.delenv("WHATSAPP_CATALOG_ID", raising=False)
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)

    boat = _make_boat_with_photos(db)
    with pytest.raises(WhatsAppError, match="no está configurado"):
        WhatsAppService().sync_boat(boat)


def test_sync_propagates_serializer_error(db, monkeypatch):
    monkeypatch.setenv("WHATSAPP_CATALOG_ID", "cat-1")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "tok")

    from app.models import Boat
    boat = Boat(
        slug="no-photo", title="X", description="x", price_usd=1000,
        boat_type="sailboat", flag="UY", status="available",
    )
    db.session.add(boat)
    db.session.commit()

    with pytest.raises(WhatsAppError, match="no tiene fotos"):
        WhatsAppService().sync_boat(boat)


@patch("app.integrations.whatsapp.service.requests.post")
def test_sync_uses_items_batch_with_update_method(mock_post, db, monkeypatch):
    monkeypatch.setenv("WHATSAPP_CATALOG_ID", "cat-1")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "tok")
    boat = _make_boat_with_photos(db)

    mock_post.return_value = _mock_response({"handles": ["h1"]})

    retailer_id = WhatsAppService().sync_boat(boat)
    assert retailer_id == "boat-velero-wa-jeanneau"

    assert mock_post.call_count == 1
    call = mock_post.call_args
    assert "items_batch" in call.args[0]
    assert "/cat-1/" in call.args[0]

    body = call.kwargs["json"]
    assert body["access_token"] == "tok"
    assert body["item_type"] == "PRODUCT_ITEM"
    assert len(body["requests"]) == 1
    assert body["requests"][0]["method"] == "UPDATE"
    assert body["requests"][0]["data"]["retailer_id"] == "boat-velero-wa-jeanneau"


@patch("app.integrations.whatsapp.service.requests.post")
def test_sync_raises_on_api_error(mock_post, db, monkeypatch):
    monkeypatch.setenv("WHATSAPP_CATALOG_ID", "cat-1")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "tok")
    boat = _make_boat_with_photos(db)

    mock_post.return_value = _mock_response(
        {"error": {"message": "Permission denied"}},
        ok=False,
        status=403,
    )

    with pytest.raises(WhatsAppError, match="Permission denied"):
        WhatsAppService().sync_boat(boat)


@patch("app.integrations.whatsapp.service.requests.post")
def test_sync_raises_when_no_handles_returned(mock_post, db, monkeypatch):
    """API can return 200 but with an error structure — we treat missing handles as failure."""
    monkeypatch.setenv("WHATSAPP_CATALOG_ID", "cat-1")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "tok")
    boat = _make_boat_with_photos(db)

    mock_post.return_value = _mock_response({"error": {"message": "Bad request"}})

    with pytest.raises(WhatsAppError):
        WhatsAppService().sync_boat(boat)


@patch("app.integrations.whatsapp.service.requests.post")
def test_delete_sends_delete_method(mock_post, db, monkeypatch):
    monkeypatch.setenv("WHATSAPP_CATALOG_ID", "cat-1")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "tok")
    boat = _make_boat_with_photos(db)

    mock_post.return_value = _mock_response({"handles": ["h1"]})

    WhatsAppService().delete_boat(boat)

    body = mock_post.call_args.kwargs["json"]
    assert body["requests"][0]["method"] == "DELETE"
    assert body["requests"][0]["data"]["retailer_id"] == "boat-velero-wa-jeanneau"


def test_delete_raises_when_credentials_missing(db, monkeypatch):
    monkeypatch.delenv("WHATSAPP_CATALOG_ID", raising=False)
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)

    boat = _make_boat_with_photos(db)
    with pytest.raises(WhatsAppError, match="no está configurado"):
        WhatsAppService().delete_boat(boat)


@patch("app.integrations.whatsapp.service.requests.post")
def test_delete_raises_on_api_error(mock_post, db, monkeypatch):
    monkeypatch.setenv("WHATSAPP_CATALOG_ID", "cat-1")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "tok")
    boat = _make_boat_with_photos(db)

    mock_post.return_value = _mock_response(
        {"error": {"message": "Not found"}}, ok=False, status=404,
    )

    with pytest.raises(WhatsAppError, match="Not found"):
        WhatsAppService().delete_boat(boat)
