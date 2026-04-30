"""Publish orchestrator: coordinates publishing a boat across platforms.

Supported platforms:
  - our_site   : set boat.status = AVAILABLE so it appears on the website
  - meli       : publish/sync to all connected Mercado Libre sites (MLU, MLA)
  - instagram  : post photos + caption to Instagram Business account
  - facebook   : post photos + caption to Facebook page
  - youtube    : sync title + description of an already-uploaded video
"""
import logging
from datetime import datetime

from flask import flash

from app.integrations.facebook.service import FACEBOOK_ENABLED, FacebookError, FacebookService
from app.integrations.instagram.service import INSTAGRAM_ENABLED, InstagramError, InstagramService
from app.integrations.mercadolibre.client import MeliAPIError, MeliNotConfiguredError
from app.integrations.mercadolibre.service import SUPPORTED_SITES, MeliService
from app.integrations.whatsapp.service import WHATSAPP_ENABLED, WhatsAppError, WhatsAppService
from app.integrations.youtube.service import YOUTUBE_ENABLED, YouTubeError, YouTubeService
from app.models.meli_credentials import MeliCredentials

log = logging.getLogger(__name__)


def meli_has_credentials() -> bool:
    """True if at least one MELI site has stored (non-expired) credentials."""
    for site_id in SUPPORTED_SITES:
        creds = MeliCredentials.query.filter_by(site_id=site_id).first()
        if creds and not creds.is_expired:
            return True
    return False


def publish_to_meli(boat) -> None:
    """Publish or sync a boat on every connected MELI site.

    - If the boat already has an item ID for a site → update/sync.
    - Otherwise → first publish.
    Flashes success/error messages for each site.
    The caller is responsible for db.session.commit().
    """
    published_any = False
    for site_id in SUPPORTED_SITES:
        creds = MeliCredentials.query.filter_by(site_id=site_id).first()
        if not creds or creds.is_expired:
            continue
        svc = MeliService(site_id)
        prefix = site_id.lower()
        already_published = bool(getattr(boat, f"meli_{prefix}_item_id", None))
        try:
            if already_published:
                svc.update(boat)
                flash(f"'{boat.title}' sincronizado en {site_id}.", "success")
            else:
                svc.publish(boat)
                flash(f"'{boat.title}' publicado en {site_id}.", "success")
            published_any = True
        except MeliNotConfiguredError as exc:
            log.warning("MELI %s not configured boat=%s: %s", site_id, boat.slug, exc)
            flash(f"Mercado Libre ({site_id}): {exc}", "error")
        except MeliAPIError as exc:
            log.warning(
                "MELI %s API error boat=%s status=%s: %s",
                site_id, boat.slug, exc.status_code, exc.message,
            )
            flash(f"Mercado Libre ({site_id}) error {exc.status_code}: {exc.message}", "error")
        except ValueError as exc:
            log.warning("MELI %s value error boat=%s: %s", site_id, boat.slug, exc)
            flash(f"Mercado Libre ({site_id}): {exc}", "error")
        except Exception as exc:  # noqa: BLE001
            log.exception("MELI %s crashed boat=%s", site_id, boat.slug)
            flash(
                f"Mercado Libre ({site_id}): error inesperado ({exc.__class__.__name__})",
                "error",
            )

    if not published_any:
        flash("No hay cuentas de Mercado Libre conectadas.", "warning")


def publish_to_instagram(boat) -> None:
    """Post a boat to Instagram. Flashes success/error message."""
    if not INSTAGRAM_ENABLED:
        flash("Instagram no está configurado (falta INSTAGRAM_ACCESS_TOKEN o INSTAGRAM_BUSINESS_ACCOUNT_ID).", "warning")
        return
    try:
        svc = InstagramService()
        media_id = svc.post_boat(boat)
        log.info("Instagram publish OK boat=%s media_id=%s", boat.slug, media_id)
        flash(f"'{boat.title}' publicado en Instagram (id: {media_id}).", "success")
    except InstagramError as exc:
        log.warning("Instagram publish error boat=%s: %s", boat.slug, exc)
        flash(f"Instagram: {exc}", "error")
    except ValueError as exc:
        log.warning("Instagram publish skipped boat=%s: %s", boat.slug, exc)
        flash(f"Instagram: {exc}", "error")
    except Exception as exc:  # noqa: BLE001
        log.exception("Instagram publish crashed boat=%s", boat.slug)
        flash(f"Instagram: error inesperado ({exc.__class__.__name__})", "error")


def publish_to_facebook(boat) -> None:
    """Post a boat to the Facebook page. Flashes success/error message."""
    if not FACEBOOK_ENABLED:
        flash("Facebook no está configurado (falta FACEBOOK_PAGE_ACCESS_TOKEN o FACEBOOK_PAGE_ID).", "warning")
        return
    try:
        svc = FacebookService()
        post_id = svc.post_boat(boat)
        log.info("Facebook publish OK boat=%s post_id=%s", boat.slug, post_id)
        flash(f"'{boat.title}' publicado en Facebook (id: {post_id}).", "success")
    except FacebookError as exc:
        log.warning("Facebook publish error boat=%s: %s", boat.slug, exc)
        flash(f"Facebook: {exc}", "error")
    except ValueError as exc:
        log.warning("Facebook publish skipped boat=%s: %s", boat.slug, exc)
        flash(f"Facebook: {exc}", "error")
    except Exception as exc:  # noqa: BLE001
        log.exception("Facebook publish crashed boat=%s", boat.slug)
        flash(f"Facebook: error inesperado ({exc.__class__.__name__})", "error")


def publish_to_whatsapp(boat) -> None:
    """Sync a boat as a product in the WhatsApp Business Catalog.

    Idempotent: uses boat.slug as retailer_id, so repeated calls upsert
    the same product. Caller is responsible for db.session.commit().
    """
    if not WHATSAPP_ENABLED:
        flash("WhatsApp Catalog no está configurado (faltan WHATSAPP_CATALOG_ID o WHATSAPP_ACCESS_TOKEN).", "warning")
        return
    try:
        svc = WhatsAppService()
        retailer_id = svc.sync_boat(boat)
        boat.whatsapp_synced_at = datetime.utcnow()
        log.info("WhatsApp sync OK boat=%s retailer_id=%s", boat.slug, retailer_id)
        flash(f"'{boat.title}' sincronizado en WhatsApp Catalog ({retailer_id}).", "success")
    except WhatsAppError as exc:
        log.warning("WhatsApp sync error boat=%s: %s", boat.slug, exc)
        flash(f"WhatsApp: {exc}", "error")
    except ValueError as exc:
        log.warning("WhatsApp sync skipped boat=%s: %s", boat.slug, exc)
        flash(f"WhatsApp: {exc}", "error")
    except Exception as exc:  # noqa: BLE001
        log.exception("WhatsApp sync crashed boat=%s", boat.slug)
        flash(f"WhatsApp: error inesperado ({exc.__class__.__name__})", "error")


def publish_to_youtube(boat) -> None:
    """Sync title + description on the boat's YouTube video.

    Requires boat.youtube_video_id to be set (video must be uploaded manually first).
    Caller is responsible for db.session.commit().
    """
    if not YOUTUBE_ENABLED:
        flash("YouTube no está configurado (faltan credenciales OAuth).", "warning")
        return
    try:
        svc = YouTubeService()
        video_id = svc.update_boat(boat)
        boat.youtube_synced_at = datetime.utcnow()
        log.info("YouTube sync OK boat=%s video_id=%s", boat.slug, video_id)
        flash(f"'{boat.title}' sincronizado en YouTube (video: {video_id}).", "success")
    except YouTubeError as exc:
        log.warning("YouTube sync error boat=%s: %s", boat.slug, exc)
        flash(f"YouTube: {exc}", "error")
    except ValueError as exc:
        log.warning("YouTube sync skipped boat=%s: %s", boat.slug, exc)
        flash(f"YouTube: {exc}", "error")
    except Exception as exc:  # noqa: BLE001
        log.exception("YouTube sync crashed boat=%s", boat.slug)
        flash(f"YouTube: error inesperado ({exc.__class__.__name__})", "error")
