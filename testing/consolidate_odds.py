"""
Consolidate all historical odds data into one normalized file.
Uses the 1000+ team name canonicalization system for 95%+ match rate.
"""
import sys
import csv
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, Tuple, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services" / "prediction-service-python" / "src"))

from production_parity.team_resolver import ProductionTeamResolver


# Target schema (normalized)
TARGET_COLUMNS = [
    "event_id",
    "commence_time",
    "home_team",           # Original team name from API
    "away_team",           # Original team name from API
    "home_team_canonical", # Resolved canonical name
    "away_team_canonical", # Resolved canonical name
    "bookmaker",
    "spread",
    "total",
    "h1_spread",
    "h1_total",
    "is_march_madness",
    "timestamp",
    "game_date",           # Extracted date for matching
    "season",              # Basketball season (e.g., 2024 = 2023-24 season)
]


def detect_march_madness(date_str: str) -> bool:
    """Detect if a game is during March Madness (mid-March to early April)."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        month = dt.month
        day = dt.day
        # March Madness typically runs mid-March through early April
        if month == 3 and day >= 14:
            return True
        if month == 4 and day <= 10:
            return True
        return False
    except:
        return False


def get_season(date_str: str) -> int:
    """Get basketball season year from date (Nov-Apr = season end year)."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        # Season runs Nov-Apr, so Nov 2023 = 2024 season
        if dt.month >= 7:  # Jul-Dec = next year's season
            return dt.year + 1
        else:  # Jan-Jun = current year's season
            return dt.year
    except:
        return 0


def get_game_date(commence_time: str) -> str:
    """Extract date from commence_time."""
    try:
        dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except:
        return ""


def normalize_row(row: Dict, resolver: ProductionTeamResolver) -> Optional[Dict]:
    """
    Normalize a row to target schema.
    Returns None if both teams can't be resolved.
    """
    # Get original team names
    home_team = row.get("home_team", "").strip()
    away_team = row.get("away_team", "").strip()
    
    if not home_team or not away_team:
        return None
    
    # Resolve team names through canonicalization
    home_result = resolver.resolve(home_team)
    away_result = resolver.resolve(away_team)
    
    # Check if both resolved successfully
    if not home_result.resolved:
        return None
    if not away_result.resolved:
        return None
    
    home_canonical = home_result.canonical_name
    away_canonical = away_result.canonical_name
    
    # Get commence time
    commence_time = row.get("commence_time", "")
    game_date = get_game_date(commence_time)
    season = get_season(commence_time)
    
    # Detect March Madness
    is_mm = row.get("is_march_madness", "")
    if is_mm == "" or is_mm is None:
        is_mm = detect_march_madness(commence_time)
    else:
        is_mm = str(is_mm).lower() in ("true", "1", "yes")
    
    # Build normalized row
    return {
        "event_id": row.get("event_id", ""),
        "commence_time": commence_time,
        "home_team": home_team,
        "away_team": away_team,
        "home_team_canonical": home_canonical,
        "away_team_canonical": away_canonical,
        "bookmaker": row.get("bookmaker", "unknown"),
        "spread": row.get("spread", ""),
        "total": row.get("total", ""),
        "h1_spread": row.get("h1_spread", ""),
        "h1_total": row.get("h1_total", ""),
        "is_march_madness": is_mm,
        "timestamp": row.get("timestamp", ""),
        "game_date": game_date,
        "season": season,
    }


def main():
    data_dir = Path(__file__).parent / "data" / "historical_odds"
    output_file = data_dir / "odds_consolidated_canonical.csv"
    
    print("=" * 80)
    print("HISTORICAL ODDS CONSOLIDATION")
    print("=" * 80)
    
    # Initialize team resolver
    resolver = ProductionTeamResolver()
    
    # Track statistics
    stats = {
        "files_processed": 0,
        "total_rows": 0,
        "matched_rows": 0,
        "unmatched_home": defaultdict(int),
        "unmatched_away": defaultdict(int),
        "duplicates_removed": 0,
        "seasons": defaultdict(int),
    }
    
    # Use set to deduplicate by unique key
    seen_keys: Set[str] = set()
    all_rows = []
    
    # Process all CSV files
    csv_files = sorted(data_dir.glob("*.csv"))
    
    # Skip the output file if it exists
    csv_files = [f for f in csv_files if f.name != "odds_consolidated_canonical.csv"]
    
    print(f"\nProcessing {len(csv_files)} files...")
    
    for csv_file in csv_files:
        stats["files_processed"] += 1
        
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    stats["total_rows"] += 1
                    
                    # Normalize the row
                    normalized = normalize_row(row, resolver)
                    
                    if normalized is None:
                        # Track unmatched teams
                        home_team = row.get("home_team", "").strip()
                        away_team = row.get("away_team", "").strip()
                        
                        home_result = resolver.resolve(home_team) if home_team else None
                        if not home_result or not home_result.resolved:
                            stats["unmatched_home"][home_team] += 1
                        
                        away_result = resolver.resolve(away_team) if away_team else None
                        if not away_result or not away_result.resolved:
                            stats["unmatched_away"][away_team] += 1
                        continue
                    
                    # Create dedup key: canonical_home|canonical_away|date|bookmaker
                    dedup_key = f"{normalized['home_team_canonical']}|{normalized['away_team_canonical']}|{normalized['game_date']}|{normalized['bookmaker']}"
                    
                    if dedup_key in seen_keys:
                        stats["duplicates_removed"] += 1
                        continue
                    
                    seen_keys.add(dedup_key)
                    all_rows.append(normalized)
                    stats["matched_rows"] += 1
                    stats["seasons"][normalized["season"]] += 1
                    
        except Exception as e:
            print(f"  Error processing {csv_file.name}: {e}")
    
    # Sort by commence_time
    all_rows.sort(key=lambda x: x.get("commence_time", ""))
    
    # Write consolidated file
    print(f"\nWriting {len(all_rows)} rows to {output_file.name}...")
    
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TARGET_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)
    
    # Calculate match rate (unique games matched / unique games attempted)
    # Count unique unmatched team names
    all_unmatched_teams = set(stats["unmatched_home"].keys()) | set(stats["unmatched_away"].keys())
    unique_unmatched_count = len(all_unmatched_teams)
    
    # Count unmatched game instances (rows where at least one team didn't resolve)
    unmatched_game_instances = stats["total_rows"] - stats["matched_rows"] - stats["duplicates_removed"]
    
    # Match rate: what % of raw rows had both teams resolve successfully
    # matched_rows = rows where BOTH teams resolved (before dedup)
    # This overcounts because of duplicates, but the ratio is what matters
    total_rows_attempted = stats["total_rows"] 
    rows_with_resolution = stats["matched_rows"] + stats["duplicates_removed"]  # All rows where both teams matched
    match_rate = (rows_with_resolution / total_rows_attempted * 100) if total_rows_attempted > 0 else 0
    
    # Print summary
    print("\n" + "=" * 80)
    print("CONSOLIDATION SUMMARY")
    print("=" * 80)
    print(f"Files processed:     {stats['files_processed']}")
    print(f"Total raw rows:      {stats['total_rows']:,}")
    print(f"Rows resolved:       {rows_with_resolution:,} ({match_rate:.1f}%)")
    print(f"Unique games output: {len(all_rows):,}")
    print(f"Duplicates removed:  {stats['duplicates_removed']:,}")
    print(f"Unmatched teams:     {unique_unmatched_count}")
    
    print("\nBy Season:")
    for season in sorted(stats["seasons"].keys()):
        print(f"  {season-1}-{str(season)[2:]}: {stats['seasons'][season]:,} games")
    
    # Show top unmatched teams
    all_unmatched = {**dict(stats["unmatched_home"]), **dict(stats["unmatched_away"])}
    if all_unmatched:
        sorted_unmatched = sorted(all_unmatched.items(), key=lambda x: -x[1])[:20]
        print(f"\nTop 20 Unmatched Teams ({len(all_unmatched)} unique):")
        for team, count in sorted_unmatched:
            print(f"  {team}: {count}")
    
    # Check if we met 95% target
    if match_rate >= 95:
        print(f"\n✅ SUCCESS: Match rate {match_rate:.1f}% >= 95% target")
    else:
        print(f"\n⚠️ WARNING: Match rate {match_rate:.1f}% < 95% target")
        print("   Consider adding missing teams to the alias dictionary")
    
    return match_rate >= 95


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
