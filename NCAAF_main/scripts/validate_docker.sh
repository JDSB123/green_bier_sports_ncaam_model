#!/bin/bash
# Production Readiness Validation - Docker Only
# All checks run through Docker containers

set -e

echo "===================================="
echo "NCAAF v5.0 Production Validation"
echo "All checks via Docker containers"
echo "===================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNED=0

pass_test() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((TESTS_PASSED++))
}

fail_test() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    [ -n "$2" ] && echo "  ${RED}→${NC} $2"
    ((TESTS_FAILED++))
}

warn_test() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
    ((TESTS_WARNED++))
}

info_test() {
    echo -e "${BLUE}ℹ INFO${NC}: $1"
}

# Determine which compose file to use
if [ -f "docker-compose.prod.yml" ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
    info_test "Using production compose file"
else
    COMPOSE_FILE="docker-compose.yml"
    warn_test "Using development compose file (docker-compose.prod.yml not found)"
fi

# ==============================================================================
# 1. Docker Services Status
# ==============================================================================
echo "1. Checking Docker services..."
if docker compose -f $COMPOSE_FILE ps 2>/dev/null | grep -q "Up"; then
    pass_test "Docker services are running"
    
    # Check each service
    for service in postgres redis ingestion ml_service; do
        if docker compose -f $COMPOSE_FILE ps | grep -q "$service.*Up"; then
            pass_test "Service '$service' is running"
        else
            fail_test "Service '$service' is not running"
        fi
    done
else
    fail_test "Docker services not running" "Start with: docker compose -f $COMPOSE_FILE up -d"
    echo ""
    echo "Starting services..."
    docker compose -f $COMPOSE_FILE up -d postgres redis
    sleep 5
fi

# ==============================================================================
# 2. Database Health (via Docker)
# ==============================================================================
echo ""
echo "2. Checking PostgreSQL (via Docker)..."
if docker compose -f $COMPOSE_FILE exec -T postgres pg_isready -U ${DATABASE_USER:-ncaaf_user} > /dev/null 2>&1; then
    pass_test "PostgreSQL is ready"
    
    # Test connection from ML service container
    if docker compose -f $COMPOSE_FILE run --rm ml_service python -c "
import os
import sys
from src.db.database import Database

try:
    db = Database()
    db.connect()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            result = cur.fetchone()
    db.close()
    print('Database connection successful')
    sys.exit(0)
except Exception as e:
    print(f'Database connection failed: {e}')
    sys.exit(1)
" 2>&1 | grep -q "successful"; then
        pass_test "ML service can connect to database"
    else
        fail_test "ML service cannot connect to database"
    fi
else
    fail_test "PostgreSQL not ready"
fi

# ==============================================================================
# 3. Database Schema (via Docker)
# ==============================================================================
echo ""
echo "3. Checking database schema (via Docker)..."
SCHEMA_CHECK=$(docker compose -f $COMPOSE_FILE run --rm ml_service python -c "
import sys
from src.db.database import Database

db = Database()
db.connect()

try:
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Check table count
            cur.execute(\"\"\"
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            \"\"\")
            table_count = cur.fetchone()[0]
            
            # Check critical tables
            critical_tables = ['teams', 'games', 'odds', 'predictions', 'team_season_stats']
            missing = []
            for table in critical_tables:
                cur.execute(\"\"\"
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                \"\"\", (table,))
                if not cur.fetchone()[0]:
                    missing.append(table)
            
            if missing:
                print(f'MISSING_TABLES:{','.join(missing)}')
                sys.exit(1)
            else:
                print(f'SCHEMA_OK:{table_count} tables')
                sys.exit(0)
except Exception as e:
    print(f'SCHEMA_ERROR:{e}')
    sys.exit(1)
finally:
    db.close()
" 2>&1)

if echo "$SCHEMA_CHECK" | grep -q "SCHEMA_OK"; then
    TABLE_COUNT=$(echo "$SCHEMA_CHECK" | grep "SCHEMA_OK" | cut -d: -f2)
    pass_test "Database schema exists ($TABLE_COUNT tables)"
    
    # Check individual tables
    for table in teams games odds predictions team_season_stats; do
        if docker compose -f $COMPOSE_FILE exec -T postgres psql -U ${DATABASE_USER:-ncaaf_user} -d ${DATABASE_NAME:-ncaaf_v5} -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '$table')" 2>/dev/null | grep -q "t"; then
            pass_test "Table '$table' exists"
        else
            fail_test "Table '$table' missing"
        fi
    done
elif echo "$SCHEMA_CHECK" | grep -q "MISSING_TABLES"; then
    MISSING=$(echo "$SCHEMA_CHECK" | grep "MISSING_TABLES" | cut -d: -f2)
    fail_test "Missing critical tables: $MISSING" "Run migrations"
else
    fail_test "Schema check failed" "$SCHEMA_CHECK"
fi

# ==============================================================================
# 4. Seed Data (via Docker)
# ==============================================================================
echo ""
echo "4. Checking seed data (via Docker)..."
DATA_CHECK=$(docker compose -f $COMPOSE_FILE run --rm ml_service python -c "
import sys
from src.db.database import Database

db = Database()
db.connect()

try:
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Check teams
            cur.execute('SELECT COUNT(*) FROM teams')
            team_count = cur.fetchone()[0]
            
            # Check stadiums
            cur.execute('SELECT COUNT(*) FROM stadiums')
            stadium_count = cur.fetchone()[0]
            
            # Check games
            cur.execute('SELECT COUNT(*) FROM games')
            game_count = cur.fetchone()[0]
            
            print(f'TEAMS:{team_count}')
            print(f'STADIUMS:{stadium_count}')
            print(f'GAMES:{game_count}')
            sys.exit(0)
except Exception as e:
    print(f'ERROR:{e}')
    sys.exit(1)
finally:
    db.close()
" 2>&1)

TEAM_COUNT=$(echo "$DATA_CHECK" | grep "TEAMS:" | cut -d: -f2)
STADIUM_COUNT=$(echo "$DATA_CHECK" | grep "STADIUMS:" | cut -d: -f2)
GAME_COUNT=$(echo "$DATA_CHECK" | grep "GAMES:" | cut -d: -f2)

if [ "$TEAM_COUNT" -gt "50" ]; then
    pass_test "Teams table populated ($TEAM_COUNT teams)"
else
    warn_test "Teams table has only $TEAM_COUNT teams (expected 50+)"
fi

if [ "$STADIUM_COUNT" -gt "50" ]; then
    pass_test "Stadiums table populated ($STADIUM_COUNT stadiums)"
else
    warn_test "Stadiums table has only $STADIUM_COUNT stadiums (expected 50+)"
fi

if [ "$GAME_COUNT" -gt "0" ]; then
    pass_test "Games data exists ($GAME_COUNT games)"
else
    warn_test "No games data yet"
fi

# ==============================================================================
# 5. Redis Health (via Docker)
# ==============================================================================
echo ""
echo "5. Checking Redis (via Docker)..."
if docker compose -f $COMPOSE_FILE exec -T redis redis-cli ${REDIS_PASSWORD:+-a $REDIS_PASSWORD} ping 2>/dev/null | grep -q "PONG"; then
    pass_test "Redis is responding"
    
    # Test from ML service
    if docker compose -f $COMPOSE_FILE run --rm ml_service python -c "
import redis
import os
import sys

try:
    r = redis.Redis(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        password=os.getenv('REDIS_PASSWORD') or None,
        decode_responses=True
    )
    r.ping()
    r.set('test_key', 'test_value', ex=10)
    value = r.get('test_key')
    r.delete('test_key')
    if value == 'test_value':
        print('Redis read/write successful')
        sys.exit(0)
    else:
        print('Redis read/write failed')
        sys.exit(1)
except Exception as e:
    print(f'Redis connection failed: {e}')
    sys.exit(1)
" 2>&1 | grep -q "successful"; then
        pass_test "ML service can connect to Redis"
    else
        fail_test "ML service cannot connect to Redis"
    fi
else
    fail_test "Redis not responding"
fi

# ==============================================================================
# 6. ML Models (via Docker)
# ==============================================================================
echo ""
echo "6. Checking ML models (via Docker)..."
MODEL_CHECK=$(docker compose -f $COMPOSE_FILE run --rm ml_service python -c "
import sys
from pathlib import Path
import joblib

model_dir = Path('/app/models')
models_found = []
models_missing = []

# Check enhanced models
enhanced_dir = model_dir / 'enhanced'
if enhanced_dir.exists():
    if (enhanced_dir / 'spread_model.pkl').exists():
        models_found.append('enhanced/spread_model.pkl')
        try:
            joblib.load(enhanced_dir / 'spread_model.pkl')
            print('ENHANCED_SPREAD:OK')
        except Exception as e:
            print(f'ENHANCED_SPREAD:ERROR:{e}')
    else:
        models_missing.append('enhanced/spread_model.pkl')
        print('ENHANCED_SPREAD:MISSING')
    
    if (enhanced_dir / 'total_model.pkl').exists():
        models_found.append('enhanced/total_model.pkl')
        try:
            joblib.load(enhanced_dir / 'total_model.pkl')
            print('ENHANCED_TOTAL:OK')
        except Exception as e:
            print(f'ENHANCED_TOTAL:ERROR:{e}')
    else:
        models_missing.append('enhanced/total_model.pkl')
        print('ENHANCED_TOTAL:MISSING')

# Check baseline models
baseline_dir = model_dir / 'baseline'
if baseline_dir.exists():
    if (baseline_dir / 'spread_model.pkl').exists():
        models_found.append('baseline/spread_model.pkl')
        print('BASELINE_SPREAD:OK')
    else:
        print('BASELINE_SPREAD:MISSING')
    
    if (baseline_dir / 'total_model.pkl').exists():
        models_found.append('baseline/total_model.pkl')
        print('BASELINE_TOTAL:OK')
    else:
        print('BASELINE_TOTAL:MISSING')

print(f'MODELS_FOUND:{len(models_found)}')
print(f'MODELS_MISSING:{len(models_missing)}')
" 2>&1)

if echo "$MODEL_CHECK" | grep -q "ENHANCED_SPREAD:OK"; then
    pass_test "Enhanced spread model exists and loads"
else
    fail_test "Enhanced spread model missing or invalid"
fi

if echo "$MODEL_CHECK" | grep -q "ENHANCED_TOTAL:OK"; then
    pass_test "Enhanced total model exists and loads"
else
    fail_test "Enhanced total model missing or invalid"
fi

# ==============================================================================
# 7. Service Health Endpoints (via Docker)
# ==============================================================================
echo ""
echo "7. Checking service health endpoints..."

# Check ML service health
ML_PORT=${ML_SERVICE_PORT:-8000}
if curl -sf http://localhost:$ML_PORT/health 2>/dev/null | grep -q "healthy"; then
    pass_test "ML service health endpoint responding"
else
    # Try from within container network
    if docker compose -f $COMPOSE_FILE exec -T ml_service wget -q -O- http://localhost:8000/health 2>/dev/null | grep -q "healthy"; then
        pass_test "ML service health endpoint responding (internal)"
    else
        fail_test "ML service health endpoint not responding"
    fi
fi

# Check ingestion service health
INGESTION_PORT=${INGESTION_PORT:-8080}
if curl -sf http://localhost:$INGESTION_PORT/health 2>/dev/null | grep -q "healthy"; then
    pass_test "Ingestion service health endpoint responding"
else
    if docker compose -f $COMPOSE_FILE exec -T ingestion wget -q -O- http://localhost:8080/health 2>/dev/null | grep -q "healthy"; then
        pass_test "Ingestion service health endpoint responding (internal)"
    else
        warn_test "Ingestion service health endpoint not responding"
    fi
fi

# ==============================================================================
# 8. API Endpoints (via Docker)
# ==============================================================================
echo ""
echo "8. Testing API endpoints (via Docker)..."
API_TEST=$(docker compose -f $COMPOSE_FILE run --rm ml_service python -c "
import sys
import requests
import os

try:
    base_url = f\"http://{os.getenv('DATABASE_HOST', 'ml_service')}:8000\"
    
    # Test health endpoint
    response = requests.get(f'{base_url}/health', timeout=5)
    if response.status_code == 200:
        print('HEALTH:OK')
    else:
        print(f'HEALTH:FAILED:{response.status_code}')
        sys.exit(1)
    
    # Test predictions endpoint (may return empty)
    try:
        response = requests.get(f'{base_url}/api/v1/predictions/week/2024/15', timeout=10)
        if response.status_code in [200, 404]:
            print('PREDICTIONS_API:OK')
        else:
            print(f'PREDICTIONS_API:ERROR:{response.status_code}')
    except Exception as e:
        print(f'PREDICTIONS_API:ERROR:{e}')
    
    sys.exit(0)
except Exception as e:
    print(f'API_TEST_ERROR:{e}')
    sys.exit(1)
" 2>&1 || echo "API_TEST_ERROR:Container test failed")

if echo "$API_TEST" | grep -q "HEALTH:OK"; then
    pass_test "Health API endpoint working"
else
    fail_test "Health API endpoint failed"
fi

# ==============================================================================
# 9. Feature Extraction (via Docker)
# ==============================================================================
echo ""
echo "9. Testing feature extraction (via Docker)..."
FEATURE_TEST=$(docker compose -f $COMPOSE_FILE run --rm ml_service python -c "
import sys
from src.db.database import Database
from src.features.feature_extractor_enhanced import EnhancedFeatureExtractor

db = Database()
db.connect()

try:
    extractor = EnhancedFeatureExtractor(db)
    
    # Try to extract features for a sample game
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT home_team_id, away_team_id, season, week FROM games LIMIT 1')
            result = cur.fetchone()
            
            if result:
                home_id, away_id, season, week = result
                features = extractor.extract_game_features(
                    home_team_id=home_id,
                    away_team_id=away_id,
                    season=season,
                    week=week
                )
                if features and len(features) > 0:
                    print(f'FEATURE_EXTRACTION:OK:{len(features)} features')
                else:
                    print('FEATURE_EXTRACTION:FAILED:No features extracted')
            else:
                print('FEATURE_EXTRACTION:SKIP:No games in database')
    
    sys.exit(0)
except Exception as e:
    print(f'FEATURE_EXTRACTION:ERROR:{e}')
    sys.exit(1)
finally:
    db.close()
" 2>&1)

if echo "$FEATURE_TEST" | grep -q "FEATURE_EXTRACTION:OK"; then
    FEATURE_COUNT=$(echo "$FEATURE_TEST" | grep "FEATURE_EXTRACTION:OK" | cut -d: -f3)
    pass_test "Feature extraction working ($FEATURE_COUNT features)"
elif echo "$FEATURE_TEST" | grep -q "FEATURE_EXTRACTION:SKIP"; then
    warn_test "Feature extraction skipped (no games data)"
else
    fail_test "Feature extraction failed"
fi

# ==============================================================================
# 10. Predictions Generation (via Docker)
# ==============================================================================
echo ""
echo "10. Testing predictions generation (via Docker)..."
PREDICTION_TEST=$(docker compose -f $COMPOSE_FILE run --rm ml_service python -c "
import sys
from src.db.database import Database
from src.models.predictor_enhanced import EnsembleNCAAFPredictor
from src.features.feature_extractor_enhanced import EnhancedFeatureExtractor

db = Database()
db.connect()

try:
    predictor = EnsembleNCAAFPredictor()
    predictor.load_models()
    extractor = EnhancedFeatureExtractor(db)
    
    # Try to generate a prediction
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT home_team_id, away_team_id, season, week FROM games WHERE status = \'Scheduled\' LIMIT 1')
            result = cur.fetchone()
            
            if result:
                home_id, away_id, season, week = result
                features = extractor.extract_game_features(
                    home_team_id=home_id,
                    away_team_id=away_id,
                    season=season,
                    week=week
                )
                
                prediction = predictor.predict(features, use_monte_carlo=True, use_ensemble=True)
                
                if prediction and 'predicted_margin' in prediction:
                    print('PREDICTION_GENERATION:OK')
                else:
                    print('PREDICTION_GENERATION:FAILED:Invalid prediction')
            else:
                print('PREDICTION_GENERATION:SKIP:No scheduled games')
    
    sys.exit(0)
except Exception as e:
    print(f'PREDICTION_GENERATION:ERROR:{e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
" 2>&1)

if echo "$PREDICTION_TEST" | grep -q "PREDICTION_GENERATION:OK"; then
    pass_test "Predictions generation working"
elif echo "$PREDICTION_TEST" | grep -q "PREDICTION_GENERATION:SKIP"; then
    warn_test "Predictions generation skipped (no scheduled games)"
else
    fail_test "Predictions generation failed"
    echo "  Details: $PREDICTION_TEST"
fi

# ==============================================================================
# 11. Backtesting System (via Docker)
# ==============================================================================
echo ""
echo "11. Checking backtesting system (via Docker)..."
BACKTEST_CHECK=$(docker compose -f $COMPOSE_FILE run --rm ml_service python -c "
import sys
from pathlib import Path

# Check if backtest script exists
backtest_script = Path('/app/scripts/backtest_enhanced.py')
if backtest_script.exists():
    print('BACKTEST_SCRIPT:EXISTS')
    
    # Check if backtest tables exist
    from src.db.database import Database
    db = Database()
    db.connect()
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(\"\"\"
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'backtests'
                    )
                \"\"\")
                if cur.fetchone()[0]:
                    print('BACKTEST_TABLES:EXISTS')
                else:
                    print('BACKTEST_TABLES:MISSING')
    finally:
        db.close()
else:
    print('BACKTEST_SCRIPT:MISSING')
" 2>&1)

if echo "$BACKTEST_CHECK" | grep -q "BACKTEST_SCRIPT:EXISTS"; then
    pass_test "Backtesting script exists"
    if echo "$BACKTEST_CHECK" | grep -q "BACKTEST_TABLES:EXISTS"; then
        pass_test "Backtesting database tables exist"
    else
        warn_test "Backtesting tables missing (run migrations)"
    fi
else
    fail_test "Backtesting script missing"
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
echo -e "${YELLOW}Warnings:${NC} $TESTS_WARNED"
TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
if [ $TOTAL_TESTS -gt 0 ]; then
    SUCCESS_RATE=$((TESTS_PASSED * 100 / TOTAL_TESTS))
    echo "Success Rate: ${SUCCESS_RATE}%"
fi
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    if [ $TESTS_WARNED -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed! System is production ready.${NC}"
        exit 0
    else
        echo -e "${YELLOW}⚠ All critical tests passed, but some warnings exist.${NC}"
        echo -e "${YELLOW}  Review warnings above before production deployment.${NC}"
        exit 0
    fi
else
    echo -e "${RED}✗ Some tests failed. Please review and fix issues.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review failed tests above"
    echo "  2. Check service logs: docker compose -f $COMPOSE_FILE logs"
    echo "  3. Consult DEPLOYMENT.md for troubleshooting"
    exit 1
fi
