
from __future__ import annotations
import datetime as dt
from typing import Dict, List
from sp_api.api import Orders, Finances
from sp_api.base import Marketplaces, SellingApiException
from tenacity import retry, stop_after_attempt, wait_exponential

REGION_TO_MARKETPLACE = {
    "eu": Marketplaces.DE,
    "na": Marketplaces.US,
    "fe": Marketplaces.AU
}

def _orders_client(region: str, refresh_token: str, lwa_client_id: str, lwa_client_secret: str, role_arn: str):
    mp = REGION_TO_MARKETPLACE.get(region, Marketplaces.DE)
    return Orders(
        refresh_token=refresh_token,
        lwa_app_id=lwa_client_id,
        lwa_client_secret=lwa_client_secret,
        role_arn=role_arn,
        marketplace=mp
    )

def _finances_client(region: str, refresh_token: str, lwa_client_id: str, lwa_client_secret: str, role_arn: str):
    mp = REGION_TO_MARKETPLACE.get(region, Marketplaces.DE)
    return Finances(
        refresh_token=refresh_token,
        lwa_app_id=lwa_client_id,
        lwa_client_secret=lwa_client_secret,
        role_arn=role_arn,
        marketplace=mp
    )

def fetch_amazon_daily(account: dict, date: dt.date) -> Dict[str, float]:
    name = account["name"]
    region = account["region"]
    refresh_token = account["refresh_token"]
    lwa_client_id = account["lwa_client_id"]
    lwa_client_secret = account["lwa_client_secret"]
    role_arn = account["role_arn"]
    start = dt.datetime(date.year, date.month, date.day, 0, 0, 0).isoformat()
    end = (dt.datetime(date.year, date.month, date.day) + dt.timedelta(days=1)).isoformat()

    key_sales = f"amazon_{name}_umsatz_brutto_eur"
    key_returns = f"amazon_{name}_retouren_eur"

    out = {key_sales: "N/A", key_returns: "N/A"}

    # Sales via Orders API (OrderTotal)
    try:
        orders_client = _orders_client(region, refresh_token, lwa_client_id, lwa_client_secret, role_arn)
        total_sales = 0.0
        token = None
        while True:
            resp = orders_client.get_orders(CreatedAfter=start, CreatedBefore=end, NextToken=token)
            for o in resp.payload.get("Orders", []):
                t = o.get("OrderTotal") or {}
                if t.get("CurrencyCode") == "EUR":
                    total_sales += float(t.get("Amount") or 0.0)
            token = resp.payload.get("NextToken")
            if not token:
                break
        out[key_sales] = round(total_sales, 2)
    except Exception:
        pass

    # Returns via Finances Refund Events (yesterday)
    try:
        finances_client = _finances_client(region, refresh_token, lwa_client_id, lwa_client_secret, role_arn)
        total_refunds = 0.0
        token = None
        while True:
            resp = finances_client.list_financial_events(
                PostedAfter=start, PostedBefore=end, NextToken=token
            )
            events = resp.payload.get("FinancialEvents", {})
            refund_events = events.get("RefundEventList") or []
            for e in refund_events:
                charge = e.get("RefundChargeList") or []
                for c in charge:
                    if c.get("ChargeAmount", {}).get("CurrencyCode") == "EUR":
                        total_refunds += float(c.get("ChargeAmount", {}).get("CurrencyAmount") or 0.0)
            token = resp.payload.get("NextToken")
            if not token:
                break
        out[key_returns] = round(abs(total_refunds), 2)
    except Exception:
        pass

    return out
