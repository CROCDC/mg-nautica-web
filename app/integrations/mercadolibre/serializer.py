"""Maps a Boat model instance to a Mercado Libre item payload.

Category IDs below are starting-point values based on URL pattern research.
Verify with GET /sites/{site}/categories before first publish, and update
CATEGORY_IDS if MELI reorganizes their taxonomy.

To look up real IDs:
    from app.integrations.mercadolibre.auth import MeliOAuth
    suggestions = MeliOAuth.predict_category("velero Bavaria 37", "MLU")
    # → [{"category_id": "MLU...", "category_name": "Veleros"}, ...]
"""
from typing import Any, Optional

from app.models.enums import BoatType

# Maps (site_id, boat_type) → MELI category_id.
# These should be verified/updated by running predict_category with real titles.
CATEGORY_IDS: dict[str, dict[str, str]] = {
    "MLU": {
        BoatType.SAILBOAT: "MLU109891",   # Veleros
        BoatType.MOTORBOAT: "MLU109890",  # Lanchas
        BoatType.CRUISER: "MLU109891",    # Cruceros → Veleros bucket
        BoatType.CATAMARAN: "MLU109891",  # Catamaranes → Veleros bucket
        BoatType.YACHT: "MLU109891",      # Yates → Veleros bucket
        BoatType.WHALER: "MLU109890",     # Balleneras → Lanchas bucket
        BoatType.OTHER: "MLU109890",
    },
    "MLA": {
        BoatType.SAILBOAT: "MLA430379",   # Embarcaciones a Vela
        BoatType.MOTORBOAT: "MLA430389",  # Lanchas
        BoatType.CRUISER: "MLA430379",
        BoatType.CATAMARAN: "MLA430379",
        BoatType.YACHT: "MLA430379",
        BoatType.WHALER: "MLA430389",
        BoatType.OTHER: "MLA430389",
    },
}

DEFAULT_LISTING_TYPE = "gold_special"


class BoatSerializer:
    """Converts a Boat instance to a MELI item payload."""

    def __init__(self, boat, site_id: str, listing_type: str = DEFAULT_LISTING_TYPE):
        self.boat = boat
        self.site_id = site_id
        self.listing_type = listing_type

    def category_id(self) -> str:
        site_map = CATEGORY_IDS.get(self.site_id, {})
        return site_map.get(self.boat.boat_type, "")

    def to_payload(self) -> dict[str, Any]:
        boat = self.boat
        payload: dict[str, Any] = {
            "title": boat.title,
            "category_id": self.category_id(),
            "price": float(boat.price_usd),
            "currency_id": "USD",
            "available_quantity": 1,
            "buying_mode": "buy_it_now",
            "listing_type_id": self.listing_type,
            "condition": "used",
        }

        photos = self._build_photos()
        if photos:
            payload["pictures"] = photos

        attributes = self._build_attributes()
        if attributes:
            payload["attributes"] = attributes

        return payload

    def description_payload(self) -> dict[str, str]:
        """Separate payload for POST /items/{id}/description."""
        return {"plain_text": self.boat.description or ""}

    def update_payload(self) -> dict[str, Any]:
        """Minimal PUT payload to sync price, title, and photos."""
        boat = self.boat
        payload: dict[str, Any] = {
            "title": boat.title,
            "price": float(boat.price_usd),
        }
        photos = self._build_photos()
        if photos:
            payload["pictures"] = photos
        return payload

    def _build_photos(self) -> list[dict[str, str]]:
        photos = []
        for photo in self.boat.photos:
            if photo.url:
                photos.append({"source": photo.url})
        return photos

    def _build_attributes(self) -> list[dict[str, Any]]:
        boat = self.boat
        attrs: list[dict[str, Any]] = []

        if boat.year:
            attrs.append({"id": "BOAT_YEAR", "value_name": str(boat.year)})

        if boat.shipyard:
            attrs.append({"id": "BRAND", "value_name": boat.shipyard})

        if boat.model_name:
            attrs.append({"id": "MODEL", "value_name": boat.model_name})

        if boat.length_m is not None:
            attrs.append({
                "id": "TOTAL_LENGTH",
                "value_name": str(float(boat.length_m)),
                "value_struct": {"number": float(boat.length_m), "unit": "m"},
            })

        if boat.beam_m is not None:
            attrs.append({
                "id": "BEAM",
                "value_name": str(float(boat.beam_m)),
                "value_struct": {"number": float(boat.beam_m), "unit": "m"},
            })

        if boat.draft_m is not None:
            attrs.append({
                "id": "DRAFT",
                "value_name": str(float(boat.draft_m)),
                "value_struct": {"number": float(boat.draft_m), "unit": "m"},
            })

        if boat.displacement_t is not None:
            attrs.append({
                "id": "DISPLACEMENT",
                "value_name": str(float(boat.displacement_t)),
                "value_struct": {"number": float(boat.displacement_t), "unit": "t"},
            })

        attrs.append({"id": "VEHICLE_CONDITION", "value_name": "Usado"})

        return attrs

    @classmethod
    def resolve_category(cls, title: str, site_id: str) -> Optional[str]:
        """Ask MELI's predictor for the best category for a given title.

        Returns the top category_id, or None if the predictor returns no results.
        """
        from app.integrations.mercadolibre.auth import MeliOAuth
        suggestions = MeliOAuth.predict_category(title, site_id)
        if suggestions:
            return suggestions[0].get("category_id")
        return None
