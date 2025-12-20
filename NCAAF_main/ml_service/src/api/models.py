"""
Pydantic models for API request/response validation and OpenAPI documentation
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, date
from decimal import Decimal


# Team Models
class Team(BaseModel):
    """Team information"""
    id: int = Field(..., description="Internal database ID")
    team_id: int = Field(..., description="SportsDataIO team ID")
    team_code: str = Field(..., description="Team abbreviation code", example="ALA")
    school_name: str = Field(..., description="Full school name", example="Alabama")
    mascot: Optional[str] = Field(None, description="Team mascot", example="Crimson Tide")
    conference: Optional[str] = Field(None, description="Conference name", example="SEC")
    division: Optional[str] = Field(None, description="Division", example="FBS")
    talent_composite: Optional[float] = Field(None, description="247Sports talent composite score", example=95.8)

    class Config:
        from_attributes = True


class TeamsResponse(BaseModel):
    """List of teams response"""
    teams: List[Team]
    count: int = Field(..., description="Total number of teams returned")


# Game Models
class Game(BaseModel):
    """Game information"""
    id: int = Field(..., description="Internal database ID")
    game_id: int = Field(..., description="SportsDataIO game ID")
    season: int = Field(..., description="Season year", example=2024)
    week: Optional[int] = Field(None, description="Week number", example=15)
    home_team_id: int = Field(..., description="Home team database ID")
    away_team_id: int = Field(..., description="Away team database ID")
    game_date: Optional[datetime] = Field(None, description="Game date and time")
    status: str = Field(..., description="Game status", example="Scheduled")
    home_score: Optional[int] = Field(None, description="Home team score")
    away_score: Optional[int] = Field(None, description="Away team score")
    total_score: Optional[int] = Field(None, description="Total combined score")
    margin: Optional[int] = Field(None, description="Margin of victory (home - away)")

    class Config:
        from_attributes = True


class GamesResponse(BaseModel):
    """List of games response"""
    games: List[Game]
    count: int = Field(..., description="Total number of games returned")


# Prediction Models
class BettingRecommendation(BaseModel):
    """Betting recommendation"""
    recommend_bet: bool = Field(..., description="Whether to recommend this bet")
    bet_type: Optional[str] = Field(None, description="Type of bet", example="spread")
    bet_side: Optional[str] = Field(None, description="Which side to bet", example="home")
    recommended_units: float = Field(0.0, description="Recommended bet size in units (0-2)", example=1.5)
    reasoning: Optional[str] = Field(None, description="Explanation for recommendation")


class Prediction(BaseModel):
    """ML prediction for a game"""
    game_id: int = Field(..., description="SportsDataIO game ID")
    model_name: str = Field(..., description="Model identifier", example="xgboost_v1")

    # Predictions
    predicted_margin: float = Field(..., description="Predicted margin (home - away)", example=7.5)
    predicted_total: float = Field(..., description="Predicted total score", example=52.0)
    predicted_home_score: float = Field(..., description="Predicted home team score", example=29.75)
    predicted_away_score: float = Field(..., description="Predicted away team score", example=22.25)

    # Market data
    consensus_spread: Optional[float] = Field(None, description="Market consensus spread", example=-7.0)
    consensus_total: Optional[float] = Field(None, description="Market consensus total", example=51.5)

    # Edge calculation
    edge_spread: float = Field(..., description="Edge vs market on spread", example=0.5)
    edge_total: float = Field(..., description="Edge vs market on total", example=0.5)

    # Confidence
    confidence: float = Field(..., description="Model confidence score (0-1)", ge=0.0, le=1.0, example=0.72)

    # Recommendation
    recommendation: Optional[BettingRecommendation] = Field(None, description="Betting recommendation")

    # Metadata
    created_at: Optional[datetime] = Field(None, description="Prediction timestamp")

    class Config:
        from_attributes = True


class PredictionsResponse(BaseModel):
    """List of predictions response"""
    predictions: List[Prediction]
    count: int = Field(..., description="Total number of predictions returned")
    season: int = Field(..., description="Season year")
    week: int = Field(..., description="Week number")


class PredictionRequest(BaseModel):
    """Request to generate a prediction"""
    game_id: int = Field(..., description="SportsDataIO game ID", example=12345)
    force_refresh: bool = Field(False, description="Force regeneration even if cached prediction exists")


# Health Check Models
class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service health status", example="healthy")
    environment: str = Field(..., description="Environment name", example="production")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")


class ServiceInfo(BaseModel):
    """Service information"""
    service: str = Field(..., description="Service name", example="NCAAF v5.0 ML Service")
    version: str = Field(..., description="Service version", example="5.0.0-beta")
    status: str = Field(..., description="Operational status", example="operational")


# Feature Extraction Models
class FeatureSet(BaseModel):
    """Extracted features for a game matchup"""
    home_team_id: int = Field(..., description="Home team ID")
    away_team_id: int = Field(..., description="Away team ID")
    season: int = Field(..., description="Season year")
    week: int = Field(..., description="Week number")
    features: Dict[str, float] = Field(..., description="Feature dictionary")
    feature_count: int = Field(..., description="Number of features extracted")


# Error Models
class ErrorResponse(BaseModel):
    """Error response"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    status_code: int = Field(..., description="HTTP status code")


# Statistics Models
class ModelStatistics(BaseModel):
    """ML model statistics"""
    model_name: str = Field(..., description="Model identifier")
    total_predictions: int = Field(..., description="Total predictions made")
    average_confidence: float = Field(..., description="Average confidence score")
    predictions_with_edge: int = Field(..., description="Predictions with betting edge")
    recommended_bets: int = Field(..., description="Total recommended bets")


class SystemStatistics(BaseModel):
    """System statistics"""
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    total_teams: int = Field(..., description="Total teams in database")
    total_games: int = Field(..., description="Total games in database")
    total_predictions: int = Field(..., description="Total predictions generated")
    cache_hit_rate: float = Field(..., description="Cache hit rate percentage", ge=0.0, le=100.0)


# Backtest Models
class BacktestRequest(BaseModel):
    """Request to create and run a backtest"""
    name: str = Field(..., description="Backtest name", example="2024 Season Spread Backtest")
    description: Optional[str] = Field(None, description="Backtest description")
    start_date: date = Field(..., description="Start date for backtest period", example="2024-09-01")
    end_date: date = Field(..., description="End date for backtest period", example="2024-12-31")
    bet_types: List[str] = Field(..., description="Bet types to test", example=["spread", "moneyline", "total"])
    game_periods: List[str] = Field(..., description="Game periods to test", example=["1Q", "1H", "full"])
    min_confidence: float = Field(0.0, description="Minimum confidence threshold", ge=0.0, le=1.0, example=0.6)
    max_risk: float = Field(100.0, description="Maximum risk per bet in dollars", gt=0, example=100.0)
    unit_size: float = Field(100.0, description="Standard bet unit size in dollars", gt=0, example=100.0)


class BetResultDetail(BaseModel):
    """Individual bet result"""
    game_id: int = Field(..., description="Game ID")
    game_date: date = Field(..., description="Game date")
    home_team_id: int = Field(..., description="Home team ID")
    away_team_id: int = Field(..., description="Away team ID")
    bet_type: str = Field(..., description="Type of bet", example="spread")
    game_period: str = Field(..., description="Game period", example="full")
    bet_side: str = Field(..., description="Bet side", example="home")
    predicted_value: Optional[float] = Field(None, description="Predicted value")
    confidence: float = Field(..., description="Prediction confidence")
    edge: float = Field(..., description="Calculated edge")
    odds_line: Optional[float] = Field(None, description="Odds line")
    odds_price: int = Field(..., description="American odds", example=-110)
    wager_amount: float = Field(..., description="Bet amount in dollars")
    actual_result: float = Field(..., description="Actual result")
    outcome: str = Field(..., description="Bet outcome", example="win")
    payout: float = Field(..., description="Total payout")
    profit: float = Field(..., description="Net profit/loss")


class BacktestPeriodBreakdown(BaseModel):
    """Breakdown of results by game period"""
    period: str = Field(..., description="Game period", example="full")
    total_bets: int = Field(..., description="Total bets for this period")
    wins: int = Field(..., description="Winning bets")
    losses: int = Field(..., description="Losing bets")
    pushes: int = Field(..., description="Push bets")
    total_wagered: float = Field(..., description="Total amount wagered")
    total_returned: float = Field(..., description="Total amount returned")
    net_profit: float = Field(..., description="Net profit/loss")
    roi: float = Field(..., description="Return on investment")
    win_rate: float = Field(..., description="Win rate percentage", ge=0.0, le=1.0)


class BacktestBetTypeBreakdown(BaseModel):
    """Breakdown of results by bet type"""
    bet_type: str = Field(..., description="Bet type", example="spread")
    total_bets: int = Field(..., description="Total bets for this type")
    wins: int = Field(..., description="Winning bets")
    losses: int = Field(..., description="Losing bets")
    pushes: int = Field(..., description="Push bets")
    total_wagered: float = Field(..., description="Total amount wagered")
    total_returned: float = Field(..., description="Total amount returned")
    net_profit: float = Field(..., description="Net profit/loss")
    roi: float = Field(..., description="Return on investment")
    win_rate: float = Field(..., description="Win rate percentage", ge=0.0, le=1.0)
    avg_edge: float = Field(..., description="Average edge per bet")


class BacktestSummary(BaseModel):
    """Summary statistics for a backtest"""
    total_bets: int = Field(..., description="Total bets placed")
    total_won: int = Field(..., description="Total winning bets")
    total_lost: int = Field(..., description="Total losing bets")
    total_push: int = Field(..., description="Total push bets")
    total_wagered: float = Field(..., description="Total amount wagered")
    total_returned: float = Field(..., description="Total amount returned")
    net_profit: float = Field(..., description="Net profit/loss")
    roi: float = Field(..., description="Overall return on investment")
    win_rate: float = Field(..., description="Overall win rate", ge=0.0, le=1.0)
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio of returns")
    max_drawdown: Optional[float] = Field(None, description="Maximum drawdown")
    avg_odds: Optional[float] = Field(None, description="Average odds price")
    breakdowns_by_period: List[BacktestPeriodBreakdown] = Field(default_factory=list, description="Results by game period")
    breakdowns_by_type: List[BacktestBetTypeBreakdown] = Field(default_factory=list, description="Results by bet type")


class BacktestResponse(BaseModel):
    """Complete backtest response"""
    id: int = Field(..., description="Backtest ID")
    name: str = Field(..., description="Backtest name")
    description: Optional[str] = Field(None, description="Backtest description")
    status: str = Field(..., description="Backtest status", example="completed")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    bet_types: List[str] = Field(..., description="Bet types tested")
    game_periods: List[str] = Field(..., description="Game periods tested")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    summary: BacktestSummary = Field(..., description="Summary statistics")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class BacktestListItem(BaseModel):
    """Backtest list item (summary only)"""
    id: int = Field(..., description="Backtest ID")
    name: str = Field(..., description="Backtest name")
    status: str = Field(..., description="Backtest status")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    total_bets: int = Field(..., description="Total bets")
    net_profit: float = Field(..., description="Net profit/loss")
    roi: float = Field(..., description="ROI")
    win_rate: float = Field(..., description="Win rate")
    created_at: datetime = Field(..., description="Creation timestamp")


class BacktestListResponse(BaseModel):
    """List of backtests"""
    backtests: List[BacktestListItem]
    count: int = Field(..., description="Total count")


class BacktestDetailResponse(BaseModel):
    """Detailed backtest results including individual bets"""
    backtest: BacktestResponse
    results: List[BetResultDetail] = Field(..., description="Individual bet results")
    results_count: int = Field(..., description="Number of results returned")
