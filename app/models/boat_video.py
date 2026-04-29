from typing import Any

from app.factory import db


class BoatVideo(db.Model):
    __tablename__ = "boat_videos"

    id = db.Column(db.Integer, primary_key=True)
    boat_id = db.Column(
        db.Integer, db.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url = db.Column(db.String(500), nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)

    boat = db.relationship("Boat", back_populates="videos")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "position": self.position,
        }
