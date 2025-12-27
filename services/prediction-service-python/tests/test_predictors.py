"""
Tests for prediction models.

Tests all 4 independent prediction models:
- FG Spread (v33.6, HCA=5.8)
- FG Total (v33.6, Calibration=+7.0)
- H1 Spread (v33.6, HCA=3.6)
- H1 Total (v33.6, Calibration=+2.7)
"""

import pytest
from app.predictors import (
    fg_spread_model,
    fg_total_model,
    h1_spread_model,
    h1_total_model,
    MarketPrediction,
)
from app.models import TeamRatings


class TestFGSpreadModel:
    """Tests for Full Game Spread model."""

    def test_prediction_returns_market_prediction(self, strong_home_team, mid_away_team):
        """Prediction returns MarketPrediction dataclass."""
        pred = fg_spread_model.predict(strong_home_team, mid_away_team)
        assert isinstance(pred, MarketPrediction)
        assert pred.value is not None
        assert pred.confidence >= 0 and pred.confidence <= 1

    def test_home_favorite_negative_spread(self, strong_home_team, weak_team):
        """Strong home vs weak away should produce negative spread."""
        pred = fg_spread_model.predict(strong_home_team, weak_team)
        assert pred.value < 0, f"Expected negative spread, got {pred.value}"

    def test_away_favorite_positive_spread(self, weak_team, strong_home_team):
        """Weak home vs strong away should produce positive spread."""
        pred = fg_spread_model.predict(weak_team, strong_home_team)
        assert pred.value > 0, f"Expected positive spread, got {pred.value}"

    def test_hca_applied_at_home(self, equal_teams):
        """HCA should be applied for home games."""
        home, away = equal_teams
        pred = fg_spread_model.predict(home, away, is_neutral=False)
        assert pred.hca_applied == 5.8, f"Expected HCA=5.8, got {pred.hca_applied}"

    def test_no_hca_at_neutral(self, equal_teams):
        """HCA should be zero at neutral site."""
        home, away = equal_teams
        pred = fg_spread_model.predict(home, away, is_neutral=True)
        assert pred.hca_applied == 0.0, f"Expected HCA=0 at neutral, got {pred.hca_applied}"

    def test_equal_teams_spread_near_hca(self, equal_teams):
        """Equal teams at home should produce spread close to -HCA."""
        home, away = equal_teams
        pred = fg_spread_model.predict(home, away, is_neutral=False)
        # Spread should be approximately -HCA for equal teams
        assert -8 < pred.value < -3, f"Expected spread ~-5.8, got {pred.value}"

    def test_rest_adjustment_home_b2b(self, strong_home_team, mid_away_team):
        """Home B2B should worsen home spread."""
        baseline = fg_spread_model.predict(strong_home_team, mid_away_team)
        b2b = fg_spread_model.predict(
            strong_home_team, mid_away_team,
            home_rest_days=0, away_rest_days=3
        )
        # B2B should make spread less favorable for home (more positive)
        assert b2b.value > baseline.value, "Home B2B should worsen spread"
        assert b2b.situational_adj != 0, "Situational adjustment should be applied"

    def test_rest_adjustment_away_b2b(self, strong_home_team, mid_away_team):
        """Away B2B should improve home spread."""
        baseline = fg_spread_model.predict(strong_home_team, mid_away_team)
        away_b2b = fg_spread_model.predict(
            strong_home_team, mid_away_team,
            home_rest_days=3, away_rest_days=0
        )
        # Away B2B should make spread more favorable for home (more negative)
        assert away_b2b.value < baseline.value, "Away B2B should improve home spread"

    def test_pick_recommendation_home(self, strong_home_team, mid_away_team):
        """Pick recommendation when model favors home."""
        pred = fg_spread_model.predict(strong_home_team, mid_away_team)
        # If model spread is -10 and market is -6, model favors home
        rec = fg_spread_model.get_pick_recommendation(pred, market_line=-6.0)
        if pred.value < -6.0:
            assert rec["pick"] == "HOME"
        else:
            assert rec["pick"] == "AWAY"


class TestFGTotalModel:
    """Tests for Full Game Total model."""

    def test_prediction_returns_market_prediction(self, strong_home_team, mid_away_team):
        """Prediction returns MarketPrediction dataclass."""
        pred = fg_total_model.predict(strong_home_team, mid_away_team)
        assert isinstance(pred, MarketPrediction)

    def test_calibration_applied(self, strong_home_team, mid_away_team):
        """FG Total calibration (+7.0) should be applied."""
        pred = fg_total_model.predict(strong_home_team, mid_away_team)
        assert pred.calibration_applied == 7.0, f"Expected calibration=7.0, got {pred.calibration_applied}"

    def test_total_in_reasonable_range(self, strong_home_team, mid_away_team):
        """Total should be in reasonable range (100-200)."""
        pred = fg_total_model.predict(strong_home_team, mid_away_team)
        assert 100 < pred.value < 200, f"Total {pred.value} outside reasonable range"

    def test_high_tempo_higher_total(self, strong_home_team, mid_away_team):
        """Higher tempo teams should produce higher totals."""
        # Create a slow-paced version
        slow_home = TeamRatings(
            team_name="Slow Home",
            adj_o=strong_home_team.adj_o,
            adj_d=strong_home_team.adj_d,
            tempo=60.0,  # Much slower
            rank=strong_home_team.rank,
            efg=strong_home_team.efg,
            efgd=strong_home_team.efgd,
            tor=strong_home_team.tor,
            tord=strong_home_team.tord,
            orb=strong_home_team.orb,
            drb=strong_home_team.drb,
            ftr=strong_home_team.ftr,
            ftrd=strong_home_team.ftrd,
            two_pt_pct=strong_home_team.two_pt_pct,
            two_pt_pct_d=strong_home_team.two_pt_pct_d,
            three_pt_pct=strong_home_team.three_pt_pct,
            three_pt_pct_d=strong_home_team.three_pt_pct_d,
            three_pt_rate=strong_home_team.three_pt_rate,
            three_pt_rate_d=strong_home_team.three_pt_rate_d,
            barthag=strong_home_team.barthag,
            wab=strong_home_team.wab,
        )

        fast_pred = fg_total_model.predict(strong_home_team, mid_away_team)
        slow_pred = fg_total_model.predict(slow_home, mid_away_team)

        assert fast_pred.value > slow_pred.value, "Higher tempo should produce higher total"

    def test_no_hca_for_totals(self, equal_teams):
        """Totals should have zero HCA (zero-sum assumption)."""
        home, away = equal_teams
        pred = fg_total_model.predict(home, away, is_neutral=False)
        assert pred.hca_applied == 0.0, f"Expected HCA=0 for totals, got {pred.hca_applied}"


class TestH1SpreadModel:
    """Tests for First Half Spread model."""

    def test_prediction_returns_market_prediction(self, strong_home_team, mid_away_team):
        """Prediction returns MarketPrediction dataclass."""
        pred = h1_spread_model.predict(strong_home_team, mid_away_team)
        assert isinstance(pred, MarketPrediction)

    def test_hca_is_3_6(self, equal_teams):
        """H1 Spread HCA should be 3.6."""
        home, away = equal_teams
        pred = h1_spread_model.predict(home, away, is_neutral=False)
        assert pred.hca_applied == 3.6, f"Expected HCA=3.6, got {pred.hca_applied}"

    def test_1h_spread_smaller_than_fg(self, strong_home_team, mid_away_team):
        """1H spread magnitude should be roughly half of FG spread."""
        fg_pred = fg_spread_model.predict(strong_home_team, mid_away_team)
        h1_pred = h1_spread_model.predict(strong_home_team, mid_away_team)

        ratio = abs(fg_pred.value) / abs(h1_pred.value) if h1_pred.value != 0 else 0
        assert 1.7 < ratio < 2.5, f"FG/1H ratio {ratio:.2f} outside expected 1.7-2.5 range"

    def test_variance_higher_than_fg(self, strong_home_team, mid_away_team):
        """1H variance should be higher than FG variance."""
        fg_pred = fg_spread_model.predict(strong_home_team, mid_away_team)
        h1_pred = h1_spread_model.predict(strong_home_team, mid_away_team)

        assert h1_pred.variance >= fg_pred.variance, "1H variance should be >= FG variance"


class TestH1TotalModel:
    """Tests for First Half Total model."""

    def test_prediction_returns_market_prediction(self, strong_home_team, mid_away_team):
        """Prediction returns MarketPrediction dataclass."""
        pred = h1_total_model.predict(strong_home_team, mid_away_team)
        assert isinstance(pred, MarketPrediction)

    def test_calibration_applied(self, strong_home_team, mid_away_team):
        """H1 Total calibration (+2.7) should be applied."""
        pred = h1_total_model.predict(strong_home_team, mid_away_team)
        assert pred.calibration_applied == 2.7, f"Expected calibration=2.7, got {pred.calibration_applied}"

    def test_1h_total_roughly_half_fg(self, strong_home_team, mid_away_team):
        """1H total should be roughly half of FG total."""
        fg_pred = fg_total_model.predict(strong_home_team, mid_away_team)
        h1_pred = h1_total_model.predict(strong_home_team, mid_away_team)

        ratio = fg_pred.value / h1_pred.value if h1_pred.value > 0 else 0
        assert 1.9 < ratio < 2.2, f"FG/1H total ratio {ratio:.2f} outside expected 1.9-2.2 range"

    def test_total_in_reasonable_range(self, strong_home_team, mid_away_team):
        """1H total should be in reasonable range (50-100)."""
        pred = h1_total_model.predict(strong_home_team, mid_away_team)
        assert 50 < pred.value < 100, f"1H total {pred.value} outside reasonable range"


class TestModelIndependence:
    """Tests to verify models are truly independent."""

    def test_fg_spread_hca_independent(self):
        """FG Spread HCA should be 5.8 (from its own backtest)."""
        assert fg_spread_model.HCA == 5.8

    def test_h1_spread_hca_independent(self):
        """H1 Spread HCA should be 3.6 (from its own backtest)."""
        assert h1_spread_model.HCA == 3.6

    def test_fg_total_calibration_independent(self):
        """FG Total calibration should be 7.0."""
        assert fg_total_model.CALIBRATION == 7.0

    def test_h1_total_calibration_independent(self):
        """H1 Total calibration should be 2.7."""
        assert h1_total_model.CALIBRATION == 2.7

    def test_model_versions(self):
        """All models should be v33.6."""
        assert "33.6" in fg_spread_model.MODEL_VERSION
        assert "33.6" in fg_total_model.MODEL_VERSION
        assert "33.6" in h1_spread_model.MODEL_VERSION
        assert "33.6" in h1_total_model.MODEL_VERSION


class TestMinEdgeThresholds:
    """Tests for MIN_EDGE betting thresholds (v33.6.1 fix)."""

    def test_fg_spread_min_edge(self):
        """FG Spread MIN_EDGE should be 2.0 (from backtest ROI analysis)."""
        assert fg_spread_model.MIN_EDGE == 2.0, f"Expected 2.0, got {fg_spread_model.MIN_EDGE}"

    def test_fg_total_min_edge(self):
        """FG Total MIN_EDGE should be 3.0 (from backtest ROI analysis)."""
        assert fg_total_model.MIN_EDGE == 3.0, f"Expected 3.0, got {fg_total_model.MIN_EDGE}"

    def test_h1_spread_min_edge(self):
        """H1 Spread MIN_EDGE should be 3.5."""
        assert h1_spread_model.MIN_EDGE == 3.5, f"Expected 3.5, got {h1_spread_model.MIN_EDGE}"

    def test_h1_total_min_edge(self):
        """H1 Total MIN_EDGE should be 2.0."""
        assert h1_total_model.MIN_EDGE == 2.0, f"Expected 2.0, got {h1_total_model.MIN_EDGE}"

    def test_fg_total_max_edge(self):
        """FG Total MAX_EDGE should be 6.0 (avoid extremes)."""
        assert fg_total_model.MAX_EDGE == 6.0, f"Expected 6.0, got {fg_total_model.MAX_EDGE}"

    def test_h1_total_max_edge(self):
        """H1 Total MAX_EDGE should be 3.5 (1H has more variance)."""
        assert h1_total_model.MAX_EDGE == 3.5, f"Expected 3.5, got {h1_total_model.MAX_EDGE}"


class TestConfidenceThresholds:
    """Tests for confidence calculation (v33.6.1 fix for 1H Total)."""

    def test_h1_total_confidence_above_threshold(self, strong_home_team, mid_away_team):
        """H1 Total confidence should be >= 0.50 for standard games (v33.6.1 fix)."""
        pred = h1_total_model.predict(strong_home_team, mid_away_team)
        # Standard games should have reasonable confidence
        # Base confidence is now 0.68, only extreme adjustments should drop below 0.50
        assert pred.confidence >= 0.50, f"H1 Total confidence {pred.confidence} too low for any game"
        # For typical games, should be around 0.65-0.72
        assert pred.confidence <= 0.72, f"H1 Total confidence {pred.confidence} unexpectedly high"

    def test_fg_spread_confidence_range(self, strong_home_team, mid_away_team):
        """FG Spread confidence should be in valid range."""
        pred = fg_spread_model.predict(strong_home_team, mid_away_team)
        assert 0.50 <= pred.confidence <= 0.95, f"Confidence {pred.confidence} out of range"

    def test_h1_spread_confidence_range(self, strong_home_team, mid_away_team):
        """H1 Spread confidence should be in valid range."""
        pred = h1_spread_model.predict(strong_home_team, mid_away_team)
        assert 0.50 <= pred.confidence <= 0.88, f"Confidence {pred.confidence} out of range"

    def test_fg_total_confidence_range(self, strong_home_team, mid_away_team):
        """FG Total confidence should be in valid range."""
        pred = fg_total_model.predict(strong_home_team, mid_away_team)
        assert 0.50 <= pred.confidence <= 0.80, f"Confidence {pred.confidence} out of range"


class TestExtremeTotalRanges:
    """Tests for extreme total detection (v33.6.1 feature)."""

    def test_fg_total_extreme_thresholds_exist(self):
        """Verify extreme total thresholds are defined in engine."""
        from app.prediction_engine_v33 import (
            FG_TOTAL_MIN_RELIABLE,
            FG_TOTAL_MAX_RELIABLE,
            H1_TOTAL_MIN_RELIABLE,
            H1_TOTAL_MAX_RELIABLE,
        )
        assert FG_TOTAL_MIN_RELIABLE == 120.0
        assert FG_TOTAL_MAX_RELIABLE == 170.0
        assert H1_TOTAL_MIN_RELIABLE == 55.0
        assert H1_TOTAL_MAX_RELIABLE == 85.0

    def test_fg_total_prediction_in_typical_range(self, strong_home_team, mid_away_team):
        """FG Total prediction for typical teams should be in reliable range."""
        from app.prediction_engine_v33 import FG_TOTAL_MIN_RELIABLE, FG_TOTAL_MAX_RELIABLE
        pred = fg_total_model.predict(strong_home_team, mid_away_team)
        # Strong vs mid-tier should produce a total in the reliable range
        assert FG_TOTAL_MIN_RELIABLE <= pred.value <= FG_TOTAL_MAX_RELIABLE, \
            f"FG Total {pred.value} outside reliable range for typical matchup"

    def test_h1_total_prediction_in_typical_range(self, strong_home_team, mid_away_team):
        """H1 Total prediction for typical teams should be in reliable range."""
        from app.prediction_engine_v33 import H1_TOTAL_MIN_RELIABLE, H1_TOTAL_MAX_RELIABLE
        pred = h1_total_model.predict(strong_home_team, mid_away_team)
        assert H1_TOTAL_MIN_RELIABLE <= pred.value <= H1_TOTAL_MAX_RELIABLE, \
            f"H1 Total {pred.value} outside reliable range for typical matchup"


class TestPickRecommendations:
    """Tests for pick recommendation logic."""

    def test_fg_spread_pick_recommendation_structure(self, strong_home_team, mid_away_team):
        """FG Spread pick recommendation has required fields."""
        pred = fg_spread_model.predict(strong_home_team, mid_away_team)
        rec = fg_spread_model.get_pick_recommendation(pred, market_line=-6.0)

        assert "pick" in rec
        assert "edge" in rec
        assert "strength" in rec
        assert "recommended" in rec
        assert "confidence" in rec
        assert rec["pick"] in ["HOME", "AWAY"]

    def test_fg_total_pick_recommendation_structure(self, strong_home_team, mid_away_team):
        """FG Total pick recommendation has required fields."""
        pred = fg_total_model.predict(strong_home_team, mid_away_team)
        rec = fg_total_model.get_pick_recommendation(pred, market_line=145.0)

        assert "pick" in rec
        assert "edge" in rec
        assert "strength" in rec
        assert "recommended" in rec
        assert rec["pick"] in ["OVER", "UNDER"]

    def test_h1_total_avoid_high_edge(self, strong_home_team, mid_away_team):
        """H1 Total should recommend AVOID for edges > MAX_EDGE."""
        pred = h1_total_model.predict(strong_home_team, mid_away_team)
        # Create artificial high edge by using very different market line
        rec = h1_total_model.get_pick_recommendation(pred, market_line=pred.value - 10.0)

        # Edge of 10 points should trigger AVOID
        assert rec["abs_edge"] > h1_total_model.MAX_EDGE
        assert rec["strength"] == "AVOID"
        assert rec["recommended"] == False


class TestLeagueAverages:
    """Tests for league average constants."""

    def test_league_avg_tempo(self):
        """All models should use league avg tempo of 67.6."""
        assert fg_spread_model.LEAGUE_AVG_TEMPO == 67.6
        assert fg_total_model.LEAGUE_AVG_TEMPO == 67.6
        assert h1_spread_model.LEAGUE_AVG_TEMPO == 67.6
        assert h1_total_model.LEAGUE_AVG_TEMPO == 67.6

    def test_league_avg_efficiency(self):
        """All models should use league avg efficiency of 105.5."""
        assert fg_spread_model.LEAGUE_AVG_EFFICIENCY == 105.5
        assert fg_total_model.LEAGUE_AVG_EFFICIENCY == 105.5
        assert h1_spread_model.LEAGUE_AVG_EFFICIENCY == 105.5


class TestCLVTracking:
    """Tests for Closing Line Value (CLV) tracking."""

    def test_clv_method_exists_on_recommendation(self):
        """BettingRecommendation should have calculate_clv method."""
        from app.models import BettingRecommendation, BetType, Pick, BetTier
        from uuid import uuid4
        from datetime import datetime

        rec = BettingRecommendation(
            game_id=uuid4(),
            home_team="Duke",
            away_team="UNC",
            commence_time=datetime.now(),
            bet_type=BetType.SPREAD,
            pick=Pick.HOME,
            line=-6.5,
            model_line=-8.0,
            market_line=-6.5,
            edge=1.5,
            confidence=0.70,
            ev_percent=5.0,
            implied_prob=0.55,
            market_prob=0.52,
            kelly_fraction=0.03,
            recommended_units=1.0,
            bet_tier=BetTier.STANDARD,
        )

        # Method should exist
        assert hasattr(rec, 'calculate_clv')

        # Call should work
        rec.calculate_clv(closing_line=-7.0, captured_at=datetime.now())

        # CLV should be calculated (we bet HOME -6.5, it closed at -7.0)
        # We got value because line moved against home
        assert rec.closing_line == -7.0
        assert rec.clv is not None
        assert rec.clv == 0.5  # -6.5 - (-7.0) = +0.5 CLV

    def test_clv_over_calculation(self):
        """Test CLV calculation for OVER total bet."""
        from app.models import BettingRecommendation, BetType, Pick, BetTier
        from uuid import uuid4
        from datetime import datetime

        rec = BettingRecommendation(
            game_id=uuid4(),
            home_team="Duke",
            away_team="UNC",
            commence_time=datetime.now(),
            bet_type=BetType.TOTAL,
            pick=Pick.OVER,
            line=145.0,
            model_line=150.0,
            market_line=145.0,
            edge=5.0,
            confidence=0.68,
            ev_percent=8.0,
            implied_prob=0.55,
            market_prob=0.50,
            kelly_fraction=0.05,
            recommended_units=1.5,
            bet_tier=BetTier.MEDIUM,
        )

        # Line moved up to 148 - we got value on OVER
        rec.calculate_clv(closing_line=148.0, captured_at=datetime.now())

        assert rec.clv == 3.0  # 148 - 145 = +3 CLV on OVER
