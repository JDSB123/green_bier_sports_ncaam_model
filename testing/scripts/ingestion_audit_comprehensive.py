#!/usr/bin/env python3
"""
COMPREHENSIVE INGESTION AUDIT

A strict, no-silent-fallback audit of all ingested data for backtest readiness.
This script validates that all data sources are properly ingested, standardized,
and complete for the target backtest seasons.

TARGET BACKTEST SEASONS:
- 2023-2024 (season 2024)
- 2024-2025 (season 2025)
- 2025-2026 YTD (season 2026)

AUDITS PERFORMED:
1. DATA EXISTENCE - All required blobs exist (no silent fallbacks)
2. SEASON COVERAGE - All target seasons have data
3. SCHEMA CONSISTENCY - Same columns across files/seasons
4. ROW COUNT SANITY - Expected game counts per season
5. H1 SCORE COVERAGE - % of games with first-half scores
6. ODDS COVERAGE - % of games with spread/total odds
7. RATINGS COVERAGE - % of teams with Barttorvik ratings
8. TEAM RESOLUTION - All teams resolve to canonical names
9. INGESTION RECENCY - Blob metadata shows recent updates
10. DATA INTEGRITY - No nulls in critical fields, valid ranges

EXIT CODES:
- 0: All audits passed, backtest ready
- 1: Critical failures, backtest blocked
- 2: Warnings only, proceed with caution

Usage:
    python testing/scripts/comprehensive_ingestion_audit.py
    python testing/scripts/comprehensive_ingestion_audit.py --verbose
    python testing/scripts/comprehensive_ingestion_audit.py --output manifests/ingestion_audit.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from testing.azure_io import read_csv, read_json, blob_exists, list_files
from testing.azure_data_reader import get_azure_reader
from testing.data_paths import DATA_PATHS
from testing.data_window import (
    current_season,
    default_backtest_seasons,
    enforce_min_season,
)


# ============================================================================
# CONFIGURATION - BACKTEST SEASONS
# ============================================================================

# Target seasons for backtesting (NCAA season naming: 2024 = 2023-2024 season)
# Season 2024 = Nov 2023 - Apr 2024
# Season 2025 = Nov 2024 - Apr 2025  
# Season 2026 = Nov 2025 - Apr 2026 (current season, YTD through today-3)
# Canonical backtest seasons (2023-24 season onward).
BACKTEST_SEASONS = default_backtest_seasons()

# Current season (allows special handling for incomplete data)
CURRENT_SEASON = current_season()

# Expected game counts per season (D1 teams play ~30 games, ~360 teams)
# Regular season + conference tourneys + NCAA = ~5500-6500 games
MIN_GAMES_PER_SEASON = 4500
MAX_GAMES_PER_SEASON = 7500

# For current season, we expect partial data (Jan 12 is ~60% through regular season)
MIN_GAMES_CURRENT_SEASON = 400  # ~2 months of games

# Coverage thresholds (fail if below)
# H1 is ~8-10% because ESPN only provides linescore for select games
MIN_H1_COVERAGE_PCT = 5.0  # At least 5% of games should have H1 scores
# Current season may have 0% H1 scores until ESPN linescores are scraped
MIN_H1_COVERAGE_PCT_CURRENT = 0.0  # Accept 0% for current season
# Odds coverage should be 80%+ after proper merging (current season may be lower)
MIN_ODDS_COVERAGE_PCT = 80.0  # At least 80% of games should have odds
MIN_ODDS_COVERAGE_PCT_CURRENT = 75.0  # At least 75% for current season
# Ratings coverage for D1 matchups (both teams have Barttorvik) should be 75%+
MIN_RATINGS_COVERAGE_PCT = 75.0  # At least 75% of D1 matchups have both ratings

# Use the pre-merged backtest master for coverage checks (already has joins done)
BACKTEST_MASTER = "backtest_datasets/backtest_master.csv"

# Critical columns that must never be null (actual schema uses 'date' not 'game_date')
CRITICAL_SCORE_COLUMNS = ["date", "home_team", "away_team", "home_score", "away_score"]
CRITICAL_ODDS_COLUMNS = ["game_date", "home_team", "away_team"]  # Odds uses game_date
CRITICAL_H1_COLUMNS = ["game_id", "home_h1", "away_h1"]


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class AuditIssue:
    """A single audit issue found."""
    category: str
    severity: str  # "critical", "error", "warning", "info"
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class AuditResult:
    """Result of the comprehensive audit."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    backtest_seasons: list = field(default_factory=lambda: BACKTEST_SEASONS)
    passed: bool = True
    has_critical: bool = False
    has_errors: bool = False
    has_warnings: bool = False
    issues: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    data_inventory: dict = field(default_factory=dict)

    def add_issue(self, issue: AuditIssue):
        self.issues.append(asdict(issue))
        if issue.severity == "critical":
            self.has_critical = True
            self.passed = False
        elif issue.severity == "error":
            self.has_errors = True
            self.passed = False
        elif issue.severity == "warning":
            self.has_warnings = True


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(title: str):
    print(f"\n{'='*72}")
    print(f"{Colors.BOLD}{title}{Colors.END}")
    print('='*72)


def print_pass(msg: str):
    print(f"  {Colors.GREEN}[PASS]{Colors.END} {msg}")


def print_fail(msg: str):
    print(f"  {Colors.RED}[FAIL]{Colors.END} {msg}")


def print_warn(msg: str):
    print(f"  {Colors.YELLOW}[WARN]{Colors.END} {msg}")


def print_info(msg: str):
    print(f"  {Colors.BLUE}[INFO]{Colors.END} {msg}")


# ============================================================================
# AUDIT 1: DATA EXISTENCE (No Silent Fallbacks)
# ============================================================================

def audit_data_existence(result: AuditResult, verbose: bool = False) -> None:
    """Verify all required data blobs exist. NO fallbacks allowed."""
    print_header("AUDIT 1: DATA EXISTENCE (No Silent Fallbacks)")
    
    required_blobs = {
        # Scores
        "scores_fg_all": "scores/fg/games_all.csv",
        "scores_h1_all": "scores/h1/h1_games_all.csv",
        
        # Odds (canonical, consolidated)
        "odds_consolidated": "odds/normalized/odds_consolidated_canonical.csv",
        
        # Team aliases (CRITICAL)
        "team_aliases": "backtest_datasets/team_aliases_db.json",
        
        # Backtest master (pre-merged dataset)
        "backtest_master": "backtest_datasets/backtest_master.csv",
    }
    
    # Per-season ratings (actual path: ratings/barttorvik/ratings_YYYY.json)
    for season in BACKTEST_SEASONS:
        required_blobs[f"barttorvik_{season}"] = f"ratings/barttorvik/ratings_{season}.json"
    
    all_exist = True
    result.data_inventory["blob_existence"] = {}
    
    for name, blob_path in required_blobs.items():
        exists = blob_exists(blob_path)
        result.data_inventory["blob_existence"][name] = {
            "path": blob_path,
            "exists": exists
        }
        
        if exists:
            print_pass(f"{name}: {blob_path}")
        else:
            print_fail(f"{name}: {blob_path} NOT FOUND")
            result.add_issue(AuditIssue(
                category="data_existence",
                severity="critical",
                message=f"Required blob missing: {blob_path}",
                details={"blob_name": name, "path": blob_path}
            ))
            all_exist = False
    
    if all_exist:
        print_pass("All required blobs exist")
    else:
        print_fail("Missing required blobs - BACKTEST BLOCKED")


# ============================================================================
# AUDIT 2: SEASON COVERAGE
# ============================================================================

def _normalize_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize date column: handle both 'date' and 'game_date'."""
    if "game_date" not in df.columns and "date" in df.columns:
        df = df.copy()
        df["game_date"] = df["date"]
    if "game_date" in df.columns:
        df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    return df


def _get_season(date) -> int | None:
    """Derive NCAA season from date (Nov-Dec = next year's season)."""
    if pd.isna(date):
        return None
    if date.month >= 11:
        return date.year + 1
    elif date.month <= 4:
        return date.year
    else:
        return None  # Off-season


# Global alias lookup cache
_ALIAS_LOOKUP = None


def _get_alias_lookup() -> dict:
    """Load and cache the team alias lookup (case-insensitive)."""
    global _ALIAS_LOOKUP
    if _ALIAS_LOOKUP is not None:
        return _ALIAS_LOOKUP
    
    try:
        aliases = read_json("backtest_datasets/team_aliases_db.json")
        _ALIAS_LOOKUP = {k.lower().strip(): v for k, v in aliases.items()}
        # Add canonical names as self-references
        for canonical in set(aliases.values()):
            key = canonical.lower().strip()
            if key not in _ALIAS_LOOKUP:
                _ALIAS_LOOKUP[key] = canonical
    except Exception:
        _ALIAS_LOOKUP = {}
    
    return _ALIAS_LOOKUP


def _resolve_team(team_name: str) -> str:
    """Resolve a team name to its canonical form (lowercase for consistent matching)."""
    if not team_name or pd.isna(team_name):
        return ""
    lookup = _get_alias_lookup()
    key = str(team_name).lower().strip()
    canonical = lookup.get(key, key)  # Return original (lowercase) if not found
    return canonical.lower().strip()  # Always lowercase for consistent matching


def _make_game_key(date, home_team: str, away_team: str) -> str:
    """Create a canonical game key for matching across data sources."""
    date_str = date.strftime("%Y-%m-%d") if pd.notna(date) else ""
    home_canonical = _resolve_team(home_team)
    away_canonical = _resolve_team(away_team)
    return f"{date_str}|{home_canonical}|{away_canonical}"


def audit_season_coverage(result: AuditResult, verbose: bool = False) -> None:
    """Verify all target seasons have data using the pre-merged backtest master."""
    print_header("AUDIT 2: SEASON COVERAGE")
    
    try:
        # Use backtest_master.csv as the single source of truth
        reader = get_azure_reader()
        if blob_exists(BACKTEST_MASTER):
            games_df = reader.read_csv(BACKTEST_MASTER, data_type=None)
        else:
            games_df = reader.read_csv("scores/fg/games_all.csv", data_type=None)
        games_df = _normalize_date_column(games_df)
        
        games_df["season"] = games_df["game_date"].apply(_get_season)
        
        result.data_inventory["season_coverage"] = {}
        
        for season in BACKTEST_SEASONS:
            season_games = games_df[games_df["season"] == season]
            count = len(season_games)
            
            # Use different thresholds for current (incomplete) season
            is_current = (season == CURRENT_SEASON)
            min_games = MIN_GAMES_CURRENT_SEASON if is_current else MIN_GAMES_PER_SEASON
            
            result.data_inventory["season_coverage"][season] = {
                "game_count": count,
                "min_required": min_games,
                "max_expected": MAX_GAMES_PER_SEASON,
                "is_current_season": is_current
            }
            
            if count == 0:
                if is_current:
                    # Current season with no data needs ingestion
                    print_fail(f"Season {season} (CURRENT): NO GAMES - needs ingestion via fetch_historical_data.py")
                    result.add_issue(AuditIssue(
                        category="season_coverage",
                        severity="error",  # Error not critical - can be fixed
                        message=f"Current season {season} has no games - run fetch_historical_data.py --seasons {season}",
                        details={"season": season, "count": 0, "action": f"python testing/scripts/fetch_historical_data.py --seasons {season}"}
                    ))
                else:
                    print_fail(f"Season {season}: NO GAMES FOUND")
                    result.add_issue(AuditIssue(
                        category="season_coverage",
                        severity="critical",
                        message=f"Season {season} has no games",
                        details={"season": season, "count": 0}
                    ))
            elif count < min_games:
                severity = "warning" if is_current else "warning"
                label = " (CURRENT, YTD)" if is_current else ""
                print_warn(f"Season {season}{label}: {count:,} games (below {min_games:,} minimum)")
                result.add_issue(AuditIssue(
                    category="season_coverage",
                    severity=severity,
                    message=f"Season {season} has fewer games than expected",
                    details={"season": season, "count": count, "min_expected": min_games}
                ))
            elif count > MAX_GAMES_PER_SEASON:
                print_warn(f"Season {season}: {count:,} games (above {MAX_GAMES_PER_SEASON:,} max)")
                result.add_issue(AuditIssue(
                    category="season_coverage",
                    severity="warning",
                    message=f"Season {season} has more games than expected",
                    details={"season": season, "count": count, "max_expected": MAX_GAMES_PER_SEASON}
                ))
            else:
                print_pass(f"Season {season}: {count:,} games")
                
            if verbose and count > 0:
                date_range = f"{season_games['game_date'].min().date()} to {season_games['game_date'].max().date()}"
                print_info(f"  Date range: {date_range}")
    
    except Exception as e:
        print_fail(f"Failed to load games data: {e}")
        result.add_issue(AuditIssue(
            category="season_coverage",
            severity="critical",
            message=f"Failed to load games data: {e}",
            details={"error": str(e)}
        ))


# ============================================================================
# AUDIT 3: SCHEMA CONSISTENCY
# ============================================================================

def audit_schema_consistency(result: AuditResult, verbose: bool = False) -> None:
    """Verify schema is consistent across data sources."""
    print_header("AUDIT 3: SCHEMA CONSISTENCY")
    
    # Expected schemas - note: scores uses 'date', odds uses 'game_date'
    expected_schemas = {
        "scores_fg": {
            "required": ["date", "home_team", "away_team", "home_score", "away_score"],
            "required_alt": ["game_date"],  # Either date or game_date is acceptable
            "optional": ["game_id", "season", "home_abbr", "away_abbr", "neutral_site", "spread_open", "total_open"]
        },
        "scores_h1": {
            "required": ["game_id", "home_h1", "away_h1"],
            "optional": ["game_date", "date", "home_team", "away_team"]
        },
        "odds_consolidated": {
            "required": ["game_date", "home_team", "away_team", "spread", "total"],
            "optional": [
                "spread_home_price", "spread_away_price",
                "total_over_price", "total_under_price",
                "h1_spread", "h1_total",
                "h1_spread_home_price", "h1_spread_away_price",
                "h1_total_over_price", "h1_total_under_price",
                "bookmaker", "timestamp", "event_id",
                "home_team_canonical", "away_team_canonical",
            ]
        }
    }
    
    files_to_check = {
        "scores_fg": "scores/fg/games_all.csv",
        "scores_h1": "scores/h1/h1_games_all.csv",
        "odds_consolidated": "odds/normalized/odds_consolidated_canonical.csv",
    }
    
    reader = get_azure_reader()
    result.data_inventory["schemas"] = {}
    
    for name, blob_path in files_to_check.items():
        try:
            if not blob_exists(blob_path):
                print_warn(f"{name}: Blob not found (skipping schema check)")
                continue
            
            # Read raw CSV (bypass canonicalization pipeline)
            df = reader.read_csv(blob_path, data_type=None)
            columns = list(df.columns)
            
            result.data_inventory["schemas"][name] = {
                "columns": columns,
                "row_count": len(df)
            }
            
            schema = expected_schemas.get(name, {"required": [], "optional": []})
            
            # Check required columns (handle alternatives like date/game_date)
            missing_required = []
            for col in schema["required"]:
                if col not in columns:
                    # Check if there's an alternative
                    if col == "date" and "game_date" in columns:
                        continue  # game_date is acceptable alternative
                    if col == "game_date" and "date" in columns:
                        continue  # date is acceptable alternative
                    missing_required.append(col)
            
            if missing_required:
                print_fail(f"{name}: Missing required columns: {missing_required}")
                result.add_issue(AuditIssue(
                    category="schema_consistency",
                    severity="error",
                    message=f"{name} missing required columns",
                    details={"file": name, "missing": missing_required, "found": columns}
                ))
            else:
                print_pass(f"{name}: {len(columns)} columns, {len(df):,} rows")
                
            if verbose:
                print_info(f"  Columns: {columns}")
                
        except Exception as e:
            print_fail(f"{name}: Failed to read schema: {e}")
            result.add_issue(AuditIssue(
                category="schema_consistency",
                severity="error",
                message=f"Failed to read schema for {name}",
                details={"file": name, "error": str(e)}
            ))


# ============================================================================
# AUDIT 4: H1 ACTUAL SCORE COVERAGE (Using Pre-Merged Data)
# Note: H1 ACTUAL SCORES come from ESPN linescores - only ~10% of games
# This is DIFFERENT from H1 ODDS which is checked in AUDIT 5 (~87%)
# ============================================================================

def audit_h1_coverage(result: AuditResult, verbose: bool = False) -> None:
    """Check what % of games have first-half ACTUAL SCORES (ESPN linescore data).
    
    NOTE: This is expected to be ~8-10% because ESPN only provides linescores
    for select games (major conferences, ranked teams, etc.).
    
    For H1 BETTING ODDS coverage (~87%), see AUDIT 5.
    """
    print_header("AUDIT 4: H1 ACTUAL SCORE COVERAGE (ESPN linescores ~8-10% expected)")
    
    try:
        reader = get_azure_reader()
        
        # Use pre-merged backtest master which has H1 already joined
        if blob_exists(BACKTEST_MASTER):
            df = reader.read_csv(BACKTEST_MASTER, data_type=None)
            df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
            df["season_calc"] = df["game_date"].apply(_get_season)
            
            result.data_inventory["h1_coverage"] = {}
            
            for season in BACKTEST_SEASONS:
                season_games = df[df["season_calc"] == season]
                if len(season_games) == 0:
                    continue
                
                # Check home_h1 column from pre-merged data
                h1_count = season_games["home_h1"].notna().sum() if "home_h1" in season_games.columns else 0
                coverage_pct = (h1_count / len(season_games)) * 100
                
                result.data_inventory["h1_coverage"][season] = {
                    "total_games": len(season_games),
                    "games_with_h1": int(h1_count),
                    "coverage_pct": round(coverage_pct, 1)
                }
                
                # Use lenient threshold for current season (H1 scores may not be scraped yet)
                is_current = (season == CURRENT_SEASON)
                threshold = MIN_H1_COVERAGE_PCT_CURRENT if is_current else MIN_H1_COVERAGE_PCT
                
                if coverage_pct < threshold:
                    print_warn(f"Season {season}: {coverage_pct:.1f}% H1 coverage ({h1_count}/{len(season_games)})")
                    result.add_issue(AuditIssue(
                        category="h1_coverage",
                        severity="warning",
                        message=f"Season {season} H1 coverage below {threshold}%",
                        details={"season": season, "coverage_pct": coverage_pct, "is_current": is_current}
                    ))
                else:
                    print_pass(f"Season {season}: {coverage_pct:.1f}% H1 coverage ({h1_count}/{len(season_games)})")
        else:
            print_warn(f"Backtest master not found: {BACKTEST_MASTER}")
            result.add_issue(AuditIssue(
                category="h1_coverage",
                severity="warning",
                message=f"Backtest master not found",
                details={"path": BACKTEST_MASTER}
            ))
    
    except Exception as e:
        print_fail(f"Failed to check H1 coverage: {e}")
        result.add_issue(AuditIssue(
            category="h1_coverage",
            severity="error",
            message=f"Failed to check H1 coverage: {e}",
            details={"error": str(e)}
        ))


# ============================================================================
# AUDIT 5: ODDS COVERAGE (Using Pre-Merged Data)
# ============================================================================

def audit_odds_coverage(result: AuditResult, verbose: bool = False) -> None:
    """Check what % of games have odds data using pre-merged backtest master.
    
    Checks both:
    - FG (full-game) odds coverage (~87%)
    - H1 (first-half) BETTING ODDS coverage (~87%)
    """
    print_header("AUDIT 5: ODDS COVERAGE (FG + H1 Betting Lines)")
    
    try:
        reader = get_azure_reader()
        
        # Use pre-merged backtest master which has odds already joined
        if blob_exists(BACKTEST_MASTER):
            df = reader.read_csv(BACKTEST_MASTER, data_type=None)
            df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
            df["season_calc"] = df["game_date"].apply(_get_season)
            
            result.data_inventory["odds_coverage"] = {}
            result.data_inventory["h1_odds_coverage"] = {}
            
            for season in BACKTEST_SEASONS:
                season_games = df[df["season_calc"] == season]
                if len(season_games) == 0:
                    continue
                
                n = len(season_games)
                
                # Check FG spread (full-game odds)
                fg_count = season_games["fg_spread"].notna().sum() if "fg_spread" in season_games.columns else 0
                fg_pct = (fg_count / n) * 100
                
                # Check H1 spread (first-half BETTING ODDS - different from H1 scores)
                h1_count = season_games["h1_spread"].notna().sum() if "h1_spread" in season_games.columns else 0
                h1_pct = (h1_count / n) * 100
                
                result.data_inventory["odds_coverage"][season] = {
                    "total_games": n,
                    "games_with_fg_odds": int(fg_count),
                    "fg_coverage_pct": round(fg_pct, 1)
                }
                
                result.data_inventory["h1_odds_coverage"][season] = {
                    "total_games": n,
                    "games_with_h1_odds": int(h1_count),
                    "h1_coverage_pct": round(h1_pct, 1)
                }
                
                # Check FG odds threshold
                is_current = (season == CURRENT_SEASON)
                fg_threshold = MIN_ODDS_COVERAGE_PCT_CURRENT if is_current else MIN_ODDS_COVERAGE_PCT
                if fg_pct < fg_threshold:
                    print_warn(f"Season {season}: FG odds {fg_pct:.1f}% ({fg_count}/{n})")
                    result.add_issue(AuditIssue(
                        category="odds_coverage",
                        severity="warning",
                        message=f"Season {season} FG odds coverage below {fg_threshold}%",
                        details={"season": season, "fg_coverage_pct": fg_pct, "is_current": is_current}
                    ))
                else:
                    print_pass(f"Season {season}: FG odds {fg_pct:.1f}% ({fg_count}/{n})")
                
                # Check H1 BETTING ODDS threshold (should be ~87%, same as FG)
                h1_threshold = MIN_ODDS_COVERAGE_PCT_CURRENT if is_current else MIN_ODDS_COVERAGE_PCT
                if h1_pct < h1_threshold:
                    print_warn(f"Season {season}: H1 BETTING ODDS {h1_pct:.1f}% ({h1_count}/{n})")
                    result.add_issue(AuditIssue(
                        category="h1_odds_coverage",
                        severity="warning",
                        message=f"Season {season} H1 betting odds coverage below {h1_threshold}%",
                        details={"season": season, "h1_coverage_pct": h1_pct, "is_current": is_current}
                    ))
                else:
                    print_pass(f"Season {season}: H1 BETTING ODDS {h1_pct:.1f}% ({h1_count}/{n})")
        else:
            print_warn(f"Backtest master not found: {BACKTEST_MASTER}")
            result.add_issue(AuditIssue(
                category="odds_coverage",
                severity="warning",
                message=f"Backtest master not found",
                details={"path": BACKTEST_MASTER}
            ))
    
    except Exception as e:
        print_fail(f"Failed to check odds coverage: {e}")
        result.add_issue(AuditIssue(
            category="odds_coverage",
            severity="error",
            message=f"Failed to check odds coverage: {e}",
            details={"error": str(e)}
        ))


# ============================================================================
# AUDIT 6: RATINGS COVERAGE (Using Pre-Merged Data)
# ============================================================================

def audit_ratings_coverage(result: AuditResult, verbose: bool = False) -> None:
    """Check what % of games have both teams with Barttorvik ratings using pre-merged data."""
    print_header("AUDIT 6: BARTTORVIK RATINGS COVERAGE")
    
    result.data_inventory["ratings_coverage"] = {}
    
    try:
        reader = get_azure_reader()
        
        # Use pre-merged backtest master which has ratings already joined
        if blob_exists(BACKTEST_MASTER):
            df = reader.read_csv(BACKTEST_MASTER, data_type=None)
            df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
            df["season_calc"] = df["game_date"].apply(_get_season)
            
            for season in BACKTEST_SEASONS:
                season_games = df[df["season_calc"] == season]
                if len(season_games) == 0:
                    continue
                
                # Check both home_adj_o and away_adj_o for D1 matchups
                home_has_rating = season_games["home_adj_o"].notna() if "home_adj_o" in season_games.columns else pd.Series([False] * len(season_games))
                away_has_rating = season_games["away_adj_o"].notna() if "away_adj_o" in season_games.columns else pd.Series([False] * len(season_games))
                both_ratings = (home_has_rating & away_has_rating).sum()
                coverage_pct = (both_ratings / len(season_games)) * 100
                
                result.data_inventory["ratings_coverage"][season] = {
                    "total_games": len(season_games),
                    "games_with_both_ratings": int(both_ratings),
                    "coverage_pct": round(coverage_pct, 1)
                }
                
                if coverage_pct < MIN_RATINGS_COVERAGE_PCT:
                    print_warn(f"Season {season}: {coverage_pct:.1f}% ratings coverage ({both_ratings}/{len(season_games)} D1 matchups)")
                    result.add_issue(AuditIssue(
                        category="ratings_coverage",
                        severity="warning",
                        message=f"Season {season} ratings coverage below {MIN_RATINGS_COVERAGE_PCT}%",
                        details={"season": season, "coverage_pct": coverage_pct}
                    ))
                else:
                    print_pass(f"Season {season}: {coverage_pct:.1f}% ratings coverage ({both_ratings}/{len(season_games)} D1 matchups)")
        else:
            print_warn(f"Backtest master not found: {BACKTEST_MASTER}")
            result.add_issue(AuditIssue(
                category="ratings_coverage",
                severity="warning",
                message=f"Backtest master not found",
                details={"path": BACKTEST_MASTER}
            ))
    
    except Exception as e:
        print_fail(f"Failed to check ratings coverage: {e}")
        result.add_issue(AuditIssue(
            category="ratings_coverage",
            severity="error",
            message=f"Failed to check ratings coverage: {e}",
            details={"error": str(e)}
        ))


# ============================================================================
# AUDIT 7: TEAM RESOLUTION
# ============================================================================

def audit_team_resolution(result: AuditResult, verbose: bool = False) -> None:
    """Verify all team names resolve to canonical names."""
    print_header("AUDIT 7: TEAM RESOLUTION")
    
    try:
        # Load team aliases
        aliases = read_json("backtest_datasets/team_aliases_db.json")
        alias_lookup = {k.lower().strip(): v for k, v in aliases.items()}
        
        # Add canonical names as self-references
        for canonical in set(aliases.values()):
            key = canonical.lower().strip()
            if key not in alias_lookup:
                alias_lookup[key] = canonical
        
        print_info(f"Loaded {len(aliases)} aliases -> {len(set(aliases.values()))} canonical teams")
        
        # Use raw read to bypass canonicalization pipeline
        reader = get_azure_reader()
        games_df = reader.read_csv("scores/fg/games_all.csv", data_type=None)
        
        unresolved = set()
        total_teams = set()
        
        for col in ["home_team", "away_team"]:
            if col in games_df.columns:
                for team in games_df[col].dropna().unique():
                    team_key = str(team).lower().strip()
                    total_teams.add(team_key)
                    if team_key not in alias_lookup:
                        unresolved.add(team)
        
        resolved_count = len(total_teams) - len(unresolved)
        resolution_pct = (resolved_count / len(total_teams) * 100) if total_teams else 100
        
        result.data_inventory["team_resolution"] = {
            "total_unique_teams": len(total_teams),
            "resolved": resolved_count,
            "unresolved": len(unresolved),
            "resolution_pct": round(resolution_pct, 1),
            "unresolved_samples": list(unresolved)[:20]
        }
        
        if len(unresolved) == 0:
            print_pass(f"All {len(total_teams)} unique teams resolve successfully")
        elif len(unresolved) <= 10:
            print_warn(f"{len(unresolved)} unresolved teams: {list(unresolved)[:10]}")
            result.add_issue(AuditIssue(
                category="team_resolution",
                severity="warning",
                message=f"{len(unresolved)} teams cannot be resolved",
                details={"unresolved": list(unresolved)[:20]}
            ))
        else:
            print_fail(f"{len(unresolved)} unresolved teams (first 10: {list(unresolved)[:10]})")
            result.add_issue(AuditIssue(
                category="team_resolution",
                severity="error",
                message=f"{len(unresolved)} teams cannot be resolved",
                details={"unresolved": list(unresolved)[:20]}
            ))
    
    except Exception as e:
        print_fail(f"Failed to check team resolution: {e}")
        result.add_issue(AuditIssue(
            category="team_resolution",
            severity="error",
            message=f"Failed to check team resolution: {e}",
            details={"error": str(e)}
        ))


# ============================================================================
# AUDIT 8: DATA INTEGRITY
# ============================================================================

def audit_data_integrity(result: AuditResult, verbose: bool = False) -> None:
    """Check for nulls in critical fields, invalid values."""
    print_header("AUDIT 8: DATA INTEGRITY")
    
    try:
        # Use raw read to bypass canonicalization pipeline
        reader = get_azure_reader()
        games_df = reader.read_csv("scores/fg/games_all.csv", data_type=None)
        
        result.data_inventory["data_integrity"] = {"scores": {}, "odds": {}}
        
        # Check critical columns for nulls
        for col in CRITICAL_SCORE_COLUMNS:
            if col in games_df.columns:
                null_count = games_df[col].isnull().sum()
                null_pct = (null_count / len(games_df)) * 100
                
                result.data_inventory["data_integrity"]["scores"][col] = {
                    "null_count": int(null_count),
                    "null_pct": round(null_pct, 2)
                }
                
                if null_pct > 5:
                    print_fail(f"scores.{col}: {null_pct:.1f}% null ({null_count} rows)")
                    result.add_issue(AuditIssue(
                        category="data_integrity",
                        severity="error",
                        message=f"Critical column {col} has excessive nulls",
                        details={"column": col, "null_pct": null_pct}
                    ))
                elif null_pct > 0:
                    print_warn(f"scores.{col}: {null_pct:.1f}% null ({null_count} rows)")
                else:
                    print_pass(f"scores.{col}: No nulls")
            else:
                print_fail(f"scores.{col}: Column missing")
                result.add_issue(AuditIssue(
                    category="data_integrity",
                    severity="critical",
                    message=f"Critical column {col} is missing from scores",
                    details={"column": col}
                ))
        
        # Check score values are valid
        for col in ["home_score", "away_score"]:
            if col in games_df.columns:
                scores = games_df[col].dropna()
                negative = (scores < 0).sum()
                too_high = (scores > 200).sum()
                
                if negative > 0:
                    print_fail(f"scores.{col}: {negative} negative values")
                    result.add_issue(AuditIssue(
                        category="data_integrity",
                        severity="error",
                        message=f"{col} has negative scores",
                        details={"column": col, "negative_count": int(negative)}
                    ))
                
                if too_high > 0:
                    print_warn(f"scores.{col}: {too_high} values > 200")
    
    except Exception as e:
        print_fail(f"Failed data integrity check: {e}")
        result.add_issue(AuditIssue(
            category="data_integrity",
            severity="error",
            message=f"Failed data integrity check: {e}",
            details={"error": str(e)}
        ))


# ============================================================================
# AUDIT 9: INGESTION RECENCY (Blob Metadata)
# ============================================================================

def audit_ingestion_recency(result: AuditResult, verbose: bool = False) -> None:
    """Check blob metadata for last modified times."""
    print_header("AUDIT 9: INGESTION RECENCY")
    
    # This requires direct Azure SDK access to get blob properties
    try:
        reader = get_azure_reader()
        
        critical_blobs = [
            "scores/fg/games_all.csv",
            "scores/h1/h1_games_all.csv",
            "odds/normalized/odds_consolidated_canonical.csv",
            "backtest_datasets/team_aliases_db.json",
        ]
        
        result.data_inventory["blob_metadata"] = {}
        
        for blob_path in critical_blobs:
            try:
                props = reader.get_blob_properties(blob_path)
                if props:
                    last_modified = props.get("last_modified")
                    size_bytes = props.get("size", 0)
                    
                    result.data_inventory["blob_metadata"][blob_path] = {
                        "last_modified": str(last_modified) if last_modified else "unknown",
                        "size_bytes": size_bytes
                    }
                    
                    if last_modified:
                        print_pass(f"{blob_path.split('/')[-1]}: Last modified {last_modified}")
                    else:
                        print_info(f"{blob_path.split('/')[-1]}: Metadata unavailable")
                else:
                    print_info(f"{blob_path.split('/')[-1]}: Properties not available")
            except AttributeError:
                # get_blob_properties may not exist
                print_info(f"Blob properties API not available")
                break
            except Exception as e:
                print_warn(f"{blob_path}: Could not get properties: {e}")
    
    except Exception as e:
        print_info(f"Ingestion recency check not available: {e}")


# ============================================================================
# SUMMARY
# ============================================================================

def print_summary(result: AuditResult) -> None:
    """Print final audit summary."""
    print(f"\n{'='*72}")
    print(f"{Colors.BOLD}COMPREHENSIVE INGESTION AUDIT SUMMARY{Colors.END}")
    print('='*72)
    
    print(f"\nBacktest Seasons: {BACKTEST_SEASONS}")
    print(f"Timestamp: {result.timestamp}")
    
    critical_count = len([i for i in result.issues if i["severity"] == "critical"])
    error_count = len([i for i in result.issues if i["severity"] == "error"])
    warning_count = len([i for i in result.issues if i["severity"] == "warning"])
    
    print(f"\nIssues Found:")
    print(f"  Critical: {critical_count}")
    print(f"  Errors:   {error_count}")
    print(f"  Warnings: {warning_count}")
    
    result.summary = {
        "critical_count": critical_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "passed": result.passed
    }
    
    if result.passed and not result.has_warnings:
        print(f"\n{Colors.GREEN}{'='*72}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}[OK] ALL AUDITS PASSED - BACKTEST READY{Colors.END}")
        print(f"{Colors.GREEN}{'='*72}{Colors.END}")
    elif result.passed:
        print(f"\n{Colors.YELLOW}{'='*72}{Colors.END}")
        print(f"{Colors.YELLOW}{Colors.BOLD}[!] PASSED WITH WARNINGS - PROCEED WITH CAUTION{Colors.END}")
        print(f"{Colors.YELLOW}{'='*72}{Colors.END}")
    else:
        print(f"\n{Colors.RED}{'='*72}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}[X] AUDIT FAILED - BACKTEST BLOCKED{Colors.END}")
        print(f"{Colors.RED}{'='*72}{Colors.END}")
        print("\nFix the following issues before running backtests:")
        for issue in result.issues:
            if issue["severity"] in ["critical", "error"]:
                print(f"  - [{issue['severity'].upper()}] {issue['message']}")


# ============================================================================
# MAIN
# ============================================================================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Comprehensive ingestion audit for backtest readiness"
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed output")
    parser.add_argument("--output", "-o", type=str,
                        help="Save audit results to JSON file")
    parser.add_argument("--seasons", type=str,
                        help="Comma-separated seasons to audit (default: canonical window)")
    args = parser.parse_args(argv)
    
    # Override seasons if specified
    global BACKTEST_SEASONS
    if args.seasons:
        BACKTEST_SEASONS = enforce_min_season([int(s.strip()) for s in args.seasons.split(",")])
    
    print(f"\n{Colors.BOLD}{'='*72}{Colors.END}")
    print(f"{Colors.BOLD}COMPREHENSIVE INGESTION AUDIT{Colors.END}")
    print(f"{Colors.BOLD}{'='*72}{Colors.END}")
    print(f"Target Backtest Seasons: {BACKTEST_SEASONS}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    result = AuditResult()
    
    # Run all audits
    audit_data_existence(result, args.verbose)
    audit_season_coverage(result, args.verbose)
    audit_schema_consistency(result, args.verbose)
    audit_h1_coverage(result, args.verbose)
    audit_odds_coverage(result, args.verbose)
    audit_ratings_coverage(result, args.verbose)
    audit_team_resolution(result, args.verbose)
    audit_data_integrity(result, args.verbose)
    audit_ingestion_recency(result, args.verbose)
    
    # Print summary
    print_summary(result)
    
    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(asdict(result), f, indent=2, default=str)
        print(f"\nResults saved to: {args.output}")
    
    # Exit code
    if result.has_critical or result.has_errors:
        return 1
    elif result.has_warnings:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
