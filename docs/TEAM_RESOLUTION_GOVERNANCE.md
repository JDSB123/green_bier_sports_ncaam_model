# Team Name Resolution Governance

## Overview

This document describes the **AUTHORITATIVE** team name resolution system and governance rules to prevent bypassing the canonical gate.

## Single Source of Truth

All team name resolution **MUST** go through:

- **Production/Backtesting**: `testing/canonical/team_resolution_service.py` (Azure/Postgres-backed)
- **Live Predictions**: `testing/canonical/barttorvik_team_mappings.py` (embedded version of same data)

Both modules contain the **identical mappings** from the Postgres `team_aliases` table (95%+ coverage, 600+ aliases).

## Rules

### ✅ ALLOWED

- Using `resolve_odds_api_to_barttorvik()` from `barttorvik_team_mappings.py`
- Using `resolve_team_name()` from `team_resolution_service.py`
- Adding new mappings to Postgres `team_aliases` table
- Exporting updates via `scripts/export_team_registry.py`

### ❌ FORBIDDEN

- Creating ad-hoc mapping dictionaries in application code
- Using fuzzy/probabilistic matching for team resolution
- Inline string manipulation to "fix" team names
- Bypassing the canonical modules with custom logic

## Adding New Team Mappings

When a team name fails to resolve:

1. **Add to Postgres**: Insert into `team_aliases` table
   ```sql
   INSERT INTO team_aliases (team_id, alias, source, confidence)
   VALUES (
     (SELECT id FROM teams WHERE canonical_name = 'Tulane'),
     'Tulane Green Wave',
     'the_odds_api',
     1.0
   );
   ```

2. **Export registry**: Run `python scripts/export_team_registry.py`

3. **Update embedded module**: Add mapping to `testing/canonical/barttorvik_team_mappings.py`
   ```python
   ODDS_API_TO_BARTTORVIK = {
       # ... existing mappings ...
       "tulane green wave": "tulane",  # Add new mapping
   }
   ```

4. **Document**: Update `Last updated` timestamp in module docstring

## Governance Enforcement

### Automated Test

Run: `python testing/test_team_resolution_governance.py`

This test ensures:
- ✅ No ad-hoc team mappings in `generate_tonight_picks.py`
- ✅ No fuzzy matching imports in critical files
- ✅ `generate_tonight_picks.py` uses authoritative gate

### Pre-Commit Check

Add to `.github/workflows/ci.yml`:
```yaml
- name: Verify team resolution governance
  run: python testing/test_team_resolution_governance.py
```

## Architecture

```
┌─────────────────────────────────────────┐
│  Postgres team_aliases Table           │
│  (Authoritative Source)                 │
│  - 600+ aliases                         │
│  - 95%+ D1 coverage                     │
└─────────��────┬──────────────────────────┘
               │
               ├──────────────────────────────────┐
               │                                  │
               ▼                                  ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│ team_resolution_service.py   │  │ barttorvik_team_mappings.py  │
│ (Azure/Postgres-backed)      │  │ (Embedded for live)          │
│ - Production                 │  │ - Local dev                  │
│ - Historical backtesting     │  │ - Live predictions           │
└──────────────────────────────┘  └──────────────────────────────┘
               │                                  │
               │                                  │
               ▼                                  ▼
       [Backtest Scripts]              [generate_tonight_picks.py]
```

## Coverage

Current coverage: **79.1%** (34/43 games on 2026-01-18)

Missing teams are typically:
- Low-tier conferences (SWAC, NEC, MEAC)
- Division II/III schools
- Transitioning programs

All major conference games have 100% coverage.

## History

- **2026-01-18**: Created governance framework and embedded mappings module
- **2025-2026**: Built Postgres team_aliases table with 600+ aliases
- **Prior**: Ad-hoc mappings scattered across codebase (deprecated)

## Contact

Questions about team resolution governance? See:
- `testing/canonical/barttorvik_team_mappings.py` (module documentation)
- `scripts/export_team_registry.py` (export process)
- `database/migrations/` (alias table schema and migrations)
