"""Tests for the Facebook integration."""
from unittest.mock import MagicMock, patch

import pytest

from app.integrations.facebook.service import FacebookError, FacebookService


def _mock_response(json_data, ok=True, status=200):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.ok = ok
    resp.status_code = status
    return resp


def _make_boat_with_n_photos(db, n: int):
    from app.models import Boat, BoatPhoto

    boat = Boat(
        slug=f"velero-fb-{n}",
        title=f"Velero FB Test {n}",
        description="Velero impecable.",
        price_usd=95000,
        boat_type="sailboat",
        flag="UY",
        status="available",
        model_name=f"FB Test {n}",
    )
    db.session.add(boat)
    db.session.flush()
    for i in range(n):
        db.session.add(BoatPhoto(
            boat_id=boat.id,
            url=f"https://cdn.example.com/fb-photo{i}.jpg",
            position=i,
            is_primary=(i == 0),
        ))
    db.session.commit()
    return boat


# ── Configuration ─────────────────────────────────────────────────────────────


def test_raises_when_token_missing(db, monkeypatch):
    monkeypatch.delenv("FACEBOOK_PAGE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("FACEBOOK_PAGE_ID", raising=False)

    boat = _make_boat_with_n_photos(db, 1)
    with pytest.raises(FacebookError, match="no está configurado"):
        FacebookService().post_boat(boat)


def test_raises_when_no_photos(db, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")

    boat = _make_boat_with_n_photos(db, 0)
    with pytest.raises(FacebookError, match="no tiene fotos"):
        FacebookService().post_boat(boat)


# ── Single photo flow ────────────────────────────────────────────────────────


@patch("app.integrations.facebook.service.requests.post")
def test_single_photo_uses_photos_endpoint(mock_post, db, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")
    boat = _make_boat_with_n_photos(db, 1)

    mock_post.return_value = _mock_response({"id": "post-123", "post_id": "999_123"})

    post_id = FacebookService().post_boat(boat)

    assert post_id == "post-123"
    assert mock_post.call_count == 1

    call = mock_post.call_args
    assert "/photos" in call.args[0]
    assert call.kwargs["params"]["url"] == "https://cdn.example.com/fb-photo0.jpg"
    assert call.kwargs["params"]["published"] == "true"
    assert "message" in call.kwargs["params"]


@patch("app.integrations.facebook.service.requests.post")
def test_single_photo_caption_uses_shared_builder(mock_post, db, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")
    boat = _make_boat_with_n_photos(db, 1)

    mock_post.return_value = _mock_response({"id": "post-1"})

    FacebookService().post_boat(boat)

    message = mock_post.call_args.kwargs["params"]["message"]
    assert "U$S 95.000" in message
    assert "VELERO EN VENTA" in message
    assert "CONSULTAS" in message


# ── Multi-photo flow ─────────────────────────────────────────────────────────


@patch("app.integrations.facebook.service.requests.post")
def test_multi_photo_stages_then_creates_feed_post(mock_post, db, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")
    boat = _make_boat_with_n_photos(db, 3)

    # 3 staged photos + 1 feed post = 4 calls
    mock_post.side_effect = [
        _mock_response({"id": "photo-0"}),
        _mock_response({"id": "photo-1"}),
        _mock_response({"id": "photo-2"}),
        _mock_response({"id": "post-multi"}),
    ]

    post_id = FacebookService().post_boat(boat)

    assert post_id == "post-multi"
    assert mock_post.call_count == 4

    # First 3 calls go to /photos with published=false
    for i in range(3):
        call = mock_post.call_args_list[i]
        assert "/photos" in call.args[0]
        assert call.kwargs["params"]["published"] == "false"

    # Last call goes to /feed with attached_media in JSON body
    feed_call = mock_post.call_args_list[3]
    assert "/feed" in feed_call.args[0]
    body = feed_call.kwargs["json"]
    assert body["attached_media"] == [
        {"media_fbid": "photo-0"},
        {"media_fbid": "photo-1"},
        {"media_fbid": "photo-2"},
    ]
    assert "message" in body


@patch("app.integrations.facebook.service.requests.post")
def test_multi_photo_two_photos_uses_feed_endpoint(mock_post, db, monkeypatch):
    """Edge case: 2 photos go through staging+feed, not a single /photos call."""
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")
    boat = _make_boat_with_n_photos(db, 2)

    mock_post.side_effect = [
        _mock_response({"id": "photo-0"}),
        _mock_response({"id": "photo-1"}),
        _mock_response({"id": "post-multi"}),
    ]

    FacebookService().post_boat(boat)

    assert mock_post.call_count == 3
    assert "/feed" in mock_post.call_args_list[2].args[0]


# ── Error handling ───────────────────────────────────────────────────────────


@patch("app.integrations.facebook.service.requests.post")
def test_raises_on_single_photo_failure(mock_post, db, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")
    boat = _make_boat_with_n_photos(db, 1)

    mock_post.return_value = _mock_response(
        {"error": {"message": "Invalid OAuth token"}},
        ok=False,
        status=401,
    )

    with pytest.raises(FacebookError, match="Invalid OAuth token"):
        FacebookService().post_boat(boat)


@patch("app.integrations.facebook.service.requests.post")
def test_raises_on_staging_failure(mock_post, db, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")
    boat = _make_boat_with_n_photos(db, 3)

    mock_post.side_effect = [
        _mock_response({"id": "photo-0"}),
        _mock_response({"error": {"message": "Image fetch failed"}}, ok=False, status=400),
    ]

    with pytest.raises(FacebookError, match="Image fetch failed"):
        FacebookService().post_boat(boat)


@patch("app.integrations.facebook.service.requests.post")
def test_raises_on_feed_failure(mock_post, db, monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")
    boat = _make_boat_with_n_photos(db, 2)

    mock_post.side_effect = [
        _mock_response({"id": "photo-0"}),
        _mock_response({"id": "photo-1"}),
        _mock_response({"error": {"message": "Permission denied"}}, ok=False, status=403),
    ]

    with pytest.raises(FacebookError, match="Permission denied"):
        FacebookService().post_boat(boat)
