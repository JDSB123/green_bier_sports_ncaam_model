#!/usr/bin/env python3
"""
Extract ALL features from ncaahoopR box scores.

Creates rolling game-by-game metrics including:
- Four Factors (EFG%, TO%, ORB%, FT Rate)
- Pace/Possessions
- Shooting tendencies (3PT rate, 2PT rate)
- Team depth (bench vs starter performance)
- Home/Away splits
- Recent form (last N games)

Output: ncaahoopR_features.csv with one row per team per game
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ncaam_historical_data_local"
NCAAHOOPR = DATA / "ncaahoopR_data-master"
OUTPUT_DIR = DATA / "backtest_datasets"
ALIASES_FILE = OUTPUT_DIR / "team_aliases_db.json"

# Rolling window sizes
ROLLING_WINDOWS = [3, 5, 10]  # Last N games


def load_team_aliases() -> Dict[str, str]:
    """Load team name aliases."""
    if ALIASES_FILE.exists():
        with open(ALIASES_FILE) as f:
            return json.load(f)
    return {}


def normalize_team_name(name: str, aliases: Dict[str, str]) -> str:
    """Normalize team name using aliases."""
    if pd.isna(name):
        return name
    # ncaahoopR uses underscores
    clean = name.replace("_", " ").strip()
    key = clean.lower()
    return aliases.get(key, clean)


def calculate_four_factors(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate Four Factors from box score data.
    
    Four Factors:
    1. eFG% = (FGM + 0.5 * 3PM) / FGA
    2. TO% = TO / Possessions (approximated)
    3. ORB% = OREB / (OREB + Opp DREB) - needs opponent data
    4. FT Rate = FTM / FGA
    """
    if df.empty:
        return {}
    
    # Aggregate team stats
    fgm = df["FGM"].sum()
    fga = df["FGA"].sum()
    three_pm = df["3PTM"].sum()
    three_pa = df["3PTA"].sum()
    ftm = df["FTM"].sum()
    fta = df["FTA"].sum()
    oreb = df["OREB"].sum()
    dreb = df["DREB"].sum()
    ast = df["AST"].sum()
    to = df["TO"].sum()
    stl = df["STL"].sum()
    blk = df["BLK"].sum()
    pts = df["PTS"].sum()
    
    # Effective FG%
    efg = (fgm + 0.5 * three_pm) / fga if fga > 0 else 0
    
    # Free Throw Rate
    ftr = ftm / fga if fga > 0 else 0
    
    # 3PT Rate (% of shots that are 3s)
    three_pt_rate = three_pa / fga if fga > 0 else 0
    
    # 3PT%
    three_pt_pct = three_pm / three_pa if three_pa > 0 else 0
    
    # FG%
    fg_pct = fgm / fga if fga > 0 else 0
    
    # Assist ratio
    ast_ratio = ast / fgm if fgm > 0 else 0
    
    # Turnover rate (approximate - TO per 100 possessions)
    # Possessions ≈ FGA + 0.44*FTA - OREB + TO
    possessions = fga + 0.44 * fta - oreb + to
    tor = (to / possessions * 100) if possessions > 0 else 0
    
    # Points per possession
    ppp = pts / possessions if possessions > 0 else 0
    
    return {
        "efg": efg * 100,  # As percentage
        "ftr": ftr * 100,
        "tor": tor,
        "three_pt_rate": three_pt_rate * 100,
        "three_pt_pct": three_pt_pct * 100,
        "fg_pct": fg_pct * 100,
        "ast_ratio": ast_ratio * 100,
        "oreb": oreb,
        "dreb": dreb,
        "possessions": possessions,
        "ppp": ppp,
        "pts": pts,
        "fgm": fgm,
        "fga": fga,
        "ftm": ftm,
        "fta": fta,
        "to": to,
        "stl": stl,
        "blk": blk,
    }


def calculate_depth_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate team depth metrics from box scores."""
    if df.empty:
        return {}
    
    # Separate starters vs bench
    starters = df[df["starter"] == True] if "starter" in df.columns else df.head(5)
    bench = df[df["starter"] == False] if "starter" in df.columns else df.tail(len(df) - 5)
    
    starter_pts = starters["PTS"].sum() if not starters.empty else 0
    bench_pts = bench["PTS"].sum() if not bench.empty else 0
    total_pts = starter_pts + bench_pts
    
    bench_pct = bench_pts / total_pts if total_pts > 0 else 0
    
    # Minutes distribution
    if "MIN" in df.columns:
        total_min = df["MIN"].sum()
        starter_min = starters["MIN"].sum() if not starters.empty else 0
        bench_min = bench["MIN"].sum() if not bench.empty else 0
        
        # Players who played significant minutes (>10)
        rotation_size = len(df[df["MIN"] >= 10])
    else:
        total_min = 200  # Approximate
        starter_min = 0
        bench_min = 0
        rotation_size = len(df)
    
    return {
        "bench_pts": bench_pts,
        "bench_pct": bench_pct * 100,
        "starter_pts": starter_pts,
        "rotation_size": rotation_size,
    }


def process_season(season_dir: Path, aliases: Dict[str, str]) -> List[Dict]:
    """Process all box scores for a season."""
    box_scores_dir = season_dir / "box_scores"
    
    if not box_scores_dir.exists():
        return []
    
    season_name = season_dir.name  # e.g., "2023-24"
    
    # Parse season year (e.g., "2023-24" -> 2024)
    try:
        season_year = int(season_name.split("-")[0]) + 1
    except:
        return []
    
    all_games = []
    team_dirs = [d for d in box_scores_dir.iterdir() if d.is_dir()]
    
    for team_dir in team_dirs:
        team_raw = team_dir.name
        team_canonical = normalize_team_name(team_raw, aliases)
        
        # Get all box score files for this team
        box_files = sorted(team_dir.glob("*.csv"))
        
        for box_file in box_files:
            try:
                df = pd.read_csv(box_file)
                
                if df.empty:
                    continue
                
                # Extract game info
                game_id = box_file.stem
                date_str = df["date"].iloc[0] if "date" in df.columns else None
                opponent_raw = df["opponent"].iloc[0] if "opponent" in df.columns else None
                is_home = df["home"].iloc[0] if "home" in df.columns else None
                
                if date_str is None:
                    continue
                
                # Parse date
                try:
                    game_date = pd.to_datetime(date_str)
                except:
                    continue
                
                opponent_canonical = normalize_team_name(opponent_raw, aliases) if opponent_raw else None
                
                # Calculate metrics
                four_factors = calculate_four_factors(df)
                depth = calculate_depth_metrics(df)
                
                game_record = {
                    "game_id": game_id,
                    "game_date": game_date,
                    "season": season_year,
                    "team": team_canonical,
                    "team_raw": team_raw,
                    "opponent": opponent_canonical,
                    "opponent_raw": opponent_raw,
                    "is_home": is_home,
                    **four_factors,
                    **depth,
                }
                
                all_games.append(game_record)
                
            except Exception as e:
                continue
    
    return all_games


def calculate_rolling_features(df: pd.DataFrame, windows: List[int] = ROLLING_WINDOWS) -> pd.DataFrame:
    """Calculate rolling averages for each team."""
    if df.empty:
        return df
    
    # Sort by team and date
    df = df.sort_values(["team", "game_date"]).reset_index(drop=True)
    
    # Columns to calculate rolling averages for
    rolling_cols = [
        "efg", "ftr", "tor", "three_pt_rate", "three_pt_pct", "fg_pct",
        "ast_ratio", "ppp", "pts", "possessions", "bench_pct", "rotation_size"
    ]
    
    # Filter to columns that exist
    rolling_cols = [c for c in rolling_cols if c in df.columns]
    
    for window in windows:
        for col in rolling_cols:
            new_col = f"{col}_last{window}"
            # Calculate rolling mean for each team (shift to exclude current game)
            df[new_col] = df.groupby("team")[col].transform(
                lambda x: x.shift(1).rolling(window=window, min_periods=1).mean()
            )
    
    return df


def calculate_home_away_splits(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate home vs away performance splits."""
    if df.empty or "is_home" not in df.columns:
        return df
    
    # Calculate season-to-date home/away averages
    metrics = ["efg", "ppp", "pts"]
    metrics = [c for c in metrics if c in df.columns]
    
    for metric in metrics:
        # Home performance (expanding mean up to current game, excluding current)
        df[f"{metric}_home_avg"] = df[df["is_home"] == True].groupby("team")[metric].transform(
            lambda x: x.shift(1).expanding().mean()
        )
        
        # Away performance
        df[f"{metric}_away_avg"] = df[df["is_home"] == False].groupby("team")[metric].transform(
            lambda x: x.shift(1).expanding().mean()
        )
    
    return df


def main():
    print("=" * 70)
    print("EXTRACTING FEATURES FROM ncaahoopR")
    print("=" * 70)
    
    # Load aliases
    aliases = load_team_aliases()
    print(f"Loaded {len(aliases):,} team aliases")
    
    # Find all seasons - FOCUS ON RECENT SEASONS WITH ODDS DATA (2020-2026)
    all_seasons = sorted([d for d in NCAAHOOPR.iterdir() if d.is_dir() and d.name[0].isdigit()])
    
    # Filter to 2023+ seasons for faster testing
    # Full backtest can expand later
    target_seasons = [s for s in all_seasons if any(
        year in s.name for year in ["2023-24", "2024-25", "2025-26"]
    )]
    
    if not target_seasons:
        # Fallback to last 3 seasons
        target_seasons = all_seasons[-3:] if len(all_seasons) >= 3 else all_seasons
    
    print(f"Processing {len(target_seasons)} seasons: {[s.name for s in target_seasons]}")
    
    # Process each season
    all_games = []
    
    for season_dir in target_seasons:
        print(f"\nProcessing {season_dir.name}...", end=" ", flush=True)
        games = process_season(season_dir, aliases)
        print(f"{len(games):,} games")
        all_games.extend(games)
    
    if not all_games:
        print("[ERROR] No games extracted!")
        sys.exit(1)
    
    # Create DataFrame
    df = pd.DataFrame(all_games)
    print(f"\nTotal games extracted: {len(df):,}")
    print(f"Date range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")
    print(f"Unique teams: {df['team'].nunique()}")
    
    # Calculate rolling features
    print("\nCalculating rolling features...")
    df = calculate_rolling_features(df)
    
    # Calculate home/away splits
    print("Calculating home/away splits...")
    df = calculate_home_away_splits(df)
    
    # Save output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "ncaahoopR_features.csv"
    df.to_csv(output_file, index=False)
    print(f"\n[OK] Saved {len(df):,} rows to {output_file.name}")
    
    # Summary
    print("\n" + "=" * 70)
    print("FEATURE SUMMARY")
    print("=" * 70)
    print(f"Total columns: {len(df.columns)}")
    print("\nFeature categories:")
    
    base_features = ["efg", "ftr", "tor", "three_pt_rate", "ppp", "pts", "possessions"]
    rolling_features = [c for c in df.columns if "_last" in c]
    split_features = [c for c in df.columns if "_home_avg" in c or "_away_avg" in c]
    depth_features = ["bench_pts", "bench_pct", "starter_pts", "rotation_size"]
    
    print(f"  Base Four Factors: {len([c for c in base_features if c in df.columns])}")
    print(f"  Rolling averages: {len(rolling_features)}")
    print(f"  Home/Away splits: {len(split_features)}")
    print(f"  Depth metrics: {len([c for c in depth_features if c in df.columns])}")
    
    return df


if __name__ == "__main__":
    main()
