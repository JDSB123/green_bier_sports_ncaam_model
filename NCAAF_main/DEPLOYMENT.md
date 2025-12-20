# NCAAF v5.0 Production Deployment Guide

Complete guide for deploying NCAAF v5.0 to production.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Database Setup](#database-setup)
- [Deployment](#deployment)
- [Post-Deployment](#post-deployment)
- [Monitoring](#monitoring)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- Docker 20.10+ and Docker Compose 2.0+
- PostgreSQL 16 (if not using Docker)
- Redis 7 (if not using Docker)
- Git
- SSL certificates (for HTTPS)

### Required Accounts
- SportsDataIO API key (production tier)
- Domain name (optional, for custom domain)
- Server with at least:
  - 4 CPU cores
  - 8GB RAM
  - 100GB SSD storage
  - Ubuntu 22.04 LTS or similar

---

## Initial Setup

### 1. Clone Repository
```bash
git clone https://github.com/your-org/ncaaf_v5.0_BETA.git
cd ncaaf_v5.0_BETA
```

### 2. Configure Environment
```bash
# Copy production environment template (if .env.production.example exists)
# Otherwise, create .env.production manually with required variables
cp .env.production.example .env.production 2>/dev/null || echo "Creating .env.production..."

# Edit with your values
nano .env.production
```

**Critical Variables to Set:**
- `DATABASE_PASSWORD` - **REQUIRED** - Strong password (20+ characters) - Generate with: `openssl rand -base64 32`
- `REDIS_PASSWORD` - **REQUIRED** - Strong password (20+ characters) - Generate with: `openssl rand -base64 32`
- `SPORTSDATA_API_KEY` - **REQUIRED** - Your production API key
- `WEBHOOK_SECRET` - **REQUIRED** - Random secure string - Generate with: `openssl rand -hex 32`
- `DATABASE_SSL_MODE=require` - Enable SSL for production

### 3. Security Hardening
```bash
# Set proper file permissions
chmod 600 .env.production

# Never commit .env.production to git
echo ".env.production" >> .gitignore
```

---

## Database Setup

### Option A: Using Unified Container (Recommended for Simplicity)
```bash
# Uses single container with all services (PostgreSQL, Redis, Ingestion, ML Service)
docker-compose -f docker-compose.prod-unified.yml up -d

# Wait for services to be healthy
docker-compose -f docker-compose.prod-unified.yml ps

# View logs
docker-compose -f docker-compose.prod-unified.yml logs -f
```

### Option B: Using Separate Containers (Recommended for Scaling)
```bash
# Uses separate containers for each service (better for horizontal scaling)
# Start only PostgreSQL and Redis first
docker-compose -f docker-compose.prod.yml up -d postgres redis

# Wait for services to be healthy
docker-compose -f docker-compose.prod.yml ps

# Then start application services
docker-compose -f docker-compose.prod.yml up -d ingestion ml_service
```

### Option B: External PostgreSQL
If using managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.):

1. Create database:
```sql
CREATE DATABASE ncaaf_v5_prod;
CREATE USER ncaaf_prod_user WITH ENCRYPTED PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ncaaf_v5_prod TO ncaaf_prod_user;
```

2. Update `.env.production`:
```bash
DATABASE_HOST=your-db-host.aws.com
DATABASE_PORT=5432
DATABASE_SSL_MODE=verify-full
```

### Run Migrations
```bash
# Install golang-migrate
curl -L https://github.com/golang-migrate/migrate/releases/download/v4.17.0/migrate.linux-amd64.tar.gz | tar xvz
sudo mv migrate /usr/local/bin/

# Run migrations
export DATABASE_URL="postgres://user:pass@host:5432/ncaaf_v5_prod?sslmode=require"
migrate -path database/migrations -database "$DATABASE_URL" up

# Verify
migrate -path database/migrations -database "$DATABASE_URL" version
```

---

## Deployment

### Build Images
```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Tag with version
docker tag ncaaf-v5/ingestion:latest ncaaf-v5/ingestion:1.0.0
docker tag ncaaf-v5/ml-service:latest ncaaf-v5/ml-service:1.0.0
```

### Deploy All Services
```bash
# Start all services
docker-compose -f docker-compose.prod.yml --env-file .env.production up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f --tail=100
```

### Scale Services (Optional)
```bash
# Scale ingestion service for high availability
docker-compose -f docker-compose.prod.yml up -d --scale ingestion=2

# Scale ML service for load balancing
docker-compose -f docker-compose.prod.yml up -d --scale ml_service=2
```

---

## Post-Deployment

### 1. Initial Data Sync
```bash
# Trigger initial sync (runs automatically on first start)
# Or manually trigger:
docker-compose -f docker-compose.prod.yml exec ingestion /app/worker --initial-sync

# Check logs
docker-compose -f docker-compose.prod.yml logs ingestion | grep "Initial sync"
```

### 2. Train ML Models
```bash
# SSH into ML service container
docker-compose -f docker-compose.prod.yml exec ml_service bash

# Run training
python scripts/train_xgboost.py

# Verify models created
ls -lh /app/models/
# Should see: xgboost_margin.pkl, xgboost_total.pkl, etc.

# Exit container
exit
```

### 3. Verify Services

**Check Ingestion Service:**
```bash
curl http://localhost:8080/health
# Expected: {"status":"healthy"}
```

**Check ML Service:**
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# Test prediction endpoint
curl http://localhost:8000/api/v1/predictions/week/2024/15
```

**Check Database:**
```bash
# Connect to database
docker-compose -f docker-compose.prod.yml exec postgres psql -U ncaaf_prod_user -d ncaaf_v5_prod

# Check tables
\dt

# Check teams
SELECT COUNT(*) FROM teams;

# Exit
\q
```

**Check Redis:**
```bash
docker-compose -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD

# Test
PING
# Expected: PONG

# Exit
exit
```

---

## Monitoring

### Health Checks
```bash
# Automated health check script
cat > health_check.sh << 'EOF'
#!/bin/bash
echo "Checking NCAAF v5.0 Services..."

# Ingestion Service
if curl -sf http://localhost:8080/health > /dev/null; then
    echo "✓ Ingestion Service: OK"
else
    echo "✗ Ingestion Service: FAILED"
fi

# ML Service
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "✓ ML Service: OK"
else
    echo "✗ ML Service: FAILED"
fi

# PostgreSQL
if docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready > /dev/null; then
    echo "✓ PostgreSQL: OK"
else
    echo "✗ PostgreSQL: FAILED"
fi

# Redis
if docker-compose -f docker-compose.prod.yml exec -T redis redis-cli -a $REDIS_PASSWORD ping > /dev/null 2>&1; then
    echo "✓ Redis: OK"
else
    echo "✗ Redis: FAILED"
fi
EOF

chmod +x health_check.sh
./health_check.sh
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f ingestion
docker-compose -f docker-compose.prod.yml logs -f ml_service

# Filter errors only
docker-compose -f docker-compose.prod.yml logs | grep ERROR

# Save logs
docker-compose -f docker-compose.prod.yml logs --no-color > logs_$(date +%Y%m%d).txt
```

### Resource Usage
```bash
# Container stats
docker stats

# Disk usage
docker system df

# Database size
docker-compose -f docker-compose.prod.yml exec postgres psql -U ncaaf_prod_user -d ncaaf_v5_prod -c "SELECT pg_size_pretty(pg_database_size('ncaaf_v5_prod'));"
```

---

## Backup & Recovery

### Database Backup
```bash
# Create backup
docker-compose -f docker-compose.prod.yml exec -T postgres pg_dump -U ncaaf_prod_user ncaaf_v5_prod | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Automated daily backup (add to crontab)
0 3 * * * cd /path/to/ncaaf_v5.0_BETA && docker-compose -f docker-compose.prod.yml exec -T postgres pg_dump -U ncaaf_prod_user ncaaf_v5_prod | gzip > backups/backup_$(date +\%Y\%m\%d).sql.gz && find backups/ -name "backup_*.sql.gz" -mtime +30 -delete
```

### Restore from Backup
```bash
# Stop services
docker-compose -f docker-compose.prod.yml stop ingestion ml_service

# Restore database
gunzip < backup_20241217.sql.gz | docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ncaaf_prod_user ncaaf_v5_prod

# Restart services
docker-compose -f docker-compose.prod.yml start ingestion ml_service
```

### Volume Backup
```bash
# Backup PostgreSQL data volume
docker run --rm -v ncaaf_v50beta_postgres_data_prod:/data -v $(pwd)/backups:/backup ubuntu tar czf /backup/postgres_volume_$(date +%Y%m%d).tar.gz /data

# Backup Redis data
docker run --rm -v ncaaf_v50beta_redis_data_prod:/data -v $(pwd)/backups:/backup ubuntu tar czf /backup/redis_volume_$(date +%Y%m%d).tar.gz /data
```

---

## Troubleshooting

### Services Won't Start
```bash
# Check Docker logs
docker-compose -f docker-compose.prod.yml logs

# Check individual service
docker-compose -f docker-compose.prod.yml logs ingestion

# Recreate containers
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

### Database Connection Issues
```bash
# Test database connection
docker-compose -f docker-compose.prod.yml exec postgres psql -U ncaaf_prod_user -d ncaaf_v5_prod -c "SELECT 1;"

# Check environment variables
docker-compose -f docker-compose.prod.yml exec ingestion env | grep DATABASE
```

### High Memory Usage
```bash
# Check container memory
docker stats --no-stream

# Restart services to clear memory
docker-compose -f docker-compose.prod.yml restart
```

### Migrations Failed
```bash
# Check migration status
migrate -path database/migrations -database "$DATABASE_URL" version

# Force to specific version
migrate -path database/migrations -database "$DATABASE_URL" force 1

# Retry migration
migrate -path database/migrations -database "$DATABASE_URL" up
```

---

## Production Checklist

Before going live, verify:

- [ ] All environment variables set in `.env.production`
- [ ] Strong passwords for database and Redis
- [ ] SSL/TLS enabled for database connections
- [ ] Firewall configured (only expose necessary ports)
- [ ] Health checks passing for all services
- [ ] Database migrations completed successfully
- [ ] Initial data sync completed
- [ ] ML models trained and loaded
- [ ] Test predictions working
- [ ] Logs configured and rotating
- [ ] Backups configured and tested
- [ ] Monitoring/alerting set up
- [ ] Resource limits configured
- [ ] Documentation updated

---

## Maintenance

### Update Application
```bash
# Pull latest changes
git pull origin main

# Rebuild images
docker-compose -f docker-compose.prod.yml build

# Rolling update (no downtime)
docker-compose -f docker-compose.prod.yml up -d --no-deps --build ingestion
docker-compose -f docker-compose.prod.yml up -d --no-deps --build ml_service
```

### Retrain Models (Weekly Recommended)
```bash
# Schedule with cron
0 4 * * 0 docker-compose -f /path/to/docker-compose.prod.yml exec -T ml_service python scripts/train_xgboost.py
```

---

## Support

For issues or questions:
- Check logs: `docker-compose -f docker-compose.prod.yml logs`
- Review documentation: `README.md`, `docs/`
- GitHub Issues: [project-url]/issues

---

**Last Updated:** December 2024
**Version:** 1.0.0
