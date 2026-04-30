"""WhatsApp Business Catalog integration.

Uses Meta's Commerce Catalog API (same backend as Facebook Shops).
Each boat is synced as a product in the catalog using its slug as
retailer_id, which means we can upsert (create or update) idempotently.

API reference:
  https://developers.facebook.com/docs/marketing-api/catalog/reference/

The catalog must be linked to the WhatsApp Business account in
Meta Business Manager for products to appear in the WhatsApp chat.
"""
import os

import requests

from app.integrations.whatsapp.serializer import WhatsAppSerializer

WHATSAPP_ENABLED = bool(
    os.getenv("WHATSAPP_CATALOG_ID") and os.getenv("WHATSAPP_ACCESS_TOKEN")
)
_API_BASE = "https://graph.facebook.com/v21.0"


class WhatsAppError(Exception):
    pass


class WhatsAppService:
    def __init__(self) -> None:
        self.catalog_id = os.getenv("WHATSAPP_CATALOG_ID", "")
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")

    def sync_boat(self, boat) -> str:
        """Upsert a boat as a product in the WhatsApp catalog.

        Returns the retailer_id used (boat.slug-based).
        Uses Meta's batch endpoint with method=UPDATE which both creates
        and updates by retailer_id.
        """
        if not self.catalog_id or not self.access_token:
            raise WhatsAppError(
                "WhatsApp Catalog no está configurado: falta WHATSAPP_CATALOG_ID o WHATSAPP_ACCESS_TOKEN"
            )

        try:
            payload = WhatsAppSerializer(boat).to_payload()
        except ValueError as exc:
            raise WhatsAppError(str(exc)) from exc

        retailer_id = payload["retailer_id"]
        resp = requests.post(
            f"{_API_BASE}/{self.catalog_id}/items_batch",
            json={
                "access_token": self.access_token,
                "item_type": "PRODUCT_ITEM",
                "requests": [
                    {
                        "method": "UPDATE",
                        "data": payload,
                    }
                ],
            },
            timeout=30,
        )
        data = resp.json()
        if not resp.ok or "handles" not in data:
            raise WhatsAppError(
                f"Error al sincronizar producto {retailer_id}: {data.get('error', {}).get('message', data)}"
            )
        return retailer_id

    def list_publications(self, max_pages: int = 20) -> list[dict]:
        """List products in the WhatsApp catalog so they can be matched to boats.

        Returns a list of {retailer_id, product_id, name, url}.
        retailer_id matches the boat slug (the catalog is upserted by slug).
        """
        if not self.catalog_id or not self.access_token:
            raise WhatsAppError(
                "WhatsApp Catalog no está configurado: falta WHATSAPP_CATALOG_ID o WHATSAPP_ACCESS_TOKEN"
            )

        results: list[dict] = []
        url = f"{_API_BASE}/{self.catalog_id}/products"
        params = {
            "fields": "id,retailer_id,name,url",
            "limit": 100,
            "access_token": self.access_token,
        }
        for _ in range(max_pages):
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            if not resp.ok:
                raise WhatsAppError(
                    f"Error al listar productos del catálogo: {data.get('error', {}).get('message', data)}"
                )
            for entry in data.get("data", []):
                if not entry.get("retailer_id"):
                    continue
                results.append({
                    "retailer_id": entry["retailer_id"],
                    "product_id": entry.get("id", ""),
                    "name": entry.get("name", ""),
                    "url": entry.get("url", ""),
                })
            next_url = (data.get("paging") or {}).get("next")
            if not next_url:
                break
            url = next_url
            params = None
        return results

    def delete_boat(self, boat) -> None:
        """Remove a boat from the WhatsApp catalog (used when boat is sold/closed)."""
        if not self.catalog_id or not self.access_token:
            raise WhatsAppError(
                "WhatsApp Catalog no está configurado: falta WHATSAPP_CATALOG_ID o WHATSAPP_ACCESS_TOKEN"
            )

        retailer_id = WhatsAppSerializer(boat).retailer_id()
        resp = requests.post(
            f"{_API_BASE}/{self.catalog_id}/items_batch",
            json={
                "access_token": self.access_token,
                "item_type": "PRODUCT_ITEM",
                "requests": [
                    {
                        "method": "DELETE",
                        "data": {"retailer_id": retailer_id},
                    }
                ],
            },
            timeout=30,
        )
        data = resp.json()
        if not resp.ok:
            raise WhatsAppError(
                f"Error al eliminar producto {retailer_id}: {data.get('error', {}).get('message', data)}"
            )
