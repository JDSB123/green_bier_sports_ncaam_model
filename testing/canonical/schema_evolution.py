#!/usr/bin/env python3
"""
SCHEMA EVOLUTION MANAGER

Handles schema versioning and evolution for historical data.
Different historical data vintages have different quality standards and schemas.

Features:
- Schema versioning by data vintage
- Automatic schema upgrades
- Quality standard adjustments by era
- Migration path definitions

Usage:
    from testing.canonical.schema_evolution import SchemaEvolutionManager

    manager = SchemaEvolutionManager()
    upgraded_df = manager.upgrade_schema(df, target_version="v2", data_type="scores")
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum

import pandas as pd


class DataVintage(Enum):
    """Data quality vintages by historical period."""
    LEGACY = "legacy"         # Pre-2020: Poor quality, incomplete
    TRANSITIONAL = "transitional"  # 2020-2022: Improving quality
    MODERN = "modern"         # 2023+: High quality, comprehensive
    CANONICAL = "canonical"   # Post-standardization


@dataclass
class SchemaVersion:
    """A data schema version definition."""
    version: str
    vintage: DataVintage
    description: str
    required_fields: List[str]
    optional_fields: List[str]
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    quality_standards: Dict[str, Any] = field(default_factory=dict)
    created_date: datetime = field(default_factory=datetime.now)

    def supports_field(self, field_name: str) -> bool:
        """Check if this schema version supports a field."""
        return field_name in self.required_fields or field_name in self.optional_fields

    def get_quality_threshold(self, metric: str) -> Any:
        """Get quality threshold for a metric."""
        return self.quality_standards.get(metric)


@dataclass
class SchemaMigration:
    """A migration path between schema versions."""
    from_version: str
    to_version: str
    migration_function: Callable[[pd.DataFrame], pd.DataFrame]
    description: str
    safe_to_automigrate: bool = True
    requires_manual_review: bool = False


class SchemaEvolutionManager:
    """
    Manages schema evolution for historical data.

    Handles different data quality standards across historical periods
    and provides migration paths between schema versions.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the schema evolution manager.

        Args:
            config_dir: Directory containing schema definitions
        """
        if config_dir is None:
            config_dir = Path(__file__).parent / "schemas"

        self.config_dir = config_dir
        self.config_dir.mkdir(exist_ok=True)

        # Load schema definitions
        self._schemas = self._load_schemas()
        self._migrations = self._build_migrations()

        # Current canonical schema
        self._canonical_version = "v3.0"

    def _load_schemas(self) -> Dict[str, SchemaVersion]:
        """Load schema definitions from config files."""
        schemas = {}

        # Define built-in schemas
        schemas["v1.0"] = SchemaVersion(
            version="v1.0",
            vintage=DataVintage.LEGACY,
            description="Legacy schema: Basic scores data with poor quality",
            required_fields=["home_team", "away_team", "home_score", "away_score"],
            optional_fields=["date", "season"],
            quality_standards={
                "null_threshold": 0.20,  # 20% nulls acceptable
                "duplicate_threshold": 0.10,  # 10% duplicates acceptable
                "team_resolution_threshold": 0.70  # 70% teams resolvable
            }
        )

        schemas["v2.0"] = SchemaVersion(
            version="v2.0",
            vintage=DataVintage.TRANSITIONAL,
            description="Transitional schema: Improved quality with odds integration",
            required_fields=["home_team", "away_team", "date", "home_score", "away_score"],
            optional_fields=["season", "spread", "total", "home_h1", "away_h1"],
            quality_standards={
                "null_threshold": 0.10,  # 10% nulls acceptable
                "duplicate_threshold": 0.05,  # 5% duplicates acceptable
                "team_resolution_threshold": 0.85  # 85% teams resolvable
            }
        )

        schemas["v3.0"] = SchemaVersion(
            version="v3.0",
            vintage=DataVintage.MODERN,
            description="Modern canonical schema: High quality with comprehensive data",
            required_fields=["home_team", "away_team", "date", "season", "home_score", "away_score"],
            optional_fields=[
                "spread", "total", "moneyline_home", "moneyline_away",
                "home_h1", "away_h1", "ratings_home", "ratings_away",
                "data_source", "canonicalized_at"
            ],
            quality_standards={
                "null_threshold": 0.02,  # 2% nulls acceptable
                "duplicate_threshold": 0.01,  # 1% duplicates acceptable
                "team_resolution_threshold": 0.98  # 98% teams resolvable
            }
        )

        # Try to load additional schemas from files
        schema_files = list(self.config_dir.glob("*.json"))
        for schema_file in schema_files:
            try:
                with open(schema_file) as f:
                    schema_data = json.load(f)

                schema = SchemaVersion(
                    version=schema_data["version"],
                    vintage=DataVintage(schema_data["vintage"]),
                    description=schema_data["description"],
                    required_fields=schema_data["required_fields"],
                    optional_fields=schema_data.get("optional_fields", []),
                    transformations=schema_data.get("transformations", []),
                    quality_standards=schema_data.get("quality_standards", {})
                )
                schemas[schema.version] = schema

            except Exception as e:
                print(f"Warning: Failed to load schema from {schema_file}: {e}")

        return schemas

    def _build_migrations(self) -> Dict[str, SchemaMigration]:
        """Build migration paths between schema versions."""
        migrations = {}

        # v1.0 -> v2.0
        migrations["v1.0->v2.0"] = SchemaMigration(
            from_version="v1.0",
            to_version="v2.0",
            migration_function=self._migrate_v1_to_v2,
            description="Add date fields, improve team resolution",
            safe_to_automigrate=True
        )

        # v2.0 -> v3.0
        migrations["v2.0->v3.0"] = SchemaMigration(
            from_version="v2.0",
            to_version="v3.0",
            migration_function=self._migrate_v2_to_v3,
            description="Add canonical fields, data source tracking",
            safe_to_automigrate=True
        )

        # v1.0 -> v3.0 (direct path, chains v1->v2->v3)
        migrations["v1.0->v3.0"] = SchemaMigration(
            from_version="v1.0",
            to_version="v3.0",
            migration_function=self._migrate_v1_to_v3,
            description="Full migration from legacy to canonical",
            safe_to_automigrate=True
        )

        return migrations

    def detect_schema_version(self, df: pd.DataFrame, data_type: str = "scores") -> str:
        """
        Detect the schema version of a DataFrame.

        Args:
            df: DataFrame to analyze
            data_type: Type of data

        Returns:
            Detected schema version string
        """
        available_fields = set(df.columns)

        # Check against each schema
        for version, schema in self._schemas.items():
            required_fields = set(schema.required_fields)
            if required_fields.issubset(available_fields):
                return version

        # Fallback to legacy if nothing matches
        return "v1.0"

    def get_schema_for_vintage(self, vintage: DataVintage) -> Optional[SchemaVersion]:
        """Get the schema version for a data vintage."""
        for schema in self._schemas.values():
            if schema.vintage == vintage:
                return schema
        return None

    def upgrade_schema(
        self,
        df: pd.DataFrame,
        target_version: Optional[str] = None,
        data_type: str = "scores"
    ) -> pd.DataFrame:
        """
        Upgrade DataFrame to target schema version.

        Args:
            df: DataFrame to upgrade
            target_version: Target schema version (default: canonical)
            data_type: Type of data

        Returns:
            Upgraded DataFrame
        """
        if target_version is None:
            target_version = self._canonical_version

        current_version = self.detect_schema_version(df, data_type)

        if current_version == target_version:
            return df  # Already at target version

        # Find migration path
        migration_key = f"{current_version}->{target_version}"
        if migration_key in self._migrations:
            migration = self._migrations[migration_key]
            print(f"Migrating {data_type} data from {current_version} to {target_version}: {migration.description}")

            try:
                migrated_df = migration.migration_function(df.copy())
                migrated_df["_schema_version"] = target_version
                migrated_df["_migrated_at"] = datetime.now().isoformat()
                return migrated_df
            except Exception as e:
                print(f"Warning: Migration failed: {e}")
                # Return original with version marker
                df["_schema_version"] = current_version
                df["_migration_failed"] = str(e)
                return df

        # No direct migration path
        print(f"Warning: No migration path from {current_version} to {target_version}")
        df["_schema_version"] = current_version
        df["_migration_missing"] = f"No path to {target_version}"
        return df

    def get_quality_standards(self, vintage: Union[str, DataVintage]) -> Dict[str, Any]:
        """
        Get quality standards for a data vintage.

        Args:
            vintage: Data vintage or schema version

        Returns:
            Quality standards dictionary
        """
        if isinstance(vintage, str):
            # Check if it's a vintage name
            vintage_map = {
                'legacy': DataVintage.LEGACY,
                'transitional': DataVintage.TRANSITIONAL,
                'modern': DataVintage.MODERN,
                'canonical': DataVintage.CANONICAL
            }
            if vintage in vintage_map:
                vintage = vintage_map[vintage]
            elif vintage in self._schemas:
                # It's a schema version
                return self._schemas[vintage].quality_standards
            else:
                # Try to infer vintage from version
                vintage = self._infer_vintage_from_version(vintage)

        if isinstance(vintage, DataVintage):
            schema = self.get_schema_for_vintage(vintage)
            if schema:
                return schema.quality_standards

        # Default standards
        return {
            "null_threshold": 0.05,
            "duplicate_threshold": 0.02,
            "team_resolution_threshold": 0.90
        }

    def _infer_vintage_from_version(self, version: str) -> DataVintage:
        """Infer data vintage from schema version."""
        version_num = float(version.lstrip('v'))

        if version_num < 2.0:
            return DataVintage.LEGACY
        elif version_num < 3.0:
            return DataVintage.TRANSITIONAL
        else:
            return DataVintage.MODERN

    def validate_against_schema(
        self,
        df: pd.DataFrame,
        schema_version: str,
        strict: bool = False
    ) -> List[str]:
        """
        Validate DataFrame against a specific schema version.

        Args:
            df: DataFrame to validate
            schema_version: Schema version to validate against
            strict: If True, require all required fields

        Returns:
            List of validation error messages
        """
        if schema_version not in self._schemas:
            return [f"Unknown schema version: {schema_version}"]

        schema = self._schemas[schema_version]
        available_fields = set(df.columns)
        errors = []

        # Check required fields
        missing_required = set(schema.required_fields) - available_fields
        if missing_required:
            if strict:
                errors.append(f"Missing required fields: {missing_required}")
            else:
                errors.append(f"Warning: Missing recommended fields: {missing_required}")

        # Check for unknown fields (optional - could be warning)
        all_allowed = set(schema.required_fields + schema.optional_fields)
        unknown_fields = available_fields - all_allowed
        if unknown_fields:
            errors.append(f"Unknown fields (may be okay): {unknown_fields}")

        return errors

    # Migration functions

    def _migrate_v1_to_v2(self, df: pd.DataFrame) -> pd.DataFrame:
        """Migrate from v1.0 to v2.0 schema."""
        # Add date field if missing (infer from filename or index)
        if "date" not in df.columns:
            # Try to infer dates from other fields or use placeholder
            df["date"] = pd.NaT  # Will be filled later

        # Add season field if missing
        if "season" not in df.columns:
            df["season"] = df.get("year", pd.Series([2020] * len(df)))

        return df

    def _migrate_v2_to_v3(self, df: pd.DataFrame) -> pd.DataFrame:
        """Migrate from v2.0 to v3.0 schema."""
        # Add data source tracking
        if "data_source" not in df.columns:
            df["data_source"] = "migrated"

        # Add canonicalization timestamp
        df["canonicalized_at"] = datetime.now().isoformat()

        # Ensure season field is integer
        if "season" in df.columns:
            df["season"] = pd.to_numeric(df["season"], errors='coerce').astype('Int64')

        return df

    def _migrate_v1_to_v3(self, df: pd.DataFrame) -> pd.DataFrame:
        """Migrate from v1.0 directly to v3.0 schema (chains v1->v2->v3)."""
        # Apply v1 -> v2 migration
        df = self._migrate_v1_to_v2(df)
        # Apply v2 -> v3 migration
        df = self._migrate_v2_to_v3(df)
        return df

    def create_custom_migration(
        self,
        from_version: str,
        to_version: str,
        migration_func: Callable[[pd.DataFrame], pd.DataFrame],
        description: str,
        safe: bool = False
    ):
        """Create a custom migration path."""
        migration = SchemaMigration(
            from_version=from_version,
            to_version=to_version,
            migration_function=migration_func,
            description=description,
            safe_to_automigrate=safe
        )

        key = f"{from_version}->{to_version}"
        self._migrations[key] = migration

    def save_schema_definition(self, schema: SchemaVersion):
        """Save a schema definition to file."""
        schema_file = self.config_dir / f"schema_{schema.version}.json"

        schema_data = {
            "version": schema.version,
            "vintage": schema.vintage.value,
            "description": schema.description,
            "required_fields": schema.required_fields,
            "optional_fields": schema.optional_fields,
            "transformations": schema.transformations,
            "quality_standards": schema.quality_standards,
            "created_date": schema.created_date.isoformat()
        }

        try:
            with open(schema_file, 'w') as f:
                json.dump(schema_data, f, indent=2)
            print(f"Saved schema {schema.version} to {schema_file}")
        except Exception as e:
            print(f"Error saving schema: {e}")

    def get_available_versions(self) -> List[str]:
        """Get list of available schema versions."""
        return list(self._schemas.keys())

    def get_migration_paths(self) -> List[str]:
        """Get list of available migration paths."""
        return list(self._migrations.keys())


# Convenience functions
def upgrade_to_canonical_schema(df: pd.DataFrame, data_type: str = "scores") -> pd.DataFrame:
    """Upgrade DataFrame to canonical schema."""
    manager = SchemaEvolutionManager()
    return manager.upgrade_schema(df, data_type=data_type)


def get_quality_standards_for_vintage(vintage: Union[str, DataVintage]) -> Dict[str, Any]:
    """Get quality standards for a vintage."""
    manager = SchemaEvolutionManager()
    return manager.get_quality_standards(vintage)


def detect_data_vintage(df: pd.DataFrame) -> DataVintage:
    """Detect the vintage of data in a DataFrame."""
    manager = SchemaEvolutionManager()
    version = manager.detect_schema_version(df)
    return manager._infer_vintage_from_version(version)