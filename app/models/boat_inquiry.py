from datetime import datetime
from typing import Any

from app.factory import db
from app.models.enums import InquiryChannel


class BoatInquiry(db.Model):
    """Lead from a specific boat detail page (buyer interested in one unit)."""

    __tablename__ = "boat_inquiries"

    id = db.Column(db.Integer, primary_key=True)
    boat_id = db.Column(
        db.Integer, db.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    message = db.Column(db.Text, nullable=True)
    channel = db.Column(
        db.Enum(InquiryChannel, native_enum=False),
        default=InquiryChannel.FORM,
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    boat = db.relationship("Boat")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "boat_id": self.boat_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "message": self.message,
            "channel": self.channel.value if self.channel else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
