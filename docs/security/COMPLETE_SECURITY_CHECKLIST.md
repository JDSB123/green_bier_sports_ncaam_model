# Complete Security Checklist - API Keys & GitHub

**Date:** January 9, 2026
**Goal:** Eliminate API key issues across all environments
**Status:** ✅ IMPLEMENTATION COMPLETE | ⏳ GITHUB SETTINGS PENDING

---

## ✅ Completed: Code & Secrets Management

### What Was Fixed

| Issue | Before | After | Status |
|-------|--------|-------|--------|
| Hardcoded password fallback | ❌ `db_password = "ncaam_dev_password"` | ✅ Fails with clear error | FIXED |
| Inconsistent API key loading | ❌ 3 different patterns across scripts | ✅ Unified `secrets_manager.py` | FIXED |
| Missing env var handling | ❌ Some scripts crash, some use fallback | ✅ All use same 3-tier priority | FIXED |
| Unclear error messages | ❌ "No API key found" | ✅ Shows 3 ways to fix it | FIXED |

### New Files Created

1. **`testing/scripts/secrets_manager.py`**
   - Unified secrets module with 3-tier priority
   - Priority: Env var > Docker secret > Local secrets file
   - Clear error messages for missing secrets

2. **`API_KEY_SETUP.md`** (14 sections, 300+ lines)
   - Complete setup guide for all environments
   - 4 setup methods (quick, env vars, Docker, Key Vault)
   - Troubleshooting guide
   - Security best practices

3. **`.env.example`** (150+ lines)
   - Template for all environment variables
   - Clear documentation for each variable
   - Environment-specific notes

4. **`SECRETS_UNIFICATION_SUMMARY.md`**
   - High-level overview of changes
   - Before/after comparison
   - Usage examples

### Scripts Updated

1. **`testing/scripts/market_validation.py`**
   - ❌ REMOVED: Hardcoded `ncaam_dev_password` fallback
   - ✅ ADDED: Uses `get_db_password()` from unified module

2. **`testing/scripts/fetch_historical_odds.py`**
   - ❌ REMOVED: Custom nested if-statements
   - ✅ ADDED: Single call to `get_api_key("odds")`

3. **`testing/scripts/debug_odds_api.py`**
   - ❌ REMOVED: Direct file read (crashes if missing)
   - ✅ ADDED: Uses unified secrets manager

---

## ⏳ TODO: GitHub Repository Settings

These settings should be applied to both:
- `JDSB123/green_bier_sports_ncaam_model` (main prediction model)
- `JDSB123/ncaam-historical-data` (deprecated data repository)

### 1. Branch Protection on `main`

**Why:** Prevent accidental commits to main, enforce PR workflow

**Steps:**
1. Go to repository **Settings** → **Branches**
2. Click **Add rule**
3. Branch name: `main`
4. Configure:
   - ✅ Require a pull request before merging
     - ✅ Require 1 approval
     - ✅ Dismiss stale approvals on new commits
   - ✅ Require status checks to pass before merging
     - (Add CI/CD checks if available later)
   - ✅ Require branches to be up to date before merging
   - ✅ Require conversation resolution before merging
   - ✅ Include administrators
   - ✅ Restrict who can force push

**Result:** Direct commits to main blocked ✅

---

### 2. Repository Secrets

**Why:** Store sensitive values securely, access in workflows

**Steps:**
1. Go to repository **Settings** → **Secrets and variables** → **Actions**
2. Create these secrets:

#### For `green_bier_sports_ncaam_model`:

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `ODDS_API_KEY` | Your actual API key | CI/CD testing, deployments |
| `AZURE_CREDENTIALS` | Azure service principal JSON | Deploy to Azure |
| `HISTORICAL_DATA_PAT` | Deprecated | Historical data repo no longer required |

**Create ODDS_API_KEY:**
```
Name: ODDS_API_KEY
Value: your_actual_key_from_https://the-odds-api.com
```

**Create HISTORICAL_DATA_PAT:**
```
Name: HISTORICAL_DATA_PAT
Value: Deprecated (historical data repo no longer required)
Scopes: repo (read-only)
Expiration: 90 days
```

**Create AZURE_CREDENTIALS** (if not exists):
```
Name: AZURE_CREDENTIALS
Value: Azure Service Principal JSON
Format: {"clientId":"...","clientSecret":"...","subscriptionId":"...","tenantId":"..."}
```

#### For `ncaam-historical-data` (deprecated):

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `GITHUB_TOKEN` | (Auto-provided) | Workflows, GitHub API access |

**Note:** This repo doesn't need API keys since it only stores data

---

### 3. Dependabot Security Updates

**Why:** Automatically fix vulnerable dependencies

**Steps:**
1. Go to **Settings** → **Code security and analysis**
2. Enable:
   - ✅ Dependabot alerts
   - ✅ Dependabot security updates
   - ✅ Dependency graph

**Result:** Auto-fixes security vulnerabilities ✅

---

### 4. Security Policy

**Why:** Tell users how to report security vulnerabilities

**Steps:**
1. Create `SECURITY.md` in repo root:

```markdown
# Security Policy

## Reporting Vulnerabilities

**DO NOT** open public issues for security vulnerabilities.

Instead, email: your_email@example.com with:
- Vulnerability description
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will:
- Acknowledge receipt within 24 hours
- Provide update within 72 hours
- Credit you in release notes (optional)
```

---

### 5. Code Owners (Optional)

**Why:** Require specific people to review certain files

**Steps:**
1. Create `.github/CODEOWNERS`:

```
# Protect sensitive files
secrets/ @yourname
*.key @yourname

# Protect deployment configs
azure/** @yourname
docker-compose.yml @yourname

# Protect model code
services/prediction-service-python/** @yourname

# Data quality
testing/scripts/canonical_data_validator.py @yourname
testing/scripts/dual_canonicalization_audit.py @yourname
```

---

### 6. Environment Secrets (For Deployments)

**Why:** Different secrets for different environments (dev, staging, production)

**Steps:**
1. Go to **Settings** → **Environments**
2. Create 3 environments:
   - `development`
   - `staging`
   - `production`

3. For each environment, add secrets:
   - `ODDS_API_KEY` (environment-specific)
   - `DB_PASSWORD` (environment-specific)
   - `AZURE_SUBSCRIPTION_ID`

**Usage in workflows:**
```yaml
jobs:
  deploy:
    environment: production
    steps:
      - name: Deploy
        env:
          ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}
        run: ./deploy.sh
```

---

### 7. Secret Scanning (GitHub Advanced Security)

**Why:** Auto-detect if secrets are accidentally committed

**Steps:**
1. Enable in **Settings** → **Code security and analysis**
2. ✅ Enable secret scanning
3. ✅ Enable push protection

**Result:** Blocks commits with exposed API keys ✅

---

## 🔍 Verification Checklist

After applying GitHub settings, verify:

### Branch Protection
- [ ] Try `git push origin main` → Should fail with "Protected branch update failed"
- [ ] Create feature branch, make PR → Should allow merge after review

### Secrets
- [ ] Go to **Settings** → **Secrets** → See your secrets listed
- [ ] Try to view secret value → Can't see it (encrypted)
- [ ] Workflow uses `${{ secrets.ODDS_API_KEY }}` → Works in logs (masked)

### Dependabot
- [ ] Go to **Security** → **Dependabot** → See alerts
- [ ] Check **Pull requests** → See auto-created security PRs

---

## 📋 Setup Tracking

### Code Changes (DONE ✅)
- [x] Create `secrets_manager.py`
- [x] Fix `market_validation.py` hardcoded password
- [x] Update `fetch_historical_odds.py`
- [x] Update `debug_odds_api.py`
- [x] Create `API_KEY_SETUP.md`
- [x] Create `.env.example`

### GitHub Configuration (TODO)
- [ ] **green_bier_sports_ncaam_model** - Branch protection
- [ ] **green_bier_sports_ncaam_model** - Repository secrets
- [ ] **ncaam-historical-data** - Branch protection (deprecated)
- [ ] **ncaam-historical-data** - Repository secrets (deprecated)
- [ ] **Both repos** - Dependabot setup
- [ ] **Both repos** - Create SECURITY.md
- [ ] **green_bier_sports_ncaam_model** - Create .github/CODEOWNERS

### Secrets Setup (ALREADY CONFIGURED)
- [x] `secrets/db_password.txt` - Created by `ensure_secrets.py`
- [x] `secrets/redis_password.txt` - Created by `ensure_secrets.py`
- [x] `secrets/odds_api_key.txt` - Manual setup
- [x] Environment variable support for Azure deployments

---

## 🚀 How to Implement

### Immediate (This Session)
1. ✅ Code changes already applied
2. ✅ Documentation already created

### Next Session (15 minutes per repo)
1. Apply branch protection (Steps 1)
2. Create repository secrets (Step 2)
3. Enable Dependabot (Step 3)
4. Create SECURITY.md (Step 4)

### Optional (When You Have Time)
1. Set up Code Owners (Step 5)
2. Create deployment environments (Step 6)
3. Enable secret scanning (Step 7)

---

## 📊 Security Impact

### Before This Work

| Aspect | Status | Risk |
|--------|--------|------|
| Hardcoded defaults | ❌ Yes | 🔴 HIGH - Silent security fallback |
| Inconsistent secrets | ❌ Yes | 🔴 HIGH - Confusion, errors |
| No branch protection | ❌ No | 🟠 MEDIUM - Direct commits possible |
| No secret scanning | ❌ No | 🟠 MEDIUM - Committed secrets undetected |
| No Dependabot | ❌ No | 🟡 LOW - Vulnerable deps not updated |

### After This Work

| Aspect | Status | Risk |
|--------|--------|------|
| Hardcoded defaults | ✅ Removed | 🟢 LOW - Fails loudly |
| Inconsistent secrets | ✅ Unified | 🟢 LOW - Single pattern |
| Branch protection | ⏳ (Configure) | 🟢 LOW - Once set |
| Secret scanning | ⏳ (Configure) | 🟢 LOW - Once set |
| Dependabot | ⏳ (Configure) | 🟢 LOW - Once set |

---

## 💡 Key Principles

✅ **Fail Loudly** - Missing secrets = clear error, not silent fallback
✅ **Single Pattern** - All scripts use same secrets manager
✅ **Multi-Environment** - Works locally, Docker, Azure, CI/CD
✅ **Well Documented** - Every step explained in API_KEY_SETUP.md
✅ **Audit Trail** - GitHub logs show which secrets were used

---

## 📞 Questions?

**For code changes:**
→ See `SECRETS_UNIFICATION_SUMMARY.md`

**For setup instructions:**
→ See `API_KEY_SETUP.md`

**For GitHub settings:**
→ See this document (sections 1-7 above)

**For environment variables:**
→ See `.env.example`

---

## 🎯 Next Steps

1. **Run one of your scripts** to verify unified secrets work:
   ```powershell
   $env:THE_ODDS_API_KEY = "your_key_here"
   python testing/scripts/fetch_historical_odds.py --season 2025 --job-id test
   ```

2. **Apply GitHub settings** to both repos (15 min each):
   - Branch protection (Step 1)
   - Repository secrets (Step 2)
   - Dependabot (Step 3)

3. **Document in your team** how to set secrets (use `API_KEY_SETUP.md`)

Done! 🎉
