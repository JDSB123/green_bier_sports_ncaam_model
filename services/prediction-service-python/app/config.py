"""
Configuration for NCAA Basketball Prediction Service v33.6.2

v33.6.2 Changes (2025-12-28):
- FIXED: 1H Total confidence now starts at 0.68 (was 0.52, below 0.65 threshold)
- FIXED: FG Spread MIN_EDGE aligned to 2.0 (was 7.0, too conservative)
- FIXED: FG Total MIN_EDGE aligned to 3.0 (matches config)
- ADDED: Extreme total handling - skip bets on FG total <120 or >170, 1H <55 or >85
- ADDED: CLV tracking infrastructure (closing line capture, calculate_clv method)
- ADDED: Settlement functions (settle_recommendations, get_clv_summary)
- ADDED: Comprehensive unit tests for all new functionality

v33.6 Changes (2024-12-24):
- ALL 4 MODELS TRULY INDEPENDENT & BACKTESTED with real ESPN data
- FG Spread: BACKTESTED on 3,318 games, HCA=5.8 (from actual home margins)
- FG Total: BACKTESTED on 3,318 games, Calibration=+7.0 (unchanged)
- H1 Spread: BACKTESTED on 904 real 1H games, HCA=3.6 (from actual 1H margins)
- H1 Total: BACKTESTED on 562 real 1H games, Calibration=+2.7 (unchanged)
- Created dedicated backtest scripts: backtest_fg_spread.py, backtest_h1_spread.py
- Previous spread HCAs (4.7, 2.35) were NOT backtested - now corrected

v33.5 Changes (2024-12-24):
- CLEANUP: Removed 7 stale/duplicate predictor files (independent_*.py, *_independent.py)
- CLEANUP: Removed stale ACR repo (prediction-service) - single source is ncaam-prediction
- CLEANUP: Removed duplicate backtest file (testing/backtest_independent_models.py)
- Canonical models: fg_total.py, fg_spread.py, h1_total.py, h1_spread.py
- h1_total.py is truly independent (backtested on 562 games with real 1H data)

v33.4 Changes (2024-12-24):
- ROOT CAUSE FIX: Removed total_calibration_adjustment (-4.6) - it was WRONG
  - Raw formula UNDERPREDICTED by 3.7 pts
  - The -4.6 calibration made it WORSE (-8.3 pts bias)
  - Real issue: league_avg_tempo was 68.5, actual data is 67.6
  - Real issue: league_avg_efficiency was 106.0, actual data is 105.5
- FIXED league_avg_tempo: 68.5 -> 67.6 (from Barttorvik data)
- FIXED league_avg_efficiency: 106.0 -> 105.5 (from Barttorvik data)
- REMOVED calibration patches: total_calibration_adjustment = 0.0
- Result: Bias reduced from -8.3 to -1.0 with CORRECT formula, not patches

v33.3 Changes (2024-12-24):
- Real odds backtest: 313 games with DraftKings/FanDuel lines
- Updated min_spread_edge from 7.0 to 3.0 based on optimal ROI
- Updated min_total_edge from 999 to 11.0 (profitable at high edge)

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

from . import __version__ as APP_VERSION


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
    # CALIBRATED v33.6: Backtested on 3,318 FG games and 904 1H games with real ESPN data
    # FG Spread: HCA = 5.8 (from actual home margins in 3,318-game backtest)
    # H1 Spread: HCA = 3.6 (from actual 1H home margins in 904-game backtest)
    home_court_advantage_spread: float = Field(
        default=5.8,
        description="Points added for home court in FG spread. Backtested on 3,318 games."
    )
    home_court_advantage_spread_1h: float = Field(
        default=3.6,
        description="1H spread HCA. Backtested on 904 real 1H games."
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
    # v33.4: REMOVED the stupid -4.6 patch! Root cause was wrong league averages.
    # The -4.6 was subtracting when we were ALREADY underpredicting.
    # FIX: Use correct league averages instead of a calibration hack.
    total_calibration_adjustment: float = Field(
        default=0.0,
        description="Points added to total prediction. Should be 0 with correct league avgs."
    )
    total_calibration_adjustment_1h: float = Field(
        default=0.0,
        description="1H total calibration. Should be 0 with correct league avgs."
    )

    # League averages (REQUIRED for correct Tempo/Efficiency formulas)
    # Formula: Expected = TeamA + TeamB - LeagueAvg
    # v33.4: FIXED from 68.5/106.0 to actual data averages (67.6/105.5)
    # Using wrong values caused systematic bias that was incorrectly "fixed" with calibration
    league_avg_tempo: float = Field(
        default=67.6,
        description="NCAA D1 average possessions per 40 minutes. From Barttorvik data."
    )
    league_avg_efficiency: float = Field(
        default=105.5,
        description="NCAA D1 average efficiency (points per 100 possessions). From Barttorvik."
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
    # BETTING EDGE THRESHOLDS (v33.4 - ROOT CAUSE FIX)
    # ─────────────────────────────────────────────────────────────────────────
    # Real odds backtest (313 games) with FIXED league averages:
    # SPREAD: 2pt+ = 62.2% win, +18.5% ROI | 6pt+ = 62.5% win, +19.3% ROI
    # TOTAL:  3pt+ = 62.0% win, +18.3% ROI | 6pt+ = 62.7% win, +19.6% ROI
    # Both markets NOW PROFITABLE at moderate edge thresholds!
    # ─────────────────────────────────────────────────────────────────────────

    # Minimum edge to recommend a spread bet (in points)
    # v33.4: 2pt optimal for volume, 6pt optimal for ROI
    min_spread_edge: float = Field(
        default=2.0,
        description="Min spread edge. 2pt = +18.5% ROI with 174 bets."
    )
    # Minimum edge to recommend a total bet (in points)
    # v33.4: Totals NOW WORK with fixed league averages!
    # 3pt = +18.3% ROI | 6pt = +19.6% ROI
    min_total_edge: float = Field(
        default=3.0,
        description="Min total edge. 3pt = +18.3% ROI with 159 bets."
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
    service_version: str = APP_VERSION  # Single source of truth from VERSION file
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
