#!/usr/bin/env python3
"""
Export Team Registry from PostgreSQL into JSON artifacts.

This supports the plan goal: treat Postgres as authoritative for team identity
and publish a JSON artifact for backtests/CI that may not have DB access.

Outputs:
  - manifests/team_registry.json (detailed export)
  - (optional) Azure Blob backtest_datasets/team_aliases_db.json
    as a derived flat mapping for legacy resolvers.

Notes:
  - The flat mapping is necessarily lossy (DB aliases are source-aware; JSON is not).
    Collisions are detected and recorded in the export.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras

from testing.azure_data_reader import AzureDataReader


ROOT = Path(__file__).resolve().parents[1]


def _utc_now_z() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


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
    """
    Resolve a Postgres connection URL.

    Priority:
      1) DATABASE_URL env var (if present)
      2) docker-compose defaults + ./secrets/db_password.txt
         (host=localhost, port=5450)
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return _normalize_db_url(url)

    sport = os.getenv("SPORT", "ncaam")
    db_user = os.getenv("DB_USER", sport)
    db_name = os.getenv("DB_NAME", sport)

    # When running locally against docker-compose published port:
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


def _table_exists(conn, table: str, schema: str = "public") -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (f"{schema}.{table}",))
        row = cur.fetchone()
        return bool(row and row[0])


def _columns(conn, table: str, schema: str = "public") -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            """,
            (schema, table),
        )
        return {r[0] for r in cur.fetchall()}


def _fetch_dicts(conn, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


@dataclass
class Collision:
    alias_key: str
    chosen_team: str
    rejected_team: str
    chosen_reason: str
    rejected_reason: str


def build_flat_alias_mapping(
    *,
    teams: list[dict],
    aliases: list[dict],
    rated_team_ids: set[str],
) -> tuple[dict[str, str], list[Collision]]:
    """
    Build a flat alias map: normalized_alias -> canonical_name.

    Winner selection for collisions (when the same normalized alias maps to
    different canonical teams in DB):
      1) prefer teams with ratings (rated_team_ids)
      2) prefer higher confidence (team_aliases.confidence)
      3) tie-breaker: canonical_name ascending
    """
    canonical_by_id: dict[str, str] = {
        str(t["id"]): str(t["canonical_name"])
        for t in teams
    }

    mapping: dict[str, str] = {}
    # alias_key -> (team_id, has_ratings, confidence)
    chosen_meta: dict[str, tuple[str, bool, float]] = {}
    collisions: list[Collision] = []

    # Always include canonical self-references (case-insensitive).
    for team_id, canonical in canonical_by_id.items():
        key = canonical.lower().strip()
        mapping[key] = canonical
        chosen_meta[key] = (team_id, team_id in rated_team_ids, 1.0)

    for row in aliases:
        alias = (row.get("alias") or "").strip()
        team_id = str(row.get("team_id"))
        canonical = canonical_by_id.get(team_id)
        if not alias or not canonical:
            continue
        alias_key = alias.lower().strip()
        confidence = float(row.get("confidence") or 1.0)
        has_ratings = team_id in rated_team_ids

        if alias_key not in mapping:
            mapping[alias_key] = canonical
            chosen_meta[alias_key] = (team_id, has_ratings, confidence)
            continue

        existing_team_id, existing_has_ratings, existing_conf = chosen_meta.get(
            alias_key,
            ("", False, 0.0),
        )
        existing_canonical = mapping[alias_key]
        if existing_canonical == canonical:
            # Same mapping, OK.
            # Still keep the \"best\" metadata so future compares are consistent.
            if has_ratings and not existing_has_ratings:
                chosen_meta[alias_key] = (team_id, has_ratings, confidence)
            elif (has_ratings == existing_has_ratings) and (confidence > existing_conf):
                chosen_meta[alias_key] = (team_id, has_ratings, confidence)
            continue

        # Collision: choose winner deterministically.
        def _rank(has_r: bool, conf: float, name: str) -> tuple[int, float, str]:
            return (1 if has_r else 0, float(conf), str(name))

        existing_rank = _rank(
            existing_has_ratings,
            existing_conf,
            existing_canonical,
        )
        incoming_rank = _rank(has_ratings, confidence, canonical)

        if incoming_rank > existing_rank:
            collisions.append(
                Collision(
                    alias_key=alias_key,
                    chosen_team=canonical,
                    rejected_team=existing_canonical,
                    chosen_reason=(
                        f"has_ratings={has_ratings}, confidence={confidence}"
                    ),
                    rejected_reason=(
                        f"has_ratings={existing_has_ratings}, "
                        f"confidence={existing_conf}"
                    ),
                )
            )
            mapping[alias_key] = canonical
            chosen_meta[alias_key] = (team_id, has_ratings, confidence)
        else:
            collisions.append(
                Collision(
                    alias_key=alias_key,
                    chosen_team=existing_canonical,
                    rejected_team=canonical,
                    chosen_reason=(
                        f"has_ratings={existing_has_ratings}, "
                        f"confidence={existing_conf}"
                    ),
                    rejected_reason=(
                        f"has_ratings={has_ratings}, confidence={confidence}"
                    ),
                )
            )

    return mapping, collisions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export Postgres Team Registry to JSON"
    )
    parser.add_argument(
        "--db-url",
        default="",
        help=(
            "Optional Postgres URL. If omitted, uses DATABASE_URL or "
            "docker-compose defaults."
        ),
    )
    parser.add_argument(
        "--output-registry",
        type=Path,
        default=ROOT / "manifests" / "team_registry.json",
        help="Output path for the detailed registry export JSON.",
    )
    parser.add_argument(
        "--azure-container",
        default=os.getenv("AZURE_CANONICAL_CONTAINER", "ncaam-historical-data"),
        help="Azure container name for aliases output.",
    )
    parser.add_argument(
        "--aliases-blob",
        default="backtest_datasets/team_aliases_db.json",
        help="Azure blob path for the derived flat alias map JSON.",
    )
    parser.add_argument(
        "--write-aliases",
        action="store_true",
        help="Write the derived flat alias mapping to --output-aliases.",
    )
    args = parser.parse_args()

    db_url = _normalize_db_url(args.db_url) if args.db_url else get_database_url()

    out_registry = args.output_registry
    if not out_registry.is_absolute():
        out_registry = (ROOT / out_registry).resolve()
    out_registry.parent.mkdir(parents=True, exist_ok=True)

    conn = psycopg2.connect(db_url)
    try:
        # Teams
        team_cols = _columns(conn, "teams")
        desired_team_cols = [
            "id",
            "canonical_name",
            "barttorvik_name",
            "conference",
            "division",
            "ncaa_id",
            "espn_id",
            "sports_ref_id",
            "city",
            "state",
            "created_at",
            "updated_at",
        ]
        team_select = [c for c in desired_team_cols if c in team_cols]
        teams = _fetch_dicts(
            conn,
            f"SELECT {', '.join(team_select)} FROM teams ORDER BY canonical_name",
        )

        # Aliases
        alias_cols = _columns(conn, "team_aliases")
        desired_alias_cols = [
            "id",
            "team_id",
            "alias",
            "source",
            "confidence",
            "created_at",
        ]
        alias_select = [c for c in desired_alias_cols if c in alias_cols]
        aliases = _fetch_dicts(
            conn,
            f"SELECT {', '.join(alias_select)} FROM team_aliases ORDER BY source, alias",
        )

        # Rated teams (for deterministic collision resolution)
        rated_team_ids: set[str] = set()
        if _table_exists(conn, "team_ratings"):
            rows = _fetch_dicts(
                conn,
                "SELECT DISTINCT team_id::text AS team_id FROM team_ratings",
            )
            rated_team_ids = {str(r["team_id"]) for r in rows if r.get("team_id")}

        # team_source_ids (optional)
        team_source_ids: list[dict] = []
        if _table_exists(conn, "team_source_ids"):
            tsi_cols = _columns(conn, "team_source_ids")
            desired_tsi_cols = [
                "id",
                "team_id",
                "source",
                "external_team_id",
                "first_season",
                "last_season",
                "metadata",
                "created_at",
                "updated_at",
            ]
            tsi_select = [c for c in desired_tsi_cols if c in tsi_cols]
            team_source_ids = _fetch_dicts(
                conn,
                f"SELECT {', '.join(tsi_select)} FROM team_source_ids ORDER BY source, external_team_id",
            )

        # Derived alias mapping
        flat_aliases, collisions = build_flat_alias_mapping(
            teams=teams,
            aliases=aliases,
            rated_team_ids=rated_team_ids,
        )

        registry_payload = {
            "generated_at": _utc_now_z(),
            "tables": {
                "teams": len(teams),
                "team_aliases": len(aliases),
                "team_ratings_distinct_teams": len(rated_team_ids),
                "team_source_ids": len(team_source_ids),
            },
            "teams": teams,
            "aliases": aliases,
            "team_source_ids": team_source_ids,
            "derived": {
                "flat_aliases_count": len(flat_aliases),
                "collisions_count": len(collisions),
                "collisions_sample": [c.__dict__ for c in collisions[:50]],
            },
        }

        out_registry.write_text(
            json.dumps(registry_payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        print(f"[OK] Wrote registry export: {out_registry}")

        if args.write_aliases:
            tag_timestamp = _utc_now_z().replace("-", "").replace(":", "")
            tags = {
                "kind": "team_aliases",
                "source": "team_registry_export",
                "updated_utc": tag_timestamp,
                "alias_count": str(len(flat_aliases)),
            }
            reader = AzureDataReader(container_name=args.azure_container)
            reader.write_json(
                args.aliases_blob,
                flat_aliases,
                indent=2,
                sort_keys=True,
                tags=tags,
            )
            print(f"[OK] Wrote derived aliases map to Azure: {args.aliases_blob}")

        # Always report collisions loudly (does not fail by default).
        if collisions:
            print(
                "[WARN] Alias collisions detected (source-aware DB aliases -> "
                f"flat JSON projection): {len(collisions)}"
            )
            print(
                "       Review manifests/team_registry.json -> "
                "derived.collisions_sample for examples."
            )
        else:
            print("[OK] No alias collisions detected in flat projection.")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

