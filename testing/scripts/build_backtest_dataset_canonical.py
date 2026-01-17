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
    python testing/scripts/build_backtest_dataset_canonical.py --validate-only  # Just validate, don't build
    python testing/scripts/build_backtest_dataset_canonical.py --force  # Rebuild even if output exists
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from testing.azure_data_reader import (
    get_azure_reader,
    read_canonical_odds,
    read_canonical_scores,
)
from testing.azure_io import blob_exists, write_csv, write_json
from testing.canonical.ingestion_pipeline import CanonicalIngestionPipeline, DataSource
from testing.canonical.quality_gates import DataQualityGate
from testing.canonical.schema_evolution import SchemaEvolutionManager
from testing.canonical.team_resolution_service import get_team_resolver
from testing.data_window import (
    CANONICAL_START_DATE,
    CANONICAL_START_SEASON,
    default_backtest_seasons,
    enforce_min_season,
    season_from_date,
)


def _canonicalize_team_series(series: pd.Series, resolver) -> pd.Series:
    """Resolve team names using the canonical alias database."""
    if series is None or series.empty:
        return series

    unique_names = series.dropna().unique()
    mapping = {}
    for name in unique_names:
        result = resolver.resolve(str(name))
        mapping[name] = result.canonical_name if result.canonical_name else str(name)
    return series.map(mapping)


def _parse_barttorvik_payload(payload, season: int, resolver) -> pd.DataFrame:
    """Parse Barttorvik ratings payload into a normalized DataFrame."""
    records = []

    def to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    if isinstance(payload, list):
        for row in payload:
            if not isinstance(row, list) or len(row) < 7:
                continue
            team_raw = str(row[1]).strip()
            canonical = resolver.resolve(team_raw).canonical_name or team_raw
            adj_t = to_float(row[44]) if len(row) > 44 else None
            records.append({
                "team": canonical,
                "adj_o": to_float(row[4]),
                "adj_d": to_float(row[6]),
                "adj_t": adj_t,
                "tempo": adj_t,
                "season": season,
            })
    elif isinstance(payload, dict):
        for team_raw, row in payload.items():
            canonical = resolver.resolve(str(team_raw)).canonical_name or str(team_raw)
            if isinstance(row, dict):
                adj_t = row.get("adj_t") if "adj_t" in row else row.get("tempo")
                records.append({
                    "team": canonical,
                    "adj_o": to_float(row.get("adj_o")),
                    "adj_d": to_float(row.get("adj_d")),
                    "adj_t": to_float(adj_t),
                    "tempo": to_float(adj_t),
                    "season": season,
                })
            elif isinstance(row, list) and len(row) >= 7:
                adj_t = to_float(row[44]) if len(row) > 44 else None
                records.append({
                    "team": canonical,
                    "adj_o": to_float(row[4]),
                    "adj_d": to_float(row[6]),
                    "adj_t": adj_t,
                    "tempo": adj_t,
                    "season": season,
                })
    else:
        raise ValueError("Unsupported ratings payload type")

    return pd.DataFrame(records)


def build_canonical_backtest_dataset(
    validate_only: bool = False,
    seasons: list[int] | None = None,
    strict_mode: bool = True
) -> pd.DataFrame | None:
    """
    Build canonical backtest dataset using ingestion pipeline.

    Args:
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
    print(f"Strict mode: {'YES' if strict_mode else 'NO'}")
    print(f"Validate only: {'YES' if validate_only else 'NO'}")
    print()

    # Enforce canonical data window (2023-24 season onward).
    if seasons is None:
        seasons = default_backtest_seasons()
    else:
        seasons = enforce_min_season(seasons)

    # Initialize canonical components
    azure_reader = get_azure_reader()
    ingestion_pipeline = CanonicalIngestionPipeline(strict_mode=strict_mode)
    quality_gate = DataQualityGate(strict_mode=strict_mode)
    schema_manager = SchemaEvolutionManager()
    resolver = get_team_resolver()

    # Track statistics
    stats = {
        "scores_loaded": 0,
        "odds_loaded": 0,
        "h1_loaded": 0,
        "ratings_loaded": 0,
        "canonicalization_issues": 0,
        "quality_issues": 0,
        "final_records": 0
    }

    try:
        # Step 1: Load canonical scores data
        print("Step 1: Loading canonical scores data...")
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

        # Validate scores data
        validation_result = quality_gate.validate(games, "scores")
        if not validation_result.passed:
            stats["quality_issues"] += len(validation_result.issues)
            if strict_mode:
                raise ValueError(f"Scores validation failed: {[issue.message for issue in validation_result.issues[:5]]}")

        print(f"  Scores validation: {len(validation_result.issues)} issues found")

        # Ensure canonical team name columns for downstream merges
        if "home_canonical" not in games.columns:
            games["home_canonical"] = _canonicalize_team_series(games["home_team"], resolver)
        if "away_canonical" not in games.columns:
            games["away_canonical"] = _canonicalize_team_series(games["away_team"], resolver)

        # Step 1b: Load canonical H1 scores if available
        print("\nStep 1b: Loading canonical H1 scores...")
        h1_df = None
        try:
            # Load without canonical ingestion to avoid failing on unresolved teams.
            h1_df = azure_reader.read_csv("scores/h1/h1_games_all.csv", data_type=None)
        except Exception as e:
            print(f"  Warning: Failed to load H1 scores: {e}")

        if h1_df is not None and not h1_df.empty:
            if "date" not in h1_df.columns and "game_date" in h1_df.columns:
                h1_df["date"] = h1_df["game_date"]
            if "date" in h1_df.columns:
                h1_df["date"] = pd.to_datetime(h1_df["date"], errors="coerce")
                h1_df = h1_df[h1_df["date"] >= pd.Timestamp(CANONICAL_START_DATE)]
            if "season" in h1_df.columns:
                h1_df = h1_df[h1_df["season"] >= CANONICAL_START_SEASON]

            if seasons:
                if "season" in h1_df.columns:
                    h1_df = h1_df[h1_df["season"].isin(seasons)].copy()
                elif "date" in h1_df.columns:
                    h1_df["_season"] = h1_df["date"].apply(
                        lambda d: season_from_date(d.date()) if pd.notna(d) else None
                    )
                    h1_df = h1_df[h1_df["_season"].isin(seasons)].drop(columns=["_season"])

            h1_cols = [col for col in ["home_h1", "away_h1", "h1_total"] if col in h1_df.columns]
            merge_cols = []

            if "game_id" in games.columns and "game_id" in h1_df.columns:
                games["game_id"] = games["game_id"].astype(str)
                h1_df["game_id"] = h1_df["game_id"].astype(str)
                merge_cols = ["game_id"]
            else:
                h1_df["home_canonical"] = _canonicalize_team_series(h1_df["home_team"], resolver)
                h1_df["away_canonical"] = _canonicalize_team_series(h1_df["away_team"], resolver)
                if "date" not in games.columns and "game_date" in games.columns:
                    games["date"] = games["game_date"]
                if "date" in games.columns:
                    games["date"] = pd.to_datetime(games["date"], errors="coerce").dt.normalize()
                if "date" in h1_df.columns:
                    h1_df["date"] = pd.to_datetime(h1_df["date"], errors="coerce").dt.normalize()
                merge_cols = ["home_canonical", "away_canonical", "date"]

            if merge_cols and h1_cols:
                h1_df = h1_df[merge_cols + h1_cols].drop_duplicates(subset=merge_cols, keep="first")
                games = games.merge(h1_df, on=merge_cols, how="left", suffixes=("", "_h1"))
                for col in h1_cols:
                    h1_col = f"{col}_h1"
                    if h1_col in games.columns:
                        if col in games.columns:
                            games[col] = games[col].fillna(games[h1_col])
                        else:
                            games[col] = games[h1_col]
                games = games.drop(columns=[f"{col}_h1" for col in h1_cols], errors="ignore")
                stats["h1_loaded"] = len(h1_df)
                h1_coverage = games[h1_cols[0]].notna().sum() if h1_cols else 0
                print(f"  Merged H1 scores: {h1_coverage:,} games with data")
            else:
                print("  Warning: H1 scores missing merge keys or columns")
        else:
            print("  Warning: H1 scores dataset is empty")

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
                raise ValueError("FG spreads validation failed")
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
        same_team = backtest_df["home_team"] == backtest_df["away_team"]
        if same_team.any():
            print(f"  Dropping {int(same_team.sum())} games with identical home/away teams")
            backtest_df = backtest_df.loc[~same_team].copy()
        if "home_score" in backtest_df.columns and "away_score" in backtest_df.columns:
            if "actual_margin" not in backtest_df.columns:
                backtest_df["actual_margin"] = backtest_df["home_score"] - backtest_df["away_score"]
            if "actual_total" not in backtest_df.columns:
                backtest_df["actual_total"] = backtest_df["home_score"] + backtest_df["away_score"]
        if "home_h1" in backtest_df.columns and "away_h1" in backtest_df.columns:
            if "h1_actual_margin" not in backtest_df.columns:
                backtest_df["h1_actual_margin"] = backtest_df["home_h1"] - backtest_df["away_h1"]
            if "h1_actual_total" not in backtest_df.columns:
                backtest_df["h1_actual_total"] = backtest_df["home_h1"] + backtest_df["away_h1"]

        # Merge function for odds data
        def merge_odds_data(base_df: pd.DataFrame, odds_df: pd.DataFrame,
                          odds_type: str, team_col: str = "home_team") -> pd.DataFrame:
            """Merge odds data with proper canonicalization.

            Uses canonical team names for matching:
            - scores: home_canonical, away_canonical
            - odds: home_team_canonical, away_team_canonical
            """
            if odds_df is None or len(odds_df) == 0:
                return base_df

            odds_df = odds_df.copy()

            line_cols = [
                col for col in odds_df.columns
                if col.startswith("line_timestamp") and "source" not in col
            ]
            if line_cols and "commence_time" in odds_df.columns:
                commence_time = pd.to_datetime(odds_df["commence_time"], errors="coerce", utc=True)
                for col in line_cols:
                    line_time = pd.to_datetime(odds_df[col], errors="coerce", utc=True)
                    violations = line_time.notna() & commence_time.notna() & (line_time > commence_time)
                    if violations.any():
                        raise ValueError(
                            f"{odds_type} odds contain {int(violations.sum())} line timestamps after commence_time"
                        )
            elif line_cols:
                raise ValueError(f"{odds_type} odds missing commence_time for pregame validation")

            # Odds data uses 'game_date', scores use 'date' - normalize
            if "game_date" in odds_df.columns and "date" not in odds_df.columns:
                odds_df = odds_df.rename(columns={"game_date": "date"})

            # Normalize date column type for reliable merges
            if "date" in odds_df.columns:
                odds_df["date"] = pd.to_datetime(odds_df["date"], errors="coerce")
                if odds_df["date"].isna().all() and "commence_time" in odds_df.columns:
                    odds_df["date"] = pd.to_datetime(odds_df["commence_time"], errors="coerce").dt.normalize()
            elif "commence_time" in odds_df.columns:
                odds_df["date"] = pd.to_datetime(odds_df["commence_time"], errors="coerce").dt.normalize()

            # Normalize base dates to date-only (no time component) for matching
            base_df["date"] = pd.to_datetime(base_df["date"], errors="coerce").dt.normalize()
            odds_df["date"] = odds_df["date"].dt.normalize()

            # Create merge keys using canonical team names resolved from the alias DB.
            if "home_canonical" not in base_df.columns or "away_canonical" not in base_df.columns:
                base_df = base_df.copy()
                base_df["home_canonical"] = _canonicalize_team_series(base_df["home_team"], resolver)
                base_df["away_canonical"] = _canonicalize_team_series(base_df["away_team"], resolver)

            home_source = "home_team_canonical" if "home_team_canonical" in odds_df.columns else "home_team"
            away_source = "away_team_canonical" if "away_team_canonical" in odds_df.columns else "away_team"
            odds_df["home_canonical"] = _canonicalize_team_series(odds_df[home_source], resolver)
            odds_df["away_canonical"] = _canonicalize_team_series(odds_df[away_source], resolver)
            merge_cols = ["home_canonical", "away_canonical", "date"]

            # Get odds-specific columns to keep
            odds_cols = [col for col in odds_df.columns
                        if col not in ["home_team", "away_team", "date",
                                       "home_team_canonical", "away_team_canonical",
                                       "home_canonical", "away_canonical",
                                       "game_date", "commence_time"]]

            cols_to_keep = merge_cols + odds_cols
            odds_df = odds_df[cols_to_keep].copy()

            # Drop duplicates - keep first occurrence per game
            odds_df = odds_df.drop_duplicates(subset=merge_cols, keep="first")

            try:
                merged = base_df.merge(
                    odds_df,
                    on=merge_cols,
                    how="left",
                    suffixes=("", f"_{odds_type}")
                )
                matched = merged[odds_cols[0] if odds_cols else merge_cols[0]].notna().sum() if odds_cols else 0
                print(f"    Matched {matched:,} records")
                return merged
            except Exception as e:
                print(f"  Warning: Failed to merge {odds_type} odds: {e}")
                return base_df

        # Normalize base date columns to datetime for consistent merges
        if "date" in backtest_df.columns:
            backtest_df["date"] = pd.to_datetime(backtest_df["date"], errors="coerce")
        if "game_date" in backtest_df.columns:
            backtest_df["game_date"] = pd.to_datetime(backtest_df["game_date"], errors="coerce")

        # Merge each odds type
        for odds_type, odds_df in odds_data.items():
            print(f"  Merging {odds_type} odds...")
            backtest_df = merge_odds_data(backtest_df, odds_df, odds_type)

        print(f"  Merged dataset shape: {backtest_df.shape}")

        # Step 4: Add ratings data (if available)
        print("\nStep 4: Adding ratings data...")
        try:
            # Use prior-season ratings to prevent leakage (season N games use N-1 ratings).
            if "ratings_season" not in backtest_df.columns:
                backtest_df["ratings_season"] = pd.to_numeric(
                    backtest_df["season"], errors="coerce"
                ).astype("Int64") - 1

            ratings_seasons = sorted(
                backtest_df["ratings_season"].dropna().unique().astype(int)
            )
            min_ratings_season = CANONICAL_START_SEASON - 1

            ratings_data = []
            for season in ratings_seasons:
                if season >= min_ratings_season:
                    try:
                        season_ratings = azure_reader.read_canonical_ratings(season)
                        ratings_df = _parse_barttorvik_payload(season_ratings, season, resolver)
                        if not ratings_df.empty:
                            ratings_data.append(ratings_df)
                            stats["ratings_loaded"] += len(ratings_df)
                    except Exception as e:
                        print(f"  Warning: Failed to load ratings for {season}: {e}")

            if ratings_data:
                all_ratings = pd.concat(ratings_data, ignore_index=True)
                if "team" in all_ratings.columns:
                    all_ratings = all_ratings.rename(columns={"team": "team_canonical"})
                if "season" in all_ratings.columns:
                    all_ratings["season"] = pd.to_numeric(
                        all_ratings["season"], errors="coerce"
                    ).astype("Int64")

                # Merge ratings for home and away teams
                backtest_df = backtest_df.merge(
                    all_ratings.add_prefix("home_"),
                    left_on=["home_canonical", "ratings_season"],
                    right_on=["home_team_canonical", "home_season"],
                    how="left"
                )

                backtest_df = backtest_df.merge(
                    all_ratings.add_prefix("away_"),
                    left_on=["away_canonical", "ratings_season"],
                    right_on=["away_team_canonical", "away_season"],
                    how="left"
                )

                print(f"  Added ratings for {len(all_ratings)} team-seasons")
                if "home_team_canonical" in backtest_df.columns and "home_canonical" in backtest_df.columns:
                    backtest_df["home_team_canonical"] = backtest_df["home_team_canonical"].fillna(
                        backtest_df["home_canonical"]
                    )
                if "away_team_canonical" in backtest_df.columns and "away_canonical" in backtest_df.columns:
                    backtest_df["away_team_canonical"] = backtest_df["away_team_canonical"].fillna(
                        backtest_df["away_canonical"]
                    )

        except Exception as e:
            print(f"  Warning: Failed to add ratings: {e}")

        # Step 5: Final canonicalization and validation
        print("\nStep 5: Final canonicalization and validation...")

        # Apply final canonical ingestion (scores-like validation)
        final_result = ingestion_pipeline.ingest_scores_data(
            backtest_df,
            DataSource.ESPN_SCORES
        )

        if not final_result.success and strict_mode:
            raise ValueError(f"Final canonical ingestion failed: {final_result.errors}")

        stats["canonicalization_issues"] = len(final_result.errors) + len(final_result.warnings)

        # Ensure both date and game_date exist and are consistent for
        # downstream consumers and quality gates.
        if "game_date" in backtest_df.columns and "date" not in backtest_df.columns:
            backtest_df["date"] = backtest_df["game_date"]
        elif "date" in backtest_df.columns and "game_date" not in backtest_df.columns:
            backtest_df["game_date"] = backtest_df["date"]

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
        if "game_date" in backtest_df.columns:
            print(f"Date range: {backtest_df['game_date'].min()} to {backtest_df['game_date'].max()}")
        elif "date" in backtest_df.columns:
            print(f"Date range: {backtest_df['date'].min()} to {backtest_df['date'].max()}")
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


def save_canonical_dataset(df: pd.DataFrame, output_blob: str | None = None):
    """Save the canonical backtest dataset with metadata.

    By default this overwrites the primary backtest master used
    throughout the codebase and in Azure:
        backtest_datasets/backtest_master.csv
    """
    if output_blob is None:
        # Align with AzureDataReader.read_backtest_master and docs
        output_blob = "backtest_datasets/backtest_master.csv"

    # Add metadata
    # Helper to safely serialize date-like values
    def _to_iso(val):
        if val is None:
            return None
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    start_val = None
    end_val = None
    if "game_date" in df.columns:
        start_val = df["game_date"].min()
        end_val = df["game_date"].max()
    elif "date" in df.columns:
        start_val = df["date"].min()
        end_val = df["date"].max()

    metadata = {
        "build_timestamp": datetime.now().isoformat(),
        "records": len(df),
        "columns": len(df.columns),
        "date_range": {
            "start": _to_iso(start_val),
            "end": _to_iso(end_val),
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
    parser.add_argument("--validate-only", action="store_true",
                       help="Only validate data, don't build dataset")
    parser.add_argument("--seasons", type=int, nargs="+",
                       help="Specific seasons to include")
    parser.add_argument("--lenient", action="store_true",
                       help="Use lenient validation (warnings instead of errors)")
    parser.add_argument("--output", type=str,
                       help="Output blob path for dataset")
    parser.add_argument("--force", action="store_true",
                       help="Rebuild even if the output already exists")

    args = parser.parse_args()

    strict_mode = not args.lenient

    output_blob = args.output or "backtest_datasets/backtest_master.csv"
    if not args.validate_only and not args.force:
        try:
            if blob_exists(output_blob):
                print(f"[SKIP] Output already exists: {output_blob}")
                print("       Use --force to rebuild.")
                return
        except Exception as exc:
            print(f"[WARN] Could not check output existence: {exc}")
            print("       Proceeding with rebuild.")

    result_df = build_canonical_backtest_dataset(
        validate_only=args.validate_only,
        seasons=args.seasons,
        strict_mode=strict_mode
    )

    if result_df is not None and not args.validate_only:
        save_canonical_dataset(result_df, output_blob)


if __name__ == "__main__":
    main()
