"""
Azure Blob Storage Data Reader - SINGLE SOURCE OF TRUTH

Reads historical data directly from Azure Blob Storage WITHOUT downloading.
Supports streaming large files (like ncaahoopR 7GB data) efficiently.

Storage Account: metricstrackersgbsv
Container: ncaam-historical-data (canonical data)

Usage:
    from testing.azure_data_reader import AzureDataReader
    
    reader = AzureDataReader()
    
    # Read CSV directly from Azure
    df = reader.read_csv("backtest_datasets/backtest_master.csv")
    
    # Read JSON
    data = reader.read_json("ratings/barttorvik/ratings_2025.json")
    
    # List files in a directory
    files = reader.list_files("ncaahoopR_data-master/box_scores/")
    
    # Stream large files (for ncaahoopR)
    for chunk in reader.read_csv_chunks("ncaahoopR_data-master/schedules/Duke_schedule.csv"):
        process(chunk)
"""

import os
import sys
import io
import json
from pathlib import Path
from typing import Optional, Iterator, Dict, List, Any
from functools import lru_cache
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


# Azure configuration
STORAGE_ACCOUNT = "metricstrackersgbsv"
RESOURCE_GROUP = "dashboard-gbsv-main-rg"
DEFAULT_CONTAINER = "ncaam-historical-data"  # Primary canonical data
RAW_CONTAINER = "ncaam-historical-raw"  # Raw data backup


class AzureDataReader:
    """
    Read historical data directly from Azure Blob Storage.
    
    Benefits:
    - No local storage required for 7GB+ files
    - Single source of truth for all environments
    - Streaming support for large datasets
    - Automatic caching for frequently accessed files
    """
    
    def __init__(
        self,
        container_name: str = DEFAULT_CONTAINER,
        connection_string: Optional[str] = None,
        use_cache: bool = True,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize Azure data reader.
        
        Args:
            container_name: Azure blob container name
            connection_string: Optional connection string (auto-detected if not provided)
            use_cache: Whether to cache small files locally
            cache_dir: Directory for local cache (default: .azure_cache/)
        """
        if not AZURE_AVAILABLE:
            raise ImportError(
                "azure-storage-blob package required. "
                "Install with: pip install azure-storage-blob"
            )
        
        self.container_name = container_name
        self.use_cache = use_cache
        self.cache_dir = cache_dir or Path(__file__).parent.parent / ".azure_cache"
        
        # Get connection string
        self._connection_string = connection_string or self._get_connection_string()
        
        # Initialize blob service
        self._blob_service: Optional[BlobServiceClient] = None
        self._container_client: Optional[ContainerClient] = None
        
        # Cache for file listings
        self._file_list_cache: Dict[str, List[str]] = {}
    
    def _get_connection_string(self) -> str:
        """Get Azure connection string from environment or Azure CLI."""
        # Try environment variable first
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if conn_str:
            return conn_str
        
        # Try Azure CLI
        import subprocess
        import shutil
        
        az_cmd = shutil.which("az") or shutil.which("az.cmd")
        if not az_cmd:
            raise RuntimeError(
                "Azure CLI not found. Either:\n"
                "1. Set AZURE_STORAGE_CONNECTION_STRING environment variable\n"
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
                "Run 'az login' first or set AZURE_STORAGE_CONNECTION_STRING"
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
    
    def read_json(self, blob_path: str) -> Any:
        """Read a JSON blob."""
        return json.loads(self.read_text(blob_path))
    
    def read_csv(
        self,
        blob_path: str,
        **pandas_kwargs
    ) -> "pd.DataFrame":
        """
        Read a CSV blob into a pandas DataFrame.
        
        Args:
            blob_path: Path to CSV in blob storage
            **pandas_kwargs: Additional arguments for pd.read_csv
        
        Returns:
            pandas DataFrame
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas required. Install with: pip install pandas")
        
        # Check local cache first
        if self.use_cache:
            cache_path = self._get_cache_path(blob_path)
            if cache_path.exists():
                return pd.read_csv(cache_path, **pandas_kwargs)
        
        # Read from Azure
        content = self.read_bytes(blob_path)
        df = pd.read_csv(io.BytesIO(content), **pandas_kwargs)
        
        # Cache small files locally
        if self.use_cache and len(content) < 50_000_000:  # < 50MB
            self._cache_file(blob_path, content)
        
        return df
    
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
    
    def _get_cache_path(self, blob_path: str) -> Path:
        """Get local cache path for a blob."""
        return self.cache_dir / blob_path.replace("/", os.sep)
    
    def _cache_file(self, blob_path: str, content: bytes):
        """Cache a file locally."""
        cache_path = self._get_cache_path(blob_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(content)
    
    def clear_cache(self):
        """Clear the local cache."""
        if self.cache_dir.exists():
            import shutil
            shutil.rmtree(self.cache_dir)
            print(f"Cleared cache: {self.cache_dir}")


class HybridDataReader:
    """
    Hybrid reader that tries local first, then falls back to Azure.
    
    This allows gradual migration to Azure while maintaining local compatibility.
    """
    
    def __init__(
        self,
        local_root: Optional[Path] = None,
        azure_container: str = DEFAULT_CONTAINER,
        prefer_azure: bool = False
    ):
        """
        Initialize hybrid reader.
        
        Args:
            local_root: Local data directory (default: ncaam_historical_data_local/)
            azure_container: Azure container name
            prefer_azure: If True, try Azure first even if local exists
        """
        self.local_root = local_root or (
            Path(__file__).parent.parent / "ncaam_historical_data_local"
        )
        self.prefer_azure = prefer_azure
        self._azure_reader: Optional[AzureDataReader] = None
    
    @property
    def azure(self) -> AzureDataReader:
        """Lazy-initialize Azure reader."""
        if self._azure_reader is None:
            self._azure_reader = AzureDataReader()
        return self._azure_reader
    
    def read_csv(self, path: str, **kwargs) -> "pd.DataFrame":
        """
        Read CSV from local or Azure.
        
        Args:
            path: Relative path within data directory
            **kwargs: Additional pandas arguments
        
        Returns:
            pandas DataFrame
        """
        local_path = self.local_root / path
        
        if self.prefer_azure:
            # Try Azure first
            try:
                return self.azure.read_csv(path, **kwargs)
            except Exception:
                if local_path.exists():
                    return pd.read_csv(local_path, **kwargs)
                raise
        else:
            # Try local first
            if local_path.exists():
                return pd.read_csv(local_path, **kwargs)
            return self.azure.read_csv(path, **kwargs)
    
    def read_json(self, path: str) -> Any:
        """Read JSON from local or Azure."""
        local_path = self.local_root / path
        
        if self.prefer_azure:
            try:
                return self.azure.read_json(path)
            except Exception:
                if local_path.exists():
                    return json.loads(local_path.read_text())
                raise
        else:
            if local_path.exists():
                return json.loads(local_path.read_text())
            return self.azure.read_json(path)


# Singleton instances
_azure_reader: Optional[AzureDataReader] = None
_hybrid_reader: Optional[HybridDataReader] = None


def get_azure_reader() -> AzureDataReader:
    """Get the singleton Azure data reader."""
    global _azure_reader
    if _azure_reader is None:
        _azure_reader = AzureDataReader()
    return _azure_reader


def get_hybrid_reader(prefer_azure: bool = False) -> HybridDataReader:
    """Get the singleton hybrid data reader."""
    global _hybrid_reader
    if _hybrid_reader is None or _hybrid_reader.prefer_azure != prefer_azure:
        _hybrid_reader = HybridDataReader(prefer_azure=prefer_azure)
    return _hybrid_reader


# Convenience functions
def read_backtest_master(enhanced: bool = True) -> "pd.DataFrame":
    """
    Read the backtest master dataset from Azure.
    
    Args:
        enhanced: If True, prefer the enhanced version with box score features
    
    Returns:
        pandas DataFrame
    """
    reader = get_hybrid_reader(prefer_azure=True)
    
    if enhanced:
        try:
            return reader.read_csv("backtest_datasets/backtest_master_enhanced.csv")
        except FileNotFoundError:
            pass
    
    return reader.read_csv("backtest_datasets/backtest_master.csv")


def read_barttorvik_ratings(season: int) -> Dict:
    """Read Barttorvik ratings for a season from Azure."""
    reader = get_hybrid_reader(prefer_azure=True)
    return reader.read_json(f"ratings/barttorvik/ratings_{season}.json")


def read_team_aliases() -> Dict[str, str]:
    """Read team aliases database from Azure."""
    reader = get_hybrid_reader(prefer_azure=True)
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
        print("2. Or set AZURE_STORAGE_CONNECTION_STRING environment variable")
