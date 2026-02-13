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
