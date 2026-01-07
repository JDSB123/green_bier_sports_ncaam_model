"""
ROI Simulator - Backtest betting performance with historical odds.

This module simulates betting outcomes using:
1. Production model predictions
2. Historical market odds
3. Actual game results

Outputs:
- ROI by edge threshold
- Win rate by model
- Optimal edge thresholds
- Unit P/L over time

Usage:
    python -m testing.production_parity.roi_simulator --season 2024
"""

import csv
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

# Add prediction-service-python to path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "services" / "prediction-service-python"))

from .team_resolver import ProductionTeamResolver
from .ratings_loader import AntiLeakageRatingsLoader, TeamRatings
from .timezone_utils import get_season_for_game, parse_date_to_cst, format_cst_date

# Import production models
try:
    from app.predictors.fg_spread import FGSpreadModel
    from app.predictors.fg_total import FGTotalModel
    from app.predictors.h1_spread import H1SpreadModel
    from app.predictors.h1_total import H1TotalModel
    from app.models import TeamRatings as ProductionTeamRatings
    MODELS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Production models not available: {e}")
    MODELS_AVAILABLE = False


@dataclass
class OddsRecord:
    """Historical odds for a game."""
    event_id: str
    commence_time: datetime
    game_date: str
    home_team: str
    away_team: str
    home_canonical: str
    away_canonical: str
    bookmaker: str
    spread: Optional[float]
    total: Optional[float]
    h1_spread: Optional[float] = None
    h1_total: Optional[float] = None
    timestamp: Optional[datetime] = None


@dataclass
class BetResult:
    """Result of a simulated bet."""
    game_id: str
    date: str
    model: str
    pick: str
    edge: float
    market_line: float
    predicted_line: float
    actual_result: float
    won: bool
    units_wagered: float = 1.0
    units_won: float = 0.0


@dataclass
class ROIResults:
    """Aggregate ROI results."""
    edge_threshold: float
    model: str
    total_bets: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    units_wagered: float
    units_won: float
    roi: float
    
    def to_dict(self) -> dict:
        return {
            "edge_threshold": self.edge_threshold,
            "model": self.model,
            "total_bets": self.total_bets,
            "wins": self.wins,
            "losses": self.losses,
            "pushes": self.pushes,
            "win_rate": round(self.win_rate * 100, 1),
            "units_wagered": self.units_wagered,
            "units_won": round(self.units_won, 2),
            "roi": round(self.roi * 100, 1),
        }


class ROISimulator:
    """
    Simulates betting ROI using historical data.
    
    Key features:
    - Anti-leakage: Uses Season N-1 ratings for Season N games
    - Actual odds: Uses historical market lines (not synthetic)
    - Fair comparison: Standard -110 juice assumed
    """
    
    JUICE = -110  # Standard juice for calculation
    
    def __init__(
        self,
        games_dir: Path = None,
        odds_dir: Path = None,
        ratings_dir: Path = None,
    ):
        self.data_dir = ROOT_DIR / "testing" / "data"
        self.games_dir = games_dir or self.data_dir / "historical"
        self.odds_dir = odds_dir or self.data_dir / "historical_odds"
        self.ratings_dir = ratings_dir or self.data_dir / "historical"
        
        self.team_resolver = ProductionTeamResolver()
        self.ratings_loader = AntiLeakageRatingsLoader(data_dir=self.ratings_dir)
        
        # Initialize models
        if MODELS_AVAILABLE:
            self.models = {
                "FGSpread": FGSpreadModel(),
                "FGTotal": FGTotalModel(),
                "H1Spread": H1SpreadModel(),
                "H1Total": H1TotalModel(),
            }
        else:
            self.models = {}
        
        self.bookmaker_priority = ["pinnacle", "draftkings", "fanduel", "betmgm"]
        self.odds_cache: Dict[str, Dict[str, OddsRecord]] = {}
        self.results: List[BetResult] = []
    
    def _normalize_game_date(self, date_str: str) -> str:
        if not date_str:
            return ""
        try:
            return format_cst_date(parse_date_to_cst(date_str))
        except (ValueError, TypeError):
            return date_str[:10]

    def _make_matchup_key(self, home_canonical: str, away_canonical: str, game_date: str) -> str:
        return f"{home_canonical}|{away_canonical}|{game_date}"

    def _parse_timestamp(self, value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.fromtimestamp(float(value))
            except (ValueError, TypeError):
                return None

    def _get_odds_files(self) -> List[Path]:
        canonical = self.odds_dir / "odds_canonical_matchups.csv"
        if canonical.exists():
            return [canonical]

        consolidated = self.odds_dir / "odds_consolidated_canonical.csv"
        if consolidated.exists():
            return [consolidated]

        csv_files = sorted(self.odds_dir.glob("*.csv"))
        exclude = {
            "odds_team_rows_canonical.csv",
            "odds_canonical_matchups.csv",
            "odds_consolidated_canonical.csv",
        }
        return [path for path in csv_files if path.name not in exclude]

    def _record_has_market(self, record: OddsRecord, market: str) -> bool:
        if market == "fg_spread":
            return record.spread is not None
        if market == "fg_total":
            return record.total is not None
        if market == "h1_spread":
            return record.h1_spread is not None
        if market == "h1_total":
            return record.h1_total is not None
        return False

    def _select_best_record(
        self,
        records: Optional[Dict[str, OddsRecord]],
        market: str,
    ) -> Optional[OddsRecord]:
        if not records:
            return None

        for book in self.bookmaker_priority:
            record = records.get(book)
            if record and self._record_has_market(record, market):
                return record

        fallback = []
        for record in records.values():
            if self._record_has_market(record, market):
                fallback.append(record)

        if not fallback:
            return None

        fallback.sort(key=lambda r: r.timestamp or datetime.max)
        return fallback[0]

    def _swap_record(self, record: OddsRecord) -> OddsRecord:
        return OddsRecord(
            event_id=record.event_id,
            commence_time=record.commence_time,
            game_date=record.game_date,
            home_team=record.away_team,
            away_team=record.home_team,
            home_canonical=record.away_canonical,
            away_canonical=record.home_canonical,
            bookmaker=record.bookmaker,
            spread=-record.spread if record.spread is not None else None,
            total=record.total,
            h1_spread=-record.h1_spread if record.h1_spread is not None else None,
            h1_total=record.h1_total,
            timestamp=record.timestamp,
        )

    def load_historical_odds(self, seasons: List[int] = None) -> int:
        """Load historical odds from CSV files."""
        loaded = 0
        unmatched = 0
        files = self._get_odds_files()

        for odds_file in files:
            try:
                with open(odds_file, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            home_team = (row.get("home_team") or "").strip()
                            away_team = (row.get("away_team") or "").strip()

                            home_canonical = (row.get("home_team_canonical") or "").strip()
                            away_canonical = (row.get("away_team_canonical") or "").strip()

                            if not home_canonical:
                                result = self.team_resolver.resolve(home_team)
                                home_canonical = result.canonical_name if result.resolved else ""
                            if not away_canonical:
                                result = self.team_resolver.resolve(away_team)
                                away_canonical = result.canonical_name if result.resolved else ""

                            if not home_canonical or not away_canonical:
                                unmatched += 1
                                continue

                            commence_time_raw = row.get("commence_time", "")
                            commence_time = parse_date_to_cst(commence_time_raw) if commence_time_raw else None
                            if commence_time is None:
                                unmatched += 1
                                continue

                            game_date = row.get("game_date", "")
                            if not game_date:
                                game_date = self._normalize_game_date(commence_time_raw)
                            else:
                                game_date = self._normalize_game_date(game_date)

                            if not game_date:
                                unmatched += 1
                                continue

                            if seasons and get_season_for_game(game_date) not in seasons:
                                continue

                            bookmaker = (row.get("bookmaker") or "unknown").strip().lower()
                            spread = float(row["spread"]) if row.get("spread") else None
                            total = float(row["total"]) if row.get("total") else None
                            h1_spread = float(row["h1_spread"]) if row.get("h1_spread") else None
                            h1_total = float(row["h1_total"]) if row.get("h1_total") else None
                            timestamp = self._parse_timestamp(row.get("timestamp", ""))

                            odds = OddsRecord(
                                event_id=row.get("event_id", ""),
                                commence_time=commence_time,
                                game_date=game_date,
                                home_team=home_team,
                                away_team=away_team,
                                home_canonical=home_canonical,
                                away_canonical=away_canonical,
                                bookmaker=bookmaker,
                                spread=spread,
                                total=total,
                                h1_spread=h1_spread,
                                h1_total=h1_total,
                                timestamp=timestamp,
                            )

                            key = self._make_matchup_key(home_canonical, away_canonical, game_date)
                            book_map = self.odds_cache.setdefault(key, {})
                            existing = book_map.get(bookmaker)

                            if not existing:
                                book_map[bookmaker] = odds
                                loaded += 1
                                continue

                            if existing.timestamp and timestamp:
                                if timestamp < existing.timestamp:
                                    book_map[bookmaker] = odds
                            elif timestamp and not existing.timestamp:
                                book_map[bookmaker] = odds
                        except (ValueError, KeyError):
                            continue
            except Exception as e:
                print(f"Error loading {odds_file}: {e}")

        print(f"Loaded {loaded} odds records from {len(files)} file(s)")
        if unmatched:
            print(f"Skipped {unmatched} odds rows due to unresolved teams or dates")
        return loaded

    def find_odds_for_market(
        self,
        home_canonical: str,
        away_canonical: str,
        game_date: str,
        market: str,
    ) -> Optional[OddsRecord]:
        """Find odds for a matchup and market using canonical names."""
        key = self._make_matchup_key(home_canonical, away_canonical, game_date)
        record = self._select_best_record(self.odds_cache.get(key), market)
        if record:
            return record

        swapped_key = self._make_matchup_key(away_canonical, home_canonical, game_date)
        record = self._select_best_record(self.odds_cache.get(swapped_key), market)
        if record:
            return self._swap_record(record)

        return None

    def _resolve_canonical(self, name: str) -> Optional[str]:
        result = self.team_resolver.resolve(name)
        return result.canonical_name if result.resolved else None

    def _parse_int(self, value: str) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _load_full_games(self, season: int) -> List[Dict[str, Optional[str]]]:
        games_file = self.games_dir / f"games_{season}.csv"
        if not games_file.exists():
            print(f"Games file not found: {games_file}")
            return []

        games = []
        with open(games_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                game_date = row.get("date", row.get("game_date", "")) or ""
                if not game_date:
                    continue
                if get_season_for_game(game_date) != season:
                    continue

                games.append({
                    "game_id": row.get("game_id", ""),
                    "date": game_date,
                    "home_team": row.get("home_team", ""),
                    "away_team": row.get("away_team", ""),
                    "home_score": self._parse_int(row.get("home_score", "")),
                    "away_score": self._parse_int(row.get("away_score", "")),
                    "h1_home": self._parse_int(row.get("h1_home", "")),
                    "h1_away": self._parse_int(row.get("h1_away", "")),
                })

        return games

    def _load_h1_games(self, season: int) -> List[Dict[str, Optional[str]]]:
        h1_file = self.data_dir / "h1_historical" / "h1_games_all.csv"
        if not h1_file.exists():
            return []

        games = []
        with open(h1_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                game_date = row.get("date", "") or ""
                if not game_date:
                    continue
                if get_season_for_game(game_date) != season:
                    continue

                games.append({
                    "game_id": row.get("game_id", ""),
                    "date": game_date,
                    "home_team": row.get("home_team", ""),
                    "away_team": row.get("away_team", ""),
                    "home_score": self._parse_int(row.get("home_fg", "")),
                    "away_score": self._parse_int(row.get("away_fg", "")),
                    "h1_home": self._parse_int(row.get("home_h1", "")),
                    "h1_away": self._parse_int(row.get("away_h1", "")),
                })

        return games
    
    def calculate_edge(
        self,
        prediction: float,
        market_line: float,
        bet_type: str,
    ) -> Tuple[float, str]:
        """
        Calculate edge and pick direction.
        
        For spreads: negative prediction means home favored
        For totals: compare prediction to market
        """
        if "Spread" in bet_type:
            # Spread: prediction is home margin (negative = home favored)
            # Market spread is from home perspective
            edge = abs(prediction - market_line)
            if prediction < market_line:
                pick = "HOME"  # Model thinks home is stronger
            else:
                pick = "AWAY"
        else:
            # Total
            edge = abs(prediction - market_line)
            if prediction > market_line:
                pick = "OVER"
            else:
                pick = "UNDER"
        
        return edge, pick
    
    def evaluate_bet(
        self,
        pick: str,
        market_line: float,
        actual_result: float,
        bet_type: str,
    ) -> Tuple[bool, float]:
        """
        Evaluate if a bet won.
        
        Returns: (won, units_won)
        Units won is +0.91 for win, -1.0 for loss, 0 for push
        """
        if "Spread" in bet_type:
            actual_margin = actual_result  # Home margin
            if pick == "HOME":
                # Bet on home to cover
                result = actual_margin + market_line
            else:
                # Bet on away to cover
                result = -(actual_margin + market_line)
            
            if result > 0:
                return True, 0.91  # Win at -110
            elif result < 0:
                return False, -1.0  # Loss
            else:
                return None, 0.0  # Push
        else:
            # Total
            actual_total = actual_result
            if pick == "OVER":
                if actual_total > market_line:
                    return True, 0.91
                elif actual_total < market_line:
                    return False, -1.0
                else:
                    return None, 0.0
            else:  # UNDER
                if actual_total < market_line:
                    return True, 0.91
                elif actual_total > market_line:
                    return False, -1.0
                else:
                    return None, 0.0
    
    def simulate_season(
        self,
        season: int,
        edge_thresholds: List[float] = None,
    ) -> Dict[str, List[ROIResults]]:
        """
        Simulate betting for a full season.
        
        Args:
            season: The season year (e.g., 2024 for 2023-24 season)
            edge_thresholds: List of edge thresholds to test
        
        Returns:
            Dict mapping model name to list of ROI results by threshold
        """
        if edge_thresholds is None:
            edge_thresholds = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0]
        
        full_games = self._load_full_games(season)
        h1_games = self._load_h1_games(season)

        if not full_games and not h1_games:
            print(f"No games found for season {season}")
            return {}

        # Track bets by model and threshold
        bets_by_model: Dict[str, List[BetResult]] = {
            model: [] for model in self.models.keys()
        }

        stats = {
            "fg_games_seen": 0,
            "fg_games_with_odds": 0,
            "h1_games_seen": 0,
            "h1_games_with_odds": 0,
            "ratings_missing": 0,
            "unresolved_teams": 0,
        }

        h1_by_game_id: Dict[str, Dict[str, Optional[str]]] = {}
        h1_by_matchup: Dict[str, Dict[str, Optional[str]]] = {}
        for row in h1_games:
            game_id = row.get("game_id", "")
            if game_id:
                h1_by_game_id[game_id] = row

            home_canonical = self._resolve_canonical(row.get("home_team", ""))
            away_canonical = self._resolve_canonical(row.get("away_team", ""))
            if not home_canonical or not away_canonical:
                continue

            game_date = self._normalize_game_date(row.get("date", ""))
            if not game_date:
                continue

            key = self._make_matchup_key(home_canonical, away_canonical, game_date)
            if key not in h1_by_matchup:
                h1_by_matchup[key] = row

        processed_h1_ids = set()
        processed_h1_keys = set()

        def run_models(
            row: Dict[str, Optional[str]],
            home_canonical: str,
            away_canonical: str,
            game_date: str,
            actual_margin: Optional[int],
            actual_total: Optional[int],
            actual_h1_margin: Optional[int],
            actual_h1_total: Optional[int],
            run_full_game: bool,
            run_h1: bool,
        ) -> Tuple[bool, bool]:
            home_result = self.ratings_loader.get_ratings_for_game(home_canonical, game_date)
            away_result = self.ratings_loader.get_ratings_for_game(away_canonical, game_date)

            if not home_result.found or not away_result.found:
                stats["ratings_missing"] += 1
                return False, False

            home_ratings = home_result.ratings
            away_ratings = away_result.ratings

            home_prod = self._to_production_ratings(home_ratings)
            away_prod = self._to_production_ratings(away_ratings)

            if not home_prod or not away_prod:
                return False, False

            fg_odds_found = False
            h1_odds_found = False

            for model_name, model in self.models.items():
                try:
                    if model_name == "FGSpread":
                        if not run_full_game or actual_margin is None:
                            continue
                        market = "fg_spread"
                        odds = self.find_odds_for_market(home_canonical, away_canonical, game_date, market)
                        if not odds or odds.spread is None:
                            continue
                        market_line = odds.spread
                        actual_result = actual_margin
                        fg_odds_found = True
                    elif model_name == "FGTotal":
                        if not run_full_game or actual_total is None:
                            continue
                        market = "fg_total"
                        odds = self.find_odds_for_market(home_canonical, away_canonical, game_date, market)
                        if not odds or odds.total is None:
                            continue
                        market_line = odds.total
                        actual_result = actual_total
                        fg_odds_found = True
                    elif model_name == "H1Spread":
                        if not run_h1 or actual_h1_margin is None:
                            continue
                        market = "h1_spread"
                        odds = self.find_odds_for_market(home_canonical, away_canonical, game_date, market)
                        if not odds or odds.h1_spread is None:
                            continue
                        market_line = odds.h1_spread
                        actual_result = actual_h1_margin
                        h1_odds_found = True
                    elif model_name == "H1Total":
                        if not run_h1 or actual_h1_total is None:
                            continue
                        market = "h1_total"
                        odds = self.find_odds_for_market(home_canonical, away_canonical, game_date, market)
                        if not odds or odds.h1_total is None:
                            continue
                        market_line = odds.h1_total
                        actual_result = actual_h1_total
                        h1_odds_found = True
                    else:
                        continue

                    result = model.predict(home_prod, away_prod)
                    prediction = result.value

                    edge, pick = self.calculate_edge(
                        prediction, market_line, model_name
                    )

                    won, units_won = self.evaluate_bet(
                        pick, market_line, actual_result, model_name
                    )

                    bet = BetResult(
                        game_id=row.get("game_id", ""),
                        date=game_date,
                        model=model_name,
                        pick=pick,
                        edge=edge,
                        market_line=market_line,
                        predicted_line=prediction,
                        actual_result=actual_result,
                        won=won if won is not None else False,
                        units_wagered=1.0,
                        units_won=units_won,
                    )

                    bets_by_model[model_name].append(bet)

                except Exception:
                    continue

            return fg_odds_found, h1_odds_found

        for row in full_games:
            game_date = self._normalize_game_date(row.get("date", ""))
            if not game_date:
                continue

            home_team_raw = row.get("home_team", "")
            away_team_raw = row.get("away_team", "")
            home_score = row.get("home_score")
            away_score = row.get("away_score")
            if home_score is None or away_score is None:
                continue

            home_canonical = self._resolve_canonical(home_team_raw)
            away_canonical = self._resolve_canonical(away_team_raw)
            if not home_canonical or not away_canonical:
                stats["unresolved_teams"] += 1
                continue

            h1_home = row.get("h1_home")
            h1_away = row.get("h1_away")
            matchup_key = self._make_matchup_key(home_canonical, away_canonical, game_date)

            h1_source = None
            if h1_home is None or h1_away is None:
                if row.get("game_id") in h1_by_game_id:
                    h1_source = h1_by_game_id.get(row.get("game_id"))
                else:
                    h1_source = h1_by_matchup.get(matchup_key)

            if h1_source:
                h1_home = h1_source.get("h1_home")
                h1_away = h1_source.get("h1_away")
                if h1_source.get("game_id"):
                    processed_h1_ids.add(h1_source.get("game_id"))
                processed_h1_keys.add(matchup_key)

            actual_margin = home_score - away_score
            actual_total = home_score + away_score
            actual_h1_margin = None
            actual_h1_total = None
            if h1_home is not None and h1_away is not None:
                actual_h1_margin = h1_home - h1_away
                actual_h1_total = h1_home + h1_away
                processed_h1_keys.add(matchup_key)
                if row.get("game_id"):
                    processed_h1_ids.add(row.get("game_id"))

            stats["fg_games_seen"] += 1
            if actual_h1_margin is not None:
                stats["h1_games_seen"] += 1

            fg_odds_found, h1_odds_found = run_models(
                row=row,
                home_canonical=home_canonical,
                away_canonical=away_canonical,
                game_date=game_date,
                actual_margin=actual_margin,
                actual_total=actual_total,
                actual_h1_margin=actual_h1_margin,
                actual_h1_total=actual_h1_total,
                run_full_game=True,
                run_h1=actual_h1_margin is not None,
            )

            if fg_odds_found:
                stats["fg_games_with_odds"] += 1
            if h1_odds_found:
                stats["h1_games_with_odds"] += 1

        for row in h1_games:
            game_id = row.get("game_id", "")
            if game_id and game_id in processed_h1_ids:
                continue

            game_date = self._normalize_game_date(row.get("date", ""))
            if not game_date:
                continue

            home_team_raw = row.get("home_team", "")
            away_team_raw = row.get("away_team", "")

            home_canonical = self._resolve_canonical(home_team_raw)
            away_canonical = self._resolve_canonical(away_team_raw)
            if not home_canonical or not away_canonical:
                stats["unresolved_teams"] += 1
                continue

            key = self._make_matchup_key(home_canonical, away_canonical, game_date)
            if key in processed_h1_keys:
                continue

            h1_home = row.get("h1_home")
            h1_away = row.get("h1_away")
            if h1_home is None or h1_away is None:
                continue

            actual_h1_margin = h1_home - h1_away
            actual_h1_total = h1_home + h1_away

            stats["h1_games_seen"] += 1

            _fg_odds_found, h1_odds_found = run_models(
                row=row,
                home_canonical=home_canonical,
                away_canonical=away_canonical,
                game_date=game_date,
                actual_margin=None,
                actual_total=None,
                actual_h1_margin=actual_h1_margin,
                actual_h1_total=actual_h1_total,
                run_full_game=False,
                run_h1=True,
            )

            if h1_odds_found:
                stats["h1_games_with_odds"] += 1

        print(
            f"Full games: {stats['fg_games_seen']} rows, "
            f"{stats['fg_games_with_odds']} with odds"
        )
        print(
            f"H1 games: {stats['h1_games_seen']} rows, "
            f"{stats['h1_games_with_odds']} with odds"
        )
        if stats["h1_games_seen"] and stats["h1_games_with_odds"] == 0:
            print("Warning: No H1 odds matched for this season (pull H1 odds for coverage).")
        if stats["ratings_missing"]:
            print(f"Skipped {stats['ratings_missing']} games due to missing ratings")
        if stats["unresolved_teams"]:
            print(f"Skipped {stats['unresolved_teams']} games due to unresolved teams")
        
        # Calculate ROI by threshold
        results: Dict[str, List[ROIResults]] = {}
        
        for model_name, bets in bets_by_model.items():
            model_results = []
            
            for threshold in edge_thresholds:
                qualified_bets = [b for b in bets if b.edge >= threshold]
                
                if not qualified_bets:
                    model_results.append(ROIResults(
                        edge_threshold=threshold,
                        model=model_name,
                        total_bets=0,
                        wins=0,
                        losses=0,
                        pushes=0,
                        win_rate=0.0,
                        units_wagered=0.0,
                        units_won=0.0,
                        roi=0.0,
                    ))
                    continue
                
                wins = sum(1 for b in qualified_bets if b.won is True)
                losses = sum(1 for b in qualified_bets if b.won is False)
                pushes = sum(1 for b in qualified_bets if b.units_won == 0)
                units_wagered = float(len(qualified_bets))
                units_won = sum(b.units_won for b in qualified_bets)
                win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0
                roi = units_won / units_wagered if units_wagered > 0 else 0.0
                
                model_results.append(ROIResults(
                    edge_threshold=threshold,
                    model=model_name,
                    total_bets=len(qualified_bets),
                    wins=wins,
                    losses=losses,
                    pushes=pushes,
                    win_rate=win_rate,
                    units_wagered=units_wagered,
                    units_won=units_won,
                    roi=roi,
                ))
            
            results[model_name] = model_results
        
        return results
    
    def _to_production_ratings(self, ratings: TeamRatings) -> Optional[ProductionTeamRatings]:
        """Convert backtest TeamRatings to production TeamRatings."""
        try:
            return ProductionTeamRatings(
                team_name=ratings.team_name,
                adj_o=ratings.adj_o,
                adj_d=ratings.adj_d,
                tempo=ratings.tempo,
                rank=ratings.rank,
                efg=ratings.efg,
                efgd=ratings.efgd,
                tor=ratings.tor,
                tord=ratings.tord,
                orb=ratings.orb,
                drb=ratings.drb,
                ftr=ratings.ftr,
                ftrd=ratings.ftrd,
                two_pt_pct=ratings.two_pt_pct,
                two_pt_pct_d=ratings.two_pt_pct_d,
                three_pt_pct=ratings.three_pt_pct,
                three_pt_pct_d=ratings.three_pt_pct_d,
                three_pt_rate=ratings.three_pt_rate,
                three_pt_rate_d=ratings.three_pt_rate_d,
                barthag=ratings.barthag,
                wab=ratings.wab,
            )
        except Exception as e:
            return None
    
    def print_results(self, results: Dict[str, List[ROIResults]]):
        """Print ROI results in a formatted table."""
        print("\n" + "=" * 80)
        print("ROI SIMULATION RESULTS")
        print("=" * 80)
        
        for model_name, model_results in results.items():
            print(f"\n{model_name}")
            print("-" * 70)
            print(f"{'Edge':>6} | {'Bets':>5} | {'Wins':>5} | {'Win%':>6} | {'Units':>8} | {'ROI':>7}")
            print("-" * 70)
            
            for r in model_results:
                print(
                    f"{r.edge_threshold:>5.1f}+ | "
                    f"{r.total_bets:>5} | "
                    f"{r.wins:>5} | "
                    f"{r.win_rate*100:>5.1f}% | "
                    f"{r.units_won:>+7.1f} | "
                    f"{r.roi*100:>+6.1f}%"
                )
    
    def save_results(self, results: Dict[str, List[ROIResults]], output_path: Path):
        """Save results to JSON."""
        output = {
            "timestamp": datetime.now().isoformat(),
            "results": {
                model: [r.to_dict() for r in model_results]
                for model, model_results in results.items()
            }
        }
        
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"\nResults saved to: {output_path}")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ROI Simulator")
    parser.add_argument("--season", type=int, default=2024, help="Season to simulate")
    parser.add_argument("--output", type=str, help="Output file path")
    args = parser.parse_args()
    
    simulator = ROISimulator()
    
    print("Loading historical odds...")
    simulator.load_historical_odds()
    
    print(f"\nSimulating season {args.season}...")
    results = simulator.simulate_season(args.season)
    
    simulator.print_results(results)
    
    if args.output:
        simulator.save_results(results, Path(args.output))


if __name__ == "__main__":
    main()
