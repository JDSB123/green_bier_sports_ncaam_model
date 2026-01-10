#!/usr/bin/env python3
"""
TEAM NAME RESOLUTION SERVICE - PRODUCTION VERSION

Centralized service for resolving team names across all data sources.
Provides fuzzy matching, learning capabilities, and confidence scoring.

This is a production copy of testing/canonical/team_resolution_service.py
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from functools import lru_cache

try:
    from fuzzywuzzy import fuzz
    from fuzzywuzzy.process import extractOne, extract
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    print("WARNING: fuzzywuzzy not installed. Team resolution will be limited.")


@dataclass
class ResolutionResult:
    """Result of team name resolution."""
    canonical_name: str
    confidence: float
    method: str  # "exact", "alias", "fuzzy", "learned"
    original_name: str
    alternatives: List[Tuple[str, float]] = None

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
        aliases_file: Optional[Path] = None,
        fuzzy_threshold: int = 85,
        learn_corrections: bool = True,
        cache_size: int = 10000
    ):
        """
        Initialize the team resolution service.

        Args:
            aliases_file: Path to team aliases JSON file
            fuzzy_threshold: Minimum confidence for fuzzy matching (0-100)
            learn_corrections: Whether to learn from manual corrections
            cache_size: Size of LRU cache for performance
        """
        if not FUZZY_AVAILABLE:
            raise ImportError("fuzzywuzzy required for team resolution")

        # Default to standard locations (try container location first)
        if aliases_file is None:
            # Try container location first
            container_location = Path(__file__).resolve().parent.parent.parent / "team_aliases_db.json"
            if container_location.exists():
                aliases_file = container_location
            else:
                # Fall back to data directory
                aliases_file = Path(__file__).resolve().parents[3] / "ncaam_historical_data_local" / "backtest_datasets" / "team_aliases_db.json"

        self.aliases_file = aliases_file
        self.fuzzy_threshold = fuzzy_threshold
        self.learn_corrections = learn_corrections

        # Load core data
        self._aliases = self._load_aliases()
        self._canonical_teams = self._build_canonical_set()
        self._reverse_aliases = self._build_reverse_aliases()

        # Learning data
        self._learned_corrections: Dict[str, str] = {}
        self._confidence_cache: Dict[str, ResolutionResult] = {}

        # Performance optimization
        self._normalize_cache = {}

        # Set up cached methods
        self.resolve = lru_cache(maxsize=cache_size)(self._resolve_uncached)

    def _load_aliases(self) -> Dict[str, str]:
        """Load team aliases from file."""
        if not self.aliases_file.exists():
            print(f"WARNING: Aliases file not found: {self.aliases_file}")
            return {}

        try:
            with open(self.aliases_file) as f:
                return json.load(f)
        except Exception as e:
            print(f"ERROR loading aliases: {e}")
            return {}

    def _build_canonical_set(self) -> Set[str]:
        """Build set of all canonical team names."""
        canonical = set(self._aliases.values())
        return canonical

    def _build_reverse_aliases(self) -> Dict[str, List[str]]:
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
        normalized = re.sub(r'\s+', ' ', normalized)  # Multiple spaces -> single
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

        original_name = str(name).strip()
        normalized = self._normalize_team_name(original_name)

        # 1. Check learned corrections first
        if normalized in self._learned_corrections:
            canonical = self._learned_corrections[normalized]
            return ResolutionResult(canonical, 100.0, "learned", original_name)

        # 2. Exact match in aliases
        if normalized in self._aliases:
            canonical = self._aliases[normalized]
            return ResolutionResult(canonical, 100.0, "exact", original_name)

        # 3. Fuzzy match against aliases
        if self._aliases:
            best_match, score = extractOne(
                normalized,
                list(self._aliases.keys()),
                scorer=fuzz.ratio
            )
            if score >= self.fuzzy_threshold:
                canonical = self._aliases[best_match]
                # Get alternatives
                alternatives_data = extract(
                    normalized,
                    list(self._aliases.keys()),
                    scorer=fuzz.ratio,
                    limit=4  # Get top 4, we'll use the 2nd, 3rd, 4th
                )[1:4]  # Skip the best match
                alternatives = [(self._aliases[k], float(s)) for k, s in alternatives_data]
                return ResolutionResult(canonical, float(score), "fuzzy", original_name, alternatives)

        # 4. Fuzzy match against canonical names directly
        if self._canonical_teams:
            best_match, score = extractOne(
                normalized,
                list(self._canonical_teams),
                scorer=fuzz.ratio
            )
            if score >= self.fuzzy_threshold:
                return ResolutionResult(best_match, float(score), "canonical_fuzzy", original_name)

        # 5. No good match found
        return ResolutionResult(original_name, 0.0, "unresolved", original_name)

    def learn_correction(self, original_name: str, canonical_name: str):
        """Learn a correction for future use."""
        if not self.learn_corrections:
            return

        normalized = self._normalize_team_name(original_name)
        self._learned_corrections[normalized] = canonical_name

    def resolve(self, name: str) -> ResolutionResult:
        """Resolve a team name to canonical form."""
        return self._resolve_uncached(name)

    def get_unresolved_teams(self, team_list: List[str]) -> List[str]:
        """Get list of teams that cannot be resolved with high confidence."""
        unresolved = []
        for team in team_list:
            result = self.resolve(team)
            if result.confidence < self.fuzzy_threshold:
                unresolved.append(team)
        return list(set(unresolved))

    def get_stats(self) -> Dict:
        """Get statistics about the resolution service."""
        return {
            "total_aliases": len(self._aliases),
            "canonical_teams": len(self._canonical_teams),
            "learned_corrections": len(self._learned_corrections),
            "cache_size": len(self._normalize_cache),
            "fuzzy_threshold": self.fuzzy_threshold
        }


# Global singleton instance
_team_resolver: Optional[TeamResolutionService] = None


def get_team_resolver() -> TeamResolutionService:
    """Get the global team resolution service instance."""
    global _team_resolver
    if _team_resolver is None:
        _team_resolver = TeamResolutionService()
    return _team_resolver


def resolve_team_name(name: str) -> str:
    """Convenience function to resolve a single team name."""
    return get_team_resolver().resolve(name).canonical_name


# Add pandas import for this module
try:
    import pandas as pd
except ImportError:
    pd = None