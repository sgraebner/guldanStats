
from __future__ import annotations
import json, os, datetime as dt, re
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import format_cell_range, CellFormat, Color
from typing import Dict, Any, List, Optional

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def _creds_from_env(service_account_json: str | None, service_account_file: str | None):
    if service_account_json:
        info = json.loads(service_account_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPE)
        return creds
    if service_account_file:
        creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPE)
        return creds
    raise RuntimeError("Google Service Account nicht konfiguriert. Setze GOOGLE_SERVICE_ACCOUNT_JSON oder GOOGLE_SERVICE_ACCOUNT_FILE.")

def get_sheet(spreadsheet_id: str, worksheet_title: str, service_account_json: str | None, service_account_file: str | None):
    creds = _creds_from_env(service_account_json, service_account_file)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(worksheet_title)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_title, rows=2000, cols=200)
    return sh, ws

def ensure_headers(ws, headers: List[str]):
    existing = ws.row_values(1)
    if existing == headers:
        return
    # Rewrite headers (row 1)
    ws.resize(rows=max(ws.row_count, 2), cols=max(len(headers), ws.col_count))
    ws.update([headers], "A1")
    # Freeze header row
    ws.freeze(rows=1)

def find_row_by_date(ws, date_str: str) -> Optional[int]:
    col1 = ws.col_values(1)
    for i, v in enumerate(col1, start=1):
        if v == date_str:
            return i
    return None

def write_row(ws, headers: List[str], date_str: str, row_data: Dict[str, Any]):
    # Find or append row
    row_idx = find_row_by_date(ws, date_str)
    if row_idx is None:
        # append
        existing_values = ws.get_all_values()
        row_idx = len(existing_values) + 1
        ws.update_cell(row_idx, 1, date_str)
    # write values
    for k, v in row_data.items():
        try:
            col_idx = headers.index(k) + 1
        except ValueError:
            continue
        ws.update_cell(row_idx, col_idx, v if v is not None else "N/A")
    return row_idx

def color_cell(ws, row: int, col: int, rgb: tuple | None):
    if rgb is None:
        return
    cf = CellFormat(backgroundColor=Color(red=rgb[0], green=rgb[1], blue=rgb[2]))
    a1 = gspread.utils.rowcol_to_a1(row, col)
    format_cell_range(ws, a1, cf)
