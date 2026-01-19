from __future__ import annotations

import os
import sys
from pathlib import Path


def test_shared_predictor_residual_math_and_edge_meta():
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from ncaam.linear_json_predictor import predict_line
    from ncaam.types import MarketOdds

    model_dir = repo_root / "models" / "linear"
    os.environ["LINEAR_JSON_MODEL_DIR"] = str(model_dir)

    odds = MarketOdds(spread=-6.5, total=145.5, spread_1h=-2.0, total_1h=68.5)

    home = {
        "team_name": "Home",
        "adj_o": 118.5,
        "adj_d": 94.2,
        "tempo": 69.0,
        "rank": 8,
        "efg": 52.5,
        "efgd": 47.8,
        "tor": 16.5,
        "orb": 31.0,
        "drb": 74.0,
        "ftr": 35.0,
        "barthag": 0.910,
        "wab": 4.5,
        "three_pt_rate": 37.0,
        "two_pt_pct": 53.0,
    }

    away = {
        "team_name": "Away",
        "adj_o": 112.0,
        "adj_d": 100.5,
        "tempo": 67.5,
        "rank": 35,
        "efg": 50.0,
        "efgd": 50.5,
        "tor": 18.0,
        "orb": 28.5,
        "drb": 71.5,
        "ftr": 32.0,
        "barthag": 0.750,
        "wab": 1.0,
        "three_pt_rate": 35.0,
        "two_pt_pct": 50.0,
    }

    predicted, confidence, meta = predict_line(
        market="fg_spread",
        home=home,
        away=away,
        market_odds=odds,
        model_dir=model_dir,
    )

    assert meta["ok"] is True
    assert predicted is not None
    assert confidence is not None
    assert meta["sigma"] > 0

    # Residual reconstruction consistency: predicted == line - raw_pred
    if meta.get("target_mode") == "residual":
        assert abs(float(predicted) - (meta["line"] - meta["raw_pred"])) < 1e-6

    # Edge meta consistency
    assert abs(meta["edge_pct"] - (meta["edge_points"] / meta["sigma"] * 100.0)) < 1e-6
