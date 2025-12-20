"""
Configuration for NCAA Basketball Prediction Service v6.0

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
    # MODULAR HCA - SINGLE SOURCE OF TRUTH
    # ─────────────────────────────────────────────────────────────────────────
    # 
    # Backtest Results (2024-12-17):
    #   - Spreads with HCA=3.0: 16.57% ROI
    #   - Totals with HCA=4.5: 34.10% ROI
    #   - Combined: 25.64% ROI
    #
    # These are loaded via MODEL__<NAME> environment variables
    # ─────────────────────────────────────────────────────────────────────────

    # SPREAD-specific HCA (lower is better for spreads)
    home_court_advantage_spread: float = Field(
        default=3.0,
        description="HCA for spread predictions. Optimized: 3.0 = 16.57% ROI."
    )
    home_court_advantage_spread_1h: float = Field(
        default=1.5,
        description="First half HCA for spreads (50% of full game)."
    )

    # TOTAL-specific HCA (higher is better for totals)
    home_court_advantage_total: float = Field(
        default=4.5,
        description="HCA for total predictions. Optimized: 4.5 = 34.10% ROI."
    )
    home_court_advantage_total_1h: float = Field(
        default=2.25,
        description="First half HCA base value for totals. NOTE: Multiplied by 0.1 in formula for ~0.2 pts actual impact."
    )

    # Legacy single HCA (deprecated, use spread/total specific)
    home_court_advantage: float = Field(
        default=3.0,
        description="DEPRECATED: Use home_court_advantage_spread/total instead."
    )
    home_court_advantage_1h: float = Field(
        default=1.5,
        description="DEPRECATED: Use spread/total specific values."
    )

    # League averages (reference values only - not used in prediction formula)
    # The prediction formula uses 100 as a mathematical constant, NOT as D1 average
    league_avg_tempo: float = Field(
        default=68.0,
        description="NCAA D1 average possessions per 40 minutes (reference only)."
    )
    league_avg_efficiency: float = Field(
        default=100.0,
        description="Reference value only. Prediction formula uses 100 as constant."
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

    class Config:
        # Note: env_prefix removed - use parent's env_nested_delimiter instead
        pass


class Settings(BaseSettings):
    """Application settings."""

    # Service
    service_name: str = "prediction-service"
    service_version: str = "6.0.0"
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
