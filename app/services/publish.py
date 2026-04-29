"""Publish orchestrator: coordinates publishing a boat across platforms.

Supported platforms:
  - our_site   : set boat.status = AVAILABLE so it appears on the website
  - meli       : publish/sync to all connected Mercado Libre sites (MLU, MLA)
  - instagram  : post primary photo + caption to Instagram Business account
"""
import os

from flask import flash

from app.integrations.instagram.service import INSTAGRAM_ENABLED, InstagramError, InstagramService
from app.integrations.mercadolibre.client import MeliAPIError, MeliNotConfiguredError
from app.integrations.mercadolibre.service import SUPPORTED_SITES, MeliService
from app.models.meli_credentials import MeliCredentials


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
            flash(f"Mercado Libre ({site_id}): {exc}", "error")
        except MeliAPIError as exc:
            flash(f"Mercado Libre ({site_id}) error {exc.status_code}: {exc.message}", "error")
        except ValueError as exc:
            flash(f"Mercado Libre ({site_id}): {exc}", "error")

    if not published_any:
        flash("No hay cuentas de Mercado Libre conectadas.", "warning")


def publish_to_instagram(boat) -> None:
    """Post a boat to Instagram. Flashes success/error message.

    Requires INSTAGRAM_ENABLED=true and valid credentials in env vars.
    """
    if not INSTAGRAM_ENABLED:
        flash("Instagram no está configurado (falta INSTAGRAM_ACCESS_TOKEN o INSTAGRAM_BUSINESS_ACCOUNT_ID).", "warning")
        return
    try:
        svc = InstagramService()
        media_id = svc.post_boat(boat)
        flash(f"'{boat.title}' publicado en Instagram (id: {media_id}).", "success")
    except InstagramError as exc:
        flash(f"Instagram: {exc}", "error")
