#!/usr/bin/env python3
"""
Run Backtest Suite - Main entry point for all backtest operations.

This script provides a CLI for running different types of backtests
without modifying production code.

Usage:
    # Run calibration validation
    python run_backtest_suite.py calibration --seasons 2021 2022 2023 2024
    
    # Run ROI simulation
    python run_backtest_suite.py roi --season 2021
    
    # Run full validation (all tests)
    python run_backtest_suite.py full

All results are saved to testing/production_parity/audit_logs/
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add paths
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR.parent / "services" / "prediction-service-python"))

from production_parity.backtest_engine import ProductionParityBacktest
from production_parity.roi_simulator import ROISimulator


def run_calibration_validation(seasons: list, verbose: bool = True) -> dict:
    """
    Run calibration validation across specified seasons.
    
    Uses anti-leakage methodology:
    - Season N games use Season N-1 ratings
    - No future data contamination
    """
    print("\n" + "=" * 60)
    print("CALIBRATION VALIDATION")
    print("=" * 60)
    print(f"Seasons: {seasons}")
    
    # Run backtest with season filter
    backtest = ProductionParityBacktest(seasons=seasons)
    stats = backtest.run(verbose=verbose)
    
    # Extract results per model
    results = {
        "FGSpread": {
            "games": stats.fg_spread_count,
            "mae": stats.fg_spread_mae,
            "direction_accuracy": stats.fg_spread_direction_accuracy,
        },
        "FGTotal": {
            "games": stats.fg_total_count,
            "mae": stats.fg_total_mae,
            "direction_accuracy": stats.fg_total_direction_accuracy,
        },
        "H1Spread": {
            "games": stats.h1_spread_count,
            "mae": stats.h1_spread_mae,
            "direction_accuracy": stats.h1_spread_direction_accuracy,
        },
        "H1Total": {
            "games": stats.h1_total_count,
            "mae": stats.h1_total_mae,
            "direction_accuracy": stats.h1_total_direction_accuracy,
        },
    }
    
    # Print summary
    print("\n" + "-" * 60)
    print("SUMMARY BY MODEL")
    print("-" * 60)
    for model, data in results.items():
        print(f"  {model}: {data['games']} games, MAE={data['mae']:.2f}, Dir={data['direction_accuracy']*100:.1f}%")
    
    print(f"\nTotal games predicted: {stats.games_predicted}")
    print(f"Games skipped: {stats.games_skipped}")
    
    return results


def run_roi_simulation(seasons: list, thresholds: list = None) -> dict:
    """
    Run ROI simulation with historical odds.
    
    Tests different edge thresholds to find optimal betting criteria.
    """
    print("\n" + "=" * 60)
    print("ROI SIMULATION")
    print("=" * 60)
    
    if thresholds is None:
        thresholds = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    
    simulator = ROISimulator()
    
    print("\nLoading historical odds...")
    odds_count = simulator.load_historical_odds()
    
    if odds_count == 0:
        print("❌ No historical odds found. Cannot run ROI simulation.")
        print("   Expected canonical odds under ncaam_historical_data_local/odds/normalized/")
        return {}
    
    all_results = {}
    
    for season in seasons:
        print(f"\n--- Season {season} ---")
        results = simulator.simulate_season(season, thresholds)
        all_results[season] = results
        
        simulator.print_results(results)
    
    return all_results


def run_full_validation():
    """Run complete validation suite."""
    print("\n" + "#" * 60)
    print("#  FULL VALIDATION SUITE")
    print("#" * 60)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = ROOT_DIR / "production_parity" / "audit_logs"
    output_dir.mkdir(exist_ok=True)
    
    # 1. Calibration validation
    calib_seasons = [2021, 2022, 2023, 2024, 2025]
    calib_results = run_calibration_validation(calib_seasons)
    
    # 2. ROI simulation (only for seasons with odds)
    roi_seasons = [2021]  # Expand as more odds data available
    roi_results = run_roi_simulation(roi_seasons)
    
    # Save combined results
    output = {
        "timestamp": datetime.now().isoformat(),
        "calibration": calib_results,
        "roi": roi_results,
    }
    
    output_file = output_dir / f"full_validation_{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n✅ Full validation complete. Results saved to:")
    print(f"   {output_file}")
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description="NCAAM Model Backtest Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_backtest_suite.py calibration --seasons 2024 2025
  python run_backtest_suite.py roi --seasons 2021
  python run_backtest_suite.py full
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Backtest type")
    
    # Calibration subcommand
    calib_parser = subparsers.add_parser("calibration", help="Validate calibrations")
    calib_parser.add_argument(
        "--seasons", 
        nargs="+", 
        type=int, 
        default=[2024, 2025],
        help="Seasons to test"
    )
    
    # ROI subcommand
    roi_parser = subparsers.add_parser("roi", help="Run ROI simulation")
    roi_parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2021],
        help="Seasons to simulate"
    )
    roi_parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=[1.0, 1.5, 2.0, 2.5, 3.0],
        help="Edge thresholds to test"
    )
    
    # Full subcommand
    full_parser = subparsers.add_parser("full", help="Run full validation suite")
    
    args = parser.parse_args()
    
    if args.command == "calibration":
        run_calibration_validation(args.seasons)
    elif args.command == "roi":
        run_roi_simulation(args.seasons, args.thresholds)
    elif args.command == "full":
        run_full_validation()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
