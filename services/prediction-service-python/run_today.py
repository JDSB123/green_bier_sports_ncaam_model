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
    python run_today.py --teams            # Send picks to Teams
    python run_today.py --teams-only       # Only send to Teams (no console)
"""

import sys
import os
import io
import argparse
from datetime import datetime, date, timezone, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict

from sqlalchemy import create_engine, text
import requests
import json

# Use existing Go/Rust binaries (reuse all hard work!)
# No need to recreate - just call the proven binaries
import subprocess

# Import prediction engine (direct, no HTTP)
from app.predictor import prediction_engine
from app.models import TeamRatings, MarketOdds
from app.situational import SituationalAdjuster, RestInfo
from app.persistence import persist_prediction_and_recommendations
from app.graph_upload import upload_file_to_teams
import csv
from pathlib import Path

# Central Time Zone
CST = ZoneInfo("America/Chicago")

def _configure_stdout() -> None:
    """
    Configure stdout encoding for Windows Azure CLI terminals.

    IMPORTANT: This must NOT run at import-time because other modules (e.g. FastAPI)
    import `run_today` and should not have their stdout replaced.
    """
    try:
        force_ascii = os.getenv("FORCE_ASCII_OUTPUT", "").strip().lower() in {"1", "true", "yes"}
        stdout_encoding = "ascii" if force_ascii else "utf-8"
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=stdout_encoding, errors="replace")
    except Exception:
        # Best effort only; never fail due to stdout wrapping.
        return

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


def _read_optional_secret_file(file_path: str, secret_name: str) -> str:
    """Best-effort secret read for OPTIONAL secrets (returns empty string if missing)."""
    try:
        return _read_secret_file(file_path, secret_name)
    except Exception:
        return ""

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
HCA_SPREAD = float(os.getenv('MODEL__HOME_COURT_ADVANTAGE_SPREAD', 3.2))
HCA_TOTAL = float(os.getenv('MODEL__HOME_COURT_ADVANTAGE_TOTAL', 0.0))
MIN_SPREAD_EDGE = float(os.getenv('MODEL__MIN_SPREAD_EDGE', 2.5))
MIN_TOTAL_EDGE = float(os.getenv('MODEL__MIN_TOTAL_EDGE', 3.0))
PICKS_OUTPUT_DIR = os.getenv("PICKS_OUTPUT_DIR", "/app/output")

# Teams Webhook URL for picks notifications (OPTIONAL)
# - Azure: set env var TEAMS_WEBHOOK_URL
# - Docker: mount secret file at /run/secrets/teams_webhook_url or set TEAMS_WEBHOOK_URL
_teams_webhook_file = os.getenv("TEAMS_WEBHOOK_URL_FILE", "/run/secrets/teams_webhook_url")
TEAMS_WEBHOOK_URL = (
    os.getenv("TEAMS_WEBHOOK_URL")
    or _read_optional_secret_file(_teams_webhook_file, "teams_webhook_url")
    or ""
)

# Teams Webhook Secret for validating outgoing webhook messages (OPTIONAL)
# - Azure: set env var TEAMS_WEBHOOK_SECRET
# - Docker: mount secret file at /run/secrets/teams_webhook_secret or set TEAMS_WEBHOOK_SECRET
_teams_webhook_secret_file = os.getenv("TEAMS_WEBHOOK_SECRET_FILE", "/run/secrets/teams_webhook_secret")
TEAMS_WEBHOOK_SECRET = (
    os.getenv("TEAMS_WEBHOOK_SECRET")
    or _read_optional_secret_file(_teams_webhook_secret_file, "teams_webhook_secret")
    or ""
)


def _is_placeholder_teams_webhook(url: str) -> bool:
    u = (url or "").strip().lower()
    if not u:
        return True
    if "change_me" in u or u.startswith("sample") or u.startswith("your_") or u.startswith("<your"):
        return True
    # Basic sanity: Teams webhooks are long and contain webhook.office.com
    if "webhook.office.com" not in u:
        return True
    if len(u) < 60:
        return True
    return False


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
    
    # Sync odds - try Rust binary first, fall back to Python if not available
    odds_success = False
    rust_binary = "/app/bin/odds-ingestion"
    
    if os.path.exists(rust_binary):
        print("  📈 Syncing odds from The Odds API (Rust binary)...")
        try:
            # Get API key from env (Azure) or Docker secret file (Compose)
            odds_api_key = os.getenv("THE_ODDS_API_KEY") or _read_secret_file("/run/secrets/odds_api_key", "odds_api_key")
            
            result = subprocess.run(
                [rust_binary],
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
                print("  ✓ Odds synced successfully (Rust)")
                odds_success = True
            else:
                print(f"  ⚠️  Rust odds sync returned code {result.returncode}")
                if result.stderr:
                    error_lines = result.stderr.strip().split('\n')[-3:]
                    for line in error_lines:
                        print(f"      {line}")
        except subprocess.TimeoutExpired:
            print("  ⚠️  Rust odds sync timed out (>2 min)")
        except Exception as e:
            print(f"  ⚠️  Rust odds sync error: {e}")
    
    # Fall back to Python-based odds sync if Rust binary not available or failed
    if not odds_success:
        print("  📈 Syncing odds from The Odds API (Python fallback)...")
        try:
            from app.odds_sync import sync_odds
            sync_result = sync_odds(
                database_url=DATABASE_URL,
                enable_full=True,
                enable_h1=True,
                enable_h2=False,
            )
            if sync_result["success"]:
                print(f"  ✓ Odds synced successfully (Python): {sync_result['total_snapshots']} snapshots")
                odds_success = True
            else:
                print(f"  ⚠️  Python odds sync error: {sync_result.get('error', 'unknown')}")
        except Exception as e:
            print(f"  ⚠️  Python odds sync error: {e}")

    # Basic resilience: if either sync failed, attempt one quick retry for transient issues
    if not (ratings_success and odds_success):
        print("  🔁 One quick retry for transient sync issues...")
        try:
            # Retry ratings using Go binary if available
            if not ratings_success and os.path.exists("/app/bin/ratings-sync"):
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

            # Retry odds using Python sync
            if not odds_success:
                try:
                    from app.odds_sync import sync_odds
                    sync_result = sync_odds(
                        database_url=DATABASE_URL,
                        enable_full=True,
                        enable_h1=True,
                        enable_h2=False,
                    )
                    odds_success = sync_result["success"]
                except Exception:
                    pass
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

def fetch_games_from_db(target_date: Optional[date] = None, engine=None) -> List[Dict]:
    """
    Fetch games, odds, and ratings from database.
    
    Args:
        target_date: Date to fetch games for (defaults to today)
        
    Returns:
        List of game dicts with ratings and odds
    """
    if target_date is None:
        target_date = date.today()
    
    engine = engine or create_engine(DATABASE_URL, pool_pre_ping=True)
    
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
        -- v6.3: ALL 22 Barttorvik fields are REQUIRED - no fallbacks, no optional data
        -- The Go sync service captures everything - we use everything
        latest_ratings AS (
            SELECT DISTINCT ON (team_id)
                team_id,
                -- Core efficiency
                adj_o,
                adj_d,
                tempo,
                torvik_rank,
                wins,
                losses,
                -- Four Factors: Shooting
                efg,
                efgd,
                -- Four Factors: Turnovers
                tor,
                tord,
                -- Four Factors: Rebounding
                orb,
                drb,
                -- Four Factors: Free Throws
                ftr,
                ftrd,
                -- Shooting Breakdown
                two_pt_pct,
                two_pt_pct_d,
                three_pt_pct,
                three_pt_pct_d,
                three_pt_rate,
                three_pt_rate_d,
                -- Quality Metrics
                barthag,
                wab,
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
            -- Home team ratings (ALL 22 fields - REQUIRED)
            htr.adj_o as home_adj_o,
            htr.adj_d as home_adj_d,
            htr.tempo as home_tempo,
            htr.torvik_rank as home_rank,
            htr.efg as home_efg,
            htr.efgd as home_efgd,
            htr.tor as home_tor,
            htr.tord as home_tord,
            htr.orb as home_orb,
            htr.drb as home_drb,
            htr.ftr as home_ftr,
            htr.ftrd as home_ftrd,
            htr.two_pt_pct as home_two_pt_pct,
            htr.two_pt_pct_d as home_two_pt_pct_d,
            htr.three_pt_pct as home_three_pt_pct,
            htr.three_pt_pct_d as home_three_pt_pct_d,
            htr.three_pt_rate as home_three_pt_rate,
            htr.three_pt_rate_d as home_three_pt_rate_d,
            htr.barthag as home_barthag,
            htr.wab as home_wab,
            -- Away team ratings (ALL 22 fields - REQUIRED)
            atr.adj_o as away_adj_o,
            atr.adj_d as away_adj_d,
            atr.tempo as away_tempo,
            atr.torvik_rank as away_rank,
            atr.efg as away_efg,
            atr.efgd as away_efgd,
            atr.tor as away_tor,
            atr.tord as away_tord,
            atr.orb as away_orb,
            atr.drb as away_drb,
            atr.ftr as away_ftr,
            atr.ftrd as away_ftrd,
            atr.two_pt_pct as away_two_pt_pct,
            atr.two_pt_pct_d as away_two_pt_pct_d,
            atr.three_pt_pct as away_three_pt_pct,
            atr.three_pt_pct_d as away_three_pt_pct_d,
            atr.three_pt_rate as away_three_pt_rate,
            atr.three_pt_rate_d as away_three_pt_rate_d,
            atr.barthag as away_barthag,
            atr.wab as away_wab,
            -- Team records (fresh from latest_ratings)
            htr.wins as home_wins,
            htr.losses as home_losses,
            atr.wins as away_wins,
            atr.losses as away_losses
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
            -- Home team ratings (all 22 fields)
            htr.adj_o, htr.adj_d, htr.tempo, htr.torvik_rank, htr.wins, htr.losses,
            htr.efg, htr.efgd, htr.tor, htr.tord, htr.orb, htr.drb, htr.ftr, htr.ftrd,
            htr.two_pt_pct, htr.two_pt_pct_d, htr.three_pt_pct, htr.three_pt_pct_d,
            htr.three_pt_rate, htr.three_pt_rate_d, htr.barthag, htr.wab,
            -- Away team ratings (all 22 fields)
            atr.adj_o, atr.adj_d, atr.tempo, atr.torvik_rank, atr.wins, atr.losses,
            atr.efg, atr.efgd, atr.tor, atr.tord, atr.orb, atr.drb, atr.ftr, atr.ftrd,
            atr.two_pt_pct, atr.two_pt_pct_d, atr.three_pt_pct, atr.three_pt_pct_d,
            atr.three_pt_rate, atr.three_pt_rate_d, atr.barthag, atr.wab
        ORDER BY g.commence_time
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"target_date": target_date})
        rows = result.fetchall()
        
        games = []
        for row in rows:
            # ═══════════════════════════════════════════════════════════════════════
            # v6.3: ALL 22 BARTTORVIK FIELDS ARE REQUIRED - NO FALLBACKS
            # If any field is missing, we log an error and skip the game.
            # The data pipeline must ensure complete data before predictions run.
            # ═══════════════════════════════════════════════════════════════════════

            # Check home team has ALL required fields
            home_required_fields = [
                row.home_adj_o, row.home_adj_d, row.home_tempo, row.home_rank,
                row.home_efg, row.home_efgd, row.home_tor, row.home_tord,
                row.home_orb, row.home_drb, row.home_ftr, row.home_ftrd,
                row.home_two_pt_pct, row.home_two_pt_pct_d,
                row.home_three_pt_pct, row.home_three_pt_pct_d,
                row.home_three_pt_rate, row.home_three_pt_rate_d,
                row.home_barthag, row.home_wab
            ]

            # Check away team has ALL required fields
            away_required_fields = [
                row.away_adj_o, row.away_adj_d, row.away_tempo, row.away_rank,
                row.away_efg, row.away_efgd, row.away_tor, row.away_tord,
                row.away_orb, row.away_drb, row.away_ftr, row.away_ftrd,
                row.away_two_pt_pct, row.away_two_pt_pct_d,
                row.away_three_pt_pct, row.away_three_pt_pct_d,
                row.away_three_pt_rate, row.away_three_pt_rate_d,
                row.away_barthag, row.away_wab
            ]

            # Build home ratings - ALL fields REQUIRED
            home_ratings = None
            if all(f is not None for f in home_required_fields):
                home_ratings = {
                    "team_name": row.home,
                    # Core efficiency
                    "adj_o": float(row.home_adj_o),
                    "adj_d": float(row.home_adj_d),
                    "tempo": float(row.home_tempo),
                    "rank": int(row.home_rank),
                    # Four Factors: Shooting
                    "efg": float(row.home_efg),
                    "efgd": float(row.home_efgd),
                    # Four Factors: Turnovers
                    "tor": float(row.home_tor),
                    "tord": float(row.home_tord),
                    # Four Factors: Rebounding
                    "orb": float(row.home_orb),
                    "drb": float(row.home_drb),
                    # Four Factors: Free Throws
                    "ftr": float(row.home_ftr),
                    "ftrd": float(row.home_ftrd),
                    # Shooting Breakdown
                    "two_pt_pct": float(row.home_two_pt_pct),
                    "two_pt_pct_d": float(row.home_two_pt_pct_d),
                    "three_pt_pct": float(row.home_three_pt_pct),
                    "three_pt_pct_d": float(row.home_three_pt_pct_d),
                    "three_pt_rate": float(row.home_three_pt_rate),
                    "three_pt_rate_d": float(row.home_three_pt_rate_d),
                    # Quality Metrics
                    "barthag": float(row.home_barthag),
                    "wab": float(row.home_wab),
                }

            # Build away ratings - ALL fields REQUIRED
            away_ratings = None
            if all(f is not None for f in away_required_fields):
                away_ratings = {
                    "team_name": row.away,
                    # Core efficiency
                    "adj_o": float(row.away_adj_o),
                    "adj_d": float(row.away_adj_d),
                    "tempo": float(row.away_tempo),
                    "rank": int(row.away_rank),
                    # Four Factors: Shooting
                    "efg": float(row.away_efg),
                    "efgd": float(row.away_efgd),
                    # Four Factors: Turnovers
                    "tor": float(row.away_tor),
                    "tord": float(row.away_tord),
                    # Four Factors: Rebounding
                    "orb": float(row.away_orb),
                    "drb": float(row.away_drb),
                    # Four Factors: Free Throws
                    "ftr": float(row.away_ftr),
                    "ftrd": float(row.away_ftrd),
                    # Shooting Breakdown
                    "two_pt_pct": float(row.away_two_pt_pct),
                    "two_pt_pct_d": float(row.away_two_pt_pct_d),
                    "three_pt_pct": float(row.away_three_pt_pct),
                    "three_pt_pct_d": float(row.away_three_pt_pct_d),
                    "three_pt_rate": float(row.away_three_pt_rate),
                    "three_pt_rate_d": float(row.away_three_pt_rate_d),
                    # Quality Metrics
                    "barthag": float(row.away_barthag),
                    "wab": float(row.away_wab),
                }
            
            game = {
                "game_id": row.game_id,
                "commence_time": row.commence_time,
                "date_cst": str(row.date_cst),
                "time_cst": row.time_cst,
                "datetime_cst": row.datetime_cst,
                "home": row.home,
                "away": row.away,
                "home_record": f"{int(row.home_wins)}-{int(row.home_losses)}" if row.home_wins is not None and row.home_losses is not None else None,
                "away_record": f"{int(row.away_wins)}-{int(row.away_losses)}" if row.away_wins is not None and row.away_losses is not None else None,
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
    game_id: Optional[UUID] = None,
    commence_time: Optional[datetime] = None,
    engine=None,
    persist: bool = True,
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
    # Convert to domain objects (v6.3: ALL 22 fields REQUIRED)
    home_ratings_obj = TeamRatings(
        team_name=home_ratings["team_name"],
        # Core efficiency
        adj_o=home_ratings["adj_o"],
        adj_d=home_ratings["adj_d"],
        tempo=home_ratings["tempo"],
        rank=home_ratings["rank"],
        # Four Factors: Shooting
        efg=home_ratings["efg"],
        efgd=home_ratings["efgd"],
        # Four Factors: Turnovers
        tor=home_ratings["tor"],
        tord=home_ratings["tord"],
        # Four Factors: Rebounding
        orb=home_ratings["orb"],
        drb=home_ratings["drb"],
        # Four Factors: Free Throws
        ftr=home_ratings["ftr"],
        ftrd=home_ratings["ftrd"],
        # Shooting Breakdown
        two_pt_pct=home_ratings["two_pt_pct"],
        two_pt_pct_d=home_ratings["two_pt_pct_d"],
        three_pt_pct=home_ratings["three_pt_pct"],
        three_pt_pct_d=home_ratings["three_pt_pct_d"],
        three_pt_rate=home_ratings["three_pt_rate"],
        three_pt_rate_d=home_ratings["three_pt_rate_d"],
        # Quality Metrics
        barthag=home_ratings["barthag"],
        wab=home_ratings["wab"],
    )

    away_ratings_obj = TeamRatings(
        team_name=away_ratings["team_name"],
        # Core efficiency
        adj_o=away_ratings["adj_o"],
        adj_d=away_ratings["adj_d"],
        tempo=away_ratings["tempo"],
        rank=away_ratings["rank"],
        # Four Factors: Shooting
        efg=away_ratings["efg"],
        efgd=away_ratings["efgd"],
        # Four Factors: Turnovers
        tor=away_ratings["tor"],
        tord=away_ratings["tord"],
        # Four Factors: Rebounding
        orb=away_ratings["orb"],
        drb=away_ratings["drb"],
        # Four Factors: Free Throws
        ftr=away_ratings["ftr"],
        ftrd=away_ratings["ftrd"],
        # Shooting Breakdown
        two_pt_pct=away_ratings["two_pt_pct"],
        two_pt_pct_d=away_ratings["two_pt_pct_d"],
        three_pt_pct=away_ratings["three_pt_pct"],
        three_pt_pct_d=away_ratings["three_pt_pct_d"],
        three_pt_rate=away_ratings["three_pt_rate"],
        three_pt_rate_d=away_ratings["three_pt_rate_d"],
        # Quality Metrics
        barthag=away_ratings["barthag"],
        wab=away_ratings["wab"],
    )
    
    market_odds_obj = None
    if market_odds:
        market_odds_obj = MarketOdds(
            spread=market_odds.get("spread"),
            spread_price=market_odds.get("spread_price") or -110,
            total=market_odds.get("total"),
            over_price=market_odds.get("over_price") or -110,
            under_price=market_odds.get("under_price") or -110,
            home_ml=market_odds.get("home_ml"),
            away_ml=market_odds.get("away_ml"),
            spread_1h=market_odds.get("spread_1h"),
            spread_price_1h=market_odds.get("spread_price_1h"),
            total_1h=market_odds.get("total_1h"),
            over_price_1h=market_odds.get("over_price_1h"),
            under_price_1h=market_odds.get("under_price_1h"),
            home_ml_1h=market_odds.get("home_ml_1h"),
            away_ml_1h=market_odds.get("away_ml_1h"),
        )
    
    # Generate prediction (v6.2: pass rest info for situational adjustments)
    if commence_time is None:
        commence_time = datetime.now(timezone.utc)
    if game_id is None:
        raise ValueError("game_id is required for persistence and reproducibility")

    prediction = prediction_engine.make_prediction(
        game_id=game_id,
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

    # Persist to Postgres (prediction + recommendations)
    if persist and engine is not None:
        try:
            features = {
                "home_ratings": home_ratings,
                "away_ratings": away_ratings,
                "market_odds": market_odds or {},
                "is_neutral": is_neutral,
                "home_rest": vars(home_rest) if home_rest else None,
                "away_rest": vars(away_rest) if away_rest else None,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            persist_prediction_and_recommendations(
                engine=engine,
                prediction=prediction,
                recommendations=recommendations,
                features=features,
            )
        except Exception as e:
            # Do not fail the whole run if persistence has a transient issue.
            print(f"  ⚠️  Persistence warning for {away_team} @ {home_team}: {type(e).__name__}: {e}")
    
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


def format_team_display(team: str, record: Optional[str] = None, rank: Optional[int] = None) -> str:
    """Format team name with optional record and rank."""
    parts = [team]
    if rank:
        parts.append(f"#{rank}")
    if record:
        parts.append(f"({record})")
    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# TEAMS WEBHOOK NOTIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def send_picks_to_teams(all_picks: list, target_date, webhook_url: str = TEAMS_WEBHOOK_URL) -> bool:
    """
    Send picks to Microsoft Teams via webhook.
    
    Args:
        all_picks: List of pick dictionaries
        target_date: Date of the picks
        webhook_url: Teams webhook URL
        
    Returns:
        True if successful, False otherwise
    """
    if not all_picks:
        print("  ⚠️  No picks to send to Teams")
        return False
    
    if _is_placeholder_teams_webhook(webhook_url):
        print("  ⚠️  No Teams webhook URL configured")
        return False
    
    # Sort picks by edge descending
    sorted_picks = sorted(all_picks, key=lambda p: p['edge'], reverse=True)
    
    # Persist CSV to output directory (host-mounted via docker-compose).
    # To save directly into a Teams channel's "Shared Documents", set PICKS_OUTPUT_HOST_DIR
    # to your local OneDrive-synced folder for that channel (manual-only workflow).
    csv_path: Optional[Path] = None
    try:
        out_dir = Path(PICKS_OUTPUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(CST).strftime("%Y%m%d_%H%M%S")
        csv_path = out_dir / f"ncaam_picks_{target_date}_{ts}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "date_time_cst",
                    "matchup_away_vs_home",
                    "segment",
                    "recommended_pick_live_odds",
                    "market_pricing",
                    "model_expectation",
                    "edge",
                    "fire_rating",
                ]
            )
            for p in sorted_picks:
                matchup = f"{p['away']} ({p.get('away_record') or '?'}) vs {p['home']} ({p.get('home_record') or '?'})"
                date_time = f"{p.get('date_cst', target_date)} {p.get('time_cst','')}".strip()
                w.writerow(
                    [
                        date_time,
                        matchup,
                        p.get("period", ""),
                        p.get("pick_display", ""),
                        p.get("market_line", ""),
                        p.get("model_line", ""),
                        f"{p.get('edge', 0.0):.2f}",
                        p.get("fire_rating", ""),
                    ]
                )
        print(f"  ✓ CSV saved: {csv_path}")
    except Exception as e:
        print(f"  ⚠️  Failed to write CSV: {type(e).__name__}: {e}")

    # Generate HTML Report
    html_url = ""
    try:
        out_dir = Path("/app/output")
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / "latest_picks.html"
        
        # Simple CSS-styled HTML table
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>NCAAM Picks - {target_date}</title>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                h1 {{ color: #333; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th {{ background: #2c3e50; color: white; padding: 12px; text-align: left; }}
                td {{ padding: 12px; border-bottom: 1px solid #ddd; }}
                tr:hover {{ background-color: #f9f9f9; }}
                .fire {{ color: #e74c3c; font-weight: bold; }}
                .edge-high {{ color: #27ae60; font-weight: bold; }}
                .timestamp {{ color: #7f8c8d; font-size: 0.9em; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏀 NCAAM Predictions</h1>
                <div class="timestamp">Generated: {datetime.now(CST).strftime("%Y-%m-%d %H:%M CST")} | Target Date: {target_date}</div>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Matchup</th>
                            <th>Seg</th>
                            <th>Pick</th>
                            <th>Market</th>
                            <th>Model</th>
                            <th>Edge</th>
                            <th>Fire</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for p in sorted_picks:
            matchup = f"{p['away']} vs {p['home']}"
            edge_val = p.get('edge', 0.0)
            edge_class = "edge-high" if edge_val > 3.0 else ""
            
            html_content += f"""
                        <tr>
                            <td>{p.get('time_cst', '')}</td>
                            <td>{matchup}</td>
                            <td>{p.get('period', '')}</td>
                            <td>{p.get('pick_display', '')}</td>
                            <td>{p.get('market_line', '')}</td>
                            <td>{p.get('model_line', '')}</td>
                            <td class="{edge_class}">{edge_val:.1f}</td>
                            <td class="fire">{p.get('fire_rating', '')}</td>
                        </tr>
            """
            
        html_content += """
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        
        with html_path.open("w", encoding="utf-8") as f:
            f.write(html_content)
            
        # URL where this file will be served
        # We need the base URL of the container app. We can get it from env or just relative.
        # Since we send this to Teams, we need absolute URL.
        # We'll rely on the API to serve /output/latest_picks.html
        # Hardcoding the base URL for now based on your deployment
        base_url = "https://ncaam-prod-prediction.bluecoast-4efaeaba.centralus.azurecontainerapps.io"
        html_url = f"{base_url}/picks/html"
        print(f"  ✓ HTML saved: {html_path}")
        
        # Upload to Microsoft Graph (SharePoint/Teams)
        upload_success = upload_file_to_teams(html_path, target_date)
        if upload_success:
            print("  ✓ HTML uploaded to Teams Shared Documents")
        
    except Exception as e:
        print(f"  ⚠️  Failed to generate HTML: {e}")

    # Build simple Adaptive Card format (ColumnSet tables don't render in Teams Workflow webhooks)
    now_cst = datetime.now(CST)
    
    # Build top picks as simple text lines (proven to work)
    top_picks_lines = []
    for p in sorted_picks[:10]:
        pick_display = p.get('pick_display', '')
        edge_str = f"{p['edge']:.1f}"
        fire = p.get('fire_rating', '')
        # Format: "🔥🔥 Siena +23.5 @ Indiana (31 pts edge)"
        matchup = f"@ {p['home']}" if p.get('pick_side') == 'away' else f"vs {p['away']}"
        top_picks_lines.append(f"{fire} {pick_display} {matchup} ({edge_str} edge)")
    
    top_picks_text = "\n".join(top_picks_lines) if top_picks_lines else "No picks found"
    
    # Count max plays
    max_plays = [p for p in sorted_picks if p.get('bet_tier') == 'MAX' or p['edge'] >= 5.0]
    max_count = len(max_plays)
    
    # Build simple Adaptive Card that actually works
    card_payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "size": "Large",
                            "weight": "Bolder",
                            "text": f"🏀 NCAAM PICKS - {target_date}"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"{len(sorted_picks)} picks | {max_count} max plays | {now_cst.strftime('%I:%M %p CST')}",
                            "wrap": True,
                            "isSubtle": True
                        },
                        {
                            "type": "TextBlock",
                            "text": f"**TOP 10 PLAYS:**",
                            "wrap": True,
                            "weight": "Bolder",
                            "spacing": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": top_picks_text,
                            "wrap": True,
                            "fontType": "Monospace",
                            "size": "Small"
                        }
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "📄 Full Report",
                            "url": html_url or "https://ncaam-prod-prediction.bluecoast-4efaeaba.centralus.azurecontainerapps.io/picks/html"
                        }
                    ]
                }
            }
        ]
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=card_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200 or response.status_code == 202:
            print(f"  ✓ Picks sent to Teams successfully ({len(sorted_picks)} picks)")
            return True
        else:
            print(f"  ⚠️  Teams webhook returned status {response.status_code}: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("  ⚠️  Teams webhook timed out")
        return False
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️  Teams webhook error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point - handles all prompts."""
    _configure_stdout()
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
    parser.add_argument(
        "--teams",
        action="store_true",
        help="Send picks to Microsoft Teams webhook"
    )
    parser.add_argument(
        "--teams-only",
        action="store_true",
        help="Only send to Teams (skip console output)"
    )
    parser.add_argument(
        "--no-settle",
        action="store_true",
        help="Skip score sync + bet settlement/report"
    )
    parser.add_argument(
        "--settle-only",
        action="store_true",
        help="Only run score sync + settlement/report (no new predictions)"
    )
    parser.add_argument(
        "--settle-days-from",
        type=int,
        default=3,
        help="How many days back to request from The Odds API /scores (default: 3)"
    )
    parser.add_argument(
        "--report-days",
        type=int,
        default=30,
        help="Lookback window for ROI/CLV report in days (default: 30)"
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
    print("║" + f"  Model: v6.3 Barttorvik | HCA: Spread={HCA_SPREAD}, Total={HCA_TOTAL} | Min Edge: {MIN_SPREAD_EDGE} pts".ljust(118) + "║")
    print("╚" + "═" * 118 + "╝")
    print()
    
    # Sync data (unless --no-sync)
    sync_fresh_data(skip_sync=args.no_sync)
    
    # Create DB engine once for the entire run (predictions persistence + settlement).
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    # Optional: score sync + settlement + ROI report (production auditing)
    if not args.no_settle:
        try:
            from app.settlement import sync_final_scores, settle_pending_bets, print_performance_report

            print("🔁 Syncing final scores + settling pending bets...")
            score_summary = sync_final_scores(engine, days_from=args.settle_days_from)
            settle_summary = settle_pending_bets(engine)
            print(
                f"  ✓ Scores: fetched={score_summary.fetched_events} completed={score_summary.completed_events} "
                f"updated_games={score_summary.updated_games} missing_games={score_summary.missing_games}"
            )
            print(
                f"  ✓ Settlement: settled={settle_summary.settled} W-L-P={settle_summary.wins}-{settle_summary.losses}-{settle_summary.pushes} "
                f"skipped_1H_missing_scores={settle_summary.skipped_missing_scores_1h} missing_closing_line={settle_summary.missing_closing_line}"
            )
            if not args.teams_only:
                print_performance_report(engine, lookback_days=args.report_days)
        except Exception as e:
            print(f"  ⚠️  Settlement step failed: {type(e).__name__}: {e}")

        if args.settle_only:
            return

    # Fetch games
    print(f"✓ Fetching games for {target_date}...")
    print()
    
    try:
        games = fetch_games_from_db(target_date=target_date, engine=engine)
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
            "spread_price": game.get("spread_home_juice") or game.get("spread_away_juice"),
            "total": game["total"],
            "over_price": game.get("over_juice"),
            "under_price": game.get("under_juice"),
            "home_ml": game["home_ml"],
            "away_ml": game["away_ml"],
            "spread_1h": game.get("spread_1h"),
            "spread_price_1h": game.get("spread_1h_home_juice") or game.get("spread_1h_away_juice"),
            "total_1h": game.get("total_1h"),
            "over_price_1h": game.get("over_1h_juice"),
            "under_price_1h": game.get("under_1h_juice"),
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
                game_id=game.get("game_id"),
                commence_time=game.get("commence_time"),
                engine=engine,
                persist=True,
            )
        except Exception as e:
            print(f"  ✗ Error predicting {game['away']} @ {game['home']}: {e}")
            continue
        
        pred = result["prediction"]
        recs = result["recommendations"]
        
        # Collect picks for executive table
        for rec in recs:
            bet_type = rec.get('bet_type', '')
            # Apply correct thresholds (fix totals being over-selected by spread threshold)
            threshold = MIN_TOTAL_EDGE if "TOTAL" in bet_type else MIN_SPREAD_EDGE
            if rec['edge'] >= threshold:
                # Determine period and market type
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
                
                # Model line display (show from PICK perspective for spreads)
                if market == "SPREAD":
                    model_line_val_home = pred["predicted_spread"] if not is_1h else pred["predicted_spread_1h"]
                    model_line_val = model_line_val_home if pick_val == "HOME" else -model_line_val_home
                    model_str = f"{format_spread(model_line_val)}"
                elif market == "TOTAL":
                    model_line_val = pred["predicted_total"] if not is_1h else pred["predicted_total_1h"]
                    model_str = f"{model_line_val:.1f}"
                else:
                    # Moneyline expectation: show model fair odds for the chosen side + implied win prob
                    if pick_val == "HOME":
                        model_ml = pred.get("predicted_home_ml" if not is_1h else "predicted_home_ml_1h")
                        prob = pred.get("home_win_prob" if not is_1h else "home_win_prob_1h", 0.5)
                    else:
                        model_ml = pred.get("predicted_away_ml" if not is_1h else "predicted_away_ml_1h")
                        prob = 1 - pred.get("home_win_prob" if not is_1h else "home_win_prob_1h", 0.5)
                    model_str = f"{format_odds(model_ml)} ({prob*100:.1f}%)" if model_ml is not None else f"{prob*100:.1f}%"
                
                # Market line display with juice (show from PICK perspective)
                if market == "SPREAD":
                    mkt_line_home = game["spread"] if not is_1h else game.get("spread_1h")
                    mkt_line = mkt_line_home if pick_val == "HOME" else (-(mkt_line_home) if mkt_line_home is not None else None)
                    if not is_1h:
                        mkt_juice = game.get("spread_home_juice", -110) if pick_val == "HOME" else game.get("spread_away_juice", -110)
                    else:
                        mkt_juice = game.get("spread_1h_home_juice", -110) if pick_val == "HOME" else game.get("spread_1h_away_juice", -110)
                    market_str = f"{format_spread(mkt_line)} ({format_odds(mkt_juice)})"
                elif market == "TOTAL":
                    mkt_line = game["total"] if not is_1h else game.get("total_1h")
                    if not is_1h:
                        mkt_juice = game.get("over_juice", -110) if pick_val == "OVER" else game.get("under_juice", -110)
                    else:
                        mkt_juice = game.get("over_1h_juice", -110) if pick_val == "OVER" else game.get("under_1h_juice", -110)
                    market_str = f"{mkt_line:.1f} ({format_odds(mkt_juice)})"
                else:
                    market_str = f"{format_odds(ml_odds)}" if ml_odds is not None else "N/A"
                
                # Fire rating
                fire = get_fire_rating(rec['edge'], rec.get('bet_tier', 'STANDARD'))
                
                all_picks.append({
                    "date_cst": game.get("date_cst"),
                    "time_cst": game["time_cst"],
                    "home": game["home"],
                    "away": game["away"],
                    "home_record": game.get("home_record"),
                    "away_record": game.get("away_record"),
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
    
    # Print executive summary table (unless --teams-only)
    if not args.teams_only:
        print_executive_table(all_picks, target_date)
    
    # Send to Teams if requested
    if args.teams or args.teams_only:
        print()
        print("📤 Sending picks to Microsoft Teams...")
        send_picks_to_teams(all_picks, target_date)


if __name__ == "__main__":
    main()
