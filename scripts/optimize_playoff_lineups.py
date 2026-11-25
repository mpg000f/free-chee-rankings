"""Estimate weekly best legal lineups from the latest Yahoo roster snapshot."""

import csv
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from pull_yahoo_data import api_get_json

POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
INACTIVE_SLOTS = {"BN", "IR", "IL", "NA"}
TEAM_ALIASES = {"LA": "LAR", "JAC": "JAX", "WSH": "WAS"}
NFL_SCHEDULE = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"


def team_code(code):
    upper = (code or "").upper()
    return TEAM_ALIASES.get(upper, upper)


def name_key(name):
    plain = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()
    plain = re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", "", plain)
    return re.sub(r"[^a-z0-9]", "", plain)


def point_value(projection, scoring):
    stats = projection["stats"]
    points = stats.get("pts_half_ppr")
    if points is None:
        return None
    # Align the core offense categories with the league's settings. K and DEF
    # retain the provider's scoring, which includes its threshold projections.
    if projection["player"]["position"] not in {"K", "DEF"}:
        for stat_id, field, default in (
            ("4", "pass_yd", .04), ("5", "pass_td", 4), ("6", "pass_int", -1),
            ("9", "rush_yd", .1), ("10", "rush_td", 6), ("11", "rec", .5),
            ("12", "rec_yd", .1), ("13", "rec_td", 6), ("18", "fum_lost", -2),
        ):
            points += (scoring.get(stat_id, default) - default) * stats.get(field, 0)
    return float(points) if math.isfinite(points) else None


def projection_index(rows, season, week, scoring):
    index = defaultdict(list)
    for row in rows:
        position = row["player"]["position"]
        if position not in POSITIONS or str(row["season"]) != season or int(row["week"]) != week:
            continue
        points = point_value(row, scoring)
        if points is None:
            continue
        first, last = (row["player"].get(key) or "" for key in ("first_name", "last_name"))
        index[name_key(f"{first} {last}")].append((position, team_code(row.get("team")), points))
        if position == "DEF":
            index[name_key(last)].append((position, team_code(row.get("team")), points))
    if len(index) < 200:
        raise ValueError(f"Insufficient player projections for Week {week}")
    return index


def source_json(url):
    response = requests.get(url, timeout=25)
    response.raise_for_status()
    return response.json()


def nfl_kickoffs(season):
    response = requests.get(NFL_SCHEDULE, timeout=25)
    response.raise_for_status()
    times = defaultdict(dict)
    for row in csv.DictReader(response.text.splitlines()):
        if row["season"] != season or row["game_type"] != "REG" or not row["gametime"]:
            continue
        kickoff = datetime.fromisoformat(f'{row["gameday"]}T{row["gametime"]}').replace(
            tzinfo=ZoneInfo("America/New_York"))
        finished = bool(row["away_score"] and row["home_score"])
        for side in ("away_team", "home_team"):
            times[int(row["week"])][team_code(row[side])] = (kickoff, finished)
    return times


def yahoo_rules(oauth, league_key):
    data = api_get_json(oauth, f"league/{league_key}/settings")
    settings = data["fantasy_content"]["league"][1]["settings"]
    if isinstance(settings, list):
        settings = settings[0]
    slots = []
    for entry in settings["roster_positions"]:
        slot = entry["roster_position"]
        position = slot["position"]
        if position not in INACTIVE_SLOTS:
            slots.extend([position] * int(slot["count"]))
    if not 1 <= len(slots) <= 12 or any(not slot_positions(slot) for slot in slots):
        raise ValueError("Unexpected Yahoo starting slots")
    scoring = {str(row["stat"]["stat_id"]): float(row["stat"]["value"])
               for row in settings["stat_modifiers"]["stats"] if row["stat"].get("value") not in (None, "")}
    return slots, scoring


def slot_positions(slot):
    aliases = {"Q": "QB", "W": "WR", "R": "RB", "T": "TE"}
    if slot == "FLEX":
        return {"RB", "WR", "TE"}
    if slot in {"SF", "SUPERFLEX"}:
        return {"QB", "RB", "WR", "TE"}
    return {aliases.get(part, part) for part in slot.split("/")} & POSITIONS


def yahoo_roster(oauth, team_key, week):
    data = api_get_json(oauth, f"team/{team_key}/roster;week={week}/players/stats")
    rows = data["fantasy_content"]["team"][1]["roster"]["0"]["players"]
    roster = []
    for i in range(rows["count"]):
        player = rows[str(i)]["player"]
        info = {key: value for part in player[0] if isinstance(part, dict) for key, value in part.items()}
        stats = {key: value for part in player[1:] if isinstance(part, dict) for key, value in part.items()}
        eligible = {entry["position"] for entry in info.get("eligible_positions", [])
                    if isinstance(entry, dict) and "position" in entry} & POSITIONS
        eligible = eligible or (set(info.get("display_position", "").split("/")) & POSITIONS)
        selection = stats.get("selected_position", info.get("selected_position", {}))
        if isinstance(selection, list):
            selection = {key: value for part in selection if isinstance(part, dict)
                         for key, value in part.items()}
        roster.append({
            "id": info["player_key"],
            "name": info["name"]["full"],
            "team": team_code(info.get("editorial_team_abbr")),
            "eligible": eligible,
            "slot": selection.get("position"),
            "status": info.get("status") or "",
            "actual": float(stats.get("player_points", {}).get("total") or 0),
        })
    if not roster or any(not player["slot"] for player in roster):
        raise ValueError("Yahoo roster returned without lineup assignments")
    return roster


def find_projection(player, index):
    matches = [entry for entry in index.get(name_key(player["name"]), []) if entry[0] in player["eligible"]]
    same_team = [entry for entry in matches if entry[1] == player["team"]]
    if len(same_team) == 1:
        return same_team[0][2]
    return matches[0][2] if len(matches) == 1 else None


def maximize_points(slots, players):
    """Assign each candidate at most once, retaining the best total for each slot mask."""
    allowed = [slot_positions(slot) for slot in slots]
    states = {0: 0.0}
    for eligible, projection in players:
        for mask, value in list(states.items()):
            for i, positions in enumerate(allowed):
                next_mask = mask | (1 << i)
                if next_mask != mask and positions & eligible:
                    states[next_mask] = max(states.get(next_mask, -math.inf), value + projection)
    # Fill as many legal slots as possible, even if a player projects below zero.
    return max(states.items(), key=lambda item: (item[0].bit_count(), item[1]))[1]


def optimized_total(roster, slots, projections, kickoffs, now, actual, current_week):
    available_slots = list(slots)
    available_players = []
    accrued = 0.0
    remaining_locked = 0.0
    matched = 0
    for player in roster:
        game = kickoffs.get(player["team"])
        points = find_projection(player, projections)
        matched += int(points is not None and game is not None)
        if current_week and game and game[0] <= now:
            if player["slot"] not in INACTIVE_SLOTS:
                available_slots.remove(player["slot"])
                accrued += player["actual"]
                if not game[1] and now < game[0] + timedelta(hours=4):
                    remaining_locked += max(0, (points or 0) - player["actual"])
            continue
        if game and points is not None and player["slot"] not in {"IR", "IL", "NA"}:
            if not current_week or player["status"].upper() not in {"O", "OUT", "IR", "NA", "SUSP", "PUP"}:
                available_players.append((player["eligible"], points))
    if matched < 5:
        raise ValueError("Insufficient matches between Yahoo roster and player projections")
    if current_week and abs(accrued - actual) > .1:
        raise ValueError("Locked Yahoo starters do not match the scoreboard total")
    return round(actual + remaining_locked + maximize_points(available_slots, available_players), 2)


def attach_optimized_projections(fixtures, oauth, league_key, owners, season, now):
    slots, scoring = yahoo_rules(oauth, league_key)
    print(f"Yahoo starting slots: {', '.join(slots)}; PPR: {scoring.get('11', .5):g}")
    weeks = sorted({game["week"] for game in fixtures})
    current_week = weeks[0]
    rosters = {owner: yahoo_roster(oauth, key, current_week) for key, owner in owners.items()}
    timings = nfl_kickoffs(season)
    published = 0
    for week in weeks:
        try:
            if len(timings.get(week, {})) < 24:
                raise ValueError("NFL kickoffs unavailable")
            rows = source_json(f"https://api.sleeper.com/projections/nfl/{season}/{week}?season_type=regular")
            projections = projection_index(rows, season, week, scoring)
        except (ValueError, KeyError, TypeError, requests.RequestException) as error:
            print(f"Week {week} optimized projections unavailable: {type(error).__name__}: {error}")
            continue
        for game in fixtures:
            if game["week"] != week:
                continue
            optimized = {}
            for side in (1, 2):
                owner = game[f"o{side}"]
                actual = game.get("live", {}).get(f"p{side}", 0)
                try:
                    optimized[f"p{side}"] = optimized_total(rosters[owner], slots, projections,
                                                            timings[week], now, actual, week == current_week)
                except ValueError as error:
                    print(f"Week {week} {owner}: {error}")
            if optimized:
                game["optimized"] = optimized
                published += len(optimized)
    print(f"Published {published} optimized team projections across {len(weeks)} weeks.")
