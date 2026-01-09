#!/usr/bin/env python3
"""
CROSS-SOURCE COVERAGE VALIDATION

Validates that every ESPN game has complete data coverage across all sources:
1. Barttorvik ratings exist for BOTH teams on game_date
2. Odds API lines exist (spreads, totals) by date + canonicalized teams
3. H1 scores exist (linked by game_id from FG scores)

This is the pre-backtest gate to ensure no missing data causes silent failures.

KNOWN GAPS (documented, not failures):
- Odds API has NO data before Nov 2020 (seasons 2019-2020)
- H1 odds unavailable for seasons 2021-2023
- Incomplete FG odds for season 2022-2023

Usage:
    python testing/scripts/validate_cross_source_coverage.py
    python testing/scripts/validate_cross_source_coverage.py --season 2025
    python testing/scripts/validate_cross_source_coverage.py --output-json manifests/coverage_gaps.json
    python testing/scripts/validate_cross_source_coverage.py --fail-on-unexpected  # CI mode
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Add project root
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "testing"))

from testing.data_paths import DATA_PATHS
from production_parity.team_resolver import ProductionTeamResolver


# ============================================================================
# KNOWN GAPS (Expected - don't fail on these)
# ============================================================================

KNOWN_ODDS_GAPS = {
    2019: "Odds API has no data before Nov 2020",
    2020: "Odds API has no data before Nov 2020",
    # 2021-2023 have partial FG odds but no H1 odds
}

KNOWN_H1_ODDS_GAPS = {
    2021: "H1 odds unavailable historically",
    2022: "H1 odds unavailable historically",
    2023: "H1 odds unavailable historically",
}

# Teams with known incomplete odds coverage (transitional D1, small programs, D2 opponents, etc.)
KNOWN_ODDS_INCOMPLETE_TEAMS = {
    "East Texas A&M",  # Transitional D1 program (formerly D2)
    "LIU",  # Long Island University - small D1 program with limited odds coverage
    "Mercyhurst",  # Transitional D1 program
    "UIC",  # Occasional missing odds for non-marquee games
    "New Haven",  # D2 school - appears in ESPN D1 schedule for exhibition/cross-level games
}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class GameCoverage:
    """Coverage status for a single game."""
    game_id: str
    date: str
    season: int
    home_team: str
    away_team: str
    home_canonical: Optional[str] = None
    away_canonical: Optional[str] = None
    # Coverage flags
    has_fg_score: bool = True  # Always true (source is FG scores)
    has_h1_score: bool = False
    has_fg_odds: bool = False
    has_h1_odds: bool = False
    has_home_ratings: bool = False
    has_away_ratings: bool = False
    # Gap reasons
    gap_reasons: List[str] = field(default_factory=list)


@dataclass
class SeasonCoverage:
    """Aggregate coverage for a season."""
    season: int
    total_games: int = 0
    games_with_h1_scores: int = 0
    games_with_fg_odds: int = 0
    games_with_h1_odds: int = 0
    games_with_ratings: int = 0
    games_fully_covered: int = 0
    gap_games: List[GameCoverage] = field(default_factory=list)


@dataclass 
class CoverageReport:
    """Full coverage validation report."""
    timestamp: str
    passed: bool
    seasons: Dict[int, SeasonCoverage] = field(default_factory=dict)
    summary: Dict[str, any] = field(default_factory=dict)
    unexpected_gaps: List[GameCoverage] = field(default_factory=list)


# ============================================================================
# DATA LOADERS
# ============================================================================

def load_fg_scores(data_paths) -> Dict[str, GameCoverage]:
    """Load full-game scores as the base game inventory."""
    games = {}
    scores_file = data_paths.scores_fg / "games_all.csv"
    
    if not scores_file.exists():
        print(f"ERROR: FG scores not found: {scores_file}")
        return games
    
    with open(scores_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            game_id = row.get("game_id", "")
            date = row.get("date", "")
            
            # Calculate season (Nov+ = next year)
            try:
                dt = datetime.fromisoformat(date)
                season = dt.year + 1 if dt.month >= 11 else dt.year
            except (ValueError, TypeError):
                season = 0
            
            games[game_id] = GameCoverage(
                game_id=game_id,
                date=date,
                season=season,
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                has_fg_score=True,
            )
    
    print(f"  Loaded {len(games):,} FG games from scores")
    return games


def load_h1_scores(data_paths) -> Set[str]:
    """Load H1 scores - returns set of game_ids that have H1 data."""
    h1_game_ids = set()
    h1_file = data_paths.scores_h1 / "h1_games_all.csv"
    
    if not h1_file.exists():
        print(f"  WARNING: H1 scores not found: {h1_file}")
        return h1_game_ids
    
    with open(h1_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            game_id = row.get("game_id", "")
            if game_id:
                h1_game_ids.add(game_id)
    
    print(f"  Loaded {len(h1_game_ids):,} H1 scores")
    return h1_game_ids


def load_odds(data_paths, resolver: ProductionTeamResolver) -> Tuple[Set[str], Set[str]]:
    """
    Load odds data - returns sets of (date|home_canonical|away_canonical) keys
    for FG and H1 markets.
    """
    fg_odds_keys = set()
    h1_odds_keys = set()
    
    # Load FG spreads (canonical)
    fg_spreads_file = data_paths.odds_canonical_spreads_fg / "spreads_fg_all.csv"
    if fg_spreads_file.exists():
        with open(fg_spreads_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Use canonical columns if available
                home = row.get("home_team_canonical") or row.get("home_team", "")
                away = row.get("away_team_canonical") or row.get("away_team", "")
                date = row.get("game_date", "")
                
                if home and away and date:
                    # Resolve to ensure canonical
                    home_res = resolver.resolve(home)
                    away_res = resolver.resolve(away)
                    if home_res.resolved and away_res.resolved:
                        key = f"{date}|{home_res.canonical_name}|{away_res.canonical_name}"
                        fg_odds_keys.add(key)
    
    print(f"  Loaded {len(fg_odds_keys):,} FG odds matchups")
    
    # Load H1 spreads (canonical)
    h1_spreads_file = data_paths.odds_canonical_spreads_h1 / "spreads_h1_all.csv"
    if h1_spreads_file.exists():
        with open(h1_spreads_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                home = row.get("home_team_canonical") or row.get("home_team", "")
                away = row.get("away_team_canonical") or row.get("away_team", "")
                date = row.get("game_date", "")
                
                if home and away and date:
                    home_res = resolver.resolve(home)
                    away_res = resolver.resolve(away)
                    if home_res.resolved and away_res.resolved:
                        key = f"{date}|{home_res.canonical_name}|{away_res.canonical_name}"
                        h1_odds_keys.add(key)
    
    print(f"  Loaded {len(h1_odds_keys):,} H1 odds matchups")
    
    return fg_odds_keys, h1_odds_keys


def load_barttorvik_teams(data_paths, resolver: ProductionTeamResolver) -> Dict[int, Set[str]]:
    """
    Load Barttorvik team names by season, resolving to canonical names.
    Returns {season: set(canonical_team_names)}
    
    This is critical because Barttorvik uses names like "Mississippi" while
    ESPN uses "Ole Miss" - we need to compare canonical-to-canonical.
    """
    teams_by_season: Dict[int, Set[str]] = defaultdict(set)
    ratings_dir = data_paths.ratings_raw_barttorvik
    
    if not ratings_dir.exists():
        print(f"  WARNING: Barttorvik ratings not found: {ratings_dir}")
        return teams_by_season
    
    unresolved_bt_teams = set()
    
    for json_file in ratings_dir.glob("barttorvik_*.json"):
        # Extract season from filename: barttorvik_2024.json → 2024
        try:
            season = int(json_file.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for row in data:
                if isinstance(row, list) and len(row) > 1:
                    team_name = str(row[1]).strip()
                    if team_name:
                        # Resolve to canonical name for proper matching
                        result = resolver.resolve(team_name)
                        if result.resolved:
                            teams_by_season[season].add(result.canonical_name)
                        else:
                            unresolved_bt_teams.add(team_name)
                            # Still add raw name as fallback
                            teams_by_season[season].add(team_name)
    
    total_teams = sum(len(t) for t in teams_by_season.values())
    print(f"  Loaded {total_teams:,} team-seasons from Barttorvik ({len(teams_by_season)} seasons)")
    
    if unresolved_bt_teams:
        print(f"  WARNING: {len(unresolved_bt_teams)} Barttorvik teams did not resolve")
    
    return teams_by_season


# ============================================================================
# COVERAGE VALIDATION
# ============================================================================

def validate_coverage(
    games: Dict[str, GameCoverage],
    h1_game_ids: Set[str],
    fg_odds_keys: Set[str],
    h1_odds_keys: Set[str],
    barttorvik_teams: Dict[int, Set[str]],
    resolver: ProductionTeamResolver,
) -> CoverageReport:
    """
    Validate coverage for all games across all sources.
    """
    report = CoverageReport(
        timestamp=datetime.now().isoformat(),
        passed=True,
    )
    
    seasons_data: Dict[int, SeasonCoverage] = defaultdict(lambda: SeasonCoverage(season=0))
    
    for game_id, game in games.items():
        season = game.season
        seasons_data[season].season = season
        seasons_data[season].total_games += 1
        
        # Canonicalize team names
        home_res = resolver.resolve(game.home_team)
        away_res = resolver.resolve(game.away_team)
        game.home_canonical = home_res.canonical_name
        game.away_canonical = away_res.canonical_name
        
        # Skip non-D1 games
        if not home_res.resolved or not away_res.resolved:
            continue
        
        # Check H1 scores
        game.has_h1_score = game_id in h1_game_ids
        if game.has_h1_score:
            seasons_data[season].games_with_h1_scores += 1
        
        # Check FG odds (by date + canonical teams)
        # Use +/- 1 day fuzzy matching to handle timezone discrepancies
        # (e.g., late games that start before midnight UTC but show as next day in ESPN)
        try:
            game_date = datetime.strptime(game.date, "%Y-%m-%d")
            date_minus_1 = (game_date - timedelta(days=1)).strftime("%Y-%m-%d")
            date_plus_1 = (game_date + timedelta(days=1)).strftime("%Y-%m-%d")
            dates_to_check = [game.date, date_minus_1, date_plus_1]
        except ValueError:
            dates_to_check = [game.date]
        
        game.has_fg_odds = False
        for check_date in dates_to_check:
            odds_key = f"{check_date}|{game.home_canonical}|{game.away_canonical}"
            odds_key_rev = f"{check_date}|{game.away_canonical}|{game.home_canonical}"
            if odds_key in fg_odds_keys or odds_key_rev in fg_odds_keys:
                game.has_fg_odds = True
                break
        
        if game.has_fg_odds:
            seasons_data[season].games_with_fg_odds += 1
        
        # Check H1 odds (also with +/- 1 day fuzzy matching)
        game.has_h1_odds = False
        for check_date in dates_to_check:
            odds_key = f"{check_date}|{game.home_canonical}|{game.away_canonical}"
            odds_key_rev = f"{check_date}|{game.away_canonical}|{game.home_canonical}"
            if odds_key in h1_odds_keys or odds_key_rev in h1_odds_keys:
                game.has_h1_odds = True
                break
        
        if game.has_h1_odds:
            seasons_data[season].games_with_h1_odds += 1
        
        # Check Barttorvik ratings
        # barttorvik_teams is already resolved to canonical names
        season_teams = barttorvik_teams.get(season, set())
        
        # Direct canonical comparison (Barttorvik teams were pre-resolved)
        home_in_bt = game.home_canonical in season_teams
        away_in_bt = game.away_canonical in season_teams
        
        game.has_home_ratings = home_in_bt
        game.has_away_ratings = away_in_bt
        
        if home_in_bt and away_in_bt:
            seasons_data[season].games_with_ratings += 1
        
        # Determine if fully covered
        fully_covered = (
            game.has_fg_score and
            game.has_h1_score and
            game.has_fg_odds and
            game.has_home_ratings and
            game.has_away_ratings
        )
        
        if fully_covered:
            seasons_data[season].games_fully_covered += 1
        else:
            # Record gap reasons
            if not game.has_h1_score:
                game.gap_reasons.append("missing_h1_score")
            if not game.has_fg_odds:
                # Check if this is a known gap
                if season in KNOWN_ODDS_GAPS:
                    game.gap_reasons.append(f"known_gap: {KNOWN_ODDS_GAPS[season]}")
                else:
                    game.gap_reasons.append("missing_fg_odds")
            if not game.has_h1_odds:
                if season in KNOWN_H1_ODDS_GAPS:
                    pass  # Don't flag known H1 gaps
                else:
                    game.gap_reasons.append("missing_h1_odds")
            if not game.has_home_ratings:
                game.gap_reasons.append(f"missing_ratings_home:{game.home_canonical}")
            if not game.has_away_ratings:
                game.gap_reasons.append(f"missing_ratings_away:{game.away_canonical}")
            
            # Is this an unexpected gap?
            # Check if the gap involves a team with known incomplete odds coverage
            has_incomplete_team = (
                game.home_canonical in KNOWN_ODDS_INCOMPLETE_TEAMS or
                game.away_canonical in KNOWN_ODDS_INCOMPLETE_TEAMS
            )
            
            # Only consider it unexpected if:
            # 1. There are gap reasons that aren't due to known incomplete teams
            # 2. The gap is not just missing odds for incomplete teams
            unexpected = False
            for reason in game.gap_reasons:
                if reason.startswith("missing_"):
                    # If it's an odds gap and we have an incomplete team, it's expected
                    if "odds" in reason and has_incomplete_team:
                        continue
                    # Otherwise it's unexpected
                    unexpected = True
                    break
            
            if unexpected and season >= 2024:  # Only flag unexpected gaps for recent seasons
                report.unexpected_gaps.append(game)
            
            seasons_data[season].gap_games.append(game)
    
    report.seasons = dict(seasons_data)
    
    # Summary
    total_games = sum(s.total_games for s in seasons_data.values())
    total_covered = sum(s.games_fully_covered for s in seasons_data.values())
    
    report.summary = {
        "total_games": total_games,
        "fully_covered": total_covered,
        "coverage_rate": total_covered / total_games if total_games > 0 else 0,
        "unexpected_gap_count": len(report.unexpected_gaps),
    }
    
    # Fail if unexpected gaps exist
    if report.unexpected_gaps:
        report.passed = False
    
    return report


# ============================================================================
# OUTPUT
# ============================================================================

def print_report(report: CoverageReport, verbose: bool = False):
    """Print coverage report to console."""
    print("\n" + "=" * 70)
    print("CROSS-SOURCE COVERAGE VALIDATION REPORT")
    print("=" * 70)
    print(f"Timestamp: {report.timestamp}")
    print(f"Status: {'PASSED' if report.passed else 'FAILED'}")
    print()
    
    print("SEASON SUMMARY:")
    print("-" * 70)
    print(f"{'Season':<8} {'Games':<8} {'H1 Scores':<12} {'FG Odds':<12} {'H1 Odds':<12} {'Ratings':<12} {'Full':<8}")
    print("-" * 70)
    
    for season in sorted(report.seasons.keys()):
        s = report.seasons[season]
        h1_pct = f"{100*s.games_with_h1_scores/s.total_games:.0f}%" if s.total_games > 0 else "0%"
        fg_pct = f"{100*s.games_with_fg_odds/s.total_games:.0f}%" if s.total_games > 0 else "0%"
        h1o_pct = f"{100*s.games_with_h1_odds/s.total_games:.0f}%" if s.total_games > 0 else "0%"
        rt_pct = f"{100*s.games_with_ratings/s.total_games:.0f}%" if s.total_games > 0 else "0%"
        full_pct = f"{100*s.games_fully_covered/s.total_games:.0f}%" if s.total_games > 0 else "0%"
        
        # Mark known gaps
        fg_note = " *" if season in KNOWN_ODDS_GAPS else ""
        h1o_note = " *" if season in KNOWN_H1_ODDS_GAPS else ""
        
        print(f"{season:<8} {s.total_games:<8} {h1_pct:<12} {fg_pct + fg_note:<12} {h1o_pct + h1o_note:<12} {rt_pct:<12} {full_pct:<8}")
    
    print("-" * 70)
    print(f"{'TOTAL':<8} {report.summary['total_games']:<8} {'':<12} {'':<12} {'':<12} {'':<12} {report.summary['coverage_rate']*100:.1f}%")
    print()
    print("* = Known historical gap (expected, not a failure)")
    
    if report.unexpected_gaps:
        print()
        print(f"WARNING - UNEXPECTED GAPS: {len(report.unexpected_gaps)}")
        print("-" * 70)
        for gap in report.unexpected_gaps[:20]:
            print(f"  {gap.date} {gap.home_canonical} vs {gap.away_canonical}")
            for reason in gap.gap_reasons:
                print(f"    - {reason}")
        if len(report.unexpected_gaps) > 20:
            print(f"  ... and {len(report.unexpected_gaps) - 20} more")
    
    print()


def save_report(report: CoverageReport, output_path: Path):
    """Save report to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to serializable format
    data = {
        "timestamp": report.timestamp,
        "passed": report.passed,
        "summary": report.summary,
        "seasons": {},
        "unexpected_gaps": [],
    }
    
    for season, coverage in report.seasons.items():
        data["seasons"][str(season)] = {
            "total_games": coverage.total_games,
            "games_with_h1_scores": coverage.games_with_h1_scores,
            "games_with_fg_odds": coverage.games_with_fg_odds,
            "games_with_h1_odds": coverage.games_with_h1_odds,
            "games_with_ratings": coverage.games_with_ratings,
            "games_fully_covered": coverage.games_fully_covered,
            "gap_count": len(coverage.gap_games),
        }
    
    for gap in report.unexpected_gaps:
        data["unexpected_gaps"].append({
            "game_id": gap.game_id,
            "date": gap.date,
            "season": gap.season,
            "home_canonical": gap.home_canonical,
            "away_canonical": gap.away_canonical,
            "gap_reasons": gap.gap_reasons,
        })
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    print(f"Report saved to: {output_path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Validate cross-source data coverage")
    parser.add_argument("--season", type=int, help="Validate specific season only")
    parser.add_argument("--output-json", type=str, help="Save report to JSON file")
    parser.add_argument("--fail-on-unexpected", action="store_true", 
                        help="Exit with code 1 if unexpected gaps found (CI mode)")
    parser.add_argument("--gap-threshold", type=int, default=0,
                        help="Number of acceptable gaps before failing (default: 0)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    print("=" * 70)
    print("CROSS-SOURCE COVERAGE VALIDATION")
    print("=" * 70)
    print()
    
    # Initialize resolver
    print("Loading ProductionTeamResolver...")
    resolver = ProductionTeamResolver()
    print()
    
    # Load all data sources
    print("Loading data sources...")
    games = load_fg_scores(DATA_PATHS)
    h1_game_ids = load_h1_scores(DATA_PATHS)
    fg_odds_keys, h1_odds_keys = load_odds(DATA_PATHS, resolver)
    barttorvik_teams = load_barttorvik_teams(DATA_PATHS, resolver)
    print()
    
    # Filter to specific season if requested
    if args.season:
        games = {k: v for k, v in games.items() if v.season == args.season}
        print(f"Filtered to season {args.season}: {len(games):,} games")
    
    # Validate coverage
    print("Validating coverage...")
    report = validate_coverage(
        games, h1_game_ids, fg_odds_keys, h1_odds_keys, barttorvik_teams, resolver
    )
    
    # Output
    print_report(report, args.verbose)
    
    if args.output_json:
        output_path = Path(args.output_json)
        if not output_path.is_absolute():
            output_path = DATA_PATHS.root / output_path
        save_report(report, output_path)
    
    # Exit code - check against threshold
    gap_count = len(report.unexpected_gaps)
    if args.fail_on_unexpected and gap_count > args.gap_threshold:
        print(f"VALIDATION FAILED: {gap_count} unexpected gaps (threshold: {args.gap_threshold})")
        sys.exit(1)
    
    if gap_count == 0:
        print("VALIDATION PASSED: No unexpected gaps")
    elif gap_count <= args.gap_threshold:
        print(f"VALIDATION PASSED: {gap_count} gaps within threshold ({args.gap_threshold})")
    
    sys.exit(0)


if __name__ == "__main__":
    main()
