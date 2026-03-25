#!/bin/bash
set -e

echo "[startup] Fetching session.json from GCS..."
python fetch_session.py

echo "[startup] Starting scraper..."
exec python main.py "$@"
