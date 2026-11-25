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
LONG_TERM = {"IR", "IR-R", "SUSP", "PUP", "NFI", "NFI-R", "RESERVE"}
UNAVAILABLE = LONG_TERM | {"O", "OUT", "INACTIVE", "NA"}
DOUBTFUL = {"D", "DOUBTFUL"}
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
        status = str(row["player"].get("injury_status") or "").strip().upper()
        entry = (position, team_code(row.get("team")), points, status)
        index[name_key(f"{first} {last}")].append(entry)
        if position == "DEF":
            index[name_key(last)].append(entry)
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
        return same_team[0]
    return matches[0] if len(matches) == 1 else None


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


def yahoo_free_agents(oauth, league_key):
    agents = []
    for position in ("K", "DEF"):
        data = api_get_json(oauth, f"league/{league_key}/players;status=FA;position={position};count=25")
        if not data:
            continue
        players = data["fantasy_content"]["league"][1]["players"]
        for i in range(players["count"]):
            info = {key: value for part in players[str(i)]["player"][0] if isinstance(part, dict)
                    for key, value in part.items()}
            agents.append({"name": info["name"]["full"], "team": team_code(info.get("editorial_team_abbr")),
                           "eligible": {position}, "status": info.get("status") or ""})
    return agents


def unavailable(player, feed_status, current_week):
    statuses = {player["status"].strip().upper(), feed_status.strip().upper()}
    # Current-week reports should not rule a player out of a later game.
    return bool(statuses & (UNAVAILABLE | DOUBTFUL if current_week else LONG_TERM))


def optimized_total(roster, slots, projections, kickoffs, now, actual, current_week, free_agents=()):
    available_slots = list(slots)
    available_players = []
    rostered_specialists = set()
    accrued = 0.0
    remaining_locked = 0.0
    active = 0
    matched = 0
    for player in roster:
        game = kickoffs.get(player["team"])
        entry = find_projection(player, projections)
        points, feed_status = (entry[2], entry[3]) if entry else (None, "")
        matched += int(points is not None and game is not None)
        if current_week and game and game[0] <= now:
            if player["slot"] not in INACTIVE_SLOTS:
                available_slots.remove(player["slot"])
                accrued += player["actual"]
                if not game[1] and now < game[0] + timedelta(hours=4) and not unavailable(player, feed_status, True):
                    active += 1
                    elapsed = (now - game[0]) / timedelta(hours=4)
                    remaining_locked += max((points or 0) - player["actual"], max(0, points or 0) * .25 * (1 - elapsed))
            continue
        if game and points is not None and (not current_week or player["slot"] not in {"IR", "IL", "NA"}):
            if not unavailable(player, feed_status, current_week):
                available_players.append((player["eligible"], points))
                rostered_specialists.update(player["eligible"] & {"K", "DEF"})
    if matched < 5:
        raise ValueError("Insufficient matches between Yahoo roster and player projections")
    if current_week and abs(accrued - actual) > .1:
        raise ValueError("Locked Yahoo starters do not match the scoreboard total")

    for slot in sorted(({"K", "DEF"} & set(available_slots)) - rostered_specialists):
        available = []
        for player in free_agents:
            if slot not in player["eligible"]:
                continue
            entry = find_projection(player, projections)
            game = kickoffs.get(player["team"])
            if entry and entry[2] > 0 and game and game[0] > now and not unavailable(player, entry[3], current_week):
                available.append(entry[2])
        if available:
            # Use a typical pickup among the three best immediate free agents.
            available.sort(reverse=True)
            available_players.append(({slot}, available[min(1, len(available) - 1)]))

    projected_remaining = remaining_locked + maximize_points(available_slots, available_players)
    has_remaining = bool(active or any(eligible & slot_positions(slot)
                                       for eligible, _ in available_players for slot in available_slots))
    return round(actual + projected_remaining, 2), has_remaining


def attach_optimized_projections(fixtures, oauth, league_key, owners, season, now,
                                 current_week, postseason, playoff_projections, refresh_titles):
    slots, scoring = yahoo_rules(oauth, league_key)
    print(f"Yahoo starting slots: {', '.join(slots)}; PPR: {scoring.get('11', .5):g}")
    weeks = sorted({game["week"] for game in fixtures} | (set(range(max(15, current_week), 18)) if refresh_titles else set()))
    if not weeks:
        return
    rosters = {owner: yahoo_roster(oauth, key, current_week) for key, owner in owners.items()}
    try:
        free_agents = yahoo_free_agents(oauth, league_key) if fixtures else []
    except (KeyError, TypeError, requests.RequestException) as error:
        print(f"Yahoo free agents unavailable: {type(error).__name__}")
        free_agents = []
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
        scheduled = [game for game in (fixtures if week < 15 else postseason) if game["week"] == week]
        actual = {game[f"o{side}"]: game.get("live", {}).get(f"p{side}", 0)
                  for game in scheduled for side in (1, 2)}
        estimates = {}
        for owner, roster in rosters.items():
            if week == current_week and owner not in actual:
                continue
            try:
                estimates[owner] = optimized_total(roster, slots, projections, timings[week],
                                                   now, actual.get(owner, 0), week == current_week,
                                                   free_agents if week < 15 else ())
            except ValueError as error:
                print(f"Week {week} {owner}: {error}")
        if week >= 15:
            playoff_projections[str(week)] = {owner: estimate[0] for owner, estimate in estimates.items()}
        else:
            for game in scheduled:
                for side in (1, 2):
                    estimate = estimates.get(game[f"o{side}"])
                    if estimate is None:
                        continue
                    game.setdefault("optimized", {})[f"p{side}"] = estimate[0]
                    if week == current_week and game.get("live"):
                        game["live"][f"remaining{side}"] = estimate[1]
        published += len(estimates)
    print(f"Published {published} optimized team projections across {len(weeks)} weeks.")
