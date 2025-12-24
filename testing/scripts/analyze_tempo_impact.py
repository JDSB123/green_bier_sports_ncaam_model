#!/usr/bin/env python3
"""
Analyze how tempo affects total prediction errors.

Key hypothesis: We're not weighting tempo correctly.
The market likely gives more weight to extreme tempos.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORICAL_DIR = ROOT_DIR / "testing" / "data" / "historical"
VALIDATION_RESULTS = ROOT_DIR / "testing" / "data" / "validation_results" / "validation_results.csv"


def load_data():
    """Load validation results and barttorvik ratings."""
    df = pd.read_csv(VALIDATION_RESULTS)

    # Load ratings
    all_ratings = {}
    for season in range(2019, 2025):
        ratings_path = HISTORICAL_DIR / f"barttorvik_{season}.json"
        if ratings_path.exists():
            with open(ratings_path, 'r') as f:
                data = json.load(f)
            ratings = {}
            for team_data in data:
                if isinstance(team_data, list) and len(team_data) > 10:
                    name = team_data[1].lower()
                    ratings[name] = {
                        'adj_o': float(team_data[4]),
                        'adj_d': float(team_data[6]),
                        'adj_t': float(team_data[44]) if len(team_data) > 44 else 68.0,
                    }
            all_ratings[season] = ratings

    return df, all_ratings


def normalize_name(name: str) -> str:
    """Normalize team name for matching."""
    name = name.lower().strip()
    suffixes = [
        " wildcats", " tigers", " bulldogs", " bears", " eagles",
        " huskies", " cavaliers", " blue devils", " tar heels",
        " spartans", " wolverines", " buckeyes", " hoosiers",
        " boilermakers", " hawkeyes", " badgers", " gophers",
        " jayhawks", " sooners", " longhorns", " aggies", " hawks",
        " razorbacks", " volunteers", " crimson tide", " rebels",
        " gamecocks", " hurricanes", " seminoles", " yellow jackets",
        " red raiders", " horned frogs", " cowboys", " cyclones",
        " mountaineers", " red storm", " fighting irish", " panthers",
        " cardinals", " bearcats", " musketeers", " bluejays",
        " golden eagles", " pirates", " gaels", " dons", " broncos",
        " cougars", " aztecs", " wolf pack", " runnin' rebels",
        " demon deacons", " friars", " golden grizzlies", " blue raiders",
        " blazers", " waves", " colonels", " black bears", " trojans",
        " mavericks", " golden lions",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return name.strip()


def get_team_tempo(name: str, ratings: dict) -> float:
    """Get team tempo from ratings."""
    norm = normalize_name(name)
    if norm in ratings:
        return ratings[norm]['adj_t']
    for key, rating in ratings.items():
        if norm in key or key in norm:
            return rating['adj_t']
    return 68.0  # Default


def main():
    print("\n")
    print("=" * 72)
    print(" TEMPO IMPACT ANALYSIS ON TOTALS")
    print("=" * 72)

    df, all_ratings = load_data()
    print(f"\nLoaded {len(df)} games")

    # Get season from date
    df['season'] = df['date'].str[:4].astype(int)
    df.loc[df['date'].str[5:7].astype(int) < 8, 'season'] = df['season'] - 1

    # Get tempo for each game
    tempos = []
    for _, row in df.iterrows():
        season = row['season']
        if season in all_ratings:
            ratings = all_ratings[season]
            home_t = get_team_tempo(row['home_team'], ratings)
            away_t = get_team_tempo(row['away_team'], ratings)
            avg_t = (home_t + away_t) / 2
        else:
            avg_t = 68.0
        tempos.append(avg_t)

    df['avg_tempo'] = tempos

    # Analyze by tempo bins
    print("\n" + "=" * 72)
    print(" ERROR BY EXPECTED TEMPO")
    print("=" * 72)

    bins = [0, 64, 66, 68, 70, 72, 74, 100]
    labels = ['<64', '64-66', '66-68', '68-70', '70-72', '72-74', '>74']

    df['tempo_bin'] = pd.cut(df['avg_tempo'], bins=bins, labels=labels)

    print(f"\n{'Tempo':<10} {'Games':>8} {'MAE':>8} {'Bias':>10} {'Avg Actual':>12} {'Avg Pred':>12}")
    print("-" * 70)

    for bin_label in labels:
        bin_data = df[df['tempo_bin'] == bin_label]
        if len(bin_data) > 10:
            mae = bin_data['total_abs_error'].mean()
            bias = bin_data['total_error'].mean()
            avg_actual = bin_data['actual_total'].mean()
            avg_pred = bin_data['pred_total'].mean()
            print(f"{bin_label:<10} {len(bin_data):>8} {mae:>8.2f} {bias:>+10.2f} {avg_actual:>12.1f} {avg_pred:>12.1f}")

    # Analyze the relationship between tempo and actual total
    print("\n" + "=" * 72)
    print(" TEMPO vs ACTUAL TOTAL RELATIONSHIP")
    print("=" * 72)

    correlation = df['avg_tempo'].corr(df['actual_total'])
    print(f"\nCorrelation between avg tempo and actual total: {correlation:.3f}")

    # Linear regression: actual_total = a * tempo + b
    from scipy import stats
    slope, intercept, r_value, p_value, std_err = stats.linregress(df['avg_tempo'], df['actual_total'])
    print(f"\nLinear regression: Total = {slope:.2f} * Tempo + {intercept:.1f}")
    print(f"  R-squared: {r_value**2:.3f}")
    print(f"  Meaning: Each +1 in tempo = +{slope:.2f} points in total")

    # Compare to our formula
    # Our formula: Total = (home_eff + away_eff) * tempo / 100
    # If league avg efficiency is 106, then:
    # Total ~ 2 * 106 * tempo / 100 = 2.12 * tempo
    print(f"\nOur formula assumes: Total ~ 2.12 * Tempo")
    print(f"Actual relationship: Total ~ {slope:.2f} * Tempo + {intercept:.1f}")

    # This means we may need a different tempo coefficient
    print("\n" + "=" * 72)
    print(" IMPROVED TEMPO SCALING")
    print("=" * 72)

    # Calculate what tempo coefficient we should use
    # If Total = coef * tempo + constant
    # And our base pred = efficiency * tempo / 100
    # We need to adjust

    avg_efficiency_sum = 2 * 106  # Typical sum of home_eff + away_eff
    current_coef = avg_efficiency_sum / 100
    suggested_coef = slope
    ratio = suggested_coef / current_coef

    print(f"\nCurrent tempo coefficient: {current_coef:.3f}")
    print(f"Actual tempo coefficient: {slope:.3f}")
    print(f"Suggested adjustment: multiply predictions by {ratio:.3f}")

    # Try adjusted predictions
    print("\n" + "=" * 72)
    print(" TESTING TEMPO-ADJUSTED PREDICTIONS")
    print("=" * 72)

    # Method 1: Simple scaling
    df['adjusted_pred_1'] = df['pred_total'] * ratio
    adj_error_1 = abs(df['adjusted_pred_1'] - df['actual_total']).mean()
    bias_1 = (df['adjusted_pred_1'] - df['actual_total']).mean()

    print(f"\nMethod 1: Scale predictions by {ratio:.3f}")
    print(f"  New MAE: {adj_error_1:.2f} (was {df['total_abs_error'].mean():.2f})")
    print(f"  New Bias: {bias_1:+.2f}")

    # Method 2: Use regression formula directly
    df['adjusted_pred_2'] = slope * df['avg_tempo'] + intercept
    adj_error_2 = abs(df['adjusted_pred_2'] - df['actual_total']).mean()
    bias_2 = (df['adjusted_pred_2'] - df['actual_total']).mean()

    print(f"\nMethod 2: Use regression directly (ignore efficiency)")
    print(f"  New MAE: {adj_error_2:.2f}")
    print(f"  New Bias: {bias_2:+.2f}")

    # Method 3: Tempo-weighted blend
    # Predict: base_pred + adjustment based on tempo deviation from mean
    avg_tempo = df['avg_tempo'].mean()
    df['tempo_adjustment'] = (df['avg_tempo'] - avg_tempo) * (slope - current_coef)
    df['adjusted_pred_3'] = df['pred_total'] + df['tempo_adjustment']
    adj_error_3 = abs(df['adjusted_pred_3'] - df['actual_total']).mean()
    bias_3 = (df['adjusted_pred_3'] - df['actual_total']).mean()

    print(f"\nMethod 3: Add tempo adjustment to predictions")
    print(f"  Formula: pred + (tempo - {avg_tempo:.1f}) * {slope - current_coef:.3f}")
    print(f"  New MAE: {adj_error_3:.2f}")
    print(f"  New Bias: {bias_3:+.2f}")

    # Test each method by tempo bin
    print("\n" + "=" * 72)
    print(" ADJUSTED PREDICTIONS BY TEMPO BIN")
    print("=" * 72)

    print(f"\n{'Tempo':<10} {'Old MAE':>10} {'Adj MAE':>10} {'Improvement':>12}")
    print("-" * 50)

    for bin_label in labels:
        bin_data = df[df['tempo_bin'] == bin_label]
        if len(bin_data) > 10:
            old_mae = bin_data['total_abs_error'].mean()
            new_mae = abs(bin_data['adjusted_pred_3'] - bin_data['actual_total']).mean()
            improvement = old_mae - new_mae
            print(f"{bin_label:<10} {old_mae:>10.2f} {new_mae:>10.2f} {improvement:>+12.2f}")

    print("\n" + "=" * 72)
    print(" RECOMMENDATION")
    print("=" * 72)
    print(f"""
The issue is clear: our current formula doesn't weight tempo correctly.

Current formula:
    Total = (Home_Eff + Away_Eff) * Tempo / 100 + calibration

The tempo coefficient (~2.12) is too low. Actual data shows:
    Each +1 in tempo corresponds to +{slope:.2f} points

Proposed fix for totals model:
    1. Add a tempo amplification factor
    2. Or use: tempo_adjustment = (tempo - 68.0) * {slope - current_coef:.3f}
    3. Add this to the base prediction

Expected improvement: {df['total_abs_error'].mean() - adj_error_3:.2f} points reduction in MAE
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
