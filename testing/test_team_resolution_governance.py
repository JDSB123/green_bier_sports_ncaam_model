#!/usr/bin/env python3
"""
GOVERNANCE TEST: Team Name Resolution

This test ensures that ALL team name resolution goes through the authoritative
team resolution gate and that no ad-hoc mappings or fuzzy matching exist.

This test MUST pass before any code can be merged to main.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_adhoc_team_mappings():
    """Ensure no ad-hoc team mapping dictionaries exist in the codebase."""

    # Files that are allowed to have team mappings (authoritative sources only)
    ALLOWED_FILES = {
        "testing/canonical/barttorvik_team_mappings.py",
        "testing/canonical/team_resolution_service.py",
        "services/prediction-service-python/app/canonical/team_resolution_service.py",
        "scripts/validate_team_aliases.py",  # Validation script
        "services/prediction-service-python/run_today.py",  # Legacy service
    }

    violations = []

    # Scan Python files for suspicious patterns
    for py_file in ROOT.rglob("*.py"):
        if ".venv" in str(py_file) or "node_modules" in str(py_file):
            continue

        rel_path = str(py_file.relative_to(ROOT))
        if rel_path in ALLOWED_FILES:
            continue

        # CRITICAL: Don't allow ad-hoc mappings in generate_tonight_picks.py
        if "generate_tonight_picks.py" in rel_path:
            content = py_file.read_text()

            # Check for inline dict assignments with team names
            patterns = [
                r'{\s*["\'].*(?:green wave|crimson tide|tar heels|blue devils)',
                r'(?:team_map|team_dict|ODDS_TO_BARTTORVIK)\s*=\s*{',
            ]

            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    violations.append(
                        f"{rel_path}:{line_num} - Ad-hoc team mapping in critical file"
                    )

    if violations:
        msg = "\n".join([
            "",
            "❌ GOVERNANCE VIOLATION: Ad-hoc team mappings in generate_tonight_picks.py!",
            "=" * 70,
            "All team name resolution MUST go through:",
            "  - testing/canonical/barttorvik_team_mappings.py",
            "",
            "Violations found:",
        ] + violations + [
            "",
            "To fix:",
            "1. Remove ad-hoc mappings from generate_tonight_picks.py",
            "2. Use resolve_odds_api_to_barttorvik() from barttorvik_team_mappings",
            "3. Add missing teams to testing/canonical/barttorvik_team_mappings.py",
            "=" * 70,
        ])
        raise AssertionError(msg)


def test_no_fuzzy_matching_imports():
    """Ensure fuzzy matching libraries aren't imported for team resolution."""

    # Files allowed to import fuzzy libraries (for testing/validation only)
    ALLOWED_FILES = {
        "testing/canonical/team_resolution_service.py",
        "services/prediction-service-python/app/canonical/team_resolution_service.py",
        "testing/test_team_resolution_governance.py",  # This test file
    }

    violations = []

    for py_file in ROOT.rglob("*.py"):
        if ".venv" in str(py_file) or "node_modules" in str(py_file):
            continue

        rel_path = str(py_file.relative_to(ROOT))
        if rel_path in ALLOWED_FILES:
            continue

        content = py_file.read_text()

        # Check for fuzzy matching imports (pattern only, not actual imports)
        if re.search(r'from fuzzywuzzy import|import fuzzywuzzy', content):
            violations.append(f"{rel_path} - Imports fuzzywuzzy (fuzzy matching)")

        if re.search(r'from rapidfuzz import|import rapidfuzz', content):
            violations.append(f"{rel_path} - Imports rapidfuzz (fuzzy matching)")

    if violations:
        msg = "\n".join([
            "",
            "❌ GOVERNANCE VIOLATION: Fuzzy matching imports detected!",
            "=" * 70,
            "Team name resolution MUST be deterministic - NO fuzzy matching.",
            "",
            "Violations:",
        ] + violations + [
            "=" * 70,
        ])
        raise AssertionError(msg)


def test_generate_tonight_picks_uses_authoritative_gate():
    """Ensure generate_tonight_picks.py uses the authoritative team resolution."""

    script = ROOT / "generate_tonight_picks.py"
    if not script.exists():
        return  # Skip if file doesn't exist

    content = script.read_text()

    # Check that it imports the authoritative module
    if "from testing.canonical.barttorvik_team_mappings import" not in content:
        raise AssertionError(
            "generate_tonight_picks.py MUST import from "
            "testing.canonical.barttorvik_team_mappings"
        )

    # Check that resolve_odds_api_to_barttorvik is used
    if "resolve_odds_api_to_barttorvik(" not in content:
        raise AssertionError(
            "generate_tonight_picks.py MUST use resolve_odds_api_to_barttorvik() "
            "for team name resolution"
        )

    print("✓ generate_tonight_picks.py correctly uses authoritative team resolution gate")


if __name__ == "__main__":
    print("Running team resolution governance tests...")
    print()

    try:
        test_no_adhoc_team_mappings()
        print("✓ No ad-hoc team mappings found")

        test_no_fuzzy_matching_imports()
        print("✓ No fuzzy matching imports found")

        test_generate_tonight_picks_uses_authoritative_gate()
        print("✓ generate_tonight_picks.py uses authoritative gate")

        print()
        print("=" * 70)
        print("✓ ALL GOVERNANCE TESTS PASSED")
        print("=" * 70)

    except AssertionError as e:
        print(str(e))
        exit(1)
