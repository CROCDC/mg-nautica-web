"""High-level operations for publishing boats on Mercado Libre.

MELI state is stored directly on the Boat model:
    boat.meli_{site}_item_id   — MELI item ID (e.g. "MLU1234567890")
    boat.meli_{site}_status    — MELI status: active | paused | closed | …
    boat.meli_{site}_permalink — public URL on MELI
    boat.meli_{site}_synced_at — last time we talked to the API

where {site} is 'mlu' or 'mla' (lowercase).

A single boat can be published independently on MLU and MLA.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from app.integrations.mercadolibre.auth import MeliOAuth
from app.integrations.mercadolibre.client import MeliClient, MeliAPIError
from app.integrations.mercadolibre.serializer import BoatSerializer

SUPPORTED_SITES = ("MLU", "MLA")


class MeliService:
    """Orchestrates MELI API calls for a given site."""

    def __init__(self, site_id: str):
        if site_id not in SUPPORTED_SITES:
            raise ValueError(f"Unsupported site_id {site_id!r}. Use 'MLU' or 'MLA'.")
        self.site_id = site_id
        self._prefix = site_id.lower()  # 'mlu' or 'mla'

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _client(self) -> MeliClient:
        token = MeliOAuth.get_valid_token(self.site_id)
        return MeliClient(access_token=token)

    def _get(self, boat, field: str) -> Any:
        return getattr(boat, f"meli_{self._prefix}_{field}", None)

    def _set(self, boat, **kwargs) -> None:
        for field, value in kwargs.items():
            setattr(boat, f"meli_{self._prefix}_{field}", value)
        setattr(boat, f"meli_{self._prefix}_synced_at", datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def publish(self, boat) -> None:
        """Publish a boat for the first time on this site.

        Sends the item and uploads its description. Updates boat fields in-place
        (caller must db.session.commit()).
        """
        serializer = BoatSerializer(boat, self.site_id)
        client = self._client()

        item = client.post("/items", json=serializer.to_payload())
        item_id = item["id"]

        try:
            client.post(
                f"/items/{item_id}/description",
                json=serializer.description_payload(),
            )
        except MeliAPIError:
            pass

        self._set(
            boat,
            item_id=item_id,
            status=item.get("status", "active"),
            permalink=item.get("permalink"),
        )

    def update(self, boat) -> None:
        """Sync title, price, photos and description to an existing listing."""
        item_id = self._get(boat, "item_id")
        if not item_id:
            raise ValueError(
                f"Boat {boat.id!r} has no listing on {self.site_id}. Publish first."
            )

        serializer = BoatSerializer(boat, self.site_id)
        client = self._client()

        client.put(f"/items/{item_id}", json=serializer.update_payload())
        try:
            client.put(
                f"/items/{item_id}/description",
                json=serializer.description_payload(),
            )
        except MeliAPIError:
            pass

        self._set(boat, item_id=item_id, status=self._get(boat, "status"))

    def pause(self, boat) -> None:
        """Pause the listing (private, can be reactivated)."""
        self._change_status(boat, "paused")

    def activate(self, boat) -> None:
        """Reactivate a paused listing."""
        self._change_status(boat, "active")

    def close(self, boat) -> None:
        """Close the listing permanently (can only be relisted, not reactivated)."""
        self._change_status(boat, "closed")

    def _change_status(self, boat, status: str) -> None:
        item_id = self._get(boat, "item_id")
        if not item_id:
            raise ValueError(
                f"Boat {boat.id!r} has no listing on {self.site_id}."
            )
        self._client().put(f"/items/{item_id}", json={"status": status})
        self._set(boat, item_id=item_id, status=status)

    def sync_status(self, boat) -> None:
        """Fetch current status from MELI and update boat fields."""
        item_id = self._get(boat, "item_id")
        if not item_id:
            raise ValueError(
                f"Boat {boat.id!r} has no listing on {self.site_id}."
            )
        item = self._client().get(f"/items/{item_id}")
        self._set(
            boat,
            item_id=item_id,
            status=item.get("status"),
            permalink=item.get("permalink", self._get(boat, "permalink")),
        )

    # ------------------------------------------------------------------
    # Read helpers (no API call)
    # ------------------------------------------------------------------

    @staticmethod
    def meli_info(boat) -> dict[str, Optional[dict]]:
        """Return {site_id: {item_id, status, permalink, synced_at}} for both sites.

        A site entry is None if the boat has never been published there.
        """
        result: dict[str, Optional[dict]] = {}
        for site in SUPPORTED_SITES:
            prefix = site.lower()
            item_id = getattr(boat, f"meli_{prefix}_item_id", None)
            if item_id:
                result[site] = {
                    "item_id": item_id,
                    "status": getattr(boat, f"meli_{prefix}_status", None),
                    "permalink": getattr(boat, f"meli_{prefix}_permalink", None),
                    "synced_at": getattr(boat, f"meli_{prefix}_synced_at", None),
                }
            else:
                result[site] = None
        return result
