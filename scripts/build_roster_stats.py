"""Build roster and draft value JSON files from Yahoo data."""

import os
import json
import numpy as np
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
DRAFT_VALUE_POSITIONS = {"QB", "RB", "WR", "TE", "DEF"}

# Team name -> owner mapping per season (from manual spreadsheet)
TEAM_OWNER_MAP = {
    "2022": {
        "Double Underhooks": "Sweeney",
        "GLOV\u00ca SIDE BRODEUR": "Matt",
        "Free Paid": "Gallo",
        "The Much Obliged": "Chris",
        "Alexander's Unreal Team": "Deez",
        "Tank Unloders": "Mitch",
        "The Jose Trevinos": "Boyle",
        "Vox Populi": "TK",
        "From You": "TJ",
        "Pots & Pans": "Joey",
        "Joe would rig a charity event": "Connor",
        "HAHAHAHAHAHAHA": "Ger",
        "The Ed Orgeron Alumni Assoc.": "Paul",
        "Uhhh THRIIIIISISSSHHHH": "Papi",
        "Tony the phenom": "Justin",
        "Senior Sack Dumpers": "Mikey",
    },
    "2023": {
        "Work Ass": "Sweeney",
        "WHERESTUA": "Matt",
        "Free Paid again..": "Gallo",
        "Sansa Ludacris": "Chris",
        "Alexander's Unreal Team": "Deez",
        "Willow Street Walruses": "Mitch",
        "The Lean Mean Fightin MaSheets": "Boyle",
        "Morior Invictus": "TK",
        "Cap Stoppers": "TJ",
        "Garlic Aioli": "Joey",
        "Sweeney.": "Connor",
        "🍾💼🥰": "Ger",
        "Formerly Known as Mousecop": "Paul",
        "Gorlock the destroyer Schwartz": "Papi",
        "Tony the phenom": "Justin",
        "Sr. Sack Dumping Scum Bags": "Mikey",
    },
    "2024": {
        "Work Ass": "Sweeney",
        "WHERESTUA": "Matt",
        "Here Without You Tishman": "Gallo",
        "Sansa Ludacris": "Chris",
        "Pigs on the 7th Rank": "Deez",
        "Deserves to be Shot": "Mitch",
        "Gotham Rogues": "Boyle",
        "Hand Me the Piss": "TK",
        "Cap Stoppers": "TJ",
        "Stewed C": "Joey",
        "Sweeney.": "Connor",
        "🍾💼🥰": "Ger",
        "Marvin\u2019s Receiver Room": "Paul",
        "Gorlock the destroyer Schwartz": "Papi",
        "Life with Derrick": "Justin",
        "Senior AI Coke Twins": "Mikey",
    },
    "2025": {
        "Work Ass": "Sweeney",
        "The Art of the Deal": "Matt",
        "Scampi": "Gallo",
        "Ginny Sack": "Chris",
        "Pigs on the 7th Rank": "Deez",
        "Sweeney Deez and Zaukas": "Mitch",
        "The Jackson Brownes": "Boyle",
        "Team OBAMA SOPRANOS": "TK",
        "Cookie Monster Golf Cart": "TJ",
        "Stewed C": "Joey",
        "Sweeney.": "Connor",
        "🍾💼🥰": "Ger",
        "Team Daniel": "Paul",
        "Gorlock the destroyer Schwartz": "Papi",
        "Life with Derrick": "Justin",
        "Senior AI Coke Twins": "Mikey",
    },
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
    """Build team_key -> owner name mapping from team names."""
    team_names = build_team_names(season)
    name_to_owner = TEAM_OWNER_MAP.get(season, {})
    owner_map = {}
    for tk, tn in team_names.items():
        # Try exact match, then strip whitespace
        owner = name_to_owner.get(tn) or name_to_owner.get(tn.strip())
        if not owner:
            # Try matching without leading/trailing special chars
            for map_name, map_owner in name_to_owner.items():
                if map_name.strip() in tn or tn.strip() in map_name:
                    owner = map_owner
                    break
        owner_map[tk] = owner or tn
    return owner_map


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
    pa_sorted = sorted(team_stats.keys(), key=lambda tk: team_stats[tk]["pa"], reverse=True)  # most PA = rank 1
    pf_rank = {tk: i + 1 for i, tk in enumerate(pf_sorted)}
    pa_rank = {tk: i + 1 for i, tk in enumerate(pa_sorted)}

    # Determine playoff finish from weeks 15-17
    # Week 15 = Quarterfinals (4 matchups, 8 teams)
    # Week 16 = Semifinals (2 championship bracket + 2 consolation)
    # Week 17 = Championship (1 champ game + consolation games)
    playoff_matchups = defaultdict(list)
    for m in matchups:
        if m["week"] > REGULAR_SEASON_WEEKS:
            playoff_matchups[m["week"]].append(m)

    # QF teams = teams in week 15
    qf_teams = set()
    for m in playoff_matchups.get(15, []):
        qf_teams.add(m["team_1_key"])
        qf_teams.add(m["team_2_key"])

    team_playoff_finish = {}

    # Track winners advancing through each round
    def get_winner(m):
        if m["team_1_points"] > m["team_2_points"]:
            return m["team_1_key"], m["team_2_key"]
        return m["team_2_key"], m["team_1_key"]

    # Week 15: QF — losers get "Quarterfinal Loss"
    qf_winners = set()
    for m in playoff_matchups.get(15, []):
        winner, loser = get_winner(m)
        qf_winners.add(winner)
        team_playoff_finish[loser] = "Quarterfinal Loss"

    # Week 16: SF — find the championship-bracket semis (matchups between QF winners)
    sf_winners = set()
    for m in playoff_matchups.get(16, []):
        t1k, t2k = m["team_1_key"], m["team_2_key"]
        winner, loser = get_winner(m)
        if t1k in qf_winners and t2k in qf_winners:
            # Championship bracket semifinal
            sf_winners.add(winner)
            team_playoff_finish[loser] = "Semifinal Loss"

    # Week 17: Championship — find the matchup between SF winners
    for m in playoff_matchups.get(17, []):
        t1k, t2k = m["team_1_key"], m["team_2_key"]
        if t1k in sf_winners and t2k in sf_winners:
            winner, loser = get_winner(m)
            team_playoff_finish[winner] = "Champion"
            team_playoff_finish[loser] = "Championship Loss"

    # Fill in remaining
    for tk in team_stats:
        if tk not in team_playoff_finish:
            if tk in qf_teams:
                team_playoff_finish[tk] = "Quarterfinal Loss"  # shouldn't happen
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

        # Find the latest week with roster data per team
        team_max_week = {}
        for r in rosters:
            tk = r["team_key"]
            team_max_week[tk] = max(team_max_week.get(tk, 0), r["week"])

        for tk, players in team_player_weeks.items():
            owner = owner_map.get(tk, team_names.get(tk, tk))
            week1_players = []
            final_players = []
            final_week = team_max_week.get(tk, max_week)

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
                if final_week in week_nums:
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
                "final_week": final_week,
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

    # First pass: pool all seasons to train a single model per position
    pooled_pos_players = defaultdict(list)
    season_data_cache = {}

    for season in SEASONS:
        draft = load_json(os.path.join(YAHOO_DIR, season, "draft.json"))
        rosters = load_json(os.path.join(YAHOO_DIR, season, "rosters.json"))

        if not draft or not rosters:
            print(f"  {season}: missing draft or roster data, skipping")
            continue

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

        season_data_cache[season] = {
            "draft": draft,
            "player_season_pts": player_season_pts,
            "player_pos": player_pos,
        }

        for d in draft:
            pk = d["player_key"]
            cost = d.get("cost", 0) or 0
            pts = player_season_pts.get(pk, 0)
            pos = player_pos.get(pk, "")
            if pos in DRAFT_VALUE_POSITIONS and cost > 0 and pts > 0:
                pooled_pos_players[pos].append({"cost": cost, "pts": pts})

    # Train pooled model: power regression (cost^0.7) on starters across all years
    pos_models = {}
    for pos, players in pooled_pos_players.items():
        threshold = STARTER_THRESHOLDS.get(pos, 16) * len(season_data_cache)
        starters = sorted(players, key=lambda p: p["pts"], reverse=True)[:threshold]
        cheap = [p for p in players if p["cost"] <= 2]

        costs = np.array([p["cost"] for p in starters], dtype=float)
        pts = np.array([p["pts"] for p in starters])
        coeffs = np.polyfit(np.power(costs, 0.7), pts, 1)

        if cheap:
            cheap_avg = sum(p["pts"] for p in cheap) / len(cheap)
            cheap_pow_cost = np.mean(np.power([float(p["cost"]) for p in cheap], 0.7))
        else:
            cheap_avg, cheap_pow_cost = 0, 1
        slope = float(coeffs[0])
        intercept = cheap_avg - slope * cheap_pow_cost

        pos_models[pos] = {"a": slope, "b": intercept}

    models_rounded = {pos: {"a": round(m["a"], 2), "b": round(m["b"], 2)}
                      for pos, m in pos_models.items()}

    # Second pass: apply pooled model to each season
    for season in SEASONS:
        if season not in season_data_cache:
            continue

        cached = season_data_cache[season]
        owner_map = build_owner_map(season)

        entries = []
        for d in cached["draft"]:
            pk = d["player_key"]
            cost = d.get("cost", 0) or 0
            total_pts = cached["player_season_pts"].get(pk, 0)
            pos = cached["player_pos"].get(pk, "")
            tk = d.get("team_key", "")

            if pos not in pos_models:
                continue

            model = pos_models[pos]
            if cost > 0:
                expected_pts = model["a"] * np.power(float(cost), 0.7) + model["b"]
                expected_pts = max(float(expected_pts), 0)
                # Cap expected pts for dart throws ($1-3) so misses aren't over-penalized
                if cost <= 3:
                    expected_pts = min(expected_pts, 30)
                value = round(total_pts - expected_pts, 1)
            else:
                expected_pts = 0
                value = 0

            entries.append({
                "player": d.get("player_name", "Unknown"),
                "pos": pos,
                "owner": owner_map.get(tk, d.get("team_name", "")),
                "cost": cost,
                "pts": round(total_pts, 2),
                "expected": round(expected_pts, 1),
                "value": value,
            })

        entries.sort(key=lambda e: e["value"], reverse=True)
        owners = sorted(set(e["owner"] for e in entries))

        result[season] = {
            "players": entries,
            "owners": owners,
            "models": models_rounded,
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
