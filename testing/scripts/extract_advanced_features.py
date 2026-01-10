#!/usr/bin/env python3
"""
Extract Advanced Features from All Available Data Sources

This script extracts features from previously untapped data sources:
1. ncaahoopR box scores - player-level aggregations
2. Sharp vs Square line divergence
3. Team-specific shooting tendencies
4. Conference strength adjustments

Output: backtest_datasets/advanced_features.csv

Usage:
    python testing/scripts/extract_advanced_features.py
    python testing/scripts/extract_advanced_features.py --seasons 2024,2025
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import warnings

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# Paths
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ncaam_historical_data_local"
NCAAHOPR = DATA / "ncaahoopR_data-master"
OUTPUT_DIR = DATA / "backtest_datasets"
ALIASES_FILE = OUTPUT_DIR / "team_aliases_db.json"


# Load team aliases
TEAM_ALIASES: Dict[str, str] = {}
if ALIASES_FILE.exists():
    with open(ALIASES_FILE) as f:
        TEAM_ALIASES = json.load(f)


def resolve_team_name(name: str) -> str:
    """Resolve team name to canonical form."""
    if pd.isna(name):
        return name
    key = name.lower().strip()
    return TEAM_ALIASES.get(key, name)


def ncaa_season_from_folder(folder_name: str) -> int:
    """Convert folder name like '2023-24' to NCAA season year (2024)."""
    try:
        parts = folder_name.split("-")
        if len(parts) == 2:
            year1 = int(parts[0])
            return year1 + 1  # 2023-24 -> 2024
        return int(folder_name)
    except:
        return 0


def extract_box_score_features(seasons: List[int]) -> pd.DataFrame:
    """
    Extract team-level features from ncaahoopR box scores.

    Features extracted:
    - starter_minutes_pct: % of team minutes from starters
    - bench_points_pct: % of points from bench
    - top_scorer_pct: % of points from leading scorer
    - team_depth: Number of players with significant minutes
    - reb_per_40: Team rebounds per 40 minutes
    - ast_to_ratio: Assist to turnover ratio
    - three_pt_attempt_rate: 3PT attempts / total FGA
    """
    print("=" * 60)
    print("EXTRACTING BOX SCORE FEATURES")
    print("=" * 60)

    if not NCAAHOPR.exists():
        print(f"[WARN] ncaahoopR data not found at {NCAAHOPR}")
        return pd.DataFrame()

    all_features = []
    season_folders = sorted([d for d in NCAAHOPR.iterdir() if d.is_dir()])

    for season_folder in season_folders:
        ncaa_season = ncaa_season_from_folder(season_folder.name)
        if ncaa_season not in seasons:
            continue

        box_scores_dir = season_folder / "box_scores"
        if not box_scores_dir.exists():
            continue

        print(f"\n[{ncaa_season}] Processing box scores from {season_folder.name}...")
        team_count = 0

        for team_dir in box_scores_dir.iterdir():
            if not team_dir.is_dir():
                continue

            team_name = team_dir.name.replace("_", " ")
            team_canonical = resolve_team_name(team_name)

            # Aggregate all games for this team in this season
            games_data = []

            for game_file in team_dir.iterdir():
                if not game_file.suffix == ".csv":
                    continue

                try:
                    df = pd.read_csv(game_file)
                    if df.empty:
                        continue

                    # Extract game date
                    game_date = df["date"].iloc[0] if "date" in df.columns else None
                    opponent = df["opponent"].iloc[0] if "opponent" in df.columns else None
                    is_home = df["home"].iloc[0] if "home" in df.columns else None

                    # Calculate team-level stats for this game
                    total_minutes = df["MIN"].sum()
                    if total_minutes == 0:
                        continue

                    starters = df[df["starter"] == True] if "starter" in df.columns else df.head(5)
                    bench = df[df["starter"] == False] if "starter" in df.columns else df.tail(len(df) - 5)

                    starter_minutes = starters["MIN"].sum()
                    bench_points = bench["PTS"].sum()
                    total_points = df["PTS"].sum()
                    top_scorer_pts = df["PTS"].max()

                    # Count players with significant minutes (>5 min)
                    team_depth = (df["MIN"] >= 5).sum()

                    # Aggregates
                    total_reb = df["REB"].sum()
                    total_ast = df["AST"].sum()
                    total_to = df["TO"].sum()
                    total_fga = df["FGA"].sum()
                    total_3pta = df["3PTA"].sum()

                    games_data.append({
                        "game_date": game_date,
                        "team": team_canonical,
                        "opponent": resolve_team_name(opponent) if opponent else None,
                        "is_home": is_home,
                        "season": ncaa_season,
                        "starter_minutes_pct": starter_minutes / total_minutes if total_minutes > 0 else 0,
                        "bench_points_pct": bench_points / total_points if total_points > 0 else 0,
                        "top_scorer_pct": top_scorer_pts / total_points if total_points > 0 else 0,
                        "team_depth": team_depth,
                        "reb_per_40": total_reb / total_minutes * 40 if total_minutes > 0 else 0,
                        "ast_to_ratio": total_ast / total_to if total_to > 0 else total_ast,
                        "three_pt_attempt_rate": total_3pta / total_fga if total_fga > 0 else 0,
                        "total_minutes": total_minutes,
                    })

                except Exception as e:
                    continue

            if games_data:
                all_features.extend(games_data)
                team_count += 1

        print(f"   Processed {team_count} teams")

    if not all_features:
        print("[WARN] No box score features extracted")
        return pd.DataFrame()

    df = pd.DataFrame(all_features)
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")

    print(f"\n[OK] Extracted {len(df):,} game-level box score features")
    return df


def calculate_rolling_team_stats(box_features: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """
    Calculate rolling averages for team stats leading up to each game.

    This creates features that represent a team's recent form,
    using only data available BEFORE the game (no data leakage).
    """
    print("\n--- Calculating Rolling Team Stats ---")

    if box_features.empty:
        return pd.DataFrame()

    # Sort by team and date
    df = box_features.sort_values(["team", "game_date"]).copy()

    # Group by team and calculate rolling stats
    rolling_cols = [
        "starter_minutes_pct", "bench_points_pct", "top_scorer_pct",
        "team_depth", "reb_per_40", "ast_to_ratio", "three_pt_attempt_rate"
    ]

    for col in rolling_cols:
        # Shift by 1 to exclude current game (use only prior games)
        df[f"{col}_rolling"] = df.groupby("team")[col].transform(
            lambda x: x.shift(1).rolling(window=window, min_periods=1).mean()
        )

    print(f"   Created rolling averages (window={window}) for {len(rolling_cols)} features")
    return df


def calculate_conference_strength(backtest_master: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate conference strength adjustments based on team performance.

    Uses team barthag/ratings within each conference to compute:
    - conf_avg_barthag: Average barthag of teams in conference
    - conf_rank: Relative strength rank of conference
    """
    print("\n--- Calculating Conference Strength ---")

    if "home_conf" not in backtest_master.columns:
        print("[WARN] Conference data not available")
        return backtest_master

    # Get unique team-conference-season-barthag combinations
    home_data = backtest_master[["season", "home_conf", "home_barthag"]].dropna()
    home_data = home_data.rename(columns={"home_conf": "conf", "home_barthag": "barthag"})

    away_data = backtest_master[["season", "away_conf", "away_barthag"]].dropna()
    away_data = away_data.rename(columns={"away_conf": "conf", "away_barthag": "barthag"})

    all_data = pd.concat([home_data, away_data]).drop_duplicates()

    # Calculate average barthag per conference per season
    conf_strength = all_data.groupby(["season", "conf"]).agg({
        "barthag": ["mean", "std", "count"]
    }).reset_index()
    conf_strength.columns = ["season", "conf", "conf_avg_barthag", "conf_std_barthag", "conf_team_count"]

    # Rank conferences by average barthag
    conf_strength["conf_rank"] = conf_strength.groupby("season")["conf_avg_barthag"].rank(ascending=False)

    # Merge back to backtest master
    backtest_master = backtest_master.merge(
        conf_strength[["season", "conf", "conf_avg_barthag", "conf_rank"]].rename(
            columns={"conf": "home_conf", "conf_avg_barthag": "home_conf_strength", "conf_rank": "home_conf_rank"}
        ),
        on=["season", "home_conf"],
        how="left"
    )

    backtest_master = backtest_master.merge(
        conf_strength[["season", "conf", "conf_avg_barthag", "conf_rank"]].rename(
            columns={"conf": "away_conf", "conf_avg_barthag": "away_conf_strength", "conf_rank": "away_conf_rank"}
        ),
        on=["season", "away_conf"],
        how="left"
    )

    # Conference strength differential
    backtest_master["conf_strength_diff"] = (
        backtest_master["home_conf_strength"].fillna(0.5) -
        backtest_master["away_conf_strength"].fillna(0.5)
    )

    print(f"   Added conference strength features for {len(conf_strength)} conference-seasons")
    return backtest_master


def extract_sharp_square_divergence(odds_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate sharp vs square book line divergence.

    Sharp books: Pinnacle, Circa, Bookmaker
    Square books: DraftKings, FanDuel, BetMGM, Caesars

    When sharp and square lines diverge, it often indicates sharp money movement.
    """
    print("\n--- Calculating Sharp/Square Line Divergence ---")

    sharp_books = ["pinnacle", "circa", "bookmaker"]
    square_books = ["draftkings", "fanduel", "betmgm", "caesars", "bovada"]

    if "bookmaker" not in odds_df.columns:
        print("[WARN] Bookmaker data not available in odds file")
        return pd.DataFrame()

    # Normalize bookmaker names
    odds_df["bookmaker_lower"] = odds_df["bookmaker"].str.lower()

    # Separate sharp and square lines
    sharp_odds = odds_df[odds_df["bookmaker_lower"].isin(sharp_books)]
    square_odds = odds_df[odds_df["bookmaker_lower"].isin(square_books)]

    if sharp_odds.empty or square_odds.empty:
        print("[WARN] Insufficient sharp/square data for divergence calculation")
        return pd.DataFrame()

    # Group by game and calculate median lines
    group_cols = ["game_date", "home_team", "away_team"]

    # For spreads
    if "spread" in odds_df.columns:
        sharp_spreads = sharp_odds.groupby(group_cols)["spread"].median().reset_index()
        sharp_spreads = sharp_spreads.rename(columns={"spread": "sharp_spread"})

        square_spreads = square_odds.groupby(group_cols)["spread"].median().reset_index()
        square_spreads = square_spreads.rename(columns={"spread": "square_spread"})

        divergence = sharp_spreads.merge(square_spreads, on=group_cols, how="inner")
        divergence["spread_divergence"] = divergence["sharp_spread"] - divergence["square_spread"]

        print(f"   Calculated spread divergence for {len(divergence):,} games")
        return divergence

    return pd.DataFrame()


def merge_advanced_features(
    backtest_master: pd.DataFrame,
    box_features: pd.DataFrame,
) -> pd.DataFrame:
    """Merge all advanced features into the backtest master dataset."""
    print("\n--- Merging Advanced Features ---")

    if box_features.empty:
        print("[WARN] No box score features to merge")
        return backtest_master

    # Calculate rolling stats
    rolling_features = calculate_rolling_team_stats(box_features)

    if rolling_features.empty:
        return backtest_master

    # Prepare for merge - get latest rolling stats per team per game date
    rolling_cols = [c for c in rolling_features.columns if c.endswith("_rolling")]
    merge_cols = ["game_date", "team", "season"] + rolling_cols
    rolling_for_merge = rolling_features[merge_cols].drop_duplicates(["game_date", "team"])

    # Merge home team features
    home_features = rolling_for_merge.rename(columns={
        "team": "home_team_canonical",
        **{c: f"home_{c}" for c in rolling_cols}
    })

    initial_len = len(backtest_master)
    backtest_master = backtest_master.merge(
        home_features,
        left_on=["game_date", "home_team_canonical", "season"],
        right_on=["game_date", "home_team_canonical", "season"],
        how="left"
    )

    # Merge away team features
    away_features = rolling_for_merge.rename(columns={
        "team": "away_team_canonical",
        **{c: f"away_{c}" for c in rolling_cols}
    })

    backtest_master = backtest_master.merge(
        away_features,
        left_on=["game_date", "away_team_canonical", "season"],
        right_on=["game_date", "away_team_canonical", "season"],
        how="left"
    )

    # Count how many got matched
    home_matched = backtest_master["home_starter_minutes_pct_rolling"].notna().sum()
    away_matched = backtest_master["away_starter_minutes_pct_rolling"].notna().sum()

    print(f"   Merged box score features: home={home_matched:,}, away={away_matched:,}")

    return backtest_master


def main():
    parser = argparse.ArgumentParser(description="Extract advanced features from all data sources")
    parser.add_argument("--seasons", type=str, default="2024,2025",
                        help="Comma-separated list of seasons")
    args = parser.parse_args()

    seasons = [int(s.strip()) for s in args.seasons.split(",")]

    print("=" * 60)
    print("ADVANCED FEATURE EXTRACTION")
    print("=" * 60)
    print(f"Seasons: {seasons}")
    print(f"Data path: {DATA}")
    print()

    # Load backtest master
    backtest_path = OUTPUT_DIR / "backtest_master.csv"
    if not backtest_path.exists():
        print(f"[ERROR] Backtest master not found at {backtest_path}")
        print("Run: python testing/scripts/build_backtest_dataset.py")
        return

    backtest_master = pd.read_csv(backtest_path)
    backtest_master["game_date"] = pd.to_datetime(backtest_master["game_date"])
    print(f"[OK] Loaded backtest master: {len(backtest_master):,} games")

    # Extract box score features
    box_features = extract_box_score_features(seasons)

    # Add conference strength
    backtest_master = calculate_conference_strength(backtest_master)

    # Merge box score features
    if not box_features.empty:
        backtest_master = merge_advanced_features(backtest_master, box_features)

    # Save enhanced dataset
    output_path = OUTPUT_DIR / "backtest_master_enhanced.csv"
    backtest_master.to_csv(output_path, index=False)
    print(f"\n[OK] Saved enhanced dataset: {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total games: {len(backtest_master):,}")

    new_cols = [c for c in backtest_master.columns if "rolling" in c or "conf_strength" in c or "conf_rank" in c]
    print(f"New feature columns: {len(new_cols)}")
    for col in new_cols[:10]:
        coverage = backtest_master[col].notna().sum()
        print(f"   {col}: {coverage:,} ({coverage/len(backtest_master)*100:.1f}%)")

    if len(new_cols) > 10:
        print(f"   ... and {len(new_cols) - 10} more")

    print("\n[DONE] Advanced feature extraction complete!")


if __name__ == "__main__":
    main()
