"""One-time Yahoo OAuth2 authorization. Run this first, then run pull_yahoo_data.py.

Yahoo will not widen an existing grant: a refresh token minted before the app
gained Fantasy Sports permission keeps its original (empty) scope forever, and
refreshing it silently returns a scopeless token that 403s on every endpoint.
Re-running this script is what issues a new grant.

Usage:
    python yahoo_auth.py            # prints the URL, waits for the pasted redirect
    python yahoo_auth.py --url URL  # exchange a redirect URL captured elsewhere
"""

import argparse
import json
import os
import sys
import webbrowser
from urllib.parse import urlparse, parse_qs

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(SCRIPT_DIR, "yahoo_creds.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "yahoo_token.json")

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"

# Must match the redirect URI registered on the Yahoo app exactly.
REDIRECT_URI = "https://localhost:1410"
# Yahoo rejects "fspt-r" with invalid_scope unless the app registration carries
# Fantasy Sports permission, which its create form no longer offers. Requesting
# no scope lets the token inherit whatever the app was granted, which is how
# working Fantasy integrations are set up. Override with --scope to experiment.
SCOPES = ""


def load_creds():
    with open(CREDS_FILE) as f:
        creds = json.load(f)
    return creds["consumer_key"], creds["consumer_secret"]


def authorize_url(client_id, scope=None):
    from urllib.parse import urlencode
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
    }
    scope = SCOPES if scope is None else scope
    if scope:
        params["scope"] = scope
    return AUTH_URL + "?" + urlencode(params)


def code_from(raw):
    """Accept either a bare code or the full localhost redirect URL."""
    raw = raw.strip()
    if raw.startswith("http"):
        qs = parse_qs(urlparse(raw).query)
        if "error" in qs:
            sys.exit(f"Yahoo returned an error: {qs['error'][0]} "
                     f"{qs.get('error_description', [''])[0]}")
        if "code" not in qs:
            sys.exit("No ?code= found in that URL.")
        return qs["code"][0]
    return raw


def exchange(client_id, client_secret, code):
    r = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "code": code,
        "grant_type": "authorization_code",
    }, timeout=30)
    if not r.ok:
        sys.exit(f"Token exchange failed ({r.status_code}): {r.text[:300]}")
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="the https://localhost:1410/?code=... URL")
    ap.add_argument("--scope", default=None, help="override the requested scope")
    args = ap.parse_args()

    client_id, client_secret = load_creds()

    if args.url:
        raw = args.url
    else:
        url = authorize_url(client_id, args.scope)
        print("=" * 68)
        print("Open this URL and authorize the app:\n")
        print(url)
        print("\nThe browser will fail to load localhost:1410 - that is expected.")
        print("Copy the whole address bar URL and paste it below.")
        print("=" * 68)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        raw = input("\nPaste the redirect URL (or just the code): ")

    token = exchange(client_id, client_secret, code_from(raw))

    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f, indent=2)

    scope = token.get("scope")
    print(f"\nToken saved to {TOKEN_FILE}")
    print(f"  scope      : {scope!r}")
    print(f"  expires_in : {token.get('expires_in')}")
    print(f"  refresh    : {'yes' if token.get('refresh_token') else 'no'}")
    if not scope:
        print("\n  WARNING: no scope was granted. Fantasy endpoints will 403.")
        print("  The Yahoo app is not actually granting Fantasy Sports access -")
        print("  register a fresh app and replace yahoo_creds.json.")
    else:
        print("\n  Now run: python pull_yahoo_data.py")


if __name__ == "__main__":
    main()
