import os

import requests

from app.integrations.publication import build_caption

FACEBOOK_ENABLED = bool(
    os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") and os.getenv("FACEBOOK_PAGE_ID")
)
_API_BASE = "https://graph.facebook.com/v21.0"
_HTTP_TIMEOUT = 60  # Allow up to 60s for staging photos with large URLs


class FacebookError(Exception):
    pass


class FacebookService:
    def __init__(self) -> None:
        self.access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
        self.page_id = os.getenv("FACEBOOK_PAGE_ID", "")

    def post_boat(self, boat) -> str:
        """Publish a boat to the Facebook page. Returns the post ID."""
        if not self.access_token or not self.page_id:
            raise FacebookError(
                "Facebook no está configurado: falta FACEBOOK_PAGE_ACCESS_TOKEN o FACEBOOK_PAGE_ID"
            )

        photos = [p for p in boat.photos if p.url and p.url.startswith("https://")]
        if not photos:
            raise FacebookError(
                f"'{boat.title}' no tiene fotos publicables en Facebook "
                "(las URLs deben ser HTTPS y accesibles públicamente)"
            )

        caption = build_caption(boat)

        if len(photos) == 1:
            return self._post_single_photo(photos[0].url, caption)
        else:
            return self._post_multi_photo(photos, caption)

    # ------------------------------------------------------------------

    def list_publications(self, max_pages: int = 20) -> list[dict]:
        """List recent posts on the page so they can be matched against boats.

        Returns a list of {post_id, message, permalink, created_time}.
        Paginates the page feed until exhaustion or `max_pages` is reached.
        """
        if not self.access_token or not self.page_id:
            raise FacebookError(
                "Facebook no está configurado: falta FACEBOOK_PAGE_ACCESS_TOKEN o FACEBOOK_PAGE_ID"
            )

        results: list[dict] = []
        url = f"{_API_BASE}/{self.page_id}/posts"
        params = {
            "fields": "id,message,permalink_url,created_time",
            "limit": 100,
            "access_token": self.access_token,
        }
        for _ in range(max_pages):
            resp = requests.get(url, params=params, timeout=_HTTP_TIMEOUT)
            data = resp.json()
            if not resp.ok:
                raise FacebookError(
                    f"Error al listar posts: {data.get('error', {}).get('message', data)}"
                )
            for entry in data.get("data", []):
                if not entry.get("message"):
                    continue
                results.append({
                    "post_id": entry["id"],
                    "message": entry["message"],
                    "permalink": entry.get("permalink_url", ""),
                    "created_time": entry.get("created_time", ""),
                })
            next_url = (data.get("paging") or {}).get("next")
            if not next_url:
                break
            url = next_url
            params = None  # next_url already contains all params
        return results

    def _post_single_photo(self, image_url: str, caption: str) -> str:
        resp = requests.post(
            f"{_API_BASE}/{self.page_id}/photos",
            params={
                "url": image_url,
                "message": caption,
                "published": "true",
                "access_token": self.access_token,
            },
            timeout=_HTTP_TIMEOUT,
        )
        data = resp.json()
        if not resp.ok or "id" not in data:
            raise FacebookError(
                f"Error al publicar foto en Facebook: {data.get('error', {}).get('message', data)}"
            )
        return data["id"]

    def _post_multi_photo(self, photos, caption: str) -> str:
        photo_ids = [self._stage_photo(p.url) for p in photos]
        attached = [{"media_fbid": pid} for pid in photo_ids]
        resp = requests.post(
            f"{_API_BASE}/{self.page_id}/feed",
            json={
                "message": caption,
                "attached_media": attached,
                "access_token": self.access_token,
            },
            timeout=_HTTP_TIMEOUT,
        )
        data = resp.json()
        if not resp.ok or "id" not in data:
            raise FacebookError(
                f"Error al publicar post en Facebook: {data.get('error', {}).get('message', data)}"
            )
        return data["id"]

    def _stage_photo(self, image_url: str) -> str:
        """Upload a photo as unpublished and return its ID."""
        resp = requests.post(
            f"{_API_BASE}/{self.page_id}/photos",
            params={
                "url": image_url,
                "published": "false",
                "access_token": self.access_token,
            },
            timeout=_HTTP_TIMEOUT,
        )
        data = resp.json()
        if not resp.ok or "id" not in data:
            raise FacebookError(
                f"Error al subir foto a Facebook ({image_url}): {data.get('error', {}).get('message', data)}"
            )
        return data["id"]
