"""Configuration for the NCAA Basketball prediction service.

Versioning:
- Runtime version is loaded from the repo root VERSION file.
- Historical change notes live in docs/VERSIONING.md.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from . import __version__ as app_version


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
    # CALIBRATED v33.10.0: Backtested on 3,318 FG games and 904 1H games with real ESPN data
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

    # EV / probability gating
    # Best practice: do not recommend negative-EV bets even if point edge is large.
    min_ev_percent: float = Field(
        default=0.0,
        description="Minimum EV% to recommend a bet. 0.0 means only positive-EV bets are recommended."
    )
    min_prob_edge: float = Field(
        default=0.0,
        description="Minimum probability edge (model_prob - market_prob). Uses no-vig market prob when available."
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

    # MARKET CONTEXT (line movement / steam / RLM)
    market_move_threshold_spread: float = Field(
        default=1.0,
        description="Points move to flag spread market movement."
    )
    market_move_threshold_total: float = Field(
        default=2.0,
        description="Points move to flag total market movement."
    )
    market_move_threshold_spread_1h: float = Field(
        default=0.75,
        description="Points move to flag 1H spread market movement."
    )
    market_move_threshold_total_1h: float = Field(
        default=1.5,
        description="Points move to flag 1H total market movement."
    )
    steam_threshold_spread: float = Field(
        default=1.5,
        description="Points move to flag a steam spread move."
    )
    steam_threshold_total: float = Field(
        default=3.0,
        description="Points move to flag a steam total move."
    )
    steam_threshold_spread_1h: float = Field(
        default=1.0,
        description="Points move to flag a steam 1H spread move."
    )
    steam_threshold_total_1h: float = Field(
        default=2.0,
        description="Points move to flag a steam 1H total move."
    )
    market_move_confidence_boost: float = Field(
        default=0.03,
        description="Confidence boost when market movement aligns with pick."
    )
    market_move_confidence_penalty: float = Field(
        default=0.05,
        description="Confidence penalty when market movement is against pick."
    )
    steam_confidence_boost: float = Field(
        default=0.05,
        description="Extra confidence boost when steam move aligns with pick."
    )
    steam_confidence_penalty: float = Field(
        default=0.08,
        description="Extra confidence penalty when steam move is against pick."
    )
    rlm_confidence_boost: float = Field(
        default=0.04,
        description="Confidence boost for reverse line movement aligned with pick."
    )
    public_bet_signal_threshold: float = Field(
        default=0.60,
        description="Public bet share threshold to flag one-sided action."
    )
    team_hca_lookback_days: int = Field(
        default=365,
        description="Lookback window (days) for team-specific HCA."
    )
    team_hca_min_games: int = Field(
        default=10,
        description="Minimum home/away games needed to compute team HCA."
    )
    team_hca_cap: float = Field(
        default=3.0,
        description="Clamp team HCA to this absolute maximum."
    )
    health_adjustment_confidence_penalty: float = Field(
        default=0.02,
        description="Confidence penalty when health adjustments are applied."
    )
    health_1h_scale: float = Field(
        default=0.50,
        description="Scale full-game health adjustments for 1H markets."
    )
    bayes_prior_weight: float = Field(
        default=20.0,
        description="Pseudo-sample weight for Bayesian calibration."
    )
    bayes_default_hit_rate: float = Field(
        default=0.524,
        description="Fallback hit rate when sample size is small."
    )
    bayes_recent_window_days: int = Field(
        default=30,
        description="Lookback window for recent ATS calibration."
    )
    bayes_min_samples: int = Field(
        default=50,
        description="Minimum settled samples before using recent hit rate."
    )
    # v33.7: Calibrated from historical backtest residuals
    # FG: Small sample (N~50), using typical NCAAM σ≈12-13
    # 1H: Large sample (N=904), empirical σ≈10.3 spread, 10.1 total
    edge_sigma_spread: float = Field(
        default=12.5,
        description="Sigma for spread edge-to-prob conversion. (Calibrated: typical NCAAM ~12-13)"
    )
    edge_sigma_total: float = Field(
        default=12.0,
        description="Sigma for total edge-to-prob conversion. (Backtest σ≈10.7, conservative +1)"
    )
    edge_sigma_spread_1h: float = Field(
        default=10.5,
        description="Sigma for 1H spread edge-to-prob conversion. (Backtest σ≈10.3)"
    )
    edge_sigma_total_1h: float = Field(
        default=10.5,
        description="Sigma for 1H total edge-to-prob conversion. (Backtest σ≈10.1)"
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
    service_version: str = app_version  # Single source of truth (VERSION)
    git_sha: str = Field(
        default="unknown",
        description="Git commit SHA used to build the container image (GIT_SHA env var).",
    )
    build_date: str = Field(
        default="",
        description="UTC build timestamp for the container image (BUILD_DATE env var).",
    )
    debug: bool = False

    # Feature Store
    feature_store_url: str = Field(
        default="http://localhost:8081",
        description="Feature store service URL."
    )

    # Model config
    model: ModelConfig = Field(default_factory=ModelConfig)

    # Prediction backend selection
    # IMPORTANT: keep this explicit to avoid accidental coupling between
    # production and backtesting artifacts.
    prediction_backend: str = Field(
        default="v33",
        description="Prediction backend. Supported: v33, linear_json",
    )
    linear_json_model_dir: str = Field(
        default="/app/models/linear",
        description="Directory containing JSON linear/logistic model artifacts when prediction_backend=linear_json.",
    )

    @field_validator("prediction_backend")
    @classmethod
    def _validate_prediction_backend(cls, v: str) -> str:
        allowed = {"v33", "linear_json"}
        if v not in allowed:
            raise ValueError(f"prediction_backend must be one of {sorted(allowed)}")
        return v

    class Config:
        # NO .env file - all configuration from environment variables set by docker-compose
        env_nested_delimiter = "__"


# Global settings instance
settings = Settings()
