"""
Enhanced first half prediction logic.

v6.3: ALL DATA IS REQUIRED - no fallbacks, no defaults.
Adjusts 1H tempo factor and margin scaling based on matchup profile.
"""
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FirstHalfFactors:
    """Dynamic first half calculation factors."""
    tempo_factor: float  # Base: 0.48
    margin_scale: float  # Base: 0.50
    confidence_scale: float  # Base: 0.90
    efg_differential: float  # Home EFG - Away EFG
    reasoning: str


class EnhancedFirstHalfCalculator:
    """
    Dynamic first half predictions based on matchup profiles.

    v6.3: ALL FIELDS REQUIRED - no fallbacks to league averages.
    TeamRatings now guarantees all 22 fields are present.

    When one team has much better shooting efficiency (EFG):
    - They score more consistently in 1H
    - Adjust tempo factor and margin scaling
    """

    # League average for EFG (used for relative calculations, not fallbacks)
    LEAGUE_AVG_EFG = 50.0

    def __init__(
        self,
        base_tempo_factor: float = 0.48,
        base_margin_scale: float = 0.50,
        base_confidence_scale: float = 0.90,
        efg_tempo_adjustment: float = 0.005,  # Per % EFG above avg
        efg_margin_adjustment: float = 0.01,  # Per % EFG diff
        max_tempo_factor: float = 0.52,
        min_tempo_factor: float = 0.44,
        max_margin_scale: float = 0.55,
        min_margin_scale: float = 0.45,
        enabled: bool = True,
    ):
        self.base_tempo_factor = base_tempo_factor
        self.base_margin_scale = base_margin_scale
        self.base_confidence_scale = base_confidence_scale
        self.efg_tempo_adjustment = efg_tempo_adjustment
        self.efg_margin_adjustment = efg_margin_adjustment
        self.max_tempo_factor = max_tempo_factor
        self.min_tempo_factor = min_tempo_factor
        self.max_margin_scale = max_margin_scale
        self.min_margin_scale = min_margin_scale
        self.enabled = enabled

    def calculate_factors(
        self,
        home_efg: float,
        away_efg: float,
        home_tempo: float,
        away_tempo: float,
    ) -> FirstHalfFactors:
        """
        Calculate dynamic 1H factors based on matchup.

        v6.3: ALL PARAMETERS ARE REQUIRED - no Optional, no fallbacks.

        Args:
            home_efg: Home team EFG% - REQUIRED
            away_efg: Away team EFG% - REQUIRED
            home_tempo: Home team tempo - REQUIRED
            away_tempo: Away team tempo - REQUIRED

        Returns:
            FirstHalfFactors with dynamic tempo and margin scales
        """
        if not self.enabled:
            return FirstHalfFactors(
                tempo_factor=self.base_tempo_factor,
                margin_scale=self.base_margin_scale,
                confidence_scale=self.base_confidence_scale,
                efg_differential=0.0,
                reasoning="Dynamic 1H disabled, using base factors",
            )

        # EFG differential (positive = home has better shooting)
        # v6.3: NO FALLBACKS - data is REQUIRED
        efg_diff = home_efg - away_efg

        # Tempo factor adjustment
        # Higher-scoring matchups (better shooters) tend to have more 1H scoring
        avg_efg = (home_efg + away_efg) / 2
        efg_above_avg = avg_efg - self.LEAGUE_AVG_EFG

        tempo_adj = efg_above_avg * self.efg_tempo_adjustment
        tempo_factor = max(
            self.min_tempo_factor,
            min(self.max_tempo_factor, self.base_tempo_factor + tempo_adj),
        )

        # Margin scale adjustment
        # Larger EFG gaps = skill shows up faster in 1H
        efg_gap = abs(efg_diff)
        margin_adj = efg_gap * self.efg_margin_adjustment
        margin_scale = max(
            self.min_margin_scale,
            min(self.max_margin_scale, self.base_margin_scale + margin_adj),
        )

        # Confidence adjustment (larger gaps = more confident in 1H prediction)
        if efg_gap > 5.0:
            confidence_scale = min(0.95, self.base_confidence_scale + 0.02)
        elif efg_gap < 2.0:
            confidence_scale = max(0.85, self.base_confidence_scale - 0.02)
        else:
            confidence_scale = self.base_confidence_scale

        reasoning = (
            f"EFG diff={efg_diff:+.1f}% (home={home_efg:.1f}%, away={away_efg:.1f}%), "
            f"tempo_factor={tempo_factor:.3f}, margin_scale={margin_scale:.3f}"
        )

        logger.debug(f"1H factors: {reasoning}")

        return FirstHalfFactors(
            tempo_factor=round(tempo_factor, 4),
            margin_scale=round(margin_scale, 4),
            confidence_scale=round(confidence_scale, 3),
            efg_differential=round(efg_diff, 2),
            reasoning=reasoning,
        )
