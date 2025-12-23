import os
from app.odds_api_client import OddsApiClient


def test_env_defaults_mapping(monkeypatch):
    monkeypatch.setenv("SPORT_KEY", "basketball_ncaab")
    monkeypatch.setenv("REGIONS", "us")
    monkeypatch.setenv("ODDS_FORMAT", "american")
    monkeypatch.setenv("MARKETS_FULL", "spreads,totals")
    monkeypatch.setenv("MARKETS_H1", "spreads_h1,totals_h1")
    monkeypatch.setenv("MARKETS_H2", "spreads_h2,totals_h2")
    monkeypatch.setenv("BOOKMAKERS_H1", "bovada,pinnacle,circa,bookmaker")
    monkeypatch.setenv("BOOKMAKERS_H2", "draftkings,fanduel,pinnacle,bovada")

    # Provide a fake API key to avoid placeholder check
    monkeypatch.setenv("THE_ODDS_API_KEY", "abc123-real-key")

    client = OddsApiClient()

    assert client.sport_key == "basketball_ncaab"
    assert client.regions == "us"
    assert client.odds_format == "american"
    assert client.markets_full == "spreads,totals"
    assert client.markets_h1 == "spreads_h1,totals_h1"
    assert client.markets_h2 == "spreads_h2,totals_h2"
    assert client.bookmakers_h1 == "bovada,pinnacle,circa,bookmaker"
    assert client.bookmakers_h2 == "draftkings,fanduel,pinnacle,bovada"

