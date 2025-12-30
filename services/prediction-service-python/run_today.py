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

# Import prediction engine (v33.6 - modular independent models)
from app.prediction_engine_v33 import prediction_engine_v33 as prediction_engine
from app.models import TeamRatings, MarketOdds, BetType
from app.config import settings
from app.predictors import fg_spread_model, fg_total_model, h1_spread_model, h1_total_model
from app.situational import SituationalAdjuster, RestInfo
from app.persistence import persist_prediction_and_recommendations
from app.graph_upload import upload_file_to_teams
from validate_team_matching import TeamMatchingValidator
import csv
from pathlib import Path


def _check_recent_team_resolution(
    engine,
    lookback_days: int,
    min_resolution_rate: float,
) -> Dict[str, object]:
    """Fail-fast guardrail for canonical team matching quality.

    Uses `team_resolution_audit` in a recent window so historical one-off issues
    don't permanently block runs.
    """
    now_utc = datetime.now(timezone.utc)
    lookback_start = now_utc - timedelta(days=int(lookback_days))

    query = text(
        """
        SELECT
            COUNT(*)::int AS total,
            SUM(CASE WHEN resolved_name IS NOT NULL THEN 1 ELSE 0 END)::int AS resolved,
            SUM(CASE WHEN resolved_name IS NULL THEN 1 ELSE 0 END)::int AS unresolved
        FROM team_resolution_audit
        WHERE created_at >= :lookback_start
        """
    )
    by_source_query = text(
        """
        SELECT
            source,
            COUNT(*)::int AS total,
            SUM(CASE WHEN resolved_name IS NOT NULL THEN 1 ELSE 0 END)::int AS resolved,
            SUM(CASE WHEN resolved_name IS NULL THEN 1 ELSE 0 END)::int AS unresolved
        FROM team_resolution_audit
        WHERE created_at >= :lookback_start
        GROUP BY source
        ORDER BY total DESC
        """
    )

    with engine.connect() as conn:
        row = conn.execute(query, {"lookback_start": lookback_start}).fetchone()
        by_source_rows = conn.execute(by_source_query, {"lookback_start": lookback_start}).fetchall()

    total = int(row.total or 0) if row else 0
    resolved = int(row.resolved or 0) if row else 0
    unresolved = int(row.unresolved or 0) if row else 0
    rate = (resolved / total) if total else 0.0
    ok = bool(total > 0 and unresolved == 0 and rate >= float(min_resolution_rate))
    return {
        "ok": ok,
        "lookback_days": int(lookback_days),
        "min_resolution_rate": float(min_resolution_rate),
        "total": total,
        "resolved": resolved,
        "unresolved": unresolved,
        "rate": rate,
        "by_source": [
            {
                "source": r.source,
                "total": int(r.total or 0),
                "resolved": int(r.resolved or 0),
                "unresolved": int(r.unresolved or 0),
                "rate": (int(r.resolved or 0) / int(r.total or 0)) if int(r.total or 0) else 0.0,
            }
            for r in (by_source_rows or [])
        ],
    }

# Central Time Zone
CST = ZoneInfo("America/Chicago")

def _pct(numerator: int, denominator: int) -> float:
    return (numerator / denominator) if denominator else 0.0


def _summarize_data_quality(games: List[Dict]) -> Dict[str, int]:
    total = len(games)
    ratings_ok = sum(1 for g in games if g.get("home_ratings") and g.get("away_ratings"))
    odds_ok = sum(1 for g in games if g.get("spread") is not None or g.get("total") is not None)
    odds_prices_ok = sum(
        1
        for g in games
        if (
            (g.get("spread") is None or (g.get("spread_home_juice") is not None and g.get("spread_away_juice") is not None))
            and (g.get("total") is None or (g.get("over_juice") is not None and g.get("under_juice") is not None))
        )
    )
    ready_ok = sum(
        1
        for g in games
        if g.get("home_ratings")
        and g.get("away_ratings")
        and (g.get("spread") is not None or g.get("total") is not None)
    )
    h1_odds_ok = sum(
        1
        for g in games
        if g.get("spread_1h") is not None or g.get("total_1h") is not None
    )
    return {
        "total": total,
        "ratings_ok": ratings_ok,
        "odds_ok": odds_ok,
        "odds_prices_ok": odds_prices_ok,
        "ready_ok": ready_ok,
        "h1_odds_ok": h1_odds_ok,
    }


def _odds_snapshot_age_minutes(now_utc: datetime, snapshot_time: Optional[datetime]) -> Optional[float]:
    if snapshot_time is None:
        return None
    if snapshot_time.tzinfo is None:
        # Assume UTC if DB returned naive timestamps.
        snapshot_time = snapshot_time.replace(tzinfo=timezone.utc)
    return (now_utc - snapshot_time.astimezone(timezone.utc)).total_seconds() / 60.0


def _enforce_odds_freshness_and_completeness(
    games: List[Dict],
    max_age_full_minutes: int,
    max_age_1h_minutes: int,
) -> List[str]:
    """Fail-fast: no stale odds and no missing prices for any present market."""
    now_utc = datetime.now(timezone.utc)
    failures: List[str] = []

    for g in games:
        matchup = f"{g.get('away')} @ {g.get('home')}"

        # Full game spread
        if g.get("spread") is not None:
            if g.get("spread_home_juice") is None or g.get("spread_away_juice") is None:
                failures.append(f"{matchup}: missing full-game spread prices")
            age = _odds_snapshot_age_minutes(now_utc, g.get("spread_time"))
            if age is None:
                failures.append(f"{matchup}: missing full-game spread snapshot time")
            elif age > max_age_full_minutes:
                failures.append(
                    f"{matchup}: stale full-game spread odds ({age:.1f}m old > {max_age_full_minutes}m)"
                )

        # Full game total
        if g.get("total") is not None:
            if g.get("over_juice") is None or g.get("under_juice") is None:
                failures.append(f"{matchup}: missing full-game total prices")
            age = _odds_snapshot_age_minutes(now_utc, g.get("total_time"))
            if age is None:
                failures.append(f"{matchup}: missing full-game total snapshot time")
            elif age > max_age_full_minutes:
                failures.append(
                    f"{matchup}: stale full-game total odds ({age:.1f}m old > {max_age_full_minutes}m)"
                )

        # First half spread (only enforce freshness if market exists)
        if g.get("spread_1h") is not None:
            if g.get("spread_1h_home_juice") is None or g.get("spread_1h_away_juice") is None:
                failures.append(f"{matchup}: missing 1H spread prices")
            age = _odds_snapshot_age_minutes(now_utc, g.get("spread_1h_time"))
            if age is None:
                failures.append(f"{matchup}: missing 1H spread snapshot time")
            elif age > max_age_1h_minutes:
                failures.append(f"{matchup}: stale 1H spread odds ({age:.1f}m old > {max_age_1h_minutes}m)")

        # First half total
        if g.get("total_1h") is not None:
            if g.get("over_1h_juice") is None or g.get("under_1h_juice") is None:
                failures.append(f"{matchup}: missing 1H total prices")
            age = _odds_snapshot_age_minutes(now_utc, g.get("total_1h_time"))
            if age is None:
                failures.append(f"{matchup}: missing 1H total snapshot time")
            elif age > max_age_1h_minutes:
                failures.append(f"{matchup}: stale 1H total odds ({age:.1f}m old > {max_age_1h_minutes}m)")

    return failures


def _enforce_data_quality(summary: Dict[str, int], args: argparse.Namespace) -> List[str]:
    total = summary["total"]
    if total <= 0:
        return []

    ratings_pct = _pct(summary["ratings_ok"], total)
    odds_pct = _pct(summary["odds_ok"], total)
    ready_pct = _pct(summary["ready_ok"], total)
    h1_pct = _pct(summary["h1_odds_ok"], total)

    print(" Data Quality")
    print(f"   Ratings coverage: {summary['ratings_ok']}/{total} ({ratings_pct:.1%})")
    print(f"   Odds coverage:    {summary['odds_ok']}/{total} ({odds_pct:.1%})")
    print(f"   Ready coverage:   {summary['ready_ok']}/{total} ({ready_pct:.1%})")
    if args.min_1h_odds_pct > 0:
        print(f"   1H odds coverage: {summary['h1_odds_ok']}/{total} ({h1_pct:.1%})")

    failures = []
    if ratings_pct < args.min_ratings_pct:
        failures.append(f"ratings {ratings_pct:.1%} < {args.min_ratings_pct:.1%}")
    if odds_pct < args.min_odds_pct:
        failures.append(f"odds {odds_pct:.1%} < {args.min_odds_pct:.1%}")
    if ready_pct < args.min_ready_pct:
        failures.append(f"ready {ready_pct:.1%} < {args.min_ready_pct:.1%}")
    if args.min_1h_odds_pct > 0 and h1_pct < args.min_1h_odds_pct:
        failures.append(f"1H odds {h1_pct:.1%} < {args.min_1h_odds_pct:.1%}")

    if failures:
        print("[WARN]  Data quality below thresholds:")
        for failure in failures:
            print(f"   - {failure}")
        print("   Re-run with --allow-data-degrade to proceed anyway.")

    return failures


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

# ==============================================================================
# CONFIGURATION - Always uses container network
# ==============================================================================

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
    # Explicitly use psycopg2 driver (sync) to avoid asyncpg conflicts
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    REDIS_PASSWORD = _read_secret_file("/run/secrets/redis_password", "redis_password")
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@redis:6379"

# Output directory for picks/reports
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


# ==============================================================================
# DATA SYNC - Uses existing Go/Rust binaries (REUSE proven logic)
# ==============================================================================

def sync_fresh_data(skip_sync: bool = False) -> bool:
    """
    Sync fresh odds and ratings using existing Go/Rust binaries.
    REUSES all the hard work: 900+ team variants, normalization, first half logic.
    """
    if skip_sync:
        print("[SKIP]  Skipping data sync (--no-sync flag)")
        return True
    
    print(" Syncing fresh data...")
    print()
    
    # Sync ratings using existing Go binary (proven normalization logic)
    print("   Syncing ratings from Barttorvik (Go binary)...")
    
    # Go/Rust binaries expect standard postgres:// URL, not SQLAlchemy's postgresql+psycopg2://
    clean_db_url = DATABASE_URL.replace("+psycopg2", "")
    
    try:
        result = subprocess.run(
            ["/app/bin/ratings-sync"],
            env={
                **os.environ,
                "DATABASE_URL": clean_db_url,
                "RUN_ONCE": "true",
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("  [OK] Ratings synced successfully")
            ratings_success = True
        else:
            print(f"  [WARN]  Ratings sync returned code {result.returncode}")
            if result.stderr:
                error_lines = result.stderr.strip().split('\n')[-3:]
                for line in error_lines:
                    print(f"      {line}")
            ratings_success = False
    except subprocess.TimeoutExpired:
        print("  [WARN]  Ratings sync timed out (>2 min)")
        ratings_success = False
    except Exception as e:
        print(f"  [WARN]  Ratings sync error: {e}")
        ratings_success = False
    
    # Sync odds - try Rust binary first, fall back to Python if not available
    odds_success = False
    rust_binary = "/app/bin/odds-ingestion"
    
    if os.path.exists(rust_binary):
        print("  [INFO] Syncing odds from The Odds API (Rust binary)...")
        try:
            # Get API key from env (Azure: ODDS_API_KEY or THE_ODDS_API_KEY) or Docker secret file (Compose)
            odds_api_key = os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY") or _read_secret_file("/run/secrets/odds_api_key", "odds_api_key")
            
            result = subprocess.run(
                [rust_binary],
                env={
                    **os.environ,
                    "DATABASE_URL": clean_db_url,
                    "REDIS_URL": REDIS_URL,
                    "THE_ODDS_API_KEY": odds_api_key,
                    "ENABLE_FULL": "true",
                    "ENABLE_H1": "true",
                    "ENABLE_H2": "false",
                    "STRICT_TEAM_MATCHING": "true",
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
                print("  [OK] Odds synced successfully (Rust)")
                odds_success = True
            else:
                print(f"  [WARN]  Rust odds sync returned code {result.returncode}")
                if result.stderr:
                    error_lines = result.stderr.strip().split('\n')[-3:]
                    for line in error_lines:
                        print(f"      {line}")
        except subprocess.TimeoutExpired:
            print("  [WARN]  Rust odds sync timed out (>2 min)")
        except Exception as e:
            print(f"  [WARN]  Rust odds sync error: {e}")
    
    # Fall back to Python-based odds sync if Rust binary not available or failed
    if not odds_success:
        print("  [INFO] Syncing odds from The Odds API (Python fallback)...")
        try:
            from app.odds_sync import sync_odds
            sync_result = sync_odds(
                database_url=DATABASE_URL,
                enable_full=True,
                enable_h1=True,
                enable_h2=False,
            )
            if sync_result["success"]:
                print(f"  [OK] Odds synced successfully (Python): {sync_result['total_snapshots']} snapshots")
                odds_success = True
            else:
                print(f"  [WARN]  Python odds sync error: {sync_result.get('error', 'unknown')}")
        except Exception as e:
            print(f"  [WARN]  Python odds sync error: {e}")

    # Basic resilience: if either sync failed, attempt one quick retry for transient issues
    if not (ratings_success and odds_success):
        print("  [RETRY] One quick retry for transient sync issues...")
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
                except Exception as e:
                    print(f"  [WARN]  Retry odds sync failed: {type(e).__name__}: {e}")
        except Exception as e:
            print(f"  [WARN]  Retry failed: {e}")
    
    print()
    if ratings_success and odds_success:
        print("[OK] Data sync complete")
    else:
        print("[WARN]  Some data sync issues - predictions may use cached data")
    print()
    
    return ratings_success and odds_success


# ==============================================================================
# DATABASE FETCHING
# ==============================================================================

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
            WHERE market_type IN ('spreads', 'totals')
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
            WHERE market_type IN ('spreads', 'totals')
              AND period = '1h'
            ORDER BY
              game_id, market_type, period,
              (bookmaker = 'pinnacle') DESC,
              (bookmaker = 'bovada') DESC,
              time DESC
        ),
        -- Opening odds (earliest snapshot)
        open_odds AS (
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
            WHERE market_type IN ('spreads', 'totals')
              AND period = 'full'
            ORDER BY
              game_id, market_type, period,
              time ASC
        ),
        open_odds_1h AS (
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
            WHERE market_type IN ('spreads', 'totals')
              AND period = '1h'
            ORDER BY
              game_id, market_type, period,
              time ASC
        ),
        sharp_open_odds AS (
            SELECT DISTINCT ON (game_id, market_type)
                game_id,
                market_type,
                home_line as sharp_home_line_open,
                total_line as sharp_total_line_open
            FROM odds_snapshots
            WHERE bookmaker = 'pinnacle'
              AND period = 'full'
              AND market_type IN ('spreads', 'totals')
            ORDER BY game_id, market_type, time ASC
        ),
        -- Sharp book reference (Pinnacle ONLY) for CLV tracking
        sharp_odds AS (
            SELECT DISTINCT ON (game_id, market_type)
                game_id,
                market_type,
                home_line as sharp_home_line,
                total_line as sharp_total_line
            FROM odds_snapshots
            WHERE bookmaker = 'pinnacle'
              AND period = 'full'
              AND market_type IN ('spreads', 'totals')
            ORDER BY game_id, market_type, time DESC
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
            MAX(CASE WHEN lo.market_type = 'spreads' THEN lo.time END) as spread_time,
            MAX(CASE WHEN lo.market_type = 'spreads' THEN lo.bookmaker END) as spread_book,
            MAX(CASE WHEN lo.market_type = 'totals' THEN lo.total_line END) as total,
            MAX(CASE WHEN lo.market_type = 'totals' THEN lo.over_price END) as over_juice,
            MAX(CASE WHEN lo.market_type = 'totals' THEN lo.under_price END) as under_juice,
            MAX(CASE WHEN lo.market_type = 'totals' THEN lo.time END) as total_time,
            MAX(CASE WHEN lo.market_type = 'totals' THEN lo.bookmaker END) as total_book,
            -- First half odds
            MAX(CASE WHEN lo1h.market_type = 'spreads' THEN lo1h.home_line END) as spread_1h,
            MAX(CASE WHEN lo1h.market_type = 'spreads' THEN lo1h.home_price END) as spread_1h_home_juice,
            MAX(CASE WHEN lo1h.market_type = 'spreads' THEN lo1h.away_price END) as spread_1h_away_juice,
            MAX(CASE WHEN lo1h.market_type = 'spreads' THEN lo1h.time END) as spread_1h_time,
            MAX(CASE WHEN lo1h.market_type = 'spreads' THEN lo1h.bookmaker END) as spread_1h_book,
            MAX(CASE WHEN lo1h.market_type = 'totals' THEN lo1h.total_line END) as total_1h,
            MAX(CASE WHEN lo1h.market_type = 'totals' THEN lo1h.over_price END) as over_1h_juice,
            MAX(CASE WHEN lo1h.market_type = 'totals' THEN lo1h.under_price END) as under_1h_juice,
            MAX(CASE WHEN lo1h.market_type = 'totals' THEN lo1h.time END) as total_1h_time,
            MAX(CASE WHEN lo1h.market_type = 'totals' THEN lo1h.bookmaker END) as total_1h_book,
            -- Opening lines (consensus)
            MAX(CASE WHEN oo.market_type = 'spreads' THEN oo.home_line END) as spread_open,
            MAX(CASE WHEN oo.market_type = 'totals' THEN oo.total_line END) as total_open,
            MAX(CASE WHEN oo1h.market_type = 'spreads' THEN oo1h.home_line END) as spread_1h_open,
            MAX(CASE WHEN oo1h.market_type = 'totals' THEN oo1h.total_line END) as total_1h_open,
            -- Opening sharp lines (Pinnacle)
            MAX(CASE WHEN soo.market_type = 'spreads' THEN soo.sharp_home_line_open END) as sharp_spread_open,
            MAX(CASE WHEN soo.market_type = 'totals' THEN soo.sharp_total_line_open END) as sharp_total_open,
            -- Sharp book reference (Pinnacle)
            MAX(CASE WHEN so.market_type = 'spreads' THEN so.sharp_home_line END) as sharp_spread,
            MAX(CASE WHEN so.market_type = 'totals' THEN so.sharp_total_line END) as sharp_total,
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
        LEFT JOIN open_odds oo ON g.id = oo.game_id
        LEFT JOIN open_odds_1h oo1h ON g.id = oo1h.game_id
        LEFT JOIN sharp_open_odds soo ON g.id = soo.game_id
        LEFT JOIN sharp_odds so ON g.id = so.game_id
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
            # 
            # v6.3: ALL 22 BARTTORVIK FIELDS ARE REQUIRED - NO FALLBACKS
            # If any field is missing, we log an error and skip the game.
            # The data pipeline must ensure complete data before predictions run.
            # 

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
                "spread_time": row.spread_time,
                "spread_book": row.spread_book,
                "total": float(row.total) if row.total is not None else None,
                "over_juice": int(row.over_juice) if row.over_juice else None,
                "under_juice": int(row.under_juice) if row.under_juice else None,
                "total_time": row.total_time,
                "total_book": row.total_book,
                "spread_1h": float(row.spread_1h) if row.spread_1h is not None else None,
                "spread_1h_home_juice": int(row.spread_1h_home_juice) if row.spread_1h_home_juice else None,
                "spread_1h_away_juice": int(row.spread_1h_away_juice) if row.spread_1h_away_juice else None,
                "spread_1h_time": row.spread_1h_time,
                "spread_1h_book": row.spread_1h_book,
                "total_1h": float(row.total_1h) if row.total_1h is not None else None,
                "over_1h_juice": int(row.over_1h_juice) if row.over_1h_juice else None,
                "under_1h_juice": int(row.under_1h_juice) if row.under_1h_juice else None,
                "total_1h_time": row.total_1h_time,
                "total_1h_book": row.total_1h_book,
                # Sharp book reference (Pinnacle)
                "sharp_spread": float(row.sharp_spread) if row.sharp_spread is not None else None,
                "sharp_total": float(row.sharp_total) if row.sharp_total is not None else None,
                # Opening lines (consensus)
                "spread_open": float(row.spread_open) if row.spread_open is not None else None,
                "total_open": float(row.total_open) if row.total_open is not None else None,
                "spread_1h_open": float(row.spread_1h_open) if row.spread_1h_open is not None else None,
                "total_1h_open": float(row.total_1h_open) if row.total_1h_open is not None else None,
                # Opening sharp lines (Pinnacle)
                "sharp_spread_open": float(row.sharp_spread_open) if row.sharp_spread_open is not None else None,
                "sharp_total_open": float(row.sharp_total_open) if row.sharp_total_open is not None else None,
                "home_ratings": home_ratings,
                "away_ratings": away_ratings,
            }
            games.append(game)
        
        return games


# ==============================================================================
# GAME HISTORY FOR REST CALCULATION (v6.2)
# ==============================================================================

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


# ----------------------------------------------------------------------------
# LEAGUE AVERAGES / TEAM HCA / HEALTH OVERRIDES
# ----------------------------------------------------------------------------
def _load_league_averages(engine, target_date: date) -> Optional[Dict[str, float]]:
    """Compute seasonal league averages from latest team ratings."""
    query = text("""
        WITH latest_ratings AS (
            SELECT DISTINCT ON (team_id)
                team_id,
                adj_o,
                adj_d,
                tempo,
                orb,
                tor,
                ftr,
                three_pt_rate,
                efg
            FROM team_ratings
            WHERE rating_date <= :target_date
            ORDER BY team_id, rating_date DESC
        )
        SELECT
            AVG(adj_o) as avg_adj_o,
            AVG(adj_d) as avg_adj_d,
            AVG(tempo) as avg_tempo,
            AVG(orb) as avg_orb,
            AVG(tor) as avg_tor,
            AVG(ftr) as avg_ftr,
            AVG(three_pt_rate) as avg_3pr,
            AVG(efg) as avg_efg
        FROM latest_ratings
    """)

    with engine.connect() as conn:
        row = conn.execute(query, {"target_date": target_date}).fetchone()
        if not row:
            return None

    avg_adj_o = float(row.avg_adj_o) if row.avg_adj_o is not None else None
    avg_adj_d = float(row.avg_adj_d) if row.avg_adj_d is not None else None
    avg_tempo = float(row.avg_tempo) if row.avg_tempo is not None else None
    avg_orb = float(row.avg_orb) if row.avg_orb is not None else None
    avg_tor = float(row.avg_tor) if row.avg_tor is not None else None
    avg_ftr = float(row.avg_ftr) if row.avg_ftr is not None else None
    avg_3pr = float(row.avg_3pr) if row.avg_3pr is not None else None
    avg_efg = float(row.avg_efg) if row.avg_efg is not None else None

    if avg_adj_o is None or avg_adj_d is None or avg_tempo is None:
        return None

    avg_eff = (avg_adj_o + avg_adj_d) / 2

    return {
        "tempo": avg_tempo,
        "efficiency": avg_eff,
        "orb": avg_orb,
        "tor": avg_tor,
        "ftr": avg_ftr,
        "three_pt_rate": avg_3pr,
        "efg": avg_efg,
    }


def _apply_league_averages(averages: Dict[str, float]) -> None:
    """Apply league averages to config + predictor instances."""
    settings.model.league_avg_tempo = averages["tempo"]
    settings.model.league_avg_efficiency = averages["efficiency"]
    if averages.get("orb") is not None:
        settings.model.league_avg_orb = averages["orb"]
    if averages.get("tor") is not None:
        settings.model.league_avg_tor = averages["tor"]
    if averages.get("ftr") is not None:
        settings.model.league_avg_ftr = averages["ftr"]
    if averages.get("three_pt_rate") is not None:
        settings.model.league_avg_3pr = averages["three_pt_rate"]

    for model in (fg_spread_model, fg_total_model, h1_spread_model, h1_total_model):
        model.LEAGUE_AVG_TEMPO = averages["tempo"]
        if hasattr(model, "LEAGUE_AVG_EFFICIENCY"):
            model.LEAGUE_AVG_EFFICIENCY = averages["efficiency"]
        if hasattr(model, "LEAGUE_AVG_ORB") and averages.get("orb") is not None:
            model.LEAGUE_AVG_ORB = averages["orb"]
        if hasattr(model, "LEAGUE_AVG_TOR") and averages.get("tor") is not None:
            model.LEAGUE_AVG_TOR = averages["tor"]
        if hasattr(model, "LEAGUE_AVG_FTR") and averages.get("ftr") is not None:
            model.LEAGUE_AVG_FTR = averages["ftr"]
        if hasattr(model, "LEAGUE_AVG_3PR") and averages.get("three_pt_rate") is not None:
            model.LEAGUE_AVG_3PR = averages["three_pt_rate"]

    if averages.get("efg") is not None:
        h1_spread_model.LEAGUE_AVG_EFG = averages["efg"]
    h1_total_model.LEAGUE_AVG_H1_EFFICIENCY = averages["efficiency"]


def _load_team_hca(
    engine,
    target_date: date,
    lookback_days: int,
    min_games: int,
    cap: float,
) -> Dict[str, float]:
    """Compute team-specific HCA using home vs away margins."""
    start_date = datetime.combine(target_date, datetime.min.time()) - timedelta(days=lookback_days)
    end_date = datetime.combine(target_date + timedelta(days=1), datetime.min.time())

    query = text("""
        WITH home_stats AS (
            SELECT
                home_team_id as team_id,
                AVG(home_score - away_score) as home_margin,
                COUNT(*) as home_games
            FROM games
            WHERE status IN ('completed', 'final')
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND commence_time >= :start_date
              AND commence_time < :end_date
            GROUP BY home_team_id
        ),
        away_stats AS (
            SELECT
                away_team_id as team_id,
                AVG(away_score - home_score) as away_margin,
                COUNT(*) as away_games
            FROM games
            WHERE status IN ('completed', 'final')
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
              AND commence_time >= :start_date
              AND commence_time < :end_date
            GROUP BY away_team_id
        )
        SELECT
            t.canonical_name,
            hs.home_margin,
            hs.home_games,
            aw.away_margin,
            aw.away_games
        FROM teams t
        LEFT JOIN home_stats hs ON t.id = hs.team_id
        LEFT JOIN away_stats aw ON t.id = aw.team_id
    """)

    team_hca = {}
    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {"start_date": start_date, "end_date": end_date},
        ).fetchall()

    for row in rows:
        if not row.canonical_name:
            continue
        if row.home_games is None or row.away_games is None:
            continue
        if row.home_games < min_games or row.away_games < min_games:
            continue
        if row.home_margin is None or row.away_margin is None:
            continue
        hca = (float(row.home_margin) - float(row.away_margin)) / 2
        hca = max(-cap, min(cap, hca))
        team_hca[row.canonical_name] = hca

    return team_hca


def _load_team_health_file(path: Optional[str]) -> Dict[str, Dict[str, float]]:
    """Load optional team health adjustments from CSV/JSON."""
    if not path:
        return {}
    health_path = Path(path)
    if not health_path.exists():
        return {}

    def _parse_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    payload = []
    if health_path.suffix.lower() == ".json":
        payload = json.loads(health_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = list(payload.values())
    elif health_path.suffix.lower() == ".csv":
        with health_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            payload = list(reader)
    else:
        return {}

    health = {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        team = entry.get("team") or entry.get("canonical_name") or entry.get("name")
        if not team:
            continue
        key = str(team).strip().lower()
        health[key] = {
            "status": entry.get("status") or "",
            "spread_adjustment": _parse_float(entry.get("spread_adjustment") or entry.get("spread_adj")),
            "total_adjustment": _parse_float(entry.get("total_adjustment") or entry.get("total_adj")),
        }

    return health


# ----------------------------------------------------------------------------
# RECENT PERFORMANCE FOR BAYESIAN CALIBRATION
# ----------------------------------------------------------------------------
def _load_recent_hit_rates(engine, lookback_days: int) -> Dict[str, Dict[str, float]]:
    """Load recent settled recommendation results for Bayesian calibration."""
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    query = text(
        """
        SELECT
            bet_type,
            SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN status = 'push' THEN 1 ELSE 0 END) AS pushes
        FROM betting_recommendations
        WHERE created_at >= :since
          AND status IN ('won', 'lost', 'push')
        GROUP BY bet_type
        """
    )

    stats: Dict[str, Dict[str, float]] = {}
    with engine.begin() as conn:
        rows = conn.execute(query, {"since": since}).fetchall()

    for row in rows:
        wins = int(row.wins or 0)
        losses = int(row.losses or 0)
        pushes = int(row.pushes or 0)
        samples = wins + losses
        hit_rate = (wins / samples) if samples else None
        stats[str(row.bet_type)] = {
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "samples": samples,
            "hit_rate": hit_rate,
        }

    return stats

# ==============================================================================
# PREDICTION - Direct import (no HTTP)
# ==============================================================================

def get_prediction(
    home_team: str,
    away_team: str,
    home_ratings: Dict,
    away_ratings: Dict,
    market_odds: Optional[Dict] = None,
    is_neutral: bool = False,
    home_rest: Optional[RestInfo] = None,
    away_rest: Optional[RestInfo] = None,
    home_hca: Optional[float] = None,
    home_hca_1h: Optional[float] = None,
    home_health: Optional[Dict[str, float]] = None,
    away_health: Optional[Dict[str, float]] = None,
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
            spread_home_price=market_odds.get("spread_home_price"),
            spread_away_price=market_odds.get("spread_away_price"),
            total=market_odds.get("total"),
            over_price=market_odds.get("over_price") or -110,
            under_price=market_odds.get("under_price") or -110,
            spread_1h=market_odds.get("spread_1h"),
            spread_price_1h=market_odds.get("spread_price_1h"),
            spread_1h_home_price=market_odds.get("spread_1h_home_price"),
            spread_1h_away_price=market_odds.get("spread_1h_away_price"),
            total_1h=market_odds.get("total_1h"),
            over_price_1h=market_odds.get("over_price_1h"),
            under_price_1h=market_odds.get("under_price_1h"),
            # Sharp book reference (Pinnacle) for CLV tracking
            sharp_spread=market_odds.get("sharp_spread"),
            sharp_total=market_odds.get("sharp_total"),
            # Opening lines (consensus + sharp)
            spread_open=market_odds.get("spread_open"),
            total_open=market_odds.get("total_open"),
            spread_1h_open=market_odds.get("spread_1h_open"),
            total_1h_open=market_odds.get("total_1h_open"),
            sharp_spread_open=market_odds.get("sharp_spread_open"),
            sharp_total_open=market_odds.get("sharp_total_open"),
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
        home_hca=home_hca,
        home_hca_1h=home_hca_1h,
        home_health=home_health,
        away_health=away_health,
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
                "home_hca": home_hca,
                "home_hca_1h": home_hca_1h,
                "home_health": home_health,
                "away_health": away_health,
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
            print(f"  [WARN]  Persistence warning for {away_team} @ {home_team}: {type(e).__name__}: {e}")
    
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


# ==============================================================================
# DISPLAY HELPERS
# ==============================================================================

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
    # Rating scale: * = filled, - = empty
    if bet_tier == "max" or edge >= 5.0:
        return "*****"  # 5/5 MAX
    elif bet_tier == "medium" or edge >= 4.0:
        return "****-"  # 4/5
    elif edge >= 3.5:
        return "***--"  # 3/5
    elif edge >= 3.0:
        return "**---"  # 2/5
    else:
        return "*----"  # 1/5


def print_executive_table(all_picks: list, target_date) -> None:
    """
    Print executive summary table with format:
    DATE/TIME CST | MATCHUP (Away vs Home w/records) | PICK (w/live odds) | MODEL | MARKET | EDGE | FIRE
    """
    if not all_picks:
        print("\n[WARN]  No bets meet minimum edge thresholds")
        return
    
    # Sort by fire rating (descending), then edge (descending), then time
    def sort_key(p):
        fire_score = p['fire_rating'].count('*')  # Count filled diamonds
        return (-fire_score, -p['edge'], p['time_cst'])
    
    sorted_picks = sorted(all_picks, key=sort_key)
    
    # Count max plays
    max_plays = sum(1 for p in sorted_picks if p.get('bet_tier') == 'max' or p['edge'] >= 5.0)
    
    # Header
    print()
    print("+" + "-" * 145 + "+")
    print("|" + f"   NCAAM PICKS - {target_date} | {len(sorted_picks)} PLAYS | {max_plays} MAX BETS".ljust(145) + "|")
    print("+" + "-" * 145 + "+")
    
    # Column headers - simplified for clarity
    header = (
        f"| {'DATE/TIME':<12} | {'MATCHUP (Away vs Home)':<40} | "
        f"{'RECOMMENDED PICK':<28} | {'MODEL':<12} | {'MARKET':<14} | {'EDGE':<8} | {'FIRE':<6} |"
    )
    print(header)
    print("+" + "-" * 145 + "+")
    
    # Data rows
    for pick in sorted_picks:
        # Date/Time
        date_str = pick.get('date_cst', str(target_date))[-5:]  # MM-DD format
        time_str = pick['time_cst']
        datetime_str = f"{date_str} {time_str}"
        
        # Matchup with records: "Away (W-L) vs Home (W-L)"
        away_rec = f"({pick.get('away_record', '?')})" if pick.get('away_record') else ""
        home_rec = f"({pick.get('home_record', '?')})" if pick.get('home_record') else ""
        matchup = f"{pick['away'][:14]} {away_rec} vs {pick['home'][:14]} {home_rec}"
        if len(matchup) > 40:
            matchup = matchup[:37] + "..."
        
        # Recommended pick with live odds (already formatted)
        pick_str = pick['pick_display']
        if len(pick_str) > 28:
            pick_str = pick_str[:25] + "..."
        
        # Model prediction
        model_str = pick['model_line']
        if len(model_str) > 12:
            model_str = model_str[:12]
        
        # Market price
        market_str = pick['market_line']
        if len(market_str) > 14:
            market_str = market_str[:14]
        
        # Edge
        edge_str = f"{pick['edge']:.1f}pts"
        
        # Fire rating
        fire = pick['fire_rating']
        
        row = (
            f"| {datetime_str:<12} | {matchup:<40} | "
            f"{pick_str:<28} | {model_str:<12} | {market_str:<14} | {edge_str:<8} | {fire:<6} |"
        )
        print(row)
    
    print("+" + "-" * 145 + "+")
    
    # Legend
    print()
    print("  LEGEND: ***** = MAX BET (5+ pts edge) | ****- = STRONG (4+ pts) | ***-- = SOLID (3.5+ pts)")
    print()


def format_team_display(team: str, record: Optional[str] = None, rank: Optional[int] = None) -> str:
    """Format team name with optional record and rank."""
    parts = [team]
    if rank:
        parts.append(f"#{rank}")
    if record:
        parts.append(f"({record})")
    return " ".join(parts)


# ==============================================================================
# TEAMS WEBHOOK NOTIFICATION
# ==============================================================================

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
        print("  [WARN]  No picks to send to Teams")
        return False

    send_enabled = not _is_placeholder_teams_webhook(webhook_url)
    if not send_enabled:
        print("  [WARN]  No Teams webhook URL configured (will still write HTML/CSV artifacts)")
    
    # Sort picks by game time ascending (earliest games first)
    sorted_picks = sorted(all_picks, key=lambda p: p['time_cst'])
    
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
            # Header row matches the new table format
            w.writerow(
                [
                    "Date/Time CST",
                    "Matchup (Away vs Home)",
                    "Recommended Pick (Live Odds)",
                    "Model Prediction",
                    "Market Price",
                    "Edge",
                    "Fire Rating",
                ]
            )
            for p in sorted_picks:
                # Date/Time CST
                date_time = f"{p.get('date_cst', target_date)} {p.get('time_cst','')}".strip()
                
                # Matchup with records
                away_rec = p.get('away_record') or '?'
                home_rec = p.get('home_record') or '?'
                matchup = f"{p['away']} ({away_rec}) vs {p['home']} ({home_rec})"
                
                # Write row
                w.writerow(
                    [
                        date_time,
                        matchup,
                        p.get("pick_display", ""),
                        p.get("model_line", ""),
                        p.get("market_line", ""),
                        f"{p.get('edge', 0.0):.1f} pts",
                        p.get("fire_rating", ""),
                    ]
                )
        print(f"  [OK] CSV saved: {csv_path}")
    except Exception as e:
        print(f"  [WARN]  Failed to write CSV: {type(e).__name__}: {e}")

    # Generate HTML Report
    html_url = ""
    try:
        out_dir = Path("/app/output")
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / "latest_picks.html"
        
        # Simple CSS-styled HTML table
        # Count max plays for summary
        max_plays = sum(1 for p in sorted_picks if p.get('bet_tier') == 'max' or p.get('edge', 0) >= 5.0)
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>NCAAM Picks - {target_date}</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
                h1 {{ color: #fff; margin-bottom: 5px; }}
                .container {{ max-width: 1400px; margin: 0 auto; background: #16213e; padding: 25px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }}
                .summary {{ background: linear-gradient(135deg, #0f3460 0%, #1a1a2e 100%); padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; }}
                .summary h2 {{ margin: 0; font-size: 1.5em; }}
                .summary .stats {{ display: flex; gap: 30px; margin-top: 10px; }}
                .summary .stat {{ text-align: center; }}
                .summary .stat-value {{ font-size: 2em; font-weight: bold; color: #e94560; }}
                .summary .stat-label {{ font-size: 0.8em; color: #888; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th {{ background: #0f3460; color: #fff; padding: 14px 10px; text-align: left; font-weight: 600; }}
                td {{ padding: 12px 10px; border-bottom: 1px solid #2a2a4a; }}
                tr:hover {{ background-color: #1f2b4d; }}
                .fire {{ color: #e94560; font-weight: bold; letter-spacing: 1px; }}
                .edge-max {{ color: #00ff88; font-weight: bold; }}
                .edge-high {{ color: #00cc6a; font-weight: bold; }}
                .edge-med {{ color: #ffa600; }}
                .pick {{ font-weight: 600; color: #4fc3f7; }}
                .matchup {{ font-size: 0.95em; }}
                .record {{ color: #888; font-size: 0.85em; }}
                .timestamp {{ color: #666; font-size: 0.85em; margin-bottom: 15px; }}
                .legend {{ margin-top: 20px; padding: 15px; background: #0f3460; border-radius: 8px; font-size: 0.9em; }}
                .legend span {{ margin-right: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1> NCAAM PICKS</h1>
                <div class="timestamp">Generated: {datetime.now(CST).strftime("%Y-%m-%d %H:%M CST")} | Target Date: {target_date}</div>
                
                <div class="summary">
                    <div class="stats">
                        <div class="stat">
                            <div class="stat-value">{len(sorted_picks)}</div>
                            <div class="stat-label">TOTAL PICKS</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">{max_plays}</div>
                            <div class="stat-label">MAX BETS</div>
                        </div>
                    </div>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>Date/Time</th>
                            <th>Matchup (Away vs Home)</th>
                            <th>Recommended Pick</th>
                            <th>Model</th>
                            <th>Market</th>
                            <th>Edge</th>
                            <th>Fire</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for p in sorted_picks:
            # Date/Time
            date_time = f"{p.get('date_cst', str(target_date))[-5:]} {p.get('time_cst', '')}"
            
            # Matchup with records
            away_rec = f"<span class='record'>({p.get('away_record', '?')})</span>" if p.get('away_record') else ""
            home_rec = f"<span class='record'>({p.get('home_record', '?')})</span>" if p.get('home_record') else ""
            matchup = f"{p['away']} {away_rec} vs {p['home']} {home_rec}"
            
            edge_val = p.get('edge', 0.0)
            if edge_val >= 5.0:
                edge_class = "edge-max"
            elif edge_val >= 4.0:
                edge_class = "edge-high"
            elif edge_val >= 3.0:
                edge_class = "edge-med"
            else:
                edge_class = ""
            
            html_content += f"""
                        <tr>
                            <td>{date_time}</td>
                            <td class="matchup">{matchup}</td>
                            <td class="pick">{p.get('pick_display', '')}</td>
                            <td>{p.get('model_line', '')}</td>
                            <td>{p.get('market_line', '')}</td>
                            <td class="{edge_class}">{edge_val:.1f} pts</td>
                            <td class="fire">{p.get('fire_rating', '')}</td>
                        </tr>
            """
            
        html_content += """
                    </tbody>
                </table>
                
                <div class="legend">
                    <strong>FIRE RATING:</strong>
                    <span>***** = MAX BET (5+ pts edge)</span>
                    <span>****- = STRONG (4+ pts)</span>
                    <span>***-- = SOLID (3.5+ pts)</span>
                    <span>**--- = STANDARD (3+ pts)</span>
                </div>
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
        print(f"  [OK] HTML saved: {html_path}")
        
        # Upload to Microsoft Graph (SharePoint/Teams)
        upload_success = upload_file_to_teams(html_path, target_date)
        if upload_success:
            print("  [OK] HTML uploaded to Teams Shared Documents")
        
    except Exception as e:
        print(f"  [WARN]  Failed to generate HTML: {e}")

    # Build simple Adaptive Card format (ColumnSet tables don't render in Teams Workflow webhooks)
    now_cst = datetime.now(CST)
    
    # Build top picks as simple text lines (proven to work)
    top_picks_lines = []
    for p in sorted_picks[:10]:
        pick_display = p.get('pick_display', '')
        edge_str = f"{p['edge']:.1f}"
        fire = p.get('fire_rating', '')
        # Format: " Siena +23.5 @ Indiana (31 pts edge)"
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
                            "text": f" NCAAM PICKS - {target_date}"
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
                            "title": " Full Report",
                            "url": html_url or "https://ncaam-stable-prediction.lemondesert-405ee2f3.centralus.azurecontainerapps.io/picks/html"
                        }
                    ]
                }
            }
        ]
    }
    
    if not send_enabled:
        return False

    try:
        response = requests.post(
            webhook_url,
            json=card_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200 or response.status_code == 202:
            print(f"  [OK] Picks sent to Teams successfully ({len(sorted_picks)} picks)")
            return True
        else:
            print(f"  [WARN]  Teams webhook returned status {response.status_code}: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("  [WARN]  Teams webhook timed out")
        return False
    except requests.exceptions.RequestException as e:
        print(f"  [WARN]  Teams webhook error: {e}")
        return False


# ==============================================================================
# MAIN
# ==============================================================================


def _format_health_summary(summary: Dict[str, object]) -> str:
    lines: List[str] = []
    timestamp = str(summary.get("timestamp", "")).strip()
    mode = str(summary.get("mode", "")).strip()
    title = "NCAAM Health Summary"
    if timestamp:
        title = f"{title} - {timestamp}"
    if mode:
        title = f"{title} ({mode})"
    lines.append(title)

    status = summary.get("status") or "unknown"
    lines.append(f"Status: {status}")

    model = summary.get("model_version")
    if model:
        lines.append(f"Model: {model}")

    sync_ok = summary.get("sync_ok")
    if sync_ok is not None:
        lines.append(f"Sync: {'OK' if sync_ok else 'FAIL'}")

    tm = summary.get("team_matching")
    if isinstance(tm, dict):
        tm_status = "OK" if tm.get("ok") else "FAIL"
        if tm.get("warned"):
            tm_status = f"{tm_status} (WARN)"
        lines.append(f"Team matching: {tm_status}")

    dq = summary.get("data_quality")
    if isinstance(dq, dict) and dq.get("total") is not None:
        total = dq.get("total", 0)
        lines.append(
            "Coverage: "
            f"ratings {dq.get('ratings_ok', 0)}/{total}, "
            f"odds {dq.get('odds_ok', 0)}/{total}, "
            f"ready {dq.get('ready_ok', 0)}/{total}"
        )
        if dq.get("h1_odds_ok") is not None:
            lines.append(f"1H odds: {dq.get('h1_odds_ok', 0)}/{total}")

    league_avgs = summary.get("league_avgs")
    if isinstance(league_avgs, dict):
        tempo = league_avgs.get("tempo")
        eff = league_avgs.get("efficiency")
        if tempo is not None and eff is not None:
            lines.append(f"League avgs: tempo={tempo} eff={eff}")

    team_hca = summary.get("team_hca")
    if isinstance(team_hca, dict):
        lines.append(
            f"Team HCA: teams={team_hca.get('teams', 0)} "
            f"lookback={team_hca.get('lookback_days', 0)}d"
        )

    team_health = summary.get("team_health")
    if isinstance(team_health, dict) and team_health:
        lines.append(
            f"Team health: teams={team_health.get('teams', 0)} "
            f"source={team_health.get('source', '')}"
        )

    bayes = summary.get("bayes_priors")
    if isinstance(bayes, dict):
        window_days = bayes.get("window_days", 0)
        min_samples = bayes.get("min_samples", 0)
        samples = bayes.get("samples")
        sample_text = ""
        if isinstance(samples, dict) and samples:
            sample_text = ", " + ", ".join(f"{k}={v}" for k, v in samples.items())
        lines.append(f"Bayes priors: window={window_days}d min={min_samples}{sample_text}")

    settlement = summary.get("settlement")
    if isinstance(settlement, dict) and settlement:
        lines.append(
            "Settlement: "
            f"{settlement.get('settled', 0)} "
            f"W-L-P={settlement.get('wins', 0)}-"
            f"{settlement.get('losses', 0)}-"
            f"{settlement.get('pushes', 0)} "
            f"skipped_1H={settlement.get('skipped_1h', 0)}"
        )

    picks = summary.get("picks")
    if isinstance(picks, dict):
        lines.append(f"Picks: total={picks.get('total', 0)} max={picks.get('max', 0)}")

    notes = summary.get("notes")
    if notes:
        if isinstance(notes, list):
            lines.append("Notes: " + "; ".join(str(n) for n in notes))
        else:
            lines.append(f"Notes: {notes}")

    return "\n".join([line for line in lines if line])


def send_health_summary_to_teams(
    summary: Dict[str, object],
    webhook_url: str = TEAMS_WEBHOOK_URL,
) -> bool:
    if _is_placeholder_teams_webhook(webhook_url):
        print("  - No Teams webhook URL configured (health summary)")
        return False

    payload = {"text": _format_health_summary(summary)}
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if response.status_code in (200, 202):
            return True
        print(f"  - Health summary webhook returned {response.status_code}: {response.text[:200]}")
        return False
    except requests.exceptions.Timeout:
        print("  - Health summary webhook timed out")
        return False
    except requests.exceptions.RequestException as e:
        print(f"  - Health summary webhook error: {e}")
        return False


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
        "--allow-data-degrade",
        action="store_true",
        help="Allow running even if data quality checks fail"
    )
    parser.add_argument(
        "--team-matching-lookback-days",
        type=int,
        default=int(os.getenv("TEAM_MATCHING_LOOKBACK_DAYS", "30")),
        help="Lookback window (days) for team matching enforcement (default: 30)"
    )
    parser.add_argument(
        "--min-team-resolution-rate",
        type=float,
        default=float(os.getenv("MIN_TEAM_RESOLUTION_RATE", "0.99")),
        help="Minimum recent team resolution rate (0-1) required (default: 0.99)"
    )
    parser.add_argument(
        "--min-ratings-pct",
        type=float,
        default=0.9,
        help="Minimum % of games with ratings (default: 0.9)"
    )
    parser.add_argument(
        "--min-odds-pct",
        type=float,
        default=0.7,
        help="Minimum % of games with full-game odds (default: 0.7)"
    )
    parser.add_argument(
        "--min-ready-pct",
        type=float,
        default=0.6,
        help="Minimum % of games ready (ratings + odds) (default: 0.6)"
    )
    parser.add_argument(
        "--min-1h-odds-pct",
        type=float,
        default=0.0,
        help="Minimum % of games with 1H odds (default: 0.0)"
    )
    parser.add_argument(
        "--max-odds-age-minutes-full",
        type=int,
        default=int(os.getenv("MAX_ODDS_AGE_MINUTES_FULL", "60")),
        help="Max allowed age for full-game odds snapshots in minutes (default: 60)"
    )
    parser.add_argument(
        "--max-odds-age-minutes-1h",
        type=int,
        default=int(os.getenv("MAX_ODDS_AGE_MINUTES_1H", "60")),
        help="Max allowed age for 1H odds snapshots in minutes (default: 60)"
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

    now_cst = datetime.now(CST)
    health_summary: Dict[str, object] = {
        "timestamp": now_cst.strftime("%Y-%m-%d %H:%M %Z"),
        "status": "ok",
        "mode": "settle-only" if args.settle_only else "full",
        "model_version": getattr(prediction_engine, "version_tag", ""),
        "notes": [],
    }

    def exit_with_health(code: int, note: str = "") -> None:
        if note:
            health_summary.setdefault("notes", []).append(note)
        if code != 0 and health_summary.get("status") == "ok":
            health_summary["status"] = "blocked"
        health_summary.setdefault("picks", {"total": 0, "max": 0})
        send_health_summary_to_teams(health_summary)
        sys.exit(code)

    # Parse target date
    target_date = date.today()
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f" Invalid date format: {args.date}. Use YYYY-MM-DD")
            exit_with_health(1, "invalid date format")
    
    
    print()
    print("" + "" * 118 + "")
    print("" + f"  NCAA BASKETBALL PREDICTIONS - {now_cst.strftime('%A, %B %d, %Y')} @ {now_cst.strftime('%I:%M %p CST')}".ljust(118) + "")
    print("" + "  Model: v33.6 Modular (FG/H1 Spread & Total)".ljust(118) + "")
    print("" + "" * 118 + "")
    print()
    
    # Sync data (unless --no-sync)

    # Create DB engine once for the entire run (predictions persistence + settlement).
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    # Canonical team matching enforcement (HARD GATE)
    # Requirement: >=99% recent resolution and ZERO unresolved in lookback window.
    print("[INFO] Enforcing canonical team matching quality...")
    try:
        tm_recent = _check_recent_team_resolution(
            engine=engine,
            lookback_days=args.team_matching_lookback_days,
            min_resolution_rate=args.min_team_resolution_rate,
        )
        health_summary["team_matching"] = tm_recent
        total = tm_recent.get("total", 0)
        unresolved = tm_recent.get("unresolved", 0)
        rate = float(tm_recent.get("rate", 0.0) or 0.0)

        print(
            f"  - Recent resolution: {rate:.2%} ({tm_recent.get('resolved', 0)}/{total}), "
            f"unresolved={unresolved} (lookback {tm_recent.get('lookback_days', 0)}d)"
        )
        if not tm_recent.get("ok"):
            print("[FATAL] Canonical team matching gate failed.")
            # No bypass here: outputs are not trustworthy when team resolution is degraded.
            exit_with_health(2, "canonical team matching below required threshold")
    except Exception as e:
        print(f"[FATAL] Canonical team matching check errored: {type(e).__name__}: {e}")
        exit_with_health(2, f"canonical team matching check error: {type(e).__name__}")

    # Optional verbose validator output (informational only)
    if not args.no_sync:
        print("[INFO] Running full team matching validator report...")
        try:
            validator = TeamMatchingValidator()
            validator_ok = validator.run_all_validations()
            validator_warned = any(r.status == "WARN" for r in getattr(validator, "results", []))
            health_summary.setdefault("team_matching", {})
            health_summary["team_matching"]["validator_ok"] = bool(validator_ok)
            health_summary["team_matching"]["validator_warned"] = bool(validator_warned)
        except Exception as e:
            print(f"[WARN] Full validator report failed: {type(e).__name__}: {e}")
            health_summary.setdefault("notes", []).append("team matching validator report failed")

    sync_ok = sync_fresh_data(skip_sync=args.no_sync)
    health_summary["sync_ok"] = sync_ok
    if not sync_ok:
        if not args.allow_data_degrade:
            exit_with_health(2, "data sync failed")
        health_summary["status"] = "warn"
        health_summary.setdefault("notes", []).append("data sync failed")


    # Optional: score sync + settlement + ROI report (production auditing)
    if not args.no_settle:
        try:
            from app.settlement import sync_final_scores, sync_halftime_scores, settle_pending_bets, print_performance_report

            print("[RETRY] Syncing final scores + settling pending bets...")
            score_summary = sync_final_scores(engine, days_from=args.settle_days_from)
            halftime_summary = sync_halftime_scores(engine, days_from=args.settle_days_from)
            settle_summary = settle_pending_bets(engine)
            health_summary["settlement"] = {
                "settled": settle_summary.settled,
                "wins": settle_summary.wins,
                "losses": settle_summary.losses,
                "pushes": settle_summary.pushes,
                "skipped_1h": settle_summary.skipped_missing_scores_1h,
                "missing_closing_line": settle_summary.missing_closing_line,
            }
            print(
                f"  [OK] Scores: fetched={score_summary.fetched_events} completed={score_summary.completed_events} "
                f"updated_games={score_summary.updated_games} missing_games={score_summary.missing_games}"
            )
            print(
                f"  - Halftime: fetched={halftime_summary.fetched_events} updated_games={halftime_summary.updated_games} "
                f"missing_games={halftime_summary.missing_games} missing_scores={halftime_summary.missing_scores}"
            )
            print(
                f"  [OK] Settlement: settled={settle_summary.settled} W-L-P={settle_summary.wins}-{settle_summary.losses}-{settle_summary.pushes} "
                f"skipped_1H_missing_scores={settle_summary.skipped_missing_scores_1h} missing_closing_line={settle_summary.missing_closing_line}"
            )
            if settle_summary.skipped_missing_scores_1h > 0:
                print("  [WARN]  Missing halftime scores for settled 1H bets.")
                if not args.allow_data_degrade:
                    exit_with_health(2, "missing halftime scores for 1H bets")
                health_summary["status"] = "warn"
                health_summary.setdefault("notes", []).append("missing halftime scores for 1H bets")
            if not args.teams_only:
                print_performance_report(engine, lookback_days=args.report_days)
        except Exception as e:
            print(f"  [WARN]  Settlement step failed: {type(e).__name__}: {e}")

        if args.settle_only:
            health_summary.setdefault("picks", {"total": 0, "max": 0})
            send_health_summary_to_teams(health_summary)
            return

    league_avgs = _load_league_averages(engine, target_date)
    if league_avgs:
        _apply_league_averages(league_avgs)
        health_summary["league_avgs"] = {
            "tempo": round(league_avgs.get("tempo", 0), 2),
            "efficiency": round(league_avgs.get("efficiency", 0), 2),
        }

    team_hca = _load_team_hca(
        engine=engine,
        target_date=target_date,
        lookback_days=settings.model.team_hca_lookback_days,
        min_games=settings.model.team_hca_min_games,
        cap=settings.model.team_hca_cap,
    )
    health_summary["team_hca"] = {
        "teams": len(team_hca),
        "lookback_days": settings.model.team_hca_lookback_days,
        "min_games": settings.model.team_hca_min_games,
    }

    team_health_file = os.getenv("TEAM_HEALTH_FILE", "").strip()
    team_health = _load_team_health_file(team_health_file)
    if team_health_file:
        health_summary["team_health"] = {
            "teams": len(team_health),
            "source": Path(team_health_file).name,
        }

    recent_stats = _load_recent_hit_rates(engine, settings.model.bayes_recent_window_days)
    bayes_priors = {}
    for bet_type in BetType:
        stats = recent_stats.get(bet_type.value) if recent_stats else None
        samples = int((stats or {}).get("samples", 0) or 0)
        hit_rate = (stats or {}).get("hit_rate")
        if hit_rate is None or samples < settings.model.bayes_min_samples:
            hit_rate = settings.model.bayes_default_hit_rate
        bayes_priors[bet_type] = {"hit_rate": float(hit_rate), "samples": samples}

    prediction_engine.set_bayes_priors(bayes_priors)
    health_summary["bayes_priors"] = {
        "window_days": settings.model.bayes_recent_window_days,
        "min_samples": settings.model.bayes_min_samples,
        "samples": {k.value: v["samples"] for k, v in bayes_priors.items()},
    }

    # Fetch games
    print(f"[OK] Fetching games for {target_date}...")
    print()
    
    try:
        games = fetch_games_from_db(target_date=target_date, engine=engine)
    except Exception as e:
        print(f" FATAL ERROR: Failed to fetch games: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        exit_with_health(1, f"failed to fetch games: {type(e).__name__}")
    
    if not games:
        print(f"[WARN]  No games found for {target_date}")
        exit_with_health(0, "no games found")
    
    # Filter by specific game if requested
    if args.game:
        home_filter, away_filter = args.game
        games = [
            g for g in games
            if home_filter.lower() in g["home"].lower()
            and away_filter.lower() in g["away"].lower()
        ]
        if not games:
            print(f"[WARN]  No games found matching '{away_filter}' @ '{home_filter}'")
            exit_with_health(0, "no games matched filter")
    # Data quality gate (avoid silent failures)
    quality_summary = _summarize_data_quality(games)
    health_summary["data_quality"] = quality_summary
    quality_failures = _enforce_data_quality(quality_summary, args)
    if quality_failures:
        if not args.allow_data_degrade:
            exit_with_health(2, "data quality below thresholds")
        health_summary["status"] = "warn"
        health_summary.setdefault("notes", []).append("data quality below thresholds")

    # Odds freshness + complete pricing gate (HARD GATE)
    odds_failures = _enforce_odds_freshness_and_completeness(
        games=games,
        max_age_full_minutes=args.max_odds_age_minutes_full,
        max_age_1h_minutes=args.max_odds_age_minutes_1h,
    )
    if odds_failures:
        print("[FATAL] Odds freshness/pricing gate failed:")
        for msg in odds_failures[:25]:
            print(f"   - {msg}")
        if len(odds_failures) > 25:
            print(f"   ... and {len(odds_failures) - 25} more")
        # No bypass: requirement is 'real fresh odds must always be used'.
        exit_with_health(2, "stale or incomplete odds")

    
    print(f"[OK] Found {len(games)} games")
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
            "spread_home_price": game.get("spread_home_juice"),
            "spread_away_price": game.get("spread_away_juice"),
            # Legacy/compat: a single spread_price for codepaths that assume symmetric juice
            "spread_price": game.get("spread_home_juice") or game.get("spread_away_juice"),
            "total": game["total"],
            "over_price": game.get("over_juice"),
            "under_price": game.get("under_juice"),
            "spread_1h": game.get("spread_1h"),
            "spread_1h_home_price": game.get("spread_1h_home_juice"),
            "spread_1h_away_price": game.get("spread_1h_away_juice"),
            "spread_price_1h": game.get("spread_1h_home_juice") or game.get("spread_1h_away_juice"),
            "total_1h": game.get("total_1h"),
            "over_price_1h": game.get("over_1h_juice"),
            "under_price_1h": game.get("under_1h_juice"),
            # Sharp book reference (Pinnacle) for CLV tracking
            "sharp_spread": game.get("sharp_spread"),
            "sharp_total": game.get("sharp_total"),
            # Opening lines (consensus + sharp)
            "spread_open": game.get("spread_open"),
            "total_open": game.get("total_open"),
            "spread_1h_open": game.get("spread_1h_open"),
            "total_1h_open": game.get("total_1h_open"),
            "sharp_spread_open": game.get("sharp_spread_open"),
            "sharp_total_open": game.get("sharp_total_open"),
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
            print(f"  [WARN] Rest calc failed for {game['away']} @ {game['home']}: {e}")


        home_health = None
        away_health = None
        if team_health:
            home_health = team_health.get(game["home"].lower())
            away_health = team_health.get(game["away"].lower())

        home_hca = None
        home_hca_1h = None
        if team_hca and not game.get("is_neutral", False):
            home_hca = team_hca.get(game["home"])
            if home_hca is not None:
                base_hca = settings.model.home_court_advantage_spread
                base_hca_1h = settings.model.home_court_advantage_spread_1h
                if base_hca:
                    home_hca_1h = home_hca * (base_hca_1h / base_hca)


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
                home_hca=home_hca,
                home_hca_1h=home_hca_1h,
                home_health=home_health,
                away_health=away_health,
                game_id=game.get("game_id"),
                commence_time=game.get("commence_time"),
                engine=engine,
                persist=True,
            )
        except Exception as e:
            print(f"[FATAL] Prediction failed for {game['away']} @ {game['home']}: {type(e).__name__}: {e}")
            exit_with_health(1, f"prediction failed: {type(e).__name__}")
        
        pred = result["prediction"]
        recs = result["recommendations"]
        
        # Collect picks for executive table
        for rec in recs:
            bet_type = rec.get('bet_type', '')
            # Engine returns already-thresholded recommendations; no extra filtering
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
            else:
                continue

            # Model line display (show from PICK perspective for spreads)
            if market == "SPREAD":
                model_line_val_home = pred["predicted_spread"] if not is_1h else pred["predicted_spread_1h"]
                model_line_val = model_line_val_home if pick_val == "HOME" else -model_line_val_home
                model_str = f"{format_spread(model_line_val)}"
            elif market == "TOTAL":
                model_line_val = pred["predicted_total"] if not is_1h else pred["predicted_total_1h"]
                model_str = f"{model_line_val:.1f}"
            else:
                continue

            # Market line display with juice (show from PICK perspective)
            if market == "SPREAD":
                mkt_line_home = game["spread"] if not is_1h else game.get("spread_1h")
                mkt_line = mkt_line_home if pick_val == "HOME" else (-(mkt_line_home) if mkt_line_home is not None else None)
                if not is_1h:
                    mkt_juice = game.get("spread_home_juice") if pick_val == "HOME" else game.get("spread_away_juice")
                else:
                    mkt_juice = game.get("spread_1h_home_juice") if pick_val == "HOME" else game.get("spread_1h_away_juice")
                market_str = f"{format_spread(mkt_line)} ({format_odds(mkt_juice)})"
            elif market == "TOTAL":
                mkt_line = game["total"] if not is_1h else game.get("total_1h")
                if not is_1h:
                    mkt_juice = game.get("over_juice") if pick_val == "OVER" else game.get("under_juice")
                else:
                    mkt_juice = game.get("over_1h_juice") if pick_val == "OVER" else game.get("under_1h_juice")
                market_str = f"{mkt_line:.1f} ({format_odds(mkt_juice)})"
            else:
                continue
            
            # Fire rating
            fire = get_fire_rating(rec['edge'], rec.get('bet_tier', 'STANDARD'))
            
            # Determine pick side for display purposes
            if market == "SPREAD" or market == "ML":
                pick_side = "home" if pick_val == "HOME" else "away"
            else:
                pick_side = "over" if pick_val == "OVER" else "under"
            
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
                "pick_side": pick_side,
                "model_line": model_str,
                "market_line": market_str,
                "edge": rec['edge'],
                "bet_tier": rec.get('bet_tier', 'STANDARD'),
                "fire_rating": fire,
            })
    
    print(f"[OK] Processed {games_processed} games ({games_skipped} skipped - missing data)")
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
        print(" Sending picks to Microsoft Teams...")
        send_picks_to_teams(all_picks, target_date)


    max_picks = sum(
        1
        for p in all_picks
        if str(p.get("bet_tier", "")).lower() == "max" or p.get("edge", 0) >= 5.0
    )
    health_summary["picks"] = {"total": len(all_picks), "max": max_picks}
    send_health_summary_to_teams(health_summary)


if __name__ == "__main__":
    main()
