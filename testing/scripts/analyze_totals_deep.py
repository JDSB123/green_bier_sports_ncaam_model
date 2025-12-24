#!/usr/bin/env python3
"""
Deep analysis of what drives total prediction errors.

Key question: If tempo only explains 6% of variance, what explains the rest?
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

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


def get_team_stats(name: str, ratings: dict) -> dict:
    """Get team stats from ratings."""
    norm = normalize_name(name)
    if norm in ratings:
        return ratings[norm]
    for key, rating in ratings.items():
        if norm in key or key in norm:
            return rating
    return {'adj_o': 106.0, 'adj_d': 106.0, 'adj_t': 68.0}


def main():
    print("\n")
    print("=" * 72)
    print(" DEEP ANALYSIS: WHAT DRIVES TOTAL PREDICTION ERRORS?")
    print("=" * 72)

    df, all_ratings = load_data()
    print(f"\nLoaded {len(df)} games")

    # Get season from date
    df['season'] = df['date'].str[:4].astype(int)
    df.loc[df['date'].str[5:7].astype(int) < 8, 'season'] = df['season'] - 1

    # Get detailed stats for each game
    stats_list = []
    for _, row in df.iterrows():
        season = row['season']
        if season in all_ratings:
            ratings = all_ratings[season]
            home = get_team_stats(row['home_team'], ratings)
            away = get_team_stats(row['away_team'], ratings)
        else:
            home = {'adj_o': 106.0, 'adj_d': 106.0, 'adj_t': 68.0}
            away = {'adj_o': 106.0, 'adj_d': 106.0, 'adj_t': 68.0}

        stats_list.append({
            'home_adj_o': home['adj_o'],
            'home_adj_d': home['adj_d'],
            'home_adj_t': home['adj_t'],
            'away_adj_o': away['adj_o'],
            'away_adj_d': away['adj_d'],
            'away_adj_t': away['adj_t'],
        })

    stats_df = pd.DataFrame(stats_list)
    df = pd.concat([df, stats_df], axis=1)

    # Calculate derived features
    df['avg_tempo'] = (df['home_adj_t'] + df['away_adj_t']) / 2
    df['avg_off'] = (df['home_adj_o'] + df['away_adj_o']) / 2
    df['avg_def'] = (df['home_adj_d'] + df['away_adj_d']) / 2
    df['net_efficiency'] = df['avg_off'] - df['avg_def']
    df['total_efficiency'] = df['home_adj_o'] + df['away_adj_o'] + df['home_adj_d'] + df['away_adj_d']
    df['expected_total_simple'] = (df['home_adj_o'] + df['away_adj_d'] + df['away_adj_o'] + df['home_adj_d'] - 2*106) * df['avg_tempo'] / 100

    # Analyze correlations with total error
    print("\n" + "=" * 72)
    print(" CORRELATIONS WITH TOTAL ERROR")
    print("=" * 72)

    features = [
        ('avg_tempo', 'Average Tempo'),
        ('avg_off', 'Average Offensive Efficiency'),
        ('avg_def', 'Average Defensive Efficiency'),
        ('net_efficiency', 'Net Efficiency (Off - Def)'),
        ('total_efficiency', 'Total Efficiency Sum'),
        ('actual_spread', 'Actual Spread (blowout factor)'),
        ('pred_total', 'Predicted Total'),
        ('actual_total', 'Actual Total'),
    ]

    print(f"\n{'Feature':<35} {'Correlation':>12} {'R-squared':>12}")
    print("-" * 60)

    for feature, name in features:
        corr = df[feature].corr(df['total_error'])
        r2 = corr ** 2
        print(f"{name:<35} {corr:>+12.3f} {r2:>12.3f}")

    # The key insight: actual_total has HIGH correlation with error
    # This means: we under-predict high games, over-predict low games

    print("\n" + "=" * 72)
    print(" THE CORE PROBLEM: REGRESSION TO MEAN")
    print("=" * 72)

    # Calculate what our predictions should have been
    # Using actual totals vs predicted
    print("\nOur predictions cluster around the mean, but actuals have more variance:")
    print(f"  Actual total std dev: {df['actual_total'].std():.2f}")
    print(f"  Predicted total std dev: {df['pred_total'].std():.2f}")
    print(f"  Ratio (pred/actual): {df['pred_total'].std() / df['actual_total'].std():.3f}")

    # This shows we're not predicting enough variance!
    # Our predictions are too conservative

    # Test: What if we amplified predictions away from mean?
    print("\n" + "=" * 72)
    print(" TESTING: VARIANCE AMPLIFICATION")
    print("=" * 72)

    pred_mean = df['pred_total'].mean()

    # Try different amplification factors
    print(f"\n{'Amp Factor':>12} {'New MAE':>10} {'New Std':>10} {'New Bias':>12}")
    print("-" * 50)

    for amp in [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]:
        # Amplify: new_pred = mean + amp * (old_pred - mean)
        df['amp_pred'] = pred_mean + amp * (df['pred_total'] - pred_mean)
        new_mae = abs(df['amp_pred'] - df['actual_total']).mean()
        new_std = df['amp_pred'].std()
        new_bias = (df['amp_pred'] - df['actual_total']).mean()
        print(f"{amp:>12.1f} {new_mae:>10.2f} {new_std:>10.2f} {new_bias:>+12.2f}")

    # Find optimal amplification
    best_amp = 1.0
    best_mae = df['total_abs_error'].mean()

    for amp in np.arange(1.0, 2.0, 0.05):
        df['amp_pred'] = pred_mean + amp * (df['pred_total'] - pred_mean)
        new_mae = abs(df['amp_pred'] - df['actual_total']).mean()
        if new_mae < best_mae:
            best_mae = new_mae
            best_amp = amp

    print(f"\nOptimal amplification: {best_amp:.2f}")
    print(f"Best possible MAE with amplification: {best_mae:.2f}")

    # But this still won't match market!
    # Let's look at what features we might be missing

    print("\n" + "=" * 72)
    print(" WHAT FEATURES MIGHT WE BE MISSING?")
    print("=" * 72)

    # Check if certain game types have systematic errors

    # 1. Blowouts vs close games
    df['is_blowout'] = abs(df['actual_spread']) > 20
    print(f"\nBlowout games (|spread| > 20): {df['is_blowout'].sum()}")
    print(f"  MAE for blowouts: {df[df['is_blowout']]['total_abs_error'].mean():.2f}")
    print(f"  MAE for close games: {df[~df['is_blowout']]['total_abs_error'].mean():.2f}")
    print(f"  Bias for blowouts: {df[df['is_blowout']]['total_error'].mean():+.2f}")
    print(f"  Bias for close games: {df[~df['is_blowout']]['total_error'].mean():+.2f}")

    # 2. High vs low efficiency games
    df['high_eff'] = df['avg_off'] > 108
    print(f"\nHigh efficiency games (avg_off > 108): {df['high_eff'].sum()}")
    print(f"  MAE for high eff: {df[df['high_eff']]['total_abs_error'].mean():.2f}")
    print(f"  MAE for normal eff: {df[~df['high_eff']]['total_abs_error'].mean():.2f}")

    # 3. Season timing (early vs late season ratings stability)
    df['month'] = df['date'].str[5:7].astype(int)
    early_season = df[df['month'].isin([11, 12])]
    late_season = df[df['month'].isin([2, 3])]

    print(f"\nSeason timing:")
    print(f"  Early season (Nov-Dec): {len(early_season)} games, MAE: {early_season['total_abs_error'].mean():.2f}")
    print(f"  Late season (Feb-Mar): {len(late_season)} games, MAE: {late_season['total_abs_error'].mean():.2f}")

    # 4. Looking at extreme predictions
    print("\n" + "=" * 72)
    print(" EXTREME GAME ANALYSIS")
    print("=" * 72)

    # Games where actual total was extremely low
    very_low = df[df['actual_total'] < 110]
    print(f"\nVery low scoring games (<110 total): {len(very_low)}")
    if len(very_low) > 0:
        print(f"  Our avg prediction: {very_low['pred_total'].mean():.1f}")
        print(f"  Actual avg: {very_low['actual_total'].mean():.1f}")
        print(f"  Error: {very_low['total_error'].mean():+.1f}")

    # Games where actual total was extremely high
    very_high = df[df['actual_total'] > 180]
    print(f"\nVery high scoring games (>180 total): {len(very_high)}")
    if len(very_high) > 0:
        print(f"  Our avg prediction: {very_high['pred_total'].mean():.1f}")
        print(f"  Actual avg: {very_high['actual_total'].mean():.1f}")
        print(f"  Error: {very_high['total_error'].mean():+.1f}")

    print("\n" + "=" * 72)
    print(" KEY INSIGHT: INHERENT VARIANCE LIMIT")
    print("=" * 72)

    # The fundamental issue is that basketball games have high variance
    # Even the market can't predict perfectly
    # Let's estimate what MAE is achievable

    # If we just predicted the mean total for every game:
    mean_total = df['actual_total'].mean()
    naive_mae = abs(df['actual_total'] - mean_total).mean()
    print(f"\nNaive model (always predict {mean_total:.1f}): MAE = {naive_mae:.2f}")
    print(f"Our model: MAE = {df['total_abs_error'].mean():.2f}")
    print(f"Market estimate: MAE ~ 10-11")

    # What percentage improvement over naive is theoretically possible?
    print(f"\nImprovement over naive:")
    print(f"  Our model: {100 * (1 - df['total_abs_error'].mean() / naive_mae):.1f}%")
    print(f"  Market: ~{100 * (1 - 10.5 / naive_mae):.1f}%")

    # Calculate what features would help close the gap
    gap = df['total_abs_error'].mean() - 10.5
    print(f"\nGap to close: {gap:.2f} points MAE")
    print(f"This requires identifying {gap / df['total_abs_error'].mean() * 100:.1f}% more signal")

    return 0


if __name__ == "__main__":
    sys.exit(main())
