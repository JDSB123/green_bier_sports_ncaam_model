#!/usr/bin/env python3
"""
Deep Analysis of Totals Prediction Errors

Goal: Understand WHY our totals MAE is ~13.7 when market is ~10-11
and find what features/patterns can improve predictions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
VALIDATION_RESULTS = ROOT_DIR / "testing" / "data" / "validation_results" / "validation_results.csv"
HISTORICAL_DIR = ROOT_DIR / "testing" / "data" / "historical"
ODDS_DIR = ROOT_DIR / "testing" / "data" / "historical_odds"


def load_validation_data():
    """Load validation results."""
    if not VALIDATION_RESULTS.exists():
        print(f"[ERROR] No validation results at {VALIDATION_RESULTS}")
        return None
    return pd.read_csv(VALIDATION_RESULTS)


def load_odds_data():
    """Load historical odds data."""
    odds_files = list(ODDS_DIR.glob("*.csv"))
    if not odds_files:
        return None

    all_odds = []
    for f in odds_files:
        df = pd.read_csv(f)
        all_odds.append(df)

    return pd.concat(all_odds, ignore_index=True)


def analyze_total_errors(df):
    """Analyze patterns in total prediction errors."""
    print("=" * 72)
    print(" TOTAL PREDICTION ERROR ANALYSIS")
    print("=" * 72)

    # Basic stats
    total_errors = df['total_error'].values
    total_abs_errors = df['total_abs_error'].values

    print(f"\nBasic Statistics:")
    print(f"  Games Analyzed: {len(df)}")
    print(f"  Mean Error (Bias): {np.mean(total_errors):+.2f}")
    print(f"  MAE: {np.mean(total_abs_errors):.2f}")
    print(f"  RMSE: {np.sqrt(np.mean(total_errors**2)):.2f}")
    print(f"  Std Dev: {np.std(total_errors):.2f}")

    # Error distribution
    print(f"\nError Distribution:")
    print(f"  < 5 pts:  {(total_abs_errors < 5).sum()} games ({100*(total_abs_errors < 5).mean():.1f}%)")
    print(f"  5-10 pts: {((total_abs_errors >= 5) & (total_abs_errors < 10)).sum()} games ({100*((total_abs_errors >= 5) & (total_abs_errors < 10)).mean():.1f}%)")
    print(f"  10-15 pts: {((total_abs_errors >= 10) & (total_abs_errors < 15)).sum()} games ({100*((total_abs_errors >= 10) & (total_abs_errors < 15)).mean():.1f}%)")
    print(f"  15-20 pts: {((total_abs_errors >= 15) & (total_abs_errors < 20)).sum()} games ({100*((total_abs_errors >= 15) & (total_abs_errors < 20)).mean():.1f}%)")
    print(f"  > 20 pts: {(total_abs_errors >= 20).sum()} games ({100*(total_abs_errors >= 20).mean():.1f}%)")

    # Over vs Under prediction bias
    over_predictions = total_errors > 0
    under_predictions = total_errors < 0
    print(f"\nOver/Under Prediction Bias:")
    print(f"  Over-predicted (too high): {over_predictions.sum()} games ({100*over_predictions.mean():.1f}%)")
    print(f"  Under-predicted (too low): {under_predictions.sum()} games ({100*under_predictions.mean():.1f}%)")

    if over_predictions.sum() > 0:
        print(f"  Avg Over-prediction: +{np.mean(total_errors[over_predictions]):.2f}")
    if under_predictions.sum() > 0:
        print(f"  Avg Under-prediction: {np.mean(total_errors[under_predictions]):.2f}")


def analyze_by_actual_total(df):
    """Analyze errors by actual total bins."""
    print("\n" + "=" * 72)
    print(" ERROR BY ACTUAL TOTAL (Game Pace)")
    print("=" * 72)

    # Create total bins
    bins = [0, 120, 130, 140, 150, 160, 170, 180, 300]
    labels = ['<120', '120-130', '130-140', '140-150', '150-160', '160-170', '170-180', '>180']

    df['total_bin'] = pd.cut(df['actual_total'], bins=bins, labels=labels)

    print(f"\n{'Total Range':<12} {'Games':>8} {'MAE':>8} {'Bias':>10} {'Over%':>8}")
    print("-" * 50)

    for bin_label in labels:
        bin_data = df[df['total_bin'] == bin_label]
        if len(bin_data) > 0:
            mae = bin_data['total_abs_error'].mean()
            bias = bin_data['total_error'].mean()
            over_pct = (bin_data['total_error'] > 0).mean() * 100
            print(f"{bin_label:<12} {len(bin_data):>8} {mae:>8.2f} {bias:>+10.2f} {over_pct:>7.1f}%")


def analyze_by_predicted_total(df):
    """Analyze errors by predicted total bins."""
    print("\n" + "=" * 72)
    print(" ERROR BY PREDICTED TOTAL")
    print("=" * 72)

    bins = [0, 130, 140, 150, 160, 170, 300]
    labels = ['<130', '130-140', '140-150', '150-160', '160-170', '>170']

    df['pred_total_bin'] = pd.cut(df['pred_total'], bins=bins, labels=labels)

    print(f"\n{'Pred Range':<12} {'Games':>8} {'MAE':>8} {'Bias':>10}")
    print("-" * 40)

    for bin_label in labels:
        bin_data = df[df['pred_total_bin'] == bin_label]
        if len(bin_data) > 0:
            mae = bin_data['total_abs_error'].mean()
            bias = bin_data['total_error'].mean()
            print(f"{bin_label:<12} {len(bin_data):>8} {mae:>8.2f} {bias:>+10.2f}")


def analyze_outliers(df):
    """Analyze the worst predictions."""
    print("\n" + "=" * 72)
    print(" WORST TOTAL PREDICTIONS (|Error| > 30)")
    print("=" * 72)

    outliers = df[df['total_abs_error'] > 30].copy()
    outliers = outliers.sort_values('total_abs_error', ascending=False)

    print(f"\n{len(outliers)} games with |error| > 30 points")
    print("\nTop 15 worst predictions:")
    print(f"{'Home':<25} {'Away':<25} {'Actual':>7} {'Pred':>7} {'Error':>8}")
    print("-" * 80)

    for _, row in outliers.head(15).iterrows():
        print(f"{row['home_team'][:24]:<25} {row['away_team'][:24]:<25} {row['actual_total']:>7.0f} {row['pred_total']:>7.1f} {row['total_error']:>+8.1f}")

    # Pattern analysis on outliers
    print(f"\nOutlier Patterns:")
    print(f"  Over-predicted: {(outliers['total_error'] > 0).sum()} ({100*(outliers['total_error'] > 0).mean():.1f}%)")
    print(f"  Under-predicted: {(outliers['total_error'] < 0).sum()} ({100*(outliers['total_error'] < 0).mean():.1f}%)")
    print(f"  Avg actual total: {outliers['actual_total'].mean():.1f}")
    print(f"  Avg predicted total: {outliers['pred_total'].mean():.1f}")


def analyze_spread_vs_total_correlation(df):
    """Check if spread error correlates with total error."""
    print("\n" + "=" * 72)
    print(" SPREAD vs TOTAL ERROR CORRELATION")
    print("=" * 72)

    correlation = df['spread_abs_error'].corr(df['total_abs_error'])
    print(f"\nCorrelation between |spread error| and |total error|: {correlation:.3f}")

    # When spread is very wrong, is total also wrong?
    high_spread_error = df[df['spread_abs_error'] > 15]
    print(f"\nWhen spread error > 15 pts ({len(high_spread_error)} games):")
    print(f"  Avg total abs error: {high_spread_error['total_abs_error'].mean():.2f}")

    low_spread_error = df[df['spread_abs_error'] < 5]
    print(f"\nWhen spread error < 5 pts ({len(low_spread_error)} games):")
    print(f"  Avg total abs error: {low_spread_error['total_abs_error'].mean():.2f}")


def analyze_vs_market(df, odds_df):
    """Compare our predictions vs market lines."""
    if odds_df is None:
        print("\n[SKIP] No odds data available for market comparison")
        return

    print("\n" + "=" * 72)
    print(" MODEL vs MARKET COMPARISON")
    print("=" * 72)

    # Merge on date and teams (simplified)
    odds_df['date'] = odds_df['commence_time'].str[:10]

    # Calculate market error vs actual
    if 'total' in odds_df.columns:
        print(f"\nMarket lines available: {len(odds_df)}")
        # Would need actual scores matched to odds to calculate market MAE
        print("  (Need to match odds with results for full comparison)")


def suggest_improvements(df):
    """Suggest potential improvements based on analysis."""
    print("\n" + "=" * 72)
    print(" POTENTIAL IMPROVEMENTS")
    print("=" * 72)

    # Check bias
    bias = df['total_error'].mean()
    if abs(bias) > 2:
        print(f"\n1. BIAS CORRECTION:")
        print(f"   Current bias: {bias:+.2f}")
        print(f"   Suggested adjustment: {-bias:+.2f}")

    # Check by total range
    low_total_games = df[df['actual_total'] < 130]
    high_total_games = df[df['actual_total'] > 160]

    if len(low_total_games) > 50:
        low_bias = low_total_games['total_error'].mean()
        print(f"\n2. LOW SCORING GAMES (<130):")
        print(f"   Count: {len(low_total_games)}")
        print(f"   Bias: {low_bias:+.2f}")
        if low_bias > 5:
            print(f"   Issue: Over-predicting low games significantly")

    if len(high_total_games) > 50:
        high_bias = high_total_games['total_error'].mean()
        print(f"\n3. HIGH SCORING GAMES (>160):")
        print(f"   Count: {len(high_total_games)}")
        print(f"   Bias: {high_bias:+.2f}")
        if high_bias < -5:
            print(f"   Issue: Under-predicting high games significantly")

    # Standard deviation analysis
    std = df['total_error'].std()
    print(f"\n4. VARIANCE REDUCTION:")
    print(f"   Current std dev: {std:.2f}")
    print(f"   Target (market-like): ~10.0")
    if std > 14:
        print(f"   Issue: High variance suggests missing features or unstable model")

    # Outlier percentage
    outlier_pct = (df['total_abs_error'] > 20).mean() * 100
    print(f"\n5. OUTLIER RATE:")
    print(f"   Games with |error| > 20: {outlier_pct:.1f}%")
    if outlier_pct > 15:
        print(f"   Issue: Too many extreme misses")


def main():
    print("\n")
    print("=" * 72)
    print(" NCAAM TOTALS PREDICTION - DEEP ANALYSIS")
    print("=" * 72)

    # Load data
    df = load_validation_data()
    if df is None:
        return 1

    print(f"\nLoaded {len(df)} validation results")

    odds_df = load_odds_data()
    if odds_df is not None:
        print(f"Loaded {len(odds_df)} market lines")

    # Run analyses
    analyze_total_errors(df)
    analyze_by_actual_total(df)
    analyze_by_predicted_total(df)
    analyze_outliers(df)
    analyze_spread_vs_total_correlation(df)
    analyze_vs_market(df, odds_df)
    suggest_improvements(df)

    print("\n" + "=" * 72)
    print(" ANALYSIS COMPLETE")
    print("=" * 72 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
