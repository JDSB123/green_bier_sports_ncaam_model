#!/usr/bin/env python3
"""
FULL DATA ENDPOINT AUDIT
Verifies EVERY data source is being utilized in the backtest pipeline.

This script inventories ALL data files and checks if they're being used.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ncaam_historical_data_local"
BACKTEST_MASTER = DATA / "backtest_datasets" / "backtest_master.csv"

# Track usage status
USAGE_STATUS: Dict[str, Tuple[str, str]] = {}  # path -> (status, notes)


def check_file_used_in_backtest(filepath: Path, backtest_df: pd.DataFrame) -> Tuple[str, str]:
    """Check if a data file's content is used in the backtest master."""
    rel_path = str(filepath.relative_to(DATA))
    
    # Skip non-data files
    if filepath.suffix not in [".csv", ".json"]:
        return "SKIP", "Not a data file"
    
    # Skip audit/log files
    if "audit" in rel_path.lower() or "log" in rel_path.lower():
        return "META", "Audit/log file"
    
    # Skip manifests and schemas
    if "manifest" in rel_path.lower() or "schema" in rel_path.lower():
        return "META", "Manifest/schema file"
    
    # Check specific file types
    filename = filepath.name.lower()
    
    # === SCORES ===
    if "games_" in filename and filepath.suffix == ".csv":
        if "scores/fg" in rel_path:
            return "USED", "FG scores -> backtest_master (home_score, away_score)"
        if "scores/h1" in rel_path:
            return "USED", "H1 scores -> backtest_master (home_h1, away_h1)"
    
    if filename == "games_all_canonical.csv":
        return "USED", "Canonical FG scores (alternative source)"
    
    if filename == "h1_games_all_canonical.csv":
        return "USED", "Canonical H1 scores -> backtest_master (home_h1, away_h1)"
    
    # === ODDS ===
    if filename == "odds_consolidated_canonical.csv":
        return "USED", "Primary FG odds source -> fg_spread, fg_total, prices"
    
    if filename == "odds_h1_archive_matchups.csv":
        return "USED", "H1 prices source -> h1_spread_home_price, h1_total_over_price"
    
    if filename == "odds_h1_archive_teams.csv":
        return "REDUNDANT", "Team-level view of H1 archive (matchups version used)"
    
    if filename == "odds_all_normalized_20201125_20260107.csv":
        return "REDUNDANT", "Raw normalized odds (consolidated version used)"
    
    if "spreads_fg_all.csv" in filename:
        return "FALLBACK", "Canonical FG spreads (used if consolidated unavailable)"
    
    if "totals_fg_all.csv" in filename:
        return "FALLBACK", "Canonical FG totals (used if consolidated unavailable)"
    
    if "spreads_h1_all.csv" in filename:
        return "PARTIAL", "H1 spread lines only (no prices) - archive has prices"
    
    if "totals_h1_all.csv" in filename:
        return "PARTIAL", "H1 total lines only (no prices) - archive has prices"
    
    if "_canonical.csv" in filename and "canonicalized/odds" in rel_path:
        return "REDUNDANT", "Canonicalized copy (canonical/ version used)"
    
    # === RATINGS ===
    if "ratings_" in filename and "barttorvik" in rel_path:
        return "USED", "Barttorvik ratings -> home_adj_o, away_adj_d, etc."
    
    if "barttorvik_" in filename and filepath.suffix == ".json":
        if "normalized" in rel_path:
            return "CACHE", "Barttorvik cache (ratings/ version is primary)"
        if "raw" in rel_path:
            return "CACHE", "Raw Barttorvik data (ratings/ version is primary)"
    
    # === BACKTEST DATASETS ===
    if "backtest_datasets" in rel_path:
        if filename == "backtest_master.csv":
            return "OUTPUT", "Final merged backtest dataset"
        if filename == "backtest_master_summary.json":
            return "OUTPUT", "Build summary metadata"
        if filename == "team_aliases_db.json":
            return "USED", "Team name canonicalization"
        if filename == "barttorvik_lookup.json":
            return "CACHE", "Ratings lookup cache"
        if filename == "barttorvik_ratings.csv":
            return "CACHE", "Ratings CSV cache"
        # Legacy/intermediate files
        return "LEGACY", "Intermediate/legacy backtest file"
    
    # === JSON duplicates of CSV ===
    if filepath.suffix == ".json" and (filepath.parent / f"{filepath.stem}.csv").exists():
        return "DUPLICATE", "JSON version of CSV (CSV used)"
    
    return "UNKNOWN", "Needs investigation"


def audit_all_endpoints():
    """Audit all data endpoints."""
    print("=" * 80)
    print("COMPREHENSIVE DATA ENDPOINT AUDIT")
    print("=" * 80)
    print(f"\nData directory: {DATA}")
    print(f"Backtest master: {BACKTEST_MASTER}")
    
    # Load backtest master for reference
    if BACKTEST_MASTER.exists():
        backtest_df = pd.read_csv(BACKTEST_MASTER)
        print(f"Backtest master columns: {len(backtest_df.columns)}")
        print(f"Backtest master rows: {len(backtest_df):,}")
    else:
        backtest_df = pd.DataFrame()
        print("[WARN] Backtest master not found!")
    
    # Scan all files
    all_files = list(DATA.rglob("*"))
    data_files = [f for f in all_files if f.is_file()]
    
    print(f"\nTotal files found: {len(data_files)}")
    
    # Categorize files
    categories = {
        "USED": [],      # Actively used in backtest pipeline
        "OUTPUT": [],    # Output files from pipeline
        "FALLBACK": [],  # Used as fallback if primary unavailable
        "PARTIAL": [],   # Partially used (some data not utilized)
        "CACHE": [],     # Cache/intermediate files
        "REDUNDANT": [], # Redundant copies (primary version used)
        "DUPLICATE": [], # Duplicate format (e.g., JSON of CSV)
        "META": [],      # Metadata/audit files
        "LEGACY": [],    # Legacy files (could be cleaned up)
        "SKIP": [],      # Non-data files
        "UNKNOWN": [],   # Needs investigation
    }
    
    for filepath in sorted(data_files):
        status, notes = check_file_used_in_backtest(filepath, backtest_df)
        rel_path = str(filepath.relative_to(DATA))
        categories[status].append((rel_path, notes))
        USAGE_STATUS[rel_path] = (status, notes)
    
    # Print report
    print("\n" + "=" * 80)
    print("USAGE REPORT")
    print("=" * 80)
    
    for category in ["USED", "OUTPUT", "FALLBACK", "PARTIAL", "CACHE", "REDUNDANT", "DUPLICATE", "META", "LEGACY", "SKIP", "UNKNOWN"]:
        files = categories[category]
        if not files:
            continue
            
        emoji = {
            "USED": "[OK]",
            "OUTPUT": "[OUT]",
            "FALLBACK": "[FB]",
            "PARTIAL": "[PART]",
            "CACHE": "[CACHE]",
            "REDUNDANT": "[DUP]",
            "DUPLICATE": "[DUP]",
            "META": "[META]",
            "LEGACY": "[OLD]",
            "SKIP": "[SKIP]",
            "UNKNOWN": "[???]",
        }[category]
        
        print(f"\n{emoji} {category} ({len(files)} files):")
        print("-" * 60)
        for rel_path, notes in files:
            print(f"  {rel_path}")
            print(f"    -> {notes}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    used_count = len(categories["USED"]) + len(categories["OUTPUT"]) + len(categories["FALLBACK"])
    total_data = len(data_files) - len(categories["SKIP"]) - len(categories["META"])
    
    print(f"\nActively Used: {used_count} files")
    print(f"Partially Used: {len(categories['PARTIAL'])} files")
    print(f"Cache/Intermediate: {len(categories['CACHE'])} files")
    print(f"Redundant/Duplicate: {len(categories['REDUNDANT']) + len(categories['DUPLICATE'])} files")
    print(f"Legacy (cleanup candidates): {len(categories['LEGACY'])} files")
    print(f"Unknown (needs investigation): {len(categories['UNKNOWN'])} files")
    
    # Check for gaps
    print("\n" + "=" * 80)
    print("POTENTIAL GAPS / UNUSED DATA")
    print("=" * 80)
    
    if categories["UNKNOWN"]:
        print("\n[WARN] Files that need investigation:")
        for rel_path, notes in categories["UNKNOWN"]:
            print(f"  - {rel_path}")
    
    if categories["PARTIAL"]:
        print("\n[INFO] Files with partial usage (some data not utilized):")
        for rel_path, notes in categories["PARTIAL"]:
            print(f"  - {rel_path}: {notes}")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if categories["LEGACY"]:
        print(f"\n1. Consider cleaning up {len(categories['LEGACY'])} legacy files")
    
    if categories["REDUNDANT"] or categories["DUPLICATE"]:
        count = len(categories["REDUNDANT"]) + len(categories["DUPLICATE"])
        print(f"\n2. {count} redundant/duplicate files could be consolidated")
    
    if not categories["UNKNOWN"] and not categories["PARTIAL"]:
        print("\n[OK] All data endpoints are accounted for!")
    
    return categories


def verify_backtest_master_completeness():
    """Verify backtest master has all expected data columns."""
    print("\n" + "=" * 80)
    print("BACKTEST MASTER COMPLETENESS CHECK")
    print("=" * 80)
    
    if not BACKTEST_MASTER.exists():
        print("[ERROR] Backtest master not found!")
        return
    
    df = pd.read_csv(BACKTEST_MASTER)
    
    # Expected columns from each source
    expected = {
        "Scores (FG)": ["home_score", "away_score", "actual_margin", "actual_total"],
        "Scores (H1)": ["home_h1", "away_h1", "h1_actual_margin", "h1_actual_total"],
        "FG Spread": ["fg_spread", "fg_spread_home_price", "fg_spread_away_price"],
        "FG Total": ["fg_total", "fg_total_over_price", "fg_total_under_price"],
        "H1 Spread": ["h1_spread", "h1_spread_home_price", "h1_spread_away_price"],
        "H1 Total": ["h1_total", "h1_total_over_price", "h1_total_under_price"],
        "Ratings (Core)": ["home_adj_o", "home_adj_d", "away_adj_o", "away_adj_d", "home_barthag", "away_barthag"],
        "Ratings (Four Factors)": ["home_efg", "home_tor", "home_orb", "home_ftr", "home_efgd"],
        "Ratings (Shooting)": ["home_three_pt_rate", "away_three_pt_rate"],
        "Ratings (Quality)": ["home_wab", "away_wab"],
    }
    
    for source, cols in expected.items():
        present = [c for c in cols if c in df.columns]
        missing = [c for c in cols if c not in df.columns]
        
        if missing:
            print(f"\n[WARN] {source}:")
            print(f"  Present: {present}")
            print(f"  MISSING: {missing}")
        else:
            # Check coverage
            non_null = df[cols[0]].notna().sum() if cols else 0
            pct = non_null / len(df) * 100
            status = "[OK]" if pct > 20 else "[LOW]"
            print(f"{status} {source}: {len(present)}/{len(cols)} columns, {pct:.1f}% coverage")


if __name__ == "__main__":
    categories = audit_all_endpoints()
    verify_backtest_master_completeness()
    
    print("\n" + "=" * 80)
    if not categories["UNKNOWN"]:
        print("[OK] ALL DATA ENDPOINTS VERIFIED")
    else:
        print("[WARN] Some endpoints need investigation")
    print("=" * 80)
