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
        # Cap values to avoid DECIMAL overflow:
        # - ev_percent: DECIMAL(6,3) max 999.999 - cap at 999.99
        # - edge: DECIMAL(5,2) max 999.99
        # - line: DECIMAL(5,2) max 999.99 - ML odds like +4000 overflow!
        capped_ev = min(r.ev_percent, 999.99) if r.ev_percent is not None else None
        capped_edge = min(r.edge, 999.99) if r.edge is not None else None
        capped_line = r.line
        if capped_line is not None and abs(capped_line) > 999.99:
            capped_line = 999.99 if capped_line > 0 else -999.99
        rows.append(
            {
                "prediction_id": prediction_id,
                "game_id": game_id,
                "bet_type": r.bet_type.value,
                "pick": r.pick.value,
                "line": capped_line,
                "edge": capped_edge,
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


# ═══════════════════════════════════════════════════════════════════════════════
# CLV TRACKING - Closing Line Value capture and calculation
# ═══════════════════════════════════════════════════════════════════════════════

def capture_closing_lines(
    engine: Engine,
    game_id: UUID,
    closing_spread: Optional[float] = None,
    closing_total: Optional[float] = None,
    closing_spread_1h: Optional[float] = None,
    closing_total_1h: Optional[float] = None,
) -> int:
    """
    Capture closing lines for pending recommendations and calculate CLV.

    Should be called just before game starts (or shortly after tip-off).
    This is the GOLD STANDARD for measuring betting model quality.

    Returns: number of recommendations updated
    """
    now = datetime.utcnow()
    updated = 0

    # Update each bet type with its closing line
    bet_type_lines = [
        ("SPREAD", closing_spread),
        ("TOTAL", closing_total),
        ("SPREAD_1H", closing_spread_1h),
        ("TOTAL_1H", closing_total_1h),
    ]

    for bet_type, closing_line in bet_type_lines:
        if closing_line is None:
            continue

        # Calculate CLV based on bet type and pick
        stmt = text(
            """
            UPDATE betting_recommendations
            SET
                closing_line = :closing_line,
                closing_line_captured_at = :captured_at,
                clv = CASE
                    -- For spreads: CLV depends on which side we took
                    WHEN bet_type IN ('SPREAD', 'SPREAD_1H') AND pick = 'HOME' THEN
                        line - :closing_line  -- If line moved against home (more negative), we got value
                    WHEN bet_type IN ('SPREAD', 'SPREAD_1H') AND pick = 'AWAY' THEN
                        :closing_line - line  -- If line moved toward away (more positive), we got value
                    -- For totals: CLV depends on OVER/UNDER
                    WHEN bet_type IN ('TOTAL', 'TOTAL_1H') AND pick = 'OVER' THEN
                        :closing_line - line  -- If total moved up, we got value on OVER
                    WHEN bet_type IN ('TOTAL', 'TOTAL_1H') AND pick = 'UNDER' THEN
                        line - :closing_line  -- If total moved down, we got value on UNDER
                    ELSE 0
                END,
                clv_percent = CASE
                    WHEN :closing_line != 0 THEN
                        CASE
                            WHEN bet_type IN ('SPREAD', 'SPREAD_1H') AND pick = 'HOME' THEN
                                ((line - :closing_line) / ABS(:closing_line)) * 100
                            WHEN bet_type IN ('SPREAD', 'SPREAD_1H') AND pick = 'AWAY' THEN
                                ((:closing_line - line) / ABS(:closing_line)) * 100
                            WHEN bet_type IN ('TOTAL', 'TOTAL_1H') AND pick = 'OVER' THEN
                                ((:closing_line - line) / ABS(:closing_line)) * 100
                            WHEN bet_type IN ('TOTAL', 'TOTAL_1H') AND pick = 'UNDER' THEN
                                ((line - :closing_line) / ABS(:closing_line)) * 100
                            ELSE 0
                        END
                    ELSE 0
                END
            WHERE game_id = :game_id
              AND bet_type = :bet_type
              AND status = 'pending'
              AND closing_line IS NULL
            """
        )

        with engine.begin() as conn:
            res = conn.execute(stmt, {
                "game_id": game_id,
                "bet_type": bet_type,
                "closing_line": closing_line,
                "captured_at": now,
            })
            updated += int(res.rowcount or 0)

    return updated


def settle_recommendations(
    engine: Engine,
    game_id: UUID,
    home_score: int,
    away_score: int,
    home_score_1h: Optional[int] = None,
    away_score_1h: Optional[int] = None,
) -> dict:
    """
    Settle all pending recommendations for a game.

    Calculates actual result (WIN/LOSS/PUSH) and P&L for each bet.

    Returns: dict with settlement summary
    """
    now = datetime.utcnow()
    actual_spread = away_score - home_score  # From home perspective (positive = home lost)
    actual_total = home_score + away_score
    actual_spread_1h = (away_score_1h - home_score_1h) if home_score_1h is not None and away_score_1h is not None else None
    actual_total_1h = (home_score_1h + away_score_1h) if home_score_1h is not None and away_score_1h is not None else None

    results = {"wins": 0, "losses": 0, "pushes": 0, "total_pnl": 0.0}

    # Fetch all pending recommendations
    fetch_stmt = text(
        """
        SELECT id, bet_type, pick, line, recommended_units
        FROM betting_recommendations
        WHERE game_id = :game_id AND status = 'pending'
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(fetch_stmt, {"game_id": game_id}).fetchall()

        for row in rows:
            rec_id, bet_type, pick, line, units = row
            result = None
            pnl = 0.0

            # Determine result based on bet type
            if bet_type == "SPREAD":
                if actual_spread is not None:
                    if pick == "HOME":
                        # Home covers if actual_spread < line (they lost by less than spread)
                        if actual_spread < line:
                            result = "WIN"
                            pnl = units * 0.909  # -110 odds
                        elif actual_spread > line:
                            result = "LOSS"
                            pnl = -units
                        else:
                            result = "PUSH"
                            pnl = 0
                    else:  # AWAY
                        if actual_spread > -line:
                            result = "WIN"
                            pnl = units * 0.909
                        elif actual_spread < -line:
                            result = "LOSS"
                            pnl = -units
                        else:
                            result = "PUSH"
                            pnl = 0

            elif bet_type == "TOTAL":
                if actual_total is not None:
                    if pick == "OVER":
                        if actual_total > line:
                            result = "WIN"
                            pnl = units * 0.909
                        elif actual_total < line:
                            result = "LOSS"
                            pnl = -units
                        else:
                            result = "PUSH"
                            pnl = 0
                    else:  # UNDER
                        if actual_total < line:
                            result = "WIN"
                            pnl = units * 0.909
                        elif actual_total > line:
                            result = "LOSS"
                            pnl = -units
                        else:
                            result = "PUSH"
                            pnl = 0

            elif bet_type == "SPREAD_1H":
                if actual_spread_1h is not None:
                    if pick == "HOME":
                        if actual_spread_1h < line:
                            result = "WIN"
                            pnl = units * 0.909
                        elif actual_spread_1h > line:
                            result = "LOSS"
                            pnl = -units
                        else:
                            result = "PUSH"
                            pnl = 0
                    else:  # AWAY
                        if actual_spread_1h > -line:
                            result = "WIN"
                            pnl = units * 0.909
                        elif actual_spread_1h < -line:
                            result = "LOSS"
                            pnl = -units
                        else:
                            result = "PUSH"
                            pnl = 0

            elif bet_type == "TOTAL_1H":
                if actual_total_1h is not None:
                    if pick == "OVER":
                        if actual_total_1h > line:
                            result = "WIN"
                            pnl = units * 0.909
                        elif actual_total_1h < line:
                            result = "LOSS"
                            pnl = -units
                        else:
                            result = "PUSH"
                            pnl = 0
                    else:  # UNDER
                        if actual_total_1h < line:
                            result = "WIN"
                            pnl = units * 0.909
                        elif actual_total_1h > line:
                            result = "LOSS"
                            pnl = -units
                        else:
                            result = "PUSH"
                            pnl = 0

            # Update the recommendation
            if result:
                update_stmt = text(
                    """
                    UPDATE betting_recommendations
                    SET status = 'settled',
                        actual_result = :result,
                        pnl = :pnl,
                        settled_at = :settled_at
                    WHERE id = :rec_id
                    """
                )
                conn.execute(update_stmt, {
                    "rec_id": rec_id,
                    "result": result,
                    "pnl": pnl,
                    "settled_at": now,
                })

                if result == "WIN":
                    results["wins"] += 1
                elif result == "LOSS":
                    results["losses"] += 1
                else:
                    results["pushes"] += 1
                results["total_pnl"] += pnl

    return results


def get_clv_summary(engine: Engine, model_version: Optional[str] = None) -> dict:
    """
    Get CLV summary statistics for all settled bets.

    This is the GOLD STANDARD metric for model quality.
    Positive average CLV = model is finding value.

    Returns: dict with CLV statistics
    """
    where_clause = "WHERE br.closing_line IS NOT NULL"
    params = {}

    if model_version:
        where_clause += " AND p.model_version = :model_version"
        params["model_version"] = model_version

    stmt = text(
        f"""
        SELECT
            COUNT(*) as total_bets,
            AVG(br.clv) as avg_clv,
            AVG(br.clv_percent) as avg_clv_percent,
            SUM(CASE WHEN br.clv > 0 THEN 1 ELSE 0 END) as positive_clv_count,
            SUM(CASE WHEN br.clv < 0 THEN 1 ELSE 0 END) as negative_clv_count,
            AVG(br.pnl) as avg_pnl,
            SUM(br.pnl) as total_pnl,
            COUNT(CASE WHEN br.actual_result = 'WIN' THEN 1 END) as wins,
            COUNT(CASE WHEN br.actual_result = 'LOSS' THEN 1 END) as losses,
            COUNT(CASE WHEN br.actual_result = 'PUSH' THEN 1 END) as pushes
        FROM betting_recommendations br
        JOIN predictions p ON br.prediction_id = p.id
        {where_clause}
        """
    )

    with engine.begin() as conn:
        row = conn.execute(stmt, params).fetchone()
        if row:
            total = row[0] or 0
            wins = row[7] or 0
            losses = row[8] or 0
            return {
                "total_bets": total,
                "avg_clv": float(row[1] or 0),
                "avg_clv_percent": float(row[2] or 0),
                "positive_clv_rate": (row[3] / total * 100) if total > 0 else 0,
                "negative_clv_rate": (row[4] / total * 100) if total > 0 else 0,
                "avg_pnl_per_bet": float(row[5] or 0),
                "total_pnl": float(row[6] or 0),
                "wins": wins,
                "losses": losses,
                "pushes": row[9] or 0,
                "win_rate": (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0,
            }
        return {}

