#!/usr/bin/env python3
"""
Import standardized team name mappings from R package datasets.

This script imports team name variants from established R packages:
- ncaahoopR: Maps variants across NCAA, ESPN, WarrenNolan, Trank (Bart Torvik), 247Sports
- hoopR: Maps ESPN and KenPom variants (includes ESPN IDs for master table)
- toRvik/cbbdata: Bart Torvik native formats

The script performs two operations:
1. Imports team name aliases into team_aliases table
2. Updates teams master table with external IDs (ESPN, NCAA) and location data (city, state)

Usage:
    # From CSV exported from R
    python import_standardized_team_mappings.py --source ncaahoopr --input ncaahoopr_dict.csv
    
    # From JSON (includes ESPN IDs for master table)
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


def load_ncaahoopr_dict(csv_path: Path) -> Tuple[List[Tuple[str, str, str]], Dict[str, Dict]]:
    """
    Load ncaahoopR dict dataset.
    
    Expected CSV format (from R: write.csv(dict, "ncaahoopr_dict.csv")):
    - Columns: NCAA, ESPN, WarrenNolan, Trank, X247Sports, etc.
    - Each row is a team with variants across sources
    
    Returns:
        Tuple of (mappings, master_data)
        - mappings: List of (canonical_name, alias, source) tuples
        - master_data: Dict mapping canonical_name to master table fields
    """
    mappings = []
    master_data = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # ncaahoopR uses NCAA as canonical
            canonical = row.get('NCAA', '').strip()
            if not canonical:
                continue
            
            # Build master data entry (ncaahoopR may have location/ID columns)
            master_entry = {}
            
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
            
            # Check for ESPN ID column (if present in ncaahoopR dict)
            if 'ESPN_ID' in row and row['ESPN_ID']:
                try:
                    master_entry['espn_id'] = int(row['ESPN_ID'])
                except (ValueError, TypeError):
                    pass
            
            if master_entry:
                master_data[canonical] = master_entry
    
    return mappings, master_data


def load_hoopr_teams_links(json_path: Path) -> Tuple[List[Tuple[str, str, str]], Dict[str, Dict]]:
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
    
    Returns:
        Tuple of (mappings, master_data)
        - mappings: List of (canonical_name, alias, source) tuples
        - master_data: Dict mapping canonical_name to master table fields
    """
    mappings = []
    master_data = {}
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for team_name, links in data.items():
        canonical = team_name.strip()
        if not canonical:
            continue
        
        # Build master data entry
        master_entry = {}
        
        # ESPN ID and name
        if 'espn_id' in links and links['espn_id']:
            try:
                master_entry['espn_id'] = int(links['espn_id'])
            except (ValueError, TypeError):
                pass
        
        if 'espn_name' in links:
            alias = links['espn_name'].strip()
            if alias and alias != canonical:
                mappings.append((canonical, alias, 'espn'))
        
        # KenPom variants
        if 'kenpom_name' in links:
            alias = links['kenpom_name'].strip()
            if alias and alias != canonical:
                mappings.append((canonical, alias, 'kenpom'))
        
        if master_entry:
            master_data[canonical] = master_entry
    
    return mappings, master_data


def load_torvik_teams(csv_path: Path) -> Tuple[List[Tuple[str, str, str]], Dict[str, Dict]]:
    """
    Load toRvik/cbbdata team names.
    
    Expected CSV format:
    - team_name column with Bart Torvik canonical names
    - May include variants in other columns
    - May include location/ID columns
    
    Returns:
        Tuple of (mappings, master_data)
        - mappings: List of (canonical_name, alias, source) tuples
        - master_data: Dict mapping canonical_name to master table fields
    """
    mappings = []
    master_data = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            canonical = row.get('team_name', '').strip()
            if not canonical:
                continue
            
            # toRvik uses Bart Torvik names as canonical
            # Add as barttorvik source variant
            mappings.append((canonical, canonical, 'barttorvik'))
            
            # Build master data entry
            master_entry = {}
            
            # Check for master table columns
            if 'espn_id' in row and row.get('espn_id'):
                try:
                    master_entry['espn_id'] = int(row['espn_id'])
                except (ValueError, TypeError):
                    pass
            if 'city' in row and row.get('city'):
                master_entry['city'] = row['city'].strip()
            if 'state' in row and row.get('state'):
                master_entry['state'] = row['state'].strip()
            
            # Check for variant columns
            for col in row:
                if col != 'team_name' and row[col]:
                    alias = row[col].strip()
                    if alias and alias != canonical:
                        mappings.append((canonical, alias, 'barttorvik'))
            
            if master_entry:
                master_data[canonical] = master_entry
    
    return mappings, master_data


def load_generic_csv(csv_path: Path, canonical_col: str = 'canonical', 
                     alias_col: str = 'alias', source_col: str = 'source') -> Tuple[List[Tuple[str, str, str]], Dict[str, Dict]]:
    """
    Load generic CSV with canonical, alias, source columns.
    Also supports master table columns: espn_id, ncaa_id, sports_ref_id, city, state
    
    Returns:
        Tuple of (mappings, master_data)
        - mappings: List of (canonical_name, alias, source) tuples
        - master_data: Dict mapping canonical_name to master table fields
    """
    mappings = []
    master_data = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            canonical = row.get(canonical_col, '').strip()
            alias = row.get(alias_col, '').strip()
            source = row.get(source_col, 'manual').strip()
            
            if canonical and alias:
                mappings.append((canonical, alias, source))
            
            # Extract master data if columns present
            master_entry = {}
            if 'espn_id' in row and row.get('espn_id'):
                try:
                    master_entry['espn_id'] = int(row['espn_id'])
                except (ValueError, TypeError):
                    pass
            if 'ncaa_id' in row and row.get('ncaa_id'):
                try:
                    master_entry['ncaa_id'] = int(row['ncaa_id'])
                except (ValueError, TypeError):
                    pass
            if 'sports_ref_id' in row and row.get('sports_ref_id'):
                master_entry['sports_ref_id'] = row['sports_ref_id'].strip()
            if 'city' in row and row.get('city'):
                master_entry['city'] = row['city'].strip()
            if 'state' in row and row.get('state'):
                master_entry['state'] = row['state'].strip()
            
            if master_entry and canonical:
                master_data[canonical] = master_entry
    
    return mappings, master_data


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


def update_teams_master_data(engine, master_data: Dict[str, Dict], 
                            dry_run: bool = False) -> Dict:
    """
    Update teams master table with external IDs and location data.
    
    Args:
        engine: SQLAlchemy engine
        master_data: Dict mapping canonical_name to master table fields
        dry_run: If True, only report what would be updated
    
    Returns:
        Statistics dict
    """
    stats = {
        'total': len(master_data),
        'updated': 0,
        'skipped_not_found': 0,
        'skipped_no_changes': 0,
        'errors': 0,
    }
    
    if not master_data:
        return stats
    
    print(f"\nUpdating master table for {len(master_data)} teams...")
    
    with engine.connect() as conn:
        for canonical, fields in master_data.items():
            # Resolve canonical to team_id
            team_id = resolve_canonical_to_team_id(engine, canonical)
            
            if not team_id:
                stats['skipped_not_found'] += 1
                continue
            
            # Build UPDATE statement - only update NULL fields (preserve existing)
            updates = []
            params = {'team_id': team_id}
            
            for field, value in fields.items():
                if field in ['espn_id', 'ncaa_id', 'sports_ref_id', 'city', 'state']:
                    updates.append(f"{field} = COALESCE({field}, :{field})")
                    params[field] = value
            
            if not updates:
                stats['skipped_no_changes'] += 1
                continue
            
            if dry_run:
                print(f"  [DRY RUN] Would update {canonical}: {', '.join([f'{k}={v}' for k, v in fields.items()])}")
                stats['updated'] += 1
                continue
            
            # Update only NULL fields (preserve existing data)
            update_sql = f"""
                UPDATE teams
                SET {', '.join(updates)}
                WHERE id = :team_id
            """
            
            try:
                result = conn.execute(text(update_sql), params)
                conn.commit()
                
                if result.rowcount > 0:
                    stats['updated'] += 1
                else:
                    stats['skipped_no_changes'] += 1
            except Exception as e:
                print(f"ERROR updating {canonical}: {e}")
                stats['errors'] += 1
    
    return stats


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
    
    # Load mappings and master data based on source type
    master_data = {}
    try:
        if args.source == 'ncaahoopr':
            mappings, master_data = load_ncaahoopr_dict(args.input)
        elif args.source == 'hoopr':
            if args.format == 'json':
                mappings, master_data = load_hoopr_teams_links(args.input)
            else:
                print("ERROR: hoopr source requires --format json")
                sys.exit(1)
        elif args.source == 'torvik':
            mappings, master_data = load_torvik_teams(args.input)
        elif args.source == 'generic':
            mappings, master_data = load_generic_csv(
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
    
    if not mappings and not master_data:
        print("WARNING: No mappings or master data loaded from input file")
        sys.exit(1)
    
    if mappings:
        print(f"Loaded {len(mappings)} mappings")
    if master_data:
        print(f"Loaded master data for {len(master_data)} teams")
    
    # Connect to database
    try:
        engine = get_db_engine()
    except Exception as e:
        print(f"ERROR connecting to database: {e}")
        sys.exit(1)
    
    # Import mappings
    alias_stats = {}
    if mappings:
        try:
            alias_stats = import_mappings(engine, mappings, args.source, args.dry_run)
        except Exception as e:
            print(f"ERROR importing mappings: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # Update master table
    master_stats = {}
    if master_data:
        try:
            master_stats = update_teams_master_data(engine, master_data, args.dry_run)
        except Exception as e:
            print(f"ERROR updating master table: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # Print statistics
    print("\n" + "=" * 70)
    print("Import Statistics")
    print("=" * 70)
    
    if alias_stats:
        print("\n📝 Team Aliases:")
        print(f"  Total mappings:        {alias_stats['total']}")
        print(f"  Resolved to teams:     {alias_stats['resolved']}")
        print(f"  Unresolved canonicals: {alias_stats['unresolved_canonical']}")
        print(f"  Inserted:              {alias_stats['inserted']}")
        print(f"  Skipped (duplicate):   {alias_stats['skipped_duplicate']}")
        print(f"  Skipped (self-ref):    {alias_stats['skipped_self']}")
        print(f"  Errors:                {alias_stats['errors']}")
    
    if master_stats:
        print("\n🏆 Master Table Updates:")
        print(f"  Total teams:           {master_stats['total']}")
        print(f"  Updated:               {master_stats['updated']}")
        print(f"  Skipped (not found):   {master_stats['skipped_not_found']}")
        print(f"  Skipped (no changes):   {master_stats['skipped_no_changes']}")
        print(f"  Errors:                {master_stats['errors']}")
    
    print()
    
    if alias_stats and alias_stats.get('unresolved_canonical', 0) > 0:
        print("⚠️  Some canonical names were not found in the database.")
        print("   You may need to update team names or add missing teams.")
    
    if not args.dry_run:
        if alias_stats and alias_stats.get('inserted', 0) > 0:
            print(f"✅ Successfully imported {alias_stats['inserted']} new aliases!")
        if master_stats and master_stats.get('updated', 0) > 0:
            print(f"✅ Successfully updated {master_stats['updated']} teams in master table!")


if __name__ == "__main__":
    main()
