from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)


def _sign(secret: str, path: str, params: dict[str, Any]) -> str:
    """Create HMAC-SHA256 signature used by TikTok Shop Open API (approximation).
    Adjust if your app's signing rules differ (some endpoints require sorted query-string signing).
    """
    # Sort params lexicographically
    items = sorted((k, str(v)) for k, v in params.items() if v is not None)
    base = path + "".join(f"{k}{v}" for k, v in items)
    return hmac.new(secret.encode("utf-8"), base.encode("utf-8"), hashlib.sha256).hexdigest()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _post(base_url: str, path: str, payload: dict, headers: dict | None = None):
    url = f"{base_url.rstrip('/')}{path}"
    r = requests.post(url, json=payload, headers=headers or {}, timeout=45)
    r.raise_for_status()
    return r.json()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _get(base_url: str, path: str, params: dict, headers: dict | None = None):
    url = f"{base_url.rstrip('/')}{path}"
    r = requests.get(url, params=params, headers=headers or {}, timeout=45)
    r.raise_for_status()
    return r.json()

def _refresh_access_token(base_url: str, app_key: str, app_secret: str, refresh_token: str) -> dict:
    """Refresh access token; endpoint name may vary by app region/version.
    This uses a common pattern: /api/token/refresh or /token/refresh.
    """
    ts = int(time.time())
    path = "/api/token/refresh"
    payload = {
        "app_key": app_key,
        "refresh_token": refresh_token,
        "timestamp": ts,
    }
    sign = _sign(app_secret, path, payload)
    payload["sign"] = sign
    try:
        data = _post(base_url, path, payload)
        return data.get("data") or data
    except Exception as e:
        log.exception("TikTok token refresh failed: %s", e)
        raise

def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

def fetch_tiktok_daily(account: dict, date: dt.date) -> dict[str, float]:
    """Fetch gross sales and refunds for TikTok Shop for the given date.
    Assumes EUR amounts; if your shop has multiple currencies, convert upstream.
    account keys: name, base_url, app_key, app_secret, access_token, refresh_token, shop_id|seller_id
    """
    name = account["name"]
    base_url = account.get("base_url") or "https://open-api.tiktokglobalshop.com"
    app_key = account["app_key"]
    app_secret = account["app_secret"]
    access_token = account["access_token"]
    refresh_token = account["refresh_token"]
    shop_id = account.get("shop_id")
    seller_id = account.get("seller_id")

    start = dt.datetime(date.year, date.month, date.day, 0, 0, 0)
    end = start + dt.timedelta(days=1)

    out: dict[str, float | str] = {
        f"tiktok_{name}_umsatz_brutto_eur": "N/A",
        f"tiktok_{name}_retouren_eur": "N/A",
    }

    # Ensure token works; refresh if needed (best-effort)
    try:
        _ = _get(base_url, "/api/ping", {}, headers=_auth_headers(access_token))
    except Exception:
        try:
            data = _refresh_access_token(base_url, app_key, app_secret, refresh_token)
            access_token = data.get("access_token", access_token)
        except Exception:
            pass

    # 1) Sales: sum order totals for orders created yesterday
    try:
        params = {
            "create_time_from": int(start.timestamp()),
            "create_time_to": int(end.timestamp()),
        }
        if shop_id:
            params["shop_id"] = shop_id
        if seller_id:
            params["seller_id"] = seller_id
        # Endpoint path may vary; adjust to your app's spec (e.g., /api/orders/search)
        data = _get(base_url, "/api/orders/search", params, headers=_auth_headers(access_token))
        total = 0.0
        for o in data.get("data", {}).get("orders", []):
            amt = (o.get("order_amount") or {}).get("currency")
            val = (o.get("order_amount") or {}).get("total")
            # Assume EUR; ignore non-EUR or convert externally
            if amt in (None, "EUR"):
                try:
                    total += float(val or 0.0)
                except Exception:
                    pass
        out[f"tiktok_{name}_umsatz_brutto_eur"] = round(total, 2)
    except Exception as e:
        log.exception("TikTok sales fetch failed for %s: %s", name, e)

    # 2) Returns/Refunds: sum refund amounts posted yesterday
    try:
        params = {
            "update_time_from": int(start.timestamp()),
            "update_time_to": int(end.timestamp()),
        }
        if shop_id:
            params["shop_id"] = shop_id
        if seller_id:
            params["seller_id"] = seller_id
        # Endpoint path may vary; adjust to your app's spec (e.g., /api/refunds/search)
        data = _get(base_url, "/api/refunds/search", params, headers=_auth_headers(access_token))
        total_refunds = 0.0
        for r in data.get("data", {}).get("refunds", []):
            amt = (r.get("refund_amount") or {}).get("currency")
            val = (r.get("refund_amount") or {}).get("total")
            if amt in (None, "EUR"):
                try:
                    total_refunds += float(val or 0.0)
                except Exception:
                    pass
        out[f"tiktok_{name}_retouren_eur"] = round(abs(total_refunds), 2)
    except Exception as e:
        log.exception("TikTok refunds fetch failed for %s: %s", name, e)

    return out  # type: ignore[return-value]
