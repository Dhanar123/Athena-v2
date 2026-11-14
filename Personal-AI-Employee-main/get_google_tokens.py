import os
import pickle
import re
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
]

print("Starting Google OAuth flow...")
print("A browser window will open asking you to sign in to your Google Account.")

flow = InstalledAppFlow.from_client_secrets_file(
    "credentials.json",
    SCOPES,
)

creds = flow.run_local_server(
    port=0,
    access_type="offline",
    prompt="consent",
)

refresh_token = creds.refresh_token
print("\nGoogle authentication successful!")
print("New Refresh Token:", refresh_token)

# 1. Save token.pickle for watchers/gmail_watcher.py
token_path = Path("watchers/token.pickle")
token_path.parent.mkdir(parents=True, exist_ok=True)
with open(token_path, "wb") as f:
    pickle.dump(creds, f)
print(f"[OK] Saved credentials to {token_path}")

# 2. Automatically update .env file
env_path = Path(".env")
if env_path.exists() and refresh_token:
    content = env_path.read_text(encoding="utf-8")
    content = re.sub(r"GMAIL_REFRESH_TOKEN=.*", f"GMAIL_REFRESH_TOKEN={refresh_token}", content)
    content = re.sub(r"GCAL_REFRESH_TOKEN=.*", f"GCAL_REFRESH_TOKEN={refresh_token}", content)
    env_path.write_text(content, encoding="utf-8")
    print("[OK] Updated GMAIL_REFRESH_TOKEN and GCAL_REFRESH_TOKEN in .env")
