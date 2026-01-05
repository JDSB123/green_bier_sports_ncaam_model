"""
Production Parity Backtest Engine.

This backtest engine replicates EXACT production behavior:
1. Same team resolution (4-step exact matching, NO fuzzy)
2. Same prediction models (FGSpread, H1Spread, FGTotal, H1Total)
3. Strict anti-leakage (Season N-1 ratings for Season N games)
4. All timestamps standardized to CST

This ensures backtest results are representative of live performance.

Usage:
    from testing.production_parity.backtest_engine import ProductionParityBacktest
    backtest = ProductionParityBacktest()
    results = backtest.run()
"""

import csv
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Add prediction-service-python to path for production model imports
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "services" / "prediction-service-python"))

from .timezone_utils import (
    parse_date_to_cst,
    get_season_for_game,
    format_cst,
    now_cst,
)
from .team_resolver import ProductionTeamResolver
from .ratings_loader import AntiLeakageRatingsLoader, TeamRatings
from .audit_logger import BacktestAuditLogger


# Try to import production models
try:
    from app.predictors.fg_spread import FGSpreadModel
    from app.predictors.fg_total import FGTotalModel
    from app.predictors.h1_spread import H1SpreadModel
    from app.predictors.h1_total import H1TotalModel
    PRODUCTION_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"[BacktestEngine] Warning: Production models not available: {e}")
    PRODUCTION_MODELS_AVAILABLE = False


@dataclass
class GameRecord:
    """Parsed game record from CSV."""
    game_id: str
    date: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    actual_margin: int
    actual_total: int
    home_h1: Optional[int] = None
    away_h1: Optional[int] = None
    neutral: bool = False

    @property
    def h1_margin(self) -> Optional[int]:
        if self.home_h1 is not None and self.away_h1 is not None:
            return self.home_h1 - self.away_h1
        return None

    @property
    def h1_total(self) -> Optional[int]:
        if self.home_h1 is not None and self.away_h1 is not None:
            return self.home_h1 + self.away_h1
        return None


@dataclass
class PredictionResult:
    """Result of model prediction for a game."""
    game_id: str
    model_name: str
    prediction: float
    actual: float
    error: float
    abs_error: float
    direction_correct: bool
    inputs: dict


@dataclass
class BacktestStats:
    """Aggregate statistics from backtest."""
    total_games: int
    games_predicted: int
    games_skipped: int
    skip_reasons: Dict[str, int]

    # By model
    fg_spread_mae: float
    fg_spread_direction_accuracy: float
    fg_spread_count: int

    h1_spread_mae: float
    h1_spread_direction_accuracy: float
    h1_spread_count: int

    fg_total_mae: float
    fg_total_direction_accuracy: float
    fg_total_count: int

    h1_total_mae: float
    h1_total_direction_accuracy: float
    h1_total_count: int

    # Overall
    team_resolution_rate: float
    ratings_found_rate: float


class ProductionParityBacktest:
    """
    Production Parity Backtest Engine.

    Ensures backtest uses EXACT same logic as production:
    - Same team resolution (4-step exact matching)
    - Same prediction models
    - Strict anti-leakage (Season N-1 ratings)
    - CST timezone standardization
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        seasons: Optional[List[int]] = None,
    ):
        """
        Initialize the backtest engine.

        Args:
            data_dir: Directory containing historical games and ratings
            output_dir: Directory to write audit logs and results
            seasons: List of seasons to backtest (default: all available)
        """
        if data_dir is None:
            data_dir = ROOT_DIR / "testing" / "data" / "historical"

        if output_dir is None:
            output_dir = ROOT_DIR / "testing" / "production_parity" / "audit_logs"

        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.seasons = seasons

        # Initialize components
        self.resolver = ProductionTeamResolver()
        self.ratings_loader = AntiLeakageRatingsLoader(
            data_dir=self.data_dir,
            team_resolver=self.resolver,
        )
        self.logger = BacktestAuditLogger(output_dir=self.output_dir)

        # Initialize models (if available)
        if PRODUCTION_MODELS_AVAILABLE:
            self.fg_spread_model = FGSpreadModel()
            self.fg_total_model = FGTotalModel()
            self.h1_spread_model = H1SpreadModel()
            self.h1_total_model = H1TotalModel()
            print("[BacktestEngine] Using PRODUCTION prediction models")
        else:
            self.fg_spread_model = None
            self.fg_total_model = None
            self.h1_spread_model = None
            self.h1_total_model = None
            print("[BacktestEngine] Using FALLBACK prediction formulas")

        # Results storage
        self.predictions: List[PredictionResult] = []
        self.games: List[GameRecord] = []

    def load_games(self, filepath: Optional[Path] = None) -> List[GameRecord]:
        """Load games from CSV file."""
        if filepath is None:
            # Prefer h1_games_all.csv (has both FG and H1 scores)
            h1_path = ROOT_DIR / "testing" / "data" / "h1_historical" / "h1_games_all.csv"
            if h1_path.exists():
                filepath = h1_path
                print(f"[BacktestEngine] Using H1 data source: {filepath.name}")
            else:
                filepath = self.data_dir / "games_all.csv"
                print(f"[BacktestEngine] H1 data not found, using: {filepath.name}")

        if not filepath.exists():
            print(f"[BacktestEngine] Games file not found: {filepath}")
            return []

        games = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Parse FG scores (support both column naming conventions)
                    # h1_games_all.csv uses: home_fg, away_fg
                    # games_all.csv uses: home_score, away_score
                    home_score = int(row.get("home_fg") or row.get("home_score") or 0)
                    away_score = int(row.get("away_fg") or row.get("away_score") or 0)

                    # Skip games without scores
                    if home_score == 0 and away_score == 0:
                        continue

                    # Parse H1 scores if available
                    home_h1 = None
                    away_h1 = None
                    if row.get("home_h1"):
                        home_h1 = int(row["home_h1"])
                    if row.get("away_h1"):
                        away_h1 = int(row["away_h1"])

                    # Parse neutral site flag
                    neutral = str(row.get("neutral", "False")).lower() == "true"

                    game = GameRecord(
                        game_id=row["game_id"],
                        date=row["date"],
                        home_team=row["home_team"],
                        away_team=row["away_team"],
                        home_score=home_score,
                        away_score=away_score,
                        actual_margin=home_score - away_score,
                        actual_total=home_score + away_score,
                        home_h1=home_h1,
                        away_h1=away_h1,
                        neutral=neutral,
                    )

                    # Filter by season if specified
                    if self.seasons:
                        game_season = get_season_for_game(game.date)
                        if game_season not in self.seasons:
                            continue

                    games.append(game)

                except (ValueError, KeyError) as e:
                    continue

        print(f"[BacktestEngine] Loaded {len(games)} games")
        self.games = games
        return games

    def _predict_spread_fallback(
        self,
        home: TeamRatings,
        away: TeamRatings,
        is_neutral: bool = False,
    ) -> float:
        """Fallback spread prediction when production models unavailable."""
        HCA = 5.8
        hca = 0.0 if is_neutral else HCA

        # Net rating approach
        home_net = home.adj_o - home.adj_d
        away_net = away.adj_o - away.adj_d
        raw_margin = (home_net - away_net) / 2.0

        return -(raw_margin + hca)

    def _predict_total_fallback(
        self,
        home: TeamRatings,
        away: TeamRatings,
    ) -> float:
        """Fallback total prediction when production models unavailable."""
        CALIBRATION = 7.0
        LEAGUE_AVG_TEMPO = 67.6
        LEAGUE_AVG_EFF = 105.5

        avg_tempo = home.tempo + away.tempo - LEAGUE_AVG_TEMPO
        home_eff = home.adj_o + away.adj_d - LEAGUE_AVG_EFF
        away_eff = away.adj_o + home.adj_d - LEAGUE_AVG_EFF

        home_pts = home_eff * avg_tempo / 100.0
        away_pts = away_eff * avg_tempo / 100.0

        return home_pts + away_pts + CALIBRATION

    def _predict_h1_spread_fallback(
        self,
        home: TeamRatings,
        away: TeamRatings,
        is_neutral: bool = False,
    ) -> float:
        """Fallback H1 spread prediction."""
        fg_spread = self._predict_spread_fallback(home, away, is_neutral)
        return fg_spread * 0.50  # H1 is roughly 50% of FG

    def _predict_h1_total_fallback(
        self,
        home: TeamRatings,
        away: TeamRatings,
    ) -> float:
        """Fallback H1 total prediction."""
        fg_total = self._predict_total_fallback(home, away)
        return fg_total * 0.485 + 2.7  # H1 ratio + calibration

    def process_game(self, game: GameRecord) -> Dict[str, Any]:
        """
        Process a single game through the prediction pipeline.

        Returns dict with predictions and metadata.
        """
        # Start audit record
        game_season = get_season_for_game(game.date)
        ratings_season = game_season - 1

        audit_record = self.logger.log_game_start(
            game_id=game.game_id,
            game_date_cst=game.date,
            home_team_raw=game.home_team,
            away_team_raw=game.away_team,
            game_season=game_season,
            ratings_season=ratings_season,
        )

        # Resolve team names
        home_result = self.resolver.resolve(game.home_team)
        away_result = self.resolver.resolve(game.away_team)

        self.logger.log_team_resolution(
            game.game_id, is_home=True,
            raw_name=game.home_team,
            canonical_name=home_result.canonical_name,
            resolution_step=home_result.step_used,
        )
        self.logger.log_team_resolution(
            game.game_id, is_home=False,
            raw_name=game.away_team,
            canonical_name=away_result.canonical_name,
            resolution_step=away_result.step_used,
        )

        # Check if teams resolved
        # Import ResolutionStep for NON_D1 check
        from .team_resolver import ResolutionStep

        if not home_result.resolved:
            if home_result.step_used == ResolutionStep.NON_D1:
                self.logger.log_game_skipped(game.game_id, f"Home team is non-D1: {game.home_team}")
                return {"skipped": True, "reason": f"non_d1: {game.home_team}"}
            else:
                self.logger.log_game_skipped(game.game_id, f"Home team unresolved: {game.home_team}")
                return {"skipped": True, "reason": f"home_team_unresolved: {game.home_team}"}

        if not away_result.resolved:
            if away_result.step_used == ResolutionStep.NON_D1:
                self.logger.log_game_skipped(game.game_id, f"Away team is non-D1: {game.away_team}")
                return {"skipped": True, "reason": f"non_d1: {game.away_team}"}
            else:
                self.logger.log_game_skipped(game.game_id, f"Away team unresolved: {game.away_team}")
                return {"skipped": True, "reason": f"away_team_unresolved: {game.away_team}"}

        # Get ratings with anti-leakage
        home_ratings, away_ratings, meta = self.ratings_loader.get_matchup_ratings(
            home_result.canonical_name,
            away_result.canonical_name,
            game.date,
        )

        self.logger.log_ratings_lookup(
            game.game_id, is_home=True,
            team_name=home_result.canonical_name,
            found=home_ratings is not None,
            ratings_dict=asdict(home_ratings) if home_ratings else None,
        )
        self.logger.log_ratings_lookup(
            game.game_id, is_home=False,
            team_name=away_result.canonical_name,
            found=away_ratings is not None,
            ratings_dict=asdict(away_ratings) if away_ratings else None,
        )

        # Check if ratings found
        if home_ratings is None:
            self.logger.log_game_skipped(
                game.game_id,
                f"No Season {ratings_season} ratings for: {home_result.canonical_name}"
            )
            return {"skipped": True, "reason": f"home_ratings_missing_season_{ratings_season}"}

        if away_ratings is None:
            self.logger.log_game_skipped(
                game.game_id,
                f"No Season {ratings_season} ratings for: {away_result.canonical_name}"
            )
            return {"skipped": True, "reason": f"away_ratings_missing_season_{ratings_season}"}

        # Run predictions
        predictions = {}

        # FG Spread
        if self.fg_spread_model:
            pred = self.fg_spread_model.predict(
                home_ratings, away_ratings, is_neutral=game.neutral
            )
            fg_spread_pred = pred.value
        else:
            fg_spread_pred = self._predict_spread_fallback(
                home_ratings, away_ratings, is_neutral=game.neutral
            )

        predictions["fg_spread"] = fg_spread_pred
        self.logger.log_prediction(
            game.game_id, "FGSpread", fg_spread_pred,
            {"home_adj_o": home_ratings.adj_o, "away_adj_o": away_ratings.adj_o}
        )

        # FG Total
        if self.fg_total_model:
            pred = self.fg_total_model.predict(
                home_ratings, away_ratings, is_neutral=game.neutral
            )
            fg_total_pred = pred.value
        else:
            fg_total_pred = self._predict_total_fallback(home_ratings, away_ratings)

        predictions["fg_total"] = fg_total_pred
        self.logger.log_prediction(
            game.game_id, "FGTotal", fg_total_pred,
            {"home_tempo": home_ratings.tempo, "away_tempo": away_ratings.tempo}
        )

        # H1 Spread
        if self.h1_spread_model:
            pred = self.h1_spread_model.predict(
                home_ratings, away_ratings, is_neutral=game.neutral
            )
            h1_spread_pred = pred.value
        else:
            h1_spread_pred = self._predict_h1_spread_fallback(
                home_ratings, away_ratings, is_neutral=game.neutral
            )

        predictions["h1_spread"] = h1_spread_pred
        self.logger.log_prediction(game.game_id, "H1Spread", h1_spread_pred, {})

        # H1 Total
        if self.h1_total_model:
            pred = self.h1_total_model.predict(
                home_ratings, away_ratings, is_neutral=game.neutral
            )
            h1_total_pred = pred.value
        else:
            h1_total_pred = self._predict_h1_total_fallback(home_ratings, away_ratings)

        predictions["h1_total"] = h1_total_pred
        self.logger.log_prediction(game.game_id, "H1Total", h1_total_pred, {})

        # Log outcomes and calculate errors
        self.logger.log_game_outcome(
            game.game_id,
            game.home_score, game.away_score,
            game.home_h1, game.away_h1,
        )

        # Store prediction results
        for model_name, pred_value in predictions.items():
            if model_name.endswith("_spread"):
                if model_name.startswith("h1"):
                    actual = game.h1_margin
                else:
                    actual = game.actual_margin
            else:  # total
                if model_name.startswith("h1"):
                    actual = game.h1_total
                else:
                    actual = game.actual_total

            if actual is not None:
                error = pred_value - (-actual if "spread" in model_name else actual)
                # For spreads: prediction is negative for home favored
                # actual_margin is positive for home win
                # So direction_correct = (prediction < 0 and actual > 0) or (prediction > 0 and actual < 0)
                if "spread" in model_name:
                    # Model spread is negative = home favored
                    # Actual margin is positive = home won
                    pred_home_wins = pred_value < 0
                    actual_home_won = actual > 0
                    direction_correct = pred_home_wins == actual_home_won
                else:  # total
                    # Not applicable for totals (need market line)
                    direction_correct = None

                self.predictions.append(PredictionResult(
                    game_id=game.game_id,
                    model_name=model_name,
                    prediction=pred_value,
                    actual=actual,
                    error=error,
                    abs_error=abs(error),
                    direction_correct=direction_correct,
                    inputs={
                        "home": home_result.canonical_name,
                        "away": away_result.canonical_name,
                        "ratings_season": ratings_season,
                    }
                ))

        return {
            "skipped": False,
            "predictions": predictions,
            "actuals": {
                "margin": game.actual_margin,
                "total": game.actual_total,
                "h1_margin": game.h1_margin,
                "h1_total": game.h1_total,
            },
            "metadata": meta,
        }

    def run(
        self,
        games_file: Optional[Path] = None,
        max_games: Optional[int] = None,
        verbose: bool = True,
    ) -> BacktestStats:
        """
        Run the full backtest.

        Args:
            games_file: Path to games CSV (default: games_all.csv)
            max_games: Limit number of games (for testing)
            verbose: Print progress

        Returns:
            BacktestStats with aggregate results
        """
        print("\n" + "=" * 60)
        print("PRODUCTION PARITY BACKTEST")
        print("=" * 60)
        print(f"Started at: {format_cst(now_cst())}")
        print(f"Models: {'PRODUCTION' if PRODUCTION_MODELS_AVAILABLE else 'FALLBACK'}")

        # Load games
        games = self.load_games(games_file)
        if max_games:
            games = games[:max_games]

        skip_reasons: Dict[str, int] = {}
        games_predicted = 0

        # Process each game
        for i, game in enumerate(games):
            if verbose and (i + 1) % 500 == 0:
                print(f"  Processed {i + 1}/{len(games)} games...")

            result = self.process_game(game)

            if result.get("skipped"):
                reason = result.get("reason", "unknown")
                # Categorize skip reasons
                if reason.startswith("non_d1"):
                    key = "non_d1_team"
                elif "unresolved" in reason:
                    key = "team_unresolved"
                elif "ratings_missing" in reason:
                    key = "ratings_missing"
                else:
                    key = reason
                skip_reasons[key] = skip_reasons.get(key, 0) + 1
            else:
                games_predicted += 1

        # Calculate statistics
        stats = self._calculate_stats(
            total_games=len(games),
            games_predicted=games_predicted,
            games_skipped=len(games) - games_predicted,
            skip_reasons=skip_reasons,
        )

        # Print summary
        self.logger.print_summary()

        # Export audit logs
        self.logger.export_to_csv()
        self.logger.export_to_json()

        return stats

    def _calculate_stats(
        self,
        total_games: int,
        games_predicted: int,
        games_skipped: int,
        skip_reasons: Dict[str, int],
    ) -> BacktestStats:
        """Calculate aggregate statistics from predictions."""

        def calc_model_stats(model_name: str) -> Tuple[float, float, int]:
            model_preds = [p for p in self.predictions if p.model_name == model_name]
            if not model_preds:
                return 0.0, 0.0, 0

            mae = sum(p.abs_error for p in model_preds) / len(model_preds)

            # Direction accuracy (for spreads only)
            if "spread" in model_name:
                direction_preds = [p for p in model_preds if p.direction_correct is not None]
                if direction_preds:
                    direction_acc = sum(1 for p in direction_preds if p.direction_correct) / len(direction_preds)
                else:
                    direction_acc = 0.0
            else:
                direction_acc = 0.0

            return mae, direction_acc, len(model_preds)

        fg_spread_mae, fg_spread_dir, fg_spread_count = calc_model_stats("fg_spread")
        h1_spread_mae, h1_spread_dir, h1_spread_count = calc_model_stats("h1_spread")
        fg_total_mae, fg_total_dir, fg_total_count = calc_model_stats("fg_total")
        h1_total_mae, h1_total_dir, h1_total_count = calc_model_stats("h1_total")

        # Calculate resolution and ratings rates
        resolver_stats = self.resolver.get_stats()
        loader_stats = self.ratings_loader.get_stats()

        return BacktestStats(
            total_games=total_games,
            games_predicted=games_predicted,
            games_skipped=games_skipped,
            skip_reasons=skip_reasons,
            fg_spread_mae=fg_spread_mae,
            fg_spread_direction_accuracy=fg_spread_dir,
            fg_spread_count=fg_spread_count,
            h1_spread_mae=h1_spread_mae,
            h1_spread_direction_accuracy=h1_spread_dir,
            h1_spread_count=h1_spread_count,
            fg_total_mae=fg_total_mae,
            fg_total_direction_accuracy=fg_total_dir,
            fg_total_count=fg_total_count,
            h1_total_mae=h1_total_mae,
            h1_total_direction_accuracy=h1_total_dir,
            h1_total_count=h1_total_count,
            team_resolution_rate=resolver_stats.get("success_rate", 0),
            ratings_found_rate=loader_stats.get("success_rate", 0),
        )

    def print_stats(self, stats: BacktestStats) -> None:
        """Print statistics summary."""
        print("\n" + "=" * 60)
        print("BACKTEST STATISTICS")
        print("=" * 60)

        print(f"\nGames:")
        print(f"  Total:     {stats.total_games}")
        print(f"  Predicted: {stats.games_predicted}")
        print(f"  Skipped:   {stats.games_skipped}")

        print(f"\nSkip Reasons:")
        for reason, count in stats.skip_reasons.items():
            print(f"  {reason}: {count}")

        print(f"\nFG Spread (n={stats.fg_spread_count}):")
        print(f"  MAE:               {stats.fg_spread_mae:.2f} pts")
        print(f"  Direction Acc:     {stats.fg_spread_direction_accuracy:.1%}")

        print(f"\nH1 Spread (n={stats.h1_spread_count}):")
        print(f"  MAE:               {stats.h1_spread_mae:.2f} pts")
        print(f"  Direction Acc:     {stats.h1_spread_direction_accuracy:.1%}")

        print(f"\nFG Total (n={stats.fg_total_count}):")
        print(f"  MAE:               {stats.fg_total_mae:.2f} pts")

        print(f"\nH1 Total (n={stats.h1_total_count}):")
        print(f"  MAE:               {stats.h1_total_mae:.2f} pts")

        print(f"\nData Quality:")
        print(f"  Team Resolution:   {stats.team_resolution_rate:.1%}")
        print(f"  Ratings Found:     {stats.ratings_found_rate:.1%}")

        print("=" * 60)
