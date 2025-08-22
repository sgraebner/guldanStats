
# KPI Harvester – Tägliche Kennzahlen nach Google Sheets

Ein produktionsreifes, echtwelt-taugliches Python-Projekt, das täglich (über **Supervisor**) Daten abruft und in eine **Google Sheets**-Tabelle schreibt. Das Skript analysiert Abweichungen, markiert auffällige Werte farblich (grün bei > +35% über Norm, rot bei < −35% unter Norm) und verfasst deutschsprachige Kurznotizen mit **OpenAI (gpt-5-nano)**. Fehler und Auffälligkeiten können per E‑Mail gemeldet werden.

## Quellen
- **Shopware 6**: Bruttoumsatz (Bestelldatum), Retouren (Gutschriften) pro **Sales Channel** und Instanz
- **GetMyInvoices**: **Kontostände** gestern EoD je Bankkonto + Gesamtsumme
- **Google Ads**: **Ausgaben** & **Umsatz (Conversion Value)** je Konto
- **Amazon Seller Central (SP‑API)**: **Umsatz brutto** (Bestellungen gestern) & **Retouren** (Finances Refund Events) je **Region**
- **eBay**: **Umsatz** (Bestellungen gestern) je Account (**Retouren übersprungen**)

## Tabellenlayout (Deutsch)
**Tab-Name (Worksheet):** `Tägliche Kennzahlen`  
**Zeilen:** ein Datum pro Tag (YYYY-MM-DD)  
**Spalten (Beispiele, dynamisch je Konfiguration):**
- `datum`
- `shopware6_<instanz>_<saleschannel>_umsatz_brutto_eur`
- `shopware6_<instanz>_<saleschannel>_retouren_eur`
- `google_ads_<kunde>_ausgaben_eur`, `google_ads_<kunde>_umsatz_eur`
- `amazon_<region>_umsatz_brutto_eur`, `amazon_<region>_retouren_eur`
- `ebay_<account>_umsatz_brutto_eur`
- `bank_<konto>_kontostand_eur` (je Konto)
- `bank_gesamt_kontostand_eur`
- `notizen` (Kurzdiagnosen zu Auffälligkeiten in Deutsch, via OpenAI)

**Markierung:**  
- Wert **grün**, wenn > +35% über der Norm (Median aller bisherigen Tage, min. 14 Tage)  
- Wert **rot**, wenn < −35% unter der Norm

## Schnellstart

1) **Python 3.12** installieren.
2) Projekt entpacken und Abhängigkeiten installieren:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3) `.env` aus `.env.example` kopieren und anpassen:
   ```bash
   cp .env.example .env
   ```
   - **Wichtig (Google Sheets):** Service-Account E‑Mail aus der JSON in `.env` entnehmen und das Ziel-Spreadsheet für diese E‑Mail **freigeben**.
4) **Supervisor**-Konfiguration installieren:
   ```bash
   sudo cp deploy/supervisor-kpi-harvester.conf /etc/supervisor/conf.d/kpi-harvester.conf
   sudo supervisorctl reread
   sudo supervisorctl update
   sudo supervisorctl status
   ```
5) Logs prüfen:
   ```bash
   tail -f logs/app.log
   ```

## Zeitplan
- Standard: täglich um **03:30** (Europa/Berlin). Konfigurierbar über `.env` (`RUN_HOUR`, `RUN_MINUTE`).

## Backfill / Historische Daten
- Beim ersten Lauf werden standardmäßig die **letzten 90 Tage** pro Quelle abgefragt (`BACKFILL_DAYS`).  
- Norm-Berechnung erst ab **≥14** vorhandenen Tagen.

## Sicherheit & Secrets
- Alle Secrets via `.env` (oder Environment). **Niemals** committen.
- OpenAI wird nur zur **Formulierung** der Notizen verwendet; die numerische Anomalie-Erkennung bleibt deterministisch.

## Grenzen / Hinweise
- Endpunkte & Rechte der jeweiligen APIs müssen freigeschaltet sein (eBay Post-Order für Retouren wird nicht benötigt; Retouren dort sind deaktiviert).
- Shopware-**Retouren** werden hier als **Gutschriften (`credit_note`)** interpretiert. Je nach Setup (Plugins) ggf. anpassen.
- Google Ads Werte für „Gestern“ können **nachträglich** noch schwanken (Conversion-Lag).

## Support
- Bei Fehlern werden Felder mit `N/A` gefüllt und (optional) E‑Mail Alerts versendet.
