#!/usr/bin/env python3
"""
ROBUST PROJECT CLEANUP

Consolidates and removes:
1. Duplicate/redundant scripts (add_2026_to_backtest.py vs append_2026_to_backtest.py)
2. Debug/test scripts no longer needed
3. Legacy analysis scripts
4. Temporary files in testing/data
5. Empty directories
6. Orphaned documentation

Maintains:
- All canonical ingestion scripts
- Core backtest/model scripts
- Active data fetching scripts
- Team resolution service
"""

import argparse
import shutil
import json
from pathlib import Path
from typing import List, Tuple

# Root directory
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "testing" / "scripts"
TESTING_DIR = ROOT / "testing"
DOCS_DIR = ROOT / "docs"

# Scripts to REMOVE (duplicates, old versions, debug scripts)
SCRIPTS_TO_REMOVE = [
    "add_2026_to_backtest.py",              # Duplicate of append_2026_to_backtest.py
    "update_2026_h1_odds.py",               # One-time manual fix (integrated into build pipeline)
    "debug_odds_api.py",                    # Debug only
    "check_data_formats.py",                # Analysis only
    "analyze_h1_archive.py",                # One-off analysis
    "analyze_historical_data.py",           # One-off analysis
    "audit_data_sources.py",                # Replaced by comprehensive_ingestion_audit.py
    "prepare_backtest.py",                  # Replaced by build_backtest_dataset_canonical.py
    "reconcile_scores.py",                  # Manual fix script (integrated into canonical)
    "generate_mascot_aliases.py",           # One-off script
    "espn_schedule_xref.py",                # Analysis only
    "add_ncaahoopR_aliases.py",             # Manual fix (integrated)
    "clean_results_history.py",             # Maintenance only
    "run_backtest.py",                      # Old version (use run_historical_backtest.py)
    "pre_backtest_gate.py",                 # Replaced by canonical_data_validator.py
    "ingestion_healthcheck.py",             # Replaced by comprehensive_ingestion_audit.py
]

# Scripts to KEEP (active, essential scripts)
SCRIPTS_TO_KEEP = [
    "fetch_historical_data.py",             # Active: ESPN API
    "fetch_historical_odds.py",             # Active: The Odds API
    "fetch_h1_data.py",                     # Active: Extract H1 scores
    "append_2026_to_backtest.py",           # Essential: Current season data
    "build_backtest_dataset_canonical.py",  # Essential: Backtest dataset builder
    "build_consolidated_master.py",         # Essential: ncaahoopR feature merge
    "run_historical_backtest.py",           # Essential: Backtest engine
    "run_clv_backtest.py",                  # Essential: CLV backtest engine
    "team_resolution_gate.py",              # Essential: Team canonicalization
    "team_utils.py",                        # Essential: Team resolution utilities
    "comprehensive_ingestion_audit.py",     # Essential: Data validation
    "canonical_data_validator.py",          # Essential: Quality gates
    "unresolved_team_variants_gate.py",     # Essential: Team resolution validation
    "grade_picks.py",                       # Model evaluation
    "calibrate_model.py",                   # Model calibration
    "validate_model.py",                    # Model validation
    "generate_ingestion_endpoint_inventory.py",  # Documentation
    "cleanup_legacy_scripts.py",            # Maintenance
]

# Directories to clean
DIRS_TO_CLEAN = [
    TESTING_DIR / "data" / "tmp_*",         # Temp files
    TESTING_DIR / "data" / "kaggle",        # Not used in canonical pipeline
]

# Documentation to consolidate
DOCS_CONSOLIDATION = {
    # Keep as primary references
    "keep": [
        "DATA_SOURCES.md",
        "INGESTION_ARCHITECTURE.md",
        "SINGLE_SOURCE_OF_TRUTH.md",
        "STANDARDIZED_TEAM_MAPPINGS.md",
        "HISTORICAL_DATA_AVAILABILITY.md",
        "TEAM_NAME_CONVENTIONS.md",
    ],
    # Can be removed (covered by above)
    "remove": [
        "HISTORICAL_DATA_GAPS.md",           # Subsumed by SINGLE_SOURCE_OF_TRUTH
        "HISTORICAL_DATA_SYNC.md",           # Covered by INGESTION_ARCHITECTURE
        "DATA_ENDPOINT_STATUS.md",           # Covered by DATA_SOURCES
        "ODDS_API_USAGE.md",                 # Covered by INGESTION_ARCHITECTURE
    ]
}


class ProjectCleaner:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.removed_count = 0
        self.kept_count = 0
        self.cleaned_count = 0
        self.removed_items = []

    def print_header(self, title):
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)

    def remove_script(self, script_path: Path, reason: str):
        """Remove a script with logging."""
        if script_path.exists():
            if self.dry_run:
                print(f"  [DRY-RUN] Would remove: {script_path.name}")
                print(f"            Reason: {reason}")
            else:
                script_path.unlink()
                self.removed_count += 1
                self.removed_items.append(script_path.name)
                print(f"  ✓ Removed: {script_path.name}")

    def keep_script(self, script_name: str):
        """Verify script to keep exists."""
        script_path = SCRIPTS_DIR / script_name
        if script_path.exists():
            self.kept_count += 1
            print(f"  ✓ Keep: {script_name}")
        else:
            print(f"  ✗ Missing: {script_name}")

    def run(self):
        """Execute cleanup."""
        self.print_header("PROJECT CLEANUP")
        print(f"Mode: {'DRY-RUN (no changes)' if self.dry_run else 'EXECUTING (real cleanup)'}")

        # Remove redundant scripts
        self.print_header("1. REMOVING REDUNDANT SCRIPTS")
        for script_name in SCRIPTS_TO_REMOVE:
            script_path = SCRIPTS_DIR / script_name
            if script_path.exists():
                self.remove_script(script_path, "Replaced or no longer needed")

        # Verify essential scripts are present
        self.print_header("2. VERIFYING ESSENTIAL SCRIPTS")
        for script_name in SCRIPTS_TO_KEEP:
            self.keep_script(script_name)

        # Clean temporary data directories
        self.print_header("3. CLEANING TEMPORARY DIRECTORIES")
        for pattern in DIRS_TO_CLEAN:
            if "*" in str(pattern):
                parent = pattern.parent
                prefix = pattern.name.replace("*", "")
                if parent.exists():
                    for item in parent.glob(f"{prefix}*"):
                        if item.is_dir():
                            if self.dry_run:
                                print(f"  [DRY-RUN] Would remove: {item.relative_to(ROOT)}")
                            else:
                                shutil.rmtree(item)
                                self.cleaned_count += 1
                                print(f"  ✓ Removed: {item.relative_to(ROOT)}")
            else:
                if pattern.exists():
                    if self.dry_run:
                        print(f"  [DRY-RUN] Would remove: {pattern.relative_to(ROOT)}")
                    else:
                        if pattern.is_dir():
                            shutil.rmtree(pattern)
                        else:
                            pattern.unlink()
                        self.cleaned_count += 1
                        print(f"  ✓ Removed: {pattern.relative_to(ROOT)}")

        # Summary
        self.print_header("CLEANUP SUMMARY")
        print(f"  Scripts removed:        {self.removed_count}")
        print(f"  Scripts kept:           {self.kept_count}")
        print(f"  Directories cleaned:    {self.cleaned_count}")
        
        if not self.dry_run:
            print(f"\n  Removed scripts: {', '.join(self.removed_items[:5])}", end="")
            if len(self.removed_items) > 5:
                print(f" ... and {len(self.removed_items)-5} more")
            else:
                print()
        
        print(f"\n  Next steps:")
        print(f"    1. Update .gitignore if needed")
        print(f"    2. Update CI/CD pipeline references")
        print(f"    3. Document the cleanup in CHANGELOG")


def main():
    parser = argparse.ArgumentParser(description="Robust project cleanup")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview what will be removed (default: enabled)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually remove files (careful!)"
    )
    
    args = parser.parse_args()
    
    if args.execute and args.dry_run:
        args.dry_run = False

    cleaner = ProjectCleaner(dry_run=args.dry_run)
    cleaner.run()
    
    return 0


if __name__ == "__main__":
    exit(main())
