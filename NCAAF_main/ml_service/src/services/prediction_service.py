"""
Prediction Service - Single Source of Truth

This is THE single source of truth for generating predictions.
Both CLI and API endpoints use this service to ensure consistency.

All operations are:
- Hardened with validation
- Error-resilient
- Logged for audit
- Database-persistent (optional)
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from src.models.predictor import NCAAFPredictor
from src.features.feature_extractor import FeatureExtractor
from src.services.consensus_service import ConsensusService
from src.db.database import Database, fetch_games_by_week, fetch_latest_odds, save_prediction

logger = logging.getLogger(__name__)


class PredictionService:
    """
    Single source of truth for generating NCAAF predictions.
    
    This service orchestrates:
    1. Game data retrieval
    2. Feature extraction
    3. Consensus calculation
    4. Model prediction
    5. Recommendation generation
    6. Database persistence (optional)
    
    Used by both CLI (main.py) and API (src/api/main.py) to ensure consistency.
    """
    
    def __init__(
        self,
        db: Optional[Database] = None,
        predictor: Optional[NCAAFPredictor] = None,
        model_dir: str = "/app/models"
    ):
        """
        Initialize prediction service.
        
        Args:
            db: Database instance (creates new if None)
            predictor: Predictor instance (creates new if None)
            model_dir: Directory containing trained models
        """
        self.db = db or Database()
        if not hasattr(self.db, 'pool') or self.db.pool is None:
            self.db.connect()
        
        self.predictor = predictor
        if self.predictor is None:
            try:
                self.predictor = NCAAFPredictor(model_dir=model_dir)
                logger.info(f"Predictor initialized from {model_dir}")
            except Exception as e:
                logger.error(f"Failed to load predictor: {e}")
                raise RuntimeError(f"Models not loaded. Train models first: {e}")
        
        self.feature_extractor = FeatureExtractor(self.db)
        self.consensus_service = ConsensusService(prefer_sharp=True)
        
        # Validate models are loaded
        if not self.predictor.models.get('margin') or not self.predictor.models.get('total'):
            raise RuntimeError(
                "Models not loaded. Run 'python main.py train' or "
                "'docker compose run --rm ml_service python main.py train'"
            )
    
    def generate_predictions_for_week(
        self,
        season: int,
        week: int,
        save_to_db: bool = True,
        model_name: str = 'xgboost_v1'
    ) -> List[Dict]:
        """
        Generate predictions for all games in a week.
        
        This is THE single method used by both CLI and API.
        
        Args:
            season: Season year (e.g., 2024)
            week: Week number (1-17)
            save_to_db: Whether to persist predictions to database
            model_name: Model name for database storage
        
        Returns:
            List of prediction dictionaries with:
            - game_id, home_team, away_team, game_date, status
            - predicted_margin, predicted_total, predicted_home_score, predicted_away_score
            - consensus_spread, consensus_total
            - edge_spread, edge_total
            - confidence_score
            - recommend_bet, recommended_bet_type, recommended_side, recommended_units
            - rationale
        
        Raises:
            ValueError: If season/week invalid
            RuntimeError: If models not loaded or database error
        """
        # Input validation
        if not isinstance(season, int) or season < 2020 or season > 2100:
            raise ValueError(f"Invalid season: {season}. Must be between 2020-2100")
        
        if not isinstance(week, int) or week < 1 or week > 17:
            raise ValueError(f"Invalid week: {week}. Must be between 1-17")
        
        logger.info(f"Generating predictions for Season {season}, Week {week}")
        
        try:
            # Fetch games
            games = fetch_games_by_week(season, week)
            
            if not games:
                logger.warning(f"No games found for Season {season}, Week {week}")
                return []
            
            logger.info(f"Found {len(games)} games for Season {season}, Week {week}")
            
            predictions = []
            errors = []
            
            # Process each game
            for game in games:
                try:
                    prediction = self._predict_single_game(
                        game=game,
                        season=season,
                        week=week,
                        save_to_db=save_to_db,
                        model_name=model_name
                    )
                    
                    if prediction:
                        predictions.append(prediction)
                
                except Exception as e:
                    error_msg = (
                        f"Failed to predict game {game.get('game_id', 'unknown')}: {e}"
                    )
                    logger.error(error_msg, exc_info=True)
                    errors.append({
                        'game_id': game.get('game_id'),
                        'error': str(e)
                    })
                    # Continue processing other games (resilient)
                    continue
            
            # Log summary
            successful = len(predictions)
            failed = len(errors)
            recommended = sum(1 for p in predictions if p.get('recommend_bet', False))
            
            logger.info(
                f"Prediction generation complete: {successful} successful, "
                f"{failed} failed, {recommended} recommended bets"
            )
            
            if errors:
                logger.warning(f"Errors encountered: {errors}")
            
            # Sort by recommendation strength (best bets first)
            predictions.sort(
                key=lambda p: (
                    p.get('recommend_bet', False),
                    p.get('recommended_units', 0),
                    p.get('confidence_score', 0)
                ),
                reverse=True
            )
            
            return predictions
        
        except Exception as e:
            logger.error(f"Prediction generation failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to generate predictions: {e}") from e
    
    def _predict_single_game(
        self,
        game: Dict,
        season: int,
        week: int,
        save_to_db: bool,
        model_name: str
    ) -> Optional[Dict]:
        """
        Generate prediction for a single game.
        
        Internal method - handles one game with full error handling.
        """
        game_id = game.get('id')
        game_api_id = game.get('game_id')
        
        if not game_id:
            logger.warning("Game missing database ID, skipping")
            return None
        
        # Extract features
        try:
            features = self.feature_extractor.extract_game_features(
                home_team_id=game['home_team_id'],
                away_team_id=game['away_team_id'],
                season=season,
                week=week
            )
        except Exception as e:
            logger.error(f"Feature extraction failed for game {game_api_id}: {e}")
            raise
        
        # Fetch odds and calculate consensus
        consensus_spread = None
        consensus_total = None
        
        try:
            odds = fetch_latest_odds(game_id)
            if odds:
                consensus_spread, consensus_total = self.consensus_service.calculate_consensus(
                    odds=odds,
                    book_type='sharp'  # Prefer sharp books
                )
        except Exception as e:
            logger.warning(f"Failed to fetch/calculate consensus for game {game_api_id}: {e}")
            # Continue without consensus (still generate prediction)
        
        # Generate prediction using model
        try:
            prediction = self.predictor.predict_game(
                features=features,
                consensus_spread=consensus_spread,
                consensus_total=consensus_total
            )
        except Exception as e:
            logger.error(f"Model prediction failed for game {game_api_id}: {e}")
            raise
        
        # Add game context
        prediction['game_id'] = game_api_id
        prediction['game_db_id'] = game_id
        # Handle both field name variations (home_team_name vs home_team)
        prediction['home_team'] = game.get('home_team_code') or game.get('home_team', 'Unknown')
        prediction['away_team'] = game.get('away_team_code') or game.get('away_team', 'Unknown')
        prediction['home_team_name'] = game.get('home_team_name') or game.get('home_team', 'Unknown')
        prediction['away_team_name'] = game.get('away_team_name') or game.get('away_team', 'Unknown')
        prediction['game_date'] = game.get('game_date')
        prediction['status'] = game.get('status', 'Scheduled')
        prediction['season'] = season
        prediction['week'] = week
        
        # Add actual scores if game is final
        if game.get('status') == 'Final':
            prediction['actual_home_score'] = game.get('home_score')
            prediction['actual_away_score'] = game.get('away_score')
            if game.get('home_score') is not None and game.get('away_score') is not None:
                prediction['actual_margin'] = game['home_score'] - game['away_score']
                prediction['actual_total'] = game['home_score'] + game['away_score']
        
        # Save to database if requested
        if save_to_db:
            try:
                save_prediction(
                    game_id=game_id,
                    model_name=model_name,
                    predicted_home_score=prediction['predicted_home_score'],
                    predicted_away_score=prediction['predicted_away_score'],
                    predicted_total=prediction['predicted_total'],
                    predicted_margin=prediction['predicted_margin'],
                    confidence_score=prediction['confidence_score'],
                    consensus_spread=consensus_spread,
                    consensus_total=consensus_total,
                    edge_spread=prediction.get('edge_spread'),
                    edge_total=prediction.get('edge_total'),
                    recommend_bet=prediction.get('recommend_bet', False),
                    recommended_bet_type=prediction.get('recommended_bet_type'),
                    recommended_side=prediction.get('recommended_side'),
                    recommended_units=prediction.get('recommended_units', 0.0),
                    rationale=prediction.get('rationale')
                )
                logger.debug(f"Prediction saved to database for game {game_api_id}")
            except Exception as e:
                logger.error(f"Failed to save prediction to database for game {game_api_id}: {e}")
                # Don't fail the whole operation if DB save fails
        
        return prediction
    
    def get_recommended_bets(
        self,
        predictions: List[Dict],
        min_confidence: float = 0.6,
        min_units: float = 0.5
    ) -> List[Dict]:
        """
        Filter predictions to only recommended bets.
        
        Args:
            predictions: List of prediction dictionaries
            min_confidence: Minimum confidence score (0-1)
            min_units: Minimum recommended units
        
        Returns:
            Filtered list of recommended bets
        """
        return [
            p for p in predictions
            if (
                p.get('recommend_bet', False) and
                p.get('confidence_score', 0) >= min_confidence and
                p.get('recommended_units', 0) >= min_units
            )
        ]
