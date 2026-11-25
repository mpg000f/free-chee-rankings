"""Publish Yahoo scoreboard totals and projections without rebuilding the site."""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from build_engagement_data import REG_SEASON_LAST_WEEK
from optimize_playoff_lineups import attach_optimized_projections
from requests import RequestException
from pull_yahoo_data import current_week, get_oauth, pull_week_scores
from weekly_update import current_season, write_credentials

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "yahoo_data/playoff_snapshot.json"
LIVE_STATUSES = {"midevent", "inevent"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_key(game):
    return game["week"], frozenset((game["o1"], game["o2"]))


def refresh_schedule(schedule, team_keys, get_scores):
    """Keep each fixture's orientation and move only Yahoo finals into standings."""
    slots = {fixture_key(game): game for game in schedule["upcoming"]}
    for week in sorted({game["week"] for game in slots.values()}):
        expected = {key for key in slots if key[0] == week}
        received = {}
        for result in get_scores(week):
            owners = [team_keys[result[f"team_{side}_key"]] for side in (1, 2)]
            key = week, frozenset(owners)
            if key in received:
                raise ValueError(f"Duplicate Yahoo matchup in Week {week}")
            received[key] = (owners, result)
        if expected != received.keys() & expected:
            raise ValueError(f"Incomplete Yahoo scoreboard for Week {week}")

        for key in sorted(expected, key=lambda item: sorted(item[1])):
            owners, result = received[key]
            fixture = slots[key]
            status = result["status"]
            if status not in {"preevent", "postevent"} | LIVE_STATUSES:
                raise ValueError(f"Unknown Yahoo matchup status {status!r}")
            if status == "preevent":
                if fixture.get("live"):
                    raise ValueError(f"Yahoo reverted a live matchup in Week {week}")
                continue
            scores = {}
            projections = {}
            for side, owner in enumerate(owners, 1):
                points = result[f"team_{side}_points"]
                if points is None or not math.isfinite(points):
                    raise ValueError(f"Missing Yahoo score in Week {week}")
                scores[owner] = round(points, 2)
                projection = result[f"team_{side}_projection"]
                if projection is not None and math.isfinite(projection) and projection > 0:
                    projections[owner] = round(projection, 2)

            score = {f"p{side}": scores[fixture[f"o{side}"]] for side in (1, 2)}
            if status == "postevent":
                finished = {field: value for field, value in fixture.items() if field != "live"}
                schedule["games"].append({**finished, **score})
                del slots[key]
            else:
                fixture["live"] = {**score, **{
                    f"projected{side}": projections.get(fixture[f"o{side}"]) for side in (1, 2)
                }}
    schedule["upcoming"] = list(slots.values())
    return schedule


def main():
    season = current_season()
    feed = read_json(ROOT / "docs/data/matchups_all.json")
    schedule = {
        group: [game for game in feed[group] if str(game["season"]) == season
                and game["week"] <= REG_SEASON_LAST_WEEK and not game.get("playoff")]
        for group in ("games", "upcoming")
    }
    if not schedule["games"] and not schedule["upcoming"]:
        print("No games in the current season's schedule.")
        return

    # Preserve a verified result if the weekly rebuild has yet to incorporate it.
    previous = read_json(SNAPSHOT) if SNAPSHOT.exists() else {}
    if previous.get("season") == season:
        finals = {fixture_key(game): game for game in previous["games"]}
        live = {fixture_key(game): game["live"] for game in previous["upcoming"] if game.get("live")}
        remaining = []
        for game in schedule["upcoming"]:
            key = fixture_key(game)
            if key in finals:
                schedule["games"].append(finals[key])
            else:
                if key in live:
                    game["live"] = live[key]
                remaining.append(game)
        schedule["upcoming"] = remaining
    now = datetime.now(timezone.utc)
    optimized_as_of = None
    postseason, playoff_projections = [], {}
    published_postseason = [game for game in feed["games"]
                            if game["season"] == season and game["playoff"]]
    if schedule["upcoming"] or not any(game.get("round") == "Championship" for game in published_postseason):
        teams = read_json(ROOT / "docs/data/rosters_data.json")[season]["teams"]
        team_keys = {key: value["owner"] for key, value in teams.items()}
        league_keys = {key.rsplit(".t.", 1)[0] for key in team_keys}
        if len(league_keys) != 1 or len(team_keys) != 16:
            raise ValueError("Expected a single 16-team Yahoo league")
        league = {"league_key": league_keys.pop()}

        write_credentials()
        oauth = get_oauth()
        refresh_schedule(schedule, team_keys,
                         lambda week: pull_week_scores(oauth, league, week, include_projections=True))
        active_week = current_week(oauth, league)
        if active_week is None:
            active_week = min((game["week"] for game in schedule["upcoming"]), default=17)
        for week in range(REG_SEASON_LAST_WEEK + 1, min(active_week, 17) + 1):
            for row in pull_week_scores(oauth, league, week, include_projections=True):
                if not row["is_playoffs"]:
                    continue
                game = {"season": season, "week": week, "playoff": True,
                        "o1": team_keys[row["team_1_key"]], "o2": team_keys[row["team_2_key"]]}
                scores = {f"p{side}": row[f"team_{side}_points"] for side in (1, 2)}
                if row["status"] == "postevent":
                    game.update(scores)
                    game["winner"] = row.get("winner")
                elif row["status"] in LIVE_STATUSES and all(value is not None for value in scores.values()):
                    game["live"] = {**scores, **{
                        f"projected{side}": row[f"team_{side}_projection"] for side in (1, 2)
                    }}
                postseason.append(game)
        try:
            attach_optimized_projections(schedule["upcoming"], oauth, league["league_key"], team_keys,
                                         season, now, active_week, postseason, playoff_projections)
            if playoff_projections or any(game.get("optimized") for game in schedule["upcoming"]):
                optimized_as_of = now.isoformat(timespec="seconds")
        except (KeyError, TypeError, ValueError, AttributeError, RequestException) as error:
            print(f"Optimized lineup refresh unavailable: {type(error).__name__}: {error}")
    snapshot = {"season": season, **schedule, "postseason": postseason,
                "playoffProjections": playoff_projections}
    if optimized_as_of:
        snapshot["lineupsAsOf"] = optimized_as_of
    previous.pop("asOf", None)
    if snapshot == previous and not schedule["upcoming"]:
        print("No new scores or projections.")
        return
    snapshot["asOf"] = now.isoformat(timespec="seconds")
    SNAPSHOT.write_text(json.dumps(snapshot, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(f"Published {len(schedule['games'])} final and {len(schedule['upcoming'])} remaining matchups.")


if __name__ == "__main__":
    main()
