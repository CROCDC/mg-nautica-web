from typing import Any, Optional

from app.factory import db
from app.models.enums import BoatStatus, BoatType, Flag, HullMaterial
from app.models.listed_object import ListedObject


class Boat(ListedObject):
    __tablename__ = "boats"
    __mapper_args__ = {"polymorphic_identity": "boat"}

    id = db.Column(db.Integer, db.ForeignKey("listed_objects.id"), primary_key=True)

    boat_type = db.Column(db.Enum(BoatType, native_enum=False), nullable=False)
    flag = db.Column(db.Enum(Flag, native_enum=False), nullable=False)
    country_location = db.Column(db.String(80), nullable=True)
    city_location = db.Column(db.String(120), nullable=True)
    zone = db.Column(db.String(120), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    year = db.Column(db.Integer, nullable=True)
    shipyard = db.Column(db.String(120), nullable=True)
    model_name = db.Column(db.String(120), nullable=True)
    hull_material = db.Column(db.Enum(HullMaterial, native_enum=False), nullable=True)

    length_m = db.Column(db.Numeric(5, 2), nullable=True)
    beam_m = db.Column(db.Numeric(5, 2), nullable=True)
    draft_m = db.Column(db.Numeric(5, 2), nullable=True)
    displacement_t = db.Column(db.Numeric(6, 2), nullable=True)

    commission_pct = db.Column(db.Numeric(4, 2), nullable=True)
    commission_flat_usd = db.Column(db.Integer, nullable=True)

    status = db.Column(
        db.Enum(BoatStatus, native_enum=False),
        default=BoatStatus.AVAILABLE,
        nullable=False,
    )

    last_refit = db.Column(db.String(40), nullable=True)
    last_careening = db.Column(db.String(40), nullable=True)

    photos = db.relationship(
        "BoatPhoto",
        back_populates="boat",
        cascade="all, delete-orphan",
        order_by="BoatPhoto.position",
    )
    specs = db.relationship(
        "BoatSpecs",
        back_populates="boat",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def primary_photo_url(self) -> Optional[str]:
        for photo in self.photos:
            if photo.is_primary:
                return photo.url
        return self.photos[0].url if self.photos else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "boat_type": self.boat_type.value if self.boat_type else None,
            "flag": self.flag.value if self.flag else None,
            "country_location": self.country_location,
            "city_location": self.city_location,
            "zone": self.zone,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "year": self.year,
            "shipyard": self.shipyard,
            "model_name": self.model_name,
            "hull_material": self.hull_material.value if self.hull_material else None,
            "length_m": float(self.length_m) if self.length_m is not None else None,
            "beam_m": float(self.beam_m) if self.beam_m is not None else None,
            "draft_m": float(self.draft_m) if self.draft_m is not None else None,
            "displacement_t": (
                float(self.displacement_t) if self.displacement_t is not None else None
            ),
            "price_usd": self.price_usd,
            "previous_price_usd": self.previous_price_usd,
            "on_sale": self.on_sale,
            "commission_pct": (
                float(self.commission_pct) if self.commission_pct is not None else None
            ),
            "commission_flat_usd": self.commission_flat_usd,
            "status": self.status.value if self.status else None,
            "featured": self.featured,
            "last_refit": self.last_refit,
            "last_careening": self.last_careening,
            "primary_photo_url": self.primary_photo_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
