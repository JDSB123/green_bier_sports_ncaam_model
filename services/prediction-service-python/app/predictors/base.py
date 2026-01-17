"""
Base Predictor Class for Modular Models

All market-specific models inherit from this base class.
Each model has its own calibration, formula, and validation metrics.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

# Use TYPE_CHECKING to avoid circular imports
# TeamRatings is defined in app.models (the parent module)
if TYPE_CHECKING:
    pass


@dataclass
class MarketPrediction:
    """
    Prediction for a single market.

    Each model returns this standardized output.
    """
    value: float              # The prediction (spread, total, etc.)
    home_component: float     # Home team contribution
    away_component: float     # Away team contribution
    hca_applied: float        # Home court advantage applied
    calibration_applied: float  # Calibration adjustment applied
    matchup_adj: float        # Matchup-specific adjustment
    situational_adj: float    # Rest/travel adjustments
    variance: float           # Estimated variance (sigma)
    confidence: float         # Model confidence (0-1)
    reasoning: str            # Human-readable explanation


class BasePredictor(ABC):
    """
    Abstract base class for all prediction models.

    Each market-specific model must implement:
    - predict(): Generate prediction for matchup
    - get_edge(): Calculate edge vs market line
    - validate(): Run validation metrics

    Uses ALL 22 Barttorvik fields for maximum accuracy.
    """

    # Model identification
    MODEL_NAME: str = "base"
    MODEL_VERSION: str = "0.0.0"

    # Market type
    MARKET_TYPE: str = "unknown"  # "spread" or "total"
    IS_FIRST_HALF: bool = False

    # Calibration parameters (to be overridden)
    HCA: float = 0.0              # Home court advantage
    CALIBRATION: float = 0.0      # Bias correction

    # League averages (from Barttorvik)
    # Each model should override these with market-specific values
    LEAGUE_AVG_TEMPO: float = 67.6
    LEAGUE_AVG_EFFICIENCY: float = 105.5
    LEAGUE_AVG_ORB: float = 28.0
    LEAGUE_AVG_TOR: float = 18.5
    LEAGUE_AVG_FTR: float = 33.0
    LEAGUE_AVG_3PR: float = 35.0

    # Matchup adjustment factors
    REBOUND_FACTOR: float = 0.15   # Points per % rebounding edge
    TURNOVER_FACTOR: float = 0.10  # Points per % turnover edge
    FT_FACTOR: float = 0.15        # Points per % FT rate edge

    # Variance parameters
    BASE_VARIANCE: float = 11.0

    def __init__(self, **config_overrides):
        """
        Initialize model with optional config overrides.

        Args:
            config_overrides: Override default calibration parameters
        """
        for key, value in config_overrides.items():
            if hasattr(self, key.upper()):
                setattr(self, key.upper(), value)

    @abstractmethod
    def predict(
        self,
        home: Any,  # TeamRatings
        away: Any,  # TeamRatings
        is_neutral: bool = False,
        home_rest_days: int | None = None,
        away_rest_days: int | None = None,
    ) -> MarketPrediction:
        """
        Generate prediction for this market.

        Args:
            home: Home team Barttorvik ratings (ALL 22 fields)
            away: Away team Barttorvik ratings (ALL 22 fields)
            is_neutral: True if neutral site game
            home_rest_days: Days since home team's last game
            away_rest_days: Days since away team's last game

        Returns:
            MarketPrediction with value, components, and confidence
        """
        pass

    def get_edge(self, prediction: float, market_line: float) -> float:
        """
        Calculate edge vs market line.

        For spreads: edge = |prediction - market| when on correct side
        For totals: edge = |prediction - market| when on correct side

        Returns positive edge if model favors a bet.
        """
        return abs(prediction - market_line)

    def calculate_expected_tempo(self, home: Any, away: Any) -> float:
        """
        Calculate expected game tempo.

        Formula: Home_Tempo + Away_Tempo - League_Avg_Tempo
        """
        return home.tempo + away.tempo - self.LEAGUE_AVG_TEMPO

    def calculate_expected_efficiency(
        self,
        offense: Any,  # TeamRatings
        defense: Any   # TeamRatings
    ) -> float:
        """
        Calculate expected efficiency for one team.

        Formula: Off_AdjO + Def_AdjD - League_Avg_Eff

        Args:
            offense: Team on offense
            defense: Team on defense

        Returns:
            Expected points per 100 possessions
        """
        return offense.adj_o + defense.adj_d - self.LEAGUE_AVG_EFFICIENCY

    def calculate_base_score(
        self,
        efficiency: float,
        tempo: float
    ) -> float:
        """
        Calculate expected score from efficiency and tempo.

        Formula: Efficiency * Tempo / 100
        """
        return efficiency * tempo / 100.0

    def calculate_matchup_adjustment(
        self,
        home: Any,  # TeamRatings
        away: Any   # TeamRatings
    ) -> float:
        """
        Calculate matchup-specific adjustments based on Four Factors.

        Returns points to ADD to home margin (positive = home advantage).

        Uses:
        - Rebounding edge (ORB vs opponent DRB)
        - Turnover edge (TOR vs opponent TORD)
        - Free throw edge (FTR vs opponent FTRD)
        """
        adjustment = 0.0

        # 1. Rebounding Edge
        home_orb_adv = (home.orb - self.LEAGUE_AVG_ORB) + ((100 - away.drb) - self.LEAGUE_AVG_ORB)
        away_orb_adv = (away.orb - self.LEAGUE_AVG_ORB) + ((100 - home.drb) - self.LEAGUE_AVG_ORB)
        net_orb_edge = home_orb_adv - away_orb_adv
        adjustment += net_orb_edge * self.REBOUND_FACTOR

        # 2. Turnover Edge
        exp_home_tor = self.LEAGUE_AVG_TOR + (home.tor - self.LEAGUE_AVG_TOR) + (away.tord - self.LEAGUE_AVG_TOR)
        exp_away_tor = self.LEAGUE_AVG_TOR + (away.tor - self.LEAGUE_AVG_TOR) + (home.tord - self.LEAGUE_AVG_TOR)
        net_tor_edge = exp_away_tor - exp_home_tor  # Positive = home commits fewer TOs
        adjustment += net_tor_edge * self.TURNOVER_FACTOR

        # 3. Free Throw Edge
        exp_home_ftr = self.LEAGUE_AVG_FTR + (home.ftr - self.LEAGUE_AVG_FTR) + (away.ftrd - self.LEAGUE_AVG_FTR)
        exp_away_ftr = self.LEAGUE_AVG_FTR + (away.ftr - self.LEAGUE_AVG_FTR) + (home.ftrd - self.LEAGUE_AVG_FTR)
        net_ftr_edge = exp_home_ftr - exp_away_ftr
        adjustment += net_ftr_edge * self.FT_FACTOR

        return adjustment

    def calculate_situational_adjustment(
        self,
        home_rest_days: int | None,
        away_rest_days: int | None,
    ) -> float:
        """
        Calculate rest-based situational adjustment.

        Returns points to ADD to home margin.

        - B2B (0 rest days): -2.0 points
        - 1 day rest: -0.5 points
        - Rest differential: 0.5 points per day difference (max 2.0)
        """
        adj = 0.0

        if home_rest_days is not None:
            if home_rest_days == 0:
                adj -= 2.0  # B2B penalty for home
            elif home_rest_days == 1:
                adj -= 0.5

        if away_rest_days is not None:
            if away_rest_days == 0:
                adj += 2.0  # B2B penalty for away = home advantage
            elif away_rest_days == 1:
                adj += 0.5

        # Rest differential
        if home_rest_days is not None and away_rest_days is not None:
            rest_diff = home_rest_days - away_rest_days
            adj += min(2.0, max(-2.0, rest_diff * 0.5))

        return adj

    def calculate_variance(self, home: Any, away: Any) -> float:
        """
        Calculate expected variance (sigma) for this game.

        Higher variance for:
        - 3P-heavy teams (higher variance in scoring)
        - Pace differential (more possessions = more variance)
        """
        base = self.BASE_VARIANCE

        # 3P variance adjustment
        avg_3pr = (home.three_pt_rate + away.three_pt_rate) / 2
        three_pt_adj = (avg_3pr - self.LEAGUE_AVG_3PR) * 0.05

        # Pace differential adjustment
        pace_diff = abs(home.tempo - away.tempo)
        pace_adj = pace_diff * 0.1

        return base + three_pt_adj + pace_adj

    def __repr__(self) -> str:
        return f"{self.MODEL_NAME} v{self.MODEL_VERSION} ({self.MARKET_TYPE})"
