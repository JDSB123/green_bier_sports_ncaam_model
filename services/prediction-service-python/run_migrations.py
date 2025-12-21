#!/usr/bin/env python3
"""One-shot schema bootstrap for Azure Container Apps.

Why this exists:
- Local Docker Compose mounts `database/migrations` into Postgres init.
- Azure Container Apps Postgres container has no mounted migration files.

This script applies `complete_schema.sql` to the DATABASE_URL Postgres.
It is safe to re-run: if `public.teams` exists, it exits successfully.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import psycopg2


MIGRATIONS_DIR = Path("/app/migrations")
COMPLETE_SCHEMA = MIGRATIONS_DIR / "complete_schema.sql"


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
                tag = sql[i : j + 1]  # includes both $
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
    """
    Apply numbered migrations first (001_*.sql ... 999_*.sql).
    Fall back to complete_schema.sql only if no numbered migrations exist.
    """
    numbered = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    if numbered:
        return numbered
    if COMPLETE_SCHEMA.exists():
        return [COMPLETE_SCHEMA]
    return []


def main() -> int:
    db_url = os.getenv("DATABASE_URL") or _build_database_url_from_env()
    if not db_url:
        raise SystemExit(
            "DATABASE_URL is required (Azure) or DB_PASSWORD_FILE must exist (Docker)."
        )

    files = _ordered_migration_files()
    if not files:
        raise SystemExit(f"No migrations found in {MIGRATIONS_DIR}")

    print(f"Connecting to DATABASE_URL={db_url}")

    conn = psycopg2.connect(db_url)
    conn.autocommit = True

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.games')")
            exists = cur.fetchone()[0]
            if exists:
                print("Schema already present (public.games exists). Nothing to do.")
                return 0

        with conn.cursor() as cur:
            for file_path in files:
                sql = file_path.read_text(encoding="utf-8")
                stmts = _split_sql(sql)
                print(f"Applying {file_path.name}: {len(stmts)} statements")

                for idx, stmt in enumerate(stmts, start=1):
                    s = stmt.strip()
                    if not s:
                        continue
                    try:
                        cur.execute(s)
                    except Exception as e:
                        preview = s.replace("\n", " ")
                        preview = preview[:300] + ("..." if len(preview) > 300 else "")
                        raise RuntimeError(
                            f"Migration failed in {file_path.name} at statement {idx}: {preview}"
                        ) from e

        print("Migrations applied successfully")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
