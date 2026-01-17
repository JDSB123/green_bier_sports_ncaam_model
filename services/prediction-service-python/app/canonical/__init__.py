"""
CANONICAL DATA INGESTION COMPONENTS

Production-ready versions of canonical ingestion components.
These are copied from testing/canonical/ for deployment.
"""

from .quality_gates import DataQualityGate
from .team_resolution_service import get_team_resolver, resolve_team_name

__all__ = [
    'get_team_resolver',
    'resolve_team_name',
    'DataQualityGate'
]
