from datetime import datetime
from typing import Any

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin import admin_bp
from app.factory import db
from app.models import ModerationStatus, PendingListing


@admin_bp.route("/pending-listings")
@login_required
def listings_list() -> str:
    status_filter = request.args.get("status") or ModerationStatus.PENDING.value
    try:
        status_enum = ModerationStatus(status_filter)
    except ValueError:
        status_enum = ModerationStatus.PENDING
    listings = (
        db.session.query(PendingListing)
        .filter(PendingListing.moderation_status == status_enum)
        .order_by(PendingListing.created_at.desc())
        .all()
    )
    return render_template(
        "admin/listings_list.html",
        listings=listings,
        statuses=list(ModerationStatus),
        selected_status=status_enum,
    )


@admin_bp.route("/pending-listings/<int:listing_id>")
@login_required
def listings_detail(listing_id: int) -> Any:
    listing = db.session.get(PendingListing, listing_id)
    if listing is None:
        flash("Publicación no encontrada.", "error")
        return redirect(url_for("admin.listings_list"))
    return render_template("admin/listings_detail.html", listing=listing)


@admin_bp.route("/pending-listings/<int:listing_id>/moderate", methods=["POST"])
@login_required
def listings_moderate(listing_id: int) -> Any:
    listing = db.session.get(PendingListing, listing_id)
    if listing is None:
        flash("Publicación no encontrada.", "error")
        return redirect(url_for("admin.listings_list"))
    action = request.form.get("action")
    notes = request.form.get("internal_notes")
    if notes is not None:
        listing.internal_notes = notes
    if action == "approve":
        listing.moderation_status = ModerationStatus.APPROVED
    elif action == "reject":
        listing.moderation_status = ModerationStatus.REJECTED
    elif action == "mark_published":
        listing.moderation_status = ModerationStatus.PUBLISHED
    else:
        flash("Acción inválida.", "error")
        return redirect(url_for("admin.listings_detail", listing_id=listing.id))
    listing.reviewed_at = datetime.utcnow()
    listing.reviewed_by = current_user.email if current_user.is_authenticated else None
    db.session.commit()
    flash(f"Publicación marcada como {listing.moderation_status.value}.", "success")
    return redirect(url_for("admin.listings_detail", listing_id=listing.id))
