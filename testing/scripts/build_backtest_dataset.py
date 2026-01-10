#!/usr/bin/env python3
"""
⚠️  DEPRECATED: Build Backtest Dataset - Legacy Version

This script has been replaced by the canonical ingestion pipeline.
Use build_backtest_dataset_canonical.py instead.

The new canonical version provides:
- Automatic team name resolution
- Preventive data quality validation
- Schema evolution handling
- Azure integration with canonicalization

Usage:
    python testing/scripts/build_backtest_dataset_canonical.py

This legacy script will be removed in a future version.
"""

#!/usr/bin/env python3
"""
Build Backtest Dataset - Fresh Start (DEPRECATED)

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
    """Load ALL games/scores data from individual year files for complete coverage.
    
    IMPORTANT: We load from individual year files (2019-2026) because:
    - games_all.csv only has 2024+ games
    - But we have price data for 2020-2023 seasons
    - This ensures we have games that match the price data period
    """
    scores_dir = DATA / "scores" / "fg"

    if not scores_dir.exists():
        print(f"[ERROR] Scores directory not found: {scores_dir}")
        sys.exit(1)

    # Load from ALL individual season files to get complete historical coverage
    # This includes 2020-2023 which have price data available
    print(f"   Loading from individual season files for complete coverage...")
    all_games = []

    for year in range(2019, 2027):
        season_file = scores_dir / f"games_{year}.csv"
        if season_file.exists():
            df = pd.read_csv(season_file)
            if "date" in df.columns:
                df = df.rename(columns={"date": "game_date"})
            if "game_date" not in df.columns:
                print(f"[WARN] No date column in {season_file.name}, skipping")
                continue
            all_games.append(df)
            print(f"   Loaded {len(df):,} games from {season_file.name}")

    if not all_games:
        # FALLBACK: Try games_all.csv
        games_all_file = scores_dir / "games_all.csv"
        if games_all_file.exists():
            print(f"   [FALLBACK] Loading from {games_all_file.name}...")
            games = pd.read_csv(games_all_file)
            if "date" in games.columns:
                games = games.rename(columns={"date": "game_date"})
            print(f"   Loaded {len(games):,} games from games_all.csv")
        else:
            print(f"[ERROR] No game files found")
            sys.exit(1)
    else:
        games = pd.concat(all_games, ignore_index=True)

    # Keep only essential columns
    cols_to_keep = ["game_id", "game_date", "home_team", "away_team", "home_score", "away_score"]
    cols_present = [c for c in cols_to_keep if c in games.columns]
    games = games[cols_present].copy()

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


def load_h1_scores() -> pd.DataFrame:
    """Load first-half scores for H1 backtest validation."""
    h1_scores_file = DATA / "scores" / "h1" / "h1_games_all.csv"
    h1_canonical_file = DATA / "canonicalized" / "scores" / "h1" / "h1_games_all_canonical.csv"

    # Prefer canonical file if available
    if h1_canonical_file.exists():
        print(f"   Loading H1 scores from canonical file...")
        h1 = pd.read_csv(h1_canonical_file)
        # Use canonical team names if available
        if "home_canonical" in h1.columns:
            h1["home_team_canonical"] = h1["home_canonical"]
            h1["away_team_canonical"] = h1["away_canonical"]
        elif "home_team" in h1.columns:
            h1["home_team_canonical"] = h1["home_team"].apply(resolve_team_name)
            h1["away_team_canonical"] = h1["away_team"].apply(resolve_team_name)
    elif h1_scores_file.exists():
        print(f"   Loading H1 scores from raw file...")
        h1 = pd.read_csv(h1_scores_file)
        h1["home_team_canonical"] = h1["home_team"].apply(resolve_team_name)
        h1["away_team_canonical"] = h1["away_team"].apply(resolve_team_name)
    else:
        print(f"   [WARN] No H1 scores file found")
        return pd.DataFrame()

    # Standardize date column
    if "date" in h1.columns:
        h1 = h1.rename(columns={"date": "game_date"})
    h1["game_date"] = pd.to_datetime(h1["game_date"])

    # Extract H1 score columns
    h1_cols = ["game_date", "home_team_canonical", "away_team_canonical"]
    if "home_h1" in h1.columns:
        h1_cols.extend(["home_h1", "away_h1"])
    elif "home_score_1h" in h1.columns:
        h1 = h1.rename(columns={"home_score_1h": "home_h1", "away_score_1h": "away_h1"})
        h1_cols.extend(["home_h1", "away_h1"])

    h1 = h1[[c for c in h1_cols if c in h1.columns]].drop_duplicates()
    print(f"[OK] Loaded {len(h1):,} H1 scores")
    return h1


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


def get_consensus_line(odds_df: pd.DataFrame, line_col: str, price_cols: list = None) -> pd.DataFrame:
    """
    Get consensus (median) line for each game WITH ACTUAL PRICES.
    
    Aggregates across bookmakers to get a single line per game.
    CRITICAL: Includes actual odds prices (not hardcoded -110).
    
    Args:
        odds_df: DataFrame with odds data
        line_col: Column name for the line (e.g., "spread", "total")
        price_cols: Optional list of price columns to include (e.g., ["spread_home_price", "spread_away_price"])
    """
    if odds_df.empty:
        return pd.DataFrame()
    
    # Group by game (date + teams) and get median line
    group_cols = ["game_date", "home_team_canonical", "away_team_canonical"]
    
    # Build aggregation dict
    agg_dict = {
        line_col: "median",
        "bookmaker": "count"  # Number of books
    }
    
    # Include price columns if available
    if price_cols:
        for col in price_cols:
            if col in odds_df.columns:
                agg_dict[col] = "median"  # Median price across books
    
    consensus = odds_df.groupby(group_cols).agg(agg_dict).reset_index()
    
    consensus = consensus.rename(columns={
        "home_team_canonical": "home_team",
        "away_team_canonical": "away_team",
        "bookmaker": f"{line_col}_books"
    })
    
    return consensus


def load_consolidated_odds() -> pd.DataFrame:
    """
    Load the consolidated odds file with ACTUAL PRICES.
    
    This is the SINGLE SOURCE OF TRUTH for odds data with real prices.
    Contains: spread, spread_home_price, spread_away_price, total, total_over_price, etc.
    """
    odds_file = DATA / "odds" / "normalized" / "odds_consolidated_canonical.csv"
    
    if not odds_file.exists():
        print(f"[WARN] Consolidated odds not found: {odds_file}")
        return pd.DataFrame()
    
    df = pd.read_csv(odds_file)
    df["game_date"] = pd.to_datetime(df["game_date"])
    
    # Resolve team names for matching
    df["home_team_canonical"] = df["home_team"].apply(resolve_team_name)
    df["away_team_canonical"] = df["away_team"].apply(resolve_team_name)
    
    print(f"[OK] Loaded {len(df):,} odds rows with ACTUAL PRICES")
    
    # Check for price columns
    price_cols = [c for c in df.columns if "price" in c.lower()]
    print(f"   Price columns available: {price_cols}")
    
    return df


def load_h1_archive_prices() -> pd.DataFrame:
    """
    Load H1 prices from the archive file.
    
    The consolidated file has 0 H1 prices, but the archive file
    odds_h1_archive_matchups.csv has 82,657+ rows with H1 prices!
    Date range: 2023-11-06 to 2025-04-08 (seasons 2024-2025)
    """
    archive_file = DATA / "odds" / "normalized" / "odds_h1_archive_matchups.csv"
    
    if not archive_file.exists():
        print(f"   [INFO] H1 archive not found: {archive_file}")
        return pd.DataFrame()
    
    df = pd.read_csv(archive_file)
    df["game_date"] = pd.to_datetime(df["game_date"])
    
    # Filter to rows that have H1 prices
    h1_price_cols = ["h1_spread_home_price", "h1_spread_away_price", 
                     "h1_total_over_price", "h1_total_under_price"]
    
    # At least one H1 price must be present
    has_h1_price = df[h1_price_cols].notna().any(axis=1)
    df = df[has_h1_price]
    
    if df.empty:
        print(f"   [INFO] No H1 prices in archive file")
        return pd.DataFrame()
    
    # Resolve team names for matching
    if "home_team_canonical" in df.columns:
        df["home_team_canonical"] = df["home_team_canonical"].apply(resolve_team_name)
        df["away_team_canonical"] = df["away_team_canonical"].apply(resolve_team_name)
    else:
        df["home_team_canonical"] = df["home_team"].apply(resolve_team_name)
        df["away_team_canonical"] = df["away_team"].apply(resolve_team_name)
    
    print(f"[OK] Loaded {len(df):,} H1 archive rows with ACTUAL PRICES")
    print(f"   Date range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")
    
    return df


def get_consensus_odds_with_prices(odds_df: pd.DataFrame, h1_archive_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Get consensus odds for all markets WITH ACTUAL PRICES.
    
    Returns one row per game with:
    - fg_spread, fg_spread_home_price, fg_spread_away_price
    - fg_total, fg_total_over_price, fg_total_under_price
    - h1_spread, h1_spread_home_price, h1_spread_away_price
    - h1_total, h1_total_over_price, h1_total_under_price
    
    Args:
        odds_df: Main consolidated odds (has FG prices, but 0 H1 prices)
        h1_archive_df: H1 archive with actual H1 prices (optional, merged if provided)
    """
    if odds_df.empty:
        return pd.DataFrame()
    
    group_cols = ["game_date", "home_team_canonical", "away_team_canonical"]
    
    # Define all columns to aggregate for FG odds
    agg_dict = {
        "bookmaker": "count",
        # FG Spread
        "spread": "median",
        "spread_home_price": "median",
        "spread_away_price": "median",
        # FG Total
        "total": "median",
        "total_over_price": "median",
        "total_under_price": "median",
        # H1 lines from consolidated (may not have prices)
        "h1_spread": "median",
        "h1_total": "median",
    }
    
    # Only include columns that exist
    agg_dict = {k: v for k, v in agg_dict.items() if k in odds_df.columns}
    
    consensus = odds_df.groupby(group_cols).agg(agg_dict).reset_index()
    
    # Rename spread/total to fg_spread/fg_total for clarity
    rename_map = {
        "spread": "fg_spread",
        "spread_home_price": "fg_spread_home_price",
        "spread_away_price": "fg_spread_away_price",
        "total": "fg_total",
        "total_over_price": "fg_total_over_price",
        "total_under_price": "fg_total_under_price",
        "bookmaker": "num_books",
    }
    
    # Only rename columns that exist
    rename_map = {k: v for k, v in rename_map.items() if k in consensus.columns}
    consensus = consensus.rename(columns=rename_map)
    
    # MERGE H1 PRICES from archive file if provided
    if h1_archive_df is not None and not h1_archive_df.empty:
        print(f"   Merging H1 prices from archive ({len(h1_archive_df):,} rows)...")
        
        # Aggregate H1 archive to consensus
        h1_agg_dict = {
            "h1_spread": "median",
            "h1_spread_home_price": "median",
            "h1_spread_away_price": "median",
            "h1_total": "median",
            "h1_total_over_price": "median",
            "h1_total_under_price": "median",
        }
        h1_agg_dict = {k: v for k, v in h1_agg_dict.items() if k in h1_archive_df.columns}
        
        h1_consensus = h1_archive_df.groupby(group_cols).agg(h1_agg_dict).reset_index()
        
        # Merge H1 prices into main consensus
        # Use suffix to avoid conflicts, then prefer archive values
        consensus = consensus.merge(
            h1_consensus,
            on=group_cols,
            how="left",
            suffixes=("", "_archive")
        )
        
        # Prefer archive H1 prices over consolidated (which are all null)
        for col in ["h1_spread", "h1_spread_home_price", "h1_spread_away_price",
                    "h1_total", "h1_total_over_price", "h1_total_under_price"]:
            archive_col = f"{col}_archive"
            if archive_col in consensus.columns:
                # Use archive value if main is null
                if col in consensus.columns:
                    consensus[col] = consensus[col].fillna(consensus[archive_col])
                else:
                    consensus[col] = consensus[archive_col]
                consensus = consensus.drop(columns=[archive_col])
        
        h1_with_price = consensus["h1_spread_home_price"].notna().sum() if "h1_spread_home_price" in consensus.columns else 0
        print(f"   [OK] Merged H1 prices: {h1_with_price:,} games with H1 spread prices")
    
    # Debug: Show what we have
    price_cols = [c for c in consensus.columns if 'price' in c.lower()]
    print(f"[OK] Created consensus odds for {len(consensus):,} games")
    print(f"   Price columns in consensus: {price_cols}")
    
    # Check for actual non-null prices
    for col in price_cols:
        if col in consensus.columns:
            nonnull = consensus[col].notna().sum()
            print(f"   {col}: {nonnull:,} non-null")
    
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
        # Index positions (from 2025 data inspection):
        # 0: rank, 1: team, 2: conf, 3: record
        # 4: adj_o, 5: adj_o_rank, 6: adj_d, 7: adj_d_rank
        # 8: barthag, 9: barthag_rank, 10: wins, 11: losses
        # 15: efg (eff FG%), 16: efgd (opp eff FG%), 17: tor (TO rate)
        # 18-20: duplicate of 15-17 for some reason
        # 21: orb (off reb %), 22: drb (def reb %)
        # 23: ftr (FT rate), 24: ftrd (opp FT rate)
        # 27-30: raw offensive/defensive metrics
        # 37: 2pt% rate, 38: 3pt% rate
        # 41: WAB (wins above bubble)
        # 44: tempo (adj tempo)
        rows = []
        for entry in data:
            if isinstance(entry, list) and len(entry) > 44:
                try:
                    rows.append({
                        "team": entry[1],  # Team name
                        "season": season,
                        "conf": entry[2],  # Conference
                        "adj_o": float(entry[4]) if entry[4] else None,
                        "adj_d": float(entry[6]) if entry[6] else None,
                        "barthag": float(entry[8]) if entry[8] else None,
                        "wins": int(entry[10]) if entry[10] else 0,
                        "losses": int(entry[11]) if entry[11] else 0,
                        # Four Factors - NEWLY ADDED
                        "efg": float(entry[15]) if entry[15] else None,  # Effective FG%
                        "efgd": float(entry[16]) if entry[16] else None,  # Opp Effective FG%
                        "tor": float(entry[17]) if entry[17] else None,  # Turnover Rate
                        "orb": float(entry[21]) if entry[21] else None,  # Offensive Reb %
                        "drb": float(entry[22]) if entry[22] else None,  # Defensive Reb %
                        "ftr": float(entry[23]) if entry[23] else None,  # Free Throw Rate
                        "ftrd": float(entry[24]) if entry[24] else None,  # Opp Free Throw Rate
                        # Shooting Tendencies - NEWLY ADDED
                        "two_pt_rate": float(entry[37]) if len(entry) > 37 and entry[37] else None,
                        "three_pt_rate": float(entry[38]) if len(entry) > 38 and entry[38] else None,
                        # Quality Metrics - NEWLY ADDED
                        "wab": float(entry[41]) if len(entry) > 41 and entry[41] else None,  # Wins Above Bubble
                        "adj_t": float(entry[44]) if len(entry) > 44 and entry[44] else None,  # Tempo
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

    # Define all rating columns to merge (core + four factors + shooting)
    rating_cols = [
        "adj_o", "adj_d", "adj_t", "barthag", "conf",
        # Four Factors
        "efg", "efgd", "tor", "orb", "drb", "ftr", "ftrd",
        # Shooting Tendencies
        "two_pt_rate", "three_pt_rate",
        # Quality
        "wab"
    ]

    # Merge home team ratings
    home_rename = {"team_canonical": "home_team_canonical", "season": "ratings_season"}
    for col in rating_cols:
        if col in all_ratings.columns:
            home_rename[col] = f"home_{col}"

    home_ratings = all_ratings.rename(columns=home_rename)
    home_cols = ["home_team_canonical", "ratings_season"] + [f"home_{c}" for c in rating_cols if c in all_ratings.columns]

    games = games.merge(
        home_ratings[home_cols],
        on=["home_team_canonical", "ratings_season"],
        how="left"
    )

    # Merge away team ratings
    away_rename = {"team_canonical": "away_team_canonical", "season": "ratings_season"}
    for col in rating_cols:
        if col in all_ratings.columns:
            away_rename[col] = f"away_{col}"

    away_ratings = all_ratings.rename(columns=away_rename)
    away_cols = ["away_team_canonical", "ratings_season"] + [f"away_{c}" for c in rating_cols if c in all_ratings.columns]

    games = games.merge(
        away_ratings[away_cols],
        on=["away_team_canonical", "ratings_season"],
        how="left"
    )

    # Rename tempo column for backward compatibility
    if "home_adj_t" in games.columns:
        games = games.rename(columns={"home_adj_t": "home_tempo", "away_adj_t": "away_tempo"})

    # Count ratings coverage
    has_ratings = games["home_adj_o"].notna() & games["away_adj_o"].notna()
    print(f"[INFO] Ratings coverage: {has_ratings.sum():,}/{len(games):,} ({has_ratings.mean()*100:.1f}%)")

    # Show new fields coverage
    new_fields = ["efg", "tor", "orb", "ftr", "wab"]
    for field in new_fields:
        home_col = f"home_{field}"
        if home_col in games.columns:
            coverage = games[home_col].notna().sum()
            print(f"   {field}: {coverage:,} games")

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
    
    # Step 2: Load and merge ALL odds with ACTUAL PRICES
    print("--- Step 2: Load Odds with ACTUAL PRICES ---")
    print("   CRITICAL: Using odds_consolidated_canonical.csv for real prices")
    print("   (No hardcoded -110 assumptions)")
    print()
    
    consolidated_odds = load_consolidated_odds()
    
    # ALSO load H1 archive prices (separate file with 82,657+ H1 prices!)
    h1_archive = load_h1_archive_prices()
    
    if not consolidated_odds.empty:
        # Get consensus odds with actual prices, including H1 from archive
        consensus = get_consensus_odds_with_prices(consolidated_odds, h1_archive)
        
        # Merge with games
        games = games.merge(
            consensus,
            on=["game_date", "home_team_canonical", "away_team_canonical"],
            how="left"
        )
        
        # Report coverage
        print()
        print("   Coverage by market (with ACTUAL PRICES):")
        for col, name in [
            ("fg_spread", "FG Spread"),
            ("fg_spread_home_price", "  -> Home Price"),
            ("fg_spread_away_price", "  -> Away Price"),
            ("fg_total", "FG Total"),
            ("fg_total_over_price", "  -> Over Price"),
            ("fg_total_under_price", "  -> Under Price"),
            ("h1_spread", "H1 Spread"),
            ("h1_spread_home_price", "  -> Home Price"),
            ("h1_spread_away_price", "  -> Away Price"),
            ("h1_total", "H1 Total"),
            ("h1_total_over_price", "  -> Over Price"),
            ("h1_total_under_price", "  -> Under Price"),
        ]:
            if col in games.columns:
                count = games[col].notna().sum()
                print(f"   {name}: {count:,}/{len(games):,} ({count/len(games)*100:.1f}%)")
    else:
        # Fallback to separate files (without prices)
        print("[WARN] Consolidated odds not found, falling back to separate files (NO PRICES)")
        fg_spreads = load_odds("spreads", "fg")
        fg_totals = load_odds("totals", "fg")
        
        if not fg_spreads.empty:
            spread_consensus = get_consensus_line(fg_spreads, "spread")
            spread_consensus = spread_consensus.rename(columns={"home_team": "home_team_canonical", "away_team": "away_team_canonical"})
            games = games.merge(
                spread_consensus[["game_date", "home_team_canonical", "away_team_canonical", "spread", "spread_books"]],
                on=["game_date", "home_team_canonical", "away_team_canonical"],
                how="left"
            )
            games = games.rename(columns={"spread": "fg_spread", "spread_books": "fg_spread_books"})
        
        if not fg_totals.empty:
            total_consensus = get_consensus_line(fg_totals, "total")
            total_consensus = total_consensus.rename(columns={"home_team": "home_team_canonical", "away_team": "away_team_canonical"})
            games = games.merge(
                total_consensus[["game_date", "home_team_canonical", "away_team_canonical", "total", "total_books"]],
                on=["game_date", "home_team_canonical", "away_team_canonical"],
                how="left"
            )
            games = games.rename(columns={"total": "fg_total", "total_books": "fg_total_books"})
        
        # H1 odds
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
        
        if not h1_totals.empty:
            h1_total_consensus = get_consensus_line(h1_totals, "total")
            h1_total_consensus = h1_total_consensus.rename(columns={"home_team": "home_team_canonical", "away_team": "away_team_canonical"})
            games = games.merge(
                h1_total_consensus[["game_date", "home_team_canonical", "away_team_canonical", "total", "total_books"]],
                on=["game_date", "home_team_canonical", "away_team_canonical"],
                how="left"
            )
            games = games.rename(columns={"total": "h1_total", "total_books": "h1_total_books"})
    
    print()

    # Step 3b: Load and merge H1 scores (for backtest validation)
    print("--- Step 3b: Load First-Half Scores ---")
    h1_scores = load_h1_scores()
    if not h1_scores.empty and "home_h1" in h1_scores.columns:
        games = games.merge(
            h1_scores[["game_date", "home_team_canonical", "away_team_canonical", "home_h1", "away_h1"]],
            on=["game_date", "home_team_canonical", "away_team_canonical"],
            how="left"
        )
        print(f"   H1 scores coverage: {games['home_h1'].notna().sum():,}/{len(games):,}")
    else:
        print(f"   [WARN] No H1 scores available for merge")
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

    # H1 results (if H1 scores available)
    if "home_h1" in games.columns and "away_h1" in games.columns:
        games["h1_actual_margin"] = games["home_h1"] - games["away_h1"]
        games["h1_actual_total"] = games["home_h1"] + games["away_h1"]

        if "h1_spread" in games.columns:
            games["h1_spread_result"] = games["h1_actual_margin"] + games["h1_spread"]
            games["h1_spread_covered"] = games["h1_spread_result"] > 0

        if "h1_total" in games.columns:
            games["h1_total_diff"] = games["h1_actual_total"] - games["h1_total"]
            games["h1_total_over"] = games["h1_actual_total"] > games["h1_total"]

    print(f"   Added margin, total, and result columns (FG + H1)")
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
            "h1_scores": int(games["home_h1"].notna().sum()) if "home_h1" in games.columns else 0,
            "ratings": int((games["home_adj_o"].notna() & games["away_adj_o"].notna()).sum()) if "home_adj_o" in games.columns else 0,
            # New Four Factors coverage
            "four_factors_efg": int(games["home_efg"].notna().sum()) if "home_efg" in games.columns else 0,
            "four_factors_tor": int(games["home_tor"].notna().sum()) if "home_tor" in games.columns else 0,
            "four_factors_orb": int(games["home_orb"].notna().sum()) if "home_orb" in games.columns else 0,
            "shooting_3pt_rate": int(games["home_three_pt_rate"].notna().sum()) if "home_three_pt_rate" in games.columns else 0,
            "wab": int(games["home_wab"].notna().sum()) if "home_wab" in games.columns else 0,
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
