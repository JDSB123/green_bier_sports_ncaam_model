# Branch Protection Setup Guide

**Date:** December 20, 2025  
**Purpose:** Protect main branch and enforce PR workflow

---

## 🛡️ Setting Up Branch Protection

### Step 1: Navigate to Branch Settings

1. Go to your GitHub repository
2. Click **Settings** (top right)
3. Click **Branches** (left sidebar)

### Step 2: Add Branch Protection Rule

1. Under "Branch protection rules", click **Add rule**
2. In "Branch name pattern", enter: `main`
3. Configure the following settings:

### Step 3: Enable Protection Rules

**Required Settings:**
- ✅ **Require a pull request before merging**
  - ✅ Require approvals: `1` (self-review is fine)
  - ✅ Dismiss stale pull request approvals when new commits are pushed
  - ✅ Require review from Code Owners (optional)

- ✅ **Require status checks to pass before merging** (if you add CI/CD later)
  - Leave empty for now (no CI/CD configured)

- ✅ **Require branches to be up to date before merging**
  - ✅ This ensures your branch has latest main

- ✅ **Require conversation resolution before merging**
  - Ensures all PR comments are addressed

**Optional but Recommended:**
- ✅ **Include administrators**
  - Even admins must use PRs (prevents accidental direct commits)

- ✅ **Do not allow bypassing the above settings**
  - Prevents circumventing protection rules

**Restrictions:**
- ❌ **Do NOT enable:** "Restrict who can push to matching branches"
  - This would prevent you from pushing feature branches

### Step 4: Save Rule

Click **Create** to save the branch protection rule.

---

## ✅ Verification

After setting up branch protection:

1. **Try to push directly to main** (should fail):
   ```powershell
   git checkout main
   # Make a small change
   echo "# test" >> test.md
   git add test.md
   git commit -m "Test direct push"
   git push origin main
   # Should fail with: "remote: error: GH006: Protected branch update failed"
   ```

2. **Verify PR workflow works**:
   - Create feature branch
   - Make changes
   - Create PR
   - PR should be mergeable (after review)

---

## 🔄 Workflow After Protection

Once branch protection is enabled:

### ✅ Allowed:
- Creating feature branches
- Pushing to feature branches
- Creating PRs from feature branches
- Merging PRs (after review)

### ❌ Blocked:
- Direct pushes to main
- Force pushes to main
- Deleting main branch
- Merging without PR

---

## 📋 Quick Reference

**Branch Protection URL:**
```
https://github.com/JDSB123/green_bier_sports_ncaam_model/settings/branches
```

**Settings to Enable:**
1. Require pull request before merging
2. Require branches to be up to date
3. Include administrators (optional)
4. Require conversation resolution

---

## 🎯 Result

After setup:
- ✅ Main branch is protected
- ✅ All changes must go through PRs
- ✅ Better version control
- ✅ Clear change history
- ✅ Safer development process

---

**Note:** You can still work on feature branches normally. Only `main` is protected.

