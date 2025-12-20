"""
Enhanced NCAAF Predictor with Monte Carlo Simulation and Ensemble Methods

Key improvements:
- Monte Carlo simulation for confidence intervals
- Ensemble model architecture
- Enhanced confidence scoring
- Sharp vs public line comparison
- Kelly Criterion optimization
"""

import numpy as np
import pandas as pd
import joblib
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class MonteCarloPredictor:
    """Monte Carlo simulation for prediction uncertainty quantification."""

    def __init__(self, base_model, n_simulations: int = 1000):
        """
        Initialize Monte Carlo predictor.

        Args:
            base_model: Base XGBoost model
            n_simulations: Number of Monte Carlo simulations
        """
        self.base_model = base_model
        self.n_simulations = n_simulations
        self.feature_stds = None

    def fit_feature_variance(self, X_train: np.ndarray):
        """
        Calculate feature standard deviations from training data.

        Args:
            X_train: Training feature matrix
        """
        self.feature_stds = np.std(X_train, axis=0)
        self.feature_stds[self.feature_stds == 0] = 0.01  # Avoid zero std

    def predict_with_uncertainty(
        self,
        features: np.ndarray,
        confidence_level: float = 0.95
    ) -> Dict:
        """
        Generate predictions with uncertainty quantification.

        Args:
            features: Feature array for a single game
            confidence_level: Confidence level for intervals

        Returns:
            Dictionary with mean, std, confidence intervals, and win probability
        """
        if self.feature_stds is None:
            # If no training data, use 5% noise
            self.feature_stds = np.abs(features) * 0.05

        predictions = []

        for _ in range(self.n_simulations):
            # Add Gaussian noise based on feature variance
            noise = np.random.normal(0, self.feature_stds * 0.1)
            noisy_features = features + noise

            # Clip to reasonable ranges
            noisy_features = np.clip(noisy_features, features - self.feature_stds,
                                    features + self.feature_stds)

            # Make prediction
            pred = self.base_model.predict(noisy_features.reshape(1, -1))[0]
            predictions.append(pred)

        predictions = np.array(predictions)

        # Calculate statistics
        mean_pred = np.mean(predictions)
        std_pred = np.std(predictions)

        # Confidence intervals
        alpha = 1 - confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100

        return {
            'mean': mean_pred,
            'std': std_pred,
            'confidence_interval': (
                np.percentile(predictions, lower_percentile),
                np.percentile(predictions, upper_percentile)
            ),
            'percentile_25': np.percentile(predictions, 25),
            'percentile_75': np.percentile(predictions, 75),
            'win_probability': float(predictions > 0).mean() if mean_pred != 0 else 0.5,
            'distribution': predictions  # Full distribution for advanced analysis
        }


class EnsembleNCAAFPredictor:
    """
    Enhanced NCAAF predictor with ensemble methods and Monte Carlo simulation.

    Combines multiple modeling approaches:
    1. XGBoost (primary)
    2. Rolling average predictor
    3. Exponential weighted predictor
    4. Monte Carlo simulation for uncertainty
    """

    def __init__(self, model_dir: str = "/app/models"):
        """
        Initialize enhanced predictor.

        Args:
            model_dir: Directory containing trained models
        """
        self.model_dir = Path(model_dir)
        self.models = {}
        self.monte_carlo = {}
        self.feature_columns = []
        self.ensemble_weights = {
            'xgboost': 0.60,
            'rolling_avg': 0.20,
            'exp_weighted': 0.20
        }
        self.historical_predictions = []

    def load_models(self):
        """Load all models and initialize Monte Carlo simulators."""
        logger.info("Loading enhanced models...")

        # Load XGBoost models
        model_names = ['margin', 'total', 'home_score', 'away_score']

        for name in model_names:
            # Try enhanced model first, fallback to standard
            enhanced_path = self.model_dir / f'xgboost_{name}_enhanced.pkl'
            standard_path = self.model_dir / f'xgboost_{name}.pkl'

            if enhanced_path.exists():
                self.models[name] = joblib.load(enhanced_path)
                logger.info(f"Loaded enhanced {name} model")
            elif standard_path.exists():
                self.models[name] = joblib.load(standard_path)
                logger.info(f"Loaded standard {name} model")
            else:
                logger.warning(f"Model {name} not found")

            # Initialize Monte Carlo simulator
            if name in self.models:
                self.monte_carlo[name] = MonteCarloPredictor(
                    self.models[name],
                    n_simulations=1000
                )

        # Load feature columns
        enhanced_cols_path = self.model_dir / 'feature_columns_enhanced.pkl'
        standard_cols_path = self.model_dir / 'feature_columns.pkl'

        if enhanced_cols_path.exists():
            self.feature_columns = joblib.load(enhanced_cols_path)
        elif standard_cols_path.exists():
            self.feature_columns = joblib.load(standard_cols_path)

        logger.info(f"Models loaded. Features: {len(self.feature_columns)}")

    def predict(
        self,
        features: Dict[str, float],
        use_monte_carlo: bool = True,
        use_ensemble: bool = True
    ) -> Dict:
        """
        Generate enhanced predictions with uncertainty quantification.

        Args:
            features: Dictionary of feature values
            use_monte_carlo: Whether to use Monte Carlo simulation
            use_ensemble: Whether to use ensemble methods

        Returns:
            Dictionary with predictions, confidence intervals, and recommendations
        """
        # Prepare feature array
        feature_array = np.array([features.get(col, 0.0) for col in self.feature_columns])

        predictions = {}

        # Get base predictions
        for model_name in ['margin', 'total', 'home_score', 'away_score']:
            if model_name not in self.models:
                continue

            if use_monte_carlo and model_name in self.monte_carlo:
                # Monte Carlo prediction with uncertainty
                mc_result = self.monte_carlo[model_name].predict_with_uncertainty(feature_array)
                predictions[model_name] = mc_result['mean']
                predictions[f'{model_name}_std'] = mc_result['std']
                predictions[f'{model_name}_ci'] = mc_result['confidence_interval']
                predictions[f'{model_name}_win_prob'] = mc_result['win_probability']
            else:
                # Standard prediction
                predictions[model_name] = self.models[model_name].predict(
                    feature_array.reshape(1, -1)
                )[0]

        # Apply ensemble methods if enabled
        if use_ensemble:
            ensemble_predictions = self._apply_ensemble(predictions, features)
            predictions.update(ensemble_predictions)

        # Calculate confidence score
        confidence = self._calculate_enhanced_confidence(features, predictions)
        predictions['confidence'] = confidence

        # Generate betting recommendations
        recommendations = self._generate_recommendations(predictions, features, confidence)
        predictions.update(recommendations)

        # Store for rolling calculations
        self.historical_predictions.append(predictions)
        if len(self.historical_predictions) > 100:
            self.historical_predictions.pop(0)

        return predictions

    def _apply_ensemble(self, base_predictions: Dict, features: Dict) -> Dict:
        """Apply ensemble methods to combine predictions."""
        ensemble_preds = {}

        # Rolling average (if we have history)
        if len(self.historical_predictions) >= 3:
            rolling_window = 3
            recent = self.historical_predictions[-rolling_window:]

            for key in ['margin', 'total']:
                if key in base_predictions:
                    rolling_avg = np.mean([p.get(key, 0) for p in recent])
                    ensemble_preds[f'{key}_rolling'] = rolling_avg

        # Exponential weighted average
        if len(self.historical_predictions) >= 2:
            alpha = 0.3  # Smoothing factor
            for key in ['margin', 'total']:
                if key in base_predictions:
                    ewm_values = []
                    weight = 1.0
                    total_weight = 0.0

                    for p in reversed(self.historical_predictions[-5:]):
                        if key in p:
                            ewm_values.append(p[key] * weight)
                            total_weight += weight
                            weight *= (1 - alpha)

                    if total_weight > 0:
                        ensemble_preds[f'{key}_ewm'] = sum(ewm_values) / total_weight

        # Combine ensemble predictions
        for key in ['margin', 'total']:
            if key in base_predictions:
                ensemble_components = [
                    (base_predictions[key], self.ensemble_weights['xgboost'])
                ]

                if f'{key}_rolling' in ensemble_preds:
                    ensemble_components.append(
                        (ensemble_preds[f'{key}_rolling'], self.ensemble_weights['rolling_avg'])
                    )

                if f'{key}_ewm' in ensemble_preds:
                    ensemble_components.append(
                        (ensemble_preds[f'{key}_ewm'], self.ensemble_weights['exp_weighted'])
                    )

                # Weighted average
                total_weight = sum(w for _, w in ensemble_components)
                weighted_sum = sum(v * w for v, w in ensemble_components)
                ensemble_preds[f'{key}_ensemble'] = weighted_sum / total_weight

        return ensemble_preds

    def _calculate_enhanced_confidence(self, features: Dict, predictions: Dict) -> float:
        """
        Calculate enhanced confidence score.

        Factors:
        - Talent differential
        - Opponent-adjusted efficiency
        - Line movement signals
        - Monte Carlo uncertainty
        - Recent form consistency
        - SRS differential
        """
        confidence = 0.5  # Base confidence

        # Talent differential (0.0 - 0.15)
        talent_diff = abs(features.get('talent_differential', 0))
        confidence += min(talent_diff / 100 * 0.15, 0.15)

        # Opponent-adjusted efficiency (0.0 - 0.15)
        adj_off_diff = abs(features.get('adj_offensive_diff', 0))
        adj_def_diff = abs(features.get('adj_defensive_diff', 0))
        efficiency_factor = (adj_off_diff + adj_def_diff) / 20.0
        confidence += min(efficiency_factor * 0.15, 0.15)

        # Line movement agreement (0.0 - 0.10)
        sharp_movement = features.get('sharp_line_movement', 0)
        public_movement = features.get('public_line_movement', 0)

        if sharp_movement != 0 and public_movement != 0:
            # Sharp and public agree on direction
            if np.sign(sharp_movement) == np.sign(public_movement):
                confidence += 0.05

            # Reverse line movement (sharp money indicator)
            if features.get('reverse_line_movement', 0) > 0:
                confidence += 0.05

        # Monte Carlo uncertainty (0.0 - 0.10)
        if 'margin_std' in predictions:
            # Lower std = higher confidence
            std_factor = 1.0 / (1.0 + predictions['margin_std'] / 10.0)
            confidence += std_factor * 0.10

        # Recent form consistency (0.0 - 0.05)
        home_recent = abs(features.get('home_recent_margin', 0))
        away_recent = abs(features.get('away_recent_margin', 0))

        if home_recent > 7 or away_recent > 7:
            confidence += 0.05

        # SRS differential (0.0 - 0.05)
        srs_diff = abs(features.get('srs_differential', 0))
        confidence += min(srs_diff / 20.0 * 0.05, 0.05)

        # Cap confidence between 0 and 1
        return min(max(confidence, 0.0), 1.0)

    def _generate_recommendations(
        self,
        predictions: Dict,
        features: Dict,
        confidence: float
    ) -> Dict:
        """
        Generate enhanced betting recommendations.

        Uses:
        - Kelly Criterion for bet sizing
        - Sharp vs public line analysis
        - Monte Carlo confidence intervals
        - Multiple bet types (spread, total, ML)
        """
        recommendations = {}

        # Minimum confidence threshold
        MIN_CONFIDENCE = 0.60

        # Edge thresholds
        SPREAD_EDGE_THRESHOLD = 2.5
        TOTAL_EDGE_THRESHOLD = 3.5

        # Get market consensus (could be from database)
        market_spread = features.get('consensus_spread', 0)
        market_total = features.get('consensus_total', 50)

        # Check spread bet
        if 'margin' in predictions and confidence >= MIN_CONFIDENCE:
            pred_spread = predictions.get('margin_ensemble', predictions['margin'])
            edge = abs(pred_spread - market_spread)

            if edge >= SPREAD_EDGE_THRESHOLD:
                recommendations['recommend_spread_bet'] = True
                recommendations['spread_side'] = 'home' if pred_spread < market_spread else 'away'

                # Kelly Criterion sizing
                win_prob = predictions.get('margin_win_prob', 0.55)
                kelly_fraction = self._calculate_kelly_fraction(win_prob, -110)  # Standard vig
                recommendations['spread_units'] = self._calculate_bet_units(
                    kelly_fraction, confidence, edge, 'spread'
                )
            else:
                recommendations['recommend_spread_bet'] = False

        # Check total bet
        if 'total' in predictions and confidence >= MIN_CONFIDENCE:
            pred_total = predictions.get('total_ensemble', predictions['total'])
            edge = abs(pred_total - market_total)

            if edge >= TOTAL_EDGE_THRESHOLD:
                recommendations['recommend_total_bet'] = True
                recommendations['total_side'] = 'over' if pred_total > market_total else 'under'

                # Kelly sizing
                total_confidence = confidence * 0.9  # Totals typically less predictable
                recommendations['total_units'] = self._calculate_bet_units(
                    0.05, total_confidence, edge, 'total'  # Conservative Kelly
                )
            else:
                recommendations['recommend_total_bet'] = False

        # Overall recommendation
        recommendations['recommend_bet'] = (
            recommendations.get('recommend_spread_bet', False) or
            recommendations.get('recommend_total_bet', False)
        )

        # Add confidence band information
        if 'margin_ci' in predictions:
            lower, upper = predictions['margin_ci']
            recommendations['spread_confidence_band'] = (lower, upper)
            recommendations['high_confidence'] = (upper - lower) < 10  # Tight band

        # Sharp vs public analysis
        if features.get('reverse_line_movement', 0) > 0:
            recommendations['sharp_money_indicator'] = True
            recommendations['follow_sharp'] = True

        return recommendations

    def _calculate_kelly_fraction(self, win_prob: float, odds: int) -> float:
        """
        Calculate Kelly Criterion fraction.

        Args:
            win_prob: Probability of winning
            odds: American odds

        Returns:
            Kelly fraction (capped at 0.25 for safety)
        """
        # Convert American odds to decimal
        if odds > 0:
            decimal_odds = (odds / 100) + 1
        else:
            decimal_odds = (100 / abs(odds)) + 1

        # Kelly formula: f = (p * (b + 1) - 1) / b
        # where p = win probability, b = decimal odds - 1
        b = decimal_odds - 1
        kelly = (win_prob * decimal_odds - 1) / b

        # Cap at 25% of bankroll (quarter Kelly for safety)
        return min(max(kelly / 4, 0), 0.25)

    def _calculate_bet_units(
        self,
        kelly_fraction: float,
        confidence: float,
        edge: float,
        bet_type: str
    ) -> float:
        """
        Calculate recommended bet units.

        Args:
            kelly_fraction: Kelly Criterion fraction
            confidence: Model confidence
            edge: Predicted edge over market
            bet_type: Type of bet (spread/total)

        Returns:
            Recommended units (0.5 to 3.0)
        """
        # Base units from Kelly
        base_units = kelly_fraction * 100  # Convert to units (1 unit = 1% of bankroll)

        # Adjust by confidence
        confidence_multiplier = confidence / 0.75  # Scale around 0.75 confidence
        adjusted_units = base_units * confidence_multiplier

        # Adjust by edge size
        if bet_type == 'spread':
            edge_multiplier = min(edge / 5.0, 2.0)  # Cap at 2x for 5+ point edge
        else:  # total
            edge_multiplier = min(edge / 7.0, 2.0)  # More conservative for totals

        final_units = adjusted_units * edge_multiplier

        # Cap between 0.5 and 3.0 units
        return min(max(final_units, 0.5), 3.0)

    def backtest_predictions(
        self,
        historical_games: List[Dict],
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Backtest the enhanced prediction system.

        Args:
            historical_games: List of historical games with outcomes
            start_date: Start date for backtest
            end_date: End date for backtest

        Returns:
            Dictionary with backtest results and performance metrics
        """
        correct_predictions = 0
        total_predictions = 0
        total_return = 0.0
        predictions_log = []

        for game in historical_games:
            # Extract features for game
            features = game['features']

            # Make prediction
            prediction = self.predict(features, use_monte_carlo=True, use_ensemble=True)

            # Check if we recommended a bet
            if prediction['recommend_bet']:
                total_predictions += 1

                # Check spread bet
                if prediction.get('recommend_spread_bet'):
                    actual_margin = game['actual_margin']
                    pred_margin = prediction.get('margin_ensemble', prediction['margin'])

                    # Did we win?
                    if prediction['spread_side'] == 'home':
                        won = actual_margin < game['spread']
                    else:
                        won = actual_margin > game['spread']

                    if won:
                        correct_predictions += 1
                        total_return += prediction['spread_units'] * 0.91  # -110 odds
                    else:
                        total_return -= prediction['spread_units']

                # Check total bet
                if prediction.get('recommend_total_bet'):
                    actual_total = game['actual_total']

                    if prediction['total_side'] == 'over':
                        won = actual_total > game['total']
                    else:
                        won = actual_total < game['total']

                    if won:
                        total_return += prediction['total_units'] * 0.91
                    else:
                        total_return -= prediction['total_units']

                predictions_log.append({
                    'game_id': game['game_id'],
                    'prediction': prediction,
                    'actual_margin': game['actual_margin'],
                    'actual_total': game['actual_total']
                })

        # Calculate metrics
        win_rate = correct_predictions / max(total_predictions, 1)
        roi = total_return / max(total_predictions, 1)

        # Sharpe ratio calculation
        returns = [p['return'] for p in predictions_log if 'return' in p]
        sharpe = np.mean(returns) / max(np.std(returns), 0.01) if returns else 0

        return {
            'total_predictions': total_predictions,
            'correct_predictions': correct_predictions,
            'win_rate': win_rate,
            'total_return': total_return,
            'roi': roi,
            'sharpe_ratio': sharpe,
            'predictions_log': predictions_log
        }