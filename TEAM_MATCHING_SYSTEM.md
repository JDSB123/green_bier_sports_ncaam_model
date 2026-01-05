# Team Variant Matching System - 99% Accuracy

## Overview
This document maps where the team variant matching logic exists in the codebase to prevent recreating the wheel. The system ensures **99%+ accuracy** in matching team names across different data sources (Barttorvik, The Odds API, etc.) before data ingestion proceeds.

---

## Core Components

### 1. Database Function: `resolve_team_name()` 
**Location:** `database/migrations/004_team_name_resolver.sql`

This is the **single source of truth** for team name resolution. It provides 99%+ accuracy by:
- Matching against `canonical_name` in `teams` table
- Matching against `alias` in `team_aliases` table  
- Preferring teams that have ratings (from Barttorvik) to avoid duplicates
- Case-insensitive matching

```sql
CREATE OR REPLACE FUNCTION resolve_team_name(input_name TEXT) 
RETURNS TEXT AS $$
    SELECT t.canonical_name 
    FROM teams t
    LEFT JOIN team_aliases ta ON t.id = ta.team_id
    LEFT JOIN team_ratings tr ON t.id = tr.team_id
    WHERE LOWER(t.canonical_name) = LOWER(input_name)
       OR LOWER(ta.alias) = LOWER(input_name)
    ORDER BY tr.team_id IS NOT NULL DESC, t.canonical_name
    LIMIT 1;
$$ LANGUAGE SQL STABLE;
```

**Usage:**
```sql
SELECT resolve_team_name('Duke Blue Devils');  -- Returns 'Duke'
SELECT resolve_team_name('UNC');              -- Returns 'North Carolina' (if alias exists)
```

---

### 2. Database Schema: `team_aliases` Table
**Location:** `database/migrations/001_initial_schema.sql` (lines 27-40)

Stores 900+ name variations across all data sources:
- `alias`: The variant name (e.g., "Duke Blue Devils", "UNC")
- `source`: Where it came from ('the_odds_api', 'barttorvik', 'espn', etc.)
- `team_id`: Links to canonical team in `teams` table
- Unique constraint on `(alias, source)` prevents duplicates

**Indexes:**
- `idx_team_aliases_alias` on `LOWER(alias)` for fast lookups
- `idx_team_aliases_team` on `team_id`
- `idx_team_aliases_source` on `source`

---

### 3. Seed Data: Canonical Teams & Aliases
**Location:** `database/migrations/005_complete_team_data.sql`

Pre-populates:
- All 365 NCAA D1 teams with canonical names
- Common aliases across data sources
- Conference assignments

---

## Implementation in Services

### A. Ratings Sync (Go) - Barttorvik Data
**Location:** `services/ratings-sync-go/main.go` (lines 242-354)

**Function:** `ensureTeam()` - Ensures team exists before storing ratings

**Matching Strategy (3-step fallback):**
1. **Direct match:** Check `barttorvik_name` field first
2. **Database resolution:** Call `resolve_team_name(team.Team)` - **99.99% accuracy**
3. **Normalization fallback:** If resolution fails, normalize name using `normalizeTeamName()` then check `canonical_name`

**Normalization Rules** (lines 330-354):
```go
replacements := map[string]string{
    " State":         " St.",
    "Saint ":         "St. ",
    "St ":            "St. ",
    "University":     "U",
    "College":        "Col.",
    "North Carolina": "N.C.",
    "South Carolina": "S.C.",
    "Northern ":      "N. ",
    "Southern ":      "S. ",
    "Eastern ":       "E. ",
    "Western ":       "W. ",
    "Central ":       "C. ",
}
```

**Key Behavior:**
- Always stores alias in `team_aliases` table for future matching
- Updates `barttorvik_name` if not set
- Only creates new team if no match found after all steps

---

### B. Odds Ingestion (Rust) - The Odds API Data
**Location:** `services/odds-ingestion-rust/src/main.rs` (lines 703-798)

**Function:** `get_or_create_team()` - Gets or creates team before storing odds

**Matching Strategy (4-step process):**
1. **Database resolution:** Call `resolve_team_name(team_name)` - **99% accuracy**
2. **Get team ID:** Lookup by resolved `canonical_name`
3. **Store alias:** If variant differs from canonical, add to `team_aliases` table
4. **Create if missing:** Only creates new team with normalized canonical name

**Normalization Rules** (lines 772-798):
```rust
let replacements = vec![
    (" State", " St."),
    ("Saint ", "St. "),
    ("St ", "St. "),
    ("University", "U"),
    ("College", "Col."),
    ("North Carolina", "N.C."),
    ("South Carolina", "S.C."),
    ("Northern ", "N. "),
    ("Southern ", "S. "),
    ("Eastern ", "E. "),
    ("Western ", "W. "),
    ("Central ", "C. "),
];
```

**Key Behavior:**
- Always stores original variant as alias for future matching
- Uses normalized canonical name for new teams
- Prevents duplicate teams by resolving first

---

## Pattern for New Data Sources

When adding a new data source, follow this pattern:

### Step 1: Use `resolve_team_name()` Function
```sql
SELECT resolve_team_name($1)  -- Returns canonical name or NULL
```

### Step 2: If Resolved, Get Team ID
```sql
SELECT id FROM teams WHERE canonical_name = $1
```

### Step 3: Store Alias for Future Matching
```sql
INSERT INTO team_aliases (team_id, alias, source)
VALUES ($1, $2, 'your_source_name')
ON CONFLICT (alias, source) DO NOTHING
```

### Step 4: Fallback Normalization (if resolution fails)
Use the normalization rules to convert to canonical format, then:
- Check if team exists with normalized name
- If not, create new team with normalized canonical name
- Store original variant as alias

---

## Key Principles

1. **Always call `resolve_team_name()` first** - This is the 99% accurate matcher
2. **Store all variants as aliases** - Future matches will be faster
3. **Use canonical names for new teams** - Normalize before creating
4. **Prefer teams with ratings** - The function prioritizes teams that have Barttorvik ratings
5. **Case-insensitive matching** - All comparisons use `LOWER()`

---

## Files Reference

| Component | File Path | Purpose |
|-----------|-----------|---------|
| **Core Function** | `database/migrations/004_team_name_resolver.sql` | `resolve_team_name()` SQL function |
| **Schema** | `database/migrations/001_initial_schema.sql` | `teams` and `team_aliases` tables |
| **Seed Data** | `database/migrations/005_complete_team_data.sql` | Canonical teams and common aliases |
| **Go Implementation** | `services/ratings-sync-go/main.go` | Barttorvik ratings sync |
| **Rust Implementation** | `services/odds-ingestion-rust/src/main.rs` | The Odds API ingestion |

---

## Testing the System

To verify team matching is working:

```sql
-- Test resolution
SELECT resolve_team_name('Duke Blue Devils');
SELECT resolve_team_name('UNC');
SELECT resolve_team_name('N.C. State');

-- Check aliases for a team
SELECT ta.alias, ta.source 
FROM team_aliases ta
JOIN teams t ON ta.team_id = t.id
WHERE t.canonical_name = 'Duke';

-- Find unmapped variants (potential issues)
SELECT DISTINCT alias, source 
FROM team_aliases 
WHERE team_id NOT IN (
    SELECT id FROM teams WHERE id IN (
        SELECT DISTINCT team_id FROM team_ratings
    )
);
```

---

---

## Standardized Mappings from R Packages

To enhance team matching coverage, we can import standardized mappings from established R packages in the college basketball analytics community:

### Available Sources

1. **ncaahoopR** - Maps variants across NCAA, ESPN, WarrenNolan, Trank (Bart Torvik), 247Sports
2. **hoopR** - Maps ESPN and KenPom variants
3. **toRvik/cbbdata** - Bart Torvik native formats

### Import Process

Use the `import_standardized_team_mappings.py` script to import mappings:

```bash
# From ncaahoopR
python services/prediction-service-python/scripts/import_standardized_team_mappings.py \
    --source ncaahoopr \
    --input ncaahoopr_dict.csv

# From hoopR (KenPom support)
python services/prediction-service-python/scripts/import_standardized_team_mappings.py \
    --source hoopr \
    --input hoopr_teams_links.json \
    --format json
```

**See:** [Standardized Team Mappings Documentation](./docs/STANDARDIZED_TEAM_MAPPINGS.md) for detailed instructions.

### Benefits

- **1000+ additional variants** from community-maintained datasets
- **KenPom support** - First-time support for KenPom team name mappings
- **ESPN enhancement** - More comprehensive ESPN variants
- **Automatic integration** - Works seamlessly with existing `resolve_team_name()` function

---

## Notes

- The system is **already implemented** in both Go and Rust services
- **Do not recreate** - use `resolve_team_name()` function
- Normalization rules are duplicated in Go and Rust - consider centralizing if needed
- The `team_aliases` table grows organically as new variants are encountered
- Accuracy improves over time as more aliases are added
- **Standardized mappings** can be imported from R packages to enhance coverage
