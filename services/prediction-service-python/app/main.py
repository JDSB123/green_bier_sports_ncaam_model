from datetime import datetime, timezone, timedelta
from typing import Optional, List
from uuid import UUID
import time

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
    
    Current model: **v33.6.3**
    
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
        # Run run_today.py with --teams flag
        result = subprocess.run(
            ["python", "run_today.py", "--teams"],
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
    """Trigger the daily picks generation process and send to Teams."""
    background_tasks.add_task(run_picks_task)
    return {"message": "Picks generation started in background. Check Teams channel shortly."}


@app.get("/trigger-picks-sync")
@limiter.limit("3/minute")
async def trigger_picks_sync(request: Request):
    """Synchronous picks trigger for debugging. Returns result directly."""
    try:
        result = subprocess.run(
            ["python", "run_today.py", "--teams"],
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
    """Health check endpoint."""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "ok",
    }


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
    lines.append(f'prediction_service_build_info{{version="{settings.service_version}"}} 1')
    
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
    lookback_days = int(os.getenv("TEAM_MATCHING_LOOKBACK_DAYS", "30"))
    min_rate = float(os.getenv("MIN_TEAM_RESOLUTION_RATE", "0.99"))
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
    rate = (resolved / total) if total else 0.0
    ok = bool(total > 0 and unresolved == 0 and rate >= min_rate)
    return {
        "ok": ok,
        "lookback_days": lookback_days,
        "min_rate": min_rate,
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
        # Try to construct from secrets
        db_password_file = "/run/secrets/db_password"
        if os.path.exists(db_password_file):
            with open(db_password_file) as f:
                db_password = f.read().strip()
            db_url = f"postgresql+psycopg2://ncaam:{db_password}@postgres:5432/ncaam"
    if not db_url:
        return None
    return create_engine(db_url)


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
async def get_picks_json(request: Request, date_param: str = "today"):
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

    # Hard guardrail: do not serve picks if canonical matching is degraded.
    try:
        tm = _check_recent_team_resolution(engine)
        if not tm.get("ok"):
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Canonical team matching degraded: rate={tm.get('rate', 0.0):.2%} "
                    f"unresolved={tm.get('unresolved', 0)} over {tm.get('lookback_days', 0)}d. "
                    "Run team matching + data sync and retry."
                ),
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Team matching gate error: {type(e).__name__}")

    max_age_full = int(os.getenv("MAX_ODDS_AGE_MINUTES_FULL", "60"))
    max_age_1h = int(os.getenv("MAX_ODDS_AGE_MINUTES_1H", "60"))
    now_utc = datetime.now(timezone.utc)

    picks = []

    try:
        with engine.connect() as conn:
            # Fetch today's games with ratings and odds
            # Use DISTINCT ON to get only the latest rating per team (prevents duplicate rows)
            result = conn.execute(text("""
                WITH latest_home_ratings AS (
                    SELECT DISTINCT ON (team_id)
                        team_id, adj_o, adj_d, tempo, efg, efgd, tor, tord, orb, drb,
                        ftr, ftrd, two_pt_pct, two_pt_pct_d, three_pt_pct, three_pt_pct_d,
                        three_pt_rate, three_pt_rate_d, barthag, wab
                    FROM team_ratings
                    ORDER BY team_id, rating_date DESC
                ),
                latest_away_ratings AS (
                    SELECT DISTINCT ON (team_id)
                        team_id, adj_o, adj_d, tempo, efg, efgd, tor, tord, orb, drb,
                        ftr, ftrd, two_pt_pct, two_pt_pct_d, three_pt_pct, three_pt_pct_d,
                        three_pt_rate, three_pt_rate_d, barthag, wab
                    FROM team_ratings
                    ORDER BY team_id, rating_date DESC
                )
                SELECT
                    g.id as game_id,
                    g.commence_time,
                    ht.canonical_name as home_team,
                    at.canonical_name as away_team,
                    hr.adj_o as home_adj_o, hr.adj_d as home_adj_d, hr.tempo as home_tempo,
                    200 as home_rank,
                    hr.efg as home_efg, hr.efgd as home_efgd,
                    hr.tor as home_tor, hr.tord as home_tord, hr.orb as home_orb, hr.drb as home_drb,
                    hr.ftr as home_ftr, hr.ftrd as home_ftrd, hr.two_pt_pct as home_2pt,
                    hr.two_pt_pct_d as home_2ptd, hr.three_pt_pct as home_3pt, hr.three_pt_pct_d as home_3ptd,
                    hr.three_pt_rate as home_3pr, hr.three_pt_rate_d as home_3prd,
                    hr.barthag as home_barthag, hr.wab as home_wab,
                    ar.adj_o as away_adj_o, ar.adj_d as away_adj_d, ar.tempo as away_tempo,
                    200 as away_rank,
                    ar.efg as away_efg, ar.efgd as away_efgd,
                    ar.tor as away_tor, ar.tord as away_tord, ar.orb as away_orb, ar.drb as away_drb,
                    ar.ftr as away_ftr, ar.ftrd as away_ftrd, ar.two_pt_pct as away_2pt,
                    ar.two_pt_pct_d as away_2ptd, ar.three_pt_pct as away_3pt, ar.three_pt_pct_d as away_3ptd,
                    ar.three_pt_rate as away_3pr, ar.three_pt_rate_d as away_3prd,
                    ar.barthag as away_barthag, ar.wab as away_wab,
                    -- Full game odds (latest)
                    (SELECT home_line FROM odds_snapshots WHERE game_id = g.id AND period = 'full' AND market_type = 'spreads' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_spread,
                    (SELECT home_price FROM odds_snapshots WHERE game_id = g.id AND period = 'full' AND market_type = 'spreads' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_spread_home_price,
                    (SELECT away_price FROM odds_snapshots WHERE game_id = g.id AND period = 'full' AND market_type = 'spreads' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_spread_away_price,
                    (SELECT time FROM odds_snapshots WHERE game_id = g.id AND period = 'full' AND market_type = 'spreads' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_spread_time,

                    (SELECT total_line FROM odds_snapshots WHERE game_id = g.id AND period = 'full' AND market_type = 'totals' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_total,
                    (SELECT over_price FROM odds_snapshots WHERE game_id = g.id AND period = 'full' AND market_type = 'totals' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_over_price,
                    (SELECT under_price FROM odds_snapshots WHERE game_id = g.id AND period = 'full' AND market_type = 'totals' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_under_price,
                    (SELECT time FROM odds_snapshots WHERE game_id = g.id AND period = 'full' AND market_type = 'totals' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_total_time,

                    -- 1H odds (latest)
                    (SELECT home_line FROM odds_snapshots WHERE game_id = g.id AND period = '1h' AND market_type = 'spreads' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_spread_1h,
                    (SELECT home_price FROM odds_snapshots WHERE game_id = g.id AND period = '1h' AND market_type = 'spreads' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_spread_1h_home_price,
                    (SELECT away_price FROM odds_snapshots WHERE game_id = g.id AND period = '1h' AND market_type = 'spreads' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_spread_1h_away_price,
                    (SELECT time FROM odds_snapshots WHERE game_id = g.id AND period = '1h' AND market_type = 'spreads' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_spread_1h_time,

                    (SELECT total_line FROM odds_snapshots WHERE game_id = g.id AND period = '1h' AND market_type = 'totals' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_total_1h,
                    (SELECT over_price FROM odds_snapshots WHERE game_id = g.id AND period = '1h' AND market_type = 'totals' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_over_price_1h,
                    (SELECT under_price FROM odds_snapshots WHERE game_id = g.id AND period = '1h' AND market_type = 'totals' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_under_price_1h,
                    (SELECT time FROM odds_snapshots WHERE game_id = g.id AND period = '1h' AND market_type = 'totals' ORDER BY (bookmaker='pinnacle') DESC, (bookmaker='bovada') DESC, time DESC LIMIT 1) as market_total_1h_time
                FROM games g
                JOIN teams ht ON g.home_team_id = ht.id
                JOIN teams at ON g.away_team_id = at.id
                LEFT JOIN latest_home_ratings hr ON ht.id = hr.team_id
                LEFT JOIN latest_away_ratings ar ON at.id = ar.team_id
                WHERE DATE(g.commence_time AT TIME ZONE 'America/Chicago') = :target_date
                  AND g.status = 'scheduled'
                ORDER BY g.commence_time
            """), {"target_date": target_date})

            # Helper to safely convert to float
            def to_float(v, default=0.0):
                if v is None:
                    return default
                return float(v)

            for row in result:
                # Skip games without ratings
                if not row.home_adj_o or not row.away_adj_o:
                    continue

                # Build TeamRatings objects (convert decimals to floats)
                home_ratings = TeamRatings(
                    team_name=row.home_team,
                    adj_o=to_float(row.home_adj_o), adj_d=to_float(row.home_adj_d), tempo=to_float(row.home_tempo),
                    rank=row.home_rank or 200,
                    efg=to_float(row.home_efg, 50), efgd=to_float(row.home_efgd, 50),
                    tor=to_float(row.home_tor, 18), tord=to_float(row.home_tord, 18),
                    orb=to_float(row.home_orb, 28), drb=to_float(row.home_drb, 72),
                    ftr=to_float(row.home_ftr, 33), ftrd=to_float(row.home_ftrd, 33),
                    two_pt_pct=to_float(row.home_2pt, 50), two_pt_pct_d=to_float(row.home_2ptd, 50),
                    three_pt_pct=to_float(row.home_3pt, 35), three_pt_pct_d=to_float(row.home_3ptd, 35),
                    three_pt_rate=to_float(row.home_3pr, 35), three_pt_rate_d=to_float(row.home_3prd, 35),
                    barthag=to_float(row.home_barthag, 0.5), wab=to_float(row.home_wab, 0),
                )
                away_ratings = TeamRatings(
                    team_name=row.away_team,
                    adj_o=to_float(row.away_adj_o), adj_d=to_float(row.away_adj_d), tempo=to_float(row.away_tempo),
                    rank=row.away_rank or 200,
                    efg=to_float(row.away_efg, 50), efgd=to_float(row.away_efgd, 50),
                    tor=to_float(row.away_tor, 18), tord=to_float(row.away_tord, 18),
                    orb=to_float(row.away_orb, 28), drb=to_float(row.away_drb, 72),
                    ftr=to_float(row.away_ftr, 33), ftrd=to_float(row.away_ftrd, 33),
                    two_pt_pct=to_float(row.away_2pt, 50), two_pt_pct_d=to_float(row.away_2ptd, 50),
                    three_pt_pct=to_float(row.away_3pt, 35), three_pt_pct_d=to_float(row.away_3ptd, 35),
                    three_pt_rate=to_float(row.away_3pr, 35), three_pt_rate_d=to_float(row.away_3prd, 35),
                    barthag=to_float(row.away_barthag, 0.5), wab=to_float(row.away_wab, 0),
                )

                # Build MarketOdds if available (convert decimals to floats)
                market_odds = None
                if row.market_spread is not None or row.market_total is not None:
                    # Freshness + price completeness: do not compute picks on stale/incomplete odds.
                    if row.market_spread is not None:
                        spread_age = _odds_snapshot_age_minutes(now_utc, row.market_spread_time)
                        if spread_age is None or spread_age > max_age_full:
                            raise HTTPException(
                                status_code=503,
                                detail=f"Stale/missing full-game spread odds for {row.away_team} @ {row.home_team}",
                            )
                        if row.market_spread_home_price is None or row.market_spread_away_price is None:
                            raise HTTPException(
                                status_code=503,
                                detail=f"Missing full-game spread prices for {row.away_team} @ {row.home_team}",
                            )
                    if row.market_total is not None:
                        total_age = _odds_snapshot_age_minutes(now_utc, row.market_total_time)
                        if total_age is None or total_age > max_age_full:
                            raise HTTPException(
                                status_code=503,
                                detail=f"Stale/missing full-game total odds for {row.away_team} @ {row.home_team}",
                            )
                        if row.market_over_price is None or row.market_under_price is None:
                            raise HTTPException(
                                status_code=503,
                                detail=f"Missing full-game total prices for {row.away_team} @ {row.home_team}",
                            )

                    if row.market_spread_1h is not None:
                        spread_1h_age = _odds_snapshot_age_minutes(now_utc, row.market_spread_1h_time)
                        if spread_1h_age is None or spread_1h_age > max_age_1h:
                            raise HTTPException(
                                status_code=503,
                                detail=f"Stale/missing 1H spread odds for {row.away_team} @ {row.home_team}",
                            )
                        if row.market_spread_1h_home_price is None or row.market_spread_1h_away_price is None:
                            raise HTTPException(
                                status_code=503,
                                detail=f"Missing 1H spread prices for {row.away_team} @ {row.home_team}",
                            )
                    if row.market_total_1h is not None:
                        total_1h_age = _odds_snapshot_age_minutes(now_utc, row.market_total_1h_time)
                        if total_1h_age is None or total_1h_age > max_age_1h:
                            raise HTTPException(
                                status_code=503,
                                detail=f"Stale/missing 1H total odds for {row.away_team} @ {row.home_team}",
                            )
                        if row.market_over_price_1h is None or row.market_under_price_1h is None:
                            raise HTTPException(
                                status_code=503,
                                detail=f"Missing 1H total prices for {row.away_team} @ {row.home_team}",
                            )

                    odds_kwargs = {}
                    if row.market_spread is not None:
                        odds_kwargs.update(
                            {
                                "spread": to_float(row.market_spread),
                                "spread_home_price": int(row.market_spread_home_price),
                                "spread_away_price": int(row.market_spread_away_price),
                                "spread_price": int(row.market_spread_home_price),
                            }
                        )
                    if row.market_total is not None:
                        odds_kwargs.update(
                            {
                                "total": to_float(row.market_total),
                                "over_price": int(row.market_over_price),
                                "under_price": int(row.market_under_price),
                            }
                        )
                    if row.market_spread_1h is not None:
                        odds_kwargs.update(
                            {
                                "spread_1h": to_float(row.market_spread_1h),
                                "spread_1h_home_price": int(row.market_spread_1h_home_price),
                                "spread_1h_away_price": int(row.market_spread_1h_away_price),
                                "spread_price_1h": int(row.market_spread_1h_home_price),
                            }
                        )
                    if row.market_total_1h is not None:
                        odds_kwargs.update(
                            {
                                "total_1h": to_float(row.market_total_1h),
                                "over_price_1h": int(row.market_over_price_1h),
                                "under_price_1h": int(row.market_under_price_1h),
                            }
                        )
                    market_odds = MarketOdds(**odds_kwargs)

                # Generate prediction
                prediction = prediction_engine.make_prediction(
                    game_id=row.game_id,
                    home_team=row.home_team,
                    away_team=row.away_team,
                    commence_time=row.commence_time,
                    home_ratings=home_ratings,
                    away_ratings=away_ratings,
                    market_odds=market_odds,
                )

                # Generate recommendations
                if market_odds:
                    recs = prediction_engine.generate_recommendations(prediction, market_odds)

                    for rec in recs:
                        # Format time in CST
                        game_time = row.commence_time.astimezone(CST)
                        time_str = game_time.strftime("%m/%d %I:%M %p")

                        # Determine period and market type
                        bet_type = rec.bet_type.value if hasattr(rec.bet_type, 'value') else str(rec.bet_type)
                        is_1h = "1H" in bet_type
                        period = "1H" if is_1h else "FG"
                        market_type = "SPREAD" if "SPREAD" in bet_type else "TOTAL"

                        # Format edge as percentage
                        edge_pct = rec.edge if isinstance(rec.edge, (int, float)) else 0

                        # Map confidence to fire rating
                        if edge_pct >= 5:
                            fire_rating = "MAX"
                        elif edge_pct >= 4:
                            fire_rating = "STRONG"
                        elif edge_pct >= 3:
                            fire_rating = "GOOD"
                        else:
                            fire_rating = "STANDARD"

                        # Pick display
                        pick_str = rec.pick.value if hasattr(rec.pick, 'value') else str(rec.pick)
                        if pick_str == "HOME":
                            pick_team = row.home_team
                        elif pick_str == "AWAY":
                            pick_team = row.away_team
                        elif pick_str == "OVER":
                            pick_team = "OVER"
                        elif pick_str == "UNDER":
                            pick_team = "UNDER"
                        else:
                            pick_team = pick_str

                        picks.append({
                            "time_cst": time_str,
                            "matchup": f"{row.away_team} @ {row.home_team}",
                            "home_team": row.home_team,
                            "away_team": row.away_team,
                            "period": period,
                            "market": market_type,
                            "pick": pick_team,
                            "pick_odds": _format_american_odds(getattr(rec, "pick_price", None)),
                            "model_line": round(rec.model_line, 1) if rec.model_line else None,
                            "market_line": round(rec.market_line, 1) if rec.market_line else None,
                            "edge": f"+{edge_pct:.1f}" if edge_pct > 0 else f"{edge_pct:.1f}",
                            "confidence": f"{rec.confidence * 100:.0f}%" if rec.confidence else None,
                            "fire_rating": fire_rating,
                        })

        # Sort by edge (highest first)
        picks.sort(key=lambda x: float(x["edge"].replace("+", "")), reverse=True)

        return {
            "date": target_date.isoformat(),
            "picks": picks,
            "total_picks": len(picks),
            "generated_at": datetime.now(CST).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching picks: {e}")
        return {"error": str(e), "picks": []}


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
import json
from fastapi import Request


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
    try:
        # Get the raw request body
        body = await request.body()
        body_str = body.decode('utf-8')

        # NOTE: Avoid logging full headers/body in production (can include tokens).
        logger.info("Teams webhook received")

        # Parse the message
        message_data = json.loads(body_str)
        
        # Extract message details
        message_text = (message_data.get("text", "") or "").strip().lower()
        sender = message_data.get("from", {})
        sender_name = sender.get("name", "Unknown") if isinstance(sender, dict) else "Unknown"

        # Process the message
        logger.info(f"Message from {sender_name}: {message_text}")

        # Check if user is asking for picks
        picks_keywords = ["picks", "predict", "bets", "recommendations", "show picks", "get picks"]
        wants_picks = any(keyword in message_text for keyword in picks_keywords) or message_text == "" or message_text == "hello"
        wants_all = any(k in message_text for k in [" all", "all ", " all ", "full", "everything"])

        if wants_picks:
            # Generate picks by calling run_today.py and capture the output
            logger.info("Generating picks for Teams webhook request")
            response = None
            try:
                # Import the pick generation logic
                from datetime import date
                from sqlalchemy import create_engine, text
                from app.prediction_engine_v33 import prediction_engine_v33 as prediction_engine
                from app.models import TeamRatings, MarketOdds
                from app.situational import SituationalAdjuster
                
                # Get database connection (same logic as run_today.py)
                db_password = os.getenv("DB_PASSWORD")
                if not db_password:
                    try:
                        with open("/run/secrets/db_password", 'r') as f:
                            db_password = f.read().strip()
                    except FileNotFoundError:
                        db_password = os.getenv("DB_PASSWORD_FILE", "")
                
                db_user = os.getenv("DB_USER", "ncaam")
                db_name = os.getenv("DB_NAME", "ncaam")
                db_host = os.getenv("DB_HOST", "postgres")
                db_port = os.getenv("DB_PORT", "5432")
                
                database_url = os.getenv("DATABASE_URL")
                if not database_url:
                    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
                
                # Get target date (today)
                target_date = date.today()
                
                # Create DB engine
                engine = create_engine(database_url, pool_pre_ping=True)
                
                # Import run_today safely (run_today.py is patched to avoid mutating sys.stdout on import)
                import sys
                if "/app" not in sys.path:
                    sys.path.insert(0, "/app")
                import run_today as run_today_module
                
                # Fetch games
                games = run_today_module.fetch_games_from_db(target_date=target_date, engine=engine)

                # Hard gates: canonical matching + fresh odds only
                try:
                    tm_recent = run_today_module._check_recent_team_resolution(
                        engine=engine,
                        lookback_days=int(os.getenv("TEAM_MATCHING_LOOKBACK_DAYS", "30")),
                        min_resolution_rate=float(os.getenv("MIN_TEAM_RESOLUTION_RATE", "0.99")),
                    )
                    if not tm_recent.get("ok"):
                        return {
                            "type": "message",
                            "text": (
                                "❌ BLOCKED: Canonical team matching degraded. "
                                f"rate={float(tm_recent.get('rate', 0.0)):.2%} "
                                f"unresolved={tm_recent.get('unresolved', 0)} "
                                f"lookback={tm_recent.get('lookback_days', 0)}d"
                            ),
                        }
                except Exception as e:
                    return {
                        "type": "message",
                        "text": f"❌ BLOCKED: Team matching gate error: {type(e).__name__}: {e}",
                    }

                try:
                    odds_failures = run_today_module._enforce_odds_freshness_and_completeness(
                        games=games,
                        max_age_full_minutes=int(os.getenv("MAX_ODDS_AGE_MINUTES_FULL", "60")),
                        max_age_1h_minutes=int(os.getenv("MAX_ODDS_AGE_MINUTES_1H", "60")),
                    )
                    if odds_failures:
                        sample = "\n".join(f"- {m}" for m in odds_failures[:10])
                        more = "" if len(odds_failures) <= 10 else f"\n...and {len(odds_failures) - 10} more"
                        return {
                            "type": "message",
                            "text": "❌ BLOCKED: stale/incomplete odds detected:\n" + sample + more,
                        }
                except Exception as e:
                    return {
                        "type": "message",
                        "text": f"❌ BLOCKED: Odds freshness gate error: {type(e).__name__}: {e}",
                    }
                
                if not games:
                    response = {
                        "type": "message",
                        "text": f"⚠️ No games found for {target_date}"
                    }
                    return response
                
                # Import helper functions from run_today
                format_spread = run_today_module.format_spread
                format_odds = run_today_module.format_odds
                get_fire_rating = run_today_module.get_fire_rating
                from uuid import uuid4
                from datetime import datetime
                from app.situational import RestInfo
                
                # Generate picks using same logic as run_today.py
                situational_adjuster = SituationalAdjuster()
                all_picks = []
                
                for game in games:
                    if not game.get("home_ratings") or not game.get("away_ratings"):
                        continue
                    
                    home_ratings = TeamRatings(**game["home_ratings"])
                    away_ratings = TeamRatings(**game["away_ratings"])
                    
                    # Parse commence_time
                    commence_time = datetime.now()
                    if game.get("commence_time"):
                        if isinstance(game["commence_time"], str):
                            commence_time = datetime.fromisoformat(game["commence_time"].replace('Z', '+00:00'))
                        else:
                            commence_time = game["commence_time"]
                    
                    # Create market odds object
                    odds_kwargs = {}
                    if game.get("spread") is not None:
                        odds_kwargs.update(
                            {
                                "spread": game.get("spread"),
                                "spread_home_price": game.get("spread_home_juice"),
                                "spread_away_price": game.get("spread_away_juice"),
                                "spread_price": game.get("spread_home_juice") or game.get("spread_away_juice"),
                            }
                        )
                    if game.get("total") is not None:
                        odds_kwargs.update(
                            {
                                "total": game.get("total"),
                                "over_price": game.get("over_juice"),
                                "under_price": game.get("under_juice"),
                            }
                        )
                    if game.get("spread_1h") is not None:
                        odds_kwargs.update(
                            {
                                "spread_1h": game.get("spread_1h"),
                                "spread_1h_home_price": game.get("spread_1h_home_juice"),
                                "spread_1h_away_price": game.get("spread_1h_away_juice"),
                                "spread_price_1h": game.get("spread_1h_home_juice") or game.get("spread_1h_away_juice"),
                            }
                        )
                    if game.get("total_1h") is not None:
                        odds_kwargs.update(
                            {
                                "total_1h": game.get("total_1h"),
                                "over_price_1h": game.get("over_1h_juice"),
                                "under_price_1h": game.get("under_1h_juice"),
                            }
                        )

                    # Sharp reference + opens if present
                    odds_kwargs.update(
                        {
                            "sharp_spread": game.get("sharp_spread"),
                            "sharp_total": game.get("sharp_total"),
                            "spread_open": game.get("spread_open"),
                            "total_open": game.get("total_open"),
                            "spread_1h_open": game.get("spread_1h_open"),
                            "total_1h_open": game.get("total_1h_open"),
                            "sharp_spread_open": game.get("sharp_spread_open"),
                            "sharp_total_open": game.get("sharp_total_open"),
                        }
                    )
                    market_odds_obj = MarketOdds(**{k: v for k, v in odds_kwargs.items() if v is not None})
                    
                    # Validate market odds (log warnings/errors but continue)
                    odds_validation = validate_market_odds(
                        spread=game.get("spread"),
                        total=game.get("total"),
                        spread_1h=game.get("spread_1h"),
                        total_1h=game.get("total_1h"),
                        context=f"{game['away']} @ {game['home']}"
                    )
                    if not odds_validation.is_valid:
                        logger.warning(f"⚠️ Invalid odds for {game['away']} @ {game['home']}, skipping game")
                        continue
                    
                    # Get rest info
                    home_rest = None
                    away_rest = None
                    if game.get("rest_info"):
                        rest_info = game["rest_info"]
                        if rest_info.get("home_rest"):
                            home_rest = RestInfo(**rest_info["home_rest"])
                        if rest_info.get("away_rest"):
                            away_rest = RestInfo(**rest_info["away_rest"])
                    
                    # Generate prediction using make_prediction
                    game_id = uuid4()
                    pred = prediction_engine.make_prediction(
                        game_id=game_id,
                        home_team=game["home"],
                        away_team=game["away"],
                        commence_time=commence_time,
                        home_ratings=home_ratings,
                        away_ratings=away_ratings,
                        market_odds=market_odds_obj,
                        is_neutral=not game.get("is_home_court", True),
                        home_rest=home_rest,
                        away_rest=away_rest
                    )
                    
                    # Get recommendations
                    recommendations = prediction_engine.generate_recommendations(pred, market_odds_obj)
                    
                    # Use prediction object directly (it's a dataclass)
                    
                    # Process each recommendation
                    for rec in recommendations:
                        # Determine period from bet_type
                        bet_type_value = rec.bet_type.value if hasattr(rec.bet_type, 'value') else str(rec.bet_type)
                        is_1h = "1H" in bet_type_value
                        period = "1H" if is_1h else "FG"
                        
                        # Determine market type
                        bet_type_str = bet_type_value.upper()
                        if "SPREAD" in bet_type_str:
                            market = "SPREAD"
                        elif "TOTAL" in bet_type_str:
                            market = "TOTAL"
                        else:
                            market = "ML"

                        # Normalize edge to POINTS for all markets (ML is percent-based in engine)
                        sigma = settings.model.spread_to_ml_sigma
                        if is_1h:
                            # Rough scaling: 1H tends to be noisier (larger sigma)
                            sigma = sigma * getattr(settings.model, "variance_1h_multiplier", 1.0)

                        if market == "ML":
                            # Convert % edge to spread-points-equivalent for consistent display/thresholding
                            edge_points = (rec.edge / 100.0) * sigma
                        else:
                            # Spread/Total edges are already in points
                            edge_points = rec.edge

                        # Apply market-specific thresholds (this fixes totals being over-selected)
                        min_edge_points = settings.model.min_spread_edge
                        if market == "TOTAL":
                            min_edge_points = settings.model.min_total_edge
                        if edge_points < min_edge_points:
                            continue
                        
                        # Format pick display with odds
                        pick_val = rec.pick.value if hasattr(rec.pick, 'value') else str(rec.pick)
                        if market == "SPREAD":
                            if pick_val == "HOME":
                                team_name = game["home"]
                                line = game["spread"] if not is_1h else game.get("spread_1h")
                                juice = game.get("spread_home_juice") if not is_1h else game.get("spread_1h_home_juice")
                            else:
                                team_name = game["away"]
                                line = -(game["spread"]) if game["spread"] and not is_1h else (-(game.get("spread_1h")) if game.get("spread_1h") else None)
                                juice = game.get("spread_away_juice") if not is_1h else game.get("spread_1h_away_juice")
                            pick_display = f"{team_name[:20]} {format_spread(line)} ({format_odds(juice)})"
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

                        # Model line display
                        if market == "SPREAD":
                            # Show model from PICK perspective (home-perspective lines are confusing for AWAY picks)
                            model_line_val_home = pred.predicted_spread if not is_1h else pred.predicted_spread_1h
                            model_line_val = model_line_val_home if pick_val == "HOME" else -model_line_val_home
                            model_str = format_spread(model_line_val)
                        elif market == "TOTAL":
                            model_line_val = pred.predicted_total if not is_1h else pred.predicted_total_1h
                            model_str = f"{model_line_val:.1f}"
                        else:
                            continue

                        # Market line display with juice
                        if market == "SPREAD":
                            mkt_line_home = game["spread"] if not is_1h else game.get("spread_1h")
                            # Show market from PICK perspective (+ for underdog side)
                            mkt_line = mkt_line_home if pick_val == "HOME" else (-mkt_line_home if mkt_line_home is not None else None)
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
                        bet_tier_value = rec.bet_tier.value if hasattr(rec.bet_tier, 'value') else str(rec.bet_tier) if hasattr(rec, 'bet_tier') else 'standard'

                        def _fire_rating(edge_pts: float, bet_tier: str) -> str:
                            tier = (bet_tier or "").strip().lower()
                            if tier == "max" or edge_pts >= 5.0:
                                return "🔥🔥🔥🔥🔥"
                            if tier == "medium" or edge_pts >= 4.0:
                                return "🔥🔥🔥🔥"
                            if edge_pts >= 3.5:
                                return "🔥🔥🔥"
                            if edge_pts >= 3.0:
                                return "🔥🔥"
                            if edge_pts >= settings.model.min_spread_edge:
                                return "🔥"
                            return ""

                        fire = _fire_rating(edge_points, bet_tier_value)

                        # Edge display (points only)
                        edge_str = f"{edge_points:.1f} pts"
                        
                        all_picks.append({
                            "date_cst": game.get("date_cst", str(target_date)),
                            "time_cst": game.get("time_cst", ""),
                            "home": game["home"],
                            "away": game["away"],
                            "home_record": game.get("home_record"),
                            "away_record": game.get("away_record"),
                            "period": period,
                            "market": market,
                            "pick_display": pick_display,
                            "model_line": model_str,
                            "market_line": market_str,
                            # Keep both raw and normalized edge
                            "edge": edge_points,
                            "edge_raw": rec.edge,
                            "edge_str": edge_str,
                            "fire_rating": fire,
                        })
                
                # Sort by edge
                all_picks.sort(key=lambda x: x['edge'], reverse=True)
                
                # -----------------------------
                # Dedupe + full report helpers
                # -----------------------------
                def _dedupe(picks: list[dict]) -> list[dict]:
                    """Remove exact duplicates while preserving highest edge per key."""
                    best: dict[tuple, dict] = {}
                    for p in picks:
                        key = (
                            (p.get("date_cst") or ""),
                            (p.get("time_cst") or ""),
                            p.get("away"),
                            p.get("home"),
                            p.get("market"),
                            p.get("period"),
                            p.get("pick_display"),
                            p.get("model_line"),
                            p.get("market_line"),
                        )
                        prev = best.get(key)
                        if prev is None or (p.get("edge", 0) > prev.get("edge", 0)):
                            best[key] = p
                    return sorted(best.values(), key=lambda x: x.get("edge", 0), reverse=True)

                def _base_url() -> str:
                    # Prefer forwarded host (Azure/Ingress), fall back to Host
                    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
                    # Trust request scheme if present; default to https for cloud
                    scheme = request.url.scheme or "https"
                    if "localhost" in host or host.startswith("127.0.0.1"):
                        scheme = "http"
                    return f"{scheme}://{host}" if host else str(request.base_url).rstrip("/")

                def _write_html_report(picks: list[dict]) -> None:
                    """Write /app/output/latest_picks.html so /picks/html can serve it."""
                    out_path = Path("/app/output/latest_picks.html")
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    rows = []
                    for i, p in enumerate(picks, 1):
                        dt = f"{p.get('date_cst','')} {p.get('time_cst','')}".strip()
                        home_rec = p.get("home_record") or "?"
                        away_rec = p.get("away_record") or "?"
                        matchup = f"{p.get('away','')} ({away_rec}) vs {p.get('home','')} ({home_rec})"
                        seg = f"{p.get('market','')} ({p.get('period','')})".strip()
                        rows.append(
                            f"<tr>"
                            f"<td>{i}</td>"
                            f"<td>{dt}</td>"
                            f"<td>{matchup}</td>"
                            f"<td>{seg}</td>"
                            f"<td>{p.get('pick_display','')}</td>"
                            f"<td>{p.get('model_line','')}</td>"
                            f"<td>{p.get('market_line','')}</td>"
                            f"<td>{p.get('edge_str','')}</td>"
                            f"<td>{p.get('fire_rating','')}</td>"
                            f"</tr>"
                        )
                    html = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>NCAAM Picks - {target_date}</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 16px; }}
      h1 {{ margin: 0 0 8px 0; }}
      .sub {{ color: #555; margin: 0 0 16px 0; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
      th {{ background: #f6f6f6; text-align: left; }}
      tr:nth-child(even) {{ background: #fafafa; }}
      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }}
    </style>
  </head>
  <body>
    <h1>🏀 NCAAM Picks - {target_date}</h1>
    <p class="sub">Total picks: {len(picks)}</p>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Date/Time CST</th>
          <th>Away vs Home (Record)</th>
          <th>Seg</th>
          <th>Pick (odds)</th>
          <th class="mono">Model</th>
          <th class="mono">Market</th>
          <th class="mono">Edge</th>
          <th>Fire</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </body>
</html>
"""
                    out_path.write_text(html, encoding="utf-8")

                # Dedupe by default (fixes “duplicative” output); allow `picks all` to show raw list
                picks_for_report = all_picks
                picks_for_card = all_picks
                if not wants_all:
                    picks_for_card = _dedupe(all_picks)
                # Always write the full report (raw list) so user can view every pick
                _write_html_report(picks_for_report)

                # Format response according to user preferences (Adaptive Card table)
                if picks_for_card:
                    def _col(text: str, width: str = "stretch", weight: str = "Default", is_subtle: bool = False) -> dict:
                        return {
                            "type": "Column",
                            "width": width,
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": text,
                                    "wrap": True,
                                    "weight": weight,
                                    "isSubtle": is_subtle,
                                    "size": "Small",
                                }
                            ],
                        }

                    # Build a table-like Adaptive Card (renders much better than markdown tables in Teams)
                    header_row = {
                        "type": "ColumnSet",
                        "columns": [
                            _col("Date/Time CST", "auto", "Bolder"),
                            _col("Away vs Home (Record)", "stretch", "Bolder"),
                            _col("Seg", "auto", "Bolder"),
                            _col("Pick (odds)", "auto", "Bolder"),
                            _col("Model", "auto", "Bolder"),
                            _col("Market", "auto", "Bolder"),
                            _col("Edge", "auto", "Bolder"),
                            _col("Fire", "auto", "Bolder"),
                        ],
                    }

                    table_rows = [header_row]
                    # Teams message size is limited; cap visible rows.
                    max_rows = 25 if wants_all else 15
                    for p in picks_for_card[:max_rows]:
                        date_time = f"{p.get('date_cst', target_date)} {p.get('time_cst','')}".strip()
                        home_rec = p.get("home_record") or "?"
                        away_rec = p.get("away_record") or "?"
                        matchup = f"{p['away']} ({away_rec}) vs {p['home']} ({home_rec})"
                        seg = f"{p.get('market','')} ({p.get('period','')})".strip()
                        table_rows.append(
                            {
                                "type": "ColumnSet",
                                "separator": True,
                                "columns": [
                                    _col(date_time, "auto"),
                                    _col(matchup, "stretch"),
                                    _col(seg, "auto", is_subtle=True),
                                    _col(p.get("pick_display", ""), "auto"),
                                    _col(str(p.get("model_line", "")), "auto"),
                                    _col(str(p.get("market_line", "")), "auto"),
                                    _col(str(p.get("edge_str", "")), "auto"),
                                    _col(str(p.get("fire_rating", "")), "auto"),
                                ],
                            }
                        )

                    total_picks = len(picks_for_report)
                    shown = min(max_rows, len(picks_for_card))
                    mode = "ALL (raw)" if wants_all else "TOP (deduped)"
                    subtitle = f"{mode} | Total picks: {total_picks} | Showing: {shown}"

                    base = _base_url()
                    html_url = f"{base}/picks/html"

                    card = {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "size": "Large",
                                "weight": "Bolder",
                                "text": f"🏀 NCAAM PICKS - {target_date}",
                                "wrap": True,
                            },
                            {
                                "type": "TextBlock",
                                "text": subtitle,
                                "wrap": True,
                                "isSubtle": True,
                                "size": "Small",
                            },
                            *table_rows,
                        ],
                        "actions": [
                            {
                                "type": "Action.OpenUrl",
                                "title": "📄 View FULL picks (HTML)",
                                "url": html_url,
                            }
                        ],
                    }

                    response = {
                        "type": "message",
                        "attachments": [
                            {
                                "contentType": "application/vnd.microsoft.card.adaptive",
                                "contentUrl": None,
                                "content": card,
                            }
                        ],
                    }
                    
                    # Return immediately to avoid any cleanup errors affecting the response
                    return response
                else:
                    response = {
                        "type": "message",
                        "text": "⚠️ No picks meet minimum edge thresholds for today."
                    }
                    return response
                    
            except ValueError as e:
                # Handle specific value errors (e.g., missing data)
                logger.warning(f"Value error generating picks: {e}")
                response = {
                    "type": "message",
                    "text": f"⚠️ Could not generate picks: {str(e)[:200]}"
                }
                return response
            except (IOError, OSError) as e:
                # Handle file I/O errors (often harmless cleanup issues)
                # These can happen during module import/cleanup
                error_msg = str(e)
                if "closed file" in error_msg.lower() or "i/o operation" in error_msg.lower():
                    # This is a cleanup error - if we have picks, return them
                    logger.warning(f"File I/O cleanup error (suppressed): {e}")
                    if 'all_picks' in locals() and all_picks:
                        # Picks were generated successfully, just return them
                        picks_text = f"🏀 **NCAAM PICKS - {target_date}**\n\n"
                        picks_text += f"Found {len(all_picks)} picks:\n\n"
                        
                        for i, pick in enumerate(all_picks[:10], 1):
                            date_time = f"{pick['date_cst']} {pick['time_cst']}".strip()
                            home_rec = pick.get('home_record', '?')
                            away_rec = pick.get('away_record', '?')
                            matchup = f"{pick['away']} ({away_rec}) vs {pick['home']} ({home_rec})"
                            
                            picks_text += f"**{i}. {date_time}**\n"
                            picks_text += f"   {matchup}\n"
                            picks_text += f"   **Pick:** {pick['pick_display']}\n"
                            picks_text += f"   **Model:** {pick['model_line']} | **Market:** {pick['market_line']}\n"
                            picks_text += f"   **Edge:** {pick['edge_str']} | **Fire:** {pick['fire_rating']} | **{pick['market']}** ({pick['period']})\n\n"
                        
                        if len(all_picks) > 10:
                            picks_text += f"\n... and {len(all_picks) - 10} more picks"
                        
                        response = {
                            "type": "message",
                            "text": picks_text
                        }
                        return response
                else:
                    response = {
                        "type": "message",
                        "text": f"⚠️ Error generating picks: {str(e)[:200]}"
                    }
                return response
            except Exception as e:
                logger.error(f"Error generating picks: {e}", exc_info=True)
                # If we have picks despite the error, return them
                if 'all_picks' in locals() and all_picks:
                    picks_text = f"🏀 **NCAAM PICKS - {target_date}**\n\n"
                    picks_text += f"Found {len(all_picks)} picks:\n\n"
                    
                    for i, pick in enumerate(all_picks[:10], 1):
                        date_time = f"{pick['date_cst']} {pick['time_cst']}".strip()
                        home_rec = pick.get('home_record', '?')
                        away_rec = pick.get('away_record', '?')
                        matchup = f"{pick['away']} ({away_rec}) vs {pick['home']} ({home_rec})"
                        
                        picks_text += f"**{i}. {date_time}**\n"
                        picks_text += f"   {matchup}\n"
                        picks_text += f"   **Pick:** {pick['pick_display']}\n"
                        picks_text += f"   **Model:** {pick['model_line']} | **Market:** {pick['market_line']}\n"
                        picks_text += f"   **Edge:** {pick['edge_str']} | **Fire:** {pick['fire_rating']} | **{pick['market']}** ({pick['period']})\n\n"
                    
                    if len(all_picks) > 10:
                        picks_text += f"\n... and {len(all_picks) - 10} more picks"
                    
                    response = {
                        "type": "message",
                        "text": picks_text
                    }
                else:
                    response = {
                        "type": "message",
                        "text": f"❌ Error generating picks: {str(e)[:200]}"
                    }
                return response
        else:
            # Default response for other messages
            response = {
                "type": "message",
                "text": f"Hi {sender_name}! 👋\n\nTry: 'picks' or 'predict' to get today's betting recommendations."
            }

        return response

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
