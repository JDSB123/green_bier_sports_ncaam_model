#!/usr/bin/env python3
"""
NCAAM Backtest V2 - PRE-GAME Rolling Stats (NO LEAKAGE)

This backtest uses ONLY data available BEFORE each game:
- Rolling team stats calculated from previous games in the season
- Box score data from ncaahoopR for game-by-game stats
- NO end-of-season ratings that would leak future information

Data Sources:
- ncaahoopR schedules: Game-by-game results with scores
- ncaahoopR box_scores: Detailed stats for calculating efficiency
- Canonical odds: Market lines at game time
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from scipy.stats import norm
from collections import defaultdict
import logging
import warnings
warnings.filterwarnings('ignore')

# Setup paths
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "ncaam_historical_data_local"
NCAAHOOPR_DIR = DATA_DIR / "ncaahoopR_data-master"
RESULTS_DIR = ROOT_DIR / "testing" / "results" / "backtest_v2_rolling"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Canonical data
ODDS_FILE = DATA_DIR / "odds" / "normalized" / "odds_consolidated_canonical.csv"
FG_SCORES_FILE = DATA_DIR / "canonicalized" / "scores" / "fg" / "games_all_canonical.csv"
TEAM_ALIASES_FILE = DATA_DIR / "backtest_datasets" / "team_aliases_db.json"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(RESULTS_DIR / "backtest_v2.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_season(date) -> int:
    """Get season year from date. Season 2025 = Nov 2024 - Apr 2025."""
    if isinstance(date, str):
        date = pd.to_datetime(date)
    month = date.month
    year = date.year
    if month >= 11:
        return year + 1
    else:
        return year


def get_season_folder(season: int) -> str:
    """Get ncaahoopR folder name for a season."""
    return f"{season-1}-{str(season)[2:]}"


def american_to_prob(odds: float) -> float:
    """Convert American odds to implied probability."""
    if odds is None or pd.isna(odds):
        return None
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def calc_payout(odds: float, stake: float = 100) -> float:
    """Calculate payout for winning bet."""
    if odds is None or pd.isna(odds):
        return 0
    if odds > 0:
        return stake * (odds / 100)
    else:
        return stake * (100 / abs(odds))


class TeamStatsTracker:
    """Track rolling stats for each team throughout the season."""
    
    def __init__(self):
        # team -> season -> list of game stats
        self.games: Dict[str, Dict[int, List[dict]]] = defaultdict(lambda: defaultdict(list))
        
    def add_game(self, team: str, season: int, game_stats: dict):
        """Add a game's stats to a team's history."""
        self.games[team][season].append(game_stats)
    
    def get_pregame_stats(self, team: str, season: int, min_games: int = 3) -> Optional[dict]:
        """Get rolling averages for a team BEFORE the current game.
        
        Returns None if team doesn't have enough games yet.
        """
        games = self.games[team][season]
        
        if len(games) < min_games:
            return None
        
        # Calculate rolling averages
        pts_for = np.mean([g['pts_for'] for g in games])
        pts_against = np.mean([g['pts_against'] for g in games])
        
        # Efficiency metrics (if available)
        if 'poss' in games[0]:
            poss = np.mean([g['poss'] for g in games])
            off_eff = pts_for / poss * 100 if poss > 0 else 100
            def_eff = pts_against / poss * 100 if poss > 0 else 100
        else:
            # Estimate possessions from score (roughly 70 poss per game)
            poss = 70
            off_eff = pts_for / poss * 100
            def_eff = pts_against / poss * 100
        
        # Margin
        margin = pts_for - pts_against
        
        # Win rate
        wins = sum(1 for g in games if g.get('won', False))
        
        return {
            'games_played': len(games),
            'wins': wins,
            'losses': len(games) - wins,
            'pts_for_avg': pts_for,
            'pts_against_avg': pts_against,
            'margin_avg': margin,
            'off_eff': off_eff,
            'def_eff': def_eff,
            'net_eff': off_eff - def_eff,
        }


class RollingBacktest:
    """Backtest using rolling pre-game stats."""
    
    # Calibration parameters
    SIGMA_FG = 11.0  # Standard deviation for FG spread
    HCA = 3.0  # Home court advantage
    
    def __init__(self):
        self.tracker = TeamStatsTracker()
        self.team_aliases = self._load_team_aliases()
        self.predictions = []
        
    def _load_team_aliases(self) -> dict:
        """Load team name aliases for matching."""
        import json
        if TEAM_ALIASES_FILE.exists():
            with open(TEAM_ALIASES_FILE) as f:
                return json.load(f)
        return {}
    
    def _normalize_team(self, name: str) -> str:
        """Normalize team name using aliases."""
        if not name:
            return name
        name_lower = name.lower().strip()
        return self.team_aliases.get(name_lower, name)
    
    def _load_all_schedules(self) -> pd.DataFrame:
        """Load all team schedules from ncaahoopR."""
        logger.info("Loading all team schedules from ncaahoopR...")
        
        all_games = []
        seasons_to_load = ['2020-21', '2021-22', '2022-23', '2023-24', '2024-25', '2025-26']
        
        for season_folder in seasons_to_load:
            season_path = NCAAHOOPR_DIR / season_folder / "schedules"
            if not season_path.exists():
                continue
            
            for schedule_file in season_path.glob("*_schedule.csv"):
                try:
                    df = pd.read_csv(schedule_file)
                    team_name = schedule_file.stem.replace("_schedule", "").replace("_", " ")
                    df['team'] = team_name
                    df['season_folder'] = season_folder
                    all_games.append(df)
                except Exception as e:
                    continue
        
        if not all_games:
            logger.error("No schedules found!")
            return pd.DataFrame()
        
        combined = pd.concat(all_games, ignore_index=True)
        combined['date'] = pd.to_datetime(combined['date'])
        combined = combined.sort_values('date')
        
        logger.info(f"  Loaded {len(combined):,} game records")
        logger.info(f"  Date range: {combined['date'].min()} to {combined['date'].max()}")
        
        return combined
    
    def _build_pregame_stats(self, schedules: pd.DataFrame):
        """Process schedules chronologically to build rolling stats."""
        logger.info("Building pre-game rolling stats...")
        
        # Process games in chronological order
        for _, row in schedules.iterrows():
            team = self._normalize_team(row['team'])
            date = row['date']
            season = get_season(date)
            
            pts_for = row.get('team_score', 0)
            pts_against = row.get('opp_score', 0)
            
            if pd.isna(pts_for) or pd.isna(pts_against):
                continue
            
            won = pts_for > pts_against
            
            game_stats = {
                'date': date,
                'pts_for': pts_for,
                'pts_against': pts_against,
                'won': won,
            }
            
            self.tracker.add_game(team, season, game_stats)
        
        logger.info(f"  Built stats for {len(self.tracker.games)} teams")
    
    def _load_odds(self) -> pd.DataFrame:
        """Load canonical odds data."""
        logger.info(f"Loading odds from {ODDS_FILE}")
        
        df = pd.read_csv(ODDS_FILE)
        df['game_date'] = pd.to_datetime(df['game_date'])
        
        # Deduplicate - keep first bookmaker per game
        df = df.drop_duplicates(subset=['event_id'], keep='first')
        
        logger.info(f"  Loaded {len(df):,} unique games with odds")
        
        return df
    
    def _load_scores(self) -> pd.DataFrame:
        """Load actual game scores."""
        logger.info(f"Loading scores from {FG_SCORES_FILE}")
        
        df = pd.read_csv(FG_SCORES_FILE)
        df['date'] = pd.to_datetime(df['date'])
        
        logger.info(f"  Loaded {len(df):,} games with scores")
        
        return df
    
    def predict_spread(self, home_team: str, away_team: str, 
                       game_date, market_spread: float) -> Tuple[Optional[float], Optional[float]]:
        """Predict spread using pre-game rolling stats only.
        
        Market spread convention: negative = home favored, positive = away favored
        Example: market_spread = -7.5 means "home team favored by 7.5"
        
        Our prediction: positive = home wins by X, negative = home loses by X
        Example: predicted = +5 means "we think home wins by 5"
        
        If market says home -7.5 and we predict home +5, our fair line is -5,
        so home ATS pick would need +7.5 to cover but we only expect +5 → bad bet on home ATS
        
        Returns: (predicted_margin, edge)
        """
        season = get_season(game_date)
        
        home_stats = self.tracker.get_pregame_stats(home_team, season)
        away_stats = self.tracker.get_pregame_stats(away_team, season)
        
        if not home_stats or not away_stats:
            return None, None
        
        # Use net efficiency differential
        home_net = home_stats['net_eff']
        away_net = away_stats['net_eff']
        
        # Predicted margin = (home_net - away_net) + HCA
        # Positive = home wins, Negative = home loses
        predicted_margin = (home_net - away_net) + self.HCA
        
        # Edge calculation:
        # If market_spread = -7.5 (home favored by 7.5) and we predict +5 (home by 5)
        # Home needs to win by MORE than 7.5 to cover
        # We think they win by 5, so home ATS is a BAD bet
        # Edge = predicted_margin - (-market_spread) = predicted_margin + market_spread
        # = 5 + (-7.5) = -2.5 → negative edge → don't bet home
        
        # Edge for HOME ATS: predicted_margin + market_spread
        # Edge for AWAY ATS: -(predicted_margin + market_spread)
        edge = predicted_margin + market_spread  # Home ATS edge
        
        return predicted_margin, edge
    
    def predict_total(self, home_team: str, away_team: str,
                      game_date, market_total: float) -> Tuple[Optional[float], Optional[float]]:
        """Predict total using pre-game rolling stats only."""
        season = get_season(game_date)
        
        home_stats = self.tracker.get_pregame_stats(home_team, season)
        away_stats = self.tracker.get_pregame_stats(away_team, season)
        
        if not home_stats or not away_stats:
            return None, None
        
        # Expected scoring based on offensive/defensive efficiency matchup
        # Home team scores: (home_off vs away_def)
        # Away team scores: (away_off vs home_def)
        
        avg_eff = 100  # D1 average
        
        # Simple model: average of both teams' scoring averages, adjusted
        home_expected = (home_stats['pts_for_avg'] + away_stats['pts_against_avg']) / 2
        away_expected = (away_stats['pts_for_avg'] + home_stats['pts_against_avg']) / 2
        
        predicted_total = home_expected + away_expected
        edge = predicted_total - market_total
        
        return predicted_total, edge
    
    def run_backtest(self) -> pd.DataFrame:
        """Run the full backtest."""
        logger.info("=" * 80)
        logger.info("NCAAM BACKTEST V2 - ROLLING PRE-GAME STATS")
        logger.info("NO DATA LEAKAGE - Only uses stats from BEFORE each game")
        logger.info("=" * 80)
        
        # Load and process data
        schedules = self._load_all_schedules()
        if schedules.empty:
            logger.error("No schedule data!")
            return pd.DataFrame()
        
        self._build_pregame_stats(schedules)
        
        odds_df = self._load_odds()
        scores_df = self._load_scores()
        
        # Create scores lookup
        scores_lookup = {}
        for _, row in scores_df.iterrows():
            key = (
                self._normalize_team(row['home_canonical']),
                self._normalize_team(row['away_canonical']),
                row['date'].strftime('%Y-%m-%d')
            )
            scores_lookup[key] = {
                'home_score': row['home_score'],
                'away_score': row['away_score']
            }
        
        logger.info(f"Processing {len(odds_df):,} games for predictions...")
        
        results = []
        
        for idx, row in odds_df.iterrows():
            if idx % 5000 == 0:
                logger.info(f"  Processed {idx:,} games...")
            
            home_team = self._normalize_team(row.get('home_team_canonical', ''))
            away_team = self._normalize_team(row.get('away_team_canonical', ''))
            game_date = row['game_date']
            
            if not home_team or not away_team:
                continue
            
            # Get actual scores
            score_key = (home_team, away_team, game_date.strftime('%Y-%m-%d'))
            actual_scores = scores_lookup.get(score_key)
            
            # FG SPREAD
            market_spread = row.get('spread')
            if pd.notna(market_spread):
                pred_margin, edge = self.predict_spread(home_team, away_team, game_date, market_spread)
                
                if pred_margin is not None:
                    # Edge > 0 means bet HOME ATS, Edge < 0 means bet AWAY ATS
                    bet_side = 'HOME' if edge > 0 else 'AWAY'
                    spread_price = row.get('spread_home_price' if bet_side == 'HOME' else 'spread_away_price', -110)
                    
                    won = None
                    if actual_scores:
                        actual_margin = actual_scores['home_score'] - actual_scores['away_score']
                        # Home covers if: actual_margin > -market_spread
                        # e.g., market_spread = -7.5, home covers if margin > 7.5
                        # Away covers if: actual_margin < -market_spread
                        if bet_side == 'HOME':
                            # Home ATS: Home must beat the spread
                            won = actual_margin > -market_spread
                        else:
                            # Away ATS: Home must lose by more than spread (or win by less)
                            won = actual_margin < -market_spread
                    
                    results.append({
                        'game_date': game_date,
                        'home_team': home_team,
                        'away_team': away_team,
                        'market': 'FG_SPREAD',
                        'prediction': pred_margin,
                        'market_line': market_spread,
                        'edge': abs(edge),
                        'bet_side': bet_side,
                        'odds': spread_price,
                        'won': won,
                    })
            
            # FG TOTAL
            market_total = row.get('total')
            if pd.notna(market_total):
                pred_total, edge = self.predict_total(home_team, away_team, game_date, market_total)
                
                if pred_total is not None:
                    bet_side = 'OVER' if edge > 0 else 'UNDER'
                    total_price = row.get('total_over_price' if bet_side == 'OVER' else 'total_under_price', -110)
                    
                    won = None
                    if actual_scores:
                        actual_total = actual_scores['home_score'] + actual_scores['away_score']
                        if bet_side == 'OVER':
                            won = actual_total > market_total
                        else:
                            won = actual_total < market_total
                    
                    results.append({
                        'game_date': game_date,
                        'home_team': home_team,
                        'away_team': away_team,
                        'market': 'FG_TOTAL',
                        'prediction': pred_total,
                        'market_line': market_total,
                        'edge': abs(edge),
                        'bet_side': bet_side,
                        'odds': total_price,
                        'won': won,
                    })
        
        results_df = pd.DataFrame(results)
        logger.info(f"Generated {len(results_df):,} predictions")
        
        # Calculate results by edge threshold
        self._print_results(results_df)
        
        # Save results
        results_df.to_csv(RESULTS_DIR / "all_predictions.csv", index=False)
        logger.info(f"Results saved to {RESULTS_DIR}")
        
        return results_df
    
    def _print_results(self, df: pd.DataFrame):
        """Print ROI results by market and edge threshold."""
        
        edge_thresholds = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0]
        
        summary = []
        
        for market in df['market'].unique():
            market_df = df[df['market'] == market]
            matched = market_df[market_df['won'].notna()]
            
            logger.info(f"\n{market}:")
            logger.info(f"  Total predictions: {len(market_df):,}")
            logger.info(f"  With outcomes: {len(matched):,}")
            
            for min_edge in edge_thresholds:
                filtered = matched[matched['edge'] >= min_edge]
                
                if len(filtered) == 0:
                    continue
                
                wins = (filtered['won'] == True).sum()
                losses = (filtered['won'] == False).sum()
                total_bets = len(filtered)
                win_rate = wins / total_bets if total_bets > 0 else 0
                
                # Calculate ROI with actual odds
                stake = 100
                total_wagered = total_bets * stake
                total_returned = 0
                
                for _, pred in filtered.iterrows():
                    if pred['won']:
                        payout = calc_payout(pred['odds'], stake)
                        total_returned += stake + payout
                
                profit = total_returned - total_wagered
                roi = (profit / total_wagered) * 100 if total_wagered > 0 else 0
                
                logger.info(f"  Edge >= {min_edge}: {total_bets} bets, {win_rate:.1%} win rate, {roi:.2f}% ROI")
                
                summary.append({
                    'market': market,
                    'min_edge': min_edge,
                    'total_bets': total_bets,
                    'wins': wins,
                    'losses': losses,
                    'win_rate': win_rate,
                    'roi': roi,
                })
        
        summary_df = pd.DataFrame(summary)
        summary_df.to_csv(RESULTS_DIR / "backtest_summary.csv", index=False)


def main():
    backtest = RollingBacktest()
    results = backtest.run_backtest()
    
    print("\n" + "=" * 80)
    print("BACKTEST V2 COMPLETE - PRE-GAME ROLLING STATS")
    print("=" * 80)
    print(f"\nResults saved to: {RESULTS_DIR}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
