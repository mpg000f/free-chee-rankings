"""Weekly refresh: pull the current season from Yahoo and rebuild the site.

Designed to run unattended (GitHub Actions) or by hand. Credentials come from
the environment when present, so CI never needs the token files on disk:

    YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET, YAHOO_REFRESH_TOKEN

The weekly rankings PDFs are gitignored at the repo root but tracked under
site/pdfs/, so they are restored before the build -- without them
generate_site_data would find no PDFs and wipe every week of rankings.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
PDF_ARCHIVE = os.path.join(ROOT, "site", "pdfs")


def current_season():
    """NFL season year. Jan/Feb belong to the season that began last year."""
    today = date.today()
    return str(today.year if today.month >= 6 else today.year - 1)


def write_credentials():
    """Materialize creds/token files from env vars, if provided."""
    cid = os.environ.get("YAHOO_CLIENT_ID")
    secret = os.environ.get("YAHOO_CLIENT_SECRET")
    refresh = os.environ.get("YAHOO_REFRESH_TOKEN")
    if not (cid and secret and refresh):
        print("No Yahoo env vars; using existing credential files.")
        return

    with open(os.path.join(SCRIPTS, "yahoo_creds.json"), "w") as f:
        json.dump({"consumer_key": cid, "consumer_secret": secret}, f)
    # An expired access token is fine: every call refreshes first.
    with open(os.path.join(SCRIPTS, "yahoo_token.json"), "w") as f:
        json.dump({"access_token": "expired", "refresh_token": refresh,
                   "token_type": "bearer", "expires_in": 3600,
                   "expires_at": 0}, f)
    print("Wrote Yahoo credentials from environment.")


def restore_pdfs():
    """Copy tracked source PDFs back to the repo root for the parser."""
    if not os.path.isdir(PDF_ARCHIVE):
        sys.exit(f"PDF archive missing: {PDF_ARCHIVE}")
    n = 0
    for name in os.listdir(PDF_ARCHIVE):
        if name.lower().endswith(".pdf"):
            dest = os.path.join(ROOT, name)
            if not os.path.exists(dest):
                shutil.copy2(os.path.join(PDF_ARCHIVE, name), dest)
            n += 1
    print(f"Source PDFs available at root: {n}")
    if n == 0:
        sys.exit("Refusing to build with no source PDFs -- would wipe rankings.")


def run(script, *args):
    print(f"\n=== {script} {' '.join(args)} ===")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                       cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"{script} failed with exit code {r.returncode}")


def main():
    season = os.environ.get("SEASON") or current_season()
    print(f"Weekly update for season {season}")

    write_credentials()
    restore_pdfs()

    run("pull_yahoo_data.py", season)
    run("build_roster_stats.py")   # not part of build.py's chain
    run("build.py")

    print("\nWeekly update complete.")


if __name__ == "__main__":
    main()
