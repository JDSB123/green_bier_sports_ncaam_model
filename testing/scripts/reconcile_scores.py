#!/usr/bin/env python3
"""
SCORE DATA RECONCILIATION

Uses ESPN Canonical scores as the source of truth to fix score mismatches
in derived datasets (backtest_ready.csv, backtest_complete.csv).

ESPN data comes directly from ESPN API and is the most authoritative source.

Usage:
    python testing/scripts/reconcile_scores.py --dry-run  # Preview changes
    python testing/scripts/reconcile_scores.py --apply    # Apply fixes
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

# Add project root
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "testing"))

from testing.data_paths import DATA_PATHS
from testing.azure_io import read_csv, write_csv, blob_exists


def load_espn_canonical() -> pd.DataFrame:
    """Load ESPN canonical scores as source of truth."""
    fg_path = str(DATA_PATHS.scores_fg_canonical / "games_all_canonical.csv")
    h1_path = str(DATA_PATHS.scores_h1_canonical / "h1_games_all_canonical.csv")

    # Load full game scores
    if not blob_exists(fg_path):
        raise FileNotFoundError(f"Azure blob not found: {fg_path}")
    fg = read_csv(fg_path)
    fg['game_key'] = (
        fg['date'] + '|' +
        fg['home_canonical'].str.lower() + '|' +
        fg['away_canonical'].str.lower()
    )

    # Load H1 scores
    if blob_exists(h1_path):
        h1 = read_csv(h1_path)
        h1['game_key'] = (
            h1['date'] + '|' +
            h1['home_canonical'].str.lower() + '|' +
            h1['away_canonical'].str.lower()
        )
        # Merge H1 scores
        fg = fg.merge(
            h1[['game_key', 'home_h1', 'away_h1']],
            on='game_key',
            how='left'
        )

    return fg


def reconcile_backtest_ready(
    espn: pd.DataFrame,
    dry_run: bool = True,
) -> Dict:
    """Reconcile backtest_ready.csv with ESPN canonical scores."""
    br_path = str(DATA_PATHS.backtest_datasets / "backtest_ready.csv")

    if not blob_exists(br_path):
        print(f"  [SKIP] {br_path} not found in Azure")
        return {"status": "skipped", "reason": "file not found"}

    # Load backtest_ready
    br = read_csv(br_path)
    original_len = len(br)
    original_br = br.copy()

    # Create game key for matching
    br['game_key'] = (
        br['game_date'] + '|' +
        br['home_team'].str.lower() + '|' +
        br['away_team'].str.lower()
    )

    # Build lookup from ESPN
    espn_scores = {}
    for _, row in espn.iterrows():
        key = row['game_key']
        espn_scores[key] = {
            'home_score': row['home_score'],
            'away_score': row['away_score'],
            'home_h1': row.get('home_h1'),
            'away_h1': row.get('away_h1'),
        }

    # Track changes
    changes = []
    rows_updated = 0

    for idx, row in br.iterrows():
        key = row['game_key']
        if key in espn_scores:
            espn_data = espn_scores[key]

            # Check for score differences
            if pd.notna(espn_data['home_score']):
                if row['home_score'] != espn_data['home_score']:
                    changes.append({
                        'row': idx,
                        'date': row['game_date'],
                        'teams': f"{row['away_team']} @ {row['home_team']}",
                        'field': 'home_score',
                        'old': row['home_score'],
                        'new': espn_data['home_score'],
                    })
                    br.at[idx, 'home_score'] = espn_data['home_score']

            if pd.notna(espn_data['away_score']):
                if row['away_score'] != espn_data['away_score']:
                    changes.append({
                        'row': idx,
                        'date': row['game_date'],
                        'teams': f"{row['away_team']} @ {row['home_team']}",
                        'field': 'away_score',
                        'old': row['away_score'],
                        'new': espn_data['away_score'],
                    })
                    br.at[idx, 'away_score'] = espn_data['away_score']

            # Update H1 scores if available
            if 'h1_home_score' in br.columns and pd.notna(espn_data.get('home_h1')):
                if row.get('h1_home_score') != espn_data['home_h1']:
                    changes.append({
                        'row': idx,
                        'date': row['game_date'],
                        'teams': f"{row['away_team']} @ {row['home_team']}",
                        'field': 'h1_home_score',
                        'old': row.get('h1_home_score'),
                        'new': espn_data['home_h1'],
                    })
                    br.at[idx, 'h1_home_score'] = espn_data['home_h1']

            if 'h1_away_score' in br.columns and pd.notna(espn_data.get('away_h1')):
                if row.get('h1_away_score') != espn_data['away_h1']:
                    changes.append({
                        'row': idx,
                        'date': row['game_date'],
                        'teams': f"{row['away_team']} @ {row['home_team']}",
                        'field': 'h1_away_score',
                        'old': row.get('h1_away_score'),
                        'new': espn_data['away_h1'],
                    })
                    br.at[idx, 'h1_away_score'] = espn_data['away_h1']

    # Recalculate derived fields if scores changed
    if changes:
        # actual_margin = home_score - away_score
        if 'actual_margin' in br.columns:
            br['actual_margin'] = br['home_score'] - br['away_score']

        # actual_total = home_score + away_score
        if 'actual_total' in br.columns:
            br['actual_total'] = br['home_score'] + br['away_score']

        # spread_result = actual_margin + spread
        if 'spread_result' in br.columns and 'spread' in br.columns:
            br['spread_result'] = br['actual_margin'] + br['spread']

        # home_covered = spread_result > 0
        if 'home_covered' in br.columns and 'spread_result' in br.columns:
            br['home_covered'] = br['spread_result'] > 0

        # total_result and went_over
        if 'total' in br.columns:
            if 'total_result' in br.columns:
                br['total_result'] = br['actual_total'] - br['total']
            if 'went_over' in br.columns:
                br['went_over'] = br['actual_total'] > br['total']

    # Drop the temp game_key column
    br = br.drop(columns=['game_key'])

    result = {
        'file': str(br_path),
        'original_rows': original_len,
        'changes_count': len(changes),
        'changes': changes[:20],  # Sample
    }

    if not dry_run and changes:
        stamp = datetime.utcnow().strftime("%Y-%m-%d")
        # Backup original
        backup_path = f"{br_path}.bak"
        if not blob_exists(backup_path):
            backup_tags = {"dataset": "backtest_ready", "source": "reconcile_scores", "scope": "backup", "updated": stamp}
            write_csv(backup_path, original_br, tags=backup_tags)
            result['backup'] = backup_path

        # Write updated file
        update_tags = {"dataset": "backtest_ready", "source": "reconcile_scores", "scope": "canonicalized", "updated": stamp}
        write_csv(br_path, br, tags=update_tags)
        result['status'] = 'updated'
    else:
        result['status'] = 'dry_run' if dry_run else 'no_changes'

    return result


def reconcile_backtest_complete(
    espn: pd.DataFrame,
    dry_run: bool = True,
) -> Dict:
    """Reconcile backtest_complete.csv with ESPN canonical scores."""
    bc_path = str(DATA_PATHS.backtest_datasets / "backtest_complete.csv")

    if not blob_exists(bc_path):
        print(f"  [SKIP] {bc_path} not found in Azure")
        return {"status": "skipped", "reason": "file not found"}

    # Load backtest_complete
    bc = read_csv(bc_path)
    original_len = len(bc)
    original_bc = bc.copy()

    # Create game key for matching
    bc['game_key'] = (
        bc['game_date'] + '|' +
        bc['home_team'].str.lower() + '|' +
        bc['away_team'].str.lower()
    )

    # Build lookup from ESPN
    espn_scores = {}
    for _, row in espn.iterrows():
        key = row['game_key']
        espn_scores[key] = {
            'home_score': row['home_score'],
            'away_score': row['away_score'],
            'home_h1': row.get('home_h1'),
            'away_h1': row.get('away_h1'),
        }

    # Track changes
    changes = []

    for idx, row in bc.iterrows():
        key = row['game_key']
        if key in espn_scores:
            espn_data = espn_scores[key]

            if pd.notna(espn_data['home_score']):
                if row['home_score'] != espn_data['home_score']:
                    changes.append({
                        'row': idx,
                        'date': row['game_date'],
                        'teams': f"{row['away_team']} @ {row['home_team']}",
                        'field': 'home_score',
                        'old': row['home_score'],
                        'new': espn_data['home_score'],
                    })
                    bc.at[idx, 'home_score'] = espn_data['home_score']

            if pd.notna(espn_data['away_score']):
                if row['away_score'] != espn_data['away_score']:
                    changes.append({
                        'row': idx,
                        'date': row['game_date'],
                        'teams': f"{row['away_team']} @ {row['home_team']}",
                        'field': 'away_score',
                        'old': row['away_score'],
                        'new': espn_data['away_score'],
                    })
                    bc.at[idx, 'away_score'] = espn_data['away_score']

    # Recalculate derived fields
    if changes:
        if 'actual_total' in bc.columns:
            bc['actual_total'] = bc['home_score'] + bc['away_score']
        if 'spread_result' in bc.columns and 'spread' in bc.columns:
            bc['spread_result'] = bc['home_score'] - bc['away_score'] + bc['spread']

    bc = bc.drop(columns=['game_key'])

    result = {
        'file': str(bc_path),
        'original_rows': original_len,
        'changes_count': len(changes),
        'changes': changes[:20],
    }

    if not dry_run and changes:
        stamp = datetime.utcnow().strftime("%Y-%m-%d")
        backup_path = f"{bc_path}.bak"
        if not blob_exists(backup_path):
            backup_tags = {"dataset": "backtest_complete", "source": "reconcile_scores", "scope": "backup", "updated": stamp}
            write_csv(backup_path, original_bc, tags=backup_tags)
            result['backup'] = backup_path

        update_tags = {"dataset": "backtest_complete", "source": "reconcile_scores", "scope": "canonicalized", "updated": stamp}
        write_csv(bc_path, bc, tags=update_tags)
        result['status'] = 'updated'
    else:
        result['status'] = 'dry_run' if dry_run else 'no_changes'

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Reconcile score data using ESPN canonical as source of truth"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to files"
    )
    parser.add_argument(
        "--output-log",
        type=str,
        default=None,
        help="Path to save change log JSON"
    )

    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Error: Must specify either --dry-run or --apply")
        return 1

    dry_run = args.dry_run or not args.apply

    print("=" * 72)
    print("SCORE DATA RECONCILIATION")
    print("=" * 72)
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'APPLY CHANGES'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Load ESPN canonical as source of truth
    print("Loading ESPN canonical scores (source of truth)...")
    espn = load_espn_canonical()
    print(f"  Loaded {len(espn):,} games from ESPN")
    print()

    results = {}

    # Reconcile backtest_ready.csv
    print("-" * 72)
    print(f"Reconciling: {DATA_PATHS.backtest_datasets / 'backtest_ready.csv'}")
    print("-" * 72)
    results['backtest_ready'] = reconcile_backtest_ready(espn, dry_run)

    if results['backtest_ready']['changes_count'] > 0:
        print(f"  Changes needed: {results['backtest_ready']['changes_count']}")
        print("  Sample changes:")
        for change in results['backtest_ready']['changes'][:10]:
            print(f"    {change['date']}: {change['field']} {change['old']} -> {change['new']}")
    else:
        print("  No changes needed")

    print()

    # Reconcile backtest_complete.csv
    print("-" * 72)
    print(f"Reconciling: {DATA_PATHS.backtest_datasets / 'backtest_complete.csv'}")
    print("-" * 72)
    results['backtest_complete'] = reconcile_backtest_complete(espn, dry_run)

    if results['backtest_complete']['changes_count'] > 0:
        print(f"  Changes needed: {results['backtest_complete']['changes_count']}")
        print("  Sample changes:")
        for change in results['backtest_complete']['changes'][:10]:
            print(f"    {change['date']}: {change['field']} {change['old']} -> {change['new']}")
    else:
        print("  No changes needed")

    # Summary
    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    total_changes = sum(r.get('changes_count', 0) for r in results.values())
    print(f"Total changes: {total_changes}")

    if dry_run:
        print("\nTo apply these changes, run:")
        print("  python testing/scripts/reconcile_scores.py --apply")
    else:
        print("\nChanges applied. Backups created with .bak extension.")

    # Save log
    if args.output_log:
        log_path = Path(args.output_log)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        log = {
            'timestamp': datetime.now().isoformat(),
            'mode': 'dry_run' if dry_run else 'apply',
            'results': results,
        }

        with open(log_path, 'w') as f:
            json.dump(log, f, indent=2, default=str)

        print(f"\nChange log saved to: {log_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
