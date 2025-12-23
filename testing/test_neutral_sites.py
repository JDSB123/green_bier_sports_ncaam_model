from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.config import settings
from app.predictor import prediction_engine


def test_neutral_site_prediction(make_team_ratings):
    """
    Neutral-site games should not receive Home Court Advantage (HCA).

    For two identical teams:
    - Neutral: spread should be ~0 (no HCA)
    - Non-neutral: spread should be ~-HCA (home favored by HCA)
    """
    dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    home = make_team_ratings("TeamA")
    away = make_team_ratings("TeamB")

    pred_neutral = prediction_engine.make_prediction(
        game_id=uuid4(),
        home_team="TeamA",
        away_team="TeamB",
        commence_time=dt,
        home_ratings=home,
        away_ratings=away,
        is_neutral=True,
    )
    pred_home = prediction_engine.make_prediction(
        game_id=uuid4(),
        home_team="TeamA",
        away_team="TeamB",
        commence_time=dt,
        home_ratings=home,
        away_ratings=away,
        is_neutral=False,
    )

    assert pred_neutral.predicted_spread == pytest.approx(0.0, abs=1e-6)
    assert pred_home.predicted_spread == pytest.approx(
        -settings.model.home_court_advantage_spread, abs=1e-6
    )