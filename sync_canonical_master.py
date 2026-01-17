import argparse
import sys

try:
    from testing.azure_data_writer import AzureDataWriter

    from testing.azure_data_reader import AzureDataReader
except ImportError:
    print("ERROR: AzureDataReader/AzureDataWriter not found. Activate your environment.")
    sys.exit(1)
import pandas as pd

LOCAL_PATH = "manifests/canonical_training_data_master.csv"
AZURE_PATH = "canonical/canonical_training_data_master.csv"

def validate_master(df):
    # Updated validation for cleaned canonical master
    required_cols = ["season", "game_id", "home_canonical", "away_canonical", "fg_spread", "fg_total"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"ERROR: Missing required columns: {missing}")
        return False

    # Coverage check
    print(f"Total rows: {len(df)}")
    print(f"Seasons: {sorted(df['season'].unique().tolist())}")
    print(f"FG Spread coverage: {df['fg_spread'].notna().sum()} ({df['fg_spread'].notna().sum()/len(df)*100:.1f}%)")
    print(f"FG Total coverage: {df['fg_total'].notna().sum()} ({df['fg_total'].notna().sum()/len(df)*100:.1f}%)")
    print(f"H1 Spread coverage: {df['h1_spread'].notna().sum()} ({df['h1_spread'].notna().sum()/len(df)*100:.1f}%)")
    print(f"Teams: {len(set(df['home_canonical']) | set(df['away_canonical']))} unique")
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
