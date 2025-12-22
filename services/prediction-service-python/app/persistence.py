"""
Postgres persistence helpers for predictions and betting recommendations.

Goal:
- Make `run_today.py` (and optionally the API) production-auditable by writing:
  - `predictions` (one row per game_id + model_version)
  - `betting_recommendations` (rows for each recommended bet)

Notes:
- We keep schema changes out of this implementation (no new migrations).
- For idempotency, we "void" prior pending recommendations for the same
  prediction_id before inserting the latest set.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.models import BettingRecommendation, Prediction


def _jsonb(value: Optional[Dict[str, Any]]) -> str:
    """Serialize a dict to a JSON string for CAST(:x AS jsonb)."""
    if value is None:
        return "{}"
    return json.dumps(value, default=str, ensure_ascii=False)


def upsert_prediction(engine: Engine, prediction: Prediction, features: Optional[Dict[str, Any]] = None) -> UUID:
    """
    Upsert a prediction row and return `predictions.id`.
    """
    stmt = text(
        """
        INSERT INTO predictions (
            game_id,
            model_version,

            predicted_spread,
            predicted_total,
            predicted_home_score,
            predicted_away_score,
            spread_confidence,
            total_confidence,

            predicted_spread_1h,
            predicted_total_1h,
            predicted_home_score_1h,
            predicted_away_score_1h,
            spread_confidence_1h,
            total_confidence_1h,

            predicted_home_ml,
            predicted_away_ml,
            predicted_home_ml_1h,
            predicted_away_ml_1h,

            market_spread,
            market_total,
            market_spread_1h,
            market_total_1h,

            spread_edge,
            total_edge,
            spread_edge_1h,
            total_edge_1h,

            features_json,
            created_at
        )
        VALUES (
            :game_id,
            :model_version,

            :predicted_spread,
            :predicted_total,
            :predicted_home_score,
            :predicted_away_score,
            :spread_confidence,
            :total_confidence,

            :predicted_spread_1h,
            :predicted_total_1h,
            :predicted_home_score_1h,
            :predicted_away_score_1h,
            :spread_confidence_1h,
            :total_confidence_1h,

            :predicted_home_ml,
            :predicted_away_ml,
            :predicted_home_ml_1h,
            :predicted_away_ml_1h,

            :market_spread,
            :market_total,
            :market_spread_1h,
            :market_total_1h,

            :spread_edge,
            :total_edge,
            :spread_edge_1h,
            :total_edge_1h,

            CAST(:features_json AS jsonb),
            NOW()
        )
        ON CONFLICT (game_id, model_version) DO UPDATE SET
            predicted_spread = EXCLUDED.predicted_spread,
            predicted_total = EXCLUDED.predicted_total,
            predicted_home_score = EXCLUDED.predicted_home_score,
            predicted_away_score = EXCLUDED.predicted_away_score,
            spread_confidence = EXCLUDED.spread_confidence,
            total_confidence = EXCLUDED.total_confidence,

            predicted_spread_1h = EXCLUDED.predicted_spread_1h,
            predicted_total_1h = EXCLUDED.predicted_total_1h,
            predicted_home_score_1h = EXCLUDED.predicted_home_score_1h,
            predicted_away_score_1h = EXCLUDED.predicted_away_score_1h,
            spread_confidence_1h = EXCLUDED.spread_confidence_1h,
            total_confidence_1h = EXCLUDED.total_confidence_1h,

            predicted_home_ml = EXCLUDED.predicted_home_ml,
            predicted_away_ml = EXCLUDED.predicted_away_ml,
            predicted_home_ml_1h = EXCLUDED.predicted_home_ml_1h,
            predicted_away_ml_1h = EXCLUDED.predicted_away_ml_1h,

            market_spread = EXCLUDED.market_spread,
            market_total = EXCLUDED.market_total,
            market_spread_1h = EXCLUDED.market_spread_1h,
            market_total_1h = EXCLUDED.market_total_1h,

            spread_edge = EXCLUDED.spread_edge,
            total_edge = EXCLUDED.total_edge,
            spread_edge_1h = EXCLUDED.spread_edge_1h,
            total_edge_1h = EXCLUDED.total_edge_1h,

            features_json = EXCLUDED.features_json,
            created_at = NOW()
        RETURNING id
        """
    )

    params = {
        "game_id": prediction.game_id,
        "model_version": prediction.model_version,
        "predicted_spread": prediction.predicted_spread,
        "predicted_total": prediction.predicted_total,
        "predicted_home_score": prediction.predicted_home_score,
        "predicted_away_score": prediction.predicted_away_score,
        "spread_confidence": prediction.spread_confidence,
        "total_confidence": prediction.total_confidence,
        "predicted_spread_1h": prediction.predicted_spread_1h,
        "predicted_total_1h": prediction.predicted_total_1h,
        "predicted_home_score_1h": prediction.predicted_home_score_1h,
        "predicted_away_score_1h": prediction.predicted_away_score_1h,
        "spread_confidence_1h": prediction.spread_confidence_1h,
        "total_confidence_1h": prediction.total_confidence_1h,
        "predicted_home_ml": prediction.predicted_home_ml,
        "predicted_away_ml": prediction.predicted_away_ml,
        "predicted_home_ml_1h": prediction.predicted_home_ml_1h,
        "predicted_away_ml_1h": prediction.predicted_away_ml_1h,
        "market_spread": prediction.market_spread,
        "market_total": prediction.market_total,
        "market_spread_1h": prediction.market_spread_1h,
        "market_total_1h": prediction.market_total_1h,
        "spread_edge": prediction.spread_edge,
        "total_edge": prediction.total_edge,
        "spread_edge_1h": prediction.spread_edge_1h,
        "total_edge_1h": prediction.total_edge_1h,
        "features_json": _jsonb(features),
    }

    with engine.begin() as conn:
        row = conn.execute(stmt, params).fetchone()
        if not row:
            raise RuntimeError("Failed to upsert prediction (no RETURNING row)")
        return row[0]


def void_pending_recommendations(engine: Engine, prediction_id: UUID) -> int:
    """
    Mark prior pending recommendations as void so repeated runs don't accumulate duplicates.
    """
    stmt = text(
        """
        UPDATE betting_recommendations
        SET status = 'void'
        WHERE prediction_id = :prediction_id
          AND status = 'pending'
        """
    )
    with engine.begin() as conn:
        res = conn.execute(stmt, {"prediction_id": prediction_id})
        return int(res.rowcount or 0)


def insert_recommendations(
    engine: Engine,
    prediction_id: UUID,
    game_id: UUID,
    recommendations: Iterable[BettingRecommendation],
) -> int:
    """
    Insert a set of recommendations for a given prediction_id.
    Returns number of rows inserted.
    """
    stmt = text(
        """
        INSERT INTO betting_recommendations (
            prediction_id,
            game_id,
            bet_type,
            pick,
            line,
            edge,
            confidence,
            ev_percent,
            kelly_fraction,
            recommended_units,
            bet_tier,
            sharp_line,
            steam_aligned,
            created_at
        )
        VALUES (
            :prediction_id,
            :game_id,
            :bet_type,
            :pick,
            :line,
            :edge,
            :confidence,
            :ev_percent,
            :kelly_fraction,
            :recommended_units,
            :bet_tier,
            :sharp_line,
            :steam_aligned,
            NOW()
        )
        """
    )

    rows = []
    for r in recommendations:
        # Cap ev_percent to 999.99 to avoid DECIMAL(5,2) overflow on extreme ML edges
        capped_ev = min(r.ev_percent, 999.99) if r.ev_percent is not None else None
        rows.append(
            {
                "prediction_id": prediction_id,
                "game_id": game_id,
                "bet_type": r.bet_type.value,
                "pick": r.pick.value,
                "line": r.line,
                "edge": r.edge,
                "confidence": r.confidence,
                "ev_percent": capped_ev,
                "kelly_fraction": r.kelly_fraction,
                "recommended_units": r.recommended_units,
                "bet_tier": r.bet_tier.value,
                "sharp_line": r.sharp_line,
                "steam_aligned": bool(r.is_sharp_aligned),
            }
        )

    if not rows:
        return 0

    with engine.begin() as conn:
        res = conn.execute(stmt, rows)
        return int(res.rowcount or 0)


def persist_prediction_and_recommendations(
    engine: Engine,
    prediction: Prediction,
    recommendations: Iterable[BettingRecommendation],
    features: Optional[Dict[str, Any]] = None,
) -> tuple[UUID, int, int]:
    """
    Persist prediction + recs.

    Returns: (prediction_id, voided_count, inserted_count)
    """
    prediction_id = upsert_prediction(engine, prediction, features=features)
    voided = void_pending_recommendations(engine, prediction_id)
    inserted = insert_recommendations(engine, prediction_id, prediction.game_id, recommendations)
    return prediction_id, voided, inserted


