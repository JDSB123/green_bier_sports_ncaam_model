#!/usr/bin/env python3
"""
CLEAN RESULTS HISTORY

Cleans up old backtest result files, keeping only the most recent results
to maintain clean data history and outputs.

Keeps:
- Most recent 5 results per market type
- Any results from the last 7 days
- Important summary files

Removes:
- Old CSV result files (>5 per market)
- Old JSON summary files (>5 per market)
- Temporary debug files
- Files older than 30 days (except most recent)

Usage:
    python testing/scripts/clean_results_history.py --dry-run  # Preview cleanup
    python testing/scripts/clean_results_history.py --clean    # Perform cleanup
    python testing/scripts/clean_results_history.py --keep-days 14  # Keep 14 days
"""

import argparse
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import re

RESULTS_DIR = Path(__file__).resolve().parents[2] / "testing" / "results"


def parse_result_filename(filename: str) -> dict:
    """Parse result filename to extract metadata."""
    # Examples:
    # fg_spread_summary_20260110_145755.json
    # h1_spread_results_20260110_113648.csv
    # backtest_results.csv

    pattern = r'^(?P<market>fg_spread|fg_total|h1_spread|h1_total|backtest)_(?P<filetype>summary|results)_(?P<date>\d{8})_(?P<time>\d{6})\.(?P<ext>json|csv)$'
    match = re.match(pattern, filename)

    if match:
        date_str = match.group('date')
        time_str = match.group('time')
        datetime_str = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
        try:
            file_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            return {
                'market': match.group('market'),
                'filetype': match.group('filetype'),
                'datetime': file_datetime,
                'filename': filename
            }
        except ValueError:
            pass

    # Fallback for unrecognized files
    return {
        'market': 'unknown',
        'filetype': 'unknown',
        'datetime': datetime.min,
        'filename': filename
    }


def find_result_files(results_dir: Path) -> list[dict]:
    """Find all result files and parse their metadata."""
    result_files = []

    if not results_dir.exists():
        return result_files

    for file_path in results_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix in ['.json', '.csv']:
            metadata = parse_result_filename(file_path.name)
            metadata['path'] = file_path
            metadata['size'] = file_path.stat().st_size
            result_files.append(metadata)

    return result_files


def categorize_files_by_market_and_type(files: list[dict]) -> dict:
    """Categorize files by market and file type."""
    categories = defaultdict(lambda: defaultdict(list))

    for file_info in files:
        market = file_info['market']
        filetype = file_info['filetype']
        categories[market][filetype].append(file_info)

    return categories


def identify_files_to_remove(categories: dict, keep_recent: int = 5, keep_days: int = 30) -> list[Path]:
    """Identify files to remove based on retention policy."""
    files_to_remove = []
    cutoff_date = datetime.now() - timedelta(days=keep_days)

    for market, filetypes in categories.items():
        for filetype, files in filetypes.items():
            if not files:
                continue

            # Sort by datetime (newest first)
            sorted_files = sorted(files, key=lambda x: x['datetime'], reverse=True)

            # Keep most recent N files
            keep_files = sorted_files[:keep_recent]

            # Also keep files from last keep_days days
            recent_files = [f for f in sorted_files if f['datetime'] > cutoff_date]
            keep_set = set(f['path'] for f in keep_files + recent_files)

            # Files to remove are those not in keep_set
            for file_info in sorted_files:
                if file_info['path'] not in keep_set:
                    files_to_remove.append(file_info['path'])

    return files_to_remove


def clean_empty_directories(results_dir: Path):
    """Remove empty directories."""
    for dir_path in sorted(results_dir.rglob("*"), reverse=True):
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            dir_path.rmdir()


def clean_results_history(dry_run: bool = True, keep_recent: int = 5, keep_days: int = 30):
    """Clean up old result files."""

    print("=" * 70)
    print("CLEAN RESULTS HISTORY")
    print("=" * 70)
    print(f"Results directory: {RESULTS_DIR}")
    print(f"Keep most recent: {keep_recent} files per market/type")
    print(f"Keep files from last: {keep_days} days")
    print(f"Dry run: {dry_run}")
    print()

    if not RESULTS_DIR.exists():
        print("Results directory does not exist.")
        return

    # Find all result files
    result_files = find_result_files(RESULTS_DIR)
    print(f"Found {len(result_files)} result files")

    if not result_files:
        print("No result files found.")
        return

    # Categorize files
    categories = categorize_files_by_market_and_type(result_files)

    print("\nFiles by market and type:")
    for market, filetypes in categories.items():
        for filetype, files in filetypes.items():
            print(f"  {market}/{filetype}: {len(files)} files")

    # Identify files to remove
    files_to_remove = identify_files_to_remove(categories, keep_recent, keep_days)

    print(f"\nFiles to remove: {len(files_to_remove)}")

    if files_to_remove:
        print("\nFiles that will be removed:")
        for file_path in sorted(files_to_remove):
            try:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                print(".2f"            except:
                print(f"  {file_path}")

        if not dry_run:
            print("\nRemoving files...")
            for file_path in files_to_remove:
                try:
                    file_path.unlink()
                    print(f"  Removed: {file_path}")
                except Exception as e:
                    print(f"  Error removing {file_path}: {e}")

            # Clean up empty directories
            clean_empty_directories(RESULTS_DIR)
            print("\nCleaned up empty directories")

    print(f"\nCleanup complete! {'(dry run)' if dry_run else ''}")


def main():
    parser = argparse.ArgumentParser(description="Clean up old backtest result files")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview what will be removed without deleting")
    parser.add_argument("--clean", action="store_true",
                       help="Actually remove the old files")
    parser.add_argument("--keep-recent", type=int, default=5,
                       help="Keep N most recent files per market/type (default: 5)")
    parser.add_argument("--keep-days", type=int, default=30,
                       help="Keep files from last N days (default: 30)")

    args = parser.parse_args()

    if not args.dry_run and not args.clean:
        args.dry_run = True  # Default to dry run

    clean_results_history(
        dry_run=args.dry_run,
        keep_recent=args.keep_recent,
        keep_days=args.keep_days
    )


if __name__ == "__main__":
    main()