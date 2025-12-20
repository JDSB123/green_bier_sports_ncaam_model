# Quick Reference - Container Usage

## Backtest Container (Self-Contained)

```bash
# Start
docker-compose -f docker-compose.backtest.yml up -d

# Run backtest
docker-compose -f docker-compose.backtest.yml exec backtest python3 main.py backtest --start-date 2024-09-01 --end-date 2024-12-17

# Stop
docker-compose -f docker-compose.backtest.yml down
```

## Production Live Container (Self-Contained)

```bash
# Start (requires proven model in ml_service/models/)
docker-compose -f docker-compose.prod-live.yml up -d

# Check health
curl http://localhost:8001/health

# Get predictions
curl http://localhost:8001/api/v1/predictions/week/2024/15

# Stop
docker-compose -f docker-compose.prod-live.yml down
```

## Clean Up Old Containers

```bash
# List all ncaaf containers
docker ps -a | grep ncaaf

# Stop and remove old containers
docker stop ncaaf_v5  # or other old container names
docker rm ncaaf_v5

# Remove unused volumes
docker volume prune
```

See `CONTAINERS.md` for detailed documentation.
