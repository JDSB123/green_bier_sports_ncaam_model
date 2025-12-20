# Kaggle Dataset Setup (Testing Branch)

Legacy NCAAM backtests rely on the free historical data provided by Kaggle's **March Machine Learning Mania** competition. Follow the steps below to pull those CSVs into `testing/data/kaggle/` for analysis.

## 1. Install Dependencies

```bash
pip install -r testing/requirements.txt
```

`rich` is included for better terminal output but is optional if you prefer to
trim dependencies.

## 2. Configure Credentials

### Option A: kaggle.json (recommended)

1. Visit https://www.kaggle.com/settings
2. In the *API* section choose **Create New API Token**
3. Save the downloaded `kaggle.json` to one of:
   - Windows: `C:\Users\<you>\.kaggle\kaggle.json`
   - macOS/Linux: `~/.kaggle/kaggle.json`
4. On non-Windows systems run `chmod 600 ~/.kaggle/kaggle.json`

### Option B: Environment Variable

Add the token (string beginning with `KGAT_`) to your environment or `.env` file:

```
KAGGLE_API_TOKEN=KGAT_xxxxxxxxx
```

The downloader pulls credentials from the environment first and falls back to `kaggle.json` if needed.

## 3. Join the Competition

Kaggle blocks downloads until you accept the competition terms.

1. Open https://www.kaggle.com/competitions/march-machine-learning-mania-2025
2. Click **Join Competition** or **I Understand and Accept**

## 4. Download the Dataset

From the repository root run:

```bash
python testing/scripts/download_kaggle_data.py
```

This script:

- Verifies credentials
- Downloads the competition ZIP via the Kaggle API
- Extracts only the required CSVs
- Writes them to `testing/data/kaggle/`
- Skips existing files unless `--force` is provided

## 5. Verify

Run the loader smoke test:

```bash
python -m testing.sources.kaggle_scores --season 2025 --sample 3
```

Expected output includes dataset metadata and a few sample games. Errors usually indicate missing files or unaccepted competition rules.

## 6. Keep Data Out of Git

The root `.gitignore` already ignores `testing/data/kaggle/*.csv`. Leave those files untracked; regenerate them whenever you need a fresh copy.

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `403 - Forbidden` | Rules not accepted | Visit the competition page and click *Join Competition* |
| `401 - Unauthorized` | Token missing/expired | Re-download `kaggle.json` and rerun the script |
| `FileNotFoundError` for CSVs | Download incomplete | Re-run downloader with `--force` |
| `ValueError` about columns | Kaggle changed schema | Inspect CSV headers and update loader mappings |

For loader internals see `testing/sources/kaggle_scores.py`.
