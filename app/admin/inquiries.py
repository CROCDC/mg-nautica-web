from flask import render_template, request
from flask_login import login_required

from app.admin import admin_bp
from app.factory import db
from app.models import BoatInquiry, InquiryStatus, SaleInquiry


@admin_bp.route("/sale-inquiries")
@login_required
def sale_inquiries_list() -> str:
    status_filter = request.args.get("status")
    try:
        status_enum = InquiryStatus(status_filter) if status_filter else None
    except ValueError:
        status_enum = None
    query = db.session.query(SaleInquiry)
    if status_enum is not None:
        query = query.filter(SaleInquiry.status == status_enum)
    inquiries = query.order_by(SaleInquiry.created_at.desc()).all()
    return render_template(
        "admin/sale_inquiries_list.html",
        inquiries=inquiries,
        statuses=list(InquiryStatus),
        selected_status=status_enum,
    )


@admin_bp.route("/boat-inquiries")
@login_required
def boat_inquiries_list() -> str:
    inquiries = (
        db.session.query(BoatInquiry).order_by(BoatInquiry.created_at.desc()).all()
    )
    return render_template("admin/boat_inquiries_list.html", inquiries=inquiries)
