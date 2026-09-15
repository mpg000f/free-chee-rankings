"""Has Yahoo granted Fantasy API access yet? Refreshes the token and probes.

    python check_yahoo_access.py

A 403 "not authorized" means the application is still pending -- the app's
Fantasy Sports checkbox in the developer console reflects stored config, not
whether Yahoo will serve the request, so the console cannot answer this.
"""

import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CREDS = os.path.join(HERE, "yahoo_creds.json")
TOKEN = os.path.join(HERE, "yahoo_token.json")
PROBE = "https://fantasysports.yahooapis.com/fantasy/v2/game/nfl?format=json"


def main():
    creds = json.load(open(CREDS))
    tok = json.load(open(TOKEN))

    r = requests.post("https://api.login.yahoo.com/oauth2/get_token", data={
        "client_id": creds["consumer_key"],
        "client_secret": creds["consumer_secret"],
        "redirect_uri": "https://localhost:1410",
        "refresh_token": tok["refresh_token"],
        "grant_type": "refresh_token",
    }, timeout=30)

    if not r.ok:
        print(f"Token refresh failed ({r.status_code}). Re-run yahoo_auth.py.")
        return
    fresh = r.json()
    tok.update(fresh)
    tok["expires_at"] = int(time.time()) + int(fresh.get("expires_in", 3600))
    json.dump(tok, open(TOKEN, "w"), indent=2)

    resp = requests.get(PROBE, headers={
        "Authorization": f"Bearer {tok['access_token']}"}, timeout=30)

    if resp.status_code == 200:
        print("ACCESS GRANTED - Fantasy API is working.")
        print("Next: re-run `python yahoo_auth.py` for a fresh grant, then pull_yahoo_data.py")
    elif resp.status_code == 403:
        print("Still blocked (403 'not authorized'). Application is pending with Yahoo.")
    elif resp.status_code == 401:
        print("401 - token lacks Fantasy permission. Re-run yahoo_auth.py.")
    else:
        print(f"Unexpected {resp.status_code}: {resp.text[:200]}")


if __name__ == "__main__":
    main()
