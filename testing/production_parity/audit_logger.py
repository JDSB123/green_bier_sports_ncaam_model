"""
Backtest Audit Logger for Production Parity.

Provides comprehensive logging of every decision made during backtest:
- Team resolution (with step used)
- Ratings lookup (with season anti-leakage verification)
- Model predictions (with inputs and outputs)
- Bet recommendations (with edge calculations)
- Game outcomes (with P&L tracking)

All timestamps are in CST for consistency with game times.
"""

import csv
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .timezone_utils import now_cst, format_cst
from .team_resolver import ResolutionStep


class AuditEventType(Enum):
    """Types of audit events."""
    GAME_START = "game_start"
    TEAM_RESOLUTION = "team_resolution"
    RATINGS_LOOKUP = "ratings_lookup"
    PREDICTION = "prediction"
    BET_RECOMMENDATION = "bet_recommendation"
    GAME_OUTCOME = "game_outcome"
    GAME_SKIPPED = "game_skipped"
    ERROR = "error"


@dataclass
class AuditEvent:
    """A single audit event with CST timestamp."""
    event_type: AuditEventType
    timestamp_cst: str
    game_id: Optional[str]
    data: Dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "timestamp_cst": self.timestamp_cst,
            "game_id": self.game_id,
            **self.data,
        }


@dataclass
class GameAuditRecord:
    """Complete audit record for a single game."""
    game_id: str
    game_date_cst: str
    game_season: int
    ratings_season: int

    # Team resolution
    home_team_raw: str
    away_team_raw: str
    home_team_canonical: Optional[str]
    away_team_canonical: Optional[str]
    home_resolution_step: str
    away_resolution_step: str

    # Ratings lookup
    home_ratings_found: bool
    away_ratings_found: bool
    home_adj_o: Optional[float] = None
    home_adj_d: Optional[float] = None
    home_tempo: Optional[float] = None
    away_adj_o: Optional[float] = None
    away_adj_d: Optional[float] = None
    away_tempo: Optional[float] = None

    # Predictions (filled after model runs)
    fg_spread_prediction: Optional[float] = None
    h1_spread_prediction: Optional[float] = None
    fg_total_prediction: Optional[float] = None
    h1_total_prediction: Optional[float] = None

    # Market lines (from historical data)
    market_spread: Optional[float] = None
    market_total: Optional[float] = None
    market_h1_spread: Optional[float] = None
    market_h1_total: Optional[float] = None

    # Bet recommendations
    fg_spread_edge: Optional[float] = None
    h1_spread_edge: Optional[float] = None
    fg_total_edge: Optional[float] = None
    h1_total_edge: Optional[float] = None
    fg_spread_pick: Optional[str] = None
    h1_spread_pick: Optional[str] = None
    fg_total_pick: Optional[str] = None
    h1_total_pick: Optional[str] = None

    # Outcomes (filled after game completes)
    final_score_home: Optional[int] = None
    final_score_away: Optional[int] = None
    h1_score_home: Optional[int] = None
    h1_score_away: Optional[int] = None

    # Results (win/loss per bet type)
    fg_spread_result: Optional[str] = None  # "WIN", "LOSS", "PUSH"
    h1_spread_result: Optional[str] = None
    fg_total_result: Optional[str] = None
    h1_total_result: Optional[str] = None

    # Units P&L
    fg_spread_units: float = 0.0
    h1_spread_units: float = 0.0
    fg_total_units: float = 0.0
    h1_total_units: float = 0.0

    # Skip reason (if game was skipped)
    skipped: bool = False
    skip_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class BacktestAuditLogger:
    """
    Comprehensive audit logger for production parity backtest.

    Logs every decision with CST timestamps and provides export
    to multiple formats for analysis.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the audit logger.

        Args:
            output_dir: Directory to write audit files
        """
        if output_dir is None:
            output_dir = Path(__file__).parent / "audit_logs"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Audit data
        self.events: List[AuditEvent] = []
        self.game_records: Dict[str, GameAuditRecord] = {}

        # Stats
        self.stats = {
            "games_processed": 0,
            "games_skipped": 0,
            "predictions_made": 0,
            "bets_placed": 0,
        }

        # Session info
        self.session_start = now_cst()
        self.session_id = format_cst(self.session_start, "%Y%m%d_%H%M%S")

        print(f"[AuditLogger] Session {self.session_id} started at {format_cst(self.session_start)}")

    def _log_event(self, event_type: AuditEventType, game_id: Optional[str], data: Dict[str, Any]) -> None:
        """Log a single audit event."""
        event = AuditEvent(
            event_type=event_type,
            timestamp_cst=format_cst(now_cst()),
            game_id=game_id,
            data=data,
        )
        self.events.append(event)

    def log_game_start(
        self,
        game_id: str,
        game_date_cst: str,
        home_team_raw: str,
        away_team_raw: str,
        game_season: int,
        ratings_season: int,
    ) -> GameAuditRecord:
        """
        Log the start of processing a game.

        Returns the GameAuditRecord for updating with results.
        """
        record = GameAuditRecord(
            game_id=game_id,
            game_date_cst=game_date_cst,
            game_season=game_season,
            ratings_season=ratings_season,
            home_team_raw=home_team_raw,
            away_team_raw=away_team_raw,
            home_team_canonical=None,
            away_team_canonical=None,
            home_resolution_step="pending",
            away_resolution_step="pending",
            home_ratings_found=False,
            away_ratings_found=False,
        )

        self.game_records[game_id] = record
        self.stats["games_processed"] += 1

        self._log_event(AuditEventType.GAME_START, game_id, {
            "game_date_cst": game_date_cst,
            "home_team_raw": home_team_raw,
            "away_team_raw": away_team_raw,
            "game_season": game_season,
            "ratings_season": ratings_season,
        })

        return record

    def log_team_resolution(
        self,
        game_id: str,
        is_home: bool,
        raw_name: str,
        canonical_name: Optional[str],
        resolution_step: ResolutionStep,
    ) -> None:
        """Log a team name resolution."""
        record = self.game_records.get(game_id)
        if record:
            if is_home:
                record.home_team_canonical = canonical_name
                record.home_resolution_step = resolution_step.value
            else:
                record.away_team_canonical = canonical_name
                record.away_resolution_step = resolution_step.value

        self._log_event(AuditEventType.TEAM_RESOLUTION, game_id, {
            "is_home": is_home,
            "raw_name": raw_name,
            "canonical_name": canonical_name,
            "resolution_step": resolution_step.value,
        })

    def log_ratings_lookup(
        self,
        game_id: str,
        is_home: bool,
        team_name: str,
        found: bool,
        ratings_dict: Optional[dict] = None,
    ) -> None:
        """Log a ratings lookup."""
        record = self.game_records.get(game_id)
        if record:
            if is_home:
                record.home_ratings_found = found
                if ratings_dict:
                    record.home_adj_o = ratings_dict.get("adj_o")
                    record.home_adj_d = ratings_dict.get("adj_d")
                    record.home_tempo = ratings_dict.get("tempo")
            else:
                record.away_ratings_found = found
                if ratings_dict:
                    record.away_adj_o = ratings_dict.get("adj_o")
                    record.away_d = ratings_dict.get("adj_d")
                    record.away_tempo = ratings_dict.get("tempo")

        self._log_event(AuditEventType.RATINGS_LOOKUP, game_id, {
            "is_home": is_home,
            "team_name": team_name,
            "found": found,
            "ratings": ratings_dict if found else None,
        })

    def log_prediction(
        self,
        game_id: str,
        model_name: str,
        prediction: float,
        inputs: dict,
    ) -> None:
        """Log a model prediction."""
        record = self.game_records.get(game_id)
        if record:
            if model_name == "FGSpread":
                record.fg_spread_prediction = prediction
            elif model_name == "H1Spread":
                record.h1_spread_prediction = prediction
            elif model_name == "FGTotal":
                record.fg_total_prediction = prediction
            elif model_name == "H1Total":
                record.h1_total_prediction = prediction

            self.stats["predictions_made"] += 1

        self._log_event(AuditEventType.PREDICTION, game_id, {
            "model_name": model_name,
            "prediction": prediction,
            "inputs": inputs,
        })

    def log_bet_recommendation(
        self,
        game_id: str,
        bet_type: str,  # "FGSpread", "H1Spread", "FGTotal", "H1Total"
        prediction: float,
        market_line: float,
        edge: float,
        pick: Optional[str],
        units: float,
    ) -> None:
        """Log a bet recommendation."""
        record = self.game_records.get(game_id)
        if record:
            if bet_type == "FGSpread":
                record.fg_spread_edge = edge
                record.fg_spread_pick = pick
                record.market_spread = market_line
            elif bet_type == "H1Spread":
                record.h1_spread_edge = edge
                record.h1_spread_pick = pick
                record.market_h1_spread = market_line
            elif bet_type == "FGTotal":
                record.fg_total_edge = edge
                record.fg_total_pick = pick
                record.market_total = market_line
            elif bet_type == "H1Total":
                record.h1_total_edge = edge
                record.h1_total_pick = pick
                record.market_h1_total = market_line

            if pick:
                self.stats["bets_placed"] += 1

        self._log_event(AuditEventType.BET_RECOMMENDATION, game_id, {
            "bet_type": bet_type,
            "prediction": prediction,
            "market_line": market_line,
            "edge": edge,
            "pick": pick,
            "units": units,
        })

    def log_game_outcome(
        self,
        game_id: str,
        final_score_home: int,
        final_score_away: int,
        h1_score_home: Optional[int] = None,
        h1_score_away: Optional[int] = None,
    ) -> None:
        """Log game outcome and calculate results."""
        record = self.game_records.get(game_id)
        if record:
            record.final_score_home = final_score_home
            record.final_score_away = final_score_away
            record.h1_score_home = h1_score_home
            record.h1_score_away = h1_score_away

            # Calculate FG Spread result
            if record.fg_spread_pick and record.market_spread is not None:
                actual_margin = final_score_home - final_score_away
                record.fg_spread_result, record.fg_spread_units = self._grade_spread_bet(
                    record.fg_spread_pick, record.market_spread, actual_margin
                )

            # Calculate H1 Spread result
            if record.h1_spread_pick and record.market_h1_spread is not None and h1_score_home is not None:
                h1_margin = h1_score_home - h1_score_away
                record.h1_spread_result, record.h1_spread_units = self._grade_spread_bet(
                    record.h1_spread_pick, record.market_h1_spread, h1_margin
                )

            # Calculate FG Total result
            if record.fg_total_pick and record.market_total is not None:
                actual_total = final_score_home + final_score_away
                record.fg_total_result, record.fg_total_units = self._grade_total_bet(
                    record.fg_total_pick, record.market_total, actual_total
                )

            # Calculate H1 Total result
            if record.h1_total_pick and record.market_h1_total is not None and h1_score_home is not None:
                h1_total = h1_score_home + h1_score_away
                record.h1_total_result, record.h1_total_units = self._grade_total_bet(
                    record.h1_total_pick, record.market_h1_total, h1_total
                )

        self._log_event(AuditEventType.GAME_OUTCOME, game_id, {
            "final_score_home": final_score_home,
            "final_score_away": final_score_away,
            "h1_score_home": h1_score_home,
            "h1_score_away": h1_score_away,
        })

    def _grade_spread_bet(self, pick: str, line: float, actual_margin: int) -> tuple[str, float]:
        """Grade a spread bet. Line is from HOME perspective."""
        # Cover margin = actual margin + spread (from home perspective)
        cover = actual_margin + line

        if pick == "HOME":
            if cover > 0:
                return "WIN", 1.0
            elif cover < 0:
                return "LOSS", -1.0
            else:
                return "PUSH", 0.0
        else:  # AWAY
            if cover < 0:
                return "WIN", 1.0
            elif cover > 0:
                return "LOSS", -1.0
            else:
                return "PUSH", 0.0

    def _grade_total_bet(self, pick: str, line: float, actual_total: int) -> tuple[str, float]:
        """Grade a total bet."""
        if pick == "OVER":
            if actual_total > line:
                return "WIN", 1.0
            elif actual_total < line:
                return "LOSS", -1.0
            else:
                return "PUSH", 0.0
        else:  # UNDER
            if actual_total < line:
                return "WIN", 1.0
            elif actual_total > line:
                return "LOSS", -1.0
            else:
                return "PUSH", 0.0

    def log_game_skipped(self, game_id: str, reason: str) -> None:
        """Log a skipped game."""
        record = self.game_records.get(game_id)
        if record:
            record.skipped = True
            record.skip_reason = reason

        self.stats["games_skipped"] += 1

        self._log_event(AuditEventType.GAME_SKIPPED, game_id, {
            "reason": reason,
        })

    def log_error(self, game_id: Optional[str], error: str, details: Optional[dict] = None) -> None:
        """Log an error."""
        self._log_event(AuditEventType.ERROR, game_id, {
            "error": error,
            "details": details or {},
        })

    def get_summary(self) -> dict:
        """Get backtest summary statistics."""
        total_units = 0.0
        wins = 0
        losses = 0
        pushes = 0

        by_bet_type = {
            "FGSpread": {"units": 0.0, "wins": 0, "losses": 0, "pushes": 0},
            "H1Spread": {"units": 0.0, "wins": 0, "losses": 0, "pushes": 0},
            "FGTotal": {"units": 0.0, "wins": 0, "losses": 0, "pushes": 0},
            "H1Total": {"units": 0.0, "wins": 0, "losses": 0, "pushes": 0},
        }

        for record in self.game_records.values():
            if record.skipped:
                continue

            for bet_type, result_attr, units_attr in [
                ("FGSpread", "fg_spread_result", "fg_spread_units"),
                ("H1Spread", "h1_spread_result", "h1_spread_units"),
                ("FGTotal", "fg_total_result", "fg_total_units"),
                ("H1Total", "h1_total_result", "h1_total_units"),
            ]:
                result = getattr(record, result_attr)
                units = getattr(record, units_attr)

                if result:
                    total_units += units
                    by_bet_type[bet_type]["units"] += units

                    if result == "WIN":
                        wins += 1
                        by_bet_type[bet_type]["wins"] += 1
                    elif result == "LOSS":
                        losses += 1
                        by_bet_type[bet_type]["losses"] += 1
                    else:
                        pushes += 1
                        by_bet_type[bet_type]["pushes"] += 1

        total_bets = wins + losses + pushes
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

        return {
            "session_id": self.session_id,
            "session_start_cst": format_cst(self.session_start),
            "games_processed": self.stats["games_processed"],
            "games_skipped": self.stats["games_skipped"],
            "predictions_made": self.stats["predictions_made"],
            "total_bets": total_bets,
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": win_rate,
            "total_units": total_units,
            "roi": (total_units / total_bets * 100) if total_bets > 0 else 0,
            "by_bet_type": by_bet_type,
        }

    def export_to_csv(self, filename: Optional[str] = None) -> Path:
        """Export game records to CSV."""
        if filename is None:
            filename = f"backtest_audit_{self.session_id}.csv"

        path = self.output_dir / filename

        if not self.game_records:
            print("[AuditLogger] No records to export")
            return path

        records = list(self.game_records.values())
        fieldnames = list(asdict(records[0]).keys())

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                writer.writerow(asdict(record))

        print(f"[AuditLogger] Exported {len(records)} records to {path}")
        return path

    def export_to_json(self, filename: Optional[str] = None) -> Path:
        """Export game records and events to JSON."""
        if filename is None:
            filename = f"backtest_audit_{self.session_id}.json"

        path = self.output_dir / filename

        output = {
            "session_id": self.session_id,
            "session_start_cst": format_cst(self.session_start),
            "summary": self.get_summary(),
            "game_records": [asdict(r) for r in self.game_records.values()],
            "events": [e.to_dict() for e in self.events],
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        print(f"[AuditLogger] Exported full audit to {path}")
        return path

    def print_summary(self) -> None:
        """Print summary to console."""
        summary = self.get_summary()

        print("\n" + "=" * 60)
        print("BACKTEST AUDIT SUMMARY")
        print("=" * 60)
        print(f"Session: {summary['session_id']}")
        print(f"Started: {summary['session_start_cst']}")
        print()
        print(f"Games Processed: {summary['games_processed']}")
        print(f"Games Skipped:   {summary['games_skipped']}")
        print(f"Predictions:     {summary['predictions_made']}")
        print()
        print(f"Total Bets:  {summary['total_bets']}")
        print(f"Record:      {summary['wins']}-{summary['losses']}-{summary['pushes']}")
        print(f"Win Rate:    {summary['win_rate']:.1%}")
        print(f"Total Units: {summary['total_units']:+.2f}")
        print(f"ROI:         {summary['roi']:+.2f}%")
        print()
        print("By Bet Type:")
        for bet_type, stats in summary["by_bet_type"].items():
            bets = stats["wins"] + stats["losses"] + stats["pushes"]
            if bets > 0:
                wr = stats["wins"] / (stats["wins"] + stats["losses"]) if (stats["wins"] + stats["losses"]) > 0 else 0
                print(f"  {bet_type}: {stats['wins']}-{stats['losses']}-{stats['pushes']} "
                      f"({wr:.1%}), {stats['units']:+.2f}u")
        print("=" * 60)
