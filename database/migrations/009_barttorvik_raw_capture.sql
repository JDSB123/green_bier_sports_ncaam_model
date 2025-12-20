-- MIGRATION 009: Capture full Barttorvik metrics payload for audit/compatibility
-- Adds a JSONB column to store the raw array-of-arrays mapped to field names

ALTER TABLE team_ratings ADD COLUMN IF NOT EXISTS raw_barttorvik JSONB;

COMMENT ON COLUMN team_ratings.raw_barttorvik IS 'Full Barttorvik metrics payload captured as JSON for audit and future compatibility with legacy files/fields.';
