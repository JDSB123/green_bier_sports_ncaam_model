# Standardized Team Name Mappings Integration

## Overview

This document describes how to integrate standardized team name mappings from established R packages in the college basketball analytics community. These packages provide comprehensive mappings across multiple data sources (ESPN, KenPom, Bart Torvik, WarrenNolan, etc.) that can significantly improve our team matching coverage.

## Available Resources

### 1. ncaahoopR (lbenz730/ncaahoopR)

**GitHub:** https://github.com/lbenz730/ncaahoopR

**Dataset:** Built-in `dict` dataset mapping variants across:
- NCAA (official)
- ESPN (including URL and play-by-play formats)
- WarrenNolan
- Trank (Bart Torvik's site)
- 247Sports

**Coverage:** ~350+ D1 teams with comprehensive variants

**How to Extract:**
```r
# Install package
install.packages("devtools")
devtools::install_github("lbenz730/ncaahoopR")

# Load and export dict
library(ncaahoopR)
data(dict)
write.csv(dict, "ncaahoopr_dict.csv", row.names = FALSE)
```

### 2. hoopR (sportsdataverse/hoopR)

**CRAN/R Package:** https://cran.r-project.org/package=hoopR

**Dataset:** `teams_links` dataset mapping:
- ESPN team names and IDs
- KenPom references/links

**Coverage:** Strong for ESPN and KenPom variants

**How to Extract:**
```r
# Install package
install.packages("hoopR")

# Load and export teams_links
library(hoopR)
data(teams_links)
jsonlite::write_json(teams_links, "hoopr_teams_links.json", pretty = TRUE)
```

### 3. toRvik/cbbdata (andreweatherman/toRvik)

**GitHub:** https://github.com/andreweatherman/toRvik

**Dataset:** Native Bart Torvik (T-Rank) data with standardized team names

**Coverage:** All teams in Bart Torvik's database

**How to Extract:**
```r
# Install package
devtools::install_github("andreweatherman/toRvik")

# Get team names
library(toRvik)
teams <- cbd_teams()
write.csv(teams, "torvik_teams.csv", row.names = FALSE)
```

## Import Process

### Step 1: Extract Data from R Packages

Use the R scripts above to export CSV or JSON files from the packages.

### Step 2: Import Using Python Script

Use the `import_standardized_team_mappings.py` script:

```bash
# From ncaahoopR dict
python services/prediction-service-python/scripts/import_standardized_team_mappings.py \
    --source ncaahoopr \
    --input ncaahoopr_dict.csv

# From hoopR teams_links (JSON)
python services/prediction-service-python/scripts/import_standardized_team_mappings.py \
    --source hoopr \
    --input hoopr_teams_links.json \
    --format json

# From toRvik teams
python services/prediction-service-python/scripts/import_standardized_team_mappings.py \
    --source torvik \
    --input torvik_teams.csv

# Dry run (preview changes)
python services/prediction-service-python/scripts/import_standardized_team_mappings.py \
    --source ncaahoopr \
    --input ncaahoopr_dict.csv \
    --dry-run
```

### Step 3: Verify Import

Check the import statistics and verify aliases were added:

```sql
-- Check new aliases by source
SELECT source, COUNT(*) as count
FROM team_aliases
WHERE source LIKE 'ncaahoopr%' OR source LIKE 'hoopr%' OR source LIKE 'torvik%'
GROUP BY source
ORDER BY source;

-- Check specific team aliases
SELECT ta.alias, ta.source, t.canonical_name
FROM team_aliases ta
JOIN teams t ON ta.team_id = t.id
WHERE t.canonical_name = 'Duke'
ORDER BY ta.source, ta.alias;
```

## Source Naming Convention

The import script prefixes source names to avoid conflicts:

- `ncaahoopr_espn` - ESPN variants from ncaahoopR
- `ncaahoopr_barttorvik` - Bart Torvik (Trank) variants from ncaahoopR
- `ncaahoopr_warren_nolan` - WarrenNolan variants from ncaahoopR
- `hoopr_espn` - ESPN variants from hoopR
- `hoopr_kenpom` - KenPom variants from hoopR
- `torvik_barttorvik` - Bart Torvik variants from toRvik

## Benefits

1. **Comprehensive Coverage:** Adds 1000+ additional team name variants
2. **KenPom Support:** First-time support for KenPom team name mappings
3. **ESPN Enhancement:** More comprehensive ESPN variants
4. **Community Standard:** Uses mappings maintained by the analytics community
5. **Conference Realignments:** Packages are updated for conference changes

## Integration with Existing System

The imported mappings integrate seamlessly with the existing team matching system:

1. **Uses Existing Infrastructure:** Aliases are stored in `team_aliases` table
2. **Works with `resolve_team_name()`:** All aliases are automatically used by the resolution function
3. **Source Tracking:** Each alias is tagged with its source for auditability
4. **No Conflicts:** Uses `ON CONFLICT DO NOTHING` to avoid duplicate aliases

## Custom CSV Format

You can also import custom mappings using the generic format:

```csv
canonical,alias,source
Duke,Duke Blue Devils,manual
North Carolina,UNC,manual
```

```bash
python services/prediction-service-python/scripts/import_standardized_team_mappings.py \
    --source generic \
    --input custom_mappings.csv \
    --canonical-col canonical \
    --alias-col alias \
    --source-col source
```

## Troubleshooting

### Unresolved Canonical Names

If the script reports unresolved canonical names, it means the R package uses different canonical names than our database. Options:

1. **Add Missing Teams:** Create teams with the R package's canonical names
2. **Create Mapping File:** Create a CSV mapping R package names to our canonical names
3. **Manual Review:** Review the unresolved names and decide if they're needed

### Duplicate Aliases

The script automatically skips duplicates (same alias + source combination). This is expected behavior.

### Source Name Conflicts

If you need to change source naming, modify the `import_mappings()` function in the script.

## Maintenance

### Regular Updates

R packages are updated for:
- Conference realignments
- New teams
- Name changes

Consider re-running imports annually or when major conference changes occur.

### Validation

After importing, validate with:

```sql
-- Check for teams with no aliases from new sources
SELECT t.canonical_name
FROM teams t
WHERE NOT EXISTS (
    SELECT 1 FROM team_aliases ta
    WHERE ta.team_id = t.id
    AND (ta.source LIKE 'ncaahoopr%' OR ta.source LIKE 'hoopr%')
)
ORDER BY t.canonical_name;
```

## References

- [ncaahoopR GitHub](https://github.com/lbenz730/ncaahoopR)
- [hoopR CRAN](https://cran.r-project.org/package=hoopR)
- [toRvik GitHub](https://github.com/andreweatherman/toRvik)
- [Team Matching System Documentation](./TEAM_MATCHING_SYSTEM.md)
