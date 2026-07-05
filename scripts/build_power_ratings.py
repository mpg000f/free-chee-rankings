"""Forward-looking power ratings.

Predicts how good each team is *going forward* from repeatable skills, not
resume. Components (each z-scored within a season, then recency-weighted):
  Scoring 55%  - regular-season points per game
  Draft   30%  - draft value extracted (from draft_value.json)
  Consist 15%  - low week-to-week scoring volatility

Wins, championships, playoff finishes and points-against are intentionally
ignored (schedule/luck, not skill).

Preseason: pure history prior. In-season: blends the prior with the current
season, current weight growing with games played (w = G/(G+K)); the new
season's draft replaces the historical draft estimate as soon as it's drafted.

Writes data/power_ratings.json to docs/ and site/.
"""
import json, os, collections, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS = {"scoring": 0.55, "draft": 0.30, "consistency": 0.15}
RECENCY = 0.65        # per-season decay for the history prior (recent = heavier)
K = 6                 # games-played half-saturation for in-season blend
FULL_SEASON = 14      # regular-season games per team
SCALE_MEAN, SCALE_SD = 100.0, 15.0


def load(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return json.load(f)


def zmap(values):
    """dict owner->value  ->  dict owner->z-score."""
    if not values:
        return {}
    m = st.mean(values.values())
    sd = st.pstdev(values.values()) or 1.0
    return {o: (v - m) / sd for o, v in values.items()}


def pct_rank(values):
    """dict owner->value -> dict owner->0..100 percentile (highest value = 100)."""
    n = len(values)
    if n <= 1:
        return {o: 50 for o in values}
    order = sorted(values, key=lambda o: values[o])
    return {o: round(100 * i / (n - 1)) for i, o in enumerate(order)}


def season_scores(games, upto_week=None):
    """(season, owner) -> list of regular-season points, optionally capped at a week."""
    out = collections.defaultdict(list)
    for g in games:
        if g["playoff"]:
            continue
        if upto_week is not None and g["week"] > upto_week:
            continue
        out[(g["season"], g["o1"])].append(g["p1"])
        out[(g["season"], g["o2"])].append(g["p2"])
    return out


def season_draft(draft):
    out = collections.defaultdict(float)
    for s, d in draft.items():
        for p in d["players"]:
            out[(s, p["owner"])] += p["value"]
    return out


def component_z(owners, season, scores, draftv, which):
    """z-scores for one component within one season."""
    if which == "scoring":
        vals = {o: st.mean(scores[(season, o)]) for o in owners if scores.get((season, o))}
    elif which == "consistency":
        vals = {o: -(st.pstdev(scores[(season, o)]) / st.mean(scores[(season, o)]))
                for o in owners if len(scores.get((season, o), [])) > 1}
    else:  # draft
        vals = {o: draftv[(season, o)] for o in owners if (season, o) in draftv}
    return zmap(vals)


def prior_component(owners, seasons, per_season_z):
    """recency-weighted average of a component's z across history seasons."""
    out = {}
    for o in owners:
        num = den = 0.0
        for i, s in enumerate(seasons):            # seasons oldest..newest
            w = RECENCY ** (len(seasons) - 1 - i)  # newest gets weight 1
            if o in per_season_z[s]:
                num += w * per_season_z[s][o]; den += w
        out[o] = num / den if den else 0.0
    return out


def build():
    games = load("docs", "data", "matchups_all.json")["games"]
    draft = load("docs", "data", "draft_value.json")

    owners = sorted({g["o1"] for g in games} | {g["o2"] for g in games})
    scores_all = season_scores(games)
    draftv = season_draft(draft)

    game_seasons = sorted({g["season"] for g in games})
    weeks_of = {s: {g["week"] for g in games if g["season"] == s and not g["playoff"]}
                for s in game_seasons}
    complete = {s for s in game_seasons if len(weeks_of[s]) >= FULL_SEASON}
    all_seasons = sorted(set(game_seasons) | set(draft.keys()))

    # target = the in-progress / just-drafted season (not yet complete), if any
    candidates = [s for s in all_seasons if s not in complete]
    target = max(candidates) if candidates else None
    hist = [s for s in all_seasons if s in complete]        # prior seasons

    # ---- history prior (recency-weighted z per component) ----
    prior = {}
    for comp in ("scoring", "draft", "consistency"):
        per = {s: component_z(owners, s, scores_all, draftv, comp) for s in hist}
        prior[comp] = prior_component(owners, hist, per)

    # ---- in-season blend toward the target season ----
    if target is not None:
        g_target = len(weeks_of.get(target, set()))          # regular weeks played
        drafted = target in draft
        w_games = g_target / (g_target + K)
        cur = {}
        for comp in ("scoring", "consistency"):
            cur[comp] = component_z(owners, target, scores_all, draftv, comp) if g_target else {}
        cur["draft"] = component_z(owners, target, scores_all, draftv, "draft") if drafted else {}
        w = {"scoring": w_games, "consistency": w_games, "draft": 1.0 if drafted else 0.0}
        label = f"{target} Week {g_target}" if g_target else f"{target} Preseason"
        through = {"season": target, "week": g_target}
    else:
        w = {"scoring": 0.0, "consistency": 0.0, "draft": 0.0}
        cur = {"scoring": {}, "consistency": {}, "draft": {}}
        nxt = str(int(max(complete)) + 1) if complete else "next"
        label = f"Preseason ({nxt})"
        through = None

    def blended(comp, o):
        p = prior[comp].get(o, 0.0)
        c = cur[comp].get(o, p)          # fall back to prior if no current data
        return (1 - w[comp]) * p + w[comp] * c

    comp_final = {c: {o: blended(c, o) for o in owners} for c in WEIGHTS}
    comp_pct = {c: pct_rank(comp_final[c]) for c in WEIGHTS}

    composite = {o: sum(WEIGHTS[c] * comp_final[c][o] for c in WEIGHTS) for o in owners}
    rating = {o: round(SCALE_MEAN + SCALE_SD * composite[o], 1) for o in owners}

    # movement vs one week ago (in-season only)
    prev_rank = {}
    if target is not None and through["week"] > 0:
        prev_scores = season_scores(games, upto_week=through["week"] - 1)
        pg = through["week"] - 1
        wg = pg / (pg + K)
        pcur = {}
        for comp in ("scoring", "consistency"):
            pcur[comp] = component_z(owners, target, prev_scores, draftv, comp) if pg else {}
        pcur["draft"] = cur["draft"]
        pw = {"scoring": wg, "consistency": wg, "draft": w["draft"]}

        def pblend(comp, o):
            p = prior[comp].get(o, 0.0); c = pcur[comp].get(o, p)
            return (1 - pw[comp]) * p + pw[comp] * c
        pcomposite = {o: sum(WEIGHTS[c] * pblend(c, o) for c in WEIGHTS) for o in owners}
        order = sorted(owners, key=lambda o: -pcomposite[o])
        prev_rank = {o: i + 1 for i, o in enumerate(order)}

    order = sorted(owners, key=lambda o: -rating[o])
    ratings = []
    for i, o in enumerate(order):
        rk = i + 1
        ratings.append({
            "owner": o, "rank": rk, "rating": rating[o],
            "prev_rank": prev_rank.get(o),
            "movement": (prev_rank.get(o) - rk) if prev_rank.get(o) else 0,
            "scoring_pct": comp_pct["scoring"][o],
            "draft_pct": comp_pct["draft"][o],
            "consistency_pct": comp_pct["consistency"][o],
        })

    payload = {
        "label": label,
        "updated_through": through,
        "weights": WEIGHTS,
        "note": ("Forward-looking: rewards scoring and drafting, ignores wins, "
                 "championships and schedule luck."),
        "ratings": ratings,
    }
    for root in ("docs", "site"):
        with open(os.path.join(ROOT, root, "data", "power_ratings.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    return payload


if __name__ == "__main__":
    p = build()
    print(f"{p['label']}  (weights {p['weights']})")
    print(f"{'#':>2} {'Owner':8} {'Rating':>6} {'Scor':>5} {'Draft':>5} {'Cons':>5} {'Mv':>3}")
    for r in p["ratings"]:
        print(f"{r['rank']:>2} {r['owner']:8} {r['rating']:6.1f} "
              f"{r['scoring_pct']:>4}% {r['draft_pct']:>4}% {r['consistency_pct']:>4}% {r['movement']:>+3}")
