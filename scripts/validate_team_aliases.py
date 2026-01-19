#!/usr/bin/env python3
"""
Pre-commit validation script for team alias consistency.

Ensures that hardcoded TEAM_NAME_ALIASES dict in odds_sync.py matches
the team_aliases table in the database.

Usage:
    python scripts/validate_team_aliases.py              # Validate only
    python scripts/validate_team_aliases.py --sync       # Sync dict to DB
    python scripts/validate_team_aliases.py --generate   # Generate dict from DB

Exit codes:
    0 - All aliases consistent
    1 - Inconsistencies found (use --sync to fix)
"""

import ast
import os
import re
import sys
from pathlib import Path

# Allow running without psycopg2 for pre-commit checks
try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


ODDS_SYNC_PATH = Path(__file__).parent.parent / "services" / "prediction-service-python" / "app" / "odds_sync.py"


def extract_hardcoded_aliases() -> dict[str, str]:
    """Extract TEAM_NAME_ALIASES dict from odds_sync.py source code."""
    if not ODDS_SYNC_PATH.exists():
        print(f"ERROR: {ODDS_SYNC_PATH} not found")
        sys.exit(1)

    source = ODDS_SYNC_PATH.read_text(encoding="utf-8")

    # Find the TEAM_NAME_ALIASES = { ... } block
    pattern = r"TEAM_NAME_ALIASES\s*=\s*\{([^}]+)\}"
    match = re.search(pattern, source, re.DOTALL)

    if not match:
        print("ERROR: Could not find TEAM_NAME_ALIASES dict in odds_sync.py")
        sys.exit(1)

    # Parse the dict entries
    dict_content = "{" + match.group(1) + "}"

    # Clean up comments for AST parsing
    lines = []
    for line in dict_content.split("\n"):
        # Remove inline comments
        if "#" in line:
            line = line[:line.index("#")]
        lines.append(line)

    dict_content = "\n".join(lines)

    try:
        return ast.literal_eval(dict_content)
    except (SyntaxError, ValueError) as e:
        print(f"ERROR: Could not parse TEAM_NAME_ALIASES: {e}")
        sys.exit(1)


def get_database_url() -> str:
    """Get database URL from environment or default."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        # Default for local development
        url = "postgres://ncaam:ncaam_local@localhost:5432/ncaam_predictions"
    return url


def fetch_db_aliases() -> dict[str, str]:
    """Fetch all aliases from team_aliases table."""
    if not HAS_PSYCOPG2:
        print("WARNING: psycopg2 not installed, skipping database validation")
        return {}

    db_url = get_database_url()

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Get alias -> canonical_name mappings
        cur.execute("""
            SELECT ta.alias, t.canonical_name
            FROM team_aliases ta
            JOIN teams t ON ta.team_id = t.id
            ORDER BY ta.alias
        """)

        aliases = {row[0]: row[1] for row in cur.fetchall()}

        cur.close()
        conn.close()

        return aliases
    except psycopg2.Error as e:
        print(f"WARNING: Could not connect to database: {e}")
        return {}


def compare_aliases(
    hardcoded: dict[str, str],
    db_aliases: dict[str, str]
) -> tuple[set[str], set[str], dict[str, tuple[str, str]]]:
    """
    Compare hardcoded aliases with database.

    Returns:
        - only_in_code: Aliases only in hardcoded dict
        - only_in_db: Aliases only in database
        - mismatched: Aliases with different canonical names {alias: (code_value, db_value)}
    """
    code_keys = set(hardcoded.keys())
    db_keys = set(db_aliases.keys())

    only_in_code = code_keys - db_keys
    only_in_db = db_keys - code_keys

    mismatched = {}
    for key in code_keys & db_keys:
        if hardcoded[key] != db_aliases[key]:
            mismatched[key] = (hardcoded[key], db_aliases[key])

    return only_in_code, only_in_db, mismatched


def sync_to_database(hardcoded: dict[str, str]) -> int:
    """Sync hardcoded aliases to database."""
    if not HAS_PSYCOPG2:
        print("ERROR: psycopg2 required for --sync")
        return 1

    db_url = get_database_url()

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        inserted = 0
        for alias, canonical in hardcoded.items():
            # Find team_id for canonical name
            cur.execute(
                "SELECT id FROM teams WHERE canonical_name = %s",
                (canonical,)
            )
            row = cur.fetchone()

            if not row:
                print(f"  SKIP: No team found for canonical_name='{canonical}'")
                continue

            team_id = row[0]

            # Insert alias if not exists
            cur.execute("""
                INSERT INTO team_aliases (team_id, alias, source)
                VALUES (%s, %s, 'odds_sync_dict')
                ON CONFLICT (alias, source) DO UPDATE SET team_id = EXCLUDED.team_id
            """, (team_id, alias))

            inserted += 1

        conn.commit()
        cur.close()
        conn.close()

        print(f"Synced {inserted} aliases to database")
        return 0

    except psycopg2.Error as e:
        print(f"ERROR: Database sync failed: {e}")
        return 1


def generate_dict_from_db() -> int:
    """Generate Python dict code from database aliases."""
    if not HAS_PSYCOPG2:
        print("ERROR: psycopg2 required for --generate")
        return 1

    db_aliases = fetch_db_aliases()

    if not db_aliases:
        print("No aliases found in database")
        return 1

    print("# Auto-generated from team_aliases table")
    print("TEAM_NAME_ALIASES = {")

    # Group by canonical name for readability
    by_canonical: dict[str, list] = {}
    for alias, canonical in sorted(db_aliases.items()):
        if canonical not in by_canonical:
            by_canonical[canonical] = []
        by_canonical[canonical].append(alias)

    for canonical in sorted(by_canonical.keys()):
        aliases = by_canonical[canonical]
        if len(aliases) == 1 and aliases[0] == canonical:
            continue  # Skip identity mappings
        print(f"    # {canonical}")
        for alias in sorted(aliases):
            if alias != canonical:
                print(f'    "{alias}": "{canonical}",')

    print("}")
    return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate team alias consistency")
    parser.add_argument("--sync", action="store_true", help="Sync hardcoded aliases to database")
    parser.add_argument("--generate", action="store_true", help="Generate dict from database")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.generate:
        return generate_dict_from_db()

    # Extract hardcoded aliases
    hardcoded = extract_hardcoded_aliases()
    print(f"Found {len(hardcoded)} hardcoded aliases in odds_sync.py")

    if args.sync:
        return sync_to_database(hardcoded)

    # Fetch database aliases
    db_aliases = fetch_db_aliases()

    if not db_aliases:
        print("WARNING: Could not fetch database aliases, checking code-only...")
        print(f"✅ Hardcoded aliases validated ({len(hardcoded)} entries)")
        return 0

    print(f"Found {len(db_aliases)} aliases in database")

    # Compare
    only_in_code, only_in_db, mismatched = compare_aliases(hardcoded, db_aliases)

    has_issues = False

    if only_in_code:
        has_issues = True
        print(f"\n⚠️  {len(only_in_code)} aliases in code but NOT in database:")
        for alias in sorted(only_in_code):
            print(f"    '{alias}' -> '{hardcoded[alias]}'")
        print("    Run with --sync to add these to the database")

    if mismatched:
        has_issues = True
        print(f"\n❌ {len(mismatched)} aliases with DIFFERENT canonical names:")
        for alias, (code_val, db_val) in sorted(mismatched.items()):
            print(f"    '{alias}': code='{code_val}', db='{db_val}'")

    if args.verbose and only_in_db:
        print(f"\nℹ️  {len(only_in_db)} aliases in database but not in code (OK):")
        for alias in sorted(list(only_in_db)[:10]):
            print(f"    '{alias}' -> '{db_aliases[alias]}'")
        if len(only_in_db) > 10:
            print(f"    ... and {len(only_in_db) - 10} more")

    if has_issues:
        print("\n❌ Validation FAILED - aliases inconsistent")
        return 1

    print(f"\n✅ All {len(hardcoded)} hardcoded aliases are consistent with database")
    return 0


if __name__ == "__main__":
    sys.exit(main())
