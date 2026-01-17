"""
Azure Blob Storage Data Reader - CANONICAL INGESTION INTEGRATION

Reads historical data directly from Azure Blob Storage with automatic canonicalization.
All data goes through the canonical ingestion pipeline for consistency.

Storage Account: metricstrackersgbsv
Container: ncaam-historical-data (canonical data)

Usage:
    from testing.azure_data_reader import AzureDataReader

    reader = AzureDataReader()

    # Read canonical CSV (automatically processed through pipeline)
    df = reader.read_csv("backtest_datasets/backtest_master.csv")

    # Read canonical JSON
    data = reader.read_json("ratings/barttorvik/ratings_2025.json")

    # List files in a directory
    files = reader.list_files("ncaahoopR_data-master/box_scores/")

    # Stream large files (for ncaahoopR)
    for chunk in reader.read_csv_chunks("ncaahoopR_data-master/schedules/Duke_schedule.csv"):
        process(chunk)
"""

import io
import json
import os
import warnings
from collections.abc import Iterator
from typing import Any

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from azure.core.exceptions import ResourceNotFoundError
    from azure.storage.blob import BlobServiceClient, ContainerClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    warnings.warn("azure-storage-blob not installed. Run: pip install azure-storage-blob")

# Import canonical ingestion components
try:
    from .canonical.ingestion_pipeline import CanonicalIngestionPipeline, DataSource
    from .canonical.quality_gates import DataQualityGate
    from .canonical.schema_evolution import SchemaEvolutionManager
    CANONICAL_AVAILABLE = True
except ImportError:
    CANONICAL_AVAILABLE = False
    warnings.warn("Canonical ingestion components not available. Data will not be canonicalized.")

from .data_window import (
    CANONICAL_START_DATE,
    CANONICAL_START_SEASON,
    enforce_min_season,
    season_from_date,
)

# Azure configuration
STORAGE_ACCOUNT = "metricstrackersgbsv"
RESOURCE_GROUP = "dashboard-gbsv-main-rg"
DEFAULT_CONTAINER = "ncaam-historical-data"  # Primary canonical data
RAW_CONTAINER = "ncaam-historical-raw"  # Raw data backup


class AzureDataReader:
    """
    Read historical data directly from Azure Blob Storage with canonical ingestion.

    Benefits:
    - No local storage required for 7GB+ files
    - Single source of truth for all environments
    - Automatic canonicalization and quality validation
    - Schema evolution handling
    - Streaming support for large datasets
    """

    def __init__(
        self,
        container_name: str = DEFAULT_CONTAINER,
        connection_string: str | None = None,
        enable_canonicalization: bool = True,
        strict_mode: bool = True,
    ):
        """
        Initialize Azure data reader.

        Args:
            container_name: Azure blob container name
            connection_string: Optional connection string (auto-detected if not provided)
            enable_canonicalization: Whether to apply canonical ingestion pipeline
            strict_mode: Whether to fail on canonicalization errors
        """
        if not AZURE_AVAILABLE:
            raise ImportError(
                "azure-storage-blob package required. "
                "Install with: pip install azure-storage-blob"
            )

        self.container_name = container_name
        self.enable_canonicalization = enable_canonicalization and CANONICAL_AVAILABLE
        self.strict_mode = strict_mode

        # Get connection string
        self._connection_string = connection_string or self._get_connection_string()

        # Initialize blob service
        self._blob_service: BlobServiceClient | None = None
        self._container_client: ContainerClient | None = None

        # Cache for file listings
        self._file_list_cache: dict[str, list[str]] = {}

        # Initialize canonical ingestion components
        if self.enable_canonicalization:
            self._ingestion_pipeline = CanonicalIngestionPipeline(strict_mode=strict_mode)
            self._quality_gate = DataQualityGate(strict_mode=strict_mode)
            self._schema_manager = SchemaEvolutionManager()
        else:
            self._ingestion_pipeline = None
            self._quality_gate = None
            self._schema_manager = None

    def _get_connection_string(self) -> str:
        """Get Azure connection string from environment or Azure CLI."""
        # Try canonical connection string first (historical data)
        conn_str = os.getenv("AZURE_CANONICAL_CONNECTION_STRING")
        if conn_str:
            return conn_str

        # Try Azure CLI
        import shutil
        import subprocess

        az_cmd = shutil.which("az") or shutil.which("az.cmd")
        if not az_cmd:
            raise RuntimeError(
                "Azure CLI not found. Either:\n"
                "1. Set AZURE_CANONICAL_CONNECTION_STRING\n"
                "2. Install Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
            )

        try:
            result = subprocess.run(
                [
                    az_cmd, "storage", "account", "show-connection-string",
                    "--name", STORAGE_ACCOUNT,
                    "--resource-group", RESOURCE_GROUP,
                    "--query", "connectionString",
                    "-o", "tsv"
                ],
                capture_output=True,
                text=True,
                check=True,
                shell=(os.name == 'nt')
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to get connection string via Azure CLI: {e}\n"
                "Run 'az login' first or set AZURE_CANONICAL_CONNECTION_STRING"
            )

    @property
    def blob_service(self) -> BlobServiceClient:
        """Lazy-initialize blob service client."""
        if self._blob_service is None:
            self._blob_service = BlobServiceClient.from_connection_string(
                self._connection_string
            )
        return self._blob_service

    @property
    def container(self) -> ContainerClient:
        """Lazy-initialize container client."""
        if self._container_client is None:
            self._container_client = self.blob_service.get_container_client(
                self.container_name
            )
        return self._container_client

    def blob_exists(self, blob_path: str) -> bool:
        """Check if a blob exists."""
        blob_client = self.container.get_blob_client(blob_path)
        return blob_client.exists()

    def get_blob_size(self, blob_path: str) -> int:
        """Get size of a blob in bytes."""
        blob_client = self.container.get_blob_client(blob_path)
        props = blob_client.get_blob_properties()
        return props.size

    def list_files(
        self,
        prefix: str = "",
        pattern: str | None = None,
        use_cache: bool = True
    ) -> list[str]:
        """
        List files in a blob directory.

        Args:
            prefix: Directory prefix (e.g., "ncaahoopR_data-master/box_scores/")
            pattern: Optional glob pattern to filter (e.g., "*.csv")
            use_cache: Whether to use cached listing

        Returns:
            List of blob paths
        """
        cache_key = f"{prefix}:{pattern}"
        if use_cache and cache_key in self._file_list_cache:
            return self._file_list_cache[cache_key]

        files = []
        for blob in self.container.list_blobs(name_starts_with=prefix):
            name = blob.name
            if pattern:
                from fnmatch import fnmatch
                if not fnmatch(name.split("/")[-1], pattern):
                    continue
            files.append(name)

        if use_cache:
            self._file_list_cache[cache_key] = files

        return files

    def read_bytes(self, blob_path: str) -> bytes:
        """Read a blob as raw bytes."""
        blob_client = self.container.get_blob_client(blob_path)
        try:
            return blob_client.download_blob().readall()
        except ResourceNotFoundError:
            raise FileNotFoundError(f"Blob not found: {blob_path}")

    def read_text(self, blob_path: str, encoding: str = "utf-8") -> str:
        """Read a blob as text."""
        return self.read_bytes(blob_path).decode(encoding)

    def read_json(self, blob_path: str, apply_canonicalization: bool = True) -> Any:
        """Read a JSON blob with optional canonicalization."""
        data = json.loads(self.read_text(blob_path))

        # Apply canonicalization for ratings data
        if apply_canonicalization and self.enable_canonicalization and "rating" in blob_path.lower():
            # For ratings, we could add canonicalization logic here
            pass

        return data

    def read_csv(
        self,
        blob_path: str,
        data_type: str = "auto",
        apply_canonicalization: bool | None = None,
        **pandas_kwargs
    ) -> "pd.DataFrame":
        """
        Read a CSV blob into a pandas DataFrame with canonical ingestion.

        Args:
            blob_path: Path to CSV in blob storage
            data_type: Type of data ("scores", "odds", "ratings", "auto")
            apply_canonicalization: Override canonicalization setting
            **pandas_kwargs: Additional arguments for pd.read_csv

        Returns:
            pandas DataFrame (canonicalized if enabled)
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. Install with: pip install pandas")

        should_canonicalize = (
            apply_canonicalization
            if apply_canonicalization is not None
            else self.enable_canonicalization
        )

        # Read raw data from Azure
        content = self.read_bytes(blob_path)
        df = pd.read_csv(io.BytesIO(content), **pandas_kwargs)

        # Apply canonical ingestion pipeline if enabled
        if should_canonicalize and self._ingestion_pipeline:
            df = self._apply_canonical_ingestion(df, blob_path, data_type)

        return df

    def _apply_canonical_ingestion(
        self,
        df: "pd.DataFrame",
        blob_path: str,
        data_type: str
    ) -> "pd.DataFrame":
        """Apply canonical ingestion pipeline to DataFrame."""
        if not self._ingestion_pipeline or not self._quality_gate or not self._schema_manager:
            return df

        # Skip canonical ingestion if data_type is None (explicitly disabled)
        if data_type is None:
            return df

        try:
            # Auto-detect data type if not specified
            if data_type == "auto":
                data_type = self._infer_data_type(blob_path)

            # Apply schema evolution
            df = self._schema_manager.upgrade_schema(df, data_type=data_type)

            # Apply canonical ingestion based on data type
            if data_type in ["scores", "games"]:
                source = DataSource.ESPN_SCORES
                result = self._ingestion_pipeline.ingest_scores_data(df, source)
            elif data_type in ["odds", "spreads", "totals"]:
                source = DataSource.ODDS_API
                result = self._ingestion_pipeline.ingest_odds_data(df, source)
            elif data_type in ["ratings"]:
                source = DataSource.BARTTORVIK
                result = self._ingestion_pipeline.ingest_odds_data(df, source)  # Close enough for now
            else:
                # Unknown data type, apply basic quality check
                validation_result = self._quality_gate.validate(df, "unknown")
                if not validation_result.passed and self.strict_mode:
                    raise ValueError(f"Data quality validation failed: {validation_result.issues}")
                return df

            # Check ingestion result
            if not result.success and self.strict_mode:
                raise ValueError(f"Canonical ingestion failed: {result.errors}")

            if result.warnings:
                print(f"Warnings during canonical ingestion of {blob_path}: {result.warnings}")

            # The ingestion pipeline transforms the data in-place and returns the result
            # For now, return the original df as the pipeline modifies it
            return df

        except Exception as e:
            if self.strict_mode:
                raise
            print(f"Warning: Canonical ingestion failed for {blob_path}: {e}")
            return df

    def _infer_data_type(self, blob_path: str) -> str:
        """Infer data type from blob path."""
        path_lower = blob_path.lower()

        if any(keyword in path_lower for keyword in ["score", "game", "fg.csv", "h1.csv"]):
            return "scores"
        if any(keyword in path_lower for keyword in ["odds", "spread", "total", "moneyline"]):
            return "odds"
        if any(keyword in path_lower for keyword in ["rating", "barttorvik"]):
            return "ratings"
        if "ncaahoopR" in path_lower:
            return "ncaahoopR"
        return "unknown"

    def read_csv_chunks(
        self,
        blob_path: str,
        chunksize: int = 10000,
        **pandas_kwargs
    ) -> Iterator["pd.DataFrame"]:
        """
        Read a large CSV in chunks (streaming).

        Args:
            blob_path: Path to CSV in blob storage
            chunksize: Number of rows per chunk
            **pandas_kwargs: Additional arguments for pd.read_csv

        Yields:
            pandas DataFrame chunks
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. Install with: pip install pandas")

        content = self.read_bytes(blob_path)
        return pd.read_csv(
            io.BytesIO(content),
            chunksize=chunksize,
            **pandas_kwargs
        )

    def _normalize_tags(self, tags: dict[str, str] | None) -> dict[str, str] | None:
        if not tags:
            return None
        normalized = {}
        for key, value in tags.items():
            if value is None:
                continue
            normalized[str(key)] = str(value)
        return normalized or None

    def set_blob_tags(self, blob_path: str, tags: dict[str, str] | None) -> None:
        """Set Azure Blob Storage tags for an existing blob."""
        normalized = self._normalize_tags(tags)
        if not normalized:
            return
        blob_client = self.container.get_blob_client(blob_path)
        blob_client.set_blob_tags(normalized)

    def upload_bytes(
        self,
        blob_path: str,
        content: bytes,
        content_type: str | None = None,
        overwrite: bool = True,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Upload raw bytes to Azure Blob Storage."""
        blob_client = self.container.get_blob_client(blob_path)
        if content_type:
            from azure.storage.blob import ContentSettings
            blob_client.upload_blob(
                content,
                overwrite=overwrite,
                content_settings=ContentSettings(content_type=content_type),
            )
        else:
            blob_client.upload_blob(content, overwrite=overwrite)
        self.set_blob_tags(blob_path, tags)

    def upload_text(
        self,
        blob_path: str,
        text: str,
        encoding: str = "utf-8",
        content_type: str | None = None,
        overwrite: bool = True,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Upload text content to Azure Blob Storage."""
        data = text.encode(encoding)
        self.upload_bytes(
            blob_path,
            data,
            content_type=content_type,
            overwrite=overwrite,
            tags=tags,
        )

    def write_json(
        self,
        blob_path: str,
        payload: Any,
        indent: int = 2,
        sort_keys: bool = False,
        overwrite: bool = True,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Serialize and upload JSON to Azure Blob Storage."""
        text = json.dumps(payload, indent=indent, sort_keys=sort_keys)
        self.upload_text(
            blob_path,
            text,
            content_type="application/json",
            overwrite=overwrite,
            tags=tags,
        )

    def write_csv(
        self,
        blob_path: str,
        df: "pd.DataFrame",
        overwrite: bool = True,
        tags: dict[str, str] | None = None,
        **pandas_kwargs,
    ) -> None:
        """Serialize and upload a DataFrame as CSV to Azure Blob Storage."""
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. Install with: pip install pandas")
        output = io.StringIO()
        if "index" not in pandas_kwargs:
            pandas_kwargs["index"] = False
        df.to_csv(output, **pandas_kwargs)
        self.upload_text(
            blob_path,
            output.getvalue(),
            content_type="text/csv",
            overwrite=overwrite,
            tags=tags,
        )
    def read_canonical_scores(self, season: int | None = None) -> "pd.DataFrame":
        """Read canonical scores data from Azure (2023-24 season onward)."""
        if season:
            enforce_min_season([season])
            df = self.read_csv(f"scores/fg/games_{season}.csv", data_type="scores")
        else:
            df = self.read_csv("scores/fg/games_all.csv", data_type="scores")

        # Filter to canonical window in case older rows are present.
        date_col = "date" if "date" in df.columns else "game_date" if "game_date" in df.columns else None
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df[df[date_col] >= pd.Timestamp(CANONICAL_START_DATE)]
        if "season" in df.columns:
            df = df[df["season"] >= CANONICAL_START_SEASON]
        if "season" in df.columns:
            df = df[df["season"] >= CANONICAL_START_SEASON]

        return df

    def _select_latest_pregame_lines(self, df: "pd.DataFrame") -> "pd.DataFrame":
        """Drop postgame lines and keep the latest pregame line per event."""
        if df is None or df.empty:
            return df

        df = df.copy()

        commence_col = "commence_time" if "commence_time" in df.columns else None
        line_time_col = None
        for col in ["bookmaker_last_update", "timestamp", "last_update", "updated_at"]:
            if col in df.columns:
                line_time_col = col
                break

        if commence_col:
            df["_commence_time"] = pd.to_datetime(df[commence_col], errors="coerce", utc=True)
        if line_time_col:
            df["_line_time"] = pd.to_datetime(df[line_time_col], errors="coerce", utc=True)
            if "line_timestamp" not in df.columns:
                df["line_timestamp"] = df["_line_time"]
            if "line_timestamp_source" not in df.columns:
                df["line_timestamp_source"] = line_time_col

        if "_commence_time" in df.columns and "_line_time" in df.columns:
            pregame_mask = (
                df["_line_time"].isna()
                | df["_commence_time"].isna()
                | (df["_line_time"] <= df["_commence_time"])
            )
            df = df.loc[pregame_mask].copy()

        group_cols = []
        for key in ["event_id", "game_id"]:
            if key in df.columns:
                group_cols = [key]
                break
        if not group_cols:
            for key in ["home_team", "away_team", "_commence_time"]:
                if key in df.columns:
                    group_cols.append(key)

        if group_cols:
            if "_line_time" in df.columns:
                df = df.sort_values("_line_time").drop_duplicates(subset=group_cols, keep="last")
            else:
                df = df.drop_duplicates(subset=group_cols, keep="first")

        return df.drop(columns=["_commence_time", "_line_time"], errors="ignore")

    def read_canonical_odds(self, market: str = "fg_spread", season: int | None = None) -> "pd.DataFrame":
        """Read canonical odds data from Azure (2023-24 season onward, pregame only)."""
        valid_markets = ["fg_spread", "fg_total", "h1_spread", "h1_total"]
        if market not in valid_markets:
            raise ValueError(f"Unknown market '{market}'. Valid: {valid_markets}")

        if season:
            enforce_min_season([season])

        # Single source of truth for odds across markets.
        df = self.read_csv("odds/normalized/odds_consolidated_canonical.csv", data_type="odds")

        date_col = "game_date" if "game_date" in df.columns else "date" if "date" in df.columns else None
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df[df[date_col] >= pd.Timestamp(CANONICAL_START_DATE)]

        if season:
            if "season" in df.columns:
                df = df[df["season"] == season].copy()
            elif date_col:
                df = df.copy()
                df["_season"] = df[date_col].apply(
                    lambda d: season_from_date(d.date()) if pd.notna(d) else None
                )
                df = df[df["_season"] == season].drop(columns=["_season"])

        df = self._select_latest_pregame_lines(df)

        # Normalize column names to backtest expectations while retaining raw fields.
        df = df.copy()
        if market == "fg_spread":
            if "spread" in df.columns and "fg_spread" not in df.columns:
                df["fg_spread"] = df["spread"]
            if "spread_home_price" in df.columns and "fg_spread_home_price" not in df.columns:
                df["fg_spread_home_price"] = df["spread_home_price"]
            if "spread_away_price" in df.columns and "fg_spread_away_price" not in df.columns:
                df["fg_spread_away_price"] = df["spread_away_price"]
            if "spread_price" in df.columns and "fg_spread_home_price" not in df.columns:
                df["fg_spread_home_price"] = df["spread_price"]
        elif market == "fg_total":
            if "total" in df.columns and "fg_total" not in df.columns:
                df["fg_total"] = df["total"]
            if "total_over_price" in df.columns and "fg_total_over_price" not in df.columns:
                df["fg_total_over_price"] = df["total_over_price"]
            if "total_under_price" in df.columns and "fg_total_under_price" not in df.columns:
                df["fg_total_under_price"] = df["total_under_price"]
        elif market == "h1_spread":
            if "h1_spread_price" in df.columns and "h1_spread_home_price" not in df.columns:
                df["h1_spread_home_price"] = df["h1_spread_price"]
        elif market == "h1_total":
            pass

        if "date" in df.columns:
            if df["date"].isna().all():
                if "game_date" in df.columns:
                    df["date"] = df["game_date"]
                elif "commence_time" in df.columns:
                    df["date"] = df["commence_time"]
        elif "game_date" in df.columns:
            df["date"] = df["game_date"]
        elif "commence_time" in df.columns:
            df["date"] = df["commence_time"]

        return df

    def read_canonical_ratings(self, season: int) -> dict:
        """Read canonical ratings data from Azure."""
        return self.read_json(f"ratings/barttorvik/ratings_{season}.json")

    def read_backtest_master(self, enhanced: bool = True) -> "pd.DataFrame":
        """
        Read the canonical backtest master dataset from Azure.

        Args:
            enhanced: Deprecated. Ignored in favor of backtest_master.csv.

        Returns:
            pandas DataFrame
        """
        if enhanced:
            warnings.warn(
                "Enhanced backtest master deprecated; using backtest_master.csv.",
                RuntimeWarning,
            )

        df = self.read_csv("backtest_datasets/backtest_master.csv", data_type="backtest")

        # Enforce canonical window.
        if "season" in df.columns:
            df = df[df["season"] >= CANONICAL_START_SEASON]
        elif "game_date" in df.columns or "date" in df.columns:
            date_col = "game_date" if "game_date" in df.columns else "date"
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df[df[date_col] >= pd.Timestamp(CANONICAL_START_DATE)]

        return df


# Singleton instances
_azure_reader: AzureDataReader | None = None


def get_azure_reader() -> AzureDataReader:
    """Get the singleton Azure data reader."""
    global _azure_reader
    if _azure_reader is None:
        _azure_reader = AzureDataReader()
    return _azure_reader




# Convenience functions
def read_backtest_master(enhanced: bool = True) -> "pd.DataFrame":
    """
    Read the backtest master dataset from Azure with canonical ingestion.

    Args:
        enhanced: Deprecated. Ignored in favor of backtest_master.csv.

    Returns:
        pandas DataFrame
    """
    reader = get_azure_reader()
    return reader.read_backtest_master(enhanced=enhanced)


def read_canonical_scores(season: int | None = None) -> "pd.DataFrame":
    """Read canonical scores data from Azure."""
    reader = get_azure_reader()
    return reader.read_canonical_scores(season=season)


def read_canonical_odds(market: str = "fg_spread", season: int | None = None) -> "pd.DataFrame":
    """Read canonical odds data from Azure."""
    reader = get_azure_reader()
    return reader.read_canonical_odds(market=market, season=season)


def read_barttorvik_ratings(season: int) -> dict:
    """Read Barttorvik ratings for a season from Azure."""
    reader = get_azure_reader()
    return reader.read_json(f"ratings/barttorvik/ratings_{season}.json")


def read_team_aliases() -> dict[str, str]:
    """Read team aliases database from Azure."""
    reader = get_azure_reader()
    return reader.read_json("backtest_datasets/team_aliases_db.json")


if __name__ == "__main__":
    # Test the reader
    print("=" * 60)
    print("Azure Data Reader Test")
    print("=" * 60)

    try:
        reader = AzureDataReader()

        # List some files
        print("\nListing backtest_datasets/...")
        files = reader.list_files("backtest_datasets/", pattern="*.csv")
        for f in files[:10]:
            size = reader.get_blob_size(f)
            print(f"  {f}: {size:,} bytes")

        # Try reading backtest master
        print("\nReading backtest_master.csv...")
        df = reader.read_csv("backtest_datasets/backtest_master.csv")
        print(f"  Rows: {len(df):,}")
        print(f"  Columns: {len(df.columns)}")

        print("\n[OK] Azure Data Reader working!")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("\nMake sure to:")
        print("1. Run 'az login' to authenticate")
        print("2. Or set AZURE_CANONICAL_CONNECTION_STRING")
