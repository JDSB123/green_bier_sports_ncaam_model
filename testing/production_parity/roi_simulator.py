"""
ROI Simulator - Backtest betting performance with historical odds.

This module simulates betting outcomes using:
1. Production model predictions
2. Historical market odds
3. Actual game results

Outputs:
- ROI by edge threshold
- Win rate by model
- Optimal edge thresholds
- Unit P/L over time

Usage:
    python -m testing.production_parity.roi_simulator --season 2024
"""

import csv
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

# Add prediction-service-python to path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "services" / "prediction-service-python"))

from .team_resolver import ProductionTeamResolver
from .ratings_loader import AntiLeakageRatingsLoader, TeamRatings
from .timezone_utils import get_season_for_game

# Import production models
try:
    from app.predictors.fg_spread import FGSpreadModel
    from app.predictors.fg_total import FGTotalModel
    from app.predictors.h1_spread import H1SpreadModel
    from app.predictors.h1_total import H1TotalModel
    from app.models import TeamRatings as ProductionTeamRatings
    MODELS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Production models not available: {e}")
    MODELS_AVAILABLE = False


@dataclass
class OddsRecord:
    """Historical odds for a game."""
    event_id: str
    commence_time: datetime
    home_team: str
    away_team: str
    bookmaker: str
    spread: float
    total: float
    h1_spread: Optional[float] = None
    h1_total: Optional[float] = None


@dataclass
class BetResult:
    """Result of a simulated bet."""
    game_id: str
    date: str
    model: str
    pick: str
    edge: float
    market_line: float
    predicted_line: float
    actual_result: float
    won: bool
    units_wagered: float = 1.0
    units_won: float = 0.0


@dataclass
class ROIResults:
    """Aggregate ROI results."""
    edge_threshold: float
    model: str
    total_bets: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    units_wagered: float
    units_won: float
    roi: float
    
    def to_dict(self) -> dict:
        return {
            "edge_threshold": self.edge_threshold,
            "model": self.model,
            "total_bets": self.total_bets,
            "wins": self.wins,
            "losses": self.losses,
            "pushes": self.pushes,
            "win_rate": round(self.win_rate * 100, 1),
            "units_wagered": self.units_wagered,
            "units_won": round(self.units_won, 2),
            "roi": round(self.roi * 100, 1),
        }


class ROISimulator:
    """
    Simulates betting ROI using historical data.
    
    Key features:
    - Anti-leakage: Uses Season N-1 ratings for Season N games
    - Actual odds: Uses historical market lines (not synthetic)
    - Fair comparison: Standard -110 juice assumed
    """
    
    JUICE = -110  # Standard juice for calculation
    
    def __init__(
        self,
        games_dir: Path = None,
        odds_dir: Path = None,
        ratings_dir: Path = None,
    ):
        self.data_dir = ROOT_DIR / "testing" / "data"
        self.games_dir = games_dir or self.data_dir / "historical"
        self.odds_dir = odds_dir or self.data_dir / "historical_odds"
        self.ratings_dir = ratings_dir or self.data_dir / "historical"
        
        self.team_resolver = ProductionTeamResolver()
        self.ratings_loader = AntiLeakageRatingsLoader(data_dir=self.ratings_dir)
        
        # Initialize models
        if MODELS_AVAILABLE:
            self.models = {
                "FGSpread": FGSpreadModel(),
                "FGTotal": FGTotalModel(),
                "H1Spread": H1SpreadModel(),
                "H1Total": H1TotalModel(),
            }
        else:
            self.models = {}
        
        self.odds_cache: Dict[str, OddsRecord] = {}
        self.results: List[BetResult] = []
    
    def load_historical_odds(self, seasons: List[int] = None) -> int:
        """Load historical odds from CSV files."""
        loaded = 0
        
        for odds_file in self.odds_dir.glob("*.csv"):
            try:
                with open(odds_file, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            odds = OddsRecord(
                                event_id=row.get("event_id", ""),
                                commence_time=datetime.fromisoformat(
                                    row["commence_time"].replace("Z", "+00:00")
                                ),
                                home_team=row["home_team"],
                                away_team=row["away_team"],
                                bookmaker=row.get("bookmaker", "unknown"),
                                spread=float(row["spread"]) if row.get("spread") else None,
                                total=float(row["total"]) if row.get("total") else None,
                                h1_spread=float(row["h1_spread"]) if row.get("h1_spread") else None,
                                h1_total=float(row["h1_total"]) if row.get("h1_total") else None,
                            )
                            
                            # Key by home_team + away_team + date
                            date_str = odds.commence_time.strftime("%Y-%m-%d")
                            key = f"{odds.home_team}|{odds.away_team}|{date_str}"
                            self.odds_cache[key] = odds
                            loaded += 1
                        except (ValueError, KeyError) as e:
                            continue
            except Exception as e:
                print(f"Error loading {odds_file}: {e}")
        
        print(f"Loaded {loaded} odds records from {self.odds_dir}")
        return loaded
    
    def find_odds(
        self, 
        home_team: str, 
        away_team: str, 
        game_date: str
    ) -> Optional[OddsRecord]:
        """Find odds for a game by team names and date."""
        # Try exact match first
        key = f"{home_team}|{away_team}|{game_date}"
        if key in self.odds_cache:
            return self.odds_cache[key]
        
        # Try resolving team names
        home_resolved = self.team_resolver.resolve(home_team)
        away_resolved = self.team_resolver.resolve(away_team)
        
        if home_resolved and away_resolved:
            key = f"{home_resolved}|{away_resolved}|{game_date}"
            if key in self.odds_cache:
                return self.odds_cache[key]
        
        # Search through odds for fuzzy match
        for odds_key, odds in self.odds_cache.items():
            if game_date in odds_key:
                odds_home = self.team_resolver.resolve(odds.home_team)
                odds_away = self.team_resolver.resolve(odds.away_team)
                if odds_home == home_resolved and odds_away == away_resolved:
                    return odds
        
        return None
    
    def calculate_edge(
        self,
        prediction: float,
        market_line: float,
        bet_type: str,
    ) -> Tuple[float, str]:
        """
        Calculate edge and pick direction.
        
        For spreads: negative prediction means home favored
        For totals: compare prediction to market
        """
        if "Spread" in bet_type:
            # Spread: prediction is home margin (negative = home favored)
            # Market spread is from home perspective
            edge = abs(prediction - market_line)
            if prediction < market_line:
                pick = "HOME"  # Model thinks home is stronger
            else:
                pick = "AWAY"
        else:
            # Total
            edge = abs(prediction - market_line)
            if prediction > market_line:
                pick = "OVER"
            else:
                pick = "UNDER"
        
        return edge, pick
    
    def evaluate_bet(
        self,
        pick: str,
        market_line: float,
        actual_result: float,
        bet_type: str,
    ) -> Tuple[bool, float]:
        """
        Evaluate if a bet won.
        
        Returns: (won, units_won)
        Units won is +0.91 for win, -1.0 for loss, 0 for push
        """
        if "Spread" in bet_type:
            actual_margin = actual_result  # Home margin
            if pick == "HOME":
                # Bet on home to cover
                result = actual_margin + market_line
            else:
                # Bet on away to cover
                result = -(actual_margin + market_line)
            
            if result > 0:
                return True, 0.91  # Win at -110
            elif result < 0:
                return False, -1.0  # Loss
            else:
                return None, 0.0  # Push
        else:
            # Total
            actual_total = actual_result
            if pick == "OVER":
                if actual_total > market_line:
                    return True, 0.91
                elif actual_total < market_line:
                    return False, -1.0
                else:
                    return None, 0.0
            else:  # UNDER
                if actual_total < market_line:
                    return True, 0.91
                elif actual_total > market_line:
                    return False, -1.0
                else:
                    return None, 0.0
    
    def simulate_season(
        self,
        season: int,
        edge_thresholds: List[float] = None,
    ) -> Dict[str, List[ROIResults]]:
        """
        Simulate betting for a full season.
        
        Args:
            season: The season year (e.g., 2024 for 2023-24 season)
            edge_thresholds: List of edge thresholds to test
        
        Returns:
            Dict mapping model name to list of ROI results by threshold
        """
        if edge_thresholds is None:
            edge_thresholds = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0]
        
        # Load games for this season
        games_file = self.games_dir / f"games_{season}.csv"
        if not games_file.exists():
            print(f"Games file not found: {games_file}")
            return {}
        
        # Track bets by model and threshold
        bets_by_model: Dict[str, List[BetResult]] = {
            model: [] for model in self.models.keys()
        }
        
        games_processed = 0
        games_with_odds = 0
        
        with open(games_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                games_processed += 1
                
                try:
                    game_date = row.get("date", row.get("game_date", ""))
                    home_team_raw = row.get("home_team", "")
                    away_team_raw = row.get("away_team", "")
                    home_score = int(row.get("home_score", 0))
                    away_score = int(row.get("away_score", 0))
                    
                    # Get H1 scores if available
                    h1_home = int(row["h1_home"]) if row.get("h1_home") else None
                    h1_away = int(row["h1_away"]) if row.get("h1_away") else None
                    
                    # Resolve team names
                    home_team = self.team_resolver.resolve(home_team_raw)
                    away_team = self.team_resolver.resolve(away_team_raw)
                    
                    if not home_team or not away_team:
                        continue
                    
                    # Find odds
                    odds = self.find_odds(home_team_raw, away_team_raw, game_date)
                    if not odds:
                        continue
                    
                    games_with_odds += 1
                    
                    # Get ratings (anti-leakage via get_ratings_for_game)
                    home_result = self.ratings_loader.get_ratings_for_game(home_team_raw, game_date)
                    away_result = self.ratings_loader.get_ratings_for_game(away_team_raw, game_date)
                    
                    if not home_result.found or not away_result.found:
                        continue
                    
                    home_ratings = home_result.ratings
                    away_ratings = away_result.ratings
                    
                    # Convert to production model format
                    home_prod = self._to_production_ratings(home_ratings)
                    away_prod = self._to_production_ratings(away_ratings)
                    
                    if not home_prod or not away_prod:
                        continue
                    
                    # Calculate actual results
                    actual_margin = home_score - away_score
                    actual_total = home_score + away_score
                    actual_h1_margin = (h1_home - h1_away) if h1_home and h1_away else None
                    actual_h1_total = (h1_home + h1_away) if h1_home and h1_away else None
                    
                    # Run each model
                    for model_name, model in self.models.items():
                        try:
                            # Get market line
                            if model_name == "FGSpread" and odds.spread is not None:
                                market_line = odds.spread
                                actual_result = actual_margin
                            elif model_name == "FGTotal" and odds.total is not None:
                                market_line = odds.total
                                actual_result = actual_total
                            elif model_name == "H1Spread" and odds.h1_spread is not None:
                                market_line = odds.h1_spread
                                actual_result = actual_h1_margin
                            elif model_name == "H1Total" and odds.h1_total is not None:
                                market_line = odds.h1_total
                                actual_result = actual_h1_total
                            else:
                                continue
                            
                            if actual_result is None:
                                continue
                            
                            # Get prediction
                            result = model.predict(home_prod, away_prod)
                            prediction = result.prediction
                            
                            # Calculate edge
                            edge, pick = self.calculate_edge(
                                prediction, market_line, model_name
                            )
                            
                            # Evaluate bet
                            won, units_won = self.evaluate_bet(
                                pick, market_line, actual_result, model_name
                            )
                            
                            bet = BetResult(
                                game_id=row.get("game_id", ""),
                                date=game_date,
                                model=model_name,
                                pick=pick,
                                edge=edge,
                                market_line=market_line,
                                predicted_line=prediction,
                                actual_result=actual_result,
                                won=won if won is not None else False,
                                units_wagered=1.0,
                                units_won=units_won,
                            )
                            
                            bets_by_model[model_name].append(bet)
                            
                        except Exception as e:
                            continue
                
                except Exception as e:
                    continue
        
        print(f"Processed {games_processed} games, {games_with_odds} with odds")
        
        # Calculate ROI by threshold
        results: Dict[str, List[ROIResults]] = {}
        
        for model_name, bets in bets_by_model.items():
            model_results = []
            
            for threshold in edge_thresholds:
                qualified_bets = [b for b in bets if b.edge >= threshold]
                
                if not qualified_bets:
                    model_results.append(ROIResults(
                        edge_threshold=threshold,
                        model=model_name,
                        total_bets=0,
                        wins=0,
                        losses=0,
                        pushes=0,
                        win_rate=0.0,
                        units_wagered=0.0,
                        units_won=0.0,
                        roi=0.0,
                    ))
                    continue
                
                wins = sum(1 for b in qualified_bets if b.won is True)
                losses = sum(1 for b in qualified_bets if b.won is False)
                pushes = sum(1 for b in qualified_bets if b.units_won == 0)
                units_wagered = float(len(qualified_bets))
                units_won = sum(b.units_won for b in qualified_bets)
                win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0
                roi = units_won / units_wagered if units_wagered > 0 else 0.0
                
                model_results.append(ROIResults(
                    edge_threshold=threshold,
                    model=model_name,
                    total_bets=len(qualified_bets),
                    wins=wins,
                    losses=losses,
                    pushes=pushes,
                    win_rate=win_rate,
                    units_wagered=units_wagered,
                    units_won=units_won,
                    roi=roi,
                ))
            
            results[model_name] = model_results
        
        return results
    
    def _to_production_ratings(self, ratings: TeamRatings) -> Optional[ProductionTeamRatings]:
        """Convert backtest TeamRatings to production TeamRatings."""
        try:
            return ProductionTeamRatings(
                team_name=ratings.team_name,
                adj_o=ratings.adj_o,
                adj_d=ratings.adj_d,
                tempo=ratings.tempo,
                rank=ratings.rank,
                efg=ratings.efg,
                efgd=ratings.efgd,
                tor=ratings.tor,
                tord=ratings.tord,
                orb=ratings.orb,
                drb=ratings.drb,
                ftr=ratings.ftr,
                ftrd=ratings.ftrd,
                two_pt_pct=ratings.two_pt_pct,
                two_pt_pct_d=ratings.two_pt_pct_d,
                three_pt_pct=ratings.three_pt_pct,
                three_pt_pct_d=ratings.three_pt_pct_d,
                three_pt_rate=ratings.three_pt_rate,
                three_pt_rate_d=ratings.three_pt_rate_d,
                barthag=ratings.barthag,
                wab=ratings.wab,
            )
        except Exception as e:
            return None
    
    def print_results(self, results: Dict[str, List[ROIResults]]):
        """Print ROI results in a formatted table."""
        print("\n" + "=" * 80)
        print("ROI SIMULATION RESULTS")
        print("=" * 80)
        
        for model_name, model_results in results.items():
            print(f"\n{model_name}")
            print("-" * 70)
            print(f"{'Edge':>6} | {'Bets':>5} | {'Wins':>5} | {'Win%':>6} | {'Units':>8} | {'ROI':>7}")
            print("-" * 70)
            
            for r in model_results:
                print(
                    f"{r.edge_threshold:>5.1f}+ | "
                    f"{r.total_bets:>5} | "
                    f"{r.wins:>5} | "
                    f"{r.win_rate*100:>5.1f}% | "
                    f"{r.units_won:>+7.1f} | "
                    f"{r.roi*100:>+6.1f}%"
                )
    
    def save_results(self, results: Dict[str, List[ROIResults]], output_path: Path):
        """Save results to JSON."""
        output = {
            "timestamp": datetime.now().isoformat(),
            "results": {
                model: [r.to_dict() for r in model_results]
                for model, model_results in results.items()
            }
        }
        
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"\nResults saved to: {output_path}")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ROI Simulator")
    parser.add_argument("--season", type=int, default=2024, help="Season to simulate")
    parser.add_argument("--output", type=str, help="Output file path")
    args = parser.parse_args()
    
    simulator = ROISimulator()
    
    print("Loading historical odds...")
    simulator.load_historical_odds()
    
    print(f"\nSimulating season {args.season}...")
    results = simulator.simulate_season(args.season)
    
    simulator.print_results(results)
    
    if args.output:
        simulator.save_results(results, Path(args.output))


if __name__ == "__main__":
    main()
