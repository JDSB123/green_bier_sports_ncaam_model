#!/usr/bin/env python3
"""
Sync raw historical data to Azure Blob Storage.

This script uploads raw odds data (and other large files) to Azure Blob Storage
for archival/backup. Raw data is gitignored but must be preserved in Azure.

Storage Account: metricstrackersgbsv (dashboard-gbsv-main-rg)
Container: ncaam-historical-raw

Usage:
    python scripts/sync_raw_data_to_azure.py
    python scripts/sync_raw_data_to_azure.py --dry-run
    python scripts/sync_raw_data_to_azure.py --container ncaam-historical-raw
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("WARNING: azure-storage-blob not installed. Run: pip install azure-storage-blob")


# Default paths
HISTORICAL_DATA_ROOT = Path(__file__).parent.parent / "ncaam_historical_data_local"
RAW_ODDS_PATH = HISTORICAL_DATA_ROOT / "odds" / "raw" / "archive"
NCAAHOOPR_PATH = HISTORICAL_DATA_ROOT / "ncaahoopR_data-master"

# Azure config
DEFAULT_CONTAINER = "ncaam-historical-raw"
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


def upload_directory(
    blob_service: BlobServiceClient,
    container_name: str,
    local_dir: Path,
    blob_prefix: str,
    extensions: list[str] = None,
    dry_run: bool = False
):
    """
    Upload all files from a directory to blob storage.
    
    Args:
        blob_service: Azure BlobServiceClient
        container_name: Target container name
        local_dir: Local directory to upload from
        blob_prefix: Prefix for blob names (e.g., "odds/raw/archive")
        extensions: Optional list of file extensions to filter (e.g., [".csv", ".json"])
        dry_run: If True, only print what would be uploaded
    
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
            print(f"  {status}: {blob_name} ({file_size:,} bytes)")
            uploaded += 1
            total_bytes += file_size
            continue
        
        # Upload the file
        try:
            blob_client = container_client.get_blob_client(blob_name)
            
            # Set content type based on extension
            content_type = "text/csv" if file_path.suffix == ".csv" else "application/octet-stream"
            if file_path.suffix == ".json":
                content_type = "application/json"
            
            with open(file_path, "rb") as data:
                blob_client.upload_blob(
                    data,
                    overwrite=True,
                    content_settings=ContentSettings(content_type=content_type)
                )
            
            print(f"  [OK] Uploaded: {blob_name} ({file_size:,} bytes)")
            uploaded += 1
            total_bytes += file_size
            
        except Exception as e:
            print(f"  [FAIL] Failed: {blob_name} - {e}")
    
    return uploaded, skipped, total_bytes


def main():
    parser = argparse.ArgumentParser(description="Sync raw historical data to Azure Blob Storage")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be uploaded without uploading")
    parser.add_argument("--container", default=DEFAULT_CONTAINER, help=f"Target container (default: {DEFAULT_CONTAINER})")
    parser.add_argument("--include-ncaahoopR", action="store_true", help="Also upload ncaahoopR data (6.7 GB)")
    args = parser.parse_args()
    
    if not AZURE_AVAILABLE:
        print("ERROR: azure-storage-blob package required")
        print("Install with: pip install azure-storage-blob")
        sys.exit(1)
    
    # Get connection string
    conn_str = get_connection_string()
    if not conn_str:
        sys.exit(1)
    
    print("=" * 60)
    print("NCAAM Historical Data -> Azure Blob Storage Sync")
    print("=" * 60)
    print(f"Storage Account: {STORAGE_ACCOUNT}")
    print(f"Container: {args.container}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE UPLOAD'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Connect to Azure
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    
    # Ensure container exists
    if not args.dry_run:
        ensure_container_exists(blob_service, args.container)
    
    total_uploaded = 0
    total_skipped = 0
    total_bytes = 0
    
    # Upload raw odds archive
    print("\n" + "-" * 40)
    print("UPLOADING: Raw Odds Archive")
    print("-" * 40)
    uploaded, skipped, bytes_up = upload_directory(
        blob_service,
        args.container,
        RAW_ODDS_PATH,
        "odds/raw/archive",
        extensions=[".csv"],
        dry_run=args.dry_run
    )
    total_uploaded += uploaded
    total_skipped += skipped
    total_bytes += bytes_up
    
    # Optionally upload ncaahoopR data
    if args.include_ncaahoopR:
        print("\n" + "-" * 40)
        print("UPLOADING: ncaahoopR Play-by-Play Data")
        print("-" * 40)
        uploaded, skipped, bytes_up = upload_directory(
            blob_service,
            args.container,
            NCAAHOOPR_PATH,
            "ncaahoopR_data-master",
            dry_run=args.dry_run
        )
        total_uploaded += uploaded
        total_skipped += skipped
        total_bytes += bytes_up
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Uploaded: {total_uploaded} files")
    print(f"Skipped (already exists): {total_skipped} files")
    print(f"Total bytes: {total_bytes:,}")
    
    if args.dry_run:
        print("\n[WARNING]  DRY RUN - No files were actually uploaded")
        print("Run without --dry-run to perform the upload")


if __name__ == "__main__":
    main()
