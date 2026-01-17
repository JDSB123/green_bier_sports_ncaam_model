"""
Training Pipeline for NCAAM ML Models.

LEAKAGE PREVENTION is the #1 priority:
1. Time-series split: Train on past, validate on future
2. Rating date filtering: Only use ratings from before game date
3. No closing lines: Only use opening/pre-game lines
4. No game results in features: Only pre-game data

Training Process:
1. Load historical games with outcomes
2. Extract features (pre-game data only)
3. Time-series cross-validation
4. Train final model on all data
5. Evaluate calibration
6. Save model with metadata
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np
import structlog

from app.ml.features import FeatureEngineer, GameFeatures
from app.ml.models import BetPredictionModel, ModelMetadata

logger = structlog.get_logger(__name__)

# Canonical training window (2023-24 season onward).
CANONICAL_START_DATE = date(2023, 11, 1)
CANONICAL_START_DATE_STR = CANONICAL_START_DATE.isoformat()

# Optional imports
try:
    from sklearn.metrics import (
        accuracy_score,
        brier_score_loss,
        calibration_curve,
        log_loss,
        roc_auc_score,
    )
    from sklearn.model_selection import TimeSeriesSplit
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("scikit-learn not installed. Training will not be available.")

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


@dataclass
class TrainingConfig:
    """Configuration for model training."""

    # Date range
    start_date: str = CANONICAL_START_DATE_STR  # Start of 2023-24 season
    end_date: str = field(default_factory=lambda: date.today().isoformat())  # Defaults to today

    # Validation
    n_splits: int = 5              # Number of time-series folds
    min_train_size: int = 500      # Minimum games in training set

    # Model params (can be overridden per bet type)
    max_depth: int = 4
    learning_rate: float = 0.05
    n_estimators: int = 200
    min_child_weight: int = 10

    # Feature selection
    use_market_features: bool = True
    use_public_betting: bool = False  # Often not available historically

    def __post_init__(self) -> None:
        start = _parse_date(self.start_date)
        end = _parse_date(self.end_date)
        if start < CANONICAL_START_DATE:
            raise ValueError(
                f"start_date must be on/after {CANONICAL_START_DATE_STR}"
            )
        if end < start:
            raise ValueError("end_date must be on/after start_date")


class TrainingDataLoader:
    """
    Load historical games with outcomes for training.

    CRITICAL: This loader ensures no leakage by:
    1. Only loading games that have completed
    2. Using ratings from BEFORE the game date
    3. Using opening lines, not closing lines
    """

    def __init__(self, engine: "Engine"):
        self.engine = engine
        self.feature_engineer = FeatureEngineer()

    def load_training_data(
        self,
        start_date: str,
        end_date: str,
        bet_type: str,
    ) -> tuple[np.ndarray, np.ndarray, list[GameFeatures]]:
        """
        Load training data for a specific bet type.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            bet_type: One of "fg_spread", "fg_total", "h1_spread", "h1_total"

        Returns:
            X: Feature matrix (n_samples, n_features)
            y: Labels (n_samples,) - 1 if bet won, 0 if lost
            games: List of GameFeatures for debugging
        """
        # Build query based on bet type
        if bet_type == "fg_spread":
            query = self._build_fg_spread_query(start_date, end_date)
        elif bet_type == "fg_total":
            query = self._build_fg_total_query(start_date, end_date)
        elif bet_type == "h1_spread":
            query = self._build_h1_spread_query(start_date, end_date)
        elif bet_type == "h1_total":
            query = self._build_h1_total_query(start_date, end_date)
        else:
            raise ValueError(f"Unknown bet type: {bet_type}")

        # Execute query
        with self.engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

        if not rows:
            raise ValueError(f"No training data found for {bet_type} between {start_date} and {end_date}")

        # Convert to features and labels
        games = []
        labels = []

        for row in rows:
            try:
                game_features = self._row_to_features(row)
                label = self._extract_label(row, bet_type)

                if label is not None:  # Skip pushes
                    games.append(game_features)
                    labels.append(label)
            except Exception as e:
                logger.warning(f"Failed to process row: {e}")
                continue

        if not games:
            raise ValueError(f"No valid training samples for {bet_type}")

        # Extract feature matrix
        X = self.feature_engineer.extract_batch(games)
        y = np.array(labels, dtype=np.float32)

        logger.info(
            f"Loaded {len(games)} training samples for {bet_type}",
            positive_rate=float(y.mean()),
        )

        return X, y, games

    def _build_fg_spread_query(self, start_date: str, end_date: str) -> str:
        """
        Build query for FG spread training data.

        Label: 1 if home covered spread, 0 if not
        """
        return f"""
        WITH game_ratings AS (
            -- Get ratings from BEFORE game date to prevent leakage
            SELECT DISTINCT ON (g.id, 'home')
                g.id as game_id,
                'home' as side,
                tr.*
            FROM games g
            JOIN teams t ON g.home_team_id = t.id
            JOIN team_ratings tr ON t.id = tr.team_id
            WHERE tr.rating_date < DATE(g.commence_time)
              AND g.status = 'completed'
            ORDER BY g.id, 'home', tr.rating_date DESC
        ),
        home_ratings AS (
            SELECT * FROM game_ratings WHERE side = 'home'
        ),
        away_ratings AS (
            SELECT DISTINCT ON (g.id)
                g.id as game_id,
                tr.*
            FROM games g
            JOIN teams t ON g.away_team_id = t.id
            JOIN team_ratings tr ON t.id = tr.team_id
            WHERE tr.rating_date < DATE(g.commence_time)
              AND g.status = 'completed'
            ORDER BY g.id, tr.rating_date DESC
        ),
        opening_odds AS (
            -- First odds snapshot (opening line)
            SELECT DISTINCT ON (game_id)
                game_id,
                home_line as spread_open,
                total_line as total_open
            FROM odds_snapshots
            WHERE market_type = 'spreads'
              AND period = 'full'
            ORDER BY game_id, time ASC
        )
        SELECT
            g.id as game_id,
            DATE(g.commence_time) as game_date,
            ht.canonical_name as home_team,
            at.canonical_name as away_team,
            g.is_neutral,
            g.home_score,
            g.away_score,
            oo.spread_open,
            oo.total_open,
            -- Home ratings
            hr.adj_o as home_adj_o,
            hr.adj_d as home_adj_d,
            hr.tempo as home_tempo,
            hr.torvik_rank as home_rank,
            hr.efg as home_efg,
            hr.efgd as home_efgd,
            hr.tor as home_tor,
            hr.tord as home_tord,
            hr.orb as home_orb,
            hr.drb as home_drb,
            hr.ftr as home_ftr,
            hr.ftrd as home_ftrd,
            hr.two_pt_pct as home_two_pt_pct,
            hr.two_pt_pct_d as home_two_pt_pct_d,
            hr.three_pt_pct as home_three_pt_pct,
            hr.three_pt_pct_d as home_three_pt_pct_d,
            hr.three_pt_rate as home_three_pt_rate,
            hr.three_pt_rate_d as home_three_pt_rate_d,
            hr.barthag as home_barthag,
            hr.wab as home_wab,
            -- Away ratings
            ar.adj_o as away_adj_o,
            ar.adj_d as away_adj_d,
            ar.tempo as away_tempo,
            ar.torvik_rank as away_rank,
            ar.efg as away_efg,
            ar.efgd as away_efgd,
            ar.tor as away_tor,
            ar.tord as away_tord,
            ar.orb as away_orb,
            ar.drb as away_drb,
            ar.ftr as away_ftr,
            ar.ftrd as away_ftrd,
            ar.two_pt_pct as away_two_pt_pct,
            ar.two_pt_pct_d as away_two_pt_pct_d,
            ar.three_pt_pct as away_three_pt_pct,
            ar.three_pt_pct_d as away_three_pt_pct_d,
            ar.three_pt_rate as away_three_pt_rate,
            ar.three_pt_rate_d as away_three_pt_rate_d,
            ar.barthag as away_barthag,
            ar.wab as away_wab
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.id
        JOIN teams at ON g.away_team_id = at.id
        LEFT JOIN home_ratings hr ON g.id = hr.game_id
        LEFT JOIN away_ratings ar ON g.id = ar.game_id
        LEFT JOIN opening_odds oo ON g.id = oo.game_id
        WHERE g.status = 'completed'
          AND g.home_score IS NOT NULL
          AND g.away_score IS NOT NULL
          AND DATE(g.commence_time) BETWEEN '{start_date}' AND '{end_date}'
          AND oo.spread_open IS NOT NULL
          AND hr.adj_o IS NOT NULL
          AND ar.adj_o IS NOT NULL
        ORDER BY g.commence_time
        """

    def _build_fg_total_query(self, start_date: str, end_date: str) -> str:
        """Build query for FG total training data."""
        # Similar to spread query but we need total line
        return self._build_fg_spread_query(start_date, end_date)

    def _build_h1_spread_query(self, start_date: str, end_date: str) -> str:
        """Build query for 1H spread training data."""
        # Would need 1H scores - for now, reuse FG query structure
        # TODO: Add 1H score columns when available
        return self._build_fg_spread_query(start_date, end_date)

    def _build_h1_total_query(self, start_date: str, end_date: str) -> str:
        """Build query for 1H total training data."""
        return self._build_fg_spread_query(start_date, end_date)

    def _row_to_features(self, row) -> GameFeatures:
        """Convert database row to GameFeatures."""
        return GameFeatures(
            game_id=str(row.game_id),
            game_date=str(row.game_date),
            home_team=row.home_team,
            away_team=row.away_team,

            # Efficiency
            home_adj_o=float(row.home_adj_o or 105),
            home_adj_d=float(row.home_adj_d or 105),
            away_adj_o=float(row.away_adj_o or 105),
            away_adj_d=float(row.away_adj_d or 105),
            home_tempo=float(row.home_tempo or 67.6),
            away_tempo=float(row.away_tempo or 67.6),
            home_rank=int(row.home_rank or 175),
            away_rank=int(row.away_rank or 175),

            # Four factors
            home_efg=float(row.home_efg or 50),
            home_efgd=float(row.home_efgd or 50),
            away_efg=float(row.away_efg or 50),
            away_efgd=float(row.away_efgd or 50),
            home_tor=float(row.home_tor or 18.5),
            home_tord=float(row.home_tord or 18.5),
            away_tor=float(row.away_tor or 18.5),
            away_tord=float(row.away_tord or 18.5),
            home_orb=float(row.home_orb or 28),
            home_drb=float(row.home_drb or 72),
            away_orb=float(row.away_orb or 28),
            away_drb=float(row.away_drb or 72),
            home_ftr=float(row.home_ftr or 33),
            home_ftrd=float(row.home_ftrd or 33),
            away_ftr=float(row.away_ftr or 33),
            away_ftrd=float(row.away_ftrd or 33),

            # Shooting
            home_two_pt_pct=float(row.home_two_pt_pct or 50),
            home_two_pt_pct_d=float(row.home_two_pt_pct_d or 50),
            away_two_pt_pct=float(row.away_two_pt_pct or 50),
            away_two_pt_pct_d=float(row.away_two_pt_pct_d or 50),
            home_three_pt_pct=float(row.home_three_pt_pct or 35),
            home_three_pt_pct_d=float(row.home_three_pt_pct_d or 35),
            away_three_pt_pct=float(row.away_three_pt_pct or 35),
            away_three_pt_pct_d=float(row.away_three_pt_pct_d or 35),
            home_three_pt_rate=float(row.home_three_pt_rate or 35),
            home_three_pt_rate_d=float(row.home_three_pt_rate_d or 35),
            away_three_pt_rate=float(row.away_three_pt_rate or 35),
            away_three_pt_rate_d=float(row.away_three_pt_rate_d or 35),

            # Quality
            home_barthag=float(row.home_barthag or 0.5),
            home_wab=float(row.home_wab or 0),
            away_barthag=float(row.away_barthag or 0.5),
            away_wab=float(row.away_wab or 0),

            # Market (opening only!)
            spread_open=float(row.spread_open) if row.spread_open else None,
            total_open=float(row.total_open) if row.total_open else None,

            # Situational
            is_neutral=bool(row.is_neutral),
        )

    def _extract_label(self, row, bet_type: str) -> int | None:
        """
        Extract label (1 = bet won, 0 = bet lost, None = push).

        For spreads: 1 if home covered
        For totals: 1 if over hit
        """
        home_score = row.home_score
        away_score = row.away_score

        if home_score is None or away_score is None:
            return None

        margin = home_score - away_score  # Positive = home won
        total = home_score + away_score

        if bet_type in ("fg_spread", "h1_spread"):
            spread = row.spread_open
            if spread is None:
                return None

            # Did home cover? (margin > -spread means home covered)
            # Spread is from home perspective: -3 means home favored by 3
            cover_margin = margin + spread  # Adjusted margin

            if abs(cover_margin) < 0.5:  # Push
                return None

            return 1 if cover_margin > 0 else 0

        # Totals
        total_line = row.total_open
        if total_line is None:
            return None

        if abs(total - total_line) < 0.5:  # Push
            return None

        return 1 if total > total_line else 0


class TrainingPipeline:
    """
    End-to-end training pipeline with time-series cross-validation.

    LEAKAGE PREVENTION:
    1. Time-series splits ensure we only train on past data
    2. Rating dates are filtered in SQL
    3. Only opening lines used (not closing)
    """

    def __init__(
        self,
        engine: "Engine",
        config: TrainingConfig | None = None,
        output_dir: Path | None = None,
    ):
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn is required for training")

        self.engine = engine
        self.config = config or TrainingConfig()
        self.output_dir = output_dir or Path(__file__).parent / "trained_models"
        self.data_loader = TrainingDataLoader(engine)
        self.feature_engineer = FeatureEngineer()

    def train_all_models(self) -> dict[str, BetPredictionModel]:
        """Train all four bet type models."""
        models = {}

        for bet_type in ["fg_spread", "fg_total", "h1_spread", "h1_total"]:
            try:
                model = self.train_model(bet_type)
                models[bet_type] = model
                logger.info(f"Successfully trained {bet_type}")
            except Exception as e:
                logger.error(f"Failed to train {bet_type}: {e}")

        return models

    def train_model(self, bet_type: str) -> BetPredictionModel:
        """
        Train a single model with time-series cross-validation.

        Returns trained model with metadata.
        """
        logger.info(f"Training {bet_type} model...")

        # Load data
        X, y, games = self.data_loader.load_training_data(
            self.config.start_date,
            self.config.end_date,
            bet_type,
        )

        # Time-series cross-validation
        cv_results = self._cross_validate(X, y, bet_type)

        # Train final model on all data
        model = BetPredictionModel(bet_type)

        # Use last fold as validation for early stopping
        n = len(X)
        train_size = int(n * 0.85)
        X_train, X_val = X[:train_size], X[train_size:]
        y_train, y_val = y[:train_size], y[train_size:]

        model.fit(
            X_train, y_train,
            X_val, y_val,
            feature_names=self.feature_engineer.feature_names,
        )

        # Evaluate on held-out validation
        y_pred_proba = model.predict_proba(X_val)

        # Calibration analysis
        prob_true, prob_pred = calibration_curve(
            y_val, y_pred_proba, n_bins=10, strategy="uniform"
        )

        # Create metadata
        model.metadata = ModelMetadata(
            model_type=bet_type,
            version="1.0.0",
            trained_at=datetime.now().isoformat(),
            training_samples=len(X_train),
            validation_samples=len(X_val),
            accuracy=cv_results["accuracy"],
            log_loss=cv_results["log_loss"],
            auc_roc=cv_results["auc_roc"],
            brier_score=cv_results["brier_score"],
            calibration_bins=prob_pred.tolist(),
            calibration_actual=prob_true.tolist(),
            feature_importance=model.get_feature_importance(),
            train_start_date=self.config.start_date,
            train_end_date=self.config.end_date,
            hyperparameters=model.params,
        )

        # Save model
        model.save(self.output_dir)

        return model

    def _cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        bet_type: str,
    ) -> dict[str, float]:
        """
        Time-series cross-validation.

        Returns dict of mean metrics across folds.
        """
        tscv = TimeSeriesSplit(n_splits=self.config.n_splits)

        accuracies = []
        log_losses = []
        aucs = []
        briers = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            if len(train_idx) < self.config.min_train_size:
                continue

            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # Train fold model
            model = BetPredictionModel(bet_type)
            model.fit(X_train, y_train)

            # Evaluate
            y_pred_proba = model.predict_proba(X_val)
            y_pred = (y_pred_proba >= 0.5).astype(int)

            accuracies.append(accuracy_score(y_val, y_pred))
            log_losses.append(log_loss(y_val, y_pred_proba))
            aucs.append(roc_auc_score(y_val, y_pred_proba))
            briers.append(brier_score_loss(y_val, y_pred_proba))

            logger.info(
                f"Fold {fold + 1}: acc={accuracies[-1]:.3f}, "
                f"auc={aucs[-1]:.3f}, brier={briers[-1]:.4f}"
            )

        return {
            "accuracy": np.mean(accuracies),
            "log_loss": np.mean(log_losses),
            "auc_roc": np.mean(aucs),
            "brier_score": np.mean(briers),
        }


def train_models_from_database(
    database_url: str,
    start_date: str | None = None,
    end_date: str | None = None,
    output_dir: str | None = None,
) -> dict[str, BetPredictionModel]:
    """
    Convenience function to train all models.

    Usage:
        from app.ml.training import train_models_from_database
        models = train_models_from_database(
            "postgresql://user:pass@localhost/ncaam",
            "2023-11-01",
            "2024-03-31",
        )
    """
    if not HAS_SQLALCHEMY:
        raise ImportError("SQLAlchemy is required")

    engine = create_engine(database_url)
    defaults = TrainingConfig()
    config = TrainingConfig(
        start_date=start_date or defaults.start_date,
        end_date=end_date or defaults.end_date,
    )

    output_path = Path(output_dir) if output_dir else None
    pipeline = TrainingPipeline(engine, config, output_path)

    return pipeline.train_all_models()
