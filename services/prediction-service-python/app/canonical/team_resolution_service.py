#!/usr/bin/env python3
"""
TEAM NAME RESOLUTION SERVICE - PRODUCTION VERSION

Centralized service for resolving team names across all data sources.
Provides fuzzy matching, learning capabilities, and confidence scoring.

This is a production copy of testing/canonical/team_resolution_service.py
"""

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

try:
    from azure.storage.blob import BlobServiceClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

try:
    from fuzzywuzzy import fuzz
    from fuzzywuzzy.process import extract, extractOne
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


def _load_alias_blob(container_client, blob_path: str) -> dict[str, str]:
    blob_client = container_client.get_blob_client(blob_path)
    payload = blob_client.download_blob().readall()
    return json.loads(payload.decode("utf-8"))


def _load_aliases_from_azure() -> dict[str, str]:
    if not AZURE_AVAILABLE:
        raise ImportError("azure-storage-blob is required to load aliases from Azure.")

    conn_str = os.getenv("AZURE_CANONICAL_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError(
            "AZURE_CANONICAL_CONNECTION_STRING is required to load team aliases from Azure."
        )

    container = os.getenv("AZURE_CANONICAL_CONTAINER", "ncaam-historical-data")
    primary_blob = os.getenv(
        "TEAM_ALIASES_BLOB_PRIMARY", "canonical/team_aliases_prod.json"
    )
    fallback_blob = os.getenv(
        "TEAM_ALIASES_BLOB_FALLBACK", "backtest_datasets/team_aliases_db.json"
    )

    service = BlobServiceClient.from_connection_string(conn_str)
    container_client = service.get_container_client(container)

    primary_aliases = _load_alias_blob(container_client, primary_blob)

    try:
        fallback_aliases = _load_alias_blob(container_client, fallback_blob)
        if len(primary_aliases) < len(fallback_aliases):
            raise RuntimeError(
                "Alias blob validation failed: primary alias set is smaller than fallback. "
                "Refusing to proceed to avoid accidental replacement."
            )
    except Exception:
        pass

    return primary_aliases


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
        """Load team aliases from file."""
        try:
            raw_aliases = _load_aliases_from_azure()
            normalized: dict[str, str] = {}
            for raw_key, canonical in raw_aliases.items():
                key = self._normalize_team_name(str(raw_key))
                if not key:
                    continue
                if key in normalized and normalized[key] != canonical:
                    continue
                normalized[key] = canonical
            return normalized
        except Exception as e:
            raise RuntimeError(f"Failed to load aliases from Azure: {e}") from e

    def _build_canonical_set(self) -> set[str]:
        """Build set of all canonical team names."""
        return set(self._aliases.values())

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
        original_name = "" if name is None else str(name).strip()
        if not original_name:
            return ResolutionResult("", 0.0, "empty", str(name))
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
        if self.enable_fuzzy and FUZZY_AVAILABLE and self._aliases:
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

        # 4. Fuzzy match against canonical names directly (OPT-IN ONLY)
        if self.enable_fuzzy and FUZZY_AVAILABLE and self._canonical_teams:
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

    def get_unresolved_teams(self, team_list: list[str]) -> list[str]:
        """Get list of teams that cannot be resolved with high confidence."""
        unresolved = []
        for team in team_list:
            result = self.resolve(team)
            if result.confidence < self.fuzzy_threshold:
                unresolved.append(team)
        return list(set(unresolved))

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
        _team_resolver = TeamResolutionService(enable_fuzzy=False, learn_corrections=False)
    return _team_resolver


def resolve_team_name(name: str) -> str:
    """Convenience function to resolve a single team name."""
    return get_team_resolver().resolve(name).canonical_name
