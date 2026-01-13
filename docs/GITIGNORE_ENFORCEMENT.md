# GITIGNORE ENFORCEMENT - Data Storage Compliance
**Version:** 1.0  
**Date:** January 12, 2026  
**Purpose:** Prevent ANY data files from being committed to Git

---

## 📋 Current .gitignore Structure

This document outlines what MUST be in `.gitignore` to enforce the data governance policy.

### Location: `.gitignore` (repository root)

```gitignore
# ============================================================================
# DATA STORAGE COMPLIANCE - SINGLE SOURCE OF TRUTH IS AZURE BLOB STORAGE ONLY
# ============================================================================
# ANY violation of these rules indicates a data governance breach

# LOCAL DATA DIRECTORIES (Blocked completely)
ncaam_historical_data_local/
testing/data/
ncaam_historical_data_backup/
local_cache/
.cache/
*.cache

# TEMPORARY PROCESSING (Auto-cleaned, not committed)
testing/data/tmp_*/
testing/data/temp_*/
testing/data/*_scratch/
*.tmp
*.temp

# PREDICTION RESULTS (Should be output to Azure, not stored locally)
predictions/
predictions_*.csv
*.predictions

# BACKTEST RESULTS (Store in Azure or ephemeral local)
backtest_results/
backtest_output/
backtest_*.csv

# CSV DATA FILES (NEVER in Git)
*.csv
*.csv.gz
*.csv.bak

# JSON DATA FILES (NEVER in Git - except config/schema files)
data_*.json
dataset_*.json
training_*.json
test_*.json
*.data.json
ncaam_*.json
# Exception: Keep config and schema files
!**/config/*.json
!**/schemas/*.json
!**/*_schema.json

# PARQUET/ARROW (Data formats - NEVER in Git)
*.parquet
*.parq
*.arrow

# EXCEL/SPREADSHEET (Data - NEVER in Git)
*.xlsx
*.xls
*.ods

# DATABASE FILES
*.db
*.sqlite
*.sqlite3
*.mdb

# LOGS (Often contain data)
logs/
*.log
*.logs

# SECRETS (Never in Git anyway, but be explicit)
secrets/
.env
.env.local
*.secret
*_secrets

# OS/EDITOR ARTIFACTS
.DS_Store
.vscode/
.idea/
*.swp
*.swo
*~
.project
.pydevproject

# PYTHON ARTIFACTS (Keep .gitignore out of __pycache__)
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# VENV (Never commit virtual env)
venv/
env/
ENV/
.venv

# R ARTIFACTS
.Rhistory
.Rdata
*.RData
.Rproject.user/
.Rbuildignore

# NOTEBOOKS (Keep outputs but not large data)
.ipynb_checkpoints/
*.ipynb_checkpoints

# BUILD/DIST
dist/
build/
*.egg-info/

# ============================================================================
# EXCEPTIONS (Things we DO want in Git)
# ============================================================================

# Configuration files ARE committed
!**/*.config.json
!**/*.config.yaml
!**/.env.example
!**/*.schema.json

# Documentation IS committed
!docs/
!README.md
!CHANGELOG.md

# Source code IS committed
!testing/scripts/
!testing/canonical/
!testing/sources/
!services/

# Manifests and audit records ARE committed
!manifests/
manifests/*.csv    # But not CSV copies - just JSON
manifests/*.xlsx

# Version/changelog files ARE committed
!VERSION
!CHANGELOG*
!*.md
```

---

## 🔍 Compliance Verification

### Check 1: Scan for violated files

```bash
# Find any CSV files that might be tracked
git ls-files | grep -E '\.(csv|xlsx|json|db|sqlite)$' | grep -v 'schema\|config'

# Find any large files (potential data)
git ls-files -z | xargs -0 du -h | sort -rh | head -20
```

### Check 2: Verify no local data directories in Git

```bash
# These should return NO results
git ls-files | grep 'ncaam_historical_data_local'
git ls-files | grep 'testing/data/' | grep -v 'testing/data/README'
git ls-files | grep 'predictions/'
git ls-files | grep 'backtest_results/'
```

### Check 3: Pre-commit hook to prevent violations

Create ``.git/hooks/pre-commit``:

```bash
#!/bin/bash
# Prevent committing data files

VIOLATIONS=0

# Check for CSV files
if git diff --cached --name-only | grep -E '\.(csv|xlsx|db|sqlite)$'; then
    echo "❌ ERROR: Attempting to commit data files (CSV/XLSX/DB)"
    echo "   Data belongs in Azure Blob Storage, not Git!"
    VIOLATIONS=$((VIOLATIONS+1))
fi

# Check for large JSON data files
if git diff --cached --name-only | grep -E '(data_|dataset_|training_|ncaam_).*\.json$'; then
    echo "❌ ERROR: Attempting to commit data JSON files"
    echo "   Data belongs in Azure Blob Storage, not Git!"
    VIOLATIONS=$((VIOLATIONS+1))
fi

# Check for prediction results
if git diff --cached --name-only | grep -i 'predictions\|backtest_results'; then
    echo "❌ ERROR: Attempting to commit prediction/backtest outputs"
    echo "   Results belong in Azure Blob Storage, not Git!"
    VIOLATIONS=$((VIOLATIONS+1))
fi

if [ $VIOLATIONS -gt 0 ]; then
    echo ""
    echo "To commit data files to Azure instead:"
    echo "  python testing/scripts/sync_data_to_azure.py --all"
    exit 1
fi

exit 0
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

---

## 🚨 Data Governance Validator

Create `testing/scripts/data_governance_validator.py` to audit compliance:

**Key Checks:**
1. ❌ Detect any CSV/JSON/Excel files in Git
2. ❌ Detect data files in local `/testing/data/` (not temp)
3. ❌ Detect prediction outputs stored locally
4. ✅ Verify all scripts read from Azure (not local)
5. ✅ Verify all ingestion outputs go to Azure
6. ✅ Check that manifests have audit trails

---

## 📋 Enforcement Matrix

| Layer | Tool | Action | Result |
|-------|------|--------|--------|
| **Commit-time** | `.gitignore` | Block patterns | Files never staged |
| **Pre-commit** | `.git/hooks/pre-commit` | Script check | Commit blocked if violation |
| **CI/CD** | GitHub Actions | Scan for violations | Build fails if data found |
| **Code audit** | `data_governance_validator.py` | Scan scripts | Reports non-compliant reads |
| **Runtime** | `AzureDataReader` | Enforce Azure-first | Scripts crash if trying local read |

---

## ✅ Audit Checklist

Before any commit:

- [ ] No `.csv` files in `git status`
- [ ] No `.xlsx` files in `git status`
- [ ] No `.json` files (except config/schema)
- [ ] No data in `testing/data/` (except temp)
- [ ] No `predictions/` directory contents
- [ ] No `backtest_results/` directory contents
- [ ] Run: `python testing/scripts/data_governance_validator.py`
- [ ] All scripts use `AzureDataReader` (not local reads)
- [ ] All outputs uploaded to Azure (not stored locally)

---

## 🎯 Why This Matters

**Without strict enforcement:**
- ❌ Data accidentally committed to Git (now permanent)
- ❌ Multiple copies of "truth" (local vs Azure)
- ❌ Confusion about which version is current
- ❌ Impossible to maintain data integrity
- ❌ Security risk (data in public Git)

**With enforcement:**
- ✅ Single source of truth (Azure only)
- ✅ Immutable audit trails
- ✅ No accidental commits
- ✅ Clear data governance
- ✅ Disaster recovery via Azure
