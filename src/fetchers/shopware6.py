from __future__ import annotations

import datetime as dt
import logging
from typing import Dict, List

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ..util.datewin import berlin_bounds_for_date


class Shopware6Client:
    def __init__(self, name: str, base_url: str, client_id: str, client_secret: str):
        self.name = name
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _auth(self):
        url = f"{self.base_url}/api/oauth/token"
        resp = requests.post(url, json={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }, timeout=30)
        resp.raise_for_status()
        self._token = resp.json()["access_token"]

    def _headers(self):
        if not self._token:
            self._auth()
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def list_sales_channels(self) -> list[dict]:
        url = f"{self.base_url}/api/sales-channel"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json().get("data", [])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def search_orders_sum(self, start_iso: str, end_iso: str, sales_channel_id: str) -> float:
        url = f"{self.base_url}/api/search/order"
        payload = {
            "filter": [
                {
                    "type": "range",
                    "field": "orderDateTime",
                    "parameters": {"gte": start_iso, "lt": end_iso},
                },
                {"type": "equals", "field": "salesChannelId", "value": sales_channel_id},
            ],
            "associations": {},
            "page": 1,
            "limit": 100,
        }
        total = 0.0
        while True:
            r = requests.post(url, headers=self._headers(), json=payload, timeout=45)
            r.raise_for_status()
            data = r.json()
            elements = data.get("data", [])
            for e in elements:
                price = e.get("attributes", {}).get("amountTotal")
                if price is not None:
                    total += float(price)
            if len(elements) < payload["limit"]:
                break
            payload["page"] += 1
        return total

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def search_credit_notes_sum(self, start_iso: str, end_iso: str, sales_channel_id: str) -> float:
        url_orders = f"{self.base_url}/api/search/order"
        payload = {
            "filter": [
                {
                    "type": "range",
                    "field": "orderDateTime",
                    "parameters": {"lt": end_iso},
                },  # include all up to end
                {"type": "equals", "field": "salesChannelId", "value": sales_channel_id},
            ],
            "associations": {},
            "page": 1,
            "limit": 100,
        }
        order_ids: list[str] = []
        while True:
            r = requests.post(url_orders, headers=self._headers(), json=payload, timeout=45)
            r.raise_for_status()
            data = r.json()
            elements = data.get("data", [])
            for e in elements:
                order_ids.append(e.get("id"))
            if len(elements) < payload["limit"]:
                break
            payload["page"] += 1

        if not order_ids:
            return 0.0

        total = 0.0
        url_docs = f"{self.base_url}/api/search/document"
        chunk_size = 100
        for i in range(0, len(order_ids), chunk_size):
            chunk = order_ids[i : i + chunk_size]
            payload_docs = {
                "filter": [
                    {
                        "type": "range",
                        "field": "createdAt",
                        "parameters": {"gte": start_iso, "lt": end_iso},
                    },
                    {"type": "equals", "field": "documentType.technicalName", "value": "credit_note"},
                    {"type": "equalsAny", "field": "orderId", "value": "|".join(chunk)},
                ],
                "associations": {},
                "page": 1,
                "limit": 100,
            }
            while True:
                r = requests.post(url_docs, headers=self._headers(), json=payload_docs, timeout=45)
                r.raise_for_status()
                data = r.json()
                elements = data.get("data", [])
                for d in elements:
                    attrs = d.get("attributes", {})
                    custom = attrs.get("customFields") or {}
                    val = custom.get("amountTotal") or custom.get("total") or 0.0
                    try:
                        total += float(val)
                    except Exception as e:
                        logging.getLogger(__name__).exception("Failed to accumulate credit note: %s", e)
                if len(elements) < payload_docs["limit"]:
                    break
                payload_docs["page"] += 1
        return total
