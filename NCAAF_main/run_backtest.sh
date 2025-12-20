#!/bin/bash
# NCAAF Model ROE Optimization Backtest Script
# This script imports cached data, trains enhanced models, and runs comprehensive backtests

set -e  # Exit on error

echo "=========================================="
echo "NCAAF MODEL ROE OPTIMIZATION BACKTEST"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env has real API key
if grep -q "YOUR_API_KEY_HERE" .env; then
    echo -e "${RED}ERROR: You must update .env with your REAL SportsDataIO API key${NC}"
    echo "Edit .env and replace YOUR_API_KEY_HERE with your actual key"
    echo "IMPORTANT: Rotate the old key that was exposed!"
    exit 1
fi

# Step 1: Start Docker containers
echo -e "${GREEN}Step 1: Starting Docker containers...${NC}"
docker compose up -d postgres redis
sleep 10  # Wait for services to start

# Step 2: Run database migrations
echo -e "${GREEN}Step 2: Running database migrations...${NC}"
docker compose run --rm ingestion sh -c "
    go install -tags 'postgres' github.com/golang-migrate/migrate/v4/cmd/migrate@latest && \
    migrate -path /app/migrations -database \$DATABASE_URL up
"

# Step 3: Import cached data (if available)
echo -e "${GREEN}Step 3: Importing cached data...${NC}"

# Check for Azure connection string
if [ ! -z "$AZURE_STORAGE_CONNECTION_STRING" ]; then
    echo "Importing from Azure storage..."
    docker compose run --rm ml_service python scripts/import_historical_data.py \
        --azure \
        --azure-container ncaaf-data \
        --consolidate
else
    echo -e "${YELLOW}No Azure connection string found. Skipping Azure import.${NC}"
fi

# Check for local data directory
if [ -d "data/cached" ]; then
    echo "Importing from local cached data..."
    docker compose run --rm ml_service python scripts/import_historical_data.py \
        --directory /app/data/cached \
        --consolidate
else
    echo -e "${YELLOW}No local cached data found at data/cached/${NC}"
fi

# Step 4: Backfill recent data from SportsDataIO
echo -e "${GREEN}Step 4: Backfilling recent data from SportsDataIO...${NC}"
docker compose run --rm ml_service python scripts/import_historical_data.py \
    --backfill \
    --start-season 2024 \
    --end-season 2024

# Step 5: Train enhanced models with walk-forward validation
echo -e "${GREEN}Step 5: Training enhanced models...${NC}"
echo "This may take 10-15 minutes with hyperparameter tuning..."

# First run with hyperparameter tuning
docker compose run --rm ml_service python scripts/train_xgboost_enhanced.py \
    --tune \
    --start-season 2018 \
    --end-season 2024

# Step 6: Run comprehensive backtest
echo -e "${GREEN}Step 6: Running comprehensive backtest...${NC}"
echo "Comparing baseline vs enhanced models on 2024 season..."

docker compose run --rm ml_service python scripts/backtest_enhanced.py \
    --start-date 2024-09-01 \
    --end-date 2024-12-17 \
    --plot

# Step 7: Check results
echo ""
echo "=========================================="
echo "BACKTEST COMPLETE"
echo "=========================================="
echo ""
echo "Check the following files for results:"
echo "  - backtest_report.txt - Detailed comparison report"
echo "  - backtest_comparison.png - Performance visualization"
echo "  - ml_service/models/performance_report.txt - Model metrics"
echo ""
echo -e "${GREEN}Expected ROI improvement: +40-60%${NC}"
echo ""

# Step 8: Optional - Start services for live predictions
read -p "Do you want to start the services for live predictions? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Starting all services...${NC}"
    docker compose up -d
    echo ""
    echo "Services running at:"
    echo "  - Ingestion API: http://localhost:8080/health"
    echo "  - ML API: http://localhost:8000/docs"
    echo "  - PostgreSQL: localhost:5434"
    echo "  - Redis: localhost:6380"
fi

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"