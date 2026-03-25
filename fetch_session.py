"""
Downloads session.json from a GCS bucket before the scraper runs.
Uses GOOGLE_CREDENTIALS_JSON and GCS_BUCKET_NAME env vars.
Skips silently if GCS_BUCKET_NAME is not set (e.g. local dev with a mounted session).
"""

import json
import os

from google.cloud import storage
from google.oauth2.service_account import Credentials

bucket_name = os.getenv("GCS_BUCKET_NAME")
if not bucket_name:
    print("[fetch_session] GCS_BUCKET_NAME not set — skipping GCS download.")
    raise SystemExit(0)

creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not creds_json:
    print("[fetch_session] GOOGLE_CREDENTIALS_JSON not set — cannot authenticate.")
    raise SystemExit(1)

creds = Credentials.from_service_account_info(
    json.loads(creds_json),
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

session_blob_path = os.getenv("GCS_SESSION_PATH", "session.json")
dest = os.path.join(os.path.dirname(__file__), "session.json")

client = storage.Client(credentials=creds)
bucket = client.bucket(bucket_name)
blob = bucket.blob(session_blob_path)
blob.download_to_filename(dest)

print(f"[fetch_session] Downloaded gs://{bucket_name}/{session_blob_path} -> {dest}")
