#!/usr/bin/env python3
"""
Production Parity Backtest Runner.

Runs a backtest using EXACT production logic:
- Same team resolution (4-step exact matching, NO fuzzy)
- Same prediction models (FGSpread, H1Spread, FGTotal, H1Total)
- Strict anti-leakage (Season N-1 ratings for Season N games)
- All timestamps standardized to CST

Usage:
    # Run full backtest on all seasons
    python -m testing.production_parity.run_backtest

    # Run on specific seasons
    python -m testing.production_parity.run_backtest --seasons 2023 2024

    # Quick test with limited games
    python -m testing.production_parity.run_backtest --max-games 100

    # Quiet mode (less output)
    python -m testing.production_parity.run_backtest --quiet
"""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

# Add parent dirs to path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from testing.production_parity.backtest_engine import ProductionParityBacktest
from testing.production_parity.timezone_utils import format_cst, now_cst


def main():
    parser = argparse.ArgumentParser(
        description="Run Production Parity Backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run full backtest
    python -m testing.production_parity.run_backtest

    # Run on seasons 2023-2024 only
    python -m testing.production_parity.run_backtest --seasons 2023 2024

    # Quick test with 100 games
    python -m testing.production_parity.run_backtest --max-games 100

    # Output to custom directory
    python -m testing.production_parity.run_backtest --output-dir ./my_results
        """
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=None,
        help="Seasons to backtest (e.g., 2023 2024). Default: all available"
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=None,
        help="Maximum games to process (for quick testing)"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory containing historical data. Default: testing/data/historical"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for audit logs and results. Default: testing/production_parity/audit_logs"
    )
    parser.add_argument(
        "--games-file",
        type=Path,
        default=None,
        help="Path to games CSV file. Default: games_all.csv in data-dir"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )

    args = parser.parse_args()

    # Print banner
    print()
    print("=" * 70)
    print("  PRODUCTION PARITY BACKTEST")
    print("=" * 70)
    print(f"  Started: {format_cst(now_cst())}")
    print()
    print("  Configuration:")
    print(f"    Seasons:    {args.seasons or 'ALL'}")
    print(f"    Max Games:  {args.max_games or 'UNLIMITED'}")
    print(f"    Data Dir:   {args.data_dir or 'DEFAULT'}")
    print(f"    Output Dir: {args.output_dir or 'DEFAULT'}")
    print("=" * 70)
    print()

    # Initialize backtest
    backtest = ProductionParityBacktest(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        seasons=args.seasons,
    )

    # Run backtest
    stats = backtest.run(
        games_file=args.games_file,
        max_games=args.max_games,
        verbose=not args.quiet,
    )

    # Print final stats
    backtest.print_stats(stats)

    # Print summary to console
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Games Processed:      {stats.games_predicted:,}")
    print(f"  Games Skipped:        {stats.games_skipped:,}")
    print()
    print(f"  FG Spread MAE:        {stats.fg_spread_mae:.2f} pts")
    print(f"  FG Spread Direction:  {stats.fg_spread_direction_accuracy:.1%}")
    print()
    print(f"  H1 Spread MAE:        {stats.h1_spread_mae:.2f} pts")
    print(f"  H1 Spread Direction:  {stats.h1_spread_direction_accuracy:.1%}")
    print()
    print(f"  FG Total MAE:         {stats.fg_total_mae:.2f} pts")
    print(f"  H1 Total MAE:         {stats.h1_total_mae:.2f} pts")
    print()
    print(f"  Team Resolution:      {stats.team_resolution_rate:.1%}")
    print(f"  Ratings Found:        {stats.ratings_found_rate:.1%}")
    print("=" * 70)
    print()

    # Return exit code based on success
    if stats.games_predicted == 0:
        print("[ERROR] No games were predicted!")
        return 1

    # Check for reasonable metrics
    if stats.fg_spread_direction_accuracy < 0.5:
        print("[WARNING] FG Spread direction accuracy below 50%")

    print(f"Completed at: {format_cst(now_cst())}")
    print("Audit logs saved to:", backtest.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
