# Zero2Sudo Story Harvester

Automatically monitors Instagram story posts from CS opportunity accounts (e.g. `@zero2sudo`), extracts internship, co-op, hackathon, and new grad listings, and saves them as structured rows in Google Sheets.

Stories disappear after 24 hours. This tool captures them before they expire, pulls the link and job details out of each post, and keeps a permanent searchable record — no manual saving required.

---

## Running with Docker (recommended)

### First-time setup

**1. Clone the repo and copy the env file:**
```bash
git clone https://github.com/sghersick1/instagram_job_scraper.git
cd instagram_job_scraper
cp .env.example .env
```

**2. Fill in `.env`** with your credentials (see Environment Variables section below).
Use `GOOGLE_CREDENTIALS_JSON` (raw JSON string) — not the file path — for Docker compatibility:
```bash
# Get your service account JSON as a single line and paste into .env:
cat ~/keys/your_service_account.json | tr -d '\n'
```

**3. Save your Instagram session** (run locally — opens Firefox for manual login):
```bash
python setup_session.py
```

**4. Seed the user ID cache** (avoids Instagram rate limiting on first run):
```bash
python seed_user_id_cache.py
```

### Run

```bash
# Build and run once
docker compose up

# Run in the background
docker compose up -d

# View logs when running in background
docker compose logs -f
```

---

## Running without Docker (local development)

**1. Create a virtual environment** (use Linux filesystem if on WSL2):
```bash
python3 -m venv ~/venvs/insta_scraper
source ~/venvs/insta_scraper/bin/activate
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
playwright install firefox
sudo apt install -y tesseract-ocr   # Ubuntu/WSL2
# brew install tesseract            # macOS
```

**3. Copy and fill in `.env`:**
```bash
cp .env.example .env
```

**4. Save your Instagram session:**
```bash
python setup_session.py
```

**5. Run:**
```bash
python main.py
```

---

## Run commands (without Docker)

```bash
# Run once and exit
python main.py

# Run on a recurring schedule (interval set by SCRAPE_INTERVAL_MINUTES in .env)
python main.py --schedule

# Run once and log raw Instagram API JSON to logs/raw.json
python main.py --log

# Log to a custom file
python main.py --log myfile.json
```

---

## How it works

1. **Scraper** — calls Instagram's mobile API using your saved session to fetch active story items
2. **Filter** — drops any story with no link sticker (advice posts, text posts, etc.)
3. **Extractor** — OCRs the story image in memory (no disk writes) to extract visible text
4. **Normalizer** — sends the text + link to Claude, which returns structured fields
5. **Storage** — deduplicates by URL and writes to Google Sheets; falls back to `logs/output.csv`

---

## Session management

The scraper authenticates using a saved Instagram session. Run `setup_session.py` once locally to log in through a visible Firefox window. Re-run it whenever your session expires.

```bash
python setup_session.py
```

For cloud deployments, upload the generated `session.json` to a GCS bucket and set `GCS_BUCKET_NAME` in your `.env` — the container will fetch it automatically on startup.

```bash
gsutil cp session.json gs://your-bucket-name/session.json
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `INSTAGRAM_USERNAME` | Yes | Your Instagram username |
| `INSTAGRAM_PASSWORD` | Yes | Your Instagram password |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key — [console.anthropic.com](https://console.anthropic.com) |
| `GOOGLE_SHEET_ID` | Yes | Google Sheet ID (from the spreadsheet URL) |
| `GOOGLE_CREDENTIALS_JSON` | Yes* | Raw service account JSON string (recommended for Docker/cloud) |
| `GOOGLE_CREDENTIALS_JSON_PATH` | Yes* | Path to service account JSON file (local dev alternative) |
| `TARGET_ACCOUNTS` | No | Comma-separated Instagram accounts (default: `zero2sudo`) |
| `SCRAPE_INTERVAL_MINUTES` | No | Polling interval in schedule mode (default: `30`) |
| `GCS_BUCKET_NAME` | No | GCS bucket name for fetching `session.json` in cloud deployments |
| `GCS_SESSION_PATH` | No | Path to session file in the bucket (default: `session.json`) |

*Set one of `GOOGLE_CREDENTIALS_JSON` or `GOOGLE_CREDENTIALS_JSON_PATH`.

---

## Google Sheets setup

1. Create a Google Cloud project and enable the **Sheets** and **Drive** APIs
2. Create a **Service Account** and download the JSON key
3. Share your Google Sheet with the service account email (Editor access)
4. Copy the Sheet ID from the spreadsheet URL into `.env`

---

## Output schema

| Column | Description |
|---|---|
| `company` | Company or organization name |
| `category` | `internship` / `co-op` / `new_grad` / `hackathon` / `accelerator` / `info_session` / `other` |
| `title` | Opportunity title |
| `deadline` | Application deadline (YYYY-MM-DD) |
| `location` | Location or Remote |
| `link_url` | Direct link from the story sticker |
| `summary` | 1-2 sentence summary |
| `source_account` | Instagram username |
| `captured_at` | ISO-8601 UTC timestamp |

---

## Project structure

```
main.py                Entry point + CLI
config.py              Environment variable loading
scraper.py             Instagram API story fetcher
extractor.py           In-memory OCR text extraction
normalizer.py          Claude API normalization
storage.py             Google Sheets write + deduplication
scheduler.py           Pipeline orchestration + APScheduler
setup_session.py       One-time Instagram login session saver
seed_user_id_cache.py  Seed user ID cache to avoid rate limiting
fetch_session.py       Downloads session.json from GCS on container startup
Dockerfile             Container definition
docker-compose.yml     Local Docker run configuration
logs/                  output.csv fallback + raw.json debug logs
```

---

## Notes

- Stories expire after 24 hours — run on a schedule of 30 minutes or less
- Only stories with a link sticker are processed; advice and text posts are skipped
- Images are processed in memory — no screenshots are saved to disk
- If your session expires, re-run `setup_session.py` and re-upload to GCS if using cloud
