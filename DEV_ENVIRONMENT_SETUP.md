# Development Environment Setup

## 🎯 Prerequisites

- **Python 3.12+** (required - matches Docker image)
- **Docker Desktop** (required)
- **Git** (required)
- **PowerShell 7+** (recommended for Windows)

---

## 🚀 One-Time Setup (New Developer)

### Step 1: Clone Repository
```powershell
git clone https://github.com/JDSB123/green_bier_sports_ncaam_model.git
cd green_bier_sports_ncaam_model
```

### Step 2: Create Python Virtual Environment
```powershell
# Create virtual environment
python -m venv .venv

# Activate it (PowerShell)
.\.venv\Scripts\Activate.ps1

# Or activate it (CMD)
.\.venv\Scripts\activate.bat

# Or activate it (Git Bash/Unix)
source .venv/Scripts/activate
```

### Step 3: Install Python Dependencies
```powershell
# Install production dependencies
pip install -r services/prediction-service-python/requirements.txt

# Install development dependencies (linting, testing, etc.)
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Step 4: Configure VS Code
VS Code should automatically detect the virtual environment. If not:
1. Press `Ctrl+Shift+P`
2. Type "Python: Select Interpreter"
3. Choose `.venv` from the list

### Step 5: Setup Docker Secrets
```powershell
# Run secret setup script
python ensure_secrets.py

# It will prompt for:
# - Odds API key (get from https://the-odds-api.com/)
# - Other secrets will be auto-generated
```

### Step 6: Verify Setup
```powershell
# Check Docker is running
docker --version
docker compose version

# Check Python environment
python --version
pip list

# Run a quick test
.\predict.bat --help
```

---

## 📂 Workspace Structure

```
green_bier_sports_ncaam_model/          ← THIS is your workspace root
├── .venv/                              ← Python virtual environment (local only)
├── .vscode/                            ← VS Code settings
├── services/
│   ├── prediction-service-python/
│   │   ├── requirements.txt            ← Production dependencies
│   │   └── app/                        ← Application code
│   ├── ratings-sync-go/                ← Go service
│   ├── odds-ingestion-rust/            ← Rust service
│   └── web-frontend/                   ← Frontend service
├── docker-compose.yml                  ← Local development containers
├── predict.bat                         ← Single entry point for predictions
├── requirements-dev.txt                ← Dev tools (NEW - to be created)
└── README.md                           ← Main documentation
```

---

## 🔄 Daily Development Workflow

### Starting Your Work Session
```powershell
# 1. Navigate to project root
cd green_bier_sports_ncaam_model

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Pull latest changes
git pull origin main

# 4. Start Docker containers (if needed)
docker compose up -d postgres redis
```

### Running the Model
```powershell
# Full slate (syncs data + runs predictions)
.\predict.bat

# Skip data sync (faster)
.\predict.bat --no-sync

# Specific game
.\predict.bat --game "Duke" "UNC"
```

### Running Tests
```powershell
# Activate venv first!
.\.venv\Scripts\Activate.ps1

# Run Python tests
pytest services/prediction-service-python/tests/

# Run pre-commit checks
pre-commit run --all-files
```

### Making Code Changes
```powershell
# 1. Create feature branch
git checkout -b feature/my-change

# 2. Make changes in your IDE

# 3. Run tests
pytest

# 4. Commit (pre-commit hooks will run automatically)
git add .
git commit -m "Description of changes"

# 5. Push to GitHub
git push origin feature/my-change

# 6. Create Pull Request on GitHub
```

---

## 🐛 Troubleshooting

### "Python command not found"
- Install Python 3.12+ from [python.org](https://www.python.org/downloads/)
- Or use `py -3.12` instead of `python`

### "Cannot activate virtual environment"
```powershell
# PowerShell execution policy issue - run as admin:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "Docker containers won't start"
```powershell
# Ensure Docker Desktop is running
# Check for port conflicts
docker compose down
docker compose up -d

# View logs
docker compose logs postgres
```

### "Module not found" errors in Python
```powershell
# Ensure venv is activated (you should see (.venv) in prompt)
.\.venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r services/prediction-service-python/requirements.txt
```

### "Secrets not found" errors
```powershell
# Verify secrets directory exists and has files
ls secrets/

# Expected files:
# - db_password.txt
# - redis_password.txt
# - odds_api_key.txt
# - teams_webhook_secret.txt

# Regenerate if missing
python ensure_secrets.py
```

---

## 🔧 VS Code Extensions (Recommended)

Install these for the best development experience:

**Essential:**
- `ms-python.python` - Python support
- `ms-azuretools.vscode-docker` - Docker support
- `golang.go` - Go support (for ratings-sync)
- `rust-lang.rust-analyzer` - Rust support (for odds-ingestion)

**Highly Recommended:**
- `charliermarsh.ruff` - Fast Python linter/formatter
- `ms-vscode.powershell` - PowerShell support
- `redhat.vscode-yaml` - YAML support
- `GitHub.copilot` - AI assistant

**Optional:**
- `ms-python.debugpy` - Python debugging
- `eamodio.gitlens` - Enhanced Git features

---

## 📝 Quick Reference

| Task | Command |
|------|---------|
| **Activate venv** | `.\.venv\Scripts\Activate.ps1` |
| **Run predictions** | `.\predict.bat` |
| **Run tests** | `pytest` |
| **Start Docker** | `docker compose up -d` |
| **Stop Docker** | `docker compose down` |
| **View logs** | `docker compose logs -f prediction-service` |
| **Deploy to Azure** | `.\azure\deploy.ps1 -QuickDeploy` |
| **Setup secrets** | `python ensure_secrets.py` |
| **Format code** | `pre-commit run --all-files` |

---

## 🆘 Getting Help

1. Check [README.md](README.md) for project overview
2. See [docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md) for Git workflow
3. See [QUICK_START_TONIGHT.md](QUICK_START_TONIGHT.md) for running predictions
4. Check Docker logs: `docker compose logs`

---

## ✅ Checklist for New Developers

- [ ] Python 3.12+ installed
- [ ] Docker Desktop running
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Pre-commit hooks installed (`pre-commit install`)
- [ ] Secrets configured (`python ensure_secrets.py`)
- [ ] VS Code Python interpreter set to `.venv`
- [ ] Successfully run `.\predict.bat --help`
- [ ] Successfully started Docker containers
- [ ] Read [README.md](README.md) and [DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md)
