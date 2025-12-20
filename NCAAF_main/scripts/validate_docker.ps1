# Production Readiness Validation - Docker Only
# All checks run through Docker containers

$ErrorActionPreference = "Stop"

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "NCAAF v5.0 Production Validation" -ForegroundColor Cyan
Write-Host "All checks via Docker containers" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

$TESTS_PASSED = 0
$TESTS_FAILED = 0
$TESTS_WARNED = 0

function Pass-Test {
    param([string]$Message)
    Write-Host "✓ PASS: $Message" -ForegroundColor Green
    $script:TESTS_PASSED++
}

function Fail-Test {
    param([string]$Message, [string]$Error = "")
    Write-Host "✗ FAIL: $Message" -ForegroundColor Red
    if ($Error) {
        Write-Host "  → $Error" -ForegroundColor Red
    }
    $script:TESTS_FAILED++
}

function Warn-Test {
    param([string]$Message)
    Write-Host "⚠ WARN: $Message" -ForegroundColor Yellow
    $script:TESTS_WARNED++
}

function Info-Test {
    param([string]$Message)
    Write-Host "ℹ INFO: $Message" -ForegroundColor Blue
}

# Determine which compose file to use
$COMPOSE_FILE = "docker-compose.yml"
if (Test-Path "docker-compose.prod.yml") {
    $COMPOSE_FILE = "docker-compose.prod.yml"
    Info-Test "Using production compose file"
} else {
    Warn-Test "Using development compose file (docker-compose.prod.yml not found)"
}

# ==============================================================================
# 1. Docker Services Status
# ==============================================================================
Write-Host "1. Checking Docker services..." -ForegroundColor Cyan
$services = docker compose -f $COMPOSE_FILE ps 2>&1
if ($LASTEXITCODE -eq 0 -and $services -match "Up") {
    Pass-Test "Docker services are running"
    
    $serviceList = @("postgres", "redis", "ingestion", "ml_service")
    foreach ($service in $serviceList) {
        if ($services -match "$service.*Up") {
            Pass-Test "Service '$service' is running"
        } else {
            Fail-Test "Service '$service' is not running"
        }
    }
} else {
    Fail-Test "Docker services not running" "Start with: docker compose -f $COMPOSE_FILE up -d"
    Write-Host "Starting services..." -ForegroundColor Yellow
    docker compose -f $COMPOSE_FILE up -d postgres redis
    Start-Sleep -Seconds 5
}

# ==============================================================================
# 2. Database Health (via Docker)
# ==============================================================================
Write-Host ""
Write-Host "2. Checking PostgreSQL (via Docker)..." -ForegroundColor Cyan
$dbCheck = docker compose -f $COMPOSE_FILE exec -T postgres pg_isready -U ncaaf_user 2>&1
if ($LASTEXITCODE -eq 0) {
    Pass-Test "PostgreSQL is ready"
    
    # Test connection from ML service container
    $mlDbTest = docker compose -f $COMPOSE_FILE run --rm ml_service python -c @"
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
"@ 2>&1
    
    if ($mlDbTest -match "successful") {
        Pass-Test "ML service can connect to database"
    } else {
        Fail-Test "ML service cannot connect to database"
    }
} else {
    Fail-Test "PostgreSQL not ready"
}

# ==============================================================================
# 3. Database Schema (via Docker)
# ==============================================================================
Write-Host ""
Write-Host "3. Checking database schema (via Docker)..." -ForegroundColor Cyan
$schemaCheck = docker compose -f $COMPOSE_FILE run --rm ml_service python -c @"
import sys
from src.db.database import Database

db = Database()
db.connect()

try:
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Check table count
            cur.execute('''
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            ''')
            table_count = cur.fetchone()[0]
            
            # Check critical tables
            critical_tables = ['teams', 'games', 'odds', 'predictions', 'team_season_stats']
            missing = []
            for table in critical_tables:
                cur.execute('''
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                ''', (table,))
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
"@ 2>&1

if ($schemaCheck -match "SCHEMA_OK:(\d+)") {
    $tableCount = $matches[1]
    Pass-Test "Database schema exists ($tableCount tables)"
    
    # Check individual tables
    $tables = @("teams", "games", "odds", "predictions", "team_season_stats")
    foreach ($table in $tables) {
        $tableCheck = docker compose -f $COMPOSE_FILE exec -T postgres psql -U ncaaf_user -d ncaaf_v5 -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '$table')" 2>&1
        if ($tableCheck -match "t") {
            Pass-Test "Table '$table' exists"
        } else {
            Fail-Test "Table '$table' missing"
        }
    }
} elseif ($schemaCheck -match "MISSING_TABLES:(.+)") {
    $missing = $matches[1]
    Fail-Test "Missing critical tables: $missing" "Run migrations"
} else {
    Fail-Test "Schema check failed" $schemaCheck
}

# ==============================================================================
# 4. Seed Data (via Docker)
# ==============================================================================
Write-Host ""
Write-Host "4. Checking seed data (via Docker)..." -ForegroundColor Cyan
$dataCheck = docker compose -f $COMPOSE_FILE run --rm ml_service python -c @"
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
"@ 2>&1

$teamCount = 0
$stadiumCount = 0
$gameCount = 0

if ($dataCheck -match "TEAMS:(\d+)") {
    $teamCount = [int]$matches[1]
}
if ($dataCheck -match "STADIUMS:(\d+)") {
    $stadiumCount = [int]$matches[1]
}
if ($dataCheck -match "GAMES:(\d+)") {
    $gameCount = [int]$matches[1]
}

if ($teamCount -gt 50) {
    Pass-Test "Teams table populated ($teamCount teams)"
} else {
    Warn-Test "Teams table has only $teamCount teams (expected 50+)"
}

if ($stadiumCount -gt 50) {
    Pass-Test "Stadiums table populated ($stadiumCount stadiums)"
} else {
    Warn-Test "Stadiums table has only $stadiumCount stadiums (expected 50+)"
}

if ($gameCount -gt 0) {
    Pass-Test "Games data exists ($gameCount games)"
} else {
    Warn-Test "No games data yet"
}

# ==============================================================================
# 5. Redis Health (via Docker)
# ==============================================================================
Write-Host ""
Write-Host "5. Checking Redis (via Docker)..." -ForegroundColor Cyan
$redisCheck = docker compose -f $COMPOSE_FILE exec -T redis redis-cli ping 2>&1
if ($redisCheck -match "PONG") {
    Pass-Test "Redis is responding"
    
    # Test from ML service
    $mlRedisTest = docker compose -f $COMPOSE_FILE run --rm ml_service python -c @"
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
"@ 2>&1
    
    if ($mlRedisTest -match "successful") {
        Pass-Test "ML service can connect to Redis"
    } else {
        Fail-Test "ML service cannot connect to Redis"
    }
} else {
    Fail-Test "Redis not responding"
}

# ==============================================================================
# 6. ML Models (via Docker)
# ==============================================================================
Write-Host ""
Write-Host "6. Checking ML models (via Docker)..." -ForegroundColor Cyan
$modelCheck = docker compose -f $COMPOSE_FILE run --rm ml_service python -c @"
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
"@ 2>&1

if ($modelCheck -match "ENHANCED_SPREAD:OK") {
    Pass-Test "Enhanced spread model exists and loads"
} else {
    Fail-Test "Enhanced spread model missing or invalid"
}

if ($modelCheck -match "ENHANCED_TOTAL:OK") {
    Pass-Test "Enhanced total model exists and loads"
} else {
    Fail-Test "Enhanced total model missing or invalid"
}

# ==============================================================================
# 7. Service Health Endpoints (via Docker)
# ==============================================================================
Write-Host ""
Write-Host "7. Checking service health endpoints..." -ForegroundColor Cyan

# Check ML service health
try {
    $mlHealth = Invoke-WebRequest -Uri "http://localhost:8001/health" -TimeoutSec 5 -UseBasicParsing 2>&1
    if ($mlHealth.StatusCode -eq 200 -and $mlHealth.Content -match "healthy") {
        Pass-Test "ML service health endpoint responding"
    } else {
        # Try from within container network
        $mlHealthInternal = docker compose -f $COMPOSE_FILE exec -T ml_service wget -q -O- http://localhost:8000/health 2>&1
        if ($mlHealthInternal -match "healthy") {
            Pass-Test "ML service health endpoint responding (internal)"
        } else {
            Fail-Test "ML service health endpoint not responding"
        }
    }
} catch {
    # Try from within container network
    $mlHealthInternal = docker compose -f $COMPOSE_FILE exec -T ml_service wget -q -O- http://localhost:8000/health 2>&1
    if ($mlHealthInternal -match "healthy") {
        Pass-Test "ML service health endpoint responding (internal)"
    } else {
        Fail-Test "ML service health endpoint not responding"
    }
}

# Check ingestion service health
try {
    $ingestionHealth = Invoke-WebRequest -Uri "http://localhost:8083/health" -TimeoutSec 5 -UseBasicParsing 2>&1
    if ($ingestionHealth.StatusCode -eq 200 -and $ingestionHealth.Content -match "healthy") {
        Pass-Test "Ingestion service health endpoint responding"
    } else {
        $ingestionHealthInternal = docker compose -f $COMPOSE_FILE exec -T ingestion wget -q -O- http://localhost:8080/health 2>&1
        if ($ingestionHealthInternal -match "healthy") {
            Pass-Test "Ingestion service health endpoint responding (internal)"
        } else {
            Warn-Test "Ingestion service health endpoint not responding"
        }
    }
} catch {
    $ingestionHealthInternal = docker compose -f $COMPOSE_FILE exec -T ingestion wget -q -O- http://localhost:8080/health 2>&1
    if ($ingestionHealthInternal -match "healthy") {
        Pass-Test "Ingestion service health endpoint responding (internal)"
    } else {
        Warn-Test "Ingestion service health endpoint not responding"
    }
}

# ==============================================================================
# 8. API Endpoints (via Docker)
# ==============================================================================
Write-Host ""
Write-Host "8. Testing API endpoints (via Docker)..." -ForegroundColor Cyan
$apiTest = docker compose -f $COMPOSE_FILE run --rm ml_service python -c @"
import sys
import requests
import os

try:
    base_url = 'http://ml_service:8000'
    
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
"@ 2>&1

if ($apiTest -match "HEALTH:OK") {
    Pass-Test "Health API endpoint working"
} else {
    Fail-Test "Health API endpoint failed"
}

# ==============================================================================
# 9. Feature Extraction (via Docker)
# ==============================================================================
Write-Host ""
Write-Host "9. Testing feature extraction (via Docker)..." -ForegroundColor Cyan
$featureTest = docker compose -f $COMPOSE_FILE run --rm ml_service python -c @"
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
"@ 2>&1

if ($featureTest -match "FEATURE_EXTRACTION:OK:(\d+)") {
    $featureCount = $matches[1]
    Pass-Test "Feature extraction working ($featureCount features)"
} elseif ($featureTest -match "FEATURE_EXTRACTION:SKIP") {
    Warn-Test "Feature extraction skipped (no games data)"
} else {
    Fail-Test "Feature extraction failed"
}

# ==============================================================================
# 10. Predictions Generation (via Docker)
# ==============================================================================
Write-Host ""
Write-Host "10. Testing predictions generation (via Docker)..." -ForegroundColor Cyan
$predictionTest = docker compose -f $COMPOSE_FILE run --rm ml_service python -c @"
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
            cur.execute('SELECT home_team_id, away_team_id, season, week FROM games WHERE status = ''Scheduled'' LIMIT 1')
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
"@ 2>&1

if ($predictionTest -match "PREDICTION_GENERATION:OK") {
    Pass-Test "Predictions generation working"
} elseif ($predictionTest -match "PREDICTION_GENERATION:SKIP") {
    Warn-Test "Predictions generation skipped (no scheduled games)"
} else {
    Fail-Test "Predictions generation failed"
    Write-Host "  Details: $predictionTest" -ForegroundColor Red
}

# ==============================================================================
# 11. Backtesting System (via Docker)
# ==============================================================================
Write-Host ""
Write-Host "11. Checking backtesting system (via Docker)..." -ForegroundColor Cyan
$backtestCheck = docker compose -f $COMPOSE_FILE run --rm ml_service python -c @"
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
                cur.execute('''
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'backtests'
                    )
                ''')
                if cur.fetchone()[0]:
                    print('BACKTEST_TABLES:EXISTS')
                else:
                    print('BACKTEST_TABLES:MISSING')
    finally:
        db.close()
else:
    print('BACKTEST_SCRIPT:MISSING')
"@ 2>&1

if ($backtestCheck -match "BACKTEST_SCRIPT:EXISTS") {
    Pass-Test "Backtesting script exists"
    if ($backtestCheck -match "BACKTEST_TABLES:EXISTS") {
        Pass-Test "Backtesting database tables exist"
    } else {
        Warn-Test "Backtesting tables missing (run migrations)"
    }
} else {
    Fail-Test "Backtesting script missing"
}

# ==============================================================================
# Summary
# ==============================================================================
Write-Host ""
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Validation Summary" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Passed: $TESTS_PASSED" -ForegroundColor Green
Write-Host "Failed: $TESTS_FAILED" -ForegroundColor Red
Write-Host "Warnings: $TESTS_WARNED" -ForegroundColor Yellow

$TOTAL_TESTS = $TESTS_PASSED + $TESTS_FAILED
if ($TOTAL_TESTS -gt 0) {
    $SUCCESS_RATE = [math]::Round(($TESTS_PASSED / $TOTAL_TESTS) * 100, 1)
    Write-Host "Success Rate: ${SUCCESS_RATE}%"
}
Write-Host ""

if ($TESTS_FAILED -eq 0) {
    if ($TESTS_WARNED -eq 0) {
        Write-Host "✓ All tests passed! System is production ready." -ForegroundColor Green
        exit 0
    } else {
        Write-Host "⚠ All critical tests passed, but some warnings exist." -ForegroundColor Yellow
        Write-Host "  Review warnings above before production deployment." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "✗ Some tests failed. Please review and fix issues." -ForegroundColor Red
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Review failed tests above"
    Write-Host "  2. Check service logs: docker compose -f $COMPOSE_FILE logs"
    Write-Host "  3. Consult DEPLOYMENT.md for troubleshooting"
    exit 1
}
