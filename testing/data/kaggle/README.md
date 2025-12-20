# Kaggle NCAA Data (Testing Only)

This folder is a placeholder for the historical CSV files downloaded from Kaggle's **March Machine Learning Mania** competition. The testing branch keeps these assets separate from production code so legacy experiments do not pollute the main model tree.

## Required Files

After running the downloader script in `testing/scripts`, the following files should live here:

- `MRegularSeasonCompactResults.csv`
- `MRegularSeasonDetailedResults.csv`
- `MTeams.csv`
- `MTeamSpellings.csv`
- `MSeasons.csv`

The scripts will automatically overwrite any existing copy. Do **not** commit the raw CSVs to source control—they are ignored by `.gitignore`.

## Quick Usage

1. Configure Kaggle credentials (`~/.kaggle/kaggle.json` or `KAGGLE_API_TOKEN` env var).
2. Run `python testing/scripts/download_kaggle_data.py` from the repository root.
3. Use the loader in `testing/sources/kaggle_scores.py` to access scores for backtests.

For troubleshooting, see `testing/docs/KAGGLE_SETUP.md`.
