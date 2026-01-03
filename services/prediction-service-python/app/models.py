"""
Domain models for NCAA Basketball Prediction Service v33.6.5.

Clean, simple data structures focused on what matters for profitable predictions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class BetType(str, Enum):
    """Types of bets we can recommend (spreads/totals only)."""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    SPREAD_1H = "SPREAD_1H"
    TOTAL_1H = "TOTAL_1H"


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

    ALL FIELDS ARE REQUIRED. No fallbacks, no defaults.
    The Go sync service captures all 22 Barttorvik fields - we use them ALL.

    All efficiency ratings are per 100 possessions.
    """
    team_name: str

    # ═══════════════════════════════════════════════════════════════════════════
    # CORE EFFICIENCY METRICS (REQUIRED)
    # ═══════════════════════════════════════════════════════════════════════════
    adj_o: float          # Adjusted offensive efficiency (pts per 100 possessions)
    adj_d: float          # Adjusted defensive efficiency (pts per 100 possessions)
    tempo: float          # Possessions per 40 minutes
    rank: int             # Barttorvik overall rank

    # ═══════════════════════════════════════════════════════════════════════════
    # FOUR FACTORS - SHOOTING (REQUIRED)
    # ═══════════════════════════════════════════════════════════════════════════
    efg: float            # Effective FG% (accounts for 3P value)
    efgd: float           # Effective FG% allowed by defense

    # ═══════════════════════════════════════════════════════════════════════════
    # FOUR FACTORS - TURNOVERS (REQUIRED)
    # ═══════════════════════════════════════════════════════════════════════════
    tor: float            # Turnover Rate (turnovers per 100 possessions)
    tord: float           # Turnover Rate forced by defense

    # ═══════════════════════════════════════════════════════════════════════════
    # FOUR FACTORS - REBOUNDING (REQUIRED)
    # ═══════════════════════════════════════════════════════════════════════════
    orb: float            # Offensive Rebound % (% of available offensive rebounds grabbed)
    drb: float            # Defensive Rebound % (% of available defensive rebounds grabbed)

    # ═══════════════════════════════════════════════════════════════════════════
    # FOUR FACTORS - FREE THROWS (REQUIRED)
    # ═══════════════════════════════════════════════════════════════════════════
    ftr: float            # Free Throw Rate (FTA per FGA)
    ftrd: float           # Free Throw Rate allowed by defense

    # ═══════════════════════════════════════════════════════════════════════════
    # SHOOTING BREAKDOWN (REQUIRED)
    # ═══════════════════════════════════════════════════════════════════════════
    two_pt_pct: float     # 2-Point FG%
    two_pt_pct_d: float   # 2-Point FG% allowed by defense
    three_pt_pct: float   # 3-Point FG%
    three_pt_pct_d: float # 3-Point FG% allowed by defense
    three_pt_rate: float  # 3-Point attempt rate (% of FGA that are 3s)
    three_pt_rate_d: float # 3-Point rate allowed by defense

    # ═══════════════════════════════════════════════════════════════════════════
    # QUALITY METRICS (REQUIRED)
    # ═══════════════════════════════════════════════════════════════════════════
    barthag: float        # Barttorvik power rating (expected win % vs average D1 team)
    wab: float            # Wins Above Bubble (wins above expected for bubble team)

    @property
    def net_rating(self) -> float:
        """Net efficiency rating (higher = better)."""
        return self.adj_o - self.adj_d

    @property
    def turnover_margin(self) -> float:
        """Turnover differential (positive = forces more than commits)."""
        return self.tord - self.tor

    @property
    def rebound_margin(self) -> float:
        """Rebounding differential (positive = better rebounder)."""
        return self.orb + self.drb - 100  # Normalized to 0 baseline

    @property
    def free_throw_margin(self) -> float:
        """Free throw rate differential (positive = gets to line more)."""
        return self.ftr - self.ftrd

    @property
    def three_pt_reliance(self) -> float:
        """How 3-point dependent is this team (higher = more 3s)."""
        return self.three_pt_rate

    @property
    def interior_strength(self) -> float:
        """Interior scoring strength (2P% relative to 3P dependence)."""
        return self.two_pt_pct * (100 - self.three_pt_rate) / 100

    def __str__(self) -> str:
        return (
            f"{self.team_name} (#{self.rank}): "
            f"O={self.adj_o:.1f} D={self.adj_d:.1f} Net={self.net_rating:+.1f} "
            f"Barthag={self.barthag:.3f}"
        )


class MarketOdds(BaseModel):
    """
    Current market odds for a game.

    All lines are from HOME team perspective:
    - Negative spread = home team favored
    - Positive spread = away team favored (home is underdog)
    """
    model_config = {"frozen": True}

    spread: Optional[float] = None
    # Legacy/compat: single spread price (assumes symmetric juice).
    # Prefer using spread_home_price/spread_away_price when available.
    spread_price: Optional[int] = None
    spread_home_price: Optional[int] = None
    spread_away_price: Optional[int] = None
    total: Optional[float] = None
    over_price: Optional[int] = None
    under_price: Optional[int] = None

    # First half
    spread_1h: Optional[float] = None
    total_1h: Optional[float] = None
    spread_price_1h: Optional[int] = None
    spread_1h_home_price: Optional[int] = None
    spread_1h_away_price: Optional[int] = None
    over_price_1h: Optional[int] = None
    under_price_1h: Optional[int] = None

    # Sharp book reference (Pinnacle/Circa)
    sharp_spread: Optional[float] = None
    sharp_total: Optional[float] = None
    
    # Square book reference (DraftKings/FanDuel) for sharp vs square comparison
    square_spread: Optional[float] = None
    square_total: Optional[float] = None

    # Opening lines (for market movement/steam context)
    spread_open: Optional[float] = None
    total_open: Optional[float] = None
    spread_1h_open: Optional[float] = None
    total_1h_open: Optional[float] = None
    sharp_spread_open: Optional[float] = None
    sharp_total_open: Optional[float] = None

    # Optional public sentiment (if available)
    public_bet_pct_home: Optional[float] = None
    public_money_pct_home: Optional[float] = None
    public_bet_pct_over: Optional[float] = None
    public_money_pct_over: Optional[float] = None

    @field_validator('total', 'total_1h', mode='before')
    @classmethod
    def validate_totals(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None:
            if v <= 0:
                raise ValueError("Total must be positive")
            
            if info.field_name == 'total_1h':
                if v < 40 or v > 120:
                    raise ValueError("1H Total out of reasonable range (40-120)")
            else:
                if v < 80 or v > 220:  # Relaxed range slightly
                    raise ValueError("Total out of reasonable range (80-220)")
        return v

    @field_validator('spread', 'spread_1h', mode='before')
    @classmethod
    def validate_spreads(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            # Expanded from +/-30 to handle heavy mismatches (e.g., D1 vs SWAC/MEAC).
            if abs(v) > 45:
                raise ValueError("Spread exceeds reasonable limit (+/-45)")
        return v


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

    # Market comparison
    market_spread: Optional[float] = None
    market_total: Optional[float] = None
    market_spread_1h: Optional[float] = None
    market_total_1h: Optional[float] = None

    # Edges (model - market)
    # FIX: Added signed edges to preserve directional information
    # NOTE: signed spread edge = (model - market), using HOME-perspective lines.
    # - Negative spread_edge_signed => model is MORE negative => HOME value
    # - Positive spread_edge_signed => model is MORE positive => AWAY value
    spread_edge: float = 0.0           # Absolute value for threshold checks
    spread_edge_signed: float = 0.0    # Signed value for direction
    total_edge: float = 0.0
    total_edge_signed: float = 0.0     # Positive = OVER value, Negative = UNDER value
    spread_edge_1h: float = 0.0
    spread_edge_1h_signed: float = 0.0
    total_edge_1h: float = 0.0
    total_edge_1h_signed: float = 0.0

    # Model metadata
    model_version: str = "v33.6.5"
    created_at: datetime = field(default_factory=datetime.utcnow)

    def calculate_edges(self, market: MarketOdds) -> None:
        """Calculate edges vs market odds.

        FIX: Now calculates both signed and unsigned edges.
        Signed edges preserve directional information for pick determination.
        """
        self.market_spread = market.spread
        self.market_total = market.total
        self.market_spread_1h = market.spread_1h
        self.market_total_1h = market.total_1h

        if market.spread is not None:
            # Edge = how much better our line is vs market
            # If we predict -5 and market is -3, signed edge = -2 (HOME value)
            # If we predict -3 and market is -5, signed edge = +2 (AWAY value)
            self.spread_edge_signed = self.predicted_spread - market.spread
            self.spread_edge = abs(self.spread_edge_signed)

        if market.total is not None:
            # Positive = model higher = OVER value
            # Negative = model lower = UNDER value
            self.total_edge_signed = self.predicted_total - market.total
            self.total_edge = abs(self.total_edge_signed)

        if market.spread_1h is not None:
            self.spread_edge_1h_signed = self.predicted_spread_1h - market.spread_1h
            self.spread_edge_1h = abs(self.spread_edge_1h_signed)

        if market.total_1h is not None:
            self.total_edge_1h_signed = self.predicted_total_1h - market.total_1h
            self.total_edge_1h = abs(self.total_edge_1h_signed)


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

    # Price context (American odds) for the specific pick side (HOME/AWAY/OVER/UNDER)
    pick_price: Optional[int] = None
    # Market-derived extras (best-practice auditing)
    market_prob_novig: Optional[float] = None
    market_hold_percent: Optional[float] = None
    prob_edge: Optional[float] = None

    # Sharp alignment
    sharp_line: Optional[float] = None
    is_sharp_aligned: bool = True   # Are we aligned with sharp movement?

    # ═══════════════════════════════════════════════════════════════════════════
    # CLV TRACKING (Closing Line Value) - Gold standard for model quality
    # ═══════════════════════════════════════════════════════════════════════════
    # CLV measures if our line was better than the closing line
    # Positive CLV = we got value (line moved in our favor after bet)
    closing_line: Optional[float] = None           # Final line before game start
    closing_line_captured_at: Optional[datetime] = None  # When closing line was captured
    clv: Optional[float] = None                    # Our line - closing line (points)
    clv_percent: Optional[float] = None            # CLV as % (clv / closing_line * 100)

    # Metadata
    model_version: str = "v33.6.5"
    created_at: datetime = field(default_factory=datetime.utcnow)

    def calculate_clv(self, closing_line: float, captured_at: datetime) -> None:
        """
        Calculate Closing Line Value after game starts.

        CLV = (our bet line) - (closing line)
        For spreads: if we bet HOME -3 and it closed at HOME -5, CLV = +2 (value)
        For totals: if we bet OVER 140 and it closed at 143, CLV = -3 (no value)

        Positive CLV indicates we got a better line than the market close.
        This is the gold standard for measuring betting model quality.
        """
        self.closing_line = closing_line
        self.closing_line_captured_at = captured_at

        if self.bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            # For spreads: CLV = market_line - closing_line (from our pick's perspective)
            # If we bet HOME and line moved from -3 to -5, that's +2 CLV
            if self.pick == Pick.HOME:
                self.clv = self.market_line - closing_line
            else:  # AWAY
                # For AWAY, we bet +spread, so line moving up is value
                self.clv = closing_line - self.market_line
        else:
            # For totals: CLV = closing_line - market_line (for OVER)
            # If we bet OVER 140 and it closed at 143, we got value (line moved up)
            if self.pick == Pick.OVER:
                self.clv = closing_line - self.market_line
            else:  # UNDER
                self.clv = self.market_line - closing_line

        # Calculate CLV as percentage
        if closing_line != 0:
            self.clv_percent = (self.clv / abs(closing_line)) * 100

    @property
    def summary(self) -> str:
        """Human-readable summary of the recommendation."""
        direction = "HOME" if self.pick in (Pick.HOME, Pick.OVER) else "AWAY"
        if self.bet_type in (BetType.TOTAL, BetType.TOTAL_1H):
            direction = "OVER" if self.pick == Pick.OVER else "UNDER"

        period = "1H" if "1H" in self.bet_type.value else "FG"
        bet_desc = self.bet_type.value.replace("_1H", "")

        if self.bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
            line_display = f"{self.line:+.1f}"
        else:
            line_display = f"{self.line:.1f}"

        return (
            f"{self.away_team} @ {self.home_team} | "
            f"{period} {bet_desc} {direction} {line_display} | "
            f"Edge: {self.edge:.1f}pts | "
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
        bet_type_short = self.bet_type.value.replace("_1H", "")

        smoke_score = self._calculate_smoke_score()
        quality = "ELITE" if smoke_score >= 85 else "STRONG" if smoke_score >= 70 else "SOLID" if smoke_score >= 55 else "SPECULATIVE"

        return (
            f">>> {quality} {self.bet_tier.value.upper()} BET ({smoke_score}/100) <<<\n"
            f"{self.away_team} @ {self.home_team}\n"
            f"PLAY: {team_display} {bet_type_short} {period}\n"
            f"EDGE: {self.edge:.1f}pts | "
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
