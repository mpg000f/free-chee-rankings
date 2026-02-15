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

# Yahoo manager nickname -> canonical owner name
MANAGER_TO_OWNER = {
    "TJ": "TJ",
    "Mitchell Gray": "Mitch",
    "Joseph": "Boyle",
    "Connor": "Connor",
    "Ryan": "Sweeney",
    "Joey": "Joey",
    "Chris": "Chris",
    "Darren": "Gallo",
    "Matt": "Matt",
    "Paul": "Paul",
    "Simon": "Papi",
    "Mike": "Deez",
    "Matthew": "Ger",
    "Justin": "Justin",
    "Alexander": "TK",
    "Michael": "Mikey",
}

# Regular season weeks (before playoffs)
REGULAR_SEASON_WEEKS = 14


def load_json(path):
    """Load JSON file, return empty list/dict if missing."""
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def build_owner_map(season):
    """Build team_key -> owner name mapping from managers.json."""
    managers = load_json(os.path.join(YAHOO_DIR, season, "managers.json"))
    if isinstance(managers, dict):
        return {tk: MANAGER_TO_OWNER.get(info["manager"], info["manager"])
                for tk, info in managers.items()}
    return {}


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
    matchups = load_json(os.path.join(YAHOO_DIR, season, "matchups.json"))
    for m in matchups:
        if m.get("team_1_key") and m.get("team_1"):
            names[m["team_1_key"]] = m["team_1"]
        if m.get("team_2_key") and m.get("team_2"):
            names[m["team_2_key"]] = m["team_2"]
    return names


def build_season_summaries(season, owner_map):
    """Build per-team season summary from matchups data."""
    matchups = load_json(os.path.join(YAHOO_DIR, season, "matchups.json"))
    if not matchups:
        return {}

    # Compute W/L/PF/PA per team
    team_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0, "pf": 0.0, "pa": 0.0})
    team_last_game = {}  # team_key -> {week, pts, opp_pts, opp}

    for m in matchups:
        t1k, t2k = m["team_1_key"], m["team_2_key"]
        t1p, t2p = m["team_1_points"], m["team_2_points"]
        week = m["week"]

        # Regular season record (weeks 1-14)
        if week <= REGULAR_SEASON_WEEKS:
            if t1p > t2p:
                team_stats[t1k]["wins"] += 1
                team_stats[t2k]["losses"] += 1
            elif t2p > t1p:
                team_stats[t2k]["wins"] += 1
                team_stats[t1k]["losses"] += 1
            else:
                team_stats[t1k]["ties"] += 1
                team_stats[t2k]["ties"] += 1

        # Always count points
        team_stats[t1k]["pf"] += t1p
        team_stats[t1k]["pa"] += t2p
        team_stats[t2k]["pf"] += t2p
        team_stats[t2k]["pa"] += t1p

        # Track last game for each team
        t1_owner = owner_map.get(t1k, "")
        t2_owner = owner_map.get(t2k, "")
        team_last_game[t1k] = {"week": week, "pts": t1p, "opp_pts": t2p, "opp": t2_owner}
        team_last_game[t2k] = {"week": week, "pts": t2p, "opp_pts": t1p, "opp": t1_owner}

    # Determine standings rank (by wins, then PF tiebreaker)
    sorted_teams = sorted(team_stats.keys(),
                          key=lambda tk: (team_stats[tk]["wins"], team_stats[tk]["pf"]),
                          reverse=True)
    standings_rank = {tk: i + 1 for i, tk in enumerate(sorted_teams)}

    # PF and PA ranks
    pf_sorted = sorted(team_stats.keys(), key=lambda tk: team_stats[tk]["pf"], reverse=True)
    pa_sorted = sorted(team_stats.keys(), key=lambda tk: team_stats[tk]["pa"])  # lowest PA = rank 1
    pf_rank = {tk: i + 1 for i, tk in enumerate(pf_sorted)}
    pa_rank = {tk: i + 1 for i, tk in enumerate(pa_sorted)}

    # Determine playoff finish from weeks 15-16
    playoff_matchups = defaultdict(list)  # week -> list of matchups
    for m in matchups:
        if m["week"] > REGULAR_SEASON_WEEKS:
            playoff_matchups[m["week"]].append(m)

    # Teams in playoffs = teams that appear in week 15+ matchups
    playoff_teams = set()
    for week_ms in playoff_matchups.values():
        for m in week_ms:
            playoff_teams.add(m["team_1_key"])
            playoff_teams.add(m["team_2_key"])

    # Week 15 = semifinals, Week 16 = finals (for top bracket)
    # Also consolation games happen in these weeks
    max_week = max(m["week"] for m in matchups)
    team_playoff_finish = {}

    if max_week >= 16 and 15 in playoff_matchups and 16 in playoff_matchups:
        # Find who made the finals (week 16): the winners of the top-bracket semi matchups
        # Top bracket semis = the matchups in week 15 whose winners appear in week 16
        week16_teams = set()
        for m in playoff_matchups[16]:
            week16_teams.add(m["team_1_key"])
            week16_teams.add(m["team_2_key"])

        # Championship game = week 16 matchup between teams that were also in week 15
        # Find it by checking which week 16 matchup has teams from the top standings
        champ_matchup = None
        for m in playoff_matchups[16]:
            t1_rank = standings_rank.get(m["team_1_key"], 99)
            t2_rank = standings_rank.get(m["team_2_key"], 99)
            if champ_matchup is None or (t1_rank + t2_rank < sum(standings_rank.get(cm[k], 99) for k, cm in [(k, champ_matchup) for k in ["team_1_key", "team_2_key"]])):
                champ_matchup = m

        # Simpler: championship = week 16 matchup with highest combined PF from the season
        best_pf = -1
        for m in playoff_matchups[16]:
            combined = team_stats[m["team_1_key"]]["pf"] + team_stats[m["team_2_key"]]["pf"]
            if combined > best_pf:
                best_pf = combined
                champ_matchup = m

        if champ_matchup:
            t1k, t2k = champ_matchup["team_1_key"], champ_matchup["team_2_key"]
            if champ_matchup["team_1_points"] > champ_matchup["team_2_points"]:
                team_playoff_finish[t1k] = "Champion"
                team_playoff_finish[t2k] = "Runner-Up"
            else:
                team_playoff_finish[t2k] = "Champion"
                team_playoff_finish[t1k] = "Runner-Up"

        # Semi losers (in week 15, lost, and were in top bracket)
        for m in playoff_matchups[15]:
            t1k, t2k = m["team_1_key"], m["team_2_key"]
            # If winner went to championship
            if m["team_1_points"] > m["team_2_points"]:
                winner, loser = t1k, t2k
            else:
                winner, loser = t2k, t1k
            if winner in team_playoff_finish:  # winner made finals = this was a real semi
                team_playoff_finish[loser] = "Semifinal Loss"

    # Fill in remaining
    for tk in team_stats:
        if tk not in team_playoff_finish:
            if tk in playoff_teams:
                team_playoff_finish[tk] = "Consolation"
            else:
                team_playoff_finish[tk] = "No Playoffs"

    # Build summaries
    summaries = {}
    for tk in team_stats:
        s = team_stats[tk]
        last = team_last_game.get(tk, {})
        summaries[tk] = {
            "wins": s["wins"],
            "losses": s["losses"],
            "ties": s["ties"],
            "pf": round(s["pf"], 2),
            "pa": round(s["pa"], 2),
            "pf_rank": pf_rank.get(tk, 0),
            "pa_rank": pa_rank.get(tk, 0),
            "standing": standings_rank.get(tk, 0),
            "playoff_finish": team_playoff_finish.get(tk, ""),
            "last_game_pts": last.get("pts", 0),
            "last_game_opp_pts": last.get("opp_pts", 0),
            "last_game_opp": last.get("opp", ""),
        }

    return summaries


def build_rosters_data():
    """Build rosters_data.json: per season+team, week 1 and final rosters + summary."""
    result = {}

    for season in SEASONS:
        rosters = load_json(os.path.join(YAHOO_DIR, season, "rosters.json"))
        if not rosters:
            print(f"  {season}: no roster data, skipping")
            continue

        team_names = build_team_names(season)
        owner_map = build_owner_map(season)
        summaries = build_season_summaries(season, owner_map)

        # Determine position field name
        pos_field = "display_position"
        if rosters and pos_field not in rosters[0]:
            pos_field = "eligible_positions"

        # Group by team_key -> player_key -> list of (week, points)
        team_player_weeks = defaultdict(lambda: defaultdict(list))
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

        max_week = max(r["week"] for r in rosters)
        season_data = {"teams": {}, "max_week": max_week}

        # For position ranks
        pos_totals = defaultdict(list)

        for tk, players in team_player_weeks.items():
            owner = owner_map.get(tk, team_names.get(tk, tk))
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

                if info["pos"] in SKILL_POSITIONS:
                    pos_totals[info["pos"]].append((info["name"], total_pts, tk))

            week1_players.sort(key=lambda p: p["pts"], reverse=True)
            final_players.sort(key=lambda p: p["pts"], reverse=True)

            season_data["teams"][tk] = {
                "owner": owner,
                "team_name": team_names.get(tk, tk),
                "week1": week1_players,
                "final": final_players,
                "summary": summaries.get(tk, {}),
            }

        # Compute position ranks league-wide
        pos_ranks = {}
        for pos, entries in pos_totals.items():
            sorted_entries = sorted(entries, key=lambda x: x[1], reverse=True)
            for rank, (name, pts, tk) in enumerate(sorted_entries, 1):
                pos_ranks[(name, tk)] = f"{pos}{rank}"

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

        owner_map = build_owner_map(season)

        pos_field = "display_position"
        if rosters and pos_field not in rosters[0]:
            pos_field = "eligible_positions"

        player_season_pts = defaultdict(float)
        player_pos = {}
        for r in rosters:
            pk = r["player_key"]
            player_season_pts[pk] += r.get("points", 0)
            if r.get(pos_field):
                player_pos[pk] = r[pos_field]

        entries = []
        for d in draft:
            pk = d["player_key"]
            cost = d.get("cost", 0) or 0
            total_pts = player_season_pts.get(pk, 0)
            pos = player_pos.get(pk, "")
            tk = d.get("team_key", "")

            entries.append({
                "player": d.get("player_name", "Unknown"),
                "pos": pos,
                "owner": owner_map.get(tk, d.get("team_name", "")),
                "cost": cost,
                "pts": round(total_pts, 2),
                "ppd": round(total_pts / cost, 2) if cost > 0 else 0,
                "player_key": pk,
            })

        # Compute starter-based baselines
        pos_players = defaultdict(list)
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

        entries.sort(key=lambda e: e["value"], reverse=True)

        # Collect unique owners for filter
        owners = sorted(set(e["owner"] for e in entries))

        result[season] = {
            "players": entries,
            "owners": owners,
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
