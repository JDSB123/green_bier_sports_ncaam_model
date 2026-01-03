#!/usr/bin/env python3
"""
Team Name Mapping for ESPN <-> The Odds API

Handles differences like:
- "Montana St" vs "Montana State"
- "Florida Int'l" vs "Florida International"
- "N Colorado" vs "Northern Colorado"
"""
from __future__ import annotations

import re
from typing import Optional

# Explicit mappings for names that can't be algorithmically matched
EXPLICIT_MAPPINGS = {
    # Odds API name -> ESPN name
    "byu cougars": "byu cougars",  # May not exist in ESPN data
    "bethune-cookman wildcats": "bethune cookman wildcats",
    "n colorado bears": "northern colorado bears",
    "csu fullerton titans": "cal state fullerton titans",
    "csun matadors": "cal state northridge matadors",
    "boise state broncos": "boise state broncos",
    "kent state golden flashes": "kent state golden flashes",
    "gw revolutionaries": "george washington revolutionaries",
    "florida int'l golden panthers": "florida international panthers",
    "saint mary's gaels": "saint mary's gaels",
    "st mary's gaels": "saint mary's gaels",
    "ole miss rebels": "mississippi rebels",
    "uconn huskies": "connecticut huskies",
    "lsu tigers": "lsu tigers",
    "ucf knights": "ucf knights",
    "vcu rams": "vcu rams",
    "smu mustangs": "smu mustangs",
    "tcu horned frogs": "tcu horned frogs",
    "unlv runnin' rebels": "unlv rebels",
    "unlv rebels": "unlv rebels",
    "usc trojans": "usc trojans",
    "ucla bruins": "ucla bruins",
    "utep miners": "utep miners",
    "utsa roadrunners": "utsa roadrunners",
    "unc wilmington seahawks": "unc wilmington seahawks",
    "unc greensboro spartans": "unc greensboro spartans",
    "unc asheville bulldogs": "unc asheville bulldogs",
    "umkc kangaroos": "kansas city roos",
    "umbc retrievers": "umbc retrievers",
    "uab blazers": "uab blazers",
    "fiu golden panthers": "florida international panthers",
    "ualr trojans": "little rock trojans",
    "ul lafayette ragin' cajuns": "louisiana ragin' cajuns",
    "louisiana ragin' cajuns": "louisiana ragin' cajuns",
    "texas a&m-commerce lions": "texas a&m-commerce lions",
    "texas a&m-corpus christi islanders": "texas a&m-corpus christi islanders",
    "grand canyon antelopes": "grand canyon lopes",
    "jackson st tigers": "jackson state tigers",
    "alcorn st braves": "alcorn state braves",
    "grambling st tigers": "grambling tigers",
    "prairie view a&m panthers": "prairie view a&m panthers",
    "southern u jaguars": "southern jaguars",
    "alabama st hornets": "alabama state hornets",
    "mississippi valley st delta devils": "mississippi valley state delta devils",
    "arkansas-pine bluff golden lions": "arkansas pine bluff golden lions",
    "texas southern tigers": "texas southern tigers",
    "boston univ. terriers": "boston university terriers",
    "boston university terriers": "boston university terriers",
    "southeast missouri st redhawks": "se missouri state redhawks",
    "southeast missouri state redhawks": "se missouri state redhawks",
    "san jose st spartans": "san jose state spartans",
    "fresno st bulldogs": "fresno state bulldogs",
    "oregon st beavers": "oregon state beavers",
    "washington st cougars": "washington state cougars",
    "michigan st spartans": "michigan state spartans",
    "penn st nittany lions": "penn state nittany lions",
    "ohio st buckeyes": "ohio state buckeyes",
    "iowa st cyclones": "iowa state cyclones",
    "kansas st wildcats": "kansas state wildcats",
    "oklahoma st cowboys": "oklahoma state cowboys",
    "colorado st rams": "colorado state rams",
    "san diego st aztecs": "san diego state aztecs",
    "arizona st sun devils": "arizona state sun devils",
    "ball st cardinals": "ball state cardinals",
    "boise st broncos": "boise state broncos",
    "app state mountaineers": "appalachian state mountaineers",
    "appalachian st mountaineers": "appalachian state mountaineers",
    "arkansas st red wolves": "arkansas state red wolves",
    "idaho st bengals": "idaho state bengals",
    "indiana st sycamores": "indiana state sycamores",
    "illinois st redbirds": "illinois state redbirds",
    "utah st aggies": "utah state aggies",
    "montana st bobcats": "montana state bobcats",
    "weber st wildcats": "weber state wildcats",
    "portland st vikings": "portland state vikings",
    "northern arizona lumberjacks": "northern arizona lumberjacks",
    "sacramento st hornets": "sacramento state hornets",
    "cal poly mustangs": "cal poly mustangs",
    "csu bakersfield roadrunners": "cal state bakersfield roadrunners",
    "uc davis aggies": "uc davis aggies",
    "uc irvine anteaters": "uc irvine anteaters",
    "uc riverside highlanders": "uc riverside highlanders",
    "uc san diego tritons": "uc san diego tritons",
    "uc santa barbara gauchos": "uc santa barbara gauchos",
    "wichita st shockers": "wichita state shockers",
    "wright st raiders": "wright state raiders",
    "youngstown st penguins": "youngstown state penguins",
    "murray st racers": "murray state racers",
    "morehead st eagles": "morehead state eagles",
    "norfolk st spartans": "norfolk state spartans",
    "coppin st eagles": "coppin state eagles",
    "morgan st bears": "morgan state bears",
    "delaware st hornets": "delaware state hornets",
    "south carolina st bulldogs": "south carolina state bulldogs",
    "north carolina a&t aggies": "north carolina a&t aggies",
    "nc central eagles": "north carolina central eagles",
    "north carolina central eagles": "north carolina central eagles",
    "florida a&m rattlers": "florida a&m rattlers",
    "tennessee st tigers": "tennessee state tigers",
    "eastern kentucky colonels": "eastern kentucky colonels",
    "cleveland st vikings": "cleveland state vikings",
    "loyola (chi) ramblers": "loyola chicago ramblers",
    "loyola (md) greyhounds": "loyola maryland greyhounds",
    "loyola marymount lions": "loyola marymount lions",
    "mt. st. mary's mountaineers": "mount st. mary's mountaineers",
    "st. francis (pa) red flash": "saint francis red flash",
    "st. francis (bkn) terriers": "st. francis brooklyn terriers",
    "st. john's red storm": "st. john's red storm",
    "st. peter's peacocks": "saint peter's peacocks",
    "st. bonaventure bonnies": "st. bonaventure bonnies",
    "st. joseph's hawks": "saint joseph's hawks",
    "st. thomas - minnesota tommies": "st. thomas tommies",
    "le moyne dolphins": "le moyne dolphins",
    "sacred heart pioneers": "sacred heart pioneers",
    "fairleigh dickinson knights": "fairleigh dickinson knights",
    "liu sharks": "long island university sharks",
    "queens university royals": "queens royals",
}


def normalize_team_name(name: str) -> str:
    """
    Normalize team name for matching.

    Applies standard transformations to allow matching between
    ESPN and The Odds API team names.
    """
    if not name or (isinstance(name, float) and name != name):  # NaN check
        return ""

    name = str(name).lower().strip()

    # Apply explicit mappings first
    if name in EXPLICIT_MAPPINGS:
        name = EXPLICIT_MAPPINGS[name]

    # Handle St. vs State carefully
    # Process "School St Mascot" (e.g., "Montana St Bobcats") FIRST - these are STATE
    # Then process "St. Name" (e.g., "St. John's") - these are SAINT

    # Step 1: Handle "School St Mascot" -> "School State Mascot"
    # Match: word + " st" + space + word (school abbreviation pattern)
    name = re.sub(r"(\w)\s+st\s+(\w)", r"\1 state \2", name)  # Montana St Bobcats -> Montana State Bobcats
    name = re.sub(r"(\w)\s+st\.?$", r"\1 state", name)         # Montana St -> Montana State

    # Step 2: Handle "St. Name" at START of string -> "Saint Name"
    # This catches: St. John's, St. Mary's, St. Francis, etc.
    name = re.sub(r"^st\.?\s+", "saint ", name)  # St. John's -> Saint John's

    # Normalize apostrophes and dashes first
    name = name.replace("'", "'").replace("'", "'")
    name = name.replace("-", " ")

    # Expand directional abbreviations (only at start of name)
    # Be careful not to match apostrophe-s patterns
    if name.startswith("n ") or name.startswith("n. "):
        name = "northern " + name.split(" ", 1)[1]
    if name.startswith("e ") or name.startswith("e. "):
        name = "eastern " + name.split(" ", 1)[1]
    if name.startswith("w ") or name.startswith("w. "):
        name = "western " + name.split(" ", 1)[1]
    if name.startswith("s ") or name.startswith("s. "):
        name = "southern " + name.split(" ", 1)[1]

    # Expand abbreviations
    replacements = [
        (r"\bint'l\b", 'international'),
        (r'\buniv\.?\b', 'university'),
        (r'\bcsu\b', 'cal state'),
        (r'\buc\b', 'uc'),  # Keep UC as-is
        (r'\b&\b', 'and'),
    ]

    for pattern, replacement in replacements:
        name = re.sub(pattern, replacement, name)

    # Remove common mascot suffixes
    mascots = [
        'wildcats', 'tigers', 'bulldogs', 'bears', 'eagles', 'hawks',
        'huskies', 'cavaliers', 'blue devils', 'tar heels', 'spartans',
        'wolverines', 'buckeyes', 'hoosiers', 'boilermakers', 'hawkeyes',
        'badgers', 'gophers', 'jayhawks', 'sooners', 'longhorns', 'aggies',
        'razorbacks', 'volunteers', 'crimson tide', 'rebels', 'gamecocks',
        'hurricanes', 'seminoles', 'yellow jackets', 'red raiders',
        'horned frogs', 'cowboys', 'cyclones', 'mountaineers', 'red storm',
        'fighting irish', 'panthers', 'cardinals', 'bearcats', 'musketeers',
        'bluejays', 'golden eagles', 'pirates', 'gaels', 'dons', 'broncos',
        'cougars', 'aztecs', 'wolf pack', 'ramblers', 'bobcats', 'falcons',
        'crimson', 'big green', 'stags', 'golden griffins', 'dolphins',
        'owls', 'royals', 'jaspers', 'saints', 'purple eagles', 'hatters',
        'ospreys', 'lions', 'governors', 'bison', 'colonels', 'explorers',
        'knights', 'raiders', 'waves', 'flyers', 'friars', 'terriers',
        'paladins', 'thundering herd', 'chanticleers', 'dukes', 'flames',
        'crusaders', 'peacocks', 'redbirds', 'salukis', 'redhawks', 'tritons',
        'anteaters', 'highlanders', 'gauchos', 'matadors', 'titans', 'lopes',
        'shockers', 'penguins', 'racers', 'mean green', 'roadrunners',
        'rattlers', 'hornets', 'delta devils', 'braves', 'jaguars',
        'golden lions', 'bengals', 'sycamores', 'vikings', 'retrievers',
        'billikens', 'bonnies', 'red flash', 'pioneers', 'sharks', 'tommies',
        'golden flashes', 'chippewas', 'rockets', 'zips', 'redskins', 'herd',
        'leathernecks', 'blue hose', 'toreros', 'phoenix', 'flames', 'antelopes',
        'fighting illini', 'nittany lions', 'sun devils', 'beavers', 'ducks',
        'trojans', 'bruins', 'utes', 'buffaloes', 'miners', 'lobos', 'rams',
        'mustangs', 'owls', 'cougars', 'frogs', 'bears', 'kangaroos', 'roos',
        'islanders', 'seahawks', 'revolutionaries', 'screaming eagles', 'pride',
        'golden panthers', 'greyhounds', 'great danes', 'seawolves', 'terrapins',
    ]

    for mascot in mascots:
        if name.endswith(' ' + mascot):
            name = name[:-len(mascot)-1]
            break

    # Clean up extra spaces
    name = ' '.join(name.split())

    return name.strip()


def get_team_mapping(odds_teams: set[str], espn_teams: set[str]) -> dict[str, str]:
    """
    Build a mapping from Odds API team names to ESPN team names.

    Returns dict: {odds_team_name: espn_team_name}
    """
    mapping = {}

    # Normalize both sets
    odds_normalized = {normalize_team_name(t): t for t in odds_teams}
    espn_normalized = {normalize_team_name(t): t for t in espn_teams}

    # Match by normalized names
    for norm_name, odds_name in odds_normalized.items():
        if norm_name in espn_normalized:
            mapping[odds_name] = espn_normalized[norm_name]
        else:
            # Try fuzzy matching for remaining
            from difflib import get_close_matches
            matches = get_close_matches(norm_name, list(espn_normalized.keys()), n=1, cutoff=0.85)
            if matches:
                mapping[odds_name] = espn_normalized[matches[0]]

    return mapping


if __name__ == "__main__":
    # Test the normalization
    test_cases = [
        ("Montana St Bobcats", "montana state"),
        ("Florida Int'l Golden Panthers", "florida international"),
        ("N Colorado Bears", "northern colorado"),
        ("Loyola (Chi) Ramblers", "loyola chicago"),
        ("Boston Univ. Terriers", "boston university"),
        ("St. John's Red Storm", "saint john"),  # St. -> Saint
        ("BYU Cougars", "byu"),
        ("Utah St Aggies", "utah state"),
        ("St. Mary's Gaels", "saint mary"),
    ]

    print("Team Name Normalization Tests:")
    for name, expected_prefix in test_cases:
        result = normalize_team_name(name)
        status = "OK" if result.startswith(expected_prefix) else "FAIL"
        print(f"  {status}: '{name}' -> '{result}'")
