#!/bin/bash
# End-to-End Pipeline Validation Script
# Tests the complete NCAAF v5.0 data flow from ingestion to predictions

set -e

echo "===================================="
echo "NCAAF v5.0 Pipeline Validation"
echo "===================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
pass_test() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((TESTS_PASSED++))
}

fail_test() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    echo "  Error: $2"
    ((TESTS_FAILED++))
}

warn_test() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

# Load environment
if [ -f .env.production ]; then
    export $(cat .env.production | grep -v '^#' | xargs)
else
    warn_test ".env.production not found, using defaults"
fi

echo "Testing Production Deployment..."
echo ""

# ==============================================================================
# Test 1: Docker Services Running
# ==============================================================================
echo "1. Checking Docker services..."

if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
    pass_test "Docker services are running"
else
    fail_test "Docker services not running" "Run: docker-compose -f docker-compose.prod.yml up -d"
fi

# ==============================================================================
# Test 2: PostgreSQL Health
# ==============================================================================
echo ""
echo "2. Checking PostgreSQL..."

if docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready > /dev/null 2>&1; then
    pass_test "PostgreSQL is ready"

    # Check database exists
    if docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ${DATABASE_USER:-ncaaf_user} -d ${DATABASE_NAME:-ncaaf_v5} -c "SELECT 1" > /dev/null 2>&1; then
        pass_test "Database connection successful"
    else
        fail_test "Cannot connect to database" "Check DATABASE_* environment variables"
    fi
else
    fail_test "PostgreSQL not ready" "Check postgres container logs"
fi

# ==============================================================================
# Test 3: Redis Health
# ==============================================================================
echo ""
echo "3. Checking Redis..."

if docker-compose -f docker-compose.prod.yml exec -T redis redis-cli -a ${REDIS_PASSWORD} ping 2>/dev/null | grep -q "PONG"; then
    pass_test "Redis is responding"
else
    fail_test "Redis not responding" "Check redis container and REDIS_PASSWORD"
fi

# ==============================================================================
# Test 4: Database Schema
# ==============================================================================
echo ""
echo "4. Checking database schema..."

TABLES=$(docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ${DATABASE_USER:-ncaaf_user} -d ${DATABASE_NAME:-ncaaf_v5} -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'" 2>/dev/null | tr -d ' ')

if [ "$TABLES" -gt "0" ]; then
    pass_test "Database schema exists ($TABLES tables)"

    # Check critical tables
    CRITICAL_TABLES=("teams" "games" "odds" "predictions" "team_season_stats")
    for table in "${CRITICAL_TABLES[@]}"; do
        if docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ${DATABASE_USER:-ncaaf_user} -d ${DATABASE_NAME:-ncaaf_v5} -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '$table')" 2>/dev/null | grep -q "t"; then
            pass_test "Table '$table' exists"
        else
            fail_test "Missing table '$table'" "Run migrations: make migrate-up"
        fi
    done
else
    fail_test "No database schema found" "Run migrations: make migrate-up"
fi

# ==============================================================================
# Test 5: Seed Data
# ==============================================================================
echo ""
echo "5. Checking seed data..."

TEAM_COUNT=$(docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ${DATABASE_USER:-ncaaf_user} -d ${DATABASE_NAME:-ncaaf_v5} -t -c "SELECT COUNT(*) FROM teams" 2>/dev/null | tr -d ' ')

if [ "$TEAM_COUNT" -gt "0" ]; then
    pass_test "Teams table populated ($TEAM_COUNT teams)"
else
    warn_test "Teams table is empty - run: ./scripts/seed_all.sh"
fi

STADIUM_COUNT=$(docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ${DATABASE_USER:-ncaaf_user} -d ${DATABASE_NAME:-ncaaf_v5} -t -c "SELECT COUNT(*) FROM stadiums" 2>/dev/null | tr -d ' ')

if [ "$STADIUM_COUNT" -gt "0" ]; then
    pass_test "Stadiums table populated ($STADIUM_COUNT stadiums)"
else
    warn_test "Stadiums table is empty - run: ./scripts/seed_all.sh"
fi

# ==============================================================================
# Test 6: Ingestion Service Health
# ==============================================================================
echo ""
echo "6. Checking Ingestion Service..."

INGESTION_HEALTH=$(curl -sf http://localhost:${INGESTION_PORT:-8080}/health 2>/dev/null || echo "failed")

if echo "$INGESTION_HEALTH" | grep -q "healthy"; then
    pass_test "Ingestion service is healthy"
else
    fail_test "Ingestion service health check failed" "Check ingestion container logs"
fi

# ==============================================================================
# Test 7: ML Service Health
# ==============================================================================
echo ""
echo "7. Checking ML Service..."

ML_HEALTH=$(curl -sf http://localhost:${ML_SERVICE_PORT:-8000}/health 2>/dev/null || echo "failed")

if echo "$ML_HEALTH" | grep -q "healthy"; then
    pass_test "ML service is healthy"
else
    fail_test "ML service health check failed" "Check ml_service container logs"
fi

# ==============================================================================
# Test 8: ML Models Exist
# ==============================================================================
echo ""
echo "8. Checking ML models..."

MODEL_FILES=("xgboost_margin.pkl" "xgboost_total.pkl" "xgboost_home_score.pkl" "xgboost_away_score.pkl")

for model in "${MODEL_FILES[@]}"; do
    if docker-compose -f docker-compose.prod.yml exec -T ml_service test -f /app/models/$model; then
        pass_test "Model '$model' exists"
    else
        warn_test "Model '$model' not found - run: docker-compose exec ml_service python scripts/train_xgboost.py"
    fi
done

# ==============================================================================
# Test 9: API Endpoints
# ==============================================================================
echo ""
echo "9. Testing API endpoints..."

# Test predictions endpoint (may return empty if no games)
PREDICTIONS_RESPONSE=$(curl -sf http://localhost:${ML_SERVICE_PORT:-8000}/api/v1/predictions/week/2024/15 2>/dev/null || echo "failed")

if [ "$PREDICTIONS_RESPONSE" != "failed" ]; then
    pass_test "Predictions API endpoint responding"
else
    fail_test "Predictions API endpoint not responding" "Check ML service logs"
fi

# ==============================================================================
# Test 10: End-to-End Data Flow
# ==============================================================================
echo ""
echo "10. Testing end-to-end data flow..."

# Check if any games exist in database
GAME_COUNT=$(docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ${DATABASE_USER:-ncaaf_user} -d ${DATABASE_NAME:-ncaaf_v5} -t -c "SELECT COUNT(*) FROM games" 2>/dev/null | tr -d ' ')

if [ "$GAME_COUNT" -gt "0" ]; then
    pass_test "Games data exists ($GAME_COUNT games)"

    # Check if odds exist
    ODDS_COUNT=$(docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ${DATABASE_USER:-ncaaf_user} -d ${DATABASE_NAME:-ncaaf_v5} -t -c "SELECT COUNT(*) FROM odds" 2>/dev/null | tr -d ' ')

    if [ "$ODDS_COUNT" -gt "0" ]; then
        pass_test "Odds data exists ($ODDS_COUNT records)"
    else
        warn_test "No odds data - will be populated on next sync"
    fi

    # Check if predictions exist
    PRED_COUNT=$(docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ${DATABASE_USER:-ncaaf_user} -d ${DATABASE_NAME:-ncaaf_v5} -t -c "SELECT COUNT(*) FROM predictions" 2>/dev/null | tr -d ' ')

    if [ "$PRED_COUNT" -gt "0" ]; then
        pass_test "Predictions data exists ($PRED_COUNT predictions)"
    else
        warn_test "No predictions - ML models may need training or games may not have odds yet"
    fi
else
    warn_test "No games data - run initial sync or wait for scheduled sync"
fi

# ==============================================================================
# Test 11: Caching
# ==============================================================================
echo ""
echo "11. Testing Redis caching..."

# Try to set and get a test key
if docker-compose -f docker-compose.prod.yml exec -T redis redis-cli -a ${REDIS_PASSWORD} SET test_key "test_value" 2>/dev/null | grep -q "OK"; then
    if docker-compose -f docker-compose.prod.yml exec -T redis redis-cli -a ${REDIS_PASSWORD} GET test_key 2>/dev/null | grep -q "test_value"; then
        pass_test "Redis read/write operations working"
        docker-compose -f docker-compose.prod.yml exec -T redis redis-cli -a ${REDIS_PASSWORD} DEL test_key > /dev/null 2>&1
    else
        fail_test "Redis read operation failed"
    fi
else
    fail_test "Redis write operation failed"
fi

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo "===================================="
echo "Validation Summary"
echo "===================================="
echo ""
echo -e "${GREEN}Passed:${NC} $TESTS_PASSED"
echo -e "${RED}Failed:${NC} $TESTS_FAILED"
TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
SUCCESS_RATE=$((TESTS_PASSED * 100 / TOTAL_TESTS))
echo "Success Rate: ${SUCCESS_RATE}%"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical tests passed! System is ready for production.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review and fix issues before production deployment.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review failed tests above"
    echo "  2. Check service logs: docker-compose -f docker-compose.prod.yml logs"
    echo "  3. Consult DEPLOYMENT.md for troubleshooting"
    exit 1
fi
