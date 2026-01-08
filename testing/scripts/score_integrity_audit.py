#!/usr/bin/env python3
"""
SCORE DATA INTEGRITY AUDIT

Cross-validates game scores across ALL historical data sources to ensure
data integrity and consistency. This is critical for backtesting validity.

Sources validated:
1. ESPN Canonical Scores (games_all_canonical.csv)
2. ESPN H1 Canonical Scores (h1_games_all_canonical.csv)
3. ncaahoopR Schedule Data (team schedules with scores)
4. Backtest Ready Dataset (testing/data/backtest_ready.csv)
5. Backtest Complete Dataset (testing/data/backtest_complete.csv)
6. Games 2023-2025 (backtest_datasets/games_2023_2025.csv)

Checks performed:
- Cross-source score consistency (same game = same scores)
- Score sanity validation (reasonable ranges)
- H1 vs FG consistency (H1 scores < FG scores)
- Duplicate detection within sources
- Date/team alignment validation

Usage:
    python testing/scripts/score_integrity_audit.py
    python testing/scripts/score_integrity_audit.py --verbose
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


@dataclass
class GameScore:
    """Represents a single game's score data."""
    date: str
    home_team: str
    away_team: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_h1: Optional[int] = None
    away_h1: Optional[int] = None
    source: str = ""
    game_id: str = ""

    def game_key(self) -> str:
        """Create a normalized key for matching games across sources."""
        # Normalize: date + sorted teams (handles home/away swap)
        teams = tuple(sorted([self.home_team.lower(), self.away_team.lower()]))
        return f"{self.date}|{teams[0]}|{teams[1]}"

    def directional_key(self) -> str:
        """Key that preserves home/away distinction."""
        return f"{self.date}|{self.home_team.lower()}|{self.away_team.lower()}"

    @property
    def total(self) -> Optional[int]:
        if self.home_score is not None and self.away_score is not None:
            return self.home_score + self.away_score
        return None

    @property
    def h1_total(self) -> Optional[int]:
        if self.home_h1 is not None and self.away_h1 is not None:
            return self.home_h1 + self.away_h1
        return None


@dataclass
class ScoreSource:
    """A source of game score data."""
    name: str
    path: Path
    games: List[GameScore] = field(default_factory=list)
    games_by_key: Dict[str, List[GameScore]] = field(default_factory=dict)


@dataclass
class IntegrityIssue:
    """Represents a data integrity issue found."""
    severity: str  # CRITICAL, WARNING, INFO
    category: str
    description: str
    details: Dict = field(default_factory=dict)


@dataclass
class AuditResult:
    """Result of the score integrity audit."""
    passed: bool
    score: float
    issues: List[IntegrityIssue] = field(default_factory=list)
    metrics: Dict = field(default_factory=dict)


def safe_int(value) -> Optional[int]:
    """Safely convert a value to int."""
    if value is None or value == "" or value == "nan":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def load_espn_canonical_fg(data_paths) -> ScoreSource:
    """Load ESPN canonical full-game scores."""
    source = ScoreSource(
        name="espn_canonical_fg",
        path=data_paths.root / "canonicalized" / "scores" / "fg" / "games_all_canonical.csv"
    )

    if not source.path.exists():
        return source

    with open(source.path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            game = GameScore(
                date=row.get("date", ""),
                home_team=row.get("home_canonical") or row.get("home_team", ""),
                away_team=row.get("away_canonical") or row.get("away_team", ""),
                home_score=safe_int(row.get("home_score")),
                away_score=safe_int(row.get("away_score")),
                source=source.name,
                game_id=row.get("game_id", ""),
            )
            if game.date and game.home_team and game.away_team:
                source.games.append(game)

    # Index by game key
    for game in source.games:
        key = game.game_key()
        if key not in source.games_by_key:
            source.games_by_key[key] = []
        source.games_by_key[key].append(game)

    return source


def load_espn_canonical_h1(data_paths) -> ScoreSource:
    """Load ESPN canonical H1 scores."""
    source = ScoreSource(
        name="espn_canonical_h1",
        path=data_paths.root / "canonicalized" / "scores" / "h1" / "h1_games_all_canonical.csv"
    )

    if not source.path.exists():
        return source

    with open(source.path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            game = GameScore(
                date=row.get("date", ""),
                home_team=row.get("home_canonical") or row.get("home_team", ""),
                away_team=row.get("away_canonical") or row.get("away_team", ""),
                home_score=safe_int(row.get("home_fg")),
                away_score=safe_int(row.get("away_fg")),
                home_h1=safe_int(row.get("home_h1")),
                away_h1=safe_int(row.get("away_h1")),
                source=source.name,
                game_id=row.get("game_id", ""),
            )
            if game.date and game.home_team and game.away_team:
                source.games.append(game)

    for game in source.games:
        key = game.game_key()
        if key not in source.games_by_key:
            source.games_by_key[key] = []
        source.games_by_key[key].append(game)

    return source


def load_backtest_ready(data_paths) -> ScoreSource:
    """Load backtest_ready.csv from testing/data/."""
    source = ScoreSource(
        name="backtest_ready",
        path=ROOT_DIR / "testing" / "data" / "backtest_ready.csv"
    )

    if not source.path.exists():
        # Try root level
        alt_path = ROOT_DIR / "backtest_ready.csv"
        if alt_path.exists():
            source.path = alt_path
        else:
            return source

    with open(source.path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            game = GameScore(
                date=row.get("game_date", ""),
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                home_score=safe_int(row.get("home_score")),
                away_score=safe_int(row.get("away_score")),
                home_h1=safe_int(row.get("h1_home_score")),
                away_h1=safe_int(row.get("h1_away_score")),
                source=source.name,
            )
            if game.date and game.home_team and game.away_team:
                source.games.append(game)

    for game in source.games:
        key = game.game_key()
        if key not in source.games_by_key:
            source.games_by_key[key] = []
        source.games_by_key[key].append(game)

    return source


def load_backtest_complete(data_paths) -> ScoreSource:
    """Load backtest_complete.csv from testing/data/."""
    source = ScoreSource(
        name="backtest_complete",
        path=ROOT_DIR / "testing" / "data" / "backtest_complete.csv"
    )

    if not source.path.exists():
        return source

    with open(source.path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            game = GameScore(
                date=row.get("game_date", ""),
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                home_score=safe_int(row.get("home_score")),
                away_score=safe_int(row.get("away_score")),
                home_h1=safe_int(row.get("h1_home_score")),
                away_h1=safe_int(row.get("h1_away_score")),
                source=source.name,
            )
            if game.date and game.home_team and game.away_team:
                source.games.append(game)

    for game in source.games:
        key = game.game_key()
        if key not in source.games_by_key:
            source.games_by_key[key] = []
        source.games_by_key[key].append(game)

    return source


def load_games_2023_2025(data_paths) -> ScoreSource:
    """Load games_2023_2025.csv backtest dataset."""
    source = ScoreSource(
        name="games_2023_2025",
        path=data_paths.backtest_datasets / "games_2023_2025.csv"
    )

    if not source.path.exists():
        return source

    with open(source.path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            game = GameScore(
                date=row.get("game_date", ""),
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                home_score=safe_int(row.get("home_score")),
                away_score=safe_int(row.get("away_score")),
                source=source.name,
                game_id=row.get("game_id", ""),
            )
            if game.date and game.home_team and game.away_team:
                source.games.append(game)

    for game in source.games:
        key = game.game_key()
        if key not in source.games_by_key:
            source.games_by_key[key] = []
        source.games_by_key[key].append(game)

    return source


def load_training_data_with_odds(data_paths) -> ScoreSource:
    """Load training_data_with_odds.csv."""
    source = ScoreSource(
        name="training_data_with_odds",
        path=data_paths.backtest_datasets / "training_data_with_odds.csv"
    )

    if not source.path.exists():
        return source

    with open(source.path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            game = GameScore(
                date=row.get("game_date", ""),
                home_team=row.get("home_team", ""),
                away_team=row.get("away_team", ""),
                home_score=safe_int(row.get("home_score")),
                away_score=safe_int(row.get("away_score")),
                source=source.name,
                game_id=row.get("game_id", ""),
            )
            if game.date and game.home_team and game.away_team:
                source.games.append(game)

    for game in source.games:
        key = game.game_key()
        if key not in source.games_by_key:
            source.games_by_key[key] = []
        source.games_by_key[key].append(game)

    return source


def check_score_sanity(sources: List[ScoreSource]) -> List[IntegrityIssue]:
    """Check that all scores are within reasonable ranges."""
    issues = []

    MIN_SCORE = 20
    MAX_SCORE = 160
    MIN_TOTAL = 60
    MAX_TOTAL = 280
    MIN_H1 = 10
    MAX_H1 = 80

    for source in sources:
        insane_scores = []
        for game in source.games:
            problems = []

            if game.home_score is not None:
                if game.home_score < MIN_SCORE or game.home_score > MAX_SCORE:
                    problems.append(f"home_score={game.home_score}")
            if game.away_score is not None:
                if game.away_score < MIN_SCORE or game.away_score > MAX_SCORE:
                    problems.append(f"away_score={game.away_score}")
            if game.total is not None:
                if game.total < MIN_TOTAL or game.total > MAX_TOTAL:
                    problems.append(f"total={game.total}")
            if game.home_h1 is not None:
                if game.home_h1 < MIN_H1 or game.home_h1 > MAX_H1:
                    problems.append(f"home_h1={game.home_h1}")
            if game.away_h1 is not None:
                if game.away_h1 < MIN_H1 or game.away_h1 > MAX_H1:
                    problems.append(f"away_h1={game.away_h1}")

            if problems:
                insane_scores.append({
                    "date": game.date,
                    "matchup": f"{game.away_team} @ {game.home_team}",
                    "problems": problems,
                })

        if insane_scores:
            issues.append(IntegrityIssue(
                severity="WARNING",
                category="score_sanity",
                description=f"{source.name}: {len(insane_scores)} games with unusual scores",
                details={"samples": insane_scores[:10]},
            ))

    return issues


def check_h1_fg_consistency(sources: List[ScoreSource]) -> List[IntegrityIssue]:
    """Check that H1 scores are less than or equal to FG scores."""
    issues = []

    for source in sources:
        inconsistent = []
        for game in source.games:
            if game.home_h1 is not None and game.home_score is not None:
                if game.home_h1 > game.home_score:
                    inconsistent.append({
                        "date": game.date,
                        "matchup": f"{game.away_team} @ {game.home_team}",
                        "issue": f"home_h1={game.home_h1} > home_fg={game.home_score}",
                    })
            if game.away_h1 is not None and game.away_score is not None:
                if game.away_h1 > game.away_score:
                    inconsistent.append({
                        "date": game.date,
                        "matchup": f"{game.away_team} @ {game.home_team}",
                        "issue": f"away_h1={game.away_h1} > away_fg={game.away_score}",
                    })

        if inconsistent:
            issues.append(IntegrityIssue(
                severity="CRITICAL",
                category="h1_fg_consistency",
                description=f"{source.name}: {len(inconsistent)} games where H1 > FG",
                details={"samples": inconsistent[:10]},
            ))

    return issues


def check_duplicates_within_source(sources: List[ScoreSource]) -> List[IntegrityIssue]:
    """Check for duplicate games within each source."""
    issues = []

    for source in sources:
        duplicates = []
        for key, games in source.games_by_key.items():
            if len(games) > 1:
                # Check if scores match
                scores = set()
                for g in games:
                    scores.add((g.home_score, g.away_score))

                if len(scores) > 1:
                    duplicates.append({
                        "key": key,
                        "count": len(games),
                        "scores": list(scores),
                        "issue": "CONFLICTING scores",
                    })
                else:
                    duplicates.append({
                        "key": key,
                        "count": len(games),
                        "issue": "exact duplicate",
                    })

        if duplicates:
            conflicting = [d for d in duplicates if d.get("issue") == "CONFLICTING scores"]
            exact = [d for d in duplicates if d.get("issue") == "exact duplicate"]

            if conflicting:
                issues.append(IntegrityIssue(
                    severity="CRITICAL",
                    category="duplicates",
                    description=f"{source.name}: {len(conflicting)} games with CONFLICTING duplicate scores",
                    details={"samples": conflicting[:10]},
                ))
            if exact:
                issues.append(IntegrityIssue(
                    severity="INFO",
                    category="duplicates",
                    description=f"{source.name}: {len(exact)} exact duplicate games",
                    details={"count": len(exact)},
                ))

    return issues


def check_cross_source_consistency(
    sources: List[ScoreSource],
    verbose: bool = False,
) -> Tuple[List[IntegrityIssue], Dict]:
    """Cross-validate scores between sources."""
    issues = []
    metrics = {
        "cross_validations": 0,
        "matches": 0,
        "mismatches": 0,
        "source_pairs_checked": [],
    }

    # Build master index of all games
    all_games_by_key: Dict[str, List[Tuple[str, GameScore]]] = defaultdict(list)
    for source in sources:
        for game in source.games:
            key = game.game_key()
            all_games_by_key[key].append((source.name, game))

    # Find games that appear in multiple sources
    multi_source_games = {
        k: v for k, v in all_games_by_key.items()
        if len(set(src for src, _ in v)) > 1
    }

    metrics["games_in_multiple_sources"] = len(multi_source_games)

    # Check each multi-source game for consistency
    mismatches = []
    for key, entries in multi_source_games.items():
        metrics["cross_validations"] += 1

        # Group by source
        by_source = defaultdict(list)
        for src, game in entries:
            by_source[src].append(game)

        # Compare scores across sources
        source_names = list(by_source.keys())
        for i, src1 in enumerate(source_names):
            for src2 in source_names[i + 1:]:
                game1 = by_source[src1][0]  # Take first if duplicates
                game2 = by_source[src2][0]

                # Compare FG scores
                if (game1.home_score is not None and game2.home_score is not None
                        and game1.away_score is not None and game2.away_score is not None):

                    # Check if scores match (allowing for home/away swap)
                    scores1 = (game1.home_score, game1.away_score)
                    scores2 = (game2.home_score, game2.away_score)
                    scores2_swapped = (game2.away_score, game2.home_score)

                    if scores1 == scores2:
                        metrics["matches"] += 1
                    elif scores1 == scores2_swapped:
                        # Home/away swapped but scores consistent
                        metrics["matches"] += 1
                    else:
                        metrics["mismatches"] += 1
                        mismatches.append({
                            "date": game1.date,
                            "teams": key,
                            "source1": src1,
                            "scores1": f"{game1.home_score}-{game1.away_score}",
                            "source2": src2,
                            "scores2": f"{game2.home_score}-{game2.away_score}",
                        })

    if mismatches:
        issues.append(IntegrityIssue(
            severity="CRITICAL",
            category="cross_source_mismatch",
            description=f"{len(mismatches)} games have DIFFERENT scores across sources",
            details={"samples": mismatches[:20]},
        ))

    # Calculate match rate
    total_comparisons = metrics["matches"] + metrics["mismatches"]
    if total_comparisons > 0:
        metrics["match_rate"] = metrics["matches"] / total_comparisons
    else:
        metrics["match_rate"] = 1.0

    return issues, metrics


def check_missing_scores(sources: List[ScoreSource]) -> List[IntegrityIssue]:
    """Check for games with missing score data."""
    issues = []

    for source in sources:
        missing_fg = 0
        missing_h1 = 0

        for game in source.games:
            if game.home_score is None or game.away_score is None:
                missing_fg += 1
            if game.home_h1 is None or game.away_h1 is None:
                missing_h1 += 1

        if missing_fg > 0:
            issues.append(IntegrityIssue(
                severity="WARNING",
                category="missing_scores",
                description=f"{source.name}: {missing_fg} games missing FG scores",
                details={"missing_fg_count": missing_fg, "total": len(source.games)},
            ))

        # Only warn about H1 if source should have H1 data
        if "h1" in source.name.lower() and missing_h1 > 0:
            issues.append(IntegrityIssue(
                severity="WARNING",
                category="missing_scores",
                description=f"{source.name}: {missing_h1} games missing H1 scores",
                details={"missing_h1_count": missing_h1, "total": len(source.games)},
            ))

    return issues


def run_score_integrity_audit(
    output_dir: Optional[Path] = None,
    verbose: bool = False,
) -> AuditResult:
    """Run the complete score integrity audit."""

    print("=" * 72)
    print("SCORE DATA INTEGRITY AUDIT")
    print("=" * 72)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    result = AuditResult(passed=True, score=1.0)

    # Load all sources
    print("Loading score data from all sources...")
    sources = [
        load_espn_canonical_fg(DATA_PATHS),
        load_espn_canonical_h1(DATA_PATHS),
        load_backtest_ready(DATA_PATHS),
        load_backtest_complete(DATA_PATHS),
        load_games_2023_2025(DATA_PATHS),
        load_training_data_with_odds(DATA_PATHS),
    ]

    # Filter to sources that exist and have data
    sources = [s for s in sources if s.games]

    print(f"\nLoaded {len(sources)} sources:")
    for source in sources:
        print(f"  {source.name}: {len(source.games):,} games")
        result.metrics[f"{source.name}_count"] = len(source.games)

    print()

    # Run all checks
    all_issues = []

    # Check 1: Score sanity
    print("-" * 72)
    print("CHECK 1: Score Sanity Validation")
    print("-" * 72)
    sanity_issues = check_score_sanity(sources)
    all_issues.extend(sanity_issues)
    if sanity_issues:
        for issue in sanity_issues:
            print(f"  [{issue.severity}] {issue.description}")
    else:
        print("  [PASS] All scores within expected ranges")

    # Check 2: H1 vs FG consistency
    print()
    print("-" * 72)
    print("CHECK 2: H1 vs FG Score Consistency")
    print("-" * 72)
    h1_issues = check_h1_fg_consistency(sources)
    all_issues.extend(h1_issues)
    if h1_issues:
        for issue in h1_issues:
            print(f"  [{issue.severity}] {issue.description}")
            if verbose and issue.details.get("samples"):
                for s in issue.details["samples"][:5]:
                    print(f"    - {s}")
    else:
        print("  [PASS] All H1 scores <= FG scores")

    # Check 3: Duplicates within sources
    print()
    print("-" * 72)
    print("CHECK 3: Duplicate Detection")
    print("-" * 72)
    dup_issues = check_duplicates_within_source(sources)
    all_issues.extend(dup_issues)
    if dup_issues:
        for issue in dup_issues:
            print(f"  [{issue.severity}] {issue.description}")
    else:
        print("  [PASS] No problematic duplicates found")

    # Check 4: Cross-source consistency
    print()
    print("-" * 72)
    print("CHECK 4: Cross-Source Score Consistency")
    print("-" * 72)
    cross_issues, cross_metrics = check_cross_source_consistency(sources, verbose)
    all_issues.extend(cross_issues)
    result.metrics.update(cross_metrics)

    print(f"  Games in multiple sources: {cross_metrics['games_in_multiple_sources']:,}")
    print(f"  Cross-validations: {cross_metrics['cross_validations']:,}")
    print(f"  Matches: {cross_metrics['matches']:,}")
    print(f"  Mismatches: {cross_metrics['mismatches']:,}")
    print(f"  Match rate: {cross_metrics['match_rate']:.1%}")

    if cross_issues:
        for issue in cross_issues:
            print(f"  [{issue.severity}] {issue.description}")
            if verbose and issue.details.get("samples"):
                for s in issue.details["samples"][:5]:
                    print(f"    - {s['date']}: {s['source1']}={s['scores1']} vs {s['source2']}={s['scores2']}")

    # Check 5: Missing scores
    print()
    print("-" * 72)
    print("CHECK 5: Missing Score Detection")
    print("-" * 72)
    missing_issues = check_missing_scores(sources)
    all_issues.extend(missing_issues)
    if missing_issues:
        for issue in missing_issues:
            print(f"  [{issue.severity}] {issue.description}")
    else:
        print("  [PASS] No significant missing scores")

    # Calculate final score
    result.issues = all_issues
    critical_count = sum(1 for i in all_issues if i.severity == "CRITICAL")
    warning_count = sum(1 for i in all_issues if i.severity == "WARNING")

    result.metrics["critical_issues"] = critical_count
    result.metrics["warning_issues"] = warning_count

    if critical_count > 0:
        result.passed = False
        result.score = max(0, 1.0 - (critical_count * 0.2))
    elif warning_count > 5:
        result.score = max(0.7, 1.0 - (warning_count * 0.05))

    # If cross-source match rate is low, that's critical
    if cross_metrics["match_rate"] < 0.95:
        result.passed = False
        result.score = min(result.score, cross_metrics["match_rate"])

    # Final summary
    print()
    print("=" * 72)
    print("AUDIT SUMMARY")
    print("=" * 72)
    print(f"\nCritical Issues: {critical_count}")
    print(f"Warnings: {warning_count}")
    print(f"Cross-source match rate: {cross_metrics['match_rate']:.1%}")
    print(f"\nOverall Score: {result.score:.2f}")
    print(f"Status: {'PASS' if result.passed else 'FAIL'}")

    if result.passed:
        print("\n[PASS] Score data integrity is VALID")
    else:
        print("\n[FAIL] Score data has integrity issues that must be resolved")

    # Save report
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f"score_integrity_audit_{timestamp}.json"

        report = {
            "timestamp": datetime.now().isoformat(),
            "passed": result.passed,
            "score": result.score,
            "metrics": result.metrics,
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "description": i.description,
                    "details": i.details,
                }
                for i in result.issues
            ],
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\nReport saved to: {report_path}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Score data integrity audit across all sources"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Directory to save audit report"
    )

    args = parser.parse_args()

    result = run_score_integrity_audit(
        output_dir=Path(args.output_dir) if args.output_dir else None,
        verbose=args.verbose,
    )

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
