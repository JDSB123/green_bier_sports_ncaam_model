#!/usr/bin/env python3
"""
CANONICAL DATA VALIDATOR - PREVENTIVE QUALITY GATES

Proactively validates data quality before ingestion using canonical quality gates.
Replaces reactive validation with preventive blocking of bad data.

Validates:
- Data quality standards by vintage
- Canonical ingestion compliance
- Cross-source consistency
- Schema adherence

Usage:
    python testing/scripts/canonical_data_validator.py --data-type scores --source azure
    python testing/scripts/canonical_data_validator.py --comprehensive  # Validate all data
    python testing/scripts/canonical_data_validator.py --report-only    # Just report issues
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from testing.azure_data_reader import get_azure_reader
from testing.data_window import default_backtest_seasons, enforce_min_season
from testing.canonical.quality_gates import DataQualityGate, ValidationSeverity
from testing.canonical.schema_evolution import SchemaEvolutionManager, detect_data_vintage
from testing.canonical.team_resolution_service import get_team_resolver


class CanonicalDataValidator:
    """
    Preventive data validator using canonical quality gates.

    Validates data before it enters the system, preventing downstream issues.
    """

    def __init__(self, strict_mode: bool = True, report_only: bool = False):
        """
        Initialize validator.

        Args:
            strict_mode: Block on any error if True
            report_only: Only report issues, don't block
        """
        self.strict_mode = strict_mode
        self.report_only = report_only

        self.quality_gate = DataQualityGate(strict_mode=strict_mode)
        self.schema_manager = SchemaEvolutionManager()
        self.team_resolver = get_team_resolver()
        self.azure_reader = get_azure_reader()

    def validate_data_source(
        self,
        data_type: str,
        source: str = "azure",
        seasons: Optional[List[int]] = None
    ) -> Dict:
        """
        Validate a specific data source.

        Args:
            data_type: Type of data ("scores", "odds", "ratings")
            source: Data source ("azure" only)
            seasons: Specific seasons to validate

        Returns:
            Validation results dictionary
        """
        print(f"\n{'='*60}")
        print(f"VALIDATING {data_type.upper()} DATA ({source.upper()})")
        print('='*60)

        results = {
            "data_type": data_type,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "seasons_validated": [],
            "total_records": 0,
            "passed": True,
            "issues": [],
            "recommendations": []
        }

        try:
            if source != "azure":
                raise ValueError("Only Azure is supported for canonical validation.")

            reader = self.azure_reader
            if seasons:
                seasons = enforce_min_season(seasons)

            # Load and validate data
            if data_type == "scores":
                data = self._load_scores_data(reader, seasons)
            elif data_type == "odds":
                data = self._load_odds_data(reader, seasons)
            elif data_type == "ratings":
                data = self._load_ratings_data(reader, seasons)
            else:
                raise ValueError(f"Unknown data type: {data_type}")

            if data is None or len(data) == 0:
                results["issues"].append({
                    "severity": "error",
                    "message": f"No {data_type} data found"
                })
                results["passed"] = False
                return results

            results["total_records"] = len(data)

            # Detect data vintage and apply appropriate standards
            vintage = detect_data_vintage(data)
            results["detected_vintage"] = vintage.value

            quality_standards = self.schema_manager.get_quality_standards(vintage)
            results["quality_standards"] = quality_standards

            # Run quality validation
            validation_result = self.quality_gate.validate(data, data_type)

            # Analyze results
            results["validation_passed"] = validation_result.passed
            results["issues"] = [
                {
                    "severity": issue.severity.value,
                    "rule": issue.rule_name,
                    "message": issue.message,
                    "field": issue.field,
                    "row_count": len(issue.row_indices) if issue.row_indices else 0
                }
                for issue in validation_result.issues
            ]

            # Generate recommendations
            results["recommendations"] = self._generate_recommendations(
                validation_result, data_type, vintage
            )

            # Overall pass/fail
            results["passed"] = validation_result.passed and len(results["issues"]) == 0

            # Summary
            print(f"Records validated: {results['total_records']}")
            print(f"Data vintage: {vintage.value}")
            print(f"Validation passed: {results['passed']}")
            print(f"Issues found: {len(results['issues'])}")

            critical_issues = [i for i in results["issues"] if i["severity"] == "critical"]
            error_issues = [i for i in results["issues"] if i["severity"] == "error"]
            warning_issues = [i for i in results["issues"] if i["severity"] == "warning"]

            if critical_issues:
                print(f"  Critical: {len(critical_issues)}")
            if error_issues:
                print(f"  Errors: {len(error_issues)}")
            if warning_issues:
                print(f"  Warnings: {len(warning_issues)}")

        except Exception as e:
            results["passed"] = False
            results["issues"].append({
                "severity": "critical",
                "message": f"Validation failed: {str(e)}"
            })
            print(f"Validation error: {e}")

        return results

    def validate_all_sources(self) -> Dict:
        """Validate all data sources comprehensively."""
        print("\n" + "="*80)
        print("COMPREHENSIVE DATA VALIDATION")
        print("="*80)

        all_results = {
            "timestamp": datetime.now().isoformat(),
            "sources_validated": [],
            "overall_passed": True,
            "summary": {},
            "details": {}
        }

        data_sources = [
            ("scores", "azure"),
            ("odds", "azure"),
            ("ratings", "azure"),
        ]

        for data_type, source in data_sources:
            try:
                result = self.validate_data_source(data_type, source)
                all_results["sources_validated"].append(f"{data_type}_{source}")
                all_results["details"][f"{data_type}_{source}"] = result

                if not result["passed"]:
                    all_results["overall_passed"] = False

                # Update summary
                if data_type not in all_results["summary"]:
                    all_results["summary"][data_type] = {"sources": [], "issues": 0, "passed": True}

                all_results["summary"][data_type]["sources"].append(source)
                all_results["summary"][data_type]["issues"] += len(result["issues"])
                all_results["summary"][data_type]["passed"] &= result["passed"]

            except Exception as e:
                print(f"Failed to validate {data_type} from {source}: {e}")
                all_results["overall_passed"] = False

        # Print summary
        print(f"\nOverall result: {'PASSED' if all_results['overall_passed'] else 'FAILED'}")
        for data_type, summary in all_results["summary"].items():
            status = "PASS" if summary["passed"] else "FAIL"
            print(f"  {data_type}: {status} ({summary['issues']} issues across {len(summary['sources'])} sources)")

        return all_results

    def _load_scores_data(self, reader, seasons: Optional[List[int]] = None) -> Optional[pd.DataFrame]:
        """Load scores data for validation."""
        try:
            seasons = seasons or default_backtest_seasons()
            dfs = []
            for season in seasons:
                df = reader.read_canonical_scores(season)
                dfs.append(df)
            return pd.concat(dfs, ignore_index=True) if dfs else None
        except Exception as e:
            print(f"Failed to load scores data: {e}")
            return None

    def _load_odds_data(self, reader, seasons: Optional[List[int]] = None) -> Optional[pd.DataFrame]:
        """Load odds data for validation."""
        try:
            seasons = seasons or default_backtest_seasons()
            dfs = []
            for season in seasons:
                df = reader.read_canonical_odds(season=season)
                dfs.append(df)
            return pd.concat(dfs, ignore_index=True) if dfs else None
        except Exception as e:
            print(f"Failed to load odds data: {e}")
            return None

    def _load_ratings_data(self, reader, seasons: Optional[List[int]] = None) -> Optional[pd.DataFrame]:
        """Load ratings data for validation."""
        try:
            seasons = seasons or default_backtest_seasons()
            dfs = []
            for season in seasons:
                ratings_payload = reader.read_canonical_ratings(season)
                if isinstance(ratings_payload, list):
                    df = pd.DataFrame(ratings_payload)
                    if "season" not in df.columns:
                        df["season"] = season
                elif isinstance(ratings_payload, dict):
                    df = pd.DataFrame.from_dict(ratings_payload, orient="index")
                    df["season"] = season
                    df["team"] = df.index
                else:
                    raise ValueError("Unsupported ratings payload format")
                dfs.append(df)
            return pd.concat(dfs, ignore_index=True) if dfs else None
        except Exception as e:
            print(f"Failed to load ratings data: {e}")
            return None

    def _generate_recommendations(
        self,
        validation_result: "ValidationResult",
        data_type: str,
        vintage: "DataVintage"
    ) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        # Vintage-specific recommendations
        if vintage.value == "legacy":
            recommendations.append("Consider upgrading to modern data sources for better quality")
        elif vintage.value == "transitional":
            recommendations.append("Data quality is improving - continue migration to canonical sources")

        # Issue-specific recommendations
        critical_issues = [i for i in validation_result.issues if i.severity == ValidationSeverity.CRITICAL]
        if critical_issues:
            recommendations.append("Critical issues found - data should not be used for production")

        unresolved_teams = [i for i in validation_result.issues if "team_resolution" in i.rule_name]
        if unresolved_teams:
            recommendations.append("Add missing team names to aliases database")

        null_issues = [i for i in validation_result.issues if "null_check" in i.rule_name]
        if null_issues:
            recommendations.append("Investigate data source for missing values")

        return recommendations


def save_validation_report(results: Dict, output_path: Optional[Path] = None):
    """Save validation results to file."""
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"validation_report_{timestamp}.json")

    import json
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"Validation report saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Canonical data validator")
    parser.add_argument("--data-type", choices=["scores", "odds", "ratings"],
                       help="Type of data to validate")
    parser.add_argument(
        "--source",
        choices=["azure"],
        default="azure",
        help="Data source (Azure only)",
    )
    parser.add_argument("--seasons", type=int, nargs="+",
                       help="Specific seasons to validate")
    parser.add_argument("--comprehensive", action="store_true",
                       help="Validate all data sources")
    parser.add_argument("--report-only", action="store_true",
                       help="Only report issues, don't block")
    parser.add_argument("--lenient", action="store_true",
                       help="Use lenient validation")
    parser.add_argument("--output", type=Path,
                       help="Output path for report")

    args = parser.parse_args()

    strict_mode = not args.lenient
    report_only = args.report_only

    validator = CanonicalDataValidator(strict_mode=strict_mode, report_only=report_only)

    if args.comprehensive:
        results = validator.validate_all_sources()
    elif args.data_type:
        results = validator.validate_data_source(
            args.data_type, args.source, args.seasons
        )
    else:
        parser.error("Must specify --data-type or --comprehensive")

    # Save report
    if args.output:
        save_validation_report(results, args.output)

    # Exit with appropriate code
    passed = results.get("overall_passed")
    if passed is None:
        passed = results.get("passed", False)

    if not passed and not report_only:
        print("\nValidation FAILED - blocking data ingestion")
        sys.exit(1)
    else:
        print("\nValidation PASSED")


if __name__ == "__main__":
    main()
