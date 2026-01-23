"""Optional production backend for the repo's lightweight JSON linear/logistic models.

This backend is deliberately gated behind configuration so production does not
accidentally depend on backtest artifacts.

Implementation note:
- The shared model loading/feature/edge/residual logic lives in
    `ncaam.linear_json_predictor` so scripts, services, and tests can use one
    canonical implementation without importing from `testing/`.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from app.logging_config import get_logger
from app.models import MarketOdds, TeamRatings

logger = get_logger(__name__)


def _import_shared_predictor():
    """Import shared predictor with a monorepo-friendly sys.path fallback."""

    try:
        from ncaam.linear_json_predictor import backend_status as shared_backend_status
        from ncaam.linear_json_predictor import predict_line as shared_predict_line

        return shared_predict_line, shared_backend_status
    except ModuleNotFoundError:
        # Local dev/CI sometimes runs from `services/prediction-service-python` and
        # doesn't have the monorepo root on `sys.path`.
        try:
            repo_root = Path(__file__).resolve().parents[4]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
        except Exception:
            pass

        from ncaam.linear_json_predictor import backend_status as shared_backend_status
        from ncaam.linear_json_predictor import predict_line as shared_predict_line

        return shared_predict_line, shared_backend_status


@dataclass(frozen=True)
class LinearJsonBackendConfig:
    model_dir: Path


def _default_model_dir() -> Path:
    env_dir = os.getenv("LINEAR_JSON_MODEL_DIR")
    if env_dir:
        return Path(env_dir)

    # Default container path (Dockerfile copies into /app/models/linear)
    return Path("/app/models/linear")


def _candidate_model_paths(market: str, model_dir: Path) -> list[Path]:
    env_name = (os.getenv("ENVIRONMENT", "") or os.getenv("APP_ENV", "")).lower()
    allow_dev_fallback = env_name in {"dev", "development", "local", "test"} or bool(
        os.getenv("PYTEST_CURRENT_TEST")
    )

    candidates = [
        model_dir / f"{market}.json",
    ]

    # Optional repo-root fallback (works in monorepo checkouts) allowed only in dev/local.
    if allow_dev_fallback:
        repo_root = None
        try:
            repo_root = Path(__file__).resolve().parents[4]
        except Exception:
            repo_root = None
        if repo_root:
            candidates.append(repo_root / "models" / "linear" / f"{market}.json")
    # De-dupe while preserving order
    out: list[Path] = []
    seen: set[Path] = set()
    for p in candidates:
        rp = p.resolve() if p.exists() else p
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out


def _load_model(market: str, *, allow_linear: bool = True):
    try:
        from ncaam.linear_json_model import load_linear_json_model
    except ModuleNotFoundError:
        # Local dev/CI sometimes runs from `services/prediction-service-python` and
        # doesn't have repo root on `sys.path`. We can derive the monorepo root
        # from this file location and add it as a fallback.
        try:
            repo_root = Path(__file__).resolve().parents[4]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
        except Exception:
            pass
        from ncaam.linear_json_model import load_linear_json_model

    model_dir = _default_model_dir()
    for path in _candidate_model_paths(market, model_dir):
        model, features, meta = load_linear_json_model(path, allow_linear=allow_linear)
        if model is not None and features:
            return model, features, meta, path
    return None, None, None, None


def predict_line(
    *,
    market: str,
    home: TeamRatings,
    away: TeamRatings,
    market_odds: MarketOdds,
) -> tuple[float | None, float | None, dict]:
    """Return (predicted_line, confidence, debug_meta)."""

    # Delegate to shared predictor to keep math consistent across entrypoints.
    shared_predict_line, _shared_backend_status = _import_shared_predictor()
    return shared_predict_line(market=market, home=home, away=away, market_odds=market_odds)


def backend_status() -> dict:
    """Lightweight health info for the linear_json backend."""
    _shared_predict_line, shared_backend_status = _import_shared_predictor()
    return shared_backend_status()
