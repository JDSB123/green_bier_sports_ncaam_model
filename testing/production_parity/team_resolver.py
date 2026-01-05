"""
Production-Parity Team Resolver.

Python port of SQL resolve_team_name() function with 4-step exact matching.
NO FUZZY MATCHING - exact matches only to prevent false positives like
Tennessee → Tennessee State.

This matches production behavior EXACTLY:
1. Exact canonical name match (case-insensitive)
2. Exact alias match (case-insensitive)
3. Normalized match (remove punctuation/whitespace normalization)
4. Mascot-stripped match (remove common mascot suffixes)

If all 4 steps fail, returns None (NEVER guess).
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class ResolutionStep(Enum):
    """Which step resolved the team name."""
    CANONICAL = "canonical"      # Step 1: Exact canonical match
    ALIAS = "alias"              # Step 2: Exact alias match
    NORMALIZED = "normalized"    # Step 3: Normalized match
    MASCOT_STRIPPED = "mascot"   # Step 4: Mascot-stripped match
    NON_D1 = "non_d1"            # Explicitly blocked (D2/NAIA/D3)
    UNRESOLVED = "unresolved"    # No match found


@dataclass
class ResolutionResult:
    """Result of team name resolution."""
    input_name: str
    canonical_name: Optional[str]
    step_used: ResolutionStep
    matched_via: Optional[str] = None  # What string matched (for audit)

    @property
    def resolved(self) -> bool:
        return self.canonical_name is not None

    def __repr__(self) -> str:
        if self.resolved:
            return f"'{self.input_name}' → '{self.canonical_name}' (step={self.step_used.value})"
        return f"'{self.input_name}' → UNRESOLVED"


# Common mascot suffixes to strip in Step 4
MASCOT_SUFFIXES = [
    # Most common mascots (sorted by frequency in NCAAM)
    "wildcats", "bulldogs", "tigers", "eagles", "panthers", "bears",
    "cougars", "hawks", "huskies", "lions", "cardinals", "knights",
    "rebels", "aggies", "wolfpack", "wolverines", "spartans", "hurricanes",
    "blue devils", "tar heels", "crimson tide", "fighting irish",
    "hoosiers", "boilermakers", "buckeyes", "wolverines", "badgers",
    "hawkeyes", "golden gophers", "cornhuskers", "terrapins", "nittany lions",
    "mountaineers", "razorbacks", "gamecocks", "volunteers", "commodores",
    "gators", "seminoles", "cavaliers", "hokies", "yellow jackets",
    "orange", "red raiders", "longhorns", "jayhawks", "sooners",
    "cowboys", "cyclones", "horned frogs", "bearcats", "musketeers",
    "bluejays", "golden eagles", "rams", "braves", "49ers",
    "owls", "peacocks", "friars", "hoyas", "pirates", "terriers",
    "gaels", "dons", "toreros", "waves", "broncos", "aztecs",
    "lobos", "utes", "buffaloes", "trojans", "bruins", "ducks",
    "beavers", "huskies", "cougars", "sun devils", "lumberjacks",
    "anteaters", "gauchos", "mustangs", "highlanders", "titans",
    "matadors", "roadrunners", "miners", "mean green", "thundering herd",
    "golden flashes", "rockets", "redhawks", "bobcats", "chippewas",
    "broncos", "zips", "cardinals", "penguins", "bulls", "flames",
    "phoenix", "leathernecks", "salukis", "redbirds", "sycamores",
    "braves", "shockers", "jayhawks", "kangaroos", "roos", "antelopes",
]


class ProductionTeamResolver:
    """
    Production-parity team resolver using 4-step exact matching.

    NO FUZZY MATCHING - this is critical for avoiding false positives.
    Production SQL uses exact matching only, so we must do the same.
    """

    def __init__(self, aliases_path: Optional[Path] = None):
        """
        Initialize resolver with team aliases.

        Args:
            aliases_path: Path to team_aliases.json. If None, uses default.
        """
        if aliases_path is None:
            aliases_path = Path(__file__).parent / "team_aliases.json"

        self._load_aliases(aliases_path)
        self._build_indexes()

        # Track resolution stats
        self.stats = {
            ResolutionStep.CANONICAL: 0,
            ResolutionStep.ALIAS: 0,
            ResolutionStep.NORMALIZED: 0,
            ResolutionStep.MASCOT_STRIPPED: 0,
            ResolutionStep.UNRESOLVED: 0,
        }

    def _load_aliases(self, path: Path) -> None:
        """Load aliases from JSON file."""
        if not path.exists():
            raise FileNotFoundError(f"Team aliases not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self._aliases = data.get("aliases", {})
        self._canonical_names = set(data.get("canonical_names", []))

        # Also add canonical names from alias targets
        for canonical in self._aliases.values():
            self._canonical_names.add(canonical)

        print(f"[TeamResolver] Loaded {len(self._aliases)} aliases, "
              f"{len(self._canonical_names)} canonical names")

    def _build_indexes(self) -> None:
        """Build lookup indexes for fast resolution."""
        # Index 1: Lowercase canonical names → canonical
        self._canonical_lower = {}
        for name in self._canonical_names:
            self._canonical_lower[name.lower()] = name

        # Index 2: Lowercase aliases → canonical (already in _aliases)
        self._alias_lower = {k.lower(): v for k, v in self._aliases.items()}

        # Index 3: Normalized canonical names → canonical
        self._canonical_normalized = {}
        for name in self._canonical_names:
            normalized = self._normalize(name)
            self._canonical_normalized[normalized] = name

        # Index 4: Normalized aliases → canonical
        self._alias_normalized = {}
        for alias, canonical in self._aliases.items():
            normalized = self._normalize(alias)
            self._alias_normalized[normalized] = canonical

        # Index 5: Mascot-stripped canonical → canonical
        self._canonical_mascot_stripped = {}
        for name in self._canonical_names:
            stripped = self._strip_mascot(name)
            if stripped != name.lower():  # Only if mascot was actually stripped
                self._canonical_mascot_stripped[stripped] = name

        # Index 6: Mascot-stripped aliases → canonical
        self._alias_mascot_stripped = {}
        for alias, canonical in self._aliases.items():
            stripped = self._strip_mascot(alias)
            if stripped != alias.lower():
                self._alias_mascot_stripped[stripped] = canonical

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Normalize text for matching:
        - Lowercase
        - Remove punctuation (except &)
        - Collapse whitespace
        - Unicode normalize
        """
        # Normalize unicode
        text = unicodedata.normalize('NFKD', text)
        text = text.encode('ascii', 'ignore').decode('ascii')

        # Lowercase
        text = text.lower()

        # Remove punctuation except & (for A&M, etc.)
        text = re.sub(r"[^\w\s&]", "", text)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    @staticmethod
    def _strip_mascot(text: str) -> str:
        """Strip mascot suffix from team name."""
        text = text.lower().strip()

        for mascot in MASCOT_SUFFIXES:
            # Must be at end of string and preceded by space
            if text.endswith(" " + mascot):
                text = text[:-len(mascot)-1].strip()
                break
            # Handle case where mascot IS the whole suffix part
            pattern = rf"\s+{re.escape(mascot)}$"
            if re.search(pattern, text):
                text = re.sub(pattern, "", text).strip()
                break

        return text

    def resolve(self, input_name: str) -> ResolutionResult:
        """
        Resolve a team name to its canonical form.

        Uses 4-step exact matching (production parity):
        0. Check if non-D1 (D2/NAIA/D3) - skip immediately
        1. Exact canonical name match
        2. Exact alias match
        3. Normalized match
        4. Mascot-stripped match

        Returns ResolutionResult with step_used for audit trail.

        Args:
            input_name: Raw team name from any source

        Returns:
            ResolutionResult with canonical_name (or None if unresolved)
        """
        if not input_name or not input_name.strip():
            return ResolutionResult(
                input_name=input_name or "",
                canonical_name=None,
                step_used=ResolutionStep.UNRESOLVED,
            )

        input_clean = input_name.strip()
        input_lower = input_clean.lower()

        # Step 0: Check if non-D1 team (D2/NAIA/D3)
        # Import here to avoid circular imports
        try:
            from .non_d1_filter import is_non_d1_team
            if is_non_d1_team(input_clean):
                self.stats[ResolutionStep.NON_D1] = self.stats.get(ResolutionStep.NON_D1, 0) + 1
                return ResolutionResult(
                    input_name=input_clean,
                    canonical_name=None,
                    step_used=ResolutionStep.NON_D1,
                    matched_via="non_d1_blocklist",
                )
        except ImportError:
            pass  # Filter not available, continue with resolution

        # Step 1: Exact canonical match
        if input_lower in self._canonical_lower:
            canonical = self._canonical_lower[input_lower]
            self.stats[ResolutionStep.CANONICAL] += 1
            return ResolutionResult(
                input_name=input_clean,
                canonical_name=canonical,
                step_used=ResolutionStep.CANONICAL,
                matched_via=canonical,
            )

        # Step 2: Exact alias match
        if input_lower in self._alias_lower:
            canonical = self._alias_lower[input_lower]
            self.stats[ResolutionStep.ALIAS] += 1
            return ResolutionResult(
                input_name=input_clean,
                canonical_name=canonical,
                step_used=ResolutionStep.ALIAS,
                matched_via=input_lower,
            )

        # Step 3: Normalized match
        input_normalized = self._normalize(input_clean)

        if input_normalized in self._canonical_normalized:
            canonical = self._canonical_normalized[input_normalized]
            self.stats[ResolutionStep.NORMALIZED] += 1
            return ResolutionResult(
                input_name=input_clean,
                canonical_name=canonical,
                step_used=ResolutionStep.NORMALIZED,
                matched_via=input_normalized,
            )

        if input_normalized in self._alias_normalized:
            canonical = self._alias_normalized[input_normalized]
            self.stats[ResolutionStep.NORMALIZED] += 1
            return ResolutionResult(
                input_name=input_clean,
                canonical_name=canonical,
                step_used=ResolutionStep.NORMALIZED,
                matched_via=input_normalized,
            )

        # Step 4: Mascot-stripped match
        input_stripped = self._strip_mascot(input_clean)

        if input_stripped in self._canonical_lower:
            canonical = self._canonical_lower[input_stripped]
            self.stats[ResolutionStep.MASCOT_STRIPPED] += 1
            return ResolutionResult(
                input_name=input_clean,
                canonical_name=canonical,
                step_used=ResolutionStep.MASCOT_STRIPPED,
                matched_via=input_stripped,
            )

        if input_stripped in self._canonical_mascot_stripped:
            canonical = self._canonical_mascot_stripped[input_stripped]
            self.stats[ResolutionStep.MASCOT_STRIPPED] += 1
            return ResolutionResult(
                input_name=input_clean,
                canonical_name=canonical,
                step_used=ResolutionStep.MASCOT_STRIPPED,
                matched_via=input_stripped,
            )

        if input_stripped in self._alias_mascot_stripped:
            canonical = self._alias_mascot_stripped[input_stripped]
            self.stats[ResolutionStep.MASCOT_STRIPPED] += 1
            return ResolutionResult(
                input_name=input_clean,
                canonical_name=canonical,
                step_used=ResolutionStep.MASCOT_STRIPPED,
                matched_via=input_stripped,
            )

        # No match found - NEVER guess (no fuzzy matching!)
        self.stats[ResolutionStep.UNRESOLVED] += 1
        return ResolutionResult(
            input_name=input_clean,
            canonical_name=None,
            step_used=ResolutionStep.UNRESOLVED,
        )

    def resolve_or_raise(self, input_name: str) -> str:
        """
        Resolve team name or raise ValueError if unresolved.

        Use this when team resolution is mandatory (e.g., for predictions).
        """
        result = self.resolve(input_name)
        if not result.resolved:
            raise ValueError(f"Could not resolve team name: '{input_name}'")
        return result.canonical_name

    def get_stats(self) -> dict:
        """Get resolution statistics."""
        total = sum(self.stats.values())
        return {
            "total_resolutions": total,
            "by_step": {k.value: v for k, v in self.stats.items()},
            "success_rate": (total - self.stats[ResolutionStep.UNRESOLVED]) / total if total > 0 else 0,
        }

    def reset_stats(self) -> None:
        """Reset resolution statistics."""
        for key in self.stats:
            self.stats[key] = 0


# Singleton instance for convenience
_resolver: Optional[ProductionTeamResolver] = None


def get_resolver() -> ProductionTeamResolver:
    """Get singleton resolver instance."""
    global _resolver
    if _resolver is None:
        _resolver = ProductionTeamResolver()
    return _resolver


def resolve_team_name(input_name: str) -> Optional[str]:
    """
    Convenience function to resolve a team name.

    Returns canonical name or None if unresolved.
    """
    return get_resolver().resolve(input_name).canonical_name


def resolve_team_name_strict(input_name: str) -> str:
    """
    Resolve team name, raising ValueError if unresolved.
    """
    return get_resolver().resolve_or_raise(input_name)


# Self-test when run directly
if __name__ == "__main__":
    print("=" * 60)
    print("Production Team Resolver - Self Test")
    print("=" * 60)

    resolver = ProductionTeamResolver()

    # Test cases that SHOULD resolve
    should_resolve = [
        ("Duke", "Duke"),
        ("Duke Blue Devils", "Duke"),
        ("duke blue devils", "Duke"),
        ("UNC", "North Carolina"),
        ("North Carolina Tar Heels", "North Carolina"),
        ("Florida St.", "Florida St."),
        ("FSU", "Florida St."),
        ("Tennessee", "Tennessee"),
        ("Kentucky Wildcats", "Kentucky"),
        ("Texas A&M", "Texas A&M"),
        ("BYU", "BYU"),
        ("St. Mary's", "St. Mary's"),
        ("Miami FL", "Miami FL"),
        ("Miami (FL)", "Miami FL"),
        ("NC State", "NC State"),
        ("N.C. State", "NC State"),
    ]

    # Test cases that should NOT resolve (to prevent false positives)
    should_not_resolve = [
        "Made Up University",
        "Random Team Name",
        "Fake State Wildcats",
    ]

    print("\n--- Should Resolve ---")
    for input_name, expected in should_resolve:
        result = resolver.resolve(input_name)
        status = "✓" if result.canonical_name == expected else "✗"
        print(f"  {status} {result}")
        if result.canonical_name != expected:
            print(f"      Expected: {expected}")

    print("\n--- Should NOT Resolve (no fuzzy matching) ---")
    for input_name in should_not_resolve:
        result = resolver.resolve(input_name)
        status = "✓" if not result.resolved else "✗"
        print(f"  {status} {result}")

    print("\n--- Resolution Stats ---")
    stats = resolver.get_stats()
    print(f"  Total: {stats['total_resolutions']}")
    print(f"  By step: {stats['by_step']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
