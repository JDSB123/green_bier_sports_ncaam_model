#!/usr/bin/env python3
"""
CLEANUP LEGACY MANUAL FIX SCRIPTS

Removes deprecated manual data fix scripts that have been replaced by
the canonical ingestion pipeline and team resolution service.

Legacy scripts being removed:
- fix_all_aliases.py
- fix_remaining_aliases*.py
- fix_coverage.py
- Other manual fix scripts

These have been replaced by:
- testing/canonical/team_resolution_service.py
- testing/canonical/ingestion_pipeline.py
- testing/canonical/quality_gates.py

Usage:
    python testing/scripts/cleanup_legacy_scripts.py --dry-run  # Preview what will be removed
    python testing/scripts/cleanup_legacy_scripts.py --clean    # Remove the scripts
"""

import argparse
from pathlib import Path
import shutil

# Scripts to remove
LEGACY_SCRIPTS = [
    "fix_all_aliases.py",
    "fix_remaining_aliases.py",
    "fix_remaining_aliases2.py",
    "fix_remaining_aliases3.py",
    "fix_remaining_aliases4.py",
    "fix_remaining_aliases5.py",
    "fix_coverage.py",
    "fix_backtest_data_issues.py",
    "debug_date_matching.py",
    "debug_ncaahoopR_merge.py",
    "diagnose_coverage.py",
    "validate_ncaahoopR_integrity.py",
    "investigate_timezones.py",
    "standardize_dates.py",
    "verify_correct_dates.py",
    "data_ingestion_gate.py"
]

# Scripts to keep but mark as deprecated
DEPRECATED_SCRIPTS = [
    "build_backtest_dataset.py",  # Replaced by build_backtest_dataset_canonical.py
    "score_integrity_audit.py",   # Replaced by canonical_data_validator.py
    "dual_canonicalization_audit.py",  # Replaced by canonical_data_validator.py
    "comprehensive_data_audit.py",     # Replaced by canonical_data_validator.py
]

# Replacement mapping
REPLACEMENT_MAP = {
    "fix_all_aliases.py": "testing/canonical/team_resolution_service.py",
    "fix_remaining_aliases*.py": "testing/canonical/team_resolution_service.py",
    "fix_coverage.py": "testing/canonical/quality_gates.py",
    "build_backtest_dataset.py": "testing/scripts/build_backtest_dataset_canonical.py",
    "score_integrity_audit.py": "testing/scripts/canonical_data_validator.py",
    "dual_canonicalization_audit.py": "testing/scripts/canonical_data_validator.py",
    "comprehensive_data_audit.py": "testing/scripts/canonical_data_validator.py",
}


def find_legacy_scripts(scripts_dir: Path) -> list[Path]:
    """Find legacy scripts to remove."""
    found_scripts = []

    for script_name in LEGACY_SCRIPTS:
        script_path = scripts_dir / script_name
        if script_path.exists():
            found_scripts.append(script_path)

    return found_scripts


def find_deprecated_scripts(scripts_dir: Path) -> list[Path]:
    """Find scripts to deprecate."""
    found_scripts = []

    for script_name in DEPRECATED_SCRIPTS:
        script_path = scripts_dir / script_name
        if script_path.exists():
            found_scripts.append(script_path)

    return found_scripts


def create_deprecation_notice(script_path: Path, replacement: str):
    """Create a deprecation notice file."""
    notice_path = script_path.with_suffix(".deprecated")

    notice_content = f"""# DEPRECATED SCRIPT
#
# This script has been replaced by the canonical ingestion framework.
#
# OLD: {script_path.name}
# NEW: {replacement}
#
# The canonical ingestion pipeline provides:
# - Automatic team name resolution
# - Preventive data quality validation
# - Schema evolution handling
# - Consistent data processing
#
# Please migrate to the new canonical system.
# This script will be removed in a future version.
"""

    with open(notice_path, 'w') as f:
        f.write(notice_content)

    print(f"Created deprecation notice: {notice_path}")


def cleanup_legacy_scripts(dry_run: bool = True, force: bool = False):
    """Clean up legacy manual fix scripts."""

    scripts_dir = Path(__file__).parent
    backup_dir = scripts_dir / "legacy_backup"

    print("=" * 70)
    print("CANONICAL INGESTION - LEGACY SCRIPT CLEANUP")
    print("=" * 70)
    print(f"Scripts directory: {scripts_dir}")
    print(f"Dry run: {dry_run}")
    print()

    # Find scripts
    legacy_scripts = find_legacy_scripts(scripts_dir)
    deprecated_scripts = find_deprecated_scripts(scripts_dir)

    print(f"Found {len(legacy_scripts)} legacy scripts to remove:")
    for script in legacy_scripts:
        print(f"  - {script.name}")

    print(f"\nFound {len(deprecated_scripts)} scripts to deprecate:")
    for script in deprecated_scripts:
        print(f"  - {script.name}")

    if dry_run:
        print("\nDRY RUN - No files will be modified")
        print("\nReplacements:")
        for old, new in REPLACEMENT_MAP.items():
            print(f"  {old} -> {new}")
        return

    if not force:
        confirm = input("\nThis will permanently remove legacy scripts. Continue? (y/N): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return

    # Create backup directory
    if legacy_scripts:
        backup_dir.mkdir(exist_ok=True)
        print(f"\nBacking up to: {backup_dir}")

    # Remove legacy scripts
    for script_path in legacy_scripts:
        print(f"Removing: {script_path.name}")

        if not dry_run:
            # Backup first
            backup_path = backup_dir / script_path.name
            shutil.copy2(script_path, backup_path)

            # Remove original
            script_path.unlink()

    # Deprecate remaining scripts
    for script_path in deprecated_scripts:
        replacement = REPLACEMENT_MAP.get(script_path.name, "canonical ingestion framework")
        print(f"Deprecating: {script_path.name} -> {replacement}")

        if not dry_run:
            create_deprecation_notice(script_path, replacement)

    print("
Cleanup complete!"    if not dry_run else "\nDry run complete - no changes made"
    print(f"Legacy scripts backed up to: {backup_dir}")


def main():
    parser = argparse.ArgumentParser(description="Clean up legacy manual fix scripts")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview what will be removed without making changes")
    parser.add_argument("--clean", action="store_true",
                       help="Actually remove the legacy scripts")
    parser.add_argument("--force", action="store_true",
                       help="Skip confirmation prompt")

    args = parser.parse_args()

    if not args.dry_run and not args.clean:
        args.dry_run = True  # Default to dry run

    cleanup_legacy_scripts(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()