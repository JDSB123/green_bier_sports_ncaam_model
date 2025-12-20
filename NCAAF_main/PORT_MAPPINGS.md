# Port Mappings - NCAAF v5.0 BETA

This document tracks all port mappings to prevent conflicts with other sport models.

## NCAAF v5.0 Unified Container

**Single Container Architecture** - All services (PostgreSQL, Redis, Ingestion, ML Service) run in one container.

| Service | Container Port | Host Port | Purpose | Status |
|---------|---------------|-----------|---------|--------|
| PostgreSQL | 5432 | **Internal only** | Database (localhost) | ✅ No external exposure |
| Redis | 6379 | **Internal only** | Cache (localhost) | ✅ No external exposure |
| Ingestion API | 8080 | **8083** | Data ingestion | ✅ Unique |
| ML Service API | 8000 | **8001** | ML predictions | ✅ Unique |

## Other Sport Models (Reference)

### NBA v5.0
- API: 8090
- Prediction Service: 8082
- PostgreSQL: 5432
- Redis: 6379

### NFL v8.0
- API: 18081
- Model: 18082
- PostgreSQL: 15432

### NCAAM v5.0 (Men's Basketball)
- API Gateway: 8091
- Prediction: 8092
- PostgreSQL: 5450
- Redis: 6390
- Internal services: 8081-8088 (not exposed)

### Dashboard v4
- Frontend: 3000
- Backend: 9090
- PostgreSQL: 5433

## Conflict Check

✅ **No conflicts detected** - All NCAAF v5.0 ports are unique and don't overlap with other sport models.

## Network Isolation

All NCAAF v5.0 containers are isolated on the `ncaaf_v50_beta_ncaaf_network` bridge network, preventing conflicts with other sport model networks.

## Notes

- Ports 8083 and 8001 are only used when ingestion and ml_service containers are running
- All containers use non-root users for security
- Security hardening: `no-new-privileges:true` on all containers
- Database schema volume is read-only
