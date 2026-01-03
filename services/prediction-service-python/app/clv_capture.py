"""
Pre-game CLV (Closing Line Value) capture utility.

This module provides functionality to capture true closing lines
just before game tip-off for accurate CLV measurement.

CLV is the gold standard metric for betting model quality.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine


def capture_pregame_closing_lines(
    engine: Engine,
    lookahead_minutes: int = 10,
    sport_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture closing lines for games starting in the next N minutes.
    
    This should be run ~5 min before tip-off to capture the true closing line.
    The closing line is the gold standard for measuring model quality.
    
    Args:
        engine: Database engine
        lookahead_minutes: How far ahead to look for starting games (default 10 min)
        sport_key: Optional sport key for odds API
        
    Returns:
        Dict with 'games_checked', 'snapshots_captured', 'recommendations_updated'
    """
    from app.odds_api_client import OddsApiClient, OddsApiError
    from app.persistence import capture_closing_lines
    
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=lookahead_minutes)
    
    # Find games starting soon that have pending bets
    stmt = text(
        """
        SELECT DISTINCT
            g.id as game_id,
            g.external_id,
            g.commence_time,
            g.home_team,
            g.away_team
        FROM games g
        INNER JOIN betting_recommendations br ON br.game_id = g.id
        WHERE br.status IN ('pending', 'placed')
          AND br.closing_line IS NULL
          AND g.commence_time BETWEEN :now AND :cutoff
        ORDER BY g.commence_time ASC
        """
    )
    
    games_checked = 0
    snapshots_captured = 0
    recommendations_updated = 0
    
    with engine.begin() as conn:
        games = conn.execute(stmt, {"now": now, "cutoff": cutoff}).fetchall()
    
    if not games:
        return {
            "games_checked": 0,
            "snapshots_captured": 0,
            "recommendations_updated": 0,
        }
    
    # Fetch current odds for these games
    try:
        client = OddsApiClient(sport_key=sport_key)
    except OddsApiError as e:
        return {
            "games_checked": len(games),
            "snapshots_captured": 0,
            "recommendations_updated": 0,
            "error": str(e),
        }
    
    for game_row in games:
        game = dict(game_row._mapping)
        game_id = game["game_id"]
        external_id = game["external_id"]
        games_checked += 1
        
        try:
            # Fetch current odds for this event
            event_odds = client.get_event_odds(
                external_id,
                markets="spreads,totals,spreads_h1,totals_h1",
            )
            
            bookmakers = event_odds.get("bookmakers") or []
            if not bookmakers:
                continue
            
            # Extract closing lines, preferring sharp books
            closing_spread = None
            closing_total = None
            closing_spread_1h = None
            closing_total_1h = None
            
            # Priority: Pinnacle > Bovada > Circa > first available
            priority_books = ["pinnacle", "bovada", "circa"]
            sorted_books = sorted(
                bookmakers,
                key=lambda b: (
                    0 if b.get("key") in priority_books else 1,
                    priority_books.index(b.get("key")) if b.get("key") in priority_books else 999,
                ),
            )
            
            for book in sorted_books:
                for market in book.get("markets") or []:
                    market_key = market.get("key", "")
                    outcomes = market.get("outcomes") or []
                    
                    if market_key == "spreads" and closing_spread is None:
                        for outcome in outcomes:
                            if outcome.get("name") == game.get("home_team"):
                                closing_spread = float(outcome.get("point", 0))
                                break
                    
                    elif market_key == "totals" and closing_total is None:
                        for outcome in outcomes:
                            if outcome.get("name") == "Over":
                                closing_total = float(outcome.get("point", 0))
                                break
                    
                    elif market_key == "spreads_h1" and closing_spread_1h is None:
                        for outcome in outcomes:
                            if outcome.get("name") == game.get("home_team"):
                                closing_spread_1h = float(outcome.get("point", 0))
                                break
                    
                    elif market_key == "totals_h1" and closing_total_1h is None:
                        for outcome in outcomes:
                            if outcome.get("name") == "Over":
                                closing_total_1h = float(outcome.get("point", 0))
                                break
            
            if any([closing_spread, closing_total, closing_spread_1h, closing_total_1h]):
                snapshots_captured += 1
                updated = capture_closing_lines(
                    engine,
                    game_id,
                    closing_spread=closing_spread,
                    closing_total=closing_total,
                    closing_spread_1h=closing_spread_1h,
                    closing_total_1h=closing_total_1h,
                )
                recommendations_updated += updated
        
        except OddsApiError:
            continue
    
    return {
        "games_checked": games_checked,
        "snapshots_captured": snapshots_captured,
        "recommendations_updated": recommendations_updated,
    }
