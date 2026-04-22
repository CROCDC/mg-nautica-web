from datetime import datetime

from app.factory import db


class ListedObject(db.Model):
    """Abstract base for everything sold on the platform (boats, accessories, etc.)."""

    __tablename__ = "listed_objects"
    __mapper_args__ = {
        "polymorphic_on": "object_type",
        "polymorphic_identity": "object",
    }

    id = db.Column(db.Integer, primary_key=True)
    object_type = db.Column(db.String(30), nullable=False)

    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")

    price_usd = db.Column(db.Integer, nullable=False)
    previous_price_usd = db.Column(db.Integer, nullable=True)
    on_sale = db.Column(db.Boolean, default=False, nullable=False)

    featured = db.Column(db.Boolean, default=False, nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
