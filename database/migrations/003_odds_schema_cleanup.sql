-- Align odds_snapshots schema with ingestion service expectations
-- Drops deprecated columns/indexes, sets composite PK, converts to hypertable

-- Ensure games.external_id supports ON CONFLICT usage
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'games_external_id_key'
    ) THEN
        ALTER TABLE games
            ADD CONSTRAINT games_external_id_key UNIQUE (external_id);
    END IF;
END$$;

-- Add required columns if missing
ALTER TABLE odds_snapshots
    ADD COLUMN IF NOT EXISTS time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS period TEXT NOT NULL DEFAULT 'full';

-- Backfill time from legacy timestamp column if present
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'odds_snapshots' AND column_name = 'timestamp'
    ) THEN
        UPDATE odds_snapshots SET time = "timestamp" WHERE time IS NULL;
    END IF;
END$$;

-- Drop legacy constraints/indexes/columns
ALTER TABLE odds_snapshots DROP CONSTRAINT IF EXISTS odds_snapshots_pkey;
DROP INDEX IF EXISTS idx_odds_timestamp;
DROP INDEX IF EXISTS idx_odds_game_bookmaker_time;
DROP INDEX IF EXISTS ux_odds_snapshots_timestamp_game_bookmaker_market_period;
ALTER TABLE odds_snapshots DROP COLUMN IF EXISTS id;
ALTER TABLE odds_snapshots DROP COLUMN IF EXISTS "timestamp";

-- Recreate primary key and supporting indexes
ALTER TABLE odds_snapshots
    ADD CONSTRAINT odds_snapshots_pkey PRIMARY KEY (time, game_id, bookmaker, market_type, period);
CREATE INDEX IF NOT EXISTS idx_odds_bookmaker ON odds_snapshots(bookmaker);
CREATE INDEX IF NOT EXISTS odds_snapshots_time_idx ON odds_snapshots(time DESC);
CREATE INDEX IF NOT EXISTS idx_odds_game_time ON odds_snapshots(game_id, time DESC);

-- Convert to TimescaleDB hypertable (no-op if already converted)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'odds_snapshots',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
    ELSE
        RAISE NOTICE 'TimescaleDB not installed; leaving odds_snapshots as a regular table';
    END IF;
END$$;
