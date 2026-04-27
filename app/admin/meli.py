"""Admin routes for Mercado Libre integration.

URL layout:
  GET  /admin/meli/                                       → overview
  GET  /admin/meli/auth/<site_id>                         → start OAuth flow
  GET  /admin/meli/callback                               → OAuth callback
  POST /admin/meli/<site_id>/disconnect                   → remove credentials
  POST /admin/meli/boats/<boat_id>/publish/<site_id>      → first publish
  POST /admin/meli/boats/<boat_id>/update/<site_id>       → sync to MELI
  POST /admin/meli/boats/<boat_id>/pause/<site_id>        → pause
  POST /admin/meli/boats/<boat_id>/activate/<site_id>     → reactivate
  POST /admin/meli/boats/<boat_id>/close/<site_id>        → close permanently
  POST /admin/meli/boats/<boat_id>/sync/<site_id>         → refresh status
"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.admin import admin_bp
from app.factory import db
from app.integrations.mercadolibre import MeliOAuth, MeliService
from app.integrations.mercadolibre.client import MeliAPIError, MeliNotConfiguredError
from app.integrations.mercadolibre.service import SUPPORTED_SITES
from app.models.meli_credentials import MeliCredentials


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@admin_bp.route("/meli/")
@login_required
def meli_overview():
    from app.models import Boat

    creds = {s: MeliCredentials.query.filter_by(site_id=s).first() for s in SUPPORTED_SITES}
    boats = Boat.query.order_by(Boat.title).all()
    meli_info = {boat.id: MeliService.meli_info(boat) for boat in boats}

    return render_template(
        "admin/meli_overview.html",
        creds=creds,
        boats=boats,
        meli_info=meli_info,
        sites=SUPPORTED_SITES,
    )


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

@admin_bp.route("/meli/auth/<site_id>")
@login_required
def meli_auth(site_id: str):
    if site_id not in SUPPORTED_SITES:
        flash(f"Sitio desconocido: {site_id}", "error")
        return redirect(url_for("admin.meli_overview"))
    try:
        auth_url = MeliOAuth.authorization_url(site_id)
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("admin.meli_overview"))
    return redirect(auth_url)


@admin_bp.route("/meli/callback")
@login_required
def meli_callback():
    code = request.args.get("code")
    site_id = request.args.get("state")

    if not code or site_id not in SUPPORTED_SITES:
        flash("Callback inválido o estado no reconocido.", "error")
        return redirect(url_for("admin.meli_overview"))

    try:
        token_data = MeliOAuth.exchange_code(code)
        MeliOAuth.store_tokens(site_id, token_data)
        flash(f"Autenticación con {site_id} exitosa.", "success")
    except Exception as exc:
        flash(f"Error al intercambiar el código: {exc}", "error")

    return redirect(url_for("admin.meli_overview"))


@admin_bp.route("/meli/<site_id>/disconnect", methods=["POST"])
@login_required
def meli_disconnect(site_id: str):
    creds = MeliCredentials.query.filter_by(site_id=site_id).first()
    if creds:
        db.session.delete(creds)
        db.session.commit()
        flash(f"Credenciales de {site_id} eliminadas.", "success")
    return redirect(url_for("admin.meli_overview"))


# ---------------------------------------------------------------------------
# Per-boat actions
# ---------------------------------------------------------------------------

def _boat_or_404(boat_id: int):
    from app.models import Boat
    from flask import abort
    boat = db.session.get(Boat, boat_id)
    if boat is None:
        abort(404)
    return boat


def _meli_action(boat_id: int, site_id: str, action: str):
    if site_id not in SUPPORTED_SITES:
        flash(f"Sitio desconocido: {site_id}", "error")
        return redirect(url_for("admin.meli_overview"))

    boat = _boat_or_404(boat_id)
    svc = MeliService(site_id)

    try:
        if action == "publish":
            svc.publish(boat)
            db.session.commit()
            flash(f"'{boat.title}' publicado en {site_id}.", "success")
        elif action == "update":
            svc.update(boat)
            db.session.commit()
            flash(f"'{boat.title}' sincronizado en {site_id}.", "success")
        elif action == "pause":
            svc.pause(boat)
            db.session.commit()
            flash(f"Publicación de '{boat.title}' pausada en {site_id}.", "success")
        elif action == "activate":
            svc.activate(boat)
            db.session.commit()
            flash(f"Publicación de '{boat.title}' reactivada en {site_id}.", "success")
        elif action == "close":
            svc.close(boat)
            db.session.commit()
            flash(f"Publicación de '{boat.title}' cerrada en {site_id}.", "success")
        elif action == "sync":
            svc.sync_status(boat)
            db.session.commit()
            flash(f"Estado sincronizado desde {site_id}.", "success")
        else:
            flash(f"Acción desconocida: {action}", "error")
    except MeliNotConfiguredError as exc:
        flash(str(exc), "error")
    except MeliAPIError as exc:
        flash(f"Error de MELI ({exc.status_code}): {exc.message}", "error")
    except ValueError as exc:
        flash(str(exc), "error")

    return redirect(url_for("admin.meli_overview"))


@admin_bp.route("/meli/boats/<int:boat_id>/publish/<site_id>", methods=["POST"])
@login_required
def meli_publish(boat_id: int, site_id: str):
    return _meli_action(boat_id, site_id, "publish")


@admin_bp.route("/meli/boats/<int:boat_id>/update/<site_id>", methods=["POST"])
@login_required
def meli_update(boat_id: int, site_id: str):
    return _meli_action(boat_id, site_id, "update")


@admin_bp.route("/meli/boats/<int:boat_id>/pause/<site_id>", methods=["POST"])
@login_required
def meli_pause(boat_id: int, site_id: str):
    return _meli_action(boat_id, site_id, "pause")


@admin_bp.route("/meli/boats/<int:boat_id>/activate/<site_id>", methods=["POST"])
@login_required
def meli_activate(boat_id: int, site_id: str):
    return _meli_action(boat_id, site_id, "activate")


@admin_bp.route("/meli/boats/<int:boat_id>/close/<site_id>", methods=["POST"])
@login_required
def meli_close(boat_id: int, site_id: str):
    return _meli_action(boat_id, site_id, "close")


@admin_bp.route("/meli/boats/<int:boat_id>/sync/<site_id>", methods=["POST"])
@login_required
def meli_sync(boat_id: int, site_id: str):
    return _meli_action(boat_id, site_id, "sync")
