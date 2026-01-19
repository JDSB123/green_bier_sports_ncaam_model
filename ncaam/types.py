from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketOdds:
    """Minimal odds/lines container used by shared prediction code."""

    spread: float | None = None
    total: float | None = None
    spread_1h: float | None = None
    total_1h: float | None = None


@dataclass(frozen=True)
class TeamRatingsLike:
    """Minimal ratings container used by shared prediction code.

    This intentionally mirrors the common subset of fields used across backtests,
    scripts, and the prediction service. It is *not* tied to any service-specific
    Pydantic or ORM models.
    """

    team_name: str | None = None

    # Core efficiency
    adj_o: float | None = None
    adj_d: float | None = None

    # Optional factors / metadata
    barthag: float | None = None
    efg: float | None = None
    efgd: float | None = None
    tor: float | None = None
    orb: float | None = None
    drb: float | None = None
    ftr: float | None = None

    rank: float | None = None
    wab: float | None = None
    tempo: float | None = None

    three_pt_rate: float | None = None
    two_pt_pct: float | None = None
