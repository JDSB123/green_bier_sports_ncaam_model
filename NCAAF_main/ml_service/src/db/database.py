"""Database connection and session management."""
from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.config.settings import settings


class Database:
    """Database connection manager."""

    def __init__(self):
        """Initialize database connection pool."""
        self.pool: ConnectionPool | None = None

    def connect(self) -> None:
        """Create connection pool with timeout settings."""
        if self.pool is not None:
            return

        # Add timeout parameters to connection string
        conninfo = f"{settings.database_url}?connect_timeout={settings.database_connect_timeout}"

        self.pool = ConnectionPool(
            conninfo=conninfo,
            min_size=2,
            max_size=10,
            kwargs={
                "row_factory": dict_row,
                "connect_timeout": settings.database_connect_timeout,
            },
            timeout=settings.database_pool_timeout,
        )

    def close(self) -> None:
        """Close connection pool."""
        if self.pool:
            self.pool.close()
            self.pool = None

    @contextmanager
    def get_connection(self) -> Generator[psycopg.Connection, None, None]:
        """
        Get a database connection from the pool.

        Yields:
            psycopg.Connection: Database connection

        Example:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM teams")
                    teams = cur.fetchall()
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        with self.pool.connection() as conn:
            yield conn

    def fetch_all(self, query: str, params: tuple = None) -> list[dict]:
        """
        Execute a query and fetch all results.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of dictionaries
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Set statement timeout on connection (PostgreSQL handles this)
                # Timeout is in milliseconds
                cur.execute(f"SET statement_timeout = {settings.database_query_timeout * 1000}")
                try:
                    cur.execute(query, params)
                    return cur.fetchall()
                except Exception as e:
                    # Reset timeout on error
                    try:
                        cur.execute("SET statement_timeout = 0")
                    except:
                        pass
                    raise

    def fetch_one(self, query: str, params: tuple = None) -> dict | None:
        """
        Execute a query and fetch one result.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Dictionary or None
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Set statement timeout on connection
                cur.execute(f"SET statement_timeout = {settings.database_query_timeout * 1000}")
                try:
                    cur.execute(query, params)
                    return cur.fetchone()
                except Exception as e:
                    # Reset timeout on error
                    try:
                        cur.execute("SET statement_timeout = 0")
                    except:
                        pass
                    raise


# Global database instance
db = Database()


def init_db() -> None:
    """Initialize database connection."""
    db.connect()


def close_db() -> None:
    """Close database connection."""
    db.close()


# Convenience functions for common queries

def fetch_teams() -> list[dict]:
    """Fetch all teams from database."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT team_id, team_code, school_name, mascot, conference,
                       talent_composite
                FROM teams
                ORDER BY school_name
            """)
            return cur.fetchall()


def fetch_games_by_week(season: int, week: int) -> list[dict]:
    """
    Fetch games for a specific week.
    
    Returns games with team information including:
    - All game fields (id, game_id, home_team_id, away_team_id, etc.)
    - home_team_name, home_team_code (from teams table)
    - away_team_name, away_team_code (from teams table)
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT g.*,
                       ht.school_name AS home_team_name,
                       ht.team_code AS home_team_code,
                       at.school_name AS away_team_name,
                       at.team_code AS away_team_code,
                       ht.school_name AS home_team,
                       at.school_name AS away_team
                FROM games g
                JOIN teams ht ON g.home_team_id = ht.id
                JOIN teams at ON g.away_team_id = at.id
                WHERE g.season = %s AND g.week = %s
                ORDER BY g.game_date
            """, (season, week))
            return cur.fetchall()


def fetch_team_stats(team_id: int, season: int) -> dict | None:
    """Fetch team season stats."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT *
                FROM team_season_stats
                WHERE team_id = %s AND season = %s
            """, (team_id, season))
            return cur.fetchone()


def fetch_latest_odds(game_id: int) -> list[dict]:
    """Fetch latest odds for a game."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (sportsbook_id, market_type, period)
                       *
                FROM odds
                WHERE game_id = %s
                ORDER BY sportsbook_id, market_type, period, fetched_at DESC
            """, (game_id,))
            return cur.fetchall()


def save_prediction(
    game_id: int,
    model_name: str,
    predicted_home_score: float,
    predicted_away_score: float,
    predicted_total: float,
    predicted_margin: float,
    confidence_score: float,
    consensus_spread: float | None = None,
    consensus_total: float | None = None,
    edge_spread: float | None = None,
    edge_total: float | None = None,
    recommend_bet: bool = False,
    recommended_bet_type: str | None = None,
    recommended_side: str | None = None,
    recommended_units: float | None = None,
    rationale: dict | None = None,
) -> int:
    """Save a prediction to the database."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO predictions (
                    game_id, model_name, predicted_home_score, predicted_away_score,
                    predicted_total, predicted_margin, confidence_score,
                    consensus_spread, consensus_total, edge_spread, edge_total,
                    recommend_bet, recommended_bet_type, recommended_side,
                    recommended_units, rationale
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                game_id, model_name, predicted_home_score, predicted_away_score,
                predicted_total, predicted_margin, confidence_score,
                consensus_spread, consensus_total, edge_spread, edge_total,
                recommend_bet, recommended_bet_type, recommended_side,
                recommended_units, rationale,
            ))
            result = cur.fetchone()
            conn.commit()
            return result["id"]
