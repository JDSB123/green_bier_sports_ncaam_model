# External Dependencies - NCAA Basketball v6.0

**Date:** December 19, 2025  
**Purpose:** Document all external dependencies required for the system

---

## 🎯 What "Self-Contained" Means

**Self-Contained = No Local Dependencies:**
- ✅ No `.env` files required
- ✅ No localhost fallbacks
- ✅ All secrets from Docker secrets only
- ✅ No manual configuration files
- ✅ All code bundled in containers

**NOT Self-Contained = External Services Required:**
- ❌ External APIs (Barttorvik, The Odds API)
- ❌ Docker Hub (for base images)
- ❌ Package registries (PyPI, crates.io, go.dev)
- ❌ Internet connectivity (for data fetching)

---

## 📡 External APIs (Required for Operation)

### 1. Barttorvik API

**Purpose:** Team efficiency ratings (AdjO, AdjD, Tempo + Four Factors)  
**URL:** `https://barttorvik.com/{season}_team_results.json`  
**Frequency:** Daily sync (6 AM ET) or on-demand  
**Authentication:** None (public API)  
**Rate Limits:** Not documented (assumed reasonable)  
**Data Format:** JSON array-of-arrays  
**Required:** ✅ **YES** - System cannot generate predictions without ratings

**Fields Pulled:** 25+ fields per team including:
- Core efficiency metrics (AdjOE, AdjDE, Tempo)
- Four Factors (EFG, TOR, ORB, FTR + defense)
- Shooting breakdown (2P%, 3P%, rates)
- Quality metrics (Barthag, WAB)

**📖 For complete field reference, see [`BARTTORVIK_FIELDS.md`](BARTTORVIK_FIELDS.md)**

**Usage:**
- Go binary (`ratings-sync`) fetches ratings
- Updates `team_ratings` table in PostgreSQL
- Used by prediction engine for all calculations

### 2. The Odds API

**Purpose:** Betting odds (spreads, totals, moneylines)  
**URL:** `https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds`  
**Frequency:** Every 30 seconds (continuous polling)  
**Authentication:** API key required (stored in Docker secret)  
**Rate Limits:** 45 requests/minute (enforced in code)  
**Data Format:** JSON  
**Required:** ✅ **YES** - System cannot compare model vs market without odds

**Usage:**
- Rust binary (`odds-ingestion`) fetches odds
- Updates `games` and `odds_snapshots` tables
- Used for edge calculation (model prediction vs market line)

**API Key:**
- Stored in `secrets/odds_api_key.txt`
- Mounted as Docker secret at `/run/secrets/odds_api_key`
- **NO fallback** - system fails if missing

---

## 🐳 Docker Base Images (From Docker Hub)

### Build-Time Dependencies

| Image | Purpose | Size | Required |
|-------|---------|------|----------|
| `golang:1.22-alpine` | Build Go binary (ratings-sync) | ~300MB | ✅ Build only |
| `rust:latest` | Build Rust binary (odds-ingestion) | ~1.5GB | ✅ Build only |
| `python:3.12-slim` | Python runtime | ~150MB | ✅ Runtime |

### Runtime Dependencies

| Image | Purpose | Size | Required |
|-------|---------|------|----------|
| `timescale/timescaledb:latest-pg15` | PostgreSQL database | ~500MB | ✅ Runtime |
| `redis:7-alpine` | Redis cache | ~30MB | ✅ Runtime |

**Note:** These images are pulled from Docker Hub during `docker compose build` or `docker compose pull`. Once pulled, they're cached locally.

**Offline Operation:** If images are already cached, system can run offline (except for API calls).

---

## 📦 Package Dependencies

### Python Packages (PyPI)

**Source:** `services/prediction-service-python/requirements.txt`

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.109.0 | Web framework |
| `uvicorn` | 0.27.0 | ASGI server |
| `pydantic` | 2.5.3 | Data validation |
| `sqlalchemy` | 2.0.25 | Database ORM |
| `psycopg2-binary` | 2.9.9 | PostgreSQL driver |
| `asyncpg` | 0.29.0 | Async PostgreSQL |
| `pandas` | 2.1.4 | Data processing |
| `numpy` | 1.26.2 | Numerical computing |
| `redis` | 5.0.1 | Redis client |
| `requests` | 2.31.0 | HTTP client |
| `httpx` | 0.26.0 | Async HTTP client |

**Total:** 35 packages (including transitive dependencies)

**Installation:** During Docker build via `pip install -r requirements.txt`

### Go Modules (go.dev / GitHub)

**Source:** `services/ratings-sync-go/go.mod`

| Module | Version | Purpose |
|--------|---------|---------|
| `github.com/jackc/pgx/v5` | 5.5.2 | PostgreSQL driver |
| `github.com/robfig/cron/v3` | 3.0.1 | Cron scheduler |
| `go.uber.org/zap` | 1.26.0 | Structured logging |

**Total:** ~10 modules (including transitive dependencies)

**Installation:** During Docker build via `go mod download`

### Rust Crates (crates.io)

**Source:** `services/odds-ingestion-rust/Cargo.toml`

| Crate | Version | Purpose |
|-------|---------|---------|
| `tokio` | 1.35 | Async runtime |
| `axum` | 0.7 | HTTP server |
| `reqwest` | 0.11 | HTTP client |
| `sqlx` | 0.7 | Database driver |
| `redis` | 0.24 | Redis client |
| `serde` | 1.0 | Serialization |
| `chrono` | 0.4 | Time handling |
| `uuid` | 1.6 | UUID generation |
| `tracing` | 0.1 | Logging |
| `anyhow` | 1.0 | Error handling |
| `governor` | 0.6 | Rate limiting |

**Total:** ~50 crates (including transitive dependencies)

**Installation:** During Docker build via `cargo build --release`

---

## 🌐 Network Requirements

### Outbound Connections (Required)

| Destination | Port | Protocol | Purpose |
|-------------|------|----------|---------|
| `barttorvik.com` | 443 | HTTPS | Fetch team ratings |
| `api.the-odds-api.com` | 443 | HTTPS | Fetch betting odds |
| `registry-1.docker.io` | 443 | HTTPS | Pull Docker images (build-time) |
| `pypi.org` | 443 | HTTPS | Install Python packages (build-time) |
| `proxy.golang.org` | 443 | HTTPS | Download Go modules (build-time) |
| `crates.io` | 443 | HTTPS | Download Rust crates (build-time) |

### Inbound Connections (Optional - for API access)

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Prediction API | 8092 (configurable) | HTTP | External API access |

---

## 🔒 Security Considerations

### API Keys

**The Odds API Key:**
- Stored in `secrets/odds_api_key.txt`
- Mounted as Docker secret
- **Never** in code, logs, or environment variables
- Required for odds fetching

**Barttorvik:**
- No authentication required (public API)

### Package Registry Security

- All packages verified via package manager signatures
- Docker images pulled from official registries
- No custom/private registries required

---

## 📊 Dependency Summary

### Build-Time Dependencies

| Type | Source | Required For | Can Cache? |
|------|--------|--------------|------------|
| Docker images | Docker Hub | Container builds | ✅ Yes |
| Python packages | PyPI | Python service | ✅ Yes |
| Go modules | go.dev/GitHub | Go binary | ✅ Yes |
| Rust crates | crates.io | Rust binary | ✅ Yes |

**Once built:** Container images contain all dependencies. No external package registries needed at runtime.

### Runtime Dependencies

| Type | Source | Required For | Can Cache? |
|------|--------|--------------|------------|
| Barttorvik API | Internet | Team ratings | ❌ No (live data) |
| The Odds API | Internet | Betting odds | ❌ No (live data) |
| Internet connectivity | Network | API calls | ❌ No |

**At runtime:** System requires internet connectivity for data fetching.

---

## 🚫 What's NOT Required

### Local Files
- ❌ `.env` files
- ❌ Configuration files (except secrets)
- ❌ Local databases
- ❌ Local Redis instances

### External Services (Optional)
- ❌ GitHub Actions
- ❌ CI/CD pipelines
- ❌ External monitoring (Azure Monitor, etc.)
- ❌ External logging services

### Manual Setup
- ❌ Manual database migrations (auto-run)
- ❌ Manual team data entry (from migrations)
- ❌ Manual configuration (all via Docker)

---

## ✅ True "Self-Contained" Aspects

1. **Secrets Management:** All secrets in Docker secrets, no local files
2. **Database Schema:** All migrations auto-run on first init
3. **Team Data:** 688+ aliases from migrations, no manual entry
4. **Code:** All binaries built into container, no external tools needed
5. **Configuration:** All config via environment variables or Docker secrets

---

## 🔄 Offline Operation

### Can Run Offline:
- ✅ Prediction engine (if data already in database)
- ✅ API endpoints
- ✅ Database queries
- ✅ Cached data operations

### Cannot Run Offline:
- ❌ Fresh ratings sync (requires Barttorvik API)
- ❌ Fresh odds sync (requires The Odds API)
- ❌ Initial Docker build (requires package registries)

### Partial Offline:
- ⚠️ Can use cached data if APIs unavailable
- ⚠️ Predictions will use stale data
- ⚠️ System logs warnings but continues

---

## 📝 Dependency Checklist

Before deployment, ensure:

- [ ] Internet connectivity for API calls
- [ ] The Odds API key obtained and stored in `secrets/odds_api_key.txt`
- [ ] Docker images can be pulled (or already cached)
- [ ] Package registries accessible (or packages already cached)
- [ ] Firewall allows outbound HTTPS (443) to:
  - `barttorvik.com`
  - `api.the-odds-api.com`
  - `registry-1.docker.io` (build-time)
  - `pypi.org` (build-time)
  - `proxy.golang.org` (build-time)
  - `crates.io` (build-time)

---

## 🎯 Summary

**External Dependencies Required:**

1. **APIs (Runtime):**
   - Barttorvik API (public, no auth)
   - The Odds API (requires API key)

2. **Package Registries (Build-Time):**
   - Docker Hub (base images)
   - PyPI (Python packages)
   - Go module proxy (Go packages)
   - Crates.io (Rust packages)

3. **Network:**
   - Internet connectivity for API calls
   - Outbound HTTPS (443) access

**What's Self-Contained:**
- ✅ Secrets management (Docker secrets only)
- ✅ Database schema (auto-migrations)
- ✅ Team data (from migrations)
- ✅ All code (bundled in containers)
- ✅ Configuration (environment variables)

---

**Last Updated:** December 19, 2025  
**Version:** v6.0 FINAL
