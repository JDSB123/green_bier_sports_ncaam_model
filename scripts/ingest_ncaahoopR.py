import pandas as pd
import sys
import os
import glob
from pathlib import Path
from tqdm import tqdm

# Add project root to path
ROOT_DIR = Path(os.getcwd())
sys.path.insert(0, str(ROOT_DIR))

from testing.production_parity.team_resolver import ProductionTeamResolver

# Setup Resolver
resolver = ProductionTeamResolver()

# Config
SOURCE_DIR = ROOT_DIR / "NCAAM_historical_data" / "ncaahoopR_data-master"
OUTPUT_SCORES_DIR = ROOT_DIR / "testing" / "data" / "historical"
OUTPUT_ODDS_DIR = ROOT_DIR / "testing" / "data" / "historical_odds"

# Map folder names to Season Year (e.g., 2021-22 -> 2022)
SEASON_MAP = {
    "2021-22": 2022,
    "2022-23": 2023,
    "2020-21": 2021,
    # Add more if needed
}

def process_season(folder_name):
    season_year = SEASON_MAP.get(folder_name)
    if not season_year:
        print(f"Skipping {folder_name} (unknown season map)")
        return

    print(f"Processing {folder_name} -> Season {season_year}")
    
    pbp_root = SOURCE_DIR / folder_name / "pbp_logs"
    if not pbp_root.exists():
        print(f"No pbp_logs found for {folder_name}")
        return

    # Collect all PBP files
    # Structure: pbp_logs/YYYY-MM-DD/game_id.csv
    csv_files = glob.glob(str(pbp_root / "**" / "*.csv"), recursive=True)
    print(f"Found {len(csv_files)} game logs to process...")

    games_data = []
    odds_data = []

    for fpath in tqdm(csv_files):
        try:
            df = pd.read_csv(fpath)
            if df.empty: continue
            
            # Basic Game Info form first row
            row0 = df.iloc[0]
            game_id = str(row0.get("game_id"))
            date_str = str(row0.get("date"))
            
            # Resolve Teams
            home_raw = row0.get("home")
            away_raw = row0.get("away")
            
            h_res = resolver.resolve(home_raw)
            a_res = resolver.resolve(away_raw)
            
            if not h_res.resolved or not a_res.resolved:
                # print(f"Unresolved: {home_raw} vs {away_raw}")
                continue
                
            home_can = h_res.canonical_name
            away_can = a_res.canonical_name
            
            # Scores (Final) - Last row
            last_row = df.iloc[-1]
            home_score_final = last_row.get("home_score")
            away_score_final = last_row.get("away_score")
            
            # H1 Scores
            # Last row where half == 1
            h1_rows = df[df['half'] == 1]
            if h1_rows.empty:
                # Maybe only 2nd half log? Skip
                continue
                
            last_h1 = h1_rows.iloc[-1]
            # Verify it's end of half? time_remaining_half might be 00:00
            # Even if not pure 00:00, it's the last recorded play ~10 mins? No, usually complete.
            home_score_h1 = last_h1.get("home_score")
            away_score_h1 = last_h1.get("away_score")
            
            # Odds / Lines (from first row usually constant)
            # home_favored_by: "-5" -> Valid Spread logic needed?
            # From sample: "home_favored_by": -5.
            # Usually: Spread = Home - Away prediction.
            # If Home is Favored by 5, Spread is -5.
            # If line is -5, Home is favored.
            # Let's assume the column is the spread from Home perspective.
            fg_spread = row0.get("home_favored_by")
            fg_total = row0.get("total_line")

            # Store Game Score Data
            games_data.append({
                "game_id": game_id,
                "date": date_str,
                "home_team": home_can,
                "away_team": away_can,
                "home_score": home_score_final,
                "away_score": away_score_final,
                "home_h1": home_score_h1,
                "away_h1": away_score_h1
            })
            
            # Store Odds Data (if valid)
            # Only if spread/total are numbers
            try:
                s_val = float(fg_spread)
                t_val = float(fg_total)
                # Create consolidated odds structure
                odds_data.append({
                    "game_id": game_id,
                    "date": date_str,
                    "commence_time": f"{date_str}T00:00:00Z", # Dummy time
                    "home_team": home_can, # Raw assumed canonical for match
                    "away_team": away_can,
                    "home_team_canonical": home_can,
                    "away_team_canonical": away_can,
                    "bookmaker": "ncaahoopR_historical",
                    "spread": s_val,
                    "total": t_val,
                    "h1_spread": "", # Not available
                    "h1_total": ""   # Not available
                })
            except (ValueError, TypeError):
                # No valid odds, that's fine
                pass

        except Exception as e:
            # print(f"Error reading {fpath}: {e}")
            continue

    # Save to CSVs
    if not games_data:
        print(f"No data extracted for {season_year}")
        return

    # Save Games (Scores)
    games_df = pd.DataFrame(games_data)
    out_games = OUTPUT_SCORES_DIR / f"games_{season_year}.csv"
    
    # We want to APPEND or OVERWRITE?
    # If overwrite, we lose existing 2024 data if we ran this on 2024.
    # But for 2022/2023 we have mostly empty/missing data.
    # Let's write to a NEW file and then merge manually or conceptually.
    # Actually, let's write to `games_{season_year}_ncaahoopR.csv` mapping
    print(f"Saving {len(games_df)} games to {out_games}")
    games_df.to_csv(out_games, index=False)
    
    # Save Odds
    if odds_data:
        odds_df = pd.DataFrame(odds_data)
        out_odds = OUTPUT_ODDS_DIR / f"odds_{season_year}_ncaahoopR.csv"
        print(f"Saving {len(odds_df)} odds records to {out_odds}")
        odds_df.to_csv(out_odds, index=False)

if __name__ == "__main__":
    for folder in SEASON_MAP.keys():
        process_season(folder)
