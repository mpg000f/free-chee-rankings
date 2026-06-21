"""Build data for the Head-to-Head, Records, and Careers pages.

Joins Yahoo matchup data to canonical owners (via rosters_data.json) and emits:
  - matchups_all.json : every game with owners (powers the interactive H2H tool)
  - records.json      : precomputed league superlatives
  - careers.json      : per-owner career summary
Outputs to both docs/data and site/data.
"""
import json, os, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASONS = ["2022", "2023", "2024", "2025"]
REG_SEASON_LAST_WEEK = 14  # weeks 15-17 are playoffs

import sys
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from owner_mapping import canonical_team


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return json.load(f)


def build():
    rosters = load("docs", "data", "rosters_data.json")

    # team_key -> owner, and team_key -> display team name, per season
    owner_of = {}
    team_of = {}
    for s in SEASONS:
        owner_of[s], team_of[s] = {}, {}
        for key, t in rosters[s]["teams"].items():
            owner_of[s][key] = t["owner"]
            team_of[s][key] = canonical_team(s, t["owner"]) or t["team_name"]

    # ---- matchups_all: every game with canonical owners ----
    games = []
    for s in SEASONS:
        for m in load("yahoo_data", s, "matchups.json"):
            k1, k2 = m["team_1_key"], m["team_2_key"]
            games.append({
                "season": s, "week": m["week"],
                "playoff": m["week"] > REG_SEASON_LAST_WEEK,
                "o1": owner_of[s][k1], "t1": team_of[s][k1], "p1": round(m["team_1_points"], 2),
                "o2": owner_of[s][k2], "t2": team_of[s][k2], "p2": round(m["team_2_points"], 2),
            })
    games.sort(key=lambda g: (g["season"], g["week"]))
    owners = sorted({g["o1"] for g in games} | {g["o2"] for g in games})

    # ---- records: superlatives over all games ----
    # flatten into per-team performances
    perf = []  # (pts, opp_pts, owner, opp, season, week, won)
    for g in games:
        perf.append((g["p1"], g["p2"], g["o1"], g["o2"], g["season"], g["week"]))
        perf.append((g["p2"], g["p1"], g["o2"], g["o1"], g["season"], g["week"]))

    def rec(pts, opp, owner, oppo, s, w):
        return {"owner": owner, "pts": pts, "opp": oppo, "opp_pts": opp, "season": s, "week": w}

    high = max(perf, key=lambda x: x[0])
    low = min(perf, key=lambda x: x[0])
    most_in_loss = max((p for p in perf if p[0] < p[1]), key=lambda x: x[0])
    fewest_in_win = min((p for p in perf if p[0] > p[1]), key=lambda x: x[0])
    blowout = max(games, key=lambda g: abs(g["p1"] - g["p2"]))
    nailbiter = min((g for g in games if g["p1"] != g["p2"]), key=lambda g: abs(g["p1"] - g["p2"]))
    shootout = max(games, key=lambda g: g["p1"] + g["p2"])
    snoozer = min(games, key=lambda g: g["p1"] + g["p2"])

    # streaks (chronological across all seasons)
    def streaks():
        seq = collections.defaultdict(list)  # owner -> list of (season,week,won)
        for g in games:
            seq[g["o1"]].append((g["season"], g["week"], g["p1"] > g["p2"]))
            seq[g["o2"]].append((g["season"], g["week"], g["p2"] > g["p1"]))
        best_w = {"owner": None, "len": 0}
        best_l = {"owner": None, "len": 0}
        for o, lst in seq.items():
            lst.sort()
            cw = cl = 0
            for _, _, won in lst:
                cw = cw + 1 if won else 0
                cl = 0 if won else cl + 1
                if cw > best_w["len"]:
                    best_w = {"owner": o, "len": cw}
                if cl > best_l["len"]:
                    best_l = {"owner": o, "len": cl}
        return best_w, best_l

    win_streak, lose_streak = streaks()

    # finishes from rosters_data
    champ = collections.Counter()
    lasts = collections.Counter()
    for s in SEASONS:
        for t in rosters[s]["teams"].values():
            if t["summary"].get("playoff_finish") == "Champion":
                champ[t["owner"]] += 1
            if t["summary"].get("standing") == 16:
                lasts[t["owner"]] += 1

    def fmt_blow(g):
        w, l = (g["o1"], g["o2"]) if g["p1"] > g["p2"] else (g["o2"], g["o1"])
        wp, lp = (g["p1"], g["p2"]) if g["p1"] > g["p2"] else (g["p2"], g["p1"])
        return {"winner": w, "loser": l, "win_pts": wp, "lose_pts": lp,
                "margin": round(wp - lp, 2), "season": g["season"], "week": g["week"]}

    records = {
        "highest_score": rec(*high),
        "lowest_score": rec(*low),
        "most_points_in_loss": rec(*most_in_loss),
        "fewest_points_in_win": rec(*fewest_in_win),
        "biggest_blowout": fmt_blow(blowout),
        "closest_game": fmt_blow(nailbiter),
        "highest_scoring_game": {"total": round(shootout["p1"] + shootout["p2"], 2), **fmt_blow(shootout)},
        "lowest_scoring_game": {"total": round(snoozer["p1"] + snoozer["p2"], 2), **fmt_blow(snoozer)},
        "longest_win_streak": win_streak,
        "longest_losing_streak": lose_streak,
        "most_championships": [{"owner": o, "count": c} for o, c in champ.most_common(3)],
        "most_last_place": [{"owner": o, "count": c} for o, c in lasts.most_common(3)],
    }

    # ---- careers: per-owner summary ----
    try:
        owners_hist = load("docs", "data", "owners.json")
    except Exception:
        owners_hist = {}
    try:
        lookback = {e["owner"]: e for e in load("docs", "data", "lookback.json")["entries"]}
    except Exception:
        lookback = {}
    draft = load("docs", "data", "draft_value.json")

    careers = {}
    for o in owners:
        w = l = tie = 0
        pf = pa = 0.0
        h2h = collections.defaultdict(lambda: [0, 0])  # opp -> [wins, losses]
        seasons_played = set()
        for g in games:
            if o not in (g["o1"], g["o2"]):
                continue
            mine, opp_pts, opp = ((g["p1"], g["p2"], g["o2"]) if g["o1"] == o
                                  else (g["p2"], g["p1"], g["o1"]))
            seasons_played.add(g["season"])
            pf += mine; pa += opp_pts
            if mine > opp_pts:
                w += 1; h2h[opp][0] += 1
            elif mine < opp_pts:
                l += 1; h2h[opp][1] += 1
            else:
                tie += 1
        gp = w + l + tie

        # finishes
        champs = finals = semis = lastp = 0
        best_standing = 99
        for s in SEASONS:
            for t in rosters[s]["teams"].values():
                if t["owner"] != o:
                    continue
                fin = t["summary"].get("playoff_finish")
                st = t["summary"].get("standing")
                if fin == "Champion":
                    champs += 1; finals += 1
                elif fin == "Championship Loss":
                    finals += 1
                elif fin == "Semifinal Loss":
                    semis += 1
                if st == 16:
                    lastp += 1
                if st and st < best_standing:
                    best_standing = st

        # biggest rival = most-played opponent
        rival = None
        if h2h:
            ro = max(h2h, key=lambda k: h2h[k][0] + h2h[k][1])
            rival = {"owner": ro, "wins": h2h[ro][0], "losses": h2h[ro][1]}

        # best / worst draft pick across seasons
        picks = [p for s in SEASONS for p in draft[s]["players"] if p["owner"] == o]
        best_pick = max(picks, key=lambda p: p["value"]) if picks else None
        worst_pick = min(picks, key=lambda p: p["value"]) if picks else None

        lb = lookback.get(o, {})
        hist = owners_hist.get(o, {})
        careers[o] = {
            "owner": o,
            "seasons_played": len(seasons_played),
            "wins": w, "losses": l, "ties": tie,
            "win_pct": round(w / gp, 3) if gp else 0,
            "pf": round(pf, 1), "pa": round(pa, 1),
            "ppg": round(pf / gp, 1) if gp else 0,
            "championships": champs, "finals": finals, "semis": semis, "last_places": lastp,
            "best_finish": best_standing if best_standing < 99 else None,
            "avg_power_rank": hist.get("avg_rank"),
            "best_rank": hist.get("best_rank"),
            "rival": rival,
            "best_pick": ({"player": best_pick["player"], "cost": best_pick["cost"],
                           "pts": best_pick["pts"], "value": round(best_pick["value"], 1)}
                          if best_pick else None),
            "worst_pick": ({"player": worst_pick["player"], "cost": worst_pick["cost"],
                            "pts": worst_pick["pts"], "value": round(worst_pick["value"], 1)}
                           if worst_pick else None),
            "power_score": lb.get("power_score"),
            "comparison": lb.get("comparison", ""),
        }

    out = {
        "matchups_all.json": {"owners": owners, "games": games},
        "records.json": records,
        "careers.json": {"owners": owners, "careers": careers},
    }
    for root in ("docs", "site"):
        for fname, payload in out.items():
            path = os.path.join(ROOT, root, "data", fname)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=1)
    return owners, games, records, careers


if __name__ == "__main__":
    owners, games, records, careers = build()
    print(f"owners: {len(owners)} | games: {len(games)}")
    print("\n--- sanity: games per owner ---")
    cnt = collections.Counter()
    for g in games:
        cnt[g["o1"]] += 1; cnt[g["o2"]] += 1
    for o in owners:
        c = careers[o]
        print(f"  {o:8} games={cnt[o]:3} record={c['wins']}-{c['losses']}-{c['ties']} "
              f"ships={c['championships']} ppg={c['ppg']}")
    print("\n--- a few records ---")
    print("  highest:", records["highest_score"])
    print("  blowout:", records["biggest_blowout"])
    print("  win streak:", records["longest_win_streak"])
    print("  championships:", records["most_championships"])
