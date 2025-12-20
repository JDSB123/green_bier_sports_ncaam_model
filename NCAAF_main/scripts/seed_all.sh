#!/bin/bash
# Seed all initial data for NCAAF v5.0
# Usage: ./scripts/seed_all.sh

set -e

echo "===================================="
echo "NCAAF v5.0 - Seed Data Script"
echo "===================================="

# Load environment variables if .env.production exists
if [ -f .env.production ]; then
    echo "Loading production environment..."
    export $(cat .env.production | grep -v '^#' | xargs)
else
    echo "Warning: .env.production not found, using default values"
    export DATABASE_USER=${DATABASE_USER:-ncaaf_user}
    export DATABASE_PASSWORD=${DATABASE_PASSWORD:-ncaaf_password}
    export DATABASE_NAME=${DATABASE_NAME:-ncaaf_v5}
    export DATABASE_HOST=${DATABASE_HOST:-localhost}
    export DATABASE_PORT=${DATABASE_PORT:-5432}
fi

# Build connection string
DB_CONN="postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@${DATABASE_HOST}:${DATABASE_PORT}/${DATABASE_NAME}"

echo ""
echo "Database: ${DATABASE_NAME}@${DATABASE_HOST}:${DATABASE_PORT}"
echo "User: ${DATABASE_USER}"
echo ""

# Test database connection
echo "Testing database connection..."
if ! psql "$DB_CONN" -c "SELECT 1" > /dev/null 2>&1; then
    echo "ERROR: Cannot connect to database!"
    echo "Please ensure:"
    echo "  1. PostgreSQL is running"
    echo "  2. Database '${DATABASE_NAME}' exists"
    echo "  3. User '${DATABASE_USER}' has access"
    exit 1
fi
echo "✓ Database connection successful"

# Seed teams
echo ""
echo "Seeding teams..."
psql "$DB_CONN" -f scripts/seed_teams.sql
echo "✓ Teams seeded successfully"

# Seed stadiums
echo ""
echo "Seeding stadiums..."
psql "$DB_CONN" -f scripts/seed_stadiums.sql
echo "✓ Stadiums seeded successfully"

# Verify data
echo ""
echo "===================================="
echo "Verification"
echo "===================================="
psql "$DB_CONN" -c "SELECT 'Teams: ' || COUNT(*)::TEXT FROM teams;"
psql "$DB_CONN" -c "SELECT 'Stadiums: ' || COUNT(*)::TEXT FROM stadiums;"

echo ""
echo "===================================="
echo "Seed complete!"
echo "===================================="
echo ""
echo "Summary:"
psql "$DB_CONN" -c "
SELECT
    conference,
    COUNT(*) as teams,
    ROUND(AVG(talent_composite)::numeric, 1) as avg_talent
FROM teams
WHERE conference IS NOT NULL
GROUP BY conference
ORDER BY avg_talent DESC;
"

echo ""
echo "Next steps:"
echo "  1. Run initial sync: docker-compose exec ingestion /app/worker --initial-sync"
echo "  2. Train ML models: docker-compose exec ml_service python scripts/train_xgboost.py"
echo "  3. Check health: curl http://localhost:8080/health"
