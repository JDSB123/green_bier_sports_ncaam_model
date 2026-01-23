from __future__ import annotations

from datetime import UTC, datetime

from app.validation_gate import PrePredictionGate, TeamResolver


def test_naive_time_assumed_cst(monkeypatch):
    resolver = TeamResolver(
        aliases={
            "duke": "Duke",
            "unc": "UNC",
        }
    )
    gate = PrePredictionGate(team_resolver=resolver)
    game = {
        "home_team": "Duke",
        "away_team": "UNC",
        "game_time": "2026-01-09T17:30:00",  # naive
    }

    result = gate.validate_game(game)

    assert result.is_valid
    assert "game_time_cst" in result.resolved_data
    cst_dt = result.resolved_data["game_time_cst"]
    assert cst_dt.tzinfo and cst_dt.tzinfo.key == "America/Chicago"
    assert any("assumed CST" in w.message for w in result.warnings)


def test_aggressive_resolution_blocked_in_prod(monkeypatch):
    # Force aggressive resolution to be blocked
    monkeypatch.setenv("DISABLE_AGGRESSIVE_TEAM_RESOLUTION", "true")
    monkeypatch.delenv("ALLOW_AGGRESSIVE_TEAM_RESOLUTION", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    resolver = TeamResolver(
        aliases={
            "duke": "Duke",
            "illinois state": "Illinois State",
        }
    )
    gate = PrePredictionGate(team_resolver=resolver)
    game = {
        "home_team": "Illinois State Redbirds",  # requires aggressive strip
        "away_team": "Duke",
        "game_time": datetime.now(UTC).isoformat(),
    }

    result = gate.validate_game(game)

    assert not result.is_valid
    errors = [e for e in result.errors if e.field == "home_team"]
    assert errors, "Aggressive resolution should be blocked without override"
    assert "Aggressive resolution" in errors[0].message
