"""Integration tests for admin inquiry and pending listing endpoints."""
import pytest

from app.models import (
    BoatInquiry,
    BoatType,
    InquiryStatus,
    ModerationStatus,
    PendingListing,
    ProductCondition,
    SaleInquiry,
)
from tests.factories import make_boat


def _make_sale_inquiry(**kwargs):
    defaults = dict(
        first_name="Juan", last_name="Pérez",
        email="juan@example.com", boat_type=BoatType.SAILBOAT,
    )
    defaults.update(kwargs)
    return SaleInquiry(**defaults)


def _make_pending_listing(**kwargs):
    defaults = dict(
        first_name="Carlos", last_name="López",
        email="carlos@example.com",
        condition=ProductCondition.USED,
        description="Accesorio náutico en buen estado.",
        moderation_status=ModerationStatus.PENDING,
    )
    defaults.update(kwargs)
    return PendingListing(**defaults)


# ── Sale Inquiries ─────────────────────────────────────────────────────────────

class TestAdminSaleInquiries:
    def test_list_returns_200(self, logged_in_admin):
        assert logged_in_admin.get("/admin/sale-inquiries").status_code == 200

    def test_list_requires_login(self, client):
        resp = client.get("/admin/sale-inquiries", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_list_shows_inquiry_email(self, db, logged_in_admin):
        db.session.add(_make_sale_inquiry(email="vendedor@example.com"))
        db.session.commit()
        resp = logged_in_admin.get("/admin/sale-inquiries")
        assert b"vendedor@example.com" in resp.data

    def test_filter_by_status_new(self, db, logged_in_admin):
        db.session.add(_make_sale_inquiry(email="new@example.com", status=InquiryStatus.NEW))
        db.session.add(_make_sale_inquiry(email="closed@example.com", status=InquiryStatus.CLOSED))
        db.session.commit()
        resp = logged_in_admin.get("/admin/sale-inquiries?status=new")
        assert b"new@example.com" in resp.data
        assert b"closed@example.com" not in resp.data

    def test_filter_by_status_closed(self, db, logged_in_admin):
        db.session.add(_make_sale_inquiry(email="contacted@example.com", status=InquiryStatus.CONTACTED))
        db.session.add(_make_sale_inquiry(email="cerrado@example.com", status=InquiryStatus.CLOSED))
        db.session.commit()
        resp = logged_in_admin.get("/admin/sale-inquiries?status=closed")
        assert b"cerrado@example.com" in resp.data
        assert b"contacted@example.com" not in resp.data

    def test_invalid_status_filter_shows_all(self, db, logged_in_admin):
        db.session.add(_make_sale_inquiry(email="cualquiera@example.com"))
        db.session.commit()
        resp = logged_in_admin.get("/admin/sale-inquiries?status=inventado")
        assert resp.status_code == 200
        assert b"cualquiera@example.com" in resp.data


# ── Boat Inquiries ─────────────────────────────────────────────────────────────

class TestAdminBoatInquiries:
    def test_list_returns_200(self, logged_in_admin):
        assert logged_in_admin.get("/admin/boat-inquiries").status_code == 200

    def test_list_requires_login(self, client):
        resp = client.get("/admin/boat-inquiries", follow_redirects=False)
        assert resp.status_code == 302

    def test_list_shows_inquiry(self, db, logged_in_admin, boat):
        inq = BoatInquiry(
            boat_id=boat.id, name="Ana García",
            email="ana@example.com", message="Me interesa el velero.",
        )
        db.session.add(inq)
        db.session.commit()
        resp = logged_in_admin.get("/admin/boat-inquiries")
        assert b"ana@example.com" in resp.data

    def test_list_empty_renders_ok(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/boat-inquiries")
        assert resp.status_code == 200


# ── Pending Listings ───────────────────────────────────────────────────────────

class TestAdminPendingListingsList:
    def test_list_returns_200(self, logged_in_admin):
        assert logged_in_admin.get("/admin/pending-listings").status_code == 200

    def test_list_requires_login(self, client):
        resp = client.get("/admin/pending-listings", follow_redirects=False)
        assert resp.status_code == 302

    def test_list_shows_pending_by_default(self, db, logged_in_admin):
        db.session.add(_make_pending_listing(email="pendiente@example.com"))
        db.session.commit()
        resp = logged_in_admin.get("/admin/pending-listings")
        assert b"pendiente@example.com" in resp.data

    def test_list_hides_approved_when_filter_is_pending(self, db, logged_in_admin):
        db.session.add(_make_pending_listing(
            email="aprobado@example.com",
            moderation_status=ModerationStatus.APPROVED,
        ))
        db.session.commit()
        resp = logged_in_admin.get("/admin/pending-listings")
        assert b"aprobado@example.com" not in resp.data

    def test_list_filter_by_approved(self, db, logged_in_admin):
        db.session.add(_make_pending_listing(
            email="aprobado2@example.com",
            moderation_status=ModerationStatus.APPROVED,
        ))
        db.session.add(_make_pending_listing(
            email="pendiente2@example.com",
            moderation_status=ModerationStatus.PENDING,
        ))
        db.session.commit()
        resp = logged_in_admin.get("/admin/pending-listings?status=approved")
        assert b"aprobado2@example.com" in resp.data
        assert b"pendiente2@example.com" not in resp.data


class TestAdminPendingListingsDetail:
    def test_detail_returns_200(self, db, logged_in_admin):
        listing = _make_pending_listing()
        db.session.add(listing)
        db.session.commit()
        resp = logged_in_admin.get(f"/admin/pending-listings/{listing.id}")
        assert resp.status_code == 200

    def test_detail_shows_listing_data(self, db, logged_in_admin):
        listing = _make_pending_listing(email="detalle@example.com", description="Producto especial")
        db.session.add(listing)
        db.session.commit()
        resp = logged_in_admin.get(f"/admin/pending-listings/{listing.id}")
        assert b"detalle@example.com" in resp.data

    def test_detail_not_found_redirects(self, logged_in_admin):
        resp = logged_in_admin.get("/admin/pending-listings/99999", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/pending-listings" in resp.headers["Location"]


class TestAdminPendingListingsModerate:
    def test_approve_changes_status(self, db, app, logged_in_admin):
        listing = _make_pending_listing()
        db.session.add(listing)
        db.session.commit()
        logged_in_admin.post(
            f"/admin/pending-listings/{listing.id}/moderate",
            data={"action": "approve"},
        )
        with app.app_context():
            updated = db.session.get(PendingListing, listing.id)
        assert updated.moderation_status == ModerationStatus.APPROVED

    def test_reject_changes_status(self, db, app, logged_in_admin):
        listing = _make_pending_listing()
        db.session.add(listing)
        db.session.commit()
        logged_in_admin.post(
            f"/admin/pending-listings/{listing.id}/moderate",
            data={"action": "reject"},
        )
        with app.app_context():
            updated = db.session.get(PendingListing, listing.id)
        assert updated.moderation_status == ModerationStatus.REJECTED

    def test_mark_published_changes_status(self, db, app, logged_in_admin):
        listing = _make_pending_listing()
        db.session.add(listing)
        db.session.commit()
        logged_in_admin.post(
            f"/admin/pending-listings/{listing.id}/moderate",
            data={"action": "mark_published"},
        )
        with app.app_context():
            updated = db.session.get(PendingListing, listing.id)
        assert updated.moderation_status == ModerationStatus.PUBLISHED

    def test_moderate_with_internal_notes(self, db, app, logged_in_admin):
        listing = _make_pending_listing()
        db.session.add(listing)
        db.session.commit()
        logged_in_admin.post(
            f"/admin/pending-listings/{listing.id}/moderate",
            data={"action": "approve", "internal_notes": "Revisado y aprobado."},
        )
        with app.app_context():
            updated = db.session.get(PendingListing, listing.id)
        assert updated.internal_notes == "Revisado y aprobado."
        assert updated.moderation_status == ModerationStatus.APPROVED

    def test_moderate_sets_reviewed_at(self, db, app, logged_in_admin):
        listing = _make_pending_listing()
        db.session.add(listing)
        db.session.commit()
        assert listing.reviewed_at is None
        logged_in_admin.post(
            f"/admin/pending-listings/{listing.id}/moderate",
            data={"action": "approve"},
        )
        with app.app_context():
            updated = db.session.get(PendingListing, listing.id)
        assert updated.reviewed_at is not None

    def test_moderate_invalid_action_redirects_to_detail(self, db, logged_in_admin):
        listing = _make_pending_listing()
        db.session.add(listing)
        db.session.commit()
        resp = logged_in_admin.post(
            f"/admin/pending-listings/{listing.id}/moderate",
            data={"action": "accion-invalida"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert str(listing.id) in resp.headers["Location"]

    def test_moderate_not_found_redirects(self, logged_in_admin):
        resp = logged_in_admin.post(
            "/admin/pending-listings/99999/moderate",
            data={"action": "approve"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/admin/pending-listings" in resp.headers["Location"]
