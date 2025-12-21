"""
Dynamic variance modeling for NCAAM predictions.

v6.3: ALL DATA IS REQUIRED - no fallbacks, no defaults.
Adjusts sigma based on shooting style and pace mismatches.
"""
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class VarianceFactors:
    """Breakdown of variance components."""
    base_variance: float
    three_pt_adjustment: float
    pace_adjustment: float
    total_variance: float

    @property
    def sigma(self) -> float:
        return self.total_variance


class DynamicVarianceCalculator:
    """
    Calculates game-specific variance based on team profiles.

    v6.3: ALL FIELDS REQUIRED - no fallbacks to league averages.
    TeamRatings now guarantees all 22 fields are present.

    Higher variance expected for:
    - High 3-point rate teams (more volatile scoring)
    - Large pace mismatches (uncertain tempo)
    """

    def __init__(
        self,
        base_sigma: float = 11.0,
        three_pt_variance_factor: float = 0.15,
        pace_variance_factor: float = 0.10,
        min_sigma: float = 9.0,
        max_sigma: float = 14.0,
        enabled: bool = True,
    ):
        self.base_sigma = base_sigma
        self.three_pt_variance_factor = three_pt_variance_factor
        self.pace_variance_factor = pace_variance_factor
        self.min_sigma = min_sigma
        self.max_sigma = max_sigma
        self.enabled = enabled

    def calculate_game_variance(
        self,
        home_three_pt_rate: float,
        away_three_pt_rate: float,
        home_tempo: float,
        away_tempo: float,
    ) -> VarianceFactors:
        """
        Calculate game-specific variance.

        v6.3: ALL PARAMETERS ARE REQUIRED - no Optional, no fallbacks.

        Args:
            home_three_pt_rate: Home team's 3-point attempt rate (%) - REQUIRED
            away_three_pt_rate: Away team's 3-point attempt rate (%) - REQUIRED
            home_tempo: Home team's tempo - REQUIRED
            away_tempo: Away team's tempo - REQUIRED

        Returns:
            VarianceFactors with breakdown and total sigma
        """
        if not self.enabled:
            return VarianceFactors(
                base_variance=self.base_sigma,
                three_pt_adjustment=0.0,
                pace_adjustment=0.0,
                total_variance=self.base_sigma,
            )

        # 3-point rate adjustment - NO FALLBACKS, data is REQUIRED
        avg_3pr = (home_three_pt_rate + away_three_pt_rate) / 2

        # Higher 3PR = more variance (35% is league average baseline)
        league_avg_3pr = 35.0
        three_pt_adj = (avg_3pr - league_avg_3pr) * self.three_pt_variance_factor

        # Pace mismatch adjustment
        tempo_diff = abs(home_tempo - away_tempo)
        pace_adj = tempo_diff * self.pace_variance_factor

        # Total variance (clamped)
        total = self.base_sigma + three_pt_adj + pace_adj
        total = max(self.min_sigma, min(self.max_sigma, total))

        logger.debug(
            f"Variance: base={self.base_sigma:.1f}, 3pr_adj={three_pt_adj:+.2f} "
            f"(avg_3pr={avg_3pr:.1f}%), pace_adj={pace_adj:+.2f} "
            f"(diff={tempo_diff:.1f}), total={total:.2f}"
        )

        return VarianceFactors(
            base_variance=self.base_sigma,
            three_pt_adjustment=round(three_pt_adj, 3),
            pace_adjustment=round(pace_adj, 3),
            total_variance=round(total, 2),
        )

    def calculate_1h_variance(
        self,
        full_game_variance: VarianceFactors,
        multiplier: float = 1.15,
    ) -> float:
        """
        Calculate 1H variance (higher than full game).

        First half has more variance due to:
        - Less time for regression to mean
        - Sample size effects
        """
        return min(
            self.max_sigma * multiplier,
            full_game_variance.total_variance * multiplier,
        )
