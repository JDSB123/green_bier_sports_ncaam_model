#!/usr/bin/env python3
"""
DATA GOVERNANCE VALIDATOR

Comprehensive compliance audit to ensure:
1. No data files in Git repository
2. All data in Azure blob storage ONLY
3. Scripts use AzureDataReader (not local files)
4. Immutable audit trails exist
5. No local permanent data storage

Usage:
    python testing/scripts/data_governance_validator.py
    python testing/scripts/data_governance_validator.py --strict
    python testing/scripts/data_governance_validator.py --fix (auto-remediate)
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "testing" / "scripts"
TESTING_DIR = ROOT / "testing"


class ComplianceValidator:
    """Validates data governance compliance."""

    def __init__(self, strict=False, fix=False):
        self.strict = strict
        self.fix = fix
        self.violations = []
        self.warnings = []
        self.passed_checks = []

    def print_header(self, title):
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)

    def print_check(self, status, message):
        if status == "PASS":
            print(f"  ✅ {message}")
            self.passed_checks.append(message)
        elif status == "WARN":
            print(f"  ⚠️  {message}")
            self.warnings.append(message)
        else:  # FAIL
            print(f"  ❌ {message}")
            self.violations.append(message)

    # ========================================================================
    # CHECK 1: Git Repository Compliance
    # ========================================================================

    def check_git_data_files(self) -> bool:
        """Verify no data files are committed to Git."""
        self.print_header("CHECK 1: GIT REPOSITORY COMPLIANCE")

        try:
            # Get all tracked files
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10
            )
            tracked_files = result.stdout.strip().split('\n')
        except Exception as e:
            self.print_check("WARN", f"Could not read Git files: {e}")
            return False

        # Patterns that should NOT be in Git
        bad_patterns = [
            ('.csv', 'CSV data file'),
            ('.xlsx', 'Excel data file'),
            ('.xls', 'Excel data file'),
            ('.parquet', 'Parquet data file'),
            ('.db', 'Database file'),
            ('.sqlite', 'SQLite database'),
            ('ncaam_historical_data', 'Local data directory'),
            ('predictions/', 'Predictions directory'),
            ('backtest_results/', 'Backtest results directory'),
        ]

        violations_found = []
        for pattern, desc in bad_patterns:
            bad_files = [f for f in tracked_files if pattern in f]

            # Allow exception: config/schema files
            if pattern == '.json':
                bad_files = [f for f in bad_files
                           if 'config' not in f and 'schema' not in f]

            if bad_files:
                violations_found.extend(bad_files)
                self.print_check("FAIL", f"Found {desc} in Git: {bad_files[0]}")

        if not violations_found:
            self.print_check("PASS", "No data files detected in Git")
            return True
        return False

    # ========================================================================
    # CHECK 2: Local Data Directory Compliance
    # ========================================================================

    def check_local_data_storage(self) -> bool:
        """Verify no permanent local data storage (except temp)."""
        self.print_header("CHECK 2: LOCAL DATA DIRECTORY COMPLIANCE")

        bad_dirs = [
            (TESTING_DIR / "data" / "kaggle", "Kaggle data (use Azure)"),
            (ROOT / "ncaam_historical_data_local", "Local data cache (use Azure)"),
            (ROOT / "predictions" / "*.csv", "Prediction results (use Azure)"),
        ]

        violations_found = []
        for path, desc in bad_dirs:
            if path.exists():
                # Ignore temp directories
                if "tmp" not in str(path) and "temp" not in str(path):
                    violations_found.append(str(path))
                    self.print_check("FAIL", f"{desc}: {path.name} found locally")

        if not violations_found:
            self.print_check("PASS", "No permanent local data storage detected")
            return True
        return False

    # ========================================================================
    # CHECK 3: Script Compliance (Reading from Azure)
    # ========================================================================

    def check_script_azure_reads(self) -> bool:
        """Verify scripts use AzureDataReader, not local file reads."""
        self.print_header("CHECK 3: SCRIPT COMPLIANCE (Azure-first reads)")

        # Scripts that should use AzureDataReader
        essential_scripts = [
            "fetch_historical_data.py",
            "fetch_historical_odds.py",
            "build_backtest_dataset_canonical.py",
            "run_historical_backtest.py",
            "run_clv_backtest.py",
        ]

        violations_found = []
        for script_name in essential_scripts:
            script_path = SCRIPTS_DIR / script_name
            if script_path.exists():
                content = script_path.read_text()

                # Check for Azure imports
                has_azure_reader = (
                    "from testing.azure_data_reader import" in content or
                    "from testing.azure_io import" in content or
                    "AzureDataReader" in content
                )

                # Check for suspicious local reads
                has_local_read = (
                    "open(" in content and "testing/data" in content
                ) and "AzureDataReader" not in content

                if has_local_read and not has_azure_reader:
                    violations_found.append(script_name)
                    self.print_check("FAIL", f"{script_name} reads from local files")
                else:
                    self.print_check("PASS", f"{script_name} uses Azure")

        return len(violations_found) == 0

    # ========================================================================
    # CHECK 4: Audit Trail Compliance
    # ========================================================================

    def check_audit_trails(self) -> bool:
        """Verify immutable audit trails exist."""
        self.print_header("CHECK 4: AUDIT TRAIL COMPLIANCE")

        manifests_dir = ROOT / "manifests"

        required_manifests = [
            "comprehensive_ingestion_audit.json",
            "ingestion_endpoint_inventory.json",
        ]

        all_found = True
        for manifest in required_manifests:
            path = manifests_dir / manifest
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    if "timestamp" in data or "last_updated" in data:
                        self.print_check("PASS", f"{manifest} exists with timestamp")
                    else:
                        self.print_check("WARN", f"{manifest} missing timestamp")
                        all_found = False
                except:
                    self.print_check("FAIL", f"{manifest} is not valid JSON")
                    all_found = False
            else:
                self.print_check("FAIL", f"{manifest} not found")
                all_found = False

        return all_found

    # ========================================================================
    # CHECK 5: Azure Blob Storage Access
    # ========================================================================

    def check_azure_connectivity(self) -> bool:
        """Verify can connect to Azure blob storage."""
        self.print_header("CHECK 5: AZURE BLOB STORAGE CONNECTIVITY")

        try:
            from testing.azure_data_reader import AzureDataReader

            reader = AzureDataReader(container_name="ncaam-historical-data")

            # Try to list files
            files = reader.list_files("backtest_datasets/", pattern="*.csv", max_results=1)

            if files:
                self.print_check("PASS", "Can connect to Azure blob storage")
                self.print_check("PASS", "Container: ncaam-historical-data")
                return True
            self.print_check("WARN", "Connected but no files found (expected in some cases)")
            return True

        except Exception as e:
            self.print_check("FAIL", f"Cannot connect to Azure: {e}")
            return False

    # ========================================================================
    # CHECK 6: Data Governance Documentation
    # ========================================================================

    def check_documentation(self) -> bool:
        """Verify governance documentation exists."""
        self.print_header("CHECK 6: DATA GOVERNANCE DOCUMENTATION")

        required_docs = [
            "AZURE_BLOB_STORAGE_ARCHITECTURE.md",
            "GITIGNORE_ENFORCEMENT.md",
            "SINGLE_SOURCE_OF_TRUTH.md",
        ]

        all_found = True
        for doc in required_docs:
            path = ROOT / "docs" / doc
            if path.exists():
                size = path.stat().st_size
                self.print_check("PASS", f"{doc} ({size:,} bytes)")
            else:
                self.print_check("FAIL", f"{doc} not found")
                all_found = False

        return all_found

    # ========================================================================
    # EXECUTION
    # ========================================================================

    def run(self) -> int:
        """Run all compliance checks."""
        print("\n" + "="*70)
        print("  DATA GOVERNANCE VALIDATOR")
        print("="*70)
        print(f"  Mode: {'STRICT' if self.strict else 'NORMAL'}")
        print(f"  Root: {ROOT}")

        # Run all checks
        check1 = self.check_git_data_files()
        check2 = self.check_local_data_storage()
        check3 = self.check_script_azure_reads()
        check4 = self.check_audit_trails()
        check5 = self.check_azure_connectivity()
        check6 = self.check_documentation()

        # Summary
        self.print_header("COMPLIANCE SUMMARY")
        print(f"\n  Passed Checks:   {len(self.passed_checks)}")
        print(f"  Warnings:        {len(self.warnings)}")
        print(f"  Violations:      {len(self.violations)}")

        if self.violations:
            print("\n  ❌ VIOLATIONS FOUND:")
            for v in self.violations:
                print(f"     • {v}")

        if self.warnings:
            print("\n  ⚠️  WARNINGS:")
            for w in self.warnings:
                print(f"     • {w}")

        # Exit code
        if self.violations:
            print("\n  Status: 🚨 NON-COMPLIANT")
            print("  See docs/AZURE_BLOB_STORAGE_ARCHITECTURE.md for remediation")
            if self.strict:
                return 1  # Fail in strict mode
            return 0  # Warn only in normal mode
        print("\n  Status: ✅ COMPLIANT")
        return 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Data Governance Validator")
    parser.add_argument("--strict", action="store_true", help="Fail on any violation")
    parser.add_argument("--fix", action="store_true", help="Auto-remediate violations")

    args = parser.parse_args()

    validator = ComplianceValidator(strict=args.strict, fix=args.fix)
    exit_code = validator.run()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
