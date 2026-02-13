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

    return "\n".join(f"<p>{p}</p>" for p in merged if p)


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


def team_to_html(team, week_id):
    """Convert a team entry to HTML card."""
    rank = team["rank"]
    name = html.escape(team["team_name"])
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

    # Grouped teams: if this team has no writeup but is grouped, show a compact header
    grouped = team.get("grouped_with", [])
    if grouped and not writeup and not subsections_html:
        return f'''<div class="team-card {tier_class}" data-rank="{rank}" data-owner="{owner}" id="{week_id}-rank-{rank}">
  <div class="team-header">
    <div class="{rank_class}">{rank}</div>
    <div class="team-info">
      <div class="team-name">{icons}{name}</div>
      <div class="team-owner">{owner}</div>
    </div>
    {movement_html}
  </div>
</div>'''

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


def generate_week_html(parsed, week_id, images):
    """Generate the full HTML content for a week's rankings."""
    teams = parsed.get("teams", [])
    total_teams = len(teams)
    parts = []

    # Intro
    if parsed.get("intro"):
        parts.append(f'<div class="intro">{writeup_to_html(parsed["intro"])}</div>')

    # Separate images: page 1 as headers, rest distributed among teams
    header_imgs = [img for img in images if img["page"] <= 1]
    content_imgs = [img for img in images if img["page"] > 1]

    for img in header_imgs:
        parts.append(f'<div class="article-image"><img src="images/{img["filename"]}" alt="Chart" loading="lazy"></div>')

    # Map content images to team indices based on page position
    team_images = defaultdict(list)
    if content_imgs and total_teams > 0:
        max_page = max(img["page"] for img in content_imgs)
        for img in content_imgs:
            fraction = (img["page"] - 1) / max(max_page, 1)
            team_idx = min(int(fraction * total_teams), total_teams - 1)
            team_images[team_idx].append(img)

    current_tier = None
    for idx, team in enumerate(teams):
        # Tier header
        if team.get("tier_full") and team["tier_full"] != current_tier:
            current_tier = team["tier_full"]
            tier_name = html.escape(current_tier)
            parts.append(f'<div class="tier-header"><h2>{tier_name}</h2></div>')

        parts.append(team_to_html(team, week_id))

        # Insert images near this team based on page proximity
        for img in team_images.get(idx, []):
            parts.append(f'<div class="article-image"><img src="images/{img["filename"]}" alt="Chart" loading="lazy"></div>')

    # Special sections (matchup previews, odds, etc.)
    for section_name, section_text in parsed.get("special_sections", {}).items():
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
    lines = text.split("\n")
    parts = []
    current_paragraph = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_paragraph:
                parts.append(f'<p>{html.escape(" ".join(current_paragraph))}</p>')
                current_paragraph = []
            continue

        # Detect matchup lines: "#N Team vs #N Team", "(N) Team vs (N) Team"
        if re.match(r'^[#(]?\d+[.)]\s*.+\s+vs\.?\s+[#(]?\d+', stripped, re.IGNORECASE):
            if current_paragraph:
                parts.append(f'<p>{html.escape(" ".join(current_paragraph))}</p>')
                current_paragraph = []
            parts.append(f'<h3 class="matchup-header">{html.escape(stripped)}</h3>')
        elif re.match(r'^\(.+\)\s+vs\.?\s+\(', stripped):
            if current_paragraph:
                parts.append(f'<p>{html.escape(" ".join(current_paragraph))}</p>')
                current_paragraph = []
            parts.append(f'<h3 class="matchup-header">{html.escape(stripped)}</h3>')
        else:
            current_paragraph.append(stripped)

    if current_paragraph:
        parts.append(f'<p>{html.escape(" ".join(current_paragraph))}</p>')

    return f'<div class="special-section matchup-section"><h2>{name}</h2>{"".join(parts)}</div>'


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

    # Insert images
    for img in images:
        parts.append(f'<div class="article-image"><img src="images/{img["filename"]}" alt="Chart" loading="lazy"></div>')

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
