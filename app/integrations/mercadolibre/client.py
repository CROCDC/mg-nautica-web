"""Low-level HTTP client for the Mercado Libre REST API.

Responsibilities:
- Base URL management
- Authorization header injection
- Unified error handling (raises MeliAPIError with status + body)
- Simple retry on 429 (rate-limit) with exponential back-off
"""
import time
from typing import Any, Optional

import requests

BASE_URL = "https://api.mercadolibre.com"
_DEFAULT_TIMEOUT = 15  # seconds


class MeliAPIError(Exception):
    """Raised when the MELI API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str, body: Any = None):
        super().__init__(f"MELI {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.body = body


class MeliNotConfiguredError(Exception):
    """Raised when credentials for a site are missing from the database."""


class MeliClient:
    """Thin wrapper around requests for the MELI API.

    Usage:
        client = MeliClient(access_token="APP_USR-...")
        item = client.get("/items/MLU1234567890")
        new_item = client.post("/items", json=payload)
    """

    def __init__(self, access_token: Optional[str] = None):
        self._token = access_token
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _headers(self) -> dict:
        if not self._token:
            raise MeliNotConfiguredError("No access_token configured for this client.")
        return {"Authorization": f"Bearer {self._token}"}

    def _request(
        self,
        method: str,
        path: str,
        retries: int = 3,
        **kwargs,
    ) -> Any:
        url = f"{BASE_URL}{path}"
        kwargs.setdefault("timeout", _DEFAULT_TIMEOUT)

        for attempt in range(retries):
            resp = self._session.request(
                method,
                url,
                headers=self._headers(),
                **kwargs,
            )

            if resp.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue

            if resp.status_code == 204:
                return None

            try:
                body = resp.json()
            except Exception:
                body = resp.text

            if not resp.ok:
                message = (
                    body.get("message", resp.reason)
                    if isinstance(body, dict)
                    else str(body)
                )
                raise MeliAPIError(resp.status_code, message, body)

            return body

        raise MeliAPIError(429, "Rate limit exceeded after retries.")

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: Any = None) -> Any:
        return self._request("POST", path, json=json)

    def put(self, path: str, json: Any = None) -> Any:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)


def unauthenticated_get(path: str, params: Optional[dict] = None) -> Any:
    """Convenience for public endpoints that don't require auth (e.g. /sites, /categories)."""
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, params=params, timeout=_DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()
