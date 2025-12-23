
import pytest
from app.predictor import BarttorvikPredictor, SituationalAdjuster
from app.models import TeamRatings

# Sample mock ratings for tests
MOCK_HOME = TeamRatings(
    team_name="Home Team",
    adj_o=110.0, adj_d=90.0, tempo=70.0, rank=1,
    barthag=0.95, wab=5.0, efg=55.0, efgd=45.0,
    tor=15.0, tord=20.0, orb=30.0, drb=70.0,
    ftr=35.0, ftrd=25.0, two_pt_pct=55.0, two_pt_pct_d=45.0,
    three_pt_pct=35.0, three_pt_pct_d=30.0, three_pt_rate=40.0,
    three_pt_rate_d=35.0
)

MOCK_AWAY = TeamRatings(
    team_name="Away Team",
    adj_o=105.0, adj_d=95.0, tempo=68.0, rank=10,
    barthag=0.85, wab=2.0, efg=52.0, efgd=48.0,
    tor=16.0, tord=18.0, orb=28.0, drb=72.0,
    ftr=32.0, ftrd=28.0, two_pt_pct=52.0, two_pt_pct_d=48.0,
    three_pt_pct=34.0, three_pt_pct_d=32.0, three_pt_rate=38.0,
    three_pt_rate_d=36.0
)

@pytest.fixture
def predictor():
    return BarttorvikPredictor()

def test_calculate_spread_neutral(predictor):
    # Neutral site: No HCA
    spread = predictor.calculate_spread(
        home_net=MOCK_HOME.net_rating,
        away_net=MOCK_AWAY.net_rating,
        is_neutral=True
    )
    assert spread == (MOCK_HOME.net_rating - MOCK_AWAY.net_rating)  # Expected: 20 - 10 = 10 (home favored by 10)

def test_calculate_spread_with_hca(predictor):
    # Home site: Add HCA
    spread = predictor.calculate_spread(
        home_net=MOCK_HOME.net_rating,
        away_net=MOCK_AWAY.net_rating,
        is_neutral=False
    )
    expected = (MOCK_HOME.net_rating - MOCK_AWAY.net_rating) + predictor.hca_spread
    assert spread == pytest.approx(expected, 0.1)

def test_situational_adjuster_b2b():
    adjuster = SituationalAdjuster()
    adj = adjuster.calculate_rest_adjustment(
        home_rest_days=0,  # B2B
        away_rest_days=3   # Well-rested
    )
    assert adj < 0  # Penalty for home team

def test_missing_ratings_handling(predictor):
    with pytest.raises(ValueError):
        predictor.predict_spread(None, MOCK_AWAY)  # Should raise on missing ratings
