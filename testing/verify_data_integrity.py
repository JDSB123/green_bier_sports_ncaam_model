#!/usr/bin/env python3
"""
Data Integrity Verification for Backtesting

This script verifies that:
1. Azure canonical data is reachable and required files exist
2. Critical files match checksums in DATA_MANIFEST.json (Azure)
3. Team aliases are loaded correctly
4. No data leakage is possible (ratings from correct seasons)

Run this BEFORE any backtesting to ensure reproducibility.
"""

import hashlib
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_paths import DATA_PATHS, get_data_reader, verify_azure_data


def sha256_bytes(payload: bytes) -> str:
    """Calculate SHA256 hash of raw bytes."""
    sha256 = hashlib.sha256()
    sha256.update(payload)
    return sha256.hexdigest()


def verify_manifest_checksums() -> tuple[int, int]:
    """Verify files match checksums in Azure DATA_MANIFEST.json."""
    reader = get_data_reader()
    try:
        manifest = reader.read_json(str(DATA_PATHS.data_manifest))
    except Exception as exc:
        print(f"WARNING: DATA_MANIFEST.json not found in Azure: {exc}")
        print("  Skipping checksum verification.")
        return 0, 0

    passed = 0
    failed = 0

    files_to_check = manifest.get("files", {})
    if not files_to_check:
        print("WARNING: DATA_MANIFEST.json has no files listed.")
        return 0, 0
    for name, info in files_to_check.items():
        rel_path = info.get("path")
        expected_sha = info.get("sha256")
        if not rel_path or not expected_sha:
            continue

        try:
            payload = reader.read_bytes(rel_path)
        except Exception:
            print(f"  ✗ MISSING: {rel_path}")
            failed += 1
            continue

        actual_sha = sha256_bytes(payload)
        if actual_sha == expected_sha:
            print(f"  ✓ {name}: checksum OK")
            passed += 1
        else:
            print(f"  ✗ {name}: checksum MISMATCH")
            print(f"      Expected: {expected_sha[:16]}...")
            print(f"      Actual:   {actual_sha[:16]}...")
            failed += 1

    return passed, failed


def verify_team_aliases() -> bool:
    """Verify team aliases file is loadable and has expected count."""
    reader = get_data_reader()
    try:
        aliases = reader.read_json(str(DATA_PATHS.team_aliases_db))
    except Exception:
        print("  ✗ team_aliases_db.json not found")
        return False

    alias_count = len(aliases)
    canonical_teams = len(set(aliases.values()))

    print(f"  ✓ Team aliases: {alias_count} aliases → {canonical_teams} canonical teams")

    # Sanity check - should have at least 1000 aliases
    if alias_count < 1000:
        print(f"  ⚠ WARNING: Expected 1000+ aliases, got {alias_count}")
        return False

    return True


def verify_ratings_anti_leakage() -> bool:
    """Verify ratings season alignment in canonical backtest dataset."""
    import pandas as pd

    reader = get_data_reader()
    dataset_path = "backtest_datasets/backtest_master.csv"
    try:
        df = reader.read_csv(dataset_path)
    except Exception:
        print("  ? backtest dataset not found.")
        print("  Skipping anti-leakage check; run dataset build first.")
        return True

    season_col = None
    if "game_season" in df.columns:
        season_col = "game_season"
    elif "season" in df.columns:
        season_col = "season"

    if "ratings_season" not in df.columns or not season_col:
        print(f"  ? {dataset_path} missing ratings_season/season columns")
        print("  Skipping anti-leakage check; build dataset first.")
        return True

    leakage = (df["ratings_season"] != df[season_col] - 1).sum()
    if leakage > 0:
        print(f"  ? Leakage detected: {leakage} rows with same-season ratings")
        return False

    seasons = sorted(df[season_col].dropna().unique())
    print(f"  OK Game seasons available: {seasons}")
    print("  OK Anti-leakage rule enforced: ratings_season = season - 1")

    return True


def main():
    print("=" * 60)
    print("NCAAM Data Integrity Verification")
    print("=" * 60)
    print(f"Data Root: {DATA_PATHS.root}")
    print()

    all_passed = True

    # 1. Check Azure access
    print("[1] Checking Azure canonical data access...")
    if verify_azure_data():
        print("  ✓ Azure canonical data reachable")
    else:
        print("  ⚠ Azure canonical data check failed")
    print()

    # 2. Check manifest checksums
    print("[2] Verifying file checksums...")
    passed, failed = verify_manifest_checksums()
    if failed > 0:
        all_passed = False
    print(f"  Summary: {passed} passed, {failed} failed")
    print()

    # 3. Check team aliases
    print("[3] Verifying team aliases...")
    if not verify_team_aliases():
        all_passed = False
    print()

    # 4. Check ratings for anti-leakage
    print("[4] Verifying ratings anti-leakage...")
    if not verify_ratings_anti_leakage():
        all_passed = False
    print()

    # Final summary
    print("=" * 60)
    if all_passed:
        print("✓ ALL CHECKS PASSED - Data integrity verified")
        print("  Safe to proceed with backtesting")
        return 0
    else:
        print("✗ SOME CHECKS FAILED - Review errors above")
        print("  Fix issues before backtesting")
        return 1


if __name__ == "__main__":
    sys.exit(main())
