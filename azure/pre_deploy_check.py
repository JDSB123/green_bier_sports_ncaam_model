#!/usr/bin/env python3
"""
Pre-Deployment Validation for Green Bier Sport Ventures
========================================================

Runs comprehensive checks before deployment to ensure:
1. No port conflicts
2. All required secrets exist
3. Docker/Azure environment is ready
4. Configuration is valid

Run this BEFORE deploying any sport model.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from port_allocator import get_sport_allocation, validate_allocation, check_docker_ports
except ImportError:
    print("Error: port_allocator.py not found in azure/ directory")
    sys.exit(1)


class PreDeployCheck:
    """Pre-deployment validation suite."""

    def __init__(self, sport: str, target: str = "docker"):
        self.sport = sport.lower()
        self.target = target  # "docker" or "azure"
        self.allocation = get_sport_allocation(self.sport)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passed: List[str] = []

    def check_secrets(self) -> bool:
        """Verify all required secrets exist."""
        secrets_dir = Path(__file__).parent.parent / "secrets"

        required_secrets = [
            ("db_password.txt", "Database password"),
            ("redis_password.txt", "Redis password"),
            ("odds_api_key.txt", "The Odds API key"),
        ]

        all_exist = True
        for filename, description in required_secrets:
            path = secrets_dir / filename
            if path.exists():
                content = path.read_text().strip()
                if not content:
                    self.errors.append(f"Secret '{filename}' exists but is EMPTY")
                    all_exist = False
                elif "CHANGE_ME" in content.upper() or "YOUR_" in content.upper():
                    self.errors.append(f"Secret '{filename}' contains placeholder value")
                    all_exist = False
                else:
                    self.passed.append(f"Secret '{description}' configured")
            else:
                self.errors.append(f"Missing secret: {filename} ({description})")
                all_exist = False

        return all_exist

    def check_ports(self) -> bool:
        """Verify no port conflicts."""
        valid, issues = validate_allocation(self.allocation)

        if valid:
            self.passed.append(f"Ports {self.allocation.postgres_port}, {self.allocation.redis_port}, {self.allocation.prediction_port} available")
            return True
        else:
            for issue in issues:
                # Check if it's our own container
                if self.sport in issue.lower():
                    self.warnings.append(f"Port in use by own container: {issue}")
                else:
                    self.errors.append(f"Port conflict: {issue}")
            return len(self.errors) == 0

    def check_docker(self) -> bool:
        """Verify Docker is available and running."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                self.passed.append("Docker daemon is running")
                return True
            else:
                self.errors.append("Docker daemon not responding")
                return False
        except FileNotFoundError:
            self.errors.append("Docker not installed")
            return False
        except subprocess.TimeoutExpired:
            self.errors.append("Docker daemon timeout")
            return False

    def check_azure_cli(self) -> bool:
        """Verify Azure CLI is available (for Azure deployments)."""
        if self.target != "azure":
            return True

        try:
            result = subprocess.run(
                ["az", "account", "show"],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                self.passed.append("Azure CLI logged in")
                return True
            else:
                self.errors.append("Azure CLI not logged in (run: az login)")
                return False
        except FileNotFoundError:
            self.errors.append("Azure CLI not installed")
            return False
        except subprocess.TimeoutExpired:
            self.errors.append("Azure CLI timeout")
            return False

    def check_env_not_exposed(self) -> bool:
        """Verify .env file is not committed to git."""
        project_root = Path(__file__).parent.parent
        env_file = project_root / ".env"

        if not env_file.exists():
            self.passed.append("No .env file present (using secrets/)")
            return True

        # Check if .env is in .gitignore
        gitignore = project_root / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text()
            if ".env" in content:
                self.passed.append(".env file protected by .gitignore")
            else:
                self.warnings.append(".env exists but not in .gitignore")

        # Check if .env is tracked in git
        try:
            result = subprocess.run(
                ["git", "ls-files", "--cached", ".env"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip():
                self.errors.append("CRITICAL: .env file is tracked in git! Run: git rm --cached .env")
                return False
            else:
                self.passed.append(".env file not tracked in git")
                return True
        except Exception:
            self.warnings.append("Could not verify git status of .env")
            return True

    def check_no_hardcoded_secrets(self) -> bool:
        """Scan for hardcoded secrets in source files."""
        project_root = Path(__file__).parent.parent

        # Patterns that indicate hardcoded secrets
        secret_patterns = [
            "api_key=",
            "password=",
            "secret=",
            "token=",
        ]

        # Files to scan (exclude binaries, secrets dir, .git)
        scan_extensions = {".py", ".rs", ".go", ".sh", ".yml", ".yaml", ".json"}
        exclude_dirs = {".git", "target", "venv", "__pycache__", "node_modules", "secrets"}

        issues_found = []

        for ext in scan_extensions:
            for file_path in project_root.rglob(f"*{ext}"):
                # Skip excluded directories
                if any(ex in file_path.parts for ex in exclude_dirs):
                    continue

                try:
                    content = file_path.read_text(errors="ignore").lower()
                    for pattern in secret_patterns:
                        if pattern in content:
                            # Check if it's env var reference (safe) or hardcoded (bad)
                            lines = content.split("\n")
                            for i, line in enumerate(lines, 1):
                                if pattern in line:
                                    # Skip if it's an env var or placeholder
                                    if "os.getenv" in line or "env::var" in line or "os.Getenv" in line:
                                        continue
                                    if "CHANGE_ME" in line.upper() or "<" in line:
                                        continue
                                    # Skip comments
                                    if line.strip().startswith("#") or line.strip().startswith("//"):
                                        continue
                                    # This might be a hardcoded secret
                                    rel_path = file_path.relative_to(project_root)
                                    issues_found.append(f"{rel_path}:{i}")
                except Exception:
                    pass

        if issues_found:
            self.warnings.append(f"Potential hardcoded secrets in {len(issues_found)} locations (manual review needed)")
        else:
            self.passed.append("No obvious hardcoded secrets detected")

        return True  # Warnings only, don't fail

    def check_database_config(self) -> bool:
        """Verify database configuration is sport-parameterized."""
        project_root = Path(__file__).parent.parent

        # Check Python service
        python_file = project_root / "services" / "prediction-service-python" / "run_today.py"
        if python_file.exists():
            content = python_file.read_text()
            if 'SPORT = os.getenv("SPORT"' in content:
                self.passed.append("Python service uses parameterized SPORT config")
            else:
                self.errors.append("Python service has hardcoded database config")

        # Check Rust service
        rust_file = project_root / "services" / "odds-ingestion-rust" / "src" / "main.rs"
        if rust_file.exists():
            content = rust_file.read_text()
            if 'env::var("SPORT")' in content:
                self.passed.append("Rust service uses parameterized SPORT config")
            else:
                self.errors.append("Rust service has hardcoded database config")

        # Check Go service
        go_file = project_root / "services" / "ratings-sync-go" / "main.go"
        if go_file.exists():
            content = go_file.read_text()
            if 'os.Getenv("SPORT")' in content:
                self.passed.append("Go service uses parameterized SPORT config")
            else:
                self.errors.append("Go service has hardcoded database config")

        return len(self.errors) == 0

    def run_all_checks(self) -> bool:
        """Run all pre-deployment checks."""
        print(f"\n{'='*60}")
        print(f"  PRE-DEPLOYMENT CHECK: {self.sport.upper()}")
        print(f"  Target: {self.target.upper()}")
        print(f"{'='*60}\n")

        checks = [
            ("Docker Environment", self.check_docker),
            ("Port Availability", self.check_ports),
            ("Secrets Configuration", self.check_secrets),
            ("Environment Security", self.check_env_not_exposed),
            ("Database Parameterization", self.check_database_config),
            ("Secret Scanning", self.check_no_hardcoded_secrets),
        ]

        if self.target == "azure":
            checks.insert(1, ("Azure CLI", self.check_azure_cli))

        all_passed = True
        for name, check_func in checks:
            print(f"Checking: {name}...")
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                self.errors.append(f"{name} check failed: {e}")
                all_passed = False

        # Print results
        print(f"\n{'='*60}")
        print("  RESULTS")
        print(f"{'='*60}\n")

        if self.passed:
            print("✅ PASSED:")
            for msg in self.passed:
                print(f"   • {msg}")
            print()

        if self.warnings:
            print("⚠️  WARNINGS:")
            for msg in self.warnings:
                print(f"   • {msg}")
            print()

        if self.errors:
            print("❌ ERRORS:")
            for msg in self.errors:
                print(f"   • {msg}")
            print()

        if all_passed and not self.errors:
            print(f"{'='*60}")
            print(f"  ✅ ALL CHECKS PASSED - Ready to deploy {self.sport.upper()}")
            print(f"{'='*60}\n")
            return True
        else:
            print(f"{'='*60}")
            print(f"  ❌ CHECKS FAILED - Fix errors before deploying")
            print(f"{'='*60}\n")
            return False


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Pre-deployment validation for Green Bier Sport Ventures"
    )
    parser.add_argument("sport", nargs="?", default="ncaam",
                        help="Sport to validate (default: ncaam)")
    parser.add_argument("--target", choices=["docker", "azure"], default="docker",
                        help="Deployment target (default: docker)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")

    args = parser.parse_args()

    checker = PreDeployCheck(args.sport, args.target)
    success = checker.run_all_checks()

    if args.json:
        print(json.dumps({
            "sport": checker.sport,
            "target": checker.target,
            "passed": checker.passed,
            "warnings": checker.warnings,
            "errors": checker.errors,
            "success": success
        }, indent=2))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
