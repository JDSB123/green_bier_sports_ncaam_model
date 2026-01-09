# Canonical Ingestion Framework - Integration Guide

## Quick Start

### 1. Import the Pipeline

```python
from testing.production_parity.canonical_ingestion import (
    CanonicalDataIngestionPipeline,
    DataSourceType,
    CanonicalGame,
    CanonicalOdds,
    CanonicalScores,
    CanonicalRatings,
)
from testing.production_parity.feature_extractor import (
    GameLevelFeatureExtractor,
    BoxScoreFeatures,
    RollingStats,
    ClosingLineFeatures,
)
```

### 2. Create Pipeline Instance

```python
pipeline = CanonicalDataIngestionPipeline()
extractor = GameLevelFeatureExtractor()
```

### 3. Ingest Data

```python
import pandas as pd

# Load raw odds data
df_raw_odds = pd.read_csv("raw_odds.csv")
canonical_odds = pipeline.ingest_odds_api(df_raw_odds)
print(f"Canonicalized {len(canonical_odds)} odds lines")

# Load raw ESPN scores
df_raw_scores = pd.read_csv("raw_scores.csv")
canonical_scores = pipeline.ingest_espn_scores(df_raw_scores)
print(f"Canonicalized {len(canonical_scores)} game results")

# Load Barttorvik ratings
ratings_dict = json.load(open("barttorvik_2024.json"))
canonical_ratings = pipeline.ingest_barttorvik_ratings(ratings_dict, season=2024)
print(f"Canonicalized {len(canonical_ratings)} team ratings")

# Load ncaahoopR games
df_ncaahoopR = pd.read_csv("ncaahoopR_games.csv")
canonical_games = pipeline.ingest_ncaahoopR_games(df_ncaahoopR)
print(f"Canonicalized {len(canonical_games)} games")
```

### 4. Check Ingestion Stats

```python
stats = pipeline.get_stats()
print(f"Total processed: {stats['total_processed']}")
print(f"Successfully resolved: {stats['successfully_resolved']}")
print(f"Success rate: {stats['success_rate']:.1%}")
```

---

## Feature Engineering Workflow

### Step 1: Get Rolling Team Stats (Point-in-Time, No Leakage)

```python
# For Duke before Jan 15, 2024
rolling_5 = extractor.get_rolling_stats(
    team="Duke",
    game_date="2024-01-15",  # This game EXCLUDED
    season=2024,
    window_size=5  # Last 5 games only
)

print(f"Games in window: {rolling_5.games_in_window}")
print(f"Record: {rolling_5.wins}-{rolling_5.losses}")
print(f"Avg points: {rolling_5.avg_points:.1f}")
print(f"Avg FG%: {rolling_5.avg_fg_pct:.1%}")
print(f"Most recent: {rolling_5.most_recent_game_date}")
```

**Key Properties:**
- ✅ Only includes games **before** 2024-01-15
- ✅ Uses last 5 games (or fewer if near season start)
- ✅ No data leakage (no information from future games)
- ✅ Ready to use for pre-game prediction

### Step 2: Get Closing Line (Pre-Game Market Info)

```python
closing = extractor.get_closing_line_features(
    home_team="Duke",
    away_team="North Carolina",
    game_date="2024-01-15",
    season=2024
)

print(f"Spread: {closing.spread_value}")  # e.g., -3.5 (Duke favored)
print(f"Implied win%: {closing.implied_home_win_pct:.1%}")  # Market consensus
print(f"Total: {closing.total_value}")  # e.g., 152.5
print(f"Bookmaker: {closing.primary_bookmaker}")
```

**What This Tells Us:**
- Market consensus (spread-derived implied probability)
- Market confidence in the matchup (tight spread = uncertain)
- Public perception before the game

### Step 3: Build Complete Feature Vector

```python
# Get stats for both teams
home_rolling = extractor.get_rolling_stats(
    "Duke", "2024-01-15", 2024, window_size=5
)
away_rolling = extractor.get_rolling_stats(
    "North Carolina", "2024-01-15", 2024, window_size=5
)

# Get market consensus
closing = extractor.get_closing_line_features(
    "Duke", "North Carolina", "2024-01-15", 2024
)

# Build feature dict
features = {
    # Home team (5-game rolling)
    "home_avg_pts": home_rolling.avg_points,
    "home_avg_fg_pct": home_rolling.avg_fg_pct,
    "home_avg_3p_pct": home_rolling.avg_three_pct,
    "home_avg_to": home_rolling.avg_turnovers,
    "home_win_pct": home_rolling.win_pct,
    
    # Away team (5-game rolling)
    "away_avg_pts": away_rolling.avg_points,
    "away_avg_fg_pct": away_rolling.avg_fg_pct,
    "away_avg_3p_pct": away_rolling.avg_three_pct,
    "away_avg_to": away_rolling.avg_turnovers,
    "away_win_pct": away_rolling.win_pct,
    
    # Market/venue
    "spread": closing.spread_value,
    "total": closing.total_value,
    "market_implied_home_wp": closing.implied_home_win_pct,
    "home_court": True,
}

# → Feed to ML model
```

---

## Integration with BacktestEngine

### Current Code Pattern

```python
# Current: Using season averages only
from testing.production_parity.backtest_engine import ProductionParityBacktest
from testing.production_parity.ratings_loader import AntiLeakageRatingsLoader

backtest = ProductionParityBacktest()
for game in games:
    resolved_home = team_resolver.resolve(game.home_team)
    resolved_away = team_resolver.resolve(game.away_team)
    
    ratings_home = ratings_loader.get_ratings_for_game(
        team=resolved_home.canonical_name,
        game_season=game.season
    )
```

### Enhanced Pattern (with Game-Level Features)

```python
# Enhanced: Using rolling stats + closing lines
from testing.production_parity.canonical_ingestion import CanonicalDataIngestionPipeline
from testing.production_parity.feature_extractor import GameLevelFeatureExtractor

pipeline = CanonicalDataIngestionPipeline()
extractor = GameLevelFeatureExtractor()

# Pre-compute rolling stats for all teams/dates (optional but faster)
rolling_cache = {}  # {(team, game_date, window): RollingStats}

for game in games:
    # Canonicalize the game
    game_canonical = pipeline.ingest_ncaahoopR_games(
        pd.DataFrame([game])
    )[0]
    
    # Get pre-game rolling stats (no leakage)
    home_rolling = extractor.get_rolling_stats(
        team=game_canonical.home_team_canonical,
        game_date=game_canonical.game_date_cst,
        season=game_canonical.season,
        window_size=5
    )
    away_rolling = extractor.get_rolling_stats(
        team=game_canonical.away_team_canonical,
        game_date=game_canonical.game_date_cst,
        season=game_canonical.season,
        window_size=5
    )
    
    # Get closing line (market consensus)
    closing = extractor.get_closing_line_features(
        home_team=game_canonical.home_team_canonical,
        away_team=game_canonical.away_team_canonical,
        game_date=game_canonical.game_date_cst,
        season=game_canonical.season
    )
    
    # Build feature vector
    feature_vector = build_features(
        game_canonical, home_rolling, away_rolling, closing
    )
    
    # Predict
    prediction = model.predict(feature_vector)
```

---

## Data Quality Checks

### 1. Season Consistency Check

```python
from testing.production_parity.canonical_ingestion import SeasonAwareCanonicalizer

canonicalizer = SeasonAwareCanonicalizer()

# Verify season assignment consistency
test_cases = [
    ("2023-11-01", 2024),  # Nov → Season 2024
    ("2024-03-15", 2024),  # Mar → Season 2024
    ("2024-06-01", 2024),  # Jun → Season 2024
    ("2023-05-01", 2023),  # May → Season 2023
]

for date_str, expected_season in test_cases:
    actual_season = canonicalizer.get_season_from_date(date_str)
    assert actual_season == expected_season, f"Season mismatch for {date_str}"
    print(f"✓ {date_str} → Season {actual_season}")
```

### 2. Team Resolution Validation

```python
# Check that team names resolve consistently
test_teams = [
    "Duke",
    "Alabama Crimson Tide",
    "UNC",
    "Tennessee Volunteers",
    "Auburn Tigers",
]

for team_name in test_teams:
    result = pipeline.resolver.resolve(team_name)
    if result.resolved:
        print(f"✓ {team_name} → {result.canonical_name}")
    else:
        print(f"✗ {team_name} (unresolved)")
```

### 3. No Data Leakage Check

```python
# Verify rolling stats don't include current game
team = "Duke"
game_date = "2024-01-15"
season = 2024

rolling = extractor.get_rolling_stats(team, game_date, season, window_size=5)

# Verify no game at or after game_date
for game_date_in_window in rolling.all_game_dates:
    assert game_date_in_window < game_date, \
        f"Data leakage: {game_date_in_window} >= {game_date}"

print(f"✓ No data leakage: all {len(rolling.all_game_dates)} games before {game_date}")
```

---

## Performance Optimization

### Caching Rolling Stats

```python
from functools import lru_cache

# Pre-compute rolling stats for all games (season-level cache)
rolling_cache = {}

def get_rolling_stats_cached(team, game_date, season, window_size=5):
    key = (team, game_date, season, window_size)
    if key not in rolling_cache:
        rolling_cache[key] = extractor.get_rolling_stats(
            team, game_date, season, window_size
        )
    return rolling_cache[key]

# Much faster on second access
rolling1 = get_rolling_stats_cached("Duke", "2024-01-15", 2024, 5)
rolling2 = get_rolling_stats_cached("Duke", "2024-01-15", 2024, 5)  # Fast!
```

### Bulk Ingestion

```python
# Ingest all data at once, then access canonical objects
canonical_games = pipeline.ingest_ncaahoopR_games(df_all_games)
canonical_odds = pipeline.ingest_odds_api(df_all_odds)
canonical_scores = pipeline.ingest_espn_scores(df_all_scores)

# Index for fast lookup
games_by_date = {}
for game in canonical_games:
    key = (game.game_date_cst, game.home_team_canonical, game.away_team_canonical)
    games_by_date[key] = game
```

---

## Troubleshooting

### Issue: Team Not Resolving

```python
# Debug team resolution
team_name = "Some Weird Team Name"
result = pipeline.resolver.resolve(team_name)

if not result.resolved:
    print(f"Team '{team_name}' not resolved")
    print(f"Attempted matching: {result.step_used}")
    
    # Options:
    # 1. Add to team_aliases.json
    # 2. Verify spelling (check source data)
    # 3. Check if non-D1 (non_d1 list)
```

### Issue: Wrong Season Assignment

```python
# Debug season assignment
date_str = "2023-12-25"
season = canonicalizer.get_season_from_date(date_str)

print(f"Date: {date_str}")
print(f"Month: {pd.to_datetime(date_str).month}")
print(f"Season: {season}")
print(f"Expected: {2024 if pd.to_datetime(date_str).month >= 11 else 2023}")
```

### Issue: Data Leakage Detected

```python
# Verify rolling stats are truly point-in-time
team = "Duke"
game_date = "2024-01-15"
rolling = extractor.get_rolling_stats(team, game_date, 2024, window_size=5)

print(f"Game date: {game_date}")
print(f"Games in window:")
for gd in rolling.all_game_dates:
    if gd >= game_date:
        print(f"  ✗ LEAKAGE: {gd} >= {game_date}")
    else:
        print(f"  ✓ {gd}")
```

---

## Next Steps

1. **Load All Data Sources:** Implement data loaders for Odds API, ESPN, Barttorvik
2. **Pre-compute Rolling Stats:** Build cache of rolling stats for all games
3. **Integrate with BacktestEngine:** Update backtest to use new feature pipeline
4. **Feature Selection:** Analyze which features most predictive
5. **Model Tuning:** Retrain with game-level features vs season averages
6. **Performance Analysis:** Measure improvement in backtest accuracy

---

## Files Reference

| File | Purpose | Key Classes |
|------|---------|------------|
| `canonical_ingestion.py` | Master ingestion pipeline | `CanonicalDataIngestionPipeline`, `SeasonAwareCanonicalizer` |
| `feature_extractor.py` | Game-level feature engineering | `GameLevelFeatureExtractor`, `RollingStats`, `ClosingLineFeatures` |
| `team_resolver.py` | Team name matching | `ProductionTeamResolver` |
| `ratings_loader.py` | Anti-leakage ratings | `AntiLeakageRatingsLoader` |
| `CANONICAL_INGESTION_ARCHITECTURE.md` | Full architecture documentation | (reference) |

---

## Questions & Support

For questions about:
- **Team resolution:** See `team_resolver.py` comments and validation guide
- **Season handling:** See `CANONICAL_INGESTION_ARCHITECTURE.md` §Season Definition
- **Data leakage:** See `DATA_MATCHING_INTEGRITY_VERIFICATION.md` §Anti-Leakage Validation
- **Feature engineering:** See `feature_extractor.py` docstrings and examples
