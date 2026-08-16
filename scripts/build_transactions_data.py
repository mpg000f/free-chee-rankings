"""Build waiver-pickup and trade-grade data from Yahoo rosters + transactions.

Outputs data/transactions.json to both docs/ and site/.

Why roster diffs instead of the transaction feed: pull_yahoo_data.py saved every
transaction's players with empty `type`/`source_team_key`/`destination_team_key`,
so transactions.json says *what* happened and *when* but never *who* was on
either end. The weekly roster snapshots in rosters.json carry that missing half —
diffing consecutive weeks recovers every add, drop and move, with per-player
weekly points attached. transactions.json is still needed to tell a genuine trade
apart from a same-week drop-and-claim, since both look like a team-to-team move
in the snapshots.

How each half is recovered:
  - Trade week comes from the roster snapshots, not the timestamp. The two agree
    where both are reliable (the 2025 trades dated Oct 9 / Nov 15 / Nov 21 show
    up as reciprocal moves in weeks 6 / 11 / 12), but a date-derived week is off
    by one whenever a season starts late, which misattributes a week of scoring.
  - Preseason trades leave no diff to read — the week-1 snapshot already shows
    the new owner — so their senders come from draft.json instead.
  - Yahoo sometimes logs one multi-team deal as several overlapping rows. The
    2022 blockbuster is recorded as two rows that both move Nyheim Miller-Hines
    and Robert Woods; grading them apart would count those players twice, so
    same-day rows sharing a player are merged into a single N-team trade.

Trades are graded on value over replacement, not raw points. Raw points can't
compare across positions, and in a superflex league that gets trades badly wrong:
a QB and a WR who both score 200 are not the same asset, because the league has
to fill 32 QB slots out of roughly 32 startable NFL quarterbacks while WR40 is
still a useful starter. Every player is therefore measured against what a freely
available player at his own position would have produced over the same weeks, so
a throw-in who merely matches the waiver wire adds nothing to his side's ledger.

Two limitations worth knowing, both surfaced as notes on the page:
  - Points are what a player produced *while rostered*, starter or bench. Yahoo's
    weekly roster payload has no lineup slot, and the team score can't be
    unmixed back into a starting nine, so started-vs-benched is unrecoverable.
  - A player dropped after being acquired stops accruing, which is the honest
    read: the trade or claim delivered nothing further to that manager.
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

from owner_mapping import YAHOO_TEAM_OWNERS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASONS = ["2022", "2023", "2024", "2025"]
FINAL_WEEK = 17

# Week 1 kickoff per season, used only to date-estimate a trade week when the
# roster snapshots show no move (both players dropped straight after the deal).
KICKOFF = {
    "2022": datetime(2022, 9, 8, tzinfo=timezone.utc),
    "2023": datetime(2023, 9, 7, tzinfo=timezone.utc),
    "2024": datetime(2024, 9, 5, tzinfo=timezone.utc),
    "2025": datetime(2025, 9, 4, tzinfo=timezone.utc),
}

# League-wide starting slots per position (16 teams, superflex). The player one
# past this rank is the best a manager could expect to find on the wire, which is
# what every traded player is measured against.
STARTER_SLOTS = {"QB": 32, "RB": 40, "WR": 40, "TE": 16, "K": 16, "DEF": 16}

# Weeks rostered before a player's scoring rate is trusted to set the baseline.
# Too low and a one-week cameo sets replacement level; too high and the ranking
# runs out of players before reaching the slot count. Six holds steady across all
# four seasons and keeps the positions in a consistent order.
REPLACEMENT_MIN_WEEKS = 6

# Net value over replacement per remaining week -> letter grade. Normalizing by
# weeks left keeps a week-12 swap from looking tame beside an identical week-2
# one. The bands are symmetric so that in a two-team deal one side's grade
# mirrors the other's.
GRADE_BANDS = [(5.0, "A"), (2.0, "B"), (-2.0, "C"), (-5.0, "D")]


def load(season, name):
    path = os.path.join(ROOT, "yahoo_data", season, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def grade_for(net_per_week):
    for threshold, letter in GRADE_BANDS:
        if net_per_week >= threshold:
            return letter
    return "F"


def replacement_rates(rosters):
    """Points per week a freely available player would have given, by position.

    Ranks every rostered player at a position by his scoring rate and reads off
    the one sitting just past the league's starting slots — the marginal startable
    player, and so the bar a traded player has to clear to be worth anything. The
    gaps between positions are the scarcity the raw point totals miss.
    """
    totals = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    for row in rosters:
        for pos in (row.get("display_position") or "").split(","):
            if pos in STARTER_SLOTS:
                entry = totals[pos][row["player_key"]]
                entry[0] += row.get("points") or 0.0
                entry[1] += 1

    rates = {}
    for pos, players in totals.items():
        ranked = sorted((pts / weeks for pts, weeks in players.values()
                         if weeks >= REPLACEMENT_MIN_WEEKS), reverse=True)
        if not ranked:
            continue
        slots = STARTER_SLOTS[pos]
        rates[pos] = round(ranked[slots] if len(ranked) > slots else ranked[-1], 2)
    return rates


def build_season_index(season):
    """Weekly roster state, per-player weekly points, and draft origin."""
    rosters = load(season, "rosters.json") or []
    managers = load(season, "managers.json") or {}
    name_to_owner = YAHOO_TEAM_OWNERS.get(season, {})

    owner_of = {}
    for team_key, info in managers.items():
        owner = name_to_owner.get(info.get("team_name", ""))
        if owner:
            owner_of[team_key] = owner

    holder = defaultdict(dict)   # week -> player_key -> team_key
    points = {}                  # (week, player_key) -> points
    meta = {}                    # player_key -> (name, position)
    for row in rosters:
        week, pkey = row["week"], row["player_key"]
        holder[week][pkey] = row["team_key"]
        points[(week, pkey)] = row.get("points") or 0.0
        meta[pkey] = (row["player_name"], row.get("display_position") or "")

    key_of = {}
    for pkey, (name, _pos) in meta.items():
        key_of.setdefault(name, pkey)

    drafted_by = {}
    for pick in load(season, "draft.json") or []:
        pkey = pick.get("player_key") or key_of.get(pick.get("player_name"))
        if pkey:
            drafted_by[pkey] = pick["team_key"]

    return {
        "season": season,
        "weeks": sorted(holder),
        "holder": holder,
        "points": points,
        "meta": meta,
        "key_of": key_of,
        "drafted_by": drafted_by,
        "owner_of": owner_of,
        "baseline": replacement_rates(rosters),
    }


def slot_position(idx, pkey):
    """The position a player is graded at, and the replacement rate there.

    Multi-eligible players (Taysom Hill's "QB,TE") are slotted where they help
    most, which is the position with the *lowest* bar to clear — the same call a
    manager makes when filling a lineup.
    """
    eligible = [p for p in (idx["meta"][pkey][1] or "").split(",") if p in idx["baseline"]]
    if not eligible:
        return (idx["meta"][pkey][1] or "").split(",")[0], 0.0
    pos = min(eligible, key=lambda p: idx["baseline"][p])
    return pos, idx["baseline"][pos]


def points_while_rostered(idx, pkey, team_key, from_week):
    """Points a player produced for one team from a week onward, plus weeks held.

    Stops at the first week the player is no longer on that roster, so a player
    who is dropped or flipped again does not keep earning for the acquirer.
    """
    total, weeks = 0.0, 0
    for week in range(from_week, FINAL_WEEK + 1):
        if idx["holder"].get(week, {}).get(pkey) != team_key:
            break
        total += idx["points"].get((week, pkey), 0.0)
        weeks += 1
    return round(total, 2), weeks


def points_in_window(idx, pkey, from_week):
    """What a player produced from a week onward, whoever was rostering him.

    Trades are graded on this rather than on the acquirer's holding period. Both
    halves of a deal have to be measured over the same weeks or the comparison is
    meaningless: in the 2022 Kupp deal one side re-traded him after four games
    while the other carried two busts for seventeen, which made a raw
    while-rostered read call the wrong winner. Weeks where nobody in the league
    rostered him count as zero — 92% of post-trade weeks have a roster row, and
    the ones that don't are players who were injured out of the season.
    """
    return round(sum(idx["points"].get((week, pkey), 0.0)
                     for week in range(from_week, FINAL_WEEK + 1)), 2)


def move_weeks(idx, pkey):
    """Weeks where a player changed teams between consecutive snapshots."""
    weeks = []
    for week in range(2, FINAL_WEEK + 1):
        before = idx["holder"].get(week - 1, {}).get(pkey)
        after = idx["holder"].get(week, {}).get(pkey)
        if before and after and before != after:
            weeks.append(week)
    return weeks


# --------------------------------------------------------------------------
# Trades
# --------------------------------------------------------------------------

def merge_same_day_trades(idx, transactions):
    """Group trade rows into deals, merging same-day rows that share a player.

    Yahoo splits some multi-team trades across rows; the shared player is the
    tell. Returns a list of (timestamp, [player_name]) with players deduped.
    """
    rows = []
    for txn in transactions:
        if txn.get("type") != "trade" or txn.get("status") != "successful":
            continue
        names = [p["player_name"] for p in txn.get("players", [])]
        day = datetime.fromtimestamp(int(txn["timestamp"]), tz=timezone.utc).date()
        rows.append({"ts": int(txn["timestamp"]), "day": day, "names": names})

    deals = []
    for row in sorted(rows, key=lambda r: r["ts"]):
        for deal in deals:
            if deal["day"] == row["day"] and set(deal["names"]) & set(row["names"]):
                deal["names"].extend(n for n in row["names"] if n not in deal["names"])
                break
        else:
            deals.append({"ts": row["ts"], "day": row["day"], "names": list(row["names"])})
    return deals


def resolve_deal(idx, deal):
    """Recover the week, and who sent and received each player, for one deal."""
    legs = [{"name": n, "pkey": idx["key_of"].get(n)} for n in deal["names"]]
    legs = [l for l in legs if l["pkey"]]
    if not legs:
        return None

    # Date fixes the window, roster snapshots fix the week inside it. Neither
    # alone is enough: the date can be off by one around a week boundary, and a
    # player's move list also holds the moves from every *other* trade he was in.
    traded_at = datetime.fromtimestamp(deal["ts"], tz=timezone.utc)
    kickoff = KICKOFF.get(idx["season"])
    preseason = kickoff is None or traded_at < kickoff

    if preseason:
        week = 1
    else:
        estimate = min(FINAL_WEEK, (traded_at - kickoff).days // 7 + 1)
        # A trade takes effect at its own week or the next one, never earlier.
        window = {estimate, estimate + 1}
        observed = sorted(w for l in legs for w in move_weeks(idx, l["pkey"])
                          if w in window)
        week = observed[0] if observed else estimate

    for leg in legs:
        pkey = leg["pkey"]
        if preseason:
            # No diff to read: week 1 already shows the buyer, draft shows the seller.
            leg["to"] = idx["holder"].get(1, {}).get(pkey)
            leg["from"] = idx["drafted_by"].get(pkey)
        else:
            # Last team to hold him, not strictly the previous week — a player
            # benched off a roster before the deal still has a seller.
            leg["from"] = next(
                (idx["holder"][w][pkey] for w in range(week - 1, 0, -1)
                 if idx["holder"].get(w, {}).get(pkey)), None)
            leg["to"] = idx["holder"].get(week, {}).get(pkey)
            if leg["to"] == leg["from"]:
                leg["to"] = None  # dropped before the snapshot; placed below

    teams = {t for l in legs for t in (l["from"], l["to"]) if t}
    if len(teams) < 2:
        return None

    # A player dropped straight after the deal has no destination snapshot. In a
    # two-team trade the other side is unambiguous; with more teams it is not.
    for leg in legs:
        if leg["to"] is None and len(teams) == 2 and leg["from"] in teams:
            leg["to"] = next(t for t in teams if t != leg["from"])
    legs = [l for l in legs if l["from"] in teams and l["to"] in teams]
    if not legs:
        return None
    teams = {t for l in legs for t in (l["from"], l["to"])}

    weeks_remaining = max(1, FINAL_WEEK - week + 1)
    sides = []
    for team in sorted(teams):
        owner = idx["owner_of"].get(team)
        if not owner:
            return None
        received, sent = [], []
        for leg in legs:
            pts = points_in_window(idx, leg["pkey"], week)
            _, held = points_while_rostered(idx, leg["pkey"], leg["to"], week)
            pos, repl = slot_position(idx, leg["pkey"])
            par = round(repl * weeks_remaining, 2)
            entry = {
                "player": leg["name"],
                "pos": pos,
                "pts": pts,
                "weeks_rostered": held,
                # What a waiver body at this position would have given over the
                # same weeks. Surplus floors at zero: a player who came back
                # below that bar could simply be dropped for one who cleared it,
                # so the worst an acquisition can be worth is nothing, never less.
                "repl": par,
                "vor": max(0.0, round(pts - par, 2)),
            }
            if leg["to"] == team:
                received.append(entry)
            elif leg["from"] == team:
                sent.append({**entry, "to_owner": idx["owner_of"].get(leg["to"], "")})
        received.sort(key=lambda r: -r["vor"])
        sent.sort(key=lambda r: -r["vor"])
        got = round(sum(r["pts"] for r in received), 2)
        gave = round(sum(r["pts"] for r in sent), 2)
        vor_in = round(sum(r["vor"] for r in received), 2)
        vor_out = round(sum(r["vor"] for r in sent), 2)
        sides.append({
            "owner": owner,
            "received": received,
            "sent": sent,
            "pts": got,
            "gave": gave,
            "net_pts": round(got - gave, 2),
            "vor_in": vor_in,
            "vor_out": vor_out,
            "net": round(vor_in - vor_out, 2),
        })

    for side in sides:
        side["grade"] = grade_for(side["net"] / weeks_remaining)
    best = max(sides, key=lambda s: s["net"])

    return {
        "date": datetime.fromtimestamp(deal["ts"], tz=timezone.utc).strftime("%b %d, %Y").replace(" 0", " "),
        "week": week,
        "preseason": preseason,
        "weeks_remaining": weeks_remaining,
        "teams": len(sides),
        "sides": sorted(sides, key=lambda s: -s["net"]),
        "net": abs(round(best["net"], 2)),
        "winner": best["owner"] if abs(best["net"]) > 0.01 else None,
    }


# --------------------------------------------------------------------------
# Waiver pickups
# --------------------------------------------------------------------------

def find_pickups(idx, trade_players):
    """Free-agent adds and waiver claims, week by week.

    Counts both a pickup from the open pool and a claim on a player another team
    dropped that same week — both are the waiver wire doing its job. Trade legs
    are excluded, since those move between teams without touching waivers.
    Week 1 is skipped: every week-1 roster spot traces to the draft or to
    preseason moves, neither of which is a waiver claim.
    """
    pickups = []
    for week in idx["weeks"]:
        if week < 2:
            continue
        prev = idx["holder"].get(week - 1, {})
        for pkey, tkey in idx["holder"].get(week, {}).items():
            if prev.get(pkey) == tkey:
                continue                       # unchanged
            if (pkey, week) in trade_players:
                continue                       # arrived via trade
            owner = idx["owner_of"].get(tkey)
            if not owner:
                continue
            pts, held = points_while_rostered(idx, pkey, tkey, week)
            name = idx["meta"][pkey][0]
            pos, repl = slot_position(idx, pkey)
            pickups.append({
                "player": name,
                "pos": pos,
                "owner": owner,
                "week": week,
                "pts": pts,
                "vor": round(pts - repl * held, 2),
                "weeks_rostered": held,
                "ppg": round(pts / held, 2) if held else 0.0,
                "claimed": pkey in prev,       # taken off another roster's scrap heap
                "held_to_end": week + held - 1 >= FINAL_WEEK,
            })
    pickups.sort(key=lambda p: -p["pts"])
    return pickups


def build_season(season):
    idx = build_season_index(season)
    if not idx["weeks"]:
        return None

    trades, skipped = [], 0
    for deal in merge_same_day_trades(idx, load(season, "transactions.json") or []):
        resolved = resolve_deal(idx, deal)
        if resolved:
            trades.append(resolved)
        else:
            skipped += 1
            print(f"    {season}: unresolvable trade omitted ({', '.join(deal['names'])})")
    trades.sort(key=lambda t: t["week"])

    # Players that changed hands by trade, so waiver detection can skip them.
    trade_players = set()
    for trade in trades:
        for side in trade["sides"]:
            for entry in side["received"]:
                pkey = idx["key_of"].get(entry["player"])
                if pkey:
                    trade_players.add((pkey, trade["week"]))

    pickups = find_pickups(idx, trade_players)
    return {
        "pickups": pickups,
        "trades": trades,
        "owners": sorted({p["owner"] for p in pickups}),
        "skipped_trades": skipped,
        "replacement": idx["baseline"],
    }


def main():
    payload = {"seasons": [], "data": {}}
    for season in SEASONS:
        built = build_season(season)
        if not built:
            continue
        payload["seasons"].append(season)
        payload["data"][season] = built
        print(f"  {season}: {len(built['pickups'])} pickups, {len(built['trades'])} trades")

    for root in ("docs", "site"):
        out_dir = os.path.join(ROOT, root, "data")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "transactions.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print(f"  wrote {root}/data/transactions.json")


if __name__ == "__main__":
    main()
