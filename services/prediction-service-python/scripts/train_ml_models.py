#!/usr/bin/env python3
"""
Train NCAAM ML Models.

This script trains XGBoost models for each bet type using historical data.
It implements proper time-series cross-validation to prevent data leakage.

Usage:
    # From services/prediction-service-python/
    $env:PYTHONPATH = "."; python scripts/train_ml_models.py
    
    # With custom date range:
    $env:PYTHONPATH = "."; python scripts/train_ml_models.py --start 2020-11-01 --end 2024-03-31
    
    # From Docker:
    docker-compose exec prediction-service python scripts/train_ml_models.py

Requirements:
    - Database with historical games and ratings
    - XGBoost: pip install xgboost
    - scikit-learn: pip install scikit-learn
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    parser = argparse.ArgumentParser(description="Train NCAAM ML models")
    parser.add_argument(
        "--start", 
        default="2019-11-01",
        help="Training start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end",
        default="2024-03-31",
        help="Training end date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory for models (default: app/ml/trained_models/)"
    )
    parser.add_argument(
        "--bet-type",
        default=None,
        choices=["fg_spread", "fg_total", "h1_spread", "h1_total"],
        help="Train only a specific bet type (default: train all)"
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL (default: from DATABASE_URL env var)"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("NCAAM ML Model Training")
    print("=" * 70)
    print(f"\nDate range: {args.start} to {args.end}")
    print(f"Output dir: {args.output or 'app/ml/trained_models/'}")
    print()
    
    # Get database URL
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ Error: DATABASE_URL not set")
        print("   Set DATABASE_URL environment variable or use --database-url")
        sys.exit(1)
    
    # Check dependencies
    try:
        import xgboost
        print(f"✓ XGBoost version: {xgboost.__version__}")
    except ImportError:
        print("❌ XGBoost not installed. Run: pip install xgboost")
        sys.exit(1)
    
    try:
        import sklearn
        print(f"✓ scikit-learn version: {sklearn.__version__}")
    except ImportError:
        print("❌ scikit-learn not installed. Run: pip install scikit-learn")
        sys.exit(1)
    
    try:
        from sqlalchemy import create_engine
        print("✓ SQLAlchemy available")
    except ImportError:
        print("❌ SQLAlchemy not installed")
        sys.exit(1)
    
    print()
    
    # Import training pipeline
    try:
        from app.ml.training import TrainingPipeline, TrainingConfig
        from app.ml.models import BetPredictionModel
    except ImportError as e:
        print(f"❌ Import error: {e}")
        sys.exit(1)
    
    # Create engine
    from sqlalchemy import create_engine
    engine = create_engine(database_url)
    
    # Test connection
    print("🔗 Connecting to database...")
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT COUNT(*) FROM games WHERE status = 'completed'")
            count = result.scalar()
            print(f"   Found {count:,} completed games")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)
    
    print()
    
    # Configure training
    config = TrainingConfig(
        start_date=args.start,
        end_date=args.end,
        n_splits=5,
        min_train_size=500,
    )
    
    output_dir = Path(args.output) if args.output else None
    pipeline = TrainingPipeline(engine, config, output_dir)
    
    # Train models
    if args.bet_type:
        # Train single model
        print(f"📊 Training {args.bet_type} model...")
        print("-" * 70)
        try:
            model = pipeline.train_model(args.bet_type)
            _print_model_summary(model)
        except Exception as e:
            print(f"❌ Training failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        # Train all models
        bet_types = ["fg_spread", "fg_total", "h1_spread", "h1_total"]
        results = {}
        
        for bet_type in bet_types:
            print(f"\n📊 Training {bet_type} model...")
            print("-" * 70)
            try:
                model = pipeline.train_model(bet_type)
                results[bet_type] = model
                _print_model_summary(model)
            except Exception as e:
                print(f"❌ {bet_type} training failed: {e}")
                import traceback
                traceback.print_exc()
        
        # Print final summary
        print("\n" + "=" * 70)
        print("TRAINING COMPLETE")
        print("=" * 70)
        
        print(f"\nSuccessfully trained: {len(results)}/{len(bet_types)} models")
        print(f"Models saved to: {pipeline.output_dir}")
        
        if results:
            print("\nModel Performance Summary:")
            print("-" * 50)
            print(f"{'Model':<15} {'Accuracy':>10} {'AUC-ROC':>10} {'Brier':>10}")
            print("-" * 50)
            for bet_type, model in results.items():
                if model.metadata:
                    print(
                        f"{bet_type:<15} "
                        f"{model.metadata.accuracy:>10.3f} "
                        f"{model.metadata.auc_roc:>10.3f} "
                        f"{model.metadata.brier_score:>10.4f}"
                    )
    
    print("\n✅ Done!")


def _print_model_summary(model: "BetPredictionModel"):
    """Print summary of trained model."""
    if not model.metadata:
        print("   (No metadata available)")
        return
    
    m = model.metadata
    
    print(f"\n   Training samples: {m.training_samples:,}")
    print(f"   Validation samples: {m.validation_samples:,}")
    print(f"\n   Cross-validation metrics:")
    print(f"     - Accuracy:    {m.accuracy:.3f}")
    print(f"     - AUC-ROC:     {m.auc_roc:.3f}")
    print(f"     - Log Loss:    {m.log_loss:.4f}")
    print(f"     - Brier Score: {m.brier_score:.4f}")
    
    # Top features
    if m.feature_importance:
        print(f"\n   Top 5 features:")
        sorted_features = sorted(
            m.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        for name, importance in sorted_features:
            print(f"     - {name}: {importance:.3f}")


if __name__ == "__main__":
    main()
