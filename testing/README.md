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

## Branch Usage

Keep this folder on the `ncaam_model_testing` branch for experimental work. When
running the same tests on `ncaam_model_dev`, cherry-pick or merge the commits so
the scripts remain in sync before executing them.
