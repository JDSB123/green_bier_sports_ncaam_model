# API Key Unification - Summary of Changes

**Date:** January 9, 2026  
**Problem:** Inconsistent API key handling across environments causing access/privacy issues  
**Solution:** Unified secrets manager with priority-based loading

---

## 🎯 What Changed

### 1. **New Unified Secrets Module** ✅
**File:** `testing/scripts/secrets_manager.py`

Provides a single, consistent way to load secrets across all environments:

```python
from secrets_manager import get_api_key, get_db_password

# Works in local dev, Docker, and Azure
api_key = get_api_key("odds")      # Tries env var → Docker secret → local file
db_pass = get_db_password()         # Same 3-tier priority

# With clear error messages if missing
# ERROR: tells you exactly which 3 sources were checked
```

**Priority order (what gets used):**
1. ✅ Environment variable (all platforms)
2. 🐳 Docker secret at `/run/secrets/` (containers)
3. 📄 Local file at `secrets/*.txt` (local dev)

---

### 2. **Fixed Scripts** ✅

#### `testing/scripts/market_validation.py`
- ❌ **REMOVED:** Hardcoded fallback `db_password = "ncaam_dev_password"`
- ✅ **ADDED:** Uses `get_db_password()` from unified module
- **Result:** Fails loudly if password missing (no silent fallback)

#### `testing/scripts/fetch_historical_odds.py`
- ❌ **REMOVED:** Custom nested if-statements trying multiple sources
- ✅ **ADDED:** Single call to `get_api_key("odds")`
- **Result:** Cleaner, consistent with all other scripts

#### `testing/scripts/debug_odds_api.py`
- ❌ **REMOVED:** Direct file read that crashed if file missing
- ✅ **ADDED:** Uses unified secrets manager
- **Result:** Better error messages

---

### 3. **New Documentation** ✅

#### `API_KEY_SETUP.md` (14 sections)
Complete guide covering:
- Quick start for each environment (local, Docker, Azure)
- All 3-tier priority levels explained
- 4 setup methods (ensure_secrets.py, env vars, Docker, Key Vault)
- Common scenarios with code examples
- Troubleshooting guide
- Security best practices

#### `.env.example` (150+ lines)
Template with all variables and environment-specific notes:
- All required secrets clearly marked
- Optional secrets documented
- Notes for each deployment scenario
- Copy/paste instructions

---

## 🔄 How It Works Now

### Before (Inconsistent ❌)

```
Script A:
  try env var
  if not: try file
  if not: crash

Script B:
  try file
  if not: try env var
  if not: hardcoded default (SECURITY ISSUE!)

Script C:
  try env var
  if not: try file
  if not: try Docker secret
  if not: hardcoded default
```

### After (Unified ✅)

```
ALL Scripts:
  1. Check env var: THE_ODDS_API_KEY
  2. Check Docker: /run/secrets/odds_api_key
  3. Check file: secrets/odds_api_key.txt
  4. If nothing found: FAIL with helpful error message
     "Here are 3 ways to fix this..."
```

---

## 🚀 Usage Examples

### Setup (One-Time)

```powershell
# Option 1: Local file (easiest for local dev)
python ensure_secrets.py  # Creates DB/Redis passwords
"your_key_here" | Out-File -Path secrets/odds_api_key.txt -NoNewline

# Option 2: Environment variable (works everywhere)
$env:THE_ODDS_API_KEY = "your_key_here"

# Option 3: Azure Key Vault (production)
# See API_KEY_SETUP.md
```

### Run Scripts (No Changes!)

```powershell
# Works the same as before, but now uses unified secret manager
python testing/scripts/fetch_historical_odds.py --season 2025

# Clear errors if something is missing:
# ❌ MISSING REQUIRED SECRET: THE_ODDS_API_KEY
#
# Please set using ONE of these methods:
# 1) $env:THE_ODDS_API_KEY = "your_key"
# 2) /run/secrets/odds_api_key (Docker)
# 3) secrets/odds_api_key.txt (local file)
```

---

## 📊 Matrix: What Works Where

|Environment|Env Var|Docker Secret|Local File|
|-----------|:-----:|:----------:|:--------:|
|Local Dev|✅|❌|✅|
|Docker Container|✅|✅|✅ (mounted)|
|Azure Container Apps|✅|❌|❌|
|GitHub Actions|✅|❌|❌|

**All use same priority order:** Env var > Docker secret > Local file

---

## 🔐 Security Improvements

✅ **Removed:**
- Hardcoded `ncaam_dev_password` fallback (security hole)
- Inconsistent error handling
- Silent failures with unclear messages

✅ **Added:**
- Unified, auditable secrets module
- Clear priority order across all scripts
- Helpful error messages when secrets missing
- Support for all deployment scenarios
- No fallback to weak defaults

✅ **Documented:**
- Exactly how to set secrets for each environment
- Best practices and security guidelines
- Troubleshooting for common issues
- Rotation schedule recommendations

---

## 📝 What You Need to Do

**Nothing!** The changes are backward compatible.

But if you want the full benefit:

1. ✅ **Add to your README:**
   ```markdown
   ## Secrets Setup
   See [API_KEY_SETUP.md](API_KEY_SETUP.md) for complete instructions.
   ```

2. ✅ **Copy `.env.example` to `.env`** (it's in .gitignore):
   ```powershell
   cp .env.example .env
   # Edit .env with your actual values
   ```

3. ✅ **Set THE_ODDS_API_KEY** before running any scripts:
   ```powershell
   $env:THE_ODDS_API_KEY = "your_key_from_https://the-odds-api.com"
   ```

---

## 🧪 Testing

All scripts should work exactly as before, but with better error handling:

```powershell
# This should work (with API key set):
python testing/scripts/fetch_historical_odds.py --season 2025 --job-id test

# This will fail with helpful message:
python testing/scripts/debug_odds_api.py
# ERROR: MISSING REQUIRED SECRET: THE_ODDS_API_KEY
```

---

## 📚 Files Modified/Created

**Created:**
- `testing/scripts/secrets_manager.py` - Unified secrets module
- `API_KEY_SETUP.md` - Complete setup guide
- `.env.example` - Environment variable template

**Modified:**
- `testing/scripts/market_validation.py` - Uses unified module, removed hardcoded password
- `testing/scripts/fetch_historical_odds.py` - Uses unified module, cleaner code
- `testing/scripts/debug_odds_api.py` - Uses unified module, better error handling

---

## 🎓 Key Takeaways

1. **One Way to Load Secrets** - All scripts use `secrets_manager.py`
2. **Same Priority Everywhere** - Env var > Docker secret > Local file
3. **Clear Error Messages** - Tells you exactly what's wrong and how to fix
4. **No More Hardcoded Defaults** - Fails fast instead of silently using wrong values
5. **Works Across All Environments** - Local dev, Docker, Azure, CI/CD

---

## ❓ Questions?

See **[API_KEY_SETUP.md](API_KEY_SETUP.md)** for:
- Step-by-step setup instructions for each environment
- Troubleshooting common issues
- Security best practices
- Detailed priority explanation
