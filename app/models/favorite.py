from datetime import datetime
from typing import Any

from app.factory import db


class Favorite(db.Model):
    """Wishlist item tied to a browser session; works for any ListedObject."""

    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    listed_object_id = db.Column(
        db.Integer,
        db.ForeignKey("listed_objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = db.Column(db.String(80), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("listed_object_id", "session_id", name="uq_favorite_obj_session"),
    )

    listed_object = db.relationship("ListedObject")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "listed_object_id": self.listed_object_id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
