# Backtest Data Integrity Fixes - Summary

## Problem
The backtest data had only **17% match rate** between odds data and score data due to team name inconsistencies.

## Root Causes Identified

1. **Mascot name variations**: Odds used "Michigan St Spartans" while training used "Michigan State"
2. **Conflicting resolver mappings**: `ualr` -> `Little Rock Trojans` but training uses `UALR` as canonical
3. **State school variations**: "michigan st." vs "Michigan State"
4. **Home/away swap**: Some games had teams in opposite order between sources
5. **Pre-computed canonical**: rebuild script used `home_team_canonical` from odds which used a DIFFERENT resolver

## Fixes Applied

### 1. Fixed rebuild script to use raw team names (not pre-computed canonical)
Changed line 151 from:
```python
home = r.get('home_team_canonical', r.get('home_team', ''))
```
to:
```python
home = r.get('home_team', '')
```

### 2. Added 600+ team name mappings including:
- Mascot stripping (100+ mappings): "Michigan St Spartans" -> "Michigan State"
- State school normalization (60 mappings): "michigan st." -> "Michigan State"
- Specific fixes: UALR, UTRGV, IPFW, Miss. Valley St., UT Martin, Loyola Maryland

### 3. Fixed conflicting canonical mappings
Ensured all variations map to the SAME canonical form:
- `ualr`, `little rock trojans`, `arkansas-little rock` -> `UALR`
- `utrgv`, `ut rio grande valley` -> `UTRGV`
- `ipfw`, `purdue fort wayne`, `fort wayne` -> `IPFW`

### 4. Added home/away swap fallback
If game not found with (date, home, away), try (date, away, home) and swap scores accordingly.

## Results

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Overall Match Rate** | 17% | 69% | +52 points |
| 2023-24 Season | 52% | 88% | +36 points |
| 2024-25 Season | 52% | 88% | +36 points |
| Resolver Mappings | 1,046 | 1,699 | +653 mappings |
| Games with odds | ~9,000 | 11,786 | +2,700 games |

## Remaining Gaps (Cannot be fixed)
- **2025-26**: ~2,000 future games without scores yet
- **2024-26**: ~700 games in odds but not in training data (coverage gap)

## Files Modified
- `testing/rebuild_backtest_data.py` - Fixed normalization logic
- `backtest_datasets/team_aliases_db.json` (Azure blob) - Added 653 mappings

## Files Created (cleanup scripts)
- `testing/normalize_state_schools.py`
- `testing/add_mascot_mappings.py`
- `testing/fix_games_all_mascots.py`
- `testing/fix_conflicting_mappings.py`
- Various analysis scripts
