
import sys
import os
import csv
from pathlib import Path
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from testing.production_parity.timezone_utils import get_season_for_game
from testing.data_paths import DATA_PATHS

def main():
    # Use ncaam_historical_data_local as source of truth
    source_file = DATA_PATHS.scores_fg / "games_all.csv"
    output_dir = DATA_PATHS.scores_fg  # Output to same location
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not source_file.exists():
        print(f"Error: {source_file} not found.")
        return
    
    print(f"Reading {source_file}...")
    
    games_by_season = defaultdict(list)
    headers = None
    
    with open(source_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        
        for row in reader:
            date = row.get("date") or row.get("game_date")
            if not date:
                continue
            
            season = get_season_for_game(date)
            games_by_season[season].append(row)
            
    print(f"Found games for seasons: {list(games_by_season.keys())}")
    
    for season, games in games_by_season.items():
        output_file = output_dir / f"games_{season}.csv"
        print(f"Writing {len(games)} games to {output_file}...")
        
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(games)
            
    print("Done.")

if __name__ == "__main__":
    main()
