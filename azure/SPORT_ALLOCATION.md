# Green Bier Sport Ventures - Port Allocation Registry

This document defines the port and network allocations for each sport to ensure
no conflicts when running multiple sports simultaneously.

## Port Allocation Matrix

| Sport | PostgreSQL | Redis | Prediction | Backend Subnet | Data Subnet |
|-------|------------|-------|------------|----------------|-------------|
| NCAAM | 5450 | 6390 | 8092 | 10.50.2.0/24 | 10.50.3.0/24 |
| NFL | 5451 | 6391 | 8093 | 10.51.2.0/24 | 10.51.3.0/24 |
| NBA | 5452 | 6392 | 8094 | 10.52.2.0/24 | 10.52.3.0/24 |
| MLB | 5453 | 6393 | 8095 | 10.53.2.0/24 | 10.53.3.0/24 |
| NHL | 5454 | 6394 | 8096 | 10.54.2.0/24 | 10.54.3.0/24 |
| WNBA | 5456 | 6396 | 8098 | 10.56.2.0/24 | 10.56.3.0/24 |
| CFB | 5457 | 6397 | 8099 | 10.57.2.0/24 | 10.57.3.0/24 |

## Environment Variables by Sport

### NCAAM (College Basketball)
```bash
export SPORT=ncaam
export COMPOSE_PROJECT_NAME=ncaam_v6_model
export POSTGRES_HOST_PORT=5450
export REDIS_HOST_PORT=6390
export PREDICTION_HOST_PORT=8092
export NETWORK_BACKEND_SUBNET=10.50.2.0/24
export NETWORK_DATA_SUBNET=10.50.3.0/24
export DB_USER=ncaam
export DB_NAME=ncaam
```

### NFL (Pro Football)
```bash
export SPORT=nfl
export COMPOSE_PROJECT_NAME=nfl_v6_model
export POSTGRES_HOST_PORT=5451
export REDIS_HOST_PORT=6391
export PREDICTION_HOST_PORT=8093
export NETWORK_BACKEND_SUBNET=10.51.2.0/24
export NETWORK_DATA_SUBNET=10.51.3.0/24
export DB_USER=nfl
export DB_NAME=nfl
```

### NBA (Pro Basketball)
```bash
export SPORT=nba
export COMPOSE_PROJECT_NAME=nba_v6_model
export POSTGRES_HOST_PORT=5452
export REDIS_HOST_PORT=6392
export PREDICTION_HOST_PORT=8094
export NETWORK_BACKEND_SUBNET=10.52.2.0/24
export NETWORK_DATA_SUBNET=10.52.3.0/24
export DB_USER=nba
export DB_NAME=nba
```

### MLB (Pro Baseball)
```bash
export SPORT=mlb
export COMPOSE_PROJECT_NAME=mlb_v6_model
export POSTGRES_HOST_PORT=5453
export REDIS_HOST_PORT=6393
export PREDICTION_HOST_PORT=8095
export NETWORK_BACKEND_SUBNET=10.53.2.0/24
export NETWORK_DATA_SUBNET=10.53.3.0/24
export DB_USER=mlb
export DB_NAME=mlb
```

## Dynamic Port Allocator

Use the Python port allocator for automatic conflict detection:

```bash
# Check allocation for a sport
python azure/port_allocator.py allocate ncaam

# Check all sports for conflicts
python azure/port_allocator.py check --sports ncaam nfl nba mlb

# Generate .env file
python azure/port_allocator.py allocate ncaam --env .env

# Auto-resolve conflicts
python azure/port_allocator.py allocate ncaam --auto-resolve

# View current Docker port usage
python azure/port_allocator.py status
```

## Azure Container Apps

In Azure Container Apps, port conflicts are NOT an issue because:

1. Each sport gets its own Container Apps Environment
2. Services communicate via DNS names within the environment
3. No host port mapping required (Azure handles ingress)

The port allocator is primarily for **local development** when running
multiple sports simultaneously on the same machine.

## Secret Naming Convention

All secrets in Azure Key Vault use sport-prefixed names:

| Secret | NCAAM | NFL | NBA |
|--------|-------|-----|-----|
| Database Password | ncaam-db-password | nfl-db-password | nba-db-password |
| Redis Password | ncaam-redis-password | nfl-redis-password | nba-redis-password |
| Odds API Key | ncaam-odds-api-key | nfl-odds-api-key | nba-odds-api-key |

This prevents any cross-contamination between sport environments.
