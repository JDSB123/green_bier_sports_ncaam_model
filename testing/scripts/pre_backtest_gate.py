#!/usr/bin/env python3
"""
PRE-BACKTEST VALIDATION GATE

Runs ALL data quality audits and blocks backtest execution if any fail.
This is the local equivalent of the GitHub Actions pre-backtest-validation.yml workflow.

AUDITS PERFORMED:
1. Score Integrity Audit - Cross-validates scores across sources
2. Dual Canonicalization Audit - Verifies team name resolution consistency
3. Cross-Source Coverage Validation - Checks games have odds/ratings/H1 data
4. Canonical Manifest Generation - Creates reproducibility manifest

EXIT CODES:
- 0: All audits passed, backtest is approved
- 1: One or more audits failed, backtest blocked

Usage:
    # Run all audits
    python testing/scripts/pre_backtest_gate.py
    
    # Run with verbose output
    python testing/scripts/pre_backtest_gate.py --verbose
    
    # Skip coverage validation (faster)
    python testing/scripts/pre_backtest_gate.py --skip-coverage
    
    # Generate manifest snapshot
    python testing/scripts/pre_backtest_gate.py --create-snapshot
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def run_audit(name: str, command: list, verbose: bool = False) -> bool:
    """Run an audit script and return success status."""
    print(f"\n{'='*70}")
    print(f"{Colors.BOLD}{name}{Colors.END}")
    print('='*70)
    
    try:
        result = subprocess.run(
            command,
            capture_output=not verbose,
            text=True,
            timeout=300,  # 5 minute timeout per audit
        )
        
        if result.returncode == 0:
            print(f"{Colors.GREEN}[PASS] {name}: PASSED{Colors.END}")
            return True
        else:
            print(f"{Colors.RED}[FAIL] {name}: FAILED{Colors.END}")
            if not verbose and result.stdout:
                print("\nOutput:")
                # Print last 50 lines
                lines = result.stdout.strip().split('\n')
                for line in lines[-50:]:
                    print(f"  {line}")
            if not verbose and result.stderr:
                print("\nErrors:")
                for line in result.stderr.strip().split('\n')[-20:]:
                    print(f"  {line}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}[FAIL] {name}: TIMEOUT (>5 minutes){Colors.END}")
        return False
    except FileNotFoundError:
        print(f"{Colors.RED}[FAIL] {name}: Script not found{Colors.END}")
        return False
    except Exception as e:
        print(f"{Colors.RED}[FAIL] {name}: ERROR - {e}{Colors.END}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Pre-backtest validation gate - runs all data quality audits"
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show full output from each audit")
    parser.add_argument("--skip-coverage", action="store_true",
                        help="Skip cross-source coverage validation")
    parser.add_argument("--skip-manifest", action="store_true",
                        help="Skip manifest generation")
    parser.add_argument("--create-snapshot", action="store_true",
                        help="Create versioned snapshot after audits pass")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Stop on first failure")
    args = parser.parse_args()
    
    # Get paths
    root_dir = Path(__file__).resolve().parents[2]
    scripts_dir = root_dir / "testing" / "scripts"
    
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}PRE-BACKTEST VALIDATION GATE{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Root: {root_dir}")
    
    results = {}
    all_passed = True
    
    # 1. Canonical Scores Validation (Azure-only)
    passed = run_audit(
        "Canonical Scores Validation",
        [
            sys.executable,
            str(scripts_dir / "canonical_data_validator.py"),
            "--data-type",
            "scores",
        ],
        args.verbose
    )
    results["score_integrity"] = passed
    if not passed:
        all_passed = False
        if args.fail_fast:
            print(f"\n{Colors.RED}Stopping due to --fail-fast{Colors.END}")
            sys.exit(1)
    
    # 2. Dual Canonicalization Audit
    passed = run_audit(
        "Dual Canonicalization Audit",
        [sys.executable, str(scripts_dir / "dual_canonicalization_audit.py")],
        args.verbose
    )
    results["canonicalization"] = passed
    if not passed:
        all_passed = False
        if args.fail_fast:
            print(f"\n{Colors.RED}Stopping due to --fail-fast{Colors.END}")
            sys.exit(1)
    
    # 3. Cross-Source Coverage Validation
    if not args.skip_coverage:
        passed = run_audit(
            "Cross-Source Coverage Validation",
            [
                sys.executable, 
                str(scripts_dir / "validate_cross_source_coverage.py"),
                "--output-json", "manifests/coverage_gaps.json",
                "--fail-on-unexpected",
                "--gap-threshold", "10"  # Allow up to 10 gaps for edge cases
            ],
            args.verbose
        )
        results["coverage"] = passed
        if not passed:
            all_passed = False
            if args.fail_fast:
                print(f"\n{Colors.RED}Stopping due to --fail-fast{Colors.END}")
                sys.exit(1)
    else:
        print(f"\n{Colors.YELLOW}[SKIP] Cross-Source Coverage Validation: SKIPPED{Colors.END}")
        results["coverage"] = None
    
    # 4. Canonical Manifest Generation
    if not args.skip_manifest:
        manifest_cmd = [
            sys.executable,
            str(scripts_dir / "generate_canonical_manifest.py"),
            "--manifest", "manifests/canonical_manifest.json"
        ]
        if args.create_snapshot:
            manifest_cmd.append("--create-snapshot")
        
        passed = run_audit(
            "Canonical Manifest Generation",
            manifest_cmd,
            args.verbose
        )
        results["manifest"] = passed
        if not passed:
            all_passed = False
    else:
        print(f"\n{Colors.YELLOW}[SKIP] Canonical Manifest Generation: SKIPPED{Colors.END}")
        results["manifest"] = None
    
    # Summary
    print(f"\n{'='*70}")
    print(f"{Colors.BOLD}VALIDATION SUMMARY{Colors.END}")
    print('='*70)
    
    for name, passed in results.items():
        if passed is True:
            print(f"  {Colors.GREEN}[PASS] {name}: PASSED{Colors.END}")
        elif passed is False:
            print(f"  {Colors.RED}[FAIL] {name}: FAILED{Colors.END}")
        else:
            print(f"  {Colors.YELLOW}[SKIP] {name}: SKIPPED{Colors.END}")
    
    print()
    
    if all_passed:
        print(f"{Colors.GREEN}{'='*70}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}ALL AUDITS PASSED - BACKTEST APPROVED{Colors.END}")
        print(f"{Colors.GREEN}{'='*70}{Colors.END}")
        print()
        print("You may now run backtests:")
        print("  python testing/scripts/run_backtest.py")
        print("  python testing/scripts/run_ml_backtest.py")
        print("  python testing/scripts/lite_backtest_no_leakage.py")
        print()
        sys.exit(0)
    else:
        print(f"{Colors.RED}{'='*70}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}VALIDATION FAILED - BACKTEST BLOCKED{Colors.END}")
        print(f"{Colors.RED}{'='*70}{Colors.END}")
        print()
        print("Fix the failing audits before running backtests.")
        print("Run with --verbose for detailed error output.")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
