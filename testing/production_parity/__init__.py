"""
Production Parity Backtest System.

This module provides a backtest system that uses the EXACT same logic as production:
- Same team resolution (4-step exact matching with 780+ aliases)
- Same prediction models (FGSpread, H1Spread, FGTotal, H1Total)
- Strict anti-leakage (Season N-1 ratings for Season N games)
- All timestamps standardized to CST

Usage:
    python -m testing.production_parity.run_backtest

Components:
    - timezone_utils: CST standardization utilities
    - team_resolver: ProductionTeamResolver with 4-step exact matching
    - ratings_loader: AntiLeakageRatingsLoader (Season N-1 for Season N)
    - audit_logger: BacktestAuditLogger with CST timestamps
    - backtest_engine: ProductionParityBacktest orchestrator
    - run_backtest: CLI entry point
"""

from .timezone_utils import (
    CST,
    UTC,
    to_cst,
    parse_date_to_cst,
    get_cst_date,
    cst_date_to_season,
    get_season_for_game,
    get_ratings_season_for_game,
    now_cst,
    format_cst,
)

from .team_resolver import (
    ProductionTeamResolver,
    ResolutionStep,
    ResolutionResult,
    resolve_team_name,
    resolve_team_name_strict,
)

from .ratings_loader import (
    AntiLeakageRatingsLoader,
    TeamRatings,
    RatingsLookupResult,
)

from .audit_logger import (
    BacktestAuditLogger,
    GameAuditRecord,
    AuditEvent,
    AuditEventType,
)

from .backtest_engine import (
    ProductionParityBacktest,
    BacktestStats,
    GameRecord,
    PredictionResult,
)

__all__ = [
    # Timezone utilities
    "CST",
    "UTC",
    "to_cst",
    "parse_date_to_cst",
    "get_cst_date",
    "cst_date_to_season",
    "get_season_for_game",
    "get_ratings_season_for_game",
    "now_cst",
    "format_cst",
    # Team resolver
    "ProductionTeamResolver",
    "ResolutionStep",
    "ResolutionResult",
    "resolve_team_name",
    "resolve_team_name_strict",
    # Ratings loader
    "AntiLeakageRatingsLoader",
    "TeamRatings",
    "RatingsLookupResult",
    # Audit logger
    "BacktestAuditLogger",
    "GameAuditRecord",
    "AuditEvent",
    "AuditEventType",
    # Backtest engine
    "ProductionParityBacktest",
    "BacktestStats",
    "GameRecord",
    "PredictionResult",
]
