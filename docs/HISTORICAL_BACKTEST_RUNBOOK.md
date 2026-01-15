# Historical Backtest Runbook

**Status:** Manual-only
**Scope:** Leakage-safe historical backtesting using Azure canonical data

---

## Goals

- Validate model performance using **canonical Azure data** only.
- Enforce **anti-leakage** rules (no same-season ratings, no closing lines for decisions).
- Produce auditable outputs with consistent, repeatable steps.

---

## Prerequisites

1. **Azure canonical access** is configured.
   - Environment variable: `AZURE_CANONICAL_CONNECTION_STRING`
2. **Canonical data exists** in `ncaam-historical-data`.
3. **No local data copies** are used; reads are via Azure only.

References:
- [docs/SINGLE_SOURCE_OF_TRUTH.md](docs/SINGLE_SOURCE_OF_TRUTH.md)
- [docs/HISTORICAL_DATA_SYNC.md](docs/HISTORICAL_DATA_SYNC.md)
- [testing/azure_data_reader.py](testing/azure_data_reader.py)

---

## Step 1: Data Integrity Gate (Required)

Run integrity checks before any backtest:
- Script: [testing/verify_data_integrity.py](testing/verify_data_integrity.py)
- Verifies data tag, checksums, team aliases, and anti-leakage ratings season rule.

**Pass/Fail:**
- Must return **ALL CHECKS PASSED**.

---

## Step 2: Build Canonical Backtest Dataset (If Data Changed)

If new data was ingested or refreshed, rebuild the canonical backtest dataset:
- Script: [testing/scripts/build_backtest_dataset_canonical.py](testing/scripts/build_backtest_dataset_canonical.py)
- Output: `backtest_datasets/backtest_master.csv` (Azure canonical)

**Pass/Fail:**
- Build completes without validation errors.

---

## Step 3: Historical Backtest (Baseline)

Run historical backtest on canonical data:
- Script: [testing/scripts/run_historical_backtest.py](testing/scripts/run_historical_backtest.py)
- Output directory: `testing/results/historical/`

**Pass/Fail:**
- Backtest completes for selected markets.
- Data validation passes in the backtest output.

---

## Step 4: CLV Backtest (Quality Signal)

Run CLV backtest to measure market sharpness:
- Script: [testing/scripts/run_clv_backtest.py](testing/scripts/run_clv_backtest.py)
- Output directory: `testing/results/clv_backtest/`

**Pass/Fail:**
- CLV backtest completes with no data leakage errors.

---

## Step 5: Validate Against No‑Leakage Benchmarks

Compare results to the validated, no‑leakage baseline:
- Reference: [docs/validation/BACKTEST_VALIDATION_REPORT.md](docs/validation/BACKTEST_VALIDATION_REPORT.md)

**Expected Ranges:**
- Spread direction accuracy and ROI should be **in line** with the validation report.
- Totals ROI should be **modest** (lower than spreads).

---

## Step 6: Record Results

Store or summarize results for audit:
- Use the generated outputs under `testing/results/`.
- Update validation documentation if new results materially differ.

Suggested update target:
- [docs/validation/BACKTEST_VALIDATION_REPORT.md](docs/validation/BACKTEST_VALIDATION_REPORT.md)

---

## Acceptance Criteria (Ready for Historical Backtesting)

All of the following must be true:

- ✅ Azure canonical access works.
- ✅ Integrity checks pass.
- ✅ Canonical backtest dataset is built (if data changed).
- ✅ Historical backtest runs on Azure data.
- ✅ CLV backtest runs on Azure data.
- ✅ Results align with no‑leakage benchmarks.

---

## Notes

- Backtesting is **manual‑only** by policy.
- **Do not** use local data copies.
- **Do not** use end‑of‑season ratings for in‑season predictions.

---

## Related Docs

- [docs/BACKTESTING_METHODOLOGY.md](docs/BACKTESTING_METHODOLOGY.md)
- [docs/validation/BACKTEST_VALIDATION_REPORT.md](docs/validation/BACKTEST_VALIDATION_REPORT.md)
- [docs/SINGLE_SOURCE_OF_TRUTH.md](docs/SINGLE_SOURCE_OF_TRUTH.md)
