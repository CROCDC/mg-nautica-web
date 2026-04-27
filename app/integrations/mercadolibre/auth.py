"""OAuth 2.0 helpers for Mercado Libre (Authorization Code Grant).

Flow:
1. Admin visits /admin/meli/auth/<site_id>  → redirect to MELI authorization URL
2. MELI redirects to /admin/meli/callback?code=XXX&state=<site_id>
3. Exchange code for access_token + refresh_token via token endpoint
4. Persist tokens in MeliCredentials table
5. Every API call checks token expiry and refreshes automatically

Important: each refresh call returns a NEW refresh_token.
Always persist both tokens after a refresh.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import requests

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

AUTH_URLS = {
    "MLU": "https://auth.mercadolibre.com.uy/authorization",
    "MLA": "https://auth.mercadolibre.com.ar/authorization",
}

# Token validity: MELI issues 6-hour access tokens.
# We refresh 5 minutes early to avoid edge-case expiry mid-request.
_EXPIRY_BUFFER_SECONDS = 300


def _client_id() -> str:
    v = os.environ.get("MELI_CLIENT_ID", "")
    if not v:
        raise RuntimeError("MELI_CLIENT_ID environment variable is not set.")
    return v


def _client_secret() -> str:
    v = os.environ.get("MELI_CLIENT_SECRET", "")
    if not v:
        raise RuntimeError("MELI_CLIENT_SECRET environment variable is not set.")
    return v


def _redirect_uri() -> str:
    return os.environ.get("MELI_REDIRECT_URI", "")


class MeliOAuth:
    """Handles the OAuth lifecycle for a single MELI site (MLU or MLA)."""

    @staticmethod
    def authorization_url(site_id: str) -> str:
        """Build the URL the admin must visit to authorize the app."""
        base = AUTH_URLS.get(site_id)
        if not base:
            raise ValueError(f"Unknown site_id: {site_id!r}. Use 'MLU' or 'MLA'.")
        params = {
            "response_type": "code",
            "client_id": _client_id(),
            "redirect_uri": _redirect_uri(),
            "state": site_id,
        }
        return f"{base}?{urlencode(params)}"

    @staticmethod
    def exchange_code(code: str) -> dict:
        """Exchange an authorization code for access_token + refresh_token.

        Returns the raw MELI token response dict:
            {
                "access_token": "APP_USR-...",
                "token_type": "bearer",
                "expires_in": 21600,
                "scope": "...",
                "user_id": 123456789,
                "refresh_token": "TG-..."
            }
        """
        resp = requests.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "code": code,
            "redirect_uri": _redirect_uri(),
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def refresh(refresh_token: str) -> dict:
        """Exchange a refresh_token for a fresh pair of tokens.

        CRITICAL: The returned refresh_token is NEW. Persist it immediately
        or the old one is invalidated and the user must re-authorize.
        """
        resp = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "refresh_token": refresh_token,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def get_valid_token(site_id: str) -> str:
        """Return a valid access_token for the given site, refreshing if needed.

        Raises MeliNotConfiguredError if no credentials are stored.
        """
        from app.integrations.mercadolibre.client import MeliNotConfiguredError
        from app.models.meli_credentials import MeliCredentials
        from app.factory import db

        creds: Optional[MeliCredentials] = MeliCredentials.query.filter_by(
            site_id=site_id
        ).first()

        if creds is None:
            raise MeliNotConfiguredError(
                f"No hay credenciales configuradas para {site_id}. "
                "Autorizá la aplicación desde Admin → Mercado Libre → Configuración."
            )

        now = datetime.now(timezone.utc)
        expires_at = creds.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now >= expires_at - timedelta(seconds=_EXPIRY_BUFFER_SECONDS):
            token_data = MeliOAuth.refresh(creds.refresh_token)
            creds.access_token = token_data["access_token"]
            creds.refresh_token = token_data["refresh_token"]
            creds.expires_at = now + timedelta(seconds=token_data.get("expires_in", 21600))
            db.session.commit()

        return creds.access_token

    @staticmethod
    def store_tokens(site_id: str, token_data: dict) -> "MeliCredentials":
        """Persist (or update) credentials after a successful exchange or refresh."""
        from app.models.meli_credentials import MeliCredentials
        from app.factory import db

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=token_data.get("expires_in", 21600))

        creds = MeliCredentials.query.filter_by(site_id=site_id).first()
        if creds is None:
            creds = MeliCredentials(site_id=site_id)
            db.session.add(creds)

        creds.access_token = token_data["access_token"]
        creds.refresh_token = token_data["refresh_token"]
        creds.expires_at = expires_at
        creds.meli_user_id = str(token_data.get("user_id", ""))
        db.session.commit()
        return creds

    @staticmethod
    def predict_category(title: str, site_id: str) -> list[dict]:
        """Use MELI's category predictor to suggest a category_id for a given title.

        No auth required. Returns a list of suggestions with category_id and name.
        """
        from app.integrations.mercadolibre.client import unauthenticated_get
        return unauthenticated_get(
            f"/sites/{site_id}/domain_discovery/search",
            params={"q": title, "limit": 5},
        )
