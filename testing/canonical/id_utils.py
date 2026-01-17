"""
Canonical ID utilities for backtests/CI.

Plan alignment:
  - Canonical key for teams: UUID
  - Canonical key for games: (game_date, home_team_id, away_team_id)

In production, Postgres `teams.id` is authoritative.
For backtests/CI (where DB may be unavailable), we support:
  - Loading a DB-exported registry JSON (preferred), OR
  - Deterministic UUIDv5 fallback derived from canonical_name (stable).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Stable namespaces (deterministic across environments)
TEAM_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "gbsv.ncaam.team_id.v1")
GAME_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "gbsv.ncaam.game_id.v1")


def _norm_name(name: str) -> str:
    return (name or "").strip().lower()


@dataclass(frozen=True)
class TeamRegistry:
    """
    Minimal mapping: canonical_name -> team_id (UUID string).

    If a registry file is present, use it. Otherwise fall back to deterministic
    IDs.
    """

    canonical_to_id: dict[str, str]
    source: str  # "registry_json" or "uuid5_fallback"

    def team_id(self, canonical_name: str) -> str:
        key = _norm_name(canonical_name)
        if not key:
            raise ValueError("Empty canonical_name")
        if key in self.canonical_to_id:
            return self.canonical_to_id[key]
        # Fallback (stable)
        return str(uuid.uuid5(TEAM_ID_NAMESPACE, key))


def load_team_registry(registry_path: Path | None = None) -> TeamRegistry:
    """
    Preferred input: `manifests/team_registry.json` created by
    scripts/export_team_registry.py (contains teams[].id + teams[].canonical_name).
    """
    if registry_path is None:
        env_path = os.getenv("TEAM_REGISTRY_PATH", "").strip()
        if env_path:
            registry_path = Path(env_path)
        else:
            registry_path = ROOT / "manifests" / "team_registry.json"

    try:
        if registry_path.exists():
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            teams = data.get("teams") if isinstance(data, dict) else None
            if isinstance(teams, list):
                mapping: dict[str, str] = {}
                for t in teams:
                    if not isinstance(t, dict):
                        continue
                    cid = t.get("id")
                    name = t.get("canonical_name")
                    if cid and name:
                        mapping[_norm_name(str(name))] = str(cid)
                if mapping:
                    return TeamRegistry(
                        canonical_to_id=mapping,
                        source="registry_json",
                    )
    except Exception:
        pass

    return TeamRegistry(canonical_to_id={}, source="uuid5_fallback")


def canonical_game_id(
    game_date_iso: str,
    home_team_id: str,
    away_team_id: str,
) -> str:
    """
    Deterministic UUIDv5 for a game based on the canonical key tuple.
    """
    key = f"{game_date_iso}|{home_team_id}|{away_team_id}"
    return str(uuid.uuid5(GAME_ID_NAMESPACE, key))
