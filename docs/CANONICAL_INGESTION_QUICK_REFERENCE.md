# Canonical Ingestion Framework - Quick Reference

## One-Page Cheat Sheet

### Import Statements
```python
from testing.production_parity.canonical_ingestion import (
    CanonicalDataIngestionPipeline,
    SeasonAwareCanonicalizer,
    CanonicalGame, CanonicalOdds, CanonicalScores, CanonicalRatings,
)
from testing.production_parity.feature_extractor import (
    GameLevelFeatureExtractor,
    RollingStats, ClosingLineFeatures,
)
```

---

## Core Classes & Methods

### CanonicalDataIngestionPipeline
```python
pipeline = CanonicalDataIngestionPipeline()

# Ingest each source
odds_list = pipeline.ingest_odds_api(df_odds)           # Odds API data
scores_list = pipeline.ingest_espn_scores(df_scores)    # ESPN game results
ratings_list = pipeline.ingest_barttorvik_ratings(dict, season=2024)  # Ratings
games_list = pipeline.ingest_ncaahoopR_games(df_games)   # ncaahoopR games

# Check stats
stats = pipeline.get_stats()  # {total_processed, successfully_resolved, success_rate}
```

### SeasonAwareCanonicalizer
```python
canonicalizer = SeasonAwareCanonicalizer()

# Get season from date
season = canonicalizer.get_season_from_date("2023-11-20")  # → 2024
season = canonicalizer.get_season_from_date(datetime.now())

# Normalize date to CST
date_cst, datetime_cst = canonicalizer.normalize_date_to_cst("2023-11-20 02:30 EST")
# → ("2023-11-20", "2023-11-20T00:30:00")
```

### GameLevelFeatureExtractor
```python
extractor = GameLevelFeatureExtractor()

# Get rolling stats (no leakage: only prior games)
rolling = extractor.get_rolling_stats(
    team="Duke",
    game_date="2024-01-15",      # This game EXCLUDED
    season=2024,
    window_size=5                 # Last 5 games
)

# Get closing line (pre-game market info)
closing = extractor.get_closing_line_features(
    home_team="Duke",
    away_team="North Carolina",
    game_date="2024-01-15",
    season=2024
)
```

---

## Common Data Objects

### CanonicalGame
```python
game = CanonicalGame(
    game_id="...",
    game_date_cst="2024-01-15",
    season=2024,
    home_team_canonical="Duke",
    away_team_canonical="North Carolina",
    home_resolution_step="alias",          # How team name was matched
    away_resolution_step="normalized",
)
```

### RollingStats
```python
rolling = RollingStats(
    team="Duke",
    game_date="2024-01-15",
    season=2024,
    window_size=5,
    games_in_window=5,
    
    # Aggregated metrics
    avg_points=75.2,
    avg_fg_pct=0.451,
    avg_three_pct=0.365,
    wins=4, losses=1, win_pct=0.80,
    
    # Metadata
    all_game_dates=["2024-01-14", "2024-01-13", ...],
    most_recent_game_date="2024-01-14"
)
```

### ClosingLineFeatures
```python
closing = ClosingLineFeatures(
    game_date="2024-01-15",
    home_team="Duke",
    away_team="North Carolina",
    
    spread_value=-3.5,              # Duke favored by 3.5
    implied_home_win_pct=0.625,     # From spread
    total_value=152.5,
    primary_bookmaker="DraftKings"
)
```

---

## Season Rules (NCAA Standard)

```
November or later (month ≥ 11) → Season = Year + 1
May through October (month < 11) → Season = Year

Examples:
Nov 20, 2023 → Season 2024  (championship year)
Dec 10, 2023 → Season 2024
Jan 15, 2024 → Season 2024
Mar 18, 2024 → Season 2024  (tournament time)
May 1, 2024  → Season 2024
June 1, 2024 → Season 2024
Nov 1, 2024  → Season 2025
```

---

## Team Resolution Steps

```
Step 1: CANONICAL     → Exact name in team_aliases.json canonical column
Step 2: ALIAS        → Exact name in team_aliases.json alias column
Step 3: NORMALIZED   → After removing punctuation/whitespace normalization
Step 4: MASCOT_STRIPPED → After removing common mascot suffixes ("Crimson Tide" → "Alabama")
Step 5: NON_D1       → Explicitly blocked (D2, NAIA, D3 teams)
Step 6: UNRESOLVED   → No match found (manual review needed)
```

**Key:** No fuzzy matching (exact only) → prevents "Tennessee" ≠ "Tennessee State"

---

## Feature Engineering Workflow

```
1. Load raw data
   ↓
2. Canonicalize via CanonicalDataIngestionPipeline
   ↓
3. For each game, extract features:
   a) Rolling stats (last 5 games, before game date)
   b) Closing line (pre-game spread/total)
   c) Barttorvik ratings (Season N-1 from AntiLeakageRatingsLoader)
   d) Box score features (if available)
   ↓
4. Build feature vector
   ↓
5. Model prediction
```

---

## Data Leakage Prevention

### ✅ Correct (No Leakage)
```python
# Get rolling stats for Duke BEFORE Jan 15
rolling = extractor.get_rolling_stats("Duke", "2024-01-15", 2024, 5)
# → Includes only games before Jan 15

# Get closing line (pre-game)
closing = extractor.get_closing_line_features("Duke", "NC", "2024-01-15", 2024)
# → Pre-game spread, available before game starts

# Use Season N-1 ratings
ratings_season = game_season - 1  # Season 2024 game → use Season 2023 ratings
# → Ratings weren't available at game time
```

### ❌ Incorrect (Data Leakage!)
```python
# DON'T: Include current game in rolling stats
rolling = extractor.get_rolling_stats("Duke", "2024-01-15", 2024, 5)
# If rolling.all_game_dates includes "2024-01-15" → LEAKAGE

# DON'T: Use closing line for past analysis
# Closing line changes after game starts → only valid pre-game

# DON'T: Use Season 2024 ratings for Season 2024 games
# Ratings finalized AFTER season ends → use Season N-1
```

---

## Validation Checklist

### Before Backtest
- [ ] Team resolution: 99%+ success rate
- [ ] Seasons assigned correctly (Nov+ = year+1)
- [ ] Rolling stats exclude current game
- [ ] Ratings are Season N-1
- [ ] Closing lines are pre-game

### After Ingestion
- [ ] `stats['success_rate'] > 0.99`
- [ ] `len(canonical_games) > 0`
- [ ] `all(game.season >= 2019 for game in canonical_games)`
- [ ] `all(game.season <= 2026 for game in canonical_games)`

### During Feature Engineering
- [ ] `rolling.games_in_window > 0`
- [ ] `all(d < game_date for d in rolling.all_game_dates)`
- [ ] `closing.spread_value is not None`
- [ ] `closing.implied_home_win_pct in [0, 1]`

---

## Performance Tips

### Caching Rolling Stats
```python
# Pre-compute for all games (saves time in backtest)
rolling_cache = {}

def get_rolling_cached(team, game_date, season, window=5):
    key = (team, game_date, season, window)
    if key not in rolling_cache:
        rolling_cache[key] = extractor.get_rolling_stats(
            team, game_date, season, window
        )
    return rolling_cache[key]
```

### Bulk Ingestion
```python
# Ingest everything at once, then index
games = pipeline.ingest_ncaahoopR_games(df_all)
odds = pipeline.ingest_odds_api(df_all_odds)

# Build lookup
games_by_key = {
    (g.game_date_cst, g.home_team_canonical, g.away_team_canonical): g
    for g in games
}
```

---

## Common Patterns

### Pattern 1: Quick Team Check
```python
result = pipeline.resolver.resolve("Alabama")
if result.resolved:
    print(f"✓ {result.canonical_name}")
else:
    print(f"✗ Unresolved")
```

### Pattern 2: Season Check
```python
season = SeasonAwareCanonicalizer.get_season_from_date("2024-01-15")
assert season == 2024
```

### Pattern 3: Build Feature Dict
```python
home_rolling = extractor.get_rolling_stats("Duke", "2024-01-15", 2024, 5)
away_rolling = extractor.get_rolling_stats("NC", "2024-01-15", 2024, 5)
closing = extractor.get_closing_line_features("Duke", "NC", "2024-01-15", 2024)

features = {
    "home_pts": home_rolling.avg_points,
    "home_fg%": home_rolling.avg_fg_pct,
    "away_pts": away_rolling.avg_points,
    "spread": closing.spread_value,
}
```

### Pattern 4: Batch Ingestion
```python
all_canonical = []
for df_chunk in chunks(df_raw, size=1000):
    canonical = pipeline.ingest_odds_api(df_chunk)
    all_canonical.extend(canonical)
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Team not resolving | Check `team_aliases.json`, verify spelling |
| Wrong season | Check date, verify month (Nov+ = year+1) |
| Data leakage warning | Verify rolling stats exclude current date |
| Missing rolling stats | Check `games_in_window > 0` |
| No closing line | Check odds file loaded, bookmaker available |

---

## File Locations

| File | Path | Purpose |
|------|------|---------|
| Main pipeline | `testing/production_parity/canonical_ingestion.py` | All ingestion |
| Features | `testing/production_parity/feature_extractor.py` | Feature engineering |
| Resolver | `testing/production_parity/team_resolver.py` | Team matching |
| Ratings | `testing/production_parity/ratings_loader.py` | Anti-leakage |
| Aliases | `testing/production_parity/team_aliases.json` | Team mappings |
| Docs | `docs/CANONICAL_INGESTION_ARCHITECTURE.md` | Full reference |

---

## Quick Start (Copy-Paste Template)

```python
from testing.production_parity.canonical_ingestion import CanonicalDataIngestionPipeline
from testing.production_parity.feature_extractor import GameLevelFeatureExtractor
import pandas as pd

# Initialize
pipeline = CanonicalDataIngestionPipeline()
extractor = GameLevelFeatureExtractor()

# Load and canonicalize data
df_games = pd.read_csv("games.csv")
canonical_games = pipeline.ingest_ncaahoopR_games(df_games)
print(f"Processed: {len(canonical_games)} games")

# Extract features for first game
game = canonical_games[0]
home_rolling = extractor.get_rolling_stats(
    game.home_team_canonical,
    game.game_date_cst,
    game.season,
    window_size=5
)
print(f"{game.home_team_canonical}: {home_rolling.wins}-{home_rolling.losses}")
```

---

Done! You have a complete, production-ready canonical ingestion framework.
