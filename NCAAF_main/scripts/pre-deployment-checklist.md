# NCAAF v5.0 Production Deployment Checklist

## Pre-Deployment Checklist

Use this checklist before deploying to production to ensure all critical components are ready.

### 1. Configuration & Environment

- [ ] `.env.production` file created from `.env.production.example`
- [ ] **DATABASE_PASSWORD** changed to a strong password (20+ characters)
- [ ] **REDIS_PASSWORD** changed to a strong password
- [ ] **SPORTSDATA_API_KEY** set to production API key
- [ ] **WEBHOOK_SECRET** set to random secure string
- [ ] **DATABASE_SSL_MODE** set to `require` or `verify-full`
- [ ] File permissions on `.env.production` set to 600 (`chmod 600 .env.production`)
- [ ] `.env.production` added to `.gitignore`
- [ ] All environment variables validated (no placeholder values)

### 2. Infrastructure

- [ ] Server meets minimum requirements:
  - [ ] 4 CPU cores
  - [ ] 8GB RAM
  - [ ] 100GB SSD storage
  - [ ] Ubuntu 22.04 LTS or similar
- [ ] Docker 20.10+ installed
- [ ] Docker Compose 2.0+ installed
- [ ] Firewall configured (only necessary ports exposed)
- [ ] SSL certificates obtained (if using custom domain)
- [ ] Backup storage configured and accessible

### 3. Database

- [ ] PostgreSQL 16 running and accessible
- [ ] Database `ncaaf_v5_prod` created
- [ ] Database user created with proper permissions
- [ ] SSL/TLS enabled for database connections
- [ ] Connection string tested: `psql "postgres://user:pass@host:port/db"`
- [ ] Migrations run successfully: `make migrate-up`
- [ ] Migration version verified: `migrate version`
- [ ] Seed data loaded: `./scripts/seed_all.sh`
- [ ] Teams count verified: `SELECT COUNT(*) FROM teams;` (>= 50 teams)
- [ ] Stadiums count verified: `SELECT COUNT(*) FROM stadiums;` (>= 50 stadiums)
- [ ] Database indexes verified (check pg_indexes)
- [ ] Automated backup configured (daily at 3 AM)
- [ ] Backup tested and verified

### 4. Redis

- [ ] Redis 7 running and accessible
- [ ] Password authentication enabled
- [ ] Maxmemory policy set (allkeys-lru)
- [ ] Persistence enabled (RDB + AOF)
- [ ] Connection tested: `redis-cli -a password PING`
- [ ] Memory limits configured (512MB recommended)

### 5. Docker Services

- [ ] Docker images built: `docker-compose -f docker-compose.prod.yml build`
- [ ] Images tagged with version: `docker tag ncaaf-v5/ingestion:latest ncaaf-v5/ingestion:1.0.0`
- [ ] Resource limits configured in docker-compose.prod.yml
- [ ] Health checks configured for all services
- [ ] Log rotation configured (max 10MB, 3-5 files)
- [ ] Volume mounts verified
- [ ] Network isolation configured

### 6. Ingestion Service

- [ ] Service starts without errors: `docker-compose -f docker-compose.prod.yml up -d ingestion`
- [ ] Health check passing: `curl http://localhost:8080/health`
- [ ] Metrics endpoint accessible: `curl http://localhost:9090/metrics`
- [ ] SportsDataIO API key valid and not rate limited
- [ ] Initial sync completed: Check logs for "Initial sync complete"
- [ ] Active games polling working (if games in progress)
- [ ] Database connection stable (no connection errors in logs)
- [ ] Redis caching working (check metrics: cache_hits_total)

### 7. ML Service

- [ ] Service starts without errors: `docker-compose -f docker-compose.prod.yml up -d ml_service`
- [ ] Health check passing: `curl http://localhost:8000/health`
- [ ] Metrics endpoint accessible: `curl http://localhost:8000/metrics`
- [ ] Database connection verified
- [ ] Redis connection verified
- [ ] ML models exist in `/app/models/`:
  - [ ] `xgboost_margin.pkl`
  - [ ] `xgboost_total.pkl`
  - [ ] `xgboost_home_score.pkl`
  - [ ] `xgboost_away_score.pkl`
- [ ] Models loaded without errors (check logs)
- [ ] Test prediction endpoint: `curl http://localhost:8000/api/v1/predictions/week/2024/15`
- [ ] Feature extraction working
- [ ] Predictions being generated and saved

### 8. Data Validation

- [ ] Teams data accurate (spot check 5-10 teams)
- [ ] Games data current (check latest week)
- [ ] Odds data being ingested (if available)
- [ ] Line movements being tracked
- [ ] Predictions being generated for upcoming games
- [ ] Confidence scores reasonable (0.0-1.0)
- [ ] Edge calculations working
- [ ] Betting recommendations appropriate

### 9. Monitoring & Observability

- [ ] Prometheus metrics accessible on both services
- [ ] Key metrics verified:
  - [ ] `ncaaf_system_uptime_seconds`
  - [ ] `ncaaf_api_calls_total`
  - [ ] `ncaaf_db_queries_total`
  - [ ] `ncaaf_cache_hits_total`
  - [ ] `ncaaf_predictions_total`
- [ ] Log aggregation configured (if using external system)
- [ ] Alert rules defined (if using alerting)
- [ ] Dashboard created (if using Grafana)

### 10. Testing

- [ ] Run full validation script: `./scripts/validate_pipeline.sh`
- [ ] All critical tests passing
- [ ] Integration tests run: `cd ml_service && pytest tests/test_e2e_pipeline.py -m integration`
- [ ] Unit tests passing: `cd ml_service && pytest`
- [ ] Go tests passing: `cd ingestion && make test`
- [ ] Load test performed (if applicable)
- [ ] Failure scenarios tested:
  - [ ] Database connection lost and recovered
  - [ ] Redis connection lost and recovered
  - [ ] API rate limit hit
  - [ ] Service restart mid-game

### 11. Security

- [ ] No secrets in git repository
- [ ] `.env.production` file secured (permissions 600)
- [ ] Database passwords are strong (20+ characters)
- [ ] Redis password is strong
- [ ] SSL/TLS enabled for database
- [ ] Firewall rules reviewed
- [ ] Only necessary ports exposed:
  - [ ] 5432 (PostgreSQL - only if external access needed)
  - [ ] 6379 (Redis - only if external access needed)
  - [ ] 8080 (Ingestion API - consider internal only)
  - [ ] 8000 (ML API)
  - [ ] 9090 (Metrics - consider internal only)
- [ ] API authentication considered (if exposing publicly)
- [ ] Rate limiting enabled
- [ ] CORS configured appropriately

### 12. Performance

- [ ] Database query performance acceptable (<100ms for most queries)
- [ ] Cache hit rate reasonable (>70% for frequently accessed data)
- [ ] API response times acceptable:
  - [ ] Health checks: <50ms
  - [ ] Team endpoints: <200ms
  - [ ] Game endpoints: <500ms
  - [ ] Prediction endpoints: <2s
- [ ] Concurrent request handling tested
- [ ] Memory usage within limits
- [ ] CPU usage within limits
- [ ] Disk I/O acceptable

### 13. Operational Readiness

- [ ] Deployment documentation reviewed (DEPLOYMENT.md)
- [ ] Runbook created for common operations
- [ ] Backup and restore procedure tested
- [ ] Disaster recovery plan documented
- [ ] On-call rotation defined (if applicable)
- [ ] Incident response procedure defined
- [ ] Rollback procedure tested
- [ ] Monitoring dashboard accessible
- [ ] Log access configured
- [ ] Support contacts documented

### 14. Final Verification

- [ ] Run end-to-end test: Generate prediction for a real game
- [ ] Verify prediction stored in database
- [ ] Verify all services healthy
- [ ] Verify metrics being collected
- [ ] Verify logs being written
- [ ] Verify data pipeline functioning
- [ ] Review recent logs for errors or warnings
- [ ] Confirm all containers running: `docker-compose -f docker-compose.prod.yml ps`
- [ ] System ready for production traffic

## Post-Deployment

After deployment, monitor these for the first 24-48 hours:

- [ ] Error rates (should be <1%)
- [ ] API response times
- [ ] Database connection pool utilization
- [ ] Memory usage trends
- [ ] CPU usage trends
- [ ] Disk usage
- [ ] Cache hit rates
- [ ] Prediction accuracy (compare against actual results)
- [ ] Data freshness (games, odds updating properly)
- [ ] Service uptime

## Emergency Contacts

- **Database Issues**: [Contact/Escalation]
- **API Issues**: [Contact/Escalation]
- **Infrastructure Issues**: [Contact/Escalation]
- **SportsDataIO Support**: [API Support Contact]

## Rollback Plan

If critical issues arise:

1. Stop all services: `docker-compose -f docker-compose.prod.yml down`
2. Restore database from last known good backup
3. Revert to previous Docker image version
4. Investigate issue in development/staging environment
5. Apply fix and re-deploy

## Sign-Off

- [ ] Technical Lead Approval: _________________ Date: _______
- [ ] Operations Approval: _________________ Date: _______
- [ ] Security Review: _________________ Date: _______

---

**Last Updated**: December 2024
**Version**: 1.0.0
