"""Maps a Boat model instance to a WhatsApp Business Catalog product payload.

WhatsApp Catalog uses Meta's Commerce Catalog (same backend as Facebook Shops).
Fields follow the Meta Catalog product schema:
  https://developers.facebook.com/docs/marketing-api/catalog/reference/

Required fields per Meta:
  - retailer_id (unique merchant SKU; we use boat.slug)
  - name        (≤ 150 chars)
  - description (≤ 9999 chars)
  - price       (in cents, with currency)
  - currency    (ISO 4217)
  - image_url   (publicly reachable HTTPS URL)
  - availability (in stock | out of stock)
  - condition   (new | used | refurbished)
"""
from app.integrations.publication import build_body, build_title

_NAME_MAX = 150
_DESC_MAX = 9999


class WhatsAppSerializer:
    """Converts a Boat instance to a Meta Catalog product payload."""

    def __init__(self, boat) -> None:
        self.boat = boat

    def retailer_id(self) -> str:
        """Stable merchant SKU used to look up / update the product."""
        return f"boat-{self.boat.slug}"

    def to_payload(self) -> dict:
        boat = self.boat

        public_photos = [
            p for p in boat.photos if p.url and p.url.startswith("https://")
        ]
        primary = next((p for p in public_photos if p.is_primary), None) or (
            public_photos[0] if public_photos else None
        )
        if not primary:
            raise ValueError(
                f"'{boat.title}' no tiene fotos publicables en WhatsApp Catalog "
                "(las URLs deben ser HTTPS)"
            )

        name = build_title(boat)[:_NAME_MAX]
        description = build_body(boat)[:_DESC_MAX]

        payload = {
            "retailer_id": self.retailer_id(),
            "name": name,
            "description": description,
            "price": int(round(float(boat.price_usd) * 100)),  # Meta expects integer cents
            "currency": "USD",
            "image_url": primary.url,
            "availability": "in stock",
            "condition": "used",
            "url": _public_url(boat),
            "brand": boat.shipyard or "MG Náutica",
        }

        extra_images = [p.url for p in public_photos if p is not primary][:9]
        if extra_images:
            payload["additional_image_urls"] = extra_images

        return payload


def _public_url(boat) -> str:
    """Build the public website URL for the boat's listing page."""
    import os
    base = os.getenv("PUBLIC_SITE_URL", "https://mgnautica.com").rstrip("/")
    return f"{base}/boats/{boat.slug}"
