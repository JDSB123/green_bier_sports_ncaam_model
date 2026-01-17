"""
Pytest configuration and fixtures for NCAAM prediction tests.
"""

import sys
from pathlib import Path

import pytest

# Add the service root to Python path
SERVICE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

from app.models import MarketOdds, TeamRatings


@pytest.fixture
def strong_home_team() -> TeamRatings:
    """A strong home team (top 10 quality)."""
    return TeamRatings(
        team_name="Duke",
        adj_o=118.5,
        adj_d=94.2,
        tempo=69.0,
        rank=8,
        efg=52.5,
        efgd=47.8,
        tor=16.5,
        tord=21.0,
        orb=31.0,
        drb=74.0,
        ftr=35.0,
        ftrd=29.0,
        two_pt_pct=53.0,
        two_pt_pct_d=47.0,
        three_pt_pct=36.0,
        three_pt_pct_d=32.0,
        three_pt_rate=37.0,
        three_pt_rate_d=35.0,
        barthag=0.92,
        wab=7.5,
    )


@pytest.fixture
def mid_away_team() -> TeamRatings:
    """A mid-tier away team (rank 30-50)."""
    return TeamRatings(
        team_name="UNC",
        adj_o=112.0,
        adj_d=100.5,
        tempo=67.5,
        rank=35,
        efg=50.0,
        efgd=50.5,
        tor=18.0,
        tord=19.0,
        orb=28.5,
        drb=71.5,
        ftr=32.0,
        ftrd=32.0,
        two_pt_pct=50.0,
        two_pt_pct_d=50.0,
        three_pt_pct=34.0,
        three_pt_pct_d=34.5,
        three_pt_rate=35.0,
        three_pt_rate_d=36.0,
        barthag=0.78,
        wab=2.0,
    )


@pytest.fixture
def weak_team() -> TeamRatings:
    """A weak team (rank 200+)."""
    return TeamRatings(
        team_name="Weak State",
        adj_o=98.0,
        adj_d=110.5,
        tempo=65.0,
        rank=250,
        efg=46.0,
        efgd=53.0,
        tor=21.0,
        tord=17.0,
        orb=25.0,
        drb=68.0,
        ftr=28.0,
        ftrd=36.0,
        two_pt_pct=46.0,
        two_pt_pct_d=53.0,
        three_pt_pct=31.0,
        three_pt_pct_d=37.0,
        three_pt_rate=33.0,
        three_pt_rate_d=38.0,
        barthag=0.35,
        wab=-8.0,
    )


@pytest.fixture
def equal_teams() -> tuple[TeamRatings, TeamRatings]:
    """Two exactly equal teams for testing HCA isolation."""
    team_a = TeamRatings(
        team_name="Team A",
        adj_o=110.0,
        adj_d=100.0,
        tempo=68.0,
        rank=100,
        efg=50.0,
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
        three_pt_rate=35.0,
        three_pt_rate_d=35.0,
        barthag=0.70,
        wab=0.0,
    )
    team_b = TeamRatings(
        team_name="Team B",
        adj_o=110.0,
        adj_d=100.0,
        tempo=68.0,
        rank=100,
        efg=50.0,
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
        three_pt_rate=35.0,
        three_pt_rate_d=35.0,
        barthag=0.70,
        wab=0.0,
    )
    return team_a, team_b


@pytest.fixture
def sample_market_odds() -> MarketOdds:
    """Sample market odds for testing."""
    return MarketOdds(
        spread=-6.5,
        spread_price=-110,
        total=145.5,
        over_price=-110,
        under_price=-110,
        spread_1h=-3.0,
        total_1h=70.5,
        spread_price_1h=-110,
        over_price_1h=-110,
        under_price_1h=-110,
    )
