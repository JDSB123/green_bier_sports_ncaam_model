# Historical Data Availability Matrix
**Canonical window:** 2023-24 season onward (season 2024+). Pre-2023 data is out of scope.

**Last Updated:** January 9, 2026  
**Purpose:** Document what historical data is available for backtesting by season

---

**Note:** Azure Blob Storage (`metricstrackersgbsv/ncaam-historical-data`) is the source of truth.

## ⚠️ CRITICAL: H1 (First-Half) Data Limitations

**The Odds API does NOT provide historical H1 data before May 3, 2023.**

This is a **hard API limitation** - H1 historical data is only available after 2023-05-03, so coverage begins with season 2024.

| Season | H1 Available | Reason |
|--------|:------------:|--------|
| 2024   | ✅ Yes | Season started Nov 2023 (after cutoff) |
| 2025   | ✅ Yes | Full coverage |
| 2026   | ✅ Yes | Ongoing collection |

**Source:** [The Odds API Documentation](https://the-odds-api.com/liveapi/guides/v4/#historical-odds)  
> "Historical data for additional markets (spreads_h1, totals_h1) is only available after 2023-05-03"

---

## Data Coverage Summary

### Full-Game (FG) Model Data

| Season | Games | FG Odds | Barttorvik | H1 Scores | Status |
|--------|------:|:-------:|:----------:|:---------:|--------|
| 2024   | 928   | ✅ 96%  | ✅ 97%     | ✅ 97%    | ✅ FG + H1 Ready |
| 2025   | 967   | ✅ 96%  | ✅ 96%     | ✅ 96%    | ✅ FG + H1 Ready |
| 2026   | 449+  | ✅ 94%  | ✅ 94%     | ✅ 94%    | 🔄 In Progress |

### H1 (First-Half) Model Data

| Season | H1 Odds | H1 Spread Rows | Unique Games | Status |
|--------|:-------:|---------------:|-------------:|--------|
| 2024   | ✅ 96%  | 44,264         | ~5,533       | ✅ Ready |
| 2025   | ✅ 96%  | 38,393         | ~4,799       | ✅ Ready |
| 2026   | ✅ 90%  | 2,296          | ~287         | 🔄 In Progress |

---

## Season Classification Convention

All data sources use the same season classification:

**Season Year = Spring Year of Academic Year**

| Season | Date Range | Examples |
|--------|------------|----------|
| 2024   | Nov 2023 → Apr 2024 | 2023-24 academic year |
| 2025   | Nov 2024 → Apr 2025 | 2024-25 academic year |
| 2026   | Nov 2025 → Apr 2026 | 2025-26 academic year |

**Sources confirmed aligned:**
- ✅ ESPN
- ✅ Barttorvik
- ✅ The Odds API
- ✅ FlashScore/ncaahoopR

---

## Backtest Scope

### For FG (Full-Game) Spread Model
- **Recommended:** Seasons 2024-2026 (canonical window)
- **Statistically significant:** ≥2,500 games recommended for reliable CLV/win-rate analysis

### For H1 (First-Half) Spread Model
- **Available:** Seasons 2024-2026 (~10,600 games with H1 odds)
- **Note:** Smaller sample size limits H1 model validation depth

---

## Data Sources

| Source | Type | Seasons | Notes |
|--------|------|---------|-------|
| The Odds API | FG/H1 Odds | 2024+ | H1 only after May 2023 |
| ESPN/FlashScore | Scores, H1 Scores | 2024+ | Via ncaahoopR package |
| Barttorvik | Team Ratings | 2024+ | Efficiency metrics |

---

## Canonical Data Files

### Odds (Canonical)
```
ncaam-historical-data/odds/normalized/odds_consolidated_canonical.csv
```

### Scores (Canonical)
```
ncaam-historical-data/scores/fg/games_all.csv
ncaam-historical-data/scores/h1/h1_games_all.csv
```

### Ratings
```
ncaam-historical-data/ratings/barttorvik/barttorvik_2024.json
ncaam-historical-data/ratings/barttorvik/barttorvik_2025.json
ncaam-historical-data/ratings/barttorvik/barttorvik_2026.json
```

---

## Team Canonicalization

**SINGLE SOURCE OF TRUTH:**
```
Azure Blob: backtest_datasets/team_aliases_db.json
```

- 362 canonical team names
- 1,679 aliases
- Version: 2026.01.09
- Used by: `testing/canonical/team_resolution_service.py` for ingestion, PostgreSQL `resolve_team_name()` for production

All ingestion scripts must use the canonical team resolution service for team name resolution to ensure consistency across all data sources.

---

## Known Gaps

### Expected (API Limitations)
- H1 odds prior to 2024 are not available from the API (out of scope)
- Some early-season exhibition games not tracked by Odds API

### Unexpected (Single Game)
- 2023-11-25: Oregon vs Alabama - Missing FG and H1 odds

---

## Update Log

| Date | Change |
|------|--------|
| 2026-01-09 | Canonicalized 2024 H1 data from archive (44,264 rows) |
| 2026-01-09 | Fixed UIC/Illinois Chicago team alias duplicate |
| 2026-01-08 | Verified season alignment across all sources |
| 2026-01-07 | Initial H1 odds ingestion for 2025-2026 |
