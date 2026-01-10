#!/usr/bin/env python3
"""
DATA QUALITY GATES

Blocking validation that prevents bad data from entering the system.
Used by the canonical ingestion pipeline to enforce data quality standards.

Features:
- Blocking vs non-blocking validation modes
- Configurable quality thresholds
- Detailed error reporting
- Learning from past validations

Usage:
    from testing.canonical.quality_gates import DataQualityGate

    gate = DataQualityGate(strict_mode=True)
    result = gate.validate(df, data_type="scores")
    if not result.passed:
        raise ValueError(f"Data quality check failed: {result.errors}")
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum

import pandas as pd


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    CRITICAL = "critical"  # Blocks ingestion
    ERROR = "error"        # Blocks ingestion
    WARNING = "warning"    # Allows ingestion but logs
    INFO = "info"         # Just logs


@dataclass
class ValidationIssue:
    """A data quality validation issue."""
    rule_name: str
    severity: ValidationSeverity
    message: str
    field: Optional[str] = None
    row_indices: List[int] = field(default_factory=list)
    suggested_fix: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of data quality validation."""
    passed: bool
    total_records: int
    issues: List[ValidationIssue] = field(default_factory=list)
    blocked_records: int = 0
    warnings_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def has_critical_issues(self) -> bool:
        return any(issue.severity == ValidationSeverity.CRITICAL for issue in self.issues)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]
                  for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == ValidationSeverity.WARNING for issue in self.issues)

    def get_issues_by_severity(self, severity: ValidationSeverity) -> List[ValidationIssue]:
        """Get issues of a specific severity."""
        return [issue for issue in self.issues if issue.severity == severity]


@dataclass
class QualityRule:
    """A data quality validation rule."""
    name: str
    description: str
    validator: Callable[[pd.DataFrame], List[ValidationIssue]]
    severity: ValidationSeverity = ValidationSeverity.ERROR
    enabled: bool = True
    applies_to: List[str] = field(default_factory=lambda: ["all"])  # Data types this applies to


class DataQualityGate:
    """
    Data quality gate that validates data before ingestion.

    Provides blocking validation with configurable rules and severity levels.
    """

    def __init__(
        self,
        strict_mode: bool = True,
        enable_warnings: bool = True,
        custom_rules: Optional[List[QualityRule]] = None,
        config_file: Optional[Path] = None
    ):
        """
        Initialize the data quality gate.

        Args:
            strict_mode: Block on any error if True
            enable_warnings: Include warnings in results
            custom_rules: Additional custom validation rules
            config_file: Path to JSON config file with rule settings
        """
        self.strict_mode = strict_mode
        self.enable_warnings = enable_warnings

        # Build standard rules
        self._rules = self._build_standard_rules()

        # Add custom rules
        if custom_rules:
            self._rules.extend(custom_rules)

        # Load configuration
        if config_file and config_file.exists():
            self._load_config(config_file)

        # Validation history for learning
        self._validation_history: List[ValidationResult] = []

    def _build_standard_rules(self) -> List[QualityRule]:
        """Build the standard set of quality validation rules."""

        rules = [
            # Universal rules (apply to all data types)
            QualityRule(
                name="null_check",
                description="Check for excessive null values",
                validator=self._validate_null_values,
                severity=ValidationSeverity.ERROR,
                applies_to=["all"]
            ),

            QualityRule(
                name="duplicate_check",
                description="Check for duplicate records",
                validator=self._validate_duplicates,
                severity=ValidationSeverity.WARNING,
                applies_to=["all"]
            ),

            # Scores-specific rules
            QualityRule(
                name="scores_required_fields",
                description="Ensure required fields for scores data",
                validator=self._validate_scores_required_fields,
                severity=ValidationSeverity.CRITICAL,
                applies_to=["scores", "games"]
            ),

            QualityRule(
                name="scores_reasonable_values",
                description="Check scores are within reasonable ranges",
                validator=self._validate_scores_reasonable_values,
                severity=ValidationSeverity.ERROR,
                applies_to=["scores", "games"]
            ),

            QualityRule(
                name="scores_date_consistency",
                description="Validate date formats and ranges",
                validator=self._validate_date_consistency,
                severity=ValidationSeverity.ERROR,
                applies_to=["scores", "games", "odds"]
            ),

            QualityRule(
                name="scores_team_resolution",
                description="Ensure team names can be resolved",
                validator=self._validate_team_resolution,
                severity=ValidationSeverity.CRITICAL,
                applies_to=["scores", "games", "odds"]
            ),

            # Odds-specific rules
            QualityRule(
                name="odds_required_fields",
                description="Ensure required fields for odds data",
                validator=self._validate_odds_required_fields,
                severity=ValidationSeverity.CRITICAL,
                applies_to=["odds"]
            ),

            QualityRule(
                name="odds_spread_convention",
                description="Validate spread sign conventions",
                validator=self._validate_spread_convention,
                severity=ValidationSeverity.ERROR,
                applies_to=["odds"]
            ),

            QualityRule(
                name="odds_price_ranges",
                description="Check betting prices are reasonable",
                validator=self._validate_price_ranges,
                severity=ValidationSeverity.WARNING,
                applies_to=["odds"]
            ),

            # Ratings-specific rules
            QualityRule(
                name="ratings_value_ranges",
                description="Check rating values are reasonable",
                validator=self._validate_rating_ranges,
                severity=ValidationSeverity.WARNING,
                applies_to=["ratings"]
            ),

            # Cross-source consistency rules
            QualityRule(
                name="cross_source_consistency",
                description="Check consistency across data sources",
                validator=self._validate_cross_source_consistency,
                severity=ValidationSeverity.WARNING,
                applies_to=["merged", "backtest"]
            )
        ]

        return rules

    def validate(
        self,
        df: pd.DataFrame,
        data_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate a DataFrame against quality rules.

        Args:
            df: DataFrame to validate
            data_type: Type of data ("scores", "odds", "ratings", etc.)
            context: Additional context for validation

        Returns:
            ValidationResult with pass/fail status and issues
        """
        context = context or {}
        result = ValidationResult(passed=True, total_records=len(df))
        issues = []

        # Get applicable rules
        applicable_rules = [rule for rule in self._rules
                          if rule.enabled and
                          ("all" in rule.applies_to or data_type in rule.applies_to)]

        # Run each rule
        for rule in applicable_rules:
            try:
                rule_issues = rule.validator(df)
                for issue in rule_issues:
                    issue.rule_name = rule.name  # Ensure rule name is set

                    # Apply severity overrides based on context
                    if context.get("lenient_mode") and issue.severity == ValidationSeverity.WARNING:
                        issue.severity = ValidationSeverity.INFO

                    issues.append(issue)

            except Exception as e:
                # Rule execution error
                error_issue = ValidationIssue(
                    rule_name=rule.name,
                    severity=ValidationSeverity.ERROR,
                    message=f"Rule execution failed: {e}",
                    metadata={"error": str(e)}
                )
                issues.append(error_issue)

        result.issues = issues

        # Count issues by severity
        for issue in issues:
            if issue.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]:
                result.blocked_records += 1
            elif issue.severity == ValidationSeverity.WARNING:
                result.warnings_count += 1

        # Determine if validation passed
        if self.strict_mode:
            result.passed = not result.has_errors
        else:
            result.passed = not result.has_critical_issues

        # Store in history
        self._validation_history.append(result)

        return result

    def validate_and_raise(
        self,
        df: pd.DataFrame,
        data_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Validate DataFrame and raise exception if validation fails.

        Args:
            df: DataFrame to validate
            data_type: Type of data
            context: Validation context

        Returns:
            Original DataFrame if validation passes

        Raises:
            ValueError: If validation fails
        """
        result = self.validate(df, data_type, context)

        if not result.passed:
            error_msg = f"Data quality validation failed for {data_type}:\n"
            error_issues = [issue for issue in result.issues
                          if issue.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]]

            for issue in error_issues[:10]:  # Limit to first 10 errors
                error_msg += f"- {issue.severity.value.upper()}: {issue.message}\n"

            if len(error_issues) > 10:
                error_msg += f"- ... and {len(error_issues) - 10} more errors\n"

            raise ValueError(error_msg)

        return df

    # Individual validation rule implementations

    def _validate_null_values(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check for excessive null values in critical columns."""
        issues = []

        # Define critical columns by data type (this could be configurable)
        critical_columns = {
            "scores": ["home_team", "away_team", "date", "home_score", "away_score"],
            "odds": ["home_team", "away_team", "spread"],
            "ratings": ["team", "season"]
        }

        # Default critical columns
        critical_cols = critical_columns.get("default", ["home_team", "away_team", "date"])

        for col in critical_cols:
            if col in df.columns:
                null_count = df[col].isnull().sum()
                null_percentage = (null_count / len(df)) * 100

                if null_percentage > 5:  # More than 5% null
                    issues.append(ValidationIssue(
                        rule_name="null_check",
                        severity=ValidationSeverity.ERROR,
                        message=f"Column '{col}' has {null_percentage:.1f}% null values ({null_count}/{len(df)})",
                        field=col,
                        suggested_fix="Investigate data source or implement data imputation"
                    ))
                elif null_percentage > 1:  # Warning threshold
                    issues.append(ValidationIssue(
                        rule_name="null_check",
                        severity=ValidationSeverity.WARNING,
                        message=f"Column '{col}' has {null_percentage:.1f}% null values",
                        field=col
                    ))

        return issues

    def _validate_duplicates(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check for duplicate records."""
        issues = []

        # Define key columns for duplicate detection
        key_columns = []
        if "home_team" in df.columns and "away_team" in df.columns:
            key_columns = ["home_team", "away_team"]
            if "date" in df.columns:
                key_columns.append("date")

        if key_columns:
            duplicates = df[df.duplicated(subset=key_columns, keep=False)]
            if len(duplicates) > 0:
                issues.append(ValidationIssue(
                    rule_name="duplicate_check",
                    severity=ValidationSeverity.WARNING,
                    message=f"Found {len(duplicates)} duplicate records based on {key_columns}",
                    row_indices=duplicates.index.tolist(),
                    suggested_fix="Remove duplicates or investigate data source"
                ))

        return issues

    def _validate_scores_required_fields(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate required fields for scores data."""
        issues = []
        required_fields = ["home_team", "away_team", "date"]

        missing_fields = [field for field in required_fields if field not in df.columns]
        if missing_fields:
            issues.append(ValidationIssue(
                rule_name="scores_required_fields",
                severity=ValidationSeverity.CRITICAL,
                message=f"Missing required fields: {missing_fields}",
                suggested_fix="Add missing columns or check data source"
            ))

        return issues

    def _validate_scores_reasonable_values(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check scores are within reasonable ranges."""
        issues = []

        score_columns = ["home_score", "away_score", "home_h1", "away_h1"]

        for col in score_columns:
            if col in df.columns:
                scores = df[col].dropna()
                if len(scores) > 0:
                    # Check for negative scores
                    negative_scores = scores[scores < 0]
                    if len(negative_scores) > 0:
                        issues.append(ValidationIssue(
                            rule_name="scores_reasonable_values",
                            severity=ValidationSeverity.ERROR,
                            message=f"Column '{col}' has {len(negative_scores)} negative values",
                            field=col,
                            row_indices=negative_scores.index.tolist()[:10],
                            suggested_fix="Negative scores are invalid"
                        ))

                    # Check for unreasonably high scores
                    high_scores = scores[scores > 200]
                    if len(high_scores) > 0:
                        issues.append(ValidationIssue(
                            rule_name="scores_reasonable_values",
                            severity=ValidationSeverity.WARNING,
                            message=f"Column '{col}' has {len(high_scores)} scores > 200",
                            field=col,
                            row_indices=high_scores.index.tolist()[:10],
                            suggested_fix="Review unusually high scores"
                        ))

        return issues

    def _validate_date_consistency(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate date formats and ranges."""
        issues = []

        date_columns = ["date", "game_date"]

        for col in date_columns:
            if col in df.columns:
                try:
                    dates = pd.to_datetime(df[col], errors='coerce')
                    invalid_dates = dates.isnull().sum()

                    if invalid_dates > 0:
                        issues.append(ValidationIssue(
                            rule_name="scores_date_consistency",
                            severity=ValidationSeverity.ERROR,
                            message=f"Column '{col}' has {invalid_dates} invalid date values",
                            field=col,
                            suggested_fix="Fix date format or remove invalid dates"
                        ))

                    # Check date ranges (reasonable NCAA seasons)
                    valid_dates = dates.dropna()
                    if len(valid_dates) > 0:
                        min_date = valid_dates.min()
                        max_date = valid_dates.max()

                        # NCAA seasons typically Aug-Dec (next year) and Jan-Mar
                        if min_date.year < 2000 or max_date.year > 2030:
                            issues.append(ValidationIssue(
                                rule_name="scores_date_consistency",
                                severity=ValidationSeverity.WARNING,
                                message=f"Dates range from {min_date.date()} to {max_date.date()} - check if reasonable",
                                field=col,
                                suggested_fix="Verify date range is correct for NCAA data"
                            ))

                except Exception as e:
                    issues.append(ValidationIssue(
                        rule_name="scores_date_consistency",
                        severity=ValidationSeverity.ERROR,
                        message=f"Failed to parse dates in '{col}': {e}",
                        field=col,
                        suggested_fix="Check date format"
                    ))

        return issues

    def _validate_team_resolution(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate team names can be resolved."""
        from .team_resolution_service import get_team_resolver

        issues = []
        resolver = get_team_resolver()

        team_columns = ["home_team", "away_team", "team_home", "team_away"]

        unresolved_teams = set()
        low_confidence_teams = set()

        for col in team_columns:
            if col in df.columns:
                for idx, team in df[col].dropna().items():
                    result = resolver.resolve(str(team))

                    if result.confidence == 0:
                        unresolved_teams.add(team)
                    elif result.confidence < 80:
                        low_confidence_teams.add(team)

        if unresolved_teams:
            issues.append(ValidationIssue(
                rule_name="scores_team_resolution",
                severity=ValidationSeverity.CRITICAL,
                message=f"Unresolved team names: {list(unresolved_teams)[:5]}{'...' if len(unresolved_teams) > 5 else ''}",
                suggested_fix="Add team name aliases or check data source"
            ))

        if low_confidence_teams:
            issues.append(ValidationIssue(
                rule_name="scores_team_resolution",
                severity=ValidationSeverity.WARNING,
                message=f"Low confidence team name matches: {list(low_confidence_teams)[:5]}{'...' if len(low_confidence_teams) > 5 else ''}",
                suggested_fix="Review team name aliases"
            ))

        return issues

    def _validate_odds_required_fields(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate required fields for odds data."""
        issues = []
        required_fields = ["home_team", "away_team"]

        # At least one of spread, total, or moneyline
        odds_fields = ["spread", "total", "moneyline_home", "moneyline_away"]
        has_odds = any(field in df.columns for field in odds_fields)

        missing_fields = [field for field in required_fields if field not in df.columns]
        if missing_fields:
            issues.append(ValidationIssue(
                rule_name="odds_required_fields",
                severity=ValidationSeverity.CRITICAL,
                message=f"Missing required fields: {missing_fields}",
                suggested_fix="Add missing columns"
            ))

        if not has_odds:
            issues.append(ValidationIssue(
                rule_name="odds_required_fields",
                severity=ValidationSeverity.CRITICAL,
                message="No odds fields found (spread, total, moneyline)",
                suggested_fix="Add odds data columns"
            ))

        return issues

    def _validate_spread_convention(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate spread sign conventions."""
        issues = []

        if "spread" in df.columns:
            spreads = df["spread"].dropna()

            # This is a simplified check - would need more context
            # In betting, spreads can be positive or negative depending on convention
            extreme_spreads = spreads[abs(spreads) > 50]  # Very large spreads
            if len(extreme_spreads) > 0:
                issues.append(ValidationIssue(
                    rule_name="odds_spread_convention",
                    severity=ValidationSeverity.WARNING,
                    message=f"Found {len(extreme_spreads)} spreads > 50 or < -50",
                    suggested_fix="Verify spread convention and units"
                ))

        return issues

    def _validate_price_ranges(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate betting price ranges."""
        issues = []

        price_columns = ["spread_price", "total_price", "moneyline_home", "moneyline_away"]

        for col in price_columns:
            if col in df.columns:
                prices = df[col].dropna()

                # American odds range check
                invalid_prices = prices[(prices > 1000) | (prices < -1000) | (prices == 0)]
                if len(invalid_prices) > 0:
                    issues.append(ValidationIssue(
                        rule_name="odds_price_ranges",
                        severity=ValidationSeverity.WARNING,
                        message=f"Column '{col}' has {len(invalid_prices)} invalid price values",
                        field=col,
                        row_indices=invalid_prices.index.tolist()[:10],
                        suggested_fix="Check price format and ranges"
                    ))

        return issues

    def _validate_rating_ranges(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate rating value ranges."""
        issues = []

        rating_columns = ["adj_o", "adj_d", "adj_t", "overall_rating"]

        for col in rating_columns:
            if col in df.columns:
                ratings = df[col].dropna()

                # Barttorvik ratings are typically 50-150 range
                invalid_ratings = ratings[(ratings < 0) | (ratings > 200)]
                if len(invalid_ratings) > 0:
                    issues.append(ValidationIssue(
                        rule_name="ratings_value_ranges",
                        severity=ValidationSeverity.WARNING,
                        message=f"Column '{col}' has {len(invalid_ratings)} ratings outside 0-200 range",
                        field=col,
                        row_indices=invalid_ratings.index.tolist()[:10],
                        suggested_fix="Check rating scale and units"
                    ))

        return issues

    def _validate_cross_source_consistency(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate consistency across data sources (for merged datasets)."""
        issues = []

        # This would check for things like:
        # - Same game having different scores from different sources
        # - Conflicting odds from different sources
        # - etc.

        # Placeholder implementation
        if "data_source" in df.columns:
            source_counts = df["data_source"].value_counts()
            if len(source_counts) > 1:
                issues.append(ValidationIssue(
                    rule_name="cross_source_consistency",
                    severity=ValidationSeverity.INFO,
                    message=f"Data from {len(source_counts)} sources: {dict(source_counts)}",
                    suggested_fix="Review cross-source consistency if needed"
                ))

        return issues

    def _load_config(self, config_file: Path):
        """Load configuration from JSON file."""
        try:
            with open(config_file) as f:
                config = json.load(f)

            # Apply rule configurations
            for rule_config in config.get("rules", []):
                rule_name = rule_config.get("name")
                for rule in self._rules:
                    if rule.name == rule_name:
                        if "enabled" in rule_config:
                            rule.enabled = rule_config["enabled"]
                        if "severity" in rule_config:
                            rule.severity = ValidationSeverity(rule_config["severity"])
                        break

        except Exception as e:
            print(f"Warning: Failed to load quality gate config: {e}")

    def get_validation_history(self) -> List[ValidationResult]:
        """Get validation history."""
        return self._validation_history.copy()

    def get_rule_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics about rule performance."""
        stats = {}

        for rule in self._rules:
            rule_results = [result for result in self._validation_history
                          if any(issue.rule_name == rule.name for issue in result.issues)]

            stats[rule.name] = {
                "executions": len(rule_results),
                "failures": len([r for r in rule_results if not r.passed]),
                "enabled": rule.enabled,
                "severity": rule.severity.value
            }

        return stats


# Convenience functions
def validate_data_quality(df: pd.DataFrame, data_type: str, **kwargs) -> ValidationResult:
    """Convenience function for data quality validation."""
    gate = DataQualityGate(**kwargs)
    return gate.validate(df, data_type)


def validate_and_clean_data(df: pd.DataFrame, data_type: str, **kwargs) -> pd.DataFrame:
    """Convenience function that validates and raises on failure."""
    gate = DataQualityGate(**kwargs)
    return gate.validate_and_raise(df, data_type)