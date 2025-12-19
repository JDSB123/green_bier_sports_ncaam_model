#!/usr/bin/env python3
"""
Import 900+ team aliases from JSON files into PostgreSQL.
This ensures 100% team name matching across all data sources.

Run inside Docker:
    docker exec ncaam_v5_1_prediction python /app/database/seeds/import_team_aliases.py
"""

import json
import os
import sys

# Add parent path for imports
sys.path.insert(0, '/app')

from sqlalchemy import create_engine, text

# Database connection
def get_db_password():
    """Read password from Docker secret file."""
    try:
        with open('/run/secrets/db_password', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.getenv('DB_PASSWORD', 'ncaam_dev_password')

DB_PASSWORD = get_db_password()
DATABASE_URL = f"postgresql://ncaam:{DB_PASSWORD}@postgres:5432/ncaam"


def load_aliases_from_json():
    """Load aliases from JSON files."""
    aliases = []
    
    # Load from team_aliases.json
    aliases_path = '/app/database/seeds/team_aliases.json'
    if os.path.exists(aliases_path):
        with open(aliases_path, 'r') as f:
            data = json.load(f)
        
        # Manual aliases
        for item in data.get('manual', []):
            aliases.append({
                'alias': item['alias'],
                'canonical': item['canonical'],
                'source': 'manual_import'
            })
        
        # Learned aliases
        for item in data.get('learned', []):
            aliases.append({
                'alias': item['alias'],
                'canonical': item['canonical'],
                'source': 'learned_import'
            })
        
        print(f"  Loaded {len(aliases)} aliases from team_aliases.json")
    
    return aliases


def import_aliases(engine, aliases):
    """Import aliases into database."""
    imported = 0
    skipped = 0
    
    with engine.connect() as conn:
        for alias_data in aliases:
            alias = alias_data['alias']
            canonical = alias_data['canonical']
            source = alias_data['source']
            
            # Find the team by canonical name
            result = conn.execute(
                text("SELECT id FROM teams WHERE canonical_name = :name"),
                {"name": canonical}
            ).fetchone()
            
            if result:
                team_id = result[0]
                
                # Insert alias (ignore conflicts)
                try:
                    conn.execute(
                        text("""
                            INSERT INTO team_aliases (team_id, alias, source)
                            VALUES (:team_id, :alias, :source)
                            ON CONFLICT (alias, source) DO NOTHING
                        """),
                        {"team_id": team_id, "alias": alias, "source": source}
                    )
                    imported += 1
                except Exception as e:
                    print(f"  Error inserting {alias}: {e}")
                    skipped += 1
            else:
                skipped += 1
        
        conn.commit()
    
    return imported, skipped


def main():
    print("=" * 60)
    print("Importing Team Aliases from JSON Files")
    print("=" * 60)
    
    # Load aliases
    aliases = load_aliases_from_json()
    print(f"\nTotal aliases to import: {len(aliases)}")
    
    if not aliases:
        print("No aliases found!")
        return
    
    # Connect to database
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    # Check current counts
    with engine.connect() as conn:
        teams_count = conn.execute(text("SELECT COUNT(*) FROM teams")).scalar()
        aliases_count = conn.execute(text("SELECT COUNT(*) FROM team_aliases")).scalar()
        print(f"\nBefore import:")
        print(f"  Teams: {teams_count}")
        print(f"  Aliases: {aliases_count}")
    
    # Import aliases
    imported, skipped = import_aliases(engine, aliases)
    
    # Check new counts
    with engine.connect() as conn:
        new_aliases_count = conn.execute(text("SELECT COUNT(*) FROM team_aliases")).scalar()
        print(f"\nAfter import:")
        print(f"  Aliases: {new_aliases_count} (+{new_aliases_count - aliases_count})")
        print(f"  Imported: {imported}")
        print(f"  Skipped: {skipped}")
    
    print("\n✓ Import complete!")


if __name__ == "__main__":
    main()
