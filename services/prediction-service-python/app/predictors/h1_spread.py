"""
First Half Spread Model v33.10.0

BACKTESTED on 904 real 1H games from ESPN (2019-2024).
HCA calibration derived from actual 1H home margins.

Backtest Results:
- MAE: 8.25 points
- Direction Accuracy: 66.6%
- Actual avg 1H home margin: +4.62 points
- Optimal HCA: 3.6 (from 1H backtest)

First half dynamics differ from full game:
- Fewer possessions (less variance normalization)
- Early game pace varies more
- EFG differential shows up faster (skill advantage)

Formula:
    1H_Spread = -(Home_Margin_1H + HCA_1H + Situational_1H + Matchup_1H)
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from app import __version__ as APP_VERSION
from app.predictors.base import BasePredictor, MarketPrediction

if TYPE_CHECKING:
    from app.models import TeamRatings


class H1SpreadModel(BasePredictor):
    """
    First Half Spread Prediction Model - TRULY INDEPENDENT.

    BACKTESTED on 904 real 1H games (2019-2024) from ESPN.

    Backtest Results (v33.6.5):
    - MAE: 8.25 points
    - Direction Accuracy: 66.6%
    - HCA derived from actual 1H home margins (+4.62 avg)
    """

    MODEL_NAME = "H1Spread"
    MODEL_VERSION = APP_VERSION
    MARKET_TYPE = "spread"
    IS_FIRST_HALF = True

    # ═══════════════════════════════════════════════════════════════════════
    # 1H SPREAD - INDEPENDENT CONSTANTS (not inherited from base)
    # ═══════════════════════════════════════════════════════════════════════
    # These are 1H-specific values derived from 1H backtest
    LEAGUE_AVG_TEMPO: float = 67.6        # FG tempo (used for base calc)
    LEAGUE_AVG_EFFICIENCY: float = 105.5  # FG efficiency (used for base calc)
    LEAGUE_AVG_EFG: float = 50.0          # 1H-specific EFG reference

    # 1H HOME COURT ADVANTAGE - independently backtested (904 real 1H games)
    # Keep this aligned with docs/config (`MODEL__HOME_COURT_ADVANTAGE_SPREAD_1H`) and
    # the "manual-only" run orchestration in `run_today.py`.
    HCA: float = 3.6

    # 1H SCALING FACTORS
    BASE_TEMPO_FACTOR: float = 0.48      # 1H has ~48% of FG possessions
    BASE_MARGIN_SCALE: float = 0.50      # Margins scale by ~50%

    # EFG-based adjustments for 1H
    EFG_TEMPO_ADJUSTMENT: float = 0.005  # Per % EFG above average
    EFG_MARGIN_ADJUSTMENT: float = 0.01  # Per % EFG differential

    # 1H-specific variance (higher than FG)
    BASE_VARIANCE: float = 12.65  # ~15% higher than FG spread variance

    # Betting thresholds - 1H specific
    MIN_EDGE: float = 3.5

    def predict(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        is_neutral: bool = False,
        home_rest_days: Optional[int] = None,
        away_rest_days: Optional[int] = None,
    ) -> MarketPrediction:
        """
        Generate first half spread prediction.

        Uses dynamic factors based on EFG differential:
        - Higher EFG teams score more consistently in 1H
        - Larger EFG gaps show up faster

        Args:
            home: Home team Barttorvik ratings
            away: Away team Barttorvik ratings
            is_neutral: True if neutral site
            home_rest_days: Days since last game
            away_rest_days: Days since last game

        Returns:
            MarketPrediction for 1H spread
        """
        # 1. Calculate dynamic 1H factors based on EFG
        tempo_factor, margin_scale = self._calculate_dynamic_factors(home, away)

        # 2. Calculate expected tempo (full game)
        fg_tempo = self.calculate_expected_tempo(home, away)

        # 3. Calculate efficiencies
        home_eff = self.calculate_expected_efficiency(home, away)
        away_eff = self.calculate_expected_efficiency(away, home)

        # 4. Calculate 1H base scores (scaled by tempo factor)
        home_base_1h = self.calculate_base_score(home_eff, fg_tempo) * tempo_factor
        away_base_1h = self.calculate_base_score(away_eff, fg_tempo) * tempo_factor

        # 5. Raw 1H margin
        raw_margin_1h = home_base_1h - away_base_1h

        # 6. Apply HCA (1H specific)
        hca_1h = 0.0 if is_neutral else self.HCA

        # 7. Calculate matchup adjustment (scaled for 1H)
        fg_matchup = self.calculate_matchup_adjustment(home, away)
        matchup_1h = fg_matchup * margin_scale

        # 8. Situational adjustment (scaled for 1H)
        fg_sit = self.calculate_situational_adjustment(home_rest_days, away_rest_days)
        sit_1h = fg_sit * margin_scale

        # 9. Calculate 1H spread
        spread_1h = -(raw_margin_1h + hca_1h + matchup_1h + sit_1h)

        # 10. Calculate 1H variance (higher than FG)
        variance_1h = self._calculate_1h_variance(home, away)

        # 11. Calculate confidence
        confidence = self._calculate_confidence(home, away, margin_scale)

        # EFG differential for reporting
        efg_diff = home.efg - away.efg

        reasoning = (
            f"1H Margin: {raw_margin_1h:+.1f} | HCA: {hca_1h:+.1f} | "
            f"EFG diff: {efg_diff:+.1f}% | Scale: {margin_scale:.2f} | "
            f"Final: {spread_1h:+.1f}"
        )

        return MarketPrediction(
            value=round(spread_1h, 1),
            home_component=round(home_base_1h, 2),
            away_component=round(away_base_1h, 2),
            hca_applied=hca_1h,
            calibration_applied=0.0,
            matchup_adj=round(matchup_1h, 2),
            situational_adj=round(sit_1h, 2),
            variance=round(variance_1h, 2),
            confidence=round(confidence, 3),
            reasoning=reasoning,
        )

    def _calculate_dynamic_factors(
        self,
        home: "TeamRatings",
        away: "TeamRatings"
    ) -> tuple[float, float]:
        """
        Calculate dynamic 1H factors based on EFG differential.

        Higher EFG = more 1H scoring (shooting efficiency shows early)
        Larger EFG gap = skill shows up faster in 1H

        Returns:
            (tempo_factor, margin_scale) tuple
        """
        # Average EFG for this game
        avg_efg = (home.efg + away.efg) / 2
        efg_above_avg = avg_efg - self.LEAGUE_AVG_EFG

        # EFG differential
        efg_diff = abs(home.efg - away.efg)

        # Tempo factor adjustment
        # Higher EFG = slightly more 1H scoring
        tempo_adj = efg_above_avg * self.EFG_TEMPO_ADJUSTMENT
        tempo_factor = max(0.44, min(0.52, self.BASE_TEMPO_FACTOR + tempo_adj))

        # Margin scale adjustment
        # Larger EFG gaps show up faster in 1H
        margin_adj = efg_diff * self.EFG_MARGIN_ADJUSTMENT
        margin_scale = max(0.45, min(0.55, self.BASE_MARGIN_SCALE + margin_adj))

        return tempo_factor, margin_scale

    def _calculate_1h_variance(
        self,
        home: "TeamRatings",
        away: "TeamRatings"
    ) -> float:
        """
        Calculate 1H spread variance.

        Higher than FG because:
        - Fewer possessions (less regression to mean)
        - Early game pace varies more
        - 3P shooting has higher variance impact
        """
        base = self.BASE_VARIANCE

        # 3P variance (amplified for 1H)
        avg_3pr = (home.three_pt_rate + away.three_pt_rate) / 2
        three_pt_adj = (avg_3pr - 35.0) * 0.08

        # EFG variance (mismatches = higher variance in 1H)
        efg_diff = abs(home.efg - away.efg)
        efg_adj = efg_diff * 0.1

        return base + three_pt_adj + efg_adj

    def _calculate_confidence(
        self,
        home: "TeamRatings",
        away: "TeamRatings",
        margin_scale: float
    ) -> float:
        """
        Calculate 1H spread confidence.

        Lower than FG spread because:
        - Higher variance in 1H
        - Less data to validate 1H specific patterns

        Higher when:
        - Large EFG gap (skill shows clearly in 1H)
        - High margin scale (1H prediction is more differentiated)
        """
        # Start lower than FG
        confidence = 0.65

        # EFG gap factor
        efg_diff = abs(home.efg - away.efg)
        if efg_diff > 5:
            confidence += 0.05
        elif efg_diff < 2:
            confidence -= 0.03

        # Margin scale factor
        if margin_scale > 0.52:
            confidence += 0.03
        elif margin_scale < 0.47:
            confidence -= 0.03

        # Team quality
        avg_rank = (home.rank + away.rank) / 2
        if avg_rank < 100:
            confidence += 0.02
        elif avg_rank > 250:
            confidence -= 0.02

        return min(0.88, max(0.50, confidence))

    def get_pick_recommendation(
        self,
        prediction: MarketPrediction,
        market_line: float
    ) -> dict:
        """
        Get betting recommendation for 1H spread.
        """
        model_spread = prediction.value
        edge = abs(model_spread - market_line)

        if model_spread < market_line:
            pick = "HOME"
        else:
            pick = "AWAY"

        if edge >= 7:
            strength = "STRONG"
            recommended = True
        elif edge >= self.MIN_EDGE:
            strength = "MODERATE"
            recommended = True
        elif edge >= 2:
            strength = "WEAK"
            recommended = False
        else:
            strength = "NO BET"
            recommended = False

        return {
            "pick": pick,
            "model_line": model_spread,
            "market_line": market_line,
            "edge": round(edge, 1),
            "strength": strength,
            "recommended": recommended,
            "confidence": prediction.confidence,
            "reasoning": prediction.reasoning,
        }


# Singleton instance
h1_spread_model = H1SpreadModel()
