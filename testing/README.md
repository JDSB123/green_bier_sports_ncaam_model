# Testing Branch Toolkit

This directory collects legacy utilities that should not live in the production
service tree.

## Quick Start

1. Install python dependencies:
   ```bash
   pip install -r testing/requirements.txt
   ```
2. Configure Kaggle credentials (see docs/KAGGLE_SETUP.md).
3. Download the historical CSVs:
   ```bash
   python testing/scripts/download_kaggle_data.py
   ```
4. Verify ingest:
   ```bash
   python -m testing.sources.kaggle_scores --season 2025 --sample 5
   ```

All output CSVs land under `testing/data/kaggle/` and are ignored by git.

## ESPN schedule reference (optional)

If you want an "official" slate reference (start times, venue, neutral site flag),
use the ESPN public scoreboard feed cross-reference script:

```bash
# Print the full D1 slate for a date as a Markdown table
python testing/scripts/espn_schedule_xref.py --date 20251221

# Cross-reference a specific matchup list (one per line: "Team A vs Team B" or "A,B")
python testing/scripts/espn_schedule_xref.py --date 20251221 --matchups-file matchups.txt
```

Data source (public, no auth): `https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard`

## Branch Usage

Keep this folder on the `ncaam_model_testing` branch for experimental work. When
running the same tests on `ncaam_model_dev`, cherry-pick or merge the commits so
the scripts remain in sync before executing them.
