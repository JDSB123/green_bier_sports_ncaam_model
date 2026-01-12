#!/usr/bin/env python3
"""
Load Historical NCAAM Data for ML Training.

This script fetches historical game data and loads it into the database.
It uses multiple data sources to build complete training records.

Data Sources:
1. Basketball API (game scores, team stats) - API key required
2. Barttorvik (team ratings) - scraped from web
3. The Odds API (historical odds if available)

Usage:
    # Load 2023-24 and 2024-25 seasons
    python scripts/load_historical_data.py --seasons 2023 2024
    
    # Load specific date range
    python scripts/load_historical_data.py --start 2023-11-01 --end 2024-03-31
"""

import argparse
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import time

# Add app and repo root to path
APP_DIR = Path(__file__).parent.parent
ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(ROOT_DIR))

from testing.azure_io import read_csv
from testing.data_paths import DATA_PATHS

DEFAULT_GAMES_BLOB = str(DATA_PATHS.backtest_datasets / "training_data_with_odds.csv")
DEFAULT_RATINGS_BLOB = str(DATA_PATHS.backtest_datasets / "barttorvik_ratings.csv")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from sqlalchemy import create_engine, text
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


class BasketballAPIClient:
    """Client for Basketball API (api-basketball.com)."""
    
    BASE_URL = "https://v1.basketball.api-sports.io"
    NCAAM_LEAGUE_ID = 116  # NCAA Men's Basketball
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("BASKETBALL_API_KEY")
        if not self.api_key:
            # Try reading from file
            key_file = Path(__file__).parent.parent.parent.parent / "secrets" / "basketball_api_key.txt"
            if key_file.exists():
                self.api_key = key_file.read_text().strip()
        
        if not self.api_key:
            raise ValueError("Basketball API key required. Set BASKETBALL_API_KEY or create secrets/basketball_api_key.txt")
        
        self.session = requests.Session()
        self.session.headers.update({
            "x-apisports-key": self.api_key,
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests
    
    def _request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make rate-limited API request."""
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params)
        self.last_request_time = time.time()
        
        if response.status_code != 200:
            raise Exception(f"API error {response.status_code}: {response.text}")
        
        return response.json()
    
    def get_games(self, season: int, date_str: Optional[str] = None) -> List[Dict]:
        """
        Get games for a season or specific date.
        
        Args:
            season: Season year (e.g., 2023 for 2023-24 season)
            date_str: Optional date (YYYY-MM-DD)
        """
        params = {
            "league": self.NCAAM_LEAGUE_ID,
            "season": f"{season}-{season + 1}",
        }
        if date_str:
            params["date"] = date_str
        
        data = self._request("games", params)
        return data.get("response", [])
    
    def get_game_stats(self, game_id: int) -> Dict:
        """Get statistics for a specific game."""
        data = self._request("games/statistics", {"id": game_id})
        return data.get("response", {})


class BartttorvikScraper:
    """Scrape historical ratings from Barttorvik."""
    
    BASE_URL = "https://barttorvik.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 NCAAM-Research/1.0",
        })
    
    def get_ratings_for_date(self, rating_date: date) -> List[Dict]:
        """
        Get team ratings as of a specific date.
        
        Note: Barttorvik may not have exact historical data publicly available.
        This is a placeholder for manual data import.
        """
        # Barttorvik doesn't have a public API for historical data
        # You would need to:
        # 1. Use Wayback Machine snapshots
        # 2. Contact Barttorvik for data access
        # 3. Use cached data from prior runs
        raise NotImplementedError(
            "Barttorvik historical scraping not implemented. "
            "Use CSV import for historical ratings."
        )


def create_database_engine():
    """Create database engine from environment."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Build from components
        db_host = os.environ.get("DB_HOST", "localhost")
        db_port = os.environ.get("DB_PORT", "5450")
        db_user = os.environ.get("DB_USER", "ncaam")
        db_name = os.environ.get("DB_NAME", "ncaam")
        db_pass = os.environ.get("DB_PASSWORD", "ncaam")
        
        # Try reading password from file
        pw_file = Path("/run/secrets/db_password")
        if pw_file.exists():
            db_pass = pw_file.read_text().strip()
        
        db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    return create_engine(db_url)


def load_games_from_blob(blob_path: str) -> List[Dict]:
    """
    Load game data from Azure Blob Storage (CSV).

    Expected columns:
    - game_date or date
    - home_team / away_team
    - home_score / away_score
    - spread_open / total_open (optional)
    - home_h1 / away_h1 (optional)
    """
    games = []
    df = read_csv(blob_path)
    for row in df.to_dict(orient="records"):
        games.append({
            "game_date": row.get("game_date") or row.get("date"),
            "home_team": row.get("home_team") or row.get("home"),
            "away_team": row.get("away_team") or row.get("away"),
            "home_score": int(row.get("home_score") or row.get("home_fg") or 0),
            "away_score": int(row.get("away_score") or row.get("away_fg") or 0),
            "spread_open": float(row["spread_open"]) if row.get("spread_open") else None,
            "total_open": float(row["total_open"]) if row.get("total_open") else None,
            "home_h1_score": int(row["home_h1"]) if row.get("home_h1") else None,
            "away_h1_score": int(row["away_h1"]) if row.get("away_h1") else None,
        })
    return games


def load_ratings_from_blob(blob_path: str) -> Dict[str, Dict]:
    """
    Load team ratings from Azure Blob Storage (CSV).

    Expected columns:
    - rating_date (optional)
    - team
    - adj_o, adj_d, tempo, rank, efg, efgd, tor, tord, orb, drb, ftr, ftrd,
      two_pt_pct, two_pt_pct_d, three_pt_pct, three_pt_pct_d, three_pt_rate,
      three_pt_rate_d, barthag, wab
    """
    ratings = {}
    df = read_csv(blob_path)
    for row in df.to_dict(orient="records"):
        rating_date = row.get("rating_date") or row.get("date") or ""
        team_name = row.get("team") or row.get("team_name")
        if not team_name:
            continue
        key = f"{rating_date}_{team_name}"
        ratings[key] = {
            "team": team_name,
            "rating_date": rating_date,
            "adj_o": float(row.get("adj_o", 100)),
            "adj_d": float(row.get("adj_d", 100)),
            "tempo": float(row.get("tempo", 67.6)),
            "rank": int(row.get("rank", 200)),
            "efg": float(row.get("efg", 50)),
            "efgd": float(row.get("efgd", 50)),
            "tor": float(row.get("tor", 18.5)),
            "tord": float(row.get("tord", 18.5)),
            "orb": float(row.get("orb", 28)),
            "drb": float(row.get("drb", 72)),
            "ftr": float(row.get("ftr", 33)),
            "ftrd": float(row.get("ftrd", 33)),
            "two_pt_pct": float(row.get("two_pt_pct", 50)),
            "two_pt_pct_d": float(row.get("two_pt_pct_d", 50)),
            "three_pt_pct": float(row.get("three_pt_pct", 35)),
            "three_pt_pct_d": float(row.get("three_pt_pct_d", 35)),
            "three_pt_rate": float(row.get("three_pt_rate", 35)),
            "three_pt_rate_d": float(row.get("three_pt_rate_d", 35)),
            "barthag": float(row.get("barthag", 0.5)),
            "wab": float(row.get("wab", 0)),
        }
    return ratings


def main():
    parser = argparse.ArgumentParser(description="Load historical NCAAM data")
    parser.add_argument(
        "--games-blob",
        type=str,
        default=DEFAULT_GAMES_BLOB,
        help="Azure blob path with game results"
    )
    parser.add_argument(
        "--ratings-blob",
        type=str,
        default=DEFAULT_RATINGS_BLOB,
        help="Azure blob path with team ratings"
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        help="Seasons to fetch from API (e.g., 2023 2024)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be loaded without writing"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("NCAAM Historical Data Loader")
    print("=" * 60)
    
    # Load from Azure if provided
    if args.games_blob:
        print(f"\nLoading games from Azure blob: {args.games_blob}")
        games = load_games_from_blob(args.games_blob)
        print(f"   Loaded {len(games)} games")
        
        if not args.dry_run:
            # TODO: Insert into database
            print("   ⚠️ Database insert not yet implemented")
    
    if args.ratings_blob:
        print(f"\nLoading ratings from Azure blob: {args.ratings_blob}")
        ratings = load_ratings_from_blob(args.ratings_blob)
        print(f"   Loaded {len(ratings)} team-date ratings")
        
        if not args.dry_run:
            # TODO: Insert into database
            print("   ⚠️ Database insert not yet implemented")
    
    # Fetch from API if seasons provided
    if args.seasons:
        if not HAS_REQUESTS:
            print("❌ requests library required for API access")
            sys.exit(1)
        
        try:
            client = BasketballAPIClient()
            print(f"\n🌐 Fetching from Basketball API...")
            
            for season in args.seasons:
                print(f"\n   Season {season}-{season+1}:")
                games = client.get_games(season)
                print(f"   Found {len(games)} games")
                
                if args.dry_run:
                    # Show sample
                    for game in games[:3]:
                        print(f"     - {game}")
        except Exception as e:
            print(f"❌ API error: {e}")
            sys.exit(1)
    
    if not any([args.games_blob, args.ratings_blob, args.seasons]):
        print("\nNo data source specified!")
        print("\nUsage examples:")
        print("  # Load from Azure blobs")
        print("  python scripts/load_historical_data.py --games-blob backtest_datasets/training_data_with_odds.csv")
        print("")
        print("  # Fetch from Basketball API")
        print("  python scripts/load_historical_data.py --seasons 2023 2024")
        print("")
        print("Azure Blob Storage is the single source of truth.")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
