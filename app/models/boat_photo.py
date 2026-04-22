from typing import Any

from app.factory import db


class BoatPhoto(db.Model):
    __tablename__ = "boat_photos"

    id = db.Column(db.Integer, primary_key=True)
    boat_id = db.Column(
        db.Integer, db.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url = db.Column(db.String(500), nullable=False)
    alt = db.Column(db.String(200), nullable=True)
    position = db.Column(db.Integer, default=0, nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)

    boat = db.relationship("Boat", back_populates="photos")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "alt": self.alt,
            "position": self.position,
            "is_primary": self.is_primary,
        }
