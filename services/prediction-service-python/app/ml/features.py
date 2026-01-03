"""
Feature Engineering for NCAAM ML Models.

CRITICAL: All features must be available BEFORE game time to prevent leakage.
Features are computed from:
1. Barttorvik ratings (as of game date - 1 day to be safe)
2. Market odds (opening lines, current lines)
3. Situational factors (rest days, travel)
4. Historical performance

NO features from:
- Game results (scores, margins)
- Post-game statistics
- Closing lines (captured after game starts)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np


@dataclass
class GameFeatures:
    """All features for a single game, computed before tip-off."""
    
    # Identification (not used as features)
    game_id: str
    game_date: str
    home_team: str
    away_team: str
    
    # ═══════════════════════════════════════════════════════════════════════
    # CORE EFFICIENCY FEATURES (from Barttorvik)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Adjusted efficiency (points per 100 possessions)
    home_adj_o: float = 0.0
    home_adj_d: float = 0.0
    away_adj_o: float = 0.0
    away_adj_d: float = 0.0
    
    # Tempo (possessions per 40 minutes)
    home_tempo: float = 0.0
    away_tempo: float = 0.0
    
    # Rank (lower = better)
    home_rank: int = 0
    away_rank: int = 0
    
    # ═══════════════════════════════════════════════════════════════════════
    # FOUR FACTORS (shooting, turnovers, rebounding, free throws)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Effective FG%
    home_efg: float = 0.0
    home_efgd: float = 0.0
    away_efg: float = 0.0
    away_efgd: float = 0.0
    
    # Turnover rate
    home_tor: float = 0.0
    home_tord: float = 0.0
    away_tor: float = 0.0
    away_tord: float = 0.0
    
    # Offensive/Defensive rebound %
    home_orb: float = 0.0
    home_drb: float = 0.0
    away_orb: float = 0.0
    away_drb: float = 0.0
    
    # Free throw rate
    home_ftr: float = 0.0
    home_ftrd: float = 0.0
    away_ftr: float = 0.0
    away_ftrd: float = 0.0
    
    # ═══════════════════════════════════════════════════════════════════════
    # SHOOTING BREAKDOWN
    # ═══════════════════════════════════════════════════════════════════════
    
    home_two_pt_pct: float = 0.0
    home_two_pt_pct_d: float = 0.0
    away_two_pt_pct: float = 0.0
    away_two_pt_pct_d: float = 0.0
    
    home_three_pt_pct: float = 0.0
    home_three_pt_pct_d: float = 0.0
    away_three_pt_pct: float = 0.0
    away_three_pt_pct_d: float = 0.0
    
    home_three_pt_rate: float = 0.0
    home_three_pt_rate_d: float = 0.0
    away_three_pt_rate: float = 0.0
    away_three_pt_rate_d: float = 0.0
    
    # ═══════════════════════════════════════════════════════════════════════
    # QUALITY METRICS
    # ═══════════════════════════════════════════════════════════════════════
    
    home_barthag: float = 0.0  # Win probability vs average team
    home_wab: float = 0.0      # Wins Above Bubble
    away_barthag: float = 0.0
    away_wab: float = 0.0
    
    # ═══════════════════════════════════════════════════════════════════════
    # MARKET DATA (pre-game only!)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Opening lines (first available)
    spread_open: Optional[float] = None
    total_open: Optional[float] = None
    spread_1h_open: Optional[float] = None
    total_1h_open: Optional[float] = None
    
    # Current lines (at prediction time, NOT closing)
    spread_current: Optional[float] = None
    total_current: Optional[float] = None
    spread_1h_current: Optional[float] = None
    total_1h_current: Optional[float] = None
    
    # Sharp book lines
    sharp_spread: Optional[float] = None
    sharp_total: Optional[float] = None
    
    # Square book lines
    square_spread: Optional[float] = None
    square_total: Optional[float] = None
    
    # ═══════════════════════════════════════════════════════════════════════
    # SITUATIONAL FEATURES
    # ═══════════════════════════════════════════════════════════════════════
    
    is_neutral: bool = False
    home_rest_days: int = 3  # Days since last game
    away_rest_days: int = 3
    home_is_back_to_back: bool = False
    away_is_back_to_back: bool = False
    
    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC BETTING (if available)
    # ═══════════════════════════════════════════════════════════════════════
    
    public_bet_pct_home: Optional[float] = None
    public_money_pct_home: Optional[float] = None
    public_bet_pct_over: Optional[float] = None
    public_money_pct_over: Optional[float] = None


class FeatureEngineer:
    """
    Transform raw game data into ML features.
    
    LEAKAGE PREVENTION:
    - Only uses data available before game time
    - Ratings are filtered to rating_date < game_date
    - Market data is pre-game snapshots only
    """
    
    # League averages for normalization
    LEAGUE_AVG_TEMPO = 67.6
    LEAGUE_AVG_EFFICIENCY = 105.5
    LEAGUE_AVG_EFG = 50.0
    LEAGUE_AVG_TOR = 18.5
    LEAGUE_AVG_ORB = 28.0
    LEAGUE_AVG_FTR = 33.0
    
    def __init__(self):
        self._feature_names: Optional[List[str]] = None
    
    @property
    def feature_names(self) -> List[str]:
        """Return ordered list of feature names for model training."""
        if self._feature_names is None:
            self._feature_names = self._compute_feature_names()
        return self._feature_names
    
    def _compute_feature_names(self) -> List[str]:
        """Define all features used by the model."""
        return [
            # ─────────────────────────────────────────────────────────────
            # DERIVED EFFICIENCY FEATURES (differences, sums)
            # ─────────────────────────────────────────────────────────────
            "home_net_efficiency",      # home_adj_o - home_adj_d
            "away_net_efficiency",      # away_adj_o - away_adj_d
            "efficiency_diff",          # home_net - away_net
            "tempo_avg",                # (home_tempo + away_tempo) / 2
            "tempo_diff",               # home_tempo - away_tempo
            "rank_diff",                # away_rank - home_rank (positive = home better)
            
            # ─────────────────────────────────────────────────────────────
            # MATCHUP FEATURES
            # ─────────────────────────────────────────────────────────────
            "home_off_vs_away_def",     # home_adj_o - away_adj_d (above avg = advantage)
            "away_off_vs_home_def",     # away_adj_o - home_adj_d
            "net_matchup",              # home_off_vs_away_def - away_off_vs_home_def
            
            # ─────────────────────────────────────────────────────────────
            # FOUR FACTORS MATCHUPS
            # ─────────────────────────────────────────────────────────────
            "shooting_matchup",         # home_efg - away_efgd (home shooting vs away D)
            "turnover_matchup",         # away_tord - home_tor (home ball security)
            "rebound_matchup",          # home_orb - away_drb (home offensive boards)
            "ftr_matchup",              # home_ftr - away_ftrd (home free throw generation)
            
            # ─────────────────────────────────────────────────────────────
            # STYLE FEATURES
            # ─────────────────────────────────────────────────────────────
            "three_pt_rate_avg",        # Average 3PT rate
            "three_pt_rate_diff",       # Home vs Away 3PT tendency
            "pace_factor",              # Combined tempo deviation from league avg
            
            # ─────────────────────────────────────────────────────────────
            # QUALITY FEATURES
            # ─────────────────────────────────────────────────────────────
            "barthag_diff",             # home_barthag - away_barthag
            "wab_diff",                 # home_wab - away_wab
            "home_barthag",             # Absolute home quality
            "away_barthag",             # Absolute away quality
            
            # ─────────────────────────────────────────────────────────────
            # MARKET FEATURES (pre-game)
            # ─────────────────────────────────────────────────────────────
            "spread_open",              # Opening spread
            "total_open",               # Opening total
            "line_movement_spread",     # current - open (if available)
            "line_movement_total",      # current - open
            "sharp_square_diff_spread", # sharp - square (divergence)
            "sharp_square_diff_total",
            
            # ─────────────────────────────────────────────────────────────
            # SITUATIONAL FEATURES
            # ─────────────────────────────────────────────────────────────
            "is_neutral",               # 1 if neutral site
            "home_rest_advantage",      # home_rest - away_rest
            "home_b2b",                 # 1 if home back-to-back
            "away_b2b",                 # 1 if away back-to-back
            
            # ─────────────────────────────────────────────────────────────
            # PUBLIC BETTING (if available, else 0)
            # ─────────────────────────────────────────────────────────────
            "public_home_pct",          # % tickets on home
            "sharp_indicator_spread",   # money% - ticket% (positive = sharp on home)
            "public_over_pct",          # % tickets on over
            "sharp_indicator_total",    # money% - ticket% for totals
        ]
    
    def extract_features(self, game: GameFeatures) -> np.ndarray:
        """
        Convert GameFeatures to numpy array for model input.
        
        Returns array of shape (n_features,)
        """
        features = []
        
        # ─────────────────────────────────────────────────────────────────
        # DERIVED EFFICIENCY FEATURES
        # ─────────────────────────────────────────────────────────────────
        home_net = game.home_adj_o - game.home_adj_d
        away_net = game.away_adj_o - game.away_adj_d
        
        features.append(home_net)
        features.append(away_net)
        features.append(home_net - away_net)  # efficiency_diff
        features.append((game.home_tempo + game.away_tempo) / 2)  # tempo_avg
        features.append(game.home_tempo - game.away_tempo)  # tempo_diff
        features.append(game.away_rank - game.home_rank)  # rank_diff (+ = home better)
        
        # ─────────────────────────────────────────────────────────────────
        # MATCHUP FEATURES
        # ─────────────────────────────────────────────────────────────────
        home_off_vs_away_def = (game.home_adj_o - self.LEAGUE_AVG_EFFICIENCY) - \
                               (game.away_adj_d - self.LEAGUE_AVG_EFFICIENCY)
        away_off_vs_home_def = (game.away_adj_o - self.LEAGUE_AVG_EFFICIENCY) - \
                               (game.home_adj_d - self.LEAGUE_AVG_EFFICIENCY)
        
        features.append(home_off_vs_away_def)
        features.append(away_off_vs_home_def)
        features.append(home_off_vs_away_def - away_off_vs_home_def)
        
        # ─────────────────────────────────────────────────────────────────
        # FOUR FACTORS MATCHUPS
        # ─────────────────────────────────────────────────────────────────
        features.append(game.home_efg - game.away_efgd)  # shooting_matchup
        features.append(game.away_tord - game.home_tor)  # turnover_matchup
        features.append(game.home_orb - game.away_drb)   # rebound_matchup
        features.append(game.home_ftr - game.away_ftrd)  # ftr_matchup
        
        # ─────────────────────────────────────────────────────────────────
        # STYLE FEATURES
        # ─────────────────────────────────────────────────────────────────
        avg_3pr = (game.home_three_pt_rate + game.away_three_pt_rate) / 2
        diff_3pr = game.home_three_pt_rate - game.away_three_pt_rate
        pace_factor = ((game.home_tempo - self.LEAGUE_AVG_TEMPO) + 
                       (game.away_tempo - self.LEAGUE_AVG_TEMPO)) / 2
        
        features.append(avg_3pr)
        features.append(diff_3pr)
        features.append(pace_factor)
        
        # ─────────────────────────────────────────────────────────────────
        # QUALITY FEATURES
        # ─────────────────────────────────────────────────────────────────
        features.append(game.home_barthag - game.away_barthag)
        features.append(game.home_wab - game.away_wab)
        features.append(game.home_barthag)
        features.append(game.away_barthag)
        
        # ─────────────────────────────────────────────────────────────────
        # MARKET FEATURES
        # ─────────────────────────────────────────────────────────────────
        features.append(game.spread_open or 0.0)
        features.append(game.total_open or 0.0)
        
        # Line movement
        line_move_spread = 0.0
        if game.spread_current is not None and game.spread_open is not None:
            line_move_spread = game.spread_current - game.spread_open
        features.append(line_move_spread)
        
        line_move_total = 0.0
        if game.total_current is not None and game.total_open is not None:
            line_move_total = game.total_current - game.total_open
        features.append(line_move_total)
        
        # Sharp vs square divergence
        sharp_sq_spread = 0.0
        if game.sharp_spread is not None and game.square_spread is not None:
            sharp_sq_spread = game.sharp_spread - game.square_spread
        features.append(sharp_sq_spread)
        
        sharp_sq_total = 0.0
        if game.sharp_total is not None and game.square_total is not None:
            sharp_sq_total = game.sharp_total - game.square_total
        features.append(sharp_sq_total)
        
        # ─────────────────────────────────────────────────────────────────
        # SITUATIONAL FEATURES
        # ─────────────────────────────────────────────────────────────────
        features.append(1.0 if game.is_neutral else 0.0)
        features.append(game.home_rest_days - game.away_rest_days)
        features.append(1.0 if game.home_is_back_to_back else 0.0)
        features.append(1.0 if game.away_is_back_to_back else 0.0)
        
        # ─────────────────────────────────────────────────────────────────
        # PUBLIC BETTING
        # ─────────────────────────────────────────────────────────────────
        public_home = game.public_bet_pct_home or 0.5
        money_home = game.public_money_pct_home or 0.5
        public_over = game.public_bet_pct_over or 0.5
        money_over = game.public_money_pct_over or 0.5
        
        features.append(public_home)
        features.append(money_home - public_home)  # Sharp indicator
        features.append(public_over)
        features.append(money_over - public_over)
        
        return np.array(features, dtype=np.float32)
    
    def extract_batch(self, games: List[GameFeatures]) -> np.ndarray:
        """Extract features for multiple games."""
        return np.stack([self.extract_features(g) for g in games])
    
    @staticmethod
    def from_game_dict(game: Dict[str, Any], ratings: Dict[str, Any]) -> GameFeatures:
        """
        Create GameFeatures from raw database query results.
        
        Args:
            game: Game row with market data
            ratings: Dict with home_ratings and away_ratings
        """
        home = ratings.get("home_ratings", {})
        away = ratings.get("away_ratings", {})
        
        return GameFeatures(
            game_id=str(game.get("game_id", "")),
            game_date=str(game.get("game_date", "")),
            home_team=game.get("home", ""),
            away_team=game.get("away", ""),
            
            # Core efficiency
            home_adj_o=float(home.get("adj_o", 0)),
            home_adj_d=float(home.get("adj_d", 0)),
            away_adj_o=float(away.get("adj_o", 0)),
            away_adj_d=float(away.get("adj_d", 0)),
            home_tempo=float(home.get("tempo", 67.6)),
            away_tempo=float(away.get("tempo", 67.6)),
            home_rank=int(home.get("rank", 175)),
            away_rank=int(away.get("rank", 175)),
            
            # Four factors
            home_efg=float(home.get("efg", 50)),
            home_efgd=float(home.get("efgd", 50)),
            away_efg=float(away.get("efg", 50)),
            away_efgd=float(away.get("efgd", 50)),
            home_tor=float(home.get("tor", 18.5)),
            home_tord=float(home.get("tord", 18.5)),
            away_tor=float(away.get("tor", 18.5)),
            away_tord=float(away.get("tord", 18.5)),
            home_orb=float(home.get("orb", 28)),
            home_drb=float(home.get("drb", 72)),
            away_orb=float(away.get("orb", 28)),
            away_drb=float(away.get("drb", 72)),
            home_ftr=float(home.get("ftr", 33)),
            home_ftrd=float(home.get("ftrd", 33)),
            away_ftr=float(away.get("ftr", 33)),
            away_ftrd=float(away.get("ftrd", 33)),
            
            # Shooting
            home_two_pt_pct=float(home.get("two_pt_pct", 50)),
            home_two_pt_pct_d=float(home.get("two_pt_pct_d", 50)),
            away_two_pt_pct=float(away.get("two_pt_pct", 50)),
            away_two_pt_pct_d=float(away.get("two_pt_pct_d", 50)),
            home_three_pt_pct=float(home.get("three_pt_pct", 35)),
            home_three_pt_pct_d=float(home.get("three_pt_pct_d", 35)),
            away_three_pt_pct=float(away.get("three_pt_pct", 35)),
            away_three_pt_pct_d=float(away.get("three_pt_pct_d", 35)),
            home_three_pt_rate=float(home.get("three_pt_rate", 35)),
            home_three_pt_rate_d=float(home.get("three_pt_rate_d", 35)),
            away_three_pt_rate=float(away.get("three_pt_rate", 35)),
            away_three_pt_rate_d=float(away.get("three_pt_rate_d", 35)),
            
            # Quality
            home_barthag=float(home.get("barthag", 0.5)),
            home_wab=float(home.get("wab", 0)),
            away_barthag=float(away.get("barthag", 0.5)),
            away_wab=float(away.get("wab", 0)),
            
            # Market
            spread_open=game.get("spread_open"),
            total_open=game.get("total_open"),
            spread_1h_open=game.get("spread_1h_open"),
            total_1h_open=game.get("total_1h_open"),
            spread_current=game.get("spread"),
            total_current=game.get("total"),
            spread_1h_current=game.get("spread_1h"),
            total_1h_current=game.get("total_1h"),
            sharp_spread=game.get("sharp_spread"),
            sharp_total=game.get("sharp_total"),
            square_spread=game.get("square_spread"),
            square_total=game.get("square_total"),
            
            # Situational
            is_neutral=game.get("is_neutral", False),
            home_rest_days=game.get("home_rest_days", 3),
            away_rest_days=game.get("away_rest_days", 3),
            home_is_back_to_back=game.get("home_rest_days", 3) <= 1,
            away_is_back_to_back=game.get("away_rest_days", 3) <= 1,
            
            # Public betting
            public_bet_pct_home=game.get("public_bet_pct_home"),
            public_money_pct_home=game.get("public_money_pct_home"),
            public_bet_pct_over=game.get("public_bet_pct_over"),
            public_money_pct_over=game.get("public_money_pct_over"),
        )
