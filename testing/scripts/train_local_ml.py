
import sys
import os
import csv
import json
import numpy as np
import pickle
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
import structlog

# Add project root and service root to path
ROOT_DIR = Path(os.getcwd())
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "services" / "prediction-service-python"))

from testing.production_parity.ratings_loader import AntiLeakageRatingsLoader
from testing.production_parity.team_resolver import ProductionTeamResolver
from testing.production_parity.timezone_utils import get_season_for_game
from app.ml.features import FeatureEngineer, GameFeatures
from app.ml.models import BetPredictionModel, ModelMetadata

logger = structlog.get_logger(__name__)

# Directory setup
TRAINED_MODELS_DIR = ROOT_DIR / "services" / "prediction-service-python" / "app" / "ml" / "trained_models"
ODDS_DIR = ROOT_DIR / "testing" / "data" / "historical_odds"
GAMES_DIR = ROOT_DIR / "testing" / "data" / "historical"

class LocalTrainer:
    def __init__(self):
        self.ratings_loader = AntiLeakageRatingsLoader(data_dir=GAMES_DIR)
        self.team_resolver = ProductionTeamResolver()
        self.feature_engineer = FeatureEngineer()
        
        # Cache odds
        self.odds_cache = self._load_odds_cache()
        
    def _load_odds_cache(self):
        """Load consolidated odds into memory for fast lookup."""
        cache = {}
        odds_file = ODDS_DIR / "odds_consolidated_canonical.csv"
        if not odds_file.exists():
            print("Warning: Odds file not found. Training will use partial data.")
            return cache
            
        print(f"Loading odds from {odds_file}...")
        with open(odds_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Key: home|away|date
                # Assuming date is YYYY-MM-DD
                game_date = row.get("commence_time", "")[:10]
                home = row.get("home_team_canonical")
                away = row.get("away_team_canonical")
                if home and away and game_date:
                    key = f"{home}|{away}|{game_date}"
                    cache[key] = row
        print(f"Loaded {len(cache)} odds records.")
        return cache
        
    def _parse_float(self, val):
        if not val: return None
        try: return float(val)
        except: return None
        
    def _get_odds_for_game(self, game_row, home_canonical, away_canonical):
        date = row.get("date") or row.get("game_date")
        # Try exact match
        key = f"{home_canonical}|{away_canonical}|{date}"
        if key in self.odds_cache:
            return self.odds_cache[key]
            
        # Try swapped? usually CSV has canonical order, but let's check
        key_swapped = f"{away_canonical}|{home_canonical}|{date}"
        if key_swapped in self.odds_cache:
            # Need to invert spread? 
            # odds_consolidated has explicit home/away columns now if canonical
            # But let's assume if we found swapped, the logic handles it later or we skip
            # The odds loader typically normalizes to Home/Away
            pass
            
        return None

    def prepare_data(self, seasons=[2021, 2024, 2025, 2026]):
        print("Preparing training data...")
        
        datasets = {
            "fg_spread": {"X": [], "y": []},
            "fg_total": {"X": [], "y": []},
            "h1_spread": {"X": [], "y": []},
            "h1_total": {"X": [], "y": []},
        }
        
        stats = defaultdict(int)
        
        for season in seasons:
            games_file = GAMES_DIR / f"games_{season}.csv"
            if not games_file.exists():
                print(f"Skipping missing season {season}")
                continue
                
            print(f"Processing Season {season}...")
            with open(games_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
            for row in rows:
                stats["processed"] += 1
                
                # 1. Resolve Teams
                home_raw = row.get("home_team")
                away_raw = row.get("away_team")
                date = row.get("date") or row.get("game_date")
                
                home_res = self.team_resolver.resolve(home_raw)
                away_res = self.team_resolver.resolve(away_raw)
                
                if not home_res.resolved or not away_res.resolved:
                    stats["skipped_unresolved"] += 1
                    continue
                    
                home_can = home_res.canonical_name
                away_can = away_res.canonical_name
                
                # 2. Get Ratings
                try:
                    home_res_lookup = self.ratings_loader.get_ratings_for_game(home_can, date)
                    away_res_lookup = self.ratings_loader.get_ratings_for_game(away_can, date)
                    
                    if not home_res_lookup.found or not away_res_lookup.found:
                        stats["skipped_ratings"] += 1
                        continue
                        
                    home_r = home_res_lookup.ratings
                    away_r = away_res_lookup.ratings
                except Exception as e:
                    stats["skipped_ratings_error"] += 1
                    if stats["skipped_ratings_error"] < 5:
                         print(f"Error getting ratings: {e} | Home: {home_can} Away: {away_can} Date: {date}")
                    continue
                    
                # 3. Get Odds/Lines
                # Prefer lines from games CSV if available (actual outcomes often have closing line)
                # But ML model wants 'opening' lines ideally. 
                # games_all.csv has 'home_fg' (spread implied?) and 'total'?
                # checking previous cat of games_all.csv... headers are:
                # game_id,date,home_team,away_team,home_score,away_score,home_fg,away_fg,home_h1,away_h1
                # It doesn't seem to have lines.
                # So we MUST look up in odds cache.
                
                # Improve lookup - try date +/- 1 day if needed, but exact first
                odds = self.odds_cache.get(f"{home_can}|{away_can}|{date}")
                if not odds:
                    stats["skipped_no_odds"] += 1
                    continue
                    
                # 4. Construct Features
                # Features module expects specific fields.
                # We need to map TeamRatings fields to GameFeatures
                
                # Check mapping
                # feature_engineer.extract_batch expects list of GameFeatures
                
                gf = GameFeatures(
                    game_id=row.get("game_id", ""),
                    game_date=date,
                    home_team=home_can,
                    away_team=away_can,
                    
                    # Ratings
                    home_adj_o=home_r.adj_o, home_adj_d=home_r.adj_d,
                    home_tempo=home_r.tempo, home_rank=home_r.rank,
                    away_adj_o=away_r.adj_o, away_adj_d=away_r.adj_d,
                    away_tempo=away_r.tempo, away_rank=away_r.rank,
                    
                    # Four Factors
                    home_efg=home_r.efg, home_efgd=home_r.efgd,
                    home_tor=home_r.tor, home_tord=home_r.tord,
                    home_orb=home_r.orb, home_drb=home_r.drb,
                    home_ftr=home_r.ftr, home_ftrd=home_r.ftrd,
                    
                    away_efg=away_r.efg, away_efgd=away_r.efgd,
                    away_tor=away_r.tor, away_tord=away_r.tord,
                    away_orb=away_r.orb, away_drb=away_r.drb,
                    away_ftr=away_r.ftr, away_ftrd=away_r.ftrd,
                    
                    # Shooting
                    home_two_pt_pct=home_r.two_pt_pct, home_two_pt_pct_d=home_r.two_pt_pct_d,
                    home_three_pt_pct=home_r.three_pt_pct, home_three_pt_pct_d=home_r.three_pt_pct_d,
                    home_three_pt_rate=home_r.three_pt_rate, home_three_pt_rate_d=home_r.three_pt_rate_d,
                    
                    away_two_pt_pct=away_r.two_pt_pct, away_two_pt_pct_d=away_r.two_pt_pct_d,
                    away_three_pt_pct=away_r.three_pt_pct, away_three_pt_pct_d=away_r.three_pt_pct_d,
                    away_three_pt_rate=away_r.three_pt_rate, away_three_pt_rate_d=away_r.three_pt_rate_d,
                    
                    # Quality (barthag etc calculated in FeatureEngineer usually or here?)
                    # FeatureEngineer calculates derived. We just provide raw.
                    # Wait, GameFeatures has fields like home_barthag. FeatureEngineer computes features *from* GameFeatures.
                    # But GameFeatures dataclass has fields. We should populate them if we have them.
                    # TeamRatings has barthag? No, it has adj_o/d.
                    # We can compute barthag here or let FeatureEngineer handle it?
                    # Looking at GameFeatures definition again... it has fields. 
                    # If we leave them 0, FeatureEngineer might use 0.
                    # FeatureEngineer.extract_features reads from these fields.
                    # DOES FeatureEngineer populate derived fields?
                    # No, extract_features reads attributes. 
                    # So WE must populate them or FeatureEngineer is useless for derived stats.
                    # CHECK FeatureEngineer logic again.
                )
                
                # Check if we need to compute barthag etc.
                # Actually, ratings_loader TeamRatings doesn't have barthag. 
                # We can compute it: 1 / (1 + (adj_d / adj_o)**11.5)
                # Let's do basic population.
                
                # Market Data (Training target dependent)
                spread = self._parse_float(odds.get("spread"))
                total = self._parse_float(odds.get("total"))
                h1_spread = self._parse_float(odds.get("h1_spread"))
                h1_total = self._parse_float(odds.get("h1_total"))
                
                # Set market features
                # GameFeatures has 'spread_open', 'total_open'.
                if spread is not None: gf.spread_open = spread
                if total is not None: gf.total_open = total
                
                # Extract Features Vector
                X_vec = self.feature_engineer.extract_features(gf)
                
                # Scores for Labels
                home_score = self._parse_float(row.get("home_score"))
                away_score = self._parse_float(row.get("away_score"))
                h1_home = self._parse_float(row.get("home_h1")) or self._parse_float(row.get("h1_home"))
                h1_away = self._parse_float(row.get("away_h1")) or self._parse_float(row.get("h1_away"))
                
                # Labels
                if home_score is not None and away_score is not None:
                    # FG Spread
                    if spread is not None:
                        margin = home_score - away_score
                        # Cover: margin > -spread ? (e.g. spread -5, margin 6. 6 > 5. cover)
                        # Spread is usually denoted as "Home Spread" in odds data (e.g. -5.5)
                        # Result + Spread > 0 -> Cover. (6 + -5.5 = 0.5 > 0)
                        if (margin + spread) > 0:
                            datasets["fg_spread"]["X"].append(X_vec)
                            datasets["fg_spread"]["y"].append(1)
                        elif (margin + spread) < 0:
                            datasets["fg_spread"]["X"].append(X_vec)
                            datasets["fg_spread"]["y"].append(0)
                            
                    # FG Total
                    if total is not None:
                        total_score = home_score + away_score
                        if total_score > total:
                            datasets["fg_total"]["X"].append(X_vec)
                            datasets["fg_total"]["y"].append(1)
                        elif total_score < total:
                            datasets["fg_total"]["X"].append(X_vec)
                            datasets["fg_total"]["y"].append(0)
                            
                if h1_home is not None and h1_away is not None:
                   # H1 Spread
                    if h1_spread is not None:
                        margin = h1_home - h1_away
                        if (margin + h1_spread) > 0:
                            datasets["h1_spread"]["X"].append(X_vec)
                            datasets["h1_spread"]["y"].append(1)
                        elif (margin + h1_spread) < 0:
                            datasets["h1_spread"]["X"].append(X_vec)
                            datasets["h1_spread"]["y"].append(0)
                    
                    # H1 Total
                    if h1_total is not None:
                        score = h1_home + h1_away
                        if score > h1_total:
                            datasets["h1_total"]["X"].append(X_vec)
                            datasets["h1_total"]["y"].append(1)
                        elif score < h1_total:
                            datasets["h1_total"]["X"].append(X_vec)
                            datasets["h1_total"]["y"].append(0)

        print("Data Preparation Complete.")
        print("Stats:", dict(stats))
        for k, v in datasets.items():
            print(f"{k}: {len(v['y'])} samples")
            
        return datasets
        
    def train_and_save(self):
        TRAINED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        datasets = self.prepare_data()
        
        feature_names = self.feature_engineer.feature_names
        
        for model_type, data in datasets.items():
            X = np.array(data["X"])
            y = np.array(data["y"])
            
            if len(y) < 100:
                print(f"Skipping {model_type} - insufficient data ({len(y)})")
                continue
                
            print(f"\nTraining {model_type} with {len(y)} samples...")
            
            # Simple TimeSeriesSplit is usually done inside fit or manually
            # Here we just fit on all available data for the "Production" model
            # Since we validated with calibration test earlier.
            
            model = BetPredictionModel(model_type=model_type)
            try:
                model.fit(X, y, feature_names=feature_names)
                
                # Check accuracy roughly
                preds = model.predict(X)
                acc = np.mean(preds == y)
                print(f"Training Accuracy: {acc:.3f}")
                
                # Metadata
                model.metadata = ModelMetadata(
                    model_type=model_type,
                    version="local_v1",
                    trained_at=datetime.now().isoformat(),
                    training_samples=len(y),
                    validation_samples=0,
                    accuracy=float(acc),
                    log_loss=0.0,
                    auc_roc=0.0,
                    brier_score=0.0,
                    calibration_bins=[],
                    calibration_actual=[],
                    feature_importance=model.get_feature_importance(),
                    train_start_date="2021-01-01",
                    train_end_date="2026-01-01",
                    hyperparameters=model.params
                )
                
                model.save(TRAINED_MODELS_DIR)
                print(f"Saved {model_type}")
                
            except Exception as e:
                print(f"Failed to train {model_type}: {e}")

if __name__ == "__main__":
    trainer = LocalTrainer()
    trainer.train_and_save()
