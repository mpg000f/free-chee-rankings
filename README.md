# Free Chee Headquarters

The league site at **https://mpg000f.github.io/free-chee-rankings/**, published from the `docs/` folder via GitHub Pages.

## Adding a new week's rankings (the weekly routine)

1. **Drop the PDF in the repo root** using the existing naming convention, including the year:
   - `Free Chee Week 3 Power Rankings 2026.pdf`
   - `Free Chee Week Final Power Rankings 2026.pdf`
   - `Free Chee Midseason Review Week 8 2026.pdf`

   The year in the filename sets the season. (Early-2024 PDFs have no year and default to 2024 — leave those alone.)

2. **Build the site:**
   ```
   python3 scripts/build.py
   ```

3. **Review, commit, push:**
   ```
   git status
   git add -A
   git commit -m "Add Week N 2026 rankings"
   git push
   ```

GitHub Pages redeploys in 1–2 minutes. Cache-busting means visitors pick up changes automatically (worst case a ~10-minute lag for someone mid-session).

## What `scripts/build.py` does

1. `generate_site_data.py` — parses every root PDF into `site/data` + `site/images`
2. syncs `site/{data,images}` → `docs/{data,images}` (docs/ is what Pages serves)
3. `build_engagement_data.py` — rebuilds Head-to-Head / League Records / Player Profiles data
4. `build_transactions_data.py` — rebuilds the Waivers & Trades page data from `yahoo_data/`
5. `build_owner_share_pages.py` — rebuilds per-owner share pages + preview cards
6. `stamp_cache_bust.py` — re-stamps `?v=<hash>` on CSS/JS

Always run the whole thing via `build.py` rather than individual scripts — the order and the site→docs sync matter.

## Notes / gotchas

- **`docs/` and `site/` are mirrors.** `docs/` is published; `site/` is the build source. `build.py` keeps them in sync. Don't hand-edit only one.
- **Canonical team names** live in `scripts/owner_mapping.py` (`CANONICAL_TEAMS`), keyed by season + owner, so names stay uniform across every week of a season. Without a block for the season, names fall back to best-effort cleanup.
- **Adding or replacing an owner** touches `scripts/owner_mapping.py` only: `ALL_OWNERS` (the all-time list — 17 names for a 16-team league, since Kevin replaced Papi in 2026), `SEASON_OWNERS` (who actually played, listed only where it differs from the original 16), `CANONICAL_TEAMS`, and `YAHOO_TEAM_OWNERS`. `ranking_parser.KNOWN_OWNERS` derives from `ALL_OWNERS`, so it needs no edit. Departed owners stay in every mapping — removing Papi would break four seasons of history.
- **New team names must also be added to `ranking_parser.TEAM_OWNER_MAP`**, which is what actually resolves an owner from a weekly PDF. It's a lowercase prefix match, so add a short variant alongside the full name where a PDF might truncate. Weeks where the PDF omits the owner resolve *only* through this map — a missing rename silently produces an unowned team.
- **Last-place counts** are hand-maintained in `lookback.html`'s `stats` array (Yahoo doesn't record them); `build_engagement_data.py` reads them from there.
- **Owner/matchup history** (records, careers) comes from `yahoo_data/` — a separate seasonal pull (`pull_yahoo_data.py`), not the weekly rankings PDFs.
- **Playoff round labels** (Quarterfinal / Semifinal / Championship / placement games) on the Schedule page are *derived*, not pulled — Yahoo's `is_playoffs`/`is_consolation` flags were never captured by `pull_yahoo_data.py`. `build_engagement_data.py` reads each team's win/loss path through weeks 15–17, which is unambiguous because every round pairs teams with identical records, then cross-checks the result against the authoritative `playoff_finish` in `rosters_data.json`. If a season ever breaks the 8-team/3-week format, the build prints a warning and emits no round labels for that season rather than guessing — the Schedule page falls back to a plain "Playoffs" grouping.
- **Waivers & Trades** (`transactions.html`) is derived, not pulled. `pull_yahoo_data.py` saved every transaction's players with empty `type`/`source_team_key`/`destination_team_key`, so the transaction feed says *what* happened and *when* but never *who* was on either end. `build_transactions_data.py` recovers the missing half by diffing consecutive weekly roster snapshots in `yahoo_data/<season>/rosters.json`, which also carry each player's weekly points. The feed is still needed to tell a real trade from a same-week drop-and-claim, since both look identical in the snapshots. Three wrinkles it handles: trade weeks come from the snapshots rather than the timestamp (a date-derived week is off by one whenever a season starts late); preseason trades leave no diff to read, so their senders come from `draft.json`; and Yahoo logs some multi-team deals as several overlapping rows, so same-day rows sharing a player are merged into one N-team trade. If `pull_yahoo_data.py` is ever fixed to capture the per-player transaction fields, most of this can be replaced with a direct read.
- **What the Waivers & Trades numbers mean.** A player's value is the points he produced *while on that manager's roster* from the week he arrived; drop him and the counter stops. Yahoo's weekly roster payload records no lineup slot and the team score can't be unmixed back into a starting nine, so bench points count the same as starting points — this is stated on the page itself. Trade grades compare points received against points sent away, normalized per week left in the season, on symmetric bands (A/B/C/D/F) so one side's A is the other's F.
- **Draft History** (`draft-history.html`) has no data file of its own — it groups `data/draft_value.json` by player name in the browser, so it stays in sync with the Draft Value page automatically. `?q=<name>` deep-links to a player and auto-expands his row. Coverage is 998 of the 1,024 picks ever made; the 26 absent were drafted and cut before appearing on any weekly roster, so no position or points can be derived for them.
- **Kickers are included in draft value** and are exempt from the `cost <= 3` cheap-pick cap in `build_roster_stats.py`. That cap exists because the model over-predicts cheap skill-position fliers, but essentially the entire kicker position goes for $1–3, so applying it credited every kicker ~23 free points and floated them near the top of the board. Adding K was purely additive — no other position's numbers moved.
- **`build_roster_stats.py` is not part of `build.py`.** It reads `yahoo_data/` and writes `site/data/{rosters_data,draft_value}.json`, so it only needs re-running after a new Yahoo pull — then run `build.py` to sync `site/` → `docs/`. It is idempotent: re-running it on unchanged input reproduces both files byte-for-byte.
- **The navbar collapses below 1240px** (`site/js/nav-menu.js` + the mobile-nav block in `style.css`). The full bar needs 1240px to lay out 12 links; under that they go behind a toggle, which is what makes the site usable on a phone — before it, only 4 of 12 links were reachable. Adding a link now only costs desktop width: measure `navLinks.scrollWidth - navLinks.clientWidth` at 1240px, and if it clips, either shorten a label or raise `BAR_FITS_ABOVE` in `nav-menu.js` and the matching `max-width` in the CSS together — they must stay in step.
- If a new season's PDF format differs and a week parses wrong, the fix is usually in `scripts/ranking_parser.py` (rank/owner line parsing) or `scripts/pdf_parser.py` (filename/season detection).
