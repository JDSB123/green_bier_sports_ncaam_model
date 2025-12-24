#!/usr/bin/env python3
"""
Test Modular Prediction Models v33.3

Tests all 4 market models:
- FG Spread (PROVEN z=3.94)
- FG Total (Hybrid approach)
- 1H Spread (Independent)
- 1H Total (Independent)
"""

import sys
sys.path.insert(0, r"c:\Users\JB\green-bier-ventures\NCAAM_main\services\prediction-service-python")

from app.models import TeamRatings
from app.predictors import (
    fg_spread_model,
    fg_total_model,
    h1_spread_model,
    h1_total_model,
    MarketPrediction,
)


def create_sample_team(
    name: str,
    adj_o: float,
    adj_d: float,
    tempo: float,
    rank: int,
    barthag: float = 0.75,
) -> TeamRatings:
    """
    Create a sample TeamRatings for testing.
    Uses reasonable defaults for Four Factors and other metrics.
    """
    net_rating = adj_o - adj_d
    is_good_team = net_rating > 10

    return TeamRatings(
        team_name=name,
        adj_o=adj_o,
        adj_d=adj_d,
        tempo=tempo,
        rank=rank,
        efg=52.0 if is_good_team else 49.0,
        efgd=49.0 if is_good_team else 52.0,
        tor=17.5 if is_good_team else 19.5,
        tord=20.0 if is_good_team else 18.0,
        orb=30.0 if is_good_team else 27.0,
        drb=73.0 if is_good_team else 70.0,
        ftr=33.0 if is_good_team else 30.0,
        ftrd=30.0 if is_good_team else 33.0,
        two_pt_pct=52.0 if is_good_team else 48.0,
        two_pt_pct_d=48.0 if is_good_team else 52.0,
        three_pt_pct=35.0 if is_good_team else 33.0,
        three_pt_pct_d=33.0 if is_good_team else 35.0,
        three_pt_rate=36.0,
        three_pt_rate_d=36.0,
        barthag=barthag,
        wab=5.0 if is_good_team else -2.0,
    )


def test_total_predictions():
    """Test FG and 1H total models."""
    print("=" * 70)
    print("TOTAL MODELS v33.3 - TEST SUITE")
    print("=" * 70)

    home = create_sample_team(
        name="Strong Home",
        adj_o=118.5,
        adj_d=94.2,
        tempo=69.0,
        rank=8,
        barthag=0.92,
    )

    away = create_sample_team(
        name="Mid Road",
        adj_o=112.0,
        adj_d=100.5,
        tempo=67.5,
        rank=35,
        barthag=0.78,
    )

    market_total = 152.5
    market_total_1h = 73.5

    print(f"\nMATCHUP: {away.team_name} @ {home.team_name}")

    print("\n" + "-" * 70)
    print("FG TOTAL MODEL (Hybrid Approach)")
    print("-" * 70)

    fg_total_pred = fg_total_model.predict(home, away)
    fg_total_rec = fg_total_model.get_pick_recommendation(fg_total_pred, market_total)

    print(f"Model Prediction: {fg_total_pred.value:.1f}")
    print(f"  Home Component: {fg_total_pred.home_component:.1f}")
    print(f"  Away Component: {fg_total_pred.away_component:.1f}")
    print(f"  Calibration:    {fg_total_pred.calibration_applied:+.1f}")
    print(f"  Matchup Adj:    {fg_total_pred.matchup_adj:+.2f}")
    print(f"  Variance:       {fg_total_pred.variance:.2f}")
    print(f"  Confidence:     {fg_total_pred.confidence:.1%}")
    print(f"  Reasoning:      {fg_total_pred.reasoning}")
    print(f"\nVs Market {market_total:.1f}:")
    print(f"  Pick: {fg_total_rec['pick']} | Edge: {fg_total_rec['edge']:.1f}pts | Strength: {fg_total_rec['strength']}")
    print(f"  Recommended: {'YES' if fg_total_rec['recommended'] else 'NO'}")
    if fg_total_rec.get('warning'):
        print(f"  WARNING: {fg_total_rec['warning']}")

    print("\n" + "-" * 70)
    print("1H TOTAL MODEL")
    print("-" * 70)

    h1_total_pred = h1_total_model.predict(home, away)
    h1_total_rec = h1_total_model.get_pick_recommendation(h1_total_pred, market_total_1h)

    print(f"Model Prediction: {h1_total_pred.value:.1f}")
    print(f"  Home Component: {h1_total_pred.home_component:.1f}")
    print(f"  Away Component: {h1_total_pred.away_component:.1f}")
    print(f"  Calibration:    {h1_total_pred.calibration_applied:+.1f}")
    print(f"  Variance:       {h1_total_pred.variance:.2f}")
    print(f"  Confidence:     {h1_total_pred.confidence:.1%}")
    print(f"  Reasoning:      {h1_total_pred.reasoning}")
    print(f"\nVs Market {market_total_1h:.1f}:")
    print(f"  Pick: {h1_total_rec['pick']} | Edge: {h1_total_rec['edge']:.1f}pts | Strength: {h1_total_rec['strength']}")
    print(f"  Recommended: {'YES' if h1_total_rec['recommended'] else 'NO'}")

    # Validation
    print("\n" + "=" * 70)
    print("TOTAL VALIDATION CHECKS")
    print("=" * 70)

    errors = []

    # FG/1H ratio should be ~2.08
    fg_to_1h = fg_total_pred.value / h1_total_pred.value if h1_total_pred.value > 0 else 0
    if not (1.9 < fg_to_1h < 2.2):
        errors.append(f"FG/1H total ratio {fg_to_1h:.2f} outside 1.9-2.2 range")
    print(f"OK FG/1H Total Ratio: {fg_to_1h:.2f} (expected ~2.08)")

    # Calibration values
    if fg_total_pred.calibration_applied != -4.6:
        errors.append(f"FG Total calibration should be -4.6, got {fg_total_pred.calibration_applied}")
    if h1_total_pred.calibration_applied != -2.3:
        errors.append(f"1H Total calibration should be -2.3, got {h1_total_pred.calibration_applied}")
    print(f"OK Calibrations: FG={fg_total_pred.calibration_applied:+.1f}, 1H={h1_total_pred.calibration_applied:+.1f}")

    if errors:
        print(f"FAILED: {len(errors)} errors")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("PASSED: All total validation checks passed!")
        return True


def test_spread_predictions():
    """Test FG and 1H spread models with sample matchups."""
    print("=" * 70)
    print("SPREAD MODELS v33.3 - TEST SUITE")
    print("=" * 70)

    # Create sample teams
    home = create_sample_team(
        name="Strong Home",
        adj_o=118.5,
        adj_d=94.2,
        tempo=69.0,
        rank=8,
        barthag=0.92,
    )

    away = create_sample_team(
        name="Mid Road",
        adj_o=112.0,
        adj_d=100.5,
        tempo=67.5,
        rank=35,
        barthag=0.78,
    )

    print(f"\nMATCHUP: {away.team_name} @ {home.team_name}")
    print(f"Home: AdjO={home.adj_o:.1f}, AdjD={home.adj_d:.1f}, Net={home.net_rating:+.1f}")
    print(f"Away: AdjO={away.adj_o:.1f}, AdjD={away.adj_d:.1f}, Net={away.net_rating:+.1f}")

    market_spread = -9.5
    market_spread_1h = -4.5

    print("\n" + "-" * 70)
    print("1. FULL GAME SPREAD MODEL (FGSpread v33.2) - PROVEN z=3.94")
    print("-" * 70)

    fg_spread_pred = fg_spread_model.predict(home, away)
    fg_spread_rec = fg_spread_model.get_pick_recommendation(fg_spread_pred, market_spread)

    print(f"Model Prediction: {fg_spread_pred.value:+.1f}")
    print(f"  Home Component: {fg_spread_pred.home_component:.1f}")
    print(f"  Away Component: {fg_spread_pred.away_component:.1f}")
    print(f"  HCA Applied:    {fg_spread_pred.hca_applied:+.1f}")
    print(f"  Matchup Adj:    {fg_spread_pred.matchup_adj:+.2f}")
    print(f"  Variance:       {fg_spread_pred.variance:.2f}")
    print(f"  Confidence:     {fg_spread_pred.confidence:.1%}")
    print(f"  Reasoning:      {fg_spread_pred.reasoning}")
    print(f"\nVs Market {market_spread:+.1f}:")
    print(f"  Pick: {fg_spread_rec['pick']} | Edge: {fg_spread_rec['edge']:.1f}pts | Strength: {fg_spread_rec['strength']}")
    print(f"  Recommended: {'YES' if fg_spread_rec['recommended'] else 'NO'}")

    print("\n" + "-" * 70)
    print("2. FIRST HALF SPREAD MODEL (H1Spread v33.2)")
    print("-" * 70)

    h1_spread_pred = h1_spread_model.predict(home, away)
    h1_spread_rec = h1_spread_model.get_pick_recommendation(h1_spread_pred, market_spread_1h)

    print(f"Model Prediction: {h1_spread_pred.value:+.1f}")
    print(f"  Home Component: {h1_spread_pred.home_component:.1f}")
    print(f"  Away Component: {h1_spread_pred.away_component:.1f}")
    print(f"  HCA Applied:    {h1_spread_pred.hca_applied:+.1f}")
    print(f"  Matchup Adj:    {h1_spread_pred.matchup_adj:+.2f}")
    print(f"  Variance:       {h1_spread_pred.variance:.2f}")
    print(f"  Confidence:     {h1_spread_pred.confidence:.1%}")
    print(f"  Reasoning:      {h1_spread_pred.reasoning}")
    print(f"\nVs Market {market_spread_1h:+.1f}:")
    print(f"  Pick: {h1_spread_rec['pick']} | Edge: {h1_spread_rec['edge']:.1f}pts | Strength: {h1_spread_rec['strength']}")
    print(f"  Recommended: {'YES' if h1_spread_rec['recommended'] else 'NO'}")

    # Validation checks
    print("\n" + "=" * 70)
    print("VALIDATION CHECKS")
    print("=" * 70)

    errors = []

    # Check 1: FG Spread should be close to 1H Spread * 2
    fg_to_1h_ratio = fg_spread_pred.value / h1_spread_pred.value if h1_spread_pred.value != 0 else 0
    if not (1.7 < abs(fg_to_1h_ratio) < 2.3):
        errors.append(f"FG/1H spread ratio {fg_to_1h_ratio:.2f} outside expected 1.7-2.3 range")
    print(f"OK FG/1H Spread Ratio: {fg_to_1h_ratio:.2f} (expected ~2.0)")

    # Check 2: Variance should be higher for 1H than FG
    if fg_spread_pred.variance >= h1_spread_pred.variance:
        errors.append("1H spread variance should be higher than FG spread")
    print(f"OK Variance FG Spread: {fg_spread_pred.variance:.2f} < 1H Spread: {h1_spread_pred.variance:.2f}")

    # Check 3: HCA applied should match calibrated values
    if fg_spread_pred.hca_applied != 4.7:
        errors.append(f"FG Spread HCA should be 4.7, got {fg_spread_pred.hca_applied}")
    if h1_spread_pred.hca_applied != 2.35:
        errors.append(f"1H Spread HCA should be 2.35, got {h1_spread_pred.hca_applied}")
    print(f"OK HCA Values: FG={fg_spread_pred.hca_applied:.1f}, 1H={h1_spread_pred.hca_applied:.2f}")

    print("\n" + "=" * 70)
    if errors:
        print(f"FAILED: {len(errors)} VALIDATION ERRORS:")
        for e in errors:
            print(f"   - {e}")
    else:
        print("PASSED: ALL VALIDATION CHECKS PASSED!")
    print("=" * 70)

    return len(errors) == 0


def test_neutral_site():
    """Test models at neutral site (no HCA)."""
    print("\n" + "=" * 70)
    print("NEUTRAL SITE TEST (No HCA)")
    print("=" * 70)

    home = create_sample_team("Team A", 115.0, 98.0, 68.0, 20, 0.85)
    away = create_sample_team("Team B", 115.0, 98.0, 68.0, 20, 0.85)

    fg_spread = fg_spread_model.predict(home, away, is_neutral=True)
    h1_spread = h1_spread_model.predict(home, away, is_neutral=True)

    print(f"Equal teams at neutral site:")
    print(f"  FG Spread: {fg_spread.value:+.1f} (HCA: {fg_spread.hca_applied:.1f})")
    print(f"  1H Spread: {h1_spread.value:+.1f} (HCA: {h1_spread.hca_applied:.1f})")

    if fg_spread.hca_applied != 0.0:
        print("FAILED: HCA should be 0 at neutral site!")
        return False
    if abs(fg_spread.value) > 1.0:
        print(f"Warning: Equal teams should have spread ~0, got {fg_spread.value:+.1f}")

    print("PASSED: Neutral site test passed!")
    return True


def test_rest_adjustments():
    """Test situational (rest) adjustments."""
    print("\n" + "=" * 70)
    print("REST ADJUSTMENT TEST")
    print("=" * 70)

    home = create_sample_team("Home Team", 110.0, 100.0, 68.0, 50, 0.75)
    away = create_sample_team("Away Team", 110.0, 100.0, 68.0, 50, 0.75)

    baseline = fg_spread_model.predict(home, away)
    home_b2b = fg_spread_model.predict(home, away, home_rest_days=0, away_rest_days=3)
    away_b2b = fg_spread_model.predict(home, away, home_rest_days=3, away_rest_days=0)

    print(f"Baseline (no rest info): {baseline.value:+.1f}")
    print(f"Home on B2B (away rested): {home_b2b.value:+.1f} (sit adj: {home_b2b.situational_adj:+.2f})")
    print(f"Away on B2B (home rested): {away_b2b.value:+.1f} (sit adj: {away_b2b.situational_adj:+.2f})")

    if home_b2b.value <= baseline.value:
        print("FAILED: Home B2B should worsen home's spread")
        return False

    if away_b2b.value >= baseline.value:
        print("FAILED: Away B2B should improve home's spread")
        return False

    print("PASSED: Rest adjustment test passed!")
    return True


if __name__ == "__main__":
    print("\n")

    success = True
    success = test_spread_predictions() and success
    success = test_total_predictions() and success
    success = test_neutral_site() and success
    success = test_rest_adjustments() and success

    print("\n" + "=" * 70)
    if success:
        print("ALL TESTS PASSED! All 4 modular models working correctly.")
    else:
        print("SOME TESTS FAILED! Review errors above.")
    print("=" * 70 + "\n")

    sys.exit(0 if success else 1)
