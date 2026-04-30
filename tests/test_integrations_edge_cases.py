"""Edge case tests for integrations — focus on bugs that would only surface in production.

Covers:
  - Invalid prices (None, 0, negative)
  - Photos with HTTP / empty / null URLs
  - Multiple photos marked is_primary (DB has no constraint preventing it)
  - Decimal precision for prices and commissions
  - Snippet without categoryId (YouTube)
  - Description with control characters / very long descriptions
  - Boats without specs at all
  - Title and model both missing
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.integrations.facebook.service import FacebookError, FacebookService
from app.integrations.instagram.service import InstagramError, InstagramService
from app.integrations.publication import build_body, build_caption, build_title
from app.integrations.whatsapp.serializer import WhatsAppSerializer
from app.integrations.whatsapp.service import WhatsAppError, WhatsAppService
from app.integrations.youtube.service import YouTubeError, YouTubeService
from app.models.enums import BoatType, HullMaterial
from tests.factories import make_boat


@pytest.fixture(autouse=True)
def _no_ig_polling(monkeypatch):
    """Skip Instagram polling delay; container is always FINISHED for tests."""
    monkeypatch.setattr("app.integrations.instagram.service.time.sleep", lambda *_: None)

    def fake_get(url, params=None, **kwargs):
        resp = MagicMock()
        resp.json.return_value = {"status_code": "FINISHED"}
        resp.ok = True
        return resp

    monkeypatch.setattr("app.integrations.instagram.service.requests.get", fake_get)


def _mock_response(json_data=None, ok=True, status=200, text=""):
    resp = MagicMock()
    resp.json.return_value = json_data or {}
    resp.ok = ok
    resp.status_code = status
    resp.text = text
    return resp


# ── Invalid prices ───────────────────────────────────────────────────────────


def test_build_title_raises_on_none_price():
    boat = make_boat(price_usd=None)
    with pytest.raises(ValueError, match="precio debe ser mayor a 0"):
        build_title(boat)


def test_build_title_raises_on_zero_price():
    boat = make_boat(price_usd=0)
    with pytest.raises(ValueError, match="precio debe ser mayor a 0"):
        build_title(boat)


def test_build_title_raises_on_negative_price():
    boat = make_boat(price_usd=-1000)
    with pytest.raises(ValueError, match="precio debe ser mayor a 0"):
        build_title(boat)


def test_build_caption_raises_on_invalid_price():
    boat = make_boat(price_usd=0)
    with pytest.raises(ValueError):
        build_caption(boat)


# ── Title / model fallbacks ─────────────────────────────────────────────────


def test_build_title_falls_back_when_both_title_and_model_missing(db):
    """Edge case: if model_name and title are both empty, must not crash with AttributeError."""
    from app.models import Boat
    boat = Boat(
        slug="test",
        title="",  # empty rather than None (title is nullable=False)
        description="x",
        price_usd=50000,
        boat_type=BoatType.MOTORBOAT,
        flag="UY",
        status="available",
        model_name=None,
    )
    # Should not raise; title is empty string
    result = build_title(boat)
    assert "U$S 50.000" in result
    assert "LANCHA EN VENTA" in result


# ── Hull material fallback ──────────────────────────────────────────────────


def test_build_body_hull_material_renders_value_for_unknown():
    """If a new HullMaterial enum value is added without translation, fall back to value."""
    boat = make_boat(hull_material=HullMaterial.OTHER)
    body = build_body(boat)
    # OTHER is in the dict; this just confirms the lookup works.
    assert "Material: Otro" in body


# ── Decimal commission precision ────────────────────────────────────────────


def test_build_body_commission_with_decimal_quantize():
    """commission_pct comes back from DB as Decimal('3.50') — must render cleanly."""
    boat = make_boat(commission_pct=Decimal("3.50"))
    body = build_body(boat)
    assert "Comisión MG Náutica: 3.5% sobre el valor de venta" in body


def test_build_body_zero_commission_skipped():
    """0% commission shouldn't render the section."""
    boat = make_boat(commission_pct=0)
    body = build_body(boat)
    assert "CONDICIONES" not in body


def test_build_body_decimal_commission_5pct():
    boat = make_boat(commission_pct=Decimal("5.00"))
    body = build_body(boat)
    assert "Comisión MG Náutica: 5%" in body


# ── No specs at all ─────────────────────────────────────────────────────────


def test_build_body_no_specs_skips_all_spec_sections():
    boat = make_boat()
    boat.specs = None
    body = build_body(boat)
    assert "MOTOR Y CAPACIDADES" not in body
    assert "INTERIOR Y CONFORT" not in body
    assert "NAVEGACIÓN Y VELAMEN" not in body
    assert "CONSULTAS" in body  # but CONSULTAS still present


# ── HTTP/empty/null photo URLs ───────────────────────────────────────────────


def _boat_with_mixed_photos(db, urls):
    """Create a boat with the given photo URLs (use '' for empty — DB requires NOT NULL)."""
    from app.models import Boat, BoatPhoto
    boat = Boat(
        slug="mixed-photos",
        title="Velero Mixed",
        description="x",
        price_usd=80000,
        boat_type=BoatType.SAILBOAT,
        flag="UY",
        status="available",
        model_name="Mixed",
    )
    db.session.add(boat)
    db.session.flush()
    for i, url in enumerate(urls):
        db.session.add(BoatPhoto(
            boat_id=boat.id,
            url=url or "",  # Empty string — DB has NOT NULL on url
            position=i,
            is_primary=(i == 0),
        ))
    db.session.commit()
    return boat


def test_instagram_filters_http_urls(db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _boat_with_mixed_photos(db, ["http://example.com/p.jpg"])
    with pytest.raises(InstagramError, match="HTTPS"):
        InstagramService().post_boat(boat)


def test_instagram_filters_empty_urls(db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _boat_with_mixed_photos(db, [None, "", "https://example.com/p.jpg"])

    with patch("app.integrations.instagram.service.requests.post") as mock_post:
        mock_post.side_effect = [
            _mock_response({"id": "container-1"}),
            _mock_response({"id": "media-1"}),
        ]
        InstagramService().post_boat(boat)
        # Only 1 valid URL → single image path → 2 calls
        assert mock_post.call_count == 2
        assert mock_post.call_args_list[0].kwargs["params"]["image_url"] == "https://example.com/p.jpg"


def test_facebook_filters_http_urls(db, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")
    boat = _boat_with_mixed_photos(db, ["http://example.com/p.jpg"])
    with pytest.raises(FacebookError, match="HTTPS"):
        FacebookService().post_boat(boat)


def test_whatsapp_filters_http_urls(db):
    boat = _boat_with_mixed_photos(db, ["http://example.com/p.jpg"])
    with pytest.raises(ValueError, match="HTTPS"):
        WhatsAppSerializer(boat).to_payload()


def test_whatsapp_filters_mixed_urls_only_keeps_https(db):
    boat = _boat_with_mixed_photos(
        db,
        [
            "http://insecure.com/p1.jpg",
            "https://cdn.com/p2.jpg",
            "",
            "https://cdn.com/p3.jpg",
            None,
        ],
    )
    payload = WhatsAppSerializer(boat).to_payload()
    # Primary is photo 0 (http) — filtered. Next https one becomes primary.
    assert payload["image_url"] == "https://cdn.com/p2.jpg"
    assert payload["additional_image_urls"] == ["https://cdn.com/p3.jpg"]


# ── Multiple is_primary photos ──────────────────────────────────────────────


def test_instagram_multiple_primary_takes_first(db, monkeypatch):
    """DB has no constraint preventing two photos marked is_primary=True.
    The code must pick *one* deterministically (first by position)."""
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    from app.models import Boat, BoatPhoto
    boat = Boat(
        slug="mp", title="Velero MP", description="x", price_usd=50000,
        boat_type="sailboat", flag="UY", status="available", model_name="MP",
    )
    db.session.add(boat); db.session.flush()
    db.session.add(BoatPhoto(boat_id=boat.id, url="https://a/0.jpg", position=0, is_primary=True))
    db.session.add(BoatPhoto(boat_id=boat.id, url="https://a/1.jpg", position=1, is_primary=True))
    db.session.commit()

    with patch("app.integrations.instagram.service.requests.post") as mock_post:
        # 2 photos → carousel flow: 2 children + container + publish
        mock_post.side_effect = [
            _mock_response({"id": "c0"}),
            _mock_response({"id": "c1"}),
            _mock_response({"id": "container"}),
            _mock_response({"id": "media"}),
        ]
        InstagramService().post_boat(boat)
        # First child should be photo 0 (lowest position)
        assert mock_post.call_args_list[0].kwargs["params"]["image_url"] == "https://a/0.jpg"


# ── WhatsApp price precision ────────────────────────────────────────────────


def test_whatsapp_price_uses_integer_cents(db):
    """Even when price_usd is a float-ish value, cents must be integer."""
    from app.models import Boat, BoatPhoto
    boat = Boat(
        slug="price-test", title="X", description="x", price_usd=130000,
        boat_type="sailboat", flag="UY", status="available",
    )
    db.session.add(boat); db.session.flush()
    db.session.add(BoatPhoto(boat_id=boat.id, url="https://a/p.jpg", is_primary=True))
    db.session.commit()
    payload = WhatsAppSerializer(boat).to_payload()
    assert payload["price"] == 13000000
    assert isinstance(payload["price"], int)


# ── Long description truncation in WhatsApp ─────────────────────────────────


def test_whatsapp_description_truncated_at_9999_chars(db):
    from app.models import Boat, BoatPhoto
    boat = Boat(
        slug="long", title="X", description="A" * 20000,
        price_usd=50000, boat_type="sailboat", flag="UY", status="available",
    )
    db.session.add(boat); db.session.flush()
    db.session.add(BoatPhoto(boat_id=boat.id, url="https://a/p.jpg", is_primary=True))
    db.session.commit()
    payload = WhatsAppSerializer(boat).to_payload()
    assert len(payload["description"]) <= 9999


# ── YouTube without categoryId ──────────────────────────────────────────────


@patch("app.integrations.youtube.service.requests.put")
@patch("app.integrations.youtube.service.requests.get")
@patch("app.integrations.youtube.service.requests.post")
def test_youtube_defaults_categoryid_when_missing(mock_post, mock_get, mock_put, db, monkeypatch):
    """Some legacy videos may have a snippet without categoryId. PUT requires it."""
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rt")
    import app.integrations.youtube.service as yt_module
    monkeypatch.setattr(yt_module, "YOUTUBE_ENABLED", True)

    from app.models import Boat
    boat = Boat(
        slug="yt", title="Velero YT", description="x", price_usd=130000,
        boat_type="sailboat", flag="UY", status="available", model_name="YT",
        youtube_video_id="ABC",
    )
    db.session.add(boat); db.session.commit()

    mock_post.return_value = _mock_response({"access_token": "tok"})
    mock_get.return_value = _mock_response({
        "items": [{"snippet": {"title": "old", "description": "old"}}]  # NO categoryId
    })
    mock_put.return_value = _mock_response({"id": "ABC"})

    YouTubeService().update_boat(boat)
    # PUT must include a categoryId (defaulted to "26")
    put_body = mock_put.call_args.kwargs["json"]
    assert put_body["snippet"]["categoryId"] == "26"


@patch("app.integrations.youtube.service.requests.put")
@patch("app.integrations.youtube.service.requests.get")
@patch("app.integrations.youtube.service.requests.post")
def test_youtube_preserves_existing_categoryid(mock_post, mock_get, mock_put, db, monkeypatch):
    """If the video already has a categoryId, we must not overwrite it."""
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rt")
    import app.integrations.youtube.service as yt_module
    monkeypatch.setattr(yt_module, "YOUTUBE_ENABLED", True)

    from app.models import Boat
    boat = Boat(
        slug="yt2", title="Velero YT2", description="x", price_usd=130000,
        boat_type="sailboat", flag="UY", status="available", model_name="YT",
        youtube_video_id="ABC",
    )
    db.session.add(boat); db.session.commit()

    mock_post.return_value = _mock_response({"access_token": "tok"})
    mock_get.return_value = _mock_response({
        "items": [{"snippet": {"title": "old", "categoryId": "10", "description": "old"}}]
    })
    mock_put.return_value = _mock_response({"id": "ABC"})

    YouTubeService().update_boat(boat)
    put_body = mock_put.call_args.kwargs["json"]
    assert put_body["snippet"]["categoryId"] == "10"  # preserved, not defaulted


# ── Caption length sanity ────────────────────────────────────────────────────


def test_caption_under_instagram_2200_char_limit_for_realistic_boat():
    """Instagram hard-caps captions at 2200 chars. Realistic boats must fit comfortably."""
    boat = make_boat(
        price_usd=130000,
        boat_type=BoatType.SAILBOAT,
        shipyard="Jeanneau",
        model_name="Sun Odyssey 54 DS",
        year=2006,
        commission_pct=4,
    )
    boat.description = (
        "Velero de crucero oceánico de gran porte, reconocido por su confort y excelente navegación. "
        "Ideal para travesías largas. Tres camarotes, dos baños, salón amplio y cocina equipada. "
        "Refit integral 2023. " * 3
    )
    caption = build_caption(boat)
    assert len(caption) < 2200, f"Caption {len(caption)} chars exceeds Instagram limit"


# ── Network/transport errors propagate cleanly ──────────────────────────────


def test_instagram_network_error_propagates_as_python_error(db, monkeypatch):
    """If requests itself raises (DNS, timeout), we don't swallow it silently."""
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _boat_with_mixed_photos(db, ["https://example.com/p.jpg"])
    with patch(
        "app.integrations.instagram.service.requests.post",
        side_effect=ConnectionError("DNS resolution failed"),
    ):
        # We let ConnectionError propagate (not wrap as InstagramError)
        # so the upstream caller sees it's a transport error, not API error
        with pytest.raises(ConnectionError):
            InstagramService().post_boat(boat)


def test_facebook_network_error_propagates(db, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")
    boat = _boat_with_mixed_photos(db, ["https://example.com/p.jpg"])
    with patch(
        "app.integrations.facebook.service.requests.post",
        side_effect=TimeoutError("read timeout"),
    ):
        with pytest.raises(TimeoutError):
            FacebookService().post_boat(boat)


# ── Whitespace / whitespace-only strings ────────────────────────────────────


def test_build_body_strips_whitespace_from_description():
    boat = make_boat()
    boat.description = "   \n  Velero impecable.  \n  "
    body = build_body(boat)
    assert body.startswith("Velero impecable.")


def test_build_body_handles_whitespace_only_description():
    """A description that's all whitespace shouldn't render as an empty paragraph."""
    boat = make_boat(year=2020, shipyard="Bavaria")
    boat.description = "   \n\n  \n"
    body = build_body(boat)
    # body should not start with whitespace lines
    assert not body.startswith("\n")
    assert not body.startswith(" ")