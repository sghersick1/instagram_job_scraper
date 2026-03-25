"""Story Capture Agent — fetches story frames via Instagram's mobile API."""

import pickle
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import json
import requests
import instaloader

import config

_USER_ID_CACHE_PATH = Path(__file__).parent / ".user_id_cache.json"


def _load_user_id_cache() -> dict:
    if _USER_ID_CACHE_PATH.exists():
        return json.loads(_USER_ID_CACHE_PATH.read_text())
    return {}


def _save_user_id_cache(cache: dict) -> None:
    _USER_ID_CACHE_PATH.write_text(json.dumps(cache))

_IG_APP_ID = "936619743392459"  # Instagram web app ID


@dataclass
class StoryFrame:
    account: str
    captured_at: str       # ISO-8601 UTC
    screenshot_path: str   # path to downloaded media file
    dom_text: str          # always empty; extractor OCRs the media file
    links: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Session loading
# ---------------------------------------------------------------------------

def _get_session() -> requests.Session:
    """Load the saved cookie jar and return a requests.Session ready for use."""
    session_path = Path(config.SESSION_FILE)
    if not session_path.exists():
        raise FileNotFoundError(
            f"No session at {config.SESSION_FILE}. Run `python setup_session.py` first."
        )

    session = requests.Session()
    with open(session_path, "rb") as f:
        session.cookies = pickle.load(f)

    csrf_list = [c.value for c in session.cookies if c.name == "csrftoken"]
    session.headers.update({
        "X-CSRFToken": csrf_list[0] if csrf_list else "",
        "X-IG-App-ID": _IG_APP_ID,
        "Referer": "https://www.instagram.com/",
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram/302.0"
        ),
    })
    return session


# ---------------------------------------------------------------------------
# Instagram API helpers
# ---------------------------------------------------------------------------

def _get_user_id(session: requests.Session, username: str) -> int:
    """Resolve a username to a numeric user ID, using a local cache to avoid repeat lookups."""
    cache = _load_user_id_cache()
    if username in cache:
        print(f"[scraper] user_id for @{username} loaded from cache: {cache[username]}")
        return cache[username]

    resp = session.get(
        f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
        timeout=30,
    )
    print(f"[scraper] user_id lookup status: {resp.status_code}")
    resp.raise_for_status()
    data = resp.json()
    user_id = int(data["data"]["user"]["id"])

    cache[username] = user_id
    _save_user_id_cache(cache)
    print(f"[scraper] user_id for @{username} cached: {user_id}")
    return user_id


def _fetch_story_items(session: requests.Session, user_id: int) -> list[dict]:
    """Fetch raw story items for a user via the mobile API."""
    resp = session.get(
        f"https://i.instagram.com/api/v1/feed/user/{user_id}/story/",
        timeout=30,
    )
    print(f"[scraper] stories fetch status: {resp.status_code}")
    if resp.status_code == 404:
        return []   # no active story
    resp.raise_for_status()
    data = resp.json()
    return data.get("reel", {}).get("items", []) or []


def _extract_link_from_item(item: dict) -> str | None:
    """Pull the link sticker destination URL from a raw story item dict.

    Structure: story_link_stickers[0]["story_link"]["display_url"]
    display_url is the clean destination (no l.instagram.com wrapper).
    """
    for sticker_wrap in item.get("story_link_stickers", []):
        story_link = sticker_wrap.get("story_link") or {}
        display_url = story_link.get("display_url", "").strip()
        if display_url:
            # display_url omits the scheme — add https:// if missing
            if not display_url.startswith("http"):
                display_url = "https://" + display_url
            return display_url
    return None


# ---------------------------------------------------------------------------
# Media download
# ---------------------------------------------------------------------------

def _download_media(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception as exc:
        print(f"[scraper] Media download failed: {exc}")
        return False


def _best_media_url(item: dict) -> str | None:
    """Return the best available image/thumbnail URL from a story item."""
    # Images
    candidates = item.get("image_versions2", {}).get("candidates", [])
    if candidates:
        return candidates[0]["url"]
    # Video thumbnail
    for v in item.get("video_versions", []):
        if v.get("url"):
            return v["url"]
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def capture_stories(log_path: str | None = None) -> list[StoryFrame]:
    """Fetch story frames for all TARGET_ACCOUNTS via Instagram's mobile API.

    If log_path is set, the raw API JSON for every story item is appended to that file.
    """
    session = _get_session()
    all_frames: list[StoryFrame] = []

    for account in config.TARGET_ACCOUNTS:
        print(f"[scraper] Fetching stories for @{account}...")
        account_dir = Path(config.SCREENSHOTS_DIR) / account
        account_dir.mkdir(parents=True, exist_ok=True)

        try:
            user_id = _get_user_id(session, account)
            print(f"[scraper] @{account} user_id={user_id}")

            items = _fetch_story_items(session, user_id)
            if not items:
                print(f"[scraper] No active stories for @{account}")
                continue

            print(f"[scraper] Found {len(items)} story item(s) for @{account}")

            if log_path:
                with open(log_path, "a", encoding="utf-8") as lf:
                    for item in items:
                        lf.write(json.dumps(item, indent=2) + "\n\n")
                print(f"[scraper] Raw JSON logged to {log_path}")

            for item in items:
                taken_at = item.get("taken_at", 0)
                ts = datetime.fromtimestamp(taken_at, tz=timezone.utc)
                ts_str = ts.strftime("%Y%m%dT%H%M%SZ")
                media_path = account_dir / f"{ts_str}_{item.get('pk', 'unknown')}.jpg"

                media_url = _best_media_url(item)
                if not media_url or not _download_media(media_url, media_path):
                    print(f"[scraper] Skipping item {ts_str} — no media URL")
                    continue

                link = _extract_link_from_item(item)
                links = [link] if link else []

                frame = StoryFrame(
                    account=account,
                    captured_at=ts.isoformat(),
                    screenshot_path=str(media_path),
                    dom_text="",
                    links=links,
                )
                all_frames.append(frame)
                print(f"[scraper] @{account} | {ts_str} | link: {links[0] if links else 'none'}")

        except Exception as exc:
            print(f"[scraper] Error fetching @{account}: {exc}")
            traceback.print_exc()

    print(f"[scraper] Total frames: {len(all_frames)}")
    return all_frames
