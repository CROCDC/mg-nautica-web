import os
import time

import requests

from app.integrations.publication import build_caption

INSTAGRAM_ENABLED = bool(
    os.getenv("INSTAGRAM_ACCESS_TOKEN") and os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
)
_API_BASE = "https://graph.facebook.com/v19.0"
_CAROUSEL_MAX = 10
_HTTP_TIMEOUT = 60  # IG can be slow on carousel containers
_STATUS_POLL_MAX = 10  # ~30s @ 3s each
_STATUS_POLL_DELAY = 3


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

        photos = [p for p in boat.photos if p.url and p.url.startswith("https://")]
        if not photos:
            raise InstagramError(
                f"'{boat.title}' no tiene fotos publicables en Instagram "
                "(las URLs deben ser HTTPS y accesibles públicamente)"
            )

        caption = build_caption(boat)

        if len(photos) == 1:
            container_id = self._create_image_container(photos[0].url, caption)
        else:
            container_id = self._create_carousel_container(photos, caption)

        # Wait for IG to finish processing the container before publishing.
        # Without this, carousel publish often fails with "Media ID is not available".
        self._wait_until_ready(container_id)
        return self._publish_container(container_id)

    def list_publications(self, max_pages: int = 20) -> list[dict]:
        """List recent media on the IG business account so they can be matched against boats.

        Returns a list of {post_id, caption, permalink, timestamp}.
        """
        if not self.access_token or not self.account_id:
            raise InstagramError(
                "Instagram no está configurado: falta INSTAGRAM_ACCESS_TOKEN o INSTAGRAM_BUSINESS_ACCOUNT_ID"
            )

        results: list[dict] = []
        url = f"{_API_BASE}/{self.account_id}/media"
        params = {
            "fields": "id,caption,permalink,timestamp",
            "limit": 100,
            "access_token": self.access_token,
        }
        for _ in range(max_pages):
            resp = requests.get(url, params=params, timeout=_HTTP_TIMEOUT)
            data = resp.json()
            if not resp.ok:
                raise InstagramError(
                    f"Error al listar media: {data.get('error', {}).get('message', data)}"
                )
            for entry in data.get("data", []):
                if not entry.get("caption"):
                    continue
                results.append({
                    "post_id": entry["id"],
                    "caption": entry["caption"],
                    "permalink": entry.get("permalink", ""),
                    "timestamp": entry.get("timestamp", ""),
                })
            next_url = (data.get("paging") or {}).get("next")
            if not next_url:
                break
            url = next_url
            params = None
        return results

    # ------------------------------------------------------------------

    def _create_image_container(self, image_url: str, caption: str) -> str:
        resp = requests.post(
            f"{_API_BASE}/{self.account_id}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": self.access_token,
            },
            timeout=_HTTP_TIMEOUT,
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
            timeout=_HTTP_TIMEOUT,
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
            timeout=_HTTP_TIMEOUT,
        )
        data = resp.json()
        if not resp.ok or "id" not in data:
            raise InstagramError(
                f"Error al crear item de carrusel ({image_url}): {data.get('error', {}).get('message', data)}"
            )
        return data["id"]

    def _wait_until_ready(self, container_id: str) -> None:
        """Poll the container's status_code until FINISHED or fail/timeout.

        Instagram processes uploads asynchronously. Publishing a container that
        is still in IN_PROGRESS state returns "Media ID is not available".
        """
        for _ in range(_STATUS_POLL_MAX):
            resp = requests.get(
                f"{_API_BASE}/{container_id}",
                params={"fields": "status_code", "access_token": self.access_token},
                timeout=_HTTP_TIMEOUT,
            )
            data = resp.json()
            status = data.get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(
                    f"Container {container_id} en estado {status}: {data.get('error', {}).get('message', data)}"
                )
            time.sleep(_STATUS_POLL_DELAY)
        raise InstagramError(
            f"Container {container_id} no quedó listo después de "
            f"{_STATUS_POLL_MAX * _STATUS_POLL_DELAY}s"
        )

    def _publish_container(self, container_id: str) -> str:
        resp = requests.post(
            f"{_API_BASE}/{self.account_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
            timeout=_HTTP_TIMEOUT,
        )
        data = resp.json()
        if not resp.ok or "id" not in data:
            raise InstagramError(
                f"Error al publicar en Instagram: {data.get('error', {}).get('message', data)}"
            )
        return data["id"]
