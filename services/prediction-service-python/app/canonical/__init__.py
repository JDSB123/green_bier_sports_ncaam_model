"""
CANONICAL DATA INGESTION COMPONENTS

Production-ready versions of canonical ingestion components.
These are copied from testing/canonical/ for deployment.
"""

from .team_resolution_service import get_team_resolver, resolve_team_name
from .quality_gates import DataQualityGate

__all__ = [
    'get_team_resolver',
    'resolve_team_name',
    'DataQualityGate'
]