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
from app.situational import SituationalAdjuster, RestInfo

# Central Time Zone
CST = ZoneInfo("America/Chicago")

# NOTE: Azure CLI on Windows often runs with a legacy codepage and will crash
# when it receives Unicode output (emoji/box-drawing). When FORCE_ASCII_OUTPUT=1,
# we emit ASCII-only output by encoding with replacement.
_force_ascii = os.getenv("FORCE_ASCII_OUTPUT", "").strip().lower() in {"1", "true", "yes"}
_stdout_encoding = "ascii" if _force_ascii else "utf-8"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=_stdout_encoding, errors="replace")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - Always uses container network
# ═══════════════════════════════════════════════════════════════════════════════

# ALWAYS use container network (postgres:5432)
# No local vs container distinction - ONE source of truth
# Read secrets from Docker secret files - REQUIRED, NO fallbacks
def _read_secret_file(file_path: str, secret_name: str) -> str:
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

# Config sources:
# - Docker Compose: secrets are mounted at /run/secrets/*
# - Azure Container Apps: secrets are provided via env vars (no /run/secrets mount)

# Sport-parameterized database configuration (enables multi-sport deployment)
SPORT = os.getenv("SPORT", "ncaam")
DB_USER = os.getenv("DB_USER", SPORT)
DB_NAME = os.getenv("DB_NAME", SPORT)
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DB_PASSWORD = _read_secret_file("/run/secrets/db_password", "db_password")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    REDIS_PASSWORD = _read_secret_file("/run/secrets/redis_password", "redis_password")
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@redis:6379"

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
        # Get API key from env (Azure) or Docker secret file (Compose)
        odds_api_key = os.getenv("THE_ODDS_API_KEY") or _read_secret_file("/run/secrets/odds_api_key", "odds_api_key")
        
        result = subprocess.run(
            ["/app/bin/odds-ingestion"],
            env={
                **os.environ,
                "DATABASE_URL": DATABASE_URL,
                "REDIS_URL": REDIS_URL,
                "THE_ODDS_API_KEY": odds_api_key,
                # odds-ingestion starts a health server; the container's daemon already
                # binds the default 8083, so use an ephemeral port for one-shot runs.
                "HEALTH_PORT": "0",
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

    # Basic resilience: if either sync failed, attempt one quick retry for transient issues
    if not (ratings_success and odds_success):
        print("  🔁 One quick retry for transient sync issues...")
        try:
            # Retry ratings
            if not ratings_success:
                result = subprocess.run(
                    ["/app/bin/ratings-sync"],
                    env={
                        **os.environ,
                        "DATABASE_URL": DATABASE_URL,
                        "RUN_ONCE": "true",
                    },
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                ratings_success = (result.returncode == 0)

            # Retry odds
            if not odds_success:
                odds_api_key = os.getenv("THE_ODDS_API_KEY") or _read_secret_file("/run/secrets/odds_api_key", "odds_api_key")
                result = subprocess.run(
                    ["/app/bin/odds-ingestion"],
                    env={
                        **os.environ,
                        "DATABASE_URL": DATABASE_URL,
                        "REDIS_URL": REDIS_URL,
                        "THE_ODDS_API_KEY": odds_api_key,
                        "HEALTH_PORT": "0",
                        "RUN_ONCE": "true",
                    },
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                odds_success = (result.returncode == 0)
        except Exception as e:
            print(f"  ⚠️  Retry failed: {e}")
    
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
        -- Full-game odds: prefer Pinnacle, fallback Bovada, then any book
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
            WHERE market_type IN ('spreads', 'totals', 'h2h')
              AND period = 'full'
            ORDER BY
              game_id, market_type, period,
              (bookmaker = 'pinnacle') DESC,
              (bookmaker = 'bovada') DESC,
              time DESC
        ),
        -- First half odds: prefer Pinnacle/Bovada, then any book
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
            WHERE market_type IN ('spreads', 'totals', 'h2h')
              AND period = '1h'
            ORDER BY
              game_id, market_type, period,
              (bookmaker = 'pinnacle') DESC,
              (bookmaker = 'bovada') DESC,
              time DESC
        ),
        -- Latest ratings (filtered by target date to prevent future data leakage)
        -- FIX: Added WHERE clause to ensure we only use ratings available on game date
        -- v6.2: Added efg, efgd, three_pt_rate, three_pt_rate_d for dynamic variance
        latest_ratings AS (
            SELECT DISTINCT ON (team_id)
                team_id,
                adj_o,
                adj_d,
                tempo,
                torvik_rank,
                efg,
                efgd,
                three_pt_rate,
                three_pt_rate_d,
                rating_date
            FROM team_ratings
            WHERE rating_date <= :target_date
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
            htr.efg as home_efg,
            htr.efgd as home_efgd,
            htr.three_pt_rate as home_three_pt_rate,
            htr.three_pt_rate_d as home_three_pt_rate_d,
            -- Away team ratings
            atr.adj_o as away_adj_o,
            atr.adj_d as away_adj_d,
            atr.tempo as away_tempo,
            atr.torvik_rank as away_rank,
            atr.efg as away_efg,
            atr.efgd as away_efgd,
            atr.three_pt_rate as away_three_pt_rate,
            atr.three_pt_rate_d as away_three_pt_rate_d
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
            htr.efg, htr.efgd, htr.three_pt_rate, htr.three_pt_rate_d,
            atr.adj_o, atr.adj_d, atr.tempo, atr.torvik_rank,
            atr.efg, atr.efgd, atr.three_pt_rate, atr.three_pt_rate_d
        ORDER BY g.commence_time
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"target_date": target_date})
        rows = result.fetchall()
        
        games = []
        for row in rows:
            # Build home ratings (v6.2: include extended metrics for dynamic variance)
            home_ratings = None
            if row.home_adj_o and row.home_adj_d:
                home_ratings = {
                    "team_name": row.home,
                    "adj_o": float(row.home_adj_o),
                    "adj_d": float(row.home_adj_d),
                    "tempo": float(row.home_tempo) if row.home_tempo else 70.0,
                    "rank": int(row.home_rank) if row.home_rank else 100,
                    # v6.2 extended metrics
                    "efg": float(row.home_efg) if row.home_efg else None,
                    "efgd": float(row.home_efgd) if row.home_efgd else None,
                    "three_pt_rate": float(row.home_three_pt_rate) if row.home_three_pt_rate else None,
                    "three_pt_rate_d": float(row.home_three_pt_rate_d) if row.home_three_pt_rate_d else None,
                }

            # Build away ratings (v6.2: include extended metrics for dynamic variance)
            away_ratings = None
            if row.away_adj_o and row.away_adj_d:
                away_ratings = {
                    "team_name": row.away,
                    "adj_o": float(row.away_adj_o),
                    "adj_d": float(row.away_adj_d),
                    "tempo": float(row.away_tempo) if row.away_tempo else 70.0,
                    "rank": int(row.away_rank) if row.away_rank else 100,
                    # v6.2 extended metrics
                    "efg": float(row.away_efg) if row.away_efg else None,
                    "efgd": float(row.away_efgd) if row.away_efgd else None,
                    "three_pt_rate": float(row.away_three_pt_rate) if row.away_three_pt_rate else None,
                    "three_pt_rate_d": float(row.away_three_pt_rate_d) if row.away_three_pt_rate_d else None,
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
# GAME HISTORY FOR REST CALCULATION (v6.2)
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_team_game_history(team_name: str, before_date: datetime, engine) -> List[Dict]:
    """
    Fetch recent completed games for a team to calculate rest days.

    Args:
        team_name: Canonical team name
        before_date: Only include games before this datetime
        engine: SQLAlchemy engine

    Returns:
        List of recent game dicts with commence_time
    """
    query = text("""
        SELECT
            g.id as game_id,
            g.commence_time,
            g.status,
            ht.canonical_name as home_team,
            at.canonical_name as away_team
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.id
        JOIN teams at ON g.away_team_id = at.id
        WHERE (ht.canonical_name = :team_name OR at.canonical_name = :team_name)
          AND g.commence_time < :before_date
          AND g.status IN ('completed', 'final')
        ORDER BY g.commence_time DESC
        LIMIT 10
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"team_name": team_name, "before_date": before_date})
        rows = result.fetchall()

        games = []
        for row in rows:
            games.append({
                "game_id": str(row.game_id),
                "commence_time": row.commence_time,
                "status": row.status,
                "home_team": row.home_team,
                "away_team": row.away_team,
            })

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
    home_rest: Optional[RestInfo] = None,
    away_rest: Optional[RestInfo] = None,
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
        home_rest: Home team rest info (v6.2)
        away_rest: Away team rest info (v6.2)

    Returns:
        Prediction result dict
    """
    # Convert to domain objects (v6.2: include extended metrics)
    home_ratings_obj = TeamRatings(
        team_name=home_ratings["team_name"],
        adj_o=home_ratings["adj_o"],
        adj_d=home_ratings["adj_d"],
        tempo=home_ratings["tempo"],
        rank=home_ratings["rank"],
        efg=home_ratings.get("efg"),
        efgd=home_ratings.get("efgd"),
        three_pt_rate=home_ratings.get("three_pt_rate"),
        three_pt_rate_d=home_ratings.get("three_pt_rate_d"),
    )

    away_ratings_obj = TeamRatings(
        team_name=away_ratings["team_name"],
        adj_o=away_ratings["adj_o"],
        adj_d=away_ratings["adj_d"],
        tempo=away_ratings["tempo"],
        rank=away_ratings["rank"],
        efg=away_ratings.get("efg"),
        efgd=away_ratings.get("efgd"),
        three_pt_rate=away_ratings.get("three_pt_rate"),
        three_pt_rate_d=away_ratings.get("three_pt_rate_d"),
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
    
    # Generate prediction (v6.2: pass rest info for situational adjustments)
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
        home_rest=home_rest,
        away_rest=away_rest,
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
        rec_dict = {}
        for k, v in rec.__dict__.items():
            if isinstance(v, datetime):
                rec_dict[k] = v.isoformat()
            elif hasattr(v, 'value'):  # Enum type (BetType, Pick, BetTier)
                rec_dict[k] = v.value
            else:
                rec_dict[k] = v
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
    """Format American odds for display."""
    if odds is None:
        return "N/A"
    return f"{odds:+d}" if odds > 0 else str(odds)


def get_fire_rating(edge: float, bet_tier: str) -> str:
    """Get fire rating 1-5 based on edge and tier. 5 = MAX."""
    # Rating scale: ◆ = filled, ◇ = empty
    if bet_tier == "max" or edge >= 5.0:
        return "◆◆◆◆◆"  # 5/5 MAX
    elif bet_tier == "medium" or edge >= 4.0:
        return "◆◆◆◆◇"  # 4/5
    elif edge >= 3.5:
        return "◆◆◆◇◇"  # 3/5
    elif edge >= 3.0:
        return "◆◆◇◇◇"  # 2/5
    else:
        return "◆◇◇◇◇"  # 1/5


def print_executive_table(all_picks: list, target_date) -> None:
    """Print bottom-line-up-front executive summary table."""
    if not all_picks:
        print("\n⚠️  No bets meet minimum edge thresholds")
        return
    
    # Sort by fire rating (edge) descending
    sorted_picks = sorted(all_picks, key=lambda p: p['edge'], reverse=True)
    
    # Header
    print()
    print("┏" + "━" * 158 + "┓")
    print("┃" + f"  🎯 EXECUTIVE BETTING SUMMARY - {target_date} ({len(sorted_picks)} PICKS)".ljust(158) + "┃")
    print("┣" + "━" * 158 + "┫")
    
    # Column headers
    header = (
        f"┃ {'TIME CST':<10} │ {'MATCHUP':<35} │ {'PERIOD':<6} │ {'MARKET':<8} │ "
        f"{'PICK':<25} │ {'MODEL':<10} │ {'MARKET':<15} │ {'EDGE':<8} │ {'FIRE':<6} ┃"
    )
    print(header)
    print("┣" + "━" * 158 + "┫")
    
    # Data rows
    for pick in sorted_picks:
        time_str = pick['time_cst']
        matchup = f"{pick['away'][:15]} @ {pick['home'][:15]}"
        period = pick['period']
        market = pick['market']
        
        # Format pick with team name and odds
        pick_str = pick['pick_display']
        
        # Model and market predictions
        model_str = pick['model_line']
        market_str = pick['market_line']
        
        # Edge
        edge_str = f"{pick['edge']:.1f} pts" if pick['market'] != "ML" else f"{pick['edge']:.1f}%"
        
        # Fire rating
        fire = pick['fire_rating']
        
        row = (
            f"┃ {time_str:<10} │ {matchup:<35} │ {period:<6} │ {market:<8} │ "
            f"{pick_str:<25} │ {model_str:<10} │ {market_str:<15} │ {edge_str:<8} │ {fire:<6} ┃"
        )
        print(row)
    
    print("┗" + "━" * 158 + "┛")
    print()


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
    parser.add_argument(
        "--debug-skips",
        action="store_true",
        help="Print skipped games and why (missing ratings vs missing odds)"
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
    print("║" + f"  Model: v6.2 Barttorvik | HCA: Spread={HCA_SPREAD}, Total={HCA_TOTAL} | Min Edge: {MIN_SPREAD_EDGE} pts".ljust(118) + "║")
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

    # v6.2: Setup situational adjuster for rest day calculations
    situational_adjuster = SituationalAdjuster()
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    # Process each game
    all_picks = []
    games_processed = 0
    games_skipped = 0
    skipped_reasons = []

    for game in games:
        # Validate ratings
        if not game.get("home_ratings") or not game.get("away_ratings"):
            games_skipped += 1
            if args.debug_skips:
                skipped_reasons.append(
                    (
                        game["away"],
                        game["home"],
                        "missing_ratings",
                        bool(game.get("home_ratings")),
                        bool(game.get("away_ratings")),
                        game.get("spread"),
                        game.get("total"),
                    )
                )
            continue
        
        # Validate odds
        if game.get("spread") is None and game.get("total") is None:
            games_skipped += 1
            if args.debug_skips:
                skipped_reasons.append(
                    (
                        game["away"],
                        game["home"],
                        "missing_odds",
                        True,
                        True,
                        game.get("spread"),
                        game.get("total"),
                    )
                )
            continue
        
        games_processed += 1
        
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

        # v6.2: Compute rest info for situational adjustments
        game_datetime = game.get("datetime_cst")
        if game_datetime is None:
            # Fallback: use noon on the game date
            game_datetime = datetime.combine(target_date, datetime.min.time().replace(hour=12))
            game_datetime = game_datetime.replace(tzinfo=CST)

        home_rest = None
        away_rest = None
        try:
            # Fetch game history for each team
            home_history = fetch_team_game_history(game["home"], game_datetime, engine)
            away_history = fetch_team_game_history(game["away"], game_datetime, engine)

            # Compute rest info
            home_rest = situational_adjuster.compute_rest_info(
                team_name=game["home"],
                game_datetime=game_datetime,
                game_history=home_history,
            )
            away_rest = situational_adjuster.compute_rest_info(
                team_name=game["away"],
                game_datetime=game_datetime,
                game_history=away_history,
            )
        except Exception as e:
            # Log but don't fail - rest info is optional enhancement
            print(f"  ⚠️ Rest calc failed for {game['away']} @ {game['home']}: {e}")

        # Get prediction
        try:
            result = get_prediction(
                home_team=game["home"],
                away_team=game["away"],
                home_ratings=game["home_ratings"],
                away_ratings=game["away_ratings"],
                market_odds=market_odds,
                is_neutral=game.get("is_neutral", False),
                home_rest=home_rest,
                away_rest=away_rest,
            )
        except Exception as e:
            print(f"  ✗ Error predicting {game['away']} @ {game['home']}: {e}")
            continue
        
        pred = result["prediction"]
        recs = result["recommendations"]
        
        # Collect picks for executive table
        for rec in recs:
            if rec['edge'] >= MIN_SPREAD_EDGE:
                # Determine period and market type
                bet_type = rec['bet_type']
                is_1h = "1H" in bet_type
                period = "1H" if is_1h else "FULL"
                
                if "SPREAD" in bet_type:
                    market = "SPREAD"
                elif "TOTAL" in bet_type:
                    market = "TOTAL"
                else:
                    market = "ML"
                
                # Format pick display with team name and odds
                pick_val = rec['pick']
                if market == "SPREAD":
                    if pick_val == "HOME":
                        team_name = game["home"]
                        line = game["spread"] if not is_1h else game.get("spread_1h")
                        juice = game.get("spread_home_juice") if not is_1h else game.get("spread_1h_home_juice")
                    else:
                        team_name = game["away"]
                        line = -(game["spread"]) if game["spread"] and not is_1h else (-(game.get("spread_1h")) if game.get("spread_1h") else None)
                        juice = game.get("spread_away_juice") if not is_1h else game.get("spread_1h_away_juice")
                    pick_display = f"{team_name[:12]} {format_spread(line)} ({format_odds(juice)})"
                elif market == "TOTAL":
                    total_line = game["total"] if not is_1h else game.get("total_1h")
                    if pick_val == "OVER":
                        juice = game.get("over_juice") if not is_1h else game.get("over_1h_juice")
                        pick_display = f"OVER {total_line:.1f} ({format_odds(juice)})"
                    else:
                        juice = game.get("under_juice") if not is_1h else game.get("under_1h_juice")
                        pick_display = f"UNDER {total_line:.1f} ({format_odds(juice)})"
                else:  # Moneyline
                    if pick_val == "HOME":
                        team_name = game["home"]
                        ml_odds = game["home_ml"] if not is_1h else game.get("home_ml_1h")
                    else:
                        team_name = game["away"]
                        ml_odds = game["away_ml"] if not is_1h else game.get("away_ml_1h")
                    pick_display = f"{team_name[:12]} ML ({format_odds(ml_odds)})"
                
                # Model line display
                if market == "SPREAD":
                    model_line_val = pred["predicted_spread"] if not is_1h else pred["predicted_spread_1h"]
                    model_str = f"{format_spread(model_line_val)}"
                elif market == "TOTAL":
                    model_line_val = pred["predicted_total"] if not is_1h else pred["predicted_total_1h"]
                    model_str = f"{model_line_val:.1f}"
                else:
                    model_str = f"{pred.get('home_win_prob', 0.5)*100:.0f}%"
                
                # Market line display with juice
                if market == "SPREAD":
                    mkt_line = game["spread"] if not is_1h else game.get("spread_1h")
                    mkt_juice = game.get("spread_home_juice", -110) if not is_1h else game.get("spread_1h_home_juice", -110)
                    market_str = f"{format_spread(mkt_line)} ({format_odds(mkt_juice)})"
                elif market == "TOTAL":
                    mkt_line = game["total"] if not is_1h else game.get("total_1h")
                    mkt_juice = game.get("over_juice", -110) if not is_1h else game.get("over_1h_juice", -110)
                    market_str = f"{mkt_line:.1f} ({format_odds(mkt_juice)})"
                else:
                    market_str = f"See odds"
                
                # Fire rating
                fire = get_fire_rating(rec['edge'], rec.get('bet_tier', 'STANDARD'))
                
                all_picks.append({
                    "time_cst": game["time_cst"],
                    "home": game["home"],
                    "away": game["away"],
                    "period": period,
                    "market": market,
                    "pick_display": pick_display,
                    "model_line": model_str,
                    "market_line": market_str,
                    "edge": rec['edge'],
                    "bet_tier": rec.get('bet_tier', 'STANDARD'),
                    "fire_rating": fire,
                })
    
    print(f"✓ Processed {games_processed} games ({games_skipped} skipped - missing data)")
    if args.debug_skips and skipped_reasons:
        missing_ratings = sum(1 for r in skipped_reasons if r[2] == "missing_ratings")
        missing_odds = sum(1 for r in skipped_reasons if r[2] == "missing_odds")
        print(f"  - skipped breakdown: {missing_ratings} missing ratings, {missing_odds} missing odds")
        for away, home, reason, has_home_r, has_away_r, spread, total in skipped_reasons[:30]:
            print(f"  - SKIP ({reason}): {away} @ {home} | ratings(home={has_home_r}, away={has_away_r}) | spread={spread} total={total}")
    
    # Print executive summary table
    print_executive_table(all_picks, target_date)


if __name__ == "__main__":
    main()
