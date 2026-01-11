#!/usr/bin/env python3
"""
CANONICAL BACKTEST DATASET BUILDER

Builds backtest dataset using the canonical ingestion pipeline.
Ensures all data goes through proper validation, canonicalization, and quality gates.

Merges:
1. Canonical games/scores from Azure (via CanonicalIngestionPipeline)
2. Canonical FG spreads from Azure
3. Canonical FG totals from Azure
4. Canonical H1 spreads from Azure
5. Canonical H1 totals from Azure
6. Barttorvik ratings (canonicalized)

Output: backtest_datasets/backtest_master.csv (canonical)

Usage:
    python testing/scripts/build_backtest_dataset_canonical.py
    python testing/scripts/build_backtest_dataset_canonical.py --enhanced  # Include ncaahoopR features
    python testing/scripts/build_backtest_dataset_canonical.py --validate-only  # Just validate, don't build
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from testing.azure_data_reader import (
    get_azure_reader, read_canonical_scores, read_canonical_odds,
    read_backtest_master
)
from testing.azure_io import write_csv, write_json
from testing.canonical.ingestion_pipeline import CanonicalIngestionPipeline, DataSource
from testing.canonical.quality_gates import DataQualityGate
from testing.canonical.schema_evolution import SchemaEvolutionManager


def build_canonical_backtest_dataset(
    include_enhanced: bool = False,
    validate_only: bool = False,
    seasons: Optional[List[int]] = None,
    strict_mode: bool = True
) -> Optional[pd.DataFrame]:
    """
    Build canonical backtest dataset using ingestion pipeline.

    Args:
        include_enhanced: Include ncaahoopR features if available
        validate_only: Only validate data, don't build dataset
        seasons: Specific seasons to include (None = all)
        strict_mode: Fail on any quality issues

    Returns:
        Canonical backtest DataFrame or None if validate_only
    """

    print("=" * 80)
    print("CANONICAL BACKTEST DATASET BUILDER")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Enhanced features: {'YES' if include_enhanced else 'NO'}")
    print(f"Strict mode: {'YES' if strict_mode else 'NO'}")
    print(f"Validate only: {'YES' if validate_only else 'NO'}")
    print()

    # Initialize canonical components
    azure_reader = get_azure_reader()
    ingestion_pipeline = CanonicalIngestionPipeline(strict_mode=strict_mode)
    quality_gate = DataQualityGate(strict_mode=strict_mode)
    schema_manager = SchemaEvolutionManager()

    # Track statistics
    stats = {
        "scores_loaded": 0,
        "odds_loaded": 0,
        "ratings_loaded": 0,
        "canonicalization_issues": 0,
        "quality_issues": 0,
        "final_records": 0
    }

    try:
        # Step 1: Load canonical scores data
        print("Step 1: Loading canonical scores data...")
        if seasons:
            # Load specific seasons
            scores_dfs = []
            for season in seasons:
                try:
                    season_df = read_canonical_scores(season)
                    scores_dfs.append(season_df)
                    stats["scores_loaded"] += len(season_df)
                    print(f"  Loaded {len(season_df)} games from {season} season")
                except Exception as e:
                    print(f"  Warning: Failed to load season {season}: {e}")
                    if strict_mode:
                        raise

            if scores_dfs:
                games = pd.concat(scores_dfs, ignore_index=True)
            else:
                raise ValueError("No season data loaded")
        else:
            # Load all games
            games = read_canonical_scores()
            stats["scores_loaded"] = len(games)
            print(f"  Loaded {len(games)} total games")

        # Validate scores data
        validation_result = quality_gate.validate(games, "scores")
        if not validation_result.passed:
            stats["quality_issues"] += len(validation_result.issues)
            if strict_mode:
                raise ValueError(f"Scores validation failed: {[issue.message for issue in validation_result.issues[:5]]}")

        print(f"  Scores validation: {len(validation_result.issues)} issues found")

        # Step 2: Load canonical odds data
        print("\nStep 2: Loading canonical odds data...")
        odds_data = {}

        # FG spreads
        try:
            fg_spreads = read_canonical_odds("fg_spread")
            odds_data["fg_spread"] = fg_spreads
            stats["odds_loaded"] += len(fg_spreads)
            print(f"  Loaded {len(fg_spreads)} FG spreads")

            validation_result = quality_gate.validate(fg_spreads, "odds")
            if not validation_result.passed and strict_mode:
                raise ValueError(f"FG spreads validation failed")
        except Exception as e:
            print(f"  Warning: Failed to load FG spreads: {e}")
            if strict_mode:
                raise

        # FG totals
        try:
            fg_totals = read_canonical_odds("fg_total")
            odds_data["fg_total"] = fg_totals
            stats["odds_loaded"] += len(fg_totals)
            print(f"  Loaded {len(fg_totals)} FG totals")
        except Exception as e:
            print(f"  Warning: Failed to load FG totals: {e}")

        # H1 spreads
        try:
            h1_spreads = read_canonical_odds("h1_spread")
            odds_data["h1_spread"] = h1_spreads
            stats["odds_loaded"] += len(h1_spreads)
            print(f"  Loaded {len(h1_spreads)} H1 spreads")
        except Exception as e:
            print(f"  Warning: Failed to load H1 spreads: {e}")

        # H1 totals
        try:
            h1_totals = read_canonical_odds("h1_total")
            odds_data["h1_total"] = h1_totals
            stats["odds_loaded"] += len(h1_totals)
            print(f"  Loaded {len(h1_totals)} H1 totals")
        except Exception as e:
            print(f"  Warning: Failed to load H1 totals: {e}")

        if validate_only:
            print("\nValidation complete!")
            print(f"Stats: {stats}")
            return None

        # Step 3: Merge games with odds data
        print("\nStep 3: Merging games with odds data...")

        # Start with games as base
        backtest_df = games.copy()

        # Merge function for odds data
        def merge_odds_data(base_df: pd.DataFrame, odds_df: pd.DataFrame,
                          odds_type: str, team_col: str = "home_team") -> pd.DataFrame:
            """Merge odds data with proper canonicalization."""
            if odds_df is None or len(odds_df) == 0:
                return base_df

            # Ensure consistent column names
            odds_cols = [col for col in odds_df.columns if col not in ["home_team", "away_team", "date"]]
            odds_df = odds_df[["home_team", "away_team", "date"] + odds_cols].copy()

            # Merge on home team odds
            merge_cols = ["home_team", "away_team", "date"]
            if team_col == "home":
                merge_cols = ["home_team", "date"]

            try:
                merged = base_df.merge(
                    odds_df,
                    on=merge_cols,
                    how="left",
                    suffixes=("", f"_{odds_type}")
                )
                return merged
            except Exception as e:
                print(f"  Warning: Failed to merge {odds_type} odds: {e}")
                return base_df

        # Merge each odds type
        for odds_type, odds_df in odds_data.items():
            print(f"  Merging {odds_type} odds...")
            backtest_df = merge_odds_data(backtest_df, odds_df, odds_type)

        print(f"  Merged dataset shape: {backtest_df.shape}")

        # Step 4: Add ratings data (if available)
        print("\nStep 4: Adding ratings data...")
        try:
            # Get unique seasons
            seasons_in_data = backtest_df["season"].dropna().unique().astype(int)

            ratings_data = []
            for season in seasons_in_data:
                if season >= 2020:  # Barttorvik data starts around here
                    try:
                        season_ratings = azure_reader.read_canonical_ratings(season)
                        # Convert to DataFrame format for merging
                        ratings_df = pd.DataFrame.from_dict(season_ratings, orient="index")
                        ratings_df["season"] = season
                        ratings_df["team"] = ratings_df.index
                        ratings_data.append(ratings_df)
                        stats["ratings_loaded"] += len(ratings_df)
                    except Exception as e:
                        print(f"  Warning: Failed to load ratings for {season}: {e}")

            if ratings_data:
                all_ratings = pd.concat(ratings_data, ignore_index=True)

                # Merge ratings for home and away teams
                backtest_df = backtest_df.merge(
                    all_ratings.add_prefix("home_"),
                    left_on=["home_team", "season"],
                    right_on=["home_team", "home_season"],
                    how="left"
                )

                backtest_df = backtest_df.merge(
                    all_ratings.add_prefix("away_"),
                    left_on=["away_team", "season"],
                    right_on=["away_team", "away_season"],
                    how="left"
                )

                print(f"  Added ratings for {len(all_ratings)} team-seasons")

        except Exception as e:
            print(f"  Warning: Failed to add ratings: {e}")

        # Step 5: Add enhanced features (ncaahoopR)
        if include_enhanced:
            print("\nStep 5: Adding enhanced features...")
            try:
                enhanced_df = read_backtest_master(enhanced=True)
                if len(enhanced_df) > len(backtest_df) * 0.8:  # Has most of our games
                    # Merge enhanced features
                    enhanced_cols = [col for col in enhanced_df.columns
                                   if col not in backtest_df.columns and
                                   col not in ["home_team", "away_team", "date"]]

                    backtest_df = backtest_df.merge(
                        enhanced_df[["home_team", "away_team", "date"] + enhanced_cols],
                        on=["home_team", "away_team", "date"],
                        how="left"
                    )

                    print(f"  Added {len(enhanced_cols)} enhanced features")

            except Exception as e:
                print(f"  Warning: Failed to add enhanced features: {e}")

        # Step 6: Final canonicalization and validation
        print("\nStep 6: Final canonicalization and validation...")

        # Apply final canonical ingestion
        final_result = ingestion_pipeline.ingest_scores_data(
            backtest_df,
            DataSource.ESPN_SCORES
        )

        if not final_result.success and strict_mode:
            raise ValueError(f"Final canonical ingestion failed: {final_result.errors}")

        stats["canonicalization_issues"] = len(final_result.errors) + len(final_result.warnings)
        backtest_df = backtest_df  # Pipeline modifies in-place

        # Final quality check
        final_validation = quality_gate.validate(backtest_df, "backtest")
        if not final_validation.passed and strict_mode:
            raise ValueError(f"Final quality check failed: {[issue.message for issue in final_validation.issues[:5]]}")

        stats["quality_issues"] += len(final_validation.issues)
        stats["final_records"] = len(backtest_df)

        print("\n" + "=" * 80)
        print("BUILD COMPLETE")
        print("=" * 80)
        print(f"Final dataset: {len(backtest_df)} records, {len(backtest_df.columns)} columns")
        print(f"Date range: {backtest_df['game_date'].min()} to {backtest_df['game_date'].max()}")
        print(f"Stats: {stats}")

        if final_result.warnings:
            print(f"Warnings: {len(final_result.warnings)}")
            for warning in final_result.warnings[:3]:
                print(f"  - {warning}")

        return backtest_df

    except Exception as e:
        print(f"\n[ERROR] Build failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_canonical_dataset(df: pd.DataFrame, output_blob: Optional[str] = None):
    """Save the canonical dataset with metadata."""
    if output_blob is None:
        output_blob = "backtest_datasets/backtest_master_canonical.csv"

    # Add metadata
    metadata = {
        "build_timestamp": datetime.now().isoformat(),
        "records": len(df),
        "columns": len(df.columns),
        "date_range": {
            "start": df["game_date"].min().isoformat() if "game_date" in df.columns else None,
            "end": df["game_date"].max().isoformat() if "game_date" in df.columns else None
        },
        "canonical_version": "3.0"
    }

    # Save main data
    write_csv(output_blob, df)

    # Save metadata
    if output_blob.endswith(".csv"):
        metadata_blob = output_blob[:-4] + ".metadata.json"
    else:
        metadata_blob = output_blob + ".metadata.json"
    write_json(metadata_blob, metadata, indent=2)

    print(f"Saved canonical dataset: {output_blob}")
    print(f"Saved metadata: {metadata_blob}")


def main():
    parser = argparse.ArgumentParser(description="Build canonical backtest dataset")
    parser.add_argument("--enhanced", action="store_true",
                       help="Include ncaahoopR enhanced features")
    parser.add_argument("--validate-only", action="store_true",
                       help="Only validate data, don't build dataset")
    parser.add_argument("--seasons", type=int, nargs="+",
                       help="Specific seasons to include")
    parser.add_argument("--lenient", action="store_true",
                       help="Use lenient validation (warnings instead of errors)")
    parser.add_argument("--output", type=str,
                       help="Output blob path for dataset")

    args = parser.parse_args()

    strict_mode = not args.lenient

    result_df = build_canonical_backtest_dataset(
        include_enhanced=args.enhanced,
        validate_only=args.validate_only,
        seasons=args.seasons,
        strict_mode=strict_mode
    )

    if result_df is not None and not args.validate_only:
        save_canonical_dataset(result_df, args.output)


if __name__ == "__main__":
    main()
