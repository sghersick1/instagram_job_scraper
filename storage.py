"""Storage + Deduplication — writes to Google Sheets, falls back to CSV."""

import csv
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import gspread
from google.oauth2.service_account import Credentials

import config

SHEET_COLUMNS = [
    "company",
    "category",
    "title",
    "Age",
    "location",
    "link_url",
    "summary",
    "source_account",
    "captured_at",
]

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ---------------------------------------------------------------------------
# URL normalization for deduplication
# ---------------------------------------------------------------------------

def _base_url(url: str) -> str:
    """Strip query params and fragment so tracking params don't break dedup.
    e.g. https://app.ripplematch.com/job/123?tl=abc → app.ripplematch.com/job/123
    """
    try:
        p = urlparse(url.strip())
        return (p.netloc + p.path).rstrip("/").lower()
    except Exception:
        return url.strip().lower()


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
    """Write the header row in place — never insert, to avoid corrupting existing data."""
    first_row = sheet.row_values(1)
    if first_row != SHEET_COLUMNS:
        sheet.update("A1", [SHEET_COLUMNS])


def _load_existing_urls(sheet) -> set[str]:
    """Return a set of normalised base URLs already in the sheet."""
    url_set: set[str] = set()
    all_rows = sheet.get_all_records()
    for row in all_rows:
        url = (row.get("link_url") or "").strip()
        if url:
            url_set.add(_base_url(url))
    return url_set


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


def _load_existing_urls_csv() -> set[str]:
    url_set: set[str] = set()
    csv_path = Path(config.CSV_FALLBACK_PATH)
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                url = (row.get("link_url") or "").strip()
                if url:
                    url_set.add(_base_url(url))
    return url_set


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save(records: list[dict]) -> None:
    """Write new (non-duplicate) records to Google Sheets, falling back to CSV."""
    if not records:
        return

    try:
        sheet = _get_sheet()
        _ensure_header(sheet)
        url_set = _load_existing_urls(sheet)

        new_count = 0
        for record in records:
            url = (record.get("link_url") or "").strip()
            base = _base_url(url) if url else ""

            if base and base in url_set:
                print(f"[storage] Skipping duplicate: {record.get('title') or url}")
                continue

            row = [str(record.get(col) or "") for col in SHEET_COLUMNS]
            sheet.append_row(row, value_input_option="USER_ENTERED")

            if base:
                url_set.add(base)

            new_count += 1
            print(f"[storage] Saved to Sheets: {record.get('title') or '(no title)'}")

        print(f"[storage] {new_count}/{len(records)} records written to Google Sheets.")

    except Exception as exc:
        print(f"[storage] Google Sheets unavailable ({exc}). Falling back to CSV.")
        url_set = _load_existing_urls_csv()

        for record in records:
            url = (record.get("link_url") or "").strip()
            base = _base_url(url) if url else ""
            if base and base in url_set:
                print(f"[storage] Skipping duplicate: {record.get('title') or url}")
                continue
            _write_csv(record)
            if base:
                url_set.add(base)
