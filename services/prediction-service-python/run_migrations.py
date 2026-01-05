#!/usr/bin/env python3
"""Database migration runner (idempotent) for ALL environments.

Why this exists:
- Docker's /docker-entrypoint-initdb.d only runs on FIRST boot of a new volume.
  Existing Postgres volumes will NOT automatically apply newly added migration files.
- Azure Container Apps Postgres does not mount repo migration files by default.

This script makes migrations deterministic and production-ready by:
- Maintaining a `public.schema_migrations` table of applied migration filenames
- Applying missing numbered migrations in order (001_*.sql, 002_*.sql, ...)
- Using a Postgres advisory lock to avoid concurrent migration runs

Time zone remains CST (America/Chicago) in the application layer; migrations here are TZ-agnostic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import psycopg2


MIGRATIONS_DIR = Path("/app/migrations")
COMPLETE_SCHEMA = MIGRATIONS_DIR / "complete_schema.sql"
SCHEMA_MIGRATIONS_TABLE = "public.schema_migrations"
MIGRATIONS_LOCK_KEY = 933_110_001  # arbitrary constant, stable across runs


def _read_secret_file(file_path: str, secret_name: str) -> str:
    try:
        return Path(file_path).read_text(encoding="utf-8").strip()
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"Secret file missing at {file_path} ({secret_name}): {e}") from e


def _build_database_url_from_env() -> Optional[str]:
    """
    Build DATABASE_URL when it's not explicitly set.

    - Docker Compose: DB password is mounted at /run/secrets/db_password and DB_HOST=postgres.
    - Azure: DATABASE_URL is provided explicitly (no /run/secrets mount).
    """
    sport = os.getenv("SPORT", "ncaam")
    db_user = os.getenv("DB_USER", sport)
    db_name = os.getenv("DB_NAME", sport)
    db_host = os.getenv("DB_HOST", "postgres")
    db_port = os.getenv("DB_PORT", "5432")

    pw_file = os.getenv("DB_PASSWORD_FILE", "/run/secrets/db_password")
    if not Path(pw_file).exists():
        return None
    password = _read_secret_file(pw_file, "db_password")
    if not password:
        return None

    return f"postgresql://{db_user}:{password}@{db_host}:{db_port}/{db_name}"


def _split_sql(sql: str) -> List[str]:
    """Split SQL into statements, respecting quotes and dollar-strings."""

    stmts: List[str] = []
    buf: List[str] = []

    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag: Optional[str] = None  # e.g. $$ or $func$

    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        # End line comment
        if in_line_comment:
            buf.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        # End block comment
        if in_block_comment:
            buf.append(ch)
            if ch == "*" and nxt == "/":
                buf.append(nxt)
                i += 2
                in_block_comment = False
            else:
                i += 1
            continue

        # Inside dollar-quoted string
        if dollar_tag is not None:
            # Check for closing delimiter
            if ch == "$" and sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(ch)
            i += 1
            continue

        # Inside single-quoted string
        if in_single:
            buf.append(ch)
            if ch == "'":
                # Escaped single quote in SQL: ''
                if nxt == "'":
                    buf.append(nxt)
                    i += 2
                    continue
                in_single = False
            i += 1
            continue

        # Inside double-quoted identifier
        if in_double:
            buf.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        # Start comments
        if ch == "-" and nxt == "-":
            buf.append(ch)
            buf.append(nxt)
            i += 2
            in_line_comment = True
            continue
        if ch == "/" and nxt == "*":
            buf.append(ch)
            buf.append(nxt)
            i += 2
            in_block_comment = True
            continue

        # Start strings/identifiers
        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue

        # Start dollar-quoted string ($$ or $tag$)
        if ch == "$":
            # Find next '$' to determine tag
            j = i + 1
            while j < n and sql[j] != "$" and sql[j] != "\n" and sql[j] != "\r":
                j += 1
            if j < n and sql[j] == "$":
                tag = sql[i: j + 1]  # includes both $
                dollar_tag = tag
                buf.append(tag)
                i = j + 1
                continue

        # Statement terminator
        if ch == ";":
            statement = "".join(buf).strip()
            if statement:
                stmts.append(statement)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)

    return stmts


def _ordered_migration_files() -> List[Path]:
    """Return numbered migration files (001_*.sql ... 999_*.sql) in order."""
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def _migration_number(path: Path) -> Optional[int]:
    """Extract leading 3-digit migration number from filename, if present."""
    name = path.name
    if len(name) < 4:
        return None
    prefix = name[:3]
    if not prefix.isdigit():
        return None
    return int(prefix)


def _table_exists(cur, regclass: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (regclass,))
    return cur.fetchone()[0] is not None


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS(
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = split_part(%s, '.', 1)
              AND table_name = split_part(%s, '.', 2)
              AND column_name = %s
        )
        """,
        (table, table, column),
    )
    return bool(cur.fetchone()[0])


def _ensure_schema_migrations(cur) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA_MIGRATIONS_TABLE} (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _get_applied(cur) -> set:
    _ensure_schema_migrations(cur)
    cur.execute(f"SELECT filename FROM {SCHEMA_MIGRATIONS_TABLE}")
    return {r[0] for r in cur.fetchall()}


def _detect_existing_baseline(cur) -> int:
    """
    Detect an existing DB that was created without schema_migrations tracking.

    We must avoid re-running early non-idempotent migrations on a live schema.
    Baseline logic:
    - If core tables don't exist: baseline=0 (new/empty DB)
    - Else if teams.ncaa_id exists: assume at least migration 014 applied
    - Else: baseline=13 (older schema present but pre-014 extensions missing)

    This is conservative and aligned to the current repo history.
    """
    if not _table_exists(cur, "public.teams") or not _table_exists(cur, "public.games"):
        return 0
    if _column_exists(cur, "public.teams", "ncaa_id"):
        return 14
    return 13


def _files_to_apply(files: List[Path], applied: set, baseline: int) -> List[Path]:
    out: List[Path] = []
    for p in files:
        num = _migration_number(p) or 0
        if baseline and num < baseline:
            # Never try to re-run early pre-baseline migrations on an existing schema
            continue
        if p.name in applied:
            continue
        out.append(p)
    return out


def _apply_file(cur, file_path: Path) -> None:
    sql = file_path.read_text(encoding="utf-8")
    stmts = _split_sql(sql)
    print(f"Applying {file_path.name}: {len(stmts)} statements")
    for idx, stmt in enumerate(stmts, start=1):
        s = stmt.strip()
        if not s:
            continue
        # psycopg2 cannot execute comment-only queries. Our splitter may emit
        # trailing comment-only "statements" after the last semicolon.
        non_comment_lines = [
            ln for ln in s.splitlines()
            if ln.strip() and not ln.strip().startswith("--")
        ]
        if not non_comment_lines:
            continue
        maybe_sql = "\n".join(non_comment_lines).strip()
        if maybe_sql.startswith("/*") and maybe_sql.endswith("*/"):
            continue
        try:
            cur.execute(s)
        except Exception as e:
            preview = s.replace("\n", " ")
            preview = preview[:300] + ("..." if len(preview) > 300 else "")
            raise RuntimeError(
                f"Migration failed in {file_path.name} at statement {idx}: {preview}"
            ) from e


def main() -> int:
    db_url = os.getenv("DATABASE_URL") or _build_database_url_from_env()
    if not db_url:
        raise SystemExit(
            "DATABASE_URL is required (Azure) or DB_PASSWORD_FILE must exist (Docker)."
        )

    files = _ordered_migration_files()
    if not files and COMPLETE_SCHEMA.exists():
        files = [COMPLETE_SCHEMA]
    if not files:
        raise SystemExit(f"No migrations found in {MIGRATIONS_DIR}")

    print(f"Connecting to DATABASE_URL={db_url}")

    conn = psycopg2.connect(db_url)
    conn.autocommit = True

    try:
        with conn.cursor() as cur:
            # Single-writer migrations
            cur.execute("SELECT pg_advisory_lock(%s)", (MIGRATIONS_LOCK_KEY,))
            try:
                _ensure_schema_migrations(cur)
                applied = _get_applied(cur)
                baseline = int(os.getenv("MIGRATIONS_BASELINE", "0")) or _detect_existing_baseline(cur)

                # If we have a pre-tracked schema, baseline protects from re-running early migrations.
                to_apply = _files_to_apply(files, applied, baseline)
                if not to_apply:
                    print("No pending migrations.")
                    return 0

                for file_path in to_apply:
                    _apply_file(cur, file_path)
                    cur.execute(
                        f"INSERT INTO {SCHEMA_MIGRATIONS_TABLE} (filename) VALUES (%s) ON CONFLICT DO NOTHING",
                        (file_path.name,),
                    )
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s)", (MIGRATIONS_LOCK_KEY,))

        print("Migrations applied successfully")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
