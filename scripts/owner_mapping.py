"""Owner mapping across seasons and team names."""

# All owners who have appeared across any season
ALL_OWNERS = [
    "Sweeney", "Joey", "Justin", "TK", "Deez", "Mitch", "Chris",
    "TJ", "Papi", "Matt", "Paul", "Connor", "Gallo", "Ger",
    "Mikey", "Boyle", "Joe", "Ron", "Zaukas", "Oscar", "Simon",
]

# Normalize owner names (handle case variations)
OWNER_NORMALIZE = {name.lower(): name for name in ALL_OWNERS}


def resolve_owner(team_name_raw, explicit_owner=None):
    """Resolve owner from explicit name or team name."""
    if explicit_owner:
        name = explicit_owner.strip().rstrip("-").strip()
        normalized = OWNER_NORMALIZE.get(name.lower())
        if normalized:
            return normalized
        return name  # Return as-is if not in our list

    if team_name_raw:
        return team_name_raw.strip()

    return explicit_owner or team_name_raw
