# Single Deployment Channel Strategy

**Date:** December 20, 2025  
**Purpose:** Ensure one source of truth and prevent conflicts across local/GitHub/Azure

---

## 🎯 The Problem

**Without a single deployment channel:**
- ❌ Changes made locally get out of sync with GitHub
- ❌ GitHub changes conflict with local changes
- ❌ Azure deployments use outdated code
- ❌ Multiple sources of truth cause confusion
- ❌ Manual sync errors lead to data loss

---

## ✅ The Solution: Single Source of Truth

### **GitHub is the Single Source of Truth**

```
┌─────────────────────────────────────────────────────────┐
│                    GITHUB (MAIN)                         │
│              Single Source of Truth                      │
│                                                          │
│  ┌──────────────┐         ┌──────────────┐             │
│  │   Local      │         │    Azure     │             │
│  │  (Pull from) │         │ (Deploy from)│             │
│  └──────────────┘         └──────────────┘             │
└─────────────────────────────────────────────────────────┘
```

**Rule:** GitHub `main` branch is ALWAYS the source of truth. Everything else pulls from it.

---

## 📋 Workflow: Push to Feature Branch, Pull from Main

### Standard Workflow (Every Time)

```powershell
# 1. ALWAYS start by pulling latest from GitHub main
git checkout main
git pull origin main

# 2. Create feature branch from latest main
git checkout -b feature/your-feature-name

# 3. Make your changes
# ... edit files ...

# 4. Commit and push to FEATURE BRANCH (not main)
git add .
git commit -m "Descriptive message"
git push origin feature/your-feature-name  # ← Push to feature branch

# 5. Create PR on GitHub (feature branch → main)
# 6. Review and merge PR to main
# 7. Pull from main after merge
git checkout main
git pull origin main  # ← Pull from main
```

**Key Rule:** All pushes go through PRs to main. Then pull from main.

---

## 🔄 Sync Strategy

### Before Starting Work

**ALWAYS run this first:**
```powershell
git checkout main
git pull origin main
git status  # Verify clean working tree
```

**Why:** Ensures you're working from the latest code.

### After Pulling Remote Changes

**If someone else (or you from another machine) made changes:**
```powershell
git pull origin main
# If conflicts occur:
git status  # See what conflicted
# Resolve conflicts manually
git add .
git commit -m "Resolve merge conflicts"
```

### Before Pushing

**ALWAYS verify:**
```powershell
git status          # Check for uncommitted changes
git log --oneline -5  # Verify recent commits
git diff origin/main  # See what's different from remote
```

---

## 🚫 What NOT to Do

### ❌ Don't Work Directly on Main
```powershell
# BAD
git checkout main
# Make changes
git commit -m "Quick fix"
git push
# This bypasses PR workflow and can cause conflicts
```

### ❌ Don't Skip Pulling
```powershell
# BAD
git checkout main
git checkout -b feature/new-feature
# Start working without pulling latest
# You might be working on outdated code
```

### ❌ Don't Force Push
```powershell
# BAD
git push --force origin main
# This can overwrite remote changes
# Branch protection prevents this anyway
```

### ❌ Don't Work on Multiple Machines Without Syncing
```powershell
# BAD
# Machine 1: Make changes, commit locally
# Machine 2: Make different changes, commit locally
# Both push → CONFLICT
```

---

## ✅ Best Practices

### 1. **One Branch Per Feature**
```powershell
# GOOD: One feature = one branch
git checkout -b feature/add-new-metric
# Work, commit, PR, merge, delete branch

# BAD: Multiple features on one branch
git checkout -b feature/multiple-things
# Hard to review, hard to revert
```

### 2. **Pull Before Every Session**
```powershell
# Start of every work session:
git checkout main
git pull origin main
```

### 3. **Commit Often, Push Regularly**
```powershell
# GOOD: Frequent commits
git commit -m "Add function X"
git commit -m "Add function Y"
git push origin feature/my-feature

# BAD: One giant commit at end
# Work for hours...
git commit -m "Everything"
```

### 4. **Verify Before Merging**
```powershell
# Before merging PR:
# 1. Review changes on GitHub
# 2. Check for conflicts
# 3. Verify tests pass (if you have them)
# 4. Merge
```

### 5. **Clean Up After Merge**
```powershell
# After PR is merged:
git checkout main
git pull origin main
git branch -d feature/my-feature  # Delete local branch
# Remote branch deleted automatically by GitHub
```

---

## 🔄 Multi-Machine Workflow

### Working on Multiple Computers

**Scenario:** You work on Desktop and Laptop

**Desktop:**
```powershell
# Start work
git checkout main
git pull origin main
git checkout -b feature/new-feature
# Make changes
git commit -m "Changes from desktop"
git push origin feature/new-feature
```

**Laptop (later):**
```powershell
# ALWAYS pull first
git checkout main
git pull origin main  # Gets desktop changes
git checkout -b feature/another-feature
# Make changes
git commit -m "Changes from laptop"
git push origin feature/another-feature
```

**Key:** Always pull from GitHub before starting work on any machine.

---

## ☁️ Azure Deployment Strategy

### Single Deployment Source

**Azure ALWAYS deploys from GitHub main branch:**

```powershell
# Azure deployment process:
# 1. Pull latest from GitHub main
# 2. Build Docker image
# 3. Deploy to Azure
# 4. Never deploy from local changes directly
```

### Deployment Workflow

**Option 1: Manual Deployment (Current)**
```powershell
# 1. Ensure changes are in GitHub main
git checkout main
git pull origin main
# Verify latest code

# 2. Deploy from GitHub
cd azure
# Read the Odds API key from an environment variable to avoid exposing it in shell history
$oddsApiKey = $env:ODDS_API_KEY
.\deploy.ps1 -Environment prod -OddsApiKey $oddsApiKey
# This pulls from GitHub, builds, deploys
```

**Option 2: Tag-Based Deployment (Recommended)**
```powershell
# 1. Tag release in GitHub
git tag -a v6.3.1 -m "Release v6.3.1"
git push origin v6.3.1

# 2. Deploy specific tag
$oddsApiKey = $env:ODDS_API_KEY
.\deploy.ps1 -Environment prod -ImageTag v6.3.1 -OddsApiKey $oddsApiKey
```

---

## 📊 State Management

### Current State Tracking

**Always know:**
1. **What's in GitHub main?** (source of truth)
2. **What's in your local main?** (should match GitHub)
3. **What's in your feature branch?** (your work)
4. **What's deployed to Azure?** (production state)

### Commands to Check State

```powershell
# Check GitHub main
git fetch origin
git log origin/main --oneline -5

# Check local main
git checkout main
git log --oneline -5

# Check if local matches remote
git status
# Should say: "Your branch is up to date with 'origin/main'"

# Check what's deployed (Azure)
# Check Azure Container App image tag
az containerapp show -n ncaam-prod-prediction -g ncaam-prod-rg --query "properties.template.containers[0].image"
```

---

## 🔍 Conflict Prevention

### Before Making Changes

**Check for conflicts:**
```powershell
# 1. Pull latest
git checkout main
git pull origin main

# 2. Check what's new on remote
git log --oneline HEAD..origin/main
# If empty, you're up to date

# 3. Check for uncommitted changes
git status
# Should be clean
```

### During Development

**If working on same files as others:**
```powershell
# Pull latest main periodically
git checkout main
git pull origin main
git checkout feature/your-branch
git merge main  # or git rebase main
# Resolve conflicts if any
```

### After Conflicts

**Resolve properly:**
```powershell
# 1. See conflicts
git status

# 2. Open conflicted files
# Look for <<<<<<< HEAD markers

# 3. Resolve manually
# Keep what you need, remove conflict markers

# 4. Mark as resolved
git add <resolved-file>

# 5. Complete merge
git commit -m "Resolve merge conflicts"
```

---

## 🎯 Deployment Checklist

### Before Any Deployment

- [ ] All changes are in GitHub main branch
- [ ] Local main is synced with GitHub (`git pull origin main`)
- [ ] No uncommitted local changes
- [ ] PRs are merged and reviewed
- [ ] Tests pass (if you have them)
- [ ] Documentation updated
- [ ] Version/tag created (if using tags)

### Deployment Process

1. **Verify GitHub main has latest:**
   ```powershell
   git checkout main
   git pull origin main
   git log --oneline -5
   ```

2. **Deploy from GitHub:**
   ```powershell
   cd azure
   # Read the Odds API key from an environment variable (set via CI/CD secret store or local environment)
   $oddsApiKey = $env:ODDS_API_KEY
   .\deploy.ps1 -Environment prod -OddsApiKey $oddsApiKey
   ```

3. **Verify deployment:**
   ```powershell
   # Check Azure Container App
   az containerapp show -n ncaam-prod-prediction -g ncaam-prod-rg
   ```

---

## 📝 Daily Workflow Summary

### Start of Day
```powershell
git checkout main
git pull origin main
git status  # Verify clean
```

### During Work
```powershell
git checkout -b feature/your-work
# Make changes
git add .
git commit -m "Descriptive message"
git push origin feature/your-work
# Create PR, review, merge
```

### End of Day
```powershell
git checkout main
git pull origin main  # Get any merged PRs
git branch -d feature/your-work  # Clean up
```

---

## 🚨 Emergency Procedures

### If Local and Remote Diverge

**Scenario:** Local main has changes, remote main has different changes

```powershell
# 1. Save your local work
git stash  # Saves uncommitted changes

# 2. Pull remote
git pull origin main

# 3. Apply your changes
git stash pop  # Reapplies your changes

# 4. Resolve conflicts if any
# Edit files, git add, git commit
```

### If You Accidentally Committed to Main

**Scenario:** You committed directly to main (shouldn't happen with protection)

```powershell
# 1. Create feature branch from current state
git checkout -b feature/fix-accidental-commit

# 2. Reset main to match remote
git checkout main
git reset --hard origin/main

# 3. Work on feature branch
git checkout feature/fix-accidental-commit
# Make changes, PR, merge
```

---

## ✅ Summary: Single Deployment Channel Rules

1. **GitHub main is ALWAYS the source of truth**
2. **Always pull before starting work**
3. **Never work directly on main** (use feature branches)
4. **Always use PRs** (enforced by branch protection)
5. **Deploy only from GitHub main**
6. **Sync regularly** (pull before every session)
7. **One feature = one branch = one PR**
8. **Clean up after merge** (delete branches)

---

## 🎯 Quick Reference

### Daily Commands
```powershell
# Start work
git checkout main; git pull origin main

# Create feature
git checkout -b feature/name

# Work and commit
git add .; git commit -m "Message"

# Push and PR
git push origin feature/name

# After merge
git checkout main; git pull origin main
```

### State Check
```powershell
# Am I up to date?
git status
git log HEAD..origin/main

# What's different?
git diff origin/main
```

---

**Remember:** GitHub main = Source of Truth. Everything else pulls from it.

