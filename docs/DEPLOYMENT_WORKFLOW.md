# Deployment Workflow - Main Branch Strategy

**Date:** December 20, 2025  
**Purpose:** Clear workflow for all pushes going through PRs to main, then pulling from main

---

## 🎯 The Workflow

```
┌─────────────────────────────────────────────────────────┐
│                    WORKFLOW                              │
│                                                          │
│  1. Feature Branch → Push to GitHub                     │
│  2. Create PR → Merge to Main                           │
│  3. Main Branch (GitHub) = Source of Truth              │
│  4. Pull from Main (Local/Azure)                        │
└─────────────────────────────────────────────────────────┘
```

**Key Rule:** All pushes go through PRs to main. Then pull from main.

---

## 📋 Step-by-Step Workflow

### Step 1: Create Feature Branch (Local)

```powershell
# Start from latest main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name
```

### Step 2: Make Changes and Push to Feature Branch

```powershell
# Make your changes
# ... edit files ...

# Commit
git add .
git commit -m "Descriptive commit message"

# Push to feature branch (NOT main)
git push origin feature/your-feature-name
```

**Important:** You're pushing to the feature branch, not main.

### Step 3: Create PR to Main

- Go to GitHub
- Create Pull Request: `feature/your-feature-name` → `main`
- Review your changes
- Merge PR

**Result:** Changes are now in GitHub `main` branch.

### Step 4: Pull from Main (Local)

```powershell
# Switch to main
git checkout main

# Pull latest from GitHub main
git pull origin main

# Now your local main matches GitHub main
```

### Step 5: Clean Up

```powershell
# Delete local feature branch
git branch -d feature/your-feature-name

# Remote branch deleted automatically by GitHub after PR merge
```

---

## 🔄 Complete Example

### Scenario: Adding a New Feature

```powershell
# 1. Start from main (pull latest)
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/add-new-metric

# 3. Make changes
# Edit files, add code, etc.
git add .
git commit -m "Add new prediction metric"

# 4. Push to feature branch (NOT main)
git push origin feature/add-new-metric

# 5. Create PR on GitHub
# - Go to GitHub
# - Create PR: feature/add-new-metric → main
# - Review, merge

# 6. After PR is merged, pull from main
git checkout main
git pull origin main

# 7. Clean up
git branch -d feature/add-new-metric
```

---

## 🚫 What NOT to Do

### ❌ Don't Push Directly to Main

```powershell
# BAD - This is blocked by branch protection
git checkout main
git commit -m "Quick fix"
git push origin main
# ERROR: Protected branch update failed
```

### ❌ Don't Skip the PR Step

```powershell
# BAD - Don't merge locally and push
git checkout main
git merge feature/my-branch
git push origin main
# This bypasses PR review and is blocked
```

### ❌ Don't Work on Main Directly

```powershell
# BAD
git checkout main
# Make changes directly
git commit -m "Changes"
# Can't push - branch is protected
```

---

## ✅ Correct Flow Summary

### All Changes Follow This Path:

```
Local Feature Branch
    ↓
Push to GitHub Feature Branch
    ↓
Create PR (Feature → Main)
    ↓
Merge PR to Main (GitHub)
    ↓
Pull from Main (Local/Azure)
```

### The Rule:

1. **Push:** Always push to feature branches
2. **PR:** All changes merge to main via PR
3. **Pull:** Always pull from main after PR merge

---

## 🔍 Visual Workflow

```
┌─────────────────────────────────────────────────────────┐
│                    LOCAL                                │
│                                                          │
│  main (pulls from GitHub)                               │
│    ↑                                                    │
│    │ git pull origin main                              │
│    │                                                    │
│  feature/xyz (pushes to GitHub)                        │
│    ↓                                                    │
│    │ git push origin feature/xyz                       │
└────┼────────────────────────────────────────────────────┘
     │
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                    GITHUB                               │
│                                                          │
│  feature/xyz branch                                     │
│    ↓                                                    │
│    │ Create PR                                          │
│    ↓                                                    │
│  main branch (Source of Truth)                          │
│    ↑                                                    │
│    │ PR merged                                          │
└────┼────────────────────────────────────────────────────┘
     │
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                    LOCAL/AZURE                          │
│                                                          │
│  Pull from main                                         │
│    ↑                                                    │
│    │ git pull origin main                              │
│    │                                                    │
│  Local main / Azure deployment                          │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 Daily Workflow

### Morning: Sync with Main

```powershell
# Always start by pulling from main
git checkout main
git pull origin main
```

### During Work: Feature Branch

```powershell
# Create feature branch
git checkout -b feature/my-work

# Make changes, commit
git add .
git commit -m "My changes"

# Push to feature branch
git push origin feature/my-work

# Create PR on GitHub
# Review, merge PR
```

### After PR Merge: Pull from Main

```powershell
# Switch to main
git checkout main

# Pull latest (includes your merged PR)
git pull origin main

# Clean up
git branch -d feature/my-work
```

---

## ☁️ Azure Deployment

### Azure Always Pulls from GitHub Main

```powershell
# Azure deployment process:
# 1. Pulls from GitHub main (not local)
# 2. Builds Docker image
# 3. Deploys to Azure

cd azure
.\deploy.ps1 -Environment prod -OddsApiKey "YOUR_KEY"
# This deploys from GitHub main, not local
```

**Key:** Azure never deploys from local changes. Always from GitHub main.

---

## 🔄 Multi-Machine Workflow

### Working on Multiple Computers

**Desktop:**
```powershell
# 1. Pull from main
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/desktop-work

# 3. Work, commit, push
git push origin feature/desktop-work

# 4. Create PR, merge
```

**Laptop (later):**
```powershell
# 1. Pull from main (gets desktop changes)
git checkout main
git pull origin main  # ← Gets desktop PR that was merged

# 2. Create new feature branch
git checkout -b feature/laptop-work

# 3. Work, commit, push
git push origin feature/laptop-work

# 4. Create PR, merge
```

**Key:** Always pull from main first to get latest changes.

---

## ✅ Summary: The Rule

### All Pushes → Feature Branches → PR → Main → Pull from Main

1. **Push:** Always push to feature branches (never directly to main)
2. **PR:** All changes merge to main via Pull Request
3. **Main:** GitHub main is the source of truth
4. **Pull:** Always pull from main after PR merge

### Commands

```powershell
# Push to feature branch
git push origin feature/your-branch

# Pull from main
git pull origin main
```

---

## 🎯 Quick Reference

### Start Work
```powershell
git checkout main
git pull origin main
git checkout -b feature/name
```

### Push Changes
```powershell
git push origin feature/name  # ← Push to feature branch
```

### After PR Merge
```powershell
git checkout main
git pull origin main  # ← Pull from main
```

---

**Remember:** Push to feature branches. Pull from main.

