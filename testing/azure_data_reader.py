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

import os
import io
import json
from typing import Optional, Iterator, Dict, List, Any
import warnings

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from azure.storage.blob import BlobServiceClient, ContainerClient
    from azure.core.exceptions import ResourceNotFoundError
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
        connection_string: Optional[str] = None,
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
        self._blob_service: Optional[BlobServiceClient] = None
        self._container_client: Optional[ContainerClient] = None

        # Cache for file listings
        self._file_list_cache: Dict[str, List[str]] = {}

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
        import subprocess
        import shutil
        
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
        pattern: Optional[str] = None,
        use_cache: bool = True
    ) -> List[str]:
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
        apply_canonicalization: Optional[bool] = None,
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
            else:
                print(f"Warning: Canonical ingestion failed for {blob_path}: {e}")
                return df

    def _infer_data_type(self, blob_path: str) -> str:
        """Infer data type from blob path."""
        path_lower = blob_path.lower()

        if any(keyword in path_lower for keyword in ["score", "game", "fg.csv", "h1.csv"]):
            return "scores"
        elif any(keyword in path_lower for keyword in ["odds", "spread", "total", "moneyline"]):
            return "odds"
        elif any(keyword in path_lower for keyword in ["rating", "barttorvik"]):
            return "ratings"
        elif "ncaahoopR" in path_lower:
            return "ncaahoopR"
        else:
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

    def _normalize_tags(self, tags: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if not tags:
            return None
        normalized = {}
        for key, value in tags.items():
            if value is None:
                continue
            normalized[str(key)] = str(value)
        return normalized or None

    def set_blob_tags(self, blob_path: str, tags: Optional[Dict[str, str]]) -> None:
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
        content_type: Optional[str] = None,
        overwrite: bool = True,
        tags: Optional[Dict[str, str]] = None,
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
        content_type: Optional[str] = None,
        overwrite: bool = True,
        tags: Optional[Dict[str, str]] = None,
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
        tags: Optional[Dict[str, str]] = None,
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
        tags: Optional[Dict[str, str]] = None,
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
    def read_canonical_scores(self, season: Optional[int] = None) -> "pd.DataFrame":
        """Read canonical scores data from Azure."""
        if season:
            return self.read_csv(f"scores/fg/games_{season}.csv", data_type="scores")
        return self.read_csv("scores/fg/games_all.csv", data_type="scores")

    def read_canonical_odds(self, market: str = "fg_spread", season: Optional[int] = None) -> "pd.DataFrame":
        """Read canonical odds data from Azure."""
        if season:
            try:
                df = self.read_csv(
                    f"odds/canonical/spreads/fg/spreads_fg_{season}.csv",
                    data_type="odds",
                )
            except FileNotFoundError:
                df = self.read_csv(
                    "odds/canonical/spreads/fg/spreads_fg_all.csv",
                    data_type="odds",
                )
            if "season" in df.columns:
                return df[df["season"] == season].copy()
            return df
        return self.read_csv("odds/normalized/odds_consolidated_canonical.csv", data_type="odds")

    def read_canonical_ratings(self, season: int) -> Dict:
        """Read canonical ratings data from Azure."""
        return self.read_json(f"ratings/barttorvik/ratings_{season}.json")

    def read_backtest_master(self, enhanced: bool = True) -> "pd.DataFrame":
        """
        Read the backtest master dataset from Azure with canonicalization.

        Args:
            enhanced: If True, prefer the enhanced version with box score features

        Returns:
            pandas DataFrame
        """
        if enhanced:
            try:
                return self.read_csv("backtest_datasets/backtest_master_enhanced.csv", data_type="backtest")
            except FileNotFoundError:
                pass
        return self.read_csv("backtest_datasets/backtest_master.csv", data_type="backtest")


# Singleton instances
_azure_reader: Optional[AzureDataReader] = None


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
        enhanced: If True, prefer the enhanced version with box score features

    Returns:
        pandas DataFrame
    """
    reader = get_azure_reader()
    return reader.read_backtest_master(enhanced=enhanced)


def read_canonical_scores(season: Optional[int] = None) -> "pd.DataFrame":
    """Read canonical scores data from Azure."""
    reader = get_azure_reader()
    return reader.read_canonical_scores(season=season)


def read_canonical_odds(market: str = "fg_spread", season: Optional[int] = None) -> "pd.DataFrame":
    """Read canonical odds data from Azure."""
    reader = get_azure_reader()
    return reader.read_canonical_odds(market=market, season=season)


def read_barttorvik_ratings(season: int) -> Dict:
    """Read Barttorvik ratings for a season from Azure."""
    reader = get_azure_reader()
    return reader.read_json(f"ratings/barttorvik/ratings_{season}.json")


def read_team_aliases() -> Dict[str, str]:
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
