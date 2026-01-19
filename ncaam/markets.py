from __future__ import annotations

from enum import Enum


class MarketType(str, Enum):
    """Canonical market identifiers shared across scripts/services."""

    FG_SPREAD = "fg_spread"
    FG_TOTAL = "fg_total"
    FG_MONEYLINE = "fg_moneyline"
    H1_SPREAD = "h1_spread"
    H1_TOTAL = "h1_total"
    H1_MONEYLINE = "h1_moneyline"
