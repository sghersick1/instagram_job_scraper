"""
One-time setup: open Firefox for manual login, extract cookies,
inject them into an instaloader session, and save it.

Run this whenever your session expires:
    python setup_session.py
"""

import instaloader
import config
from playwright.sync_api import sync_playwright

print("Opening Firefox — log in to Instagram, then come back here and press Enter.")

with sync_playwright() as pw:
    browser = pw.firefox.launch(headless=False)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; rv:125.0) Gecko/20100101 Firefox/125.0"
    )
    page = context.new_page()
    page.goto("https://www.instagram.com/accounts/login/")

    input("\nPress Enter once you are fully logged in and can see your feed...")

    cookies = context.cookies()
    browser.close()

# Filter to Instagram cookies only
ig_cookies = [c for c in cookies if "instagram.com" in c["domain"]]
print(f"Extracted {len(ig_cookies)} Instagram cookies from browser.")

# Build instaloader session and inject cookies
L = instaloader.Instaloader(quiet=True, save_metadata=False)
for c in ig_cookies:
    L.context._session.cookies.set(c["name"], c["value"], domain=c["domain"])

# Set CSRF header (required by Instagram's API)
# Multiple csrftoken cookies may exist across subdomains — pick the first one
csrf_cookies = [c for c in ig_cookies if c["name"] == "csrftoken"]
csrf = csrf_cookies[0]["value"] if csrf_cookies else ""
L.context._session.headers.update({
    "X-CSRFToken": csrf,
    "Referer": "https://www.instagram.com/",
})

# Verify the session works
print("Verifying session with Instagram...")
username = L.test_login()
if not username:
    print("Authentication failed — cookies did not transfer correctly. Try logging in again.")
    exit(1)

print(f"Authenticated as: @{username}")

# save_session_to_file internally just pickles the cookie jar — do it directly
# to avoid the login-state check on the Instaloader wrapper.
import pickle
with open(config.SESSION_FILE, "wb") as f:
    pickle.dump(L.context._session.cookies, f)
print(f"Session saved to {config.SESSION_FILE}")
print(f"Session saved to {config.SESSION_FILE}")
