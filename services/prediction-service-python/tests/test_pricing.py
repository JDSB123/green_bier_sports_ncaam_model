import math
from datetime import UTC, datetime
from uuid import uuid4

from app.models import BetType, MarketOdds
from app.prediction_engine_v33 import prediction_engine_v33


def _american_to_prob(odds: int) -> float:
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def test_spread_home_pick_uses_home_price(strong_home_team, weak_team):
    market_odds = MarketOdds(
        spread=-10.0,
        spread_home_price=-105,
        spread_away_price=-115,
    )

    pred = prediction_engine_v33.make_prediction(
        game_id=uuid4(),
        home_team=strong_home_team.team_name,
        away_team=weak_team.team_name,
        commence_time=datetime.now(UTC),
        home_ratings=strong_home_team,
        away_ratings=weak_team,
        market_odds=market_odds,
        is_neutral=False,
    )

    recs = prediction_engine_v33.generate_recommendations(pred, market_odds)
    spread_recs = [r for r in recs if r.bet_type == BetType.SPREAD]
    assert spread_recs, "Expected at least one SPREAD recommendation"

    rec = spread_recs[0]
    assert rec.pick.value == "HOME"
    assert rec.pick_price == -105

    # Market probability should be derived from the same pick-specific price
    assert math.isclose(rec.market_prob, _american_to_prob(-105), rel_tol=1e-12)


def test_spread_away_pick_uses_away_price(weak_team, strong_home_team):
    market_odds = MarketOdds(
        spread=10.0,
        spread_home_price=-105,
        spread_away_price=-115,
    )

    pred = prediction_engine_v33.make_prediction(
        game_id=uuid4(),
        home_team=weak_team.team_name,
        away_team=strong_home_team.team_name,
        commence_time=datetime.now(UTC),
        home_ratings=weak_team,
        away_ratings=strong_home_team,
        market_odds=market_odds,
        is_neutral=False,
    )

    recs = prediction_engine_v33.generate_recommendations(pred, market_odds)
    spread_recs = [r for r in recs if r.bet_type == BetType.SPREAD]
    assert spread_recs, "Expected at least one SPREAD recommendation"

    rec = spread_recs[0]
    assert rec.pick.value == "AWAY"
    assert rec.pick_price == -115

    # Market probability should be derived from the same pick-specific price
    assert math.isclose(rec.market_prob, _american_to_prob(-115), rel_tol=1e-12)
