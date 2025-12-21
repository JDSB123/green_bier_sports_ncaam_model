# Development Workflow - Single Source of Truth

**Date:** December 21, 2025  
**Purpose:** Clarify where development happens vs where deployments run

---

## 🎯 Single Source of Truth

**GitHub `main` branch is the SINGLE source of truth for all code.**

```
┌─────────────────────────────────────────────────────────┐
│              WHERE DEVELOPMENT HAPPENS                   │
│                                                          │
│  ┌──────────────────────────────────────────────┐      │
│  │  LOCAL (Your Computer / IDE)                 │      │
│  │  • Edit code                                 │      │
│  │  • Make changes                              │      │
│  │  • Test locally                              │      │
│  │  • Commit changes                            │      │
│  └──────────────┬───────────────────────────────┘      │
│                 │                                        │
│                 │ git push (to feature branch)          │
│                 ▼                                        │
│  ┌──────────────────────────────────────────────┐      │
│  │  GITHUB (main branch = Source of Truth)      │      │
│  │  • All code versions                         │      │
│  │  • All history                               │      │
│  │  • Pull Requests → Merge to main             │      │
│  └──────────────┬───────────────────────────────┘      │
│                 │                                        │
│                 │ Azure pulls FROM GitHub main          │
│                 ▼                                        │
│  ┌──────────────────────────────────────────────┐      │
│  │  AZURE (Production Deployment)               │      │
│  │  • Runs the application                      │      │
│  │  • Pulls code FROM GitHub main               │      │
│  │  • Deploys and runs containers               │      │
│  └──────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

---

## ❌ What Azure is NOT

- ❌ **Azure is NOT where you edit code**
- ❌ **Azure is NOT where you develop**
- ❌ **Azure is NOT where you make changes**
- ❌ **Azure is NOT the source of truth**

---

## ✅ What Azure IS

- ✅ **Azure is where your APPLICATION RUNS** (production environment)
- ✅ **Azure pulls code FROM GitHub main** to deploy
- ✅ **Azure builds Docker images FROM GitHub main**
- ✅ **Azure runs the containers** with your code

---

## 📋 Complete Workflow

### Step 1: Development (LOCAL)

**This happens on YOUR computer:**

```powershell
# 1. Pull latest from GitHub main
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/my-change

# 3. Edit code in your IDE
# - Open files
# - Make changes
# - Test locally with Docker Compose

# 4. Commit changes
git add .
git commit -m "My change description"

# 5. Push to GitHub (feature branch, NOT main)
git push origin feature/my-change
```

**Key Point:** All editing happens **locally** in your IDE/editor.

### Step 2: Version Control (GITHUB)

**Push to GitHub, create PR, merge:**

```powershell
# After pushing feature branch, create PR on GitHub
# - Go to GitHub website
# - Create Pull Request: feature/my-change → main
# - Review, merge PR

# After merge, pull to local main
git checkout main
git pull origin main
```

**Key Point:** GitHub `main` branch becomes the **single source of truth**.

### Step 3: Deployment (AZURE)

**Azure pulls FROM GitHub main and deploys:**

```powershell
# Azure deployment pulls from GitHub main
cd azure
.\deploy.ps1 -Environment prod -OddsApiKey "YOUR_KEY"

# This process:
# 1. Pulls latest code FROM GitHub main
# 2. Builds Docker image
# 3. Pushes image to Azure Container Registry
# 4. Deploys to Azure Container Apps
```

**Key Point:** Azure **pulls FROM GitHub main**, it does NOT pull from your local machine.

---

## 🔄 Where Each Activity Happens

| Activity | Location | Why |
|----------|----------|-----|
| **Edit Code** | **LOCAL** (your IDE) | Fast iteration, local testing |
| **Commit Changes** | **LOCAL** → GitHub | Version control |
| **Push Code** | **LOCAL** → GitHub feature branch | Share work |
| **Review/Approve** | **GITHUB** (PR) | Code review |
| **Merge to Main** | **GITHUB** | Single source of truth |
| **Deploy to Production** | **AZURE** (from GitHub main) | Run application |

---

## 🚫 What NOT to Do

### ❌ Don't Edit Code in Azure

```powershell
# BAD - Azure is not an editor
# Don't SSH into Azure containers to edit files
# Don't try to modify code running in Azure
```

### ❌ Don't Deploy from Local

```powershell
# BAD - Don't deploy directly from local changes
# Local might have uncommitted changes
# Local might be out of sync with GitHub
```

### ❌ Don't Skip GitHub

```powershell
# BAD - Don't try to push directly from local to Azure
# Always: Local → GitHub → Azure
```

---

## ✅ Correct Flow

### Always Follow This Order:

```
1. LOCAL: Edit code in your IDE
   ↓
2. LOCAL: Commit and push to GitHub (feature branch)
   ↓
3. GITHUB: Create PR, review, merge to main
   ↓
4. LOCAL: Pull latest main (git pull origin main)
   ↓
5. AZURE: Deploy from GitHub main (./deploy.ps1)
```

---

## 🎯 Single Source of Truth Summary

### The Rule:

**GitHub `main` branch = Single Source of Truth**

- ✅ All development happens **locally**
- ✅ All code is pushed to **GitHub**
- ✅ All changes merge to **GitHub main**
- ✅ Azure deploys **FROM GitHub main**

### Quick Reference:

```powershell
# Development (LOCAL)
git checkout -b feature/my-change
# Edit files in IDE
git commit -m "Change"
git push origin feature/my-change

# Version Control (GITHUB)
# Create PR on GitHub → Merge to main

# Deployment (AZURE - FROM GitHub)
cd azure
.\deploy.ps1 -Environment prod -OddsApiKey "KEY"
# Azure pulls FROM GitHub main automatically
```

---

## 💡 Key Takeaways

1. **Edit code LOCALLY** (in your IDE/editor)
2. **Push to GITHUB** (feature branch → PR → main)
3. **Azure pulls FROM GitHub main** (not from local)
4. **GitHub main = Single source of truth** (all code versions)

---

**Remember:** Development is LOCAL, version control is GITHUB, deployment is AZURE (from GitHub).

