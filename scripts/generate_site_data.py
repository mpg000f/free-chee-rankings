"""Master script: parse all PDFs and generate JSON data + HTML content for the site."""

import os
import sys
import json
import re
import html
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from pdf_parser import extract_full_text, extract_images, parse_filename
from ranking_parser import parse_rankings

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PDF_DIR = BASE_DIR
SITE_DIR = os.path.join(BASE_DIR, "site")
DATA_DIR = os.path.join(SITE_DIR, "data")
IMG_DIR = os.path.join(SITE_DIR, "images")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

# ===== IMAGE OVERRIDES =====
# Images to skip entirely (by filename substring match)
SKIP_IMAGES = {
    "2024_week_15_p7_1",   # Excel rankings history screenshot
    "2025_week_13_p2_1",   # Zach Wilson / JJ McCarthy picture
    "2025_week_4_p9_1",    # CJ Stroud vs Caleb Williams comparison
    "2025_week_8_p3_1",    # Nathan Peterman stats screenshot (data already in table)
    "2025_week_13_p5_1",   # Power trios chart screenshot (replaced with HTML)
    "2025_week_13_p6_1",   # Power trios table screenshot (replaced with HTML)
}

# Images to force into a specific owner's section (filename substring → owner name)
IMAGE_OWNER_OVERRIDE = {
    "2025_week_7_p5_1": "Connor",  # #1 pick FPPG graph
    "2025_week_7_p5_2": "Connor",
    "2025_week_7_p5_3": "Connor",
    "2025_week_12_p3_1": "Mitch",  # Power trios chart
    "2025_week_12_p3_2": "Mitch",  # Power trios table
    "2025_week_14_p4_1": "Mitch",  # Power trios chart
    "2025_week_14_p4_2": "Mitch",  # Power trios table
}

# Special sections to remove entirely (by section name regex)
REMOVE_SECTIONS = {
    "2025-final": [r'(?i)^playoff bracket$', r'(?i)^mud eater bracket$',
                   r'(?i)^playoff preview$', r'(?i)^second round$',
                   r'(?i)^final round$', r'(?i)^relegation preview$'],
    "2024-week-14": [r'(?i)^matchup previews?$'],
    "2024-week-15": [r'(?i)^matchup previews?$', r'(?i)^rankings history'],
}

# ===== POWER TRIOS DATA (transcribed from PDF screenshots) =====
POWER_TRIOS = {
    "2025-week-8": [
        ("Scampi", "Jonathan Taylor (258.9)", "Sam Darnold (148.4)", "Davante Adams (131.8)", 539.1),
        ("Sweeney Deez and Zaukas", "Drake Maye (212.2)", "Dak Prescott (174.9)", "Ja'Marr Chase (149.7)", 536.8),
        ("Pigs on the 7th Rank", "Patrick Mahomes (211.5)", "Caleb Williams (185.2)", "Rico Dowdle (138.0)", 534.7),
        ("Cookie Monster Golf Cart", "De'Von Achane (189.0)", "Baker Mayfield (165.5)", "Jaxon Dart (163.4)", 517.9),
        ("The Art of the Deal", "Justin Herbert (210.8)", "Josh Jacobs (162.5)", "Javonte Williams (143.4)", 516.7),
        ("Work Ass", "Bo Nix (193.5)", "Jaxon Smith-Njigba (165.8)", "Trevor Lawrence (150.1)", 509.4),
        ("Stewed C", "Matthew Stafford (190.2)", "Jalen Hurts (186.8)", "Derrick Henry (112.4)", 489.4),
        ("Ginny Sack", "Christian McCaffrey (214.3)", "Kyren Williams (138.6)", "Drake London (131.6)", 484.5),
        ("The Jackson Brownes", "Josh Allen (209.7)", "Bijan Robinson (158.1)", "Michael Penix Jr. (115.4)", 483.2),
        ("Team Daniel", "Daniel Jones (199.7)", "Jahmyr Gibbs (168.0)", "Jayden Daniels (113.6)", 481.3),
        ("Gorlock the destroyer Schwartz", "Puka Nacua (146.0)", "Trey McBride (126.8)", "Geno Smith (116.6)", 389.4),
        ("Sweeney.", "Puka Nacua (146.0)", "Trey McBride (126.8)", "Geno Smith (116.6)", 389.4),
        ("Champagne Suitcase", "Jared Goff (164.7)", "Travis Etienne Jr. (113.1)", "Spencer Rattler (103.6)", 381.4),
        ("Senior AI Coke Twins", "Aaron Rodgers (142.9)", "Saquon Barkley (127.4)", "Tucker Kraft (101.2)", 371.5),
        ("Life with Derrick", "C.J. Stroud (126.0)", "Michael Pittman Jr. (123.0)", "D'Andre Swift (114.9)", 363.9),
        ("Team OBAMA SOPRANOS", "Lamar Jackson (136.6)", "Tyler Warren (111.3)", "Jordan Mason (76.8)", 324.7),
    ],
    "2025-week-12": [
        ("Scampi", "Jonathan Taylor", "Sam Darnold", "Davante Adams", 539.1),
        ("Sweeney Deez and Zaukas", "Drake Maye", "Dak Prescott", "Ja'Marr Chase", 536.8),
        ("Pigs on the 7th Rank", "Patrick Mahomes", "Caleb Williams", "Rico Dowdle", 534.7),
        ("Cookie Monster Golf Cart", "De'Von Achane", "Baker Mayfield", "Jaxon Dart", 517.9),
        ("The Art of the Deal", "Justin Herbert", "Josh Jacobs", "Javonte Williams", 516.7),
        ("Work Ass", "Bo Nix", "Jaxon Smith-Njigba", "Trevor Lawrence", 509.4),
        ("Stewed C", "Matthew Stafford", "Jalen Hurts", "Derrick Henry", 489.4),
        ("Ginny Sack", "Christian McCaffrey", "Kyren Williams", "Drake London", 484.5),
        ("The Jackson Brownes", "Josh Allen", "Bijan Robinson", "Michael Penix Jr.", 483.2),
        ("Team Daniel", "Daniel Jones", "Jahmyr Gibbs", "Jayden Daniels", 481.3),
        ("Gorlock the destroyer Schwartz", "Jordan Love", "Amon-Ra St. Brown", "Justin Fields", 425.2),
        ("Sweeney.", "Puka Nacua", "Trey McBride", "Geno Smith", 389.4),
        ("Champagne Suitcase", "Jared Goff", "Travis Etienne Jr.", "Spencer Rattler", 381.4),
        ("Senior AI Coke Twins", "Aaron Rodgers", "Saquon Barkley", "Tucker Kraft", 371.5),
        ("Life with Derrick", "C.J. Stroud", "Michael Pittman Jr.", "D'Andre Swift", 363.9),
        ("Team OBAMA SOPRANOS", "Lamar Jackson", "Tyler Warren", "Jordan Mason", 324.7),
    ],
    "2025-week-13": [
        ("Sweeney Deez and Zaukas", "Drake Maye (227.6)", "Dak Prescott (199.2)", "Ja'Marr Chase (154.2)", 581.0),
        ("The Jackson Brownes", "Josh Allen (254.3)", "Bijan Robinson (186.4)", "Michael Penix Jr. (123.3)", 564.0),
        ("Pigs on the 7th Rank", "Patrick Mahomes (225.8)", "Jahmyr Gibbs (185.1)", "Rico Dowdle (150.5)", 561.4),
        ("Cookie Monster Golf Cart", "De'Von Achane (208.0)", "Baker Mayfield (183.3)", "Jaxon Dart (163.4)", 554.7),
        ("Work Ass", "Bo Nix (206.1)", "Jaxon Smith-Njigba (181.9)", "Trevor Lawrence (166.1)", 554.1),
        ("Scampi", "Jonathan Taylor (258.9)", "Sam Darnold (156.6)", "Davante Adams (138.4)", 553.9),
        ("Ginny Sack", "Christian McCaffrey (246.9)", "Kyren Williams (154.7)", "Drake London (147.0)", 548.6),
        ("The Art of the Deal", "Justin Herbert (215.1)", "Josh Jacobs (166.5)", "George Pickens (161.8)", 543.4),
        ("Stewed C", "Matthew Stafford (203.4)", "Jalen Hurts (201.3)", "Derrick Henry (131.6)", 536.3),
        ("Team Daniel", "Daniel Jones (199.7)", "Caleb Williams (195.6)", "Jayden Daniels (113.6)", 508.9),
        ("Gorlock the destroyer Schwartz", "Jordan Love (168.3)", "Amon-Ra St. Brown (155.4)", "Justin Fields (143.7)", 467.4),
        ("Sweeney.", "Puka Nacua (156.8)", "Trey McBride (149.3)", "Geno Smith (130.5)", 436.6),
        ("Champagne Suitcase", "Jared Goff (177.8)", "Travis Etienne Jr. (132.4)", "TreVeyon Henderson (112.7)", 422.9),
        ("Senior AI Coke Twins", "Aaron Rodgers (152.4)", "Saquon Barkley (136.9)", "Kenneth Walker III (104.3)", 393.6),
        ("Life with Derrick", "Bryce Young (135.8)", "C.J. Stroud (126.0)", "D'Andre Swift (123.9)", 385.7),
        ("Team OBAMA SOPRANOS", "Lamar Jackson (143.3)", "Tyler Warren (111.3)", "Tre Tucker (102.8)", 357.4),
    ],
    "2025-week-14": [
        ("Pigs on the 7th Rank", "Patrick Mahomes (243.9)", "Jahmyr Gibbs (235.0)", "Rico Dowdle (159.9)", 638.8),
        ("Sweeney Deez and Zaukas", "Drake Maye (244.6)", "Dak Prescott (227.2)", "Ja'Marr Chase (154.2)", 626.0),
        ("Stewed C", "Jalen Hurts (232.2)", "Matthew Stafford (226.3)", "Derrick Henry (153.4)", 611.9),
        ("Work Ass", "Jaxon Smith-Njigba (215.0)", "Bo Nix (206.1)", "Trevor Lawrence (186.3)", 607.4),
        ("Scampi", "Jonathan Taylor (266.5)", "Sam Darnold (174.3)", "Davante Adams (159.1)", 599.9),
        ("The Jackson Brownes", "Josh Allen (264.5)", "Bijan Robinson (200.1)", "Michael Penix Jr. (123.3)", 587.9),
        ("Ginny Sack", "Christian McCaffrey (270.6)", "Kyren Williams (160.0)", "Drake London (147.0)", 577.6),
        ("The Art of the Deal", "Justin Herbert (215.1)", "George Pickens (186.9)", "Josh Jacobs (166.5)", 568.5),
        ("Cookie Monster Golf Cart", "De'Von Achane (208.0)", "Baker Mayfield (188.8)", "Jaxon Dart (163.4)", 560.2),
        ("Team Daniel", "Caleb Williams (217.2)", "Daniel Jones (216.5)", "Jayden Daniels (113.6)", 547.3),
        ("Gorlock the destroyer Schwartz", "Amon-Ra St. Brown (180.8)", "Jordan Love (175.4)", "Justin Fields (143.7)", 499.9),
        ("Sweeney.", "Puka Nacua (170.0)", "Trey McBride (161.7)", "Geno Smith (144.7)", 476.4),
        ("Champagne Suitcase", "Jared Goff (196.0)", "Travis Etienne Jr. (151.5)", "TreVeyon Henderson (122.3)", 469.8),
        ("Senior AI Coke Twins", "Aaron Rodgers (152.4)", "Saquon Barkley (145.8)", "Kenneth Walker III (115.9)", 414.1),
        ("Life with Derrick", "Bryce Young (146.0)", "Michael Pittman Jr. (134.2)", "C.J. Stroud (126.0)", 406.2),
        ("Team OBAMA SOPRANOS", "Lamar Jackson (150.5)", "Tyler Warren (118.3)", "Tre Tucker (107.1)", 375.9),
    ],
}


def get_display_label(file_info):
    """Get a nice display label for a week."""
    season = file_info["season"]
    week = file_info["week"]
    doc_type = file_info["type"]

    if doc_type == "lookback":
        return "First Term Lookback"
    elif doc_type == "midseason":
        return f"Midseason Review"
    elif doc_type == "final":
        return f"Final Rankings"
    elif doc_type == "playoff_preview":
        return f"Week {week} + Playoff Preview"
    else:
        return f"Week {week}"


def get_week_id(file_info):
    """Get a unique ID for URL hashing."""
    season = file_info["season"]
    week = file_info["week"]
    doc_type = file_info["type"]

    if doc_type == "lookback":
        return "lookback"
    elif doc_type == "midseason":
        return f"{season}-midseason"
    elif doc_type == "final":
        return f"{season}-final"
    else:
        return f"{season}-week-{week}"


def _render_power_trios_table(data):
    """Render power trios data as an HTML table."""
    rows = ""
    for team, p1, p2, p3, total in data:
        rows += f"<tr><td>{html.escape(team)}</td><td>{html.escape(p1)}</td><td>{html.escape(p2)}</td><td>{html.escape(p3)}</td><td><strong>{total}</strong></td></tr>\n"
    return f'''<table class="odds-table">
<thead><tr><th>Team</th><th>Player 1</th><th>Player 2</th><th>Player 3</th><th>Total</th></tr></thead>
<tbody>{rows}</tbody>
</table>'''


_trios_chart_counter = 0

def _render_power_trios_chart(data, week_id):
    """Render power trios data as an inline Chart.js horizontal bar chart."""
    global _trios_chart_counter
    _trios_chart_counter += 1
    canvas_id = f"trios-chart-{week_id}-{_trios_chart_counter}"

    # Build JS data arrays
    labels = json.dumps([team for team, *_ in data])
    totals = json.dumps([total for *_, total in data])

    return f'''<div class="trios-chart-wrapper" style="max-width:800px;margin:1em auto;">
<canvas id="{canvas_id}" height="400"></canvas>
</div>
<script>
(function() {{
  const ctx = document.getElementById('{canvas_id}');
  if (!ctx) return;
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: {labels},
      datasets: [{{
        label: 'Total FPPG (Top 3 Players)',
        data: {totals},
        backgroundColor: 'rgba(245, 166, 35, 0.7)',
        borderColor: '#f5a623',
        borderWidth: 1
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
        title: {{ display: false }}
      }},
      scales: {{
        x: {{
          beginAtZero: true,
          grid: {{ color: 'rgba(255,255,255,0.1)' }},
          ticks: {{ color: '#ccc' }}
        }},
        y: {{
          grid: {{ display: false }},
          ticks: {{ color: '#ccc', font: {{ size: 11 }} }}
        }}
      }}
    }}
  }});
}})();
</script>'''


def _convert_player_assessment(text):
    """Convert 'Player Assessment/Status' text blocks to HTML tables."""
    # Match "Player Assessment ..." or "Player Status ..." blocks
    pattern = re.compile(
        r'(Player (?:Assessment|Status))\s+(.+?)(?=</p>|$)',
        re.IGNORECASE
    )

    def _parse_roster(match):
        label = match.group(1)
        rest = match.group(2).strip()
        # Known player name patterns: first name + last name(s)
        # Split by detecting Name Status Name Status pattern
        # Use a heuristic: capitalize words that start player names
        known_statuses = {
            "prison", "hurt", "zoo", "zoo animal", "credit", "not bad", "good",
            "bad", "mid", "clean", "ascending", "retire already", "my hair",
            "stop the cap", "feed the beast", "zaukas", "boyle", "soon",
            "hurt but also zaukas", "just stop", "prison but good", "wdhdi",
            "cooked", "injured", "stinks", "decent",
        }
        # Try to pair up: every other token is a name/status
        # Split on known status words
        entries = []
        remaining = rest
        while remaining.strip():
            # Try to find next player name + status pair
            best_match = None
            for status in sorted(known_statuses, key=len, reverse=True):
                idx = remaining.lower().find(status.lower())
                if idx > 0:  # status found after some player name text
                    name = remaining[:idx].strip()
                    if name and len(name) > 2:
                        if best_match is None or idx < best_match[0]:
                            best_match = (idx, name, status, idx + len(status))
            if best_match:
                _, name, status, end = best_match
                entries.append((name, status.title()))
                remaining = remaining[end:].strip()
            else:
                break

        if not entries:
            return match.group(0)  # Return original if parsing failed

        rows = "".join(f"<tr><td>{html.escape(n)}</td><td>{html.escape(s)}</td></tr>" for n, s in entries)
        return f'</p><table class="odds-table"><thead><tr><th>Player</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table><p>'

    return pattern.sub(_parse_roster, text)


def _convert_inline_odds_table(text):
    """Detect and convert inline odds table text (Team odds odds odds ...) to HTML table."""
    # Pattern: "Team Playoff odds Championship odds Relegation odds TeamName value value value ..."
    header_match = re.search(
        r'(Team\s+Playoff odds\s+Championship odds\s+Relegation odds)\s+',
        text, re.IGNORECASE
    )
    if not header_match:
        return text

    # Extract the table data after the headers
    before = text[:header_match.start()].strip()
    table_text = text[header_match.end():].strip()

    # Known team names to split on
    from ranking_parser import TEAM_OWNER_MAP
    from owner_mapping import ALL_OWNERS
    all_team_names = sorted(TEAM_OWNER_MAP.keys(), key=len, reverse=True)
    all_team_names += [n.lower() for n in ALL_OWNERS]

    # Parse rows: team name followed by 3 values
    rows = []
    remaining = table_text
    while remaining.strip():
        best_match = None
        for tname in all_team_names:
            if remaining.lower().startswith(tname):
                if best_match is None or len(tname) > len(best_match):
                    best_match = tname
        if not best_match:
            # Try matching any capitalized multi-word team name
            m = re.match(r'([A-Z][\w\s\'\.]+?)(?=\s+(?:clinched|off the board|[+\-]\d))', remaining)
            if m:
                best_match = m.group(1).strip().lower()
            else:
                break

        # Extract team name (use original case)
        team_display = remaining[:len(best_match)].strip()
        # Try to get proper case from original
        for tname in sorted(TEAM_OWNER_MAP.keys(), key=len, reverse=True):
            if remaining.lower().startswith(tname):
                team_display = remaining[:len(tname)]
                break
        remaining = remaining[len(best_match):].strip()

        # Extract 3 values (clinched, +/-NNN, off board, off the board)
        vals = []
        for _ in range(3):
            val_m = re.match(r'(clinched|off the board|off board|[+\-]?\d+)\s*', remaining, re.IGNORECASE)
            if val_m:
                vals.append(val_m.group(1))
                remaining = remaining[val_m.end():]
            else:
                break
        if len(vals) == 3:
            rows.append((team_display, vals[0], vals[1], vals[2]))

    if not rows:
        return text

    table_html = '<table class="odds-table"><thead><tr><th>Team</th><th>Playoff Odds</th><th>Championship Odds</th><th>Relegation Odds</th></tr></thead><tbody>'
    for team, playoff, champ, releg in rows:
        table_html += f'<tr><td>{html.escape(team)}</td><td>{html.escape(playoff)}</td><td>{html.escape(champ)}</td><td>{html.escape(releg)}</td></tr>'
    table_html += '</tbody></table>'

    before_html = f'<p>{html.escape(before)}</p>' if before else ''
    return before_html + table_html


def writeup_to_html(text):
    """Convert plain text writeup to HTML."""
    if not text:
        return ""
    # Escape HTML entities
    text = html.escape(text)

    # Fix PDF page-break artifacts: merge paragraphs where the second part
    # starts with a lowercase letter (indicating mid-sentence split)
    paragraphs = re.split(r'\n\s*\n', text)
    merged = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Join lines within paragraph
        p = re.sub(r'\n', ' ', p)
        # Merge with previous if this starts with lowercase (page break artifact)
        if merged and p and p[0].islower():
            merged[-1] += " " + p
        else:
            merged.append(p)

    result = "\n".join(f"<p>{p}</p>" for p in merged if p)

    # Convert "Player Assessment/Status" blocks to tables
    result = _convert_player_assessment(result)

    return result


def subsection_to_html(key, value):
    """Convert a subsection to an HTML callout box."""
    labels = {
        "next_up": ("Next Up", "next-up"),
        "draft_steal": ("Draft Steal", "draft-steal"),
        "draft_bust": ("Draft Bust", "draft-bust"),
        "best_pick": ("Best Pick", "best-pick"),
        "worst_pick": ("Worst Pick", "worst-pick"),
        "general_strategy": ("General Strategy", "strategy"),
        "x_factors": ("X-Factors", "x-factors"),
        "pick": ("The Pick", "pick"),
        "playoff_scenario": ("Playoff Scenario", "playoff"),
        "best_move": ("Best Move", "best-pick"),
        "predicted_finish": ("Predicted Finish", "pick"),
        "sleeper": ("Sleeper", "draft-steal"),
        "a_chirp": ("A Chirp", "worst-pick"),
        "looking_ahead": ("Looking Ahead", "next-up"),
        "midseason_draft_checkin": ("Midseason Draft Check-in", "strategy"),
        "newark_street_stat": ("Newark Street Stat", "x-factors"),
        "nervous_about": ("Nervous About", "worst-pick"),
        "best_draft_pick": ("Best Draft Pick", "best-pick"),
        "reason_for_optimism": ("Reason for Optimism", "draft-steal"),
    }
    # Handle team_comp_ prefixed keys
    if key.startswith("team_comp_"):
        comp_label = key.replace("team_comp_", "").replace("_", " ")
        label, css_class = comp_label, "strategy"
    elif key.startswith("pick_"):
        # Per-team pick labels (e.g. "pick_scampi_best_pick")
        pick_label = key.replace("pick_", "").replace("_", " ").title()
        css_class = "best-pick" if "best" in key else "worst-pick"
        label, css_class = pick_label, css_class
    else:
        label, css_class = labels.get(key, (key.replace("_", " ").title(), key))
    escaped = html.escape(value)
    return f'<div class="callout callout-{css_class}"><span class="callout-label">{label}:</span> {escaped}</div>'


def merge_grouped_teams(parsed):
    """Post-process: combine adjacent teams that share a single writeup.

    Detects when consecutive ranked teams have no writeup text between their
    rank headers in the PDF. The first N-1 teams in the group get empty
    writeups; the last team gets the combined text. We merge them into a single
    'grouped' card.
    """
    teams = parsed.get("teams", [])
    if len(teams) < 2:
        return

    merged = []
    i = 0
    while i < len(teams):
        team = teams[i]
        # Check if this team has no writeup and next team does
        if not team.get("writeup", "").strip() and not team.get("subsections"):
            # Collect consecutive empty-writeup teams
            group = [team]
            j = i + 1
            while j < len(teams) and not teams[j].get("writeup", "").strip() and not teams[j].get("subsections"):
                group.append(teams[j])
                j += 1
            # The next team (at index j) should have the shared writeup
            if j < len(teams) and teams[j].get("writeup", "").strip():
                group.append(teams[j])
                # Mark as grouped: the last team in the group has the writeup
                for g in group:
                    g["grouped_with"] = [t["team_name"] for t in group if t != g]
                merged.extend(group)
                i = j + 1
                continue
        merged.append(team)
        i += 1

    parsed["teams"] = merged


def _clean_team_display_name(name, owner):
    """Strip owner suffix from team name for display (e.g. 'Team- Owner' → 'Team')."""
    if not owner:
        return name
    from ranking_parser import TEAM_OWNER_MAP, _normalize_team_name
    from owner_mapping import OWNER_CONSOLIDATION, ALL_OWNERS
    owner_names = set(n.lower() for n in ALL_OWNERS)
    owner_names.update(OWNER_CONSOLIDATION.keys())

    # First try stripping "(Owner)" or "- Owner" suffixes
    for oname in sorted(owner_names, key=len, reverse=True):
        # "Team- Owner" or "Team: Owner" pattern
        cleaned = re.sub(r'[-:]\s*' + re.escape(oname) + r'[-.\s]*$', '', name, flags=re.IGNORECASE).strip()
        if cleaned and cleaned != name:
            return cleaned
        # "(Owner)" pattern at end
        cleaned = re.sub(r'\s*\(' + re.escape(oname) + r'\)\s*$', '', name, flags=re.IGNORECASE).strip()
        if cleaned and cleaned != name:
            return cleaned

    # If no suffix found, check if the full name is a known team — if so, keep it as-is
    name_lower = _normalize_team_name(name.lower().strip())
    for team_pattern in TEAM_OWNER_MAP:
        if name_lower == team_pattern or name_lower.startswith(team_pattern):
            return name
    return name


def _grouped_team_to_html(leader, all_teams, week_id):
    """Render a group of tied/combined teams as a single card."""
    grouped_names = leader.get("grouped_with", [])
    # Find all teams in this group
    group_teams = [t for t in all_teams if t["team_name"] in grouped_names]
    group_teams.append(leader)
    # Sort by rank (put leader's rank first)
    group_teams.sort(key=lambda t: (t is leader, t["rank"]))

    rank = leader["rank"]
    tier_class = "tier-1" if rank <= 4 else "tier-2" if rank <= 8 else "tier-3" if rank <= 12 else "tier-4"

    # Build headers for all teams in the group
    headers_html = ""
    for t in group_teams:
        t_name = html.escape(_clean_team_display_name(t["team_name"], t["owner"]))
        t_owner = html.escape(t["owner"])
        t_rank = t["rank"]
        rank_class = "rank"
        if t_rank == 1:
            rank_class += " rank-first"
        elif t_rank == 16:
            rank_class += " rank-last"
        movement_html = ""
        movement = t.get("computed_movement")
        if movement is not None:
            if movement > 0:
                movement_html = f'<span class="movement up" title="Up {movement}">&#9650; {movement}</span>'
            elif movement < 0:
                movement_html = f'<span class="movement down" title="Down {abs(movement)}">&#9660; {abs(movement)}</span>'
            else:
                movement_html = '<span class="movement same">&#8212;</span>'
        headers_html += f'''  <div class="team-header" id="{week_id}-rank-{t_rank}">
    <div class="{rank_class}">{t_rank}</div>
    <div class="team-info">
      <div class="team-name">{t_name}</div>
      <div class="team-owner">{t_owner}</div>
    </div>
    {movement_html}
  </div>\n'''

    writeup = writeup_to_html(leader["writeup"])
    subsections_html = ""
    for key, value in leader.get("subsections", {}).items():
        subsections_html += subsection_to_html(key, value)

    return f'''<div class="team-card {tier_class}" data-rank="{rank}">
{headers_html}  <div class="team-writeup">
    {writeup}
    {subsections_html}
  </div>
</div>'''


def team_to_html(team, week_id):
    """Convert a team entry to HTML card."""
    rank = team["rank"]
    name = html.escape(_clean_team_display_name(team["team_name"], team["owner"]))
    owner = html.escape(team["owner"])
    writeup = writeup_to_html(team["writeup"])

    # Movement indicator (computed from previous week)
    movement_html = ""
    movement = team.get("computed_movement")
    if movement is not None:
        if movement > 0:
            movement_html = f'<span class="movement up" title="Up {movement}">&#9650; {movement}</span>'
        elif movement < 0:
            movement_html = f'<span class="movement down" title="Down {abs(movement)}">&#9660; {abs(movement)}</span>'
        else:
            movement_html = '<span class="movement same">&#8212;</span>'

    # Special rank styling
    rank_class = "rank"
    if rank == 1:
        rank_class += " rank-first"
    elif rank == 16:
        rank_class += " rank-last"

    # Tier color class (always assign based on rank)
    if rank <= 4:
        tier_class = "tier-1"
    elif rank <= 8:
        tier_class = "tier-2"
    elif rank <= 12:
        tier_class = "tier-3"
    else:
        tier_class = "tier-4"

    # Icons
    icons = ""
    if rank == 1:
        icons = '<span class="icon-fire" title="Number One">&#128293;</span>'
    if rank == 16:
        icons = '<span class="icon-skull" title="Last Place">&#128128;</span>'

    # Subsections
    subsections_html = ""
    for key, value in team.get("subsections", {}).items():
        subsections_html += subsection_to_html(key, value)

    # Grouped teams: if this team has no writeup but is grouped, skip rendering
    # (it will be rendered as part of the group leader's card)
    grouped = team.get("grouped_with", [])
    if grouped and not writeup and not subsections_html:
        return ""  # Will be included in the grouped card below

    return f'''<div class="team-card {tier_class}" data-rank="{rank}" data-owner="{owner}" id="{week_id}-rank-{rank}">
  <div class="team-header">
    <div class="{rank_class}">{rank}</div>
    <div class="team-info">
      <div class="team-name">{icons}{name}</div>
      <div class="team-owner">{owner}</div>
    </div>
    {movement_html}
  </div>
  <div class="team-writeup">
    {writeup}
    {subsections_html}
  </div>
</div>'''


def _should_skip_image(img):
    """Check if an image should be skipped based on SKIP_IMAGES patterns."""
    for pattern in SKIP_IMAGES:
        if pattern in img["filename"]:
            return True
    return False


def _get_image_owner_override(img):
    """Check if an image has an owner override."""
    for pattern, owner in IMAGE_OWNER_OVERRIDE.items():
        if pattern in img["filename"]:
            return owner
    return None


def generate_week_html(parsed, week_id, images):
    """Generate the full HTML content for a week's rankings."""
    teams = parsed.get("teams", [])
    total_teams = len(teams)
    parts = []

    # Build owner→team index mapping
    owner_to_idx = {}
    for idx, team in enumerate(teams):
        if team["owner"] and team["owner"] not in owner_to_idx:
            owner_to_idx[team["owner"]] = idx

    # Intro (check for inline odds table)
    if parsed.get("intro"):
        intro_text = parsed["intro"]
        converted = _convert_inline_odds_table(intro_text)
        if converted != intro_text:
            # Was converted to HTML table
            parts.append(f'<div class="intro">{converted}</div>')
        else:
            parts.append(f'<div class="intro">{writeup_to_html(intro_text)}</div>')

    # Filter and categorize images
    filtered_images = [img for img in images if not _should_skip_image(img)]
    header_imgs = [img for img in filtered_images if img["page"] <= 1]
    content_imgs = [img for img in filtered_images if img["page"] > 1]

    for img in header_imgs:
        parts.append(f'<div class="article-image"><img src="images/{img["filename"]}" alt="Chart" loading="lazy"></div>')

    # Map content images to team indices based on page position or owner override
    team_images = defaultdict(list)
    if content_imgs and total_teams > 0:
        max_page = max(img["page"] for img in content_imgs)
        for img in content_imgs:
            override_owner = _get_image_owner_override(img)
            if override_owner and override_owner in owner_to_idx:
                team_idx = owner_to_idx[override_owner]
            else:
                fraction = (img["page"] - 1) / max(max_page, 1)
                team_idx = min(int(fraction * total_teams), total_teams - 1)
            team_images[team_idx].append(img)

    # Check if we need to inject power trios table for this week
    trios_data = POWER_TRIOS.get(week_id)

    current_tier = None
    for idx, team in enumerate(teams):
        # Tier header
        if team.get("tier_full") and team["tier_full"] != current_tier:
            current_tier = team["tier_full"]
            tier_name = html.escape(current_tier)
            parts.append(f'<div class="tier-header"><h2>{tier_name}</h2></div>')

        # Check if this is a grouped team that should be merged into one card
        grouped = team.get("grouped_with", [])
        if grouped and not team.get("writeup", "").strip() and not team.get("subsections"):
            continue

        if grouped and team.get("writeup", "").strip():
            parts.append(_grouped_team_to_html(team, teams, week_id))
        else:
            card_html = team_to_html(team, week_id)
            if card_html:
                parts.append(card_html)

        # Insert images near this team based on page proximity or override
        for img in team_images.get(idx, []):
            parts.append(f'<div class="article-image"><img src="images/{img["filename"]}" alt="Chart" loading="lazy"></div>')

        # Inject power trios chart + table after the team whose writeup references it
        # Or after Mitch's section if no trigger text found (fallback)
        if trios_data and team.get("writeup", ""):
            writeup_lower = team["writeup"].lower()
            trio_triggers = ["top trio", "power trio", "see the chart below", "see the table below", "vaunted trio", "deep dive the top trio"]
            inject = any(t in writeup_lower for t in trio_triggers)
            if not inject and team.get("owner") == "Mitch":
                inject = True  # Fallback: inject after Mitch/SDZ section
            if inject:
                chart_html = _render_power_trios_chart(trios_data, week_id)
                table_html = _render_power_trios_table(trios_data)
                parts.append(f'<div class="special-section"><h2>Fantasy Team Power Trios</h2>{chart_html}{table_html}</div>')
                trios_data = None  # Only inject once

    # Special sections (matchup previews, odds, etc.)
    remove_patterns = REMOVE_SECTIONS.get(week_id, [])
    for section_name, section_text in parsed.get("special_sections", {}).items():
        # Check if this section should be removed
        skip = False
        for pattern in remove_patterns:
            if re.match(pattern, section_name):
                skip = True
                break
        if skip:
            continue
        parts.append(format_special_section(section_name, section_text))

    return "\n".join(parts)


def format_special_section(section_name, section_text):
    """Format special sections with appropriate HTML."""
    escaped_name = html.escape(section_name)

    # Odds section → table
    if re.search(r'odds', section_name, re.IGNORECASE):
        return format_odds_section(escaped_name, section_text)

    # Matchup/preview sections → bold matchup headers
    if re.search(r'preview|bracket|matchup|round', section_name, re.IGNORECASE):
        return format_matchup_section(escaped_name, section_text)

    # Default
    section_html = writeup_to_html(section_text)
    return f'<div class="special-section"><h2>{escaped_name}</h2>{section_html}</div>'


def format_matchup_section(name, text):
    """Format matchup preview sections with bold matchup headers."""
    # Matchup patterns: "Team (N) vs. Team (N)", "#N Team vs #N Team", "(N) Team vs (N) Team"
    matchup_re = re.compile(
        r'(?:^|\n|(?<=\. )|(?<=\.\s))'  # Start of line, after sentence, etc.
        r'('
        r'[A-Z][\w\s\'\.]+?\s*\(\d+\)\s+vs\.?\s+[A-Z][\w\s\'\.]+?\s*\(\d+\)'  # Team (N) vs. Team (N)
        r'|'
        r'[#(]?\d+[.)]\s*.+?\s+vs\.?\s+[#(]?\d+[.)]\s*.+?(?=\s|$)'  # #N Team vs #N Team
        r')'
    )

    # First join all lines into a single text block
    flat = " ".join(line.strip() for line in text.split("\n") if line.strip())

    # Split text on matchup headers
    parts_out = []
    last_end = 0
    for m in matchup_re.finditer(flat):
        # Text before this matchup
        before = flat[last_end:m.start()].strip()
        if before:
            parts_out.append(f'<p>{html.escape(before)}</p>')
        # The matchup header
        parts_out.append(f'<h3 class="matchup-header">{html.escape(m.group(1).strip())}</h3>')
        last_end = m.end()

    # Remaining text after last matchup
    remaining = flat[last_end:].strip()
    if remaining:
        parts_out.append(f'<p>{html.escape(remaining)}</p>')

    # If no matchups found, fall back to simple paragraph rendering
    if not parts_out:
        parts_out.append(writeup_to_html(text))

    return f'<div class="special-section matchup-section"><h2>{name}</h2>{"".join(parts_out)}</div>'


def format_odds_section(name, text):
    """Format odds sections as HTML tables."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]

    # Detect columnar layout: if first few lines look like headers followed by
    # alternating name/value lines (from PDF table extraction)
    # Pattern: "Player", "Championship Odds", "Last Place Odds", then name, odds, odds, name, ...
    if len(lines) >= 6 and any("odds" in l.lower() for l in lines[:3]):
        # Find header lines (non-numeric, non-plus lines at the start)
        headers = []
        data_start = 0
        for i, line in enumerate(lines):
            if re.match(r'^[+\-]?\d', line) or line.lower() in ("off the board", "cooked", "n/a"):
                data_start = i
                break
            # Check if this looks like a player name (known owners)
            if i > 0 and line.lower().rstrip('.') in {n.lower() for n in [
                "Sweeney","Joey","Justin","TK","Deez","Mitch","Chris","TJ",
                "Papi","Matt","Paul","Connor","Gallo","Ger","Mikey","Boyle","Joe"]}:
                data_start = i
                break
            headers.append(line)

        num_cols = max(len(headers), 1)
        data_lines = lines[data_start:]

        if num_cols >= 2 and len(data_lines) >= num_cols:
            table_html = '<table class="odds-table"><thead><tr>'
            for h in headers:
                table_html += f'<th>{html.escape(h)}</th>'
            table_html += '</tr></thead><tbody>'

            # Group data lines into rows of num_cols
            for i in range(0, len(data_lines), num_cols):
                chunk = data_lines[i:i + num_cols]
                if len(chunk) == num_cols:
                    table_html += '<tr>' + ''.join(f'<td>{html.escape(c)}</td>' for c in chunk) + '</tr>'
            table_html += '</tbody></table>'
            return f'<div class="special-section"><h2>{name}</h2>{table_html}</div>'

    # Fallback: try tab/space-delimited rows
    rows = []
    for line in lines:
        parts = re.split(r'\t+|\s{3,}', line)
        if len(parts) >= 2:
            rows.append(parts)
        else:
            colon_parts = re.split(r':\s+', line, maxsplit=1)
            if len(colon_parts) == 2:
                rows.append(colon_parts)
            else:
                rows.append([line])

    if rows and any(len(r) >= 2 for r in rows):
        table_html = '<table class="odds-table"><tbody>'
        for row in rows:
            if len(row) >= 2:
                table_html += '<tr>' + ''.join(f'<td>{html.escape(c.strip())}</td>' for c in row) + '</tr>'
            else:
                table_html += f'<tr><td colspan="4" class="odds-header">{html.escape(row[0])}</td></tr>'
        table_html += '</tbody></table>'
        return f'<div class="special-section"><h2>{name}</h2>{table_html}</div>'

    return f'<div class="special-section"><h2>{name}</h2>{writeup_to_html(text)}</div>'


def generate_lookback_html(parsed, images):
    """Generate HTML for the lookback article."""
    parts = []

    parts.append(f'<div class="lookback-intro">{writeup_to_html(parsed["intro"])}</div>')

    # Skip images - interactive charts/tables on the lookback page replace them

    for entry in parsed.get("entries", []):
        rank = entry["rank"]
        owner = html.escape(entry["owner"])
        score = entry["power_score"]
        writeup = writeup_to_html(entry["writeup"])
        comparison = html.escape(entry.get("comparison", ""))

        parts.append(f'''<div class="lookback-entry" data-rank="{rank}">
  <div class="lookback-header">
    <span class="lookback-rank">{rank}</span>
    <span class="lookback-owner">{owner}</span>
    <span class="lookback-score">Power Score: {score}</span>
  </div>
  <div class="lookback-writeup">{writeup}</div>
  {f'<div class="lookback-comparison"><span class="comparison-label">Presidential Comparison:</span> {comparison}</div>' if comparison else ''}
</div>''')

    return "\n".join(parts)


def main():
    # Collect all PDFs
    pdfs = []
    for f in os.listdir(PDF_DIR):
        if f.endswith(".pdf"):
            pdfs.append(os.path.join(PDF_DIR, f))

    # Skip known duplicate/mislabeled PDFs
    SKIP_FILES = {
        "Free Chee Week 12 Power Rankings.pdf",  # Duplicate of 2025 Week 12
    }

    # ===== FIRST PASS: Parse all PDFs =====
    parsed_weeks = []  # (file_info, parsed, images, week_id)
    lookback_data = None
    lookback_images = None

    for pdf_path in sorted(pdfs):
        filename = os.path.basename(pdf_path)
        if filename in SKIP_FILES:
            print(f"Skipping (duplicate): {filename}")
            continue

        print(f"Processing: {filename}")

        file_info = parse_filename(filename)
        text = extract_full_text(pdf_path)
        week_id = get_week_id(file_info)
        img_prefix = week_id.replace("-", "_") + "_"
        images = extract_images(pdf_path, IMG_DIR, prefix=img_prefix)
        print(f"  Extracted {len(images)} images")

        parsed = parse_rankings(text, file_info)

        if file_info["type"] == "lookback":
            lookback_data = parsed
            lookback_images = images
            print(f"  Lookback: {len(parsed.get('entries', []))} entries")
            continue

        team_count = len(parsed.get("teams", []))
        print(f"  {team_count} teams, {len(parsed.get('tiers', []))} tiers")
        parsed_weeks.append((file_info, parsed, images, week_id))

    # ===== Sort weeks chronologically =====
    season_order = {"2024": 0, "2025": 1, "special": 2}
    type_order = {"regular": 0, "midseason": 0.5, "playoff_preview": 1, "final": 2}
    parsed_weeks.sort(key=lambda x: (
        season_order.get(x[0]["season"], 99),
        x[0]["week"] or 0,
        type_order.get(x[0]["type"], 0),
    ))

    # ===== Compute movement from previous week =====
    prev_owner_ranks = {}
    for file_info, parsed, images, week_id in parsed_weeks:
        for team in parsed.get("teams", []):
            owner = team["owner"]
            if owner and owner in prev_owner_ranks:
                team["computed_movement"] = prev_owner_ranks[owner] - team["rank"]
            else:
                team["computed_movement"] = None

        # Build current owner→rank mapping for next iteration
        current_ranks = {}
        for team in parsed.get("teams", []):
            if team["owner"]:
                current_ranks[team["owner"]] = team["rank"]
        prev_owner_ranks = current_ranks

    # ===== SECOND PASS: Generate JSON + HTML =====
    all_weeks = []
    all_owners_data = defaultdict(lambda: {
        "rankings": [],
        "team_names": set(),
        "seasons": set(),
    })

    for file_info, parsed, images, week_id in parsed_weeks:
        # Merge grouped teams (adjacent teams sharing a writeup)
        merge_grouped_teams(parsed)

        # Generate HTML content
        week_html = generate_week_html(parsed, week_id, images)

        with open(os.path.join(DATA_DIR, f"{week_id}.html"), "w") as f:
            f.write(week_html)

        # Build week JSON data
        teams_json = []
        for team in parsed.get("teams", []):
            movement = team.get("computed_movement")
            teams_json.append({
                "rank": team["rank"],
                "team_name": team["team_name"],
                "owner": team["owner"],
                "movement": movement,
                "tier": team.get("tier"),
                "subsections": list(team.get("subsections", {}).keys()),
            })

            # Track owner data
            owner = team["owner"]
            if owner:
                all_owners_data[owner]["rankings"].append({
                    "season": file_info["season"],
                    "week": file_info["week"],
                    "week_id": week_id,
                    "rank": team["rank"],
                })
                all_owners_data[owner]["team_names"].add(team["team_name"])
                all_owners_data[owner]["seasons"].add(file_info["season"])

        week_json = {
            "week_id": week_id,
            "season": file_info["season"],
            "week": file_info["week"],
            "type": file_info["type"],
            "title": parsed.get("title", ""),
            "label": get_display_label(file_info),
            "teams": teams_json,
            "tiers": [t["name"] for t in parsed.get("tiers", [])],
            "has_special_sections": bool(parsed.get("special_sections")),
            "image_count": len(images),
        }

        with open(os.path.join(DATA_DIR, f"{week_id}.json"), "w") as f:
            json.dump(week_json, f, indent=2)

        all_weeks.append(week_json)

    # ===== Process lookback =====
    if lookback_data:
        lookback_html = generate_lookback_html(lookback_data, lookback_images or [])
        with open(os.path.join(DATA_DIR, "lookback_content.html"), "w") as f:
            f.write(lookback_html)
        lookback_json = {
            "title": lookback_data["title"],
            "intro": lookback_data["intro"],
            "entries": lookback_data["entries"],
        }
        with open(os.path.join(DATA_DIR, "lookback.json"), "w") as f:
            json.dump(lookback_json, f, indent=2, default=list)

    # ===== Save rankings index =====
    rankings_index = {
        "seasons": ["2024", "2025"],
        "weeks": all_weeks,
    }
    with open(os.path.join(DATA_DIR, "rankings.json"), "w") as f:
        json.dump(rankings_index, f, indent=2)

    # ===== Build and save owners data =====
    owners_json = {}
    for owner, data in all_owners_data.items():
        rankings = data["rankings"]
        if not rankings:
            continue
        ranks = [r["rank"] for r in rankings]
        owners_json[owner] = {
            "name": owner,
            "team_names": sorted(data["team_names"]),
            "seasons": sorted(data["seasons"]),
            "total_weeks": len(rankings),
            "avg_rank": round(sum(ranks) / len(ranks), 2),
            "best_rank": min(ranks),
            "worst_rank": max(ranks),
            "weeks_at_1": sum(1 for r in ranks if r == 1),
            "weeks_at_16": sum(1 for r in ranks if r == 16),
            "rankings": sorted(rankings, key=lambda r: (r["season"], r["week"] or 0)),
        }

    with open(os.path.join(DATA_DIR, "owners.json"), "w") as f:
        json.dump(owners_json, f, indent=2)

    print(f"\n=== Summary ===")
    print(f"Weeks processed: {len(all_weeks)}")
    print(f"Unique owners: {len(owners_json)}")
    print(f"Data files written to: {DATA_DIR}")

    # Verify
    for week in all_weeks:
        if len(week["teams"]) != 16:
            print(f"  WARNING: {week['week_id']} has {len(week['teams'])} teams (expected 16)")


if __name__ == "__main__":
    main()
