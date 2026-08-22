"""Owner mapping across seasons and team names.

Owner consolidation rules (same person, different names used):
- Matt = Ron
- Boyle = Joe = North Willow
- Zaukas = Paul
- Papi = Simon
- Ger = Gerry Lewis
- Mikey = Oscar

Kevin joined for 2026 and took Papi's spot; Papi played 2022-2025 and stays in
every mapping below so his history keeps resolving. The league is still 16 teams
a year — see SEASON_OWNERS for who actually plays in a given season.
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

# Every person who has ever held a team, active or not. Not a season roster —
# it's 17 names for a 16-team league because Kevin replaced Papi in 2026.
ALL_OWNERS = [
    "Sweeney", "Joey", "Justin", "TK", "Deez", "Mitch", "Chris",
    "TJ", "Papi", "Matt", "Paul", "Connor", "Gallo", "Ger",
    "Mikey", "Boyle", "Kevin",
]

# Normalize owner names (handle case variations)
OWNER_NORMALIZE = {name.lower(): name for name in ALL_OWNERS}

# Who actually played each season. Only listed where it differs from "everyone
# in ALL_OWNERS": 2022-2025 were the original 16, 2026 swaps Papi out for Kevin.
SEASON_OWNERS = {
    "2026": [
        "Sweeney", "Joey", "Justin", "TK", "Deez", "Mitch", "Chris",
        "TJ", "Kevin", "Matt", "Paul", "Connor", "Gallo", "Ger",
        "Mikey", "Boyle",
    ],
}


def active_owners(season):
    """The 16 owners who played a season, defaulting to the original lineup."""
    return SEASON_OWNERS.get(str(season), [o for o in ALL_OWNERS if o != "Kevin"])


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
    "2026": {
        "Joey": "Stewed C",
        "Chris": "Ginny Sack",
        "Connor": "Healthy as a Fucking Rhino",
        "Deez": "Pigs on the 7th Rank",
        "Gallo": "Free Paid",
        "Ger": "Ger",
        "Justin": "Phenom",
        "Kevin": "Tuanigamanuolepola Donny",
        "Matt": "The Art of the Deal",
        "Mikey": "Pelosi's Powder",
        "Mitch": "Charles Dickens",
        "Paul": "Hello Darkness My Old Friend",
        "Sweeney": "Work Ass",
        "TJ": "Boone",
        "TK": "Nick Wright Barely Legal",
        "Boyle": "Shough and F#ck",
    },
}


def canonical_team(season, owner):
    """Canonical team name for a season/owner, or None if unmapped."""
    return CANONICAL_TEAMS.get(str(season), {}).get(owner)


# Yahoo team name -> owner, per season (from the manual spreadsheet). Keyed by the
# team_name recorded in yahoo_data/<season>/managers.json. Distinct from
# ranking_parser.TEAM_OWNER_MAP, which matches loose team-name patterns in the PDFs.
YAHOO_TEAM_OWNERS = {
    "2022": {
        "Double Underhooks": "Sweeney",
        "GLOV\u00ca SIDE BRODEUR": "Matt",
        "Free Paid": "Gallo",
        "The Much Obliged": "Chris",
        "Alexander's Unreal Team": "Deez",
        "Tank Unloders": "Mitch",
        "The Jose Trevinos": "Boyle",
        "Vox Populi": "TK",
        "From You": "TJ",
        "Pots & Pans": "Joey",
        "Joe would rig a charity event": "Connor",
        "HAHAHAHAHAHAHA": "Ger",
        "The Ed Orgeron Alumni Assoc.": "Paul",
        "Uhhh THRIIIIISISSSHHHH": "Papi",
        "Tony the phenom": "Justin",
        "Senior Sack Dumpers": "Mikey",
    },
    "2023": {
        "Work Ass": "Sweeney",
        "WHERESTUA": "Matt",
        "Free Paid again..": "Gallo",
        "Sansa Ludacris": "Chris",
        "Alexander's Unreal Team": "Deez",
        "Willow Street Walruses": "Mitch",
        "The Lean Mean Fightin MaSheets": "Boyle",
        "Morior Invictus": "TK",
        "Cap Stoppers": "TJ",
        "Garlic Aioli": "Joey",
        "Sweeney.": "Connor",
        "🍾💼🥰": "Ger",
        "Formerly Known as Mousecop": "Paul",
        "Gorlock the destroyer Schwartz": "Papi",
        "Tony the phenom": "Justin",
        "Sr. Sack Dumping Scum Bags": "Mikey",
    },
    "2024": {
        "Work Ass": "Sweeney",
        "WHERESTUA": "Matt",
        "Here Without You Tishman": "Gallo",
        "Sansa Ludacris": "Chris",
        "Pigs on the 7th Rank": "Deez",
        "Deserves to be Shot": "Mitch",
        "Gotham Rogues": "Boyle",
        "Hand Me the Piss": "TK",
        "Cap Stoppers": "TJ",
        "Stewed C": "Joey",
        "Sweeney.": "Connor",
        "🍾💼🥰": "Ger",
        "Marvin\u2019s Receiver Room": "Paul",
        "Gorlock the destroyer Schwartz": "Papi",
        "Life with Derrick": "Justin",
        "Senior AI Coke Twins": "Mikey",
    },
    "2025": {
        "Work Ass": "Sweeney",
        "The Art of the Deal": "Matt",
        "Scampi": "Gallo",
        "Ginny Sack": "Chris",
        "Pigs on the 7th Rank": "Deez",
        "Sweeney Deez and Zaukas": "Mitch",
        "The Jackson Brownes": "Boyle",
        "Team OBAMA SOPRANOS": "TK",
        "Cookie Monster Golf Cart": "TJ",
        "Stewed C": "Joey",
        "Sweeney.": "Connor",
        "🍾💼🥰": "Ger",
        "Team Daniel": "Paul",
        "Gorlock the destroyer Schwartz": "Papi",
        "Life with Derrick": "Justin",
        "Senior AI Coke Twins": "Mikey",
    },
    # Taken from the league page before the draft, so these are the names as
    # typed, not as Yahoo returns them — confirm against managers.json after the
    # first successful 2026 pull.
    "2026": {
        "Work Ass": "Sweeney",
        "The Art of the Deal": "Matt",
        "Scampi": "Gallo",
        "Ginny Sack": "Chris",
        "Pigs on the 7th Rank": "Deez",
        "Charles Dickens": "Mitch",
        "The Jackson Brownes": "Boyle",
        "Nick Wright Barely Legal": "TK",
        "Boone": "TJ",
        "Stewed C": "Joey",
        "Healthy as a Fucking Rhino": "Connor",
        "🍾💼🥰": "Ger",
        "Team Daniel": "Paul",
        "Tuanigamanuolepola Donny": "Kevin",
        "Phenom": "Justin",
        "Pelosis Powder": "Mikey",
    },
}


def owner_from_yahoo_team(season, team_name):
    """Owner for a Yahoo team name in a season, or None if unmapped."""
    return YAHOO_TEAM_OWNERS.get(str(season), {}).get(team_name)
