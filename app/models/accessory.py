from typing import Any

from app.factory import db
from app.models.enums import AccessoryCategory
from app.models.listed_object import ListedObject


class Accessory(ListedObject):
    __tablename__ = "accessories"
    __mapper_args__ = {"polymorphic_identity": "accessory"}

    id = db.Column(db.Integer, db.ForeignKey("listed_objects.id"), primary_key=True)

    category = db.Column(
        db.Enum(AccessoryCategory, native_enum=False), nullable=False, index=True
    )
    stock = db.Column(db.Integer, default=0, nullable=False)
    photo_url = db.Column(db.String(500), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "category": self.category.value if self.category else None,
            "price_usd": self.price_usd,
            "previous_price_usd": self.previous_price_usd,
            "on_sale": self.on_sale,
            "stock": self.stock,
            "photo_url": self.photo_url,
            "active": self.active,
        }
