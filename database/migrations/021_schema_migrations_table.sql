-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION 021: schema_migrations tracking table (idempotent)
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Purpose:
-- Provide a canonical place to track applied migration filenames for production
-- environments where Postgres init scripts do not run on existing volumes.
--
-- The runtime migration runner (`/app/run_migrations.py`) will also ensure this
-- table exists, but we create it here so it is present on fresh DB init too.
--

CREATE TABLE IF NOT EXISTS public.schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

