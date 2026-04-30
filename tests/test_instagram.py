"""Tests for the Instagram integration.

All Graph API HTTP calls are mocked — no real network requests.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.integrations.instagram.service import InstagramError, InstagramService


@pytest.fixture(autouse=True)
def _no_real_polling(monkeypatch):
    """Skip the polling delay and mock the status_code GET to return FINISHED."""
    monkeypatch.setattr("app.integrations.instagram.service.time.sleep", lambda *_: None)

    def fake_get(url, params=None, **kwargs):
        resp = MagicMock()
        resp.json.return_value = {"status_code": "FINISHED"}
        resp.ok = True
        return resp

    monkeypatch.setattr("app.integrations.instagram.service.requests.get", fake_get)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_post(json_data, ok=True, status=200):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.ok = ok
    resp.status_code = status
    return resp


def _make_boat_with_n_photos(db, n: int):
    from app.models import Boat, BoatPhoto

    boat = Boat(
        slug=f"velero-ig-{n}",
        title=f"Velero Test {n}",
        description="Velero impecable.",
        price_usd=80000,
        boat_type="sailboat",
        flag="UY",
        status="available",
        model_name=f"Test {n}",
    )
    db.session.add(boat)
    db.session.flush()
    for i in range(n):
        db.session.add(BoatPhoto(
            boat_id=boat.id,
            url=f"https://cdn.example.com/photo{i}.jpg",
            position=i,
            is_primary=(i == 0),
        ))
    db.session.commit()
    return boat


# ── Configuration ─────────────────────────────────────────────────────────────


def test_service_raises_when_token_missing(db, monkeypatch):
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", raising=False)

    boat = _make_boat_with_n_photos(db, 1)
    svc = InstagramService()

    with pytest.raises(InstagramError, match="no está configurado"):
        svc.post_boat(boat)


def test_service_raises_when_boat_has_no_photos(db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")

    boat = _make_boat_with_n_photos(db, 0)
    svc = InstagramService()

    with pytest.raises(InstagramError, match="no tiene fotos"):
        svc.post_boat(boat)


# ── Single image flow ────────────────────────────────────────────────────────


@patch("app.integrations.instagram.service.requests.post")
def test_single_photo_uses_image_container_flow(mock_post, db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 1)

    mock_post.side_effect = [
        _mock_post({"id": "container-1"}),  # _create_image_container
        _mock_post({"id": "media-1"}),       # _publish_container
    ]

    svc = InstagramService()
    media_id = svc.post_boat(boat)

    assert media_id == "media-1"
    assert mock_post.call_count == 2

    create_call = mock_post.call_args_list[0]
    create_params = create_call.kwargs["params"]
    assert "image_url" in create_params
    assert create_params["image_url"] == "https://cdn.example.com/photo0.jpg"
    assert "is_carousel_item" not in create_params
    assert "media_type" not in create_params
    assert "caption" in create_params


@patch("app.integrations.instagram.service.requests.post")
def test_single_photo_caption_uses_shared_builder(mock_post, db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 1)

    mock_post.side_effect = [
        _mock_post({"id": "container-1"}),
        _mock_post({"id": "media-1"}),
    ]

    InstagramService().post_boat(boat)

    caption = mock_post.call_args_list[0].kwargs["params"]["caption"]
    assert "U$S 80.000" in caption
    assert "VELERO EN VENTA" in caption
    assert "CONSULTAS" in caption


# ── Carousel flow ─────────────────────────────────────────────────────────────


@patch("app.integrations.instagram.service.requests.post")
def test_carousel_with_three_photos(mock_post, db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 3)

    # 3 children + 1 carousel container + 1 publish = 5 calls
    mock_post.side_effect = [
        _mock_post({"id": "child-0"}),
        _mock_post({"id": "child-1"}),
        _mock_post({"id": "child-2"}),
        _mock_post({"id": "carousel-1"}),
        _mock_post({"id": "media-1"}),
    ]

    media_id = InstagramService().post_boat(boat)

    assert media_id == "media-1"
    assert mock_post.call_count == 5

    # First 3 calls are children with is_carousel_item=true
    for i in range(3):
        params = mock_post.call_args_list[i].kwargs["params"]
        assert params["is_carousel_item"] == "true"
        assert "caption" not in params

    # 4th call is the carousel container
    carousel_params = mock_post.call_args_list[3].kwargs["params"]
    assert carousel_params["media_type"] == "CAROUSEL"
    assert carousel_params["children"] == "child-0,child-1,child-2"
    assert "caption" in carousel_params


@patch("app.integrations.instagram.service.requests.post")
def test_carousel_caps_at_10_photos(mock_post, db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 15)

    # Should only create 10 children, not 15
    side_effects = [_mock_post({"id": f"child-{i}"}) for i in range(10)]
    side_effects.append(_mock_post({"id": "carousel-1"}))
    side_effects.append(_mock_post({"id": "media-1"}))
    mock_post.side_effect = side_effects

    InstagramService().post_boat(boat)

    # 10 children + 1 carousel + 1 publish = 12 calls (not 17)
    assert mock_post.call_count == 12


@patch("app.integrations.instagram.service.requests.post")
def test_carousel_two_photos_uses_carousel_not_single(mock_post, db, monkeypatch):
    """Edge case: 2 photos must use the carousel flow (single requires exactly 1)."""
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 2)

    mock_post.side_effect = [
        _mock_post({"id": "child-0"}),
        _mock_post({"id": "child-1"}),
        _mock_post({"id": "carousel-1"}),
        _mock_post({"id": "media-1"}),
    ]

    InstagramService().post_boat(boat)

    # Should see media_type=CAROUSEL in the third call
    third_params = mock_post.call_args_list[2].kwargs["params"]
    assert third_params["media_type"] == "CAROUSEL"


# ── Error handling ────────────────────────────────────────────────────────────


@patch("app.integrations.instagram.service.requests.post")
def test_raises_on_container_creation_failure(mock_post, db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 1)

    mock_post.return_value = _mock_post(
        {"error": {"message": "Invalid image URL"}},
        ok=False,
        status=400,
    )

    with pytest.raises(InstagramError, match="Invalid image URL"):
        InstagramService().post_boat(boat)


@patch("app.integrations.instagram.service.requests.post")
def test_raises_on_publish_failure(mock_post, db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 1)

    mock_post.side_effect = [
        _mock_post({"id": "container-1"}),
        _mock_post({"error": {"message": "Token expired"}}, ok=False, status=401),
    ]

    with pytest.raises(InstagramError, match="Token expired"):
        InstagramService().post_boat(boat)


@patch("app.integrations.instagram.service.requests.post")
def test_raises_on_carousel_child_failure(mock_post, db, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 3)

    mock_post.side_effect = [
        _mock_post({"id": "child-0"}),
        _mock_post({"error": {"message": "Image too small"}}, ok=False, status=400),
    ]

    with pytest.raises(InstagramError, match="Image too small"):
        InstagramService().post_boat(boat)


def test_polling_waits_until_finished(db, monkeypatch):
    """Container starts as IN_PROGRESS, then transitions to FINISHED → publish proceeds."""
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 1)

    states = iter(["IN_PROGRESS", "IN_PROGRESS", "FINISHED"])

    def staged_get(url, params=None, **kwargs):
        resp = MagicMock()
        resp.json.return_value = {"status_code": next(states)}
        resp.ok = True
        return resp

    monkeypatch.setattr("app.integrations.instagram.service.requests.get", staged_get)

    with patch("app.integrations.instagram.service.requests.post") as mock_post:
        mock_post.side_effect = [
            _mock_post({"id": "container-1"}),
            _mock_post({"id": "media-1"}),
        ]
        media_id = InstagramService().post_boat(boat)
        assert media_id == "media-1"


def test_polling_raises_on_error_status(db, monkeypatch):
    """If IG marks the container as ERROR or EXPIRED, fail fast."""
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 1)

    def error_get(url, params=None, **kwargs):
        resp = MagicMock()
        resp.json.return_value = {"status_code": "ERROR", "error": {"message": "rejected"}}
        resp.ok = True
        return resp

    monkeypatch.setattr("app.integrations.instagram.service.requests.get", error_get)

    with patch("app.integrations.instagram.service.requests.post") as mock_post:
        mock_post.return_value = _mock_post({"id": "container-1"})
        with pytest.raises(InstagramError, match="ERROR"):
            InstagramService().post_boat(boat)


def test_polling_timeout_raises(db, monkeypatch):
    """If status never becomes FINISHED, raise after max polls."""
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 1)

    # Always returns IN_PROGRESS — should hit poll limit
    def stuck_get(url, params=None, **kwargs):
        resp = MagicMock()
        resp.json.return_value = {"status_code": "IN_PROGRESS"}
        resp.ok = True
        return resp

    monkeypatch.setattr("app.integrations.instagram.service.requests.get", stuck_get)

    with patch("app.integrations.instagram.service.requests.post") as mock_post:
        mock_post.return_value = _mock_post({"id": "container-1"})
        with pytest.raises(InstagramError, match="no quedó listo"):
            InstagramService().post_boat(boat)


@patch("app.integrations.instagram.service.requests.post")
def test_raises_on_carousel_container_failure(mock_post, db, monkeypatch):
    """Children succeed but the parent CAROUSEL container creation fails."""
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")
    boat = _make_boat_with_n_photos(db, 3)

    mock_post.side_effect = [
        _mock_post({"id": "child-0"}),
        _mock_post({"id": "child-1"}),
        _mock_post({"id": "child-2"}),
        _mock_post(
            {"error": {"message": "Carousel children invalid"}},
            ok=False,
            status=400,
        ),
    ]

    with pytest.raises(InstagramError, match="Carousel children invalid"):
        InstagramService().post_boat(boat)
