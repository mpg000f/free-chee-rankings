"""Parse ranking data from extracted PDF text."""

import re
from owner_mapping import resolve_owner

# Known owner names for matching
KNOWN_OWNERS = {
    "tk", "joey", "justin", "sweeney", "deez", "mitch", "chris",
    "tj", "papi", "matt", "paul", "connor", "gallo", "ger",
    "mikey", "boyle", "joe", "ron", "zaukas", "oscar", "simon",
    "gerry lewis", "north willow",
}

# Team name -> owner lookup (for weeks where owner is not listed)
TEAM_OWNER_MAP = {
    "hand me the piss": "TK",
    "team obama sopranos": "TK",
    "team obama": "TK",
    "stewed c": "Joey",
    "life with derrick": "Justin",
    "tony the phenom": "Justin",
    "work ass": "Sweeney",
    "alexander's unreal team": "Deez",
    "pigs on the 7th rank": "Deez",
    "deserves to be shot": "Mitch",
    "sweeney deez and zaukas": "Mitch",
    "sansa ludacris": "Chris",
    "ginny sack": "Chris",
    "cap stoppers": "TJ",
    "cookie monster golf cart": "TJ",
    "gorlock the destroyer": "Papi",
    "gorlock the destroyer schwartz": "Papi",
    "gorlock the d": "Papi",
    "wherestua": "Matt",
    "the art of the deal": "Matt",
    "art of the deal": "Matt",
    "marvin\u2019s receiver room": "Paul",
    "marvin's receiver room": "Paul",
    "team daniel": "Paul",
    "sweeney.": "Connor",
    "here without you tishman": "Gallo",
    "scampi": "Gallo",
    "senior ai coke twins": "Mikey",
    "senior bag master": "Mikey",
    "ai coke twins": "Mikey",
    "gotham rogues": "Boyle",  # 2024 (Joe = Boyle)
    "champagne suitcase heart emoji": "Ger",
    "champagne suitcase heart face": "Ger",
    "champagne suitcase kiss face": "Ger",
    "ger": "Ger",
    "the jackson brownes": "Boyle",
    "jackson brownes": "Boyle",
}


def _normalize_team_name(name):
    """Normalize team name for consistent lookup."""
    # Replace unicode quotes with ASCII
    name = name.replace("\u2019", "'").replace("\u2018", "'")
    return name


def _strip_owner_suffix(name):
    """Strip owner name suffix from a team name (e.g. 'Team- Owner' → 'Team')."""
    # Try stripping "- Owner", ": Owner", or trailing owner name after separator
    for owner_name in sorted(KNOWN_OWNERS, key=len, reverse=True):
        pattern = re.compile(r'^(.+?)[-:\s]+' + re.escape(owner_name) + r'[-\s]*$', re.IGNORECASE)
        m = pattern.match(name)
        if m:
            return m.group(1).strip()
    return name


def parse_rank_line(line):
    """Parse a single rank line into rank number and rest of text.

    Returns (rank, rest) or None if not a rank line.
    """
    m = re.match(r'^(\d{1,2})\.\s+(.+)$', line.strip())
    if m and 1 <= int(m.group(1)) <= 16:
        return int(m.group(1)), m.group(2).strip()
    return None


def extract_team_owner(rest):
    """Extract team name and owner from the rest of a rank line.

    Handles formats:
    - "Team Name- Owner (LW rank: X)"
    - "Team Name- Owner"
    - "Team Name (Owner)"
    - "Team Name: Owner"
    - "Team Name" (no owner - use lookup)
    """
    # Step 1: Remove LW rank suffix in all its forms
    # Patterns: (LW rank: X), (LW rank- X), (LW Rank: X), (LW- X), (LW rank:X)
    lw_rank = None
    lw_pattern = re.compile(r'\(?\s*LW[\s-]*[Rr]ank[\s:-]*(\d+)\s*\)?')
    lw_match = lw_pattern.search(rest)
    if lw_match:
        lw_rank = int(lw_match.group(1))
        rest = rest[:lw_match.start()].strip()

    # Also handle standalone (LW- X) pattern
    if lw_rank is None:
        lw_match2 = re.search(r'\(LW[\s-]+(\d+)\)', rest)
        if lw_match2:
            lw_rank = int(lw_match2.group(1))
            rest = rest[:lw_match2.start()].strip()

    # Clean trailing punctuation
    rest = rest.rstrip("(").strip()

    # Step 2: Check full team name against TEAM_OWNER_MAP first
    # (handles cases where owner names appear in team names, e.g. "Sweeney Deez and Zaukas")
    team_lower_check = _normalize_team_name(rest.lower().strip())
    for team_pattern, owner in TEAM_OWNER_MAP.items():
        if team_lower_check == team_pattern or team_lower_check.startswith(team_pattern):
            # Strip owner suffix (e.g. "Team- Owner" → "Team")
            clean = _strip_owner_suffix(rest)
            return clean, owner, lw_rank

    # Step 3: Try to split team and owner

    # Format: "Team Name: Owner" (2025 late season)
    colon_match = re.match(r'^(.+?):\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*$', rest)
    if colon_match:
        team_name = colon_match.group(1).strip()
        owner = resolve_owner(None, colon_match.group(2).strip())
        return team_name, owner, lw_rank

    # Format: "Team Name (Owner)" (2025 Week 3 style)
    paren_match = re.match(r'^(.+?)\s+\(([A-Za-z]+(?:\s+[A-Za-z]+)?)\)\s*$', rest)
    if paren_match:
        candidate_owner = paren_match.group(2).strip().lower()
        if candidate_owner in KNOWN_OWNERS:
            team_name = paren_match.group(1).strip()
            owner = resolve_owner(None, paren_match.group(2).strip())
            return team_name, owner, lw_rank

    # Format: "Team Name- Owner" (most 2024 entries)
    # Match last occurrence of "- OwnerName" where OwnerName is a known owner
    # Work backwards to handle teams with dashes in names
    dash_match = re.match(r'^(.+?)-\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\s*$', rest)
    if dash_match:
        candidate = dash_match.group(2).strip().lower().rstrip("-").strip()
        if candidate in KNOWN_OWNERS:
            team_name = dash_match.group(1).strip()
            owner = resolve_owner(None, dash_match.group(2).strip().rstrip("-").strip())
            return team_name, owner, lw_rank

    # Special case: "Ger- still uses emoji stuff..." (Ger's weird entries)
    if "ger" in rest.lower() and ("emoji" in rest.lower() or rest.lower().startswith("ger")):
        return rest, "Ger", lw_rank

    # Special case: messy lines with embedded dashes
    # Try matching known owner at the end after any separator
    for owner_name in sorted(KNOWN_OWNERS, key=len, reverse=True):
        pattern = re.compile(r'^(.+?)[-:\s]+(' + re.escape(owner_name) + r')[-\s]*$', re.IGNORECASE)
        m = pattern.match(rest)
        if m:
            team_name = m.group(1).strip()
            owner = resolve_owner(None, m.group(2).strip())
            return team_name, owner, lw_rank

    # No owner found - try team lookup
    team_lower = _normalize_team_name(rest.lower().strip())
    for team_pattern, owner in TEAM_OWNER_MAP.items():
        if team_lower == team_pattern or team_lower.startswith(team_pattern):
            clean = _strip_owner_suffix(rest)
            return clean, owner, lw_rank

    # Last resort: return with no owner
    return rest, "", lw_rank


def parse_rankings(text, file_info):
    """Parse rankings from extracted PDF text."""
    lines = text.split("\n")
    result = {
        "title": "",
        "intro": "",
        "tiers": [],
        "teams": [],
        "special_sections": {},
        "file_info": file_info,
    }

    if file_info["type"] == "lookback":
        return parse_lookback(text, file_info)

    # Find title
    for line in lines:
        if line.strip():
            result["title"] = line.strip()
            break

    current_tier = None
    current_team = None
    current_text = []
    intro_lines = []
    in_intro = True
    in_special = None
    special_text = []

    tier_pattern = re.compile(
        r'^(?:Tier\s+(?:One|Two|Three|Four|\d+))\s*:\s*(.+)$', re.IGNORECASE
    )

    bracket_pattern = re.compile(
        r'^(Playoff Bracket|Mud Eater Bracket|Playoff Preview|Second Round|Final Round|Relegation Preview|Matchup Previews?|Odds\s*\(.*?\)\s*:?|Rankings History).*$',
        re.IGNORECASE
    )

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line:
            if current_team is not None:
                current_text.append("")
            elif in_special:
                special_text.append("")
            continue

        # Check for tier header
        tier_match = tier_pattern.match(line)
        if tier_match:
            if current_team is not None:
                _finalize_team(current_team, current_text)
                result["teams"].append(current_team)
                current_team = None
                current_text = []
            if in_special:
                result["special_sections"][in_special] = "\n".join(special_text).strip()
                in_special = None
                special_text = []
            in_intro = False
            tier_name = tier_match.group(1).strip()
            current_tier = {"name": tier_name, "full": line}
            result["tiers"].append(current_tier)
            continue

        # Check for bracket/section headers
        bracket_match = bracket_pattern.match(line)
        if bracket_match and not parse_rank_line(line):
            if current_team is not None:
                _finalize_team(current_team, current_text)
                result["teams"].append(current_team)
                current_team = None
                current_text = []
            if in_special:
                result["special_sections"][in_special] = "\n".join(special_text).strip()
            in_intro = False
            in_special = line.strip().rstrip(":")
            special_text = []
            continue

        # Check for rank line
        rank_result = parse_rank_line(line)
        if rank_result:
            rank_num, rest = rank_result

            # Handle ties: "Tied- Team1- Owner1 ... and Team2- Owner2 ..."
            if rest.lower().startswith("tied"):
                rest = re.sub(r'^[Tt]ied[-\s]*', '', rest).strip()
                # Split on " and "
                tie_parts = re.split(r'\s+and\s+', rest)
                if len(tie_parts) >= 2:
                    # Save previous team
                    if current_team is not None:
                        _finalize_team(current_team, current_text)
                        result["teams"].append(current_team)

                    if in_special:
                        result["special_sections"][in_special] = "\n".join(special_text).strip()
                        in_special = None
                        special_text = []

                    in_intro = False

                    # First tied team
                    team_name1, owner1, lw1 = extract_team_owner(tie_parts[0])
                    team1 = {
                        "rank": rank_num, "team_name": team_name1, "owner": owner1,
                        "lw_rank": lw1, "writeup": "", "subsections": {},
                        "tier": current_tier["name"] if current_tier else None,
                        "tier_full": current_tier["full"] if current_tier else None,
                        "tied": True,
                    }
                    result["teams"].append(team1)

                    # Second tied team
                    team_name2, owner2, lw2 = extract_team_owner(tie_parts[1])
                    current_team = {
                        "rank": rank_num, "team_name": team_name2, "owner": owner2,
                        "lw_rank": lw2, "writeup": "", "subsections": {},
                        "tier": current_tier["name"] if current_tier else None,
                        "tier_full": current_tier["full"] if current_tier else None,
                        "tied": True,
                    }
                    current_text = []
                    continue

            # Regular rank entry
            team_name, owner, lw_rank = extract_team_owner(rest)

            if current_team is not None:
                _finalize_team(current_team, current_text)
                result["teams"].append(current_team)

            if in_special:
                result["special_sections"][in_special] = "\n".join(special_text).strip()
                in_special = None
                special_text = []

            in_intro = False
            current_team = {
                "rank": rank_num, "team_name": team_name, "owner": owner,
                "lw_rank": lw_rank, "writeup": "", "subsections": {},
                "tier": current_tier["name"] if current_tier else None,
                "tier_full": current_tier["full"] if current_tier else None,
            }
            current_text = []
            continue

        # Intro text
        if in_intro and current_team is None and not result["teams"]:
            if line == result["title"]:
                continue
            intro_lines.append(line)
            continue

        # Special section text
        if in_special and current_team is None:
            special_text.append(line)
            continue

        # Team writeup text
        if current_team is not None:
            current_text.append(line)
        elif in_special:
            special_text.append(line)

    # Finalize last team
    if current_team is not None:
        _finalize_team(current_team, current_text)
        result["teams"].append(current_team)

    if in_special:
        result["special_sections"][in_special] = "\n".join(special_text).strip()

    result["intro"] = "\n".join(intro_lines).strip()
    return result


def _finalize_team(team, text_lines):
    """Process writeup text and extract subsections."""
    # Remove LW rank lines that leaked into writeup text
    cleaned_lines = []
    for line in text_lines:
        stripped = line.strip()
        if re.match(r'^LW[\s-]*[Rr]ank[\s:-]*\d+', stripped):
            continue
        if re.match(r'^LW[\s-]*[Rr]ank[\s:-]*\d+\s*and\s*\d+', stripped):
            continue
        if stripped.lower().startswith("lw rank") or stripped.lower().startswith("lw-rank"):
            continue
        cleaned_lines.append(line)
    full_text = "\n".join(cleaned_lines).strip()
    subsections = {}

    # Next up
    m = re.search(r'(?:^|\n)Next [Uu]p:\s*(.+?)(?:\n\n|\Z)', full_text, re.DOTALL)
    if m:
        subsections["next_up"] = m.group(1).strip()
        full_text = full_text[:m.start()].strip()

    # Draft Steal / Draft Bust
    steal = re.search(r'(?:^|\n)Draft Steal:\s*(.+?)(?=\nDraft Bust:|\n\n|\Z)', full_text, re.DOTALL)
    bust = re.search(r'(?:^|\n)Draft Bust:\s*(.+?)(?:\n\n|\Z)', full_text, re.DOTALL)
    if steal:
        subsections["draft_steal"] = steal.group(1).strip()
    if bust:
        subsections["draft_bust"] = bust.group(1).strip()
    if steal or bust:
        full_text = re.sub(r'\nDraft (?:Steal|Bust):.*$', '', full_text, flags=re.DOTALL).strip()

    # Best Pick / Worst Pick
    best = re.search(r'(?:^|\n)Best [Pp]ick:\s*(.+?)(?=\n(?:Worst|Best) [Pp]ick:|\n\n|\Z)', full_text, re.DOTALL)
    worst = re.search(r'(?:^|\n)Worst [Pp]ick:\s*(.+?)(?:\n\n|\Z)', full_text, re.DOTALL)
    if best:
        subsections["best_pick"] = best.group(1).strip()
    if worst:
        subsections["worst_pick"] = worst.group(1).strip()
    if best or worst:
        full_text = re.sub(r'\n(?:Best|Worst) [Pp]ick:.*$', '', full_text, flags=re.DOTALL).strip()

    # General Strategy
    strat = re.search(r'(?:^|\n)General Strategy:\s*(.+?)(?:\n\n|\Z)', full_text, re.DOTALL)
    if strat:
        subsections["general_strategy"] = strat.group(1).strip()
        full_text = full_text[:strat.start()].strip()

    # Generic subsection extractor for labeled sections
    # These patterns match "Label:" at start of line and capture until next labeled section or double newline
    generic_patterns = [
        ("playoff_scenario", r'Playoff [Ss]cenario:'),
        ("best_move", r'Best [Mm]ove[^:]*:'),
        ("predicted_finish", r'Predicted [Ff]inish:'),
        ("sleeper", r'Sleeper:'),
        ("a_chirp", r'A [Cc]hirp:'),
        ("looking_ahead", r'Looking [Aa]head:'),
        ("midseason_draft_checkin", r'Midseason [Dd]raft [Cc]heck-?in:'),
        ("newark_street_stat", r'Newark [Ss]treet [Ss]tat:'),
        ("nervous_about", r'Nervous [Aa]bout:'),
        ("best_draft_pick", r'Best [Dd]raft [Pp]ick:'),
        ("reason_for_optimism", r'Reason [Ff]or [Oo]ptimism:'),
    ]

    # Extract "Algorithm's roster suggestion:" which can appear inline (mid-paragraph)
    algo_m = re.search(r"Algorithm['\u2019]?s? [Rr]oster [Ss]uggestion:\s*(.+?)(?:\n\n|\Z)", full_text, re.DOTALL)
    if algo_m:
        subsections["algorithm_roster_suggestion"] = algo_m.group(1).strip()
        full_text = full_text[:algo_m.start()].rstrip() + full_text[algo_m.end():]

    # Find all matches and their positions
    all_matches = []
    for key, pattern in generic_patterns:
        m = re.search(r'(?:^|\n)(' + pattern + r')\s*(.+?)(?=\n(?:[A-Z][a-z]+ [A-Z]|Playoff|Predicted|Best [Mm]ove|Sleeper|Looking|Midseason|Newark|Nervous|A [Cc]hirp|Algorithm)|\n\n|\Z)', full_text, re.DOTALL)
        if m:
            subsections[key] = m.group(2).strip()
            all_matches.append(m)

    # Also check for "Team Comp:" / team comparison sections
    comp_matches = list(re.finditer(r'(?:^|\n)(Team [Cc]omp(?:arison)?[^:]*:)\s*(.+?)(?=\n(?:Team [Cc]omp|[A-Z][a-z]+ [A-Z])|\n\n|\Z)', full_text, re.DOTALL))
    for m in comp_matches:
        label = m.group(1).rstrip(":")
        subsections[f"team_comp_{label}"] = m.group(2).strip()
        all_matches.append(m)

    # Check for per-team "X best pick:" / "X worst pick:" patterns (grouped sections)
    # Only match on a single line (no newline in the label prefix or separator)
    team_pick_matches = list(re.finditer(
        r'(?:^|\n)([A-Z][\w ]{1,30}[ \t]+(?:best|worst)[ \t]+(?:pick|draft pick)[^:\n]*:)[ \t]*(.+?)(?=\n[A-Z][\w ]{1,30}[ \t]+(?:best|worst)[ \t]+(?:pick|draft pick)|\n\n|\Z)',
        full_text, re.DOTALL | re.IGNORECASE))
    for m in team_pick_matches:
        label = m.group(1).strip().rstrip(":")
        key = f"pick_{label.lower().replace(' ', '_')}"
        subsections[key] = m.group(2).strip()
        all_matches.append(m)

    # Remove extracted subsections from main writeup (cut at earliest match)
    if all_matches:
        earliest = min(m.start() for m in all_matches)
        full_text = full_text[:earliest].strip()

    team["writeup"] = full_text
    team["subsections"] = subsections


def parse_lookback(text, file_info):
    """Parse the First Term Lookback document."""
    lines = text.split("\n")
    result = {
        "title": "Free Chee First Term Lookback",
        "intro": "",
        "entries": [],
        "file_info": file_info,
        "type": "lookback",
    }

    current_entry = None
    current_text = []
    intro_lines = []
    in_intro = True

    # Match "1. Sweeney- 0.847"
    rank_pattern = re.compile(r'^(\d{1,2})\.\s+(.+?)[-\s]+([\d.]+)\s*$')

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_entry:
                current_text.append("")
            elif in_intro:
                intro_lines.append("")
            continue

        rank_match = rank_pattern.match(stripped)
        if rank_match:
            if current_entry:
                _finalize_lookback_entry(current_entry, current_text)
                result["entries"].append(current_entry)

            in_intro = False
            rank_num = int(rank_match.group(1))
            owner_raw = rank_match.group(2).strip().rstrip("-").strip()
            score = float(rank_match.group(3))
            owner = resolve_owner(None, owner_raw)
            current_entry = {
                "rank": rank_num,
                "owner": owner,
                "power_score": score,
                "writeup": "",
                "comparison": "",
            }
            current_text = []
            continue

        if in_intro and not current_entry:
            if stripped == result["title"]:
                continue
            intro_lines.append(stripped)
        elif current_entry:
            current_text.append(stripped)

    if current_entry:
        _finalize_lookback_entry(current_entry, current_text)
        result["entries"].append(current_entry)

    result["intro"] = "\n".join(intro_lines).strip()
    return result


def _finalize_lookback_entry(entry, text_lines):
    """Process lookback entry text and extract comparison."""
    full_text = "\n".join(text_lines).strip()
    entry["writeup"] = full_text

    # Extract comparison - it usually starts with "Comparison:" and goes to end or next paragraph
    comp_match = re.search(r'Comparison:\s*(.+)', full_text, re.DOTALL)
    if comp_match:
        entry["comparison"] = comp_match.group(1).strip()


if __name__ == "__main__":
    import sys
    import json
    from pdf_parser import extract_full_text, parse_filename

    if len(sys.argv) < 2:
        print("Usage: python ranking_parser.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    file_info = parse_filename(pdf_path)
    text = extract_full_text(pdf_path)
    result = parse_rankings(text, file_info)
    print(json.dumps(result, indent=2, default=str))
