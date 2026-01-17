"""
NCAA Prediction Engine v33.10.0

Orchestrator for modular market-specific prediction models.

ARCHITECTURE (v33.10.0):
1. Analytical models predict fair lines (spread/total)
2. ML models (when available) predict P(bet wins) directly
3. Fallback to statistical CDF when ML models not trained

Each market has its own independently-backtested model:
- FG Spread: 3,318 games, MAE 10.57, HCA 5.8
- FG Total: 3,318 games, MAE 13.1, Calibration +7.0
- 1H Spread: 904 games, MAE 8.25, HCA 3.6
- 1H Total: 562 games, MAE 8.88, Calibration +2.7

Version History:
- v33.10.0: Azure Key Vault integration, removed FG Total MAX_EDGE cap
- v33.7.0: Initial stable release with modular architecture
"""

import math
from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog

from app import __version__ as APP_VERSION
from app.config import settings
from app.ml.features import FeatureEngineer, GameFeatures

# ML models are ALWAYS available - integrate trained models into production
from app.ml.models import ModelRegistry
from app.models import (
    BetTier,
    BettingRecommendation,
    BetType,
    MarketOdds,
    Pick,
    Prediction,
    TeamRatings,
)
from app.predictors import (
    fg_spread_model,
    fg_total_model,
    h1_spread_model,
    h1_total_model,
)
from app.totals_strategy import totals_strategy, TotalsSignalType

HAS_ML_MODELS = True


# Extreme total thresholds - predictions outside these ranges are unreliable
# From backtest: FG model under-predicts high games, over-predicts low games
FG_TOTAL_MIN_RELIABLE = 120.0  # Below this, model over-predicts
FG_TOTAL_MAX_RELIABLE = 170.0  # Above this, model under-predicts
H1_TOTAL_MIN_RELIABLE = 55.0   # Below this, model over-predicts
H1_TOTAL_MAX_RELIABLE = 85.0   # Above this, model under-predicts


class PredictionEngineV33:
    """
    v33.10 Prediction Engine - Modular architecture with ML probability models.

    ARCHITECTURE:
    1. Analytical models (FGSpreadModel, etc.) predict fair lines
    2. ML models (XGBoost) predict P(bet wins) directly when available
    3. Statistical CDF fallback when ML not trained

    Provides same interface as BarttorvikPredictor for drop-in replacement.
    """

    # Map bet types to ML model names
    BET_TYPE_TO_ML_MODEL = {
        BetType.SPREAD: "fg_spread",
        BetType.TOTAL: "fg_total",
        BetType.SPREAD_1H: "h1_spread",
        BetType.TOTAL_1H: "h1_total",
    }

    def __init__(self, use_ml_models: bool = True):
        """
        Initialize with v33.11 modular models + integrated ML.

        PRODUCTION INTEGRATION:
        - ML models are now PRODUCTION READY and integrated
        - Uses all 22 Barttorvik features in ML feature engineering
        - Statistical confidence intervals replace heuristic calculations

        Args:
            use_ml_models: If True and ML models are trained, use them for
                          probability predictions. Falls back to statistical
                          CDF if models not available.
        """
        self.config = settings.model
        self.logger = structlog.get_logger()
        self.version_tag = f"v{APP_VERSION}"
        self.bayes_priors: dict[BetType, dict[str, float]] = {}

        # Analytical models for fair line prediction
        self.fg_spread_model = fg_spread_model
        self.fg_total_model = fg_total_model
        self.h1_spread_model = h1_spread_model
        self.h1_total_model = h1_total_model

        # ML models are NOW PRODUCTION INTEGRATED (v33.11)
        self._use_ml = use_ml_models and HAS_ML_MODELS
        self._ml_registry: ModelRegistry | None = None
        self._feature_engineer: FeatureEngineer | None = None
        self._ml_loaded = False

        # ALWAYS load ML models in production (v33.11)
        if HAS_ML_MODELS:
            self._load_ml_models()

    def _load_ml_models(self) -> None:
        """Load trained ML models if available."""
        if not HAS_ML_MODELS:
            self.logger.debug("ML models not available (missing xgboost)")
            return

        try:
            self._ml_registry = ModelRegistry()
            self._feature_engineer = FeatureEngineer()
            self._ml_loaded = self._ml_registry.load_models()

            if self._ml_loaded:
                available = self._ml_registry.available_models
                self.logger.info(f"ML models loaded: {available}")
            else:
                self.logger.debug("No trained ML models found, using statistical fallback")
        except Exception as e:
            self.logger.warning(f"Failed to load ML models: {e}")
            self._ml_loaded = False

    def set_bayes_priors(self, priors: dict) -> None:
        """Inject Bayesian priors for confidence calibration."""
        self.bayes_priors = priors or {}

    def make_prediction(
        self,
        game_id: UUID,
        home_team: str,
        away_team: str,
        commence_time: datetime,
        home_ratings: TeamRatings,
        away_ratings: TeamRatings,
        market_odds: MarketOdds | None = None,
        is_neutral: bool = False,
        home_rest: Optional['RestInfo'] = None,
        away_rest: Optional['RestInfo'] = None,
        home_hca: float | None = None,
        home_hca_1h: float | None = None,
        home_health: dict | None = None,
        away_health: dict | None = None,
    ) -> Prediction:
        """
        Generate predictions using v33.10.0 modular models.

        Each market gets its own specialized model:
        - FG Spread: Proven statistical edge
        - FG Total: Hybrid approach
        - 1H Spread: Independent calibration
        - 1H Total: Independent calibration

        Args:
            game_id: Unique game identifier
            home_team: Home team name
            away_team: Away team name
            commence_time: Game start time
            home_ratings: Barttorvik ratings (all 22 fields required)
            away_ratings: Barttorvik ratings (all 22 fields required)
            market_odds: Current market odds (optional)
            is_neutral: True if neutral site game
            home_rest: Rest info for situational adjustments (optional)
            away_rest: Rest info for situational adjustments (optional)
            home_hca: Optional team-specific HCA override (full game)
            home_hca_1h: Optional team-specific HCA override (1H)
            home_health: Optional health adjustments for home team
            away_health: Optional health adjustments for away team

        Returns:
            Complete Prediction object with all 4 market predictions
        """
        if home_ratings is None or away_ratings is None:
            raise ValueError("home_ratings and away_ratings are required")

        def _rest_days(rest: Optional['RestInfo']) -> int | None:
            """Gracefully handle both legacy and current rest attributes."""
            if rest is None:
                return None
            return getattr(rest, "days_since_game", None) or getattr(rest, "days_rest", None)

        self.logger.info(
            f"{self.version_tag}: Predicting {home_team} vs {away_team}",
            game_id=str(game_id),
            models=["FGSpread", "FGTotal", "H1Spread", "H1Total"]
        )

        # ═══════════════════════════════════════════════════════════════════════
        # Get predictions from each independent model
        # ═══════════════════════════════════════════════════════════════════════

        fg_spread_hca = self.fg_spread_model.HCA
        h1_spread_hca = self.h1_spread_model.HCA
        if home_hca is not None:
            self.fg_spread_model.HCA = home_hca
        if home_hca_1h is not None:
            self.h1_spread_model.HCA = home_hca_1h

        try:
            # FG Spread (independent, backtested on 3,318 games)
            fg_spread_pred = self.fg_spread_model.predict(
                home=home_ratings,
                away=away_ratings,
                is_neutral=is_neutral,
                home_rest_days=_rest_days(home_rest),
                away_rest_days=_rest_days(away_rest),
            )

            # FG Total (independent, backtested on 3,318 games)
            fg_total_pred = self.fg_total_model.predict(
                home=home_ratings,
                away=away_ratings,
                is_neutral=is_neutral,
                home_rest_days=_rest_days(home_rest),
                away_rest_days=_rest_days(away_rest),
            )

            # 1H Spread (independent, backtested on 904 games)
            h1_spread_pred = self.h1_spread_model.predict(
                home=home_ratings,
                away=away_ratings,
                is_neutral=is_neutral,
                home_rest_days=_rest_days(home_rest),
                away_rest_days=_rest_days(away_rest),
            )

            # 1H Total (independent, backtested on 562 games)
            h1_total_pred = self.h1_total_model.predict(
                home=home_ratings,
                away=away_ratings,
                is_neutral=is_neutral,
                home_rest_days=_rest_days(home_rest),
                away_rest_days=_rest_days(away_rest),
            )
        finally:
            self.fg_spread_model.HCA = fg_spread_hca
            self.h1_spread_model.HCA = h1_spread_hca

        # ═══════════════════════════════════════════════════════════════════════
        # Convert model predictions to Prediction object
        # ═══════════════════════════════════════════════════════════════════════

        # Derive implied scores from spread and total (for consistency)
        fg_spread = fg_spread_pred.value
        fg_total = fg_total_pred.value
        fg_home_score = (fg_total - fg_spread) / 2
        fg_away_score = (fg_total + fg_spread) / 2

        h1_spread = h1_spread_pred.value
        h1_total = h1_total_pred.value
        h1_home_score = (h1_total - h1_spread) / 2
        h1_away_score = (h1_total + h1_spread) / 2

        health_spread_adj = 0.0
        health_total_adj = 0.0
        if home_health or away_health:
            home_spread_adj = float((home_health or {}).get("spread_adjustment", 0.0))
            away_spread_adj = float((away_health or {}).get("spread_adjustment", 0.0))
            home_total_adj = float((home_health or {}).get("total_adjustment", 0.0))
            away_total_adj = float((away_health or {}).get("total_adjustment", 0.0))
            health_spread_adj = home_spread_adj - away_spread_adj
            health_total_adj = home_total_adj + away_total_adj

            fg_spread = fg_spread - health_spread_adj
            fg_total = fg_total + health_total_adj
            h1_spread = h1_spread - (health_spread_adj * self.config.health_1h_scale)
            h1_total = h1_total + (health_total_adj * self.config.health_1h_scale)

        fg_spread = round(fg_spread, 1)
        fg_total = round(fg_total, 1)
        h1_spread = round(h1_spread, 1)
        h1_total = round(h1_total, 1)

        fg_home_score = (fg_total - fg_spread) / 2
        fg_away_score = (fg_total + fg_spread) / 2
        h1_home_score = (h1_total - h1_spread) / 2
        h1_away_score = (h1_total + h1_spread) / 2

        # Create Prediction object
        prediction = Prediction(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            commence_time=commence_time,
            # FG Predictions
            predicted_spread=fg_spread,
            predicted_total=fg_total,
            predicted_home_score=fg_home_score,
            predicted_away_score=fg_away_score,
            spread_confidence=max(
                0.50,
                fg_spread_pred.confidence - (self.config.health_adjustment_confidence_penalty if health_spread_adj else 0.0),
            ),
            total_confidence=max(
                0.50,
                fg_total_pred.confidence - (self.config.health_adjustment_confidence_penalty if health_total_adj else 0.0),
            ),
            # 1H Predictions
            predicted_spread_1h=h1_spread,
            predicted_total_1h=h1_total,
            predicted_home_score_1h=h1_home_score,
            predicted_away_score_1h=h1_away_score,
            spread_confidence_1h=max(
                0.50,
                h1_spread_pred.confidence - (self.config.health_adjustment_confidence_penalty if health_spread_adj else 0.0),
            ),
            total_confidence_1h=max(
                0.50,
                h1_total_pred.confidence - (self.config.health_adjustment_confidence_penalty if health_total_adj else 0.0),
            ),
            # Model metadata
            model_version=self.version_tag,
        )

        # Calculate edges if market odds available
        if market_odds:
            prediction.calculate_edges(market_odds)

        return prediction

    def generate_recommendations(
        self,
        prediction: Prediction,
        market_odds: MarketOdds,
        home_ratings: TeamRatings | None = None,
        away_ratings: TeamRatings | None = None,
        is_neutral: bool = False,
        game_date: datetime | None = None,
    ) -> list[BettingRecommendation]:
        """
        Generate betting recommendations from predictions and market odds.

        Uses model-specific minimum edges and confidence thresholds.

        v33.10: Optionally uses ML models for probability prediction when
        home_ratings and away_ratings are provided.

        v33.11: Uses independent totals strategy based on sharp money tracking
        and seasonal patterns instead of regression model (which has -6% ROI).

        Args:
            prediction: Prediction object from make_prediction()
            market_odds: Current market odds
            home_ratings: Home team ratings (for ML models)
            away_ratings: Away team ratings (for ML models)
            is_neutral: Neutral site flag
            game_date: Game date for seasonal pattern detection

        Returns:
            List of BettingRecommendation objects
        """
        # Store for use in _create_recommendation
        self._current_home_ratings = home_ratings
        self._current_away_ratings = away_ratings
        self._current_is_neutral = is_neutral
        self._current_game_date = game_date or datetime.now()

        recommendations = []

        # ─────────────────────────────────────────────────────────────────────
        # FG SPREAD RECOMMENDATIONS
        # ─────────────────────────────────────────────────────────────────────
        if market_odds.spread is not None and prediction.spread_edge >= self.fg_spread_model.MIN_EDGE:
            if prediction.spread_confidence >= self.config.min_confidence:
                pick = Pick.HOME if prediction.predicted_spread < market_odds.spread else Pick.AWAY
                rec = self._create_recommendation(
                    prediction,
                    BetType.SPREAD,
                    pick,
                    prediction.predicted_spread,
                    market_odds.spread,
                    prediction.spread_edge,
                    prediction.spread_confidence,
                    market_odds,
                )
                if rec:
                    recommendations.append(rec)

        # ─────────────────────────────────────────────────────────────────────
        # FG TOTAL RECOMMENDATIONS (v33.11 - Independent Totals Strategy)
        # ─────────────────────────────────────────────────────────────────────
        # Traditional regression models have -6% ROI on totals because the market
        # already incorporates tempo/efficiency data. Instead, we use:
        # 1. Sharp money tracking (Action Network) - when pros disagree with public
        # 2. Seasonal patterns - statistically significant edges in Nov/Dec/March

        if market_odds.total is not None:
            # Extract betting splits from market_odds if available
            total_over_public = getattr(market_odds, 'public_bet_pct_over', None)
            total_under_public = 100 - total_over_public if total_over_public is not None else None
            total_over_money = getattr(market_odds, 'public_money_pct_over', None)
            total_under_money = 100 - total_over_money if total_over_money is not None else None

            # Convert from 0-1 to 0-100 if needed
            if total_over_public is not None and total_over_public <= 1:
                total_over_public *= 100
                total_under_public = 100 - total_over_public
            if total_over_money is not None and total_over_money <= 1:
                total_over_money *= 100
                total_under_money = 100 - total_over_money

            # Get model's pick for reference (but don't use it as primary signal)
            model_pick = "OVER" if prediction.predicted_total > market_odds.total else "UNDER"
            model_edge = prediction.total_edge

            # Check totals strategy for actionable signal
            should_bet, totals_signal = totals_strategy.should_bet_total(
                game_date=self._current_game_date,
                total_over_public=total_over_public,
                total_under_public=total_under_public,
                total_over_money=total_over_money,
                total_under_money=total_under_money,
                model_pick=model_pick,
                model_edge=model_edge,
            )

            if should_bet:
                pick = Pick.OVER if totals_signal.pick == "OVER" else Pick.UNDER
                # Use signal confidence instead of model confidence
                rec = self._create_recommendation(
                    prediction,
                    BetType.TOTAL,
                    pick,
                    prediction.predicted_total,
                    market_odds.total,
                    totals_signal.expected_roi,  # Use expected ROI as "edge"
                    totals_signal.confidence,
                    market_odds,
                    signal_type=totals_signal.signal_type.value,
                    signal_reasoning=totals_signal.reasoning,
                )
                if rec:
                    recommendations.append(rec)
            else:
                self.logger.debug(
                    "fg_total_no_signal",
                    reasoning=totals_signal.reasoning,
                    signal_type=totals_signal.signal_type.value,
                )

        # ─────────────────────────────────────────────────────────────────────
        # 1H SPREAD RECOMMENDATIONS
        # ─────────────────────────────────────────────────────────────────────
        if market_odds.spread_1h is not None and prediction.spread_edge_1h >= self.h1_spread_model.MIN_EDGE:
            if prediction.spread_confidence_1h >= self.config.min_confidence:
                pick = Pick.HOME if prediction.predicted_spread_1h < market_odds.spread_1h else Pick.AWAY
                rec = self._create_recommendation(
                    prediction,
                    BetType.SPREAD_1H,
                    pick,
                    prediction.predicted_spread_1h,
                    market_odds.spread_1h,
                    prediction.spread_edge_1h,
                    prediction.spread_confidence_1h,
                    market_odds,
                )
                if rec:
                    recommendations.append(rec)

        # ─────────────────────────────────────────────────────────────────────
        # 1H TOTAL RECOMMENDATIONS
        # ─────────────────────────────────────────────────────────────────────
        # Skip extreme 1H totals - model is unreliable at extremes
        h1_total_in_range = H1_TOTAL_MIN_RELIABLE <= prediction.predicted_total_1h <= H1_TOTAL_MAX_RELIABLE
        if not h1_total_in_range:
            self.logger.info(
                f"Skipping 1H total bet - prediction {prediction.predicted_total_1h:.1f} outside reliable range "
                f"({H1_TOTAL_MIN_RELIABLE}-{H1_TOTAL_MAX_RELIABLE})"
            )
        if market_odds.total_1h is not None and prediction.total_edge_1h >= self.h1_total_model.MIN_EDGE and h1_total_in_range:
            if prediction.total_confidence_1h >= self.config.min_confidence:
                pick = Pick.OVER if prediction.predicted_total_1h > market_odds.total_1h else Pick.UNDER
                rec = self._create_recommendation(
                    prediction,
                    BetType.TOTAL_1H,
                    pick,
                    prediction.predicted_total_1h,
                    market_odds.total_1h,
                    prediction.total_edge_1h,
                    prediction.total_confidence_1h,
                    market_odds,
                )
                if rec:
                    recommendations.append(rec)

        return recommendations

    def _create_recommendation(
        self,
        prediction: Prediction,
        bet_type: BetType,
        pick: Pick,
        model_line: float,
        market_line: float,
        edge: float,
        confidence: float,
        market_odds: MarketOdds,
        signal_type: str | None = None,
        signal_reasoning: str | None = None,
    ) -> BettingRecommendation | None:
        """
        Create a single BettingRecommendation.

        Handles conversion to Pick perspective (for AWAY picks, flip spread sign).

        Args:
            signal_type: Optional signal type for totals (e.g., "sharp_money", "seasonal")
            signal_reasoning: Optional explanation of why this bet is recommended
        """
        # Store bet line from PICK perspective
        bet_line = market_line
        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            bet_line = market_line if pick == Pick.HOME else -market_line

        # Get sharp line for comparison
        sharp_line = None
        is_sharp_aligned = True
        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            sharp_line = market_odds.sharp_spread
        else:
            sharp_line = market_odds.sharp_total

        # Check sharp alignment
        if sharp_line is not None:
            is_sharp_aligned = self._check_sharp_alignment(
                pick, model_line, market_line, sharp_line, bet_type
            )

        # Apply sharp alignment penalty
        final_confidence = confidence
        if not is_sharp_aligned:
            final_confidence *= (1 - self.config.against_sharp_penalty)

        # Apply market context adjustments (line movement / steam / RLM)
        final_confidence = self._apply_market_context(
            final_confidence, bet_type, pick, market_odds
        )

        # Skip if confidence dropped below threshold
        if final_confidence < self.config.min_confidence:
            return None

        # Get probability (ML model if available, otherwise statistical)
        implied_prob = self._calibrated_probability(
            edge,
            final_confidence,
            bet_type,
            home_ratings=getattr(self, '_current_home_ratings', None),
            away_ratings=getattr(self, '_current_away_ratings', None),
            market_odds=market_odds,
            is_neutral=getattr(self, '_current_is_neutral', False),
        )
        price = self._get_pick_price(bet_type, pick, market_odds)
        ev_percent, kelly = self._calculate_ev_kelly(implied_prob, price)

        # Determine bet tier
        bet_tier = self._get_bet_tier(edge, final_confidence)

        # Calculate recommended units
        recommended_units = min(
            kelly * self.config.kelly_fraction * 10,
            self.config.max_bet_units,
        )

        # Get market probabilities from odds
        market_prob = self._get_market_probability(bet_type, market_odds, pick)
        market_prob_novig, market_hold_percent = self._get_market_probability_novig(
            bet_type, market_odds, pick
        )

        # Probability edge vs market (prefer no-vig when possible)
        market_ref_prob = market_prob_novig if market_prob_novig is not None else market_prob
        prob_edge = implied_prob - market_ref_prob

        # EV/probability gating (best practice)
        if ev_percent < self.config.min_ev_percent:
            return None
        if prob_edge < self.config.min_prob_edge:
            return None

        return BettingRecommendation(
            game_id=prediction.game_id,
            home_team=prediction.home_team,
            away_team=prediction.away_team,
            commence_time=prediction.commence_time,
            bet_type=bet_type,
            pick=pick,
            line=bet_line,
            model_line=model_line,
            market_line=market_line,
            edge=edge,
            confidence=final_confidence,
            ev_percent=ev_percent,
            implied_prob=implied_prob,
            market_prob=market_prob,
            pick_price=price,
            market_prob_novig=market_prob_novig,
            market_hold_percent=market_hold_percent,
            prob_edge=prob_edge,
            kelly_fraction=kelly,
            recommended_units=round(recommended_units, 1),
            bet_tier=bet_tier,
            sharp_line=sharp_line,
            is_sharp_aligned=is_sharp_aligned,
            model_version=prediction.model_version,
        )

    def _get_pick_price(
        self,
        bet_type: BetType,
        pick: Pick,
        market_odds: MarketOdds,
    ) -> int:
        """Return the American odds price for the specific pick side.

        This must be explicit: no implicit -110 defaults.
        """
        if bet_type == BetType.SPREAD:
            if pick == Pick.HOME and market_odds.spread_home_price is not None:
                return int(market_odds.spread_home_price)
            if pick == Pick.AWAY and market_odds.spread_away_price is not None:
                return int(market_odds.spread_away_price)
            if market_odds.spread_price is not None:
                return int(market_odds.spread_price)
            raise ValueError("Missing spread price (need spread_home_price/spread_away_price or spread_price)")

        if bet_type == BetType.SPREAD_1H:
            if pick == Pick.HOME and market_odds.spread_1h_home_price is not None:
                return int(market_odds.spread_1h_home_price)
            if pick == Pick.AWAY and market_odds.spread_1h_away_price is not None:
                return int(market_odds.spread_1h_away_price)
            if market_odds.spread_price_1h is not None:
                return int(market_odds.spread_price_1h)
            raise ValueError("Missing 1H spread price (need spread_1h_home_price/spread_1h_away_price or spread_price_1h)")

        if bet_type == BetType.TOTAL:
            if pick == Pick.OVER and market_odds.over_price is not None:
                return int(market_odds.over_price)
            if pick == Pick.UNDER and market_odds.under_price is not None:
                return int(market_odds.under_price)
            raise ValueError("Missing total price (need over_price/under_price)")

        if bet_type == BetType.TOTAL_1H:
            if pick == Pick.OVER and market_odds.over_price_1h is not None:
                return int(market_odds.over_price_1h)
            if pick == Pick.UNDER and market_odds.under_price_1h is not None:
                return int(market_odds.under_price_1h)
            raise ValueError("Missing 1H total price (need over_price_1h/under_price_1h)")

        raise ValueError(f"Unsupported bet_type for pricing: {bet_type}")

    def _get_edge_sigma(self, bet_type: BetType) -> float:
        if bet_type == BetType.SPREAD:
            return self.config.edge_sigma_spread
        if bet_type == BetType.TOTAL:
            return self.config.edge_sigma_total
        if bet_type == BetType.SPREAD_1H:
            return self.config.edge_sigma_spread_1h
        return self.config.edge_sigma_total_1h

    def _get_bayes_prior(self, bet_type: BetType) -> tuple[float, float]:
        """Return (hit_rate, prior_weight) for the bet type."""
        default_rate = self.config.bayes_default_hit_rate
        prior_weight = self.config.bayes_prior_weight
        if not self.bayes_priors:
            return default_rate, prior_weight

        key = bet_type
        prior = self.bayes_priors.get(key)
        if prior is None and isinstance(bet_type, BetType):
            prior = self.bayes_priors.get(bet_type.value)
        if not isinstance(prior, dict):
            return default_rate, prior_weight

        hit_rate = float(prior.get("hit_rate", default_rate))
        samples = int(prior.get("samples", 0) or 0)
        if samples < self.config.bayes_min_samples:
            return default_rate, prior_weight
        return hit_rate, prior_weight

    def _get_ml_probability(
        self,
        bet_type: BetType,
        home_ratings: TeamRatings,
        away_ratings: TeamRatings,
        market_odds: MarketOdds,
        is_neutral: bool = False,
    ) -> float | None:
        """
        Get probability from trained ML model if available.

        Returns None if ML model not available for this bet type.
        """
        if not self._ml_loaded or self._ml_registry is None:
            return None

        ml_model_name = self.BET_TYPE_TO_ML_MODEL.get(bet_type)
        if ml_model_name is None or not self._ml_registry.has_model(ml_model_name):
            return None

        try:
            # Build features
            game_features = GameFeatures(
                game_id="inference",
                game_date="",
                home_team=home_ratings.team_name,
                away_team=away_ratings.team_name,

                # Efficiency
                home_adj_o=home_ratings.adj_o,
                home_adj_d=home_ratings.adj_d,
                away_adj_o=away_ratings.adj_o,
                away_adj_d=away_ratings.adj_d,
                home_tempo=home_ratings.tempo,
                away_tempo=away_ratings.tempo,
                home_rank=home_ratings.rank,
                away_rank=away_ratings.rank,

                # Four factors
                home_efg=home_ratings.efg,
                home_efgd=home_ratings.efgd,
                away_efg=away_ratings.efg,
                away_efgd=away_ratings.efgd,
                home_tor=home_ratings.tor,
                home_tord=home_ratings.tord,
                away_tor=away_ratings.tor,
                away_tord=away_ratings.tord,
                home_orb=home_ratings.orb,
                home_drb=home_ratings.drb,
                away_orb=away_ratings.orb,
                away_drb=away_ratings.drb,
                home_ftr=home_ratings.ftr,
                home_ftrd=home_ratings.ftrd,
                away_ftr=away_ratings.ftr,
                away_ftrd=away_ratings.ftrd,

                # Shooting
                home_two_pt_pct=home_ratings.two_pt_pct,
                home_two_pt_pct_d=home_ratings.two_pt_pct_d,
                away_two_pt_pct=away_ratings.two_pt_pct,
                away_two_pt_pct_d=away_ratings.two_pt_pct_d,
                home_three_pt_pct=home_ratings.three_pt_pct,
                home_three_pt_pct_d=home_ratings.three_pt_pct_d,
                away_three_pt_pct=away_ratings.three_pt_pct,
                away_three_pt_pct_d=away_ratings.three_pt_pct_d,
                home_three_pt_rate=home_ratings.three_pt_rate,
                home_three_pt_rate_d=home_ratings.three_pt_rate_d,
                away_three_pt_rate=away_ratings.three_pt_rate,
                away_three_pt_rate_d=away_ratings.three_pt_rate_d,

                # Quality
                home_barthag=home_ratings.barthag,
                home_wab=home_ratings.wab,
                away_barthag=away_ratings.barthag,
                away_wab=away_ratings.wab,

                # Market
                spread_open=market_odds.spread_open,
                total_open=market_odds.total_open,
                spread_current=market_odds.spread,
                total_current=market_odds.total,
                sharp_spread=market_odds.sharp_spread,
                sharp_total=market_odds.sharp_total,
                square_spread=market_odds.square_spread,
                square_total=market_odds.square_total,

                # Situational
                is_neutral=is_neutral,

                # Public betting
                public_bet_pct_home=market_odds.public_bet_pct_home,
                public_money_pct_home=market_odds.public_money_pct_home,
                public_bet_pct_over=market_odds.public_bet_pct_over,
                public_money_pct_over=market_odds.public_money_pct_over,
            )

            # Extract features
            X = self._feature_engineer.extract_features(game_features)
            X = X.reshape(1, -1)

            # Get probability
            proba = self._ml_registry.predict_proba(ml_model_name, X)
            if proba is not None:
                return float(proba[0])

        except Exception as e:
            self.logger.warning(f"ML prediction failed for {bet_type}: {e}")

        return None

    def _calibrated_probability(
        self,
        edge: float,
        confidence: float,
        bet_type: BetType,
        home_ratings: TeamRatings | None = None,
        away_ratings: TeamRatings | None = None,
        market_odds: MarketOdds | None = None,
        is_neutral: bool = False,
    ) -> float:
        """
        Convert edge to win probability.

        v33.10: Uses ML model if available, otherwise statistical CDF.

        The formula (statistical fallback): P(cover) = Φ(edge / sigma) blended with prior

        Key insight: Even large edges have uncertainty because:
        1. Our model has error (MAE ~10-13 points)
        2. Markets incorporate information we don't have
        3. Game outcomes have inherent variance
        """
        # Try ML model first (if available and we have all inputs)
        if (
            self._ml_loaded
            and home_ratings is not None
            and away_ratings is not None
            and market_odds is not None
        ):
            ml_prob = self._get_ml_probability(
                bet_type, home_ratings, away_ratings, market_odds, is_neutral
            )
            if ml_prob is not None:
                self.logger.debug(f"Using ML probability for {bet_type}: {ml_prob:.3f}")
                return ml_prob

        # Fallback: Statistical CDF approach
        sigma = self._get_edge_sigma(bet_type)
        conf = min(1.0, max(0.0, confidence))

        if sigma <= 0:
            base_prob = conf
        else:
            # Cap edge at 2.5 sigma to prevent overconfidence
            # This limits max probability to ~99.4% even for huge edges
            max_z = 2.5
            z = edge / sigma
            z_capped = min(z, max_z)

            # Log when we cap (useful for debugging)
            if z > max_z:
                self.logger.debug(
                    f"Edge capped: {edge:.1f} pts (z={z:.2f} -> {z_capped:.2f})"
                )

            edge_prob = 0.5 * (1.0 + math.erf(z_capped / math.sqrt(2.0)))
            edge_prob = min(0.99, max(0.01, edge_prob))

            # Blend with confidence: move from 50% toward edge_prob
            # Lower confidence = stay closer to 50%
            base_prob = 0.5 + (edge_prob - 0.5) * conf

        # Bayesian regularization toward historical hit rate
        prior_rate, prior_weight = self._get_bayes_prior(bet_type)
        model_weight = max(1.0, prior_weight * max(0.25, conf))
        blended = (prior_rate * prior_weight + base_prob * model_weight) / (prior_weight + model_weight)

        # Hard floor/ceiling to prevent extreme Kelly sizing
        return min(0.85, max(0.15, blended))

    def _calculate_ev_kelly(
        self,
        implied_prob: float,
        price: int,
    ) -> tuple[float, float]:
        """Calculate expected value percentage and Kelly criterion."""
        if price >= 0:
            win = price
            loss = 100
        else:
            win = 100
            loss = abs(price)

        p = min(0.99, max(0.01, implied_prob))
        q = 1 - p
        b = win / loss if loss else 0.0

        ev = (p * win) - (q * loss)
        ev_percent = (ev / loss * 100) if loss else 0.0

        # Kelly: f* = (bp - q) / b
        kelly = max(0, (b * p - q) / b) if b > 0 else 0

        return ev_percent, kelly

    def _get_bet_tier(self, edge: float, confidence: float) -> BetTier:
        """Determine bet tier based on edge and confidence."""
        if edge >= 5.0 and confidence >= 0.75:
            return BetTier.MAX
        if edge >= 3.0 and confidence >= 0.70:
            return BetTier.MEDIUM
        return BetTier.STANDARD

    def _check_sharp_alignment(
        self,
        pick: Pick,
        model_line: float,
        market_line: float,
        sharp_line: float | None,
        bet_type: BetType,
    ) -> bool:
        """Check if we're aligned with sharp movement."""
        if sharp_line is None:
            return True

        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            # For spreads: model and sharp should agree on direction
            model_favors_home = model_line < market_line
            sharp_favors_home = sharp_line < market_line
            return model_favors_home == sharp_favors_home
        # For totals: model and sharp should agree on direction
        model_over = model_line > market_line
        sharp_over = sharp_line > market_line
        return model_over == sharp_over

    def _apply_market_context(
        self,
        confidence: float,
        bet_type: BetType,
        pick: Pick,
        market_odds: MarketOdds,
    ) -> float:
        """Adjust confidence using line movement/steam/RLM/sharp-square signals."""
        adjusted = confidence

        # 1. Line movement signals (requires opening line)
        move = self._get_market_move(bet_type, market_odds)
        if move is not None:
            move_threshold, steam_threshold = self._get_move_thresholds(bet_type)
            aligned = self._is_move_aligned(bet_type, pick, move)

            if abs(move) >= move_threshold:
                if aligned:
                    adjusted *= (1 + self.config.market_move_confidence_boost)
                else:
                    adjusted *= (1 - self.config.market_move_confidence_penalty)

            if abs(move) >= steam_threshold:
                if aligned:
                    adjusted *= (1 + self.config.steam_confidence_boost)
                else:
                    adjusted *= (1 - self.config.steam_confidence_penalty)

            # RLM detection (if public percentages available)
            if self._is_reverse_line_move(bet_type, move, market_odds):
                if aligned:
                    adjusted *= (1 + self.config.rlm_confidence_boost)

        # 2. Sharp vs Square divergence (alternative to public percentages)
        # When sharp books have moved but square books haven't, that's actionable
        divergence_detected, divergence_amount = self._detect_sharp_square_divergence(
            bet_type, market_odds
        )
        if divergence_detected:
            aligned_with_sharps = self._is_aligned_with_sharp_divergence(
                bet_type, pick, market_odds
            )
            if aligned_with_sharps:
                # Boost confidence when we agree with sharps
                adjusted *= (1 + self.config.rlm_confidence_boost)
            else:
                # Penalty when we're going against sharps
                adjusted *= (1 - self.config.market_move_confidence_penalty)

        return min(0.99, max(0.01, adjusted))

    def _get_market_move(self, bet_type: BetType, market_odds: MarketOdds) -> float | None:
        """Return current - open line for the bet type (home-perspective for spreads)."""
        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            current = market_odds.spread if bet_type == BetType.SPREAD else market_odds.spread_1h
            open_line = market_odds.spread_open if bet_type == BetType.SPREAD else market_odds.spread_1h_open
            if open_line is None:
                open_line = market_odds.sharp_spread_open
                if current is None:
                    current = market_odds.sharp_spread
            if current is None or open_line is None:
                return None
            return current - open_line

        current = market_odds.total if bet_type == BetType.TOTAL else market_odds.total_1h
        open_line = market_odds.total_open if bet_type == BetType.TOTAL else market_odds.total_1h_open
        if open_line is None:
            open_line = market_odds.sharp_total_open
            if current is None:
                current = market_odds.sharp_total
        if current is None or open_line is None:
            return None
        return current - open_line

    def _get_move_thresholds(self, bet_type: BetType) -> tuple[float, float]:
        if bet_type == BetType.SPREAD:
            return self.config.market_move_threshold_spread, self.config.steam_threshold_spread
        if bet_type == BetType.SPREAD_1H:
            return self.config.market_move_threshold_spread_1h, self.config.steam_threshold_spread_1h
        if bet_type == BetType.TOTAL_1H:
            return self.config.market_move_threshold_total_1h, self.config.steam_threshold_total_1h
        return self.config.market_move_threshold_total, self.config.steam_threshold_total

    def _is_move_aligned(self, bet_type: BetType, pick: Pick, move: float) -> bool:
        """True if line movement direction aligns with the pick side."""
        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            if pick == Pick.HOME:
                return move < 0
            return move > 0

        if pick == Pick.OVER:
            return move > 0
        return move < 0

    def _is_reverse_line_move(
        self,
        bet_type: BetType,
        move: float,
        market_odds: MarketOdds,
    ) -> bool:
        """Detect reverse line movement when public bet splits are available."""
        threshold = self.config.public_bet_signal_threshold

        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            pct_home = market_odds.public_bet_pct_home
            if pct_home is None:
                return False
            public_home = pct_home >= threshold
            public_away = pct_home <= (1 - threshold)
            if not (public_home or public_away):
                return False
            if public_home and move > 0:
                return True
            if public_away and move < 0:
                return True
            return False

        pct_over = market_odds.public_bet_pct_over
        if pct_over is None:
            return False
        public_over = pct_over >= threshold
        public_under = pct_over <= (1 - threshold)
        if not (public_over or public_under):
            return False
        if public_over and move < 0:
            return True
        if public_under and move > 0:
            return True
        return False

    def _detect_sharp_square_divergence(
        self,
        bet_type: BetType,
        market_odds: MarketOdds,
    ) -> tuple[bool, float]:
        """
        Detect when sharp books (Pinnacle) have moved but square books haven't.

        This is an alternative to public betting percentages - we infer sharp action
        from the difference between sharp and square lines.

        Returns: (divergence_detected, divergence_amount)
        """
        divergence_threshold = 0.5  # Half-point difference is meaningful

        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            sharp = market_odds.sharp_spread
            square = market_odds.square_spread
            if sharp is None or square is None:
                # Fallback: compare sharp to consensus spread
                square = market_odds.spread
            if sharp is None or square is None:
                return False, 0.0

            divergence = abs(sharp - square)
            return divergence >= divergence_threshold, divergence

        # Totals
        sharp = market_odds.sharp_total
        square = market_odds.square_total
        if sharp is None or square is None:
            square = market_odds.total
        if sharp is None or square is None:
            return False, 0.0

        divergence = abs(sharp - square)
        return divergence >= 1.0, divergence  # Full point for totals

    def _is_aligned_with_sharp_divergence(
        self,
        bet_type: BetType,
        pick: Pick,
        market_odds: MarketOdds,
    ) -> bool:
        """
        Check if our pick is on the same side as the sharp divergence.

        If sharp spread is more negative than square (sharps favor home more),
        and we're picking HOME, we're aligned with sharps.
        """
        if bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            sharp = market_odds.sharp_spread
            square = market_odds.square_spread or market_odds.spread
            if sharp is None or square is None:
                return True  # No data = neutral

            sharps_favor_home = sharp < square  # More negative = more home favorite
            if pick == Pick.HOME:
                return sharps_favor_home
            # AWAY
            return not sharps_favor_home

        # Totals
        sharp = market_odds.sharp_total
        square = market_odds.square_total or market_odds.total
        if sharp is None or square is None:
            return True

        sharps_favor_over = sharp > square  # Higher total = over
        if pick == Pick.OVER:
            return sharps_favor_over
        # UNDER
        return not sharps_favor_over

    def _get_market_probability(
        self,
        bet_type: BetType,
        market_odds: MarketOdds,
        pick: Pick,
    ) -> float:
        """Get implied probability from market odds."""
        def american_to_prob(odds: int) -> float:
            if odds < 0:
                return abs(odds) / (abs(odds) + 100)
            return 100 / (odds + 100)

        odds = self._get_pick_price(bet_type, pick, market_odds)
        return american_to_prob(odds)

    def _get_market_probability_novig(
        self,
        bet_type: BetType,
        market_odds: MarketOdds,
        pick: Pick,
    ) -> tuple[float | None, float | None]:
        """Return (no-vig probability for pick, market hold %), when both sides are available."""

        def american_to_prob(odds: int) -> float:
            if odds < 0:
                return abs(odds) / (abs(odds) + 100)
            return 100 / (odds + 100)

        def no_vig_two_way(odds_a: int, odds_b: int) -> tuple[float, float, float]:
            pa_raw = american_to_prob(odds_a)
            pb_raw = american_to_prob(odds_b)
            denom = pa_raw + pb_raw
            if denom <= 0:
                return 0.5, 0.5, 0.0
            pa = pa_raw / denom
            pb = pb_raw / denom
            hold = max(0.0, denom - 1.0)
            return pa, pb, hold

        # Spreads (need both HOME and AWAY prices)
        if bet_type == BetType.SPREAD:
            home = market_odds.spread_home_price
            away = market_odds.spread_away_price
            if home is None or away is None:
                return None, None
            p_home, p_away, hold = no_vig_two_way(int(home), int(away))
            prob = p_home if pick == Pick.HOME else p_away
            return prob, hold * 100

        if bet_type == BetType.SPREAD_1H:
            home = market_odds.spread_1h_home_price
            away = market_odds.spread_1h_away_price
            if home is None or away is None:
                return None, None
            p_home, p_away, hold = no_vig_two_way(int(home), int(away))
            prob = p_home if pick == Pick.HOME else p_away
            return prob, hold * 100

        # Totals (need both OVER and UNDER prices)
        if bet_type == BetType.TOTAL:
            over = market_odds.over_price
            under = market_odds.under_price
            if over is None or under is None:
                return None, None
            p_over, p_under, hold = no_vig_two_way(int(over), int(under))
            prob = p_over if pick == Pick.OVER else p_under
            return prob, hold * 100

        if bet_type == BetType.TOTAL_1H:
            over = market_odds.over_price_1h
            under = market_odds.under_price_1h
            if over is None or under is None:
                return None, None
            p_over, p_under, hold = no_vig_two_way(int(over), int(under))
            prob = p_over if pick == Pick.OVER else p_under
            return prob, hold * 100

        return None, None


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton instance for use throughout the application
# ═══════════════════════════════════════════════════════════════════════════════

prediction_engine_v33 = PredictionEngineV33()
