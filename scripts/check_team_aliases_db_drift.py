#!/usr/bin/env python3
"""
Drift gate: verify the flat aliases JSON matches the Postgres Team Registry.

Source of truth: Postgres (teams + team_aliases [+ team_ratings preference]).
Artifact: Azure Blob `backtest_datasets/team_aliases_db.json`

Exit codes:
  0 - no drift
  1 - drift detected (file is stale or inconsistent)
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

try:
    from azure.storage.blob import BlobServiceClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False


ROOT = Path(__file__).resolve().parents[1]


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_db_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("postgresql+psycopg2://"):
        u = "postgresql://" + u[len("postgresql+psycopg2://") :]
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://") :]
    return u


def _read_secret(path: Path) -> Optional[str]:
    try:
        s = path.read_text(encoding="utf-8").strip()
        return s or None
    except Exception:
        return None


def _load_aliases_from_azure(container: str, blob_path: str) -> Dict[str, str]:
    if not AZURE_AVAILABLE:
        raise ImportError("azure-storage-blob is required to load aliases from Azure.")

    conn_str = os.getenv("AZURE_CANONICAL_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError(
            "AZURE_CANONICAL_CONNECTION_STRING is required to load aliases from Azure."
        )

    service = BlobServiceClient.from_connection_string(conn_str)
    container_client = service.get_container_client(container)
    blob_client = container_client.get_blob_client(blob_path)
    payload = blob_client.download_blob().readall()
    return json.loads(payload.decode("utf-8"))


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return _normalize_db_url(url)

    sport = os.getenv("SPORT", "ncaam")
    db_user = os.getenv("DB_USER", sport)
    db_name = os.getenv("DB_NAME", sport)

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT") or os.getenv("POSTGRES_HOST_PORT") or "5450"

    pw = os.getenv("DB_PASSWORD", "").strip() or _read_secret(ROOT / "secrets" / "db_password.txt")
    if not pw:
        raise RuntimeError(
            "Database password not found. Set DATABASE_URL, or set DB_PASSWORD, "
            "or create secrets/db_password.txt to match docker-compose."
        )

    return f"postgresql://{db_user}:{pw}@{host}:{port}/{db_name}"


def _table_exists(conn, table: str, schema: str = "public") -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (f"{schema}.{table}",))
        row = cur.fetchone()
        return bool(row and row[0])


def _fetch_dicts(conn, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def _build_flat_aliases(conn) -> Dict[str, str]:
    """
    Build a deterministic flat mapping from DB aliases to canonical names.

    Collision resolution is consistent with export_team_registry.py:
      ratings > confidence > canonical_name
    """
    teams = _fetch_dicts(conn, "SELECT id::text AS id, canonical_name FROM teams")
    canonical_by_id = {t["id"]: t["canonical_name"] for t in teams}

    rated_team_ids: set[str] = set()
    if _table_exists(conn, "team_ratings"):
        rows = _fetch_dicts(conn, "SELECT DISTINCT team_id::text AS team_id FROM team_ratings")
        rated_team_ids = {r["team_id"] for r in rows if r.get("team_id")}

    aliases = _fetch_dicts(conn, "SELECT team_id::text AS team_id, alias, source, confidence FROM team_aliases")

    # canonical self-references
    mapping: Dict[str, str] = {c.lower().strip(): c for c in canonical_by_id.values()}
    chosen: Dict[str, tuple[str, bool, float, str]] = {}  # key -> (team_id, has_ratings, confidence, canonical)
    for tid, canonical in canonical_by_id.items():
        chosen[canonical.lower().strip()] = (tid, tid in rated_team_ids, 1.0, canonical)

    for row in aliases:
        alias = (row.get("alias") or "").strip()
        tid = row.get("team_id")
        canonical = canonical_by_id.get(tid)
        if not alias or not tid or not canonical:
            continue
        key = alias.lower().strip()
        conf = float(row.get("confidence") or 1.0)
        has_r = tid in rated_team_ids

        if key not in mapping:
            mapping[key] = canonical
            chosen[key] = (tid, has_r, conf, canonical)
            continue

        existing_tid, existing_has_r, existing_conf, existing_canonical = chosen.get(key, ("", False, 0.0, mapping[key]))
        if existing_canonical == canonical:
            # Keep best metadata
            if has_r and not existing_has_r:
                chosen[key] = (tid, has_r, conf, canonical)
            elif (has_r == existing_has_r) and (conf > existing_conf):
                chosen[key] = (tid, has_r, conf, canonical)
            continue

        # Compare ranks
        existing_rank = (1 if existing_has_r else 0, existing_conf, str(existing_canonical))
        incoming_rank = (1 if has_r else 0, conf, str(canonical))
        if incoming_rank > existing_rank:
            mapping[key] = canonical
            chosen[key] = (tid, has_r, conf, canonical)

    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="Check drift between DB and team_aliases_db.json")
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
    parser.add_argument("--max-diffs", type=int, default=50, help="Max diffs to print")
    args = parser.parse_args()

    db_url = _normalize_db_url(args.db_url) if args.db_url else get_database_url()
    conn = psycopg2.connect(db_url)
    try:
        db_map = _build_flat_aliases(conn)
    finally:
        conn.close()

    file_map = _load_aliases_from_azure(args.azure_container, args.aliases_blob)
    if not isinstance(file_map, dict):
        print("[FAIL] aliases file is not a JSON object")
        return 1

    # Normalize file keys to match our projection semantics (lowercase).
    file_map_norm: Dict[str, str] = {str(k).lower().strip(): str(v) for k, v in file_map.items()}

    only_in_db = sorted(set(db_map.keys()) - set(file_map_norm.keys()))
    only_in_file = sorted(set(file_map_norm.keys()) - set(db_map.keys()))
    mismatched = sorted(k for k in (set(db_map.keys()) & set(file_map_norm.keys())) if db_map[k] != file_map_norm[k])

    if not only_in_db and not only_in_file and not mismatched:
        print(f"[OK] No drift detected at {_utc_now_z()}")
        print(f"     DB aliases: {len(db_map):,} | file aliases: {len(file_map_norm):,}")
        return 0

    print(f"[FAIL] Drift detected at {_utc_now_z()}")
    print(f"       DB aliases: {len(db_map):,} | file aliases: {len(file_map_norm):,}")
    print(f"       only_in_db: {len(only_in_db):,} | only_in_file: {len(only_in_file):,} | mismatched: {len(mismatched):,}")

    max_diffs = int(args.max_diffs)

    def _print_list(label: str, items: List[str]):
        if not items:
            return
        print(f"\n{label} (showing up to {max_diffs}):")
        for k in items[:max_diffs]:
            if label == "mismatched":
                print(f"  - {k!r}: db={db_map.get(k)!r} file={file_map_norm.get(k)!r}")
            else:
                print(f"  - {k!r}")
    _print_list("only_in_db", only_in_db)
    _print_list("only_in_file", only_in_file)
    _print_list("mismatched", mismatched)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

