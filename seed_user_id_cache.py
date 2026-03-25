"""Seed the user ID cache using instaloader's profile lookup (avoids rate-limited endpoint)."""

import pickle
import json
import instaloader
import config
from pathlib import Path

session_path = Path(config.SESSION_FILE)
L = instaloader.Instaloader(quiet=True, save_metadata=False)
with open(session_path, "rb") as f:
    L.context._session.cookies = pickle.load(f)
L.context._username = config.INSTAGRAM_USERNAME

cache = {}
for account in config.TARGET_ACCOUNTS:
    print(f"Looking up @{account}...")
    profile = instaloader.Profile.from_username(L.context, account)
    cache[account] = profile.userid
    print(f"  @{account} -> {profile.userid}")

cache_path = Path(__file__).parent / ".user_id_cache.json"
cache_path.write_text(json.dumps(cache))
print(f"\nSaved to {cache_path}")
