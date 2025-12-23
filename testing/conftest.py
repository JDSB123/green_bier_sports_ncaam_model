"""
Test configuration for repo-level tests in `testing/`.

These tests use the prediction engine code located at:
  services/prediction-service-python/app

When running pytest from the repo root, that package isn't on PYTHONPATH by
default, so we add the prediction-service directory to sys.path to allow:
  from app.predictor import prediction_engine
"""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

import pytest

# Ensure the prediction-service package root is importable for all tests in this
# directory, before any test modules import `app.*`.
repo_root = Path(__file__).resolve().parents[1]
prediction_service_root = repo_root / "services" / "prediction-service-python"
if prediction_service_root.exists():
    sys.path.insert(0, str(prediction_service_root))

# Avoid static `from app.models import ...` imports so type checkers that don't
# understand our dynamic sys.path tweak won't flag missing imports.
TeamRatings = import_module("app.models").TeamRatings  # type: ignore[attr-defined]

@pytest.fixture
def make_team_ratings():
    """
    Factory for minimal-but-valid `TeamRatings` instances.

    v6.3 requires all fields (no defaults), so tests should always construct a
    complete object.
    """

    def _make(team_name: str = "Team"):
        return TeamRatings(
            team_name=team_name,
            adj_o=110.0,
            adj_d=100.0,
            tempo=68.5,
            rank=50,
            efg=52.0,
            efgd=50.0,
            tor=18.0,
            tord=18.0,
            orb=28.0,
            drb=72.0,
            ftr=33.0,
            ftrd=33.0,
            two_pt_pct=50.0,
            two_pt_pct_d=50.0,
            three_pt_pct=35.0,
            three_pt_pct_d=35.0,
            three_pt_rate=40.0,
            three_pt_rate_d=40.0,
            barthag=0.85,
            wab=1.0,
        )

    return _make


