from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import subprocess
import logging
import os
from pathlib import Path
from app.predictor import prediction_engine
from app.models import TeamRatings, MarketOdds, Prediction, BettingRecommendation
from app.config import settings

logger = logging.getLogger("api")


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
        )


class MarketOddsInput(BaseModel):
    spread: Optional[float] = None
    spread_price: int = -110
    total: Optional[float] = None
    over_price: int = -110
    under_price: int = -110
    home_ml: Optional[int] = None
    away_ml: Optional[int] = None

    # First half
    spread_1h: Optional[float] = None
    total_1h: Optional[float] = None
    home_ml_1h: Optional[int] = None
    away_ml_1h: Optional[int] = None
    spread_price_1h: Optional[int] = None
    over_price_1h: Optional[int] = None
    under_price_1h: Optional[int] = None

    # Sharp book reference
    sharp_spread: Optional[float] = None
    sharp_total: Optional[float] = None

    def to_domain(self) -> MarketOdds:
        return MarketOdds(
            spread=self.spread,
            spread_price=self.spread_price,
            total=self.total,
            over_price=self.over_price,
            under_price=self.under_price,
            home_ml=self.home_ml,
            away_ml=self.away_ml,
            spread_1h=self.spread_1h,
            total_1h=self.total_1h,
            home_ml_1h=self.home_ml_1h,
            away_ml_1h=self.away_ml_1h,
            spread_price_1h=self.spread_price_1h,
            over_price_1h=self.over_price_1h,
            under_price_1h=self.under_price_1h,
            sharp_spread=self.sharp_spread,
            sharp_total=self.sharp_total,
        )


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
    title="NCAA Prediction Service", 
    version=settings.service_version
)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def trigger_picks(background_tasks: BackgroundTasks):
    """Trigger the daily picks generation process and send to Teams."""
    background_tasks.add_task(run_picks_task)
    return {"message": "Picks generation started in background. Check Teams channel shortly."}


@app.get("/trigger-picks-sync")
async def trigger_picks_sync():
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
    """Serve the latest HTML picks report."""
    html_path = Path("/app/output/latest_picks.html")
    if not html_path.exists():
        return {"error": "No report generated yet. Trigger picks first."}
    return FileResponse(html_path)


@app.get("/health")
async def health():
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "ok",
    }


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


@app.post("/predict", response_model=PredictionResponse)
async def predict(req: PredictRequest):
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


# -----------------------------
# Teams Outgoing Webhook Handler
# -----------------------------

import hmac
import hashlib
import json
from fastapi import Request, HTTPException


class TeamsWebhookMessage(BaseModel):
    """Teams outgoing webhook message structure."""
    text: str
    type: str = "message"
    timestamp: Optional[str] = None
    from_field: Optional[dict] = Field(alias="from", default=None)
    channelData: Optional[dict] = None


@app.post("/teams-webhook")
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
                from app.predictor import prediction_engine
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
                    market_odds_obj = MarketOdds(
                        spread=game.get("spread"),
                        spread_price=game.get("spread_price", -110),
                        total=game.get("total"),
                        over_price=game.get("over_price", -110),
                        under_price=game.get("under_price", -110),
                        home_ml=game.get("home_ml"),
                        away_ml=game.get("away_ml"),
                        spread_1h=game.get("spread_1h"),
                        total_1h=game.get("total_1h"),
                        home_ml_1h=game.get("home_ml_1h"),
                        away_ml_1h=game.get("away_ml_1h"),
                        spread_price_1h=game.get("spread_price_1h"),
                        over_price_1h=game.get("over_price_1h"),
                        under_price_1h=game.get("under_price_1h"),
                        sharp_spread=game.get("sharp_spread"),
                        sharp_total=game.get("sharp_total")
                    )
                    
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
                        # For ML (now in points-equivalent), use spread threshold for consistency
                        if edge_points < min_edge_points:
                            continue
                        
                        # Format pick display with odds
                        pick_val = rec.pick.value if hasattr(rec.pick, 'value') else str(rec.pick)
                        if market == "SPREAD":
                            if pick_val == "HOME":
                                team_name = game["home"]
                                line = game["spread"] if not is_1h else game.get("spread_1h")
                                juice = game.get("spread_home_juice", -110) if not is_1h else game.get("spread_1h_home_juice", -110)
                            else:
                                team_name = game["away"]
                                line = -(game["spread"]) if game["spread"] and not is_1h else (-(game.get("spread_1h")) if game.get("spread_1h") else None)
                                juice = game.get("spread_away_juice", -110) if not is_1h else game.get("spread_1h_away_juice", -110)
                            pick_display = f"{team_name[:20]} {format_spread(line)} ({format_odds(juice)})"
                        elif market == "TOTAL":
                            total_line = game["total"] if not is_1h else game.get("total_1h")
                            if pick_val == "OVER":
                                juice = game.get("over_juice", -110) if not is_1h else game.get("over_1h_juice", -110)
                                pick_display = f"OVER {total_line:.1f} ({format_odds(juice)})"
                            else:
                                juice = game.get("under_juice", -110) if not is_1h else game.get("under_1h_juice", -110)
                                pick_display = f"UNDER {total_line:.1f} ({format_odds(juice)})"
                        else:  # Moneyline
                            if pick_val == "HOME":
                                team_name = game["home"]
                                ml_odds = game["home_ml"] if not is_1h else game.get("home_ml_1h")
                            else:
                                team_name = game["away"]
                                ml_odds = game["away_ml"] if not is_1h else game.get("away_ml_1h")
                            pick_display = f"{team_name[:20]} ML ({format_odds(ml_odds)})"
                        
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
                            if pick_val == "HOME":
                                model_ml = pred.predicted_home_ml if not is_1h else pred.predicted_home_ml_1h
                                prob = pred.home_win_prob if not is_1h else pred.home_win_prob_1h
                            else:
                                model_ml = pred.predicted_away_ml if not is_1h else pred.predicted_away_ml_1h
                                prob = 1 - (pred.home_win_prob if not is_1h else pred.home_win_prob_1h)
                            model_str = f"{format_odds(model_ml)} ({prob*100:.1f}%)" if model_ml is not None else f"{prob*100:.1f}%"
                        
                        # Market line display with juice
                        if market == "SPREAD":
                            mkt_line_home = game["spread"] if not is_1h else game.get("spread_1h")
                            # Show market from PICK perspective (+ for underdog side)
                            mkt_line = mkt_line_home if pick_val == "HOME" else (-mkt_line_home if mkt_line_home is not None else None)
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
                            ml_odds = game["home_ml"] if pick_val == "HOME" and not is_1h else (game.get("home_ml_1h") if pick_val == "HOME" else (game["away_ml"] if not is_1h else game.get("away_ml_1h")))
                            market_str = f"{format_odds(ml_odds)}" if ml_odds is not None else "N/A"
                        
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


# Local run helper
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8082, reload=True)
