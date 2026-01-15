import os
import sys
import argparse
from datetime import datetime

try:
    from testing.azure_data_reader import AzureDataReader
    from testing.azure_data_writer import AzureDataWriter
except ImportError:
    print("ERROR: AzureDataReader/AzureDataWriter not found. Activate your environment.")
    sys.exit(1)
import pandas as pd

LOCAL_PATH = "manifests/canonical_training_data_master.csv"
AZURE_PATH = "canonical/canonical_training_data_master.csv"

def validate_master(df):
    required_cols = ["season", "game_id", "market", "home_team", "away_team", "spread", "total", "odds_source"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"ERROR: Missing required columns: {missing}")
        return False
    # Market coverage check
    markets = df["market"].unique()
    print(f"Markets present: {markets}")
    for m in ["fg_spread", "fg_total", "h1_spread", "h1_total"]:
        count = (df["market"] == m).sum()
        print(f"{m}: {count} rows")
        if count == 0:
            print(f"WARNING: No coverage for {m}")
    print(f"Total rows: {len(df)}")
    return True

def download_from_azure():
    reader = AzureDataReader()
    print(f"Downloading {AZURE_PATH} from Azure to {LOCAL_PATH}...")
    df = reader.read_csv(AZURE_PATH)
    df.to_csv(LOCAL_PATH, index=False)
    print("Download complete.")
    validate_master(df)

def upload_to_azure():
    writer = AzureDataWriter()
    print(f"Uploading {LOCAL_PATH} to Azure as {AZURE_PATH}...")
    df = pd.read_csv(LOCAL_PATH)
    validate_master(df)
    writer.write_csv(df, AZURE_PATH)
    print("Upload complete.")

def main():
    parser = argparse.ArgumentParser(description="Sync canonical master between local and Azure.")
    parser.add_argument("--direction", choices=["upload", "download"], required=True, help="Direction of sync: upload or download.")
    args = parser.parse_args()

    if args.direction == "download":
        download_from_azure()
    elif args.direction == "upload":
        upload_to_azure()

if __name__ == "__main__":
    main()
