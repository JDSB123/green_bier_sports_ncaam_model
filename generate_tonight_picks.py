#!/usr/bin/env python3
"""
Generate Tonight's Picks - Paper Mode Only

Generates predictions for tonight's NCAAM slate using profitable models:
- FG Spread (+3.82% ROI historically)
- H1 Spread (+1.54% ROI historically)

Paper mode: No real money. Outputs predictions to CSV for review.

Usage:
    python generate_tonight_picks.py
    python generate_tonight_picks.py --market fg_spread
    python generate_tonight_picks.py --live  # To pull real games from Odds API
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict

import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from testing.azure_data_reader import get_azure_reader
from testing.scripts.run_historical_backtest import (
    NCAAMPredictor, BacktestConfig, MarketType, _add_derived_features
)

RESULTS_DIR = ROOT_DIR / "testing" / "results" / "predictions"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Markets that are historically profitable
PROFITABLE_MARKETS = [MarketType.FG_SPREAD, MarketType.H1_SPREAD]

@dataclass
class TonightPick:
    """A single pick for tonight."""
    game_date: str
    game_time: str
    home_team: str
    away_team: str
    market: str
    predicted_line: float
    market_line: float
    edge: float
    bet_side: str
    edge_pct: float
    confidence: str  # HIGH, MEDIUM, LOW
    paper_mode: bool = True


def load_games_for_tonight(live: bool = False) -> pd.DataFrame:
    """
    Load games for tonight.
    
    If live=True, fetch from Odds API (requires API key).
    If live=False, use tomorrow's date from canonical master as a simulation.
    """
    reader = get_azure_reader()
    
    if live:
        try:
            # Load Odds API to get tonight's games
            import requests
            
            api_key = os.environ.get("ODDS_API_KEY")
            if not api_key:
                print("[WARN] ODDS_API_KEY not in environment; can't fetch live games")
                return pd.DataFrame()
            
            # Fetch upcoming games for NCAAM
            url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/events"
            params = {
                "apiKey": api_key,
            }
            
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            
            events = resp.json()
            if not events:
                print("[INFO] No upcoming games found from Odds API")
                return pd.DataFrame()
            
            # Parse events into DataFrame
            games = []
            for event in events:
                games.append({
                    "game_id": event["id"],
                    "commence_time": event["commence_time"],
                    "home_team": event["home_team"],
                    "away_team": event["away_team"],
                    "home_score": None,
                    "away_score": None,
                    "home_h1": None,
                    "away_h1": None,
                })
            
            return pd.DataFrame(games)
        
        except Exception as e:
            print(f"[ERROR] Failed to fetch live games: {e}")
            return pd.DataFrame()
    
    else:
        # For demo: use tomorrow's date
        print("[INFO] Live mode off; using canonical master for demo purposes")
        local_master = ROOT_DIR / "manifests" / "canonical_training_data_master.csv"
        df = pd.read_csv(local_master)
        
        # Get tomorrow's date
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
        
        # Filter for near-future games (within next 7 days) for demo
        future_games = df[df["game_date"] >= pd.Timestamp(tomorrow)]
        
        if future_games.empty:
            print("[INFO] No games in the near future; using most recent games for demo")
            # Use most recent games instead
            future_games = df.nlargest(10, "game_date")
        
        return future_games.head(5).copy()


def add_ratings_to_games(df: pd.DataFrame) -> pd.DataFrame:
    """Join ratings to tonight's games from canonical master."""
    reader = get_azure_reader()
    
    local_master = ROOT_DIR / "manifests" / "canonical_training_data_master.csv"
    if local_master.exists():
        master = pd.read_csv(local_master)
    else:
        master = reader.read_csv("manifests/canonical_training_data_master.csv")
    
    # Normalize team names
    if "home_canonical" in master.columns:
        master["home_team"] = master["home_canonical"].str.strip()
        master["away_team"] = master["away_canonical"].str.strip()
    elif "home_team" in master.columns:
        master["home_team"] = master["home_team"].str.strip()
        master["away_team"] = master["away_team"].str.strip()
    
    # Handle input dataframe columns
    if "home_team" in df.columns:
        df["home_team"] = df["home_team"].str.strip()
        df["away_team"] = df["away_team"].str.strip()
    elif "home_abbr" in df.columns:
        df["home_team"] = df["home_abbr"]
        df["away_team"] = df["away_abbr"]
    else:
        print("[WARN] No home/away team columns found")
        return df
    
    # Keep most recent rating columns
    rating_cols = [
        "home_adj_o", "home_adj_d", "home_barthag", "home_efg", "home_efgd",
        "home_tor", "home_orb", "home_drb", "home_ftr", "home_tempo",
        "home_three_pt_rate", "home_wab",
        "away_adj_o", "away_adj_d", "away_barthag", "away_efg", "away_efgd",
        "away_tor", "away_orb", "away_drb", "away_ftr", "away_tempo",
        "away_three_pt_rate", "away_wab",
        "fg_spread", "fg_total", "h1_spread", "h1_total",
        "fg_spread_home_price", "fg_spread_away_price",
        "h1_spread_home_price", "h1_spread_away_price"
    ]
    
    # Merge on team names
    result = df.copy()
    
    for _, row in df.iterrows():
        home_name = row["home_team"]
        away_name = row["away_team"]
        
        matching = master[
            (master["home_team"] == home_name) & (master["away_team"] == away_name)
        ]
        
        if not matching.empty:
            latest = matching.iloc[-1]
            for col in rating_cols:
                if col in latest:
                    result.loc[result.index == row.name, col] = latest[col]
    
    return result


def generate_picks(df: pd.DataFrame, markets: List[MarketType]) -> List[TonightPick]:
    """Generate predictions for tonight's games."""
    picks = []
    
    # Create predictor
    config = BacktestConfig(
        market=MarketType.FG_SPREAD,
        seasons=[2025],
        use_trained_models=True,
        min_edge=1.5
    )
    predictor = NCAAMPredictor(config)
    
    # Add derived features
    df = _add_derived_features(df)
    
    for market in markets:
        config.market = market
        
        for _, game in df.iterrows():
            # Extract required fields
            try:
                home_team = game.get("home_team", "UNKNOWN")
                away_team = game.get("away_team", "UNKNOWN")
                game_date = game.get("game_date", datetime.now().date())
                game_time = game.get("commence_time", "TBD")
                
                # Ratings
                home_adj_o = game.get("home_adj_o")
                home_adj_d = game.get("home_adj_d")
                away_adj_o = game.get("away_adj_o")
                away_adj_d = game.get("away_adj_d")
                
                if any(pd.isna(x) for x in [home_adj_o, home_adj_d, away_adj_o, away_adj_d]):
                    continue  # Skip if missing ratings
                
                # Make prediction
                if market == MarketType.FG_SPREAD:
                    predicted = predictor.predict_spread(
                        home_adj_o, home_adj_d, away_adj_o, away_adj_d,
                        is_neutral=game.get("neutral", False),
                        home_efg=game.get("home_efg"),
                        away_efg=game.get("away_efg"),
                    )
                    market_line = game.get("fg_spread")
                    price_home = game.get("fg_spread_home_price")
                    price_away = game.get("fg_spread_away_price")
                
                elif market == MarketType.H1_SPREAD:
                    predicted = predictor.predict_h1_spread(
                        home_adj_o, home_adj_d, away_adj_o, away_adj_d,
                        is_neutral=game.get("neutral", False),
                        home_efg=game.get("home_efg"),
                        away_efg=game.get("away_efg"),
                    )
                    market_line = game.get("h1_spread")
                    price_home = game.get("h1_spread_home_price")
                    price_away = game.get("h1_spread_away_price")
                
                elif market == MarketType.FG_TOTAL:
                    predicted = predictor.predict_total(
                        home_adj_o, home_adj_d, game.get("home_tempo", 67),
                        away_adj_o, away_adj_d, game.get("away_tempo", 67),
                        is_neutral=game.get("neutral", False),
                    )
                    market_line = game.get("fg_total")
                    price_home = game.get("fg_total_over_price")
                    price_away = game.get("fg_total_under_price")
                
                elif market == MarketType.H1_TOTAL:
                    predicted = predictor.predict_h1_total(
                        home_adj_o, home_adj_d, game.get("home_tempo", 67),
                        away_adj_o, away_adj_d, game.get("away_tempo", 67),
                        is_neutral=game.get("neutral", False),
                    )
                    market_line = game.get("h1_total")
                    price_home = game.get("h1_total_over_price")
                    price_away = game.get("h1_total_under_price")
                
                else:
                    continue
                
                # Check if we have market line
                if pd.isna(market_line):
                    continue
                
                # Calculate edge
                if "spread" in market.value:
                    edge_points = abs(predicted - market_line)
                    edge_pct = (edge_points / 11.0) * 100  # Assume 11 point std dev for spreads
                else:
                    edge_points = abs(predicted - market_line)
                    edge_pct = (edge_points / 8.0) * 100  # Assume 8 point std dev for totals
                
                # Only pick if edge > 1.5%
                if edge_pct < 1.5:
                    continue
                
                # Determine bet side
                if "spread" in market.value:
                    bet_side = "home" if predicted < market_line else "away"
                else:
                    bet_side = "over" if predicted > market_line else "under"
                
                # Confidence based on edge
                if edge_pct >= 10:
                    confidence = "HIGH"
                elif edge_pct >= 5:
                    confidence = "MEDIUM"
                else:
                    confidence = "LOW"
                
                pick = TonightPick(
                    game_date=str(game_date),
                    game_time=str(game_time),
                    home_team=home_team,
                    away_team=away_team,
                    market=market.value,
                    predicted_line=round(predicted, 1),
                    market_line=round(market_line, 1),
                    edge=round(edge_points, 1),
                    bet_side=bet_side,
                    edge_pct=round(edge_pct, 2),
                    confidence=confidence,
                    paper_mode=True,
                )
                picks.append(pick)
            
            except Exception as e:
                print(f"[WARN] Error processing {home_team} vs {away_team}: {e}")
                continue
    
    return picks


def main():
    parser = argparse.ArgumentParser(
        description="Generate tonight's picks using profitable models (paper mode)"
    )
    parser.add_argument(
        "--market",
        choices=["fg_spread", "h1_spread", "fg_total", "h1_total"],
        default=None,
        help="Specific market to generate picks for (default: all profitable)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fetch real games from Odds API (requires ODDS_API_KEY environment variable)"
    )
    
    args = parser.parse_args()
    
    # Select markets
    if args.market:
        markets = [MarketType(args.market)]
    else:
        markets = PROFITABLE_MARKETS
    
    print("\n" + "="*70)
    print("TONIGHT'S PICKS - PAPER MODE")
    print("="*70)
    print(f"Markets: {[m.value for m in markets]}")
    print(f"Live Mode: {args.live}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    # Load games
    print("[INFO] Loading games for tonight...")
    games_df = load_games_for_tonight(live=args.live)
    
    if games_df.empty:
        print("[WARN] No games found; cannot generate picks")
        return
    
    print(f"[OK] Loaded {len(games_df)} games")
    
    # Add ratings
    print("[INFO] Adding team ratings...")
    games_df = add_ratings_to_games(games_df)
    
    # Generate picks
    print("[INFO] Generating predictions...")
    picks = generate_picks(games_df, markets)
    
    if not picks:
        print("[WARN] No picks generated (all edges below 1.5%)")
        return
    
    # Output results
    print(f"\n[OK] Generated {len(picks)} picks:\n")
    
    picks_df = pd.DataFrame([
        {
            "Date": p.game_date,
            "Time": p.game_time,
            "Matchup": f"{p.away_team} @ {p.home_team}",
            "Market": p.market,
            "Predicted": p.predicted_line,
            "Market Line": p.market_line,
            "Edge (pts)": p.edge,
            "Bet": p.bet_side,
            "Edge %": f"{p.edge_pct}%",
            "Confidence": p.confidence,
        }
        for p in picks
    ])
    
    print(picks_df.to_string(index=False))
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RESULTS_DIR / f"tonight_picks_{timestamp}.csv"
    picks_df.to_csv(output_file, index=False)
    
    # Save JSON for integration with betting systems
    json_file = RESULTS_DIR / f"tonight_picks_{timestamp}.json"
    picks_json = [
        {
            "game_date": p.game_date,
            "game_time": p.game_time,
            "home_team": p.home_team,
            "away_team": p.away_team,
            "market": p.market,
            "predicted_line": p.predicted_line,
            "market_line": p.market_line,
            "edge_points": p.edge,
            "edge_pct": p.edge_pct,
            "bet_side": p.bet_side,
            "confidence": p.confidence,
            "paper_mode": p.paper_mode,
        }
        for p in picks
    ]
    with open(json_file, "w") as f:
        json.dump(picks_json, f, indent=2)
    
    print(f"\n[OK] Saved picks to {output_file}")
    print(f"[OK] Saved JSON to {json_file}")
    print("\n⚠️  PAPER MODE ONLY - No real money at stake")
    print("Review picks before any real action\n")


if __name__ == "__main__":
    import os
    main()
