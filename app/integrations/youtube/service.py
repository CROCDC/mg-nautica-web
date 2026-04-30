"""YouTube Data API v3 integration — metadata only.

This service does NOT upload videos. The workflow is:
  1. The video is uploaded manually to YouTube.
  2. The admin saves the resulting video_id on the boat.
  3. This service updates the video's title and description using the
     same shared title/body as Instagram/Facebook.

Auth: OAuth 2.0 with a long-lived refresh token. The access token is
exchanged on demand from the refresh token.
"""
import os

import requests

from app.integrations.publication import build_body, build_title

YOUTUBE_ENABLED = bool(
    os.getenv("YOUTUBE_CLIENT_ID")
    and os.getenv("YOUTUBE_CLIENT_SECRET")
    and os.getenv("YOUTUBE_REFRESH_TOKEN")
)
_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeError(Exception):
    pass


class YouTubeService:
    def __init__(self) -> None:
        self.client_id = os.getenv("YOUTUBE_CLIENT_ID", "")
        self.client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "")
        self.refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

    def update_boat(self, boat) -> str:
        """Update title and description of the boat's YouTube video.

        Requires boat.youtube_video_id to be set. Returns the video ID.
        """
        if not YOUTUBE_ENABLED:
            raise YouTubeError(
                "YouTube no está configurado: faltan YOUTUBE_CLIENT_ID, "
                "YOUTUBE_CLIENT_SECRET o YOUTUBE_REFRESH_TOKEN"
            )

        video_id = getattr(boat, "youtube_video_id", None)
        if not video_id:
            raise YouTubeError(
                f"'{boat.title}' no tiene youtube_video_id asociado. "
                "Subí el video manualmente y guardá el ID antes de sincronizar."
            )

        access_token = self._exchange_refresh_token()
        snippet = self._fetch_snippet(video_id, access_token)
        # categoryId is required by the YouTube API on PUT — preserve it from the
        # existing video. If for some reason it's missing, default to "26" (Howto).
        snippet.setdefault("categoryId", "26")
        snippet["title"] = build_title(boat)
        snippet["description"] = build_body(boat)

        resp = requests.put(
            f"{_API_BASE}/videos",
            params={"part": "snippet"},
            json={"id": video_id, "snippet": snippet},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if not resp.ok:
            raise YouTubeError(
                f"Error al actualizar video {video_id}: {resp.status_code} {resp.text}"
            )
        return video_id

    def list_publications(self, max_pages: int = 20) -> list[dict]:
        """List videos uploaded by the authenticated channel.

        Returns a list of {video_id, title, description, permalink}.
        Uses the channel's "uploads" playlist as the source.
        """
        if not YOUTUBE_ENABLED:
            raise YouTubeError(
                "YouTube no está configurado: faltan YOUTUBE_CLIENT_ID, "
                "YOUTUBE_CLIENT_SECRET o YOUTUBE_REFRESH_TOKEN"
            )

        access_token = self._exchange_refresh_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        ch_resp = requests.get(
            f"{_API_BASE}/channels",
            params={"part": "contentDetails", "mine": "true"},
            headers=headers,
            timeout=30,
        )
        ch_data = ch_resp.json()
        if not ch_resp.ok or not ch_data.get("items"):
            raise YouTubeError(f"No se pudo obtener el canal: {ch_data}")
        uploads_playlist = ch_data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        results: list[dict] = []
        page_token: str = ""
        for _ in range(max_pages):
            params: dict = {
                "part": "snippet",
                "playlistId": uploads_playlist,
                "maxResults": 50,
            }
            if page_token:
                params["pageToken"] = page_token
            resp = requests.get(
                f"{_API_BASE}/playlistItems",
                params=params,
                headers=headers,
                timeout=30,
            )
            data = resp.json()
            if not resp.ok:
                raise YouTubeError(f"Error al listar videos: {data}")
            for entry in data.get("items", []):
                snippet = entry.get("snippet", {})
                video_id = (snippet.get("resourceId") or {}).get("videoId")
                if not video_id:
                    continue
                results.append({
                    "video_id": video_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "permalink": f"https://www.youtube.com/watch?v={video_id}",
                })
            page_token = data.get("nextPageToken", "")
            if not page_token:
                break
        return results

    # ------------------------------------------------------------------

    def _exchange_refresh_token(self) -> str:
        resp = requests.post(
            _OAUTH_TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        data = resp.json()
        if not resp.ok or "access_token" not in data:
            raise YouTubeError(
                f"Error obteniendo access token de YouTube: {data}"
            )
        return data["access_token"]

    def _fetch_snippet(self, video_id: str, access_token: str) -> dict:
        """Fetch the existing snippet so we preserve categoryId, tags, etc."""
        resp = requests.get(
            f"{_API_BASE}/videos",
            params={"part": "snippet", "id": video_id},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        data = resp.json()
        if not resp.ok:
            raise YouTubeError(
                f"Error leyendo video {video_id}: {resp.status_code} {data}"
            )
        items = data.get("items", [])
        if not items:
            raise YouTubeError(
                f"Video {video_id} no encontrado en YouTube"
            )
        return items[0]["snippet"]
