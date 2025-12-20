# Azure Migration Checklist

**Project:** NCAA Basketball v6.0 Prediction System  
**Target:** Azure Container Apps  
**Date:** December 19, 2025

---

## Pre-Migration

### ✅ Code Preparation
- [x] All code committed to Git
- [x] Docker images build successfully
- [x] End-to-end test passes locally
- [x] Secrets management documented
- [x] Database migrations tested
- [x] Documentation complete

### ✅ Azure Account Setup
- [ ] Azure subscription active
- [ ] Azure CLI installed (`az --version`)
- [ ] Azure CLI logged in (`az login`)
- [ ] Default subscription set (`az account set --subscription "Name"`)
- [ ] Permissions verified (Contributor role)

---

## Infrastructure Setup

### Resource Group
- [ ] Create resource group: `greenbier-enterprise-rg`
- [ ] Set location: `eastus` (or preferred region)

### Azure Container Registry (ACR)
- [ ] Create ACR: `greenbieracr`
- [ ] Enable admin user
- [ ] Login to ACR: `az acr login --name greenbieracr`
- [ ] Build and push prediction service image
- [ ] Verify image in ACR

### Azure Key Vault
- [ ] Create Key Vault: `greenbier-keyvault`
- [ ] Store `db-password` secret
- [ ] Store `redis-password` secret
- [ ] Store `odds-api-key` secret
- [ ] Verify secrets accessible

### Database
- [ ] **Option A:** Create Azure Database for PostgreSQL Flexible Server
- [ ] **Option B:** Deploy PostgreSQL container in Container Apps
- [ ] Run database migrations (001-006)
- [ ] Verify team_aliases table populated (688+ entries)
- [ ] Test team name resolution function

### Redis
- [ ] **Option A:** Create Azure Cache for Redis
- [ ] **Option B:** Deploy Redis container in Container Apps
- [ ] Configure password authentication
- [ ] Test connection

---

## Container Apps Deployment

### Environment
- [ ] Create Container Apps environment: `greenbier-ncaam-env`
- [ ] Configure networking (internal/external)
- [ ] Set up Log Analytics workspace

### PostgreSQL Container (if not using managed DB)
- [ ] Create container app: `ncaam-postgres`
- [ ] Configure environment variables
- [ ] Set resource limits (CPU/Memory)
- [ ] Verify container starts successfully
- [ ] Test database connection

### Redis Container (if not using managed cache)
- [ ] Create container app: `ncaam-redis`
- [ ] Configure password authentication
- [ ] Set resource limits
- [ ] Verify container starts successfully
- [ ] Test Redis connection

### Prediction Service Container
- [ ] Create container app: `ncaam-prediction`
- [ ] Configure ACR authentication
- [ ] Set environment variables:
  - [ ] DATABASE_URL
  - [ ] REDIS_URL
  - [ ] THE_ODDS_API_KEY
  - [ ] MODEL__HOME_COURT_ADVANTAGE_SPREAD
  - [ ] MODEL__HOME_COURT_ADVANTAGE_TOTAL
- [ ] Configure ingress (external, port 8082)
- [ ] Set resource limits
- [ ] Verify container starts successfully

---

## Post-Deployment Testing

### Health Checks
- [ ] PostgreSQL health check passes
- [ ] Redis health check passes
- [ ] Prediction service health endpoint responds: `/health`
- [ ] All containers show "Running" status

### Data Sync Testing
- [ ] Ratings sync (Go binary) executes successfully
- [ ] Odds ingestion (Rust binary) executes successfully
- [ ] Verify data in database:
  - [ ] Team ratings populated
  - [ ] Games table has entries
  - [ ] Odds snapshots created

### Prediction Testing
- [ ] Execute `run_today.py` in container
- [ ] Verify predictions generated
- [ ] Check executive table output format
- [ ] Verify fire ratings (1-5 scale)
- [ ] Confirm all 6 markets calculated

### API Testing
- [ ] Test prediction API endpoint (if exposed)
- [ ] Verify CORS headers (if needed)
- [ ] Test authentication (if implemented)

---

## Security & Compliance

### Network Security
- [ ] Configure Network Security Groups
- [ ] Set up private endpoints (if using managed services)
- [ ] Configure firewall rules
- [ ] Restrict public access where possible

### Secrets Management
- [ ] Verify no secrets in code/logs
- [ ] Use Managed Identity for Key Vault access (recommended)
- [ ] Rotate secrets if needed
- [ ] Audit secret access logs

### Monitoring
- [ ] Enable Container Insights
- [ ] Set up Application Insights
- [ ] Configure alerting rules
- [ ] Set up log retention policies

---

## Performance & Optimization

### Resource Sizing
- [ ] Monitor CPU usage (adjust if needed)
- [ ] Monitor memory usage (adjust if needed)
- [ ] Review database performance
- [ ] Optimize container startup time

### Cost Optimization
- [ ] Review Azure Cost Management
- [ ] Set up budget alerts
- [ ] Consider reserved instances (if long-term)
- [ ] Optimize container scaling

---

## Documentation

### Update Documentation
- [ ] Update README.md with Azure deployment info
- [ ] Document connection strings
- [ ] Document troubleshooting steps
- [ ] Create runbook for common operations

### Team Handoff
- [ ] Share Azure credentials securely
- [ ] Document access procedures
- [ ] Train team on Azure portal
- [ ] Provide escalation contacts

---

## Go-Live

### Final Checks
- [ ] All tests passing
- [ ] Monitoring configured
- [ ] Alerts set up
- [ ] Backup strategy in place
- [ ] Rollback plan documented

### Migration Execution
- [ ] Schedule maintenance window (if needed)
- [ ] Backup local database (if applicable)
- [ ] Deploy to Azure
- [ ] Run smoke tests
- [ ] Verify end-to-end flow

### Post-Migration
- [ ] Monitor for 24-48 hours
- [ ] Address any issues
- [ ] Update DNS/endpoints (if applicable)
- [ ] Decommission local resources (if applicable)

---

## Rollback Plan

If issues occur:
1. [ ] Document specific issue
2. [ ] Check container logs
3. [ ] Review Azure Monitor metrics
4. [ ] Revert to previous image version (if needed)
5. [ ] Scale down problematic containers
6. [ ] Restore from backup (if database issue)

---

## Sign-Off

- [ ] **Technical Lead:** _________________ Date: _______
- [ ] **DevOps Engineer:** _________________ Date: _______
- [ ] **Project Manager:** _________________ Date: _______

---

## Notes

- Migration target date: _______________
- Estimated downtime: _______________
- Rollback contact: _______________

---

**Last Updated:** December 19, 2025
