#!/usr/bin/env python3
"""
Team Resolution Gate - Single Source of Truth for Team Name Canonicalization

This is THE gate that ALL data ingestion must pass through. It:
1. Loads the canonical team aliases from team_aliases_db.json (1,672+ mappings)
2. Attempts resolution with fallback normalization strategies
3. Logs unresolved names for manual review (does NOT abort)
4. Tracks source-specific variants for debugging

Usage:
    from team_resolution_gate import TeamResolutionGate
    
    gate = TeamResolutionGate()
    canonical = gate.resolve("Alabama Crimson Tide", source="espn")
    # Returns "Alabama" or None if unresolved
    
    # At end of ingestion:
    gate.report()  # Shows stats and unresolved names
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from testing.azure_data_reader import get_azure_reader


@dataclass
class ResolutionResult:
    """Result of a team name resolution attempt."""
    original: str
    canonical: Optional[str]
    method: str  # "exact", "normalized", "unresolved"
    source: str


@dataclass
class TeamResolutionGate:
    """
    Single entry point for all team name canonicalization.
    
    Cross-references against the master team_aliases_db.json and applies
    normalization fallbacks if needed.
    """
    
    # Azure blob path
    _aliases_blob: str = field(
        default_factory=lambda: os.getenv(
            "TEAM_ALIASES_BLOB", "backtest_datasets/team_aliases_db.json"
        )
    )
    
    # Loaded aliases: {lowercase_variant: canonical_name}
    _aliases: dict = field(default_factory=dict)
    
    # Stats tracking
    _resolved_count: int = 0
    _unresolved_count: int = 0
    _by_method: dict = field(default_factory=lambda: defaultdict(int))
    _by_source: dict = field(default_factory=lambda: defaultdict(lambda: {"resolved": 0, "unresolved": 0}))
    
    # Unresolved names for logging: {source: {raw_name: count}}
    _unresolved: dict = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    
    # Source variant tracking: {source: {raw_name: canonical_name}}
    _source_variants: dict = field(default_factory=lambda: defaultdict(dict))
    
    def __post_init__(self):
        """Load aliases on init."""
        self._load_aliases()
    
    def _load_aliases(self) -> None:
        """Load the master team aliases database."""
        reader = get_azure_reader()
        raw_aliases = reader.read_json(self._aliases_blob)
        
        # Build lowercase lookup
        self._aliases = {k.lower().strip(): v for k, v in raw_aliases.items()}
        
        # Also add canonical names as self-references, but NEVER override an explicit
        # alias mapping. This matters because some historical artifacts contain
        # "canonical-to-canonical" redirects (e.g. "Texas A&M-Corpus Christi" -> "Texas A&M-CC")
        # to unify naming across sources.
        canonical_names = set(raw_aliases.values())
        for name in canonical_names:
            key = name.lower().strip()
            if key not in self._aliases:
                self._aliases[key] = name

    def _lookup(self, candidate: str) -> Optional[str]:
        """
        Try multiple deterministic lookup keys for a candidate string.
        """
        if not candidate:
            return None
        keys = []
        c = candidate.strip()
        if not c:
            return None

        # Exact lowercase
        keys.append(c.lower().strip())

        # Hyphen spacing variants (some sources emit "A-B" vs "A - B")
        keys.append(c.lower().replace(" - ", "-").strip())
        keys.append(c.lower().replace("-", " - ").strip())

        # De-dupe while preserving order
        seen = set()
        for k in keys:
            kk = " ".join(k.split())
            if kk and kk not in seen:
                seen.add(kk)
                if kk in self._aliases:
                    return self._aliases[kk]
        return None
    
    def resolve(self, raw_name: str, source: str = "unknown") -> Optional[str]:
        """
        Resolve a raw team name to its canonical form.
        
        Args:
            raw_name: The raw team name from the data source
            source: Which data source this came from (espn, odds_api, barttorvik, ncaahoopr)
        
        Returns:
            Canonical team name, or None if unresolved
        """
        if not raw_name or not isinstance(raw_name, str):
            return None
        
        original = raw_name.strip()
        if not original:
            return None
        
        # Attempt 1: Exact match (case-insensitive)
        canonical = self._lookup(original)
        if canonical:
            self._record_resolution(original, canonical, "exact", source)
            return canonical
        
        # Attempt 2: Apply standard normalizations
        normalized = self._normalize(original)
        canonical = self._lookup(normalized)
        if canonical:
            self._record_resolution(original, canonical, "normalized", source)
            return canonical
        
        # Attempt 3: Aggressive normalization (remove mascots, etc.)
        aggressive = self._normalize_aggressive(original)
        canonical = self._lookup(aggressive)
        if canonical:
            self._record_resolution(original, canonical, "aggressive", source)
            return canonical

        # Attempt 4: Deterministic suffix stripping (common for ESPN mascots):
        # e.g. "Texas A&M-Corpus Christi Islanders" -> "Texas A&M-Corpus Christi"
        # We ONLY accept if the stripped base already exists in aliases.
        base = aggressive.strip()
        words = base.split()
        for n in (1, 2, 3):
            if len(words) <= n:
                continue
            stripped = " ".join(words[:-n]).strip()
            canonical = self._lookup(stripped)
            if canonical:
                self._record_resolution(original, canonical, f"suffix_strip_{n}", source)
                return canonical
        
        # Failed - log and return None
        self._record_unresolved(original, source)
        return None
    
    def _normalize(self, name: str) -> str:
        """
        Apply standard normalization rules (matches database migration 023).
        
        State → St.
        Saint → St.
        Northern/Southern/Eastern/Western/Central → N./S./E./W./C.
        Remove " University", "University of "
        """
        result = name.strip()
        
        # State → St.
        result = re.sub(r' State$', ' St.', result, flags=re.IGNORECASE)
        result = re.sub(r' State ', ' St. ', result, flags=re.IGNORECASE)
        
        # Saint → St.
        result = re.sub(r'^Saint ', 'St. ', result, flags=re.IGNORECASE)
        result = re.sub(r'^St ', 'St. ', result, flags=re.IGNORECASE)
        
        # Directional abbreviations
        result = re.sub(r'^Northern ', 'N. ', result, flags=re.IGNORECASE)
        result = re.sub(r'^Southern ', 'S. ', result, flags=re.IGNORECASE)
        result = re.sub(r'^Eastern ', 'E. ', result, flags=re.IGNORECASE)
        result = re.sub(r'^Western ', 'W. ', result, flags=re.IGNORECASE)
        result = re.sub(r'^Central ', 'C. ', result, flags=re.IGNORECASE)
        
        # Carolina abbreviations
        result = re.sub(r'^North Carolina', 'N.C.', result, flags=re.IGNORECASE)
        result = re.sub(r'^South Carolina', 'S.C.', result, flags=re.IGNORECASE)
        
        # Remove University suffix/prefix
        result = re.sub(r' University$', '', result, flags=re.IGNORECASE)
        result = re.sub(r'^University of ', '', result, flags=re.IGNORECASE)
        
        # Normalize quotes and dashes
        result = result.replace("'", "'").replace('"', '"').replace('"', '"')
        result = result.replace("–", "-").replace("—", "-")
        
        # Collapse whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    def _normalize_aggressive(self, name: str) -> str:
        """
        Aggressive normalization - remove mascots and common suffixes.
        """
        result = self._normalize(name)
        
        # Common mascot patterns (remove everything after team name)
        # e.g., "Alabama Crimson Tide" → "Alabama"
        mascot_patterns = [
            r' Crimson Tide$', r' Blue Devils$', r' Tar Heels$', r' Wildcats$',
            r' Tigers$', r' Bulldogs$', r' Bears$', r' Eagles$', r' Cardinals$',
            r' Seminoles$', r' Hurricanes$', r' Cavaliers$', r' Hokies$',
            r' Yellow Jackets$', r' Orange$', r' Demon Deacons$', r' Wolfpack$',
            r' Mountaineers$', r' Cyclones$', r' Jayhawks$', r' Longhorns$',
            r' Sooners$', r' Cowboys$', r' Red Raiders$', r' Horned Frogs$',
            r' Baylor Bears$', r' Volunteers$', r' Gators$', r' Razorbacks$',
            r' Gamecocks$', r' Commodores$', r' Rebels$', r' Aggies$',
            r' Spartans$', r' Wolverines$', r' Buckeyes$', r' Badgers$',
            r' Hawkeyes$', r' Cornhuskers$', r' Boilermakers$', r' Fighting Irish$',
            r' Hoosiers$', r' Illini$', r' Nittany Lions$', r' Terrapins$',
            r' Scarlet Knights$', r' Golden Gophers$', r' Bruins$', r' Trojans$',
            r' Ducks$', r' Huskies$', r' Cougars$', r' Beavers$', r' Sun Devils$',
            r' Buffaloes$', r' Utes$', r' Wildcats$', r' Devils$', r' Zags$',
            r' Gaels$', r' Broncos$', r' Pilots$', r' Waves$', r' Lions$',
            r' Panthers$', r' Owls$', r' Rams$', r' Miners$', r' Aztecs$',
            r' Falcons$', r' Mean Green$', r' Roadrunners$', r' Mustangs$',
            r' Golden$', r' Rattlers$', r' Hornets$', r' Blazers$',
        ]
        
        for pattern in mascot_patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        
        return result.strip()
    
    def _record_resolution(self, original: str, canonical: str, method: str, source: str) -> None:
        """Record a successful resolution."""
        self._resolved_count += 1
        self._by_method[method] += 1
        self._by_source[source]["resolved"] += 1
        self._source_variants[source][original] = canonical
    
    def _record_unresolved(self, original: str, source: str) -> None:
        """Record an unresolved name."""
        self._unresolved_count += 1
        self._by_source[source]["unresolved"] += 1
        self._unresolved[source][original] += 1
    
    @property
    def stats(self) -> dict:
        """Get resolution statistics."""
        total = self._resolved_count + self._unresolved_count
        return {
            "total": total,
            "resolved": self._resolved_count,
            "unresolved": self._unresolved_count,
            "success_rate": self._resolved_count / total if total > 0 else 0,
            "by_method": dict(self._by_method),
            "by_source": {k: dict(v) for k, v in self._by_source.items()},
        }
    
    @property
    def unresolved_names(self) -> dict:
        """Get all unresolved names by source."""
        return {source: dict(names) for source, names in self._unresolved.items()}
    
    def report(self, verbose: bool = True) -> None:
        """Print resolution report."""
        stats = self.stats
        
        print("\n" + "=" * 60)
        print("TEAM RESOLUTION GATE REPORT")
        print("=" * 60)
        print(f"Total resolutions: {stats['total']}")
        print(f"  Resolved: {stats['resolved']} ({stats['success_rate']:.1%})")
        print(f"  Unresolved: {stats['unresolved']}")
        
        if stats['by_method']:
            print("\nBy method:")
            for method, count in stats['by_method'].items():
                print(f"  {method}: {count}")
        
        if stats['by_source']:
            print("\nBy source:")
            for source, counts in stats['by_source'].items():
                total = counts['resolved'] + counts['unresolved']
                rate = counts['resolved'] / total if total > 0 else 0
                print(f"  {source}: {counts['resolved']}/{total} ({rate:.1%})")
        
        if verbose and self._unresolved:
            print("\nUnresolved names (add to team_aliases_db.json):")
            for source, names in self._unresolved.items():
                print(f"\n  [{source}]")
                for name, count in sorted(names.items(), key=lambda x: -x[1])[:20]:
                    print(f"    - {name!r} (×{count})")
        
        print("=" * 60 + "\n")
    
    def save_unresolved(self, blob_path: Optional[str] = None) -> str:
        """Save unresolved names to Azure Blob Storage for review."""
        if blob_path is None:
            blob_path = "team_resolution/unresolved_names.json"

        reader = get_azure_reader()
        reader.write_json(blob_path, self.unresolved_names, indent=2, sort_keys=True)
        return blob_path


# Singleton instance for convenience
_GATE: Optional[TeamResolutionGate] = None


def get_gate() -> TeamResolutionGate:
    """Get the singleton TeamResolutionGate instance."""
    global _GATE
    if _GATE is None:
        _GATE = TeamResolutionGate()
    return _GATE


def resolve_team_name(name: str, source: str = "unknown") -> Optional[str]:
    """
    Convenience function to resolve a team name.
    
    This is the DROP-IN REPLACEMENT for the old team_utils.resolve_team_name().
    """
    return get_gate().resolve(name, source)


# Backwards compatibility alias
def resolve_team(name: str, source: str = "unknown") -> Optional[str]:
    """Alias for resolve_team_name."""
    return resolve_team_name(name, source)


if __name__ == "__main__":
    # Self-test
    gate = TeamResolutionGate()
    
    test_cases = [
        ("Alabama", "test"),
        ("Alabama Crimson Tide", "espn"),
        ("alabama", "test"),
        ("Duke Blue Devils", "odds_api"),
        ("North Carolina Tar Heels", "espn"),
        ("UNC", "barttorvik"),
        ("Florida State Seminoles", "odds_api"),
        ("FSU", "barttorvik"),
        ("Gonzaga Bulldogs", "espn"),
        ("Zags", "odds_api"),
        ("St. John's", "barttorvik"),
        ("Saint John's Red Storm", "espn"),
        ("FAKE TEAM NAME", "test"),  # Should fail
        ("Not A Real University", "test"),  # Should fail
    ]
    
    print("Team Resolution Gate Self-Test")
    print("-" * 50)
    
    for raw_name, source in test_cases:
        canonical = gate.resolve(raw_name, source)
        status = "✓" if canonical else "✗"
        print(f"{status} {raw_name!r} ({source}) → {canonical!r}")
    
    gate.report()
