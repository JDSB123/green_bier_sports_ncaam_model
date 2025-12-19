#!/usr/bin/env python3
"""
NCAA Basketball Predictions - Single Self-Contained Entry Point

ONE SOURCE OF TRUTH: Everything runs inside this container.
No local vs container distinction - always uses container network.

Usage:
    python run_today.py                    # Full slate today
    python run_today.py --no-sync          # Skip data sync
    python run_today.py --game "Duke" "UNC"  # Specific game
    python run_today.py --date 2025-12-20    # Specific date
"""

import sys
import os
import io
import argparse
from datetime import datetime, date, timezone, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict

from sqlalchemy import create_engine, text

# Use existing Go/Rust binaries (reuse all hard work!)
# No need to recreate - just call the proven binaries
import subprocess

# Import prediction engine (direct, no HTTP)
from app.predictor import prediction_engine
from app.models import TeamRatings, MarketOdds

# Central Time Zone
CST = ZoneInfo("America/Chicago")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - Always uses container network
# ═══════════════════════════════════════════════════════════════════════════════

# ALWAYS use container network (postgres:5432)
# No local vs container distinction - ONE source of truth
# Read secrets from Docker secret files - REQUIRED, NO fallbacks
def _read_required_secret(file_path: str, secret_name: str) -> str:
    """Read secret from Docker secret file - FAILS HARD if missing."""
    try:
        with open(file_path, 'r') as f:
            value = f.read().strip()
            if not value:
                raise ValueError(f"Secret file {file_path} is empty")
            return value
    except FileNotFoundError:
        raise FileNotFoundError(
            f"CRITICAL: Secret file not found: {file_path} ({secret_name}). "
            f"Container must have secrets mounted. Check docker-compose.yml secrets configuration."
        )

DB_PASSWORD = _read_required_secret("/run/secrets/db_password", "db_password")
REDIS_PASSWORD = _read_required_secret("/run/secrets/redis_password", "redis_password")
DATABASE_URL = f"postgresql://ncaam:{DB_PASSWORD}@postgres:5432/ncaam"

# Model parameters (from config, but display here for clarity)
HCA_SPREAD = float(os.getenv('MODEL__HOME_COURT_ADVANTAGE_SPREAD', 3.0))
HCA_TOTAL = float(os.getenv('MODEL__HOME_COURT_ADVANTAGE_TOTAL', 4.5))
MIN_SPREAD_EDGE = float(os.getenv('MODEL__MIN_SPREAD_EDGE', 2.5))
MIN_TOTAL_EDGE = float(os.getenv('MODEL__MIN_TOTAL_EDGE', 3.0))


# ═══════════════════════════════════════════════════════════════════════════════
# DATA SYNC - Uses existing Go/Rust binaries (REUSE proven logic)
# ═══════════════════════════════════════════════════════════════════════════════

def sync_fresh_data(skip_sync: bool = False) -> bool:
    """
    Sync fresh odds and ratings using existing Go/Rust binaries.
    REUSES all the hard work: 900+ team variants, normalization, first half logic.
    """
    if skip_sync:
        print("⏭️  Skipping data sync (--no-sync flag)")
        return True
    
    print("🔄 Syncing fresh data...")
    print()
    
    # Sync ratings using existing Go binary (proven normalization logic)
    print("  📊 Syncing ratings from Barttorvik (Go binary)...")
    try:
        result = subprocess.run(
            ["/app/bin/ratings-sync"],
            env={
                **os.environ,
                "DATABASE_URL": DATABASE_URL,
                "RUN_ONCE": "true",
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("  ✓ Ratings synced successfully")
            ratings_success = True
        else:
            print(f"  ⚠️  Ratings sync returned code {result.returncode}")
            if result.stderr:
                error_lines = result.stderr.strip().split('\n')[-3:]
                for line in error_lines:
                    print(f"      {line}")
            ratings_success = False
    except subprocess.TimeoutExpired:
        print("  ⚠️  Ratings sync timed out (>2 min)")
        ratings_success = False
    except Exception as e:
        print(f"  ⚠️  Ratings sync error: {e}")
        ratings_success = False
    
    # Sync odds using existing Rust binary (proven first half/full game logic)
    print("  📈 Syncing odds from The Odds API (Rust binary)...")
    try:
        # Read API key from secret file if available
        odds_api_key_file = os.getenv("THE_ODDS_API_KEY_FILE", "/run/secrets/odds_api_key")
        odds_api_key = None
        if os.path.exists(odds_api_key_file):
            with open(odds_api_key_file, 'r') as f:
                odds_api_key = f.read().strip()
        else:
            odds_api_key = os.getenv("THE_ODDS_API_KEY", "")
        
        # Build Redis URL from secret (REQUIRED, no fallback)
        redis_url = f"redis://:{REDIS_PASSWORD}@redis:6379"
        
        result = subprocess.run(
            ["/app/bin/odds-ingestion"],
            env={
                **os.environ,
                "DATABASE_URL": DATABASE_URL,
                "REDIS_URL": redis_url,
                "THE_ODDS_API_KEY": odds_api_key,
                "RUN_ONCE": "true",
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("  ✓ Odds synced successfully")
            odds_success = True
        else:
            print(f"  ⚠️  Odds sync returned code {result.returncode}")
            if result.stderr:
                error_lines = result.stderr.strip().split('\n')[-3:]
                for line in error_lines:
                    print(f"      {line}")
            odds_success = False
    except subprocess.TimeoutExpired:
        print("  ⚠️  Odds sync timed out (>2 min)")
        odds_success = False
    except Exception as e:
        print(f"  ⚠️  Odds sync error: {e}")
        odds_success = False
    
    print()
    if ratings_success and odds_success:
        print("✓ Data sync complete")
    else:
        print("⚠️  Some data sync issues - predictions may use cached data")
    print()
    
    return ratings_success and odds_success


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_games_from_db(target_date: Optional[date] = None) -> List[Dict]:
    """
    Fetch games, odds, and ratings from database.
    
    Args:
        target_date: Date to fetch games for (defaults to today)
        
    Returns:
        List of game dicts with ratings and odds
    """
    if target_date is None:
        target_date = date.today()
    
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    
    query = text("""
        -- Full-game odds: Pinnacle only (sharp lines)
        WITH latest_odds AS (
            SELECT DISTINCT ON (game_id, market_type, period)
                game_id,
                market_type,
                period,
                home_line,
                away_line,
                total_line,
                home_price,
                away_price,
                over_price,
                under_price
            FROM odds_snapshots
            WHERE bookmaker = 'pinnacle'
              AND market_type IN ('spreads', 'totals', 'h2h')
              AND period = 'full'
            ORDER BY game_id, market_type, period, time DESC
        ),
        -- First half odds: Pinnacle/Bovada
        latest_odds_1h AS (
            SELECT DISTINCT ON (game_id, market_type, period)
                game_id,
                market_type,
                period,
                home_line,
                away_line,
                total_line,
                home_price,
                away_price,
                over_price,
                under_price
            FROM odds_snapshots
            WHERE bookmaker IN ('pinnacle', 'bovada')
              AND market_type IN ('spreads', 'totals', 'h2h')
              AND period = '1h'
            ORDER BY game_id, market_type, period, time DESC
        ),
        -- Latest ratings
        latest_ratings AS (
            SELECT DISTINCT ON (team_id)
                team_id,
                adj_o,
                adj_d,
                tempo,
                torvik_rank
            FROM team_ratings
            ORDER BY team_id, rating_date DESC
        )
        SELECT 
            g.id as game_id,
            g.commence_time,
            DATE(g.commence_time AT TIME ZONE 'America/Chicago') as date_cst,
            TO_CHAR(g.commence_time AT TIME ZONE 'America/Chicago', 'HH24:MI') as time_cst,
            g.commence_time AT TIME ZONE 'America/Chicago' as datetime_cst,
            ht.canonical_name as home,
            at.canonical_name as away,
            g.is_neutral,
            -- Full game odds
            MAX(CASE WHEN lo.market_type = 'spreads' THEN lo.home_line END) as spread,
            MAX(CASE WHEN lo.market_type = 'spreads' THEN lo.home_price END) as spread_home_juice,
            MAX(CASE WHEN lo.market_type = 'spreads' THEN lo.away_price END) as spread_away_juice,
            MAX(CASE WHEN lo.market_type = 'totals' THEN lo.total_line END) as total,
            MAX(CASE WHEN lo.market_type = 'totals' THEN lo.over_price END) as over_juice,
            MAX(CASE WHEN lo.market_type = 'totals' THEN lo.under_price END) as under_juice,
            MAX(CASE WHEN lo.market_type = 'h2h' THEN lo.home_price END) as home_ml,
            MAX(CASE WHEN lo.market_type = 'h2h' THEN lo.away_price END) as away_ml,
            -- First half odds
            MAX(CASE WHEN lo1h.market_type = 'spreads' THEN lo1h.home_line END) as spread_1h,
            MAX(CASE WHEN lo1h.market_type = 'spreads' THEN lo1h.home_price END) as spread_1h_home_juice,
            MAX(CASE WHEN lo1h.market_type = 'spreads' THEN lo1h.away_price END) as spread_1h_away_juice,
            MAX(CASE WHEN lo1h.market_type = 'totals' THEN lo1h.total_line END) as total_1h,
            MAX(CASE WHEN lo1h.market_type = 'totals' THEN lo1h.over_price END) as over_1h_juice,
            MAX(CASE WHEN lo1h.market_type = 'totals' THEN lo1h.under_price END) as under_1h_juice,
            MAX(CASE WHEN lo1h.market_type = 'h2h' THEN lo1h.home_price END) as home_ml_1h,
            MAX(CASE WHEN lo1h.market_type = 'h2h' THEN lo1h.away_price END) as away_ml_1h,
            -- Home team ratings
            htr.adj_o as home_adj_o,
            htr.adj_d as home_adj_d,
            htr.tempo as home_tempo,
            htr.torvik_rank as home_rank,
            -- Away team ratings
            atr.adj_o as away_adj_o,
            atr.adj_d as away_adj_d,
            atr.tempo as away_tempo,
            atr.torvik_rank as away_rank
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.id
        JOIN teams at ON g.away_team_id = at.id
        LEFT JOIN latest_odds lo ON g.id = lo.game_id
        LEFT JOIN latest_odds_1h lo1h ON g.id = lo1h.game_id
        LEFT JOIN latest_ratings htr ON ht.id = htr.team_id
        LEFT JOIN latest_ratings atr ON at.id = atr.team_id
        WHERE DATE(g.commence_time AT TIME ZONE 'America/Chicago') = :target_date
          AND g.status = 'scheduled'
        GROUP BY 
            g.id, g.commence_time, ht.canonical_name, at.canonical_name, g.is_neutral,
            htr.adj_o, htr.adj_d, htr.tempo, htr.torvik_rank,
            atr.adj_o, atr.adj_d, atr.tempo, atr.torvik_rank
        ORDER BY g.commence_time
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"target_date": target_date})
        rows = result.fetchall()
        
        games = []
        for row in rows:
            # Build home ratings
            home_ratings = None
            if row.home_adj_o and row.home_adj_d:
                home_ratings = {
                    "team_name": row.home,
                    "adj_o": float(row.home_adj_o),
                    "adj_d": float(row.home_adj_d),
                    "tempo": float(row.home_tempo) if row.home_tempo else 70.0,
                    "rank": int(row.home_rank) if row.home_rank else 100,
                }
            
            # Build away ratings
            away_ratings = None
            if row.away_adj_o and row.away_adj_d:
                away_ratings = {
                    "team_name": row.away,
                    "adj_o": float(row.away_adj_o),
                    "adj_d": float(row.away_adj_d),
                    "tempo": float(row.away_tempo) if row.away_tempo else 70.0,
                    "rank": int(row.away_rank) if row.away_rank else 100,
                }
            
            game = {
                "game_id": str(row.game_id),
                "date_cst": str(row.date_cst),
                "time_cst": row.time_cst,
                "datetime_cst": row.datetime_cst,
                "home": row.home,
                "away": row.away,
                "is_neutral": bool(row.is_neutral) if row.is_neutral is not None else False,
                "spread": float(row.spread) if row.spread is not None else None,
                "spread_home_juice": int(row.spread_home_juice) if row.spread_home_juice else None,
                "spread_away_juice": int(row.spread_away_juice) if row.spread_away_juice else None,
                "total": float(row.total) if row.total is not None else None,
                "over_juice": int(row.over_juice) if row.over_juice else None,
                "under_juice": int(row.under_juice) if row.under_juice else None,
                "home_ml": int(row.home_ml) if row.home_ml else None,
                "away_ml": int(row.away_ml) if row.away_ml else None,
                "spread_1h": float(row.spread_1h) if row.spread_1h is not None else None,
                "spread_1h_home_juice": int(row.spread_1h_home_juice) if row.spread_1h_home_juice else None,
                "spread_1h_away_juice": int(row.spread_1h_away_juice) if row.spread_1h_away_juice else None,
                "total_1h": float(row.total_1h) if row.total_1h is not None else None,
                "over_1h_juice": int(row.over_1h_juice) if row.over_1h_juice else None,
                "under_1h_juice": int(row.under_1h_juice) if row.under_1h_juice else None,
                "home_ml_1h": int(row.home_ml_1h) if row.home_ml_1h else None,
                "away_ml_1h": int(row.away_ml_1h) if row.away_ml_1h else None,
                "home_ratings": home_ratings,
                "away_ratings": away_ratings,
            }
            games.append(game)
        
        return games


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTION - Direct import (no HTTP)
# ═══════════════════════════════════════════════════════════════════════════════

def get_prediction(
    home_team: str,
    away_team: str,
    home_ratings: Dict,
    away_ratings: Dict,
    market_odds: Optional[Dict] = None,
    is_neutral: bool = False,
) -> Dict:
    """
    Get prediction using direct import (no HTTP).
    
    Args:
        home_team: Home team name
        away_team: Away team name
        home_ratings: Home team ratings dict
        away_ratings: Away team ratings dict
        market_odds: Market odds dict (optional)
        is_neutral: True if neutral site
        
    Returns:
        Prediction result dict
    """
    # Convert to domain objects
    home_ratings_obj = TeamRatings(
        team_name=home_ratings["team_name"],
        adj_o=home_ratings["adj_o"],
        adj_d=home_ratings["adj_d"],
        tempo=home_ratings["tempo"],
        rank=home_ratings["rank"],
    )
    
    away_ratings_obj = TeamRatings(
        team_name=away_ratings["team_name"],
        adj_o=away_ratings["adj_o"],
        adj_d=away_ratings["adj_d"],
        tempo=away_ratings["tempo"],
        rank=away_ratings["rank"],
    )
    
    market_odds_obj = None
    if market_odds:
        market_odds_obj = MarketOdds(
            spread=market_odds.get("spread"),
            total=market_odds.get("total"),
            home_ml=market_odds.get("home_ml"),
            away_ml=market_odds.get("away_ml"),
            spread_1h=market_odds.get("spread_1h"),
            total_1h=market_odds.get("total_1h"),
            home_ml_1h=market_odds.get("home_ml_1h"),
            away_ml_1h=market_odds.get("away_ml_1h"),
        )
    
    # Generate prediction
    commence_time = datetime.now(timezone.utc)
    prediction = prediction_engine.make_prediction(
        game_id=uuid4(),
        home_team=home_team,
        away_team=away_team,
        commence_time=commence_time,
        home_ratings=home_ratings_obj,
        away_ratings=away_ratings_obj,
        market_odds=market_odds_obj,
        is_neutral=is_neutral,
    )
    
    # Generate recommendations
    recommendations = []
    if market_odds_obj:
        recommendations = prediction_engine.generate_recommendations(
            prediction, market_odds_obj
        )
    
    # Convert to dict
    prediction_dict = {
        k: (v.isoformat() if isinstance(v, datetime) else v)
        for k, v in prediction.__dict__.items()
    }
    
    recommendations_list = []
    for rec in recommendations:
        rec_dict = {
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in rec.__dict__.items()
        }
        rec_dict["summary"] = rec.summary
        rec_dict["executive_summary"] = rec.executive_summary
        rec_dict["detailed_rationale"] = rec.detailed_rationale
        recommendations_list.append(rec_dict)
    
    return {
        "prediction": prediction_dict,
        "recommendations": recommendations_list,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def format_spread(spread: Optional[float]) -> str:
    """Format spread for display."""
    if spread is None:
        return "N/A"
    return f"{spread:+.1f}"


def format_odds(odds: Optional[int]) -> str:
    """Format odds for display."""
    if odds is None:
        return "N/A"
    if odds > 0:
        return f"+{odds}"
    return str(odds)


def format_team_display(team: str, record: Optional[str] = None, rank: Optional[int] = None) -> str:
    """Format team name with optional record and rank."""
    parts = [team]
    if rank:
        parts.append(f"#{rank}")
    if record:
        parts.append(f"({record})")
    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point - handles all prompts."""
    parser = argparse.ArgumentParser(
        description="NCAA Basketball Predictions - Self-Contained Container Entry Point"
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip data sync (use cached data)"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date to fetch games for (YYYY-MM-DD, defaults to today)"
    )
    parser.add_argument(
        "--game",
        nargs=2,
        metavar=("HOME", "AWAY"),
        help="Specific game matchup (e.g., --game 'Duke' 'UNC')"
    )
    
    args = parser.parse_args()
    
    # Parse target date
    target_date = date.today()
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"✗ Invalid date format: {args.date}. Use YYYY-MM-DD")
            sys.exit(1)
    
    now_cst = datetime.now(CST)
    
    print()
    print("╔" + "═" * 118 + "╗")
    print("║" + f"  NCAA BASKETBALL PREDICTIONS - {now_cst.strftime('%A, %B %d, %Y')} @ {now_cst.strftime('%I:%M %p CST')}".ljust(118) + "║")
    print("║" + f"  Model: v5.0 Barttorvik | HCA: Spread={HCA_SPREAD}, Total={HCA_TOTAL} | Min Edge: {MIN_SPREAD_EDGE} pts".ljust(118) + "║")
    print("╚" + "═" * 118 + "╝")
    print()
    
    # Sync data (unless --no-sync)
    sync_fresh_data(skip_sync=args.no_sync)
    
    # Fetch games
    print(f"✓ Fetching games for {target_date}...")
    print()
    
    try:
        games = fetch_games_from_db(target_date=target_date)
    except Exception as e:
        print(f"✗ FATAL ERROR: Failed to fetch games: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    if not games:
        print(f"⚠️  No games found for {target_date}")
        sys.exit(0)
    
    # Filter by specific game if requested
    if args.game:
        home_filter, away_filter = args.game
        games = [
            g for g in games
            if home_filter.lower() in g["home"].lower()
            and away_filter.lower() in g["away"].lower()
        ]
        if not games:
            print(f"⚠️  No games found matching '{away_filter}' @ '{home_filter}'")
            sys.exit(0)
    
    print(f"✓ Found {len(games)} games")
    print()
    
    # Process each game
    all_picks = []
    for game in games:
        # Validate ratings
        if not game.get("home_ratings") or not game.get("away_ratings"):
            print(f"  ⚠️  Skipping {game['away']} @ {game['home']} - Missing ratings")
            continue
        
        # Validate odds
        if not game.get("spread") and not game.get("total"):
            print(f"  ⚠️  Skipping {game['away']} @ {game['home']} - Missing Pinnacle odds")
            continue
        
        # Build market odds
        market_odds = {
            "spread": game["spread"],
            "total": game["total"],
            "home_ml": game["home_ml"],
            "away_ml": game["away_ml"],
            "spread_1h": game.get("spread_1h"),
            "total_1h": game.get("total_1h"),
            "home_ml_1h": game.get("home_ml_1h"),
            "away_ml_1h": game.get("away_ml_1h"),
        }
        
        # Get prediction
        try:
            result = get_prediction(
                home_team=game["home"],
                away_team=game["away"],
                home_ratings=game["home_ratings"],
                away_ratings=game["away_ratings"],
                market_odds=market_odds,
                is_neutral=game.get("is_neutral", False),
            )
        except Exception as e:
            print(f"  ✗ Error predicting {game['away']} @ {game['home']}: {e}")
            continue
        
        pred = result["prediction"]
        recs = result["recommendations"]
        
        # Display game
        print(f"┌{'─' * 118}┐")
        print(f"│ {game['date_cst']} {game['time_cst']:<15} {game['away']:<40} @ {game['home']:<40} │")
        print(f"├{'─' * 118}┤")
        
        # Market line
        spread_str = f"{game['home']} {format_spread(game['spread'])}" if game['spread'] else "N/A"
        total_str = f"O/U {game['total']:.1f}" if game['total'] else "N/A"
        print(f"│ Market: {spread_str} | {total_str:<116} │")
        
        # Model prediction
        model_line = f"Model:  {game['home']} {format_spread(pred['predicted_spread'])} | O/U {pred['predicted_total']:.1f}"
        print(f"│ {model_line:<116} │")
        
        # Recommendations
        if recs:
            print(f"│ {'─' * 116} │")
            for rec in sorted(recs, key=lambda r: r['edge'], reverse=True):
                if rec['edge'] >= MIN_SPREAD_EDGE:
                    print(f"│ {rec['executive_summary']:<116} │")
        
        print(f"└{'─' * 118}┘")
        print()
        
        # Collect picks
        for rec in recs:
            if rec['edge'] >= MIN_SPREAD_EDGE:
                all_picks.append({
                    "game": f"{game['away']} @ {game['home']}",
                    "bet": rec['executive_summary'],
                    "edge": rec['edge'],
                })
    
    # Summary
    if all_picks:
        print("=" * 120)
        print(f"  🎯 BETTING RECOMMENDATIONS ({len(all_picks)} picks)")
        print("=" * 120)
        for pick in sorted(all_picks, key=lambda p: p['edge'], reverse=True):
            print(f"  {pick['game']}: {pick['bet']} (Edge: {pick['edge']:.1f} pts)")
    else:
        print("⚠️  No bets meet minimum edge thresholds")


if __name__ == "__main__":
    main()
