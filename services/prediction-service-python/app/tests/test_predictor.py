"""
Unit tests for BarttorvikPredictor - Core prediction engine.

Tests cover:
1. Basic prediction formulas (spread, total, 1H)
2. HCA application (home vs neutral)
3. Matchup adjustments (ORB/TOR/FTR edge)
4. Situational adjustments (rest days, B2B)
5. Dynamic variance calculations
7. Edge cases and boundary conditions
"""

import math
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.models import TeamRatings, MarketOdds, BetType, Pick
from app.predictor import BarttorkvikPredictor, PredictionEngine, PredictorOutput
from app.situational import RestInfo


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

def make_team(
    name: str,
    adj_o: float = 110.0,
    adj_d: float = 100.0,
    tempo: float = 70.0,
    rank: int = 50,
    efg: float = 52.0,
    efgd: float = 48.0,
    tor: float = 17.0,
    tord: float = 20.0,
    orb: float = 30.0,
    drb: float = 74.0,
    ftr: float = 35.0,
    ftrd: float = 31.0,
    three_pt_rate: float = 35.0,
) -> TeamRatings:
    """Create a TeamRatings with sensible defaults for testing."""
    return TeamRatings(
        team_name=name,
        adj_o=adj_o,
        adj_d=adj_d,
        tempo=tempo,
        rank=rank,
        efg=efg,
        efgd=efgd,
        tor=tor,
        tord=tord,
        orb=orb,
        drb=drb,
        ftr=ftr,
        ftrd=ftrd,
        two_pt_pct=50.0,
        two_pt_pct_d=48.0,
        three_pt_pct=35.0,
        three_pt_pct_d=33.0,
        three_pt_rate=three_pt_rate,
        three_pt_rate_d=33.0,
        barthag=0.85,
        wab=3.0,
    )


def make_neutral_team(name: str, adj_o: float, adj_d: float, tempo: float) -> TeamRatings:
    """Create a team with neutral four-factor values (matchup adj ~0)."""
    return TeamRatings(
        team_name=name,
        adj_o=adj_o,
        adj_d=adj_d,
        tempo=tempo,
        rank=100,
        efg=50.0,
        efgd=50.0,
        tor=18.5,
        tord=18.5,
        orb=28.0,
        drb=72.0,  # 100 - 72 = 28% ORB allowed (league avg)
        ftr=33.0,
        ftrd=33.0,
        two_pt_pct=50.0,
        two_pt_pct_d=50.0,
        three_pt_pct=35.0,
        three_pt_pct_d=35.0,
        three_pt_rate=30.0,
        three_pt_rate_d=30.0,
        barthag=0.50,
        wab=0.0,
    )


@pytest.fixture
def predictor() -> BarttorkvikPredictor:
    """Create a predictor with default settings."""
    return BarttorkvikPredictor()


@pytest.fixture
def engine() -> PredictionEngine:
    """Create a prediction engine with default settings."""
    return PredictionEngine()


# ═══════════════════════════════════════════════════════════════════════════════
# BASIC PREDICTION FORMULA TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBasicPredictions:
    """Test core prediction formulas."""

    def test_predict_returns_predictor_output(self, predictor: BarttorkvikPredictor):
        """Predict should return a PredictorOutput dataclass."""
        home = make_team("Duke", adj_o=115.0, adj_d=95.0)
        away = make_team("UNC", adj_o=110.0, adj_d=100.0)
        
        result = predictor.predict(home, away)
        
        assert isinstance(result, PredictorOutput)
        assert result.spread is not None
        assert result.total is not None
        assert result.spread_1h is not None
        assert result.total_1h is not None

    def test_stronger_home_team_is_favored(self, predictor: BarttorkvikPredictor):
        """A much better home team should have negative spread (favored)."""
        home = make_team("Duke", adj_o=120.0, adj_d=90.0)  # +30 net
        away = make_team("Weak", adj_o=95.0, adj_d=110.0)  # -15 net
        
        result = predictor.predict(home, away)
        
        # Home is much better, so spread should be significantly negative
        assert result.spread < -10, f"Expected home favored by >10, got {result.spread}"

    def test_underdog_home_team_has_positive_spread(self, predictor: BarttorkvikPredictor):
        """A weaker home team should have positive spread (underdog)."""
        home = make_team("Weak", adj_o=95.0, adj_d=110.0)  # -15 net
        away = make_team("Duke", adj_o=120.0, adj_d=90.0)  # +30 net
        
        result = predictor.predict(home, away)
        
        # Away is better, so home spread should be positive (underdog)
        assert result.spread > 5, f"Expected home underdog, got spread {result.spread}"

    def test_evenly_matched_teams_close_to_hca(self, predictor: BarttorkvikPredictor):
        """Evenly matched teams should produce spread ≈ -HCA."""
        home = make_neutral_team("Home", adj_o=106.0, adj_d=106.0, tempo=68.5)
        away = make_neutral_team("Away", adj_o=106.0, adj_d=106.0, tempo=68.5)
        
        result = predictor.predict(home, away)
        
        # Should be close to -HCA (default 3.2)
        expected_hca = predictor.hca_spread
        assert result.spread == pytest.approx(-expected_hca, abs=0.5)

    def test_total_is_reasonable_range(self, predictor: BarttorkvikPredictor):
        """Total should be in reasonable NCAA range (120-180)."""
        home = make_team("Duke", adj_o=115.0, adj_d=95.0, tempo=72.0)
        away = make_team("UNC", adj_o=110.0, adj_d=100.0, tempo=70.0)
        
        result = predictor.predict(home, away)
        
        assert 120 < result.total < 180, f"Total {result.total} out of reasonable range"

    def test_high_tempo_increases_total(self, predictor: BarttorkvikPredictor):
        """Higher tempo teams should produce higher totals."""
        slow_home = make_neutral_team("Slow", adj_o=106.0, adj_d=106.0, tempo=62.0)
        slow_away = make_neutral_team("Slow2", adj_o=106.0, adj_d=106.0, tempo=62.0)
        
        fast_home = make_neutral_team("Fast", adj_o=106.0, adj_d=106.0, tempo=75.0)
        fast_away = make_neutral_team("Fast2", adj_o=106.0, adj_d=106.0, tempo=75.0)
        
        slow_result = predictor.predict(slow_home, slow_away)
        fast_result = predictor.predict(fast_home, fast_away)
        
        assert fast_result.total > slow_result.total + 5

    def test_first_half_total_less_than_full_game(self, predictor: BarttorkvikPredictor):
        """1H total should be roughly 48% of full game total."""
        home = make_team("Duke")
        away = make_team("UNC")
        
        result = predictor.predict(home, away)
        
        ratio = result.total_1h / result.total
        assert 0.40 < ratio < 0.55, f"1H/FG ratio {ratio} outside expected range"

    def test_first_half_spread_scaled_from_full_game(self, predictor: BarttorkvikPredictor):
        """1H spread should be roughly 50% of full game spread magnitude."""
        home = make_team("Duke", adj_o=120.0, adj_d=90.0)
        away = make_team("UNC", adj_o=100.0, adj_d=105.0)
        
        result = predictor.predict(home, away)
        
        # Allow for HCA difference between FG and 1H
        fg_spread_mag = abs(result.spread)
        h1_spread_mag = abs(result.spread_1h)
        
        if fg_spread_mag > 2:  # Only check if meaningful spread
            ratio = h1_spread_mag / fg_spread_mag
            assert 0.35 < ratio < 0.65, f"1H/FG spread ratio {ratio} outside expected range"


# ═══════════════════════════════════════════════════════════════════════════════
# HOME COURT ADVANTAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHomeCourt:
    """Test HCA application."""

    def test_neutral_site_removes_hca_from_spread(self, predictor: BarttorkvikPredictor):
        """Neutral site should remove HCA from spread calculation."""
        home = make_neutral_team("Home", adj_o=110.0, adj_d=100.0, tempo=70.0)
        away = make_neutral_team("Away", adj_o=110.0, adj_d=100.0, tempo=70.0)
        
        home_result = predictor.predict(home, away, is_neutral=False)
        neutral_result = predictor.predict(home, away, is_neutral=True)
        
        spread_diff = home_result.spread - neutral_result.spread
        expected_hca = predictor.hca_spread
        
        # The difference should be approximately -HCA (home advantage removed)
        assert spread_diff == pytest.approx(-expected_hca, abs=0.3)

    def test_neutral_site_removes_hca_from_1h_spread(self, predictor: BarttorkvikPredictor):
        """Neutral site should also affect 1H spread."""
        home = make_team("Duke")
        away = make_team("UNC")
        
        home_result = predictor.predict(home, away, is_neutral=False)
        neutral_result = predictor.predict(home, away, is_neutral=True)
        
        # 1H HCA should also be removed
        h1_diff = home_result.spread_1h - neutral_result.spread_1h
        expected_hca_1h = predictor.hca_spread_1h
        
        # Allow for matchup adjustments scaling
        assert abs(h1_diff + expected_hca_1h) < 1.0

    def test_hca_total_default_is_zero(self, predictor: BarttorkvikPredictor):
        """Default HCA for totals should be 0 (zero-sum assumption)."""
        assert predictor.hca_total == 0.0
        assert predictor.hca_total_1h == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# MATCHUP ADJUSTMENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMatchupAdjustments:
    """Test Four Factors matchup adjustments."""

    def test_rebounding_edge_affects_spread(self, predictor: BarttorkvikPredictor):
        """Team with significant ORB advantage should have better spread."""
        # Home team is elite rebounder
        home = make_team("Duke", orb=35.0, drb=78.0)  # Great rebounding
        away = make_team("UNC", orb=25.0, drb=68.0)   # Poor rebounding
        
        # Baseline with neutral rebounding
        neutral_home = make_team("Duke2")
        neutral_away = make_team("UNC2")
        
        elite_result = predictor.predict(home, away)
        neutral_result = predictor.predict(neutral_home, neutral_away)
        
        # Elite rebounder should be more favored
        assert elite_result.spread < neutral_result.spread

    def test_turnover_edge_affects_spread(self, predictor: BarttorkvikPredictor):
        """Team forcing more turnovers should have spread advantage."""
        # Home team forces turnovers, protects ball
        home = make_team("Duke", tor=14.0, tord=24.0)  # Low TO, forces many
        away = make_team("UNC", tor=22.0, tord=15.0)   # High TO, doesn't force
        
        result = predictor.predict(home, away)
        
        # Should show matchup advantage tracked
        assert result.matchup_adj > 0

    def test_matchup_adj_stored_in_output(self, predictor: BarttorkvikPredictor):
        """PredictorOutput should include matchup adjustment value."""
        home = make_team("Duke")
        away = make_team("UNC")
        
        result = predictor.predict(home, away)
        
        # Matchup adjustment should be tracked
        assert hasattr(result, 'matchup_adj')
        assert isinstance(result.matchup_adj, float)


# ═══════════════════════════════════════════════════════════════════════════════
# SITUATIONAL ADJUSTMENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSituationalAdjustments:
    """Test rest days and B2B adjustments."""

    def test_b2b_penalizes_team(self, predictor: BarttorkvikPredictor):
        """Back-to-back game should penalize that team via situational adjustment."""
        home = make_team("Duke")
        away = make_team("UNC")
        
        # Home is rested, away is B2B
        home_rest = RestInfo(team_name="Duke", days_rest=3, is_back_to_back=False)
        away_rest = RestInfo(team_name="UNC", days_rest=0, is_back_to_back=True)
        
        result = predictor.predict(home, away, home_rest=home_rest, away_rest=away_rest)
        
        # Situational adjustment should be tracked
        assert result.situational_adj is not None
        # Away B2B should create a rest differential advantage for home
        assert result.situational_adj.rest_differential > 0
        assert result.situational_adj.away_is_b2b == True

    def test_home_b2b_helps_away(self, predictor: BarttorkvikPredictor):
        """If home is B2B, situational adjustment should reflect that."""
        home = make_team("Duke")
        away = make_team("UNC")
        
        home_rest = RestInfo(team_name="Duke", days_rest=0, is_back_to_back=True)
        away_rest = RestInfo(team_name="UNC", days_rest=4, is_back_to_back=False)
        
        result = predictor.predict(home, away, home_rest=home_rest, away_rest=away_rest)
        
        # Situational adjustment should reflect home's disadvantage
        assert result.situational_adj is not None
        assert result.situational_adj.home_is_b2b == True
        assert result.situational_adj.rest_differential < 0

    def test_situational_adj_tracked_in_output(self, predictor: BarttorkvikPredictor):
        """PredictorOutput should track situational adjustment."""
        home = make_team("Duke")
        away = make_team("UNC")
        
        home_rest = RestInfo(team_name="Duke", days_rest=3, is_back_to_back=False)
        away_rest = RestInfo(team_name="UNC", days_rest=1, is_back_to_back=False)
        
        result = predictor.predict(home, away, home_rest=home_rest, away_rest=away_rest)
        
        assert result.situational_adj is not None


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC VARIANCE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDynamicVariance:
    """Test dynamic variance based on shooting style."""

    def test_high_3pt_rate_increases_variance(self, predictor: BarttorkvikPredictor):
        """3-point heavy teams should have higher variance."""
        # Both teams are 3-point heavy
        home = make_team("Duke", three_pt_rate=45.0)
        away = make_team("UNC", three_pt_rate=45.0)
        
        result = predictor.predict(home, away)
        
        # Higher 3PT rate should increase variance
        assert result.variance >= predictor.config.base_sigma

    def test_variance_tracked_in_output(self, predictor: BarttorkvikPredictor):
        """PredictorOutput should include variance values."""
        home = make_team("Duke")
        away = make_team("UNC")
        
        result = predictor.predict(home, away)
        
        assert hasattr(result, 'variance')
        assert hasattr(result, 'variance_1h')
        assert result.variance > 0
        assert result.variance_1h > 0


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTION ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPredictionEngine:
    """Test the full PredictionEngine including recommendations."""

    def test_engine_generates_prediction(self, engine: PredictionEngine):
        """Engine should generate a Prediction object."""
        home = make_team("Duke")
        away = make_team("UNC")
        
        prediction = engine.make_prediction(
            game_id=uuid4(),
            home_team="Duke",
            away_team="UNC",
            commence_time=datetime.now(),
            home_ratings=home,
            away_ratings=away,
        )
        
        assert prediction.predicted_spread is not None
        assert prediction.predicted_total is not None

    def test_engine_calculates_edges_with_market_odds(self, engine: PredictionEngine):
        """Engine should calculate edges when market odds provided."""
        home = make_team("Duke", adj_o=115.0, adj_d=95.0)
        away = make_team("UNC", adj_o=105.0, adj_d=105.0)
        
        market = MarketOdds(spread=-7.5, total=145.0)
        
        prediction = engine.make_prediction(
            game_id=uuid4(),
            home_team="Duke",
            away_team="UNC",
            commence_time=datetime.now(),
            home_ratings=home,
            away_ratings=away,
            market_odds=market,
        )
        
        assert prediction.spread_edge >= 0
        assert prediction.total_edge >= 0

    def test_engine_generates_recommendations_with_edge(self, engine: PredictionEngine):
        """Engine should generate recommendations when edge exists."""
        # Create a scenario with obvious edge
        home = make_team("Duke", adj_o=120.0, adj_d=90.0)  # Very strong
        away = make_team("Weak", adj_o=95.0, adj_d=110.0)  # Very weak
        
        # Market undervalues Duke by 10 points
        market = MarketOdds(spread=-5.0, total=145.0)
        
        prediction = engine.make_prediction(
            game_id=uuid4(),
            home_team="Duke",
            away_team="Weak",
            commence_time=datetime.now(),
            home_ratings=home,
            away_ratings=away,
            market_odds=market,
        )
        
        recommendations = engine.generate_recommendations(prediction, market)
        
        # Should have at least one recommendation given the huge edge
        assert len(recommendations) > 0
        
        # First recommendation should be for home spread
        spread_recs = [r for r in recommendations if r.bet_type == BetType.SPREAD]
        if spread_recs:
            assert spread_recs[0].pick == Pick.HOME

    def test_engine_requires_minimum_edge(self, engine: PredictionEngine):
        """Recommendations should only be generated above min edge threshold."""
        home = make_team("Duke", adj_o=110.0, adj_d=100.0)
        away = make_team("UNC", adj_o=109.0, adj_d=101.0)  # Very similar
        
        # Market is very close to model (minimal edge)
        market = MarketOdds(spread=-3.5, total=145.0)
        
        prediction = engine.make_prediction(
            game_id=uuid4(),
            home_team="Duke",
            away_team="UNC",
            commence_time=datetime.now(),
            home_ratings=home,
            away_ratings=away,
            market_odds=market,
        )
        
        recommendations = engine.generate_recommendations(prediction, market)
        
        # All recommendations should have edge >= min threshold
        for rec in recommendations:
            if rec.bet_type in (BetType.SPREAD, BetType.SPREAD_1H):
                assert rec.edge >= engine.config.min_spread_edge
            elif rec.bet_type in (BetType.TOTAL, BetType.TOTAL_1H):
                assert rec.edge >= engine.config.min_total_edge


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES & BOUNDARY CONDITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_identical_teams_neutral_spread(self, predictor: BarttorkvikPredictor):
        """Identical teams on neutral site should have ~0 spread."""
        team = make_neutral_team("Same", adj_o=106.0, adj_d=106.0, tempo=68.5)
        
        result = predictor.predict(team, team, is_neutral=True)
        
        assert result.spread == pytest.approx(0.0, abs=0.5)

    def test_extreme_efficiency_difference(self, predictor: BarttorkvikPredictor):
        """Extreme efficiency differences should produce large spreads for mismatches."""
        elite = make_team("Elite", adj_o=118.0, adj_d=95.0)  # +23 net
        terrible = make_team("Bad", adj_o=95.0, adj_d=108.0)  # -13 net
        
        result = predictor.predict(elite, terrible)
        
        # Strong team should be favored (negative spread)
        assert result.spread < -10

    def test_prediction_is_reproducible(self, predictor: BarttorkvikPredictor):
        """Same inputs should produce same outputs."""
        home = make_team("Duke")
        away = make_team("UNC")
        
        result1 = predictor.predict(home, away)
        result2 = predictor.predict(home, away)
        
        assert result1.spread == result2.spread
        assert result1.total == result2.total

