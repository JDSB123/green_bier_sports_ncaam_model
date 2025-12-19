"""
Domain models for NCAA Basketball Prediction Service v5.0.

Clean, simple data structures focused on what matters for profitable predictions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class BetType(str, Enum):
    """Types of bets we can recommend."""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    MONEYLINE = "MONEYLINE"
    SPREAD_1H = "SPREAD_1H"
    TOTAL_1H = "TOTAL_1H"
    MONEYLINE_1H = "MONEYLINE_1H"


class Pick(str, Enum):
    """Bet direction."""
    HOME = "HOME"
    AWAY = "AWAY"
    OVER = "OVER"
    UNDER = "UNDER"


class BetTier(str, Enum):
    """Bet sizing tier based on edge strength."""
    STANDARD = "standard"   # 1 unit
    MEDIUM = "medium"       # 2 units
    MAX = "max"             # 3 units


class GameStatus(str, Enum):
    """Game status."""
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


@dataclass(frozen=True)
class TeamRatings:
    """
    Barttorvik team ratings - the core data for predictions.

    All ratings are per 100 possessions.
    """
    team_name: str
    adj_o: float          # Adjusted offensive efficiency
    adj_d: float          # Adjusted defensive efficiency
    tempo: float          # Possessions per 40 minutes
    rank: int             # Barttorvik rank

    @property
    def net_rating(self) -> float:
        """Net efficiency rating (higher = better)."""
        return self.adj_o - self.adj_d

    def __str__(self) -> str:
        return f"{self.team_name} (#{self.rank}): O={self.adj_o:.1f} D={self.adj_d:.1f} Net={self.net_rating:+.1f}"


@dataclass(frozen=True)
class MarketOdds:
    """
    Current market odds for a game.

    All lines are from HOME team perspective:
    - Negative spread = home team favored
    - Positive spread = away team favored (home is underdog)
    """
    spread: Optional[float] = None
    spread_price: int = -110
    total: Optional[float] = None
    over_price: int = -110
    under_price: int = -110
    home_ml: Optional[int] = None
    away_ml: Optional[int] = None

    # First half
    spread_1h: Optional[float] = None
    total_1h: Optional[float] = None
    home_ml_1h: Optional[int] = None
    away_ml_1h: Optional[int] = None

    # Sharp book reference (Pinnacle/Circa)
    sharp_spread: Optional[float] = None
    sharp_total: Optional[float] = None


@dataclass
class Prediction:
    """
    Model prediction for a game.

    Clean structure focused on actionable outputs.
    """
    # Game identifiers
    game_id: UUID
    home_team: str
    away_team: str
    commence_time: datetime

    # Full game predictions
    predicted_spread: float         # Home team perspective
    predicted_total: float
    predicted_home_score: float
    predicted_away_score: float
    spread_confidence: float        # 0.0 to 1.0
    total_confidence: float

    # First half predictions
    predicted_spread_1h: float
    predicted_total_1h: float
    predicted_home_score_1h: float
    predicted_away_score_1h: float
    spread_confidence_1h: float
    total_confidence_1h: float

    # Moneyline (American odds)
    predicted_home_ml: int
    predicted_away_ml: int
    predicted_home_ml_1h: int
    predicted_away_ml_1h: int
    home_win_prob: float            # 0.0 to 1.0
    home_win_prob_1h: float

    # Market comparison
    market_spread: Optional[float] = None
    market_total: Optional[float] = None
    market_spread_1h: Optional[float] = None
    market_total_1h: Optional[float] = None

    # Edges (model - market)
    spread_edge: float = 0.0
    total_edge: float = 0.0
    spread_edge_1h: float = 0.0
    total_edge_1h: float = 0.0

    # Model metadata
    model_version: str = "v5.0"
    created_at: datetime = field(default_factory=datetime.utcnow)

    def calculate_edges(self, market: MarketOdds) -> None:
        """Calculate edges vs market odds."""
        self.market_spread = market.spread
        self.market_total = market.total
        self.market_spread_1h = market.spread_1h
        self.market_total_1h = market.total_1h

        if market.spread is not None:
            # Edge = how much better our line is vs market
            # If we predict -5 and market is -3, we have +2 edge on HOME
            self.spread_edge = abs(self.predicted_spread - market.spread)

        if market.total is not None:
            self.total_edge = abs(self.predicted_total - market.total)

        if market.spread_1h is not None:
            self.spread_edge_1h = abs(self.predicted_spread_1h - market.spread_1h)

        if market.total_1h is not None:
            self.total_edge_1h = abs(self.predicted_total_1h - market.total_1h)


@dataclass
class BettingRecommendation:
    """
    A recommended bet with full analysis.

    Only generated when edge exceeds threshold.
    """
    # Identifiers
    game_id: UUID
    home_team: str
    away_team: str
    commence_time: datetime

    # Bet details
    bet_type: BetType
    pick: Pick
    line: float                     # The line we're betting (spread or total)

    # Edge analysis
    model_line: float               # Our predicted line
    market_line: float              # Market consensus
    edge: float                     # Points of edge
    confidence: float               # 0.0 to 1.0

    # Expected value
    ev_percent: float               # Expected value as percentage
    implied_prob: float             # Our implied probability
    market_prob: float              # Market implied probability

    # Bet sizing (Kelly criterion)
    kelly_fraction: float           # Full Kelly bet fraction
    recommended_units: float        # Actual recommended bet (fractional Kelly)
    bet_tier: BetTier

    # Sharp alignment
    sharp_line: Optional[float] = None
    is_sharp_aligned: bool = True   # Are we aligned with sharp movement?

    # Metadata
    model_version: str = "v5.0"
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def summary(self) -> str:
        """Human-readable summary of the recommendation."""
        direction = "HOME" if self.pick in (Pick.HOME, Pick.OVER) else "AWAY"
        if self.bet_type in (BetType.TOTAL, BetType.TOTAL_1H):
            direction = "OVER" if self.pick == Pick.OVER else "UNDER"

        period = "1H" if "1H" in self.bet_type.value else "FG"
        bet_desc = self.bet_type.value.replace("_1H", "")

        # For spreads/totals show line, for moneylines show odds
        if "MONEYLINE" in self.bet_type.value:
            line_display = f"{self.line:+d}"  # Show as American odds
        else:
            line_display = f"{self.line:+.1f}"

        return (
            f"{self.away_team} @ {self.home_team} | "
            f"{period} {bet_desc} {direction} {line_display} | "
            f"Edge: {self.edge:.1f}{'%' if 'MONEYLINE' in self.bet_type.value else 'pts'} | "
            f"EV: {self.ev_percent:+.1f}% | "
            f"{self.bet_tier.value.upper()} ({self.recommended_units:.1f}u)"
        )

    @property
    def detailed_rationale(self) -> str:
        """
        Detailed rationale explaining WHY this bet is recommended.

        Includes model vs market comparison, edge analysis, and confidence indicators.
        """
        direction = "HOME" if self.pick in (Pick.HOME, Pick.OVER) else "AWAY"
        if self.bet_type in (BetType.TOTAL, BetType.TOTAL_1H):
            direction = "OVER" if self.pick == Pick.OVER else "UNDER"
            team_display = f"the {direction}"
        else:
            team_display = self.home_team if self.pick == Pick.HOME else self.away_team

        period = "full game" if "1H" not in self.bet_type.value else "1st half"
        bet_type_display = self.bet_type.value.replace("_1H", "").lower()

        # Build rationale
        lines = []
        lines.append(f"RECOMMENDED: {team_display} {bet_type_display} ({period})")
        lines.append("")

        # Model vs Market
        lines.append("MODEL VS MARKET:")
        if "MONEYLINE" in self.bet_type.value:
            lines.append(f"  Our Win Probability: {self.implied_prob:.1%}")
            lines.append(f"  Market Probability: {self.market_prob:.1%}")
            lines.append(f"  Probability Edge: {(self.implied_prob - self.market_prob):.1%}")
            lines.append(f"  Market Odds: {self.market_line:+d}")
        else:
            lines.append(f"  Model Line: {self.model_line:+.1f}")
            lines.append(f"  Market Line: {self.market_line:+.1f}")
            lines.append(f"  Edge: {self.edge:.1f} points")

        lines.append("")

        # Value Analysis
        lines.append("VALUE ANALYSIS:")
        lines.append(f"  Expected Value: {self.ev_percent:+.1f}%")
        lines.append(f"  Confidence Score: {self.confidence:.0%}")

        # Smoke score (quality indicator)
        smoke_score = self._calculate_smoke_score()
        smoke_emoji = "🔥🔥🔥" if smoke_score >= 90 else "🔥🔥" if smoke_score >= 75 else "🔥" if smoke_score >= 60 else "⚠️"
        lines.append(f"  Quality Score: {smoke_score}/100 {smoke_emoji}")

        lines.append("")

        # Bet Sizing
        lines.append("BET SIZING:")
        lines.append(f"  Recommended: {self.recommended_units:.1f} units ({self.bet_tier.value.upper()})")
        lines.append(f"  Kelly Fraction: {self.kelly_fraction:.2%}")

        # Sharp alignment
        if self.sharp_line is not None:
            lines.append("")
            lines.append("SHARP BOOK ANALYSIS:")
            lines.append(f"  Sharp Line: {self.sharp_line:+.1f}")
            alignment_status = "✓ ALIGNED" if self.is_sharp_aligned else "✗ CONTRARIAN"
            lines.append(f"  Status: {alignment_status}")

        lines.append("")
        lines.append("RATIONALE:")

        # Build specific rationale based on bet type
        if "MONEYLINE" in self.bet_type.value:
            prob_diff = (self.implied_prob - self.market_prob) * 100
            lines.append(f"  Our model projects {team_display} to win {self.implied_prob:.1%} of the time,")
            lines.append(f"  while the market implies only {self.market_prob:.1%}. This {prob_diff:.1f}%")
            lines.append(f"  probability edge translates to {self.ev_percent:+.1f}% expected value.")
        else:
            if self.bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
                lines.append(f"  Our efficiency-based model predicts a spread of {self.model_line:+.1f},")
                lines.append(f"  giving us {self.edge:.1f} points of value vs the market line of {self.market_line:+.1f}.")
                lines.append(f"  This represents {self.ev_percent:+.1f}% expected value.")
            else:  # TOTAL
                lines.append(f"  Our tempo-adjusted model projects a total of {self.model_line:.1f} points,")
                lines.append(f"  creating {self.edge:.1f} points of edge vs the market total of {self.market_line:.1f}.")
                lines.append(f"  This translates to {self.ev_percent:+.1f}% expected value on the {direction}.")

        return "\n".join(lines)

    def _calculate_smoke_score(self) -> int:
        """
        Calculate quality/confidence score (0-100).

        Higher scores indicate higher confidence bets.
        Combines edge, EV, confidence, and sharp alignment.
        """
        score = 0

        # Edge component (0-40 points)
        if "MONEYLINE" in self.bet_type.value:
            # For moneylines, use EV percentage
            edge_score = min(40, self.ev_percent * 4)  # 10% EV = 40 points
        else:
            # For spreads/totals, use point edge
            edge_score = min(40, self.edge * 8)  # 5 pt edge = 40 points
        score += edge_score

        # EV component (0-30 points)
        ev_score = min(30, abs(self.ev_percent) * 2)  # 15% EV = 30 points
        score += ev_score

        # Confidence component (0-20 points)
        confidence_score = self.confidence * 20  # 100% confidence = 20 points
        score += confidence_score

        # Sharp alignment bonus (0-10 points)
        if self.is_sharp_aligned:
            score += 10

        return int(min(100, score))

    @property
    def executive_summary(self) -> str:
        """
        Bottom-line-up-front executive summary.

        Quick snapshot of the bet recommendation for rapid decision making.
        """
        team_display = self.home_team if self.pick == Pick.HOME else self.away_team
        if self.bet_type in (BetType.TOTAL, BetType.TOTAL_1H):
            direction = "OVER" if self.pick == Pick.OVER else "UNDER"
            team_display = direction

        period = "FG" if "1H" not in self.bet_type.value else "1H"
        bet_type_short = self.bet_type.value.replace("_1H", "").replace("MONEYLINE", "ML")

        smoke_score = self._calculate_smoke_score()
        quality = "ELITE" if smoke_score >= 85 else "STRONG" if smoke_score >= 70 else "SOLID" if smoke_score >= 55 else "SPECULATIVE"

        return (
            f">>> {quality} {self.bet_tier.value.upper()} BET ({smoke_score}/100) <<<\n"
            f"{self.away_team} @ {self.home_team}\n"
            f"PLAY: {team_display} {bet_type_short} {period}\n"
            f"EDGE: {self.edge:.1f}{'%' if 'MONEYLINE' in self.bet_type.value else 'pts'} | "
            f"EV: {self.ev_percent:+.1f}% | UNITS: {self.recommended_units:.1f}"
        )


@dataclass
class Game:
    """
    A game with all associated data.
    """
    id: UUID
    home_team: str
    away_team: str
    commence_time: datetime
    status: GameStatus = GameStatus.SCHEDULED
    is_neutral: bool = False
    venue: Optional[str] = None

    # Scores (if completed)
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_score_1h: Optional[int] = None
    away_score_1h: Optional[int] = None

    # Ratings (loaded separately)
    home_ratings: Optional[TeamRatings] = None
    away_ratings: Optional[TeamRatings] = None

    # Market odds
    market_odds: Optional[MarketOdds] = None

    # Prediction
    prediction: Optional[Prediction] = None

    @property
    def actual_spread(self) -> Optional[float]:
        """Actual spread result (home perspective)."""
        if self.home_score is not None and self.away_score is not None:
            return self.away_score - self.home_score
        return None

    @property
    def actual_total(self) -> Optional[int]:
        """Actual total points."""
        if self.home_score is not None and self.away_score is not None:
            return self.home_score + self.away_score
        return None
