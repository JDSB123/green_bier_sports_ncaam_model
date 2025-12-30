"""
Manual matchup runner for NCAA predictions without a database dependency.

This helper uses hard-coded Barttorvik-like ratings so you can explore matchups
such as Utah vs. Washington when the full Docker stack (Postgres/Redis/the odds
API) is unavailable.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Dict

# Ensure the service root is first on the import path (same trick as tests/conftest.py)
SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.models import MarketOdds, TeamRatings
from app.prediction_engine_v33 import prediction_engine_v33

TEAM_RATING_PRESETS: Dict[str, Dict[str, object]] = {
    "utah": {
        "team_name": "Utah Utes",
        "adj_o": 114.2,
        "adj_d": 101.1,
        "tempo": 66.0,
        "rank": 36,
        "efg": 52.8,
        "efgd": 47.4,
        "tor": 15.1,
        "tord": 18.9,
        "orb": 31.0,
        "drb": 71.5,
        "ftr": 33.8,
        "ftrd": 29.8,
        "two_pt_pct": 52.2,
        "two_pt_pct_d": 47.6,
        "three_pt_pct": 34.4,
        "three_pt_pct_d": 34.1,
        "three_pt_rate": 33.5,
        "three_pt_rate_d": 32.0,
        "barthag": 0.84,
        "wab": 5.6,
    },
    "washington": {
        "team_name": "Washington Huskies",
        "adj_o": 109.7,
        "adj_d": 101.8,
        "tempo": 67.3,
        "rank": 58,
        "efg": 51.7,
        "efgd": 48.3,
        "tor": 16.5,
        "tord": 18.6,
        "orb": 29.0,
        "drb": 70.9,
        "ftr": 32.2,
        "ftrd": 30.7,
        "two_pt_pct": 51.3,
        "two_pt_pct_d": 48.5,
        "three_pt_pct": 34.9,
        "three_pt_pct_d": 35.0,
        "three_pt_rate": 35.2,
        "three_pt_rate_d": 34.1,
        "barthag": 0.70,
        "wab": 1.9,
    },
}


def _rating(name: str) -> TeamRatings:
    """Return the preset ratings for a team name."""
    key = name.strip().lower()
    payload = TEAM_RATING_PRESETS.get(key)
    if payload is None:
        raise ValueError(f"No rating preset for '{name}'. Available: {sorted(TEAM_RATING_PRESETS)}")
    return TeamRatings(**payload)


def _build_market(
    spread: float,
    total: float,
    spread_home_price: int,
    spread_away_price: int,
    over_price: int,
    under_price: int,
) -> MarketOdds:
    """Construct a MarketOdds instance with optional 1H values derived from the full-game line."""
    return MarketOdds(
        spread=spread,
        spread_home_price=spread_home_price,
        spread_away_price=spread_away_price,
        total=total,
        over_price=over_price,
        under_price=under_price,
        spread_1h=round(spread / 2.0, 1),
        spread_1h_home_price=spread_home_price,
        spread_1h_away_price=spread_away_price,
        total_1h=round(total / 2.0, 1),
        over_price_1h=over_price,
        under_price_1h=under_price,
    )


def _print_prediction(prediction, recs, home, away, market):
    """Emit a concise summary of what the model produced."""
    print(f"Manual matchup: {away} @ {home} ({datetime.now(timezone.utc).isoformat()})")
    print("-" * 68)
    print(f" Model spread (home perspective): {prediction.predicted_spread:+.1f}")
    print(f" Market spread:                    {market.spread:+.1f}")
    print(f" Model total:                      {prediction.predicted_total:.1f}")
    print(f" Market total:                     {market.total:.1f}")
    print(f" Spread edge:                      {prediction.spread_edge:.2f}")
    print(f" Total edge:                       {prediction.total_edge:.2f}")
    print("-" * 68)
    if not recs:
        print(" No recommendations (edge/confidence clamps did not pass).")
        return

    for rec in recs:
        pick = rec.pick.value
        line = rec.line
        price = rec.pick_price
        print(
            f" {rec.bet_type.value.ljust(10)} | pick={pick:6} | "
            f"line={line:+.1f} | market={rec.market_line:+.1f} | "
            f"edge={rec.edge:.2f} | conf={rec.confidence:.2f} | "
            f"EV%={rec.ev_percent:.1f} | price={price}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual Utah vs Washington prediction without the full stack.")
    parser.add_argument("--home", default="Utah", help="Home team (preset available).")
    parser.add_argument("--away", default="Washington", help="Away team (preset available).")
    parser.add_argument("--spread", type=float, default=-3.5, help="Full-game spread (home perspective).")
    parser.add_argument("--total", type=float, default=137.5, help="Full-game total.")
    parser.add_argument("--spread-home-price", type=int, default=-110, help="Home price for full-game spread.")
    parser.add_argument("--spread-away-price", type=int, default=-110, help="Away price for full-game spread.")
    parser.add_argument("--over-price", type=int, default=-110, help="Over price for full-game total.")
    parser.add_argument("--under-price", type=int, default=-110, help="Under price for full-game total.")

    args = parser.parse_args()

    home_ratings = _rating(args.home)
    away_ratings = _rating(args.away)
    market = _build_market(
        spread=args.spread,
        total=args.total,
        spread_home_price=args.spread_home_price,
        spread_away_price=args.spread_away_price,
        over_price=args.over_price,
        under_price=args.under_price,
    )

    prediction = prediction_engine_v33.make_prediction(
        game_id=uuid4(),
        home_team=home_ratings.team_name,
        away_team=away_ratings.team_name,
        commence_time=datetime.now(timezone.utc),
        home_ratings=home_ratings,
        away_ratings=away_ratings,
        market_odds=market,
        is_neutral=False,
    )
    recs = prediction_engine_v33.generate_recommendations(prediction, market)

    _print_prediction(prediction, recs, home_ratings.team_name, away_ratings.team_name, market)


if __name__ == "__main__":
    main()
