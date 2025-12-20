# Local Setup Guide - NCAA Basketball v6.0

This guide walks you through setting up the NCAA Basketball prediction model on your local machine.

## Prerequisites

Before you begin, ensure you have the following installed:

### Required Software

1. **Docker Desktop** (v20.10 or later)
   - Windows: [Download Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
   - macOS: [Download Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
   - Linux: [Install Docker Engine](https://docs.docker.com/engine/install/)

2. **Docker Compose** (included with Docker Desktop on Windows/Mac)
   - Linux users may need to install separately: [Install Docker Compose](https://docs.docker.com/compose/install/)

3. **Python 3.8+** (for running the setup script)
   - Windows: [Download Python](https://www.python.org/downloads/)
   - macOS: `brew install python3` or download from python.org
   - Linux: Usually pre-installed, or use `sudo apt install python3` (Ubuntu/Debian)

4. **Git** (for cloning the repository)
   - Windows: [Download Git for Windows](https://git-scm.com/download/win)
   - macOS: `brew install git` or use Xcode Command Line Tools
   - Linux: `sudo apt install git` (Ubuntu/Debian)

### Optional but Recommended

- **PowerShell** (Windows users already have this)
   - macOS/Linux: Install PowerShell Core from [here](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell)
   - Or use bash/shell equivalents of the commands

## Step-by-Step Setup

### 1. Clone the Repository

Open a terminal/command prompt and run:

```bash
git clone https://github.com/JDSB123/green_bier_sports_ncaam_model.git
cd green_bier_sports_ncaam_model
```

### 2. Create Required Secrets

The application requires three secret files. Run the setup script to create them:

```bash
python ensure_secrets.py
```

This script will:
- Create the `secrets/` directory if it doesn't exist
- Generate secure random passwords for `db_password.txt` and `redis_password.txt`
- **Exit with an error** for `odds_api_key.txt` (you must provide this)

### 3. Add Your Odds API Key

You need to obtain an API key from [The Odds API](https://the-odds-api.com/):

1. Visit https://the-odds-api.com/ and sign up for a free account
2. Copy your API key from the dashboard
3. Create the file `secrets/odds_api_key.txt` with your API key:

**Windows (PowerShell):**
```powershell
"YOUR_API_KEY_HERE" | Out-File -FilePath secrets/odds_api_key.txt -NoNewline -Encoding UTF8
```

**macOS/Linux (bash):**
```bash
echo -n "YOUR_API_KEY_HERE" > secrets/odds_api_key.txt
```

Replace `YOUR_API_KEY_HERE` with your actual API key.

### 4. Verify Secret Files

Check that all three files exist:

```bash
# Windows (PowerShell)
Get-ChildItem secrets/*.txt

# macOS/Linux
ls -l secrets/*.txt
```

You should see:
- `db_password.txt`
- `redis_password.txt`
- `odds_api_key.txt`

### 5. Build the Docker Containers

Build all the required containers (this may take 5-10 minutes the first time):

```bash
docker compose build
```

This builds:
- PostgreSQL database (TimescaleDB)
- Redis cache
- Prediction service (Python)
- Odds ingestion service (Rust)
- Ratings sync service (Go)

### 6. Start the Services

Start the database and core services:

```bash
docker compose up -d postgres redis prediction-service
```

Check that services are running:

```bash
docker compose ps
```

You should see all three services with status "Up" and "healthy".

### 7. Run Your First Prediction

Now you're ready to run predictions!

**Windows:**
```powershell
.\predict.bat
```

**macOS/Linux:**
```bash
# Option 1: Run with PowerShell Core (recommended if installed)
pwsh predict.bat

# Option 2: Manually run the Docker commands
docker compose run --rm odds-full-once
docker compose run --rm odds-1h-once
docker compose exec prediction-service python /app/src/predictor.py
```

## What Happens When You Run Predictions

1. **Syncs fresh ratings** from Barttorvik (Go binary)
2. **Syncs fresh odds** from The Odds API (Rust binary)
3. **Runs predictions** using the model (Python)
4. **Outputs betting recommendations** with edge calculations

## Common Commands

### View Logs
```bash
# All services
docker compose logs

# Specific service
docker compose logs prediction-service
docker compose logs postgres

# Follow logs in real-time
docker compose logs -f prediction-service
```

### Stop Services
```bash
# Stop all services
docker compose down

# Stop and remove all data (including database)
docker compose down -v
```

### Restart Services
```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart prediction-service
```

### Update and Rebuild
```bash
# Pull latest changes
git pull

# Rebuild containers
docker compose build

# Restart services with new build
docker compose up -d
```

## Prediction Options

The `predict.bat` script supports various options:

```powershell
# Full slate for today (default)
.\predict.bat

# Skip data sync (use cached data)
.\predict.bat --no-sync

# Predict a specific game
.\predict.bat --game "Duke" "UNC"

# Predict games for a specific date
.\predict.bat --date 2025-12-20
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  prediction-service                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ ratings-sync│  │odds-ingestion│  │  predictor.py  │ │
│  │   (Go)      │  │   (Rust)     │  │   (Python)     │ │
│  └──────┬──────┘  └──────┬───────┘  └────────┬───────┘ │
│         │                │                    │         │
│         └────────────────┴────────────────────┘         │
│                          │                              │
└──────────────────────────┼──────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  PostgreSQL  │
                    │   (ncaam)    │
                    └─────────────┘
```

## Port Allocations

The services use the following ports on your local machine:

- **PostgreSQL**: 5450 (localhost:5450)
- **Redis**: 6390 (localhost:6390)
- **Prediction Service**: 8092 (localhost:8092)

These ports are chosen to avoid conflicts with other applications.

## Troubleshooting

### "Secret file not found" Error

**Cause**: Missing secret files in the `secrets/` directory.

**Solution**: Run `python ensure_secrets.py` and ensure all three `.txt` files exist.

### "Cannot connect to Docker daemon" Error

**Cause**: Docker is not running.

**Solution**: 
- Windows/Mac: Start Docker Desktop
- Linux: Run `sudo systemctl start docker`

### "Port already in use" Error

**Cause**: Another application is using one of the required ports.

**Solution**: Edit `docker-compose.yml` to change port mappings. For example, to change PostgreSQL from port 5450 to 5451:
```yaml
# Find this line in docker-compose.yml under the postgres service:
ports:
  - "${POSTGRES_HOST_PORT:-5450}:5432"

# Change it to:
ports:
  - "5451:5432"  # Changed from 5450 to 5451
```

### Services Won't Start or Are Unhealthy

**Check logs**:
```bash
docker compose logs postgres
docker compose logs redis
docker compose logs prediction-service
```

**Common issues**:
- Database password mismatch: Delete containers and volumes, then recreate
  ```bash
  docker compose down -v
  docker compose up -d
  ```

### "No module named 'X'" Error

**Cause**: Python dependencies not installed in container.

**Solution**: Rebuild the container:
```bash
docker compose build prediction-service
docker compose up -d prediction-service
```

## Directory Structure

```
green_bier_sports_ncaam_model/
├── services/
│   ├── prediction-service-python/   # Main prediction engine
│   ├── odds-ingestion-rust/         # Odds data fetcher
│   └── ratings-sync-go/             # Team ratings syncer
├── database/
│   └── migrations/                  # Database schema
├── secrets/                         # Secret files (not committed)
│   ├── db_password.txt
│   ├── redis_password.txt
│   └── odds_api_key.txt
├── docker-compose.yml               # Service orchestration
├── predict.bat                      # Main entry point
├── ensure_secrets.py                # Secret setup script
└── README.md                        # Quick start guide
```

## Security Notes

- **Never commit** secret files to version control (they're in `.gitignore`)
- Secret files are mounted as Docker secrets (read-only)
- Generate new secrets for production deployments
- Rotate secrets regularly (at least quarterly)

## Getting Help

If you encounter issues not covered here:

1. Check the logs: `docker compose logs`
2. Review the main [README.md](README.md) for model-specific information
3. Check [The Odds API documentation](https://the-odds-api.com/liveapi/guides/v4/)
4. Open an issue on GitHub with your logs and error messages

## Model Parameters

The model uses these default parameters (configured in `docker-compose.yml`):

- **Home Court Advantage (Spread)**: 3.0 points
- **Home Court Advantage (Total)**: 4.5 points  
- **Minimum Spread Edge**: 2.5 points
- **Minimum Total Edge**: 3.0 points

These can be adjusted by modifying the `MODEL__*` environment variables in `docker-compose.yml`.

## What's Next?

Once you have predictions running:

1. Review the output to understand the recommendations
2. Experiment with different dates and games
3. Monitor model performance over time
4. Adjust parameters based on your analysis

Enjoy your NCAA Basketball predictions! 🏀
