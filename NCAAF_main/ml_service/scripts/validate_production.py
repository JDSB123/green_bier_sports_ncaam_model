#!/usr/bin/env python3
"""
Production Readiness Validation Script
Runs all validation checks for production deployment
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import Database
from pathlib import Path
import joblib

class ValidationResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def add_pass(self, message: str):
        self.passed.append(message)
        print(f"✓ PASS: {message}")
    
    def add_fail(self, message: str, error: str = ""):
        self.failed.append(message)
        print(f"✗ FAIL: {message}")
        if error:
            print(f"  → {error}")
    
    def add_warn(self, message: str):
        self.warnings.append(message)
        print(f"⚠ WARN: {message}")
    
    def print_summary(self):
        print("\n" + "="*60)
        print("Validation Summary")
        print("="*60)
        print(f"\nPassed: {len(self.passed)}")
        print(f"Failed: {len(self.failed)}")
        print(f"Warnings: {len(self.warnings)}")
        
        total = len(self.passed) + len(self.failed)
        if total > 0:
            success_rate = (len(self.passed) / total) * 100
            print(f"Success Rate: {success_rate:.1f}%")
        
        if self.failed:
            print("\nFailed Tests:")
            for msg in self.failed:
                print(f"  - {msg}")
        
        if self.warnings:
            print("\nWarnings:")
            for msg in self.warnings:
                print(f"  - {msg}")
        
        return len(self.failed) == 0

def validate_database(result: ValidationResult, db: Database):
    """Validate database connection and schema"""
    print("\n1. Checking Database...")
    
    try:
        result.add_pass("Database connection successful")
        
        # Check schema
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                # Count tables
                cur.execute("""
                    SELECT COUNT(*) as table_count
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                row = cur.fetchone()
                table_count = row['table_count'] if isinstance(row, dict) else row[0]
                result.add_pass(f"Database schema exists ({table_count} tables)")
                
                # Check critical tables
                critical_tables = ['teams', 'games', 'odds', 'predictions', 'team_season_stats']
                missing = []
                for table in critical_tables:
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = %s
                        ) as exists
                    """, (table,))
                    row = cur.fetchone()
                    exists = row['exists'] if isinstance(row, dict) else row[0]
                    if exists:
                        result.add_pass(f"Table '{table}' exists")
                    else:
                        missing.append(table)
                        result.add_fail(f"Table '{table}' missing")
                
                if missing:
                    result.add_fail(f"Missing critical tables: {', '.join(missing)}")
    except Exception as e:
        error_msg = str(e) if e else "Unknown error"
        result.add_fail("Database validation failed", error_msg)

def validate_seed_data(result: ValidationResult, db: Database):
    """Validate seed data exists"""
    print("\n2. Checking Seed Data...")
    
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                # Check teams
                cur.execute("SELECT COUNT(*) as count FROM teams")
                row = cur.fetchone()
                team_count = row['count'] if isinstance(row, dict) else row[0]
                if team_count >= 50:
                    result.add_pass(f"Teams table populated ({team_count} teams)")
                else:
                    result.add_warn(f"Teams table has only {team_count} teams (expected 50+)")
                
                # Check stadiums
                cur.execute("SELECT COUNT(*) as count FROM stadiums")
                row = cur.fetchone()
                stadium_count = row['count'] if isinstance(row, dict) else row[0]
                if stadium_count >= 50:
                    result.add_pass(f"Stadiums table populated ({stadium_count} stadiums)")
                else:
                    result.add_warn(f"Stadiums table has only {stadium_count} stadiums (expected 50+)")
                
                # Check games
                cur.execute("SELECT COUNT(*) as count FROM games")
                row = cur.fetchone()
                game_count = row['count'] if isinstance(row, dict) else row[0]
                if game_count > 0:
                    result.add_pass(f"Games data exists ({game_count} games)")
                else:
                    result.add_warn("No games data yet")
    except Exception as e:
        error_msg = str(e) if e else "Unknown error"
        result.add_fail("Seed data validation failed", error_msg)

def validate_models(result: ValidationResult):
    """Validate ML models exist and can be loaded"""
    print("\n3. Checking ML Models...")
    
    model_dir = Path("/app/models")
    
    # Check enhanced models
    enhanced_dir = model_dir / "enhanced"
    if enhanced_dir.exists():
        spread_model = enhanced_dir / "spread_model.pkl"
        total_model = enhanced_dir / "total_model.pkl"
        
        if spread_model.exists():
            try:
                joblib.load(spread_model)
                result.add_pass("Enhanced spread model exists and loads")
            except Exception as e:
                result.add_fail("Enhanced spread model cannot be loaded", str(e))
        else:
            result.add_fail("Enhanced spread model missing")
        
        if total_model.exists():
            try:
                joblib.load(total_model)
                result.add_pass("Enhanced total model exists and loads")
            except Exception as e:
                result.add_fail("Enhanced total model cannot be loaded", str(e))
        else:
            result.add_fail("Enhanced total model missing")
    else:
        result.add_fail("Enhanced models directory missing")

def validate_feature_extraction(result: ValidationResult, db: Database):
    """Validate feature extraction works"""
    print("\n4. Checking Feature Extraction...")
    
    try:
        from src.features.feature_extractor_enhanced import EnhancedFeatureExtractor
        
        extractor = EnhancedFeatureExtractor(db)
        
        # Try to extract features for a sample game
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT home_team_id, away_team_id, season, week FROM games LIMIT 1")
                result_row = cur.fetchone()
                
                if result_row:
                    home_id = result_row['home_team_id']
                    away_id = result_row['away_team_id']
                    season = result_row['season']
                    week = result_row['week']
                    
                    features = extractor.extract_game_features(
                        home_team_id=home_id,
                        away_team_id=away_id,
                        season=season,
                        week=week
                    )
                    if features and len(features) > 0:
                        result.add_pass(f"Feature extraction working ({len(features)} features)")
                    else:
                        result.add_fail("Feature extraction returned no features")
                else:
                    result.add_warn("Feature extraction skipped (no games in database)")
    except Exception as e:
        result.add_fail("Feature extraction failed", str(e))
        import traceback
        traceback.print_exc()

def validate_predictions(result: ValidationResult, db: Database):
    """Validate predictions can be generated"""
    print("\n5. Checking Predictions Generation...")
    
    try:
        from src.models.predictor_enhanced import EnsembleNCAAFPredictor
        from src.features.feature_extractor_enhanced import EnhancedFeatureExtractor
        
        predictor = EnsembleNCAAFPredictor()
        predictor.load_models()
        result.add_pass("Models loaded successfully")
        
        extractor = EnhancedFeatureExtractor(db)
        
        # Try to generate a prediction
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT home_team_id, away_team_id, season, week FROM games WHERE status = 'Scheduled' LIMIT 1")
                result_row = cur.fetchone()
                
                if result_row:
                    home_id = result_row['home_team_id']
                    away_id = result_row['away_team_id']
                    season = result_row['season']
                    week = result_row['week']
                    
                    features = extractor.extract_game_features(
                        home_team_id=home_id,
                        away_team_id=away_id,
                        season=season,
                        week=week
                    )
                    
                    prediction = predictor.predict(features, use_monte_carlo=True, use_ensemble=True)
                    
                    if prediction and 'predicted_margin' in prediction:
                        result.add_pass("Predictions generation working")
                    else:
                        result.add_fail("Predictions generation returned invalid result")
                else:
                    result.add_warn("Predictions generation skipped (no scheduled games)")
    except Exception as e:
        result.add_fail("Predictions generation failed", str(e))
        import traceback
        traceback.print_exc()

def validate_backtesting(result: ValidationResult, db: Database):
    """Validate backtesting system"""
    print("\n6. Checking Backtesting System...")
    
    backtest_script = Path("/app/scripts/backtest_enhanced.py")
    if backtest_script.exists():
        result.add_pass("Backtesting script exists")
        
        # Check if backtest tables exist
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'backtests'
                        ) as exists
                    """)
                    row = cur.fetchone()
                    exists = row['exists'] if isinstance(row, dict) else row[0]
                    if exists:
                        result.add_pass("Backtesting database tables exist")
                    else:
                        result.add_warn("Backtesting tables missing (run migrations)")
        except Exception as e:
            result.add_warn(f"Could not check backtest tables: {e}")
    else:
        result.add_fail("Backtesting script missing")

def main():
    print("="*60)
    print("NCAAF v5.0 Production Readiness Validation")
    print("All checks via Docker containers")
    print("="*60)
    
    result = ValidationResult()
    db = None
    
    try:
        # Initialize database connection once for all validations
        db = Database()
        db.connect()
        
        # Run all validations
        validate_database(result, db)
        validate_seed_data(result, db)
        validate_models(result)
        validate_feature_extraction(result, db)
        validate_predictions(result, db)
        validate_backtesting(result, db)
        
    except Exception as e:
        result.add_fail("Validation script error", str(e))
        import traceback
        traceback.print_exc()
    finally:
        # Close database connection at the end
        if db:
            try:
                db.close()
            except Exception:
                pass
    
    # Print summary
    success = result.print_summary()
    
    if success:
        if result.warnings:
            print("\n⚠ All critical tests passed, but some warnings exist.")
            print("  Review warnings above before production deployment.")
        else:
            print("\n✓ All tests passed! System is production ready.")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed. Please review and fix issues.")
        sys.exit(1)

if __name__ == "__main__":
    main()
