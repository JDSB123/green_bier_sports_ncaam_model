import pytest

from app.predictor import prediction_engine

def test_missing_ratings():
    # Placeholder test for missing data
    try:
        prediction = prediction_engine.make_prediction(
            game_id="test",
            home_team="TeamA",
            away_team="TeamB",
            commence_time="2025-01-01",
            home_ratings=None,  # Missing
            away_ratings=...,
        )
        assert False, "Should raise exception for missing ratings"
    except ValueError:
        assert True