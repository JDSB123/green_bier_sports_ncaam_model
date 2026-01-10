# Data Endpoint Status Report

**Generated**: 2026-01-10  
**Purpose**: Document ALL data sources and their utilization status

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| Actively Used | 17 | ✅ |
| Fallback/Cache | 16 | ✅ |
| Partially Used | 2 | ⚠️ |
| **NOT USED (MAJOR GAP)** | **332,357** | 🚨 |

---

## ✅ ACTIVELY USED Data Sources

### Scores
| File | Usage | Fields in Backtest |
|------|-------|-------------------|
| `scores/fg/games_2019.csv` - `games_2026.csv` | Primary FG scores | `home_score`, `away_score` |
| `scores/h1/h1_games_all.csv` | H1 scores | `home_h1`, `away_h1` |
| `canonicalized/scores/h1/h1_games_all_canonical.csv` | Canonical H1 | (same) |

### Odds  
| File | Usage | Fields in Backtest |
|------|-------|-------------------|
| `odds/normalized/odds_consolidated_canonical.csv` | Primary FG odds | `fg_spread`, `fg_total`, FG prices |
| `odds/normalized/odds_h1_archive_matchups.csv` | H1 prices | `h1_spread_home_price`, `h1_total_over_price` |

### Ratings
| File | Usage | Fields in Backtest |
|------|-------|-------------------|
| `ratings/barttorvik/ratings_2019.json` - `ratings_2026.json` | Barttorvik ratings | `adj_o`, `adj_d`, `barthag`, `efg`, `tor`, `orb`, `ftr`, `wab`, `three_pt_rate` |

### Supporting
| File | Usage |
|------|-------|
| `backtest_datasets/team_aliases_db.json` | Team name canonicalization |

---

## ✅ Fallback/Cache (Available if needed)

| File | Purpose |
|------|---------|
| `odds/canonical/spreads/fg/spreads_fg_all.csv` | FG spreads fallback |
| `odds/canonical/totals/fg/totals_fg_all.csv` | FG totals fallback |
| `ratings/raw/barttorvik/*.json` | Raw Barttorvik data |
| `odds/normalized/barttorvik_*.json` | Barttorvik cache |

---

## ⚠️ PARTIALLY USED

| File | Issue | Potential |
|------|-------|-----------|
| `odds/canonical/spreads/h1/spreads_h1_all.csv` | Lines only, no prices | Archive has prices |
| `odds/canonical/totals/h1/totals_h1_all.csv` | Lines only, no prices | Archive has prices |

---

## 🚨 NOT USED - MAJOR DATA GAP

### ncaahoopR Dataset (332,357 files!)

**Location**: `ncaam_historical_data_local/ncaahoopR_data-master/`

**Contents**:
- **Box Scores**: ~12,000 per season (player-level stats per game)
- **Play-by-Play**: ~6,000 per season (every play in every game)
- **Rosters**: 360 per season
- **Schedules**: 360 per season
- **Coverage**: 2002-03 through 2025-26

**Available Fields (Box Scores)**:
```
player_id, player, position, MIN, 
FGM, FGA, 3PTM, 3PTA, FTM, FTA,    # Shooting
OREB, DREB, REB, AST, STL, BLK,    # Stats
TO, PF, PTS,                        # Performance
team, opponent, home, starter, date, location
```

**Potential Uses (NOT CURRENTLY IMPLEMENTED)**:
1. ⭐ **Game-by-game Four Factors** (not just season averages)
2. ⭐ **Rolling team efficiency** (last N games)
3. ⭐ **Pace/tempo per game** (possessions)
4. ⭐ **Team depth analysis** (bench minutes, starters vs reserves)
5. ⭐ **Home/away performance splits**
6. ⭐ **Fatigue metrics** (minutes distribution)
7. ⭐ **Shooting tendencies** (3PT rate per game)
8. ⭐ **Turnover tendencies** (game-by-game)

---

## Recommendations

### Priority 1: Utilize ncaahoopR Data
The ncaahoopR dataset contains 332,357 files of granular game data that could significantly improve predictions:

1. **Extract rolling Four Factors** from box scores (not just season-end Barttorvik)
2. **Calculate game-by-game efficiency** for recency-weighted features
3. **Derive pace/possessions** for tempo-adjusted predictions

### Priority 2: Clean Up Redundant Files
- 10 JSON duplicates of CSV files
- 2 redundant odds files (`odds_h1_archive_teams.csv`, `odds_all_normalized_*.csv`)

### Priority 3: Verify Data Freshness
- Ensure all 2025-26 season data is being ingested
- Confirm H1 prices continue to be captured going forward

---

## Current Backtest Master Coverage

| Market | Lines | Prices | Coverage |
|--------|-------|--------|----------|
| FG Spread | 4,693 | 2,639 | 35.2% |
| FG Total | 4,694 | 2,640 | 35.2% |
| H1 Spread | 1,981 | 1,567 | 20.9% |
| H1 Total | 1,981 | 1,567 | 20.9% |
| Ratings | - | 5,443 | 72.6% |

**Total games**: 7,500 (2019-2026)

---

## Backtest Master Columns (69 total)

### From Scores
- `game_id`, `game_date`, `season`
- `home_team`, `away_team` (original + canonical)
- `home_score`, `away_score`, `actual_margin`, `actual_total`
- `home_h1`, `away_h1`, `h1_actual_margin`, `h1_actual_total`

### From Odds
- `fg_spread`, `fg_spread_home_price`, `fg_spread_away_price`
- `fg_total`, `fg_total_over_price`, `fg_total_under_price`
- `h1_spread`, `h1_spread_home_price`, `h1_spread_away_price`
- `h1_total`, `h1_total_over_price`, `h1_total_under_price`

### From Ratings
- `home_adj_o`, `home_adj_d`, `away_adj_o`, `away_adj_d`
- `home_barthag`, `away_barthag`
- `home_efg`, `home_efgd`, `away_efg`, `away_efgd` (Four Factors)
- `home_tor`, `away_tor` (Turnover Rate)
- `home_orb`, `home_drb`, `away_orb`, `away_drb` (Rebounding)
- `home_ftr`, `home_ftrd`, `away_ftr`, `away_ftrd` (Free Throw Rate)
- `home_three_pt_rate`, `away_three_pt_rate` (Shooting Tendencies)
- `home_wab`, `away_wab` (Wins Above Bubble)
- `home_tempo`, `away_tempo`
- `home_conf`, `away_conf`

### Computed
- `fg_spread_result`, `fg_spread_covered`
- `fg_total_diff`, `fg_total_over`
- `h1_spread_result`, `h1_spread_covered`
- `h1_total_diff`, `h1_total_over`
