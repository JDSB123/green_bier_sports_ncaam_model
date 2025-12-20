"""
Backtesting engine for NCAAF betting strategies.

Supports backtesting across:
- Bet Types: Spread, Moneyline, Totals
- Game Periods: 1st Quarter (1Q), 1st Half (1H), Full Game

Includes:
- CLV (Closing Line Value) tracking for edge validation
- Full database persistence
- Walk-forward validation support
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from enum import Enum
import json
from pathlib import Path

import structlog
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class BetType(str, Enum):
    """Supported bet types."""
    SPREAD = "spread"
    MONEYLINE = "moneyline"
    TOTAL = "total"


class GamePeriod(str, Enum):
    """Supported game periods."""
    FIRST_QUARTER = "1Q"
    FIRST_HALF = "1H"
    FULL_GAME = "full"


class BetOutcome(str, Enum):
    """Possible bet outcomes."""
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"


class BetSide(str, Enum):
    """Bet side selection."""
    HOME = "home"
    AWAY = "away"
    OVER = "over"
    UNDER = "under"


class BacktestConfig:
    """Configuration for a backtest run."""

    def __init__(
        self,
        name: str,
        start_date: date,
        end_date: date,
        bet_types: List[BetType],
        game_periods: List[GamePeriod],
        min_confidence: float = 0.0,
        max_risk: Decimal = Decimal("100.00"),
        unit_size: Decimal = Decimal("100.00"),
        description: Optional[str] = None,
    ):
        self.name = name
        self.start_date = start_date
        self.end_date = end_date
        self.bet_types = bet_types
        self.game_periods = game_periods
        self.min_confidence = min_confidence
        self.max_risk = max_risk
        self.unit_size = unit_size
        self.description = description


class BetResult:
    """Result of a single bet with CLV tracking."""

    def __init__(
        self,
        game_id: int,
        game_date: date,
        home_team_id: int,
        away_team_id: int,
        bet_type: BetType,
        game_period: GamePeriod,
        bet_side: BetSide,
        predicted_value: Optional[Decimal],
        confidence: float,
        edge: float,
        odds_line: Optional[Decimal],
        odds_price: int,
        wager_amount: Decimal,
        actual_result: Decimal,
        outcome: BetOutcome,
        payout: Decimal,
        profit: Decimal,
        # CLV (Closing Line Value) tracking
        opening_line: Optional[Decimal] = None,
        closing_line: Optional[Decimal] = None,
        bet_line: Optional[Decimal] = None,
    ):
        self.game_id = game_id
        self.game_date = game_date
        self.home_team_id = home_team_id
        self.away_team_id = away_team_id
        self.bet_type = bet_type
        self.game_period = game_period
        self.bet_side = bet_side
        self.predicted_value = predicted_value
        self.confidence = confidence
        self.edge = edge
        self.odds_line = odds_line
        self.odds_price = odds_price
        self.wager_amount = wager_amount
        self.actual_result = actual_result
        self.outcome = outcome
        self.payout = payout
        self.profit = profit
        # CLV tracking
        self.opening_line = opening_line
        self.closing_line = closing_line
        self.bet_line = bet_line or odds_line

    @property
    def clv(self) -> Optional[float]:
        """
        Calculate Closing Line Value.
        
        CLV = closing_line - bet_line (for spreads/totals)
        Positive CLV means you got a better line than closing.
        This is the gold standard for measuring betting edge.
        """
        if self.closing_line is None or self.bet_line is None:
            return None
        
        clv_value = float(self.closing_line - self.bet_line)
        
        # For away bets on spread, CLV sign is inverted
        if self.bet_type == BetType.SPREAD and self.bet_side == BetSide.AWAY:
            clv_value = -clv_value
        # For under bets on total, CLV sign is inverted
        if self.bet_type == BetType.TOTAL and self.bet_side == BetSide.UNDER:
            clv_value = -clv_value
            
        return clv_value

    @property
    def beat_closing_line(self) -> Optional[bool]:
        """Did we get a better line than closing?"""
        clv = self.clv
        return clv > 0 if clv is not None else None


class BacktestEngine:
    """Engine for running backtests on betting strategies."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logger.bind(component="backtest_engine")

    async def run_backtest(self, config: BacktestConfig) -> Tuple[int, List[BetResult], Dict]:
        """
        Run a backtest with the given configuration.

        Returns:
            Tuple of (backtest_id, list of bet results, CLV metrics)
        """
        self.logger.info(
            "Starting backtest",
            name=config.name,
            start_date=config.start_date,
            end_date=config.end_date,
        )

        # Create backtest record
        backtest_id = await self._create_backtest_record(config)

        # Get historical games and predictions for the date range
        games_data = await self._load_historical_data(
            config.start_date,
            config.end_date
        )

        # Simulate bets for each game
        all_results = []
        for game in games_data:
            results = await self._simulate_bets_for_game(
                game,
                config
            )
            all_results.extend(results)

        # Store results in database
        await self._store_results(backtest_id, all_results)

        # Calculate CLV metrics
        clv_metrics = self.calculate_clv_metrics(all_results)

        # Update backtest status
        await self._complete_backtest(backtest_id)

        # Log CLV summary
        if clv_metrics.get("clv_available"):
            self.logger.info(
                "CLV Analysis",
                avg_clv=f"{clv_metrics['avg_clv']:.2f}",
                beat_closing_rate=f"{clv_metrics['beat_closing_rate']:.1%}",
                clv_positive_rate=f"{clv_metrics['clv_positive_rate']:.1%}",
            )

        self.logger.info(
            "Backtest completed",
            backtest_id=backtest_id,
            total_bets=len(all_results),
        )

        return backtest_id, all_results, clv_metrics

    async def _create_backtest_record(self, config: BacktestConfig) -> int:
        """Create initial backtest record in database."""
        query = text("""
            INSERT INTO backtests (
                name, description, start_date, end_date, 
                bet_types, game_periods, min_confidence, max_risk,
                status, started_at
            ) VALUES (
                :name, :description, :start_date, :end_date,
                :bet_types, :game_periods, :min_confidence, :max_risk,
                'running', NOW()
            ) RETURNING id
        """)
        
        result = await self.db.execute(query, {
            "name": config.name,
            "description": config.description,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "bet_types": [bt.value for bt in config.bet_types],
            "game_periods": [gp.value for gp in config.game_periods],
            "min_confidence": float(config.min_confidence),
            "max_risk": float(config.max_risk),
        })
        
        row = result.fetchone()
        await self.db.commit()
        
        backtest_id = row[0]
        self.logger.info("Created backtest record", backtest_id=backtest_id)
        return backtest_id

    async def _load_historical_data(
        self,
        start_date: date,
        end_date: date
    ) -> List[Dict]:
        """
        Load historical game data with predictions and actual results.

        Returns list of games with:
        - Game info (id, date, teams)
        - Predictions (spread, total, win probability)
        - Actual results by period (1Q, 1H, full)
        - Odds lines and prices (including opening/closing for CLV)
        """
        query = text("""
            WITH game_odds AS (
                SELECT 
                    game_id,
                    -- Opening lines (first recorded)
                    FIRST_VALUE(spread_home) OVER (
                        PARTITION BY game_id ORDER BY created_at ASC
                    ) as opening_spread,
                    FIRST_VALUE(total_over) OVER (
                        PARTITION BY game_id ORDER BY created_at ASC
                    ) as opening_total,
                    -- Closing lines (last recorded)
                    FIRST_VALUE(spread_home) OVER (
                        PARTITION BY game_id ORDER BY created_at DESC
                    ) as closing_spread,
                    FIRST_VALUE(total_over) OVER (
                        PARTITION BY game_id ORDER BY created_at DESC
                    ) as closing_total,
                    -- Consensus (average)
                    AVG(spread_home) OVER (PARTITION BY game_id) as consensus_spread,
                    AVG(total_over) OVER (PARTITION BY game_id) as consensus_total,
                    AVG(spread_home_price) OVER (PARTITION BY game_id) as spread_home_price,
                    AVG(spread_away_price) OVER (PARTITION BY game_id) as spread_away_price,
                    AVG(total_over_price) OVER (PARTITION BY game_id) as total_over_price,
                    AVG(total_under_price) OVER (PARTITION BY game_id) as total_under_price,
                    AVG(moneyline_home) OVER (PARTITION BY game_id) as ml_home_price,
                    AVG(moneyline_away) OVER (PARTITION BY game_id) as ml_away_price,
                    ROW_NUMBER() OVER (PARTITION BY game_id ORDER BY created_at DESC) as rn
                FROM odds
            )
            SELECT 
                g.id,
                g.date_time::date as game_date,
                g.home_team_id,
                g.away_team_id,
                g.home_score,
                g.away_score,
                g.home_score - g.away_score as margin,
                g.home_score + g.away_score as total_score,
                -- Period scores (if available)
                g.home_score_q1,
                g.away_score_q1,
                g.home_score_h1,
                g.away_score_h1,
                -- Predictions
                p.predicted_margin as spread_full_prediction,
                p.predicted_total as total_full_prediction,
                p.home_win_probability,
                p.confidence_score,
                -- Opening lines (for CLV)
                o.opening_spread,
                o.opening_total,
                -- Closing lines (for CLV)
                o.closing_spread,
                o.closing_total,
                -- Consensus odds
                COALESCE(o.consensus_spread, 0) as full_spread_home,
                COALESCE(o.consensus_total, 48) as full_total_line,
                COALESCE(o.spread_home_price, -110)::int as full_spread_home_price,
                COALESCE(o.spread_away_price, -110)::int as full_spread_away_price,
                COALESCE(o.total_over_price, -110)::int as full_total_over_price,
                COALESCE(o.total_under_price, -110)::int as full_total_under_price,
                COALESCE(o.ml_home_price, -110)::int as full_ml_home_price,
                COALESCE(o.ml_away_price, -110)::int as full_ml_away_price
            FROM games g
            LEFT JOIN predictions p ON g.id = p.game_id
            LEFT JOIN game_odds o ON g.id = o.game_id AND o.rn = 1
            WHERE g.date_time::date BETWEEN :start_date AND :end_date
              AND g.status IN ('Final', 'F/OT')
              AND g.home_score IS NOT NULL
              AND g.away_score IS NOT NULL
            ORDER BY g.date_time
        """)
        
        result = await self.db.execute(query, {
            "start_date": start_date,
            "end_date": end_date
        })
        
        rows = result.fetchall()
        columns = result.keys()
        
        games = []
        for row in rows:
            game_dict = dict(zip(columns, row))
            
            # Add period-specific data
            if game_dict.get('home_score_q1') is not None:
                game_dict['1Q_home_score'] = game_dict['home_score_q1']
                game_dict['1Q_away_score'] = game_dict['away_score_q1']
            if game_dict.get('home_score_h1') is not None:
                game_dict['1H_home_score'] = game_dict['home_score_h1']
                game_dict['1H_away_score'] = game_dict['away_score_h1']
            game_dict['full_home_score'] = game_dict['home_score']
            game_dict['full_away_score'] = game_dict['away_score']
            
            games.append(game_dict)
        
        self.logger.info(
            "Loaded historical data",
            games_count=len(games),
            start_date=start_date,
            end_date=end_date
        )
        
        return games

    async def _simulate_bets_for_game(
        self,
        game: Dict,
        config: BacktestConfig
    ) -> List[BetResult]:
        """Simulate all configured bets for a single game."""
        results = []

        for bet_type in config.bet_types:
            for period in config.game_periods:
                # Check if we have prediction and confidence meets threshold
                prediction = game.get(f"{bet_type}_{period}_prediction")
                confidence = game.get(f"{bet_type}_{period}_confidence", 0.0)

                if not prediction or confidence < config.min_confidence:
                    continue

                # Simulate the bet
                bet_result = self._simulate_single_bet(
                    game=game,
                    bet_type=bet_type,
                    period=period,
                    prediction=prediction,
                    confidence=confidence,
                    config=config,
                )

                if bet_result:
                    results.append(bet_result)

        return results

    def _simulate_single_bet(
        self,
        game: Dict,
        bet_type: BetType,
        period: GamePeriod,
        prediction: Dict,
        confidence: float,
        config: BacktestConfig,
    ) -> Optional[BetResult]:
        """Simulate a single bet and calculate outcome."""

        # Get actual result for the period
        actual = self._get_actual_result(game, bet_type, period)
        if actual is None:
            return None

        # Determine bet side and odds
        bet_side, odds_line, odds_price, edge = self._determine_bet_side(
            bet_type, prediction, game, period
        )

        if bet_side is None:
            return None

        # Calculate wager amount (Kelly Criterion or flat betting)
        wager = self._calculate_wager(
            edge=edge,
            confidence=confidence,
            unit_size=config.unit_size,
            max_risk=config.max_risk,
        )

        # Determine outcome
        outcome = self._calculate_outcome(
            bet_type=bet_type,
            bet_side=bet_side,
            odds_line=odds_line,
            actual_result=actual,
        )

        # Calculate payout and profit
        payout, profit = self._calculate_payout(
            wager=wager,
            odds_price=odds_price,
            outcome=outcome,
        )

        # Get CLV data
        opening_line = None
        closing_line = None
        
        if bet_type == BetType.SPREAD:
            opening_line = Decimal(str(game.get("opening_spread", 0) or 0))
            closing_line = Decimal(str(game.get("closing_spread", 0) or 0))
        elif bet_type == BetType.TOTAL:
            opening_line = Decimal(str(game.get("opening_total", 0) or 0))
            closing_line = Decimal(str(game.get("closing_total", 0) or 0))
        
        return BetResult(
            game_id=game["id"],
            game_date=game["game_date"],
            home_team_id=game["home_team_id"],
            away_team_id=game["away_team_id"],
            bet_type=bet_type,
            game_period=period,
            bet_side=bet_side,
            predicted_value=prediction.get("value"),
            confidence=confidence,
            edge=edge,
            odds_line=odds_line,
            odds_price=odds_price,
            wager_amount=wager,
            actual_result=actual,
            outcome=outcome,
            payout=payout,
            profit=profit,
            # CLV tracking
            opening_line=opening_line,
            closing_line=closing_line,
            bet_line=odds_line,
        )

    def _get_actual_result(
        self,
        game: Dict,
        bet_type: BetType,
        period: GamePeriod,
    ) -> Optional[Decimal]:
        """Extract actual result for bet type and period."""

        if bet_type == BetType.SPREAD:
            # Return margin (positive = home won by that much)
            home_score = game.get(f"{period.value}_home_score")
            away_score = game.get(f"{period.value}_away_score")
            if home_score is not None and away_score is not None:
                return Decimal(str(home_score - away_score))

        elif bet_type == BetType.TOTAL:
            # Return total points scored
            home_score = game.get(f"{period.value}_home_score")
            away_score = game.get(f"{period.value}_away_score")
            if home_score is not None and away_score is not None:
                return Decimal(str(home_score + away_score))

        elif bet_type == BetType.MONEYLINE:
            # Return 1 for home win, -1 for away win, 0 for tie
            home_score = game.get(f"{period.value}_home_score")
            away_score = game.get(f"{period.value}_away_score")
            if home_score is not None and away_score is not None:
                if home_score > away_score:
                    return Decimal("1")
                elif away_score > home_score:
                    return Decimal("-1")
                else:
                    return Decimal("0")

        return None

    def _determine_bet_side(
        self,
        bet_type: BetType,
        prediction: Dict,
        game: Dict,
        period: GamePeriod,
    ) -> Tuple[Optional[BetSide], Optional[Decimal], int, float]:
        """
        Determine which side to bet based on prediction vs odds.

        Returns: (bet_side, odds_line, odds_price, edge)
        """

        if bet_type == BetType.SPREAD:
            predicted_margin = prediction.get("margin", 0)
            spread_line = game.get(f"{period.value}_spread_home", 0)

            # If predicted margin > spread, bet home; else bet away
            if predicted_margin > spread_line:
                edge = abs(predicted_margin - spread_line)
                return (
                    BetSide.HOME,
                    Decimal(str(spread_line)),
                    game.get(f"{period.value}_spread_home_price", -110),
                    edge,
                )
            elif predicted_margin < spread_line:
                edge = abs(predicted_margin - spread_line)
                return (
                    BetSide.AWAY,
                    Decimal(str(-spread_line)),
                    game.get(f"{period.value}_spread_away_price", -110),
                    edge,
                )

        elif bet_type == BetType.TOTAL:
            predicted_total = prediction.get("total", 0)
            total_line = game.get(f"{period.value}_total_line", 0)

            # If predicted total > line, bet over; else bet under
            if predicted_total > total_line:
                edge = abs(predicted_total - total_line)
                return (
                    BetSide.OVER,
                    Decimal(str(total_line)),
                    game.get(f"{period.value}_total_over_price", -110),
                    edge,
                )
            elif predicted_total < total_line:
                edge = abs(predicted_total - total_line)
                return (
                    BetSide.UNDER,
                    Decimal(str(total_line)),
                    game.get(f"{period.value}_total_under_price", -110),
                    edge,
                )

        elif bet_type == BetType.MONEYLINE:
            home_win_prob = prediction.get("home_win_prob", 0.5)
            home_ml_price = game.get(f"{period.value}_ml_home_price", -110)
            away_ml_price = game.get(f"{period.value}_ml_away_price", -110)

            # Convert American odds to implied probability
            home_implied = self._american_to_prob(home_ml_price)
            away_implied = self._american_to_prob(away_ml_price)

            # Bet if we have edge over implied probability
            home_edge = home_win_prob - home_implied
            away_edge = (1 - home_win_prob) - away_implied

            if home_edge > 0:
                return (BetSide.HOME, None, home_ml_price, home_edge)
            elif away_edge > 0:
                return (BetSide.AWAY, None, away_ml_price, away_edge)

        return (None, None, 0, 0.0)

    def _american_to_prob(self, american_odds: int) -> float:
        """Convert American odds to implied probability."""
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)

    def _calculate_wager(
        self,
        edge: float,
        confidence: float,
        unit_size: Decimal,
        max_risk: Decimal,
    ) -> Decimal:
        """
        Calculate wager amount using Kelly Criterion with constraints.

        Kelly = (edge * confidence) / (1 - confidence)
        But we cap at unit_size and max_risk
        """
        # Simple approach: use unit size scaled by confidence
        # More sophisticated: use fractional Kelly

        if confidence <= 0 or edge <= 0:
            return Decimal("0")

        # Fractional Kelly (25% Kelly for safety)
        kelly_fraction = (edge * confidence) / (1 - confidence) if confidence < 1 else edge
        kelly_fraction = min(kelly_fraction * 0.25, 0.10)  # Max 10% of bankroll

        # Scale unit size by Kelly fraction
        wager = unit_size * Decimal(str(kelly_fraction / 0.01))

        # Cap at unit size
        wager = min(wager, unit_size)

        # Cap at max risk
        wager = min(wager, max_risk)

        return wager.quantize(Decimal("0.01"))

    def _calculate_outcome(
        self,
        bet_type: BetType,
        bet_side: BetSide,
        odds_line: Optional[Decimal],
        actual_result: Decimal,
    ) -> BetOutcome:
        """Determine if bet won, lost, or pushed."""

        if bet_type == BetType.SPREAD:
            if bet_side == BetSide.HOME:
                # Home covers if: actual margin > spread line
                if actual_result > odds_line:
                    return BetOutcome.WIN
                elif actual_result == odds_line:
                    return BetOutcome.PUSH
                else:
                    return BetOutcome.LOSS
            else:  # AWAY
                # Away covers if: actual margin < spread line
                if actual_result < -odds_line:
                    return BetOutcome.WIN
                elif actual_result == -odds_line:
                    return BetOutcome.PUSH
                else:
                    return BetOutcome.LOSS

        elif bet_type == BetType.TOTAL:
            if bet_side == BetSide.OVER:
                if actual_result > odds_line:
                    return BetOutcome.WIN
                elif actual_result == odds_line:
                    return BetOutcome.PUSH
                else:
                    return BetOutcome.LOSS
            else:  # UNDER
                if actual_result < odds_line:
                    return BetOutcome.WIN
                elif actual_result == odds_line:
                    return BetOutcome.PUSH
                else:
                    return BetOutcome.LOSS

        elif bet_type == BetType.MONEYLINE:
            if bet_side == BetSide.HOME:
                return BetOutcome.WIN if actual_result > 0 else BetOutcome.LOSS
            else:  # AWAY
                return BetOutcome.WIN if actual_result < 0 else BetOutcome.LOSS

        return BetOutcome.LOSS

    def _calculate_payout(
        self,
        wager: Decimal,
        odds_price: int,
        outcome: BetOutcome,
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate payout and profit based on American odds.

        Returns: (payout, profit)
        """
        if outcome == BetOutcome.PUSH:
            return (wager, Decimal("0"))
        elif outcome == BetOutcome.LOSS:
            return (Decimal("0"), -wager)
        else:  # WIN
            # Calculate winnings from American odds
            if odds_price > 0:
                # Positive odds: win = wager * (odds / 100)
                win_amount = wager * Decimal(str(odds_price / 100))
            else:
                # Negative odds: win = wager / (abs(odds) / 100)
                win_amount = wager / Decimal(str(abs(odds_price) / 100))

            payout = wager + win_amount
            profit = win_amount

            return (payout.quantize(Decimal("0.01")), profit.quantize(Decimal("0.01")))

    async def _store_results(self, backtest_id: int, results: List[BetResult]):
        """Store backtest results in database with CLV tracking."""
        if not results:
            return
        
        # Bulk insert results
        for result in results:
            query = text("""
                INSERT INTO backtest_results (
                    backtest_id, game_id, game_date, home_team_id, away_team_id,
                    bet_type, game_period, bet_side, predicted_value, confidence, edge,
                    odds_line, odds_price, wager_amount, actual_result, outcome,
                    payout, profit
                ) VALUES (
                    :backtest_id, :game_id, :game_date, :home_team_id, :away_team_id,
                    :bet_type, :game_period, :bet_side, :predicted_value, :confidence, :edge,
                    :odds_line, :odds_price, :wager_amount, :actual_result, :outcome,
                    :payout, :profit
                )
            """)
            
            await self.db.execute(query, {
                "backtest_id": backtest_id,
                "game_id": result.game_id,
                "game_date": result.game_date,
                "home_team_id": result.home_team_id,
                "away_team_id": result.away_team_id,
                "bet_type": result.bet_type.value,
                "game_period": result.game_period.value,
                "bet_side": result.bet_side.value if result.bet_side else None,
                "predicted_value": float(result.predicted_value) if result.predicted_value else None,
                "confidence": result.confidence,
                "edge": result.edge,
                "odds_line": float(result.odds_line) if result.odds_line else None,
                "odds_price": result.odds_price,
                "wager_amount": float(result.wager_amount),
                "actual_result": float(result.actual_result),
                "outcome": result.outcome.value,
                "payout": float(result.payout),
                "profit": float(result.profit),
            })
        
        await self.db.commit()
        self.logger.info("Stored backtest results", backtest_id=backtest_id, count=len(results))

    async def _complete_backtest(self, backtest_id: int):
        """Mark backtest as completed and calculate CLV metrics."""
        query = text("""
            UPDATE backtests 
            SET status = 'completed', completed_at = NOW(), updated_at = NOW()
            WHERE id = :backtest_id
        """)
        await self.db.execute(query, {"backtest_id": backtest_id})
        await self.db.commit()
        self.logger.info("Completed backtest", backtest_id=backtest_id)

    def calculate_clv_metrics(self, results: List[BetResult]) -> Dict:
        """
        Calculate CLV (Closing Line Value) metrics for the backtest.
        
        CLV is the gold standard for measuring betting edge:
        - Positive CLV = got better line than closing (good)
        - Consistently beating closing line = real edge
        """
        clv_values = [r.clv for r in results if r.clv is not None]
        beat_closing = [r.beat_closing_line for r in results if r.beat_closing_line is not None]
        
        if not clv_values:
            return {
                "clv_available": False,
                "avg_clv": 0.0,
                "clv_positive_rate": 0.0,
                "total_clv_bets": 0,
            }
        
        return {
            "clv_available": True,
            "avg_clv": sum(clv_values) / len(clv_values),
            "clv_positive_rate": sum(1 for c in clv_values if c > 0) / len(clv_values),
            "total_clv_bets": len(clv_values),
            "beat_closing_rate": sum(1 for b in beat_closing if b) / len(beat_closing) if beat_closing else 0.0,
            "clv_std": (sum((c - sum(clv_values)/len(clv_values))**2 for c in clv_values) / len(clv_values)) ** 0.5,
        }

    async def get_backtest_summary(self, backtest_id: int) -> Dict:
        """Get comprehensive backtest summary including CLV metrics."""
        query = text("""
            SELECT 
                b.*,
                -- Period breakdown
                COUNT(CASE WHEN r.game_period = 'full' THEN 1 END) as full_game_bets,
                COUNT(CASE WHEN r.game_period = '1H' THEN 1 END) as first_half_bets,
                COUNT(CASE WHEN r.game_period = '1Q' THEN 1 END) as first_quarter_bets,
                -- Bet type breakdown
                COUNT(CASE WHEN r.bet_type = 'spread' THEN 1 END) as spread_bets,
                COUNT(CASE WHEN r.bet_type = 'total' THEN 1 END) as total_bets,
                COUNT(CASE WHEN r.bet_type = 'moneyline' THEN 1 END) as moneyline_bets,
                -- Win rates by type
                AVG(CASE WHEN r.bet_type = 'spread' AND r.outcome = 'win' THEN 1.0 ELSE 0.0 END) as spread_win_rate,
                AVG(CASE WHEN r.bet_type = 'total' AND r.outcome = 'win' THEN 1.0 ELSE 0.0 END) as total_win_rate,
                -- ROI by type
                SUM(CASE WHEN r.bet_type = 'spread' THEN r.profit ELSE 0 END) / 
                    NULLIF(SUM(CASE WHEN r.bet_type = 'spread' THEN r.wager_amount ELSE 0 END), 0) as spread_roi,
                SUM(CASE WHEN r.bet_type = 'total' THEN r.profit ELSE 0 END) / 
                    NULLIF(SUM(CASE WHEN r.bet_type = 'total' THEN r.wager_amount ELSE 0 END), 0) as total_roi,
                -- Average metrics
                AVG(r.confidence) as avg_confidence,
                AVG(r.edge) as avg_edge
            FROM backtests b
            LEFT JOIN backtest_results r ON b.id = r.backtest_id
            WHERE b.id = :backtest_id
            GROUP BY b.id
        """)
        
        result = await self.db.execute(query, {"backtest_id": backtest_id})
        row = result.fetchone()
        
        if not row:
            return {}
        
        return dict(zip(result.keys(), row))

    async def archive_backtest_results(self, backtest_id: int, output_dir: str = "backtest_archives"):
        """
        Archive backtest results to JSON for regression testing.
        
        This allows comparing current model performance against historical baselines.
        """
        summary = await self.get_backtest_summary(backtest_id)
        
        # Get all individual results
        query = text("""
            SELECT * FROM backtest_results WHERE backtest_id = :backtest_id
        """)
        result = await self.db.execute(query, {"backtest_id": backtest_id})
        rows = result.fetchall()
        columns = result.keys()
        
        results = [dict(zip(columns, row)) for row in rows]
        
        # Create archive
        archive = {
            "backtest_id": backtest_id,
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "results_count": len(results),
            "results": results,
        }
        
        # Ensure output directory exists
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Write archive file
        filename = f"backtest_{backtest_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = output_path / filename
        
        with open(filepath, 'w') as f:
            json.dump(archive, f, indent=2, default=str)
        
        self.logger.info("Archived backtest results", filepath=str(filepath))
        return str(filepath)
