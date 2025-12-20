"""FastAPI application for NCAAF ML prediction service."""
from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import JSONResponse

from src.api.metrics import metrics_handler, update_system_uptime
from src.api.models import (
    HealthResponse,
    ServiceInfo,
    TeamsResponse,
    GamesResponse,
    PredictionsResponse,
    ErrorResponse,
)
from src.api.routes import backtest
from src.config.settings import settings
from src.db.database import (
    Database,
    close_db,
    fetch_games_by_week,
    fetch_latest_odds,
    fetch_teams,
    init_db,
    save_prediction,
)
from src.services.prediction_service import PredictionService
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances
db_instance = None
prediction_service = None  # Single source of truth - used by both CLI and API
start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global db_instance, prediction_service, start_time

    # Startup
    logger.info("Starting ML Service...")
    start_time = time.time()
    init_db()

    # Initialize database instance
    db_instance = Database()
    db_instance.connect()
    logger.info("Database connection initialized")

    # Initialize prediction service (single source of truth)
    # This service handles all prediction logic - both CLI and API use it
    try:
        prediction_service = PredictionService(
            db=db_instance,
            model_dir=settings.model_path
        )
        logger.info(f"Prediction service initialized (single source of truth) from {settings.model_path}")
    except Exception as e:
        logger.warning(f"Failed to initialize prediction service: {e}")
        logger.warning("Service will start but predictions will fail until models are trained")
        prediction_service = None

    logger.info("ML Service startup complete")

    yield

    # Shutdown
    logger.info("Shutting down ML Service...")
    close_db()
    if db_instance:
        db_instance.close()
    logger.info("ML Service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="NCAAF v5.0 ML Service",
    description="""
    Machine Learning prediction service for NCAA Football (NCAAF) betting analysis.

    ## Features

    * **Game Predictions**: XGBoost-based predictions for margin, total, and team scores
    * **Edge Calculation**: Compare model predictions against market consensus
    * **Betting Recommendations**: Kelly-inspired unit sizing based on edge and confidence
    * **Feature Engineering**: 40+ features including efficiency metrics, QB stats, recent form
    * **Real-time Data**: Integration with SportsDataIO for live odds and game data

    ## Endpoints

    * `/api/v1/teams` - Get all teams
    * `/api/v1/games/week/{season}/{week}` - Get games for a specific week
    * `/api/v1/predictions/week/{season}/{week}` - Generate predictions for a week
    * `/health` - Service health check
    * `/metrics` - Prometheus metrics

    ## Data Flow

    1. Game data ingested via Go ingestion service
    2. Features extracted from historical stats
    3. XGBoost models generate predictions
    4. Edge calculated vs market consensus
    5. Betting recommendations provided based on edge and confidence
    """,
    version="5.0.0-beta",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "predictions",
            "description": "ML predictions and betting recommendations",
        },
        {
            "name": "data",
            "description": "Access to teams and games data",
        },
        {
            "name": "Backtesting",
            "description": "Backtest betting strategies across different bet types and game periods",
        },
        {
            "name": "system",
            "description": "Health checks and monitoring",
        },
    ],
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
        503: {
            "model": ErrorResponse,
            "description": "Service unavailable (models not loaded)",
        },
    },
)

# Include routers
app.include_router(backtest.router, prefix="/api/v1")


@app.get(
    "/",
    response_model=ServiceInfo,
    tags=["system"],
    summary="Service information",
    description="Get basic information about the ML service",
)
async def root():
    """Root endpoint providing service information."""
    return {
        "service": "NCAAF v5.0 ML Service",
        "version": "5.0.0-beta",
        "status": "operational",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Health check",
    description="Check if the service is healthy and operational",
)
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    # Update system uptime metric
    update_system_uptime(time.time() - start_time)

    return {
        "status": "healthy",
        "environment": settings.app_env,
    }


@app.get(
    "/metrics",
    tags=["system"],
    summary="Prometheus metrics",
    description="Endpoint for Prometheus to scrape metrics",
    include_in_schema=False,  # Hide from OpenAPI docs
)
async def metrics():
    """Prometheus metrics endpoint."""
    update_system_uptime(time.time() - start_time)
    return metrics_handler()


@app.get(
    "/api/v1/teams",
    response_model=TeamsResponse,
    tags=["data"],
    summary="Get all teams",
    description="Retrieve all NCAA Football teams in the database",
)
async def get_teams():
    """
    Get all teams.

    Returns:
        List of teams with their information
    """
    try:
        teams = fetch_teams()
        return {
            "count": len(teams),
            "teams": teams,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/games/week/{season}/{week}",
    response_model=GamesResponse,
    tags=["data"],
    summary="Get games by week",
    description="Retrieve all games for a specific season and week",
)
async def get_games_by_week(
    season: int = Path(..., description="Season year", example=2024, ge=2020),
    week: int = Path(..., description="Week number", example=15, ge=1, le=17),
):
    """
    Get games for a specific week.

    Returns all scheduled, in-progress, and completed games for the specified
    season and week number.
    """
    try:
        games = fetch_games_by_week(season, week)
        return {
            "season": season,
            "week": week,
            "count": len(games),
            "games": games,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/predictions/week/{season}/{week}",
    response_model=PredictionsResponse,
    tags=["predictions"],
    summary="Generate weekly predictions",
    description="Generate ML predictions and betting recommendations for all games in a week",
    responses={
        503: {
            "model": ErrorResponse,
            "description": "ML models not loaded",
        },
    },
)
async def get_predictions_for_week(
    season: int = Path(..., description="Season year", example=2024, ge=2020),
    week: int = Path(..., description="Week number", example=15, ge=1, le=17),
):
    """
    Generate predictions for all games in a week.

    Uses PredictionService (single source of truth) for all prediction logic.
    This endpoint only handles HTTP request/response formatting.

    Returns predictions with confidence scores and recommended bet sizes (0-2 units).
    """
    if not prediction_service:
        raise HTTPException(
            status_code=503,
            detail=(
                "ML models not loaded. Please train models first using: "
                "docker compose run --rm ml_service python main.py train"
            )
        )

    try:
        # Use shared prediction service (single source of truth)
        predictions = prediction_service.generate_predictions_for_week(
            season=season,
            week=week,
            save_to_db=True  # Persist to database
        )

        if not predictions:
            return {
                "season": season,
                "week": week,
                "count": 0,
                "predictions": [],
                "message": "No games found for this week",
            }

        # Filter recommended bets
        recommendations = [
            p for p in predictions
            if p.get('recommend_bet', False)
        ]

        return {
            "season": season,
            "week": week,
            "count": len(predictions),
            "predictions": predictions,
            "recommendations": recommendations,
        }

    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Prediction service error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: {e}"
        )
    except Exception as e:
        logger.error(f"Prediction generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/models/train")
async def train_models():
    """
    Trigger model training.

    This endpoint would:
    1. Load historical game data from database
    2. Extract features
    3. Train XGBoost models for spread and total
    4. Save models to disk
    5. Update model metadata in database

    Returns:
        Training results and metrics
    """
    return JSONResponse(
        status_code=501,
        content={
            "error": "Training endpoint not yet implemented",
            "message": "Use scripts/train_xgboost.py for now",
        },
    )


@app.post("/api/v1/backtest")
async def run_backtest(season: int, start_week: int = 1, end_week: int = 15):
    """
    Run backtest on historical data.

    Args:
        season: Season to backtest
        start_week: Starting week
        end_week: Ending week

    Returns:
        Backtest results with ROI, accuracy, and metrics
    """
    return JSONResponse(
        status_code=501,
        content={
            "error": "Backtest endpoint not yet implemented",
            "message": "Use scripts/backtest.py for now",
        },
    )


@app.get("/api/v1/stats")
async def get_service_stats():
    """
    Get service statistics.

    Returns:
        Service stats like number of predictions, model performance, etc.
    """
    try:
        # For now, just return basic stats
        teams = fetch_teams()

        return {
            "teams_count": len(teams),
            "models_loaded": prediction_service is not None and prediction_service.predictor is not None,
            "status": "operational",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ModelStatusResponse(BaseModel):
    """Response model for model status endpoint."""
    models_loaded: bool
    loaded_models: dict
    model_dir: str
    version: str = "v1"


@app.get(
    "/api/v1/models/status",
    response_model=ModelStatusResponse,
    tags=["system"],
    summary="Model status",
    description="Get status and version of loaded ML models."
)
async def model_status():
    """Report which models are loaded and their version."""
    if prediction_service is None or prediction_service.predictor is None:
        return ModelStatusResponse(
            models_loaded=False,
            loaded_models={},
            model_dir="",
            version="v1"
        )
    
    predictor = prediction_service.predictor
    loaded = {k: v is not None for k, v in getattr(predictor, 'models', {}).items()}
    
    return ModelStatusResponse(
        models_loaded=all(loaded.values()),
        loaded_models=loaded,
        model_dir=str(getattr(predictor, 'model_dir', '')),
        version="v1"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=settings.ml_service_port,
        reload=settings.is_development,
    )
