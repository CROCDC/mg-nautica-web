from flask import render_template
from flask_login import login_required

from app.admin import admin_bp
from app.factory import db
from app.models import (
    Accessory,
    Boat,
    BoatInquiry,
    BoatStatus,
    ModerationStatus,
    PendingListing,
    SaleInquiry,
)


@admin_bp.route("/")
@login_required
def dashboard() -> str:
    stats = {
        "boats_total": db.session.query(Boat).count(),
        "boats_available": db.session.query(Boat)
        .filter_by(status=BoatStatus.AVAILABLE)
        .count(),
        "accessories_total": db.session.query(Accessory).count(),
        "pending_listings": db.session.query(PendingListing)
        .filter_by(moderation_status=ModerationStatus.PENDING)
        .count(),
        "sale_inquiries": db.session.query(SaleInquiry).count(),
        "boat_inquiries": db.session.query(BoatInquiry).count(),
    }
    return render_template("admin/dashboard.html", stats=stats)
