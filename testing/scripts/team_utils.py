#!/usr/bin/env python3
"""
Centralized team name canonicalization utility.

SINGLE SOURCE OF TRUTH: testing/production_parity/team_aliases.json

All scripts should use this module for team name resolution to ensure
consistent canonicalization across all ingestion, backtesting, and
prediction workflows.

Usage:
    from team_utils import resolve_team_name, ProductionTeamResolver
    
    # Simple usage:
    canonical = resolve_team_name("Alabama State")  # Returns "Alabama St."
    
    # Or use the resolver directly for more control:
    resolver = get_resolver()
    result = resolver.resolve("Alabama State")
    print(result.canonical_name)  # "Alabama St."
    print(result.match_type)      # "alias"
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Add production_parity to path
_SCRIPT_DIR = Path(__file__).resolve().parent
_PRODUCTION_PARITY_DIR = _SCRIPT_DIR.parent / "production_parity"
sys.path.insert(0, str(_PRODUCTION_PARITY_DIR))

# Import the resolver
try:
    from team_resolver import ProductionTeamResolver, ResolutionResult
    _RESOLVER: Optional[ProductionTeamResolver] = None
except ImportError as e:
    raise ImportError(
        f"Could not import ProductionTeamResolver. "
        f"Ensure team_resolver.py exists in {_PRODUCTION_PARITY_DIR}: {e}"
    )


def get_resolver() -> ProductionTeamResolver:
    """Get the singleton ProductionTeamResolver instance."""
    global _RESOLVER
    if _RESOLVER is None:
        _RESOLVER = ProductionTeamResolver()
    return _RESOLVER


def resolve_team_name(name: str) -> str:
    """
    Resolve a team name to its canonical form.
    
    Uses the SINGLE SOURCE OF TRUTH: team_aliases.json
    
    Args:
        name: Raw team name from any source (ESPN, Odds API, etc.)
        
    Returns:
        Canonical team name, or original name if not found
    """
    if not name or not isinstance(name, str):
        return ""
    
    name = name.strip()
    if not name:
        return ""
    
    resolver = get_resolver()
    result = resolver.resolve(name)
    
    # Return canonical name or original if not matched
    return result.canonical_name if result.canonical_name else name


# Export resolver components
__all__ = [
    "resolve_team_name",
    "get_resolver",
    "ProductionTeamResolver",
    "ResolutionResult",
]


if __name__ == "__main__":
    # Test the module
    test_names = [
        "Alabama",
        "Alabama A&M",
        "Alabama State",
        "alabama st",
        "Tennessee",
        "Tennessee State",
        "Tennessee Tech",
        "Illinois",
        "Illinois Chicago",
        "UIC",
        "Ole Miss",
        "mississippi",
        "Random University",  # Should not match
    ]
    
    print("Team Name Resolution Test")
    print("=" * 60)
    print(f"{'Input':<30} | {'Canonical':<30}")
    print("-" * 60)
    
    for name in test_names:
        canonical = resolve_team_name(name)
        print(f"{name:<30} | {canonical:<30}")
