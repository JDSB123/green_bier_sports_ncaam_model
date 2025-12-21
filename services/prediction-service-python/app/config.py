"""
Configuration for NCAA Basketball Prediction Service v6.3

v6.3 Changes:
- HCA values are now EXPLICIT (what you see is what gets applied)
- Removed hidden multipliers from predictor.py
- Synced with corrected total/spread formulas

Key differences from v4.0:
- Simplified formulas (no interaction terms)
- No mismatch amplification
- Stricter edge thresholds
- CLV-first validation approach
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
    # Backtest Results (2024-12-17):
    #   - Spreads with HCA=3.0: 16.57% ROI
    #   - Totals with HCA=0.9: 34.10% ROI (was "4.5 * 0.2" internally)
    #   - Combined: 25.64% ROI
    #
    # Environment override: MODEL__HOME_COURT_ADVANTAGE_SPREAD=3.5
    # ─────────────────────────────────────────────────────────────────────────

    # SPREAD HCA - Points added to home team advantage
    # Standard Barttorvik/KenPom value is ~3.2 points
    home_court_advantage_spread: float = Field(
        default=3.2,
        description="Points added for home court in spread calc. Applied directly."
    )
    home_court_advantage_spread_1h: float = Field(
        default=1.6,
        description="1H spread HCA (50% of full game). Applied directly."
    )

    # TOTAL HCA - Points added to total score prediction
    # Standard efficiency models assume HCA is zero-sum for totals (Home scores more, Away scores less)
    home_court_advantage_total: float = Field(
        default=0.9,
        description="Points added to total prediction. Backtested optimal: 0.9 (34.10% ROI)."
    )
    home_court_advantage_total_1h: float = Field(
        default=0.0,
        description="1H total HCA. Standard is 0.0."
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
    # BETTING EDGE THRESHOLDS
    # ─────────────────────────────────────────────────────────────────────────

    # Minimum edge to recommend a bet (in points)
    min_spread_edge: float = Field(
        default=2.5,
        description="Minimum spread edge to recommend bet. Higher than v4.0's 2.0 for selectivity."
    )
    min_total_edge: float = Field(
        default=3.0,
        description="Minimum total edge to recommend bet."
    )

    # Minimum confidence threshold
    min_confidence: float = Field(
        default=0.65,
        description="Minimum confidence to recommend bet. Higher than v4.0's 0.60."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # MONEYLINE CONVERSION
    # ─────────────────────────────────────────────────────────────────────────

    # Pythagorean exponent for win probability
    pythagorean_exponent: float = Field(
        default=11.5,
        description="Exponent for Pythagorean win probability. Calibrated for NCAAB."
    )

    # Spread to moneyline conversion sigma
    spread_to_ml_sigma: float = Field(
        default=11.0,
        description="Standard deviation for spread-to-win-probability conversion."
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
    service_version: str = "6.3.0"
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
