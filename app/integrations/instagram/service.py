import os

import requests

INSTAGRAM_ENABLED = bool(
    os.getenv("INSTAGRAM_ACCESS_TOKEN") and os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
)
_API_BASE = "https://graph.facebook.com/v19.0"
_HASHTAGS = "#nautica #barcos #veleros #yachts #mgNautica #embarcaciones #venta"
_CAROUSEL_MAX = 10


class InstagramError(Exception):
    pass


class InstagramService:
    def __init__(self) -> None:
        self.access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        self.account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

    def post_boat(self, boat) -> str:
        """Publish a boat to Instagram. Returns the published media ID."""
        if not self.access_token or not self.account_id:
            raise InstagramError(
                "Instagram no está configurado: falta INSTAGRAM_ACCESS_TOKEN o INSTAGRAM_BUSINESS_ACCOUNT_ID"
            )

        photos = [p for p in boat.photos if p.url]
        if not photos:
            raise InstagramError(
                f"'{boat.title}' no tiene fotos para publicar en Instagram"
            )

        caption = self._build_caption(boat)

        if len(photos) == 1:
            container_id = self._create_image_container(photos[0].url, caption)
        else:
            container_id = self._create_carousel_container(photos, caption)

        return self._publish_container(container_id)

    # ------------------------------------------------------------------

    def _build_caption(self, boat) -> str:
        lines = [f"🚢 {boat.title}"]

        details = []
        if boat.year:
            details.append(str(boat.year))
        if boat.length_m:
            details.append(f"{boat.length_m}m eslora")
        if details:
            lines.append(" · ".join(details))

        if boat.price_usd:
            lines.append(f"💰 US$ {boat.price_usd:,}")

        location = ", ".join(p for p in [boat.city_location, boat.country_location] if p)
        if location:
            lines.append(f"📍 {location}")

        if boat.description:
            desc = boat.description.strip()
            lines.append("")
            lines.append(desc[:400] + ("…" if len(desc) > 400 else ""))

        lines.append("")
        lines.append(_HASHTAGS)
        return "\n".join(lines)

    def _create_image_container(self, image_url: str, caption: str) -> str:
        resp = requests.post(
            f"{_API_BASE}/{self.account_id}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": self.access_token,
            },
            timeout=30,
        )
        data = resp.json()
        if not resp.ok or "id" not in data:
            raise InstagramError(
                f"Error al crear el container en Instagram: {data.get('error', {}).get('message', data)}"
            )
        return data["id"]

    def _create_carousel_container(self, photos, caption: str) -> str:
        child_ids = [
            self._create_carousel_child(photo.url)
            for photo in photos[:_CAROUSEL_MAX]
        ]
        resp = requests.post(
            f"{_API_BASE}/{self.account_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
                "access_token": self.access_token,
            },
            timeout=30,
        )
        data = resp.json()
        if not resp.ok or "id" not in data:
            raise InstagramError(
                f"Error al crear el carrusel en Instagram: {data.get('error', {}).get('message', data)}"
            )
        return data["id"]

    def _create_carousel_child(self, image_url: str) -> str:
        resp = requests.post(
            f"{_API_BASE}/{self.account_id}/media",
            params={
                "image_url": image_url,
                "is_carousel_item": "true",
                "access_token": self.access_token,
            },
            timeout=30,
        )
        data = resp.json()
        if not resp.ok or "id" not in data:
            raise InstagramError(
                f"Error al crear item de carrusel ({image_url}): {data.get('error', {}).get('message', data)}"
            )
        return data["id"]

    def _publish_container(self, container_id: str) -> str:
        resp = requests.post(
            f"{_API_BASE}/{self.account_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
            timeout=30,
        )
        data = resp.json()
        if not resp.ok or "id" not in data:
            raise InstagramError(
                f"Error al publicar en Instagram: {data.get('error', {}).get('message', data)}"
            )
        return data["id"]
