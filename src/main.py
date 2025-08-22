
from __future__ import annotations
import os, json, time, datetime as dt, traceback, logging
from dotenv import load_dotenv
from tzlocal import get_localzone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Settings
from .logger import setup_logger
from .sheets import get_sheet, ensure_headers, write_row, color_cell
from .anomaly import classify
from .notify import send_email
from .openai_notes import write_notes

from .fetchers.shopware6 import Shopware6Client, fetch_shopware_daily
from .fetchers.getmyinvoices import fetch_gmi_bank_balances_eod
from .fetchers.google_ads import fetch_google_ads_daily
from .fetchers.amazon import fetch_amazon_daily
from .fetchers.ebay import fetch_ebay_daily

log = setup_logger()

def build_headers(settings: Settings, dynamic_keys_example: dict) -> list[str]:
    base = ["datum"]
    # dynamic_keys_example holds all keys we plan to write
    base.extend(sorted(dynamic_keys_example.keys()))
    base.append("notizen")
    return base

def enumerate_dynamic_keys(settings: Settings) -> dict:
    dummy: dict = {}
    # Shopware Channels are dynamic -> cannot know names before first run; leave empty here.
    # Google Ads
    if settings.GOOGLE_ADS_CUSTOMER_IDS:
        for cid in [c.strip() for c in settings.GOOGLE_ADS_CUSTOMER_IDS.split(",") if c.strip()]:
            dummy[f"google_ads_{cid}_ausgaben_eur"] = ""
            dummy[f"google_ads_{cid}_umsatz_eur"] = ""
    # Amazon
    for acc in settings.AMAZON_ACCOUNTS:
        dummy[f"amazon_{acc.name}_umsatz_brutto_eur"] = ""
        dummy[f"amazon_{acc.name}_retouren_eur"] = ""
    # eBay
    for acc in settings.EBAY_ACCOUNTS:
        dummy[f"ebay_{acc.name}_umsatz_brutto_eur"] = ""
    # Banks are dynamic (names from API), add total column now:
    dummy["bank_gesamt_kontostand_eur"] = ""
    return dummy

def fetch_all_for_date(settings: Settings, target_date: dt.date, sh, ws) -> tuple[dict, list[tuple[str,int,int]]]:
    # returns row data dict and list of (column_key, row_idx, col_idx) for coloring after anomaly
    # 1) Shopware
    row: dict = {}
    color_targets = []

    for inst in settings.SHOPWARE6_INSTANCES:
        client = Shopware6Client(inst.name, inst.base_url, inst.client_id, inst.client_secret)
        try:
            sw = fetch_shopware_daily(client, target_date)
            row.update(sw)
        except Exception as e:
            log.exception("Shopware fetch failed for %s: %s", inst.name, e)

    # 2) GetMyInvoices
    try:
        if settings.GETMYINVOICES_API_KEY:
            gmi = fetch_gmi_bank_balances_eod(settings.GETMYINVOICES_API_KEY, target_date)
            row.update(gmi)
    except Exception as e:
        log.exception("GMI fetch failed: %s", e)

    # 3) Google Ads
    try:
        if settings.GOOGLE_ADS_DEVELOPER_TOKEN and settings.GOOGLE_ADS_CLIENT_ID and settings.GOOGLE_ADS_CLIENT_SECRET and settings.GOOGLE_ADS_REFRESH_TOKEN and settings.GOOGLE_ADS_CUSTOMER_IDS:
            ga = fetch_google_ads_daily(
                settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                settings.GOOGLE_ADS_CLIENT_ID,
                settings.GOOGLE_ADS_CLIENT_SECRET,
                settings.GOOGLE_ADS_REFRESH_TOKEN,
                [c.strip() for c in settings.GOOGLE_ADS_CUSTOMER_IDS.split(",") if c.strip()],
                target_date
            )
            row.update(ga)
    except Exception as e:
        log.exception("Google Ads fetch failed: %s", e)

    # 4) Amazon
    for acc in settings.AMAZON_ACCOUNTS:
        try:
            amz = fetch_amazon_daily(acc.model_dump(), target_date)
            row.update(amz)
        except Exception as e:
            log.exception("Amazon fetch failed for %s: %s", acc.name, e)

    # 5) eBay
    for acc in settings.EBAY_ACCOUNTS:
        try:
            eb = fetch_ebay_daily(acc.model_dump(), target_date)
            row.update(eb)
        except Exception as e:
            log.exception("eBay fetch failed for %s: %s", acc.name, e)

    return row, color_targets

def compute_history(ws, headers, col_key) -> list[float]:
    # read entire column (excluding header), parse to floats ignoring N/A
    import gspread
    col_idx = headers.index(col_key) + 1
    values = ws.col_values(col_idx)[1:]  # skip header
    hist = []
    for v in values:
        try:
            x = float(v)
        except:
            x = None
        hist.append(x)
    return hist

def job_run():
    load_dotenv(".env")
    settings = Settings()
    os.environ["TZ"] = settings.TZ
    try:
        import time
        time.tzset()
    except Exception:
        pass

    sh, ws = get_sheet(settings.GOOGLE_SPREADSHEET_ID, settings.GOOGLE_SHEET_TAB, settings.GOOGLE_SERVICE_ACCOUNT_JSON, settings.GOOGLE_SERVICE_ACCOUNT_FILE)
    # Determine date(s) to process: backfill if missing
    today = dt.datetime.now().date()
    # Yesterday range or backfill logic
    backfill_days = settings.BACKFILL_DAYS
    dates = [today - dt.timedelta(days=i+1) for i in range(backfill_days)][::-1]  # oldest -> newest

    # Build headers dynamically on first run; will extend later if new keys appear
    dynamic_keys = enumerate_dynamic_keys(settings)
    headers = ["datum"] + sorted(dynamic_keys.keys()) + ["notizen"]
    ensure_headers(ws, headers)

    anomalies_for_email = []
    for d in dates:
        date_str = d.isoformat()
        # Fetch
        row_values, _ = fetch_all_for_date(settings, d, sh, ws)

        # Extend headers if new keys (e.g., new Shopware channels, bank accounts) appeared
        new_keys = [k for k in row_values.keys() if k not in headers]
        if new_keys:
            headers = ["datum"] + sorted(list(set(headers[1:-1] + new_keys))) + ["notizen"]
            ensure_headers(ws, headers)

        # Write row
        row_index = write_row(ws, headers, date_str, row_values)

        # Anomaly detection (per numeric field)
        flagged = []
        for k, v in row_values.items():
            if k not in headers:  # if header updated later
                continue
            if k in ("datum", "notizen"):
                continue
            try:
                val = float(v)
            except:
                val = None
            hist = compute_history(ws, headers, k)[:-1]  # exclude the just-written value (we'll use prior history)
            flag, norm = classify(val, [x for x in hist])
            if flag != "none" and norm is not None:
                col_idx = headers.index(k) + 1
                # Color the cell now
                if flag == "green":
                    # green
                    from gspread_formatting import Color
                    from .sheets import color_cell
                    color_cell(ws, row_index, col_idx, (0.8, 0.94, 0.8))
                elif flag == "red":
                    color_cell(ws, row_index, col_idx, (0.98, 0.8, 0.8))
                flagged.append({"metric": k, "value": val, "norm": norm, "flag": flag})

        # Notes with OpenAI (German)
        note_text = ""
        if flagged:
            try:
                note_text = write_notes(settings.OPENAI_API_KEY, settings.OPENAI_MODEL, date_str, flagged)
                ws.update_cell(row_index, headers.index("notizen")+1, note_text)
            except Exception as e:
                log.exception("OpenAI notes failed: %s", e)

        if flagged:
            anomalies_for_email.append((date_str, flagged, note_text))

    # Email alert if anomalies or failures indicated as N/A
    if settings.ALERT_EMAIL_TO and settings.ALERT_EMAIL_FROM and settings.SMTP_HOST:
        try:
            body_lines = []
            for (date_str, fl, note) in anomalies_for_email:
                body_lines.append(f"[{date_str}] {len(fl)} Auffälligkeiten")
                if note:
                    body_lines.append(note)
            if body_lines:
                send_email(
                    smtp_host=settings.SMTP_HOST, smtp_port=settings.SMTP_PORT,
                    smtp_user=settings.SMTP_USER, smtp_password=settings.SMTP_PASSWORD, use_tls=settings.SMTP_USE_TLS,
                    from_addr=settings.ALERT_EMAIL_FROM, to_addr=settings.ALERT_EMAIL_TO,
                    subject="KPI-Harvester: Auffälligkeiten erkannt",
                    body="\n".join(body_lines)
                )
        except Exception as e:
            log.exception("Email alert failed: %s", e)

def run_forever():
    load_dotenv(".env")
    settings = Settings()
    os.environ["TZ"] = settings.TZ
    try:
        import time
        time.tzset()
    except Exception:
        pass

    scheduler = BackgroundScheduler(timezone=settings.TZ)
    trigger = CronTrigger(hour=settings.RUN_HOUR, minute=settings.RUN_MINUTE)
    scheduler.add_job(job_run, trigger)
    scheduler.start()
    log.info("KPI Harvester gestartet. Geplante Uhrzeit: %02d:%02d %s", settings.RUN_HOUR, settings.RUN_MINUTE, settings.TZ)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        scheduler.shutdown()

if __name__ == "__main__":
    run_forever()
