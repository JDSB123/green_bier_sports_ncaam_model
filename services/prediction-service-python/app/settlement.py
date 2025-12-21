"""
Score sync + bet settlement + performance reporting.

This is intentionally "manual-trigger friendly":
- `run_today.py` can call into this module at the start of a run to:
  - Pull recent final scores from The Odds API `/scores`
  - Update `games` rows (status + final score)
  - Settle any pending/placed bets in `betting_recommendations`
  - Print a CLV/ROI report grouped by market

Important limitations:
- We can only settle 1H markets if halftime scores are present in `games.home_score_1h`
  and `games.away_score_1h`. (This stack currently does not ingest halftime scores.)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.odds_api_client import OddsApiClient, OddsApiError


@dataclass
class ScoreSyncSummary:
    fetched_events: int
    completed_events: int
    updated_games: int
    missing_games: int


@dataclass
class SettlementSummary:
    settled: int
    wins: int
    losses: int
    pushes: int
    skipped_missing_scores_1h: int
    missing_closing_line: int


def _american_odds_to_prob(odds: int) -> float:
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    return 100.0 / (odds + 100.0)


def _profit_per_unit(odds: int) -> float:
    """Profit (not return) per 1 unit stake if the bet wins."""
    if odds >= 0:
        return odds / 100.0
    return 100.0 / abs(odds)


def sync_final_scores(engine: Engine, days_from: int = 3, sport_key: Optional[str] = None) -> ScoreSyncSummary:
    """
    Pull recent scores from The Odds API and update `games` final scores/status.
    """
    client = OddsApiClient(sport_key=sport_key)
    events = client.get_scores(days_from=days_from)

    fetched = len(events)
    completed = 0
    updated = 0
    missing = 0

    update_stmt = text(
        """
        UPDATE games
        SET
            status = 'completed',
            home_score = :home_score,
            away_score = :away_score,
            updated_at = NOW()
        WHERE external_id = :external_id
        """
    )

    with engine.begin() as conn:
        for ev in events:
            if not ev or not isinstance(ev, dict):
                continue

            external_id = ev.get("id")
            if not external_id:
                continue

            if not ev.get("completed"):
                continue

            scores = ev.get("scores") or []
            if not isinstance(scores, list) or len(scores) < 2:
                continue

            home_team = ev.get("home_team")
            away_team = ev.get("away_team")
            if not home_team or not away_team:
                continue

            score_map: Dict[str, Optional[int]] = {}
            for s in scores:
                if not isinstance(s, dict):
                    continue
                name = s.get("name")
                val = s.get("score")
                if not name or val is None:
                    continue
                try:
                    score_map[name] = int(val)
                except (TypeError, ValueError):
                    continue

            home_score = score_map.get(home_team)
            away_score = score_map.get(away_team)
            if home_score is None or away_score is None:
                # Some feeds may present different names; skip rather than corrupting.
                continue

            completed += 1
            res = conn.execute(
                update_stmt,
                {"external_id": external_id, "home_score": home_score, "away_score": away_score},
            )
            if (res.rowcount or 0) > 0:
                updated += 1
            else:
                missing += 1

    return ScoreSyncSummary(
        fetched_events=fetched,
        completed_events=completed,
        updated_games=updated,
        missing_games=missing,
    )


def _closing_snapshot(
    engine: Engine,
    game_id: UUID,
    market_type: str,
    period: str,
    commence_time: datetime,
) -> Optional[Dict[str, Any]]:
    """
    Get the "closing" snapshot: latest odds <= commence_time, preferring Pinnacle then Bovada.
    """
    stmt = text(
        """
        SELECT
            time,
            bookmaker,
            home_line,
            away_line,
            total_line,
            home_price,
            away_price,
            over_price,
            under_price
        FROM odds_snapshots
        WHERE game_id = :game_id
          AND market_type = :market_type
          AND period = :period
          AND time <= :commence_time
        ORDER BY
          (bookmaker = 'pinnacle') DESC,
          (bookmaker = 'bovada') DESC,
          time DESC
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            stmt,
            {
                "game_id": game_id,
                "market_type": market_type,
                "period": period,
                "commence_time": commence_time,
            },
        ).fetchone()
        if not row:
            return None
        return dict(row._mapping)


def _market_mapping(bet_type: str) -> Tuple[str, str]:
    """
    Map betting_recommendations.bet_type -> (odds_snapshots.market_type, odds_snapshots.period)
    """
    bet_type = (bet_type or "").upper()
    if bet_type == "SPREAD":
        return "spreads", "full"
    if bet_type == "TOTAL":
        return "totals", "full"
    if bet_type == "MONEYLINE":
        return "h2h", "full"
    if bet_type == "SPREAD_1H":
        return "spreads", "1h"
    if bet_type == "TOTAL_1H":
        return "totals", "1h"
    if bet_type == "MONEYLINE_1H":
        return "h2h", "1h"
    # Unknown: best effort
    return "unknown", "full"


def _settle_spread(pick: str, line: float, home_score: int, away_score: int) -> str:
    # line is from the PICK perspective:
    # - HOME: home_score + line vs away_score
    # - AWAY: away_score + line vs home_score
    pick = (pick or "").upper()
    if pick == "HOME":
        diff = (home_score + line) - away_score
    else:
        diff = (away_score + line) - home_score
    if diff > 0:
        return "won"
    if diff < 0:
        return "lost"
    return "push"


def _settle_total(pick: str, line: float, home_score: int, away_score: int) -> str:
    total = home_score + away_score
    pick = (pick or "").upper()
    if pick == "OVER":
        if total > line:
            return "won"
        if total < line:
            return "lost"
        return "push"
    # UNDER
    if total < line:
        return "won"
    if total > line:
        return "lost"
    return "push"


def _settle_moneyline(pick: str, home_score: int, away_score: int) -> str:
    pick = (pick or "").upper()
    if pick == "HOME":
        return "won" if home_score > away_score else "lost"
    return "won" if away_score > home_score else "lost"


def settle_pending_bets(engine: Engine) -> SettlementSummary:
    """
    Settle any pending/placed betting_recommendations where the game has final scores.
    Computes:
    - closing_line from odds_snapshots at commence_time
    - clv (market-dependent definition; positive means "beat close")
    - pnl in units (uses closing price for spread/total if available, else assumes -110)
    """
    fetch_stmt = text(
        """
        SELECT
            br.id,
            br.game_id,
            br.bet_type,
            br.pick,
            br.line,
            br.recommended_units,
            br.created_at,
            g.commence_time,
            g.home_score,
            g.away_score,
            g.home_score_1h,
            g.away_score_1h
        FROM betting_recommendations br
        JOIN games g ON g.id = br.game_id
        WHERE br.status IN ('pending', 'placed')
          AND g.status IN ('completed', 'final')
          AND g.home_score IS NOT NULL
          AND g.away_score IS NOT NULL
        ORDER BY br.created_at ASC
        """
    )

    update_stmt = text(
        """
        UPDATE betting_recommendations
        SET
            status = :status,
            actual_result = :actual_result,
            closing_line = :closing_line,
            clv = :clv,
            pnl = :pnl,
            settled_at = NOW()
        WHERE id = :id
        """
    )

    settled = wins = losses = pushes = 0
    skipped_1h = 0
    missing_close = 0

    with engine.begin() as conn:
        rows = conn.execute(fetch_stmt).fetchall()

    for row in rows:
        r = dict(row._mapping)

        bet_id: UUID = r["id"]
        game_id: UUID = r["game_id"]
        bet_type: str = r["bet_type"]
        pick: str = r["pick"]
        line = float(r["line"])
        stake = float(r.get("recommended_units") or 1.0)
        commence_time: datetime = r["commence_time"]

        # Choose which scores to use
        is_1h = bet_type.upper().endswith("_1H")
        if is_1h:
            h1 = r.get("home_score_1h")
            a1 = r.get("away_score_1h")
            if h1 is None or a1 is None:
                skipped_1h += 1
                continue
            home_score = int(h1)
            away_score = int(a1)
        else:
            home_score = int(r["home_score"])
            away_score = int(r["away_score"])

        # Closing snapshot
        market_type, period = _market_mapping(bet_type)
        snap = _closing_snapshot(engine, game_id, market_type, period, commence_time)
        if not snap:
            missing_close += 1

        closing_line = None
        clv_val = None
        price_for_pnl: Optional[int] = None

        bet_type_u = bet_type.upper()
        pick_u = (pick or "").upper()

        # Determine closing line + price based on market/pick
        if snap:
            if bet_type_u.startswith("SPREAD"):
                closing_line = float(snap["home_line"]) if pick_u == "HOME" else float(snap["away_line"])
                price_for_pnl = int(snap["home_price"] or -110) if pick_u == "HOME" else int(snap["away_price"] or -110)
                # Positive = beat close (got a better number than closing)
                clv_val = round(line - closing_line, 3)
            elif bet_type_u.startswith("TOTAL"):
                closing_line = float(snap["total_line"])
                if pick_u == "OVER":
                    price_for_pnl = int(snap["over_price"] or -110)
                    clv_val = round(closing_line - line, 3)  # closing higher than bet is good for OVER
                else:
                    price_for_pnl = int(snap["under_price"] or -110)
                    clv_val = round(line - closing_line, 3)  # bet higher than closing is good for UNDER
            else:
                # MONEYLINE: store CLV as implied probability delta in percentage points (positive = beat close)
                closing_odds = int(snap["home_price"]) if pick_u == "HOME" else int(snap["away_price"])
                bet_odds = int(round(line))
                clv_val = round((_american_odds_to_prob(closing_odds) - _american_odds_to_prob(bet_odds)) * 100.0, 3)
                closing_line = float(closing_odds)
                price_for_pnl = bet_odds  # use the bet odds we recorded as the payout basis
        else:
            # No closing snapshot: still settle outcome; assume -110 for spread/total
            if bet_type_u.startswith("SPREAD") or bet_type_u.startswith("TOTAL"):
                price_for_pnl = -110
            else:
                price_for_pnl = int(round(line))

        # Settle outcome
        if bet_type_u.startswith("SPREAD"):
            status = _settle_spread(pick_u, line, home_score, away_score)
            actual_result = f"{home_score}-{away_score}"
        elif bet_type_u.startswith("TOTAL"):
            status = _settle_total(pick_u, line, home_score, away_score)
            actual_result = f"{home_score + away_score} total ({home_score}-{away_score})"
        else:
            status = _settle_moneyline(pick_u, home_score, away_score)
            actual_result = f"{home_score}-{away_score}"

        pnl = 0.0
        if status == "won":
            pnl = stake * _profit_per_unit(int(price_for_pnl or -110))
            wins += 1
        elif status == "lost":
            pnl = -stake
            losses += 1
        else:
            pnl = 0.0
            pushes += 1

        with engine.begin() as conn:
            conn.execute(
                update_stmt,
                {
                    "id": bet_id,
                    "status": status,
                    "actual_result": actual_result,
                    "closing_line": closing_line,
                    "clv": clv_val,
                    "pnl": round(pnl, 3),
                },
            )

        settled += 1

    return SettlementSummary(
        settled=settled,
        wins=wins,
        losses=losses,
        pushes=pushes,
        skipped_missing_scores_1h=skipped_1h,
        missing_closing_line=missing_close,
    )


def print_performance_report(engine: Engine, lookback_days: int = 30) -> None:
    """
    Print ROI/CLV report grouped by bet_type for last N days (by created_at).
    """
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    stmt = text(
        """
        SELECT
            bet_type,
            COUNT(*) FILTER (WHERE status IN ('won','lost','push')) AS settled_bets,
            SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN status = 'push' THEN 1 ELSE 0 END) AS pushes,
            SUM(recommended_units) FILTER (WHERE status IN ('won','lost','push')) AS total_units,
            SUM(pnl) FILTER (WHERE status IN ('won','lost','push')) AS total_pnl,
            AVG(clv) FILTER (WHERE clv IS NOT NULL AND status IN ('won','lost','push')) AS avg_clv
        FROM betting_recommendations
        WHERE created_at >= :since
        GROUP BY bet_type
        ORDER BY bet_type
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(stmt, {"since": since}).fetchall()

    if not rows:
        print(f"📉 No settled bets in last {lookback_days} days")
        return

    print()
    print(f"📈 PERFORMANCE (last {lookback_days} days)")
    print("┏" + "━" * 98 + "┓")
    print("┃ " + f"{'BET TYPE':<14} {'BETS':>6} {'W-L-P':>9} {'UNITS':>10} {'PNL':>10} {'ROI':>8} {'AVG CLV':>10}".ljust(96) + " ┃")
    print("┣" + "━" * 98 + "┫")

    for row in rows:
        m = dict(row._mapping)
        bet_type = m["bet_type"]
        bets = int(m["settled_bets"] or 0)
        wins = int(m["wins"] or 0)
        losses = int(m["losses"] or 0)
        pushes = int(m["pushes"] or 0)
        units = float(m["total_units"] or 0.0)
        pnl = float(m["total_pnl"] or 0.0)
        avg_clv = m["avg_clv"]
        roi = (pnl / units) if units > 0 else 0.0

        avg_clv_str = f"{float(avg_clv):+.3f}" if avg_clv is not None else "N/A"

        line = (
            f"┃ {bet_type:<14} {bets:>6} {wins:>3}-{losses:<3}-{pushes:<3} "
            f"{units:>10.1f} {pnl:>+10.2f} {roi:>+7.1%} {avg_clv_str:>10} ┃"
        )
        print(line)

    print("┗" + "━" * 98 + "┛")
    print()


