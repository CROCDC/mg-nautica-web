"""Tests for the publish orchestrator that wires platform services into Flask routes.

Avoids importlib.reload — patches *_ENABLED flags in-place so the publish module's
own bindings (which were imported at module load) get updated.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from flask import get_flashed_messages

from app.services import publish
from tests.factories import make_boat


def _make_creds(db, site_id="MLU", expired=False):
    from app.models.meli_credentials import MeliCredentials
    offset = -1 if expired else 7200
    creds = MeliCredentials(
        site_id=site_id,
        meli_user_id="123456",
        access_token="APP_USR-test",
        refresh_token="TG-test",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=offset),
    )
    db.session.add(creds)
    db.session.commit()
    return creds


# ── meli_has_credentials ─────────────────────────────────────────────────────


def test_meli_has_credentials_false_when_none(db):
    assert publish.meli_has_credentials() is False


def test_meli_has_credentials_true_when_one_active(db):
    _make_creds(db, site_id="MLU", expired=False)
    assert publish.meli_has_credentials() is True


def test_meli_has_credentials_false_when_only_expired(db):
    _make_creds(db, site_id="MLU", expired=True)
    assert publish.meli_has_credentials() is False


# ── publish_to_meli ──────────────────────────────────────────────────────────


def test_publish_to_meli_warns_when_no_credentials(db, app):
    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        publish.publish_to_meli(boat)
        flashes = get_flashed_messages(with_categories=True)
        assert any(cat == "warning" and "Mercado Libre" in msg for cat, msg in flashes)


def test_publish_to_meli_first_publish(db, app):
    _make_creds(db, site_id="MLU")

    boat = make_boat()
    boat.meli_mlu_item_id = None  # not yet published
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(publish.MeliService, "publish") as mock_pub, \
             patch.object(publish.MeliService, "update") as mock_upd:
            publish.publish_to_meli(boat)
            mock_pub.assert_called_once_with(boat)
            mock_upd.assert_not_called()
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "success" and "publicado" in msg for cat, msg in flashes)


def test_publish_to_meli_update_when_already_published(db, app):
    _make_creds(db, site_id="MLU")

    boat = make_boat()
    boat.meli_mlu_item_id = "MLU111"
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(publish.MeliService, "publish") as mock_pub, \
             patch.object(publish.MeliService, "update") as mock_upd:
            publish.publish_to_meli(boat)
            mock_upd.assert_called_once_with(boat)
            mock_pub.assert_not_called()
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "success" and "sincronizado" in msg for cat, msg in flashes)


def test_publish_to_meli_skips_expired_credentials(db, app):
    _make_creds(db, site_id="MLU", expired=True)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(publish.MeliService, "publish") as mock_pub:
            publish.publish_to_meli(boat)
            mock_pub.assert_not_called()
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "warning" for cat, _ in flashes)


def test_publish_to_meli_handles_api_error(db, app):
    _make_creds(db, site_id="MLU")
    boat = make_boat()
    db.session.add(boat); db.session.commit()

    err = publish.MeliAPIError(400, "category invalid")
    with app.test_request_context():
        with patch.object(publish.MeliService, "publish", side_effect=err):
            publish.publish_to_meli(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(
                cat == "error" and "category invalid" in msg
                for cat, msg in flashes
            )


def test_publish_to_meli_handles_value_error(db, app):
    _make_creds(db, site_id="MLU")
    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(publish.MeliService, "publish", side_effect=ValueError("bad input")):
            publish.publish_to_meli(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "error" and "bad input" in msg for cat, msg in flashes)


def test_publish_to_meli_handles_not_configured_error(db, app):
    _make_creds(db, site_id="MLU")
    boat = make_boat()
    db.session.add(boat); db.session.commit()

    err = publish.MeliNotConfiguredError("missing OAuth")
    with app.test_request_context():
        with patch.object(publish.MeliService, "publish", side_effect=err):
            publish.publish_to_meli(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "error" and "missing OAuth" in msg for cat, msg in flashes)


# ── publish_to_instagram ─────────────────────────────────────────────────────


def test_publish_to_instagram_warns_when_disabled(db, app, monkeypatch):
    monkeypatch.setattr(publish, "INSTAGRAM_ENABLED", False)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        publish.publish_to_instagram(boat)
        flashes = get_flashed_messages(with_categories=True)
        assert any(cat == "warning" and "Instagram" in msg for cat, msg in flashes)


def test_publish_to_instagram_flashes_success(db, app, monkeypatch):
    monkeypatch.setattr(publish, "INSTAGRAM_ENABLED", True)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(publish.InstagramService, "post_boat", return_value="media-1"):
            publish.publish_to_instagram(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "success" and "media-1" in msg for cat, msg in flashes)


def test_publish_to_instagram_flashes_error(db, app, monkeypatch):
    monkeypatch.setattr(publish, "INSTAGRAM_ENABLED", True)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(
            publish.InstagramService,
            "post_boat",
            side_effect=publish.InstagramError("rate limited"),
        ):
            publish.publish_to_instagram(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "error" and "rate limited" in msg for cat, msg in flashes)


# ── Defensive error wrapping (catch unexpected exceptions) ──────────────────


def test_publish_to_instagram_catches_value_error_from_builder(db, app, monkeypatch):
    """If build_caption raises ValueError (eg price=0), surface as user-facing error."""
    monkeypatch.setattr(publish, "INSTAGRAM_ENABLED", True)
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "111")

    from app.models import Boat, BoatPhoto
    boat = Boat(
        slug="zeroprice", title="Z", description="x", price_usd=0,
        boat_type="sailboat", flag="UY", status="available",
    )
    db.session.add(boat); db.session.flush()
    db.session.add(BoatPhoto(boat_id=boat.id, url="https://a/p.jpg", is_primary=True))
    db.session.commit()

    with app.test_request_context():
        publish.publish_to_instagram(boat)
        flashes = get_flashed_messages(with_categories=True)
        assert any(cat == "error" and "precio" in msg for cat, msg in flashes)


def test_publish_to_instagram_catches_unexpected_exception(db, app, monkeypatch):
    """Unexpected exceptions must not bubble up to the user as a 500."""
    monkeypatch.setattr(publish, "INSTAGRAM_ENABLED", True)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(
            publish.InstagramService,
            "post_boat",
            side_effect=ConnectionError("DNS failed"),
        ):
            publish.publish_to_instagram(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(
                cat == "error" and "ConnectionError" in msg
                for cat, msg in flashes
            )


def test_publish_to_facebook_catches_value_error_from_builder(db, app, monkeypatch):
    """build_caption raises ValueError on invalid price; orchestrator must flash, not 500."""
    monkeypatch.setattr(publish, "FACEBOOK_ENABLED", True)
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")

    from app.models import Boat, BoatPhoto
    boat = Boat(
        slug="fb-zero", title="Z", description="x", price_usd=0,
        boat_type="sailboat", flag="UY", status="available",
    )
    db.session.add(boat); db.session.flush()
    db.session.add(BoatPhoto(boat_id=boat.id, url="https://a/p.jpg", is_primary=True))
    db.session.commit()

    with app.test_request_context():
        publish.publish_to_facebook(boat)
        flashes = get_flashed_messages(with_categories=True)
        assert any(cat == "error" and "precio" in msg for cat, msg in flashes)


def test_publish_to_youtube_catches_value_error_from_builder(db, app, monkeypatch):
    monkeypatch.setattr(publish, "YOUTUBE_ENABLED", True)
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rt")
    import app.integrations.youtube.service as yt_module
    monkeypatch.setattr(yt_module, "YOUTUBE_ENABLED", True)

    from app.models import Boat
    boat = Boat(
        slug="yt-zero", title="Z", description="x", price_usd=0,
        boat_type="sailboat", flag="UY", status="available",
        youtube_video_id="ABC",
    )
    db.session.add(boat); db.session.commit()

    # build_title is called inside update_boat — fake the entire pipeline by
    # patching the service to call the builder directly, then propagate
    with app.test_request_context():
        with patch.object(
            publish.YouTubeService,
            "update_boat",
            side_effect=ValueError("precio debe ser mayor a 0"),
        ):
            publish.publish_to_youtube(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "error" and "precio" in msg for cat, msg in flashes)


def test_publish_to_whatsapp_catches_value_error_from_serializer(db, app, monkeypatch):
    """Serializer raises ValueError when no public photos; flashed cleanly."""
    monkeypatch.setattr(publish, "WHATSAPP_ENABLED", True)
    monkeypatch.setenv("WHATSAPP_CATALOG_ID", "cat-1")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "tok")

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    # Service raises WhatsAppError wrapping ValueError today; but if a future
    # change re-exposes ValueError, the orchestrator must still handle it.
    with app.test_request_context():
        with patch.object(
            publish.WhatsAppService,
            "sync_boat",
            side_effect=ValueError("no tiene fotos publicables"),
        ):
            publish.publish_to_whatsapp(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(
                cat == "error" and "fotos" in msg for cat, msg in flashes
            )
            assert boat.whatsapp_synced_at is None


def test_publish_to_facebook_catches_unexpected_exception(db, app, monkeypatch):
    monkeypatch.setattr(publish, "FACEBOOK_ENABLED", True)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(
            publish.FacebookService,
            "post_boat",
            side_effect=TimeoutError("read timeout"),
        ):
            publish.publish_to_facebook(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(
                cat == "error" and "TimeoutError" in msg for cat, msg in flashes
            )


def test_publish_to_youtube_catches_unexpected_exception(db, app, monkeypatch):
    monkeypatch.setattr(publish, "YOUTUBE_ENABLED", True)

    boat = make_boat(youtube_video_id="ABC")
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(
            publish.YouTubeService,
            "update_boat",
            side_effect=RuntimeError("oops"),
        ):
            publish.publish_to_youtube(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(
                cat == "error" and "RuntimeError" in msg for cat, msg in flashes
            )
            # synced_at must NOT be set on error
            assert boat.youtube_synced_at is None


def test_publish_to_whatsapp_catches_unexpected_exception(db, app, monkeypatch):
    monkeypatch.setattr(publish, "WHATSAPP_ENABLED", True)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(
            publish.WhatsAppService,
            "sync_boat",
            side_effect=RuntimeError("network"),
        ):
            publish.publish_to_whatsapp(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(
                cat == "error" and "RuntimeError" in msg for cat, msg in flashes
            )
            assert boat.whatsapp_synced_at is None


def test_publish_to_meli_catches_unexpected_exception(db, app):
    _make_creds(db, site_id="MLU")

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(
            publish.MeliService,
            "publish",
            side_effect=RuntimeError("kaboom"),
        ):
            publish.publish_to_meli(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(
                cat == "error" and "RuntimeError" in msg for cat, msg in flashes
            )


# ── publish_to_facebook ──────────────────────────────────────────────────────


def test_publish_to_facebook_warns_when_disabled(db, app, monkeypatch):
    monkeypatch.setattr(publish, "FACEBOOK_ENABLED", False)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        publish.publish_to_facebook(boat)
        flashes = get_flashed_messages(with_categories=True)
        assert any(cat == "warning" and "Facebook" in msg for cat, msg in flashes)


def test_publish_to_facebook_flashes_success(db, app, monkeypatch):
    monkeypatch.setattr(publish, "FACEBOOK_ENABLED", True)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(publish.FacebookService, "post_boat", return_value="post-1"):
            publish.publish_to_facebook(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "success" and "post-1" in msg for cat, msg in flashes)


def test_publish_to_facebook_flashes_error(db, app, monkeypatch):
    monkeypatch.setattr(publish, "FACEBOOK_ENABLED", True)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(
            publish.FacebookService,
            "post_boat",
            side_effect=publish.FacebookError("boom"),
        ):
            publish.publish_to_facebook(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "error" and "boom" in msg for cat, msg in flashes)


# ── publish_to_youtube ───────────────────────────────────────────────────────


def test_publish_to_youtube_warns_when_disabled(db, app, monkeypatch):
    monkeypatch.setattr(publish, "YOUTUBE_ENABLED", False)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        publish.publish_to_youtube(boat)
        flashes = get_flashed_messages(with_categories=True)
        assert any(cat == "warning" and "YouTube" in msg for cat, msg in flashes)


def test_publish_to_youtube_updates_synced_at_on_success(db, app, monkeypatch):
    monkeypatch.setattr(publish, "YOUTUBE_ENABLED", True)

    boat = make_boat(youtube_video_id="ABC")
    db.session.add(boat); db.session.commit()
    assert boat.youtube_synced_at is None

    with app.test_request_context():
        with patch.object(publish.YouTubeService, "update_boat", return_value="ABC"):
            publish.publish_to_youtube(boat)
            assert boat.youtube_synced_at is not None


def test_publish_to_youtube_flashes_error(db, app, monkeypatch):
    monkeypatch.setattr(publish, "YOUTUBE_ENABLED", True)

    boat = make_boat(youtube_video_id="ABC")
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(
            publish.YouTubeService,
            "update_boat",
            side_effect=publish.YouTubeError("quota exceeded"),
        ):
            publish.publish_to_youtube(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "error" and "quota exceeded" in msg for cat, msg in flashes)
            # Failed sync must NOT touch synced_at
            assert boat.youtube_synced_at is None


# ── publish_to_whatsapp ──────────────────────────────────────────────────────


def test_publish_to_whatsapp_warns_when_disabled(db, app, monkeypatch):
    monkeypatch.setattr(publish, "WHATSAPP_ENABLED", False)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        publish.publish_to_whatsapp(boat)
        flashes = get_flashed_messages(with_categories=True)
        assert any(cat == "warning" and "WhatsApp" in msg for cat, msg in flashes)


def test_publish_to_whatsapp_updates_synced_at_on_success(db, app, monkeypatch):
    monkeypatch.setattr(publish, "WHATSAPP_ENABLED", True)

    boat = make_boat()
    db.session.add(boat); db.session.commit()
    assert boat.whatsapp_synced_at is None

    with app.test_request_context():
        with patch.object(
            publish.WhatsAppService,
            "sync_boat",
            return_value="boat-velero-test",
        ):
            publish.publish_to_whatsapp(boat)
            assert boat.whatsapp_synced_at is not None


def test_publish_to_whatsapp_flashes_error(db, app, monkeypatch):
    monkeypatch.setattr(publish, "WHATSAPP_ENABLED", True)

    boat = make_boat()
    db.session.add(boat); db.session.commit()

    with app.test_request_context():
        with patch.object(
            publish.WhatsAppService,
            "sync_boat",
            side_effect=publish.WhatsAppError("invalid catalog"),
        ):
            publish.publish_to_whatsapp(boat)
            flashes = get_flashed_messages(with_categories=True)
            assert any(cat == "error" and "invalid catalog" in msg for cat, msg in flashes)
            assert boat.whatsapp_synced_at is None
