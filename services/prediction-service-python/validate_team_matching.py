#!/usr/bin/env python3
"""
Green Bier Sport Ventures - Team Matching Validation Script

This script validates 100% team matching accuracy before running predictions.
It ensures all teams from data sources (Barttorvik, The Odds API) are properly
resolved to canonical names with ratings available.

Usage:
    python validate_team_matching.py              # Full validation
    python validate_team_matching.py --fix        # Attempt to fix issues
    python validate_team_matching.py --verbose    # Show all details
"""

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import create_engine, text

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    try:
        with open("/run/secrets/db_password") as f:
            DB_PASSWORD = f.read().strip()
        DATABASE_URL = f"postgresql://ncaam:{DB_PASSWORD}@postgres:5432/ncaam"
    except FileNotFoundError:
        print("ERROR: DATABASE_URL not set and secrets not found")
        sys.exit(1)


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    metric: str
    value: float
    status: str  # PASS, WARN, FAIL, INFO
    details: str | None = None


@dataclass
class UnresolvedTeam:
    """Team that failed to resolve."""
    input_name: str
    source: str
    context: str
    occurrences: int
    last_seen: datetime
    alternatives: list[str]


class TeamMatchingValidator:
    """Validates team matching accuracy across all data sources."""

    def __init__(self, verbose: bool = False):
        self.engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        self.verbose = verbose
        self.results: list[ValidationResult] = []

    def run_all_validations(self) -> bool:
        """Run all validation checks. Returns True if all critical checks pass."""
        print()
        print("╔═══════════════════════════════════════════════════════════════════════════════╗")
        print("║  GREEN BIER SPORT VENTURES - Team Matching Validation                        ║")
        print("╠═══════════════════════════════════════════════════════════════════════════════╣")
        print(f"║  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<68}║")
        print("╚═══════════════════════════════════════════════════════════════════════════════╝")
        print()

        # Run all checks
        self._check_database_stats()
        self._check_resolution_accuracy()
        self._check_unresolved_teams()
        self._check_games_data_completeness()
        self._check_four_factors_coverage()
        self._check_duplicate_teams()

        # Print summary
        return self._print_summary()

    def _check_database_stats(self):
        """Check basic database statistics."""
        print("📊 Database Statistics")
        print("-" * 60)

        with self.engine.connect() as conn:
            # Total teams
            result = conn.execute(text("SELECT COUNT(*) FROM teams"))
            count = result.scalar()
            self.results.append(ValidationResult("Total Teams", count, "INFO"))
            print(f"   Total Teams:              {count}")

            # Teams with ratings
            result = conn.execute(text("SELECT COUNT(DISTINCT team_id) FROM team_ratings"))
            count = result.scalar()
            self.results.append(ValidationResult("Teams with Ratings", count, "INFO"))
            print(f"   Teams with Ratings:       {count}")

            # Total aliases
            result = conn.execute(text("SELECT COUNT(*) FROM team_aliases"))
            count = result.scalar()
            self.results.append(ValidationResult("Total Aliases", count, "INFO"))
            print(f"   Total Aliases:            {count}")

            # Aliases by source
            result = conn.execute(text("""
                SELECT source, COUNT(*) as cnt
                FROM team_aliases
                GROUP BY source
                ORDER BY cnt DESC
            """))
            print("   Aliases by Source:")
            for row in result:
                print(f"      - {row.source}: {row.cnt}")

        print()

    def _check_resolution_accuracy(self):
        """Check team resolution success rate."""
        print("🎯 Resolution Accuracy")
        print("-" * 60)

        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN resolved_name IS NOT NULL THEN 1 ELSE 0 END) as resolved,
                    SUM(CASE WHEN resolved_name IS NULL THEN 1 ELSE 0 END) as unresolved
                FROM team_resolution_audit
            """))
            row = result.fetchone()

            if row and row.total > 0:
                rate = 100.0 * row.resolved / row.total
                status = "PASS" if rate >= 99.9 else "WARN" if rate >= 99.0 else "FAIL"
                self.results.append(ValidationResult("Resolution Rate", rate, status))
                print(f"   Total Resolution Attempts: {row.total}")
                print(f"   Successfully Resolved:     {row.resolved}")
                print(f"   Failed to Resolve:         {row.unresolved}")
                print(f"   Success Rate:              {rate:.2f}% [{status}]")
            else:
                print("   No resolution attempts recorded yet")
                self.results.append(ValidationResult("Resolution Rate", 0, "INFO", "No data"))

            # Resolution by source
            result = conn.execute(text("""
                SELECT
                    source,
                    COUNT(*) as total,
                    SUM(CASE WHEN resolved_name IS NOT NULL THEN 1 ELSE 0 END) as resolved
                FROM team_resolution_audit
                GROUP BY source
                ORDER BY total DESC
            """))
            print("   By Source:")
            for row in result:
                rate = 100.0 * row.resolved / row.total if row.total > 0 else 0
                status = "✓" if rate >= 99.9 else "⚠" if rate >= 99.0 else "✗"
                print(f"      {status} {row.source}: {rate:.2f}% ({row.resolved}/{row.total})")

        print()

    def _check_unresolved_teams(self) -> list[UnresolvedTeam]:
        """Check for unresolved teams and return them."""
        print("❌ Unresolved Teams")
        print("-" * 60)

        unresolved = []
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    input_name,
                    source,
                    context,
                    COUNT(*) as occurrences,
                    MAX(created_at) as last_seen,
                    alternatives
                FROM team_resolution_audit
                WHERE resolved_name IS NULL
                GROUP BY input_name, source, context, alternatives
                ORDER BY occurrences DESC
                LIMIT 50
            """))

            for row in result:
                unresolved.append(UnresolvedTeam(
                    input_name=row.input_name,
                    source=row.source,
                    context=row.context or "unknown",
                    occurrences=row.occurrences,
                    last_seen=row.last_seen,
                    alternatives=row.alternatives or []
                ))

        if unresolved:
            self.results.append(ValidationResult(
                "Unresolved Teams", len(unresolved), "FAIL",
                f"{len(unresolved)} unique teams failed to resolve"
            ))
            print(f"   Found {len(unresolved)} unresolved team names:")
            for team in unresolved[:20]:  # Show first 20
                print(f"      [{team.source}] \"{team.input_name}\" ({team.occurrences}x)")
                if team.alternatives:
                    print(f"         Possible matches: {', '.join(team.alternatives[:3])}")
            if len(unresolved) > 20:
                print(f"      ... and {len(unresolved) - 20} more")
        else:
            self.results.append(ValidationResult("Unresolved Teams", 0, "PASS"))
            print("   ✓ All teams resolved successfully!")

        print()
        return unresolved

    def _check_games_data_completeness(self):
        """Check that scheduled games have complete data."""
        print("📅 Scheduled Games Data Completeness")
        print("-" * 60)

        with self.engine.connect() as conn:
            # Total scheduled games
            result = conn.execute(text("""
                SELECT COUNT(*) FROM games WHERE status = 'scheduled'
            """))
            total_games = result.scalar()
            print(f"   Total Scheduled Games: {total_games}")

            # Games with both teams having ratings
            result = conn.execute(text("""
                SELECT COUNT(*) FROM games g
                JOIN teams ht ON g.home_team_id = ht.id
                JOIN teams at ON g.away_team_id = at.id
                WHERE g.status = 'scheduled'
                  AND EXISTS (SELECT 1 FROM team_ratings WHERE team_id = ht.id)
                  AND EXISTS (SELECT 1 FROM team_ratings WHERE team_id = at.id)
            """))
            games_with_ratings = result.scalar()

            # Games with odds
            result = conn.execute(text("""
                SELECT COUNT(DISTINCT g.id) FROM games g
                JOIN odds_snapshots os ON g.id = os.game_id
                WHERE g.status = 'scheduled'
            """))
            games_with_odds = result.scalar()

            # Games ready for prediction (have both ratings and odds)
            result = conn.execute(text("""
                SELECT COUNT(DISTINCT g.id) FROM games g
                JOIN teams ht ON g.home_team_id = ht.id
                JOIN teams at ON g.away_team_id = at.id
                JOIN odds_snapshots os ON g.id = os.game_id
                WHERE g.status = 'scheduled'
                  AND EXISTS (SELECT 1 FROM team_ratings WHERE team_id = ht.id)
                  AND EXISTS (SELECT 1 FROM team_ratings WHERE team_id = at.id)
            """))
            games_ready = result.scalar()

            if total_games > 0:
                ratings_rate = 100.0 * games_with_ratings / total_games
                odds_rate = 100.0 * games_with_odds / total_games
                ready_rate = 100.0 * games_ready / total_games

                self.results.append(ValidationResult(
                    "Games with Ratings",
                    ratings_rate,
                    "PASS" if ratings_rate >= 95 else "WARN" if ratings_rate >= 80 else "FAIL"
                ))
                self.results.append(ValidationResult(
                    "Games with Odds",
                    odds_rate,
                    "PASS" if odds_rate >= 95 else "WARN" if odds_rate >= 80 else "FAIL"
                ))
                self.results.append(ValidationResult(
                    "Games Ready for Prediction",
                    ready_rate,
                    "PASS" if ready_rate >= 90 else "WARN" if ready_rate >= 70 else "FAIL"
                ))

                print(f"   Games with Both Ratings: {games_with_ratings} ({ratings_rate:.1f}%)")
                print(f"   Games with Odds:         {games_with_odds} ({odds_rate:.1f}%)")
                print(f"   Games Ready (Both):      {games_ready} ({ready_rate:.1f}%)")

                # Show games missing data
                if games_ready < total_games:
                    result = conn.execute(text("""
                        SELECT
                            ht.canonical_name as home,
                            at.canonical_name as away,
                            g.commence_time,
                            CASE WHEN htr.team_id IS NULL THEN 'MISSING' ELSE 'OK' END as home_ratings,
                            CASE WHEN atr.team_id IS NULL THEN 'MISSING' ELSE 'OK' END as away_ratings,
                            CASE WHEN os.game_id IS NULL THEN 'MISSING' ELSE 'OK' END as odds
                        FROM games g
                        JOIN teams ht ON g.home_team_id = ht.id
                        JOIN teams at ON g.away_team_id = at.id
                        LEFT JOIN (SELECT DISTINCT team_id FROM team_ratings) htr ON ht.id = htr.team_id
                        LEFT JOIN (SELECT DISTINCT team_id FROM team_ratings) atr ON at.id = atr.team_id
                        LEFT JOIN (SELECT DISTINCT game_id FROM odds_snapshots) os ON g.id = os.game_id
                        WHERE g.status = 'scheduled'
                          AND (htr.team_id IS NULL OR atr.team_id IS NULL OR os.game_id IS NULL)
                        ORDER BY g.commence_time
                        LIMIT 10
                    """))

                    print("\n   Games Missing Data (first 10):")
                    for row in result:
                        issues = []
                        if row.home_ratings == 'MISSING':
                            issues.append(f"home_ratings({row.home})")
                        if row.away_ratings == 'MISSING':
                            issues.append(f"away_ratings({row.away})")
                        if row.odds == 'MISSING':
                            issues.append("odds")
                        print(f"      {row.away} @ {row.home}: {', '.join(issues)}")
            else:
                print("   No scheduled games found")

        print()

    def _check_four_factors_coverage(self):
        """Check that Four Factors data is being captured."""
        print("📈 Four Factors Data Coverage")
        print("-" * 60)

        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total_ratings,
                    SUM(CASE WHEN efg IS NOT NULL THEN 1 ELSE 0 END) as has_efg,
                    SUM(CASE WHEN tor IS NOT NULL THEN 1 ELSE 0 END) as has_tor,
                    SUM(CASE WHEN orb IS NOT NULL THEN 1 ELSE 0 END) as has_orb,
                    SUM(CASE WHEN ftr IS NOT NULL THEN 1 ELSE 0 END) as has_ftr,
                    SUM(CASE WHEN barthag IS NOT NULL THEN 1 ELSE 0 END) as has_barthag,
                    SUM(CASE WHEN three_pt_rate IS NOT NULL THEN 1 ELSE 0 END) as has_3pr
                FROM team_ratings
            """))
            row = result.fetchone()

            if row and row.total_ratings > 0:
                total = row.total_ratings
                print(f"   Total Rating Records: {total}")
                print("   Four Factors Coverage:")

                for field, count in [
                    ("EFG%", row.has_efg),
                    ("Turnover Rate", row.has_tor),
                    ("Off Reb Rate", row.has_orb),
                    ("FT Rate", row.has_ftr),
                    ("Barthag", row.has_barthag),
                    ("3P Rate", row.has_3pr)
                ]:
                    rate = 100.0 * count / total
                    status = "✓" if rate >= 95 else "⚠" if rate > 0 else "✗"
                    print(f"      {status} {field}: {count}/{total} ({rate:.1f}%)")

                # Add result for overall coverage
                avg_coverage = (row.has_efg + row.has_tor + row.has_orb + row.has_ftr) / 4 / total * 100
                self.results.append(ValidationResult(
                    "Four Factors Coverage",
                    avg_coverage,
                    "PASS" if avg_coverage >= 95 else "WARN" if avg_coverage >= 50 else "INFO"
                ))
            else:
                print("   No rating records with Four Factors data")
                self.results.append(ValidationResult("Four Factors Coverage", 0, "INFO"))

        print()

    def _check_duplicate_teams(self):
        """Check for potential duplicate teams (same canonical name, different IDs)."""
        print("🔍 Duplicate Team Detection")
        print("-" * 60)

        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT LOWER(canonical_name) as canonical_name, COUNT(*) as cnt
                FROM teams
                GROUP BY LOWER(canonical_name)
                HAVING COUNT(*) > 1
            """))

            duplicates = list(result)
            if duplicates:
                self.results.append(ValidationResult(
                    "Duplicate Teams", len(duplicates), "WARN",
                    "Potential duplicate canonical names"
                ))
                print(f"   ⚠ Found {len(duplicates)} potential duplicates:")
                for row in duplicates:
                    print(f"      - \"{row.canonical_name}\" appears {row.cnt} times")
            else:
                self.results.append(ValidationResult("Duplicate Teams", 0, "PASS"))
                print("   ✓ No duplicate teams detected")

        print()

    def _print_summary(self) -> bool:
        """Print validation summary. Returns True if all critical checks pass."""
        print("═" * 60)
        print("VALIDATION SUMMARY")
        print("═" * 60)

        passed = 0
        warned = 0
        failed = 0

        for result in self.results:
            if result.status == "PASS":
                passed += 1
            elif result.status == "WARN":
                warned += 1
            elif result.status == "FAIL":
                failed += 1

        print(f"   ✓ Passed: {passed}")
        print(f"   ⚠ Warnings: {warned}")
        print(f"   ✗ Failed: {failed}")
        print()

        if failed > 0:
            print("❌ VALIDATION FAILED - Fix issues before running predictions")
            print()
            print("   Failed Checks:")
            for result in self.results:
                if result.status == "FAIL":
                    print(f"      - {result.metric}: {result.details or result.value}")
            return False
        if warned > 0:
            print("⚠️  VALIDATION PASSED WITH WARNINGS")
            print("   Predictions can run but may have incomplete data")
            return True
        print("✅ ALL VALIDATIONS PASSED")
        print("   Team matching is at 100% accuracy")
        return True

    def attempt_fixes(self, unresolved: list[UnresolvedTeam]):
        """Attempt to automatically fix unresolved teams."""
        print()
        print("🔧 Attempting Automatic Fixes")
        print("-" * 60)

        fixed_count = 0
        with self.engine.connect() as conn:
            for team in unresolved:
                # Try to find a close match
                result = conn.execute(text("""
                    SELECT canonical_name
                    FROM teams
                    WHERE LOWER(canonical_name) LIKE :pattern
                       OR EXISTS (
                           SELECT 1 FROM team_aliases
                           WHERE team_id = teams.id
                             AND LOWER(alias) LIKE :pattern
                       )
                    LIMIT 1
                """), {"pattern": f"%{team.input_name.lower().split()[0]}%"})

                match = result.fetchone()
                if match:
                    # Add alias
                    try:
                        conn.execute(text("""
                            INSERT INTO team_aliases (team_id, alias, source, confidence)
                            SELECT id, :alias, :source, 0.9
                            FROM teams WHERE canonical_name = :canonical
                            ON CONFLICT (alias, source) DO NOTHING
                        """), {
                            "alias": team.input_name,
                            "source": team.source,
                            "canonical": match.canonical_name
                        })
                        conn.commit()
                        print(f"   ✓ Added alias: \"{team.input_name}\" → \"{match.canonical_name}\"")
                        fixed_count += 1
                    except Exception as e:
                        print(f"   ✗ Failed to add alias for \"{team.input_name}\": {e}")

        print()
        print(f"   Fixed {fixed_count} of {len(unresolved)} unresolved teams")


def main():
    parser = argparse.ArgumentParser(
        description="Validate team matching accuracy for Green Bier Sport Ventures"
    )
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")
    parser.add_argument("--verbose", action="store_true", help="Show verbose output")
    args = parser.parse_args()

    validator = TeamMatchingValidator(verbose=args.verbose)
    success = validator.run_all_validations()

    if args.fix:
        unresolved = validator._check_unresolved_teams()
        if unresolved:
            validator.attempt_fixes(unresolved)
            print()
            print("Re-running validation after fixes...")
            validator.results = []
            success = validator.run_all_validations()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
