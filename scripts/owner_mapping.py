"""Owner mapping across seasons and team names.

Owner consolidation rules (same person, different names used):
- Matt = Ron
- Boyle = Joe = North Willow
- Zaukas = Paul
- Papi = Simon
- Ger = Gerry Lewis
- Mikey = Oscar
"""

# Map variant names to canonical owner name
OWNER_CONSOLIDATION = {
    "ron": "Matt",
    "joe": "Boyle",
    "north willow": "Boyle",
    "zaukas": "Paul",
    "simon": "Papi",
    "gerry lewis": "Ger",
    "oscar": "Mikey",
}

# All canonical owner names (the 16 actual people)
ALL_OWNERS = [
    "Sweeney", "Joey", "Justin", "TK", "Deez", "Mitch", "Chris",
    "TJ", "Papi", "Matt", "Paul", "Connor", "Gallo", "Ger",
    "Mikey", "Boyle",
]

# Normalize owner names (handle case variations)
OWNER_NORMALIZE = {name.lower(): name for name in ALL_OWNERS}


def resolve_owner(team_name_raw, explicit_owner=None):
    """Resolve owner from explicit name or team name, applying consolidation."""
    if explicit_owner:
        name = explicit_owner.strip().rstrip("-").strip()
        # Check consolidation first
        consolidated = OWNER_CONSOLIDATION.get(name.lower())
        if consolidated:
            return consolidated
        # Then check canonical names
        normalized = OWNER_NORMALIZE.get(name.lower())
        if normalized:
            return normalized
        return name

    if team_name_raw:
        return team_name_raw.strip()

    return explicit_owner or team_name_raw


# Canonical team name per (season, owner). Keeps team names uniform across all
# weeks of a season and strips PDF-parsing artifacts (stray "- Tishman" suffixes,
# "(Owner)" tags, case/spacing variants). Update when an owner renames a team.
CANONICAL_TEAMS = {
    "2024": {
        "Joey": "Stewed C",
        "TK": "Hand me the Piss",
        "Chris": "Sansa Ludacris",
        "Papi": "Gorlock the Destroyer",
        "Mitch": "Deserves to be Shot",
        "Justin": "Life with Derrick",
        "Paul": "Marvin’s Receiver Room",
        "TJ": "Cap Stoppers",
        "Connor": "Sweeney.",
        "Sweeney": "Work Ass",
        "Deez": "Pigs on the 7th Rank",
        "Matt": "WHERESTUA",
        "Boyle": "Gotham Rogues",
        "Ger": "Ger",
        "Gallo": "Here Without You Tishman",
        "Mikey": "Senior AI Coke Twins",
    },
    "2025": {
        "Joey": "Stewed C",
        "Chris": "Ginny Sack",
        "Connor": "Sweeney.",
        "Deez": "Pigs on the 7th Rank",
        "Gallo": "Scampi",
        "Ger": "Ger",
        "Justin": "Life with Derrick",
        "Matt": "Art of the Deal",
        "Mikey": "Senior AI Coke Twins",
        "Mitch": "Sweeney Deez and Zaukas",
        "Papi": "Gorlock the Destroyer Schwartz",
        "Paul": "Team Daniel",
        "Sweeney": "Work Ass",
        "TJ": "Cookie Monster Golf Cart",
        "TK": "Team Obama Sopranos",
        "Boyle": "The Jackson Brownes",
    },
}


def canonical_team(season, owner):
    """Canonical team name for a season/owner, or None if unmapped."""
    return CANONICAL_TEAMS.get(str(season), {}).get(owner)
