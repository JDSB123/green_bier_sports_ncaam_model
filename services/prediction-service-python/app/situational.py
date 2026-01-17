"""
Situational adjustments for NCAAM predictions.

Computes rest day differentials and back-to-back penalties.
"""
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def _ensure_tz_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (assume UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@dataclass
class RestInfo:
    """Rest information for a team."""
    team_name: str
    days_rest: int  # Days since last game (0 = B2B, 1 = 1 day rest, etc.)
    is_back_to_back: bool
    last_game_datetime: datetime | None = None

    @property
    def days_since_game(self) -> int:
        """Legacy alias used by models; equals days_rest."""
        return self.days_rest


@dataclass
class SituationalAdjustment:
    """Computed situational adjustments for a matchup."""
    home_rest_days: int
    away_rest_days: int
    rest_differential: int  # home_rest - away_rest
    spread_adjustment: float  # Points to add to spread (positive = helps home)
    total_adjustment: float  # Points to add to total (usually negative for tired teams)
    home_is_b2b: bool
    away_is_b2b: bool

    @property
    def any_b2b(self) -> bool:
        return self.home_is_b2b or self.away_is_b2b


class SituationalAdjuster:
    """
    Computes situational adjustments based on rest days.

    Research-based adjustments:
    - Back-to-back (0 days rest): -2.0 to -2.5 points
    - 1 day rest: -1.0 to -1.5 points
    - 2+ days rest: neutral (baseline)
    - Rest differential matters: +0.5 points per day advantage (capped)
    """

    def __init__(
        self,
        b2b_penalty: float = -2.25,
        one_day_penalty: float = -1.25,
        rest_diff_factor: float = 0.5,
        max_rest_diff_adj: float = 2.0,
        enabled: bool = True,
    ):
        self.b2b_penalty = b2b_penalty
        self.one_day_penalty = one_day_penalty
        self.rest_diff_factor = rest_diff_factor
        self.max_rest_diff_adj = max_rest_diff_adj
        self.enabled = enabled

    def compute_rest_info(
        self,
        team_name: str,
        game_datetime: datetime,
        game_history: list[dict],
    ) -> RestInfo:
        """
        Compute rest days for a team based on their game history.

        Args:
            team_name: Team name for logging
            game_datetime: Datetime of the game being predicted
            game_history: List of recent completed games for this team

        Returns:
            RestInfo with days of rest and B2B flag
        """
        if not game_history:
            # No history = assume well-rested (7+ days)
            return RestInfo(
                team_name=team_name,
                days_rest=7,
                is_back_to_back=False,
            )

        # Find most recent completed game before this one
        # Ensure game_datetime is timezone-aware for comparison
        game_datetime_aware = _ensure_tz_aware(game_datetime)

        last_game_dt = None
        for game in sorted(game_history, key=lambda g: g["commence_time"], reverse=True):
            game_time = game["commence_time"]
            if isinstance(game_time, str):
                game_time = datetime.fromisoformat(game_time.replace("Z", "+00:00"))

            # Ensure game_time is also timezone-aware
            game_time = _ensure_tz_aware(game_time)

            if game_time < game_datetime_aware:
                last_game_dt = game_time
                break

        if last_game_dt is None:
            return RestInfo(
                team_name=team_name,
                days_rest=7,
                is_back_to_back=False,
            )

        # Calculate days difference (both are now timezone-aware)
        time_diff = game_datetime_aware - last_game_dt
        days_rest = time_diff.days

        # B2B is same calendar day or next calendar day (< 36 hours)
        is_b2b = days_rest == 0 or (days_rest == 1 and time_diff.total_seconds() < 36 * 3600)

        return RestInfo(
            team_name=team_name,
            days_rest=days_rest,
            is_back_to_back=is_b2b,
            last_game_datetime=last_game_dt,
        )

    def compute_adjustment(
        self,
        home_rest: RestInfo,
        away_rest: RestInfo,
    ) -> SituationalAdjustment:
        """
        Compute spread and total adjustments based on rest.

        Returns:
            SituationalAdjustment with point adjustments
        """
        if not self.enabled:
            return SituationalAdjustment(
                home_rest_days=home_rest.days_rest,
                away_rest_days=away_rest.days_rest,
                rest_differential=0,
                spread_adjustment=0.0,
                total_adjustment=0.0,
                home_is_b2b=home_rest.is_back_to_back,
                away_is_b2b=away_rest.is_back_to_back,
            )

        # Individual team fatigue penalties
        home_fatigue = 0.0
        away_fatigue = 0.0

        if home_rest.is_back_to_back:
            home_fatigue = self.b2b_penalty
        elif home_rest.days_rest == 1:
            home_fatigue = self.one_day_penalty

        if away_rest.is_back_to_back:
            away_fatigue = self.b2b_penalty
        elif away_rest.days_rest == 1:
            away_fatigue = self.one_day_penalty

        # Rest differential advantage (home - away)
        rest_diff = home_rest.days_rest - away_rest.days_rest
        rest_diff_adj = min(
            self.max_rest_diff_adj,
            max(-self.max_rest_diff_adj, rest_diff * self.rest_diff_factor),
        )

        # Spread adjustment: positive = helps home team
        # Home fatigue hurts home (negative), away fatigue helps home (positive)
        spread_adj = -home_fatigue + away_fatigue + rest_diff_adj

        # Total adjustment: tired teams score less
        # Both teams being tired = lower total
        total_adj = (home_fatigue + away_fatigue) * 0.3  # Dampened effect on total

        logger.debug(
            f"Rest adjustment: home={home_rest.days_rest}d (b2b={home_rest.is_back_to_back}), "
            f"away={away_rest.days_rest}d (b2b={away_rest.is_back_to_back}), "
            f"spread_adj={spread_adj:+.2f}, total_adj={total_adj:+.2f}"
        )

        return SituationalAdjustment(
            home_rest_days=home_rest.days_rest,
            away_rest_days=away_rest.days_rest,
            rest_differential=rest_diff,
            spread_adjustment=round(spread_adj, 2),
            total_adjustment=round(total_adj, 2),
            home_is_b2b=home_rest.is_back_to_back,
            away_is_b2b=away_rest.is_back_to_back,
        )
