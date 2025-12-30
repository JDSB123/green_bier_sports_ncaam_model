# Pull Request Workflow - Version Control Best Practices

**Date:** December 20, 2025  
**Purpose:** Establish proper version control with PR-based workflow

---

## 🎯 Why PR-Based Workflow?

### Problems with Direct Commits to Main
- ❌ No review process (even self-review)
- ❌ Hard to track what changed and why
- ❌ Difficult to revert specific changes
- ❌ No documentation of decision-making
- ❌ Risk of breaking main branch
- ❌ No separation between work-in-progress and production

### Benefits of PR Workflow
- ✅ **Version control:** Clear history of what changed
- ✅ **Review process:** Self-review catches mistakes
- ✅ **Documentation:** PR descriptions explain changes
- ✅ **Safety:** Test changes before merging to main
- ✅ **Rollback:** Easy to revert entire PR if needed
- ✅ **Organization:** Separate branches for different work

---

## 📋 Branch Strategy

### Main Branches
- **`main`** - Production-ready code (protected)
- **`develop`** - Integration branch (optional, for larger projects)

### Feature Branches
- **`feature/{description}`** - New features
- **`fix/{description}`** - Bug fixes
- **`docs/{description}`** - Documentation updates
- **`refactor/{description}`** - Code refactoring
- **`cleanup/{description}`** - Cleanup work

### Naming Examples
```
feature/new-prediction-model
fix/odds-api-rate-limiting
docs/update-deployment-guide
refactor/predictor-logic
cleanup/remove-unused-code
```

---

## 🔄 Standard PR Workflow

### Step 1: Create Feature Branch
```powershell
# Always start from latest main
git checkout main
git pull origin main

# Create and switch to feature branch
git checkout -b feature/your-feature-name
```

### Step 2: Make Changes
```powershell
# Make your changes
# Edit files, test locally, etc.

# Bump the single source of truth when the release version changes
# (example shows a patch bump)
$currentVersion = Get-Content VERSION
Set-Content VERSION -Value "<NEW_VERSION>"

# Commit changes (use descriptive messages)
git add .
git commit -m "Add new prediction feature"
```

### Step 3: Push Branch
```powershell
# Push branch to remote
git push origin feature/your-feature-name
```

### Step 4: Create Pull Request
- Go to GitHub repository
- Click "New Pull Request"
- Select: `feature/your-feature-name` → `main`
- Fill out PR template (see below)
- Create PR

### Step 5: Review & Merge
- Review your own changes
- Check PR description matches changes
- Test if needed
- Merge PR (squash merge recommended)
- Delete branch after merge

---

## 📝 PR Template

### Required Information
```markdown
## Description
Brief description of what this PR does

## Type of Change
- [ ] Feature (new functionality)
- [ ] Bug fix
- [ ] Documentation
- [ ] Refactoring
- [ ] Cleanup

## Changes Made
- Change 1
- Change 2
- Change 3

## Testing
- [ ] Tested locally
- [ ] Manual testing completed
- [ ] No breaking changes

## Related Issues
- Closes #issue-number (if applicable)

## Checklist
- [ ] Code follows project standards
- [ ] Documentation updated (if needed)
- [ ] No hardcoded secrets/passwords
- [ ] Commits are descriptive
```

---

## 🛡️ Branch Protection (Recommended)

### Set Up Branch Protection Rules

**In GitHub:**
1. Go to Settings → Branches
2. Add rule for `main` branch
3. Enable:
   - ✅ Require pull request reviews (even if just self-review)
   - ✅ Require status checks to pass (if you add CI/CD)
   - ✅ Require branches to be up to date
   - ✅ Include administrators (optional)

**This prevents:**
- Direct pushes to main
- Merging without PR
- Accidental deletions

---

## 🔍 Review Process

### Self-Review Checklist
Before merging your PR, review:

1. **Code Quality**
   - [ ] Code is clean and readable
   - [ ] No commented-out code
   - [ ] No debug statements
   - [ ] Follows project conventions

2. **Functionality**
   - [ ] Changes work as intended
   - [ ] No breaking changes (or documented)
   - [ ] Error handling is appropriate

3. **Documentation**
   - [ ] PR description is clear
   - [ ] Code comments where needed
   - [ ] README/docs updated if needed

4. **Security**
   - [ ] No hardcoded secrets
   - [ ] No API keys in code
   - [ ] Proper secret management

5. **Testing**
   - [ ] Tested locally
   - [ ] Manual testing completed
   - [ ] Edge cases considered

---

## 📊 Example Workflow

### Scenario: Adding New Feature

```powershell
# 1. Start from main
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/enhanced-predictions

# 3. Make changes
# ... edit files ...

# 4. Commit
git add .
git commit -m "Add enhanced prediction model with new metrics"

# 5. Push
git push origin feature/enhanced-predictions

# 6. Create PR on GitHub
# - Title: "Add enhanced prediction model"
# - Description: Use PR template
# - Review your changes
# - Merge when ready

# 7. After merge, clean up
git checkout main
git pull origin main
git branch -d feature/enhanced-predictions  # Delete local branch
```

---

## 🚫 What NOT to Do

### ❌ Don't Commit Directly to Main
```powershell
# BAD
git checkout main
git add .
git commit -m "Quick fix"
git push
```

### ❌ Don't Skip PR Review
```powershell
# BAD - Merging without reviewing
# Always review your PR before merging
```

### ❌ Don't Use Vague Commit Messages
```powershell
# BAD
git commit -m "fix stuff"

# GOOD
git commit -m "Fix odds API rate limiting by adding exponential backoff"
```

### ❌ Don't Mix Unrelated Changes
```powershell
# BAD - One PR with multiple unrelated changes
# GOOD - Separate PRs for separate concerns
```

---

## ✅ Best Practices

### 1. Keep Branches Small
- One feature/fix per branch
- Easier to review
- Easier to revert if needed

### 2. Regular Commits
- Commit often with descriptive messages
- Makes history easier to follow
- Easier to identify issues

### 3. Update from Main Regularly
```powershell
# While working on feature branch
git checkout feature/your-branch
git merge main  # or git rebase main
# Resolve conflicts if any
```

### 4. Clean Up After Merge
```powershell
# Delete local branch
git branch -d feature/your-branch

# Delete remote branch (usually done automatically)
git push origin --delete feature/your-branch
```

### 5. Use Descriptive PR Titles
```markdown
# BAD
"Updates"

# GOOD
"Add event-driven polling to odds ingestion service"
```

---

## 🔄 Migration Plan

### Current State → PR Workflow

**Step 1: Protect Main Branch**
- Set up branch protection rules
- Prevent direct pushes

**Step 2: Create Feature Branch for Next Work**
```powershell
git checkout -b feature/next-feature-name
```

**Step 3: Use PR Workflow Going Forward**
- All changes via PR
- Review before merge
- Document decisions

**Step 4: Clean Up Old Direct Commits**
- Keep existing commits (they're history)
- Just use PR workflow from now on

---

## ?? Version Discipline

- **Single source:** Update the root VERSION file whenever you bump semantic versions.
- **Deploys:** Run `azure/deploy.ps1` (it reads `VERSION`, builds/pushes images, and updates Azure Container Apps).
- **Process:** Bump VERSION, run tests, open a PR, merge, and deploy.

---

## 📚 Quick Reference

### Daily Workflow
```powershell
# Start work
git checkout main
git pull origin main
git checkout -b feature/my-work

# Make changes, commit
git add .
git commit -m "Descriptive message"
git push origin feature/my-work

# Create PR on GitHub, review, merge

# After merge
git checkout main
git pull origin main
git branch -d feature/my-work
```

### Emergency Hotfix
```powershell
# For urgent fixes
git checkout main
git checkout -b hotfix/critical-bug
# Fix, commit, push, PR, merge quickly
```

---

## 🎯 Summary

**Always:**
1. ✅ Create feature branch from main
2. ✅ Make changes and commit
3. ✅ Push branch
4. ✅ Create PR
5. ✅ Review your changes
6. ✅ Merge PR
7. ✅ Delete branch

**Never:**
1. ❌ Commit directly to main
2. ❌ Skip PR review
3. ❌ Mix unrelated changes
4. ❌ Use vague commit messages

---

**This workflow gives you:**
- ✅ Better version control
- ✅ Clear change history
- ✅ Safety (can revert easily)
- ✅ Documentation (PR descriptions)
- ✅ Professional development process


