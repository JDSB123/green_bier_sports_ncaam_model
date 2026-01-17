"""NCAA Basketball Prediction Service - dynamic version loader."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

# Configure structured logging on import
from .logging_config import configure_logging

# Configure logging based on environment
_log_level = os.getenv("LOG_LEVEL", "INFO")
_json_logs = os.getenv("JSON_LOGS", "true").lower() == "true"
_service_name = os.getenv("SERVICE_NAME", "prediction-service")

configure_logging(
    log_level=_log_level,
    json_logs=_json_logs,
    service_name=_service_name,
)


def _candidate_version_paths(start: Path) -> Iterable[Path]:
    """Yield possible VERSION file locations from closest to farthest."""
    # 1) Custom override via environment variable
    env_override = os.getenv("NCAAM_VERSION_FILE")
    if env_override:
        yield Path(env_override)

    # 2) VERSION file next to this module or up the tree
    for parent in [start.parent, start.parent.parent, *start.parents]:
        yield parent / "VERSION"

    # 3) Current working directory fallback
    yield Path.cwd() / "VERSION"


def _load_version() -> str:
    module_path = Path(__file__).resolve()
    for version_path in _candidate_version_paths(module_path):
        try:
            if version_path.is_file():
                value = version_path.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except OSError:
            continue
    return "0.0.0"


__version__ = _load_version()
