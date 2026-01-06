from datetime import datetime, timezone, timedelta
from typing import Optional, List
from uuid import UUID
import time
import sys
import hashlib
import re

from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field, model_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import subprocess
import os
from pathlib import Path
from sqlalchemy import text
from app.prediction_engine_v33 import prediction_engine_v33 as prediction_engine
from app.models import TeamRatings, MarketOdds, Prediction, BettingRecommendation
from app.predictors import fg_spread_model, fg_total_model, h1_spread_model, h1_total_model
from app.config import settings
from app.validation import validate_market_odds, validate_team_ratings
from app.logging_config import get_logger, log_request, log_error
from app.metrics import increment_counter, observe_histogram, Timer

logger = get_logger(__name__)

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)


# -----------------------------
# Request Logging Middleware
# -----------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests with structured logging."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(
            "http_request_started",
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            client_ip=request.client.host if request.client else None,
        )
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            log_request(
                logger,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            
            return response
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_error(
                logger,
                e,
                context={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise


# -----------------------------
# Pydantic request/response DTOs
# -----------------------------

class TeamRatingsInput(BaseModel):
    team_name: str
    adj_o: float
    adj_d: float
    tempo: float
    rank: int
    
    # Four Factors
    efg: float
    efgd: float
    tor: float
    tord: float
    orb: float
    drb: float
    ftr: float
    ftrd: float
    
    # Shooting Breakdown
    two_pt_pct: float
    two_pt_pct_d: float
    three_pt_pct: float
    three_pt_pct_d: float
    three_pt_rate: float
    three_pt_rate_d: float
    barthag: float
    wab: float

    def to_domain(self) -> TeamRatings:
        return TeamRatings(
            team_name=self.team_name,
            adj_o=self.adj_o,
            adj_d=self.adj_d,
            tempo=self.tempo,
            rank=self.rank,
            efg=self.efg,
            efgd=self.efgd,
            tor=self.tor,
            tord=self.tord,
            orb=self.orb,
            drb=self.drb,
            ftr=self.ftr,
            ftrd=self.ftrd,
            two_pt_pct=self.two_pt_pct,
            two_pt_pct_d=self.two_pt_pct_d,
            three_pt_pct=self.three_pt_pct,
            three_pt_pct_d=self.three_pt_pct_d,
            three_pt_rate=self.three_pt_rate,
            three_pt_rate_d=self.three_pt_rate_d,
            barthag=self.barthag,
            wab=self.wab,
        )


class MarketOddsInput(BaseModel):
    spread: Optional[float] = None
    spread_price: Optional[int] = None
    spread_home_price: Optional[int] = None
    spread_away_price: Optional[int] = None
    total: Optional[float] = None
    over_price: Optional[int] = None
    under_price: Optional[int] = None

    # First half
    spread_1h: Optional[float] = None
    total_1h: Optional[float] = None
    spread_price_1h: Optional[int] = None
    spread_1h_home_price: Optional[int] = None
    spread_1h_away_price: Optional[int] = None
    over_price_1h: Optional[int] = None
    under_price_1h: Optional[int] = None

    # Sharp book reference
    sharp_spread: Optional[float] = None
    sharp_total: Optional[float] = None
    # Opening lines (consensus + sharp)
    spread_open: Optional[float] = None
    total_open: Optional[float] = None
    spread_1h_open: Optional[float] = None
    total_1h_open: Optional[float] = None
    sharp_spread_open: Optional[float] = None
    sharp_total_open: Optional[float] = None

    @model_validator(mode="after")
    def _validate_odds_completeness(self):
        def _has_pair(a: Optional[int], b: Optional[int]) -> bool:
            return a is not None and b is not None

        # Disallow "prices without lines" (prevents ambiguous / accidental payloads).
        if self.spread is None and any(
            v is not None for v in [self.spread_price, self.spread_home_price, self.spread_away_price]
        ):
            raise ValueError("spread prices require spread")
        if self.total is None and any(v is not None for v in [self.over_price, self.under_price]):
            raise ValueError("total prices require total")
        if self.spread_1h is None and any(
            v is not None for v in [self.spread_price_1h, self.spread_1h_home_price, self.spread_1h_away_price]
        ):
            raise ValueError("1H spread prices require spread_1h")
        if self.total_1h is None and any(v is not None for v in [self.over_price_1h, self.under_price_1h]):
            raise ValueError("1H total prices require total_1h")

        # Full game spread must include pricing if provided.
        if self.spread is not None:
            if self.spread_price is None and not _has_pair(self.spread_home_price, self.spread_away_price):
                raise ValueError(
                    "spread requires either spread_price or (spread_home_price and spread_away_price)"
                )

        # Full game total must include both sides if provided.
        if self.total is not None:
            if self.over_price is None or self.under_price is None:
                raise ValueError("total requires both over_price and under_price")

        # First half spread must include pricing if provided.
        if self.spread_1h is not None:
            if self.spread_price_1h is None and not _has_pair(self.spread_1h_home_price, self.spread_1h_away_price):
                raise ValueError(
                    "spread_1h requires either spread_price_1h or (spread_1h_home_price and spread_1h_away_price)"
                )

        # First half total must include both sides if provided.
        if self.total_1h is not None:
            if self.over_price_1h is None or self.under_price_1h is None:
                raise ValueError("total_1h requires both over_price_1h and under_price_1h")

        # Require at least one market if market_odds block is present.
        if all(v is None for v in [self.spread, self.total, self.spread_1h, self.total_1h]):
            raise ValueError("market_odds must include at least one market (spread/total/spread_1h/total_1h)")

        return self

    def to_domain(self) -> MarketOdds:
        odds_kwargs = {
            "spread": self.spread,
            "spread_price": self.spread_price,
            "spread_home_price": self.spread_home_price,
            "spread_away_price": self.spread_away_price,
            "total": self.total,
            "over_price": self.over_price,
            "under_price": self.under_price,
            "spread_1h": self.spread_1h,
            "total_1h": self.total_1h,
            "spread_price_1h": self.spread_price_1h,
            "spread_1h_home_price": self.spread_1h_home_price,
            "spread_1h_away_price": self.spread_1h_away_price,
            "over_price_1h": self.over_price_1h,
            "under_price_1h": self.under_price_1h,
            "sharp_spread": self.sharp_spread,
            "sharp_total": self.sharp_total,
            "spread_open": self.spread_open,
            "total_open": self.total_open,
            "spread_1h_open": self.spread_1h_open,
            "total_1h_open": self.total_1h_open,
            "sharp_spread_open": self.sharp_spread_open,
            "sharp_total_open": self.sharp_total_open,
        }
        return MarketOdds(**{k: v for k, v in odds_kwargs.items() if v is not None})


class PredictRequest(BaseModel):
    game_id: UUID
    home_team: str
    away_team: str
    commence_time: datetime
    home_ratings: TeamRatingsInput
    away_ratings: TeamRatingsInput
    market_odds: Optional[MarketOddsInput] = None
    is_neutral: bool = False


class PredictionResponse(BaseModel):
    prediction: dict
    recommendations: List[dict]


# -----------------------------
# FastAPI app
# -----------------------------

app = FastAPI(
    title="NCAA Basketball Prediction Service",
    description="""
    Production-grade NCAA basketball prediction API.
    
    ## Features
    
    - **Predictions**: Generate predictions for spreads and totals (full game + 1H)
    - **Recommendations**: Get betting recommendations with edge analysis
    - **Picks**: Fetch formatted picks for specific dates
    
    ## Model Version
    
    Current model: see `/health` (the service version is also exposed via the OpenAPI `version` field).
    
    - FG Spread: MAE 10.57 pts, 71.9% accuracy (3,318 games)
    - FG Total: MAE 13.1 pts, 10.7 for middle games (3,318 games)
    - 1H Spread: MAE 8.25 pts, 66.6% accuracy (904 games)
    - 1H Total: MAE 8.88 pts (562 games)
    
    ## Authentication
    
    No authentication required for public endpoints. Rate limiting applies.
    """,
    version=settings.service_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add middleware (order matters - logging first)
app.add_middleware(RequestLoggingMiddleware)

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/debug/odds-periods")
async def debug_odds_periods():
    """Diagnostic endpoint to check odds periods in database."""
    import os
    from sqlalchemy import create_engine, text
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return {"error": "DATABASE_URL not set"}
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Check odds periods
            result = conn.execute(text("""
                SELECT period, market_type, COUNT(*) as cnt 
                FROM odds_snapshots 
                WHERE time > NOW() - INTERVAL '24 hours' 
                GROUP BY period, market_type 
                ORDER BY period, market_type
            """))
            periods = [{"period": r.period, "market_type": r.market_type, "count": r.cnt} for r in result]
            
            # Check total odds count
            total_result = conn.execute(text("""
                SELECT COUNT(*) as total FROM odds_snapshots WHERE time > NOW() - INTERVAL '24 hours'
            """))
            total = total_result.scalar()
            
            return {
                "periods": periods,
                "total_odds_last_24h": total,
                "has_1h_odds": any(p["period"] == "1h" for p in periods),
                "has_full_odds": any(p["period"] == "full" for p in periods)
            }
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/game-odds")
async def debug_game_odds():
    """Check which games have 1H odds loaded."""
    import os
    from sqlalchemy import create_engine, text
    from datetime import date
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return {"error": "DATABASE_URL not set"}
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Check 1H odds - which dates do they belong to?
            result_dates = conn.execute(text("""
                SELECT 
                    DATE(g.commence_time AT TIME ZONE 'America/Chicago') as game_date,
                    COUNT(DISTINCT o.game_id) as games_with_1h_odds
                FROM odds_snapshots o
                JOIN games g ON o.game_id = g.id
                WHERE o.period = '1h'
                  AND o.time > NOW() - INTERVAL '24 hours'
                GROUP BY DATE(g.commence_time AT TIME ZONE 'America/Chicago')
                ORDER BY game_date DESC
            """))
            dates_with_1h = [{"date": str(r.game_date), "games_with_1h": r.games_with_1h_odds} for r in result_dates]
            
            # Get today's games with their odds status
            result = conn.execute(text("""
                WITH game_list AS (
                    SELECT 
                        g.id,
                        ht.canonical_name as home_team,
                        at.canonical_name as away_team,
                        g.commence_time
                    FROM games g
                    JOIN teams ht ON g.home_team_id = ht.id
                    JOIN teams at ON g.away_team_id = at.id
                    WHERE DATE(g.commence_time AT TIME ZONE 'America/Chicago') = CURRENT_DATE
                      AND g.status = 'scheduled'
                ),
                odds_status AS (
                    SELECT 
                        game_id,
                        MAX(CASE WHEN period = 'full' AND market_type = 'spreads' THEN 1 ELSE 0 END) as has_full_spread,
                        MAX(CASE WHEN period = '1h' AND market_type = 'spreads' THEN 1 ELSE 0 END) as has_1h_spread,
                        MAX(CASE WHEN period = 'full' AND market_type = 'totals' THEN 1 ELSE 0 END) as has_full_total,
                        MAX(CASE WHEN period = '1h' AND market_type = 'totals' THEN 1 ELSE 0 END) as has_1h_total
                    FROM odds_snapshots
                    WHERE time > NOW() - INTERVAL '24 hours'
                    GROUP BY game_id
                )
                SELECT 
                    gl.home_team || ' vs ' || gl.away_team as matchup,
                    COALESCE(os.has_full_spread, 0) as has_full_spread,
                    COALESCE(os.has_1h_spread, 0) as has_1h_spread,
                    COALESCE(os.has_full_total, 0) as has_full_total,
                    COALESCE(os.has_1h_total, 0) as has_1h_total
                FROM game_list gl
                LEFT JOIN odds_status os ON gl.id = os.game_id
                ORDER BY gl.commence_time
            """))
            
            games = []
            for r in result:
                games.append({
                    "matchup": r.matchup,
                    "full_spread": bool(r.has_full_spread),
                    "1h_spread": bool(r.has_1h_spread),
                    "full_total": bool(r.has_full_total),
                    "1h_total": bool(r.has_1h_total),
                })
            
            return {
                "date": str(date.today()),
                "dates_with_1h_odds": dates_with_1h,
                "games_count": len(games),
                "games_with_1h": sum(1 for g in games if g["1h_spread"]),
                "games": games
            }
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/team-matching")
async def debug_team_matching():
    """Check if teams from odds ingestion match ratings teams."""
    import os
    from sqlalchemy import create_engine, text

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return {"error": "DATABASE_URL not set"}

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Get games with their team info
            result = conn.execute(text("""
                SELECT
                    g.id as game_id,
                    g.commence_time,
                    ht.id as home_team_id,
                    ht.canonical_name as home_team,
                    at.id as away_team_id,
                    at.canonical_name as away_team,
                    (SELECT COUNT(*) FROM team_ratings WHERE team_id = ht.id) as home_ratings_count,
                    (SELECT COUNT(*) FROM team_ratings WHERE team_id = at.id) as away_ratings_count
                FROM games g
                JOIN teams ht ON g.home_team_id = ht.id
                JOIN teams at ON g.away_team_id = at.id
                WHERE g.status = 'scheduled'
                ORDER BY g.commence_time
                LIMIT 20
            """))

            games = []
            for r in result:
                games.append({
                    "game_id": str(r.game_id),
                    "commence_time": str(r.commence_time),
                    "home_team": r.home_team,
                    "home_team_id": str(r.home_team_id),
                    "home_has_ratings": r.home_ratings_count > 0,
                    "away_team": r.away_team,
                    "away_team_id": str(r.away_team_id),
                    "away_has_ratings": r.away_ratings_count > 0,
                })

            # Get total teams and ratings counts
            teams_count = conn.execute(text("SELECT COUNT(*) FROM teams")).scalar()
            ratings_count = conn.execute(text("SELECT COUNT(DISTINCT team_id) FROM team_ratings")).scalar()

            return {
                "total_teams": teams_count,
                "teams_with_ratings": ratings_count,
                "games": games
            }
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/sync-odds")
async def debug_sync_odds():
    """Test the Python odds sync directly."""
    import os
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return {"error": "DATABASE_URL not set"}
        
        from app.odds_sync import sync_odds
        result = sync_odds(
            database_url=database_url,
            enable_full=True,
            enable_h1=True,
            enable_h2=False,
        )
        return result
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


def run_picks_task():
    """Run the picks generation script in background."""
    try:
        print("[trigger-picks] Starting background picks generation task...", flush=True)
        # Run run_today.py (incoming webhook --teams flag removed)
        result = subprocess.run(
            ["python", "run_today.py"],
            capture_output=True,
            text=True,
            cwd="/app"  # Ensure we run from app root in container
        )
        if result.returncode == 0:
            print(f"[trigger-picks] Picks generation completed successfully", flush=True)
            print(f"[trigger-picks] stdout: {result.stdout[:500] if result.stdout else 'none'}", flush=True)
        else:
            print(f"[trigger-picks] Picks generation failed with code {result.returncode}", flush=True)
            print(f"[trigger-picks] stderr: {result.stderr[:1000] if result.stderr else 'none'}", flush=True)
    except Exception as e:
        print(f"[trigger-picks] Failed to run picks task: {e}", flush=True)


@app.get("/trigger-picks")
@limiter.limit("5/minute")
async def trigger_picks(request: Request, background_tasks: BackgroundTasks):
    """Trigger the daily picks generation process."""
    background_tasks.add_task(run_picks_task)
    return {"message": "Picks generation started in background. Use /teams-webhook endpoint for Teams integration."}


@app.get("/trigger-picks-sync")
@limiter.limit("3/minute")
async def trigger_picks_sync(request: Request):
    """Synchronous picks trigger for debugging. Returns result directly."""
    try:
        result = subprocess.run(
            ["python", "run_today.py"],
            capture_output=True,
            text=True,
            cwd="/app",
            timeout=120  # 2 minute timeout
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:] if result.stdout else None,  # Last 2000 chars
            "stderr": result.stderr[-2000:] if result.stderr else None
        }
    except subprocess.TimeoutExpired:
        return {"error": "Script timed out after 120 seconds"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/picks/html")
async def get_picks_html():
    """Serve the latest HTML picks report.

    Freshness contract: if the report is stale, callers must trigger picks
    generation first (e.g. /trigger-picks-sync).
    """
    html_path = Path("/app/output/latest_picks.html")
    if not html_path.exists():
        return {"error": "No report generated yet. Trigger picks first."}

    max_age_minutes = int(os.getenv("MAX_PICKS_REPORT_AGE_MINUTES", "180"))
    try:
        mtime = datetime.fromtimestamp(html_path.stat().st_mtime, tz=timezone.utc)
        age_minutes = (datetime.now(timezone.utc) - mtime).total_seconds() / 60.0
        if age_minutes > max_age_minutes:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Picks report is stale ({age_minutes:.1f}m old > {max_age_minutes}m). "
                    "Trigger picks generation and retry."
                ),
            )
    except HTTPException:
        raise
    except Exception:
        # If filesystem metadata is unavailable, still serve the file.
        pass
    return FileResponse(html_path)


@app.get("/")
async def root():
    return {
        "message": "NCAA Basketball Prediction Service",
        "docs_url": "/docs",
        "health_url": "/health"
    }


@app.get("/health")
async def health():
    """Health check endpoint with database and schema validation."""
    health_status = {
        "service": settings.service_name,
        "version": settings.service_version,
        "git_sha": getattr(settings, "git_sha", "unknown"),
        "build_date": getattr(settings, "build_date", ""),
        "status": "ok",
    }

    # Check database connectivity and schema
    try:
        engine = _get_db_engine()
        if engine:
            with engine.connect() as conn:
                # Check if required migrations are applied
                required_migrations = [
                    '012_recommendation_probabilities.sql',
                    '021_schema_migrations_table.sql'
                ]

                result = conn.execute(text("""
                    SELECT filename FROM public.schema_migrations
                    WHERE filename = ANY(:migrations)
                """), {"migrations": required_migrations})

                applied = {row[0] for row in result}
                missing = [m for m in required_migrations if m not in applied]

                if missing:
                    health_status.update({
                        "status": "degraded",
                        "database": {
                            "connected": True,
                            "missing_migrations": missing,
                            "schema_issue": "Required migrations not applied"
                        }
                    })
                else:
                    health_status["database"] = {
                        "connected": True,
                        "schema_valid": True
                    }
        else:
            health_status.update({
                "status": "error",
                "database": {
                    "connected": False,
                    "error": "Database not configured"
                }
            })
    except Exception as e:
        health_status.update({
            "status": "error",
            "database": {
                "connected": False,
                "error": str(e)
            }
        })

    return health_status


@app.get("/metrics")
async def get_metrics():
    """
    Export metrics in Prometheus-compatible format.
    
    Returns metrics for monitoring and observability.
    """
    from app.metrics import metrics
    
    all_metrics = metrics.get_all_metrics()
    
    # Format for Prometheus (simple text format)
    lines = []

    # Always emit a build/info metric so the payload is never empty and
    # scrapers can validate the endpoint is alive.
    lines.append("# TYPE prediction_service_build_info gauge")
    lines.append(
        'prediction_service_build_info{'
        f'version="{settings.service_version}",'
        f'git_sha="{getattr(settings, "git_sha", "unknown")}",'
        f'build_date="{getattr(settings, "build_date", "")}"'
        "} 1"
    )
    
    # Counters
    for name, value in all_metrics["counters"].items():
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name} {value}")
    
    # Histograms
    for name, stats in all_metrics["histograms"].items():
        lines.append(f"# TYPE {name} histogram")
        lines.append(f"{name}_count {stats['count']}")
        lines.append(f"{name}_sum {stats['sum']}")
        lines.append(f"{name}_avg {stats['avg']}")
        lines.append(f"{name}_min {stats['min']}")
        lines.append(f"{name}_max {stats['max']}")
        lines.append(f"{name}_p50 {stats['p50']}")
        lines.append(f"{name}_p95 {stats['p95']}")
        lines.append(f"{name}_p99 {stats['p99']}")
    
    # Prometheus expects text/plain (not JSON) and a trailing newline is customary.
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")


@app.get("/config")
async def config():
    """Return current model configuration for debugging."""
    return {
        "hca_spread": settings.model.home_court_advantage_spread,
        "hca_total": settings.model.home_court_advantage_total,
        "hca_spread_1h": settings.model.home_court_advantage_spread_1h,
        "hca_total_1h": settings.model.home_court_advantage_total_1h,
        "min_spread_edge": settings.model.min_spread_edge,
        "min_total_edge": settings.model.min_total_edge,
    }


# -----------------------------
# Picks API Endpoint (for frontend integration)
# -----------------------------

from datetime import date, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine, text

CST = ZoneInfo("America/Chicago")


def _odds_snapshot_age_minutes(now_utc: datetime, snapshot_time: Optional[datetime]) -> Optional[float]:
    if snapshot_time is None:
        return None
    if snapshot_time.tzinfo is None:
        snapshot_time = snapshot_time.replace(tzinfo=timezone.utc)
    return (now_utc - snapshot_time.astimezone(timezone.utc)).total_seconds() / 60.0


def _format_american_odds(odds: Optional[int]) -> str:
    if odds is None:
        return "N/A"
    return f"+{int(odds)}" if int(odds) > 0 else str(int(odds))


def _check_recent_team_resolution(engine) -> dict:
    """Best-effort guardrail: ensure canonical resolution isn't degraded."""
    # Keep this aligned with `run_today.py` defaults so behavior is consistent.
    lookback_days = int(os.getenv("TEAM_MATCHING_LOOKBACK_DAYS", "7"))
    min_rate = float(os.getenv("MIN_TEAM_RESOLUTION_RATE", "0.98"))
    max_unresolved = int(os.getenv("MAX_UNRESOLVED_TEAM_VARIANTS", "1"))
    now_utc = datetime.now(timezone.utc)
    lookback_start = now_utc - timedelta(days=lookback_days)

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*)::int AS total,
                    SUM(CASE WHEN resolved_name IS NOT NULL THEN 1 ELSE 0 END)::int AS resolved,
                    SUM(CASE WHEN resolved_name IS NULL THEN 1 ELSE 0 END)::int AS unresolved
                FROM team_resolution_audit
                WHERE created_at >= :lookback_start
                """
            ),
            {"lookback_start": lookback_start},
        ).fetchone()

    total = int(row.total or 0) if row else 0
    resolved = int(row.resolved or 0) if row else 0
    unresolved = int(row.unresolved or 0) if row else 0
    rate = (resolved / total) if total else 1.0
    # Treat no-audit as OK (no recent pressure), and allow a small number of unresolved variants.
    ok = bool((total == 0) or (rate >= min_rate and unresolved <= max_unresolved))
    return {
        "ok": ok,
        "lookback_days": lookback_days,
        "min_rate": min_rate,
        "max_unresolved": max_unresolved,
        "total": total,
        "resolved": resolved,
        "unresolved": unresolved,
        "rate": rate,
    }


def _get_target_date(date_param: str) -> date:
    """Parse date parameter to actual date."""
    today = datetime.now(CST).date()
    if date_param == "today":
        return today
    elif date_param == "tomorrow":
        return today + timedelta(days=1)
    else:
        return datetime.strptime(date_param, "%Y-%m-%d").date()


def _get_db_engine():
    """Get database engine from environment."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Build from docker-compose style env + secrets (sport-parameterized).
        sport = os.getenv("SPORT", "ncaam")
        db_user = os.getenv("DB_USER", sport)
        db_name = os.getenv("DB_NAME", sport)
        db_host = os.getenv("DB_HOST", "postgres")
        db_port = os.getenv("DB_PORT", "5432")

        db_password_file = os.getenv("DB_PASSWORD_FILE", "/run/secrets/db_password")
        if os.path.exists(db_password_file):
            with open(db_password_file, encoding="utf-8") as f:
                db_password = f.read().strip()
            if db_password:
                db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    if not db_url:
        return None
    return create_engine(db_url)


def _model_version_tag() -> str:
    """Stable tag used to scope run locks (date + model version)."""
    return (getattr(prediction_engine, "version_tag", "") or "").strip() or "current"


def _advisory_lock_key(namespace: str, target_date: date, model_version: str) -> int:
    """
    Create a stable signed BIGINT key for pg_advisory_lock.

    Postgres advisory locks take a BIGINT. We derive it from a SHA256 digest and
    coerce into signed int64 range.
    """
    seed = f"{namespace}:{target_date.isoformat()}:{model_version}"
    raw = hashlib.sha256(seed.encode("utf-8")).digest()[:8]
    val = int.from_bytes(raw, byteorder="big", signed=False)
    if val >= 2**63:
        val -= 2**64
    return int(val)


def _run_today_path() -> str:
    """Absolute path to the container's single runner script."""
    # main.py is /app/app/main.py → parent[1] is /app
    return str(Path(__file__).resolve().parents[1] / "run_today.py")


def _check_and_release_stale_lock(conn, lock_key: int, max_lock_age_seconds: int = 1800) -> bool:
    """
    Check if lock is held by a dead process and release it if stale.
    
    Returns True if lock was released, False if lock is active or doesn't exist.
    """
    try:
        # Check if lock is held and by which PID
        result = conn.execute(text("""
            SELECT pid, granted, mode
            FROM pg_locks
            WHERE locktype = 'advisory'
              AND objid = :lock_key
              AND classid = 0
        """), {"lock_key": lock_key}).fetchone()
        
        if not result:
            return False  # No lock exists
        
        pid = result[0]
        granted = result[1]
        
        if not granted:
            return False  # Lock not granted (waiting)
        
        # Check if the process is still alive
        proc_check = conn.execute(text("SELECT pid FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}).fetchone()
        
        if not proc_check:
            # Process is dead - force release the lock
            try:
                conn.execute(text("SELECT pg_advisory_unlock_all() FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid})
            except:
                pass
            # Try to acquire the lock ourselves
            return bool(conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_key}).scalar())
        
        # Process is alive - check if lock is stale (held too long)
        # Note: We can't easily check lock age without tracking, so we'll be conservative
        # and only release if process is definitely dead
        return False
        
    except Exception:
        return False


def _trigger_run_today(
    engine,
    target_date: date,
    *,
    source: str,
    sync: bool = True,
    settle: bool = False,
    allow_data_degrade: bool = False,
    lock_wait_seconds: float = 0.0,
) -> dict:
    """
    Single source-of-truth trigger: run `run_today.py` once for a given date.

    - Uses a Postgres advisory lock so concurrent triggers don't duplicate runs.
    - Automatically detects and releases stale locks from dead processes.
    - Always writes results to Postgres (predictions + betting_recommendations).
    - Returns a small status payload (no large stdout dumps).
    """
    model_version = _model_version_tag()
    lock_key = _advisory_lock_key("run_today", target_date, model_version)
    started_at = datetime.now(timezone.utc)

    # Hold the advisory lock on a single connection for the duration of the run.
    conn = engine.connect()
    try:
        got_lock = False
        
        # First, try to get the lock
        got_lock = bool(conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_key}).scalar())
        
        # If lock is held, check if it's stale (from a dead process)
        if not got_lock:
            if _check_and_release_stale_lock(conn, lock_key):
                got_lock = True
            elif lock_wait_seconds and lock_wait_seconds > 0:
                # Wait with retries, checking for stale locks periodically
                deadline = time.time() + float(lock_wait_seconds)
                while time.time() < deadline:
                    if _check_and_release_stale_lock(conn, lock_key):
                        got_lock = True
                        break
                    got_lock = bool(
                        conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_key}).scalar()
                    )
                    if got_lock:
                        break
                    time.sleep(0.5)

        if not got_lock:
            return {
                "ok": False,
                "status": "busy",
                "source": source,
                "model_version": model_version,
                "date": target_date.isoformat(),
                "message": "Another run is in progress. If this persists, the previous run may have crashed - locks auto-release after connection closes.",
            }

        argv = [sys.executable, _run_today_path(), "--date", target_date.isoformat()]
        if not sync:
            argv.append("--no-sync")
        if not settle:
            argv.append("--no-settle")
        if allow_data_degrade:
            argv.append("--allow-data-degrade")

        timeout_s = int(os.getenv("RUN_TODAY_TIMEOUT_SECONDS", "600"))
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=os.environ.copy(),
        )
        duration_ms = (datetime.now(timezone.utc) - started_at).total_seconds() * 1000.0

        def _tail(s: str, n: int = 20) -> str:
            lines = (s or "").splitlines()
            return "\n".join(lines[-n:]).strip()

        return {
            "ok": proc.returncode == 0,
            "status": "ran",
            "source": source,
            "model_version": model_version,
            "date": target_date.isoformat(),
            "returncode": int(proc.returncode),
            "duration_ms": round(duration_ms, 1),
            "stdout_tail": _tail(proc.stdout),
            "stderr_tail": _tail(proc.stderr),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "status": "timeout",
            "source": source,
            "model_version": model_version,
            "date": target_date.isoformat(),
        }
    finally:
        try:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
        except Exception:
            pass
        conn.close()


def _fetch_persisted_picks(engine, target_date: date) -> List[dict]:
    """
    Read picks from Postgres (single source of truth).

    Uses latest predictions per game_id and their active recommendations.
    """
    model_version = _model_version_tag()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                WITH games_today AS (
                    SELECT g.id, g.commence_time, g.is_neutral, g.status,
                           ht.canonical_name AS home_team,
                           at.canonical_name AS away_team
                    FROM games g
                    JOIN teams ht ON ht.id = g.home_team_id
                    JOIN teams at ON at.id = g.away_team_id
                    WHERE DATE(g.commence_time AT TIME ZONE 'America/Chicago') = :target_date
                      AND g.status = 'scheduled'
                ),
                latest_pred AS (
                    SELECT DISTINCT ON (p.game_id)
                        p.id AS prediction_id,
                        p.game_id,
                        p.model_version,
                        p.created_at,
                        p.predicted_spread,
                        p.predicted_total,
                        p.predicted_spread_1h,
                        p.predicted_total_1h
                    FROM predictions p
                    JOIN games_today gt ON gt.id = p.game_id
                    ORDER BY p.game_id, p.created_at DESC
                )
                SELECT
                    gt.commence_time,
                    gt.home_team,
                    gt.away_team,
                    lp.model_version,
                    br.bet_type,
                    br.pick,
                    br.line,
                    br.edge,
                    br.confidence,
                    br.pick_price,
                    lp.predicted_spread,
                    lp.predicted_total,
                    lp.predicted_spread_1h,
                    lp.predicted_total_1h
                FROM games_today gt
                JOIN latest_pred lp ON lp.game_id = gt.id
                JOIN betting_recommendations br ON br.prediction_id = lp.prediction_id
                WHERE br.status IN ('pending', 'placed')
                ORDER BY gt.commence_time, br.created_at
                """
            ),
            {"target_date": target_date},
        ).fetchall()

    def to_float(v) -> Optional[float]:
        return None if v is None else float(v)

    picks: List[dict] = []
    for r in rows:
        bet_type = str(r.bet_type or "")
        pick = str(r.pick or "")
        is_1h = bet_type.endswith("_1H")
        period = "1H" if is_1h else "FG"
        market_type = "SPREAD" if "SPREAD" in bet_type else "TOTAL"

        # Model/market lines from the PICK perspective (line we are actually betting).
        if market_type == "SPREAD":
            pred_home = to_float(r.predicted_spread_1h if is_1h else r.predicted_spread)
            model_line = None
            if pred_home is not None:
                model_line = pred_home if pick == "HOME" else -pred_home
        else:
            model_line = to_float(r.predicted_total_1h if is_1h else r.predicted_total)

        market_line = to_float(r.line)

        # Pick label for frontend
        if pick == "HOME":
            pick_label = r.home_team
        elif pick == "AWAY":
            pick_label = r.away_team
        elif pick in {"OVER", "UNDER"}:
            pick_label = pick
        else:
            pick_label = pick

        edge_val = to_float(r.edge) or 0.0
        if edge_val >= 5:
            fire_rating = "MAX"
        elif edge_val >= 4:
            fire_rating = "STRONG"
        elif edge_val >= 3:
            fire_rating = "GOOD"
        else:
            fire_rating = "STANDARD"

        game_time = r.commence_time.astimezone(CST)
        time_str = game_time.strftime("%m/%d %I:%M %p")

        picks.append(
            {
                "time_cst": time_str,
                "matchup": f"{r.away_team} @ {r.home_team}",
                "home_team": r.home_team,
                "away_team": r.away_team,
                "period": period,
                "market": market_type,
                "pick": pick_label,
                "pick_odds": _format_american_odds(r.pick_price),
                "model_line": round(model_line, 1) if model_line is not None else None,
                "market_line": round(market_line, 1) if market_line is not None else None,
                "edge": f"+{edge_val:.1f}" if edge_val > 0 else f"{edge_val:.1f}",
                "confidence": f"{float(r.confidence) * 100:.0f}%" if r.confidence is not None else None,
                "fire_rating": fire_rating,
                "model_version": r.model_version,
                "is_current_model": (str(r.model_version or "") == model_version),
            }
        )

    # Sort by edge (highest first), then time
    picks.sort(key=lambda x: (float(x["edge"].replace("+", "")), x["time_cst"]), reverse=True)
    return picks


def _fetch_latest_team_ratings(engine, team_name: str) -> TeamRatings:
    """Resolve team name and fetch latest ratings from DB."""
    with engine.connect() as conn:
        resolved = conn.execute(
            text("SELECT resolve_team_name(:name)"),
            {"name": team_name},
        ).fetchone()
        canonical = resolved[0] if resolved and resolved[0] else None
        if not canonical:
            raise HTTPException(status_code=404, detail=f"Unknown team: {team_name}")

        row = conn.execute(
            text(
                """
                SELECT
                    tr.adj_o,
                    tr.adj_d,
                    tr.tempo,
                    tr.torvik_rank,
                    tr.efg,
                    tr.efgd,
                    tr.tor,
                    tr.tord,
                    tr.orb,
                    tr.drb,
                    tr.ftr,
                    tr.ftrd,
                    tr.two_pt_pct,
                    tr.two_pt_pct_d,
                    tr.three_pt_pct,
                    tr.three_pt_pct_d,
                    tr.three_pt_rate,
                    tr.three_pt_rate_d,
                    tr.barthag,
                    tr.wab
                FROM team_ratings tr
                JOIN teams t ON t.id = tr.team_id
                WHERE t.canonical_name = :canonical
                ORDER BY tr.rating_date DESC
                LIMIT 1
                """
            ),
            {"canonical": canonical},
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"No ratings for team: {canonical}")

    return TeamRatings(
        team_name=canonical,
        adj_o=float(row.adj_o),
        adj_d=float(row.adj_d),
        tempo=float(row.tempo),
        rank=int(row.torvik_rank or 0),
        efg=float(row.efg),
        efgd=float(row.efgd),
        tor=float(row.tor),
        tord=float(row.tord),
        orb=float(row.orb),
        drb=float(row.drb),
        ftr=float(row.ftr),
        ftrd=float(row.ftrd),
        two_pt_pct=float(row.two_pt_pct),
        two_pt_pct_d=float(row.two_pt_pct_d),
        three_pt_pct=float(row.three_pt_pct),
        three_pt_pct_d=float(row.three_pt_pct_d),
        three_pt_rate=float(row.three_pt_rate),
        three_pt_rate_d=float(row.three_pt_rate_d),
        barthag=float(row.barthag),
        wab=float(row.wab),
    )


@app.get("/api/picks/{date_param}")
@limiter.limit("30/minute")
async def get_picks_json(
    request: Request,
    date_param: str = "today",
    trigger: bool = False,
    sync: bool = True,
):
    """
    Fetch picks for a specific date in JSON format (for frontend integration).

    Args:
        date_param: 'today', 'tomorrow', or 'YYYY-MM-DD'

    Returns:
        JSON with picks array matching frontend expected format
    """
    try:
        target_date = _get_target_date(date_param)
    except ValueError:
        return {"error": f"Invalid date format: {date_param}. Use 'today', 'tomorrow', or 'YYYY-MM-DD'"}

    engine = _get_db_engine()
    if not engine:
        return {"error": "Database not configured", "picks": []}

    # Best-effort: include recent team matching health, but do not block serving picks.
    tm = None
    try:
        tm = _check_recent_team_resolution(engine)
    except Exception:
        tm = {"ok": False, "error": "team_matching_check_failed"}

    run_result = None
    if trigger:
        run_result = _trigger_run_today(
            engine,
            target_date,
            source="api_picks",
            sync=bool(sync),
            settle=False,
            allow_data_degrade=False,
            lock_wait_seconds=2.0,
        )

    try:
        picks = _fetch_persisted_picks(engine, target_date)
        return {
            "date": target_date.isoformat(),
            "picks": picks,
            "total_picks": len(picks),
            "generated_at": datetime.now(CST).isoformat(),
            "team_matching": tm,
            "run": run_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching picks: {e}")
        return {"error": str(e), "picks": []}


@app.post("/api/run/{date_param}")
@limiter.limit("10/minute")
async def run_picks(request: Request, date_param: str = "today", sync: bool = True):
    """
    Trigger a model run (single source of truth) and return persisted picks.

    This is safe to call from Teams, a web app, or manual operators.
    Concurrent calls are deduplicated via a Postgres advisory lock.
    """
    try:
        target_date = _get_target_date(date_param)
    except ValueError:
        return {"error": f"Invalid date format: {date_param}. Use 'today', 'tomorrow', or 'YYYY-MM-DD'"}

    engine = _get_db_engine()
    if not engine:
        return {"error": "Database not configured", "picks": []}

    tm = None
    try:
        tm = _check_recent_team_resolution(engine)
    except Exception:
        tm = {"ok": False, "error": "team_matching_check_failed"}

    run_result = _trigger_run_today(
        engine,
        target_date,
        source="api_run",
        sync=bool(sync),
        settle=False,
        allow_data_degrade=False,
        lock_wait_seconds=0.0,
    )
    picks = _fetch_persisted_picks(engine, target_date)
    return {
        "date": target_date.isoformat(),
        "picks": picks,
        "total_picks": len(picks),
        "generated_at": datetime.now(CST).isoformat(),
        "team_matching": tm,
        "run": run_result,
    }


@app.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Generate predictions for a game",
    description="""
    Generate predictions for all 4 markets (FG Spread, FG Total, 1H Spread, 1H Total)
    and betting recommendations based on market odds.
    
    **Input:**
    - Team ratings (all 22 Barttorvik fields required)
    - Market odds (optional, but required for recommendations)
    
    **Output:**
    - Predictions for all 4 markets
    - Betting recommendations (filtered by edge/EV thresholds)
    """,
)
@limiter.limit("60/minute")
async def predict(request: Request, req: PredictRequest):
    increment_counter("predictions_requested_total")
    
    try:
        with Timer("prediction_generation_duration_seconds"):
            home = req.home_ratings.to_domain()
            away = req.away_ratings.to_domain()
            market = req.market_odds.to_domain() if req.market_odds else None

            pred: Prediction = prediction_engine.make_prediction(
                game_id=req.game_id,
                home_team=req.home_team,
                away_team=req.away_team,
                commence_time=req.commence_time,
                home_ratings=home,
                away_ratings=away,
                market_odds=market,
                is_neutral=req.is_neutral,
            )

            recs: List[BettingRecommendation] = []
            if market:
                recs = prediction_engine.generate_recommendations(pred, market)
            
            increment_counter("predictions_generated_total")
            increment_counter("recommendations_generated_total", amount=len(recs))
            
            logger.info(
                "prediction_completed",
                game_id=str(req.game_id),
                home_team=req.home_team,
                away_team=req.away_team,
                recommendations_count=len(recs),
            )
        
        # Convert dataclasses to serializable dicts
        prediction_dict = {
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in pred.__dict__.items()
        }

        recommendations_list = []
        for r in recs:
            d = {
                k: (v.isoformat() if isinstance(v, datetime) else v)
                for k, v in r.__dict__.items()
            }
            # Add formatted outputs
            d["summary"] = r.summary
            d["executive_summary"] = r.executive_summary
            d["detailed_rationale"] = r.detailed_rationale
            d["smoke_score"] = r._calculate_smoke_score()
            recommendations_list.append(d)

        return PredictionResponse(prediction=prediction_dict, recommendations=recommendations_list)
        
    except HTTPException:
        raise
    except Exception as e:
        increment_counter("predictions_errors_total")
        log_error(logger, e, context={"game_id": str(req.game_id)})
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


# -----------------------------
# Teams Outgoing Webhook Handler
# -----------------------------

import hmac
import hashlib
import base64
import json
from fastapi import Request


def _load_teams_webhook_secret() -> Optional[str]:
    """Load Teams webhook secret from Docker secret or environment."""
    # Try Docker secret first
    secret_file = os.getenv("TEAMS_WEBHOOK_SECRET_FILE", "/run/secrets/teams_webhook_secret")
    if os.path.exists(secret_file):
        try:
            with open(secret_file, encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    # Fall back to environment variable
    return os.getenv("TEAMS_WEBHOOK_SECRET")


def _verify_teams_hmac(body: bytes, auth_header: Optional[str], secret: str) -> bool:
    """Verify the HMAC signature from Teams outgoing webhook.
    
    Teams sends: Authorization: HMAC <base64-encoded-hmac>
    We compute: HMAC-SHA256(body, base64_decode(secret))
    """
    if not auth_header:
        return False
    
    # Parse "HMAC <signature>" format
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].upper() != "HMAC":
        return False
    
    received_sig = parts[1]
    
    try:
        # Decode the shared secret (it's base64 encoded)
        secret_bytes = base64.b64decode(secret)
        
        # Compute HMAC-SHA256 of the request body
        computed = hmac.new(secret_bytes, body, hashlib.sha256)
        computed_sig = base64.b64encode(computed.digest()).decode('utf-8')
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(computed_sig, received_sig)
    except Exception as e:
        logger.warning(f"HMAC verification error: {e}")
        return False


class TeamsWebhookMessage(BaseModel):
    """Teams outgoing webhook message structure."""
    text: str
    type: str = "message"
    timestamp: Optional[str] = None
    from_field: Optional[dict] = Field(alias="from", default=None)
    channelData: Optional[dict] = None


@app.post("/teams-webhook")
@limiter.limit("20/minute")
async def teams_webhook_handler(request: Request):
    """Handle incoming messages from Teams outgoing webhook."""
    body_str = ""
    try:
        body = await request.body()
        body_str = body.decode("utf-8")

        # Verify HMAC signature from Teams (if configured)
        webhook_secret = _load_teams_webhook_secret()
        if webhook_secret:
            auth_header = request.headers.get("Authorization")
            if not _verify_teams_hmac(body, auth_header, webhook_secret):
                logger.warning("Teams webhook HMAC verification failed")
                raise HTTPException(status_code=401, detail="Invalid HMAC signature")

        message_data = json.loads(body_str)
        message_text = (message_data.get("text", "") or "").strip().lower()
        sender = message_data.get("from", {})
        sender_name = sender.get("name", "Unknown") if isinstance(sender, dict) else "Unknown"

        picks_keywords = ["picks", "predict", "bets", "recommendations", "show picks", "get picks"]
        wants_picks = any(keyword in message_text for keyword in picks_keywords) or message_text in {"", "hello"}
        wants_all = any(k in message_text for k in [" all", "all ", " all ", "full", "everything"])

        if not wants_picks:
            return {"type": "message", "text": f"Hi {sender_name}! Try: `picks` (or `picks tomorrow`)."}

        # Decide target date (default today; support "tomorrow" and explicit YYYY-MM-DD)
        if "tomorrow" in message_text:
            target_date = datetime.now(CST).date() + timedelta(days=1)
        else:
            m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", message_text)
            if m:
                target_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            else:
                target_date = datetime.now(CST).date()

        engine = _get_db_engine()
        if not engine:
            return {"type": "message", "text": "❌ Database not configured."}

        run_result = _trigger_run_today(
            engine,
            target_date,
            source="teams_webhook",
            sync=True,
            settle=False,
            allow_data_degrade=False,
            lock_wait_seconds=5.0,  # Wait up to 5 seconds for lock to clear
        )
        if run_result.get("status") == "busy":
            msg = run_result.get("message", f"A run is already in progress for {target_date}")
            return {"type": "message", "text": f"⏳ {msg}. Try again in a moment."}

        picks = _fetch_persisted_picks(engine, target_date)
        if not picks:
            extra = ""
            if run_result and not run_result.get("ok", True):
                extra = f" (run rc={run_result.get('returncode')})"
            return {"type": "message", "text": f"⚠️ No picks available for {target_date}.{extra}"}

        max_display = 30 if wants_all else 10
        lines = [f"NCAAM PICKS — {target_date} ({_model_version_tag()})", ""]
        for i, p in enumerate(picks[:max_display], 1):
            market_line = p.get("market_line")
            if market_line is None:
                line_str = ""
            elif p.get("market") == "SPREAD":
                line_str = f" {float(market_line):+.1f}"
            else:
                line_str = f" {float(market_line):.1f}"
            lines.append(
                f"{i}. {p.get('time_cst')} | {p.get('period')} {p.get('market')} | "
                f"{p.get('pick')}{line_str} {p.get('pick_odds')} | edge {p.get('edge')} {p.get('fire_rating')}"
            )
        if len(picks) > max_display:
            lines.append(f"\n...and {len(picks) - max_display} more")

        return {"type": "message", "text": "\n".join(lines)}

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}, body: {body_str[:200]}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Teams webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/predict/fh_total_indep")
async def predict_fh_total_indep(home: str, away: str, neutral: bool = False):
    engine = _get_db_engine()
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")
    home_ratings = _fetch_latest_team_ratings(engine, home)
    away_ratings = _fetch_latest_team_ratings(engine, away)
    pred = h1_total_model.predict(home=home_ratings, away=away_ratings, is_neutral=neutral)
    return {
        "prediction": pred.value,
        "confidence": pred.confidence,
        "home": home_ratings.team_name,
        "away": away_ratings.team_name,
    }


@app.get("/predict/fh_spread_indep")
async def predict_fh_spread_indep(home: str, away: str, neutral: bool = False):
    engine = _get_db_engine()
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")
    home_ratings = _fetch_latest_team_ratings(engine, home)
    away_ratings = _fetch_latest_team_ratings(engine, away)
    pred = h1_spread_model.predict(home=home_ratings, away=away_ratings, is_neutral=neutral)
    return {
        "prediction": pred.value,
        "confidence": pred.confidence,
        "home": home_ratings.team_name,
        "away": away_ratings.team_name,
    }


@app.get("/predict/full_total_indep")
async def predict_full_total_indep(home: str, away: str, neutral: bool = False):
    engine = _get_db_engine()
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")
    home_ratings = _fetch_latest_team_ratings(engine, home)
    away_ratings = _fetch_latest_team_ratings(engine, away)
    pred = fg_total_model.predict(home=home_ratings, away=away_ratings, is_neutral=neutral)
    return {
        "prediction": pred.value,
        "confidence": pred.confidence,
        "home": home_ratings.team_name,
        "away": away_ratings.team_name,
    }


@app.get("/predict/full_spread_indep")
async def predict_full_spread_indep(home: str, away: str, neutral: bool = False):
    engine = _get_db_engine()
    if not engine:
        raise HTTPException(status_code=500, detail="Database not configured")
    home_ratings = _fetch_latest_team_ratings(engine, home)
    away_ratings = _fetch_latest_team_ratings(engine, away)
    pred = fg_spread_model.predict(home=home_ratings, away=away_ratings, is_neutral=neutral)
    return {
        "prediction": pred.value,
        "confidence": pred.confidence,
        "home": home_ratings.team_name,
        "away": away_ratings.team_name,
    }


# Local run helper
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8082, reload=True)
