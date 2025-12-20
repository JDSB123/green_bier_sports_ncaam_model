"""Database access layer."""
from src.db.database import db, fetch_games_by_week, fetch_teams, init_db

__all__ = ["db", "init_db", "fetch_teams", "fetch_games_by_week"]
