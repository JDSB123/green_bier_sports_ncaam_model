#!/usr/bin/env python3
"""
Import team aliases from team_aliases_db.json into Postgres team_aliases.

Use case:
  - Bootstrap or reconcile DB aliases with the historical/backtest alias database
    (Azure Blob: backtest_datasets/team_aliases_db.json).

IMPORTANT:
  - By default this script does NOT create missing teams.
  - It only inserts aliases for canonical teams that already exist in teams.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Optional

import psycopg2

try:
    from azure.storage.blob import BlobServiceClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False


ROOT = Path(__file__).resolve().parents[1]


def _normalize_db_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("postgresql+psycopg2://"):
        u = "postgresql://" + u[len("postgresql+psycopg2://"):]
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]
    return u


def _read_secret(path: Path) -> Optional[str]:
    try:
        s = path.read_text(encoding="utf-8").strip()
        return s or None
    except Exception:
        return None


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return _normalize_db_url(url)

    sport = os.getenv("SPORT", "ncaam")
    db_user = os.getenv("DB_USER", sport)
    db_name = os.getenv("DB_NAME", sport)
    host = os.getenv("DB_HOST", "localhost")
    port = (
        os.getenv("DB_PORT")
        or os.getenv("POSTGRES_HOST_PORT")
        or "5450"
    )

    pw = (
        os.getenv("DB_PASSWORD", "").strip()
        or _read_secret(ROOT / "secrets" / "db_password.txt")
    )
    if not pw:
        raise RuntimeError(
            "Database password not found. Set DATABASE_URL, or set DB_PASSWORD, "
            "or create secrets/db_password.txt to match docker-compose."
        )
    return f"postgresql://{db_user}:{pw}@{host}:{port}/{db_name}"


def _load_aliases_from_azure(container: str, blob_path: str) -> Dict[str, str]:
    if not AZURE_AVAILABLE:
        raise ImportError("azure-storage-blob is required to load aliases from Azure.")

    conn_str = os.getenv("AZURE_CANONICAL_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError(
            "AZURE_CANONICAL_CONNECTION_STRING is required to load team aliases from Azure."
        )

    service = BlobServiceClient.from_connection_string(conn_str)
    container_client = service.get_container_client(container)
    blob_client = container_client.get_blob_client(blob_path)
    payload = blob_client.download_blob().readall()
    return json.loads(payload.decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import team aliases JSON into Postgres"
    )
    parser.add_argument("--db-url", default="", help="Optional Postgres URL override")
    parser.add_argument(
        "--azure-container",
        default=os.getenv("AZURE_CANONICAL_CONTAINER", "ncaam-historical-data"),
        help="Azure container name (default: ncaam-historical-data)",
    )
    parser.add_argument(
        "--aliases-blob",
        default="backtest_datasets/team_aliases_db.json",
        help="Blob path for team_aliases_db.json",
    )
    parser.add_argument(
        "--source",
        default="aliases_db_json",
        help="Source string to store in team_aliases.source",
    )
    parser.add_argument(
        "--create-missing-teams",
        action="store_true",
        help=(
            "If set, create teams rows for canonical names not present "
            "(USE WITH CAUTION)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute actions but do not modify DB.",
    )
    args = parser.parse_args()

    mapping = _load_aliases_from_azure(args.azure_container, args.aliases_blob)
    if not isinstance(mapping, dict) or not mapping:
        print("[FAIL] aliases file is empty or invalid JSON object")
        return 1

    db_url = _normalize_db_url(args.db_url) if args.db_url else get_database_url()
    conn = psycopg2.connect(db_url)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            inserted = 0
            skipped_missing_team = 0
            created_teams = 0

            for alias_key, canonical in mapping.items():
                alias = str(alias_key).strip()
                canonical_name = str(canonical).strip()
                if not alias or not canonical_name:
                    continue

                # Ensure canonical team exists
                cur.execute("SELECT id FROM teams WHERE canonical_name = %s", (canonical_name,))
                row = cur.fetchone()
                if not row:
                    if not args.create_missing_teams:
                        skipped_missing_team += 1
                        continue
                    if args.dry_run:
                        created_teams += 1
                        team_id = None
                    else:
                        cur.execute(
                            "INSERT INTO teams (canonical_name) VALUES (%s) RETURNING id",
                            (canonical_name,),
                        )
                        team_id = cur.fetchone()[0]
                        created_teams += 1
                else:
                    team_id = row[0]

                if args.dry_run:
                    inserted += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO team_aliases (team_id, alias, source, confidence)
                    VALUES (%s, %s, %s, 1.0)
                    ON CONFLICT (alias, source) DO UPDATE SET team_id = EXCLUDED.team_id
                    """,
                    (team_id, alias, args.source),
                )
                inserted += 1

            if args.dry_run:
                conn.rollback()
                print("[DRY RUN] No DB changes made.")
            else:
                conn.commit()

        print(f"[OK] Processed {len(mapping):,} alias mappings")
        print(f"     inserted/updated aliases: {inserted:,} (source={args.source})")
        print(f"     missing canonical teams skipped: {skipped_missing_team:,}")
        if args.create_missing_teams:
            print(f"     canonical teams created: {created_teams:,}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

