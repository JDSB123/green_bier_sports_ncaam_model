#!/usr/bin/env python3
"""
Import standardized team name mappings from R package datasets.

This script imports team name variants from established R packages:
- ncaahoopR: Maps variants across NCAA, ESPN, WarrenNolan, Trank (Bart Torvik), 247Sports
- hoopR: Maps ESPN and KenPom variants
- toRvik/cbbdata: Bart Torvik native formats

Usage:
    # From CSV exported from R
    python import_standardized_team_mappings.py --source ncaahoopr --input ncaahoopr_dict.csv
    
    # From JSON
    python import_standardized_team_mappings.py --source hoopr --input hoopr_teams_links.json --format json
    
    # Dry run (preview changes)
    python import_standardized_team_mappings.py --source torvik --input torvik_teams.csv --dry-run
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from sqlalchemy import create_engine, text
    HAS_SQLALCHEMY = True
except ImportError:
    print("ERROR: sqlalchemy not installed. Install with: pip install sqlalchemy psycopg2-binary")
    sys.exit(1)


def get_db_engine():
    """Get database engine from environment."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        db_host = os.environ.get("DB_HOST", "localhost")
        db_port = os.environ.get("DB_PORT", "5450")
        db_user = os.environ.get("DB_USER", "ncaam")
        db_name = os.environ.get("DB_NAME", "ncaam")
        db_pass = os.environ.get("DB_PASSWORD", "ncaam")
        
        # Try secrets file
        pw_file = Path("/run/secrets/db_password")
        if pw_file.exists():
            db_pass = pw_file.read_text().strip()
        
        db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    return create_engine(db_url, pool_pre_ping=True)


def load_ncaahoopr_dict(csv_path: Path) -> List[Tuple[str, str, str]]:
    """
    Load ncaahoopR dict dataset.
    
    Expected CSV format (from R: write.csv(dict, "ncaahoopr_dict.csv")):
    - Columns: NCAA, ESPN, WarrenNolan, Trank, X247Sports, etc.
    - Each row is a team with variants across sources
    
    Returns: List of (canonical_name, alias, source) tuples
    """
    mappings = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # ncaahoopR uses NCAA as canonical
            canonical = row.get('NCAA', '').strip()
            if not canonical:
                continue
            
            # Map each source column to our source names
            source_mapping = {
                'ESPN': 'espn',
                'WarrenNolan': 'warren_nolan',
                'Trank': 'barttorvik',  # Trank is Bart Torvik's site
                'X247Sports': '247sports',
            }
            
            for csv_col, source_name in source_mapping.items():
                alias = row.get(csv_col, '').strip()
                if alias and alias != canonical:
                    mappings.append((canonical, alias, source_name))
    
    return mappings


def load_hoopr_teams_links(json_path: Path) -> List[Tuple[str, str, str]]:
    """
    Load hoopR teams_links dataset.
    
    Expected JSON format:
    {
        "team_name": {
            "espn_id": 123,
            "espn_name": "Team Name",
            "kenpom_id": "team-id",
            "kenpom_name": "Team Name"
        }
    }
    
    Returns: List of (canonical_name, alias, source) tuples
    """
    mappings = []
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for team_name, links in data.items():
        canonical = team_name.strip()
        if not canonical:
            continue
        
        # ESPN variants
        if 'espn_name' in links:
            alias = links['espn_name'].strip()
            if alias and alias != canonical:
                mappings.append((canonical, alias, 'espn'))
        
        # KenPom variants
        if 'kenpom_name' in links:
            alias = links['kenpom_name'].strip()
            if alias and alias != canonical:
                mappings.append((canonical, alias, 'kenpom'))
    
    return mappings


def load_torvik_teams(csv_path: Path) -> List[Tuple[str, str, str]]:
    """
    Load toRvik/cbbdata team names.
    
    Expected CSV format:
    - team_name column with Bart Torvik canonical names
    - May include variants in other columns
    
    Returns: List of (canonical_name, alias, source) tuples
    """
    mappings = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            canonical = row.get('team_name', '').strip()
            if not canonical:
                continue
            
            # toRvik uses Bart Torvik names as canonical
            # Add as barttorvik source variant
            mappings.append((canonical, canonical, 'barttorvik'))
            
            # Check for variant columns
            for col in row:
                if col != 'team_name' and row[col]:
                    alias = row[col].strip()
                    if alias and alias != canonical:
                        mappings.append((canonical, alias, 'barttorvik'))
    
    return mappings


def load_generic_csv(csv_path: Path, canonical_col: str = 'canonical', 
                     alias_col: str = 'alias', source_col: str = 'source') -> List[Tuple[str, str, str]]:
    """
    Load generic CSV with canonical, alias, source columns.
    
    Returns: List of (canonical_name, alias, source) tuples
    """
    mappings = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            canonical = row.get(canonical_col, '').strip()
            alias = row.get(alias_col, '').strip()
            source = row.get(source_col, 'manual').strip()
            
            if canonical and alias:
                mappings.append((canonical, alias, source))
    
    return mappings


def resolve_canonical_to_team_id(engine, canonical_name: str) -> Optional[str]:
    """Resolve canonical name to team UUID."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id FROM teams WHERE canonical_name = :canonical"),
            {"canonical": canonical_name}
        ).fetchone()
        
        if result:
            return str(result[0])
        return None


def find_team_by_alias(engine, alias: str) -> Optional[Tuple[str, str]]:
    """
    Find team by alias (canonical_name, team_id).
    
    Returns: (canonical_name, team_id) or None
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT t.canonical_name, t.id::text
                FROM teams t
                JOIN team_aliases ta ON t.id = ta.team_id
                WHERE LOWER(ta.alias) = LOWER(:alias)
                LIMIT 1
            """),
            {"alias": alias}
        ).fetchone()
        
        if result:
            return (result[0], result[1])
        return None


def import_mappings(engine, mappings: List[Tuple[str, str, str]], 
                   source_prefix: str, dry_run: bool = False) -> Dict:
    """
    Import mappings into team_aliases table.
    
    Args:
        engine: SQLAlchemy engine
        mappings: List of (canonical_name, alias, source) tuples
        source_prefix: Prefix for source names (e.g., 'ncaahoopr', 'hoopr')
        dry_run: If True, only report what would be imported
    
    Returns:
        Statistics dict
    """
    stats = {
        'total': len(mappings),
        'resolved': 0,
        'unresolved_canonical': 0,
        'inserted': 0,
        'skipped_duplicate': 0,
        'skipped_self': 0,
        'errors': 0,
    }
    
    unresolved_canonicals = set()
    to_insert = []
    
    print(f"\nProcessing {len(mappings)} mappings from {source_prefix}...")
    
    for canonical, alias, source in mappings:
        # Skip if alias is same as canonical (self-reference)
        if alias.lower() == canonical.lower():
            stats['skipped_self'] += 1
            continue
        
        # Resolve canonical to team_id
        team_id = resolve_canonical_to_team_id(engine, canonical)
        
        if not team_id:
            # Try to find team by alias
            found = find_team_by_alias(engine, canonical)
            if found:
                canonical, team_id = found
            else:
                unresolved_canonicals.add(canonical)
                stats['unresolved_canonical'] += 1
                continue
        
        stats['resolved'] += 1
        
        # Full source name with prefix
        full_source = f"{source_prefix}_{source}" if source != source_prefix else source_prefix
        
        to_insert.append({
            'team_id': team_id,
            'alias': alias,
            'source': full_source,
            'canonical': canonical
        })
    
    if unresolved_canonicals:
        print(f"\n⚠️  WARNING: {len(unresolved_canonicals)} canonical names not found in database:")
        for name in sorted(unresolved_canonicals)[:20]:  # Show first 20
            print(f"    - {name}")
        if len(unresolved_canonicals) > 20:
            print(f"    ... and {len(unresolved_canonicals) - 20} more")
    
    if dry_run:
        print(f"\n[DRY RUN] Would insert {len(to_insert)} aliases:")
        for item in to_insert[:10]:  # Show first 10
            print(f"    {item['canonical']} <- '{item['alias']}' (source: {item['source']})")
        if len(to_insert) > 10:
            print(f"    ... and {len(to_insert) - 10} more")
        stats['inserted'] = len(to_insert)
        return stats
    
    # Insert into database
    print(f"\nInserting {len(to_insert)} aliases...")
    
    with engine.connect() as conn:
        for item in to_insert:
            try:
                conn.execute(
                    text("""
                        INSERT INTO team_aliases (team_id, alias, source, confidence)
                        VALUES (:team_id::uuid, :alias, :source, 1.0)
                        ON CONFLICT (alias, source) DO NOTHING
                    """),
                    {
                        'team_id': item['team_id'],
                        'alias': item['alias'],
                        'source': item['source']
                    }
                )
                conn.commit()
                stats['inserted'] += 1
            except Exception as e:
                # Check if it's a duplicate conflict (shouldn't happen with ON CONFLICT)
                if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                    stats['skipped_duplicate'] += 1
                else:
                    print(f"ERROR inserting {item['alias']} for {item['canonical']}: {e}")
                    stats['errors'] += 1
                    stats['skipped_duplicate'] += 1
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Import standardized team name mappings from R package datasets'
    )
    parser.add_argument('--source', required=True,
                       choices=['ncaahoopr', 'hoopr', 'torvik', 'generic'],
                       help='Source dataset type')
    parser.add_argument('--input', required=True, type=Path,
                       help='Input file path (CSV or JSON)')
    parser.add_argument('--format', choices=['csv', 'json'], default='csv',
                       help='Input file format (default: csv)')
    parser.add_argument('--canonical-col', default='canonical',
                       help='Canonical name column (for generic CSV)')
    parser.add_argument('--alias-col', default='alias',
                       help='Alias column (for generic CSV)')
    parser.add_argument('--source-col', default='source',
                       help='Source column (for generic CSV)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without inserting')
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)
    
    print("=" * 70)
    print("Standardized Team Mapping Importer")
    print("=" * 70)
    print(f"Source: {args.source}")
    print(f"Input: {args.input}")
    print(f"Format: {args.format}")
    if args.dry_run:
        print("Mode: DRY RUN (no changes will be made)")
    print()
    
    # Load mappings based on source type
    try:
        if args.source == 'ncaahoopr':
            mappings = load_ncaahoopr_dict(args.input)
        elif args.source == 'hoopr':
            if args.format == 'json':
                mappings = load_hoopr_teams_links(args.input)
            else:
                print("ERROR: hoopr source requires --format json")
                sys.exit(1)
        elif args.source == 'torvik':
            mappings = load_torvik_teams(args.input)
        elif args.source == 'generic':
            mappings = load_generic_csv(
                args.input,
                args.canonical_col,
                args.alias_col,
                args.source_col
            )
    except Exception as e:
        print(f"ERROR loading mappings: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    if not mappings:
        print("WARNING: No mappings loaded from input file")
        sys.exit(1)
    
    print(f"Loaded {len(mappings)} mappings")
    
    # Connect to database
    try:
        engine = get_db_engine()
    except Exception as e:
        print(f"ERROR connecting to database: {e}")
        sys.exit(1)
    
    # Import mappings
    try:
        stats = import_mappings(engine, mappings, args.source, args.dry_run)
    except Exception as e:
        print(f"ERROR importing mappings: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Print statistics
    print("\n" + "=" * 70)
    print("Import Statistics")
    print("=" * 70)
    print(f"Total mappings:        {stats['total']}")
    print(f"Resolved to teams:     {stats['resolved']}")
    print(f"Unresolved canonicals: {stats['unresolved_canonical']}")
    print(f"Inserted:              {stats['inserted']}")
    print(f"Skipped (duplicate):    {stats['skipped_duplicate']}")
    print(f"Skipped (self-ref):    {stats['skipped_self']}")
    print(f"Errors:                {stats['errors']}")
    print()
    
    if stats['unresolved_canonical'] > 0:
        print("⚠️  Some canonical names were not found in the database.")
        print("   You may need to update team names or add missing teams.")
    
    if not args.dry_run and stats['inserted'] > 0:
        print(f"✅ Successfully imported {stats['inserted']} new aliases!")


if __name__ == "__main__":
    main()
