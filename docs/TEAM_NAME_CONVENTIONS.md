# NCAA Men's Basketball Team Name Conventions by Source

This document defines the official team name formats used by each data source
integrated into the Green Bier Sports NCAAM prediction model.

## Quick Reference

| Source | Format | Example |
|--------|--------|---------|
| **Odds API** | `[School] [Mascot]` | `Duke Blue Devils` |
| **Barttorvik** | `[Short Name]` | `Duke` |
| **KenPom** | `[Short Name]` | `Duke` |
| **ESPN** | `[School] [Mascot]` | `Duke Blue Devils` |
| **Basketball API** | `[School Name]` | `Duke` |
| **NCAA Official** | Multiple formats | `DUKE` / `Duke` / `duke` |

## Detailed Source Documentation

### 1. The Odds API

**Endpoint**: `https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds`

**Format**: Full school name with mascot

**Examples**:
```json
{
  "home_team": "Duke Blue Devils",
  "away_team": "Wake Forest Demon Deacons"
}
```

**Critical Distinctions**:
- `Tennessee Volunteers` (SEC, Knoxville)
- `Tennessee State Tigers` (OVC, Nashville)
- `East Tennessee State Buccaneers` (SoCon, Johnson City)
- `Tennessee Tech Golden Eagles` (OVC, Cookeville)

**Mapping Rule**: Strip mascot to get canonical name, then resolve via `team_aliases`.

---

### 2. Barttorvik (T-Rank)

**Endpoint**: `https://barttorvik.com/{year}_team_results.json`

**Format**: Short school name, "State" abbreviated to "St."

**Examples**:
```
Duke
North Carolina
Michigan St.
Ohio St.
Tennessee
Tennessee St.
```

**Notes**:
- This is our **canonical name** standard
- No mascots
- Abbreviates "State" to "St." consistently
- Uses "FL" / "OH" suffixes for disambiguation (e.g., "Miami FL")

---

### 3. KenPom

**Endpoint**: `https://kenpom.com/` (scraping required, no public API)

**Format**: Nearly identical to Barttorvik

**Examples**:
```
Michigan
Iowa St.
Gonzaga
Connecticut (not "UConn")
BYU (acronym)
```

**Mapping Rule**: Usually 1:1 with Barttorvik canonical names.

---

### 4. ESPN

**Endpoint**: `https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard`

**Multiple Fields Available**:

| Field | Example | Use |
|-------|---------|-----|
| `displayName` | `Duke Blue Devils` | Full name |
| `shortDisplayName` | `Duke` | Short name |
| `name` | `Blue Devils` | Mascot only |
| `abbreviation` | `DUKE` | 4-6 char code |
| `id` | `150` | ESPN team ID |

**Recommendation**: Use `shortDisplayName` for matching, `id` for disambiguation.

---

### 5. API-Basketball

**Endpoint**: `https://v1.basketball.api-sports.io/teams?league=116`

**Format**: Variable, usually school name only

**Examples**:
```json
{
  "id": 3423,
  "name": "Duke",
  "logo": "..."
}
```

**Notes**:
- Less consistent than other sources
- Use team `id` for reliable matching

---

### 6. NCAA Official

**Source**: NCAA.com / henrygd/ncaa-api

**Multiple Formats**:

| Format | Example | Description |
|--------|---------|-------------|
| `char6` | `OHIOST` | 6-character abbreviation |
| `short` | `Ohio St.` | Display name |
| `seo` | `ohio-st` | URL-safe slug |
| `full` | `The Ohio State University` | Legal name |
| `ncaa_id` | `518` | Unique NCAA ID |

---

## Disambiguation Rules

### Problem Teams (Multiple with Same Base Name)

| Base Name | Variants | Solution |
|-----------|----------|----------|
| Tennessee | Tennessee (SEC), Tennessee St. (OVC), Tennessee Tech (OVC), ETSU (SoCon), UT Martin (OVC), Middle Tennessee (CUSA) | Use full name + conference |
| Miami | Miami FL (ACC), Miami OH (MAC) | Use state suffix |
| USC | USC (Big Ten), South Carolina (SEC) | Different canonical names |
| Washington | Washington (Big Ten), Washington St. (Big 12) | Use "St." suffix |
| Florida | Florida (SEC), Florida St. (ACC) | Use "St." suffix |

### Required Metadata for Disambiguation

1. **Conference** - Primary disambiguator
2. **City** - Secondary (Knoxville vs Nashville)
3. **State** - Tertiary (FL vs OH)
4. **ESPN ID** - Authoritative unique identifier
5. **NCAA ID** - Official NCAA identifier

---

## Team Aliases Table Structure

```sql
CREATE TABLE team_aliases (
    id          UUID PRIMARY KEY,
    team_id     UUID REFERENCES teams(id),
    alias       TEXT NOT NULL,
    source      TEXT NOT NULL,  -- 'the_odds_api', 'espn', 'barttorvik', 'kenpom', 'basketball_api'
    confidence  FLOAT DEFAULT 1.0,
    UNIQUE(alias, source)
);
```

**Source Values**:
- `the_odds_api` - Full names with mascots
- `espn` - Multiple formats (displayName, shortDisplayName)
- `barttorvik` - Short names (our canonical)
- `kenpom` - Short names
- `basketball_api` - Variable format
- `ncaa` - Official NCAA names
- `manual` - Hand-entered corrections

---

## Resolution Priority

When resolving a team name, the system checks in order:

1. **Exact match** on `canonical_name`
2. **Exact match** on `team_aliases.alias` for given source
3. **Normalized match** (lowercase, no punctuation)
4. **Mascot-stripped match** (remove known mascot words)
5. **NO FUZZY MATCHING** - Return NULL if no match

If no match found, the team is flagged as unresolved and the prediction
is blocked until manually resolved.

---

## Adding New Aliases

When a new team variant is encountered:

```sql
-- Find the canonical team
SELECT id, canonical_name FROM teams WHERE canonical_name ILIKE '%tennessee%';

-- Add the alias
INSERT INTO team_aliases (team_id, alias, source, confidence)
VALUES (
    '<team-uuid>',
    'Tennessee State Tigers',  -- exact string from source
    'the_odds_api',
    1.0
);
```

---

## Common Mistakes to Avoid

1. **Fuzzy matching** - Never use Levenshtein or similarity for team names
2. **Partial matching** - "Tennessee" should NOT match "Tennessee State"
3. **Case sensitivity** - Always normalize to lowercase for comparison
4. **Mascot confusion** - "Panthers" matches 10+ teams, never use alone
5. **Missing state suffix** - Miami FL ≠ Miami (must include FL/OH)

---

## References

- [The Odds API NCAAB](https://the-odds-api.com/sports-odds-data/ncaa-basketball-odds.html)
- [ESPN API](https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball)
- [KenPom Ratings](https://kenpom.com/)
- [Barttorvik T-Rank](https://barttorvik.com/)
- [NCAA API (henrygd)](https://github.com/henrygd/ncaa-api)
- [toRvik R Package](https://www.torvik.dev/articles/introduction.php)
