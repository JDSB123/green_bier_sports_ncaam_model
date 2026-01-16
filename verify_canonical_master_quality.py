#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive verification of canonical_training_data_master.csv quality.

Validates:
1. Single source of truth enforcement
2. Data completeness and coverage
3. Team name canonicalization consistency
4. No data leakage (ratings are N-1)
5. Closing line data availability
6. Market coverage across all required markets
"""
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("=" * 80)
    print("CANONICAL MASTER DATA QUALITY VERIFICATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Load data
    master_path = Path("manifests/canonical_training_data_master.csv")
    if not master_path.exists():
        print(f"❌ CRITICAL: Canonical master not found at {master_path}")
        return 1

    df = pd.read_csv(master_path)
    print(f"✓ Loaded canonical master: {len(df):,} rows, {len(df.columns)} columns\n")

    # 1. CHECK FOR DUPLICATE FILES
    print("-" * 80)
    print("1. SINGLE SOURCE OF TRUTH CHECK")
    print("-" * 80)
    manifests_dir = Path("manifests")
    csv_files = list(manifests_dir.glob("*.csv"))
    non_backup = [f for f in csv_files if '.bak_' not in f.name]

    print(f"CSV files in manifests/:")
    for f in csv_files:
        print(f"  - {f.name} ({f.stat().st_size / 1024 / 1024:.1f} MB)")

    if len(non_backup) == 1 and non_backup[0].name == "canonical_training_data_master.csv":
        print("✓ PASS: Only canonical master exists (backups ignored)\n")
    else:
        print(f"⚠️  WARNING: Found {len(non_backup)} non-backup CSV files\n")

    # 2. SEASON AND DATE COVERAGE
    print("-" * 80)
    print("2. TEMPORAL COVERAGE")
    print("-" * 80)
    df['game_date'] = pd.to_datetime(df['game_date'], errors='coerce')
    seasons = sorted(df['season'].unique())
    print(f"Seasons: {seasons}")
    print(f"Date range: {df['game_date'].min()} to {df['game_date'].max()}")
    print(f"\nGames by season:")
    for season in seasons:
        season_df = df[df['season'] == season]
        print(f"  {season}: {len(season_df):,} games")

    if min(seasons) >= 2023 and max(seasons) >= 2025:
        print("✓ PASS: Covers required canonical window (2023+)\n")
    else:
        print("❌ FAIL: Missing required seasons\n")

    # 3. TEAM NAME CANONICALIZATION
    print("-" * 80)
    print("3. TEAM NAME CANONICALIZATION")
    print("-" * 80)

    # Check which canonical column to use
    canonical_cols = [c for c in df.columns if 'canonical' in c.lower() and 'team' in c.lower()]
    print(f"Team canonical columns found: {canonical_cols}")

    # Count unique team names across different columns
    team_name_cols = [c for c in df.columns if 'team' in c.lower() and 'home' in c.lower()]
    print(f"\nUnique team counts by column:")
    for col in team_name_cols[:5]:  # First 5 team columns
        if col in df.columns:
            unique = df[col].nunique()
            print(f"  {col}: {unique}")

    # Check for consistency
    if 'home_canonical' in df.columns and 'away_canonical' in df.columns:
        unique_canonical = len(set(df['home_canonical'].dropna()) | set(df['away_canonical'].dropna()))
        print(f"\n  Total unique canonical teams: {unique_canonical}")
        if unique_canonical <= 350:  # D1 has ~350 teams
            print(f"✓ PASS: Canonical team count is reasonable\n")
        else:
            print(f"⚠️  WARNING: High canonical team count, may have duplicates\n")
    else:
        print("⚠️  WARNING: home_canonical/away_canonical columns not found\n")

    # 4. MARKET COVERAGE
    print("-" * 80)
    print("4. MARKET DATA COVERAGE")
    print("-" * 80)

    markets = {
        'fg_spread': 'FG Spread',
        'fg_total': 'FG Total',
        'fg_spread_home_price': 'FG Spread Home Price',
        'fg_spread_away_price': 'FG Spread Away Price',
        'fg_total_over_price': 'FG Total Over Price',
        'fg_total_under_price': 'FG Total Under Price',
        'moneyline_home_price': 'Moneyline Home',
        'moneyline_away_price': 'Moneyline Away',
        'h1_spread': 'H1 Spread',
        'h1_total': 'H1 Total',
        'h1_spread_home_price': 'H1 Spread Home Price',
        'h1_spread_away_price': 'H1 Spread Away Price',
        'h1_total_over_price': 'H1 Total Over Price',
        'h1_total_under_price': 'H1 Total Under Price',
    }

    print(f"{'Market':<30} {'Coverage':<15} {'Percentage':<10}")
    print("-" * 55)

    all_good = True
    for col, name in markets.items():
        if col in df.columns:
            coverage = df[col].notna().sum()
            pct = coverage / len(df) * 100
            status = "✓" if pct > 70 else "⚠️" if pct > 50 else "❌"
            print(f"{status} {name:<28} {coverage:>6,} / {len(df):<6,} {pct:>5.1f}%")
            if pct < 70:
                all_good = False
        else:
            print(f"❌ {name:<28} MISSING")
            all_good = False

    if all_good:
        print("\n✓ PASS: All markets have good coverage (>70%)")
    else:
        print("\n⚠️  WARNING: Some markets have low coverage")

    # 5. RATINGS DATA
    print("\n" + "-" * 80)
    print("5. RATINGS DATA (Barttorvik)")
    print("-" * 80)

    ratings_cols = {
        'home_adj_o': 'Adj Offensive Efficiency',
        'home_adj_d': 'Adj Defensive Efficiency',
        'home_barthag': 'Barthag Rating',
        'home_tempo': 'Tempo',
        'home_efg': 'eFG%',
        'home_tor': 'Turnover Rate',
    }

    for col, name in ratings_cols.items():
        if col in df.columns:
            coverage = df[col].notna().sum()
            pct = coverage / len(df) * 100
            status = "✓" if pct > 85 else "⚠️"
            print(f"{status} {name:<30} {coverage:>6,} / {len(df):<6,} {pct:>5.1f}%")

    # Check ratings season alignment
    if 'ratings_season' in df.columns and 'season' in df.columns:
        season_check = df[df['ratings_season'].notna() & df['season'].notna()]
        correct = (season_check['ratings_season'] == season_check['season'] - 1).sum()
        total = len(season_check)

        if correct == total:
            print(f"\n✓ PASS: All ratings use prior season (N-1) - NO DATA LEAKAGE")
        else:
            print(f"\n❌ FAIL: {total - correct:,} games have incorrect rating season")

    # 6. ACTUAL RESULTS
    print("\n" + "-" * 80)
    print("6. ACTUAL GAME RESULTS")
    print("-" * 80)

    results_cols = {
        'home_score': 'FG Home Score',
        'away_score': 'FG Away Score',
        'home_h1': 'H1 Home Score',
        'away_h1': 'H1 Away Score',
        'actual_margin': 'FG Margin',
        'actual_total': 'FG Total',
        'h1_actual_margin': 'H1 Margin',
        'h1_actual_total': 'H1 Total',
    }

    for col, name in results_cols.items():
        if col in df.columns:
            coverage = df[col].notna().sum()
            pct = coverage / len(df) * 100
            status = "✓" if pct > 95 else "⚠️"
            print(f"{status} {name:<20} {coverage:>6,} / {len(df):<6,} {pct:>5.1f}%")

    # 7. CLOSING LINE DATA (CRITICAL FOR CLV)
    print("\n" + "-" * 80)
    print("7. CLOSING LINE DATA (CLV GOLD STANDARD)")
    print("-" * 80)

    closing_cols = [c for c in df.columns if 'closing' in c.lower()]

    if not closing_cols:
        print("❌ CRITICAL: NO CLOSING LINE DATA FOUND")
        print("   CLV backtests cannot run without closing lines")
        print("   Need columns like: fg_spread_closing, fg_total_closing, etc.")
    else:
        print(f"Closing line columns found: {closing_cols}")
        for col in closing_cols:
            coverage = df[col].notna().sum()
            pct = coverage / len(df) * 100
            print(f"  {col}: {coverage:,} / {len(df):,} ({pct:.1f}%)")

    # 8. DATA QUALITY BY SEASON
    print("\n" + "-" * 80)
    print("8. QUALITY BREAKDOWN BY SEASON")
    print("-" * 80)

    print(f"\n{'Season':<8} {'Games':<8} {'FG Odds':<12} {'H1 Odds':<12} {'Ratings':<12}")
    print("-" * 55)

    for season in seasons:
        season_df = df[df['season'] == season]
        games = len(season_df)
        fg_odds = season_df['fg_spread'].notna().sum()
        h1_odds = season_df['h1_spread'].notna().sum()
        ratings = season_df['home_adj_o'].notna().sum()

        print(f"{season:<8} {games:<8,} {fg_odds:>5,} ({fg_odds/games*100:>4.1f}%)  "
              f"{h1_odds:>5,} ({h1_odds/games*100:>4.1f}%)  "
              f"{ratings:>5,} ({ratings/games*100:>4.1f}%)")

    # FINAL SUMMARY
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    issues = []

    # Check critical requirements
    if len(non_backup) > 1:
        issues.append("Multiple CSV files in manifests/")

    if min(seasons) > 2023:
        issues.append("Missing 2023 season data")

    fg_coverage = df['fg_spread'].notna().sum() / len(df) * 100 if 'fg_spread' in df.columns else 0
    if fg_coverage < 70:
        issues.append(f"Low FG spread coverage ({fg_coverage:.1f}%)")

    ratings_coverage = df['home_adj_o'].notna().sum() / len(df) * 100 if 'home_adj_o' in df.columns else 0
    if ratings_coverage < 80:
        issues.append(f"Low ratings coverage ({ratings_coverage:.1f}%)")

    if not closing_cols:
        issues.append("NO CLOSING LINE DATA - CLV backtests will fail")

    if issues:
        print("⚠️  ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print("✓ ALL CHECKS PASSED")

    print("\n" + "=" * 80)
    return 0 if not issues else 1

if __name__ == "__main__":
    exit(main())
