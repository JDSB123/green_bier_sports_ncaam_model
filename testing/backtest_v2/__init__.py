"""
Backtest Engine V2 - Clean Implementation

This module provides a fresh backtest engine that:
1. Uses ONLY canonical data from Azure Blob Storage (source of truth)
2. Falls back to local cache in ncaam_historical_data_local/
3. Routes ALL team names through the centralized team_aliases_db.json
4. Implements strict anti-leakage guards (temporal isolation)
5. Uses actual odds prices (no hardcoded -110)

Data Flow:
    Azure Blob (metricstrackersgbsv/ncaam-historical-raw)
        ↓
    Local Cache (ncaam_historical_data_local/)
        ↓
    Canonicalization (team name normalization)
        ↓
    Backtest Engine (point-in-time feature extraction)

Key Principles:
- Season N ratings can ONLY be used for Season N+1 predictions (anti-leakage)
- All team names must resolve through team_aliases_db.json
- Use closing lines from odds data (last snapshot before game time)
- Never use post-game information for predictions
"""

__version__ = "2.0.0"

from .data_loader import DataLoader
from .team_resolver import TeamResolver
from .backtest_engine import BacktestEngine

__all__ = ["DataLoader", "DataLoader", "TeamResolver", "BacktestEngine"]
