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
    # Split into paragraphs
    paragraphs = re.split(r'\n\s*\n', text)
    html_parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Join lines within a paragraph
        p = re.sub(r'\n', ' ', p)
        html_parts.append(f"<p>{p}</p>")
    return "\n".join(html_parts)


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
    }
    label, css_class = labels.get(key, (key.replace("_", " ").title(), key))
    escaped = html.escape(value)
    return f'<div class="callout callout-{css_class}"><span class="callout-label">{label}:</span> {escaped}</div>'


def team_to_html(team, week_id):
    """Convert a team entry to HTML card."""
    rank = team["rank"]
    name = html.escape(team["team_name"])
    owner = html.escape(team["owner"])
    lw = team["lw_rank"]
    writeup = writeup_to_html(team["writeup"])

    # Movement indicator
    movement_html = ""
    if lw is not None:
        diff = lw - rank  # positive = moved up
        if diff > 0:
            movement_html = f'<span class="movement up" title="Up {diff}">&#9650; {diff}</span>'
        elif diff < 0:
            movement_html = f'<span class="movement down" title="Down {abs(diff)}">&#9660; {abs(diff)}</span>'
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
    parts = []

    # Intro
    if parsed.get("intro"):
        parts.append(f'<div class="intro">{writeup_to_html(parsed["intro"])}</div>')

    # Insert images from page 1-2 as header images
    header_imgs = [img for img in images if img["page"] <= 2]
    for img in header_imgs:
        parts.append(f'<div class="article-image"><img src="images/{img["filename"]}" alt="Chart" loading="lazy"></div>')

    current_tier = None
    for team in parsed.get("teams", []):
        # Tier header
        if team.get("tier_full") and team["tier_full"] != current_tier:
            current_tier = team["tier_full"]
            tier_name = html.escape(current_tier)
            parts.append(f'<div class="tier-header"><h2>{tier_name}</h2></div>')

        parts.append(team_to_html(team, week_id))

    # Remaining images (after page 2)
    other_imgs = [img for img in images if img["page"] > 2]
    if other_imgs:
        parts.append('<div class="article-images">')
        for img in other_imgs:
            parts.append(f'<div class="article-image"><img src="images/{img["filename"]}" alt="Chart" loading="lazy"></div>')
        parts.append('</div>')

    # Special sections
    for section_name, section_text in parsed.get("special_sections", {}).items():
        section_html = writeup_to_html(section_text)
        parts.append(f'<div class="special-section"><h2>{html.escape(section_name)}</h2>{section_html}</div>')

    return "\n".join(parts)


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

    all_weeks = []
    all_owners_data = defaultdict(lambda: {
        "rankings": [],
        "team_names": set(),
        "seasons": set(),
    })

    lookback_data = None

    for pdf_path in sorted(pdfs):
        filename = os.path.basename(pdf_path)
        print(f"Processing: {filename}")

        file_info = parse_filename(filename)
        text = extract_full_text(pdf_path)

        # Generate image prefix from week ID
        week_id = get_week_id(file_info)
        img_prefix = week_id.replace("-", "_") + "_"

        # Extract images
        images = extract_images(pdf_path, IMG_DIR, prefix=img_prefix)
        print(f"  Extracted {len(images)} images")

        # Parse rankings
        parsed = parse_rankings(text, file_info)

        if file_info["type"] == "lookback":
            lookback_data = parsed
            lookback_html = generate_lookback_html(parsed, images)
            # Save lookback HTML
            with open(os.path.join(DATA_DIR, "lookback_content.html"), "w") as f:
                f.write(lookback_html)
            # Save lookback JSON
            lookback_json = {
                "title": parsed["title"],
                "intro": parsed["intro"],
                "entries": parsed["entries"],
            }
            with open(os.path.join(DATA_DIR, "lookback.json"), "w") as f:
                json.dump(lookback_json, f, indent=2, default=list)
            print(f"  Lookback: {len(parsed['entries'])} entries")
            continue

        # Generate HTML content
        week_html = generate_week_html(parsed, week_id, images)

        # Save per-week HTML
        with open(os.path.join(DATA_DIR, f"{week_id}.html"), "w") as f:
            f.write(week_html)

        # Build week JSON data
        teams_json = []
        for team in parsed.get("teams", []):
            teams_json.append({
                "rank": team["rank"],
                "team_name": team["team_name"],
                "owner": team["owner"],
                "lw_rank": team["lw_rank"],
                "tier": team.get("tier"),
                "subsections": list(team.get("subsections", {}).keys()),
            })

            # Track owner data
            owner = team["owner"]
            all_owners_data[owner]["rankings"].append({
                "season": file_info["season"],
                "week": file_info["week"],
                "week_id": week_id,
                "rank": team["rank"],
                "lw_rank": team["lw_rank"],
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

        # Save per-week JSON
        with open(os.path.join(DATA_DIR, f"{week_id}.json"), "w") as f:
            json.dump(week_json, f, indent=2)

        all_weeks.append(week_json)
        team_count = len(parsed.get("teams", []))
        print(f"  {team_count} teams, {len(parsed.get('tiers', []))} tiers")

    # Sort weeks by season then sort_key
    season_order = {"2024": 0, "2025": 1, "special": 2}
    all_weeks.sort(key=lambda w: (season_order.get(w["season"], 99), w["week"] or 0))

    # Save master rankings index
    rankings_index = {
        "seasons": ["2024", "2025"],
        "weeks": all_weeks,
    }
    with open(os.path.join(DATA_DIR, "rankings.json"), "w") as f:
        json.dump(rankings_index, f, indent=2)

    # Build and save owners data
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
