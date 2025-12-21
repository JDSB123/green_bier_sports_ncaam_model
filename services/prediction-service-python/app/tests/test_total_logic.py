import pytest

from app.models import TeamRatings
from app.predictor import BarttorkvikPredictor


def _make_team(
    name: str,
    adj_o: float,
    adj_d: float,
    tempo: float,
    rank: int = 100,
) -> TeamRatings:
    """
    Create a TeamRatings object with neutral "league average" four-factor values so
    matchup adjustments are ~0 and the total math is easy to validate.
    """
    return TeamRatings(
        team_name=name,
        adj_o=adj_o,
        adj_d=adj_d,
        tempo=tempo,
        rank=rank,
        # Four Factors: use neutral values so matchup_adj ~ 0
        efg=50.0,
        efgd=50.0,
        tor=18.5,
        tord=18.5,
        orb=28.0,
        drb=72.0,  # 100 - 72 = 28 ORB allowed (league avg)
        ftr=33.0,
        ftrd=33.0,
        # Shooting breakdown (arbitrary but plausible)
        two_pt_pct=50.0,
        two_pt_pct_d=50.0,
        three_pt_pct=35.0,
        three_pt_pct_d=35.0,
        three_pt_rate=30.0,
        three_pt_rate_d=30.0,
        # Quality metrics
        barthag=0.80,
        wab=0.0,
    )


def _configure_for_determinism(p: BarttorkvikPredictor) -> None:
    """
    Make the predictor deterministic for math tests:
    - Fix league averages used in the formulas
    - Fix HCA totals
    - Disable dynamic 1H factors so tempo_factor is the base constant
    - Ensure matchup adjustment averages match our neutral team values
    """
    # Formula constants
    p.config.league_avg_tempo = 68.5
    p.config.league_avg_efficiency = 106.0

    # Matchup adjustment league avgs (must match _make_team)
    p.config.league_avg_orb = 28.0
    p.config.league_avg_tor = 18.5
    p.config.league_avg_ftr = 33.0

    # HCA knobs
    p.hca_total = 0.9
    p.hca_total_1h = 0.0

    # Disable dynamic 1H so tempo_factor is stable
    p.first_half_calc.enabled = False
    p.first_half_calc.base_tempo_factor = 0.48
    p.first_half_calc.base_margin_scale = 0.50
    p.first_half_calc.base_confidence_scale = 0.90


def _expected_full_game_total(home: TeamRatings, away: TeamRatings, *, hca_total: float) -> float:
    avg_tempo = home.tempo + away.tempo - 68.5
    home_eff = home.adj_o + away.adj_d - 106.0
    away_eff = away.adj_o + home.adj_d - 106.0
    home_score_base = home_eff * avg_tempo / 100.0
    away_score_base = away_eff * avg_tempo / 100.0
    total = home_score_base + away_score_base + hca_total
    return round(total, 1)


def _expected_first_half_total(home: TeamRatings, away: TeamRatings, *, tempo_factor: float, hca_total_1h: float) -> float:
    avg_tempo = home.tempo + away.tempo - 68.5
    home_eff = home.adj_o + away.adj_d - 106.0
    away_eff = away.adj_o + home.adj_d - 106.0
    home_score_base = home_eff * avg_tempo / 100.0
    away_score_base = away_eff * avg_tempo / 100.0
    total_1h = (home_score_base + away_score_base) * tempo_factor + hca_total_1h
    return round(total_1h, 1)


def test_total_full_game_and_first_half_math_matches_expected() -> None:
    """
    Validate that:
    - full game total matches the v6.3 formula (with controlled constants)
    - 1H total matches (base scores * tempo_factor) + HCA_1h
    - returned score components are internally consistent with totals
    """
    home = _make_team("Home", adj_o=110.0, adj_d=100.0, tempo=70.0, rank=10)
    away = _make_team("Away", adj_o=105.0, adj_d=105.0, tempo=68.0, rank=100)

    p = BarttorkvikPredictor()
    _configure_for_determinism(p)

    out = p.predict(home, away, is_neutral=False)

    assert out.total == _expected_full_game_total(home, away, hca_total=0.9)
    assert out.total_1h == _expected_first_half_total(home, away, tempo_factor=0.48, hca_total_1h=0.0)

    # Internal consistency (allow tiny rounding noise from 0.1 rounding)
    assert (out.home_score + out.away_score) == pytest.approx(out.total, abs=0.2)
    assert (out.home_score_1h + out.away_score_1h) == pytest.approx(out.total_1h, abs=0.2)


def test_total_hca_removed_on_neutral_site_full_game() -> None:
    """
    Neutral site should remove full-game total HCA (and not break totals).
    """
    home = _make_team("Home", adj_o=110.0, adj_d=100.0, tempo=70.0, rank=10)
    away = _make_team("Away", adj_o=105.0, adj_d=105.0, tempo=68.0, rank=100)

    p = BarttorkvikPredictor()
    _configure_for_determinism(p)

    out_home = p.predict(home, away, is_neutral=False)
    out_neutral = p.predict(home, away, is_neutral=True)

    assert out_home.total == _expected_full_game_total(home, away, hca_total=0.9)
    assert out_neutral.total == _expected_full_game_total(home, away, hca_total=0.0)
    assert (out_home.total - out_neutral.total) == pytest.approx(0.9, abs=0.2)


