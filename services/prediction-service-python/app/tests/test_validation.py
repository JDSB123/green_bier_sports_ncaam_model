"""
Unit tests for validation module - odds and ratings validation.
"""

import pytest

from app.validation import (
    validate_spread,
    validate_total,
    validate_moneyline,
    validate_price,
    validate_market_odds,
    validate_team_ratings,
    ValidationSeverity,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SPREAD VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpreadValidation:
    """Test spread value validation."""

    def test_valid_spread_no_issues(self):
        """Normal spread should have no issues."""
        issues = validate_spread(-7.5)
        assert len(issues) == 0

    def test_none_spread_allowed(self):
        """None is valid (no odds available)."""
        issues = validate_spread(None)
        assert len(issues) == 0

    def test_extreme_spread_error(self):
        """Spread beyond bounds should error."""
        issues = validate_spread(-55.0)
        assert len(issues) > 0
        assert issues[0].severity == ValidationSeverity.ERROR

    def test_large_spread_warning(self):
        """Large but valid spread should warn."""
        issues = validate_spread(-40.0)
        assert any(i.severity == ValidationSeverity.WARNING for i in issues)

    def test_positive_spread_valid(self):
        """Positive spread (underdog) is valid."""
        issues = validate_spread(12.5)
        assert len(issues) == 0

    def test_non_numeric_spread_error(self):
        """Non-numeric spread should error."""
        issues = validate_spread("invalid")
        assert len(issues) > 0
        assert issues[0].severity == ValidationSeverity.ERROR


# ═══════════════════════════════════════════════════════════════════════════════
# TOTAL VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTotalValidation:
    """Test total value validation."""

    def test_valid_total_no_issues(self):
        """Normal total should have no issues."""
        issues = validate_total(145.0)
        assert len(issues) == 0

    def test_none_total_allowed(self):
        """None is valid (no odds available)."""
        issues = validate_total(None)
        assert len(issues) == 0

    def test_impossibly_low_total_error(self):
        """Total below minimum should error."""
        issues = validate_total(50.0)
        assert len(issues) > 0
        assert issues[0].severity == ValidationSeverity.ERROR

    def test_impossibly_high_total_error(self):
        """Total above maximum should error."""
        issues = validate_total(250.0)
        assert len(issues) > 0
        assert issues[0].severity == ValidationSeverity.ERROR

    def test_unusual_low_total_warning(self):
        """Unusual but valid low total should warn."""
        issues = validate_total(105.0)
        assert any(i.severity == ValidationSeverity.WARNING for i in issues)

    def test_unusual_high_total_warning(self):
        """Unusual but valid high total should warn."""
        issues = validate_total(190.0)
        assert any(i.severity == ValidationSeverity.WARNING for i in issues)


# ═══════════════════════════════════════════════════════════════════════════════
# MONEYLINE VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMoneylineValidation:
    """Test moneyline value validation."""

    def test_valid_favorite_ml(self):
        """Normal favorite ML should have no issues."""
        issues = validate_moneyline(-150)
        assert len(issues) == 0

    def test_valid_underdog_ml(self):
        """Normal underdog ML should have no issues."""
        issues = validate_moneyline(200)
        assert len(issues) == 0

    def test_none_ml_allowed(self):
        """None is valid (no odds available)."""
        issues = validate_moneyline(None)
        assert len(issues) == 0

    def test_invalid_range_ml_error(self):
        """ML between -100 and +100 is invalid."""
        issues = validate_moneyline(-50)
        assert len(issues) > 0
        assert issues[0].severity == ValidationSeverity.ERROR

    def test_extreme_ml_error(self):
        """ML beyond bounds should error."""
        issues = validate_moneyline(-20000)
        assert len(issues) > 0
        assert issues[0].severity == ValidationSeverity.ERROR


# ═══════════════════════════════════════════════════════════════════════════════
# PRICE (JUICE) VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPriceValidation:
    """Test price/juice value validation."""

    def test_standard_juice_no_issues(self):
        """Standard -110 should have no issues."""
        issues = validate_price(-110)
        assert len(issues) == 0

    def test_none_price_allowed(self):
        """None is valid."""
        issues = validate_price(None)
        assert len(issues) == 0

    def test_positive_price_warning(self):
        """Positive price is unusual for spreads/totals."""
        issues = validate_price(105)
        assert any(i.severity == ValidationSeverity.WARNING for i in issues)

    def test_extreme_juice_warning(self):
        """Very high juice should warn."""
        issues = validate_price(-300)
        assert any(i.severity == ValidationSeverity.WARNING for i in issues)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLETE MARKET ODDS VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarketOddsValidation:
    """Test complete market odds validation."""

    def test_valid_odds_is_valid(self):
        """Valid odds should pass validation."""
        result = validate_market_odds(
            spread=-5.5,
            total=145.0,
            home_ml=-200,
            away_ml=170,
            spread_1h=-2.5,
            total_1h=69.5,  # ~48% of FG total is realistic for 1H
        )
        assert result.is_valid

    def test_invalid_total_fails(self):
        """Invalid total should fail validation."""
        result = validate_market_odds(
            spread=-5.5,
            total=50.0,  # Impossibly low
        )
        assert not result.is_valid
        assert result.has_errors

    def test_1h_total_greater_than_fg_error(self):
        """1H total >= FG total should error."""
        result = validate_market_odds(
            total=140.0,
            total_1h=145.0,  # 1H > FG is impossible
        )
        assert not result.is_valid
        assert any("1H total" in i.message for i in result.issues)

    def test_1h_spread_larger_than_fg_warning(self):
        """1H spread larger magnitude than FG should warn."""
        result = validate_market_odds(
            spread=-5.0,
            spread_1h=-8.0,  # 1H spread larger than FG
        )
        assert result.has_warnings

    def test_both_underdogs_warning(self):
        """Both teams having positive ML should warn."""
        result = validate_market_odds(
            home_ml=120,
            away_ml=105,
        )
        assert result.has_warnings


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM RATINGS VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTeamRatingsValidation:
    """Test team ratings validation."""

    def test_valid_ratings_is_valid(self):
        """Valid ratings should pass validation."""
        result = validate_team_ratings(
            adj_o=115.0,
            adj_d=100.0,
            tempo=70.0,
            efg=52.0,
            efgd=48.0,
            tor=17.0,
            tord=20.0,
            orb=30.0,
            drb=72.0,
        )
        assert result.is_valid

    def test_missing_adj_o_error(self):
        """Missing adj_o should error."""
        result = validate_team_ratings(
            adj_o=None,
            adj_d=100.0,
            tempo=70.0,
            efg=52.0,
            efgd=48.0,
            tor=17.0,
            tord=20.0,
            orb=30.0,
            drb=72.0,
        )
        assert not result.is_valid

    def test_impossible_efficiency_error(self):
        """Efficiency outside bounds should error."""
        result = validate_team_ratings(
            adj_o=150.0,  # Too high
            adj_d=100.0,
            tempo=70.0,
            efg=52.0,
            efgd=48.0,
            tor=17.0,
            tord=20.0,
            orb=30.0,
            drb=72.0,
        )
        assert not result.is_valid

    def test_impossible_net_rating_error(self):
        """Net rating > 50 should error."""
        result = validate_team_ratings(
            adj_o=130.0,
            adj_d=70.0,  # +60 net - impossible
            tempo=70.0,
            efg=52.0,
            efgd=48.0,
            tor=17.0,
            tord=20.0,
            orb=30.0,
            drb=72.0,
        )
        assert not result.is_valid

    def test_invalid_tempo_error(self):
        """Tempo outside bounds should error."""
        result = validate_team_ratings(
            adj_o=110.0,
            adj_d=100.0,
            tempo=95.0,  # Too high
            efg=52.0,
            efgd=48.0,
            tor=17.0,
            tord=20.0,
            orb=30.0,
            drb=72.0,
        )
        assert not result.is_valid

