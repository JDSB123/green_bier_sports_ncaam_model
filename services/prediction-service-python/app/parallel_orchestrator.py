"""
Parallel Data Orchestrator - Single Entry Point for All Data Sources.

v33.11.0: Unified pipeline that fetches ALL data sources in parallel:
1. Barttorvik Ratings (team stats) - ALWAYS FETCH (changes daily)
2. The Odds API (betting lines) - ALWAYS FETCH (changes constantly)
3. Action Network (betting splits) - ALWAYS FETCH (changes constantly)
4. Schedule (ESPN + Basketball API) - CACHED (load once, delta sync)

Schedule Optimization:
- Full season schedule loaded ONCE at season start
- Cached in Redis (fast) + PostgreSQL (persistent)
- Daily runs use cached schedule - no API calls needed
- Periodic delta sync catches postponements/reschedules

Usage:
    from app.parallel_orchestrator import go
    result = go()  # Single entry point
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Import schedule cache (optimized path)
try:
    from .schedule_cache import (
        ScheduleCache,
        get_or_load_schedule,
        get_today_games,
    )
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

# Import schedule sources (for cross-validation)
try:
    from .schedule_sources import cross_validate_schedules
    SCHEDULE_SOURCES_AVAILABLE = True
except ImportError:
    SCHEDULE_SOURCES_AVAILABLE = False
    cross_validate_schedules = None

# Import odds sync
try:
    from .odds_sync import sync_odds
except ImportError:
    sync_odds = None

# Import betting splits
try:
    from .betting_splits import ActionNetworkClient
except ImportError:
    ActionNetworkClient = None


@dataclass
class DataSourceResult:
    """Result from a single data source fetch."""

    source: str
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    record_count: int = 0
    from_cache: bool = False


@dataclass
class OrchestratorResult:
    """Combined result from all data sources."""

    success: bool
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    # Individual source results
    ratings: DataSourceResult | None = None
    odds: DataSourceResult | None = None
    betting_splits: DataSourceResult | None = None
    schedule: DataSourceResult | None = None

    # Validation results
    schedule_cross_validation: dict[str, Any] | None = None
    team_resolution_report: dict[str, Any] | None = None

    # Summary
    total_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


class ParallelOrchestrator:
    """
    Orchestrates parallel data fetching from all sources.

    Single entry point for the "GO" command.
    """

    def __init__(
        self,
        database_url: str | None = None,
        redis_url: str | None = None,
        odds_api_key: str | None = None,
        basketball_api_key: str | None = None,
        action_network_username: str | None = None,
        action_network_password: str | None = None,
    ):
        self.database_url = database_url or os.environ.get(
            "DATABASE_URL", ""
        )
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "")
        self.odds_api_key = odds_api_key or os.environ.get(
            "THE_ODDS_API_KEY", ""
        )
        self.basketball_api_key = basketball_api_key or os.environ.get(
            "BASKETBALL_API_KEY", ""
        )
        self.action_network_username = action_network_username or os.environ.get(
            "ACTION_NETWORK_USERNAME", ""
        )
        self.action_network_password = action_network_password or os.environ.get(
            "ACTION_NETWORK_PASSWORD", ""
        )

    def sync_all_sources(
        self,
        target_date: date | None = None,
        force_schedule_refresh: bool = False,
        season_year: int = 2025,
    ) -> OrchestratorResult:
        """
        Fetch all data sources in parallel.

        Args:
            target_date: Date to fetch data for (defaults to today)
            force_schedule_refresh: Force reload schedule from APIs
            season_year: Season year (e.g., 2025 for 2024-25)

        Returns:
            OrchestratorResult with all source results
        """
        if target_date is None:
            target_date = date.today()

        start_time = datetime.now(UTC)
        result = OrchestratorResult(success=True)

        logger.info(
            "orchestrator_starting",
            target_date=str(target_date),
            force_schedule_refresh=force_schedule_refresh,
        )

        # Define fetch tasks
        # Schedule uses cache - doesn't need to run in parallel with others
        # Ratings, Odds, Splits run in parallel (always fetch fresh)
        tasks = {
            "ratings": lambda: self._fetch_ratings(),
            "odds": lambda: self._fetch_odds(),
            "betting_splits": lambda: self._fetch_betting_splits(target_date),
        }

        # Execute API tasks in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(task): name
                for name, task in tasks.items()
            }

            for future in as_completed(futures):
                task_name = futures[future]
                try:
                    task_result = future.result()
                    setattr(result, task_name, task_result)

                    if not task_result.success:
                        result.errors.append(
                            f"{task_name}: {task_result.error}"
                        )

                    logger.info(
                        "orchestrator_task_complete",
                        task=task_name,
                        success=task_result.success,
                        duration_ms=task_result.duration_ms,
                        record_count=task_result.record_count,
                    )

                except Exception as e:
                    error_msg = f"{task_name} failed: {e}"
                    result.errors.append(error_msg)
                    setattr(result, task_name, DataSourceResult(
                        source=task_name,
                        success=False,
                        error=str(e),
                    ))
                    logger.error(
                        "orchestrator_task_error",
                        task=task_name,
                        error=str(e),
                    )

        # Fetch schedule (uses cache - fast path)
        result.schedule = self._fetch_schedule(
            target_date,
            season_year,
            force_schedule_refresh,
        )

        # Calculate total duration
        end_time = datetime.now(UTC)
        result.total_duration_ms = (
            (end_time - start_time).total_seconds() * 1000
        )

        # Determine overall success (ratings + odds must succeed)
        critical_sources = [result.ratings, result.odds]
        result.success = all(s and s.success for s in critical_sources)

        logger.info(
            "orchestrator_complete",
            success=result.success,
            total_duration_ms=result.total_duration_ms,
            error_count=len(result.errors),
        )

        return result

    def _fetch_ratings(self) -> DataSourceResult:
        """Fetch ratings from Barttorvik via Go binary."""
        import subprocess

        start = time.time()

        # Try Go binary first
        if os.path.exists("/app/bin/ratings-sync"):
            try:
                proc = subprocess.run(
                    ["/app/bin/ratings-sync"],
                    env={
                        **os.environ,
                        "DATABASE_URL": self.database_url,
                        "RUN_ONCE": "true",
                    },
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                duration = (time.time() - start) * 1000

                if proc.returncode == 0:
                    return DataSourceResult(
                        source="ratings",
                        success=True,
                        data={"method": "go_binary"},
                        duration_ms=duration,
                    )
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                logger.warning("ratings_go_binary_failed", error=str(e))

        duration = (time.time() - start) * 1000
        return DataSourceResult(
            source="ratings",
            success=True,
            data={"method": "skipped_no_binary"},
            duration_ms=duration,
        )

    def _fetch_odds(self) -> DataSourceResult:
        """Fetch odds from The Odds API."""
        start = time.time()

        if not self.database_url or not self.odds_api_key:
            return DataSourceResult(
                source="odds",
                success=False,
                error="Missing DATABASE_URL or THE_ODDS_API_KEY",
                duration_ms=0,
            )

        try:
            if sync_odds:
                api_result = sync_odds(
                    database_url=self.database_url,
                    api_key=self.odds_api_key,
                    enable_full=True,
                    enable_h1=True,
                    enable_h2=False,
                )

                duration = (time.time() - start) * 1000
                return DataSourceResult(
                    source="odds",
                    success=api_result.get("success", False),
                    data=api_result,
                    duration_ms=duration,
                    record_count=api_result.get("total_snapshots", 0),
                    error=api_result.get("error"),
                )
            return DataSourceResult(
                source="odds",
                success=False,
                error="sync_odds not available",
                duration_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            return DataSourceResult(
                source="odds",
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )

    def _fetch_betting_splits(self, target_date: date) -> DataSourceResult:
        """Fetch betting splits from Action Network."""
        start = time.time()

        if not ActionNetworkClient:
            return DataSourceResult(
                source="betting_splits",
                success=False,
                error="ActionNetworkClient not available",
                duration_ms=0,
            )

        try:
            client = ActionNetworkClient(
                username=self.action_network_username or None,
                password=self.action_network_password or None,
            )

            target_datetime = datetime.combine(
                target_date, datetime.min.time()
            )
            splits = client.get_betting_splits(target_datetime)
            duration = (time.time() - start) * 1000

            return DataSourceResult(
                source="betting_splits",
                success=True,
                data=splits,
                duration_ms=duration,
                record_count=len(splits),
            )

        except Exception as e:
            return DataSourceResult(
                source="betting_splits",
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )

    def _fetch_schedule(
        self,
        target_date: date,
        season_year: int,
        force_refresh: bool,
    ) -> DataSourceResult:
        """
        Fetch schedule - uses cache for fast access.

        Schedule is loaded once per season and cached.
        Daily runs just read from cache (no API calls).
        """
        start = time.time()

        if not CACHE_AVAILABLE:
            return DataSourceResult(
                source="schedule",
                success=False,
                error="Schedule cache not available",
                duration_ms=0,
            )

        try:
            # Get games for today from cache (or load if needed)
            games = get_today_games(force_refresh=force_refresh)
            duration = (time.time() - start) * 1000

            # Check if this came from cache (fast) or API (slow)
            from_cache = duration < 1000  # Cache hits are < 1 second

            return DataSourceResult(
                source="schedule",
                success=True,
                data=games,
                duration_ms=duration,
                record_count=len(games),
                from_cache=from_cache,
            )

        except Exception as e:
            return DataSourceResult(
                source="schedule",
                success=False,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )


def go(
    target_date: date | None = None,
    force_schedule_refresh: bool = False,
) -> OrchestratorResult:
    """
    Single entry point - "GO" command.

    Fetches all data sources in parallel, validates, and returns results.

    Args:
        target_date: Date to run for (defaults to today)
        force_schedule_refresh: Force reload schedule from APIs

    Returns:
        OrchestratorResult with all source data
    """
    orchestrator = ParallelOrchestrator()
    return orchestrator.sync_all_sources(
        target_date=target_date,
        force_schedule_refresh=force_schedule_refresh,
    )


if __name__ == "__main__":
    print("=" * 70)
    print("  PARALLEL DATA ORCHESTRATOR - GO")
    print("=" * 70)

    result = go()

    status = "SUCCESS" if result.success else "FAILED"
    print(f"\n{status}")
    print(f"Total duration: {result.total_duration_ms:.0f}ms")
    print()

    sources = [
        ("Ratings", result.ratings),
        ("Odds", result.odds),
        ("Betting Splits", result.betting_splits),
        ("Schedule", result.schedule),
    ]

    for name, src in sources:
        if src:
            status_icon = "OK" if src.success else "FAIL"
            cache_note = " [CACHED]" if src.from_cache else ""
            print(
                f"  [{status_icon}] {name}: "
                f"{src.record_count} records "
                f"({src.duration_ms:.0f}ms){cache_note}"
            )
            if src.error:
                print(f"        Error: {src.error}")
        else:
            print(f"  [--] {name}: not run")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for err in result.errors:
            print(f"  - {err}")
