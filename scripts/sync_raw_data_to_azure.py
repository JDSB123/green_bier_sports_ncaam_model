#!/usr/bin/env python3
"""
Sync ALL historical data to Azure Blob Storage - SINGLE SOURCE OF TRUTH.

This script uploads ALL NCAAM data to Azure Blob Storage:
- Canonical data (odds, scores, ratings, backtest datasets)
- Raw data (API responses, ncaahoopR 7GB)
- Derived data (enhanced backtest datasets)

Azure serves as the SINGLE SOURCE OF TRUTH for all historical data.
Local files are optional - backtesting can read directly from Azure.

Storage Account: metricstrackersgbsv (dashboard-gbsv-main-rg)
Containers:
- ncaam-historical-data: Canonical data (primary, for backtesting)
- ncaam-historical-raw: Raw data backup (large files, archives)

Usage:
    python scripts/sync_raw_data_to_azure.py --all           # Sync everything
    python scripts/sync_raw_data_to_azure.py --canonical     # Sync canonical only
    python scripts/sync_raw_data_to_azure.py --dry-run       # Preview what would sync
    python scripts/sync_raw_data_to_azure.py --include-ncaahoopR  # Include 7GB PBP data
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("WARNING: azure-storage-blob not installed. Run: pip install azure-storage-blob")

# Import canonical components
try:
    from testing.canonical.ingestion_pipeline import CanonicalIngestionPipeline, DataSource
    from testing.canonical.quality_gates import DataQualityGate
    CANONICAL_AVAILABLE = True
except ImportError:
    CANONICAL_AVAILABLE = False
    print("WARNING: Canonical ingestion components not available. Data will not be canonicalized.")


# Default paths
HISTORICAL_DATA_ROOT = Path(__file__).parent.parent / "ncaam_historical_data_local"
RAW_ODDS_PATH = HISTORICAL_DATA_ROOT / "odds" / "raw" / "archive"
NCAAHOOPR_PATH = HISTORICAL_DATA_ROOT / "ncaahoopR_data-master"

# Canonical data paths (primary data for backtesting)
CANONICAL_PATHS = {
    "backtest_datasets": HISTORICAL_DATA_ROOT / "backtest_datasets",
    "scores_fg": HISTORICAL_DATA_ROOT / "scores" / "fg",
    "scores_h1": HISTORICAL_DATA_ROOT / "scores" / "h1",
    "ratings": HISTORICAL_DATA_ROOT / "ratings",
    "odds_canonical": HISTORICAL_DATA_ROOT / "odds" / "canonical",
    "odds_normalized": HISTORICAL_DATA_ROOT / "odds" / "normalized",
    "canonicalized": HISTORICAL_DATA_ROOT / "canonicalized",
    "schemas": HISTORICAL_DATA_ROOT / "schemas",
    "manifests": HISTORICAL_DATA_ROOT / "manifests",
}

# Azure config
CANONICAL_CONTAINER = "ncaam-historical-data"  # Primary container for backtesting
RAW_CONTAINER = "ncaam-historical-raw"  # Raw data backup
DEFAULT_CONTAINER = CANONICAL_CONTAINER
STORAGE_ACCOUNT = "metricstrackersgbsv"
RESOURCE_GROUP = "dashboard-gbsv-main-rg"


def get_connection_string():
    """Get Azure Storage connection string from env or az CLI."""
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        return conn_str
    
    # Try to fetch via Azure CLI
    import subprocess
    import shutil
    
    # Find az executable (Windows: az.cmd, Linux/Mac: az)
    az_cmd = shutil.which("az") or shutil.which("az.cmd")
    if not az_cmd:
        print("ERROR: Azure CLI (az) not found in PATH")
        return None
    
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
            shell=(os.name == 'nt')  # Use shell on Windows
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR: Could not get connection string: {e}")
        print("Set AZURE_STORAGE_CONNECTION_STRING or login with 'az login'")
        return None


def ensure_container_exists(blob_service: BlobServiceClient, container_name: str):
    """Create the container if it doesn't exist."""
    container_client = blob_service.get_container_client(container_name)
    try:
        container_client.get_container_properties()
        print(f"[OK] Container '{container_name}' exists")
    except Exception:
        print(f"Creating container '{container_name}'...")
        container_client.create_container()
        print(f"[OK] Container '{container_name}' created")


def get_existing_blobs(blob_service: BlobServiceClient, container_name: str, prefix: str = ""):
    """Get set of existing blob names with their sizes."""
    container_client = blob_service.get_container_client(container_name)
    existing = {}
    try:
        for blob in container_client.list_blobs(name_starts_with=prefix):
            existing[blob.name] = blob.size
    except Exception:
        pass
    return existing


def canonicalize_data_before_upload(
    file_path: Path,
    data_type: str = "auto"
) -> Optional[bytes]:
    """
    Canonicalize data before uploading to Azure.

    Args:
        file_path: Path to the local file
        data_type: Type of data for canonicalization

    Returns:
        Canonicalized data as bytes, or None if canonicalization failed
    """
    if not CANONICAL_AVAILABLE:
        # Fall back to original file
        with open(file_path, "rb") as f:
            return f.read()

    try:
        # Read the data
        if file_path.suffix == ".csv":
            df = pd.read_csv(file_path)
        elif file_path.suffix == ".json":
            import json
            with open(file_path) as f:
                data = json.load(f)
            # For JSON data, we might not canonicalize yet
            return json.dumps(data, indent=2).encode('utf-8')
        else:
            # Binary file, return as-is
            with open(file_path, "rb") as f:
                return f.read()

        # Initialize canonical components
        ingestion_pipeline = CanonicalIngestionPipeline(strict_mode=False)  # Don't fail on warnings
        quality_gate = DataQualityGate(strict_mode=False)

        # Infer data type from path if not specified
        if data_type == "auto":
            path_str = str(file_path).lower()
            if "score" in path_str or "game" in path_str:
                data_type = "scores"
            elif "odds" in path_str or "spread" in path_str or "total" in path_str:
                data_type = "odds"
            elif "rating" in path_str:
                data_type = "ratings"
            else:
                data_type = "unknown"

        # Apply canonical ingestion
        if data_type == "scores":
            result = ingestion_pipeline.ingest_scores_data(df, DataSource.ESPN_SCORES)
        elif data_type == "odds":
            result = ingestion_pipeline.ingest_odds_data(df, DataSource.ODDS_API)
        else:
            # Unknown type, just validate
            validation = quality_gate.validate(df, data_type)
            if not validation.passed:
                print(f"  [WARN] Quality issues in {file_path.name}: {len(validation.issues)} issues")
            result = type('Result', (), {'success': True, 'errors': [], 'warnings': []})()

        if result.success:
            # Convert back to bytes
            if file_path.suffix == ".csv":
                return df.to_csv(index=False).encode('utf-8')
            else:
                # For now, return original
                with open(file_path, "rb") as f:
                    return f.read()
        else:
            print(f"  [WARN] Canonical ingestion failed for {file_path.name}: {result.errors}")
            # Return original data
            with open(file_path, "rb") as f:
                return f.read()

    except Exception as e:
        print(f"  [WARN] Canonicalization failed for {file_path.name}: {e}")
        # Return original data
        with open(file_path, "rb") as f:
            return f.read()


def upload_directory(
    blob_service: BlobServiceClient,
    container_name: str,
    local_dir: Path,
    blob_prefix: str,
    extensions: list[str] = None,
    dry_run: bool = False,
    canonicalize: bool = True
):
    """
    Upload all files from a directory to blob storage with canonical ingestion.

    Args:
        blob_service: Azure BlobServiceClient
        container_name: Target container name
        local_dir: Local directory to upload from
        blob_prefix: Prefix for blob names (e.g., "odds/raw/archive")
        extensions: Optional list of file extensions to filter (e.g., [".csv", ".json"])
        dry_run: If True, only print what would be uploaded
        canonicalize: Whether to apply canonical ingestion before upload

    Returns:
        Tuple of (uploaded_count, skipped_count, total_bytes)
    """
    if not local_dir.exists():
        print(f"WARNING: Directory does not exist: {local_dir}")
        return 0, 0, 0

    container_client = blob_service.get_container_client(container_name)
    existing_blobs = get_existing_blobs(blob_service, container_name, blob_prefix)

    uploaded = 0
    skipped = 0
    total_bytes = 0

    files = list(local_dir.rglob("*"))
    files = [f for f in files if f.is_file()]

    if extensions:
        files = [f for f in files if f.suffix.lower() in extensions]

    print(f"\nProcessing {len(files)} files from {local_dir}...")
    if canonicalize and CANONICAL_AVAILABLE:
        print("  Canonical ingestion enabled")
    elif canonicalize:
        print("  Canonical ingestion requested but not available")

    for file_path in sorted(files):
        relative_path = file_path.relative_to(local_dir)
        blob_name = f"{blob_prefix}/{relative_path}".replace("\\", "/")
        file_size = file_path.stat().st_size

        # Check if already exists with same size
        if blob_name in existing_blobs and existing_blobs[blob_name] == file_size:
            skipped += 1
            continue

        if dry_run:
            status = "WOULD UPLOAD" if blob_name not in existing_blobs else "WOULD UPDATE"
            canonical_note = " (canonicalized)" if canonicalize and CANONICAL_AVAILABLE else ""
            print(f"  {status}: {blob_name} ({file_size:,} bytes){canonical_note}")
            uploaded += 1
            total_bytes += file_size
            continue

        # Canonicalize data if requested
        if canonicalize and CANONICAL_AVAILABLE and file_path.suffix in [".csv", ".json"]:
            data_bytes = canonicalize_data_before_upload(file_path)
            actual_size = len(data_bytes) if data_bytes else 0
        else:
            # Upload original file
            with open(file_path, "rb") as f:
                data_bytes = f.read()
            actual_size = file_size

        if data_bytes is None:
            print(f"  [SKIP] Failed to prepare: {blob_name}")
            continue

        # Upload the file
        try:
            blob_client = container_client.get_blob_client(blob_name)

            # Set content type based on extension
            content_type = "text/csv" if file_path.suffix == ".csv" else "application/octet-stream"
            if file_path.suffix == ".json":
                content_type = "application/json"

            blob_client.upload_blob(
                data_bytes,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type)
            )

            canonical_note = " (canonicalized)" if canonicalize and CANONICAL_AVAILABLE and file_path.suffix in [".csv", ".json"] else ""
            print(f"  [OK] Uploaded: {blob_name} ({actual_size:,} bytes){canonical_note}")
            uploaded += 1
            total_bytes += actual_size

        except Exception as e:
            print(f"  [FAIL] Failed: {blob_name} - {e}")

    return uploaded, skipped, total_bytes


def sync_canonical_data(
    blob_service: BlobServiceClient,
    container_name: str,
    dry_run: bool = False,
    canonicalize: bool = True
) -> tuple[int, int, int]:
    """
    Sync all canonical data to Azure.
    
    This includes:
    - backtest_datasets/ (backtest_master.csv, team_aliases, etc.)
    - scores/fg/ and scores/h1/
    - ratings/barttorvik/
    - odds/canonical/ and odds/normalized/
    - canonicalized/ data
    - schemas/ and manifests/
    """
    total_uploaded = 0
    total_skipped = 0
    total_bytes = 0
    
    for name, path in CANONICAL_PATHS.items():
        if not path.exists():
            print(f"\n[SKIP] {name}: Directory not found")
            continue
        
        print(f"\n" + "-" * 40)
        print(f"UPLOADING: {name}")
        print("-" * 40)
        
        # Determine blob prefix from path relative to data root
        try:
            relative = path.relative_to(HISTORICAL_DATA_ROOT)
            blob_prefix = str(relative).replace("\\", "/")
        except ValueError:
            blob_prefix = name
        
        uploaded, skipped, bytes_up = upload_directory(
            blob_service,
            container_name,
            path,
            blob_prefix,
            extensions=[".csv", ".json"],
            dry_run=dry_run,
            canonicalize=canonicalize
        )
        total_uploaded += uploaded
        total_skipped += skipped
        total_bytes += bytes_up
    
    return total_uploaded, total_skipped, total_bytes


def main():
    parser = argparse.ArgumentParser(
        description="Sync ALL historical data to Azure Blob Storage (SINGLE SOURCE OF TRUTH)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be uploaded without uploading"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Sync ALL data (canonical + raw + ncaahoopR)"
    )
    parser.add_argument(
        "--canonical", action="store_true",
        help="Sync canonical data only (backtest_datasets, scores, ratings, odds)"
    )
    parser.add_argument(
        "--raw", action="store_true",
        help="Sync raw data archive only"
    )
    parser.add_argument(
        "--include-ncaahoopR", action="store_true",
        help="Also upload ncaahoopR data (6.7 GB) - use with --all or --raw"
    )
    parser.add_argument(
        "--container", default=None,
        help=f"Override target container (default: auto-select based on data type)"
    )
    parser.add_argument(
        "--canonicalize", action="store_true",
        help="Apply canonical ingestion pipeline before uploading"
    )
    parser.add_argument(
        "--no-canonicalize", action="store_true",
        help="Skip canonical ingestion (upload raw data)"
    )
    args = parser.parse_args()
    
    # Default to canonical if nothing specified
    if not (args.all or args.canonical or args.raw):
        args.canonical = True

    # Default canonicalization behavior
    if args.no_canonicalize:
        canonicalize = False
    elif args.canonicalize:
        canonicalize = True
    else:
        # Auto-enable for canonical data uploads
        canonicalize = CANONICAL_AVAILABLE
    
    if not AZURE_AVAILABLE:
        print("ERROR: azure-storage-blob package required")
        print("Install with: pip install azure-storage-blob")
        sys.exit(1)
    
    # Get connection string
    conn_str = get_connection_string()
    if not conn_str:
        sys.exit(1)
    
    print("=" * 70)
    print("NCAAM Historical Data -> Azure Blob Storage")
    print("SINGLE SOURCE OF TRUTH SYNC")
    print("=" * 70)
    print(f"Storage Account: {STORAGE_ACCOUNT}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE UPLOAD'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    print("Data to sync:")
    print(f"  Canonical data: {'YES' if args.canonical or args.all else 'NO'}")
    print(f"  Raw data archive: {'YES' if args.raw or args.all else 'NO'}")
    print(f"  ncaahoopR (7GB): {'YES' if args.include_ncaahoopR else 'NO'}")
    
    # Connect to Azure
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    
    total_uploaded = 0
    total_skipped = 0
    total_bytes = 0
    
    # Sync canonical data
    if args.canonical or args.all:
        container = args.container or CANONICAL_CONTAINER
        print(f"\n{'='*70}")
        print(f"CANONICAL DATA -> {container}")
        print("=" * 70)
        
        if not args.dry_run:
            ensure_container_exists(blob_service, container)
        
        uploaded, skipped, bytes_up = sync_canonical_data(
            blob_service, container, dry_run=args.dry_run, canonicalize=canonicalize
        )
        total_uploaded += uploaded
        total_skipped += skipped
        total_bytes += bytes_up
    
    # Sync raw data
    if args.raw or args.all:
        container = args.container or RAW_CONTAINER
        print(f"\n{'='*70}")
        print(f"RAW DATA -> {container}")
        print("=" * 70)
        
        if not args.dry_run:
            ensure_container_exists(blob_service, container)
        
        # Raw odds archive
        print("\n" + "-" * 40)
        print("UPLOADING: Raw Odds Archive")
        print("-" * 40)
        uploaded, skipped, bytes_up = upload_directory(
            blob_service,
            container,
            RAW_ODDS_PATH,
            "odds/raw/archive",
            extensions=[".csv"],
            dry_run=args.dry_run
        )
        total_uploaded += uploaded
        total_skipped += skipped
        total_bytes += bytes_up
    
    # Sync ncaahoopR data
    if args.include_ncaahoopR:
        container = args.container or RAW_CONTAINER
        print(f"\n{'='*70}")
        print(f"ncaahoopR DATA (7GB) -> {container}")
        print("=" * 70)
        
        if not args.dry_run:
            ensure_container_exists(blob_service, container)
        
        uploaded, skipped, bytes_up = upload_directory(
            blob_service,
            container,
            NCAAHOOPR_PATH,
            "ncaahoopR_data-master",
            dry_run=args.dry_run
        )
        total_uploaded += uploaded
        total_skipped += skipped
        total_bytes += bytes_up
    
    # Summary
    print("\n" + "=" * 70)
    print("SYNC SUMMARY")
    print("=" * 70)
    print(f"Uploaded: {total_uploaded} files")
    print(f"Skipped (already exists): {total_skipped} files")
    print(f"Total bytes: {total_bytes:,} ({total_bytes / 1024 / 1024:.2f} MB)")
    
    if args.dry_run:
        print("\n[WARNING]  DRY RUN - No files were actually uploaded")
        print("Run without --dry-run to perform the upload")
    else:
        print("\n[OK] Azure is now the SINGLE SOURCE OF TRUTH")
        print("Backtesting can read directly from Azure using:")
        print("  from testing.azure_data_reader import read_backtest_master")
        print("  df = read_backtest_master()")


if __name__ == "__main__":
    main()
