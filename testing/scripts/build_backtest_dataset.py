#!/usr/bin/env python3
"""
Build Backtest Dataset - Fresh Start

Merges:
1. Games/Scores from scores/fg/games_all.csv
2. Canonical FG spreads from odds/canonical/spreads/fg/spreads_fg_all.csv
3. Canonical FG totals from odds/canonical/totals/fg/totals_fg_all.csv
4. Canonical H1 spreads from odds/canonical/spreads/h1/spreads_h1_all.csv
5. Canonical H1 totals from odds/canonical/totals/h1/totals_h1_all.csv
6. Barttorvik ratings (fetched fresh or from cache)

Output: backtest_datasets/backtest_master.csv

Usage:
    python testing/scripts/build_backtest_dataset.py
    python testing/scripts/build_backtest_dataset.py --fetch-ratings  # Force refresh ratings
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import requests

# Paths
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ncaam_historical_data_local"
OUTPUT_DIR = DATA / "backtest_datasets"
ALIASES_FILE = DATA / "backtest_datasets" / "team_aliases_db.json"

# Global team alias lookup
TEAM_ALIASES: Dict[str, str] = {}


def load_team_aliases():
    """Load team name aliases for matching."""
    global TEAM_ALIASES
    
    if ALIASES_FILE.exists():
        with open(ALIASES_FILE) as f:
            TEAM_ALIASES = json.load(f)
        print(f"[OK] Loaded {len(TEAM_ALIASES):,} team aliases")
    else:
        print(f"[WARN] No team aliases file found at {ALIASES_FILE}")


def resolve_team_name(name: str) -> str:
    """Resolve a team name to its canonical form."""
    if pd.isna(name):
        return name
    
    # Try exact match (case-insensitive)
    key = name.lower().strip()
    if key in TEAM_ALIASES:
        return TEAM_ALIASES[key]
    
    # Try without common suffixes
    import re
    cleaned = re.sub(r'[^\w\s]', '', key)
    cleaned = ' '.join(cleaned.split())
    if cleaned in TEAM_ALIASES:
        return TEAM_ALIASES[cleaned]
    
    # Return original if no match
    return name

# Season calculation
def get_season(date_val) -> int:
    """Get NCAA season year (Aug-Dec = next year, Jan-Jul = current year)."""
    if pd.isna(date_val):
        return 0
    if isinstance(date_val, str):
        date_val = pd.to_datetime(date_val)
    if date_val.month >= 8:
        return date_val.year + 1
    return date_val.year


def load_games() -> pd.DataFrame:
    """Load games/scores data from all available season files."""
    scores_dir = DATA / "scores" / "fg"
    
    if not scores_dir.exists():
        print(f"[ERROR] Scores directory not found: {scores_dir}")
        sys.exit(1)
    
    # Load all season files (games_2019.csv through games_2026.csv)
    all_games = []
    
    for year in range(2019, 2027):
        season_file = scores_dir / f"games_{year}.csv"
        if season_file.exists():
            df = pd.read_csv(season_file)
            # Standardize column names
            if "date" in df.columns:
                df = df.rename(columns={"date": "game_date"})
            if "game_date" not in df.columns:
                print(f"[WARN] No date column in {season_file.name}, skipping")
                continue
            
            # Keep only essential columns
            cols_to_keep = ["game_id", "game_date", "home_team", "away_team", "home_score", "away_score"]
            cols_present = [c for c in cols_to_keep if c in df.columns]
            df = df[cols_present].copy()
            
            all_games.append(df)
            print(f"   Loaded {len(df):,} games from {season_file.name}")
    
    if not all_games:
        print(f"[ERROR] No game files found")
        sys.exit(1)
    
    games = pd.concat(all_games, ignore_index=True)
    games["game_date"] = pd.to_datetime(games["game_date"])
    games["season"] = games["game_date"].apply(get_season)
    
    # Standardize team names - remove mascots for matching
    # The odds files use canonical names like "Duke" not "Duke Blue Devils"
    games["home_team_original"] = games["home_team"]
    games["away_team_original"] = games["away_team"]
    
    # Simple normalization: remove common mascot suffixes
    def normalize_team(name: str) -> str:
        if pd.isna(name):
            return name
        # Remove trailing mascot names (very common pattern)
        parts = name.split()
        if len(parts) > 1:
            # Common mascot patterns to remove
            mascots = ["Wildcats", "Tigers", "Bulldogs", "Bears", "Eagles", "Cougars", 
                      "Panthers", "Lions", "Hawks", "Cardinals", "Knights", "Aggies",
                      "Wolverines", "Buckeyes", "Terrapins", "Crimson", "Jayhawks",
                      "Fighting", "Blue", "Golden", "Illini", "Hoosiers", "Badgers",
                      "Boilermakers", "Hawkeyes", "Cornhuskers", "Spartans", "Gophers",
                      "Mountaineers", "Volunteers", "Commodores", "Razorbacks"]
            if parts[-1] in mascots:
                return " ".join(parts[:-1])
        return name
    
    print(f"[OK] Loaded {len(games):,} total games")
    print(f"   Date range: {games['game_date'].min().date()} to {games['game_date'].max().date()}")
    print(f"   Seasons: {sorted(games['season'].unique())}")
    
    # Resolve team names to canonical forms for matching with odds
    games["home_team_canonical"] = games["home_team"].apply(resolve_team_name)
    games["away_team_canonical"] = games["away_team"].apply(resolve_team_name)
    
    # Drop old odds columns if they exist (we'll get fresh ones)
    for col in ["spread_open", "total_open"]:
        if col in games.columns:
            games = games.drop(columns=[col])
    
    return games


def load_odds(market: str, period: str) -> pd.DataFrame:
    """Load canonical odds for a specific market and period."""
    if market == "spreads":
        path = DATA / "odds" / "canonical" / "spreads" / period / f"spreads_{period}_all.csv"
    else:
        path = DATA / "odds" / "canonical" / "totals" / period / f"totals_{period}_all.csv"
    
    if not path.exists():
        print(f"[WARN] Odds file not found: {path}")
        return pd.DataFrame()
    
    df = pd.read_csv(path)
    df["game_date"] = pd.to_datetime(df["game_date"])
    
    # Standardize column names (h1_spread -> spread, h1_total -> total)
    if f"{period}_spread" in df.columns:
        df = df.rename(columns={f"{period}_spread": "spread"})
    if f"{period}_total" in df.columns:
        df = df.rename(columns={f"{period}_total": "total"})
    
    # Re-resolve canonical names using our alias database to ensure consistency
    # The odds files have their own canonical names that may differ from our aliases
    df["home_team_canonical"] = df["home_team"].apply(resolve_team_name)
    df["away_team_canonical"] = df["away_team"].apply(resolve_team_name)
    
    print(f"[OK] Loaded {len(df):,} {period.upper()} {market} odds")
    return df


def get_consensus_line(odds_df: pd.DataFrame, line_col: str) -> pd.DataFrame:
    """
    Get consensus (median) line for each game.
    
    Aggregates across bookmakers to get a single line per game.
    """
    if odds_df.empty:
        return pd.DataFrame()
    
    # Group by game (date + teams) and get median line
    group_cols = ["game_date", "home_team_canonical", "away_team_canonical"]
    
    consensus = odds_df.groupby(group_cols).agg({
        line_col: "median",
        "bookmaker": "count"  # Number of books
    }).reset_index()
    
    consensus = consensus.rename(columns={
        "home_team_canonical": "home_team",
        "away_team_canonical": "away_team",
        "bookmaker": f"{line_col}_books"
    })
    
    return consensus


def fetch_barttorvik_ratings(seasons: list, force_refresh: bool = False) -> Dict[int, pd.DataFrame]:
    """Fetch Barttorvik ratings for specified seasons."""
    ratings_dir = DATA / "ratings" / "barttorvik"
    ratings_dir.mkdir(parents=True, exist_ok=True)
    
    all_ratings = {}
    
    for season in seasons:
        cache_path = ratings_dir / f"ratings_{season}.json"
        
        if cache_path.exists() and not force_refresh:
            with open(cache_path) as f:
                data = json.load(f)
            print(f"[OK] Loaded {season} ratings from cache ({len(data)} teams)")
        else:
            url = f"https://barttorvik.com/{season}_team_results.json"
            print(f"[FETCH] {url}")
            
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                
                with open(cache_path, "w") as f:
                    json.dump(data, f)
                print(f"[OK] Fetched {season} ratings ({len(data)} teams)")
            except Exception as e:
                print(f"[WARN] Failed to fetch {season} ratings: {e}")
                continue
        
        # Parse Barttorvik format: list of arrays
        # Index positions (from inspection):
        # 0: rank, 1: team, 2: conf, 3: record, 4: adj_o, 5: adj_o_rank, 6: adj_d, 7: adj_d_rank,
        # 8: barthag, 9: barthag_rank, 10: wins, 11: losses, ...
        rows = []
        for entry in data:
            if isinstance(entry, list) and len(entry) > 11:
                try:
                    rows.append({
                        "team": entry[1],  # Team name
                        "season": season,
                        "adj_o": float(entry[4]) if entry[4] else None,
                        "adj_d": float(entry[6]) if entry[6] else None,
                        "barthag": float(entry[8]) if entry[8] else None,
                        "adj_t": float(entry[44]) if len(entry) > 44 and entry[44] else None,  # Tempo
                        "wins": int(entry[10]) if entry[10] else 0,
                        "losses": int(entry[11]) if entry[11] else 0,
                    })
                except (ValueError, TypeError, IndexError):
                    continue
        
        if rows:
            all_ratings[season] = pd.DataFrame(rows)
            print(f"   Parsed {len(rows)} team ratings")
    
    return all_ratings


def merge_ratings(games: pd.DataFrame, ratings: Dict[int, pd.DataFrame]) -> pd.DataFrame:
    """Merge ratings with games, using prior season ratings for each game."""
    # Combine all ratings
    if not ratings:
        print("[WARN] No ratings available, skipping ratings merge")
        return games
    
    all_ratings = pd.concat(ratings.values(), ignore_index=True)
    
    # Resolve team names in ratings to canonical form
    all_ratings["team_canonical"] = all_ratings["team"].apply(resolve_team_name)
    
    # For each game, we need PRIOR season ratings (to avoid data leakage)
    # Game in season 2024 uses ratings from season 2023
    games["ratings_season"] = games["season"] - 1
    
    # Merge home team ratings
    home_ratings = all_ratings.rename(columns={
        "team_canonical": "home_team_canonical",
        "adj_o": "home_adj_o",
        "adj_d": "home_adj_d", 
        "adj_t": "home_tempo",
        "barthag": "home_barthag",
    })
    home_ratings = home_ratings.rename(columns={"season": "ratings_season"})
    
    games = games.merge(
        home_ratings[["home_team_canonical", "ratings_season", "home_adj_o", "home_adj_d", "home_tempo", "home_barthag"]],
        on=["home_team_canonical", "ratings_season"],
        how="left"
    )
    
    # Merge away team ratings
    away_ratings = all_ratings.rename(columns={
        "team_canonical": "away_team_canonical",
        "adj_o": "away_adj_o",
        "adj_d": "away_adj_d",
        "adj_t": "away_tempo",
        "barthag": "away_barthag",
    })
    away_ratings = away_ratings.rename(columns={"season": "ratings_season"})
    
    games = games.merge(
        away_ratings[["away_team_canonical", "ratings_season", "away_adj_o", "away_adj_d", "away_tempo", "away_barthag"]],
        on=["away_team_canonical", "ratings_season"],
        how="left"
    )
    
    # Count ratings coverage
    has_ratings = games["home_adj_o"].notna() & games["away_adj_o"].notna()
    print(f"[INFO] Ratings coverage: {has_ratings.sum():,}/{len(games):,} ({has_ratings.mean()*100:.1f}%)")
    
    return games


def build_dataset(args) -> pd.DataFrame:
    """Build the complete backtest dataset."""
    print("=" * 60)
    print("BUILDING BACKTEST DATASET")
    print("=" * 60)
    print()
    
    # Load team aliases first
    load_team_aliases()
    print()
    
    # Step 1: Load games
    print("--- Step 1: Load Games ---")
    games = load_games()
    print()
    
    # Step 2: Load and merge FG odds
    print("--- Step 2: Load Full-Game Odds ---")
    fg_spreads = load_odds("spreads", "fg")
    fg_totals = load_odds("totals", "fg")
    
    if not fg_spreads.empty:
        spread_consensus = get_consensus_line(fg_spreads, "spread")
        # Rename for merge on canonical names
        spread_consensus = spread_consensus.rename(columns={"home_team": "home_team_canonical", "away_team": "away_team_canonical"})
        games = games.merge(
            spread_consensus[["game_date", "home_team_canonical", "away_team_canonical", "spread", "spread_books"]],
            on=["game_date", "home_team_canonical", "away_team_canonical"],
            how="left"
        )
        games = games.rename(columns={"spread": "fg_spread", "spread_books": "fg_spread_books"})
        print(f"   FG spread coverage: {games['fg_spread'].notna().sum():,}/{len(games):,}")
    
    if not fg_totals.empty:
        total_consensus = get_consensus_line(fg_totals, "total")
        total_consensus = total_consensus.rename(columns={"home_team": "home_team_canonical", "away_team": "away_team_canonical"})
        games = games.merge(
            total_consensus[["game_date", "home_team_canonical", "away_team_canonical", "total", "total_books"]],
            on=["game_date", "home_team_canonical", "away_team_canonical"],
            how="left"
        )
        games = games.rename(columns={"total": "fg_total", "total_books": "fg_total_books"})
        print(f"   FG total coverage: {games['fg_total'].notna().sum():,}/{len(games):,}")
    print()
    
    # Step 3: Load and merge H1 odds
    print("--- Step 3: Load First-Half Odds ---")
    h1_spreads = load_odds("spreads", "h1")
    h1_totals = load_odds("totals", "h1")
    
    if not h1_spreads.empty:
        h1_spread_consensus = get_consensus_line(h1_spreads, "spread")
        h1_spread_consensus = h1_spread_consensus.rename(columns={"home_team": "home_team_canonical", "away_team": "away_team_canonical"})
        games = games.merge(
            h1_spread_consensus[["game_date", "home_team_canonical", "away_team_canonical", "spread", "spread_books"]],
            on=["game_date", "home_team_canonical", "away_team_canonical"],
            how="left"
        )
        games = games.rename(columns={"spread": "h1_spread", "spread_books": "h1_spread_books"})
        print(f"   H1 spread coverage: {games['h1_spread'].notna().sum():,}/{len(games):,}")
    
    if not h1_totals.empty:
        h1_total_consensus = get_consensus_line(h1_totals, "total")
        h1_total_consensus = h1_total_consensus.rename(columns={"home_team": "home_team_canonical", "away_team": "away_team_canonical"})
        games = games.merge(
            h1_total_consensus[["game_date", "home_team_canonical", "away_team_canonical", "total", "total_books"]],
            on=["game_date", "home_team_canonical", "away_team_canonical"],
            how="left"
        )
        games = games.rename(columns={"total": "h1_total", "total_books": "h1_total_books"})
        print(f"   H1 total coverage: {games['h1_total'].notna().sum():,}/{len(games):,}")
    print()
    
    # Step 4: Fetch and merge Barttorvik ratings
    print("--- Step 4: Fetch Barttorvik Ratings ---")
    seasons_needed = sorted(games["season"].unique())
    # Also fetch prior seasons for ratings lookup
    all_seasons = sorted(set(seasons_needed) | set(s - 1 for s in seasons_needed if s > 2019))
    
    ratings = fetch_barttorvik_ratings(all_seasons, force_refresh=args.fetch_ratings)
    games = merge_ratings(games, ratings)
    print()
    
    # Step 5: Add computed columns
    print("--- Step 5: Add Computed Columns ---")
    
    # Actual margin (home - away, positive = home win)
    games["actual_margin"] = games["home_score"] - games["away_score"]
    games["actual_total"] = games["home_score"] + games["away_score"]
    
    # Spread result (did home cover?)
    if "fg_spread" in games.columns:
        games["fg_spread_result"] = games["actual_margin"] + games["fg_spread"]
        games["fg_spread_covered"] = games["fg_spread_result"] > 0
    
    # Total result (did it go over?)
    if "fg_total" in games.columns:
        games["fg_total_diff"] = games["actual_total"] - games["fg_total"]
        games["fg_total_over"] = games["actual_total"] > games["fg_total"]
    
    print(f"   Added margin, total, and result columns")
    print()
    
    # Step 6: Save output
    print("--- Step 6: Save Output ---")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    output_path = OUTPUT_DIR / "backtest_master.csv"
    games.to_csv(output_path, index=False)
    print(f"[OK] Saved {len(games):,} games to {output_path}")
    
    # Also save a summary
    summary = {
        "build_time": datetime.now().isoformat(),
        "total_games": len(games),
        "date_range": {
            "min": str(games["game_date"].min().date()),
            "max": str(games["game_date"].max().date()),
        },
        "seasons": sorted(games["season"].unique().tolist()),
        "coverage": {
            "fg_spread": int(games["fg_spread"].notna().sum()) if "fg_spread" in games.columns else 0,
            "fg_total": int(games["fg_total"].notna().sum()) if "fg_total" in games.columns else 0,
            "h1_spread": int(games["h1_spread"].notna().sum()) if "h1_spread" in games.columns else 0,
            "h1_total": int(games["h1_total"].notna().sum()) if "h1_total" in games.columns else 0,
            "ratings": int((games["home_adj_o"].notna() & games["away_adj_o"].notna()).sum()) if "home_adj_o" in games.columns else 0,
        },
        "columns": list(games.columns),
    }
    
    summary_path = OUTPUT_DIR / "backtest_master_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[OK] Saved summary to {summary_path.name}")
    
    return games


def print_final_summary(games: pd.DataFrame):
    """Print final summary statistics."""
    print()
    print("=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Total games: {len(games):,}")
    print(f"Date range: {games['game_date'].min().date()} to {games['game_date'].max().date()}")
    print()
    
    print("Coverage by market:")
    for col, name in [
        ("fg_spread", "FG Spread"),
        ("fg_total", "FG Total"),
        ("h1_spread", "H1 Spread"),
        ("h1_total", "H1 Total"),
    ]:
        if col in games.columns:
            count = games[col].notna().sum()
            pct = count / len(games) * 100
            print(f"  {name}: {count:,} ({pct:.1f}%)")
    
    if "home_adj_o" in games.columns:
        has_ratings = games["home_adj_o"].notna() & games["away_adj_o"].notna()
        print(f"  Ratings: {has_ratings.sum():,} ({has_ratings.mean()*100:.1f}%)")
    
    print()
    print("Coverage by season:")
    for season in sorted(games["season"].unique()):
        season_games = games[games["season"] == season]
        fg_spread_pct = season_games["fg_spread"].notna().mean() * 100 if "fg_spread" in games.columns else 0
        print(f"  {season}: {len(season_games):,} games, {fg_spread_pct:.1f}% with FG spread")


def main():
    parser = argparse.ArgumentParser(description="Build backtest dataset from canonical data")
    parser.add_argument("--fetch-ratings", action="store_true", help="Force refresh Barttorvik ratings")
    args = parser.parse_args()
    
    games = build_dataset(args)
    print_final_summary(games)
    
    print()
    print("[DONE] Backtest dataset ready!")


if __name__ == "__main__":
    main()
