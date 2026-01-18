"""Optional production backend for the repo's lightweight JSON linear/logistic models.

This is deliberately gated behind configuration so production does not
accidentally depend on backtest artifacts.

Env/config:
- PREDICTION_BACKEND=linear_json
- LINEAR_JSON_MODEL_DIR=/app/models/linear (default)

Model artifacts live at the repo root under `models/linear/`.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from app.logging_config import get_logger
from app.models import MarketOdds, TeamRatings

logger = get_logger(__name__)


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
    # Allow a couple fallbacks for local dev.
    candidates = [
        model_dir / f"{market}.json",
    ]

    # Optional repo-root fallback (works in monorepo checkouts).
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


def _compute_derived_features(
    *,
    market: str,
    home: TeamRatings,
    away: TeamRatings,
    odds: MarketOdds,
) -> dict[str, float | None]:
    """Mirror the derived feature definitions used in training/backtests."""

    def _get(obj, name: str):
        return getattr(obj, name, None)

    home_adj_o = _get(home, "adj_o")
    home_adj_d = _get(home, "adj_d")
    away_adj_o = _get(away, "adj_o")
    away_adj_d = _get(away, "adj_d")

    home_net = (home_adj_o - home_adj_d) if (home_adj_o is not None and home_adj_d is not None) else None
    away_net = (away_adj_o - away_adj_d) if (away_adj_o is not None and away_adj_d is not None) else None

    # Base line inputs
    fg_spread = odds.spread
    h1_spread = odds.spread_1h
    fg_total = odds.total
    h1_total = odds.total_1h

    # Four factors + style features
    # Note: efg_diff uses offense vs defense matchups, consistent with backtests.
    home_efg = _get(home, "efg")
    home_efgd = _get(home, "efgd")
    away_efg = _get(away, "efg")
    away_efgd = _get(away, "efgd")

    home_tor = _get(home, "tor")
    away_tor = _get(away, "tor")

    home_orb = _get(home, "orb")
    home_drb = _get(home, "drb")
    away_orb = _get(away, "orb")
    away_drb = _get(away, "drb")

    home_ftr = _get(home, "ftr")
    away_ftr = _get(away, "ftr")

    home_rank = _get(home, "rank")
    away_rank = _get(away, "rank")

    home_wab = _get(home, "wab")
    away_wab = _get(away, "wab")

    home_tempo = _get(home, "tempo")
    away_tempo = _get(away, "tempo")

    home_three_pt_rate = _get(home, "three_pt_rate")
    away_three_pt_rate = _get(away, "three_pt_rate")

    home_two_pt_pct = _get(home, "two_pt_pct")
    away_two_pt_pct = _get(away, "two_pt_pct")

    def _safe_sub(a, b):
        if a is None or b is None:
            return None
        return float(a) - float(b)

    def _safe_add(a, b):
        if a is None or b is None:
            return None
        return float(a) + float(b)

    net_diff = _safe_sub(home_net, away_net) if home_net is not None and away_net is not None else None

    # barthag may not always be present in the service payload
    barthag_diff = _safe_sub(_get(home, "barthag"), _get(away, "barthag"))

    efg_diff = None
    if None not in (home_efg, away_efgd, away_efg, home_efgd):
        efg_diff = (float(home_efg) - float(away_efgd)) - (float(away_efg) - float(home_efgd))

    tor_diff = _safe_sub(away_tor, home_tor)

    orb_diff = None
    if None not in (home_orb, away_drb, away_orb, home_drb):
        orb_diff = (float(home_orb) - float(away_drb)) - (float(away_orb) - float(home_drb))

    ftr_diff = _safe_sub(home_ftr, away_ftr)
    rank_diff = _safe_sub(away_rank, home_rank)
    wab_diff = _safe_sub(home_wab, away_wab)

    tempo_avg = None
    if home_tempo is not None and away_tempo is not None:
        tempo_avg = (float(home_tempo) + float(away_tempo)) / 2.0

    home_eff = _safe_add(home_adj_o, away_adj_d)
    away_eff = _safe_add(away_adj_o, home_adj_d)

    three_pt_rate_avg = None
    if home_three_pt_rate is not None and away_three_pt_rate is not None:
        three_pt_rate_avg = (float(home_three_pt_rate) + float(away_three_pt_rate)) / 2.0
        # Training code normalizes if on 0-100 scale
        if three_pt_rate_avg > 2.0:
            three_pt_rate_avg = three_pt_rate_avg / 100.0

    two_pt_pct_avg = None
    if home_two_pt_pct is not None and away_two_pt_pct is not None:
        two_pt_pct_avg = (float(home_two_pt_pct) + float(away_two_pt_pct)) / 2.0

    features: dict[str, float | None] = {
        "fg_spread": fg_spread,
        "h1_spread": h1_spread,
        "fg_total": fg_total,
        "h1_total": h1_total,
        "net_diff": net_diff,
        "barthag_diff": barthag_diff,
        "efg_diff": efg_diff,
        "tor_diff": tor_diff,
        "orb_diff": orb_diff,
        "ftr_diff": ftr_diff,
        "rank_diff": rank_diff,
        "wab_diff": wab_diff,
        "tempo_avg": tempo_avg,
        "home_eff": home_eff,
        "away_eff": away_eff,
        "three_pt_rate_avg": three_pt_rate_avg,
        "two_pt_pct_avg": two_pt_pct_avg,
    }

    # Market-specific required base line check is handled by caller.
    _ = market
    return features


def predict_line(
    *,
    market: str,
    home: TeamRatings,
    away: TeamRatings,
    market_odds: MarketOdds,
) -> tuple[float | None, float | None, dict]:
    """Return (predicted_line, confidence, debug_meta)."""

    model, feature_names, meta, path = _load_model(market, allow_linear=True)
    if model is None or not feature_names:
        return None, None, {"ok": False, "reason": "model_not_found"}

    derived = _compute_derived_features(market=market, home=home, away=away, odds=market_odds)

    # Build feature vector, imputing missing values with model means.
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

    target_mode = (meta or {}).get("target_mode", "raw")
    sigma = float((meta or {}).get("sigma", 11.0))

    if market in {"fg_spread", "h1_spread"}:
        line = market_odds.spread if market == "fg_spread" else market_odds.spread_1h
    elif market in {"fg_total", "h1_total"}:
        line = market_odds.total if market == "fg_total" else market_odds.total_1h
    else:
        line = None

    if line is None:
        return None, None, {"ok": False, "reason": "missing_market_line"}

    predicted = float(line) - raw_pred if target_mode == "residual" else raw_pred

    edge = abs(predicted - float(line))
    confidence = min(1.0, edge / sigma) if sigma else 0.5

    return predicted, confidence, {
        "ok": True,
        "model_path": str(path) if path else None,
        "model_type": (meta or {}).get("model_type"),
        "target_mode": target_mode,
        "sigma": sigma,
        "edge": edge,
    }


def backend_status() -> dict:
    """Lightweight health info for the linear_json backend."""
    out: dict = {"backend": "linear_json", "model_dir": str(_default_model_dir())}
    markets = ["fg_spread", "fg_total", "h1_spread", "h1_total"]
    models: dict[str, dict] = {}
    for m in markets:
        model, features, meta, path = _load_model(m, allow_linear=True)
        models[m] = {
            "found": bool(model and features),
            "path": str(path) if path else None,
            "feature_count": len(features or []),
            "target_mode": (meta or {}).get("target_mode") if meta else None,
        }
    out["models"] = models
    return out
