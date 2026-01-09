# Data Matching Verification - Quick Reference

## 🎯 Key Principles

| Principle | Implementation | Verification |
|-----------|-----------------|--------------|
| **Single Source of Truth (Team Names)** | ProductionTeamResolver (4-step exact matching, NO fuzzy) | `validate_team_canonicalization.py` |
| **Consistent Season Definition** | season = year+1 if month ≥ 11 else year | `validate_canonical_odds.py` |
| **Timezone Standardization** | All timestamps → CST (America/Chicago) | Audit logs show CST dates |
| **Anti-Data Leakage** | Season N games use Season N-1 FINAL ratings | `AntiLeakageRatingsLoader` enforces N-1 rule |
| **Cross-Source Matching** | Games matched by (home_team_canonical, away_team_canonical, game_date, season) | Pre-backtest-gate validates joins |

---

## 🔍 Team Resolution (4-Step Exact Matching)

```
Input: "Alabama State"
        ↓
Step 1: Exact canonical name match? "Alabama" ❌
        ↓
Step 2: Exact alias match? "Alabama St." ✅
        ↓
Result: canonical_name = "Alabama St."
        resolution_step = "ALIAS"
```

**Critical:** Step 4 MASCOT_STRIPPED is last resort. If all 4 fail → REJECT (return None).

**No fuzzy matching!** Prevents false positives like "Tennessee" → "Tennessee State"

---

## 📅 Season Definition

```python
# Season = championship year (NCAA basketball)
season = date.year + 1 if date.month >= 11 else date.year

# Examples:
2024-01-15 → Season 2024  (2023-24 championship)
2023-11-20 → Season 2024  (2023-24 championship, early)
2023-03-18 → Season 2023  (2022-23 championship, late)
```

**Used everywhere:** Games, odds, ratings must all use same season assignment.

---

## ⏰ Anti-Data Leakage Rule (CRITICAL!)

```
Game Date      Game Season    Ratings Season    Logic
────────────────────────────────────────────────────────────
2024-01-15     2024          2023 FINAL        ✅ Prior season only
2023-11-20     2024          2023 FINAL        ✅ Prior season only
2023-04-15     2023          2022 FINAL        ✅ Prior season only
```

**Why:** Using Season N ratings for Season N games = future data leakage!

**Penalty:** Win rate inflates 5-10+ percentage points artificially.

**Enforcement:** `AntiLeakageRatingsLoader` automatically converts game_season → ratings_season.

---

## 🧪 Cross-Source Matching Example

```
Odds API Data:
  home_team: "Alabama Crimson Tide"
  away_team: "Tennessee Volunteers"
  commence_time: "2024-01-15T18:00:00Z"
  spread: -7.0

ESPN Scores:
  home_team: "Alabama"
  away_team: "Tennessee"
  date: "2024-01-15"
  home_score: 75
  away_score: 68

Barttorvik Ratings:
  team: "Alabama" (adj_o=106.5, adj_d=92.3, tempo=68.2)
  team: "Tennessee" (adj_o=104.2, adj_d=95.1, tempo=67.1)

After Canonicalization:
  home_team_canonical: "Alabama"        ← All resolve to same
  away_team_canonical: "Tennessee"      ← All resolve to same
  game_date: "2024-01-15"               ← All match
  season: 2024                          ← All same

Join Key: (Alabama, Tennessee, 2024-01-15, 2024)
Result: ✅ Matched - can predict & backtest
```

---

## 📊 Join Key Formula

```python
# Every game is uniquely identified by:
join_key = (
    home_team_canonical,          # Must match exactly
    away_team_canonical,          # Must match exactly
    game_date,                    # Must match (±1 day OK for timezone)
    season                        # Must match
)

# Optional for odds:
join_key_with_bookmaker = (
    home_team_canonical,
    away_team_canonical,
    game_date,
    season,
    bookmaker                     # Different lines for different books
)
```

**Usage:** 
- Inner join odds to scores → Get all games with odds
- Left join ratings to odds → Add team strength metrics
- Check for duplicates after join → Should be 2 rows per game (home/away in team-level data)

---

## ✅ Data Quality Thresholds

| Metric | Must Pass |
|--------|-----------|
| Team resolution rate | ≥ 99% |
| Cross-source consistency | 100% (same game = same canonical names) |
| Fuzzy matching false positives | 0 (never) |
| Game join success rate | ≥ 98% |
| Anti-leakage enforcement | 100% (zero future data) |
| Season assignment errors | 0 (never) |
| Timezone consistency | 100% (all CST) |
| Team consistency within game | 100% (home ≠ away, both canonical) |

---

## 🚀 Quick Validation Commands

```bash
# Full validation pipeline (REQUIRED before backtest)
python testing/scripts/pre_backtest_gate.py --verbose

# Team matching only
python testing/scripts/validate_team_canonicalization.py
python testing/scripts/audit_team_aliases.py

# Date/season consistency
python testing/scripts/validate_canonical_odds.py

# Cross-source today's games
python services/prediction-service-python/scripts/test_today_team_matching.py

# Anti-leakage test
python -c "from testing.production_parity.ratings_loader import AntiLeakageRatingsLoader; AntiLeakageRatingsLoader()._test_anti_leakage()"
```

---

## 🎯 Audit Log Interpretation

```csv
game_id,date_cst,home_team_raw,home_team_canonical,resolution_step,game_season,ratings_season

abc123,2024-01-15,Duke,Duke,CANONICAL,2024,2023
def456,2024-01-16,Alabama St,Alabama St.,ALIAS,2024,2023
ghi789,2024-01-17,Tennessee Volunteers,Tennessee,MASCOT_STRIPPED,2024,2023
jkl012,2024-01-18,UnknownSchool,NULL,UNRESOLVED,2024,2023
```

**Read as:**
- ✅ abc123: Duke resolved in Step 1 (CANONICAL), using 2023 ratings for 2024 game
- ✅ def456: Alabama St. resolved in Step 2 (ALIAS), using 2023 ratings for 2024 game
- ✅ ghi789: Tennessee resolved in Step 4 (MASCOT_STRIPPED), using 2023 ratings for 2024 game
- ❌ jkl012: UnknownSchool failed to resolve, game SKIPPED

**Goal:** Most games in CANONICAL/ALIAS (first 2 steps). Few in NORMALIZED/MASCOT. Zero UNRESOLVED.

---

## 🔴 Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| "Team not resolving" | Name not in aliases | Add to `team_aliases.json` |
| "Cross-source mismatch" | Different canonicals for same team | Update aliases for all sources |
| "Season mismatch" | Wrong month handling (5-10 mixed) | Check month distribution, fix parser |
| "Anti-leakage failed" | Using current season ratings | Ensure `AntiLeakageRatingsLoader` used |
| "Join rate < 98%" | Team names don't match after resolution | Run validation to find bad matches |

---

## 📋 Pre-Backtest Checklist

- [ ] `pre_backtest_gate.py` passes (all audits)
- [ ] Team resolution rate ≥ 99%
- [ ] Zero cross-source inconsistencies
- [ ] All seasons: Nov-Apr window ✓
- [ ] All timestamps: CST ✓
- [ ] Anti-leakage: Game N → Ratings N-1 ✓
- [ ] Join rate: ≥ 98% ✓
- [ ] Audit logs reviewed ✓
- [ ] No blockers in validation output ✓

**If all pass:**
```bash
python testing/production_parity/run_backtest.py
```

---

## 📚 Full Documentation

See [DATA_MATCHING_INTEGRITY_VERIFICATION.md](DATA_MATCHING_INTEGRITY_VERIFICATION.md) for detailed explanations.
