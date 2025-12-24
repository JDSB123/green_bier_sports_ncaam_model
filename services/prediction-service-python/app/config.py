"""
Configuration for NCAA Basketball Prediction Service v33.2

v33.2 Changes (2024-12-23):
- MARKET-VALIDATED: Edge thresholds based on 1120-game backtest with real odds
- min_spread_edge set to 7.0 (optimal balance of volume and ROI)
  - 7pt+: 960 bets, 57.8% win rate, +10.4% ROI, z=2.9, p<0.001
  - 10pt+: 845 bets, 59.2% win rate, +13.0% ROI, z=3.94, p<0.0001
- min_total_edge set to 999 (totals not consistently profitable)
- Used 2,088 historical odds from The Odds API (Jan-Apr 2024)
- Used database resolve_team_name() for 99%+ team matching accuracy

v33.1 Changes (2024-12-23):
- CALIBRATED: HCA increased from 3.2 to 4.7 based on 4194-game backtest
- CALIBRATED: Total adjustment -4.6 to fix over-prediction bias
- Validated against 5 seasons of real ESPN game data (2020-2024)

v33.0 Changes:
- Enforce single entry point, consolidated Dockerfiles
- HCA values are now EXPLICIT (what you see is what gets applied)
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class ModelConfig(BaseSettings):
    """Model configuration - MODULAR approach (spreads vs totals optimized separately)."""

    # ─────────────────────────────────────────────────────────────────────────
    # MODULAR HCA - SINGLE SOURCE OF TRUTH (v6.1 - EXPLICIT VALUES)
    # ─────────────────────────────────────────────────────────────────────────
    #
    # These values are applied DIRECTLY to predictions (no hidden multipliers).
    # What you see here is exactly what gets added to spreads/totals.
    #
    # Environment override: MODEL__HOME_COURT_ADVANTAGE_SPREAD=3.5
    # ─────────────────────────────────────────────────────────────────────────

    # SPREAD HCA - Points added to home team advantage
    # CALIBRATED v33.1: Increased from 3.2 to 4.7 based on 4194-game backtest
    # Bias was -1.86 (underestimating home), optimal HCA = 4.66
    home_court_advantage_spread: float = Field(
        default=4.7,
        description="Points added for home court in spread calc. Calibrated from 4194 games."
    )
    home_court_advantage_spread_1h: float = Field(
        default=2.35,
        description="1H spread HCA (50% of 4.7). Calibrated proportionally."
    )

    # TOTAL HCA - Points added to total score prediction
    # Standard efficiency models assume HCA is zero-sum for totals (Home scores more, Away scores less)
    home_court_advantage_total: float = Field(
        default=0.0,
        description="Points added to total prediction. Default 0.0 (zero-sum assumption)."
    )
    home_court_advantage_total_1h: float = Field(
        default=0.0,
        description="1H total HCA. Standard is 0.0."
    )

    # TOTAL CALIBRATION ADJUSTMENT
    # CALIBRATED v33.1: Model was over-predicting totals by ~4 points
    # Based on 4194-game backtest, optimal adjustment is -4.6
    total_calibration_adjustment: float = Field(
        default=-4.6,
        description="Points subtracted from total prediction. Calibrated from 4194 games."
    )
    total_calibration_adjustment_1h: float = Field(
        default=-2.3,
        description="1H total calibration (50% of full game adjustment)."
    )

    # League averages (REQUIRED for correct Tempo/Efficiency formulas)
    # Formula: Expected = TeamA + TeamB - LeagueAvg
    league_avg_tempo: float = Field(
        default=68.5,
        description="NCAA D1 average possessions per 40 minutes."
    )
    league_avg_efficiency: float = Field(
        default=106.0,
        description="NCAA D1 average efficiency (points per 100 possessions)."
    )
    league_avg_orb: float = Field(
        default=28.0,
        description="NCAA D1 average Offensive Rebound %."
    )
    league_avg_tor: float = Field(
        default=18.5,
        description="NCAA D1 average Turnover Rate."
    )
    league_avg_ftr: float = Field(
        default=33.0,
        description="NCAA D1 average Free Throw Rate (FTA/FGA)."
    )
    league_avg_3pr: float = Field(
        default=35.0,
        description="NCAA D1 average 3-Point Rate (% of FGA)."
    )

    # ──────────────────────────────────────────────────────────────────────────────
    # MATCHUP ADJUSTMENT FACTORS (Points per % edge)
    # ──────────────────────────────────────────────────────────────────────────────
    matchup_rebound_factor: float = Field(
        default=0.15,
        description="Points added to margin per 1% net rebounding edge."
    )
    matchup_turnover_factor: float = Field(
        default=0.10,
        description="Points added to margin per 1% net turnover edge."
    )
    matchup_ft_factor: float = Field(
        default=0.15,
        description="Points added to margin per 1% net free throw rate edge."
    )

    # First half scoring factors
    first_half_score_factor: float = Field(
        default=0.50,
        description="First half scoring share; nudged to 50% to remove observed underestimation and improve 1H CLV."
    )
    first_half_pace_factor: float = Field(
        default=0.50,
        description="First half pace share; aligned to 50% to match calibrated scoring split and tighten 1H line estimates."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # BETTING EDGE THRESHOLDS (MARKET-VALIDATED v33.1)
    # ─────────────────────────────────────────────────────────────────────────
    # Based on backtesting 574 games with real The Odds API data (Jan-Apr 2024):
    # - Spread edges < 15 pts: ~50% win rate (no edge)
    # - Spread edges >= 15 pts: 60.3% win rate, +15.2% ROI (profitable)
    # - Total betting: 48.1% win rate (unprofitable at all edge levels)
    # ─────────────────────────────────────────────────────────────────────────

    # Minimum edge to recommend a spread bet (in points)
    # MARKET-VALIDATED: 7+ pt edges show 57.8% win rate, +10.4% ROI (z=2.9, p<0.001)
    # Higher thresholds yield higher ROI but fewer bets:
    #   10pt: 59.2%, +13% | 15pt: ~60%, +15% (small sample)
    min_spread_edge: float = Field(
        default=7.0,
        description="Min spread edge to bet. 7pt = optimal volume/ROI balance."
    )
    # Minimum edge to recommend a total bet (in points)
    # DISABLED: Total betting was unprofitable in backtesting (48.1% win rate)
    # Set to 999 to effectively disable total bet recommendations
    min_total_edge: float = Field(
        default=999.0,
        description="Min total edge to bet. Set to 999 to disable (unprofitable in backtest)."
    )

    # Minimum confidence threshold
    min_confidence: float = Field(
        default=0.65,
        description="Minimum confidence to recommend bet. Higher than v4.0's 0.60."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # SHARP BOOK HANDLING
    # ─────────────────────────────────────────────────────────────────────────

    sharp_books: list[str] = Field(
        default=["pinnacle", "circa", "bookmaker"],
        description="Sharp bookmakers to use as benchmark."
    )

    @field_validator('sharp_books', mode='before')
    @classmethod
    def parse_sharp_books(cls, v):
        """Parse comma-separated string to list."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(',') if s.strip()]
        return v

    # If betting against sharp line movement, reduce confidence
    against_sharp_penalty: float = Field(
        default=0.15,
        description="Confidence penalty when betting against sharp movement."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # KELLY CRITERION
    # ─────────────────────────────────────────────────────────────────────────

    kelly_fraction: float = Field(
        default=0.25,
        description="Fractional Kelly (25% of full Kelly for safety)."
    )
    max_bet_units: float = Field(
        default=3.0,
        description="Maximum bet size in units."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # SITUATIONAL ADJUSTMENTS (Rest Days, Back-to-Back)
    # ─────────────────────────────────────────────────────────────────────────

    situational_enabled: bool = Field(
        default=True,
        description="Enable rest/B2B situational adjustments."
    )
    b2b_penalty: float = Field(
        default=-2.25,
        description="Point penalty for back-to-back games."
    )
    one_day_rest_penalty: float = Field(
        default=-1.25,
        description="Point penalty for 1 day of rest."
    )
    rest_differential_factor: float = Field(
        default=0.5,
        description="Points per day of rest advantage."
    )
    max_rest_differential_adj: float = Field(
        default=2.0,
        description="Maximum rest differential adjustment."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # DYNAMIC VARIANCE (Game-Specific Sigma)
    # ─────────────────────────────────────────────────────────────────────────

    dynamic_variance_enabled: bool = Field(
        default=True,
        description="Enable dynamic variance based on shooting style."
    )
    base_sigma: float = Field(
        default=11.0,
        description="Base sigma for spread-to-probability conversion."
    )
    three_pt_variance_factor: float = Field(
        default=0.15,
        description="Variance adjustment per % above/below avg 3PR."
    )
    pace_variance_factor: float = Field(
        default=0.10,
        description="Variance adjustment per tempo differential point."
    )
    min_sigma: float = Field(
        default=9.0,
        description="Minimum allowed sigma."
    )
    max_sigma: float = Field(
        default=14.0,
        description="Maximum allowed sigma."
    )
    variance_1h_multiplier: float = Field(
        default=1.15,
        description="Multiplier for 1H variance vs full game."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # ENHANCED FIRST HALF PREDICTIONS
    # ─────────────────────────────────────────────────────────────────────────

    enhanced_1h_enabled: bool = Field(
        default=True,
        description="Enable dynamic 1H factor adjustments."
    )
    first_half_base_tempo_factor: float = Field(
        default=0.48,
        description="Base tempo factor for 1H predictions."
    )
    first_half_base_margin_scale: float = Field(
        default=0.50,
        description="Base margin scale for 1H predictions."
    )
    efg_tempo_adjustment: float = Field(
        default=0.005,
        description="Tempo adjustment per % EFG above average."
    )
    efg_margin_adjustment: float = Field(
        default=0.01,
        description="Margin adjustment per % EFG differential."
    )

    class Config:
        # Note: env_prefix removed - use parent's env_nested_delimiter instead
        pass


class Settings(BaseSettings):
    """Application settings."""

    # Service
    service_name: str = "prediction-service"
    service_version: str = "33.2.0"  # Market-validated edge thresholds
    debug: bool = False

    # Feature Store
    feature_store_url: str = Field(
        default="http://localhost:8081",
        description="Feature store service URL."
    )

    # Model config
    model: ModelConfig = Field(default_factory=ModelConfig)

    class Config:
        # NO .env file - all configuration from environment variables set by docker-compose
        env_nested_delimiter = "__"


# Global settings instance
settings = Settings()
