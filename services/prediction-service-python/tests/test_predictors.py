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
