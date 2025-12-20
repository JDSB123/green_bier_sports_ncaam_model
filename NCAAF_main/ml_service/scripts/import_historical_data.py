#!/usr/bin/env python3
"""
Historical Data Import Script for NCAAF Predictions

Imports historical NCAAF data from multiple sources:
1. Azure Blob Storage (if configured)
2. Local CSV/JSON files
3. SportsDataIO API backfill
4. Existing database consolidation

Supports bulk import from 2-3 months of automated scrapes.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio
import aiohttp
from sqlalchemy import create_engine, text
import psycopg2
from psycopg2.extras import execute_batch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import Settings
from src.db.database import Database

# Azure imports (optional)
try:
    from azure.storage.blob import BlobServiceClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("Azure SDK not installed. Install with: pip install azure-storage-blob")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalDataImporter:
    """Import historical NCAAF data from multiple sources."""

    def __init__(self, db: Database):
        """Initialize importer with database connection."""
        self.db = db
        self.settings = Settings()
        self.imported_games = set()
        self.imported_odds = set()

    async def import_from_azure(self,
                               container_name: str = "ncaaf-data",
                               connection_string: Optional[str] = None) -> int:
        """
        Import data from Azure Blob Storage.

        Args:
            container_name: Azure container name
            connection_string: Azure storage connection string

        Returns:
            Number of records imported
        """
        if not AZURE_AVAILABLE:
            logger.error("Azure SDK not installed")
            return 0

        conn_str = connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if not conn_str:
            logger.error("Azure connection string not provided")
            return 0

        logger.info(f"Connecting to Azure container: {container_name}")

        try:
            blob_service = BlobServiceClient.from_connection_string(conn_str)
            container_client = blob_service.get_container_client(container_name)

            imported_count = 0

            # List all blobs in container
            blobs = container_client.list_blobs()

            for blob in blobs:
                if blob.name.endswith(('.json', '.csv')):
                    logger.info(f"Processing blob: {blob.name}")

                    # Download blob
                    blob_client = container_client.get_blob_client(blob)
                    data = blob_client.download_blob().readall()

                    # Process based on file type
                    if blob.name.endswith('.json'):
                        imported_count += self._import_json_data(data, blob.name)
                    elif blob.name.endswith('.csv'):
                        imported_count += self._import_csv_data(data, blob.name)

            logger.info(f"Imported {imported_count} records from Azure")
            return imported_count

        except Exception as e:
            logger.error(f"Azure import failed: {e}")
            return 0

    def import_from_directory(self, directory: str) -> int:
        """
        Import data from local directory of CSV/JSON files.

        Args:
            directory: Path to directory containing data files

        Returns:
            Number of records imported
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.error(f"Directory not found: {directory}")
            return 0

        imported_count = 0

        # Process JSON files
        for json_file in dir_path.glob("**/*.json"):
            logger.info(f"Processing file: {json_file}")
            with open(json_file, 'r') as f:
                data = json.load(f)
            imported_count += self._process_json_file(data, str(json_file))

        # Process CSV files
        for csv_file in dir_path.glob("**/*.csv"):
            logger.info(f"Processing file: {csv_file}")
            df = pd.read_csv(csv_file)
            imported_count += self._process_csv_file(df, str(csv_file))

        logger.info(f"Imported {imported_count} records from {directory}")
        return imported_count

    async def backfill_from_sportsdataio(self,
                                        start_season: int = 2018,
                                        end_season: int = 2024) -> int:
        """
        Backfill historical data from SportsDataIO API.

        Args:
            start_season: First season to backfill
            end_season: Last season to backfill

        Returns:
            Number of records imported
        """
        api_key = os.getenv("SPORTSDATA_API_KEY")
        if not api_key:
            logger.error("SportsDataIO API key not configured")
            return 0

        base_url = "https://api.sportsdata.io/v3/cfb"
        imported_count = 0

        async with aiohttp.ClientSession() as session:
            for season in range(start_season, end_season + 1):
                logger.info(f"Backfilling season {season}")

                # Fetch season games
                games_url = f"{base_url}/scores/json/Games/{season}"
                headers = {"Ocp-Apim-Subscription-Key": api_key}

                async with session.get(games_url, headers=headers) as resp:
                    if resp.status == 200:
                        games = await resp.json()
                        imported_count += self._import_games(games, season)

                # Fetch team stats for season
                stats_url = f"{base_url}/scores/json/TeamSeasonStats/{season}"
                async with session.get(stats_url, headers=headers) as resp:
                    if resp.status == 200:
                        stats = await resp.json()
                        imported_count += self._import_team_stats(stats, season)

                # Fetch odds for each week
                for week in range(1, 16):  # Weeks 1-15
                    odds_url = f"{base_url}/odds/json/GameOddsByWeek/{season}/{week}"
                    async with session.get(odds_url, headers=headers) as resp:
                        if resp.status == 200:
                            odds = await resp.json()
                            imported_count += self._import_odds(odds, season, week)

                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.5)

        logger.info(f"Backfilled {imported_count} records from SportsDataIO")
        return imported_count

    def _import_json_data(self, data: bytes, filename: str) -> int:
        """Process JSON data from blob/file."""
        try:
            json_data = json.loads(data)

            # Detect data type based on structure
            if isinstance(json_data, list) and len(json_data) > 0:
                first_item = json_data[0]

                if 'GameID' in first_item or 'game_id' in first_item:
                    return self._import_games(json_data, None)
                elif 'TeamID' in first_item and 'PointsPerGamePassing' in first_item:
                    return self._import_team_stats(json_data, None)
                elif 'GameOddID' in first_item or 'Sportsbook' in first_item:
                    return self._import_odds(json_data, None, None)

            logger.warning(f"Unknown JSON structure in {filename}")
            return 0

        except Exception as e:
            logger.error(f"Failed to process JSON {filename}: {e}")
            return 0

    def _import_csv_data(self, data: bytes, filename: str) -> int:
        """Process CSV data from blob/file."""
        try:
            import io
            df = pd.read_csv(io.BytesIO(data))
            return self._process_csv_file(df, filename)
        except Exception as e:
            logger.error(f"Failed to process CSV {filename}: {e}")
            return 0

    def _process_json_file(self, data: dict, filename: str) -> int:
        """Process local JSON file."""
        if 'games' in data:
            return self._import_games(data['games'], None)
        elif 'odds' in data:
            return self._import_odds(data['odds'], None, None)
        elif 'stats' in data:
            return self._import_team_stats(data['stats'], None)
        else:
            logger.warning(f"Unknown JSON structure in {filename}")
            return 0

    def _process_csv_file(self, df: pd.DataFrame, filename: str) -> int:
        """Process local CSV file."""
        imported = 0

        # Detect CSV type based on columns
        columns = df.columns.tolist()

        if 'game_id' in columns and 'home_score' in columns:
            # Games CSV
            for _, row in df.iterrows():
                if self._insert_game(row.to_dict()):
                    imported += 1

        elif 'team_id' in columns and 'points_per_game' in columns:
            # Team stats CSV
            for _, row in df.iterrows():
                if self._insert_team_stats(row.to_dict()):
                    imported += 1

        elif 'sportsbook' in columns and 'spread' in columns:
            # Odds CSV
            for _, row in df.iterrows():
                if self._insert_odds(row.to_dict()):
                    imported += 1

        else:
            logger.warning(f"Unknown CSV structure in {filename}")

        return imported

    def _import_games(self, games: List[Dict], season: int) -> int:
        """Import game data."""
        imported = 0

        for game in games:
            game_id = game.get('GameID') or game.get('game_id')

            if game_id in self.imported_games:
                continue

            # Map API fields to database fields
            game_data = {
                'game_id': game_id,
                'season': season or game.get('Season'),
                'week': game.get('Week'),
                'home_team_id': game.get('HomeTeamID') or game.get('home_team_id'),
                'away_team_id': game.get('AwayTeamID') or game.get('away_team_id'),
                'home_score': game.get('HomeScore') or game.get('home_score'),
                'away_score': game.get('AwayScore') or game.get('away_score'),
                'status': game.get('Status'),
                'day': game.get('Day'),
                'date_time': game.get('DateTime'),
                'stadium_id': game.get('StadiumID'),
                'channel': game.get('Channel'),
                'attendance': game.get('Attendance'),
                'weather': game.get('Weather'),
                'over_under': game.get('OverUnder'),
                'point_spread': game.get('PointSpread'),
            }

            if self._insert_game(game_data):
                imported += 1
                self.imported_games.add(game_id)

        return imported

    def _import_team_stats(self, stats: List[Dict], season: int) -> int:
        """Import team statistics."""
        imported = 0

        for stat in stats:
            team_id = stat.get('TeamID') or stat.get('team_id')

            # Map API fields to database fields
            stat_data = {
                'team_id': team_id,
                'season': season or stat.get('Season'),
                'games': stat.get('Games'),
                'wins': stat.get('Wins'),
                'losses': stat.get('Losses'),
                'points_per_game': stat.get('PointsPerGamePassing', 0) + stat.get('PointsPerGameRushing', 0),
                'points_allowed': stat.get('OpponentOffensiveYardsPerGame'),
                'offensive_yards_per_game': stat.get('OffensiveYardsPerGame'),
                'defensive_yards_per_game': stat.get('DefensiveYardsPerGame'),
                'passing_yards_per_game': stat.get('PassingYardsPerGame'),
                'rushing_yards_per_game': stat.get('RushingYardsPerGame'),
                'third_down_pct': stat.get('ThirdDownPercentage'),
                'red_zone_pct': stat.get('RedZoneAttempts'),
                'turnovers': stat.get('Turnovers'),
                'takeaways': stat.get('Takeaways'),
            }

            if self._insert_team_stats(stat_data):
                imported += 1

        return imported

    def _import_odds(self, odds: List[Dict], season: int, week: int) -> int:
        """Import odds data."""
        imported = 0

        for odd in odds:
            game_id = odd.get('GameID') or odd.get('game_id')
            sportsbook = odd.get('Sportsbook') or odd.get('sportsbook')

            # Create unique key for deduplication
            odd_key = f"{game_id}_{sportsbook}"

            if odd_key in self.imported_odds:
                continue

            # Map API fields to database fields
            odd_data = {
                'game_id': game_id,
                'sportsbook_id': self._get_sportsbook_id(sportsbook),
                'sportsbook_name': sportsbook,
                'spread_home': odd.get('HomePointSpread'),
                'spread_away': odd.get('AwayPointSpread'),
                'total_over': odd.get('OverUnder'),
                'total_under': odd.get('UnderOver'),
                'moneyline_home': odd.get('HomeMoneyLine'),
                'moneyline_away': odd.get('AwayMoneyLine'),
                'created_at': odd.get('Created'),
                'updated_at': odd.get('Updated'),
            }

            if self._insert_odds(odd_data):
                imported += 1
                self.imported_odds.add(odd_key)

        return imported

    def _get_sportsbook_id(self, name: str) -> int:
        """Map sportsbook name to ID."""
        sportsbook_map = {
            'DraftKings': 1100,
            'FanDuel': 1101,
            'BetMGM': 1103,
            'Caesars': 1104,
            'Pinnacle': 1105,
            'Circa': 1106,
            'Bet365': 1107,
            'ESPNBet': 1114,
            'Fanatics': 1116,
            'BetOnline': 1118,
        }
        return sportsbook_map.get(name, 9999)

    def _insert_game(self, game: Dict) -> bool:
        """Insert game record into database."""
        try:
            query = """
                INSERT INTO games (
                    game_id, season, week, home_team_id, away_team_id,
                    home_score, away_score, status, day, date_time,
                    stadium_id, channel, attendance, weather,
                    over_under, point_spread, created_at, updated_at
                ) VALUES (
                    %(game_id)s, %(season)s, %(week)s, %(home_team_id)s, %(away_team_id)s,
                    %(home_score)s, %(away_score)s, %(status)s, %(day)s, %(date_time)s,
                    %(stadium_id)s, %(channel)s, %(attendance)s, %(weather)s,
                    %(over_under)s, %(point_spread)s, NOW(), NOW()
                )
                ON CONFLICT (game_id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    status = EXCLUDED.status,
                    updated_at = NOW()
            """

            # Calculate derived fields
            if game.get('home_score') is not None and game.get('away_score') is not None:
                game['total_score'] = game['home_score'] + game['away_score']
                game['margin'] = game['home_score'] - game['away_score']

            self.db.execute(query, game)
            return True

        except Exception as e:
            logger.error(f"Failed to insert game: {e}")
            return False

    def _insert_team_stats(self, stats: Dict) -> bool:
        """Insert team statistics record."""
        try:
            query = """
                INSERT INTO team_season_stats (
                    team_id, season, games, wins, losses,
                    points_per_game, points_allowed,
                    offensive_yards_per_game, defensive_yards_per_game,
                    passing_yards_per_game, rushing_yards_per_game,
                    third_down_pct, red_zone_pct,
                    turnovers, takeaways,
                    created_at, updated_at
                ) VALUES (
                    %(team_id)s, %(season)s, %(games)s, %(wins)s, %(losses)s,
                    %(points_per_game)s, %(points_allowed)s,
                    %(offensive_yards_per_game)s, %(defensive_yards_per_game)s,
                    %(passing_yards_per_game)s, %(rushing_yards_per_game)s,
                    %(third_down_pct)s, %(red_zone_pct)s,
                    %(turnovers)s, %(takeaways)s,
                    NOW(), NOW()
                )
                ON CONFLICT (team_id, season) DO UPDATE SET
                    games = EXCLUDED.games,
                    wins = EXCLUDED.wins,
                    losses = EXCLUDED.losses,
                    points_per_game = EXCLUDED.points_per_game,
                    points_allowed = EXCLUDED.points_allowed,
                    updated_at = NOW()
            """

            self.db.execute(query, stats)
            return True

        except Exception as e:
            logger.error(f"Failed to insert team stats: {e}")
            return False

    def _insert_odds(self, odds: Dict) -> bool:
        """Insert odds record."""
        try:
            query = """
                INSERT INTO odds (
                    game_id, sportsbook_id, sportsbook_name,
                    spread_home, spread_away,
                    total_over, total_under,
                    moneyline_home, moneyline_away,
                    created_at, updated_at
                ) VALUES (
                    %(game_id)s, %(sportsbook_id)s, %(sportsbook_name)s,
                    %(spread_home)s, %(spread_away)s,
                    %(total_over)s, %(total_under)s,
                    %(moneyline_home)s, %(moneyline_away)s,
                    %(created_at)s, NOW()
                )
                ON CONFLICT (game_id, sportsbook_id, created_at) DO NOTHING
            """

            self.db.execute(query, odds)
            return True

        except Exception as e:
            logger.error(f"Failed to insert odds: {e}")
            return False

    def consolidate_duplicates(self) -> int:
        """Remove duplicate records and consolidate data."""
        logger.info("Consolidating duplicate records...")

        # Remove duplicate games
        query = """
            DELETE FROM games a USING games b
            WHERE a.id < b.id
            AND a.game_id = b.game_id
        """
        deleted = self.db.execute(query)

        logger.info(f"Removed {deleted} duplicate games")
        return deleted


async def main():
    """Main entry point for historical data import."""
    import argparse

    parser = argparse.ArgumentParser(description="Import historical NCAAF data")
    parser.add_argument("--azure", action="store_true", help="Import from Azure Blob Storage")
    parser.add_argument("--azure-container", default="ncaaf-data", help="Azure container name")
    parser.add_argument("--azure-connection", help="Azure connection string")
    parser.add_argument("--directory", help="Import from local directory")
    parser.add_argument("--backfill", action="store_true", help="Backfill from SportsDataIO")
    parser.add_argument("--start-season", type=int, default=2018, help="Start season for backfill")
    parser.add_argument("--end-season", type=int, default=2024, help="End season for backfill")
    parser.add_argument("--consolidate", action="store_true", help="Consolidate duplicates after import")

    args = parser.parse_args()

    # Initialize database
    db = Database()
    db.connect()

    importer = HistoricalDataImporter(db)
    total_imported = 0

    # Import from Azure
    if args.azure:
        count = await importer.import_from_azure(
            container_name=args.azure_container,
            connection_string=args.azure_connection
        )
        total_imported += count

    # Import from directory
    if args.directory:
        count = importer.import_from_directory(args.directory)
        total_imported += count

    # Backfill from SportsDataIO
    if args.backfill:
        count = await importer.backfill_from_sportsdataio(
            start_season=args.start_season,
            end_season=args.end_season
        )
        total_imported += count

    # Consolidate duplicates
    if args.consolidate:
        importer.consolidate_duplicates()

    logger.info(f"Total records imported: {total_imported}")

    # Close database
    db.close()


if __name__ == "__main__":
    asyncio.run(main())