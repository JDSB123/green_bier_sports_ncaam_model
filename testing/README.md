# Testing Branch Toolkit

This directory collects legacy utilities that should not live in the production
service tree.

## Quick Start

1. Install python dependencies:
   ```bash
   pip install -r testing/requirements.txt
   ```
2. Ensure Azure Blob access is configured.
3. Run the backtest suite:
   ```bash
   python testing/run_backtest_suite.py calibration --seasons 2024 2025
   python testing/run_backtest_suite.py roi --seasons 2024
   ```

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
