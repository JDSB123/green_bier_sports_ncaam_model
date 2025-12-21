# Configuration Guide - Avoiding Port and Resource Conflicts

**Date:** December 19, 2025  
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

**Option 2: .env File (Optional)**
```bash
# Copy template
cp config.example .env

# Edit .env file
POSTGRES_HOST_PORT=5451
REDIS_HOST_PORT=6391
PREDICTION_HOST_PORT=8093

# Docker Compose automatically reads .env
docker compose up -d
```

**Option 3: Inline with docker compose**
```bash
POSTGRES_HOST_PORT=5451 REDIS_HOST_PORT=6391 PREDICTION_HOST_PORT=8093 docker compose up -d
```

---

## 🌍 Azure Location Configuration

### Default Location
- **Azure Region:** `eastus`

### Changing Azure Location

**Before running enterprise-deploy.sh:**
```bash
export AZURE_LOCATION="westus2"
./azure/enterprise-deploy.sh
```

**Or edit enterprise-deploy.sh:**
```bash
LOCATION="${AZURE_LOCATION:-westus2}"
```

**Available Regions:**
- `eastus` (default)
- `eastus2`
- `westus`
- `westus2`
- `westus3`
- `centralus`
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

**All Azure resources are configurable:**

```bash
export AZURE_RESOURCE_GROUP="my-ncaam-rg"
export AZURE_ACR_NAME="myregistry"
export AZURE_KEY_VAULT_NAME="my-secrets"
export AZURE_CONTAINER_APP_ENV="my-env"
export AZURE_POSTGRES_NAME="my-postgres"
export AZURE_REDIS_NAME="my-redis"
export AZURE_PREDICTION_NAME="my-prediction"
./azure/enterprise-deploy.sh
```

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

### Azure Deployment (Custom Location/Names)

```bash
# Set Azure configuration
export AZURE_LOCATION="westus2"
export AZURE_RESOURCE_GROUP="ncaam-prod-rg"
export AZURE_ACR_NAME="ncaamprodregistry"
export AZURE_KEY_VAULT_NAME="ncaam-prod-secrets"
export AZURE_CONTAINER_APP_ENV="ncaam-prod-env"

# Deploy
./azure/enterprise-deploy.sh
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

**Find available ports:**
```bash
# Windows PowerShell
Get-NetTCPConnection | Where-Object {$_.LocalPort -notin 5450,6390,8092} | Select-Object LocalPort | Sort-Object -Unique

# Linux/Mac
comm -23 <(seq 5000 9000) <(ss -tan | awk '{print $4}' | cut -d':' -f2 | sort -u) | head -3
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

**Check existing Key Vaults:**
```bash
az keyvault list --query "[].name" -o table
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

### Azure Resource Name Conflict

**Error:** `The resource name 'greenbier-enterprise-rg' is already taken`

**Solution:**
```bash
# Use different name
export AZURE_RESOURCE_GROUP="greenbier-enterprise-rg-$(date +%s)"
./azure/enterprise-deploy.sh
```

### Container Name Conflict

**Error:** `Conflict. The container name "/ncaam_v6_model_postgres" is already in use`

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
| `COMPOSE_PROJECT_NAME` | `ncaam_v6_model_final` | Project name (affects all resource names) |
| `POSTGRES_HOST_PORT` | `5450` | PostgreSQL host port |
| `REDIS_HOST_PORT` | `6390` | Redis host port |
| `PREDICTION_HOST_PORT` | `8092` | Prediction API host port |
| `NETWORK_BACKEND_SUBNET` | `10.51.2.0/24` | Backend network subnet |
| `NETWORK_DATA_SUBNET` | `10.51.3.0/24` | Data network subnet |

### Azure Deployment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_LOCATION` | `eastus` | Azure region |
| `AZURE_RESOURCE_GROUP` | `greenbier-enterprise-rg` | Resource group name |
| `AZURE_ACR_NAME` | `greenbieracr` | Container registry name |
| `AZURE_KEY_VAULT_NAME` | `greenbier-keyvault` | Key Vault name |
| `AZURE_CONTAINER_APP_ENV` | `greenbier-ncaam-env` | Container Apps environment |
| `AZURE_POSTGRES_NAME` | `ncaam-postgres` | PostgreSQL container name |
| `AZURE_REDIS_NAME` | `ncaam-redis` | Redis container name |
| `AZURE_PREDICTION_NAME` | `ncaam-prediction` | Prediction service name |
| `IMAGE_TAG` | `v6.0` | Container image tag |

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
- `docs/AZURE_MIGRATION.md` - Azure deployment guide
- `config.example` - Configuration template

---

**Last Updated:** December 19, 2025  
**Version:** v6.0 ENTERPRISE
# Ingestion Healthcheck

This guide helps quickly validate external API ingestion is operational and resilient.

## What it checks
- Barttorvik ratings JSON endpoint responds and decodes
- The Odds API odds endpoint responds with valid JSON (using configured API key)
- Retries on transient failures (429/5xx, network errors) with exponential backoff and jitter

## Prerequisites
- Odds API key available via environment `THE_ODDS_API_KEY` or Docker secret `/run/secrets/odds_api_key`
- Python with dependencies installed (see below)

## Install dependencies
Use the testing requirements:

```bash
pip install -r testing/requirements.txt
```

## Run the healthcheck
Default options match service configuration (season auto-calculated, sport key `basketball_ncaab`).

```bash
python testing/scripts/ingestion_healthcheck.py
```

Override options if needed:
```bash
python testing/scripts/ingestion_healthcheck.py --season 2025 --sport-key basketball_ncaab
```

Exit codes: `0` when all checks pass, `1` otherwise.

## Interpreting results
- PASS: Endpoint reachable and payload decoded as expected.
- FAIL: Includes the reason (rate limited, server error, JSON parse error, missing key).

If Odds API reports `429` frequently, consider:
- Reducing poll interval
- Ensuring per-minute quotas are observed (see Rust rate limiter)
- Honoring `Retry-After` headers (already implemented in services)

## Related resilience changes
- Go ratings sync: robust HTTP retries/backoff and `Retry-After` support.
- Rust odds ingestion: retries for `429/5xx`, `Retry-After` honored.
- Python orchestrator: one-shot retry when a sync step fails.
