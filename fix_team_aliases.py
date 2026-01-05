#!/usr/bin/env python3
import os, sys
sys.path.insert(0, '/app')
from sqlalchemy import create_engine, text

def get_db_password():
    try:
        with open('/run/secrets/db_password', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.getenv('DB_PASSWORD', 'ncaam_dev_password')

DB_PASSWORD = get_db_password()
DATABASE_URL = f"postgresql://ncaam:{DB_PASSWORD}@postgres:5432/ncaam"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Mapping of Odds API names to correct canonical names
CORRECT_MAPPINGS = {
    "SE Louisiana Lions": "Southeastern Louisiana",
    "Grand Canyon Antelopes": "Grand Canyon",
    "Lipscomb Bisons": "Lipscomb",
    "Tenn-Martin Skyhawks": "UT Martin",
    "Montana St Bobcats": "Montana St.",
    "UIC Flames": "Illinois-Chicago",
    "SE Missouri St Redhawks": "Southeast Missouri St.",
    "Northwestern St Demons": "Northwestern St.",
    "UT Rio Grande Valley Vaqueros": "UT Rio Grande Valley",
    "Prairie View Panthers": "Prairie View A&M",
    "North Dakota Fighting Hawks": "North Dakota",
    "Hawai'i Rainbow Warriors": "Hawai'i",
    "Furman Paladins": "Furman",
    "Sacred Heart Pioneers": "Sacred Heart",
    "Loyola (Chi) Ramblers": "Loyola Chicago",
    "Presbyterian Blue Hose": "Presbyterian",
    "Miss Valley St Delta Devils": "Mississippi Valley St.",
    "St. Thomas (MN) Tommies": "St. Thomas (MN)",
    "Loyola (MD) Greyhounds": "Loyola (MD)",
    "Fort Wayne Mastodons": "Purdue Fort Wayne",
    "Howard Bison": "Howard",
    "Bucknell Bison": "Bucknell",
    "Arkansas-Pine Bluff Golden Lions": "Arkansas-Pine Bluff",
    "Murray St Racers": "Murray St.",
    "CSU Northridge Matadors": "Cal St. Northridge",
    "Southern Utah Thunderbirds": "Southern Utah",
    "Quinnipiac Bobcats": "Quinnipiac",
    "Austin Peay Governors": "Austin Peay",
    "Southern Indiana Screaming Eagles": "Southern Indiana",
    "Queens University Royals": "Queens (NC)",
    "San José St Spartans": "San Jose St.",
    "Idaho State Bengals": "Idaho St.",
    "Idaho Vandals": "Idaho",
    "Delaware Blue Hens": "Delaware",
    "North Dakota St Bison": "North Dakota St.",
    "CSU Bakersfield Roadrunners": "Cal St. Bakersfield",
    "UMKC Kangaroos": "Kansas City",
    "Oregon St Beavers": "Oregon St.",
    "Montana Grizzlies": "Montana",
    "CSU Fullerton Titans": "Cal St. Fullerton",
    "Merrimack Warriors": "Merrimack"
}

with engine.connect() as conn:
    # First, remove the bad aliases added by the broken auto-fix
    bad_aliases = list(CORRECT_MAPPINGS.keys())
    if bad_aliases:
        placeholders = ','.join(['?'] * len(bad_aliases))
        conn.execute(text(f"""
            DELETE FROM team_aliases
            WHERE alias IN ({','.join(['%s'] * len(bad_aliases))})
            AND source = 'the_odds_api'
        """), bad_aliases)
        print(f"Removed {len(bad_aliases)} incorrect aliases")

    # Now add the correct mappings
    fixed_count = 0
    for odds_name, canonical_name in CORRECT_MAPPINGS.items():
        try:
            # Check if the canonical team exists
            result = conn.execute(text("SELECT id FROM teams WHERE canonical_name = ?"), [canonical_name])
            team_row = result.fetchone()

            if team_row:
                # Add the alias
                conn.execute(text("""
                    INSERT INTO team_aliases (team_id, alias, source, confidence)
                    VALUES (?, ?, 'the_odds_api', 1.0)
                    ON CONFLICT (alias, source) DO NOTHING
                """), [team_row.id, odds_name])
                print(f"✓ Added alias: \"{odds_name}\" → \"{canonical_name}\"")
                fixed_count += 1
            else:
                print(f"✗ Canonical team not found: \"{canonical_name}\" for \"{odds_name}\"")

        except Exception as e:
            print(f"✗ Error adding alias for \"{odds_name}\": {e}")

    conn.commit()
    print(f"\nFixed {fixed_count} of {len(CORRECT_MAPPINGS)} team aliases")