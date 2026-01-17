#!/usr/bin/env python3
"""
Test team matching for today's games (Jan 5, 2026).

This script:
1. Tests each team name from multiple sources against resolve_team_name()
2. Shows source identifiers (ESPN, Odds API, Barttorvik) for each variant
3. Reports match rate and any failures
"""

import os
import sys
from datetime import date

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Today's games - with how each source names them
# Format: {source: (away_team, home_team)}
TODAYS_GAMES_BY_SOURCE = [
    # Game 1: Columbia @ Cornell (4:00 PM CST)
    {"espn": ("Columbia", "Cornell"),
     "odds_api": ("Columbia Lions", "Cornell Big Red"),
     "barttorvik": ("Columbia", "Cornell")},

    # Game 2: Nebraska @ Ohio St (5:30 PM CST)
    {"espn": ("Nebraska", "Ohio St"),
     "odds_api": ("Nebraska Cornhuskers", "Ohio State Buckeyes"),
     "barttorvik": ("Nebraska", "Ohio St.")},

    # Game 3: William & Mary @ Coll of Charleston (6:00 PM CST)
    {"espn": ("William & Mary", "Coll of Charleston"),
     "odds_api": ("William & Mary Tribe", "Charleston Cougars"),
     "barttorvik": ("William & Mary", "Charleston")},

    # Game 4: Wisc Milwaukee @ Wisc Green Bay (6:00 PM CST)
    {"espn": ("Wisc Milwaukee", "Wisc Green Bay"),
     "odds_api": ("Milwaukee Panthers", "Green Bay Phoenix"),
     "barttorvik": ("Milwaukee", "Green Bay")},

    # Game 5: Pennsylvania @ Princeton (6:00 PM CST)
    {"espn": ("Pennsylvania", "Princeton"),
     "odds_api": ("Penn Quakers", "Princeton Tigers"),
     "barttorvik": ("Penn", "Princeton")},

    # Game 6: Dartmouth @ Harvard (6:00 PM CST)
    {"espn": ("Dartmouth", "Harvard"),
     "odds_api": ("Dartmouth Big Green", "Harvard Crimson"),
     "barttorvik": ("Dartmouth", "Harvard")},

    # Game 7: Yale @ Brown (6:00 PM CST)
    {"espn": ("Yale", "Brown"),
     "odds_api": ("Yale Bulldogs", "Brown Bears"),
     "barttorvik": ("Yale", "Brown")},

    # Game 8: Oregon @ Rutgers (6:00 PM CST)
    {"espn": ("Oregon", "Rutgers"),
     "odds_api": ("Oregon Ducks", "Rutgers Scarlet Knights"),
     "barttorvik": ("Oregon", "Rutgers")},

    # Game 9: USC @ Michigan St (7:30 PM CST)
    {"espn": ("USC", "Michigan St"),
     "odds_api": ("USC Trojans", "Michigan State Spartans"),
     "barttorvik": ("USC", "Michigan St.")},
]

# Tennessee variant test cases - critical for avoiding false matches
VARIANT_TEST_CASES = [
    # (input_variant, expected_canonical, should_match)
    ("Tennessee", "Tennessee", True),
    ("Tennessee State", "Tennessee St.", True),
    ("Tennessee St", "Tennessee St.", True),
    ("Tennessee St.", "Tennessee St.", True),
    ("Tennessee St Tigers", "Tennessee St.", True),
    ("East Tennessee St.", "ETSU", True),
    ("East Tennessee State", "ETSU", True),
    ("Tennessee Tech", "Tennessee Tech", True),
    ("Tennessee Martin", "UT Martin", True),
    ("UT Martin", "UT Martin", True),
    ("Middle Tennessee", "Middle Tennessee", True),
    ("Middle Tennessee Blue Raiders", "Middle Tennessee", True),
    # These should NOT match Tennessee (the SEC team)
    ("Tennessee State", "Tennessee", False),
    ("Tennessee Martin", "Tennessee", False),
    ("East Tennessee St.", "Tennessee", False),
]


def test_team_matching():
    """Test team name resolution against PostgreSQL."""
    from sqlalchemy import create_engine, text

    # Get database connection
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        try:
            with open("/run/secrets/db_password") as f:
                db_password = f.read().strip()
            database_url = f"postgresql://ncaam:{db_password}@postgres:5432/ncaam"
        except FileNotFoundError:
            # Local development
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql://ncaam:ncaam@localhost:5432/ncaam"
            )

    engine = create_engine(database_url, pool_pre_ping=True)

    print("=" * 70)
    print("GREEN BIER SPORT VENTURES - Team Matching Test")
    print(f"Date: {date.today()}")
    print("=" * 70)
    print()

    # ─────────────────────────────────────────────────────────────────────
    # TEST 1: Today's Games by Source
    # ─────────────────────────────────────────────────────────────────────
    print("TEST 1: TODAY'S GAMES BY SOURCE (Jan 5, 2026)")
    print("-" * 70)
    print()

    results_by_source = {"espn": [], "odds_api": [], "barttorvik": []}
    all_resolved = {}  # Track canonical names for cross-validation

    with engine.connect() as conn:
        for game_idx, game in enumerate(TODAYS_GAMES_BY_SOURCE, 1):
            print(f"  GAME {game_idx}:")

            game_canonical = {"away": set(), "home": set()}

            for source in ["espn", "odds_api", "barttorvik"]:
                if source not in game:
                    continue

                away, home = game[source]

                for team_name, position in [(away, "away"), (home, "home")]:
                    result = conn.execute(
                        text("SELECT resolve_team_name(:name)"),
                        {"name": team_name}
                    )
                    resolved = result.scalar()

                    if resolved:
                        status = "✓"
                        results_by_source[source].append(True)
                        game_canonical[position].add(resolved)
                    else:
                        status = "✗"
                        results_by_source[source].append(False)

                    src_label = source.upper().ljust(10)
                    print(f"    {status} [{src_label}] \"{team_name}\"")
                    print(f"                     → {resolved or 'NOT FOUND'}")

            # Check cross-source consistency
            away_match = len(game_canonical["away"]) == 1
            home_match = len(game_canonical["home"]) == 1
            if away_match and home_match:
                print("    ✓ CROSS-SOURCE: All sources resolve to same teams")
            else:
                if not away_match:
                    print(f"    ✗ CROSS-SOURCE: Away team mismatch: "
                          f"{game_canonical['away']}")
                if not home_match:
                    print(f"    ✗ CROSS-SOURCE: Home team mismatch: "
                          f"{game_canonical['home']}")
            print()

    # Summary by source
    print("  MATCH RATE BY SOURCE:")
    for source, results in results_by_source.items():
        if results:
            matched = sum(results)
            total = len(results)
            rate = 100.0 * matched / total
            status = "✓" if rate == 100 else "⚠" if rate >= 90 else "✗"
            print(f"    {status} {source.upper():12} {matched}/{total} "
                  f"({rate:.1f}%)")
    print()

    # ─────────────────────────────────────────────────────────────────────
    # TEST 2: Tennessee Variant Protection
    # ─────────────────────────────────────────────────────────────────────
    print("TEST 2: TENNESSEE VARIANT PROTECTION")
    print("-" * 70)
    print("  Testing that Tennessee State != Tennessee (critical)")
    print()

    variant_passed = 0
    variant_failed = 0

    with engine.connect() as conn:
        for variant, expected, should_match in VARIANT_TEST_CASES:
            result = conn.execute(
                text("SELECT resolve_team_name(:name)"),
                {"name": variant}
            )
            resolved = result.scalar()

            if should_match:
                if resolved == expected:
                    status = "✓"
                    variant_passed += 1
                else:
                    status = "✗"
                    variant_failed += 1
                print(f"  {status} \"{variant}\"")
                print(f"       → {resolved or 'NULL'} (expected: {expected})")
            else:
                if resolved != expected:
                    status = "✓"
                    variant_passed += 1
                    print(f"  {status} \"{variant}\"")
                    print(f"       → {resolved or 'NULL'} "
                          f"(correctly NOT \"{expected}\")")
                else:
                    status = "✗"
                    variant_failed += 1
                    print(f"  {status} \"{variant}\"")
                    print(f"       → {resolved} (BUG: matched \"{expected}\")")

    print()
    total_variant = variant_passed + variant_failed
    print(f"  VARIANT PROTECTION: {variant_passed}/{total_variant} passed")
    print()

    # ─────────────────────────────────────────────────────────────────────
    # TEST 3: Database Statistics
    # ─────────────────────────────────────────────────────────────────────
    print("TEST 3: DATABASE STATISTICS")
    print("-" * 70)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM teams"))
        team_count = result.scalar()
        print(f"  Total Teams: {team_count}")

        result = conn.execute(text("SELECT COUNT(*) FROM team_aliases"))
        alias_count = result.scalar()
        print(f"  Total Aliases: {alias_count}")

        result = conn.execute(
            text("SELECT COUNT(DISTINCT team_id) FROM team_ratings")
        )
        rated_count = result.scalar()
        print(f"  Teams with Ratings: {rated_count}")

        result = conn.execute(text("""
            SELECT t.canonical_name, COUNT(ta.id) as alias_count
            FROM teams t
            LEFT JOIN team_aliases ta ON t.id = ta.team_id
            WHERE t.canonical_name LIKE '%Tennessee%'
               OR t.canonical_name IN ('ETSU', 'UT Martin')
            GROUP BY t.canonical_name
            ORDER BY t.canonical_name
        """))

        print()
        print("  Tennessee-related teams:")
        for row in result:
            print(f"    - {row.canonical_name}: {row.alias_count} aliases")

    print()
    print("=" * 70)

    # Overall assessment
    all_results = []
    for results in results_by_source.values():
        all_results.extend(results)

    overall_rate = 100.0 * sum(all_results) / len(all_results) if all_results else 0
    overall_pass = overall_rate >= 90 and variant_failed == 0

    if overall_pass:
        print(f"OVERALL: PASSED ({overall_rate:.1f}% match rate)")
    else:
        print("OVERALL: FAILED")
        if overall_rate < 90:
            print(f"   - Match rate below 90%: {overall_rate:.1f}%")
        if variant_failed > 0:
            print(f"   - {variant_failed} variant tests failed")

    return overall_pass


if __name__ == "__main__":
    success = test_team_matching()
    sys.exit(0 if success else 1)
