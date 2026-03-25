"""Central config — load once, import everywhere."""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val


# Instagram credentials
INSTAGRAM_USERNAME: str = _require("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD: str = _require("INSTAGRAM_PASSWORD")

# Anthropic
ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")

# Google Sheets
GOOGLE_SHEET_ID: str = _require("GOOGLE_SHEET_ID")
# Raw JSON string takes precedence over file path
GOOGLE_CREDENTIALS_JSON: str | None = os.getenv("GOOGLE_CREDENTIALS_JSON")
GOOGLE_CREDENTIALS_JSON_PATH: str | None = os.getenv("GOOGLE_CREDENTIALS_JSON_PATH")
if not GOOGLE_CREDENTIALS_JSON and not GOOGLE_CREDENTIALS_JSON_PATH:
    raise EnvironmentError(
        "Set either GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_JSON_PATH"
    )

# Target accounts
_raw_accounts = os.getenv("TARGET_ACCOUNTS", "zero2sudo")
TARGET_ACCOUNTS: list[str] = [a.strip() for a in _raw_accounts.split(",") if a.strip()]

# Scheduler
SCRAPE_INTERVAL_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "30"))

# Filesystem
_BASE: str = os.path.dirname(__file__)
SCREENSHOTS_DIR: str = os.path.join(_BASE, "screenshots")
SESSION_FILE: str = os.path.join(_BASE, "session.json")
LOGS_DIR: str = os.path.join(_BASE, "logs")
CSV_FALLBACK_PATH: str = os.path.join(LOGS_DIR, "output.csv")
