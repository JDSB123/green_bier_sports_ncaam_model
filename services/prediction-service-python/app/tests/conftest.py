import sys
from pathlib import Path


# Ensure `import app...` works when pytest is executed from the repo root.
PREDICTION_SERVICE_DIR = Path(__file__).resolve().parents[2]  # services/prediction-service-python
if str(PREDICTION_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(PREDICTION_SERVICE_DIR))


