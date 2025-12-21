from datetime import datetime
from typing import Optional, List
from uuid import UUID
import subprocess
import logging
import os
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

logger = logging.getLogger(__name__)


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


@app.post("/api/sync/ratings")
async def sync_ratings_manual():
    """
    Manually trigger the ratings sync from Barttorvik.
    Runs the embedded ratings-sync Go binary with RUN_ONCE mode.
    """
    try:
        logger.info("Triggering manual ratings sync...")
        result = subprocess.run(
            ["/app/ratings-sync"],
            env={**dict(os.environ), "RUN_ONCE": "true"},
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        if result.returncode != 0:
            logger.error(f"Sync failed: {result.stderr}")
            return {
                "status": "error",
                "message": "Ratings sync failed",
                "stderr": result.stderr[-500:],  # Last 500 chars
            }
        
        logger.info("Manual ratings sync completed successfully")
        return {
            "status": "success",
            "message": "Ratings sync completed",
            "stdout": result.stdout[-500:],  # Last 500 chars
        }
    except subprocess.TimeoutExpired:
        logger.error("Sync timed out after 300 seconds")
        return {
            "status": "error",
            "message": "Ratings sync timed out (5 min limit)",
        }
    except Exception as e:
        logger.error(f"Sync execution error: {e}")
        return {
            "status": "error",
            "message": f"Sync execution failed: {str(e)}",
        }



# Local run helper
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8082, reload=True)
