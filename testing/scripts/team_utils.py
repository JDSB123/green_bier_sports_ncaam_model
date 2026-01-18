#!/usr/bin/env python3
"""

Centralized team name canonicalization utility.

SINGLE SOURCE OF TRUTH: Canonical master (manifests/canonical_training_data_master.csv)

All scripts should use this module for team name resolution to ensure
consistent canonicalization across all ingestion, backtesting, and
prediction workflows.

Usage:
    from team_utils import resolve_team_name

    # Simple usage:
    canonical = resolve_team_name("Alabama State")  # Returns "Alabama St."

    # With source tracking:
    canonical = resolve_team_name("Alabama Crimson Tide", source="espn")
"""
from __future__ import annotations

# Import from the canonical Team Resolution Service
from testing.canonical.team_resolution_service import (
    ResolutionResult,
)
from testing.canonical.team_resolution_service import (
    resolve_team_name as _resolve,
)


def resolve_team_name(name: str, source: str = "unknown") -> str:
    """
    Resolve a team name to its canonical form.

    Uses the SINGLE SOURCE OF TRUTH: canonical master (manifests/canonical_training_data_master.csv)

    Args:
        name: Raw team name from any source (ESPN, Odds API, etc.)
        source: Which data source this came from (for tracking)

    Returns:
        Canonical team name, or original name if not found
    """
    if not name or not isinstance(name, str):
        return ""

    name = name.strip()
    if not name:
        return ""

    # Use the gate (note: source is for tracking only, not used by resolver)
    canonical = _resolve(name)

    # Return canonical name or original if not matched
    return canonical if canonical else name


def get_resolver() -> TeamResolutionGate:
    """Get the singleton TeamResolutionGate instance."""
    return get_gate()


# Export components
__all__ = [
    "resolve_team_name",
    "get_resolver",
    "TeamResolutionGate",
    "ResolutionResult",
]


if __name__ == "__main__":
    # Test the module
    test_names = [
        ("Alabama", "test"),
        ("Alabama A&M", "test"),
        ("Alabama State", "test"),
        ("alabama st", "test"),
        ("Tennessee", "espn"),
        ("Tennessee State", "espn"),
        ("Tennessee Tech", "espn"),
        ("Illinois", "barttorvik"),
        ("Illinois Chicago", "barttorvik"),
        ("UIC", "odds_api"),
        ("Ole Miss", "odds_api"),
        ("mississippi", "odds_api"),
        ("Random University", "test"),  # Should not match
    ]

    print("Team Name Resolution Test")
    print("=" * 60)
    print(f"{'Input':<30} | {'Canonical':<30}")
    print("-" * 60)

    for name, source in test_names:
        canonical = resolve_team_name(name, source)
        print(f"{name:<30} | {canonical:<30}")

    # Show report
    get_resolver().report()
