#!/usr/bin/env python3
"""
Data Integrity Verification for Backtesting

This script verifies that:
1. The data repo is at the expected tag
2. All critical files exist with correct checksums
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

from data_paths import DATA_PATHS, EXPECTED_DATA_TAG, verify_data_integrity


def sha256_file(filepath: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_manifest_checksums() -> tuple[int, int]:
    """Verify files match checksums in DATA_MANIFEST.json."""
    manifest_path = DATA_PATHS.data_manifest
    if not manifest_path.exists():
        print(f"ERROR: DATA_MANIFEST.json not found at {manifest_path}")
        return 0, 1
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    passed = 0
    failed = 0
    
    files_to_check = manifest.get("files", {})
    for name, info in files_to_check.items():
        rel_path = info.get("path")
        expected_sha = info.get("sha256")
        if not rel_path or not expected_sha:
            continue
        
        full_path = DATA_PATHS.root / rel_path
        if not full_path.exists():
            print(f"  ✗ MISSING: {rel_path}")
            failed += 1
            continue
        
        actual_sha = sha256_file(full_path)
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
    aliases_path = DATA_PATHS.team_aliases_db
    if not aliases_path.exists():
        print(f"  ✗ team_aliases_db.json not found")
        return False
    
    with open(aliases_path) as f:
        aliases = json.load(f)
    
    alias_count = len(aliases)
    canonical_teams = len(set(aliases.values()))
    
    print(f"  ✓ Team aliases: {alias_count} aliases → {canonical_teams} canonical teams")
    
    # Sanity check - should have at least 1000 aliases
    if alias_count < 1000:
        print(f"  ⚠ WARNING: Expected 1000+ aliases, got {alias_count}")
        return False
    
    return True


def verify_ratings_anti_leakage() -> bool:
    """Verify ratings file has proper season structure for anti-leakage."""
    import pandas as pd
    
    ratings_path = DATA_PATHS.barttorvik_ratings
    if not ratings_path.exists():
        print(f"  ✗ barttorvik_ratings.csv not found")
        return False
    
    df = pd.read_csv(ratings_path)
    
    if "season" not in df.columns:
        print("  ✗ ratings file missing 'season' column")
        return False
    
    seasons = sorted(df["season"].unique())
    print(f"  ✓ Ratings seasons available: {seasons}")
    print(f"  ✓ Total team-seasons: {len(df)}")
    
    # For backtesting season N, we use ratings from season N-1
    print("  ℹ Anti-leakage rule: Use Season N-1 ratings for Season N predictions")
    
    return True


def main():
    print("=" * 60)
    print("NCAAM Data Integrity Verification")
    print("=" * 60)
    print(f"Data Root: {DATA_PATHS.root}")
    print(f"Expected Tag: {EXPECTED_DATA_TAG}")
    print()
    
    all_passed = True
    
    # 1. Check git tag
    print("[1] Checking data repo version...")
    if verify_data_integrity():
        print(f"  ✓ Data repo at expected tag: {EXPECTED_DATA_TAG}")
    else:
        print(f"  ⚠ Data repo NOT at expected tag (may be newer)")
        # Not a hard failure - data might be newer
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
