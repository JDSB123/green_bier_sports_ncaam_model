"""
CST Timezone Standardization Utilities.

ALL timestamps in the backtest system MUST go through these functions.
CST (America/Chicago) is the canonical timezone for all operations.

Why CST?
- NCAAM games are played across US timezones
- CST is central to the country (fair baseline)
- Season boundaries (Nov 1 -> next season) must be consistent
- Late-night games on West Coast could be "next day" in EST

Usage:
    from testing.production_parity.timezone_utils import (
        to_cst, parse_date_to_cst, get_season_for_game, now_cst, format_cst
    )

    # Convert datetime to CST
    cst_dt = to_cst(some_datetime)

    # Parse date string to CST
    cst_dt = parse_date_to_cst("2024-01-15")

    # Get season for a game date
    season = get_season_for_game("2024-11-15")  # Returns 2025
"""
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Union

# =============================================================================
# CANONICAL TIMEZONES
# =============================================================================

CST = ZoneInfo("America/Chicago")
UTC = ZoneInfo("UTC")


# =============================================================================
# CORE CONVERSION FUNCTIONS
# =============================================================================

def to_cst(dt: datetime) -> datetime:
    """
    Convert any datetime to CST.

    Args:
        dt: Datetime (naive assumed UTC, or timezone-aware)

    Returns:
        Datetime in CST timezone

    Examples:
        >>> from datetime import datetime
        >>> naive_dt = datetime(2024, 1, 15, 12, 0, 0)
        >>> cst_dt = to_cst(naive_dt)  # Assumes UTC, converts to CST
    """
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(CST)


def parse_date_to_cst(date_str: str) -> datetime:
    """
    Parse date/datetime string and return CST datetime.

    Handles:
    - "2024-01-15" (YYYY-MM-DD) - assumes midnight UTC
    - "2024-01-15T19:00:00Z" (ISO with Z)
    - "2024-01-15T19:00:00+00:00" (ISO with offset)

    Args:
        date_str: Date string in various formats

    Returns:
        Datetime in CST timezone

    Examples:
        >>> dt = parse_date_to_cst("2024-01-15")
        >>> dt = parse_date_to_cst("2024-01-15T19:00:00Z")
    """
    date_str = date_str.strip()

    if len(date_str) == 10:
        # YYYY-MM-DD format - assume midnight UTC
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dt = dt.replace(tzinfo=UTC)
    else:
        # ISO format with timezone
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

    return to_cst(dt)


def get_cst_date(dt: datetime) -> date:
    """
    Get the CST date from a datetime.

    Args:
        dt: Any datetime

    Returns:
        Date in CST timezone
    """
    return to_cst(dt).date()


def get_cst_date_str(dt: datetime) -> str:
    """
    Get the CST date as YYYY-MM-DD string.

    Args:
        dt: Any datetime

    Returns:
        Date string in YYYY-MM-DD format (CST)
    """
    return to_cst(dt).strftime("%Y-%m-%d")


# =============================================================================
# SEASON DETERMINATION (CST-BASED)
# =============================================================================

def cst_date_to_season(cst_date: date) -> int:
    """
    Determine NCAAM season from CST date.

    Season rule (based on CST):
    - Nov-Dec YYYY -> Season YYYY+1
    - Jan-Apr YYYY -> Season YYYY

    Args:
        cst_date: Date (should already be in CST context)

    Returns:
        Season year (e.g., 2025 for the 2024-25 season)

    Examples:
        >>> from datetime import date
        >>> cst_date_to_season(date(2024, 11, 15))  # Returns 2025
        >>> cst_date_to_season(date(2025, 3, 15))   # Returns 2025
    """
    if cst_date.month >= 11:  # Nov-Dec
        return cst_date.year + 1
    return cst_date.year


def get_season_for_game(date_str: str) -> int:
    """
    Get the NCAAM season for a game date.

    Converts to CST first, then determines season.

    Args:
        date_str: Game date string (any format supported by parse_date_to_cst)

    Returns:
        Season year

    Examples:
        >>> get_season_for_game("2024-11-15")  # Returns 2025 (Nov = next season)
        >>> get_season_for_game("2025-03-15")  # Returns 2025
    """
    cst_dt = parse_date_to_cst(date_str)
    return cst_date_to_season(cst_dt.date())


def get_ratings_season_for_game(date_str: str) -> int:
    """
    Get the Barttorvik ratings season to use for a game (anti-leakage).

    Returns Season N-1 for Season N games (prior season's final ratings).

    Args:
        date_str: Game date string

    Returns:
        Ratings season to use (game_season - 1)

    Examples:
        >>> get_ratings_season_for_game("2024-11-15")  # Returns 2024 (use 2024 ratings for 2025 season games)
    """
    game_season = get_season_for_game(date_str)
    return game_season - 1


# =============================================================================
# TIMESTAMP UTILITIES
# =============================================================================

def now_cst() -> datetime:
    """
    Get current datetime in CST.

    Returns:
        Current datetime in CST timezone
    """
    return datetime.now(CST)


def format_cst(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S CST") -> str:
    """
    Format datetime as CST string.

    Args:
        dt: Any datetime
        fmt: strftime format string (default includes "CST" suffix)

    Returns:
        Formatted string in CST
    """
    return to_cst(dt).strftime(fmt)


def format_cst_date(dt: datetime) -> str:
    """
    Format datetime as CST date string (YYYY-MM-DD).

    Args:
        dt: Any datetime

    Returns:
        Date string in YYYY-MM-DD format (CST)
    """
    return to_cst(dt).strftime("%Y-%m-%d")


# =============================================================================
# VALIDATION
# =============================================================================

def validate_cst_aware(dt: datetime) -> bool:
    """
    Check if datetime is CST-aware.

    Args:
        dt: Datetime to check

    Returns:
        True if datetime has CST timezone
    """
    if dt.tzinfo is None:
        return False
    return dt.tzinfo == CST or str(dt.tzinfo) == "America/Chicago"
