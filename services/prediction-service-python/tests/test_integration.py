"""
Integration tests for the full prediction pipeline.

Tests the complete flow from data fetch to prediction generation.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.config import settings
from app.models import BetType, MarketOdds, TeamRatings
from app.prediction_engine_v33 import prediction_engine_v33


@pytest.fixture
def sample_home_ratings():
    """Sample home team ratings."""
    return TeamRatings(
        team_name="Duke",
        adj_o=115.5,
        adj_d=95.2,
        tempo=68.5,
        rank=15,
        efg=54.2,
        efgd=46.8,
        tor=16.5,
        tord=20.2,
        orb=32.5,
        drb=72.8,
        ftr=35.2,
        ftrd=28.5,
        two_pt_pct=52.5,
        two_pt_pct_d=45.2,
        three_pt_pct=36.8,
        three_pt_pct_d=32.5,
        three_pt_rate=38.5,
        three_pt_rate_d=35.2,
        barthag=0.875,
        wab=8.5,
    )


@pytest.fixture
def sample_away_ratings():
    """Sample away team ratings."""
    return TeamRatings(
        team_name="North Carolina",
        adj_o=112.8,
        adj_d=98.5,
        tempo=70.2,
        rank=25,
        efg=52.8,
        efgd=48.2,
        tor=17.2,
        tord=18.8,
        orb=30.5,
        drb=71.2,
        ftr=33.5,
        ftrd=30.2,
        two_pt_pct=51.2,
        two_pt_pct_d=46.8,
        three_pt_pct=35.5,
        three_pt_pct_d=33.8,
        three_pt_rate=36.2,
        three_pt_rate_d=34.5,
        barthag=0.825,
        wab=6.8,
    )


@pytest.fixture
def sample_market_odds():
    """Sample market odds."""
    return MarketOdds(
        spread=-5.5,
        spread_home_price=-110,
        spread_away_price=-110,
        total=148.5,
        over_price=-110,
        under_price=-110,
        spread_1h=-2.5,
        spread_1h_home_price=-110,
        spread_1h_away_price=-110,
        total_1h=74.5,
        over_price_1h=-110,
        under_price_1h=-110,
    )


def test_full_prediction_pipeline(
    sample_home_ratings,
    sample_away_ratings,
    sample_market_odds,
):
    """Test the complete prediction pipeline."""
    game_id = uuid4()
    commence_time = datetime.now(UTC)

    # Generate prediction
    prediction = prediction_engine_v33.make_prediction(
        game_id=game_id,
        home_team=sample_home_ratings.team_name,
        away_team=sample_away_ratings.team_name,
        commence_time=commence_time,
        home_ratings=sample_home_ratings,
        away_ratings=sample_away_ratings,
        market_odds=sample_market_odds,
        is_neutral=False,
    )

    # Verify prediction structure
    assert prediction.game_id == game_id
    assert prediction.home_team == "Duke"
    assert prediction.away_team == "North Carolina"
    assert prediction.model_version.startswith("v33")

    # Verify all 4 markets are predicted
    assert prediction.predicted_spread is not None
    assert prediction.predicted_total is not None
    assert prediction.predicted_spread_1h is not None
    assert prediction.predicted_total_1h is not None

    # Verify edges are calculated
    assert prediction.spread_edge >= 0
    assert prediction.total_edge >= 0

    # Generate recommendations
    recommendations = prediction_engine_v33.generate_recommendations(
        prediction,
        sample_market_odds,
    )

    # Verify recommendations structure
    assert isinstance(recommendations, list)

    # If recommendations exist, verify structure
    for rec in recommendations:
        assert rec.game_id == game_id
        assert rec.bet_type in [BetType.SPREAD, BetType.TOTAL, BetType.SPREAD_1H, BetType.TOTAL_1H]
        assert rec.edge >= 0
        assert rec.confidence >= 0
        assert rec.ev_percent is not None
        assert rec.pick_price is not None


def test_prediction_without_odds(
    sample_home_ratings,
    sample_away_ratings,
):
    """Test prediction generation without market odds."""
    game_id = uuid4()
    commence_time = datetime.now(UTC)

    prediction = prediction_engine_v33.make_prediction(
        game_id=game_id,
        home_team=sample_home_ratings.team_name,
        away_team=sample_away_ratings.team_name,
        commence_time=commence_time,
        home_ratings=sample_home_ratings,
        away_ratings=sample_away_ratings,
        market_odds=None,
        is_neutral=False,
    )

    # Should still generate predictions
    assert prediction.predicted_spread is not None
    assert prediction.predicted_total is not None

    # But edges should be 0 without market odds
    assert prediction.spread_edge == 0.0
    assert prediction.total_edge == 0.0


def test_neutral_site_prediction(
    sample_home_ratings,
    sample_away_ratings,
):
    """Test prediction for neutral site game."""
    game_id = uuid4()
    commence_time = datetime.now(UTC)

    prediction_neutral = prediction_engine_v33.make_prediction(
        game_id=game_id,
        home_team=sample_home_ratings.team_name,
        away_team=sample_away_ratings.team_name,
        commence_time=commence_time,
        home_ratings=sample_home_ratings,
        away_ratings=sample_away_ratings,
        market_odds=None,
        is_neutral=True,
    )

    prediction_home = prediction_engine_v33.make_prediction(
        game_id=game_id,
        home_team=sample_home_ratings.team_name,
        away_team=sample_away_ratings.team_name,
        commence_time=commence_time,
        home_ratings=sample_home_ratings,
        away_ratings=sample_away_ratings,
        market_odds=None,
        is_neutral=False,
    )

    # Neutral site should have less home advantage
    # (spread should be less negative or more positive)
    assert prediction_neutral.predicted_spread > prediction_home.predicted_spread


def test_recommendation_filtering(
    sample_home_ratings,
    sample_away_ratings,
):
    """Test that recommendations are properly filtered by edge thresholds."""
    game_id = uuid4()
    commence_time = datetime.now(UTC)

    # Create market odds with very small edge (should be filtered out)
    small_edge_odds = MarketOdds(
        spread=-5.0,  # Very close to model prediction
        spread_home_price=-110,
        spread_away_price=-110,
        total=148.0,
        over_price=-110,
        under_price=-110,
    )

    prediction = prediction_engine_v33.make_prediction(
        game_id=game_id,
        home_team=sample_home_ratings.team_name,
        away_team=sample_away_ratings.team_name,
        commence_time=commence_time,
        home_ratings=sample_home_ratings,
        away_ratings=sample_away_ratings,
        market_odds=small_edge_odds,
        is_neutral=False,
    )

    recommendations = prediction_engine_v33.generate_recommendations(
        prediction,
        small_edge_odds,
    )

    # Should filter out recommendations with edge < threshold
    for rec in recommendations:
        if rec.bet_type == BetType.SPREAD:
            assert rec.edge >= settings.model.min_spread_edge
        elif rec.bet_type == BetType.TOTAL:
            assert rec.edge >= settings.model.min_total_edge


def test_recommendation_ev_gating(
    sample_home_ratings,
    sample_away_ratings,
):
    """Test that recommendations are filtered by EV thresholds."""
    game_id = uuid4()
    commence_time = datetime.now(UTC)

    market_odds = MarketOdds(
        spread=-5.5,
        spread_home_price=-110,
        spread_away_price=-110,
        total=148.5,
        over_price=-110,
        under_price=-110,
    )

    prediction = prediction_engine_v33.make_prediction(
        game_id=game_id,
        home_team=sample_home_ratings.team_name,
        away_team=sample_away_ratings.team_name,
        commence_time=commence_time,
        home_ratings=sample_home_ratings,
        away_ratings=sample_away_ratings,
        market_odds=market_odds,
        is_neutral=False,
    )

    recommendations = prediction_engine_v33.generate_recommendations(
        prediction,
        market_odds,
    )

    # All recommendations should have positive EV
    for rec in recommendations:
        assert rec.ev_percent >= settings.model.min_ev_percent
        assert rec.confidence >= settings.model.min_confidence
