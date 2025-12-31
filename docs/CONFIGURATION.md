# Configuration Guide - Avoiding Port and Resource Conflicts

**Date:** December 23, 2025  
**Purpose:** Make ports, locations, and resource names configurable to avoid conflicts with other projects

---

## 🎯 Overview

All ports, locations, and resource names are now **configurable via environment variables** to prevent conflicts with other projects running on the same machine or Azure subscription.

---

## 🔌 Port Configuration

### Default Ports

| Service | Host Port | Container Port | Environment Variable |
|---------|-----------|----------------|---------------------|
| PostgreSQL | 5450 | 5432 | `POSTGRES_HOST_PORT` |
| Redis | 6390 | 6379 | `REDIS_HOST_PORT` |
| Prediction API | 8092 | 8082 | `PREDICTION_HOST_PORT` |

### Changing Ports

**Option 1: Environment Variables (Recommended)**
```bash
# Windows PowerShell
$env:POSTGRES_HOST_PORT="5451"
$env:REDIS_HOST_PORT="6391"
$env:PREDICTION_HOST_PORT="8093"
docker compose up -d

# Linux/Mac
export POSTGRES_HOST_PORT=5451
export REDIS_HOST_PORT=6391
export PREDICTION_HOST_PORT=8093
docker compose up -d
```

**Option 2: `.env` files are not supported**

This repository does **not** load `.env` files; secrets must come from the `secrets/` directory or be provided directly via environment variables (Option 1). There is no `config.example` template to copy because configuration is expected to be explicit/per-deployment.

**Option 3: Inline with docker compose**
```bash
POSTGRES_HOST_PORT=5451 REDIS_HOST_PORT=6391 PREDICTION_HOST_PORT=8093 docker compose up -d
```

---

## 🌍 Azure Location Configuration

### Default Location
- **Azure Region:** `centralus`
- **Resource Group:** `NCAAM-GBSV-MODEL-RG`

### Changing Azure Location

**Using deploy.ps1:**
```powershell
.\azure\deploy.ps1 -Location "eastus" -OddsApiKey "YOUR_KEY"
```

**Available Regions:**
- `centralus` (default)
- `eastus`
- `eastus2`
- `westus`
- `westus2`
- `westus3`
- `southcentralus`
- `northcentralus`
- See: `az account list-locations --output table`

---

## 🏷️ Resource Naming

### Docker Compose Resources

**Project Name (affects all resource names):**
```bash
export COMPOSE_PROJECT_NAME="my_custom_project"
docker compose up -d
```

This changes:
- Container names: `my_custom_project_postgres`, `my_custom_project_redis`, etc.
- Network names: `my_custom_project_backend`, `my_custom_project_data`
- Volume names: `my_custom_project_postgres_data`

### Azure Resource Names

**Standard Production Resources (NCAAM-GBSV-MODEL-RG):**

| Resource | Name |
|----------|------|
| Resource Group | `NCAAM-GBSV-MODEL-RG` |
| Container Registry | `ncaamstablegbsvacr` |
| PostgreSQL | `ncaam-stable-postgres` |
| Redis | `ncaam-stable-redis` |
| Container App | `ncaam-stable-prediction` |
| Log Analytics | `ncaam-stable-logs` |

---

## 🌐 Network Configuration

### Subnet Configuration

**Default Subnets:**
- Backend: `10.51.2.0/24`
- Data: `10.51.3.0/24`

**Change if conflicts exist:**
```bash
export NETWORK_BACKEND_SUBNET="10.52.2.0/24"
export NETWORK_DATA_SUBNET="10.52.3.0/24"
docker compose up -d
```

**Check for conflicts:**
```bash
# Check existing Docker networks
docker network ls

# Inspect network subnets
docker network inspect <network_name>
```

---

## 📋 Complete Configuration Example

### Local Development (Custom Ports)

```bash
# Set environment variables
export POSTGRES_HOST_PORT=5451
export REDIS_HOST_PORT=6391
export PREDICTION_HOST_PORT=8093
export COMPOSE_PROJECT_NAME="ncaam_dev"
export NETWORK_BACKEND_SUBNET="10.60.2.0/24"
export NETWORK_DATA_SUBNET="10.60.3.0/24"

# Start services
docker compose up -d
```

### Azure Deployment

```powershell
# Deploy to production (NCAAM-GBSV-MODEL-RG)
.\azure\deploy.ps1 -OddsApiKey "YOUR_KEY"
```

---

## 🔍 Checking for Conflicts

### Port Conflicts

**Check if ports are in use:**
```bash
# Windows
netstat -ano | findstr :5450
netstat -ano | findstr :6390
netstat -ano | findstr :8092

# Linux/Mac
lsof -i :5450
lsof -i :6390
lsof -i :8092
```

### Docker Resource Conflicts

**Check existing containers:**
```bash
docker ps -a | grep ncaam
```

**Check existing networks:**
```bash
docker network ls | grep ncaam
```

**Check existing volumes:**
```bash
docker volume ls | grep ncaam
```

### Azure Resource Conflicts

**Check existing resource groups:**
```bash
az group list --query "[].name" -o table
```

**Check existing ACR:**
```bash
az acr list --query "[].name" -o table
```

---

## 🛠️ Troubleshooting

### Port Already in Use

**Error:** `Bind for 0.0.0.0:5450 failed: port is already allocated`

**Solution:**
```bash
# Change to different port
export POSTGRES_HOST_PORT=5451
docker compose up -d
```

### Network Subnet Conflict

**Error:** `Pool overlaps with other one on this address space`

**Solution:**
```bash
# Change subnet
export NETWORK_BACKEND_SUBNET="10.60.2.0/24"
export NETWORK_DATA_SUBNET="10.60.3.0/24"
docker compose down
docker compose up -d
```

### Container Name Conflict

**Error:** `Conflict. The container name "/ncaam_v33_model_postgres" is already in use`

**Solution:**
```bash
# Use different project name
export COMPOSE_PROJECT_NAME="ncaam_custom"
docker compose up -d
```

---

## 📝 Environment Variable Reference

### Docker Compose Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPOSE_PROJECT_NAME` | `ncaam_v33_model` | Project name (affects all resource names) |
| `POSTGRES_HOST_PORT` | `5450` | PostgreSQL host port |
| `REDIS_HOST_PORT` | `6390` | Redis host port |
| `PREDICTION_HOST_PORT` | `8092` | Prediction API host port |
| `NETWORK_BACKEND_SUBNET` | `10.51.2.0/24` | Backend network subnet |
| `NETWORK_DATA_SUBNET` | `10.51.3.0/24` | Data network subnet |

### Azure Deployment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `Location` | `centralus` | Azure region |
| `ResourceGroup` | `NCAAM-GBSV-MODEL-RG` | Resource group name |
| `Environment` | `stable` | Deployment environment |
| `ImageTag` | `v<VERSION>` (e.g., `v33.6.5`) | Container image tag (read from repo `VERSION`) |

---

## ✅ Best Practices

1. **Use Environment Variables** - Don't hardcode values in scripts
2. **Check for Conflicts First** - Verify ports/networks before starting
3. **Use Descriptive Names** - Make project names unique and descriptive
4. **Document Your Config** - Keep track of custom configurations
5. **Test in Isolation** - Use different ports/names for dev/staging/prod

---

## 📚 Related Documentation

- `README.md` - Quick start guide
- `azure/README.md` - Azure deployment guide
- `docs/NAMING_STANDARDS.md` - Naming conventions

---

**Last Updated:** December 23, 2025  
# Ingestion Healthcheck

This guide helps quickly validate external API ingestion is operational and resilient.

## What it checks
- Barttorvik ratings JSON endpoint responds and decodes
- The Odds API odds endpoint responds with valid JSON (using configured API key)
- Retries on transient failures (429/5xx, network errors) with exponential backoff and jitter

## Prerequisites
- Odds API key available via environment `THE_ODDS_API_KEY` or Docker secret `/run/secrets/odds_api_key`
- Python with dependencies installed (see below)

## Quick checks (no extra scripts required)

- **Prediction service**: `GET /health` and `GET /metrics`
- **Odds API sanity** (inside the prediction-service container):

```bash
python -m app.odds_pull_all
```

Exit codes: `0` when all checks pass, `1` otherwise.

## Interpreting results
- PASS: Endpoint reachable and payload decoded as expected.
- FAIL: Includes the reason (rate limited, server error, JSON parse error, missing key).

If Odds API reports `429` frequently, consider:
- Running sync less frequently (manual-only; no continuous polling loop)
- Reducing market/bookmaker coverage (fewer requests and smaller payloads)
- Ensuring per-minute quotas are observed (see Rust rate limiter)
- Honoring `Retry-After` headers (already implemented in services)

## Related resilience changes
- Go ratings sync: robust HTTP retries/backoff and `Retry-After` support.
- Rust odds ingestion: retries for `429/5xx`, `Retry-After` honored.
- Python orchestrator: one-shot retry when a sync step fails.
