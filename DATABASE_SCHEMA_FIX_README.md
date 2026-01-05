# Database Schema Fix - Sustainable Solution

## Problem
Deployed databases can become out-of-sync with application code when the migration system detects existing schema and skips applying newer migrations.

## Root Cause
The migration system's safety-first approach:
- ✅ **Safe**: Won't overwrite existing data
- ❌ **Incomplete**: Won't apply missing schema updates to existing DBs

## Symptoms
- API returns `column br.pick_price does not exist` errors
- Health checks show `missing_migrations` warnings
- Weekly lineup integration fails

## Sustainable Fix

### 1. Force Migration Application
```bash
# Option A: Use deployment script
.\azure\deploy.ps1 -ForceMigrations -QuickDeploy

# Option B: Manual container exec
az containerapp exec --name ncaam-stable-prediction \
  --resource-group NCAAM-GBSV-MODEL-RG \
  --command "cd /app && FORCE_MISSING_MIGRATIONS=true python run_migrations.py"
```

### 2. Schema Validation
Health checks now include database schema validation:
```json
{
  "status": "ok",
  "database": {
    "connected": true,
    "schema_valid": true
  }
}
```

### 3. Prevention Measures

#### A. Environment Variable Override
Set `FORCE_MISSING_MIGRATIONS=true` to bypass baseline logic:
```bash
export FORCE_MISSING_MIGRATIONS=true
python run_migrations.py
```

#### B. Deployment Health Checks
Run before deployment:
```bash
python scripts/check_deployment_health.py
```

#### C. Migration Force Script
Apply specific migrations safely:
```bash
python services/prediction-service-python/scripts/force_migration_fix.py
```

## Files Added/Modified

### New Files
- `scripts/check_deployment_health.py` - Pre-deployment validation
- `services/prediction-service-python/scripts/force_migration_fix.py` - Safe migration forcing

### Modified Files
- `services/prediction-service-python/run_migrations.py` - Added FORCE_MISSING_MIGRATIONS support
- `services/prediction-service-python/app/main.py` - Enhanced health checks with schema validation
- `azure/deploy.ps1` - Added ForceMigrations parameter and schema validation

## Future Prevention

### 1. Deployment Pipeline Integration
```yaml
# Add to CI/CD pipeline
- name: Check deployment health
  run: python scripts/check_deployment_health.py

- name: Apply missing migrations
  run: python services/prediction-service-python/scripts/force_migration_fix.py
  if: failure()
```

### 2. Monitoring Alerts
Schema validation is now part of health checks - monitor for:
- `status: "degraded"`
- `database.missing_migrations`

### 3. Documentation Updates
- Update deployment docs to include schema validation steps
- Document the migration force procedure
- Add troubleshooting guide for schema issues

## Testing

### Health Check Verification
```bash
curl https://ncaam-stable-prediction.../health
# Should show: "database": {"connected": true, "schema_valid": true}
```

### API Functionality Test
```bash
curl https://ncaam-stable-prediction.../api/picks/today
# Should return picks array instead of DB error
```

### Migration Verification
```bash
# Check applied migrations
python -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute('SELECT filename FROM public.schema_migrations ORDER BY filename;')
print('Applied:', [row[0] for row in cur.fetchall()])
cur.close(); conn.close()
"
```

## Summary

This fix provides a **sustainable, production-safe solution** to database schema drift:

1. **Detection**: Health checks identify missing migrations
2. **Recovery**: Force migration option safely applies missing schema
3. **Prevention**: Enhanced validation prevents future occurrences
4. **Monitoring**: Continuous schema validation in production

The solution maintains data safety while ensuring schema consistency across environments.