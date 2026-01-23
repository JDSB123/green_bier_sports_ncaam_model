"""
Schedule Cache - Persistent Storage for Season Schedules

The full season schedule only needs to be fetched once and cached.
Subsequent runs check for changes (postponements, reschedules) via delta sync.

Storage Options:
1. Redis (preferred for distributed/container environments)
2. PostgreSQL (fallback, also serves as permanent record)

v33.11.0: Optimized schedule fetching - load once, sync changes.
"""

import contextlib
import hashlib
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import structlog

from .schedule_sources import ScheduledGame

logger = structlog.get_logger(__name__)

try:
    import redis
except ImportError:
    redis = None

try:
    from sqlalchemy import create_engine, text
except ImportError:
    create_engine = None

# Cache keys
SCHEDULE_CACHE_KEY = "ncaam:schedule:season:{season}"
SCHEDULE_HASH_KEY = "ncaam:schedule:hash:{season}"
SCHEDULE_LAST_SYNC_KEY = "ncaam:schedule:last_sync:{season}"

# Cache TTL: 24 hours for schedule data (refreshed daily)
SCHEDULE_CACHE_TTL = 24 * 60 * 60


def _build_redis_url_from_env() -> str:
    """Build a Redis URL from environment variables and an optional secret file.

    Priority:
    1) REDIS_URL (explicit)
    2) REDIS_PASSWORD_FILE + REDIS_HOST/REDIS_PORT/REDIS_DB
    3) REDIS_HOST/REDIS_PORT/REDIS_DB without auth
    """

    explicit = (os.getenv("REDIS_URL") or "").strip()
    if explicit:
        return explicit

    host = (os.getenv("REDIS_HOST") or "").strip() or "redis"
    port = (os.getenv("REDIS_PORT") or "").strip() or "6379"
    db = (os.getenv("REDIS_DB") or "").strip() or "0"

    pw_file = (os.getenv("REDIS_PASSWORD_FILE") or "").strip()
    password: str | None = None
    if pw_file:
        with contextlib.suppress(Exception):
            p = Path(pw_file)
            if p.exists():
                val = p.read_text(encoding="utf-8").strip()
                if val:
                    password = val

    if password:
        return f"redis://:{quote(password)}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


class ScheduleCache:
    """
    Manages cached season schedule data.

    Uses Redis for fast access, PostgreSQL for persistence.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        database_url: str | None = None,
    ):
        self.redis_url = redis_url or _build_redis_url_from_env()
        self.database_url = database_url or os.environ.get("DATABASE_URL", "")

        self._redis_client = None
        self._db_engine = None

        # Initialize connections
        self._init_redis()
        self._init_db()

    def _init_redis(self):
        """Initialize Redis connection."""
        if not redis or not self.redis_url:
            logger.info("schedule_cache_redis_disabled", reason="no redis URL or library")
            return

        try:
            self._redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            # Test connection
            self._redis_client.ping()
            logger.info("schedule_cache_redis_connected")
        except Exception as e:
            logger.warning("schedule_cache_redis_failed", error=str(e))
            self._redis_client = None

    def _init_db(self):
        """Initialize database connection."""
        if not create_engine or not self.database_url:
            logger.info("schedule_cache_db_disabled", reason="no database URL or sqlalchemy")
            return

        try:
            self._db_engine = create_engine(self.database_url, pool_pre_ping=True)
            # Ensure table exists
            self._ensure_schedule_table()
            logger.info("schedule_cache_db_connected")
        except Exception as e:
            logger.warning("schedule_cache_db_failed", error=str(e))
            self._db_engine = None

    def _ensure_schedule_table(self):
        """Create schedule cache table if it doesn't exist."""
        if not self._db_engine:
            return

        create_sql = text("""
            CREATE TABLE IF NOT EXISTS schedule_cache (
                id SERIAL PRIMARY KEY,
                season INTEGER NOT NULL,
                source VARCHAR(50) NOT NULL,
                external_id VARCHAR(100) NOT NULL,
                game_date DATE NOT NULL,
                game_time TIMESTAMPTZ,
                home_team_raw VARCHAR(200) NOT NULL,
                away_team_raw VARCHAR(200) NOT NULL,
                home_team VARCHAR(200),
                away_team VARCHAR(200),
                venue VARCHAR(300),
                is_neutral BOOLEAN DEFAULT FALSE,
                status VARCHAR(50) DEFAULT 'scheduled',
                home_score INTEGER,
                away_score INTEGER,
                data_hash VARCHAR(64),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(season, source, external_id)
            );

            CREATE INDEX IF NOT EXISTS idx_schedule_cache_season_date
            ON schedule_cache(season, game_date);

            CREATE INDEX IF NOT EXISTS idx_schedule_cache_status
            ON schedule_cache(status);
        """)

        with self._db_engine.connect() as conn:
            conn.execute(create_sql)
            conn.commit()

    def _game_to_dict(self, game: ScheduledGame) -> dict[str, Any]:
        """Convert ScheduledGame to serializable dict."""
        return {
            "external_id": game.external_id,
            "source": game.source,
            "home_team_raw": game.home_team_raw,
            "away_team_raw": game.away_team_raw,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "game_date": game.game_date.isoformat() if game.game_date else None,
            "game_time": game.game_time.isoformat() if game.game_time else None,
            "venue": game.venue,
            "is_neutral": game.is_neutral,
            "status": game.status,
            "home_score": game.home_score,
            "away_score": game.away_score,
            "home_conference": game.home_conference,
            "away_conference": game.away_conference,
        }

    def _dict_to_game(self, data: dict[str, Any]) -> ScheduledGame:
        """Convert dict back to ScheduledGame."""
        game_date = data.get("game_date")
        if isinstance(game_date, str):
            game_date = date.fromisoformat(game_date)
        elif game_date is None:
            game_date = date.today()

        game_time = data.get("game_time")
        if isinstance(game_time, str):
            game_time = datetime.fromisoformat(game_time)

        return ScheduledGame(
            external_id=data.get("external_id", ""),
            source=data.get("source", ""),
            home_team_raw=data.get("home_team_raw", ""),
            away_team_raw=data.get("away_team_raw", ""),
            home_team=data.get("home_team"),
            away_team=data.get("away_team"),
            game_date=game_date,
            game_time=game_time,
            venue=data.get("venue"),
            is_neutral=data.get("is_neutral", False),
            status=data.get("status", "scheduled"),
            home_score=data.get("home_score"),
            away_score=data.get("away_score"),
            home_conference=data.get("home_conference"),
            away_conference=data.get("away_conference"),
        )

    def _compute_hash(self, games: list[ScheduledGame]) -> str:
        """Compute hash of schedule for change detection."""
        # Sort by external_id for consistent hashing
        sorted_games = sorted(games, key=lambda g: g.external_id)
        data = json.dumps([self._game_to_dict(g) for g in sorted_games], sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def get_cached_schedule(
        self,
        season: int,
        source: str | None = None,
    ) -> tuple[list[ScheduledGame] | None, str | None, datetime | None]:
        """
        Get cached schedule for a season.

        Returns:
            Tuple of (games, hash, last_sync_time) or (None, None, None) if not cached
        """
        cache_key = SCHEDULE_CACHE_KEY.format(season=season)
        hash_key = SCHEDULE_HASH_KEY.format(season=season)
        sync_key = SCHEDULE_LAST_SYNC_KEY.format(season=season)

        # Try Redis first
        if self._redis_client:
            try:
                cached = self._redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    games = [self._dict_to_game(g) for g in data]

                    if source:
                        games = [g for g in games if g.source == source]

                    cached_hash = self._redis_client.get(hash_key)
                    last_sync_str = self._redis_client.get(sync_key)
                    last_sync = None
                    if last_sync_str:
                        last_sync = datetime.fromisoformat(last_sync_str)

                    logger.info(
                        "schedule_cache_redis_hit",
                        season=season,
                        games=len(games),
                    )
                    return games, cached_hash, last_sync
            except Exception as e:
                logger.warning("schedule_cache_redis_get_failed", error=str(e))

        # Fall back to database
        if self._db_engine:
            try:
                games = self._get_from_db(season, source)
                if games:
                    logger.info(
                        "schedule_cache_db_hit",
                        season=season,
                        games=len(games),
                    )
                    return games, self._compute_hash(games), None
            except Exception as e:
                logger.warning("schedule_cache_db_get_failed", error=str(e))

        return None, None, None

    def _get_from_db(
        self,
        season: int,
        source: str | None = None,
    ) -> list[ScheduledGame]:
        """Get schedule from database."""
        if not self._db_engine:
            return []

        if source:
            query = text("""
                SELECT * FROM schedule_cache
                WHERE season = :season AND source = :source
                ORDER BY game_date, game_time
            """)
            params = {"season": season, "source": source}
        else:
            query = text("""
                SELECT * FROM schedule_cache
                WHERE season = :season
                ORDER BY game_date, game_time
            """)
            params = {"season": season}

        with self._db_engine.connect() as conn:
            result = conn.execute(query, params)
            rows = result.fetchall()

        games = []
        for row in rows:
            games.append(ScheduledGame(
                external_id=row.external_id,
                source=row.source,
                home_team_raw=row.home_team_raw,
                away_team_raw=row.away_team_raw,
                home_team=row.home_team,
                away_team=row.away_team,
                game_date=row.game_date,
                game_time=row.game_time,
                venue=row.venue,
                is_neutral=row.is_neutral or False,
                status=row.status or "scheduled",
                home_score=row.home_score,
                away_score=row.away_score,
            ))

        return games

    def save_schedule(
        self,
        season: int,
        games: list[ScheduledGame],
    ) -> bool:
        """
        Save schedule to cache (both Redis and DB).

        Returns True if successful.
        """
        if not games:
            return True

        cache_key = SCHEDULE_CACHE_KEY.format(season=season)
        hash_key = SCHEDULE_HASH_KEY.format(season=season)
        sync_key = SCHEDULE_LAST_SYNC_KEY.format(season=season)

        data = [self._game_to_dict(g) for g in games]
        schedule_hash = self._compute_hash(games)
        now = datetime.now(UTC)

        success = True

        # Save to Redis
        if self._redis_client:
            try:
                pipe = self._redis_client.pipeline()
                pipe.set(cache_key, json.dumps(data), ex=SCHEDULE_CACHE_TTL)
                pipe.set(hash_key, schedule_hash, ex=SCHEDULE_CACHE_TTL)
                pipe.set(sync_key, now.isoformat(), ex=SCHEDULE_CACHE_TTL)
                pipe.execute()
                logger.info("schedule_cache_redis_saved", season=season, games=len(games))
            except Exception as e:
                logger.warning("schedule_cache_redis_save_failed", error=str(e))
                success = False

        # Save to database
        if self._db_engine:
            try:
                self._save_to_db(season, games)
                logger.info("schedule_cache_db_saved", season=season, games=len(games))
            except Exception as e:
                logger.warning("schedule_cache_db_save_failed", error=str(e))
                success = False

        return success

    def _save_to_db(self, season: int, games: list[ScheduledGame]):
        """Save schedule to database using upsert."""
        if not self._db_engine:
            return

        upsert_sql = text("""
            INSERT INTO schedule_cache (
                season, source, external_id, game_date, game_time,
                home_team_raw, away_team_raw, home_team, away_team,
                venue, is_neutral, status, home_score, away_score,
                data_hash, updated_at
            ) VALUES (
                :season, :source, :external_id, :game_date, :game_time,
                :home_team_raw, :away_team_raw, :home_team, :away_team,
                :venue, :is_neutral, :status, :home_score, :away_score,
                :data_hash, NOW()
            )
            ON CONFLICT (season, source, external_id) DO UPDATE SET
                game_date = EXCLUDED.game_date,
                game_time = EXCLUDED.game_time,
                home_team_raw = EXCLUDED.home_team_raw,
                away_team_raw = EXCLUDED.away_team_raw,
                home_team = EXCLUDED.home_team,
                away_team = EXCLUDED.away_team,
                venue = EXCLUDED.venue,
                is_neutral = EXCLUDED.is_neutral,
                status = EXCLUDED.status,
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score,
                data_hash = EXCLUDED.data_hash,
                updated_at = NOW()
        """)

        with self._db_engine.connect() as conn:
            for game in games:
                game_dict = self._game_to_dict(game)
                game_hash = hashlib.sha256(
                    json.dumps(game_dict, sort_keys=True).encode()
                ).hexdigest()[:16]

                conn.execute(upsert_sql, {
                    "season": season,
                    "source": game.source,
                    "external_id": game.external_id,
                    "game_date": game.game_date,
                    "game_time": game.game_time,
                    "home_team_raw": game.home_team_raw,
                    "away_team_raw": game.away_team_raw,
                    "home_team": game.home_team,
                    "away_team": game.away_team,
                    "venue": game.venue,
                    "is_neutral": game.is_neutral,
                    "status": game.status,
                    "home_score": game.home_score,
                    "away_score": game.away_score,
                    "data_hash": game_hash,
                })
            conn.commit()

    def get_schedule_changes(
        self,
        season: int,
        new_games: list[ScheduledGame],
    ) -> dict[str, list[ScheduledGame]]:
        """
        Compare new games with cached schedule to find changes.

        Returns dict with:
        - added: Games in new but not in cache
        - removed: Games in cache but not in new
        - changed: Games that exist in both but have different data
        - unchanged: Games that are identical
        """
        cached_games, _, _ = self.get_cached_schedule(season)

        if not cached_games:
            return {
                "added": new_games,
                "removed": [],
                "changed": [],
                "unchanged": [],
            }

        # Build lookup by external_id
        cached_by_id = {g.external_id: g for g in cached_games}
        new_by_id = {g.external_id: g for g in new_games}

        added = []
        removed = []
        changed = []
        unchanged = []

        # Find added and changed
        for ext_id, new_game in new_by_id.items():
            if ext_id not in cached_by_id:
                added.append(new_game)
            else:
                cached_game = cached_by_id[ext_id]
                if self._games_differ(cached_game, new_game):
                    changed.append(new_game)
                else:
                    unchanged.append(new_game)

        # Find removed
        for ext_id, cached_game in cached_by_id.items():
            if ext_id not in new_by_id:
                removed.append(cached_game)

        return {
            "added": added,
            "removed": removed,
            "changed": changed,
            "unchanged": unchanged,
        }

    def _games_differ(self, g1: ScheduledGame, g2: ScheduledGame) -> bool:
        """Check if two games have different data (ignoring resolved names)."""
        return (
            g1.game_date != g2.game_date or
            g1.status != g2.status or
            g1.home_score != g2.home_score or
            g1.away_score != g2.away_score or
            g1.is_neutral != g2.is_neutral
        )

    def needs_full_sync(self, season: int, max_age_hours: int = 24) -> bool:
        """
        Check if we need a full sync (vs delta sync).

        Full sync needed if:
        - No cached data exists
        - Last sync was more than max_age_hours ago
        """
        _, _, last_sync = self.get_cached_schedule(season)

        if last_sync is None:
            return True

        age = datetime.now(UTC) - last_sync
        return age > timedelta(hours=max_age_hours)

    def get_games_for_date(
        self,
        target_date: date,
        season: int | None = None,
    ) -> list[ScheduledGame]:
        """
        Get cached games for a specific date.

        This is the fast path - no API calls needed for daily runs
        once schedule is cached.
        """
        if season is None:
            # Determine season from date
            # Season 2025 = Nov 2024 - Apr 2025
            season = target_date.year + 1 if target_date.month >= 11 else target_date.year

        all_games, _, _ = self.get_cached_schedule(season)

        if not all_games:
            return []

        return [g for g in all_games if g.game_date == target_date]


def get_or_load_schedule(
    season: int,
    force_refresh: bool = False,
) -> list[ScheduledGame]:
    """
    Get schedule from cache or load from APIs if needed.

    This is the main entry point for schedule data:
    1. Check cache
    2. If cache miss or stale, fetch from APIs
    3. Save to cache
    4. Return games
    """
    from .schedule_sources import cross_validate_schedules, fetch_schedules_parallel

    cache = ScheduleCache()

    # Check if we need to fetch
    if not force_refresh and not cache.needs_full_sync(season):
        games, _, _ = cache.get_cached_schedule(season)
        if games:
            logger.info("schedule_using_cache", season=season, games=len(games))
            return games

    # Fetch from both sources in parallel
    logger.info("schedule_fetching_from_apis", season=season)
    espn_games, bball_games = fetch_schedules_parallel(season_year=season)

    # Cross-validate
    validation = cross_validate_schedules(espn_games, bball_games)
    logger.info(
        "schedule_cross_validated",
        matched=validation["matched"],
        espn_only=validation["espn_only"],
        bball_only=validation["bball_only"],
        match_rate=validation["match_rate"],
    )

    # Merge: use ESPN as primary, add Basketball API only games
    all_games = espn_games.copy()
    espn_keys = {f"{g.game_date}:{g.home_team_raw}:{g.away_team_raw}" for g in espn_games}

    for game in bball_games:
        key = f"{game.game_date}:{game.home_team_raw}:{game.away_team_raw}"
        if key not in espn_keys:
            all_games.append(game)

    # Save to cache
    cache.save_schedule(season, all_games)

    return all_games


def get_today_games(force_refresh: bool = False) -> list[ScheduledGame]:
    """
    Get games for today from cache.

    Fast path for daily predictions - uses cached schedule.
    """
    today = date.today()

    # Determine season
    season = today.year + 1 if today.month >= 11 else today.year

    cache = ScheduleCache()

    # First check if we have cached data
    games = cache.get_games_for_date(today, season)

    if games and not force_refresh:
        logger.info("schedule_today_from_cache", date=str(today), games=len(games))
        return games

    # Need to load schedule
    _ = get_or_load_schedule(season, force_refresh=force_refresh)

    # Now get today's games from cache
    return cache.get_games_for_date(today, season)


if __name__ == "__main__":
    print("=" * 60)
    print("Schedule Cache Test")
    print("=" * 60)

    # Test getting today's games
    today = date.today()
    print(f"\nGetting games for {today}...")

    games = get_today_games()
    print(f"Found {len(games)} games")

    for g in games[:10]:
        print(f"  {g.away_team_raw} @ {g.home_team_raw} ({g.status})")

    if len(games) > 10:
        print(f"  ... and {len(games) - 10} more")
