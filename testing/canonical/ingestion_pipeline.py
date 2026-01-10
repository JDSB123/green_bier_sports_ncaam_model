#!/usr/bin/env python3
"""
CANONICAL DATA INGESTION PIPELINE

Orchestrates data ingestion with validation, transformation, and canonicalization.
All data ingestion should go through this pipeline to ensure consistency.

Features:
- Team name canonicalization
- Data quality validation
- Schema enforcement
- Error handling and reporting
- Audit trail generation

Usage:
    from testing.canonical.ingestion_pipeline import CanonicalIngestionPipeline

    pipeline = CanonicalIngestionPipeline()
    result = pipeline.ingest_scores_data(df, source="ESPN")
"""

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum

import pandas as pd

from .team_resolution_service import get_team_resolver, ResolutionResult


class DataSource(Enum):
    """Supported data sources."""
    ESPN_SCORES = "espn_scores"
    ESPN_ODDS = "espn_odds"
    BARTTORVIK = "barttorvik"
    NCAAHOOPR = "ncaahoopR"
    ODDS_API = "odds_api"
    UNKNOWN = "unknown"


class IngestionStage(Enum):
    """Stages of the ingestion pipeline."""
    VALIDATION = "validation"
    CANONICALIZATION = "canonicalization"
    TRANSFORMATION = "transformation"
    QUALITY_CHECK = "quality_check"
    STORAGE = "storage"


@dataclass
class IngestionResult:
    """Result of data ingestion."""
    success: bool
    records_processed: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    transformations_applied: List[str] = field(default_factory=list)
    canonicalization_stats: Dict[str, int] = field(default_factory=dict)
    data_hash: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


@dataclass
class DataQualityRule:
    """A data quality validation rule."""
    name: str
    description: str
    validator: Callable[[pd.DataFrame], List[str]]
    severity: str = "error"  # "error" or "warning"
    enabled: bool = True


class CanonicalIngestionPipeline:
    """
    Canonical data ingestion pipeline.

    Orchestrates the entire ingestion process:
    1. Validation - Check data quality and completeness
    2. Canonicalization - Resolve team names, standardize formats
    3. Transformation - Apply business rules and calculations
    4. Quality Check - Final validation before storage
    5. Storage - Save to canonical location with audit trail
    """

    def __init__(
        self,
        team_resolver=None,
        strict_mode: bool = True,
        enable_audit: bool = True
    ):
        """
        Initialize the ingestion pipeline.

        Args:
            team_resolver: Team resolution service (auto-created if None)
            strict_mode: Fail on any error if True
            enable_audit: Generate audit trails if True
        """
        self.team_resolver = team_resolver or get_team_resolver()
        self.strict_mode = strict_mode
        self.enable_audit = enable_audit

        # Quality rules for different data types
        self._quality_rules = self._build_quality_rules()

        # Audit log
        self._audit_log: List[Dict] = []

    def _build_quality_rules(self) -> Dict[str, List[DataQualityRule]]:
        """Build data quality validation rules."""

        rules = {}

        # Scores data rules
        rules["scores"] = [
            DataQualityRule(
                name="required_columns",
                description="Check for required columns",
                validator=self._validate_required_columns,
                severity="error"
            ),
            DataQualityRule(
                name="non_null_scores",
                description="Ensure scores are not null for completed games",
                validator=self._validate_non_null_scores,
                severity="error"
            ),
            DataQualityRule(
                name="reasonable_scores",
                description="Check scores are within reasonable ranges",
                validator=self._validate_reasonable_scores,
                severity="warning"
            ),
            DataQualityRule(
                name="date_format",
                description="Validate date formats",
                validator=self._validate_date_format,
                severity="error"
            ),
            DataQualityRule(
                name="team_resolution",
                description="Ensure teams can be resolved",
                validator=self._validate_team_resolution,
                severity="error"
            )
        ]

        # Odds data rules
        rules["odds"] = [
            DataQualityRule(
                name="required_columns",
                description="Check for required columns",
                validator=self._validate_odds_columns,
                severity="error"
            ),
            DataQualityRule(
                name="spread_sign_convention",
                description="Validate spread sign conventions",
                validator=self._validate_spread_signs,
                severity="error"
            ),
            DataQualityRule(
                name="price_ranges",
                description="Check betting prices are reasonable",
                validator=self._validate_price_ranges,
                severity="warning"
            )
        ]

        # Ratings data rules
        rules["ratings"] = [
            DataQualityRule(
                name="rating_ranges",
                description="Check rating values are reasonable",
                validator=self._validate_rating_ranges,
                severity="warning"
            )
        ]

        return rules

    def ingest_scores_data(
        self,
        df: pd.DataFrame,
        source: Union[str, DataSource],
        season: Optional[int] = None
    ) -> IngestionResult:
        """
        Ingest scores data through the canonical pipeline.

        Args:
            df: Raw scores DataFrame
            source: Data source identifier
            season: Season year (inferred if not provided)

        Returns:
            IngestionResult with processing details
        """
        if isinstance(source, str):
            source = DataSource(source)

        result = IngestionResult(success=True, records_processed=len(df))

        try:
            # Stage 1: Validation
            self._log_stage(IngestionStage.VALIDATION, f"Validating {len(df)} records from {source.value}")
            validation_errors = self._run_quality_checks(df, "scores")
            if validation_errors["errors"]:
                if self.strict_mode:
                    result.success = False
                    result.errors.extend(validation_errors["errors"])
                    return result
                else:
                    result.warnings.extend(validation_errors["errors"])

            # Stage 2: Canonicalization
            self._log_stage(IngestionStage.CANONICALIZATION, "Canonicalizing team names")
            df_canonical, canon_stats = self._canonicalize_scores_data(df)
            result.canonicalization_stats = canon_stats
            result.transformations_applied.append("team_canonicalization")

            # Stage 3: Transformation
            self._log_stage(IngestionStage.TRANSFORMATION, "Applying data transformations")
            df_transformed = self._transform_scores_data(df_canonical, source, season)
            result.transformations_applied.append("scores_transformation")

            # Stage 4: Final Quality Check
            self._log_stage(IngestionStage.QUALITY_CHECK, "Final quality validation")
            final_errors = self._run_quality_checks(df_transformed, "scores")
            if final_errors["errors"]:
                result.errors.extend(final_errors["errors"])
                result.success = False
                return result

            # Stage 5: Storage (placeholder - would integrate with Azure)
            self._log_stage(IngestionStage.STORAGE, "Preparing for storage")
            result.data_hash = self._generate_data_hash(df_transformed)
            result.records_accepted = len(df_transformed)

            result.success = True

        except Exception as e:
            result.success = False
            result.errors.append(f"Pipeline error: {str(e)}")
            self._log_error(f"Pipeline failed: {e}")

        return result

    def ingest_odds_data(
        self,
        df: pd.DataFrame,
        source: Union[str, DataSource],
        market: str = "fg_spread"
    ) -> IngestionResult:
        """
        Ingest odds data through the canonical pipeline.

        Args:
            df: Raw odds DataFrame
            source: Data source identifier
            market: Odds market type

        Returns:
            IngestionResult with processing details
        """
        if isinstance(source, str):
            source = DataSource(source)

        result = IngestionResult(success=True, records_processed=len(df))

        try:
            # Similar pipeline stages as scores...
            self._log_stage(IngestionStage.VALIDATION, f"Validating odds data from {source.value}")

            # Validation
            validation_errors = self._run_quality_checks(df, "odds")
            if validation_errors["errors"]:
                if self.strict_mode:
                    result.success = False
                    result.errors.extend(validation_errors["errors"])
                    return result

            # Canonicalization
            df_canonical, canon_stats = self._canonicalize_odds_data(df)
            result.canonicalization_stats = canon_stats

            # Transformation
            df_transformed = self._transform_odds_data(df_canonical, market)

            # Quality Check
            final_errors = self._run_quality_checks(df_transformed, "odds")
            if final_errors["errors"]:
                result.errors.extend(final_errors["errors"])
                result.success = False
                return result

            result.records_accepted = len(df_transformed)
            result.data_hash = self._generate_data_hash(df_transformed)
            result.success = True

        except Exception as e:
            result.success = False
            result.errors.append(f"Pipeline error: {str(e)}")

        return result

    def _canonicalize_scores_data(self, df: pd.DataFrame) -> tuple[pd.DataFrame, Dict[str, int]]:
        """Canonicalize team names in scores data."""
        df_copy = df.copy()
        stats = {"resolved": 0, "unresolved": 0, "conflicts": 0}

        team_columns = []
        if "home_team" in df.columns:
            team_columns.append("home_team")
        if "away_team" in df.columns:
            team_columns.append("away_team")

        for col in team_columns:
            if col not in df_copy.columns:
                continue

            resolved_names = []
            for name in df_copy[col]:
                if pd.isna(name):
                    resolved_names.append(name)
                    continue

                result = self.team_resolver.resolve(str(name))
                resolved_names.append(result.canonical_name)

                if result.confidence >= 80:
                    stats["resolved"] += 1
                elif result.confidence > 0:
                    stats["conflicts"] += 1
                else:
                    stats["unresolved"] += 1

            df_copy[col] = resolved_names

        return df_copy, stats

    def _canonicalize_odds_data(self, df: pd.DataFrame) -> tuple[pd.DataFrame, Dict[str, int]]:
        """Canonicalize team names in odds data."""
        df_copy = df.copy()
        stats = {"resolved": 0, "unresolved": 0, "conflicts": 0}

        # Odds data might have different column names
        team_columns = ["home_team", "away_team", "team_home", "team_away"]
        for col in team_columns:
            if col in df_copy.columns:
                resolved_names = []
                for name in df_copy[col]:
                    if pd.isna(name):
                        resolved_names.append(name)
                        continue

                    result = self.team_resolver.resolve(str(name))
                    resolved_names.append(result.canonical_name)

                    if result.confidence >= 80:
                        stats["resolved"] += 1
                    elif result.confidence > 0:
                        stats["conflicts"] += 1
                    else:
                        stats["unresolved"] += 1

                df_copy[col] = resolved_names

        return df_copy, stats

    def _transform_scores_data(
        self,
        df: pd.DataFrame,
        source: DataSource,
        season: Optional[int]
    ) -> pd.DataFrame:
        """Apply transformations to scores data."""
        df_copy = df.copy()

        # Standardize date formats
        if "date" in df_copy.columns:
            df_copy["date"] = pd.to_datetime(df_copy["date"]).dt.date

        # Add season if not present
        if season and "season" not in df_copy.columns:
            df_copy["season"] = season

        # Calculate totals
        if "home_score" in df_copy.columns and "away_score" in df_copy.columns:
            df_copy["total_score"] = df_copy["home_score"] + df_copy["away_score"]

        # Add data source
        df_copy["data_source"] = source.value

        return df_copy

    def _transform_odds_data(self, df: pd.DataFrame, market: str) -> pd.DataFrame:
        """Apply transformations to odds data."""
        df_copy = df.copy()

        # Standardize market
        df_copy["market"] = market

        # Ensure spread signs are correct (home favorite = negative)
        if "spread" in df_copy.columns:
            # Validation will catch sign issues
            pass

        return df_copy

    def _run_quality_checks(self, df: pd.DataFrame, data_type: str) -> Dict[str, List[str]]:
        """Run quality checks for the given data type."""
        errors = []
        warnings = []

        if data_type not in self._quality_rules:
            warnings.append(f"No quality rules defined for data type: {data_type}")
            return {"errors": errors, "warnings": warnings}

        for rule in self._quality_rules[data_type]:
            if not rule.enabled:
                continue

            try:
                rule_errors = rule.validator(df)
                if rule_errors:
                    if rule.severity == "error":
                        errors.extend([f"{rule.name}: {err}" for err in rule_errors])
                    else:
                        warnings.extend([f"{rule.name}: {warn}" for warn in rule_errors])
            except Exception as e:
                errors.append(f"Rule {rule.name} failed: {e}")

        return {"errors": errors, "warnings": warnings}

    # Quality validation methods
    def _validate_required_columns(self, df: pd.DataFrame) -> List[str]:
        """Validate required columns are present."""
        required_cols = ["home_team", "away_team", "date"]
        missing = [col for col in required_cols if col not in df.columns]
        return [f"Missing required columns: {missing}"] if missing else []

    def _validate_non_null_scores(self, df: pd.DataFrame) -> List[str]:
        """Validate scores are not null for games that should have scores."""
        errors = []
        score_cols = ["home_score", "away_score"]

        for col in score_cols:
            if col in df.columns:
                null_count = df[col].isnull().sum()
                if null_count > 0:
                    errors.append(f"{null_count} null values in {col}")

        return errors

    def _validate_reasonable_scores(self, df: pd.DataFrame) -> List[str]:
        """Validate scores are within reasonable ranges."""
        warnings = []

        for col in ["home_score", "away_score", "home_h1", "away_h1"]:
            if col in df.columns:
                scores = df[col].dropna()
                if len(scores) > 0:
                    unreasonable = scores[(scores < 0) | (scores > 200)]
                    if len(unreasonable) > 0:
                        warnings.append(f"{len(unreasonable)} unreasonable values in {col}: {unreasonable.tolist()[:5]}...")

        return warnings

    def _validate_date_format(self, df: pd.DataFrame) -> List[str]:
        """Validate date formats."""
        errors = []

        date_cols = ["date", "game_date"]
        for col in date_cols:
            if col in df.columns:
                try:
                    pd.to_datetime(df[col])
                except Exception as e:
                    errors.append(f"Invalid dates in {col}: {e}")

        return errors

    def _validate_team_resolution(self, df: pd.DataFrame) -> List[str]:
        """Validate team names can be resolved."""
        errors = []
        unresolved_teams = set()

        team_cols = ["home_team", "away_team"]
        for col in team_cols:
            if col in df.columns:
                for team in df[col].dropna().unique():
                    result = self.team_resolver.resolve(str(team))
                    if result.confidence < 50:  # Low confidence threshold
                        unresolved_teams.add(team)

        if unresolved_teams:
            errors.append(f"Unresolved teams: {list(unresolved_teams)[:10]}...")

        return errors

    def _validate_odds_columns(self, df: pd.DataFrame) -> List[str]:
        """Validate odds data has required columns."""
        required_cols = ["home_team", "away_team", "spread"]
        missing = [col for col in required_cols if col not in df.columns]
        return [f"Missing required columns: {missing}"] if missing else []

    def _validate_spread_signs(self, df: pd.DataFrame) -> List[str]:
        """Validate spread sign conventions."""
        errors = []

        if "spread" in df.columns:
            spreads = df["spread"].dropna()
            # Home favorites should have negative spreads
            invalid_signs = spreads[spreads > 0]  # This is simplistic - would need more logic
            if len(invalid_signs) > 0:
                errors.append(f"{len(invalid_signs)} spreads with potentially incorrect signs")

        return errors

    def _validate_price_ranges(self, df: pd.DataFrame) -> List[str]:
        """Validate betting prices are reasonable."""
        warnings = []

        price_cols = ["spread_price", "total_price", "moneyline_price"]
        for col in price_cols:
            if col in df.columns:
                prices = df[col].dropna()
                if len(prices) > 0:
                    unreasonable = prices[(prices < -1000) | (prices > 1000)]
                    if len(unreasonable) > 0:
                        warnings.append(f"{len(unreasonable)} unreasonable prices in {col}")

        return warnings

    def _validate_rating_ranges(self, df: pd.DataFrame) -> List[str]:
        """Validate rating values are reasonable."""
        warnings = []

        rating_cols = ["adj_o", "adj_d", "adj_t"]
        for col in rating_cols:
            if col in df.columns:
                ratings = df[col].dropna()
                if len(ratings) > 0:
                    unreasonable = ratings[(ratings < 50) | (ratings > 150)]
                    if len(unreasonable) > 0:
                        warnings.append(f"{len(unreasonable)} unreasonable ratings in {col}")

        return warnings

    def _generate_data_hash(self, df: pd.DataFrame) -> str:
        """Generate a hash of the DataFrame for integrity checking."""
        # Simple hash based on key columns
        key_data = ""
        if "home_team" in df.columns and "away_team" in df.columns:
            key_data = df[["home_team", "away_team"]].to_string()

        return hashlib.md5(key_data.encode()).hexdigest()[:16]

    def _log_stage(self, stage: IngestionStage, message: str):
        """Log a pipeline stage."""
        if self.enable_audit:
            self._audit_log.append({
                "stage": stage.value,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
        print(f"[{stage.value.upper()}] {message}")

    def _log_error(self, message: str):
        """Log an error."""
        if self.enable_audit:
            self._audit_log.append({
                "stage": "error",
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
        print(f"[ERROR] {message}")

    def get_audit_log(self) -> List[Dict]:
        """Get the audit log."""
        return self._audit_log.copy()


# Convenience functions
def ingest_scores_data(df: pd.DataFrame, source: str, **kwargs) -> IngestionResult:
    """Convenience function for ingesting scores data."""
    pipeline = CanonicalIngestionPipeline()
    return pipeline.ingest_scores_data(df, source, **kwargs)


def ingest_odds_data(df: pd.DataFrame, source: str, **kwargs) -> IngestionResult:
    """Convenience function for ingesting odds data."""
    pipeline = CanonicalIngestionPipeline()
    return pipeline.ingest_odds_data(df, source, **kwargs)