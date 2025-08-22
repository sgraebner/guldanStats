
from __future__ import annotations
import requests, datetime as dt
from typing import Dict, List
from tenacity import retry, stop_after_attempt, wait_exponential
from ..util.datewin import berlin_bounds_for_date

BASE_URL = "https://api.getmyinvoices.com/api/v2"

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _get(path: str, api_key: str, params=None):
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(f"{BASE_URL}{path}", headers=headers, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_gmi_bank_balances_eod(api_key: str, date: dt.date) -> Dict[str, float]:
    # 1) list accounts
    data = _get("/bank-accounts", api_key)
    accounts = data.get("data") or []
    # 2) for each account, get EoD balance for date
    out: Dict[str, float] = {}
    total = 0.0
    for acc in accounts:
        acc_id = acc.get("id")
        name = acc.get("name") or acc.get("iban") or acc_id
        # Hypothetical endpoint for balances history; adjust to actual GMI API if different.
        try:
            bal = _get(f"/bank-accounts/{acc_id}/balances", api_key, params={"date": date.isoformat()})
            amount = float(bal.get("data", {}).get("amount"))
            out[f"bank_{name}_kontostand_eur"] = round(amount, 2)
            total += amount
        except Exception:
            out[f"bank_{name}_kontostand_eur"] = "N/A"
    out["bank_gesamt_kontostand_eur"] = round(total, 2) if total else "N/A"
    return out
