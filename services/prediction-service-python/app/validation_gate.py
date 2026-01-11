#!/usr/bin/env python3
"""
NCAAM Pre-Prediction Validation Gate

This module provides comprehensive validation before predictions are generated:
1. Team Name Resolution - All teams must resolve to canonical names
2. Alias Coverage - Check that all incoming team names have known aliases
3. Timezone Standardization - All times must be in CST (America/Chicago)
4. Sign Convention - Verify spread conventions are correct:
   - Home favorite = NEGATIVE spread
   - Home underdog = POSITIVE spread
5. Data Freshness - Barttorvik ratings must be current

Usage:
    from validation_gate import PrePredictionGate
    
    gate = PrePredictionGate(db_connection)
    result = gate.validate_game({
        "home_team": "Wisc Green Bay",
        "away_team": "Milwaukee", 
        "spread": -3.5,
        "game_time": "2026-01-09T18:00:00-06:00"
    })
    
    if not result.is_valid:
        print(f"Validation failed: {result.errors}")
"""

import re
import json
import os
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from zoneinfo import ZoneInfo
import logging

# Constants
CST = ZoneInfo("America/Chicago")
UTC = timezone.utc

try:
    from azure.storage.blob import BlobServiceClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

ROOT_DIR = Path(__file__).resolve().parents[3]


def _load_aliases_from_azure() -> Dict[str, str]:
    if not AZURE_AVAILABLE:
        raise ImportError("azure-storage-blob is required to load aliases from Azure.")

    conn_str = os.getenv("AZURE_CANONICAL_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError(
            "AZURE_CANONICAL_CONNECTION_STRING is required to load team aliases from Azure."
        )

    container = os.getenv("AZURE_CANONICAL_CONTAINER", "ncaam-historical-data")
    blob_path = os.getenv(
        "TEAM_ALIASES_BLOB", "backtest_datasets/team_aliases_db.json"
    )

    service = BlobServiceClient.from_connection_string(conn_str)
    container_client = service.get_container_client(container)
    blob_client = container_client.get_blob_client(blob_path)
    payload = blob_client.download_blob().readall()
    return json.loads(payload.decode("utf-8"))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Single validation error."""
    field: str
    message: str
    severity: str = "error"  # error, warning, info
    
    def __str__(self):
        return f"[{self.severity.upper()}] {self.field}: {self.message}"


@dataclass 
class ValidationResult:
    """Result of validation with all errors/warnings."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    resolved_data: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, field: str, message: str):
        self.errors.append(ValidationError(field, message, "error"))
        self.is_valid = False
        
    def add_warning(self, field: str, message: str):
        self.warnings.append(ValidationError(field, message, "warning"))
        
    def summary(self) -> str:
        lines = [f"Valid: {self.is_valid}"]
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  - {e}")
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)


class TeamResolver:
    """Resolve team names using the master alias database."""
    
    def __init__(
        self,
        aliases: Optional[Dict[str, str]] = None,
        aliases_file: Optional[Path] = None,
    ):
        self.aliases: Dict[str, str] = {}
        self.canonical_names: set = set()
        if aliases is not None:
            self._load_aliases_dict(aliases)
        else:
            self._load_aliases(aliases_file)
        
    def _load_aliases(self, aliases_file: Optional[Path]):
        """Load aliases from Azure blob storage."""
        if aliases_file is not None:
            raise RuntimeError(
                "Local alias files are disabled. Use the Azure blob via TEAM_ALIASES_BLOB."
            )
        try:
            self.aliases = _load_aliases_from_azure()
        except Exception as exc:
            raise RuntimeError(f"Aliases load failed: {exc}") from exc
            
        # Build set of canonical names
        self.canonical_names = set(self.aliases.values())
        
        # Add canonical names as self-referencing aliases
        for canonical in self.canonical_names:
            if canonical.lower() not in self.aliases:
                self.aliases[canonical.lower()] = canonical
                
        logger.info(f"Loaded {len(self.aliases)} aliases → {len(self.canonical_names)} canonical teams")
        
    def _load_aliases_dict(self, aliases: Dict[str, str]):
        self.aliases = dict(aliases)
        self.canonical_names = set(self.aliases.values())
        for canonical in self.canonical_names:
            if canonical.lower() not in self.aliases:
                self.aliases[canonical.lower()] = canonical

    def resolve(self, name: str) -> Tuple[Optional[str], str]:
        """
        Resolve a team name to its canonical form.
        
        Returns:
            Tuple of (canonical_name, resolution_method)
            If unresolved, canonical_name is None
        """
        if not name:
            return None, "empty"
            
        # Stage 1: Exact match (case-insensitive)
        normalized = name.lower().strip()
        if normalized in self.aliases:
            return self.aliases[normalized], "exact"
            
        # Stage 2: Normalized match (remove punctuation, extra spaces)
        cleaned = re.sub(r'[^\w\s]', '', normalized)
        cleaned = ' '.join(cleaned.split())
        if cleaned in self.aliases:
            return self.aliases[cleaned], "normalized"
            
        # Stage 3: Aggressive match (remove common suffixes like mascots)
        # Try removing last word if it looks like a mascot
        words = cleaned.split()
        if len(words) > 1:
            without_mascot = ' '.join(words[:-1])
            if without_mascot in self.aliases:
                return self.aliases[without_mascot], "aggressive"
                
        # Stage 4: Check if already canonical
        if name in self.canonical_names:
            return name, "canonical"
            
        return None, "unresolved"


class PrePredictionGate:
    """
    Comprehensive validation gate for predictions.
    
    Validates:
    1. Team names resolve to canonical names
    2. Timezone is CST
    3. Spread sign conventions are correct
    4. Required data is present
    5. Barttorvik ratings are fresh
    """
    
    def __init__(self, db_connection=None, aliases_file: Optional[Path] = None):
        self.team_resolver = TeamResolver(aliases_file=aliases_file)
        self.db = db_connection
        
    def validate_game(self, game: Dict[str, Any]) -> ValidationResult:
        """
        Validate a single game before prediction.
        
        Args:
            game: Dictionary containing:
                - home_team: str
                - away_team: str
                - spread: float (optional, home team spread)
                - total: float (optional)
                - game_time: str or datetime
                - is_neutral: bool (optional)
                
        Returns:
            ValidationResult with is_valid flag and any errors/warnings
        """
        result = ValidationResult(is_valid=True, resolved_data={})
        
        # 1. Validate and resolve team names
        self._validate_teams(game, result)
        
        # 2. Validate timezone
        self._validate_timezone(game, result)
        
        # 3. Validate spread sign convention
        self._validate_spread_convention(game, result)
        
        # 4. Validate required data
        self._validate_required_data(game, result)
        
        return result
        
    def validate_slate(self, games: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate an entire slate of games.
        
        Returns:
            Dictionary with:
                - valid_count: int
                - invalid_count: int
                - results: List of (game, ValidationResult) tuples
                - unresolved_teams: Set of team names that couldn't be resolved
        """
        results = []
        unresolved_teams = set()
        valid_count = 0
        invalid_count = 0
        
        for game in games:
            validation = self.validate_game(game)
            results.append((game, validation))
            
            if validation.is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                
            # Track unresolved teams
            for error in validation.errors:
                if "unresolved" in error.message.lower():
                    # Extract team name from error message
                    unresolved_teams.add(error.message.split("'")[1] if "'" in error.message else error.field)
                    
        return {
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "total": len(games),
            "pass_rate": valid_count / len(games) if games else 0.0,
            "results": results,
            "unresolved_teams": unresolved_teams,
        }
        
    def _validate_teams(self, game: Dict, result: ValidationResult):
        """Validate and resolve team names."""
        # Home team
        home = game.get("home_team", "")
        home_canonical, home_method = self.team_resolver.resolve(home)
        
        if home_canonical:
            result.resolved_data["home_team"] = home_canonical
            result.resolved_data["home_resolution"] = home_method
            if home_method == "aggressive":
                result.add_warning("home_team", f"'{home}' resolved aggressively to '{home_canonical}'")
        else:
            result.add_error("home_team", f"Team name '{home}' could not be resolved")
            
        # Away team
        away = game.get("away_team", "")
        away_canonical, away_method = self.team_resolver.resolve(away)
        
        if away_canonical:
            result.resolved_data["away_team"] = away_canonical
            result.resolved_data["away_resolution"] = away_method
            if away_method == "aggressive":
                result.add_warning("away_team", f"'{away}' resolved aggressively to '{away_canonical}'")
        else:
            result.add_error("away_team", f"Team name '{away}' could not be resolved")
            
        # Check for duplicate teams
        if home_canonical and away_canonical and home_canonical == away_canonical:
            result.add_error("teams", f"Home and away teams resolved to same team: '{home_canonical}'")
            
    def _validate_timezone(self, game: Dict, result: ValidationResult):
        """Validate and convert game time to CST."""
        game_time = game.get("game_time")
        
        if not game_time:
            result.add_warning("game_time", "No game time provided")
            return
            
        try:
            # Parse if string
            if isinstance(game_time, str):
                # Handle ISO format with timezone
                if 'Z' in game_time:
                    game_time = game_time.replace('Z', '+00:00')
                dt = datetime.fromisoformat(game_time)
            elif isinstance(game_time, datetime):
                dt = game_time
            else:
                result.add_error("game_time", f"Invalid game_time type: {type(game_time)}")
                return
                
            # Convert to CST
            if dt.tzinfo is None:
                # Assume UTC if no timezone
                dt = dt.replace(tzinfo=UTC)
                result.add_warning("game_time", "No timezone provided, assumed UTC")
                
            cst_time = dt.astimezone(CST)
            result.resolved_data["game_time_cst"] = cst_time
            result.resolved_data["game_time_utc"] = dt.astimezone(UTC)
            
            # Check if game is in the past
            now_cst = datetime.now(CST)
            if cst_time < now_cst - timedelta(hours=3):
                result.add_warning("game_time", f"Game time appears to be in the past: {cst_time}")
                
        except Exception as e:
            result.add_error("game_time", f"Failed to parse game time: {e}")
            
    def _validate_spread_convention(self, game: Dict, result: ValidationResult):
        """
        Validate spread sign convention.
        
        Convention: 
        - Home favorite = NEGATIVE spread (home expected to win by X points)
        - Home underdog = POSITIVE spread (home expected to lose by X points)
        - Spread is ALWAYS from home team perspective
        """
        spread = game.get("spread")
        
        if spread is None:
            # Spread not provided, that's OK
            return
            
        try:
            spread = float(spread)
        except (ValueError, TypeError):
            result.add_error("spread", f"Invalid spread value: {spread}")
            return
            
        result.resolved_data["spread"] = spread
        
        # Basic sanity checks
        if abs(spread) > 40:
            result.add_warning("spread", f"Spread {spread} is unusually large (>40 points)")
            
        # If we have team ratings, we could validate the spread direction here
        # But that requires database access, so we'll leave it as a warning
        home_ratings = game.get("home_ratings")
        away_ratings = game.get("away_ratings")
        
        if home_ratings and away_ratings:
            # Calculate expected spread direction based on ratings
            home_quality = home_ratings.get("adj_o", 100) - home_ratings.get("adj_d", 100)
            away_quality = away_ratings.get("adj_o", 100) - away_ratings.get("adj_d", 100)
            
            expected_home_favored = home_quality > away_quality
            actual_home_favored = spread < 0
            
            # Only flag if there's a large discrepancy
            if expected_home_favored != actual_home_favored:
                quality_diff = home_quality - away_quality
                if abs(quality_diff) > 5:  # Significant mismatch
                    result.add_warning(
                        "spread",
                        f"Spread sign may be incorrect: ratings suggest {'home' if expected_home_favored else 'away'} "
                        f"should be favored (quality diff: {quality_diff:.1f}), but spread is {spread}"
                    )
                    
    def _validate_required_data(self, game: Dict, result: ValidationResult):
        """Validate that required data is present."""
        # Must have at least one of spread or total
        if game.get("spread") is None and game.get("total") is None:
            result.add_warning("odds", "No spread or total provided - cannot generate pick recommendations")
            
        # Check for juice/vig if available
        if game.get("spread") is not None:
            if game.get("spread_home_juice") is None or game.get("spread_away_juice") is None:
                result.add_warning("juice", "Spread juice not provided - will use default -110")
                
    def validate_barttorvik_freshness(self, 
                                       ratings_date: Optional[datetime] = None,
                                       max_age_days: int = 1) -> ValidationResult:
        """
        Validate that Barttorvik ratings are sufficiently fresh.
        
        Args:
            ratings_date: Date the ratings were pulled (if known)
            max_age_days: Maximum acceptable age in days
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True)
        
        if ratings_date is None:
            result.add_warning("barttorvik", "Ratings date unknown - cannot verify freshness")
            return result
            
        if isinstance(ratings_date, str):
            ratings_date = datetime.fromisoformat(ratings_date)
            
        if ratings_date.tzinfo is None:
            ratings_date = ratings_date.replace(tzinfo=CST)
            
        now = datetime.now(CST)
        age = now - ratings_date
        
        if age.days > max_age_days:
            result.add_error(
                "barttorvik", 
                f"Ratings are {age.days} days old (max allowed: {max_age_days}). "
                f"Ratings date: {ratings_date.strftime('%Y-%m-%d')}"
            )
        elif age.days == max_age_days:
            result.add_warning(
                "barttorvik",
                f"Ratings are {age.days} day(s) old - consider refreshing"
            )
        else:
            result.resolved_data["ratings_age_days"] = age.days
            result.resolved_data["ratings_date"] = ratings_date
            
        return result


def validate_spread_direction(home_spread: float, 
                               home_adj_em: float, 
                               away_adj_em: float,
                               hca: float = 5.8) -> Tuple[bool, str]:
    """
    Validate that spread direction matches expected based on ratings.
    
    Args:
        home_spread: The spread from home team perspective (negative = home favored)
        home_adj_em: Home team's adjusted efficiency margin
        away_adj_em: Away team's adjusted efficiency margin
        hca: Home court advantage in points
        
    Returns:
        Tuple of (is_valid, message)
    """
    # Expected spread: (away_adj_em - home_adj_em) - hca
    # If home is better + HCA, expected spread is negative
    expected_spread = away_adj_em - home_adj_em - hca
    
    # Check if signs match
    expected_home_favored = expected_spread < 0
    actual_home_favored = home_spread < 0
    
    if expected_home_favored == actual_home_favored:
        return True, f"Spread direction correct (expected ~{expected_spread:.1f}, actual {home_spread})"
    else:
        # Check magnitude of mismatch
        diff = abs(expected_spread - home_spread)
        if diff < 5:
            return True, f"Minor mismatch within tolerance (expected ~{expected_spread:.1f}, actual {home_spread})"
        else:
            return False, (
                f"SIGN CONVENTION ERROR: Expected spread ~{expected_spread:.1f} "
                f"but got {home_spread}. Spread may need to be flipped."
            )


# CLI for testing
if __name__ == "__main__":
    import sys
    
    # Initialize gate
    gate = PrePredictionGate()
    
    print("=" * 60)
    print("PRE-PREDICTION VALIDATION GATE")
    print(f"Loaded {len(gate.team_resolver.aliases)} aliases")
    print("=" * 60)
    
    # Test with Jan 9, 2026 slate
    test_games = [
        {
            "home_team": "Wisc Green Bay",
            "away_team": "Wisc Milwaukee",
            "spread": -3.5,
            "game_time": "2026-01-09T18:00:00-06:00",
        },
        {
            "home_team": "Ohio State Buckeyes",  # Will need aggressive resolution
            "away_team": "Nebraska Cornhuskers",
            "spread": -8.5,
            "game_time": "2026-01-09T17:30:00Z",  # UTC, should convert to CST
        },
        {
            "home_team": "Some Fake Team",  # Should fail
            "away_team": "Duke",
            "spread": 5.0,
            "game_time": "2026-01-09T19:00:00-06:00",
        },
    ]
    
    print("\nValidating test games...")
    slate_result = gate.validate_slate(test_games)
    
    print(f"\nResults: {slate_result['valid_count']}/{slate_result['total']} valid")
    print(f"Pass rate: {slate_result['pass_rate']:.1%}")
    
    if slate_result['unresolved_teams']:
        print(f"\nUnresolved teams: {slate_result['unresolved_teams']}")
        
    print("\nDetailed results:")
    for i, (game, validation) in enumerate(slate_result['results']):
        print(f"\n--- Game {i+1}: {game.get('away_team')} @ {game.get('home_team')} ---")
        print(validation.summary())
        if validation.resolved_data:
            print(f"Resolved data: {validation.resolved_data}")
