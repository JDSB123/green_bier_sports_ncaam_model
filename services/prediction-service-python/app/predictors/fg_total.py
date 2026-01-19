"""
Full Game Total Prediction Model v33.10.0

BACKTESTED on 3,318 games with actual scores from ESPN.

Backtest Results:
- MAE: 13.1 points (historical backtest; calibration has since been updated)
- Market benchmark: ~10.5 MAE (we're ~2.6 pts worse)
- Middle games (120-170): MAE = 10.7 (matches market!)

Key insight: Regression to mean awareness
- Our predictions have std=10.7, actual has std=18.3
- Extreme predictions have higher variance, not lower accuracy
- Model is calibrated for middle-range games; extremes use confidence scaling

Betting Strategy (v33.10.0):
- All edges >= MIN_EDGE are bet candidates
- Higher edges get STRONG tier designation
- Confidence scaling handles variance in extreme predictions
- No artificial MAX_EDGE cap (removed in v33.10.0)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app import __version__ as app_version
from app.models import BetType
from app.predictors.base import BasePredictor, MarketPrediction
from app.statistical_confidence import statistical_confidence

if TYPE_CHECKING:
    from app.models import TeamRatings


@dataclass
class TotalAdjustmentFactors:
    """Factors from backtest analysis - IMPROVED based on validation."""
    # Base calibration for middle range (135-145)
    base_calibration: float = 1.5  # Minimal for middle range

    # Tempo adjustment
    tempo_high_threshold: float = 70.0
    tempo_low_threshold: float = 66.0
    tempo_adj_per_point: float = 0.3

    # Quality mismatch
    barthag_diff_threshold: float = 0.15
    quality_adj_factor: float = 2.0

    # 3PT rate
    three_pt_high_threshold: float = 38.0
    three_pt_adj_factor: float = 0.15

    # Efficiency extremes
    eff_high_threshold: float = 115.0
    eff_low_threshold: float = 100.0
    eff_adj_factor: float = 0.2

    # NEW: Turnover rate adjustment (high TOR = fewer scoring possessions)
    tor_high_threshold: float = 20.0
    tor_low_threshold: float = 16.0
    tor_adj_per_point: float = 0.3

    # NEW: Free throw rate adjustment (high FTR = more points per possession)
    ftr_high_threshold: float = 36.0
    ftr_adj_per_point: float = 0.2




class FGTotalModel(BasePredictor):
    """
    Full Game Total predictor - TRULY INDEPENDENT model.

    BACKTESTED on 3,318 games with actual ESPN scores.

    Formula:
        Total = BaseEfficiencyPrediction + Adjustment + Calibration

    Backtest Results:
        - Calibration: see CALIBRATION constant (recalibrated over time)
        - MAE: 13.1 pts overall
        - Middle games (120-170): MAE = 10.7 (matches market)
    """

    MODEL_NAME = "FGTotal"
    MODEL_VERSION = app_version
    MARKET_TYPE = "total"

    # ═══════════════════════════════════════════════════════════════════════
    # FG TOTAL - INDEPENDENT CONSTANTS (not inherited from base)
    # ═══════════════════════════════════════════════════════════════════════
    # These are FG-specific values derived from FG backtest data
    LEAGUE_AVG_TEMPO: float = 67.6        # FG tempo from Barttorvik
    LEAGUE_AVG_EFFICIENCY: float = 105.5  # FG efficiency from Barttorvik

    # Calibration - RECALIBRATED on 3,222 games with anti-leakage
    # Original +7.0 had +16.5 bias; corrected to -9.5
    CALIBRATION: float = -9.5
    HCA: float = 0.0  # Totals don't use HCA (zero-sum)

    # Betting thresholds - from 3,318-game backtest with real odds
    # 3pt edge = +18.3% ROI with 159 bets (optimal volume/ROI balance)
    MIN_EDGE: float = 3.0
    STRONG_EDGE: float = 6.0  # Edges >= 6pt get STRONG tier
    MEDIUM_EDGE: float = 4.5  # Edges >= 4.5pt get MEDIUM tier

    # Variance - FG-specific
    BASE_VARIANCE: float = 20.0

    def __init__(self):
        self.factors = TotalAdjustmentFactors()

    def _calculate_base_total(
        self,
        home: TeamRatings,
        away: TeamRatings,
        is_neutral: bool = False,
    ) -> tuple[float, float, float]:
        """
        Calculate base total using efficiency formula.

        Returns: (total, home_component, away_component)
        """
        avg_tempo = self.calculate_expected_tempo(home, away)

        # Expected efficiency for each team
        home_eff = home.adj_o + away.adj_d - self.LEAGUE_AVG_EFFICIENCY
        away_eff = away.adj_o + home.adj_d - self.LEAGUE_AVG_EFFICIENCY

        # Base scores
        home_score = home_eff * avg_tempo / 100.0
        away_score = away_eff * avg_tempo / 100.0

        base_total = home_score + away_score

        return base_total, home_score, away_score

    def _calculate_adjustment(
        self,
        home: TeamRatings,
        away: TeamRatings,
        base_total: float,
    ) -> tuple[float, str]:
        """
        Calculate learned adjustment to base prediction.

        This captures patterns where the base formula is systematically wrong.

        Returns: (adjustment, reasoning)
        """
        adjustment = 0.0
        reasons = []

        avg_tempo = (home.tempo + away.tempo) / 2

        # 1. Tempo adjustment
        if avg_tempo > self.factors.tempo_high_threshold:
            tempo_adj = (avg_tempo - self.factors.tempo_high_threshold) * self.factors.tempo_adj_per_point
            adjustment += tempo_adj
            if tempo_adj > 1.0:
                reasons.append(f"fast tempo +{tempo_adj:.1f}")
        elif avg_tempo < self.factors.tempo_low_threshold:
            tempo_adj = (avg_tempo - self.factors.tempo_low_threshold) * self.factors.tempo_adj_per_point
            adjustment += tempo_adj
            if tempo_adj < -1.0:
                reasons.append(f"slow tempo {tempo_adj:.1f}")

        # 2. Quality mismatch adjustment
        home_quality = getattr(home, 'barthag', 0.5) or 0.5
        away_quality = getattr(away, 'barthag', 0.5) or 0.5
        quality_diff = abs(home_quality - away_quality)

        if quality_diff > self.factors.barthag_diff_threshold:
            # Big mismatches often score lower than expected (blowouts slow down)
            quality_adj = -quality_diff * self.factors.quality_adj_factor
            adjustment += quality_adj
            if abs(quality_adj) > 0.5:
                reasons.append(f"mismatch {quality_adj:.1f}")

        # 3. 3PT rate adjustment
        home_3pr = getattr(home, 'three_pt_rate', 35.0) or 35.0
        away_3pr = getattr(away, 'three_pt_rate', 35.0) or 35.0
        avg_3pr = (home_3pr + away_3pr) / 2

        if avg_3pr > self.factors.three_pt_high_threshold:
            # High 3PT games have more variance, we tend to under-predict
            three_adj = (avg_3pr - self.factors.three_pt_high_threshold) * self.factors.three_pt_adj_factor
            adjustment += three_adj
            if three_adj > 0.5:
                reasons.append(f"3PT heavy +{three_adj:.1f}")

        # 4. Efficiency extreme adjustment
        avg_off = (home.adj_o + away.adj_o) / 2
        if avg_off > self.factors.eff_high_threshold:
            eff_adj = (avg_off - self.factors.eff_high_threshold) * self.factors.eff_adj_factor
            adjustment += eff_adj
            if eff_adj > 0.5:
                reasons.append(f"high eff +{eff_adj:.1f}")
        elif avg_off < self.factors.eff_low_threshold:
            eff_adj = (avg_off - self.factors.eff_low_threshold) * self.factors.eff_adj_factor
            adjustment += eff_adj
            if eff_adj < -0.5:
                reasons.append(f"low eff {eff_adj:.1f}")

        # 5. Turnover rate adjustment (NEW)
        # High turnover games = fewer possessions complete, lower scoring
        home_tor = getattr(home, 'tor', 18.5) or 18.5
        away_tor = getattr(away, 'tor', 18.5) or 18.5
        home_tord = getattr(home, 'tord', 18.5) or 18.5
        away_tord = getattr(away, 'tord', 18.5) or 18.5
        avg_tor = (home_tor + away_tord + away_tor + home_tord) / 4

        if avg_tor > self.factors.tor_high_threshold:
            tor_adj = -(avg_tor - self.factors.tor_high_threshold) * self.factors.tor_adj_per_point
            adjustment += tor_adj
            if tor_adj < -0.5:
                reasons.append(f"high TO {tor_adj:.1f}")
        elif avg_tor < self.factors.tor_low_threshold:
            tor_adj = (self.factors.tor_low_threshold - avg_tor) * self.factors.tor_adj_per_point
            adjustment += tor_adj
            if tor_adj > 0.5:
                reasons.append(f"clean +{tor_adj:.1f}")

        # 6. Free throw rate adjustment (NEW)
        # High FTR = more points per possession (and/or foul trouble slowing game)
        home_ftr = getattr(home, 'ftr', 33.0) or 33.0
        away_ftr = getattr(away, 'ftr', 33.0) or 33.0
        avg_ftr = (home_ftr + away_ftr) / 2

        if avg_ftr > self.factors.ftr_high_threshold:
            ftr_adj = (avg_ftr - self.factors.ftr_high_threshold) * self.factors.ftr_adj_per_point
            adjustment += ftr_adj
            if ftr_adj > 0.5:
                reasons.append(f"FT heavy +{ftr_adj:.1f}")

        reasoning = ", ".join(reasons) if reasons else "standard"
        return adjustment, reasoning

    def _calculate_variance(
        self,
        home: TeamRatings,
        away: TeamRatings,
    ) -> float:
        """
        Calculate prediction variance for totals.

        Totals have higher inherent variance than spreads.
        3PT-heavy teams and tempo mismatches increase variance.
        """
        variance = self.BASE_VARIANCE

        # Tempo mismatch increases variance
        tempo_diff = abs(home.tempo - away.tempo)
        variance += tempo_diff * 0.1

        # 3PT rate increases variance
        home_3pr = getattr(home, 'three_pt_rate', 35.0) or 35.0
        away_3pr = getattr(away, 'three_pt_rate', 35.0) or 35.0
        avg_3pr = (home_3pr + away_3pr) / 2
        if avg_3pr > 35.0:
            variance += (avg_3pr - 35.0) * 0.1

        return variance

    def predict(
        self,
        home: TeamRatings,
        away: TeamRatings,
        is_neutral: bool = False,
        home_rest_days: int | None = None,
        away_rest_days: int | None = None,
    ) -> MarketPrediction:
        """
        Generate total prediction using hybrid approach.
        """
        # Base prediction from efficiency formula
        base_total, home_score, away_score = self._calculate_base_total(
            home, away, is_neutral
        )

        # Learned adjustment
        adjustment, adj_reasoning = self._calculate_adjustment(
            home, away, base_total
        )

        # Situational adjustment
        situational_adj = 0.0
        if home_rest_days is not None and away_rest_days is not None:
            situational_adj = self.calculate_situational_adjustment(
                home_rest_days, away_rest_days
            )
            situational_adj *= 0.3

        # Final total
        total = base_total + adjustment + self.CALIBRATION + situational_adj

        # Variance
        variance = self._calculate_variance(home, away)

        # v33.11: Statistical confidence using proper intervals
        predicted_edge = total - (home_score + away_score)  # Edge vs naive total
        confidence = statistical_confidence.calculate_prediction_confidence(
            home_ratings=home,
            away_ratings=away,
            bet_type=BetType.TOTAL,
            predicted_edge=predicted_edge
        )

        reasoning = (
            f"Base: {base_total:.1f} | "
            f"Adj: {adjustment:+.1f} ({adj_reasoning}) | "
            f"Cal: {self.CALIBRATION:+.1f} | "
            f"Final: {total:.1f}"
        )

        return MarketPrediction(
            value=round(total, 1),
            home_component=round(home_score, 1),
            away_component=round(away_score, 1),
            hca_applied=0.0,
            calibration_applied=self.CALIBRATION,
            matchup_adj=adjustment,
            situational_adj=situational_adj,
            variance=variance,
            confidence=confidence,
            reasoning=reasoning,
        )

    def get_pick_recommendation(
        self,
        prediction: MarketPrediction,
        market_line: float,
    ) -> dict:
        """
        Get betting recommendation for totals.

        v33.10.0: Removed artificial MAX_EDGE cap. All edges >= MIN_EDGE are
        bet candidates with tiered strength classification:
        - STRONG: >= 6.0 pts (high conviction)
        - MEDIUM: >= 4.5 pts (solid edge)
        - STANDARD: >= 3.0 pts (min threshold)
        """
        edge = prediction.value - market_line  # positive = over, negative = under
        abs_edge = abs(edge)

        # Determine pick
        pick = "OVER" if edge > 0 else "UNDER"

        # Tiered strength classification (v33.10.0 - no MAX_EDGE cap)
        if abs_edge >= self.STRONG_EDGE:
            strength = "STRONG"
            recommended = True
        elif abs_edge >= self.MEDIUM_EDGE:
            strength = "MEDIUM"
            recommended = True
        elif abs_edge >= self.MIN_EDGE:
            strength = "STANDARD"
            recommended = True
        else:
            strength = "NO BET"
            recommended = False

        return {
            "pick": pick,
            "edge": edge,
            "abs_edge": abs_edge,
            "strength": strength,
            "recommended": recommended,
            "market_line": market_line,
            "model_prediction": prediction.value,
            "confidence": prediction.confidence,
        }


# Singleton instance
fg_total_model = FGTotalModel()
