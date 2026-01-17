#!/usr/bin/env python3
"""Analyze backtest results to find patterns in losses."""
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

import pandas as pd


def main():
    results_file = Path("testing/results/historical/fg_spread_results_20260116_173511.csv")

    if not results_file.exists():
        print(f"Results file not found: {results_file}")
        return 1

    df = pd.read_csv(results_file)

    print('='*80)
    print('FG SPREAD BACKTEST ANALYSIS (2024-2025)')
    print('='*80)

    # Normalize outcome to lowercase
    df['outcome'] = df['outcome'].str.lower()

    wins = (df['outcome'] == 'win').sum()
    losses = (df['outcome'] == 'loss').sum()
    pushes = (df['outcome'] == 'push').sum()

    print('\nOVERALL PERFORMANCE:')
    print(f'  Total Bets: {len(df):,}')
    print(f'  Record: {wins}W - {losses}L - {pushes}P')
    print(f'  Win Rate: {wins / (wins + losses) * 100:.1f}%')
    print(f'  Total Profit: ${df["profit"].sum():,.2f}')
    print(f'  ROI: {df["profit"].sum() / df["wager"].sum() * 100:.2f}%')
    print(f'  Avg Edge: {df["edge"].mean():.2f} points')

    # Analyze by bet side
    print('\n' + '='*80)
    print('PERFORMANCE BY BET SIDE')
    print('='*80)
    for side in sorted(df['bet_side'].unique()):
        side_df = df[df['bet_side'] == side]
        side_wins = (side_df['outcome'] == 'win').sum()
        side_losses = (side_df['outcome'] == 'loss').sum()
        side_roi = side_df["profit"].sum()/side_df["wager"].sum()*100
        print(f'{side:10s}: {len(side_df):4d} bets, {side_wins:3d}W/{side_losses:3d}L ({side_wins/(side_wins+side_losses)*100:5.1f}%), ROI: {side_roi:7.2f}%')

    # Analyze by edge ranges
    print('\n' + '='*80)
    print('PERFORMANCE BY EDGE RANGE')
    print('='*80)
    df['edge_bucket'] = pd.cut(df['edge'], bins=[0, 2, 5, 10, 20, 100], labels=['1.5-2pts', '2-5pts', '5-10pts', '10-20pts', '20+pts'])
    for bucket in df['edge_bucket'].cat.categories:
        bucket_df = df[df['edge_bucket'] == bucket]
        if len(bucket_df) > 0:
            bucket_wins = (bucket_df['outcome'] == 'win').sum()
            bucket_losses = (bucket_df['outcome'] == 'loss').sum()
            if bucket_wins + bucket_losses > 0:
                bucket_roi = bucket_df["profit"].sum()/bucket_df["wager"].sum()*100
                print(f'{str(bucket):10s}: {len(bucket_df):4d} bets, {bucket_wins:3d}W/{bucket_losses:3d}L ({bucket_wins/(bucket_wins+bucket_losses)*100:5.1f}%), ROI: {bucket_roi:7.2f}%')

    # Analyze by season
    print('\n' + '='*80)
    print('PERFORMANCE BY SEASON')
    print('='*80)
    for season in sorted(df['season'].unique()):
        season_df = df[df['season'] == season]
        season_wins = (season_df['outcome'] == 'win').sum()
        season_losses = (season_df['outcome'] == 'loss').sum()
        season_roi = season_df["profit"].sum()/season_df["wager"].sum()*100
        print(f'{season}: {len(season_df):4d} bets, {season_wins:3d}W/{season_losses:3d}L ({season_wins/(season_wins+season_losses)*100:5.1f}%), ROI: {season_roi:7.2f}%')

    # Find best/worst performing teams
    print('\n' + '='*80)
    print('BEST PERFORMING TEAMS (min 15 bets)')
    print('='*80)
    team_performance = []
    for team in set(df['home_team'].tolist() + df['away_team'].tolist()):
        team_df = df[(df['home_team'] == team) | (df['away_team'] == team)]
        if len(team_df) >= 15:
            roi = team_df['profit'].sum() / team_df['wager'].sum() * 100
            team_wins = (team_df['outcome'] == 'win').sum()
            team_losses = (team_df['outcome'] == 'loss').sum()
            team_performance.append((team, len(team_df), team_wins, team_losses, roi))

    team_performance.sort(key=lambda x: x[4], reverse=True)
    for team, bets, w, l, roi in team_performance[:10]:
        print(f'{team:28s}: {bets:3d} bets, {w:3d}W/{l:3d}L, ROI: {roi:7.2f}%')

    print('\n' + '='*80)
    print('WORST PERFORMING TEAMS (min 15 bets)')
    print('='*80)
    for team, bets, w, l, roi in team_performance[-10:]:
        print(f'{team:28s}: {bets:3d} bets, {w:3d}W/{l:3d}L, ROI: {roi:7.2f}%')

    # Analyze prediction accuracy
    print('\n' + '='*80)
    print('PREDICTION ACCURACY BY SPREAD RANGE')
    print('='*80)
    df['pred_bucket'] = pd.cut(df['predicted_line'],
                               bins=[-100, -10, -5, -2, 2, 5, 10, 100],
                               labels=['Big Fav (10+)', 'Fav (5-10)', 'Small Fav (2-5)', 'PK (-2 to 2)', 'Small Dog (2-5)', 'Dog (5-10)', 'Big Dog (10+)'])
    for bucket in df['pred_bucket'].cat.categories:
        bucket_df = df[df['pred_bucket'] == bucket]
        if len(bucket_df) > 0:
            bucket_wins = (bucket_df['outcome'] == 'win').sum()
            bucket_losses = (bucket_df['outcome'] == 'loss').sum()
            if bucket_wins + bucket_losses > 0:
                bucket_roi = bucket_df["profit"].sum()/bucket_df["wager"].sum()*100
                print(f'{str(bucket):18s}: {len(bucket_df):4d} bets, {bucket_wins:3d}W/{bucket_losses:3d}L ({bucket_wins/(bucket_wins+bucket_losses)*100:5.1f}%), ROI: {bucket_roi:7.2f}%')

    print('\n' + '='*80)
    print('KEY INSIGHTS')
    print('='*80)

    # Calculate key metrics
    home_df = df[df['bet_side'] == 'home']
    away_df = df[df['bet_side'] == 'away']

    home_roi = home_df["profit"].sum()/home_df["wager"].sum()*100 if len(home_df) > 0 else 0
    away_roi = away_df["profit"].sum()/away_df["wager"].sum()*100 if len(away_df) > 0 else 0

    high_edge_df = df[df['edge'] > 10]
    low_edge_df = df[df['edge'] <= 2]

    high_edge_roi = high_edge_df["profit"].sum()/high_edge_df["wager"].sum()*100 if len(high_edge_df) > 0 else 0
    low_edge_roi = low_edge_df["profit"].sum()/low_edge_df["wager"].sum()*100 if len(low_edge_df) > 0 else 0

    print('\n1. Home vs Away Bias:')
    print(f'   - Betting home: {home_roi:+.2f}% ROI')
    print(f'   - Betting away: {away_roi:+.2f}% ROI')
    if abs(home_roi - away_roi) > 5:
        print(f'   ⚠️  SIGNIFICANT BIAS: {"Home" if home_roi > away_roi else "Away"} bets perform {abs(home_roi - away_roi):.1f}% better')

    print('\n2. Edge Calibration:')
    print(f'   - High edge (>10pts): {high_edge_roi:+.2f}% ROI on {len(high_edge_df)} bets')
    print(f'   - Low edge (1.5-2pts): {low_edge_roi:+.2f}% ROI on {len(low_edge_df)} bets')
    if high_edge_roi < 0:
        print('   ⚠️  HIGH EDGE BETS LOSING: Model edge calculation may be miscalibrated')

    print('\n3. Season Trend:')
    s2024_roi = df[df['season'] == 2024]["profit"].sum()/df[df['season'] == 2024]["wager"].sum()*100
    s2025_roi = df[df['season'] == 2025]["profit"].sum()/df[df['season'] == 2025]["wager"].sum()*100
    print(f'   - 2024: {s2024_roi:+.2f}% ROI')
    print(f'   - 2025: {s2025_roi:+.2f}% ROI')
    print(f'   {"✓ IMPROVING" if s2025_roi > s2024_roi else "✗ DECLINING"}: {abs(s2025_roi - s2024_roi):.1f}% {"improvement" if s2025_roi > s2024_roi else "decline"}')

    print('\n' + '='*80)

    return 0

if __name__ == "__main__":
    sys.exit(main())
