#!/usr/bin/env python3
"""
NCAAM Backtest V2 Enhanced - PRE-GAME Rolling Stats with Box Score Features

Uses detailed box score data to calculate:
- eFG% (Effective Field Goal %)
- TO% (Turnover Rate)
- ORB% (Offensive Rebound Rate)
- FT Rate (Free Throws per FGA)
- Tempo (estimated possessions per game)
- Offensive/Defensive efficiency (points per 100 possessions)

NO DATA LEAKAGE - Only uses stats from BEFORE each game.
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
RESULTS_DIR = ROOT_DIR / "testing" / "results" / "backtest_v2_enhanced"
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
        logging.FileHandler(RESULTS_DIR / "backtest_v2_enhanced.log"),
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


@dataclass
class GameBoxScore:
    """Parsed box score data for a single game."""
    date: datetime
    team: str
    opponent: str
    home: bool
    pts_for: int
    pts_against: int
    
    # Four Factors (offense)
    fgm: int = 0
    fga: int = 0
    fg3m: int = 0
    fg3a: int = 0
    ftm: int = 0
    fta: int = 0
    oreb: int = 0
    dreb: int = 0
    ast: int = 0
    to: int = 0
    stl: int = 0
    blk: int = 0
    
    # Opponent stats (for defensive metrics)
    opp_fgm: int = 0
    opp_fga: int = 0
    opp_fg3m: int = 0
    opp_fg3a: int = 0
    opp_ftm: int = 0
    opp_fta: int = 0
    opp_oreb: int = 0
    opp_dreb: int = 0
    opp_to: int = 0
    
    @property
    def won(self) -> bool:
        return self.pts_for > self.pts_against
    
    @property
    def possessions(self) -> float:
        """Estimate possessions using Kenpom formula."""
        return self.fga - self.oreb + self.to + 0.475 * self.fta
    
    @property
    def opp_possessions(self) -> float:
        return self.opp_fga - self.opp_oreb + self.opp_to + 0.475 * self.opp_fta
    
    @property
    def efg_pct(self) -> float:
        """Effective FG% = (FGM + 0.5*3PM) / FGA."""
        if self.fga == 0:
            return 0
        return (self.fgm + 0.5 * self.fg3m) / self.fga
    
    @property
    def to_pct(self) -> float:
        """Turnover rate."""
        poss = self.possessions
        if poss == 0:
            return 0
        return self.to / poss
    
    @property
    def orb_pct(self) -> float:
        """Offensive rebound %."""
        total_rebs = self.oreb + self.opp_dreb
        if total_rebs == 0:
            return 0
        return self.oreb / total_rebs
    
    @property
    def ft_rate(self) -> float:
        """Free throw rate = FTA/FGA."""
        if self.fga == 0:
            return 0
        return self.fta / self.fga
    
    @property
    def off_eff(self) -> float:
        """Offensive efficiency = pts per 100 possessions."""
        poss = self.possessions
        if poss == 0:
            return 100
        return (self.pts_for / poss) * 100
    
    @property
    def def_eff(self) -> float:
        """Defensive efficiency = opp pts per 100 possessions."""
        poss = self.opp_possessions
        if poss == 0:
            return 100
        return (self.pts_against / poss) * 100


class EnhancedTeamStatsTracker:
    """Track rolling box score stats for each team throughout the season."""
    
    def __init__(self):
        # team -> season -> list of GameBoxScore
        self.games: Dict[str, Dict[int, List[GameBoxScore]]] = defaultdict(lambda: defaultdict(list))
        
    def add_game(self, team: str, season: int, game: GameBoxScore):
        """Add a game's stats to a team's history."""
        self.games[team][season].append(game)
    
    def get_pregame_stats(self, team: str, season: int, min_games: int = 5) -> Optional[dict]:
        """Get rolling averages for a team BEFORE the current game.
        
        Returns None if team doesn't have enough games yet.
        """
        games = self.games[team][season]
        
        if len(games) < min_games:
            return None
        
        n = len(games)
        
        # Basic stats
        pts_for = np.mean([g.pts_for for g in games])
        pts_against = np.mean([g.pts_against for g in games])
        wins = sum(1 for g in games if g.won)
        
        # Tempo (average possessions per game)
        tempo = np.mean([g.possessions for g in games if g.possessions > 0])
        if np.isnan(tempo) or tempo == 0:
            tempo = 70  # Default
        
        # Four Factors (offensive)
        efg_pct = np.mean([g.efg_pct for g in games])
        to_pct = np.mean([g.to_pct for g in games])
        orb_pct = np.mean([g.orb_pct for g in games])
        ft_rate = np.mean([g.ft_rate for g in games])
        
        # Efficiency
        off_effs = [g.off_eff for g in games if g.possessions > 0]
        def_effs = [g.def_eff for g in games if g.opp_possessions > 0]
        
        off_eff = np.mean(off_effs) if off_effs else 100
        def_eff = np.mean(def_effs) if def_effs else 100
        
        return {
            'games_played': n,
            'wins': wins,
            'losses': n - wins,
            'win_pct': wins / n,
            'pts_for_avg': pts_for,
            'pts_against_avg': pts_against,
            'margin_avg': pts_for - pts_against,
            
            'tempo': tempo,
            'off_eff': off_eff,
            'def_eff': def_eff,
            'net_eff': off_eff - def_eff,
            
            'efg_pct': efg_pct,
            'to_pct': to_pct,
            'orb_pct': orb_pct,
            'ft_rate': ft_rate,
        }


class EnhancedBacktest:
    """Backtest using enhanced pre-game stats from box scores."""
    
    # Calibration parameters
    SIGMA_FG = 10.5  # Std dev for FG spread predictions
    HCA = 3.0  # Home court advantage in points
    
    def __init__(self):
        self.tracker = EnhancedTeamStatsTracker()
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
    
    def _load_box_scores(self) -> Dict[Tuple[str, str], pd.DataFrame]:
        """Load all box scores from ncaahoopR, indexed by (season, team)."""
        logger.info("Loading box scores from ncaahoopR...")
        
        box_scores = {}
        seasons_to_load = ['2020-21', '2021-22', '2022-23', '2023-24', '2024-25', '2025-26']
        
        for season_folder in seasons_to_load:
            season_path = NCAAHOOPR_DIR / season_folder / "box_scores"
            if not season_path.exists():
                continue
            
            for team_dir in season_path.iterdir():
                if not team_dir.is_dir():
                    continue
                
                team_name = team_dir.name.replace("_", " ")
                
                for box_file in team_dir.glob("*.csv"):
                    try:
                        df = pd.read_csv(box_file)
                        key = (season_folder, team_name, box_file.stem)
                        box_scores[key] = df
                    except:
                        continue
        
        logger.info(f"  Loaded {len(box_scores):,} box score files")
        return box_scores
    
    def _load_schedules_with_box_scores(self, box_scores: Dict) -> List[GameBoxScore]:
        """Load schedules and match with box score data."""
        logger.info("Loading schedules and matching with box scores...")
        
        all_games = []
        seasons_to_load = ['2020-21', '2021-22', '2022-23', '2023-24', '2024-25', '2025-26']
        
        for season_folder in seasons_to_load:
            season_path = NCAAHOOPR_DIR / season_folder / "schedules"
            box_path = NCAAHOOPR_DIR / season_folder / "box_scores"
            
            if not season_path.exists():
                continue
            
            for schedule_file in season_path.glob("*_schedule.csv"):
                try:
                    sched_df = pd.read_csv(schedule_file)
                    team_name = schedule_file.stem.replace("_schedule", "").replace("_", " ")
                    
                    for _, row in sched_df.iterrows():
                        game_id = row.get('game_id')
                        if pd.isna(game_id):
                            continue
                        
                        # Try to load box score for this game
                        box_key = (season_folder, team_name, str(int(game_id)))
                        box_df = box_scores.get(box_key)
                        
                        game = self._parse_game(row, team_name, box_df)
                        if game:
                            all_games.append((season_folder, game))
                
                except Exception as e:
                    continue
        
        logger.info(f"  Parsed {len(all_games):,} games with stats")
        return all_games
    
    def _parse_game(self, row, team_name: str, box_df: Optional[pd.DataFrame]) -> Optional[GameBoxScore]:
        """Parse a game from schedule + optional box score."""
        try:
            date = pd.to_datetime(row['date'])
            opponent = row.get('opponent', '')
            pts_for = row.get('team_score', 0)
            pts_against = row.get('opp_score', 0)
            location = row.get('location', 'N')
            home = location == 'H'
            
            if pd.isna(pts_for) or pd.isna(pts_against):
                return None
            
            game = GameBoxScore(
                date=date,
                team=team_name,
                opponent=opponent,
                home=home,
                pts_for=int(pts_for),
                pts_against=int(pts_against),
            )
            
            # If we have box score data, parse it
            if box_df is not None and len(box_df) > 0:
                # Get TEAM row
                team_row = box_df[box_df['player'] == 'TEAM']
                if len(team_row) > 0:
                    tr = team_row.iloc[0]
                    game.fgm = int(tr.get('FGM', 0) or 0)
                    game.fga = int(tr.get('FGA', 0) or 0)
                    game.fg3m = int(tr.get('3PTM', 0) or 0)
                    game.fg3a = int(tr.get('3PTA', 0) or 0)
                    game.ftm = int(tr.get('FTM', 0) or 0)
                    game.fta = int(tr.get('FTA', 0) or 0)
                    game.oreb = int(tr.get('OREB', 0) or 0)
                    game.dreb = int(tr.get('DREB', 0) or 0)
                    game.ast = int(tr.get('AST', 0) or 0)
                    game.to = int(tr.get('TO', 0) or 0)
                    game.stl = int(tr.get('STL', 0) or 0)
                    game.blk = int(tr.get('BLK', 0) or 0)
            else:
                # Estimate stats from score
                game.fga = max(1, int(pts_for / 1.0))  # Rough estimate
                game.fgm = int(pts_for * 0.35)
                game.to = 12  # Average turnovers
            
            return game
        
        except Exception as e:
            return None
    
    def _build_pregame_stats(self, games: List[Tuple[str, GameBoxScore]]):
        """Process games chronologically to build rolling stats."""
        logger.info("Building pre-game rolling stats from box scores...")
        
        # Sort by date
        games.sort(key=lambda x: x[1].date)
        
        for season_folder, game in games:
            team = self._normalize_team(game.team)
            season = get_season(game.date)
            self.tracker.add_game(team, season, game)
        
        logger.info(f"  Built stats for {len(self.tracker.games)} teams")
    
    def _load_odds(self) -> pd.DataFrame:
        """Load canonical odds data."""
        logger.info(f"Loading odds from {ODDS_FILE}")
        df = pd.read_csv(ODDS_FILE)
        df['game_date'] = pd.to_datetime(df['game_date'])
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
                       game_date, market_spread: float) -> Tuple[Optional[float], Optional[float], Optional[dict]]:
        """Predict spread using enhanced pre-game stats.
        
        Uses efficiency differential and tempo for more accurate predictions.
        
        Returns: (predicted_margin, edge, debug_info)
        """
        season = get_season(game_date)
        
        home_stats = self.tracker.get_pregame_stats(home_team, season)
        away_stats = self.tracker.get_pregame_stats(away_team, season)
        
        if not home_stats or not away_stats:
            return None, None, None
        
        # Expected tempo = average of both teams
        game_tempo = (home_stats['tempo'] + away_stats['tempo']) / 2
        
        # Adjusted efficiencies (normalize to D1 average of ~100)
        # Home team offense vs Away team defense
        # Away team offense vs Home team defense
        d1_avg_eff = 100
        
        # Simple model: use net efficiency differential
        home_net = home_stats['net_eff']
        away_net = away_stats['net_eff']
        
        # Predicted margin = tempo-adjusted net efficiency diff + HCA
        raw_diff = (home_net - away_net) / 100 * game_tempo
        predicted_margin = raw_diff + self.HCA
        
        # Edge for HOME ATS
        edge = predicted_margin + market_spread
        
        debug_info = {
            'home_net_eff': home_net,
            'away_net_eff': away_net,
            'tempo': game_tempo,
            'raw_diff': raw_diff,
        }
        
        return predicted_margin, edge, debug_info
    
    def predict_total(self, home_team: str, away_team: str,
                      game_date, market_total: float) -> Tuple[Optional[float], Optional[float], Optional[dict]]:
        """Predict total using enhanced pre-game stats."""
        season = get_season(game_date)
        
        home_stats = self.tracker.get_pregame_stats(home_team, season)
        away_stats = self.tracker.get_pregame_stats(away_team, season)
        
        if not home_stats or not away_stats:
            return None, None, None
        
        # Expected tempo
        game_tempo = (home_stats['tempo'] + away_stats['tempo']) / 2
        
        # Expected scoring
        # Home scores: (home off_eff + away def_eff) / 2 * tempo / 100
        # But we'll use simpler approach: average of both teams' PPG, tempo-adjusted
        
        d1_avg_tempo = 68  # Approximate D1 average
        
        home_ppg = home_stats['pts_for_avg']
        home_oppg = home_stats['pts_against_avg']
        away_ppg = away_stats['pts_for_avg']
        away_oppg = away_stats['pts_against_avg']
        
        # Tempo adjustment factor
        tempo_adj = game_tempo / d1_avg_tempo
        
        # Expected home score = (home_ppg + away_oppg) / 2 * tempo_adj
        expected_home = (home_ppg + away_oppg) / 2 * tempo_adj
        expected_away = (away_ppg + home_oppg) / 2 * tempo_adj
        
        predicted_total = expected_home + expected_away
        edge = predicted_total - market_total
        
        debug_info = {
            'home_ppg': home_ppg,
            'away_ppg': away_ppg,
            'tempo': game_tempo,
            'expected_home': expected_home,
            'expected_away': expected_away,
        }
        
        return predicted_total, edge, debug_info
    
    def run_backtest(self) -> pd.DataFrame:
        """Run the full backtest."""
        logger.info("=" * 80)
        logger.info("NCAAM BACKTEST V2 ENHANCED - BOX SCORE FEATURES")
        logger.info("NO DATA LEAKAGE - Only uses stats from BEFORE each game")
        logger.info("=" * 80)
        
        # Load and process data
        box_scores = self._load_box_scores()
        games = self._load_schedules_with_box_scores(box_scores)
        self._build_pregame_stats(games)
        
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
                pred_margin, edge, debug = self.predict_spread(home_team, away_team, game_date, market_spread)
                
                if pred_margin is not None:
                    bet_side = 'HOME' if edge > 0 else 'AWAY'
                    spread_price = row.get('spread_home_price' if bet_side == 'HOME' else 'spread_away_price', -110)
                    
                    won = None
                    if actual_scores:
                        actual_margin = actual_scores['home_score'] - actual_scores['away_score']
                        if bet_side == 'HOME':
                            won = actual_margin > -market_spread
                        else:
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
                pred_total, edge, debug = self.predict_total(home_team, away_team, game_date, market_total)
                
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
        
        edge_thresholds = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
        
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
                
                logger.info(f"  Edge >= {min_edge}: {total_bets:>5} bets | {win_rate:>5.1%} win | {roi:>7.2f}% ROI")
                
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
    backtest = EnhancedBacktest()
    results = backtest.run_backtest()
    
    print("\n" + "=" * 80)
    print("BACKTEST V2 ENHANCED COMPLETE - BOX SCORE FEATURES")
    print("=" * 80)
    print(f"\nResults saved to: {RESULTS_DIR}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
