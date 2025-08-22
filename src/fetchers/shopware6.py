
from __future__ import annotations
import requests, datetime as dt
from typing import Dict, List, Tuple, Optional
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
    def list_sales_channels(self) -> List[Dict]:
        url = f"{self.base_url}/api/sales-channel"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json().get("data", [])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def search_orders_sum(self, start_iso: str, end_iso: str, sales_channel_id: str) -> float:
        url = f"{self.base_url}/api/search/order"
        # Sum of amountTotal (gross), orders created in [start,end)
        payload = {
            "filter": [
                {"type":"range","field":"orderDateTime","parameters":{"gte": start_iso, "lt": end_iso}},
                {"type":"equals","field":"salesChannelId","value": sales_channel_id}
            ],
            "associations": {},
            "page": 1,
            "limit": 100
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
        # Approximation: sum of document type 'credit_note' created yesterday filtered by order's salesChannelId
        # We need to join via orderId; Shopware search API allows nested filter via associations isn't trivial.
        # Strategy: fetch relevant orders, then fetch documents per order.
        url_orders = f"{self.base_url}/api/search/order"
        payload = {
            "filter": [
                {"type":"range","field":"orderDateTime","parameters":{"lt": end_iso}},  # include all up to end
                {"type":"equals","field":"salesChannelId","value": sales_channel_id}
            ],
            "associations": {},
            "page": 1,
            "limit": 100
        }
        order_ids: List[str] = []
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
        # filter by createdAt in [start, end), by documentType.technicalName == 'credit_note' and orderId in order_ids
        # Shopware search supports "equalsAny" for ID arrays
        CHUNK = 100
        for i in range(0, len(order_ids), CHUNK):
            chunk = order_ids[i:i+CHUNK]
            payload_docs = {
                "filter": [
                    {"type":"range","field":"createdAt","parameters":{"gte": start_iso, "lt": end_iso}},
                    {"type":"equals","field":"documentType.technicalName","value":"credit_note"},
                    {"type":"equalsAny","field":"orderId","value":"|".join(chunk)}
                ],
                "associations": {},
                "page": 1,
                "limit": 100
            }
            while True:
                r = requests.post(url_docs, headers=self._headers(), json=payload_docs, timeout=45)
                r.raise_for_status()
                data = r.json()
                elements = data.get("data", [])
                for d in elements:
                    # document totals are not standardized; fallback: try config or custom fields
                    # If unavailable, count each credit note as amountTotal from referenced order line items is non-trivial.
                    # Here we sum 'documentReferencing' amount when present in custom fields 'amountTotal'.
                    attrs = d.get("attributes", {})
                    custom = attrs.get("customFields") or {}
                    val = custom.get("amountTotal") or custom.get("total") or 0.0
                    try:
                        total += float(val)
                    except:
                        pass
                if len(elements) < payload_docs["limit"]:
                    break
                payload_docs["page"] += 1
        return total

def fetch_shopware_daily(instance: Shopware6Client, date: dt.date) -> Dict[str, float]:
    start, end = berlin_bounds_for_date(date)
    start_iso = start.isoformat()
    end_iso = end.isoformat()
    out: Dict[str, float] = {}
    channels = instance.list_sales_channels()
    for ch in channels:
        ch_id = ch.get("id")
        ch_name = (ch.get("attributes", {}) or {}).get("name") or ch_id[:8]
        key_sales = f"shopware6_{instance.name}_{ch_name}_umsatz_brutto_eur"
        key_ret = f"shopware6_{instance.name}_{ch_name}_retouren_eur"
        try:
            sales = instance.search_orders_sum(start_iso, end_iso, ch_id)
        except Exception:
            sales = None
        try:
            returns = instance.search_credit_notes_sum(start_iso, end_iso, ch_id)
        except Exception:
            returns = None
        out[key_sales] = round(sales, 2) if sales is not None else "N/A"
        out[key_ret] = round(returns, 2) if returns is not None else "N/A"
    return out
