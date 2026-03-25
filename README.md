# Zero2Sudo Story Harvester

Automatically monitors Instagram story posts from CS opportunity accounts (e.g. `@zero2sudo`), extracts internship and hackathon listings, and saves them as structured rows in Google Sheets.

Stories disappear after 24 hours. This tool captures them before they expire, pulls the link and job details out of each post, and keeps a permanent searchable record — no manual saving required.

---

## Quick start

```bash
# 1. Create a virtual environment (use Linux filesystem if on WSL2)
python3 -m venv ~/venvs/insta_scraper
source ~/venvs/insta_scraper/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
playwright install firefox

# 3. Install Tesseract (OCR)
sudo apt install -y tesseract-ocr        # Ubuntu/WSL2
# brew install tesseract                 # macOS

# 4. Copy .env.example to .env and fill in your credentials
cp .env.example .env

# 5. Save your Instagram session (opens Firefox — log in manually)
python setup_session.py

# 6. Run
python main.py
```

---

## Run commands

```bash
# Run once and exit
python main.py

# Run on a recurring schedule (set interval via SCRAPE_INTERVAL_MINUTES in .env)
python main.py --schedule

# Run once and log raw Instagram API JSON to logs/raw.json (useful for debugging)
python main.py --log

# Log to a custom file
python main.py --log myfile.json
```

---

## How it works

1. **Scraper** — calls Instagram's mobile API using your saved session to fetch active story items for each target account
2. **Filter** — drops any story with no link sticker (advice posts, text posts, etc.) — only internship and hackathon posts have links
3. **Extractor** — OCRs the downloaded story image to get visible text
4. **Normalizer** — sends the text + link to Claude, which returns structured fields (title, company, deadline, category, summary)
5. **Storage** — deduplicates and writes to Google Sheets; falls back to `logs/output.csv` if Sheets is unavailable

---

## First-time setup

### Instagram session

The scraper uses your Instagram account to read stories. Run `setup_session.py` once to log in through a visible Firefox window and save your session locally. Re-run it if your session expires.

```bash
python setup_session.py
```

If you add new accounts to `TARGET_ACCOUNTS`, seed the user ID cache to avoid rate limiting:

```bash
python seed_user_id_cache.py
```

### Google Sheets

1. Create a Google Cloud project and enable the **Sheets** and **Drive** APIs
2. Create a **Service Account** and download the JSON key
3. Share your Google Sheet with the service account email (Editor access)
4. Copy the Sheet ID from the URL and add it to `.env`

### Environment variables

Copy `.env.example` to `.env`:

| Variable | Description |
|---|---|
| `INSTAGRAM_USERNAME` | Your Instagram username |
| `INSTAGRAM_PASSWORD` | Your Instagram password |
| `ANTHROPIC_API_KEY` | Anthropic API key — [console.anthropic.com](https://console.anthropic.com) |
| `GOOGLE_SHEET_ID` | Google Sheet ID (from the spreadsheet URL) |
| `GOOGLE_CREDENTIALS_JSON_PATH` | Path to service account JSON key file |
| `GOOGLE_CREDENTIALS_JSON` | Raw JSON string alternative (useful in CI/Docker) |
| `TARGET_ACCOUNTS` | Comma-separated Instagram accounts, e.g. `zero2sudo` |
| `SCRAPE_INTERVAL_MINUTES` | Polling interval in schedule mode (default: `30`) |

---

## Output schema

Each captured opportunity produces one row in Google Sheets:

| Column | Description |
|---|---|
| `captured_at` | ISO-8601 UTC timestamp |
| `source_account` | Instagram username |
| `category` | `internship` or `hackathon` |
| `company_or_org` | Company or organization name |
| `title` | Opportunity title |
| `deadline` | Application deadline (YYYY-MM-DD) |
| `location` | Location or Remote |
| `link_url` | Direct link from the story sticker |
| `summary` | 1-2 sentence summary |

---

## Project structure

```
main.py                Entry point + CLI
config.py              Environment variable loading
scraper.py             Instagram API story fetcher
extractor.py           OCR text extraction from story images
normalizer.py          Claude API normalization
storage.py             Google Sheets write + deduplication
scheduler.py           Pipeline orchestration + APScheduler
setup_session.py       One-time Instagram login session saver
seed_user_id_cache.py  Seed user ID cache to avoid rate limiting
logs/                  output.csv fallback + raw.json debug logs
screenshots/           Downloaded story images (used for OCR)
```

---

## Notes

- Stories expire after 24 hours — run on a schedule of 30 minutes or less
- Only stories with a link sticker are processed; advice and text posts are automatically skipped
- If your session expires, re-run `setup_session.py`
- If Google Sheets is unavailable, records fall back to `logs/output.csv`
