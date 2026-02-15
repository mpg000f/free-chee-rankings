"""Pull fantasy football data from Yahoo Fantasy API."""

import os
import sys
import json
import time
import csv
from collections import defaultdict
from requests_oauthlib import OAuth2Session

# ===== CONFIG =====
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(SCRIPT_DIR, "yahoo_creds.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "yahoo_token.json")
BASE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_OUT = os.path.join(BASE_DIR, "yahoo_data")
os.makedirs(DATA_OUT, exist_ok=True)

YAHOO_API = "https://fantasysports.yahooapis.com/fantasy/v2"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"


def get_oauth():
    """Load saved token and create OAuth2 session with auto-refresh."""
    with open(CREDS_FILE) as f:
        creds = json.load(f)

    if not os.path.exists(TOKEN_FILE):
        print("No token found. Run yahoo_auth.py first!")
        sys.exit(1)

    with open(TOKEN_FILE) as f:
        token = json.load(f)

    client_id = creds["consumer_key"]
    client_secret = creds["consumer_secret"]

    def token_saver(new_token):
        with open(TOKEN_FILE, "w") as f:
            json.dump(new_token, f, indent=2)

    extra = {"client_id": client_id, "client_secret": client_secret}
    oauth = OAuth2Session(client_id, token=token,
                          auto_refresh_url=TOKEN_URL,
                          auto_refresh_kwargs=extra,
                          token_updater=token_saver)
    return oauth


def api_get_json(oauth, endpoint, retries=3):
    """Make a GET request and return JSON. Retries on rate limit (999) and connection errors."""
    url = f"{YAHOO_API}/{endpoint}"
    for attempt in range(retries + 1):
        try:
            resp = oauth.get(url, params={"format": "json"})
        except Exception as e:
            wait = 15 * (attempt + 1)
            print(f"  Connection error: {e.__class__.__name__}. Waiting {wait}s ({attempt + 1}/{retries})...")
            time.sleep(wait)
            continue
        if resp.status_code == 401:
            print("  Token expired, refreshing...")
            with open(CREDS_FILE) as f:
                creds = json.load(f)
            token = oauth.refresh_token(TOKEN_URL,
                                         client_id=creds["consumer_key"],
                                         client_secret=creds["consumer_secret"])
            with open(TOKEN_FILE, "w") as f:
                json.dump(token, f, indent=2)
            resp = oauth.get(url, params={"format": "json"})
        if resp.status_code == 999:
            wait = 30 * (attempt + 1)
            print(f"  Rate limited. Waiting {wait}s before retry ({attempt + 1}/{retries})...")
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            print(f"  API error {resp.status_code}: {url}")
            print(f"  Response: {resp.text[:300]}")
            return None
        return resp.json()
    print(f"  Failed after {retries} retries: {url}")
    return None


def discover_leagues(oauth):
    """Find all NFL fantasy leagues for the authenticated user."""
    print("Discovering leagues...")
    data = api_get_json(oauth, "users;use_login=1/games;game_codes=nfl/leagues")
    if not data:
        print("  Could not discover leagues. Using known leagues only.")
        return {}

    leagues = {}
    try:
        games = data["fantasy_content"]["users"]["0"]["user"][1]["games"]
        game_count = games["count"]
        for i in range(game_count):
            game = games[str(i)]["game"]
            game_info = game[0]
            game_key = str(game_info["game_key"])
            season = str(game_info["season"])

            if "leagues" in game[1]:
                league_data = game[1]["leagues"]
                league_count = league_data["count"]
                for j in range(league_count):
                    lg = league_data[str(j)]["league"][0]
                    league_id = str(lg["league_id"])
                    league_name = lg["name"]
                    entry = {
                        "game_key": game_key,
                        "league_id": league_id,
                        "league_key": f"{game_key}.l.{league_id}",
                        "name": league_name,
                        "season": season,
                    }
                    # Use league name as part of key to keep multiple leagues per season
                    key = f"{season}_{league_name}"
                    leagues[key] = entry
                    print(f"  Found: {season} - {league_name} (key: {game_key}.l.{league_id})")
    except (KeyError, TypeError) as e:
        print(f"  Error parsing leagues: {e}")

    return leagues


def pull_standings(oauth, league):
    """Pull league standings."""
    print(f"  Pulling standings...")
    data = api_get_json(oauth, f"league/{league['league_key']}/standings")
    if not data:
        return []

    standings = []
    try:
        teams = data["fantasy_content"]["league"][1]["standings"][0]["teams"]
        team_count = teams["count"]
        for i in range(team_count):
            team = teams[str(i)]["team"]
            info = team[0]
            # Team info is in a list of dicts
            team_data = {}
            for item in info:
                if isinstance(item, dict):
                    team_data.update(item)

            team_standings = team[1].get("team_standings", team[1])
            standings.append({
                "team_key": team_data.get("team_key", ""),
                "team_name": team_data.get("name", ""),
                "team_id": team_data.get("team_id", ""),
                "wins": int(team_standings.get("outcome_totals", {}).get("wins", 0)),
                "losses": int(team_standings.get("outcome_totals", {}).get("losses", 0)),
                "ties": int(team_standings.get("outcome_totals", {}).get("ties", 0)),
                "points_for": float(team_standings.get("points_for", 0)),
                "points_against": float(team_standings.get("points_against", 0)),
                "rank": int(team_standings.get("rank", 0)),
            })
    except (KeyError, TypeError, ValueError) as e:
        print(f"    Error parsing standings: {e}")

    return standings


def pull_draft_results(oauth, league):
    """Pull draft results with player details and costs."""
    print(f"  Pulling draft results...")
    data = api_get_json(oauth, f"league/{league['league_key']}/draftresults")
    if not data:
        return []

    results = []
    try:
        drafts = data["fantasy_content"]["league"][1]["draft_results"]
        draft_count = drafts["count"]
        for i in range(draft_count):
            pick = drafts[str(i)]["draft_result"]
            results.append({
                "pick": int(pick.get("pick", 0)),
                "round": int(pick.get("round", 0)),
                "team_key": pick.get("team_key", ""),
                "player_key": pick.get("player_key", ""),
                "cost": int(pick.get("cost", 0)) if "cost" in pick else None,
            })
    except (KeyError, TypeError, ValueError) as e:
        print(f"    Error parsing draft results: {e}")

    # Now resolve player names in batches
    if results:
        player_keys = [r["player_key"] for r in results if r["player_key"]]
        player_names = resolve_player_names(oauth, player_keys)
        for r in results:
            r["player_name"] = player_names.get(r["player_key"], "Unknown")

    # Resolve team names
    team_keys = set(r["team_key"] for r in results)
    team_names = {}
    standings = pull_standings(oauth, league)
    for s in standings:
        team_names[s["team_key"]] = s["team_name"]
    for r in results:
        r["team_name"] = team_names.get(r["team_key"], "Unknown")

    return results


def resolve_player_names(oauth, player_keys, batch_size=25):
    """Resolve player keys to names in batches."""
    names = {}
    for i in range(0, len(player_keys), batch_size):
        batch = player_keys[i:i + batch_size]
        keys_str = ",".join(batch)
        data = api_get_json(oauth, f"players;player_keys={keys_str}")
        if not data:
            continue
        try:
            players = data["fantasy_content"]["players"]
            count = players["count"]
            for j in range(count):
                player = players[str(j)]["player"]
                info = player[0]
                pkey = ""
                pname = ""
                for item in info:
                    if isinstance(item, dict):
                        if "player_key" in item:
                            pkey = item["player_key"]
                        if "name" in item:
                            pname = item["name"].get("full", "")
                names[pkey] = pname
        except (KeyError, TypeError):
            pass
        time.sleep(0.5)  # Rate limit
    return names


def pull_weekly_scores(oauth, league, num_weeks=17):
    """Pull weekly matchup scores."""
    print(f"  Pulling weekly scores (up to {num_weeks} weeks)...")
    all_matchups = []

    for week in range(1, num_weeks + 1):
        data = api_get_json(oauth, f"league/{league['league_key']}/scoreboard;week={week}")
        if not data:
            break

        try:
            matchups = data["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]
            match_count = matchups["count"]
            if match_count == 0:
                break

            for i in range(match_count):
                matchup = matchups[str(i)]["matchup"]
                teams = matchup.get("0", {}).get("teams", {})
                team_count = teams.get("count", 0)

                matchup_teams = []
                for j in range(team_count):
                    team = teams[str(j)]["team"]
                    info = team[0]
                    team_data = {}
                    for item in info:
                        if isinstance(item, dict):
                            team_data.update(item)

                    points = team[1].get("team_points", {})
                    matchup_teams.append({
                        "team_key": team_data.get("team_key", ""),
                        "team_name": team_data.get("name", ""),
                        "points": float(points.get("total", 0)),
                    })

                if len(matchup_teams) == 2:
                    all_matchups.append({
                        "week": week,
                        "team_1": matchup_teams[0]["team_name"],
                        "team_1_key": matchup_teams[0]["team_key"],
                        "team_1_points": matchup_teams[0]["points"],
                        "team_2": matchup_teams[1]["team_name"],
                        "team_2_key": matchup_teams[1]["team_key"],
                        "team_2_points": matchup_teams[1]["points"],
                    })

            print(f"    Week {week}: {match_count} matchups")
        except (KeyError, TypeError, ValueError) as e:
            print(f"    Week {week}: error - {e}")
            break

        time.sleep(0.3)

    return all_matchups


def pull_rosters(oauth, league, team_keys, num_weeks=17):
    """Pull weekly rosters with player stats for all teams."""
    print(f"  Pulling weekly rosters...")
    all_rosters = []

    for week in range(1, num_weeks + 1):
        week_rosters = []
        for team_key in team_keys:
            data = api_get_json(oauth, f"team/{team_key}/roster;week={week}/players/stats")
            if not data:
                continue

            try:
                roster = data["fantasy_content"]["team"][1]["roster"]["0"]["players"]
                player_count = roster["count"]
                for i in range(player_count):
                    player = roster[str(i)]["player"]
                    info = player[0]
                    pdata = {}
                    for item in info:
                        if isinstance(item, dict):
                            pdata.update(item)
                            if "name" in item:
                                pdata["player_name"] = item["name"].get("full", "")
                            if "display_position" in item:
                                pdata["display_position"] = item["display_position"]

                    # Get player points — index varies by response
                    player_points = 0
                    for pi in range(1, len(player)):
                        if isinstance(player[pi], dict) and "player_points" in player[pi]:
                            try:
                                player_points = float(player[pi]["player_points"]["total"])
                            except (KeyError, TypeError, ValueError):
                                pass
                            break

                    week_rosters.append({
                        "week": week,
                        "team_key": team_key,
                        "player_key": pdata.get("player_key", ""),
                        "player_name": pdata.get("player_name", ""),
                        "display_position": pdata.get("display_position", ""),
                        "points": player_points,
                    })
            except (KeyError, TypeError, ValueError) as e:
                pass

            time.sleep(1)

        if not week_rosters:
            break
        all_rosters.extend(week_rosters)
        pts_total = sum(r["points"] for r in week_rosters)
        print(f"    Week {week}: {len(week_rosters)} players, {pts_total:.1f} total pts")

    return all_rosters


def pull_transactions(oauth, league):
    """Pull league transactions (trades, adds, drops)."""
    print(f"  Pulling transactions...")
    data = api_get_json(oauth, f"league/{league['league_key']}/transactions")
    if not data:
        return []

    transactions = []
    try:
        txns = data["fantasy_content"]["league"][1]["transactions"]
        txn_count = txns["count"]
        for i in range(txn_count):
            txn = txns[str(i)]["transaction"]
            txn_info = txn[0]
            if len(txn) < 2:
                continue
            players_data = txn[1].get("players", {})

            players = []
            pcount = players_data.get("count", 0)
            for j in range(pcount):
                p = players_data[str(j)]["player"]
                pinfo = p[0]
                pdata = {}
                for item in pinfo:
                    if isinstance(item, dict):
                        pdata.update(item)
                        if "name" in item:
                            pdata["player_name"] = item["name"].get("full", "")
                        if "transaction_data" in item:
                            pdata.update(item["transaction_data"])
                players.append({
                    "player_name": pdata.get("player_name", ""),
                    "type": pdata.get("type", ""),
                    "source_team_key": pdata.get("source_team_key", ""),
                    "destination_team_key": pdata.get("destination_team_key", ""),
                })

            transactions.append({
                "transaction_id": txn_info.get("transaction_id", ""),
                "type": txn_info.get("type", ""),
                "timestamp": txn_info.get("timestamp", ""),
                "status": txn_info.get("status", ""),
                "players": players,
            })
    except (KeyError, TypeError, ValueError) as e:
        print(f"    Error parsing transactions: {e}")

    return transactions


def save_json(data, filename):
    """Save data as JSON."""
    path = os.path.join(DATA_OUT, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"    Saved: {path}")


def save_csv(data, filename, fieldnames=None):
    """Save list of dicts as CSV."""
    if not data:
        return
    path = os.path.join(DATA_OUT, filename)
    if not fieldnames:
        fieldnames = list(data[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
    print(f"    Saved: {path}")


def main():
    # Optional: pass a season year as argument to only pull that season
    only_season = sys.argv[1] if len(sys.argv) > 1 else None

    print("=== Yahoo Fantasy Data Pull ===\n")

    # Authenticate
    print("Authenticating with Yahoo...")
    oauth = get_oauth()
    print("  Authenticated!\n")

    # Discover leagues
    leagues = discover_leagues(oauth)
    print()

    if not leagues:
        print("No leagues found via API. Check your credentials.")
        return

    # Filter to only Free Chee leagues
    free_chee = {k: l for k, l in leagues.items() if "free chee" in l["name"].lower()}
    print(f"\nFiltered to {len(free_chee)} Free Chee leagues:")
    for k, l in sorted(free_chee.items()):
        print(f"  {l['season']}: {l['name']} ({l['league_key']})")
    leagues = free_chee

    if only_season:
        leagues = {k: l for k, l in leagues.items() if l["season"] == only_season}
        print(f"\nFiltering to season {only_season} only: {len(leagues)} league(s)")

    # Pull data for each season
    for key in sorted(leagues.keys()):
        league = leagues[key]
        season = league["season"]
        print(f"\n{'='*50}")
        print(f"Season {season}: {league['name']}")
        print(f"League key: {league['league_key']}")
        print(f"{'='*50}")

        season_dir = os.path.join(DATA_OUT, season)
        os.makedirs(season_dir, exist_ok=True)

        # Standings
        standings = pull_standings(oauth, league)
        if standings:
            save_json(standings, f"{season}/standings.json")
            save_csv(standings, f"{season}/standings.csv")
            team_keys = [s["team_key"] for s in standings]
        else:
            team_keys = []

        # Draft results
        draft = pull_draft_results(oauth, league)
        if draft:
            save_json(draft, f"{season}/draft.json")
            save_csv(draft, f"{season}/draft.csv",
                     ["pick", "round", "player_name", "team_name", "cost", "player_key", "team_key"])

        # Weekly scores
        matchups = pull_weekly_scores(oauth, league)
        if matchups:
            save_json(matchups, f"{season}/matchups.json")
            save_csv(matchups, f"{season}/matchups.csv")

        # Weekly rosters (this is the big one - takes a while)
        if team_keys:
            rosters = pull_rosters(oauth, league, team_keys)
            if rosters:
                save_json(rosters, f"{season}/rosters.json")
                save_csv(rosters, f"{season}/rosters.csv")

        # Transactions
        transactions = pull_transactions(oauth, league)
        if transactions:
            save_json(transactions, f"{season}/transactions.json")

        print(f"\n  Season {season} complete!")
        print(f"    Standings: {len(standings)} teams")
        print(f"    Draft picks: {len(draft)}")
        print(f"    Matchups: {len(matchups)}")
        print(f"    Roster entries: {len(rosters) if team_keys else 'skipped'}")
        print(f"    Transactions: {len(transactions)}")

    print(f"\n\n=== All data saved to {DATA_OUT} ===")


if __name__ == "__main__":
    main()
