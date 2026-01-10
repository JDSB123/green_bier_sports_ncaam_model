#!/usr/bin/env python3
"""
DATA QUALITY GATES - PRODUCTION VERSION

Blocking validation that prevents bad data from entering the system.
Simplified version for production deployment.

This is a production copy of testing/canonical/quality_gates.py
"""

import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


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


class DataQualityGate:
    """
    Data quality gate that validates data before ingestion.

    Provides blocking validation with configurable rules and severity levels.
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the data quality gate.

        Args:
            strict_mode: Block on any error if True
        """
        self.strict_mode = strict_mode

    def validate(self, df: pd.DataFrame, data_type: str) -> ValidationResult:
        """
        Validate a DataFrame against quality rules.

        Args:
            df: DataFrame to validate
            data_type: Type of data ("scores", "odds", "ratings")

        Returns:
            ValidationResult with pass/fail status and issues
        """
        result = ValidationResult(passed=True, total_records=len(df))
        issues = []

        # Run validation rules based on data type
        if data_type in ["scores", "games"]:
            issues.extend(self._validate_scores_data(df))
        elif data_type in ["odds"]:
            issues.extend(self._validate_odds_data(df))
        elif data_type in ["ratings"]:
            issues.extend(self._validate_ratings_data(df))

        # Add universal validations
        issues.extend(self._validate_universal(df))

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

        return result

    def _validate_universal(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate universal rules applicable to all data types."""
        issues = []

        # Check for null values in critical columns
        for col in df.columns:
            if df[col].isnull().sum() > len(df) * 0.05:  # More than 5% null
                issues.append(ValidationIssue(
                    rule_name="null_check",
                    severity=ValidationSeverity.WARNING,
                    message=f"Column '{col}' has >5% null values",
                    field=col
                ))

        # Check for duplicate records
        if len(df) > 0:
            duplicates = df.duplicated().sum()
            if duplicates > 0:
                issues.append(ValidationIssue(
                    rule_name="duplicate_check",
                    severity=ValidationSeverity.WARNING,
                    message=f"Found {duplicates} duplicate records",
                    suggested_fix="Remove duplicate records"
                ))

        return issues

    def _validate_scores_data(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate scores data."""
        issues = []

        required_fields = ["home_team", "away_team", "date"]
        for field in required_fields:
            if field not in df.columns:
                issues.append(ValidationIssue(
                    rule_name="required_fields",
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Missing required field: {field}",
                    field=field
                ))

        # Check score ranges
        score_cols = ["home_score", "away_score", "home_h1", "away_h1"]
        for col in score_cols:
            if col in df.columns:
                scores = df[col].dropna()
                if len(scores) > 0:
                    if (scores < 0).any():
                        issues.append(ValidationIssue(
                            rule_name="score_ranges",
                            severity=ValidationSeverity.ERROR,
                            message=f"Negative scores found in {col}",
                            field=col
                        ))
                    if (scores > 200).any():
                        issues.append(ValidationIssue(
                            rule_name="score_ranges",
                            severity=ValidationSeverity.WARNING,
                            message=f"Unusually high scores found in {col}",
                            field=col
                        ))

        return issues

    def _validate_odds_data(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate odds data."""
        issues = []

        # Check for odds fields
        odds_fields = ["spread", "total", "moneyline_home", "moneyline_away"]
        has_odds = any(field in df.columns for field in odds_fields)

        if not has_odds:
            issues.append(ValidationIssue(
                rule_name="odds_fields",
                severity=ValidationSeverity.CRITICAL,
                message="No odds fields found (spread, total, moneyline)",
                suggested_fix="Add odds data columns"
            ))

        # Check spread conventions
        if "spread" in df.columns:
            spreads = df["spread"].dropna()
            if len(spreads) > 0:
                extreme_spreads = spreads[abs(spreads) > 50]
                if len(extreme_spreads) > 0:
                    issues.append(ValidationIssue(
                        rule_name="spread_convention",
                        severity=ValidationSeverity.WARNING,
                        message=f"Found {len(extreme_spreads)} spreads >50 or <-50",
                        field="spread"
                    ))

        return issues

    def _validate_ratings_data(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate ratings data."""
        issues = []

        # Check rating value ranges
        rating_cols = ["adj_o", "adj_d", "adj_t", "overall_rating"]
        for col in rating_cols:
            if col in df.columns:
                ratings = df[col].dropna()
                if len(ratings) > 0:
                    invalid_ratings = ratings[(ratings < 0) | (ratings > 200)]
                    if len(invalid_ratings) > 0:
                        issues.append(ValidationIssue(
                            rule_name="rating_ranges",
                            severity=ValidationSeverity.WARNING,
                            message=f"Column '{col}' has ratings outside 0-200 range",
                            field=col
                        ))

        return issues