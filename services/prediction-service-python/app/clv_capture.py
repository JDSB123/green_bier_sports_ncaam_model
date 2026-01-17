"""
Pre-game CLV (Closing Line Value) capture utility.

This module provides functionality to capture true closing lines
just before game tip-off for accurate CLV measurement.

CLV is the gold standard metric for betting model quality.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


def capture_pregame_closing_lines(
    engine: Engine,
    lookahead_minutes: int = 10,
    sport_key: str | None = None,
) -> dict[str, Any]:
    """
    Capture closing lines for games starting in the next N minutes.

    This should be run ~5 min before tip-off to capture the true closing line.
    The closing line is the gold standard for measuring model quality.

    Args:
        engine: Database engine
        lookahead_minutes: How far ahead to look for starting games (default 10 min)
        sport_key: Optional sport key for odds API

    Returns:
        Dict with:
        - games_checked: number of games considered in the window
        - snapshots_inserted: number of odds_snapshots rows inserted/updated
        - error: optional error string when odds API client initialization fails
    """
    from app.odds_api_client import OddsApiClient, OddsApiError

    now = datetime.now(UTC)
    cutoff = now + timedelta(minutes=lookahead_minutes)

    # Find games starting soon that have pending bets
    stmt = text(
        """
        SELECT DISTINCT
            g.id as game_id,
            g.external_id,
            g.commence_time,
            ht.canonical_name as home_team,
            at.canonical_name as away_team
        FROM games g
        JOIN teams ht ON ht.id = g.home_team_id
        JOIN teams at ON at.id = g.away_team_id
        INNER JOIN betting_recommendations br ON br.game_id = g.id
        WHERE br.status IN ('pending', 'placed')
          AND br.closing_line IS NULL
          AND g.commence_time BETWEEN :now AND :cutoff
        ORDER BY g.commence_time ASC
        """
    )

    games_checked = 0
    snapshots_inserted = 0

    with engine.begin() as conn:
        games = conn.execute(stmt, {"now": now, "cutoff": cutoff}).fetchall()

    if not games:
        return {
            "games_checked": 0,
            "snapshots_inserted": 0,
        }

    # Fetch current odds for these games
    try:
        client = OddsApiClient(sport_key=sport_key)
    except OddsApiError as e:
        return {
            "games_checked": len(games),
            "snapshots_inserted": 0,
            "error": str(e),
        }

    for game_row in games:
        game = dict(game_row._mapping)
        game_id = game["game_id"]
        external_id = game["external_id"]
        commence_time = game.get("commence_time") or now
        games_checked += 1

        try:
            if not external_id:
                continue

            # Fetch current odds for this event from sharp books
            event_odds = client.get_closing_lines_for_event(external_id)
            bookmakers = event_odds.get("bookmakers") or []
            if not bookmakers:
                continue

            event_home = event_odds.get("home_team") or game.get("home_team")
            event_away = event_odds.get("away_team") or game.get("away_team")

            # Store as odds_snapshots so the settlement logic can compute true closing line later.
            # Important: ensure snapshot time <= commence_time so it is eligible as "closing".
            snapshot_time = now if now <= commence_time else commence_time

            rows = []
            for bookmaker in bookmakers:
                book_key = bookmaker.get("key")
                if not book_key:
                    continue
                for market in bookmaker.get("markets") or []:
                    market_key = (market.get("key") or "").lower()
                    outcomes = market.get("outcomes") or []

                    if market_key in ("spreads", "spreads_h1"):
                        market_type = "spreads"
                        period = "1h" if market_key.endswith("_h1") else "full"
                        home_line = away_line = None
                        home_price = away_price = None
                        for outcome in outcomes:
                            name = outcome.get("name")
                            if name == event_home:
                                home_line = outcome.get("point")
                                home_price = outcome.get("price")
                            elif name == event_away:
                                away_line = outcome.get("point")
                                away_price = outcome.get("price")
                        rows.append(
                            {
                                "time": snapshot_time,
                                "game_id": game_id,
                                "bookmaker": book_key,
                                "market_type": market_type,
                                "period": period,
                                "home_line": home_line,
                                "away_line": away_line,
                                "total_line": None,
                                "home_price": home_price,
                                "away_price": away_price,
                                "over_price": None,
                                "under_price": None,
                            }
                        )
                    elif market_key in ("totals", "totals_h1"):
                        market_type = "totals"
                        period = "1h" if market_key.endswith("_h1") else "full"
                        total_line = None
                        over_price = under_price = None
                        for outcome in outcomes:
                            name = (outcome.get("name") or "").lower()
                            if name == "over":
                                total_line = outcome.get("point")
                                over_price = outcome.get("price")
                            elif name == "under":
                                under_price = outcome.get("price")
                        rows.append(
                            {
                                "time": snapshot_time,
                                "game_id": game_id,
                                "bookmaker": book_key,
                                "market_type": market_type,
                                "period": period,
                                "home_line": None,
                                "away_line": None,
                                "total_line": total_line,
                                "home_price": None,
                                "away_price": None,
                                "over_price": over_price,
                                "under_price": under_price,
                            }
                        )

            if not rows:
                continue

            insert_stmt = text(
                """
                INSERT INTO odds_snapshots (
                    time, game_id, bookmaker, market_type, period,
                    home_line, away_line, total_line,
                    home_price, away_price, over_price, under_price
                ) VALUES (
                    :time, :game_id, :bookmaker, :market_type, :period,
                    :home_line, :away_line, :total_line,
                    :home_price, :away_price, :over_price, :under_price
                )
                ON CONFLICT (time, game_id, bookmaker, market_type, period) DO UPDATE SET
                    home_line = EXCLUDED.home_line,
                    away_line = EXCLUDED.away_line,
                    total_line = EXCLUDED.total_line,
                    home_price = EXCLUDED.home_price,
                    away_price = EXCLUDED.away_price,
                    over_price = EXCLUDED.over_price,
                    under_price = EXCLUDED.under_price
                """
            )
            with engine.begin() as conn:
                conn.execute(insert_stmt, rows)
            snapshots_inserted += len(rows)

        except OddsApiError:
            continue

    return {
        "games_checked": games_checked,
        "snapshots_inserted": snapshots_inserted,
    }
