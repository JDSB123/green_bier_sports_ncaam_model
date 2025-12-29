"""
Score sync + bet settlement + performance reporting.

This is intentionally "manual-trigger friendly":
- `run_today.py` can call into this module at the start of a run to:
  - Pull recent final scores from The Odds API `/scores`
  - Update `games` rows (status + final score)
  - Settle any pending/placed bets in `betting_recommendations`
  - Print a CLV/ROI report grouped by market

Important limitations:
- We can only settle 1H markets if halftime scores are present in `games.home_score_1h`
  and `games.away_score_1h`. Halftime scores are synced from ESPN; unresolved team names
  or missing linescores will prevent settlement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

import requests
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.odds_api_client import OddsApiClient, OddsApiError

ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"
ESPN_DEFAULT_GROUP = "50"
ESPN_FALLBACK_GROUPS = (ESPN_DEFAULT_GROUP, None)


@dataclass
class ScoreSyncSummary:
    fetched_events: int
    completed_events: int
    updated_games: int
    missing_games: int


@dataclass
class SettlementSummary:
    settled: int
    wins: int
    losses: int
    pushes: int
    skipped_missing_scores_1h: int
    missing_closing_line: int


@dataclass
class HalftimeSyncSummary:
    fetched_events: int
    updated_games: int
    missing_games: int
    missing_scores: int





def _profit_per_unit(odds: int) -> float:
    """Profit (not return) per 1 unit stake if the bet wins."""
    if odds >= 0:
        return odds / 100.0
    return 100.0 / abs(odds)


def sync_final_scores(engine: Engine, days_from: int = 3, sport_key: Optional[str] = None) -> ScoreSyncSummary:
    """
    Pull recent scores from The Odds API and update `games` final scores/status.
    """
    client = OddsApiClient(sport_key=sport_key)
    events = client.get_scores(days_from=days_from)

    fetched = len(events)
    completed = 0
    updated = 0
    missing = 0

    update_stmt = text(
        """
        UPDATE games
        SET
            status = 'completed',
            home_score = :home_score,
            away_score = :away_score,
            updated_at = NOW()
        WHERE external_id = :external_id
        """
    )

    with engine.begin() as conn:
        for ev in events:
            if not ev or not isinstance(ev, dict):
                continue

            external_id = ev.get("id")
            if not external_id:
                continue

            if not ev.get("completed"):
                continue

            scores = ev.get("scores") or []
            if not isinstance(scores, list) or len(scores) < 2:
                continue

            home_team = ev.get("home_team")
            away_team = ev.get("away_team")
            if not home_team or not away_team:
                continue

            score_map: Dict[str, Optional[int]] = {}
            for s in scores:
                if not isinstance(s, dict):
                    continue
                name = s.get("name")
                val = s.get("score")
                if not name or val is None:
                    continue
                try:
                    score_map[name] = int(val)
                except (TypeError, ValueError):
                    continue

            home_score = score_map.get(home_team)
            away_score = score_map.get(away_team)
            if home_score is None or away_score is None:
                # Some feeds may present different names; skip rather than corrupting.
                continue

            completed += 1
            res = conn.execute(
                update_stmt,
                {"external_id": external_id, "home_score": home_score, "away_score": away_score},
            )
            if (res.rowcount or 0) > 0:
                updated += 1
            else:
                missing += 1

    return ScoreSyncSummary(
        fetched_events=fetched,
        completed_events=completed,
        updated_games=updated,
        missing_games=missing,
    )


def _resolve_team_canonical(engine: Engine, name: str) -> Optional[str]:
    if not name:
        return None
    stmt = text("SELECT resolve_team_name(:name)")
    with engine.begin() as conn:
        row = conn.execute(stmt, {"name": name}).fetchone()
        if not row:
            return None
        return row[0]


def _upsert_team_alias(engine: Engine, canonical: str, alias: str, source: str) -> None:
    if not canonical or not alias:
        return
    if canonical.strip().lower() == alias.strip().lower():
        return
    stmt = text(
        """
        INSERT INTO team_aliases (team_id, alias, source)
        SELECT id, :alias, :source
        FROM teams
        WHERE canonical_name = :canonical
        ON CONFLICT (alias, source) DO NOTHING
        """
    )
    with engine.begin() as conn:
        conn.execute(stmt, {"alias": alias, "source": source, "canonical": canonical})


def _fetch_espn_scoreboard(target_date: date, group: Optional[str] = ESPN_DEFAULT_GROUP) -> list[dict]:
    params = {
        "dates": target_date.strftime("%Y%m%d"),
        "groups": group,
        "limit": 500,
    }
    if group is None:
        params.pop("groups", None)
    resp = requests.get(ESPN_SCOREBOARD_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("events", []) or []

def _fetch_espn_events(target_date: date, groups: tuple[Optional[str], ...] = ESPN_FALLBACK_GROUPS) -> list[dict]:
    events: dict[str, dict] = {}
    for group in groups:
        try:
            for event in _fetch_espn_scoreboard(target_date, group=group):
                event_id = event.get("id")
                if not event_id:
                    continue
                if event_id not in events:
                    events[event_id] = event
                else:
                    if _event_has_1h_scores(event) and not _event_has_1h_scores(events[event_id]):
                        events[event_id] = event
        except requests.RequestException:
            continue
    return list(events.values())


def _fetch_espn_summary(event_id: str) -> Optional[dict]:
    resp = requests.get(ESPN_SUMMARY_URL, params={"event": event_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _coerce_int(value: Optional[object]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _first_half_from_linescores(lines: list[dict]) -> Optional[int]:
    if not lines:
        return None
    for ls in lines:
        if ls.get("period") == 1:
            return _coerce_int(ls.get("value") or ls.get("displayValue"))
    return _coerce_int(lines[0].get("value") or lines[0].get("displayValue"))


def _extract_scores_from_competitors(competitors: list[dict]) -> tuple[Optional[str], Optional[str], Optional[int], Optional[int]]:
    home = away = None
    home_1h = away_1h = None
    for team in competitors:
        home_away = team.get("homeAway")
        team_info = team.get("team") or {}
        name = team_info.get("displayName") or team_info.get("name") or team.get("displayName")
        if not name:
            continue
        lines = team.get("linescores") or []
        first_half = _first_half_from_linescores(lines)
        if home_away == "home":
            home = name
            home_1h = first_half
        elif home_away == "away":
            away = name
            away_1h = first_half
    return home, away, home_1h, away_1h


def _event_has_1h_scores(event: dict) -> bool:
    comp = (event.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    home, away, home_1h, away_1h = _extract_scores_from_competitors(competitors)
    return bool(home and away and home_1h is not None and away_1h is not None)


def _extract_espn_1h_scores(event: dict) -> Optional[dict]:
    comp = (event.get("competitions") or [{}])[0]
    competitors = comp.get("competitors") or []
    event_date = comp.get("date") or event.get("date")

    home, away, home_1h, away_1h = _extract_scores_from_competitors(competitors)

    if (home_1h is None or away_1h is None) and event.get("id"):
        try:
            summary = _fetch_espn_summary(event["id"])
        except requests.RequestException:
            summary = None
        if summary:
            header_comp = (summary.get("header", {}).get("competitions") or [{}])[0]
            summary_competitors = header_comp.get("competitors") or []
            event_date = event_date or header_comp.get("date")
            home, away, home_1h, away_1h = _extract_scores_from_competitors(summary_competitors)

    if not home or not away:
        return None

    return {
        "home_team": home,
        "away_team": away,
        "home_score_1h": home_1h,
        "away_score_1h": away_1h,
        "event_date": event_date,
    }


def sync_halftime_scores(engine: Engine, days_from: int = 3, group: str = ESPN_DEFAULT_GROUP) -> HalftimeSyncSummary:
    """
    Pull halftime (1H) scores from ESPN and update games.home_score_1h/away_score_1h.
    """
    cst = ZoneInfo("America/Chicago")
    today_cst = datetime.now(cst).date()

    fetched_events = 0
    updated = 0
    missing_games = 0
    missing_scores = 0

    update_stmt = text(
        """
        UPDATE games g
        SET
            home_score_1h = :home_score_1h,
            away_score_1h = :away_score_1h,
            updated_at = NOW()
        FROM teams ht, teams at
        WHERE g.home_team_id = ht.id
          AND g.away_team_id = at.id
          AND ht.canonical_name = :home_canonical
          AND at.canonical_name = :away_canonical
          AND DATE(g.commence_time AT TIME ZONE 'America/Chicago') = :game_date
          AND (g.home_score_1h IS NULL OR g.away_score_1h IS NULL)
        """
    )

    for offset in range(days_from + 1):
        target_date = today_cst - timedelta(days=offset)
        try:
            events = _fetch_espn_events(target_date, groups=(group, None))
        except requests.RequestException:
            continue

        fetched_events += len(events)
        for event in events:
            parsed = _extract_espn_1h_scores(event)
            if not parsed:
                continue
            if parsed["home_score_1h"] is None or parsed["away_score_1h"] is None:
                missing_scores += 1
                continue

            home_canonical = _resolve_team_canonical(engine, parsed["home_team"])
            away_canonical = _resolve_team_canonical(engine, parsed["away_team"])
            if not home_canonical or not away_canonical:
                missing_games += 1
                continue

            _upsert_team_alias(engine, home_canonical, parsed["home_team"], "espn")
            _upsert_team_alias(engine, away_canonical, parsed["away_team"], "espn")

            event_date = parsed["event_date"]
            if event_date:
                event_dt = datetime.fromisoformat(event_date.replace("Z", "+00:00")).astimezone(cst)
                game_date = event_dt.date()
            else:
                game_date = target_date

            with engine.begin() as conn:
                res = conn.execute(
                    update_stmt,
                    {
                        "home_score_1h": int(parsed["home_score_1h"]),
                        "away_score_1h": int(parsed["away_score_1h"]),
                        "home_canonical": home_canonical,
                        "away_canonical": away_canonical,
                        "game_date": game_date,
                    },
                )
                if (res.rowcount or 0) > 0:
                    updated += int(res.rowcount or 0)
                    continue

                # Try swapped orientation (some feeds disagree on home/away)
                res = conn.execute(
                    update_stmt,
                    {
                        "home_score_1h": int(parsed["away_score_1h"]),
                        "away_score_1h": int(parsed["home_score_1h"]),
                        "home_canonical": away_canonical,
                        "away_canonical": home_canonical,
                        "game_date": game_date,
                    },
                )
                if (res.rowcount or 0) > 0:
                    updated += int(res.rowcount or 0)
                else:
                    missing_games += 1

    return HalftimeSyncSummary(
        fetched_events=fetched_events,
        updated_games=updated,
        missing_games=missing_games,
        missing_scores=missing_scores,
    )


def _closing_snapshot(
    engine: Engine,
    game_id: UUID,
    market_type: str,
    period: str,
    commence_time: datetime,
) -> Optional[Dict[str, Any]]:
    """
    Get the "closing" snapshot: latest odds <= commence_time, preferring Pinnacle then Bovada.
    """
    stmt = text(
        """
        SELECT
            time,
            bookmaker,
            home_line,
            away_line,
            total_line,
            home_price,
            away_price,
            over_price,
            under_price
        FROM odds_snapshots
        WHERE game_id = :game_id
          AND market_type = :market_type
          AND period = :period
          AND time <= :commence_time
        ORDER BY
          (bookmaker = 'pinnacle') DESC,
          (bookmaker = 'bovada') DESC,
          time DESC
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            stmt,
            {
                "game_id": game_id,
                "market_type": market_type,
                "period": period,
                "commence_time": commence_time,
            },
        ).fetchone()
        if not row:
            return None
        return dict(row._mapping)


def _market_mapping(bet_type: str) -> Tuple[str, str]:
    """
    Map betting_recommendations.bet_type -> (odds_snapshots.market_type, odds_snapshots.period)
    """
    bet_type = (bet_type or "").upper()
    if bet_type == "SPREAD":
        return "spreads", "full"
    if bet_type == "TOTAL":
        return "totals", "full"
    if bet_type == "SPREAD_1H":
        return "spreads", "1h"
    if bet_type == "TOTAL_1H":
        return "totals", "1h"
    # Unknown: best effort
    return "unknown", "full"


def _settle_spread(pick: str, line: float, home_score: int, away_score: int) -> str:
    # line is from the PICK perspective:
    # - HOME: home_score + line vs away_score
    # - AWAY: away_score + line vs home_score
    pick = (pick or "").upper()
    if pick == "HOME":
        diff = (home_score + line) - away_score
    else:
        diff = (away_score + line) - home_score
    if diff > 0:
        return "won"
    if diff < 0:
        return "lost"
    return "push"


def _settle_total(pick: str, line: float, home_score: int, away_score: int) -> str:
    total = home_score + away_score
    pick = (pick or "").upper()
    if pick == "OVER":
        if total > line:
            return "won"
        if total < line:
            return "lost"
        return "push"
    # UNDER
    if total < line:
        return "won"
    if total > line:
        return "lost"
    return "push"





def settle_pending_bets(engine: Engine) -> SettlementSummary:
    """
    Settle any pending/placed betting_recommendations where the game has final scores.
    Computes:
    - closing_line from odds_snapshots at commence_time
    - clv (market-dependent definition; positive means "beat close")
    - pnl in units (uses closing price for spread/total if available, else assumes -110)
    """
    fetch_stmt = text(
        """
        SELECT
            br.id,
            br.game_id,
            br.bet_type,
            br.pick,
            br.line,
            br.recommended_units,
            br.created_at,
            g.commence_time,
            g.home_score,
            g.away_score,
            g.home_score_1h,
            g.away_score_1h
        FROM betting_recommendations br
        JOIN games g ON g.id = br.game_id
        WHERE br.status IN ('pending', 'placed')
          AND g.status IN ('completed', 'final')
          AND g.home_score IS NOT NULL
          AND g.away_score IS NOT NULL
        ORDER BY br.created_at ASC
        """
    )

    update_stmt = text(
        """
        UPDATE betting_recommendations
        SET
            status = :status,
            actual_result = :actual_result,
            closing_line = :closing_line,
            clv = :clv,
            pnl = :pnl,
            settled_at = NOW()
        WHERE id = :id
        """
    )

    settled = wins = losses = pushes = 0
    skipped_1h = 0
    missing_close = 0

    with engine.begin() as conn:
        rows = conn.execute(fetch_stmt).fetchall()

    for row in rows:
        r = dict(row._mapping)

        bet_id: UUID = r["id"]
        game_id: UUID = r["game_id"]
        bet_type: str = r["bet_type"]
        pick: str = r["pick"]
        line = float(r["line"])
        stake = float(r.get("recommended_units") or 1.0)
        commence_time: datetime = r["commence_time"]

        # Choose which scores to use
        is_1h = bet_type.upper().endswith("_1H")
        if is_1h:
            h1 = r.get("home_score_1h")
            a1 = r.get("away_score_1h")
            if h1 is None or a1 is None:
                skipped_1h += 1
                continue
            home_score = int(h1)
            away_score = int(a1)
        else:
            home_score = int(r["home_score"])
            away_score = int(r["away_score"])

        # Closing snapshot
        market_type, period = _market_mapping(bet_type)
        snap = _closing_snapshot(engine, game_id, market_type, period, commence_time)
        if not snap:
            missing_close += 1

        closing_line = None
        clv_val = None
        price_for_pnl: Optional[int] = None

        bet_type_u = bet_type.upper()
        pick_u = (pick or "").upper()

        # Determine closing line + price based on market/pick
        if snap:
            if bet_type_u.startswith("SPREAD"):
                closing_line = float(snap["home_line"]) if pick_u == "HOME" else float(snap["away_line"])
                price_for_pnl = int(snap["home_price"] or -110) if pick_u == "HOME" else int(snap["away_price"] or -110)
                # Positive = beat close (got a better number than closing)
                clv_val = round(line - closing_line, 3)
            elif bet_type_u.startswith("TOTAL"):
                closing_line = float(snap["total_line"])
                if pick_u == "OVER":
                    price_for_pnl = int(snap["over_price"] or -110)
                    clv_val = round(closing_line - line, 3)  # closing higher than bet is good for OVER
                else:
                    price_for_pnl = int(snap["under_price"] or -110)
                    clv_val = round(line - closing_line, 3)  # bet higher than closing is good for UNDER
            else:
                # Unsupported market type
                pass
        else:
            # No closing snapshot: still settle outcome; assume -110
            price_for_pnl = -110

        # Settle outcome
        if bet_type_u.startswith("SPREAD"):
            status = _settle_spread(pick_u, line, home_score, away_score)
            actual_result = f"{home_score}-{away_score}"
        elif bet_type_u.startswith("TOTAL"):
            status = _settle_total(pick_u, line, home_score, away_score)
            actual_result = f"{home_score + away_score} total ({home_score}-{away_score})"
        else:
            # Unsupported market type
            continue

        pnl = 0.0
        if status == "won":
            pnl = stake * _profit_per_unit(int(price_for_pnl or -110))
            wins += 1
        elif status == "lost":
            pnl = -stake
            losses += 1
        else:
            pnl = 0.0
            pushes += 1

        with engine.begin() as conn:
            conn.execute(
                update_stmt,
                {
                    "id": bet_id,
                    "status": status,
                    "actual_result": actual_result,
                    "closing_line": closing_line,
                    "clv": clv_val,
                    "pnl": round(pnl, 3),
                },
            )

        settled += 1

    return SettlementSummary(
        settled=settled,
        wins=wins,
        losses=losses,
        pushes=pushes,
        skipped_missing_scores_1h=skipped_1h,
        missing_closing_line=missing_close,
    )


def print_performance_report(engine: Engine, lookback_days: int = 30) -> None:
    """
    Print ROI/CLV report grouped by bet_type for last N days (by created_at).
    """
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    stmt = text(
        """
        SELECT
            bet_type,
            COUNT(*) FILTER (WHERE status IN ('won','lost','push')) AS settled_bets,
            SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN status = 'push' THEN 1 ELSE 0 END) AS pushes,
            SUM(recommended_units) FILTER (WHERE status IN ('won','lost','push')) AS total_units,
            SUM(pnl) FILTER (WHERE status IN ('won','lost','push')) AS total_pnl,
            AVG(clv) FILTER (WHERE clv IS NOT NULL AND status IN ('won','lost','push')) AS avg_clv
        FROM betting_recommendations
        WHERE created_at >= :since
        GROUP BY bet_type
        ORDER BY bet_type
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(stmt, {"since": since}).fetchall()

    if not rows:
        print(f"📉 No settled bets in last {lookback_days} days")
        return

    print()
    print(f"📈 PERFORMANCE (last {lookback_days} days)")
    print("┏" + "━" * 98 + "┓")
    print("┃ " + f"{'BET TYPE':<14} {'BETS':>6} {'W-L-P':>9} {'UNITS':>10} {'PNL':>10} {'ROI':>8} {'AVG CLV':>10}".ljust(96) + " ┃")
    print("┣" + "━" * 98 + "┫")

    for row in rows:
        m = dict(row._mapping)
        bet_type = m["bet_type"]
        bets = int(m["settled_bets"] or 0)
        wins = int(m["wins"] or 0)
        losses = int(m["losses"] or 0)
        pushes = int(m["pushes"] or 0)
        units = float(m["total_units"] or 0.0)
        pnl = float(m["total_pnl"] or 0.0)
        avg_clv = m["avg_clv"]
        roi = (pnl / units) if units > 0 else 0.0

        avg_clv_str = f"{float(avg_clv):+.3f}" if avg_clv is not None else "N/A"

        line = (
            f"┃ {bet_type:<14} {bets:>6} {wins:>3}-{losses:<3}-{pushes:<3} "
            f"{units:>10.1f} {pnl:>+10.2f} {roi:>+7.1%} {avg_clv_str:>10} ┃"
        )
        print(line)

    print("┗" + "━" * 98 + "┛")
    print()


