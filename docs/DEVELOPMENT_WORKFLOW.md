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
│                 │ LOCAL deploy (clean checkout of main)  │
│                 │ builds + pushes images to ACR          │
│                 ▼                                        │
│  ┌──────────────────────────────────────────────┐      │
│  │  AZURE (Production Deployment)               │      │
│  │  • Runs the application                      │      │
│  │  • Pulls container images FROM ACR           │      │
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
- ✅ **Azure runs container images pulled from ACR**
- ✅ **A deploy operator builds/pushes images from a clean `main` checkout**
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

**Deploy from a clean, up-to-date checkout of `main`:**

```powershell
# Ensure local is aligned to GitHub main first
git checkout main
git pull origin main

# Build/push images to ACR + update Azure Container Apps/Jobs
cd azure
.\deploy.ps1 -Environment prod -OddsApiKey "YOUR_KEY"

# This process:
# 1. Builds Docker images locally from this repo checkout
# 3. Pushes image to Azure Container Registry
# 4. Deploys to Azure Container Apps
```

**Key Point:** Azure does **not** pull code from GitHub. It pulls **container images from ACR**.
To keep deployments consistent, always run `deploy.ps1` from a clean, up-to-date checkout of `main`.

---

## 🔄 Where Each Activity Happens

| Activity | Location | Why |
|----------|----------|-----|
| **Edit Code** | **LOCAL** (your IDE) | Fast iteration, local testing |
| **Commit Changes** | **LOCAL** → GitHub | Version control |
| **Push Code** | **LOCAL** → GitHub feature branch | Share work |
| **Review/Approve** | **GITHUB** (PR) | Code review |
| **Merge to Main** | **GITHUB** | Single source of truth |
| **Deploy to Production** | **LOCAL deploy script** → Azure | Build/push to ACR + update Container Apps |

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
5. LOCAL: Deploy from clean main (./deploy.ps1 → ACR → Azure)
```

---

## 🎯 Single Source of Truth Summary

### The Rule:

**GitHub `main` branch = Single Source of Truth**

- ✅ All development happens **locally**
- ✅ All code is pushed to **GitHub**
- ✅ All changes merge to **GitHub main**
- ✅ Azure runs **ACR images built from main**

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
# Azure pulls images from ACR (deploy script pushes them)
```

---

## 💡 Key Takeaways

1. **Edit code LOCALLY** (in your IDE/editor)
2. **Push to GITHUB** (feature branch → PR → main)
3. **Deploy from a clean main checkout** (`deploy.ps1` builds/pushes to ACR)
4. **GitHub main = single source of truth** for what should be deployed

---

**Remember:** Development is LOCAL, version control is GITHUB, deployment is AZURE (from GitHub).

