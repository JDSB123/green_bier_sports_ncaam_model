# Quick Setup: Branch Protection

**Fastest way to set up branch protection for main branch**

---

## Option 1: GitHub CLI (Automated) ⚡

If you have GitHub CLI installed:

```powershell
# 1. Authenticate (if not already)
gh auth login

# 2. Run the setup script
.\scripts\setup-branch-protection.ps1
```

**Or manually with gh CLI:**
```powershell
gh api repos/JDSB123/green_bier_sports_ncaam_model/branches/main/protection \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  -f required_pull_request_reviews[required_approving_review_count]=1 \
  -f required_pull_request_reviews[dismiss_stale_reviews]=true \
  -f enforce_admins=true \
  -f required_conversation_resolution=true \
  -f allow_force_pushes=false \
  -f allow_deletions=false
```

---

## Option 2: GitHub Web UI (Manual) 🌐

**Direct link:** https://github.com/JDSB123/green_bier_sports_ncaam_model/settings/branches

### Steps:
1. Click **"Add rule"**
2. Branch name pattern: `main`
3. Enable these settings:
   - ✅ **Require a pull request before merging**
     - ✅ Require approvals: `1`
     - ✅ Dismiss stale pull request approvals when new commits are pushed
   - ✅ **Require conversation resolution before merging**
   - ✅ **Include administrators**
   - ✅ **Do not allow force pushes**
   - ✅ **Do not allow deletions**
4. Click **"Create"**

**Done!** Main branch is now protected.

---

## Option 3: PowerShell Script

Run the provided script:
```powershell
.\scripts\setup-branch-protection.ps1
```

---

## Verify Protection

After setup, try to push directly to main (should fail):
```powershell
git checkout main
echo "# test" >> test.md
git add test.md
git commit -m "Test direct push"
git push origin main
# Should fail: "Protected branch update failed"
```

---

## What This Does

- ✅ Prevents direct pushes to main
- ✅ Requires PRs for all changes
- ✅ Requires at least 1 approval (self-review is fine)
- ✅ Requires conversation resolution
- ✅ Prevents force pushes
- ✅ Prevents branch deletion

**Result:** All changes must go through PR workflow!

