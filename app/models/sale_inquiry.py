from datetime import datetime
from typing import Any, Optional

from app.factory import db
from app.models.enums import BoatType, InquiryStatus


class SaleInquiry(db.Model):
    """Lead from the 'Sell Your Boat' page (owner wants MG to broker their boat)."""

    __tablename__ = "sale_inquiries"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    boat_type = db.Column(db.Enum(BoatType, native_enum=False), nullable=False)
    message = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.Enum(InquiryStatus, native_enum=False),
        default=InquiryStatus.NEW,
        nullable=False,
        index=True,
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "boat_type": self.boat_type.value if self.boat_type else None,
            "message": self.message,
            "status": self.status.value if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
