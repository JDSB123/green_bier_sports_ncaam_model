-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 025: Team Source IDs (External ID Registry)
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose:
--   Provide a normalized, extensible mapping of teams to authoritative external
--   identifiers (ESPN, NCAA, Sports-Reference, API-Basketball, etc.).
--
-- Why:
--   Team name variants drift across sources. External IDs are more stable and
--   should be the preferred join key whenever available.
--
-- Notes:
--   - We KEEP existing teams.ncaa_id / teams.espn_id / teams.sports_ref_id columns
--     (added in migration 014) but backfill them into this table for unified access.
--   - This table supports seasonal scoping (first_season/last_season) and metadata.
--
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS team_source_ids (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id          UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    source           TEXT NOT NULL,      -- e.g. 'espn', 'ncaa', 'sports_ref', 'api_basketball'
    external_team_id TEXT NOT NULL,      -- store as TEXT to support numeric + string IDs
    first_season     INTEGER,            -- optional season bound (NCAA season year)
    last_season      INTEGER,            -- optional season bound
    metadata         JSONB DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source, external_team_id)
);

CREATE INDEX IF NOT EXISTS idx_team_source_ids_team ON team_source_ids(team_id);
CREATE INDEX IF NOT EXISTS idx_team_source_ids_source ON team_source_ids(source);

-- Keep updated_at current
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trigger_team_source_ids_updated_at'
    ) THEN
        CREATE TRIGGER trigger_team_source_ids_updated_at
            BEFORE UPDATE ON team_source_ids
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END
$$;

COMMENT ON TABLE team_source_ids IS
    'Maps canonical teams(id) to external source identifiers (ESPN/NCAA/etc.) to avoid name-based joins';

COMMENT ON COLUMN team_source_ids.source IS
    'Source system identifier: espn, ncaa, sports_ref, api_basketball, the_odds_api, barttorvik, kenpom, etc.';

COMMENT ON COLUMN team_source_ids.external_team_id IS
    'External team identifier from the source system (stored as text)';

COMMENT ON COLUMN team_source_ids.first_season IS
    'First NCAA season year this mapping is valid (optional)';

COMMENT ON COLUMN team_source_ids.last_season IS
    'Last NCAA season year this mapping is valid (optional)';


-- Backfill from existing columns added by migration 014 (best-effort).
INSERT INTO team_source_ids (team_id, source, external_team_id, metadata)
SELECT id, 'espn', espn_id::text, jsonb_build_object('backfilled_from', 'teams.espn_id')
FROM teams
WHERE espn_id IS NOT NULL
ON CONFLICT (source, external_team_id) DO NOTHING;

INSERT INTO team_source_ids (team_id, source, external_team_id, metadata)
SELECT id, 'ncaa', ncaa_id::text, jsonb_build_object('backfilled_from', 'teams.ncaa_id')
FROM teams
WHERE ncaa_id IS NOT NULL
ON CONFLICT (source, external_team_id) DO NOTHING;

INSERT INTO team_source_ids (team_id, source, external_team_id, metadata)
SELECT id, 'sports_ref', sports_ref_id::text, jsonb_build_object('backfilled_from', 'teams.sports_ref_id')
FROM teams
WHERE sports_ref_id IS NOT NULL
ON CONFLICT (source, external_team_id) DO NOTHING;

