"""Tests for the YouTube integration."""
from unittest.mock import MagicMock, patch

import pytest

from app.integrations.youtube.service import YouTubeError, YouTubeService


def _mock_response(json_data=None, ok=True, status=200, text=""):
    resp = MagicMock()
    resp.json.return_value = json_data or {}
    resp.ok = ok
    resp.status_code = status
    resp.text = text
    return resp


def _make_boat(db, video_id="ABC123XYZ"):
    from app.models import Boat
    boat = Boat(
        slug="velero-yt",
        title="Velero YT Test",
        description="Velero impecable.",
        price_usd=130000,
        boat_type="sailboat",
        flag="UY",
        status="available",
        model_name="Sun Odyssey 54 DS",
        youtube_video_id=video_id,
    )
    db.session.add(boat)
    db.session.commit()
    return boat


# ── Configuration ─────────────────────────────────────────────────────────────


def test_raises_when_credentials_missing(db, monkeypatch):
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)
    # Patch the module-level flag directly (it's evaluated at import time)
    import app.integrations.youtube.service as yt_module
    monkeypatch.setattr(yt_module, "YOUTUBE_ENABLED", False)

    boat = _make_boat(db)
    with pytest.raises(YouTubeError, match="no está configurado"):
        YouTubeService().update_boat(boat)


def test_raises_when_boat_has_no_video_id(db, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rt")
    import app.integrations.youtube.service as yt_module
    monkeypatch.setattr(yt_module, "YOUTUBE_ENABLED", True)

    boat = _make_boat(db, video_id=None)
    with pytest.raises(YouTubeError, match="no tiene youtube_video_id"):
        YouTubeService().update_boat(boat)


# ── Happy path ───────────────────────────────────────────────────────────────


@patch("app.integrations.youtube.service.requests.put")
@patch("app.integrations.youtube.service.requests.get")
@patch("app.integrations.youtube.service.requests.post")
def test_update_boat_full_flow(mock_post, mock_get, mock_put, db, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rt")
    import app.integrations.youtube.service as yt_module
    monkeypatch.setattr(yt_module, "YOUTUBE_ENABLED", True)

    boat = _make_boat(db, video_id="ABC123")

    mock_post.return_value = _mock_response({"access_token": "ya29.access"})
    mock_get.return_value = _mock_response({
        "items": [{
            "snippet": {
                "title": "old title",
                "description": "old desc",
                "categoryId": "26",
                "tags": ["sailing"],
            }
        }]
    })
    mock_put.return_value = _mock_response({"id": "ABC123"})

    video_id = YouTubeService().update_boat(boat)
    assert video_id == "ABC123"

    assert mock_post.call_args.args[0] == "https://oauth2.googleapis.com/token"
    assert mock_post.call_args.kwargs["data"]["grant_type"] == "refresh_token"

    assert "/videos" in mock_get.call_args.args[0]
    assert mock_get.call_args.kwargs["params"]["id"] == "ABC123"
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer ya29.access"

    put_body = mock_put.call_args.kwargs["json"]
    assert put_body["id"] == "ABC123"
    assert put_body["snippet"]["categoryId"] == "26"
    assert put_body["snippet"]["tags"] == ["sailing"]
    assert "U$S 130.000" in put_body["snippet"]["title"]
    assert "VELERO EN VENTA" in put_body["snippet"]["title"]
    assert "CONSULTAS" in put_body["snippet"]["description"]


@patch("app.integrations.youtube.service.requests.post")
def test_token_exchange_failure(mock_post, db, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rt")
    import app.integrations.youtube.service as yt_module
    monkeypatch.setattr(yt_module, "YOUTUBE_ENABLED", True)

    boat = _make_boat(db)
    mock_post.return_value = _mock_response(
        {"error": "invalid_grant"}, ok=False, status=400
    )

    with pytest.raises(YouTubeError, match="Error obteniendo access token"):
        YouTubeService().update_boat(boat)


@patch("app.integrations.youtube.service.requests.get")
@patch("app.integrations.youtube.service.requests.post")
def test_snippet_not_found(mock_post, mock_get, db, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rt")
    import app.integrations.youtube.service as yt_module
    monkeypatch.setattr(yt_module, "YOUTUBE_ENABLED", True)

    boat = _make_boat(db, video_id="missing")
    mock_post.return_value = _mock_response({"access_token": "tok"})
    mock_get.return_value = _mock_response({"items": []})

    with pytest.raises(YouTubeError, match="no encontrado"):
        YouTubeService().update_boat(boat)


@patch("app.integrations.youtube.service.requests.get")
@patch("app.integrations.youtube.service.requests.post")
def test_snippet_fetch_api_error(mock_post, mock_get, db, monkeypatch):
    """API returns non-OK on the GET /videos call."""
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rt")
    import app.integrations.youtube.service as yt_module
    monkeypatch.setattr(yt_module, "YOUTUBE_ENABLED", True)

    boat = _make_boat(db, video_id="ABC123")
    mock_post.return_value = _mock_response({"access_token": "tok"})
    mock_get.return_value = _mock_response(
        {"error": {"message": "Forbidden"}},
        ok=False,
        status=403,
    )

    with pytest.raises(YouTubeError, match="Error leyendo video"):
        YouTubeService().update_boat(boat)


@patch("app.integrations.youtube.service.requests.put")
@patch("app.integrations.youtube.service.requests.get")
@patch("app.integrations.youtube.service.requests.post")
def test_put_update_failure(mock_post, mock_get, mock_put, db, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rt")
    import app.integrations.youtube.service as yt_module
    monkeypatch.setattr(yt_module, "YOUTUBE_ENABLED", True)

    boat = _make_boat(db)
    mock_post.return_value = _mock_response({"access_token": "tok"})
    mock_get.return_value = _mock_response({
        "items": [{"snippet": {"title": "x", "categoryId": "26"}}]
    })
    mock_put.return_value = _mock_response(ok=False, status=403, text="quotaExceeded")

    with pytest.raises(YouTubeError, match="Error al actualizar"):
        YouTubeService().update_boat(boat)
