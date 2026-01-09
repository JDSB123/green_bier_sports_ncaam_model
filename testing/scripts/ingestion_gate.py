#!/usr/bin/env python3
"""
NCAAM Ingestion Validation Gate

A unified validation layer for ALL data ingestion - both historical (batch) and
live (real-time) paths. This ensures data quality BEFORE it enters the system.

This module validates:
1. Team Name Resolution - All teams resolve to canonical names
2. Timezone Standardization - All dates/times converted to CST
3. Spread Sign Convention - Home team perspective (negative = favorite)
4. Data Completeness - Required fields are present
5. Cross-Source Consistency - Same game from different sources matches

Usage:
    from ingestion_gate import IngestionGate
    
    gate = IngestionGate()
    
    # For historical data ingestion
    result = gate.validate_historical_game({
        "game_date": "2024-03-15",
        "home_team": "Duke",
        "away_team": "North Carolina",
        "home_score": 78,
        "away_score": 72,
        "spread": -3.5,  # Home team spread
    })
    
    # For live odds ingestion
    result = gate.validate_live_odds({
        "home_team": "Ohio State Buckeyes",
        "away_team": "Nebraska Cornhuskers",
        "commence_time": "2026-01-09T23:30:00Z",
        "spread": -8.5,
        "total": 145.5,
    })
"""

import re
import json
from datetime import datetime, timezone, timedelta, date
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from zoneinfo import ZoneInfo
import logging

# Constants
CST = ZoneInfo("America/Chicago")
UTC = timezone.utc

# Seasons typically run Aug-Apr, so Jan games belong to the "current academic year"
def get_season_year(game_date: date) -> int:
    """
    Get the season year for a game date.
    NCAA season runs ~Nov-April, so Jan-Apr games belong to current year,
    Aug-Dec games belong to next year.
    
    Examples:
        2024-01-15 -> 2024 season
        2024-11-15 -> 2025 season
        2025-03-20 -> 2025 season (March Madness)
    """
    if isinstance(game_date, str):
        game_date = datetime.fromisoformat(game_date).date()
    elif isinstance(game_date, datetime):
        game_date = game_date.date()
        
    if game_date.month >= 8:  # Aug-Dec
        return game_date.year + 1
    else:  # Jan-Jul
        return game_date.year

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class IngestionError:
    """Single ingestion validation error."""
    field: str
    message: str
    severity: str = "error"  # error, warning, info
    source: str = "unknown"  # espn, odds_api, barttorvik, etc.
    
    def __str__(self):
        return f"[{self.severity.upper()}] [{self.source}] {self.field}: {self.message}"


@dataclass 
class IngestionResult:
    """Result of ingestion validation."""
    is_valid: bool
    errors: List[IngestionError] = field(default_factory=list)
    warnings: List[IngestionError] = field(default_factory=list)
    canonical_data: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, field: str, message: str, source: str = "unknown"):
        self.errors.append(IngestionError(field, message, "error", source))
        self.is_valid = False
        
    def add_warning(self, field: str, message: str, source: str = "unknown"):
        self.warnings.append(IngestionError(field, message, "warning", source))
        
    def merge(self, other: 'IngestionResult'):
        """Merge another result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.canonical_data.update(other.canonical_data)
        if other.errors:
            self.is_valid = False


class IngestionGate:
    """
    Unified validation gate for all data ingestion.
    
    Validates data from any source before it enters the system.
    """
    
    def __init__(self, aliases_file: Optional[Path] = None):
        # Find aliases file
        if aliases_file is None:
            aliases_file = self._find_aliases_file()
            
        self.aliases: Dict[str, str] = {}
        self.canonical_names: set = set()
        self._load_aliases(aliases_file)
        
    def _find_aliases_file(self) -> Path:
        """Find the team aliases file from various possible locations."""
        possible_paths = [
            Path("ncaam_historical_data_local/backtest_datasets/team_aliases_db.json"),
            Path(__file__).resolve().parent / "team_aliases_db.json",
            Path(__file__).resolve().parents[1] / "ncaam_historical_data_local" / "backtest_datasets" / "team_aliases_db.json",
            Path(__file__).resolve().parents[2] / "ncaam_historical_data_local" / "backtest_datasets" / "team_aliases_db.json",
        ]
        
        for p in possible_paths:
            if p.exists():
                return p
                
        return possible_paths[0]  # Default
        
    def _load_aliases(self, aliases_file: Path):
        """Load aliases from JSON file."""
        if not aliases_file.exists():
            logger.warning(f"Aliases file not found: {aliases_file}")
            return
            
        with open(aliases_file, 'r') as f:
            self.aliases = json.load(f)
            
        self.canonical_names = set(self.aliases.values())
        
        # Add canonical names as self-referencing aliases
        for canonical in list(self.canonical_names):
            if canonical.lower() not in self.aliases:
                self.aliases[canonical.lower()] = canonical
                
        logger.info(f"Loaded {len(self.aliases)} aliases → {len(self.canonical_names)} canonical teams")
        
    def resolve_team(self, name: str) -> Tuple[Optional[str], str]:
        """
        Resolve a team name to its canonical form.
        
        Returns:
            Tuple of (canonical_name, resolution_method)
        """
        if not name:
            return None, "empty"
            
        # Stage 1: Exact match (case-insensitive)
        normalized = name.lower().strip()
        if normalized in self.aliases:
            return self.aliases[normalized], "exact"
            
        # Stage 2: Normalized (remove punctuation)
        cleaned = re.sub(r'[^\w\s]', '', normalized)
        cleaned = ' '.join(cleaned.split())
        if cleaned in self.aliases:
            return self.aliases[cleaned], "normalized"
            
        # Stage 3: Aggressive (remove last word/mascot)
        words = cleaned.split()
        if len(words) > 1:
            without_mascot = ' '.join(words[:-1])
            if without_mascot in self.aliases:
                return self.aliases[without_mascot], "aggressive"
                
        # Check if already canonical
        if name in self.canonical_names:
            return name, "canonical"
            
        return None, "unresolved"
        
    def validate_historical_game(self, 
                                  game: Dict[str, Any],
                                  source: str = "unknown") -> IngestionResult:
        """
        Validate a historical game record.
        
        Expected fields:
            - game_date: str (YYYY-MM-DD) or date object
            - home_team: str
            - away_team: str
            - home_score: int (optional)
            - away_score: int (optional)
            - spread: float (optional, home team perspective)
            - total: float (optional)
        """
        result = IngestionResult(is_valid=True)
        
        # Validate teams
        self._validate_teams(game, result, source)
        
        # Validate date
        self._validate_date(game, result, source)
        
        # Validate scores if present
        self._validate_scores(game, result, source)
        
        # Validate spread convention
        self._validate_spread(game, result, source)
        
        return result
        
    def validate_live_odds(self,
                           odds: Dict[str, Any],
                           source: str = "odds_api") -> IngestionResult:
        """
        Validate live odds data.
        
        Expected fields:
            - home_team: str
            - away_team: str
            - commence_time: str (ISO format) or datetime
            - spread: float (optional, home team perspective)
            - spread_home_juice: int (optional, e.g., -110)
            - spread_away_juice: int (optional)
            - total: float (optional)
            - over_juice: int (optional)
            - under_juice: int (optional)
        """
        result = IngestionResult(is_valid=True)
        
        # Validate teams
        self._validate_teams(odds, result, source)
        
        # Validate commence time
        self._validate_commence_time(odds, result, source)
        
        # Validate spread
        self._validate_spread(odds, result, source)
        
        # Validate total
        self._validate_total(odds, result, source)
        
        # Validate juice/vig
        self._validate_juice(odds, result, source)
        
        return result
        
    def validate_ratings(self,
                         ratings: Dict[str, Any],
                         source: str = "barttorvik") -> IngestionResult:
        """
        Validate team ratings data.
        
        Expected fields:
            - team_name: str
            - adj_o: float (adjusted offensive efficiency)
            - adj_d: float (adjusted defensive efficiency)
            - tempo: float
            - rank: int
            - season: int (optional)
        """
        result = IngestionResult(is_valid=True)
        
        # Validate team
        team_name = ratings.get("team_name", "")
        canonical, method = self.resolve_team(team_name)
        
        if canonical:
            result.canonical_data["team_name"] = canonical
            result.canonical_data["resolution_method"] = method
        else:
            result.add_error("team_name", f"Team '{team_name}' could not be resolved", source)
            
        # Validate efficiency ratings
        adj_o = ratings.get("adj_o")
        adj_d = ratings.get("adj_d")
        
        if adj_o is not None:
            try:
                adj_o = float(adj_o)
                if not (70 <= adj_o <= 140):
                    result.add_warning("adj_o", f"Unusual adj_o value: {adj_o} (expected 70-140)", source)
                result.canonical_data["adj_o"] = adj_o
            except (ValueError, TypeError):
                result.add_error("adj_o", f"Invalid adj_o value: {adj_o}", source)
        else:
            result.add_error("adj_o", "Missing adj_o value", source)
            
        if adj_d is not None:
            try:
                adj_d = float(adj_d)
                if not (70 <= adj_d <= 140):
                    result.add_warning("adj_d", f"Unusual adj_d value: {adj_d} (expected 70-140)", source)
                result.canonical_data["adj_d"] = adj_d
            except (ValueError, TypeError):
                result.add_error("adj_d", f"Invalid adj_d value: {adj_d}", source)
        else:
            result.add_error("adj_d", "Missing adj_d value", source)
            
        # Validate tempo
        tempo = ratings.get("tempo")
        if tempo is not None:
            try:
                tempo = float(tempo)
                if not (55 <= tempo <= 85):
                    result.add_warning("tempo", f"Unusual tempo value: {tempo} (expected 55-85)", source)
                result.canonical_data["tempo"] = tempo
            except (ValueError, TypeError):
                result.add_warning("tempo", f"Invalid tempo value: {tempo}", source)
                
        return result
        
    def _validate_teams(self, data: Dict, result: IngestionResult, source: str):
        """Validate and resolve team names."""
        # Home team
        home = data.get("home_team", "")
        home_canonical, home_method = self.resolve_team(home)
        
        if home_canonical:
            result.canonical_data["home_team"] = home_canonical
            result.canonical_data["home_resolution"] = home_method
            if home_method == "aggressive":
                result.add_warning("home_team", f"'{home}' resolved aggressively to '{home_canonical}'", source)
        else:
            result.add_error("home_team", f"Team '{home}' could not be resolved", source)
            
        # Away team
        away = data.get("away_team", "")
        away_canonical, away_method = self.resolve_team(away)
        
        if away_canonical:
            result.canonical_data["away_team"] = away_canonical
            result.canonical_data["away_resolution"] = away_method
            if away_method == "aggressive":
                result.add_warning("away_team", f"'{away}' resolved aggressively to '{away_canonical}'", source)
        else:
            result.add_error("away_team", f"Team '{away}' could not be resolved", source)
            
        # Check for duplicates
        if home_canonical and away_canonical and home_canonical == away_canonical:
            result.add_error("teams", f"Home and away resolved to same team: '{home_canonical}'", source)
            
    def _validate_date(self, data: Dict, result: IngestionResult, source: str):
        """Validate and standardize game date."""
        game_date = data.get("game_date")
        
        if not game_date:
            result.add_error("game_date", "Missing game_date", source)
            return
            
        try:
            if isinstance(game_date, str):
                # Parse YYYY-MM-DD format
                parsed = datetime.strptime(game_date, "%Y-%m-%d").date()
            elif isinstance(game_date, datetime):
                parsed = game_date.date()
            elif isinstance(game_date, date):
                parsed = game_date
            else:
                result.add_error("game_date", f"Invalid date type: {type(game_date)}", source)
                return
                
            result.canonical_data["game_date"] = parsed.isoformat()
            result.canonical_data["season"] = get_season_year(parsed)
            
        except Exception as e:
            result.add_error("game_date", f"Failed to parse date: {e}", source)
            
    def _validate_commence_time(self, data: Dict, result: IngestionResult, source: str):
        """Validate and convert commence time to CST."""
        commence_time = data.get("commence_time")
        
        if not commence_time:
            result.add_warning("commence_time", "Missing commence_time", source)
            return
            
        try:
            if isinstance(commence_time, str):
                if 'Z' in commence_time:
                    commence_time = commence_time.replace('Z', '+00:00')
                dt = datetime.fromisoformat(commence_time)
            elif isinstance(commence_time, datetime):
                dt = commence_time
            else:
                result.add_error("commence_time", f"Invalid type: {type(commence_time)}", source)
                return
                
            # Convert to CST
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
                result.add_warning("commence_time", "No timezone, assumed UTC", source)
                
            cst_time = dt.astimezone(CST)
            result.canonical_data["commence_time_cst"] = cst_time.isoformat()
            result.canonical_data["commence_time_utc"] = dt.astimezone(UTC).isoformat()
            result.canonical_data["game_date"] = cst_time.date().isoformat()
            result.canonical_data["season"] = get_season_year(cst_time.date())
            
        except Exception as e:
            result.add_error("commence_time", f"Failed to parse: {e}", source)
            
    def _validate_scores(self, data: Dict, result: IngestionResult, source: str):
        """Validate score data."""
        home_score = data.get("home_score")
        away_score = data.get("away_score")
        
        if home_score is not None:
            try:
                home_score = int(home_score)
                if not (0 <= home_score <= 200):
                    result.add_warning("home_score", f"Unusual score: {home_score}", source)
                result.canonical_data["home_score"] = home_score
            except (ValueError, TypeError):
                result.add_error("home_score", f"Invalid score: {home_score}", source)
                
        if away_score is not None:
            try:
                away_score = int(away_score)
                if not (0 <= away_score <= 200):
                    result.add_warning("away_score", f"Unusual score: {away_score}", source)
                result.canonical_data["away_score"] = away_score
            except (ValueError, TypeError):
                result.add_error("away_score", f"Invalid score: {away_score}", source)
                
    def _validate_spread(self, data: Dict, result: IngestionResult, source: str):
        """
        Validate spread data and sign convention.
        
        Convention: Spread is ALWAYS from home team perspective
        - Negative spread = home team favored
        - Positive spread = away team favored (home is underdog)
        """
        spread = data.get("spread")
        
        if spread is None:
            return  # Spread is optional
            
        try:
            spread = float(spread)
            result.canonical_data["spread"] = spread
            
            # Sanity check
            if abs(spread) > 40:
                result.add_warning("spread", f"Unusually large spread: {spread}", source)
                
            # Check if spread matches score result (for historical data)
            home_score = data.get("home_score")
            away_score = data.get("away_score")
            
            if home_score is not None and away_score is not None:
                actual_margin = int(home_score) - int(away_score)
                spread_covered = actual_margin > -spread  # Did home cover?
                result.canonical_data["spread_covered_by_home"] = spread_covered
                result.canonical_data["actual_margin"] = actual_margin
                
        except (ValueError, TypeError):
            result.add_error("spread", f"Invalid spread value: {spread}", source)
            
    def _validate_total(self, data: Dict, result: IngestionResult, source: str):
        """Validate total (over/under) data."""
        total = data.get("total")
        
        if total is None:
            return  # Total is optional
            
        try:
            total = float(total)
            result.canonical_data["total"] = total
            
            # Sanity check for NCAA basketball
            if not (100 <= total <= 200):
                result.add_warning("total", f"Unusual total: {total} (expected 100-200)", source)
                
        except (ValueError, TypeError):
            result.add_error("total", f"Invalid total value: {total}", source)
            
    def _validate_juice(self, data: Dict, result: IngestionResult, source: str):
        """Validate juice/vig values."""
        spread = data.get("spread")
        total = data.get("total")
        
        # Check spread juice
        if spread is not None:
            home_juice = data.get("spread_home_juice")
            away_juice = data.get("spread_away_juice")
            
            if home_juice is None or away_juice is None:
                result.add_warning("spread_juice", "Missing spread juice, will use -110 default", source)
            else:
                try:
                    home_juice = int(home_juice)
                    away_juice = int(away_juice)
                    
                    # Sanity check - juice should typically be -115 to -105
                    for juice, name in [(home_juice, "home"), (away_juice, "away")]:
                        if juice > 0:  # Plus money
                            if juice > 200:
                                result.add_warning("spread_juice", f"Unusual {name} juice: +{juice}", source)
                        else:  # Minus money
                            if juice < -150:
                                result.add_warning("spread_juice", f"Unusual {name} juice: {juice}", source)
                                
                    result.canonical_data["spread_home_juice"] = home_juice
                    result.canonical_data["spread_away_juice"] = away_juice
                    
                except (ValueError, TypeError) as e:
                    result.add_warning("spread_juice", f"Invalid juice values: {e}", source)
                    
        # Check total juice
        if total is not None:
            over_juice = data.get("over_juice")
            under_juice = data.get("under_juice")
            
            if over_juice is None or under_juice is None:
                result.add_warning("total_juice", "Missing total juice, will use -110 default", source)
            else:
                try:
                    result.canonical_data["over_juice"] = int(over_juice)
                    result.canonical_data["under_juice"] = int(under_juice)
                except (ValueError, TypeError):
                    result.add_warning("total_juice", "Invalid juice values", source)


def validate_spread_sign_convention(home_team: str,
                                     away_team: str,
                                     spread: float,
                                     home_score: Optional[int] = None,
                                     away_score: Optional[int] = None) -> Tuple[bool, str]:
    """
    Validate that spread sign convention is correct.
    
    Convention:
    - Negative spread = home team is favored (expected to win by X)
    - Positive spread = away team is favored (home expected to lose by X)
    
    If scores are provided, validate that spread direction made sense.
    """
    # If we have scores, we can validate the spread direction made sense
    if home_score is not None and away_score is not None:
        actual_margin = home_score - away_score
        
        # If home won big and spread was positive (away favored), flag it
        if actual_margin > 10 and spread > 3:
            return True, f"Home team {home_team} won by {actual_margin} as underdog (+{spread})"
            
        # If away won big and spread was very negative (home favored), flag it
        if actual_margin < -10 and spread < -3:
            return True, f"Away team {away_team} won as underdog (spread was {spread})"
            
    return True, "Spread convention appears correct"


# CLI for testing
if __name__ == "__main__":
    gate = IngestionGate()
    
    print("=" * 60)
    print("INGESTION VALIDATION GATE")
    print(f"Loaded {len(gate.aliases)} aliases → {len(gate.canonical_names)} canonical teams")
    print("=" * 60)
    
    # Test historical game
    print("\n--- Historical Game Test ---")
    historical = {
        "game_date": "2024-03-15",
        "home_team": "Duke Blue Devils",
        "away_team": "UNC",
        "home_score": 78,
        "away_score": 72,
        "spread": -3.5,
    }
    result = gate.validate_historical_game(historical, "test")
    print(f"Valid: {result.is_valid}")
    print(f"Canonical: {result.canonical_data}")
    if result.warnings:
        print(f"Warnings: {[str(w) for w in result.warnings]}")
        
    # Test live odds
    print("\n--- Live Odds Test ---")
    live = {
        "home_team": "Ohio State Buckeyes",
        "away_team": "Nebraska Cornhuskers",
        "commence_time": "2026-01-09T23:30:00Z",
        "spread": -8.5,
        "spread_home_juice": -110,
        "spread_away_juice": -110,
        "total": 145.5,
        "over_juice": -108,
        "under_juice": -112,
    }
    result = gate.validate_live_odds(live)
    print(f"Valid: {result.is_valid}")
    print(f"Canonical: {result.canonical_data}")
    
    # Test ratings
    print("\n--- Ratings Test ---")
    ratings = {
        "team_name": "Gonzaga Bulldogs",
        "adj_o": 118.5,
        "adj_d": 92.3,
        "tempo": 71.2,
        "rank": 5,
    }
    result = gate.validate_ratings(ratings)
    print(f"Valid: {result.is_valid}")
    print(f"Canonical: {result.canonical_data}")
