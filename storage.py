"""Storage + Deduplication — writes to Google Sheets, falls back to CSV."""

import csv
import json
import os
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

import config

SHEET_COLUMNS = [
    "captured_at",
    "source_account",
    "category",
    "company_or_org",
    "title",
    "deadline",
    "location",
    "link_url",
    "summary",
]

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ---------------------------------------------------------------------------
# Google Sheets helpers
# ---------------------------------------------------------------------------

def _get_sheet():
    if config.GOOGLE_CREDENTIALS_JSON:
        creds_dict = json.loads(config.GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            os.path.expanduser(config.GOOGLE_CREDENTIALS_JSON_PATH), scopes=_SCOPES
        )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(config.GOOGLE_SHEET_ID).sheet1
    return sheet


def _ensure_header(sheet) -> None:
    first_row = sheet.row_values(1)
    if first_row != SHEET_COLUMNS:
        sheet.insert_row(SHEET_COLUMNS, index=1)


def _load_existing_keys(sheet) -> tuple[set[str], set[tuple]]:
    """Return (url_set, (title, company, date) set) for deduplication."""
    url_set: set[str] = set()
    tcd_set: set[tuple] = set()

    all_rows = sheet.get_all_records()  # list of dicts, skip header
    for row in all_rows:
        url = (row.get("link_url") or "").strip()
        if url:
            url_set.add(url)

        title = (row.get("title") or "").strip().lower()
        company = (row.get("company_or_org") or "").strip().lower()
        date = (row.get("captured_at") or "")[:10]  # just YYYY-MM-DD
        if title and company:
            tcd_set.add((title, company, date))

    return url_set, tcd_set


# ---------------------------------------------------------------------------
# CSV fallback
# ---------------------------------------------------------------------------

def _write_csv(record: dict) -> None:
    path = Path(config.CSV_FALLBACK_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SHEET_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(record)
    print(f"[storage] Written to CSV fallback: {path}")


# ---------------------------------------------------------------------------
# Deduplication check
# ---------------------------------------------------------------------------

def _is_duplicate(
    record: dict,
    url_set: set[str],
    tcd_set: set[tuple],
) -> bool:
    url = (record.get("link_url") or "").strip()
    if url and url in url_set:
        return True

    title = (record.get("title") or "").strip().lower()
    company = (record.get("company_or_org") or "").strip().lower()
    date = (record.get("captured_at") or "")[:10]
    if title and company and (title, company, date) in tcd_set:
        return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save(records: list[dict]) -> None:
    """
    Write new (non-duplicate) records to Google Sheets.
    Falls back to CSV if Sheets is unavailable.
    """
    if not records:
        return

    try:
        sheet = _get_sheet()
        _ensure_header(sheet)
        url_set, tcd_set = _load_existing_keys(sheet)

        new_count = 0
        for record in records:
            if _is_duplicate(record, url_set, tcd_set):
                print(f"[storage] Skipping duplicate: {record.get('title') or record.get('link_url')}")
                continue

            row = [str(record.get(col) or "") for col in SHEET_COLUMNS]
            sheet.append_row(row, value_input_option="USER_ENTERED")

            # Update in-memory sets so subsequent records in this batch are checked too
            if record.get("link_url"):
                url_set.add(record["link_url"].strip())
            title = (record.get("title") or "").strip().lower()
            company = (record.get("company_or_org") or "").strip().lower()
            date = (record.get("captured_at") or "")[:10]
            if title and company:
                tcd_set.add((title, company, date))

            new_count += 1
            print(f"[storage] Saved to Sheets: {record.get('title') or '(no title)'}")

        print(f"[storage] {new_count}/{len(records)} records written to Google Sheets.")

    except Exception as exc:
        print(f"[storage] Google Sheets unavailable ({exc}). Falling back to CSV.")
        # Load existing CSV keys for deduplication
        url_set: set[str] = set()
        tcd_set: set[tuple] = set()
        csv_path = Path(config.CSV_FALLBACK_PATH)
        if csv_path.exists():
            with open(csv_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    url = (row.get("link_url") or "").strip()
                    if url:
                        url_set.add(url)
                    t = (row.get("title") or "").strip().lower()
                    c = (row.get("company_or_org") or "").strip().lower()
                    d = (row.get("captured_at") or "")[:10]
                    if t and c:
                        tcd_set.add((t, c, d))

        for record in records:
            if _is_duplicate(record, url_set, tcd_set):
                print(f"[storage] Skipping duplicate: {record.get('title') or record.get('link_url')}")
                continue
            _write_csv(record)
