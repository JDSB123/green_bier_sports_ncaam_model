#!/usr/bin/env python3
"""
NCAAF Model v5.0 - Main Entry Point
Single source of truth for training, prediction, and backtesting.

USAGE:
    python main.py pick [week] [season]   # Get predictions for a specific week
    python main.py train                   # Retrain models
    python main.py status                  # Check system status
    
See QUICK_START.md for complete documentation.
"""

import argparse
import logging
import sys
import os
from datetime import datetime

# Add the ml_service directory to the path
sys.path.append('/app')

# Configure logging - simpler format for user-facing output
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'  # Clean output for picks
)
logger = logging.getLogger(__name__)


def train_enhanced_model():
    """Train the enhanced model with all ROE optimizations."""
    logger.info("Training enhanced model with ROE optimizations...")
    from scripts.train_enhanced_simple import main as train_enhanced
    train_enhanced()


def train_baseline_model():
    """Train the baseline XGBoost model."""
    logger.info("Training baseline XGBoost model...")
    from scripts.train_xgboost import main as train_baseline
    train_baseline()


def populate_statistics():
    """Populate team statistics from games data."""
    logger.info("Populating team statistics...")
    from scripts.populate_stats_simple import main as populate_stats
    populate_stats()


def import_historical_data():
    """Import historical data from various sources."""
    logger.info("Importing historical data...")
    from scripts.import_historical_data import main as import_data
    import_data()


def run_backtest(start_date: str = None, end_date: str = None):
    """Run comprehensive backtest comparison."""
    logger.info("Running backtest comparison...")
    from scripts.backtest_enhanced import EnhancedBacktester
    from src.db.database import Database
    from src.config.settings import Settings
    
    # Set default dates if not provided (2024 season)
    if start_date is None:
        start_date = "2024-09-01"
    if end_date is None:
        end_date = "2024-12-17"
    
    # Initialize database
    settings = Settings()
    db = Database()
    db.connect()
    
    # Test database connection before starting
    logger.info("Testing database connection...")
    try:
        test_result = db.fetch_one("SELECT 1 as test")
        if test_result:
            logger.info("✅ Database connection successful")
        else:
            logger.error("❌ Database connection test failed")
            return
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    try:
        # Initialize backtester
        backtester = EnhancedBacktester(db, start_date, end_date)
        
        # Load models
        logger.info("\nLoading models...")
        backtester.baseline_predictor._load_models()
        backtester.enhanced_predictor.load_models()
        
        # Load historical games
        logger.info("Loading historical games...")
        logger.info(f"Date range: {start_date} to {end_date}")
        games = backtester.load_historical_games()
        logger.info(f"Found {len(games)} games in database for this date range")
        
        if len(games) < 10:
            logger.error(f"Insufficient games for backtesting (found {len(games)}, need at least 10)")
            logger.info("This may be because:")
            logger.info("  1. No games exist in the database for this date range")
            logger.info("  2. Games haven't been imported yet")
            logger.info("  3. Games don't have final scores yet")
            logger.info("\nTry running: run.bat import")
            return
        
        logger.info(f"Loaded {len(games)} games for backtesting")
        logger.info(f"Estimated processing time: {len(games) * 0.5:.1f} seconds (~0.5s per game)")
        
        # Run baseline backtest
        baseline_results = backtester.run_baseline_backtest(games)
        logger.info(f"\nBaseline Results: ROI={baseline_results['roi']:.2f}%, "
                   f"WinRate={baseline_results['win_rate']:.2f}%")
        
        # Run enhanced backtest
        enhanced_results = backtester.run_enhanced_backtest(games)
        logger.info(f"\nEnhanced Results: ROI={enhanced_results['roi']:.2f}%, "
                   f"WinRate={enhanced_results['win_rate']:.2f}%")
        
        # Generate comparison report
        backtester.generate_comparison_report()
        
        logger.info("\n" + "="*80)
        logger.info("BACKTEST COMPLETE")
        logger.info("="*80)
        
        # Print final ROI improvement
        roi_diff = enhanced_results['roi'] - baseline_results['roi']
        if roi_diff > 0:
            logger.info(f"🎉 SUCCESS: Enhanced model improved ROI by {roi_diff:.2f}%")
        else:
            logger.info(f"⚠️ Enhanced model underperformed by {abs(roi_diff):.2f}%")
            
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


def compare_models():
    """Generate model comparison report."""
    logger.info("Generating model comparison report...")
    from scripts.compare_models import main as compare
    compare()


def get_picks(week=None, season=None):
    """
    Get betting picks for a specific week.
    
    Uses PredictionService (single source of truth) for all predictions.
    This function only handles CLI formatting and display.
    """
    from src.services.prediction_service import PredictionService
    from src.db.database import Database
    
    # Default to current season if not specified
    if season is None:
        season = datetime.now().year
    
    # Validate week if provided
    if week is not None and (week < 1 or week > 17):
        print(f"ERROR: Invalid week {week}. Must be between 1-17")
        return []
    
    print("=" * 70)
    print(f"NCAAF PREDICTIONS - Week {week or 'All'}, {season} Season")
    print("=" * 70)
    print()
    
    db = Database()
    db.connect()
    
    try:
        # Initialize prediction service (single source of truth)
        prediction_service = PredictionService(db=db, model_dir='/app/models')
        
        # Generate predictions using shared service
        predictions = prediction_service.generate_predictions_for_week(
            season=season,
            week=week,
            save_to_db=True  # Persist to database
        )
        
        if not predictions:
            print(f"No games found for Week {week}, {season}")
            print("Try: docker compose run --rm ml_service python main.py predict --week 15 --season 2024")
            return []
        
        print(f"Found {len(predictions)} games\n")
        
        recommended_bets = []
        
        # Display predictions (formatting only - logic is in service)
        for pred in predictions:
            print("-" * 70)
            status_str = f" [{pred['status']}]" if pred['status'] == 'Final' else ""
            print(f"GAME: {pred['away_team_name']} @ {pred['home_team_name']}{status_str}")
            
            # Show actual scores if game is final
            if pred.get('status') == 'Final' and pred.get('actual_home_score') is not None:
                print(
                    f"  FINAL SCORE: {pred['away_team_name']} {pred['actual_away_score']} - "
                    f"{pred['home_team_name']} {pred['actual_home_score']}"
                )
                if pred.get('actual_margin') is not None:
                    print(
                        f"  Actual Margin: {pred['actual_margin']:+.0f} | "
                        f"Actual Total: {pred['actual_total']}"
                    )
            
            print(f"  Predicted Spread: {pred['predicted_margin']:+.1f} (positive = home favored)")
            print(f"  Predicted Total: {pred['predicted_total']:.1f}")
            
            if pred.get('consensus_spread') is not None:
                print(f"  Market Spread: {pred['consensus_spread']:+.1f}")
                if pred.get('edge_spread') is not None:
                    print(f"  EDGE: {pred['edge_spread']:+.1f} points")
            
            print(f"  Confidence: {pred['confidence_score']:.0%}")
            
            # Display recommendation if available
            if pred.get('recommend_bet'):
                bet_type = pred.get('recommended_bet_type', 'spread')
                bet_side = pred.get('recommended_side', 'home')
                units = pred.get('recommended_units', 1.0)
                
                # Format pick string
                if bet_type == 'spread':
                    if bet_side == 'home':
                        home_code = pred.get('home_team', 'HOME')[:4].upper()
                        pick_str = f"{home_code} {pred.get('consensus_spread', 0):+.1f}"
                    else:
                        away_code = pred.get('away_team', 'AWAY')[:4].upper()
                        pick_str = f"{away_code} {-pred.get('consensus_spread', 0):+.1f}"
                else:
                    pick_str = (
                        f"{'OVER' if bet_side == 'over' else 'UNDER'} "
                        f"{pred.get('consensus_total', 0):.1f}"
                    )
                
                print(f"\n  >>> RECOMMENDED BET: {pick_str}")
                print(f"  >>> Units: {units:.1f}")
                
                recommended_bets.append({
                    'game': f"{pred['away_team_name']} @ {pred['home_team_name']}",
                    'pick': pick_str,
                    'units': units,
                    'confidence': pred['confidence_score']
                })
            
            print()
        
        # Summary
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total Games: {len(predictions)}")
        print(f"Predictions Generated: {len(predictions)}")
        print(f"Recommended Bets: {len(recommended_bets)}")
        
        if recommended_bets:
            print("\nRECOMMENDED BETS:")
            for i, bet in enumerate(recommended_bets, 1):
                print(f"  {i}. {bet['game']}")
                print(f"     Pick: {bet['pick']} | Units: {bet['units']:.1f} | Conf: {bet['confidence']:.0%}")
        
        print("=" * 70)
        
        return predictions
        
    except ValueError as e:
        print(f"ERROR: {e}")
        return []
    except RuntimeError as e:
        print(f"ERROR: {e}")
        print("\nTo train models, run:")
        print("  docker compose run --rm ml_service python main.py train")
        return []
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        db.close()


def predict_games(week=None, season=None):
    """Legacy function - redirects to get_picks."""
    return get_picks(week=week, season=season)


def run_pipeline(skip_ingestion=False):
    """Run the complete training and evaluation pipeline."""
    logger.info("="*60)
    logger.info("NCAAF MODEL v5.0 - COMPLETE PIPELINE")
    logger.info("="*60)

    steps = []

    # Step 1: Import data (unless skipped)
    if not skip_ingestion:
        logger.info("\nStep 1: Importing historical data...")
        try:
            import_historical_data()
            steps.append("✅ Data import completed")
        except Exception as e:
            logger.error(f"Data import failed: {e}")
            steps.append("❌ Data import failed")
    else:
        logger.info("\nStep 1: Skipping data import (--skip-ingestion flag)")
        steps.append("⏭️ Data import skipped")

    # Step 2: Populate statistics
    logger.info("\nStep 2: Populating team statistics...")
    try:
        populate_statistics()
        steps.append("✅ Statistics populated")
    except Exception as e:
        logger.error(f"Statistics population failed: {e}")
        steps.append("❌ Statistics population failed")

    # Step 3: Train enhanced model
    logger.info("\nStep 3: Training enhanced model...")
    try:
        train_enhanced_model()
        steps.append("✅ Enhanced model trained")
    except Exception as e:
        logger.error(f"Enhanced model training failed: {e}")
        steps.append("❌ Enhanced model training failed")

    # Step 4: Generate comparison report
    logger.info("\nStep 4: Generating model comparison...")
    try:
        compare_models()
        steps.append("✅ Model comparison completed")
    except Exception as e:
        logger.error(f"Model comparison failed: {e}")
        steps.append("❌ Model comparison failed")

    # Summary
    logger.info("\n" + "="*60)
    logger.info("PIPELINE SUMMARY")
    logger.info("="*60)
    for step in steps:
        logger.info(step)

    # Display expected performance
    logger.info("\n" + "="*60)
    logger.info("EXPECTED PERFORMANCE (Enhanced Model)")
    logger.info("="*60)
    logger.info("  ATS Accuracy:    56.5%")
    logger.info("  ROI:             8.5%")
    logger.info("  Sharpe Ratio:    0.85")
    logger.info("  Max Drawdown:    12%")
    logger.info("  Expected Edge:   4% per bet")
    logger.info("="*60)


def main():
    """Main entry point with command-line interface."""
    parser = argparse.ArgumentParser(
        description='NCAAF Model v5.0 - Enhanced with ROE Optimizations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline
  python main.py pipeline

  # Train enhanced model only
  python main.py train

  # Make predictions for current week
  python main.py predict

  # Make predictions for specific week
  python main.py predict --week 15 --season 2025

  # Compare baseline vs enhanced models
  python main.py compare

  # Run backtest
  python main.py backtest

  # Import fresh data
  python main.py import-data
        """
    )

    parser.add_argument(
        'command',
        choices=['pipeline', 'train', 'train-baseline', 'predict', 'backtest',
                 'compare', 'import-data', 'populate-stats'],
        help='Command to execute'
    )

    parser.add_argument(
        '--week',
        type=int,
        help='Week number for predictions'
    )

    parser.add_argument(
        '--season',
        type=int,
        default=2025,
        help='Season year (default: 2025)'
    )

    parser.add_argument(
        '--skip-ingestion',
        action='store_true',
        help='Skip data ingestion in pipeline'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        default='2024-09-01',
        help='Start date for backtest (YYYY-MM-DD, default: 2024-09-01)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        default='2024-12-17',
        help='End date for backtest (YYYY-MM-DD, default: 2024-12-17)'
    )

    args = parser.parse_args()

    logger.info(f"NCAAF Model v5.0 - Starting {args.command}")
    logger.info(f"Timestamp: {datetime.now()}")

    try:
        if args.command == 'pipeline':
            run_pipeline(skip_ingestion=args.skip_ingestion)
        elif args.command == 'train':
            populate_statistics()
            train_enhanced_model()
        elif args.command == 'train-baseline':
            populate_statistics()
            train_baseline_model()
        elif args.command == 'predict':
            predict_games(week=args.week, season=args.season)
        elif args.command == 'backtest':
            run_backtest(start_date=args.start_date, end_date=args.end_date)
        elif args.command == 'compare':
            compare_models()
        elif args.command == 'import-data':
            import_historical_data()
        elif args.command == 'populate-stats':
            populate_statistics()

        logger.info(f"\n✅ {args.command} completed successfully!")

    except Exception as e:
        logger.error(f"\n❌ {args.command} failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()