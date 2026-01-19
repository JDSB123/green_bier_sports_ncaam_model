#!/usr/bin/env python3
"""
TEAM NAME RESOLUTION SERVICE

Centralized service for resolving team names across all data sources.
Provides fuzzy matching, learning capabilities, and confidence scoring.

Usage:
    from testing.canonical.team_resolution_service import TeamResolutionService

    resolver = TeamResolutionService()
    canonical_name = resolver.resolve("cal state northridge")
    # Returns: "CSU Northridge"
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

try:
    from fuzzywuzzy import fuzz
    from fuzzywuzzy.process import extractOne
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    # Fuzzy matching is OPTIONAL and must be explicitly enabled.


@dataclass
class ResolutionResult:
    """Result of team name resolution."""
    canonical_name: str
    confidence: float
    method: str  # "exact", "alias", "fuzzy", "learned"
    original_name: str
    alternatives: list[tuple[str, float]] = None

    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


class TeamResolutionService:
    """
    Centralized team name resolution service.

    Features:
    - Exact matching with aliases database
    - Fuzzy matching for similar names
    - Learning from corrections
    - Confidence scoring
    - Performance caching
    """

    def __init__(
        self,
        aliases_file: Path | None = None,
        fuzzy_threshold: int = 85,
        learn_corrections: bool = False,
        enable_fuzzy: bool = False,
        cache_size: int = 10000
    ):
        """
        Initialize the team resolution service.

        Args:
            aliases_file: Disabled (Azure-only); keep None
            fuzzy_threshold: Minimum confidence for fuzzy matching (0-100)
            learn_corrections: Whether to learn from manual corrections
            cache_size: Size of LRU cache for performance
        """
        # IMPORTANT:
        # - Authoritative ingestion must be deterministic (no fuzzy).
        # - Fuzzy matching is allowed ONLY as an opt-in suggestion tool.
        self.enable_fuzzy = bool(enable_fuzzy)
        if self.enable_fuzzy and not FUZZY_AVAILABLE:
            raise ImportError(
                "Fuzzy matching requested but fuzzywuzzy is not installed. "
                "Install: pip install fuzzywuzzy python-levenshtein"
            )

        if aliases_file is not None:
            raise RuntimeError(
                "Local aliases_file overrides are disabled. "
                "Use the Azure blob via TEAM_ALIASES_BLOB."
            )

        self.aliases_file = None
        self.fuzzy_threshold = fuzzy_threshold
        self.learn_corrections = learn_corrections

        # Performance optimization
        self._normalize_cache = {}

        # Load core data
        self._aliases = self._load_aliases()
        self._canonical_teams = self._build_canonical_set()
        self._reverse_aliases = self._build_reverse_aliases()

        # Learning data
        self._learned_corrections: dict[str, str] = {}
        self._confidence_cache: dict[str, ResolutionResult] = {}

        # Set up cached methods
        self.resolve = lru_cache(maxsize=cache_size)(self._resolve_uncached)

    def _load_aliases(self) -> dict[str, str]:
        """Load team aliases from Azure blob storage, with local Barttorvik fallback."""
        # Try Azure first (production/backtest environment)
        try:
            from testing.azure_data_reader import AzureDataReader

            reader = AzureDataReader(enable_canonicalization=False)
            raw_aliases = reader.read_json("backtest_datasets/team_aliases_db.json")

            normalized: dict[str, str] = {}
            for raw_key, canonical in raw_aliases.items():
                key = self._normalize_team_name(str(raw_key))
                if not key:
                    continue
                if key in normalized and normalized[key] != canonical:
                    continue
                normalized[key] = canonical
            return normalized
        except Exception as azure_error:
            # FALLBACK: Use Barttorvik live data for local/live predictions
            # This provides the same canonical team names that the Azure DB has
            try:
                from datetime import datetime

                import requests

                season = datetime.now().year if datetime.now().month >= 11 else datetime.now().year
                url = f"https://barttorvik.com/{season}_team_results.json"
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                # Build aliases using Barttorvik team names as canonical
                normalized: dict[str, str] = {}
                for row in data:
                    if not isinstance(row, list) or len(row) < 2:
                        continue
                    canonical_name = str(row[1]).strip()  # Barttorvik's team name

                    # Add self-reference
                    key = self._normalize_team_name(canonical_name)
                    if key:
                        normalized[key] = canonical_name

                return normalized
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Failed to load aliases from Azure: {azure_error}\n"
                    f"Failed to load fallback from Barttorvik: {fallback_error}"
                ) from azure_error

    def _build_canonical_set(self) -> set[str]:
        """Build set of all canonical team names."""
        return set(self._aliases.values())
        # Add some common variations that might not be in aliases

    def _build_reverse_aliases(self) -> dict[str, list[str]]:
        """Build reverse mapping from canonical name to all variants."""
        reverse = defaultdict(list)
        for variant, canonical in self._aliases.items():
            reverse[canonical].append(variant)
        return dict(reverse)

    def _normalize_team_name(self, name: str) -> str:
        """Normalize team name for consistent matching."""
        if pd.isna(name):
            return ""

        # Use cache for performance
        cache_key = name.lower().strip()
        if cache_key in self._normalize_cache:
            return self._normalize_cache[cache_key]

        # Normalize
        normalized = name.lower().strip()

        # Remove common suffixes and clean up
        # Multiple spaces -> single
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        normalized = normalized.strip()

        # Common abbreviation expansions
        expansions = {
            'st ': 'state ',
            'csu ': 'cal state ',
            'cal ': 'california ',
            'nc ': 'north carolina ',
            'sc ': 'south carolina ',
            'usc ': 'southern california ',
            'unlv ': 'nevada las vegas ',
            'utep ': 'texas el paso ',
            'utsa ': 'texas san antonio ',
            'uab ': 'alabama birmingham ',
            'vcu ': 'virginia commonwealth ',
            'unc ': 'north carolina ',
            'etsu ': 'east tennessee state ',
            'njit ': 'new jersey institute technology ',
            'iupui ': 'indiana university purdue university indianapolis ',
            'siue ': 'southern illinois edwardsville ',
            'umbc ': 'university maryland baltimore county ',
            'umkc ': 'university missouri kansas city ',
            'uic ': 'university illinois chicago ',
            'uri ': 'university rhode island ',
            'usf ': 'university south florida ',
            'fgcu ': 'florida gulf coast ',
            'fau ': 'florida atlantic ',
            'fiu ': 'florida international ',
            'ucf ': 'university central florida ',
        }

        for abbr, full in expansions.items():
            if normalized.startswith(abbr):
                normalized = full + normalized[len(abbr):]
                break

        self._normalize_cache[cache_key] = normalized
        return normalized

    def _resolve_uncached(self, name: str) -> ResolutionResult:
        """
        Resolve team name without caching.

        Returns ResolutionResult with confidence score and method used.
        """
        if pd.isna(name) or not name.strip():
            return ResolutionResult("", 0.0, "empty", name)

        original_name = name.strip()
        normalized = self._normalize_team_name(original_name)

        # 1. Check learned corrections first
        if normalized in self._learned_corrections:
            canonical = self._learned_corrections[normalized]
            return ResolutionResult(canonical, 100.0, "learned", original_name)

        # 2. Exact match in aliases
        if normalized in self._aliases:
            canonical = self._aliases[normalized]
            return ResolutionResult(canonical, 100.0, "exact", original_name)

        # 3. Fuzzy match (OPT-IN ONLY; not used by authoritative ingestion)
        if self.enable_fuzzy and FUZZY_AVAILABLE:
            # 3a) Fuzzy match against aliases
            if self._aliases:
                from fuzzywuzzy.process import extract

                best_match, score = extractOne(
                    normalized,
                    list(self._aliases.keys()),
                    scorer=fuzz.ratio,
                )
                if score >= self.fuzzy_threshold:
                    canonical = self._aliases[best_match]
                    # Get alternatives using extract with limit
                    alternatives_data = extract(
                        normalized,
                        list(self._aliases.keys()),
                        scorer=fuzz.ratio,
                        limit=4,
                    )[1:4]  # Skip best match
                    alternatives = [
                        (self._aliases[k], float(s))
                        for k, s in alternatives_data
                    ]
                    return ResolutionResult(
                        canonical,
                        float(score),
                        "fuzzy",
                        original_name,
                        alternatives,
                    )

            # 3b) Fuzzy match against canonical names directly
            if self._canonical_teams:
                best_match, score = extractOne(
                    normalized,
                    list(self._canonical_teams),
                    scorer=fuzz.ratio,
                )
                if score >= self.fuzzy_threshold:
                    return ResolutionResult(
                        best_match,
                        float(score),
                        "canonical_fuzzy",
                        original_name,
                    )

        # 4. No good match found:
        # leave original string in-place; gate fails in strict mode.
        return ResolutionResult(original_name, 0.0, "unresolved", original_name)

    def learn_correction(self, original_name: str, canonical_name: str):
        """Learn a correction for future use."""
        if not self.learn_corrections:
            return

        normalized = self._normalize_team_name(original_name)
        self._learned_corrections[normalized] = canonical_name

        # Clear cache for this name
        if hasattr(self, 'resolve') and hasattr(self.resolve, 'cache_info'):
            self.resolve.cache_clear()

    def get_unresolved_teams(self, team_list: list[str]) -> list[str]:
        """Get list of teams that cannot be resolved with high confidence."""
        unresolved = []
        for team in team_list:
            result = self.resolve(team)
            if result.confidence < self.fuzzy_threshold:
                unresolved.append(team)
        return list(set(unresolved))

    def validate_resolution(
        self,
        team_list: list[str],
    ) -> dict[str, ResolutionResult]:
        """Validate resolution for a list of teams, return detailed results."""
        results = {}
        for team in team_list:
            results[team] = self.resolve(team)
        return results

    def add_aliases(self, new_aliases: dict[str, str]):
        raise RuntimeError(
            "Alias mutation is disabled. Update aliases in the Team Registry "
            "(Postgres) and re-export the JSON artifact."
        )

    def save_aliases(self):
        raise RuntimeError(
            "Writing team_aliases_db.json is disabled from this service. "
            "Use scripts/export_team_registry.py to publish the "
            "synced artifact."
        )

    def get_stats(self) -> dict:
        """Get statistics about the resolution service."""
        return {
            "total_aliases": len(self._aliases),
            "canonical_teams": len(self._canonical_teams),
            "learned_corrections": len(self._learned_corrections),
            "cache_size": len(self._normalize_cache),
            "fuzzy_threshold": self.fuzzy_threshold
        }


# Global singleton instance
_team_resolver: TeamResolutionService | None = None


def get_team_resolver() -> TeamResolutionService:
    """Get the global team resolution service instance."""
    global _team_resolver
    if _team_resolver is None:
        # Default to deterministic-only resolution (no fuzzy, no learning).
        _team_resolver = TeamResolutionService(
            enable_fuzzy=False,
            learn_corrections=False,
        )
    return _team_resolver


def resolve_team_name(name: str) -> str:
    """Convenience function to resolve a single team name."""
    return get_team_resolver().resolve(name).canonical_name


def resolve_team_names(names: list[str]) -> list[str]:
    """Convenience function to resolve multiple team names."""
    resolver = get_team_resolver()
    return [resolver.resolve(name).canonical_name for name in names]


if __name__ == "__main__":
    # Test the service
    print("=" * 60)
    print("TEAM RESOLUTION SERVICE TEST")
    print("=" * 60)

    try:
        resolver = TeamResolutionService()

        test_names = [
            "cal state northridge",
            "NC State",
            "Southern Illinois",
            "bethune-cookman",
            "some unknown team"
        ]

        print(f"Loaded {len(resolver._aliases)} aliases")
        print(f"Found {len(resolver._canonical_teams)} canonical teams")

        for name in test_names:
            result = resolver.resolve(name)
            print(
                f"\n'{name}' -> '{result.canonical_name}' "
                f"(confidence: {result.confidence:.1f}, method: {result.method})"
            )
            if result.alternatives:
                print(f"  Alternatives: {result.alternatives[:2]}")

        print("\n[OK] Team resolution service working!")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("Install fuzzywuzzy: pip install fuzzywuzzy python-levenshtein")
