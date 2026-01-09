"""
Historical Odds Loader.

Loads historical betting odds for backtest ROI calculation.
Games without odds should be skipped (can't calculate betting ROI).

Sources:
- training_data_with_odds.csv: Games with spread_open, total_open
- historical_odds/*.csv: Additional odds data from The Odds API
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from .timezone_utils import parse_date_to_cst, format_cst
from .team_resolver import ProductionTeamResolver, resolve_team_name


@dataclass
class GameOdds:
    """Odds for a single game."""
    game_id: str
    game_date: str
    home_team: str
    away_team: str
    spread_open: Optional[float]  # Home spread (negative = home favored)
    total_open: Optional[float]   # Over/under line
    h1_spread: Optional[float] = None
    h1_total: Optional[float] = None

    @property
    def has_spread(self) -> bool:
        return self.spread_open is not None

    @property
    def has_total(self) -> bool:
        return self.total_open is not None

    @property
    def has_h1_spread(self) -> bool:
        return self.h1_spread is not None

    @property
    def has_h1_total(self) -> bool:
        return self.h1_total is not None


class HistoricalOddsLoader:
    """
    Loads historical odds from training data.

    Uses training_data_with_odds.csv as primary source.
    """

    def __init__(self, data_dir: Optional[Path] = None, team_resolver: Optional[ProductionTeamResolver] = None):
        """
        Initialize the odds loader.

        Args:
            data_dir: Directory containing odds files
            team_resolver: Optional resolver (uses default if not provided)
        """
        if data_dir is None:
            # Default to prediction-service-python/training_data
            data_dir = Path(__file__).parents[2] / "services" / "prediction-service-python" / "training_data"

        self.data_dir = Path(data_dir)
        self.resolver = team_resolver or ProductionTeamResolver()

        # Cache: game_id -> GameOdds
        self._odds_cache: Dict[str, GameOdds] = {}

        # Also index by normalized key (date + teams)
        self._odds_by_matchup: Dict[str, GameOdds] = {}

        # Stats
        self.stats = {
            "total_games": 0,
            "games_with_spread": 0,
            "games_with_total": 0,
            "lookups": 0,
            "found": 0,
        }

        self._load_odds()

    def _normalize_team_name(self, name: str) -> str:
        """Normalize team name for matching."""
        return name.lower().strip()

    def _make_matchup_key(self, date: str, home: str, away: str) -> str:
        """Create normalized key for matchup lookup."""
        # Normalize date to YYYY-MM-DD
        try:
            dt = parse_date_to_cst(date)
            date_str = format_cst(dt, "%Y-%m-%d")
        except:
            date_str = date[:10]  # Just take first 10 chars

        home_norm = self._normalize_team_name(home)
        away_norm = self._normalize_team_name(away)

        return f"{date_str}|{home_norm}|{away_norm}"

    def _load_odds(self) -> None:
        """Load odds from training data file."""
        # Primary source: training_data_with_odds.csv
        primary_path = self.data_dir / "training_data_with_odds.csv"

        if not primary_path.exists():
            print(f"[OddsLoader] Warning: Primary odds file not found: {primary_path}")
            return

        with open(primary_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    game_id = row.get("game_id", "")
                    game_date = row.get("game_date", "")
                    home_team_raw = row.get("home_team", "")
                    away_team_raw = row.get("away_team", "")
                    
                    # Canonicalize team names at load time
                    home_result = self.resolver.resolve(home_team_raw)
                    away_result = self.resolver.resolve(away_team_raw)
                    
                    home_team = home_result.canonical_name if home_result.resolved else home_team_raw
                    away_team = away_result.canonical_name if away_result.resolved else away_team_raw

                    # Parse spread (may be empty)
                    spread_str = row.get("spread_open", "")
                    spread = float(spread_str) if spread_str else None

                    # Parse total (may be empty)
                    total_str = row.get("total_open", "")
                    total = float(total_str) if total_str else None

                    odds = GameOdds(
                        game_id=game_id,
                        game_date=game_date,
                        home_team=home_team,
                        away_team=away_team,
                        spread_open=spread,
                        total_open=total,
                    )

                    self._odds_cache[game_id] = odds
                    self.stats["total_games"] += 1

                    if spread is not None:
                        self.stats["games_with_spread"] += 1
                    if total is not None:
                        self.stats["games_with_total"] += 1

                    # Also index by matchup
                    key = self._make_matchup_key(game_date, home_team, away_team)
                    self._odds_by_matchup[key] = odds

                except (ValueError, KeyError) as e:
                    continue

        print(f"[OddsLoader] Loaded {self.stats['total_games']} games, "
              f"{self.stats['games_with_spread']} with spreads, "
              f"{self.stats['games_with_total']} with totals")

    def get_odds_by_id(self, game_id: str) -> Optional[GameOdds]:
        """Get odds by game ID."""
        self.stats["lookups"] += 1
        odds = self._odds_cache.get(game_id)
        if odds:
            self.stats["found"] += 1
        return odds

    def get_odds_by_matchup(
        self,
        game_date: str,
        home_team: str,
        away_team: str,
    ) -> Optional[GameOdds]:
        """Get odds by matchup details.
        
        Team names are canonicalized before lookup to handle different 
        name variants between data sources.
        """
        self.stats["lookups"] += 1
        
        # Canonicalize input team names for lookup
        home_result = self.resolver.resolve(home_team)
        away_result = self.resolver.resolve(away_team)
        
        home_canonical = home_result.canonical_name if home_result.resolved else home_team
        away_canonical = away_result.canonical_name if away_result.resolved else away_team
        
        key = self._make_matchup_key(game_date, home_canonical, away_canonical)
        odds = self._odds_by_matchup.get(key)
        if odds:
            self.stats["found"] += 1
        return odds

    def get_stats(self) -> dict:
        """Get loader statistics."""
        return {
            **self.stats,
            "hit_rate": self.stats["found"] / self.stats["lookups"] if self.stats["lookups"] > 0 else 0,
        }


# Betting calculation utilities

def calculate_spread_result(
    pick: str,
    market_spread: float,
    actual_margin: int,
) -> Tuple[str, float]:
    """
    Calculate spread bet result.

    Args:
        pick: "HOME" or "AWAY"
        market_spread: Market spread from home perspective (negative = home favored)
        actual_margin: Actual home margin (positive = home won)

    Returns:
        (result, units) where result is "WIN", "LOSS", or "PUSH"
    """
    # Cover = actual_margin + spread (from home perspective)
    cover = actual_margin + market_spread

    if pick == "HOME":
        if cover > 0.5:  # Home covered
            return "WIN", 1.0
        elif cover < -0.5:  # Home didn't cover
            return "LOSS", -1.1  # Standard -110 juice
        else:
            return "PUSH", 0.0
    else:  # AWAY
        if cover < -0.5:  # Away covered
            return "WIN", 1.0
        elif cover > 0.5:  # Away didn't cover
            return "LOSS", -1.1
        else:
            return "PUSH", 0.0


def calculate_total_result(
    pick: str,
    market_total: float,
    actual_total: int,
) -> Tuple[str, float]:
    """
    Calculate total bet result.

    Args:
        pick: "OVER" or "UNDER"
        market_total: Market over/under line
        actual_total: Actual combined score

    Returns:
        (result, units) where result is "WIN", "LOSS", or "PUSH"
    """
    diff = actual_total - market_total

    if pick == "OVER":
        if diff > 0.5:
            return "WIN", 1.0
        elif diff < -0.5:
            return "LOSS", -1.1
        else:
            return "PUSH", 0.0
    else:  # UNDER
        if diff < -0.5:
            return "WIN", 1.0
        elif diff > 0.5:
            return "LOSS", -1.1
        else:
            return "PUSH", 0.0


def get_spread_pick(model_spread: float, market_spread: float, min_edge: float = 2.0) -> Optional[str]:
    """
    Determine spread pick based on model vs market.

    Args:
        model_spread: Model predicted spread (negative = home favored)
        market_spread: Market spread (negative = home favored)
        min_edge: Minimum edge required to make a pick

    Returns:
        "HOME", "AWAY", or None (no bet)
    """
    edge = abs(model_spread - market_spread)

    if edge < min_edge:
        return None

    # If model thinks home is MORE favored than market, bet HOME
    # If model thinks away is MORE favored than market, bet AWAY
    if model_spread < market_spread:
        return "HOME"
    else:
        return "AWAY"


def get_total_pick(model_total: float, market_total: float, min_edge: float = 2.0) -> Optional[str]:
    """
    Determine total pick based on model vs market.

    Args:
        model_total: Model predicted total
        market_total: Market total line
        min_edge: Minimum edge required to make a pick

    Returns:
        "OVER", "UNDER", or None (no bet)
    """
    edge = abs(model_total - market_total)

    if edge < min_edge:
        return None

    if model_total > market_total:
        return "OVER"
    else:
        return "UNDER"


# Self-test
if __name__ == "__main__":
    print("=" * 60)
    print("Historical Odds Loader - Self Test")
    print("=" * 60)

    loader = HistoricalOddsLoader()

    # Test lookup
    print("\n--- Sample Lookups ---")
    sample_ids = ["376089", "376112", "356551"]
    for gid in sample_ids:
        odds = loader.get_odds_by_id(gid)
        if odds:
            print(f"  {gid}: {odds.home_team} vs {odds.away_team}")
            print(f"         Spread: {odds.spread_open}, Total: {odds.total_open}")
        else:
            print(f"  {gid}: Not found")

    print("\n--- Loader Stats ---")
    print(f"  {loader.get_stats()}")

    print("\n--- Bet Calculations ---")
    # Test: Model says -5.0, market is -3.0, edge = 2.0, pick HOME
    pick = get_spread_pick(-5.0, -3.0, min_edge=2.0)
    print(f"  Model -5.0 vs Market -3.0: {pick}")

    # Test: Actual margin +10, market -5, bet HOME -> covered by 15
    result, units = calculate_spread_result("HOME", -5.0, 10)
    print(f"  HOME bet, spread -5.0, margin +10: {result} ({units:+.1f}u)")

    # Test: Model total 145, market 140, bet OVER, actual 150
    pick = get_total_pick(145.0, 140.0, min_edge=2.0)
    result, units = calculate_total_result("OVER", 140.0, 150)
    print(f"  OVER bet, line 140, actual 150: {result} ({units:+.1f}u)")
