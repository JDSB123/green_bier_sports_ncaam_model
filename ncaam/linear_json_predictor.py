from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from ncaam.derived_features import compute_matchup_features
from ncaam.linear_json_model import load_linear_json_model
from ncaam.types import MarketOdds


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_model_dir() -> Path:
    env_dir = os.getenv("LINEAR_JSON_MODEL_DIR")
    if env_dir:
        return Path(env_dir)

    # Prefer repo-root artifacts for local runs.
    return _repo_root() / "models" / "linear"


def _candidate_model_paths(market: str, model_dir: Path) -> list[Path]:
    candidates = [
        model_dir / f"{market}.json",
        # Common container layout (Dockerfile copies into /app/models/linear)
        Path("/app/models/linear") / f"{market}.json",
        # Repo-root fallback (in case model_dir points elsewhere)
        _repo_root() / "models" / "linear" / f"{market}.json",
    ]

    out: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


@lru_cache(maxsize=64)
def _load_market_model_cached(market: str, model_dir_str: str):
    model_dir = Path(model_dir_str)
    for path in _candidate_model_paths(market, model_dir):
        model, features, meta = load_linear_json_model(path, allow_linear=True)
        if model is not None and features:
            return model, tuple(features), meta or {}, str(path)
    return None, None, None, None


def load_market_model(market: str, *, model_dir: Path | None = None):
    """Load a JSON model artifact for a given market."""
    md = model_dir or _default_model_dir()
    return _load_market_model_cached(market, str(md))


def get_market_line(market: str, odds: MarketOdds | object) -> float | None:
    if market == "fg_spread":
        return getattr(odds, "spread", None)
    if market == "h1_spread":
        return getattr(odds, "spread_1h", None)
    if market == "fg_total":
        return getattr(odds, "total", None)
    if market == "h1_total":
        return getattr(odds, "total_1h", None)
    return None


def predict_line(
    *,
    market: str,
    home: object,
    away: object,
    market_odds: MarketOdds,
    model_dir: Path | None = None,
) -> tuple[float | None, float | None, dict]:
    """Return (predicted_line, confidence, debug_meta)."""

    model, feature_names, meta, model_path = load_market_model(market, model_dir=model_dir)
    if model is None or not feature_names:
        return None, None, {"ok": False, "reason": "model_not_found"}

    derived = compute_matchup_features(home=home, away=away, odds=market_odds)

    row: list[float] = []
    for idx, name in enumerate(feature_names):
        val = derived.get(name)
        if val is None:
            try:
                val = float(model.means[idx])
            except Exception:
                val = None
        if val is None:
            return None, None, {"ok": False, "reason": f"missing_feature:{name}"}
        row.append(float(val))

    raw_pred = float(model.predict([row])[0])

    target_mode = str(meta.get("target_mode", "raw"))
    sigma = float(meta.get("sigma", 11.0))
    min_edge_pct = meta.get("min_edge")

    line = get_market_line(market, market_odds)
    if line is None:
        return None, None, {"ok": False, "reason": "missing_market_line"}

    predicted = float(line) - raw_pred if target_mode == "residual" else raw_pred

    edge_points = abs(predicted - float(line))
    edge_pct = (edge_points / sigma) * 100.0 if sigma else 0.0
    confidence = min(1.0, edge_points / sigma) if sigma else 0.5

    out = {
        "ok": True,
        "model_path": model_path,
        "model_type": meta.get("model_type"),
        "target_mode": target_mode,
        "sigma": sigma,
        "min_edge_pct": float(min_edge_pct) if min_edge_pct is not None else None,
        "edge_points": edge_points,
        "edge_pct": edge_pct,
        "line": float(line),
        "raw_pred": raw_pred,
    }

    return predicted, confidence, out


def backend_status(*, model_dir: Path | None = None) -> dict:
    """Lightweight health info for the JSON model artifacts."""
    md = model_dir or _default_model_dir()
    markets = ["fg_spread", "fg_total", "h1_spread", "h1_total"]
    models: dict[str, dict] = {}

    for m in markets:
        model, features, meta, model_path = load_market_model(m, model_dir=md)
        models[m] = {
            "found": bool(model and features),
            "path": model_path,
            "feature_count": len(features or []),
            "target_mode": (meta or {}).get("target_mode") if meta else None,
        }

    return {
        "backend": "linear_json",
        "model_dir": str(md),
        "models": models,
    }
