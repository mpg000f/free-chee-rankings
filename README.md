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
4. `build_owner_share_pages.py` — rebuilds per-owner share pages + preview cards
5. `stamp_cache_bust.py` — re-stamps `?v=<hash>` on CSS/JS

Always run the whole thing via `build.py` rather than individual scripts — the order and the site→docs sync matter.

## Notes / gotchas

- **`docs/` and `site/` are mirrors.** `docs/` is published; `site/` is the build source. `build.py` keeps them in sync. Don't hand-edit only one.
- **Canonical team names** live in `scripts/owner_mapping.py` (`CANONICAL_TEAMS`), keyed by season + owner. When the 2026 names settle, add a `"2026": {...}` block there so names stay uniform across weeks. Without it, new-season names fall back to best-effort cleanup.
- **Last-place counts** are hand-maintained in `lookback.html`'s `stats` array (Yahoo doesn't record them); `build_engagement_data.py` reads them from there.
- **Owner/matchup history** (records, careers) comes from `yahoo_data/` — a separate seasonal pull (`pull_yahoo_data.py`), not the weekly rankings PDFs.
- If a new season's PDF format differs and a week parses wrong, the fix is usually in `scripts/ranking_parser.py` (rank/owner line parsing) or `scripts/pdf_parser.py` (filename/season detection).
