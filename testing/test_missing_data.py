from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.predictor import prediction_engine


def test_missing_ratings_raises(make_team_ratings):
    dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    away = make_team_ratings("TeamB")

    with pytest.raises(ValueError, match="home_ratings and away_ratings are required"):
        prediction_engine.make_prediction(
            game_id=uuid4(),
            home_team="TeamA",
            away_team="TeamB",
            commence_time=dt,
            home_ratings=None,
            away_ratings=away,
        )