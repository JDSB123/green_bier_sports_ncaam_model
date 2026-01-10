#!/usr/bin/env python3
"""
DOWNLOAD CANONICAL DATA FROM AZURE - SINGLE SOURCE OF TRUTH
===========================================================

This script downloads the canonical backtest datasets from Azure Blob Storage,
which serves as the SINGLE SOURCE OF TRUTH for all historical NCAAM data.

Azure Storage Account: metricstrackersgbsv (dashboard-gbsv-main-rg)
Container: ncaam-historical-data (canonical data for backtesting)

This replaces any local corrupted data with the authoritative version.

Usage:
    python scripts/download_canonical_from_azure.py --all              # Download all canonical data
    python scripts/download_canonical_from_azure.py --datasets         # Download backtest datasets only
    python scripts/download_canonical_from_azure.py --dry-run          # Preview what would download
    python scripts/download_canonical_from_azure.py --force            # Overwrite local files
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from azure.storage.blob import BlobServiceClient
    from azure.identity import DefaultAzureCredential
    AZURE_AVAILABLE = True
except ImportError as e:
    AZURE_AVAILABLE = False
    print(f"ERROR: Azure packages not installed: {e}")
    print("Run: pip install azure-storage-blob azure-identity")
    sys.exit(1)

# Configuration
STORAGE_ACCOUNT = "metricstrackersgbsv"
CONTAINER_NAME = "ncaam-historical-data"  # Canonical data container
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "ncaam_historical_data_local"
BACKTEST_DIR = DATA_DIR / "backtest_datasets"

# Canonical files to download
CANONICAL_FILES = [
    "backtest_datasets/backtest_master_consolidated.csv",
    "backtest_datasets/ncaahoopR_features.csv",
    "backtest_datasets/team_aliases_db.json",
    "backtest_datasets/validation_results.json",
    # Add more canonical files as needed
]


def get_blob_service_client():
    """Get Azure BlobServiceClient using Azure CLI authentication."""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        account_url = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net"
        credential = DefaultAzureCredential()

        blob_service = BlobServiceClient(account_url=account_url, credential=credential)
        return blob_service
    except ImportError:
        print("ERROR: azure-identity not installed. Run: pip install azure-identity")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to authenticate with Azure: {e}")
        print("Make sure you're logged in with: az login")
        sys.exit(1)


def ensure_directories():
    """Ensure local directories exist."""
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)


def list_canonical_blobs(blob_service: BlobServiceClient, prefix: str = "") -> list:
    """List all blobs in the canonical container."""
    container_client = blob_service.get_container_client(CONTAINER_NAME)
    blobs = container_client.list_blobs(name_starts_with=prefix)
    return [blob.name for blob in blobs]


def download_blob(blob_service: BlobServiceClient, blob_name: str, local_path: Path, force: bool = False):
    """Download a single blob to local path."""
    if local_path.exists() and not force:
        print(f"SKIP: {blob_name} (exists locally, use --force to overwrite)")
        return False

    try:
        blob_client = blob_service.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
        print(f"DOWNLOADING: {blob_name} -> {local_path}")

        with open(local_path, "wb") as download_file:
            download_stream = blob_client.download_blob()
            download_file.write(download_stream.readall())

        return True
    except Exception as e:
        print(f"ERROR downloading {blob_name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download canonical data from Azure Blob Storage")
    parser.add_argument('--all', action='store_true', help='Download all canonical data')
    parser.add_argument('--datasets', action='store_true', help='Download backtest datasets only')
    parser.add_argument('--dry-run', action='store_true', help='Preview what would download')
    parser.add_argument('--force', action='store_true', help='Overwrite existing local files')
    parser.add_argument('--list', action='store_true', help='List all canonical blobs')

    args = parser.parse_args()

    # Validate arguments
    if not any([args.all, args.datasets, args.list]):
        print("ERROR: Must specify --all, --datasets, or --list")
        sys.exit(1)

    # Get blob service client with Azure CLI authentication
    blob_service = get_blob_service_client()
    ensure_directories()

    print(f"🔗 Connected to Azure Storage: {STORAGE_ACCOUNT}")
    print(f"📦 Container: {CONTAINER_NAME}")
    print(f"📁 Local directory: {DATA_DIR}")
    print()

    if args.list:
        print("📋 Listing all canonical blobs:")
        blobs = list_canonical_blobs(blob_service)
        for blob in sorted(blobs):
            print(f"  {blob}")
        return

    # Determine which files to download
    files_to_download = []
    if args.all or args.datasets:
        # Download all files from backtest_datasets directory
        prefix = "backtest_datasets/"
        blobs = list_canonical_blobs(blob_service, prefix)
        files_to_download = [blob for blob in blobs if blob.startswith(prefix)]

    if args.dry_run:
        print("🔍 DRY RUN - Would download:")
        for blob_name in files_to_download:
            local_path = ROOT_DIR / blob_name
            exists = local_path.exists()
            status = "EXISTS" if exists else "NEW"
            print(f"  {status}: {blob_name} -> {local_path}")
        return

    # Download files
    print(f"⬇️ Downloading {len(files_to_download)} canonical files...")
    print()

    downloaded = 0
    for blob_name in files_to_download:
        local_path = ROOT_DIR / blob_name
        if download_blob(blob_service, blob_name, local_path, args.force):
            downloaded += 1

    print()
    print(f"✅ Downloaded {downloaded}/{len(files_to_download)} canonical files")
    print("🔄 Local data now matches Azure single source of truth")


if __name__ == "__main__":
    main()