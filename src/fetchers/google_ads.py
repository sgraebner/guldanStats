from __future__ import annotations

import datetime as dt

from google.ads.googleads.client import GoogleAdsClient

GA_QUERY = '''
SELECT
  segments.date,
  metrics.cost_micros,
  metrics.conversions_value
FROM customer
WHERE segments.date BETWEEN '%(start)s' AND '%(end)s'
'''


def _client(dev_token, client_id, client_secret, refresh_token):
    config = {
        "developer_token": dev_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "login_customer_id": None,
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(config)


def fetch_google_ads_daily(
    dev_token: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    customer_ids: list[str],
    date: dt.date,
) -> dict[str, float]:
    out: dict[str, float | str] = {}
    if not dev_token or not client_id or not client_secret or not refresh_token or not customer_ids:
        return out
    client = _client(dev_token, client_id, client_secret, refresh_token)
    ga_service = client.get_service("GoogleAdsService")
    start = date.strftime("%Y-%m-%d")
    end = date.strftime("%Y-%m-%d")
    query = GA_QUERY % {"start": start, "end": end}
    for cid in customer_ids:
        try:
            resp = ga_service.search(customer_id=cid, query=query)
            cost_micros = 0
            conv_value = 0.0
            for row in resp:
                cost_micros += int(row.metrics.cost_micros or 0)
                conv_value += float(row.metrics.conversions_value or 0.0)
            out[f"google_ads_{cid}_ausgaben_eur"] = round(cost_micros / 1_000_000.0, 2)
            out[f"google_ads_{cid}_umsatz_eur"] = round(conv_value, 2)
        except Exception:
            out[f"google_ads_{cid}_ausgaben_eur"] = "N/A"
            out[f"google_ads_{cid}_umsatz_eur"] = "N/A"
    return out
