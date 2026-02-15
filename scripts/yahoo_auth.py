"""One-time Yahoo OAuth2 authorization. Run this first, then run pull_yahoo_data.py."""

import os
import json
import webbrowser
from requests_oauthlib import OAuth2Session

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(SCRIPT_DIR, "yahoo_creds.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "yahoo_token.json")

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"

with open(CREDS_FILE) as f:
    creds = json.load(f)

CLIENT_ID = creds["consumer_key"]
CLIENT_SECRET = creds["consumer_secret"]
REDIRECT_URI = "oob"  # Out-of-band for installed apps

# Step 1: Get authorization URL
oauth = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
auth_url, state = oauth.authorization_url(AUTH_URL)

print("=" * 60)
print("Open this URL in your browser and authorize the app:")
print()
print(auth_url)
print()
print("=" * 60)

# Try to open the browser automatically
try:
    webbrowser.open(auth_url)
    print("(Browser should have opened automatically)")
except:
    print("(Copy/paste the URL above into your browser)")

print()
code = input("After authorizing, paste the verification code here: ").strip()

# Step 2: Exchange code for tokens
token = oauth.fetch_token(
    TOKEN_URL,
    code=code,
    client_secret=CLIENT_SECRET,
)

# Save token
with open(TOKEN_FILE, "w") as f:
    json.dump(token, f, indent=2)

print(f"\nToken saved to {TOKEN_FILE}")
print("You can now run: python pull_yahoo_data.py")
