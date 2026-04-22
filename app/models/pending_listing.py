from datetime import datetime
from typing import Any, Optional

from app.factory import db
from app.models.enums import ModerationStatus, ProductCondition


class PendingListing(db.Model):
    """Intake from the 'Publish Free' form — moderated manually before publishing."""

    __tablename__ = "pending_listings"

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), nullable=True)

    condition = db.Column(
        db.Enum(ProductCondition, native_enum=False), nullable=False
    )
    description = db.Column(db.Text, nullable=False)
    asked_price_usd = db.Column(db.Integer, nullable=True)
    file_urls = db.Column(db.JSON, nullable=True)

    moderation_status = db.Column(
        db.Enum(ModerationStatus, native_enum=False),
        default=ModerationStatus.PENDING,
        nullable=False,
        index=True,
    )
    internal_notes = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.String(120), nullable=True)

    published_boat_id = db.Column(
        db.Integer, db.ForeignKey("boats.id"), nullable=True
    )
    published_boat = db.relationship("Boat")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "condition": self.condition.value if self.condition else None,
            "description": self.description,
            "asked_price_usd": self.asked_price_usd,
            "file_urls": self.file_urls or [],
            "moderation_status": (
                self.moderation_status.value if self.moderation_status else None
            ),
            "published_boat_id": self.published_boat_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
