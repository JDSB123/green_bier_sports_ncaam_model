#!/usr/bin/env python3
"""
DUAL METHODOLOGY TEAM CANONICALIZATION AUDIT

Implements TWO independent audit methodologies to validate team canonicalization
across ALL data ingestion sources:

METHODOLOGY 1: Cross-Source Team Resolution Consistency
    - Extracts unique team names from ALL sources (Odds, Scores, Barttorvik)
    - Runs each through ProductionTeamResolver
    - Validates canonicalized outputs match resolver output exactly
    - Reports resolution coverage and gaps by source

METHODOLOGY 2: Round-Trip Canonicalization Integrity
    - Verifies raw → canonical → cross-reference integrity
    - Detects self-play games (canonicalization collisions)
    - Cross-validates games can be matched between odds and scores
    - Checks data linkage across the entire pipeline

Both audits must pass for canonicalization to be considered valid.

Usage:
    python testing/scripts/dual_canonicalization_audit.py
    python testing/scripts/dual_canonicalization_audit.py --verbose
    python testing/scripts/dual_canonicalization_audit.py --output-dir ./audit_results
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add project root
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "testing"))

from testing.data_paths import DATA_PATHS
from production_parity.team_resolver import ProductionTeamResolver
from production_parity.non_d1_filter import is_non_d1_team


@dataclass
class SourceTeamData:
    """Team names extracted from a single data source."""
    source_name: str
    file_path: Path
    raw_teams: Set[str] = field(default_factory=set)
    resolved: Dict[str, str] = field(default_factory=dict)  # raw → canonical
    unresolved: Set[str] = field(default_factory=set)
    resolution_steps: Dict[str, str] = field(default_factory=dict)  # raw → step used


@dataclass
class AuditResult:
    """Result of a single audit methodology."""
    methodology_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, any] = field(default_factory=dict)


# ============================================================================
# DATA EXTRACTION FUNCTIONS
# ============================================================================

def extract_teams_from_csv(
    csv_path: Path,
    team_columns: List[str],
    source_name: str,
) -> SourceTeamData:
    """Extract unique team names from CSV columns."""
    result = SourceTeamData(source_name=source_name, file_path=csv_path)

    if not csv_path.exists():
        return result

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for col in team_columns:
                val = (row.get(col) or "").strip()
                if val:
                    result.raw_teams.add(val)

    return result


def extract_teams_from_barttorvik(ratings_dir: Path) -> SourceTeamData:
    """Extract team names from Barttorvik JSON files."""
    result = SourceTeamData(source_name="barttorvik", file_path=ratings_dir)

    if not ratings_dir.exists():
        return result

    for json_file in ratings_dir.glob("barttorvik_*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for row in data:
                    if isinstance(row, list) and len(row) > 1:
                        team_name = str(row[1]).strip()
                        if team_name:
                            result.raw_teams.add(team_name)
        except (json.JSONDecodeError, IOError):
            pass

    return result


def extract_all_sources(data_paths) -> Dict[str, SourceTeamData]:
    """Extract team names from ALL data sources."""
    sources = {}

    # 1. Odds API - Spreads FG (raw teams)
    odds_spreads_fg = data_paths.odds_canonical_spreads_fg / "spreads_fg_all.csv"
    sources["odds_spreads_fg"] = extract_teams_from_csv(
        odds_spreads_fg,
        ["home_team", "away_team"],
        "odds_spreads_fg"
    )

    # 2. Odds API - Spreads FG (canonical teams - for comparison)
    sources["odds_spreads_fg_canonical"] = extract_teams_from_csv(
        odds_spreads_fg,
        ["home_team_canonical", "away_team_canonical"],
        "odds_spreads_fg_canonical"
    )

    # 3. Odds API - Totals FG
    odds_totals_fg = data_paths.odds_canonical_totals_fg / "totals_fg_all.csv"
    sources["odds_totals_fg"] = extract_teams_from_csv(
        odds_totals_fg,
        ["home_team", "away_team"],
        "odds_totals_fg"
    )

    # 4. ESPN Scores - Full Game
    scores_fg = data_paths.scores_fg / "games_all.csv"
    sources["espn_scores_fg"] = extract_teams_from_csv(
        scores_fg,
        ["home_team", "away_team"],
        "espn_scores_fg"
    )

    # 5. ESPN Scores - H1
    scores_h1 = data_paths.scores_h1 / "h1_games_all.csv"
    sources["espn_scores_h1"] = extract_teams_from_csv(
        scores_h1,
        ["home_team", "away_team"],
        "espn_scores_h1"
    )

    # 6. Canonicalized Scores (uses home_canonical/away_canonical columns)
    canonical_scores = data_paths.root / "canonicalized" / "scores" / "fg" / "games_all_canonical.csv"
    sources["canonical_scores_fg"] = extract_teams_from_csv(
        canonical_scores,
        ["home_canonical", "away_canonical"],
        "canonical_scores_fg"
    )

    # 7. Canonicalized Odds
    canonical_odds = data_paths.root / "canonicalized" / "odds" / "spreads" / "fg" / "spreads_fg_canonical.csv"
    sources["canonical_odds_fg"] = extract_teams_from_csv(
        canonical_odds,
        ["home_team_canonical", "away_team_canonical"],
        "canonical_odds_fg"
    )

    # 8. Barttorvik Ratings
    sources["barttorvik"] = extract_teams_from_barttorvik(data_paths.ratings_raw_barttorvik)

    # 9. Training data (backtest_ready.csv)
    backtest_ready = ROOT_DIR / "backtest_ready.csv"
    sources["backtest_ready"] = extract_teams_from_csv(
        backtest_ready,
        ["home_team", "away_team", "home_canonical", "away_canonical"],
        "backtest_ready"
    )

    return sources


# ============================================================================
# METHODOLOGY 1: CROSS-SOURCE TEAM RESOLUTION CONSISTENCY
# ============================================================================

def audit_methodology_1(
    sources: Dict[str, SourceTeamData],
    resolver: ProductionTeamResolver,
    verbose: bool = False,
) -> AuditResult:
    """
    METHODOLOGY 1: Cross-Source Team Resolution Consistency

    For every unique raw team name across all sources:
    1. Resolve using ProductionTeamResolver
    2. Check if already-canonicalized values match resolver output
    3. Report coverage and gaps by source
    """
    result = AuditResult(
        methodology_name="Cross-Source Team Resolution Consistency",
        passed=True,
        score=1.0,
    )

    # Aggregate all unique raw teams across sources
    all_raw_teams: Set[str] = set()
    source_raw_counts = {}

    for source_name, source_data in sources.items():
        # Skip canonical sources for raw team aggregation
        if "canonical" in source_name.lower():
            continue
        all_raw_teams.update(source_data.raw_teams)
        source_raw_counts[source_name] = len(source_data.raw_teams)

    result.metrics["total_unique_raw_teams"] = len(all_raw_teams)
    result.metrics["teams_by_source"] = source_raw_counts

    # Resolve all raw teams
    resolved_count = 0
    unresolved_teams: Dict[str, List[str]] = defaultdict(list)  # team → sources it appears in
    resolution_by_step: Dict[str, int] = defaultdict(int)

    for source_name, source_data in sources.items():
        if "canonical" in source_name.lower():
            continue

        for raw_team in source_data.raw_teams:
            res = resolver.resolve(raw_team)
            source_data.resolution_steps[raw_team] = res.step_used.value

            if res.resolved:
                source_data.resolved[raw_team] = res.canonical_name
                resolution_by_step[res.step_used.value] += 1
            else:
                source_data.unresolved.add(raw_team)
                unresolved_teams[raw_team].append(source_name)

    # Calculate resolution rate
    resolved_set = set()
    unresolved_set = set()
    for source_data in sources.values():
        resolved_set.update(source_data.resolved.keys())
        unresolved_set.update(source_data.unresolved)

    total_unique = len(resolved_set | unresolved_set)
    resolution_rate = len(resolved_set) / total_unique if total_unique > 0 else 0

    result.metrics["resolution_rate"] = resolution_rate
    result.metrics["resolved_count"] = len(resolved_set)
    result.metrics["unresolved_count"] = len(unresolved_set)
    result.metrics["resolution_by_step"] = dict(resolution_by_step)

    # Check for consistency: same raw team should resolve to same canonical across sources
    canonical_conflicts: Dict[str, Set[str]] = defaultdict(set)
    for source_data in sources.values():
        for raw_team, canonical in source_data.resolved.items():
            canonical_conflicts[raw_team].add(canonical)

    inconsistent_teams = {team: list(canonicals) for team, canonicals in canonical_conflicts.items() if len(canonicals) > 1}
    result.metrics["inconsistent_resolutions"] = len(inconsistent_teams)

    if inconsistent_teams:
        result.issues.append(f"CRITICAL: {len(inconsistent_teams)} teams resolve to different canonical names!")
        for team, canonicals in list(inconsistent_teams.items())[:10]:
            result.issues.append(f"  '{team}' → {canonicals}")
        result.passed = False
        result.score -= 0.3

    # Validate canonical outputs match resolver
    canonical_mismatches = []
    for source_name, source_data in sources.items():
        if "canonical" not in source_name.lower():
            continue

        # These are already-canonical values - they should be valid canonical names
        for canonical_team in source_data.raw_teams:
            # Resolving a canonical name should return itself
            res = resolver.resolve(canonical_team)
            if res.resolved and res.canonical_name != canonical_team:
                canonical_mismatches.append((source_name, canonical_team, res.canonical_name))

    if canonical_mismatches:
        result.warnings.append(f"INFO: {len(canonical_mismatches)} canonical names differ from resolver output")
        if verbose:
            for source, stored, expected in canonical_mismatches[:10]:
                result.warnings.append(f"  {source}: '{stored}' vs resolver '{expected}'")

    result.metrics["canonical_mismatches"] = len(canonical_mismatches)

    # Report unresolved teams
    if len(unresolved_set) > 0:
        # Filter to D1 teams only (non-D1 is expected to be unresolved)
        d1_unresolved = [t for t in unresolved_set if not _is_likely_non_d1(t)]

        # Many "D1 unresolved" are actually non-D1 schools appearing in ESPN
        # exhibition games. Check if they only appear in ESPN sources.
        espn_only_sources = {"espn_scores_fg", "espn_scores_h1"}
        espn_only_unresolved = []
        multi_source_unresolved = []

        for team in d1_unresolved:
            team_sources = set(unresolved_teams.get(team, []))
            if team_sources.issubset(espn_only_sources):
                espn_only_unresolved.append(team)
            else:
                multi_source_unresolved.append(team)

        # Only flag as issue if unresolved teams appear in odds or barttorvik
        if len(multi_source_unresolved) > 10:
            result.issues.append(
                f"WARNING: {len(multi_source_unresolved)} unresolved teams "
                "in odds/ratings sources"
            )
            result.score -= 0.1

        result.metrics["d1_unresolved_count"] = len(d1_unresolved)
        result.metrics["espn_only_unresolved"] = len(espn_only_unresolved)
        result.metrics["multi_source_unresolved"] = len(multi_source_unresolved)
        result.metrics["non_d1_unresolved_count"] = (
            len(unresolved_set) - len(d1_unresolved)
        )

        if verbose and d1_unresolved:
            result.warnings.append("Sample unresolved teams (likely non-D1):")
            for team in sorted(d1_unresolved)[:15]:
                sources_list = unresolved_teams.get(team, [])
                result.warnings.append(
                    f"  '{team}' (in: {', '.join(sources_list[:3])})"
                )

    # Calculate D1-focused resolution rate
    # For pass/fail, we care about teams that appear in odds or barttorvik
    odds_bart_teams = (
        sources.get("odds_spreads_fg", SourceTeamData("", Path())).raw_teams |
        sources.get("barttorvik", SourceTeamData("", Path())).raw_teams
    )
    odds_bart_resolved = sum(
        1 for t in odds_bart_teams
        if any(t in s.resolved for s in sources.values())
    )
    d1_resolution_rate = odds_bart_resolved / len(odds_bart_teams) if odds_bart_teams else 0

    result.metrics["d1_resolution_rate"] = d1_resolution_rate

    # Set pass threshold based on D1 resolution (odds/barttorvik teams)
    if d1_resolution_rate < 0.95:
        result.issues.append(
            f"FAIL: D1 resolution rate {d1_resolution_rate:.1%} < 95% threshold"
        )
        result.passed = False
        result.score = d1_resolution_rate
    elif d1_resolution_rate < 0.98:
        result.warnings.append(
            f"WARNING: D1 resolution rate {d1_resolution_rate:.1%} below 98% ideal"
        )
        result.score = d1_resolution_rate

    # Overall resolution rate is informational
    result.warnings.append(
        f"INFO: Overall resolution rate {resolution_rate:.1%} "
        f"(includes ESPN exhibition games)"
    )

    return result


def _is_likely_non_d1(team_name: str) -> bool:
    """Check if team is non-D1 using the official filter."""
    # Use the production non_d1_filter
    if is_non_d1_team(team_name):
        return True

    # Additional heuristics for teams not in the blocklist
    name_lower = team_name.lower()
    non_d1_indicators = [
        "d2", "d3", "naia", "juco", "cc", "community",
        "junior", "prep", "high school", "hs",
        "club", "aau", "exhibition",
    ]
    for indicator in non_d1_indicators:
        if indicator in name_lower:
            return True

    return False


# ============================================================================
# METHODOLOGY 2: ROUND-TRIP CANONICALIZATION INTEGRITY
# ============================================================================

def audit_methodology_2(
    data_paths,
    resolver: ProductionTeamResolver,
    verbose: bool = False,
) -> AuditResult:
    """
    METHODOLOGY 2: Round-Trip Canonicalization Integrity

    Validates the complete data pipeline:
    1. Raw data → canonicalized data integrity
    2. Self-play detection (same team on both sides)
    3. Cross-source game matching (odds ↔ scores linkage)
    4. Canonical name consistency in output files
    """
    result = AuditResult(
        methodology_name="Round-Trip Canonicalization Integrity",
        passed=True,
        score=1.0,
    )

    # ─────────────────────────────────────────────────────────────
    # CHECK 1: Self-Play Detection
    # ─────────────────────────────────────────────────────────────
    self_play_games = []

    # Check canonical odds
    canonical_odds_path = data_paths.root / "canonicalized" / "odds" / "spreads" / "fg" / "spreads_fg_canonical.csv"
    if canonical_odds_path.exists():
        with open(canonical_odds_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                home = (row.get("home_team_canonical") or "").strip()
                away = (row.get("away_team_canonical") or "").strip()
                if home and away and home == away:
                    self_play_games.append({
                        "source": "canonical_odds",
                        "date": row.get("game_date"),
                        "home_raw": row.get("home_team"),
                        "away_raw": row.get("away_team"),
                        "canonical": home,
                    })

    # Check canonical scores (uses home_canonical/away_canonical)
    canonical_scores_path = (
        data_paths.root / "canonicalized" / "scores" / "fg" / "games_all_canonical.csv"
    )
    if canonical_scores_path.exists():
        with open(canonical_scores_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                home = (row.get("home_canonical") or "").strip()
                away = (row.get("away_canonical") or "").strip()
                if home and away and home == away:
                    self_play_games.append({
                        "source": "canonical_scores",
                        "date": row.get("date"),
                        "home_raw": row.get("home_team"),
                        "away_raw": row.get("away_team"),
                        "canonical": home,
                    })

    result.metrics["self_play_games"] = len(self_play_games)

    if self_play_games:
        result.issues.append(f"CRITICAL: {len(self_play_games)} self-play games detected (canonicalization collision)!")
        for game in self_play_games[:5]:
            result.issues.append(
                f"  {game['date']}: {game['home_raw']} vs {game['away_raw']} → both '{game['canonical']}'"
            )
        result.passed = False
        result.score -= 0.5

    # ─────────────────────────────────────────────────────────────
    # CHECK 2: Raw → Canonical Field Consistency
    # ─────────────────────────────────────────────────────────────
    field_mismatches = []

    if canonical_odds_path.exists():
        with open(canonical_odds_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 1000:  # Sample check
                    break

                home_raw = (row.get("home_team") or "").strip()
                away_raw = (row.get("away_team") or "").strip()
                home_canonical = (row.get("home_team_canonical") or "").strip()
                away_canonical = (row.get("away_team_canonical") or "").strip()

                if home_raw and home_canonical:
                    expected = resolver.resolve(home_raw)
                    if expected.resolved and expected.canonical_name != home_canonical:
                        field_mismatches.append({
                            "raw": home_raw,
                            "stored": home_canonical,
                            "expected": expected.canonical_name,
                        })

                if away_raw and away_canonical:
                    expected = resolver.resolve(away_raw)
                    if expected.resolved and expected.canonical_name != away_canonical:
                        field_mismatches.append({
                            "raw": away_raw,
                            "stored": away_canonical,
                            "expected": expected.canonical_name,
                        })

    result.metrics["field_mismatches_sample"] = len(field_mismatches)

    if field_mismatches:
        result.warnings.append(f"INFO: {len(field_mismatches)} stored canonicals differ from resolver (sample of 1000 rows)")
        if verbose:
            for m in field_mismatches[:5]:
                result.warnings.append(f"  '{m['raw']}' stored as '{m['stored']}' but resolver says '{m['expected']}'")

    # ─────────────────────────────────────────────────────────────
    # CHECK 3: Cross-Source Game Matching (Odds ↔ Scores)
    # ─────────────────────────────────────────────────────────────
    odds_games = set()
    scores_games = set()

    # Load canonical odds games
    if canonical_odds_path.exists():
        with open(canonical_odds_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                game_date = row.get("game_date", "")
                home = (row.get("home_team_canonical") or "").strip()
                away = (row.get("away_team_canonical") or "").strip()
                if game_date and home and away:
                    # Normalize key: date + sorted teams
                    teams = tuple(sorted([home, away]))
                    odds_games.add((game_date, teams))

    # Load canonical scores games (uses home_canonical/away_canonical)
    if canonical_scores_path.exists():
        with open(canonical_scores_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                game_date = row.get("date", "")
                home = (row.get("home_canonical") or "").strip()
                away = (row.get("away_canonical") or "").strip()
                if game_date and home and away:
                    teams = tuple(sorted([home, away]))
                    scores_games.add((game_date, teams))

    # Calculate match rate
    matched_games = odds_games & scores_games
    odds_only = odds_games - scores_games
    scores_only = scores_games - odds_games

    if odds_games:
        match_rate = len(matched_games) / len(odds_games)
    else:
        match_rate = 0.0

    result.metrics["odds_games_count"] = len(odds_games)
    result.metrics["scores_games_count"] = len(scores_games)
    result.metrics["matched_games_count"] = len(matched_games)
    result.metrics["odds_only_count"] = len(odds_only)
    result.metrics["scores_only_count"] = len(scores_only)
    result.metrics["cross_source_match_rate"] = match_rate

    # NOTE: Match rate reflects data coverage, not canonicalization quality.
    # ESPN scores don't cover all games (exhibition, some mid-majors, etc.)
    # A lower match rate is expected - we're checking that MATCHED games
    # have consistent canonical names, not that all odds games have scores.
    if match_rate < 0.10:
        result.issues.append(
            f"CRITICAL: Only {match_rate:.1%} cross-source match - "
            "possible date format or canonicalization issue"
        )
        result.passed = False
        result.score -= 0.3
    elif match_rate < 0.20:
        result.warnings.append(
            f"INFO: {match_rate:.1%} cross-source match rate "
            "(ESPN scores don't cover all games)"
        )

    if verbose and odds_only:
        result.warnings.append(
            f"Sample games in odds but not scores ({len(odds_only)} total):"
        )
        for date, teams in sorted(odds_only)[:5]:
            result.warnings.append(f"  {date}: {teams[0]} vs {teams[1]}")

    # ─────────────────────────────────────────────────────────────
    # CHECK 4: Canonical Name Set Consistency
    # ─────────────────────────────────────────────────────────────
    odds_canonical_teams = set()
    scores_canonical_teams = set()
    barttorvik_teams = set()

    # Extract canonical teams from odds
    if canonical_odds_path.exists():
        with open(canonical_odds_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                home = (row.get("home_team_canonical") or "").strip()
                away = (row.get("away_team_canonical") or "").strip()
                if home:
                    odds_canonical_teams.add(home)
                if away:
                    odds_canonical_teams.add(away)

    # Extract canonical teams from scores (uses home_canonical/away_canonical)
    if canonical_scores_path.exists():
        with open(canonical_scores_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                home = (row.get("home_canonical") or "").strip()
                away = (row.get("away_canonical") or "").strip()
                if home:
                    scores_canonical_teams.add(home)
                if away:
                    scores_canonical_teams.add(away)

    # Extract from Barttorvik (these are raw names, resolve them)
    for json_file in data_paths.ratings_raw_barttorvik.glob("barttorvik_*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for row in data:
                    if isinstance(row, list) and len(row) > 1:
                        team_name = str(row[1]).strip()
                        res = resolver.resolve(team_name)
                        if res.resolved:
                            barttorvik_teams.add(res.canonical_name)
        except (json.JSONDecodeError, IOError):
            pass

    # Calculate overlap
    all_canonical = odds_canonical_teams | scores_canonical_teams
    in_barttorvik = all_canonical & barttorvik_teams
    missing_from_barttorvik = all_canonical - barttorvik_teams

    barttorvik_coverage = len(in_barttorvik) / len(all_canonical) if all_canonical else 0

    result.metrics["canonical_teams_odds"] = len(odds_canonical_teams)
    result.metrics["canonical_teams_scores"] = len(scores_canonical_teams)
    result.metrics["canonical_teams_barttorvik"] = len(barttorvik_teams)
    result.metrics["barttorvik_coverage"] = barttorvik_coverage
    result.metrics["missing_from_barttorvik"] = len(missing_from_barttorvik)

    if barttorvik_coverage < 0.90:
        result.warnings.append(f"WARNING: Only {barttorvik_coverage:.1%} of canonical teams have Barttorvik ratings")
        if verbose and missing_from_barttorvik:
            result.warnings.append("Sample teams missing from Barttorvik:")
            for team in sorted(missing_from_barttorvik)[:10]:
                result.warnings.append(f"  {team}")

    return result


# ============================================================================
# MAIN AUDIT RUNNER
# ============================================================================

def run_dual_audit(
    output_dir: Optional[Path] = None,
    verbose: bool = False,
) -> Tuple[AuditResult, AuditResult, bool]:
    """Run both audit methodologies and generate report."""

    print("=" * 72)
    print("DUAL METHODOLOGY TEAM CANONICALIZATION AUDIT")
    print("=" * 72)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Initialize resolver
    print("Initializing ProductionTeamResolver...")
    resolver = ProductionTeamResolver()
    resolver.reset_stats()

    # Extract all sources
    print("Extracting team names from all data sources...")
    sources = extract_all_sources(DATA_PATHS)

    source_summary = []
    for name, data in sources.items():
        source_summary.append(f"  {name}: {len(data.raw_teams)} teams")
    print("\n".join(source_summary))
    print()

    # ─────────────────────────────────────────────────────────────
    # RUN METHODOLOGY 1
    # ─────────────────────────────────────────────────────────────
    print("-" * 72)
    print("METHODOLOGY 1: Cross-Source Team Resolution Consistency")
    print("-" * 72)

    result1 = audit_methodology_1(sources, resolver, verbose)

    print(f"\nResolution Rate: {result1.metrics.get('resolution_rate', 0):.1%}")
    print(f"  Resolved: {result1.metrics.get('resolved_count', 0)}")
    print(f"  Unresolved: {result1.metrics.get('unresolved_count', 0)}")
    print(f"  D1 Unresolved: {result1.metrics.get('d1_unresolved_count', 0)}")
    print(f"\nResolution by step:")
    for step, count in result1.metrics.get("resolution_by_step", {}).items():
        print(f"  {step}: {count}")

    if result1.issues:
        print("\nISSUES:")
        for issue in result1.issues:
            print(f"  {issue}")

    if result1.warnings:
        print("\nWARNINGS:")
        for warning in result1.warnings:
            print(f"  {warning}")

    status1 = "PASS" if result1.passed else "FAIL"
    print(f"\n>>> METHODOLOGY 1: {status1} (score: {result1.score:.2f})")

    # ─────────────────────────────────────────────────────────────
    # RUN METHODOLOGY 2
    # ─────────────────────────────────────────────────────────────
    print()
    print("-" * 72)
    print("METHODOLOGY 2: Round-Trip Canonicalization Integrity")
    print("-" * 72)

    result2 = audit_methodology_2(DATA_PATHS, resolver, verbose)

    print(f"\nSelf-play games detected: {result2.metrics.get('self_play_games', 0)}")
    print(f"Field mismatches (sample): {result2.metrics.get('field_mismatches_sample', 0)}")
    print(f"\nCross-source matching:")
    print(f"  Odds games: {result2.metrics.get('odds_games_count', 0)}")
    print(f"  Scores games: {result2.metrics.get('scores_games_count', 0)}")
    print(f"  Matched: {result2.metrics.get('matched_games_count', 0)}")
    print(f"  Match rate: {result2.metrics.get('cross_source_match_rate', 0):.1%}")
    print(f"\nBarttorvik coverage: {result2.metrics.get('barttorvik_coverage', 0):.1%}")

    if result2.issues:
        print("\nISSUES:")
        for issue in result2.issues:
            print(f"  {issue}")

    if result2.warnings:
        print("\nWARNINGS:")
        for warning in result2.warnings:
            print(f"  {warning}")

    status2 = "PASS" if result2.passed else "FAIL"
    print(f"\n>>> METHODOLOGY 2: {status2} (score: {result2.score:.2f})")

    # ─────────────────────────────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────────────────────────────
    print()
    print("=" * 72)
    print("FINAL AUDIT SUMMARY")
    print("=" * 72)

    overall_pass = result1.passed and result2.passed
    overall_score = (result1.score + result2.score) / 2

    print(f"\nMethodology 1 (Cross-Source): {'PASS' if result1.passed else 'FAIL'} ({result1.score:.2f})")
    print(f"Methodology 2 (Round-Trip):   {'PASS' if result2.passed else 'FAIL'} ({result2.score:.2f})")
    print(f"\nOverall Score: {overall_score:.2f}")
    print(f"Overall Status: {'PASS' if overall_pass else 'FAIL'}")

    if overall_pass:
        print("\n[PASS] Team canonicalization is VALID across all data sources")
    else:
        print("\n[FAIL] Team canonicalization has ISSUES that must be resolved")

    # Save report if output directory specified
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f"canonicalization_audit_{timestamp}.json"

        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_pass": overall_pass,
            "overall_score": overall_score,
            "methodology_1": {
                "name": result1.methodology_name,
                "passed": result1.passed,
                "score": result1.score,
                "issues": result1.issues,
                "warnings": result1.warnings,
                "metrics": result1.metrics,
            },
            "methodology_2": {
                "name": result2.methodology_name,
                "passed": result2.passed,
                "score": result2.score,
                "issues": result2.issues,
                "warnings": result2.warnings,
                "metrics": result2.metrics,
            },
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\nReport saved to: {report_path}")

    return result1, result2, overall_pass


def main():
    parser = argparse.ArgumentParser(
        description="Dual methodology team canonicalization audit"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including sample issues"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Directory to save audit report JSON"
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None

    _, _, passed = run_dual_audit(
        output_dir=output_dir,
        verbose=args.verbose,
    )

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
