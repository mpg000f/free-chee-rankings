"""Build roster and draft value JSON files from Yahoo data."""

import os
import json
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
YAHOO_DIR = os.path.join(BASE_DIR, "yahoo_data")
SITE_DATA = os.path.join(BASE_DIR, "site", "data")
os.makedirs(SITE_DATA, exist_ok=True)

SEASONS = ["2022", "2023", "2024", "2025"]

# Superflex 16-team league starter thresholds
STARTER_THRESHOLDS = {"QB": 32, "RB": 40, "WR": 40, "TE": 16, "K": 16, "DEF": 16}
SKILL_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}


def load_json(path):
    """Load JSON file, return empty list if missing."""
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def build_team_names(season):
    """Build team_key -> team_name mapping from draft + standings + matchups."""
    names = {}
    for src in ["standings.json", "draft.json"]:
        data = load_json(os.path.join(YAHOO_DIR, season, src))
        for entry in data:
            tk = entry.get("team_key", "")
            tn = entry.get("team_name", "")
            if tk and tn:
                names[tk] = tn
    # Also from matchups
    matchups = load_json(os.path.join(YAHOO_DIR, season, "matchups.json"))
    for m in matchups:
        if m.get("team_1_key") and m.get("team_1"):
            names[m["team_1_key"]] = m["team_1"]
        if m.get("team_2_key") and m.get("team_2"):
            names[m["team_2_key"]] = m["team_2"]
    return names


def build_rosters_data():
    """Build rosters_data.json: per season+team, week 1 and week 16 rosters."""
    result = {}

    for season in SEASONS:
        rosters = load_json(os.path.join(YAHOO_DIR, season, "rosters.json"))
        if not rosters:
            print(f"  {season}: no roster data, skipping")
            continue

        team_names = build_team_names(season)

        # Determine position field name (old format uses eligible_positions, new uses display_position)
        pos_field = "display_position"
        if rosters and pos_field not in rosters[0]:
            pos_field = "eligible_positions"

        # Group by team_key -> player_key -> list of (week, points)
        team_player_weeks = defaultdict(lambda: defaultdict(list))
        # Track player info (name, position)
        player_info = {}

        for r in rosters:
            tk = r["team_key"]
            pk = r["player_key"]
            team_player_weeks[tk][pk].append({
                "week": r["week"],
                "points": r.get("points", 0),
            })
            player_info[pk] = {
                "name": r.get("player_name", ""),
                "pos": r.get(pos_field, ""),
            }

        # Get max week in data
        max_week = max(r["week"] for r in rosters)

        # Build rosters for week 1 and final week per team
        # Also compute season total points per player per team
        season_data = {"teams": {}, "max_week": max_week}

        # For position ranks: accumulate all player season totals by position
        pos_totals = defaultdict(list)  # pos -> [(player_name, total_pts, team_key)]

        for tk, players in team_player_weeks.items():
            tn = team_names.get(tk, tk)
            week1_players = []
            final_players = []

            for pk, weeks in players.items():
                info = player_info[pk]
                total_pts = sum(w["points"] for w in weeks)
                week_nums = {w["week"] for w in weeks}

                entry = {
                    "name": info["name"],
                    "pos": info["pos"],
                    "pts": round(total_pts, 2),
                }

                if 1 in week_nums:
                    week1_players.append(entry)
                if max_week in week_nums:
                    final_players.append(entry)

                # Track for position ranking (only skill positions)
                if info["pos"] in SKILL_POSITIONS:
                    pos_totals[info["pos"]].append((info["name"], total_pts, tk))

            # Sort by points descending
            week1_players.sort(key=lambda p: p["pts"], reverse=True)
            final_players.sort(key=lambda p: p["pts"], reverse=True)

            season_data["teams"][tk] = {
                "team_name": tn,
                "week1": week1_players,
                "final": final_players,
            }

        # Compute position ranks league-wide
        pos_ranks = {}  # player_key not available here, use (name, team_key)
        for pos, entries in pos_totals.items():
            sorted_entries = sorted(entries, key=lambda x: x[1], reverse=True)
            for rank, (name, pts, tk) in enumerate(sorted_entries, 1):
                pos_ranks[(name, tk)] = f"{pos}{rank}"

        # Attach position ranks to roster entries
        for tk, team_data in season_data["teams"].items():
            for roster_list in [team_data["week1"], team_data["final"]]:
                for p in roster_list:
                    p["pos_rank"] = pos_ranks.get((p["name"], tk), "")

        result[season] = season_data
        team_count = len(season_data["teams"])
        print(f"  {season}: {team_count} teams, weeks 1-{max_week}")

    return result


def build_draft_value():
    """Build draft_value.json: per season, drafted players with value scores."""
    result = {}

    for season in SEASONS:
        draft = load_json(os.path.join(YAHOO_DIR, season, "draft.json"))
        rosters = load_json(os.path.join(YAHOO_DIR, season, "rosters.json"))

        if not draft or not rosters:
            print(f"  {season}: missing draft or roster data, skipping")
            continue

        team_names = build_team_names(season)

        # Determine position field
        pos_field = "display_position"
        if rosters and pos_field not in rosters[0]:
            pos_field = "eligible_positions"

        # Compute season total points per player (across all teams they were on)
        player_season_pts = defaultdict(float)
        player_pos = {}
        for r in rosters:
            pk = r["player_key"]
            player_season_pts[pk] += r.get("points", 0)
            if r.get(pos_field):
                player_pos[pk] = r[pos_field]

        # Build draft entries with points
        entries = []
        for d in draft:
            pk = d["player_key"]
            cost = d.get("cost", 0) or 0
            total_pts = player_season_pts.get(pk, 0)
            pos = player_pos.get(pk, "")

            entries.append({
                "player": d.get("player_name", "Unknown"),
                "pos": pos,
                "team": team_names.get(d.get("team_key", ""), d.get("team_name", "")),
                "cost": cost,
                "pts": round(total_pts, 2),
                "ppd": round(total_pts / cost, 2) if cost > 0 else 0,
                "player_key": pk,
            })

        # Compute starter-based baselines per position
        pos_players = defaultdict(list)  # pos -> [(pts, cost)]
        for e in entries:
            if e["pos"] in SKILL_POSITIONS and e["pts"] > 0:
                pos_players[e["pos"]].append((e["pts"], e["cost"]))

        pos_baselines = {}
        for pos, players in pos_players.items():
            threshold = STARTER_THRESHOLDS.get(pos, 16)
            sorted_by_pts = sorted(players, key=lambda x: x[0], reverse=True)
            starters = sorted_by_pts[:threshold]
            if starters:
                avg_pts = sum(p[0] for p in starters) / len(starters)
                avg_cost = sum(p[1] for p in starters) / len(starters)
                pos_baselines[pos] = {"avg_pts": avg_pts, "avg_cost": avg_cost}

        # Compute value scores
        for e in entries:
            pos = e["pos"]
            if pos in pos_baselines and pos_baselines[pos]["avg_cost"] > 0:
                bl = pos_baselines[pos]
                expected_pts = (e["cost"] / bl["avg_cost"]) * bl["avg_pts"]
                voe = e["pts"] - expected_pts
                value_score = (voe / bl["avg_pts"]) * 100
                e["expected"] = round(expected_pts, 1)
                e["voe"] = round(voe, 1)
                e["value"] = round(value_score, 1)
            else:
                e["expected"] = 0
                e["voe"] = 0
                e["value"] = 0

            del e["player_key"]

        # Sort by value score
        entries.sort(key=lambda e: e["value"], reverse=True)

        result[season] = {
            "players": entries,
            "baselines": {pos: {"avg_pts": round(b["avg_pts"], 1), "avg_cost": round(b["avg_cost"], 1)}
                          for pos, b in pos_baselines.items()},
        }
        print(f"  {season}: {len(entries)} drafted players")

    return result


def main():
    print("=== Building Roster & Draft Value Data ===\n")

    print("Building rosters data...")
    rosters_data = build_rosters_data()
    out_path = os.path.join(SITE_DATA, "rosters_data.json")
    with open(out_path, "w") as f:
        json.dump(rosters_data, f, indent=2)
    print(f"  Saved: {out_path}\n")

    print("Building draft value data...")
    draft_value = build_draft_value()
    out_path = os.path.join(SITE_DATA, "draft_value.json")
    with open(out_path, "w") as f:
        json.dump(draft_value, f, indent=2)
    print(f"  Saved: {out_path}\n")

    print("Done!")


if __name__ == "__main__":
    main()
