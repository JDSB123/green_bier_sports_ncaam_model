#!/usr/bin/env python3
"""
Generate Tonight's Picks - Paper Mode Only

Generates predictions for tonight's NCAAM slate using profitable models:
- FG Spread (+3.82% ROI historically)
- H1 Spread (+1.54% ROI historically)

Paper mode: No real money. Outputs predictions to CSV for review.

GOVERNANCE - TEAM NAME RESOLUTION:
    ALWAYS use testing.canonical.barttorvik_team_mappings for team resolution.
    This module contains the authoritative mappings from Postgres team_aliases
    table (95%+ coverage, 600+ aliases). DO NOT create ad-hoc mappings or
    use fuzzy matching - all team name resolution must go through the canonical gate.

Usage:
    python generate_tonight_picks.py
    python generate_tonight_picks.py --market fg_spread
    python generate_tonight_picks.py --live  # To pull real games from Odds API
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytz

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from testing.azure_data_reader import get_azure_reader
from testing.canonical.barttorvik_team_mappings import resolve_odds_api_to_barttorvik
from testing.scripts.run_historical_backtest import (
    BacktestConfig,
    MarketType,
    _add_derived_features,
)

RESULTS_DIR = ROOT_DIR / "testing" / "results" / "predictions"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Markets that are historically profitable
PROFITABLE_MARKETS = [MarketType.FG_SPREAD, MarketType.H1_SPREAD]

@dataclass
class TonightPick:
    """A single pick for tonight."""
    game_date: str
    game_time: str
    home_team: str
    away_team: str
    market: str
    predicted_line: float
    market_line: float
    edge: float
    bet_side: str
    edge_pct: float
    confidence: str  # HIGH, MEDIUM, LOW
    paper_mode: bool = True


def _read_secret_file(path: str) -> str | None:
    try:
        value = Path(path).read_text(encoding="utf-8").strip()
        return value if value else None
    except Exception:
        return None


def _get_odds_api_key() -> str | None:
    """Best-effort Odds API key retrieval across local/dev/prod patterns."""
    env_key = os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")
    if env_key:
        return env_key.strip()

    file_path = os.getenv("THE_ODDS_API_KEY_FILE") or "/run/secrets/odds_api_key"
    file_key = _read_secret_file(file_path)
    if file_key:
        return file_key

    local_key = _read_secret_file(str(ROOT_DIR / "secrets" / "odds_api_key.txt"))
    if local_key:
        return local_key

    return None


def _determine_current_season(today: datetime | None = None) -> int:
    """Return the NCAAM season year used by Barttorvik (e.g., Jan 2026 -> 2026)."""
    dt = today or datetime.now()
    return dt.year if dt.month <= 6 else dt.year + 1


def _safe_canonicalize_team(name: str | None, source: str) -> str | None:
    if not name:
        return name
    try:
        from testing.scripts.team_utils import resolve_team_name

        return resolve_team_name(name, source=source)
    except Exception:
        return str(name).strip()


def _extract_spread_from_bookmakers(
    bookmakers: list[dict] | None,
    market_key: str,
    home_team: str,
    away_team: str,
) -> tuple[float | None, float | None, float | None]:
    """Return (home_point, home_price, away_price) for a spreads-like market."""
    if not bookmakers:
        return None, None, None

    preferred = [
        "draftkings",
        "fanduel",
        "betmgm",
        "caesars",
        "pointsbetus",
        "betrivers",
    ]
    ordered = sorted(
        bookmakers,
        key=lambda b: (0 if b.get("key") in preferred else 1),
    )

    for book in ordered:
        markets = book.get("markets") or []
        for m in markets:
            if m.get("key") != market_key:
                continue
            outcomes = m.get("outcomes") or []
            home = next((o for o in outcomes if o.get("name") == home_team), None)
            away = next((o for o in outcomes if o.get("name") == away_team), None)
            if not home or not away:
                continue

            point = home.get("point")
            if point is None:
                continue
            try:
                home_point = float(point)
            except Exception:
                continue

            def _as_float(v):
                try:
                    return float(v)
                except Exception:
                    return None

            return home_point, _as_float(home.get("price")), _as_float(away.get("price"))

    return None, None, None


def _fetch_live_games_with_odds() -> pd.DataFrame:
    """Fetch upcoming games + spread lines from The Odds API (live mode)."""
    import requests

    api_key = _get_odds_api_key()
    if not api_key:
        print(
            "[WARN] Odds API key not found; can't fetch live games. "
            "Set THE_ODDS_API_KEY/ODDS_API_KEY or provide /run/secrets/odds_api_key (Compose)."
        )
        return pd.DataFrame()

    url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        # We need spreads + (if available) 1H spreads.
        "markets": "spreads,spreads_1st_half",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }

    resp = requests.get(url, params=params, timeout=20)
    if resp.status_code == 422 and "spreads_1st_half" in str(params.get("markets")):
        # Some Odds API plans/sports don't expose 1H spreads; fall back to full-game spreads.
        params["markets"] = "spreads"
        resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    games = resp.json() or []
    if not games:
        print("[INFO] No upcoming games found from Odds API")
        return pd.DataFrame()

    rows: list[dict] = []
    for g in games:
        home_team = _safe_canonicalize_team(g.get("home_team"), source="the_odds_api")
        away_team = _safe_canonicalize_team(g.get("away_team"), source="the_odds_api")
        if not home_team or not away_team:
            continue

        fg_spread, fg_home_price, fg_away_price = _extract_spread_from_bookmakers(
            g.get("bookmakers"), "spreads", home_team, away_team
        )
        h1_spread, h1_home_price, h1_away_price = _extract_spread_from_bookmakers(
            g.get("bookmakers"), "spreads_1st_half", home_team, away_team
        )

        rows.append(
            {
                "game_id": g.get("id"),
                "commence_time": g.get("commence_time"),
                "game_date": (
                    (lambda ts: ts.date() if not pd.isna(ts) else None)(
                        pd.to_datetime(g.get("commence_time"), errors="coerce")
                    )
                    if g.get("commence_time")
                    else None
                ),
                "home_team": home_team,
                "away_team": away_team,
                "neutral": False,
                "fg_spread": fg_spread,
                "fg_spread_home_price": fg_home_price,
                "fg_spread_away_price": fg_away_price,
                "h1_spread": h1_spread,
                "h1_spread_home_price": h1_home_price,
                "h1_spread_away_price": h1_away_price,
            }
        )

    return pd.DataFrame(rows)


def _load_barttorvik_ratings_live(season: int) -> dict[str, dict]:
    """Fetch Barttorvik season ratings directly from the public endpoint (no Azure)."""
    import requests

    url = f"https://barttorvik.com/{season}_team_results.json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    ratings: dict[str, dict] = {}
    if isinstance(payload, list):
        for row in payload:
            if not isinstance(row, list) or len(row) < 9:
                continue
            # Use Barttorvik's raw team name (already in canonical short form)
            # e.g., "tulane", "north texas", "george washington"
            name = str(row[1]).strip()
            if not name:
                continue

            def _num(idx: int) -> float | None:
                if idx >= len(row):
                    return None
                try:
                    return float(row[idx])
                except Exception:
                    return None

            adj_o = _num(4)
            adj_d = _num(6)
            barthag = _num(8)
            if barthag is None and adj_o is not None and adj_d is not None:
                # Fallback approximation.
                exp = 11.5
                try:
                    barthag = (adj_o**exp) / ((adj_o**exp) + (adj_d**exp))
                except Exception:
                    barthag = None

            # Best-effort mapping for additional fields used by derived features.
            # Some fields are percentages on the 0-100 scale in the JSON.
            tor_pct = _num(12)
            orb_pct = _num(10)
            tempo = _num(44)
            wab = _num(11)
            rank = _num(0)

            ratings[name.lower()] = {
                "adj_o": adj_o,
                "adj_d": adj_d,
                "barthag": barthag,
                "tempo": tempo,
                "wab": wab,
                "rank": rank,
                "tor": (tor_pct / 100.0) if tor_pct is not None and tor_pct > 1.0 else tor_pct,
                "orb": (orb_pct / 100.0) if orb_pct is not None and orb_pct > 1.0 else orb_pct,
            }
    return ratings


def load_games_for_tonight(live: bool = False) -> pd.DataFrame:
    """
    Load games for tonight.

    If live=True, fetch from Odds API (requires API key).
    If live=False, use tomorrow's date from canonical master as a simulation.
    """
    if live:
        try:
            return _fetch_live_games_with_odds()
        except Exception as e:
            print(f"[ERROR] Failed to fetch live games/odds: {e}")
            return pd.DataFrame()

    else:
        # For demo: use tomorrow's date
        print("[INFO] Live mode off; using canonical master for demo purposes")
        local_master = ROOT_DIR / "manifests" / "canonical_training_data_master.csv"
        if local_master.exists():
            df = pd.read_csv(local_master)
        else:
            try:
                reader = get_azure_reader()
                df = reader.read_csv("manifests/canonical_training_data_master.csv")
            except Exception as exc:
                print(
                    "[ERROR] Can't load canonical master (local file missing and Azure unavailable). "
                    "Set AZURE_CANONICAL_CONNECTION_STRING (or AZURE_CANONICAL_CONNECTION_STRING_FILE) "
                    "or sync manifests/canonical_training_data_master.csv locally."
                )
                return pd.DataFrame()

        # Get tomorrow's date
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")

        # Filter for near-future games (within next 7 days) for demo
        future_games = df[df["game_date"] >= pd.Timestamp(tomorrow)]

        if future_games.empty:
            print("[INFO] No games in the near future; using most recent games for demo")
            # Use most recent games instead
            future_games = df.nlargest(10, "game_date")

        return future_games.head(5).copy()


def add_ratings_to_games(df: pd.DataFrame) -> pd.DataFrame:
    """Populate ratings for tonight's games.

    - If the canonical master exists locally, use it (stable/reproducible).
    - Otherwise, for live mode, fetch Barttorvik ratings directly (no Azure).
    - As a last resort, fall back to Azure.
    """
    # Normalize team names in input
    result = df.copy()
    if "home_team" in result.columns:
        result["home_team"] = result["home_team"].astype(str).str.strip()
        result["away_team"] = result["away_team"].astype(str).str.strip()
    elif "home_abbr" in result.columns:
        result["home_team"] = result["home_abbr"].astype(str).str.strip()
        result["away_team"] = result["away_abbr"].astype(str).str.strip()
    else:
        print("[WARN] No home/away team columns found")
        return result

    local_master = ROOT_DIR / "manifests" / "canonical_training_data_master.csv"
    if local_master.exists():
        master = pd.read_csv(local_master)

        if "home_canonical" in master.columns:
            master["home_team"] = master["home_canonical"].astype(str).str.strip()
            master["away_team"] = master["away_canonical"].astype(str).str.strip()
        elif "home_team" in master.columns:
            master["home_team"] = master["home_team"].astype(str).str.strip()
            master["away_team"] = master["away_team"].astype(str).str.strip()

        rating_cols = [
            "home_adj_o",
            "home_adj_d",
            "home_barthag",
            "home_efg",
            "home_efgd",
            "home_tor",
            "home_orb",
            "home_drb",
            "home_ftr",
            "home_tempo",
            "home_three_pt_rate",
            "home_wab",
            "home_rank",
            "away_adj_o",
            "away_adj_d",
            "away_barthag",
            "away_efg",
            "away_efgd",
            "away_tor",
            "away_orb",
            "away_drb",
            "away_ftr",
            "away_tempo",
            "away_three_pt_rate",
            "away_wab",
            "away_rank",
            # market lines/prices are also in the master
            "fg_spread",
            "h1_spread",
            "fg_spread_home_price",
            "fg_spread_away_price",
            "h1_spread_home_price",
            "h1_spread_away_price",
        ]

        for _, row in result.iterrows():
            home_name = row["home_team"]
            away_name = row["away_team"]
            matching = master[(master["home_team"] == home_name) & (master["away_team"] == away_name)]
            if matching.empty:
                continue
            latest = matching.iloc[-1]
            for col in rating_cols:
                if col in latest:
                    result.loc[result.index == row.name, col] = latest[col]

        return result

    # No local master: if we have odds lines already, we can still do live predictions by pulling ratings.
    try:
        season = _determine_current_season()
        ratings = _load_barttorvik_ratings_live(season)
    except Exception as exc:
        ratings = {}
        print(f"[WARN] Failed to fetch live Barttorvik ratings: {exc}")

    if ratings:
        # ============================================================
        # GOVERNANCE: AUTHORITATIVE TEAM NAME RESOLUTION GATE
        # ============================================================
        # Source: Postgres team_aliases table (95%+ coverage, 600+ aliases)
        # Module: testing.canonical.barttorvik_team_mappings
        #
        # DO NOT modify this section to use:
        # - Ad-hoc dictionaries
        # - Inline string manipulation
        # - Fuzzy matching
        #
        # All changes to team mappings must go through:
        # 1. Postgres team_aliases table (authoritative source)
        # 2. Export via scripts/export_team_registry.py
        # 3. Update testing.canonical.barttorvik_team_mappings module
        # ============================================================

        for idx, row in result.iterrows():
            home_team = row["home_team"]
            away_team = row["away_team"]

            # Resolve using authoritative mappings module
            home_bart = resolve_odds_api_to_barttorvik(home_team)
            away_bart = resolve_odds_api_to_barttorvik(away_team)

            # Lookup in Barttorvik ratings using resolved names
            h = ratings.get(home_bart) if home_bart else None
            a = ratings.get(away_bart) if away_bart else None

            if h:
                result.at[idx, "home_adj_o"] = h.get("adj_o")
                result.at[idx, "home_adj_d"] = h.get("adj_d")
                result.at[idx, "home_barthag"] = h.get("barthag")
                result.at[idx, "home_tempo"] = h.get("tempo")
                result.at[idx, "home_wab"] = h.get("wab")
                result.at[idx, "home_rank"] = h.get("rank")
                result.at[idx, "home_tor"] = h.get("tor")
                result.at[idx, "home_orb"] = h.get("orb")
                result.at[idx, "home_ftr"] = h.get("ftr", 0.3)  # Default if missing
                result.at[idx, "home_efg"] = h.get("efg", 50.0)  # Default if missing
                result.at[idx, "home_efgd"] = h.get("efgd", 50.0)  # Default if missing
                result.at[idx, "home_drb"] = h.get("drb", 70.0)  # Default if missing
                result.at[idx, "home_three_pt_rate"] = h.get("three_pt_rate", 35.0)  # Default if missing
            if a:
                result.at[idx, "away_adj_o"] = a.get("adj_o")
                result.at[idx, "away_adj_d"] = a.get("adj_d")
                result.at[idx, "away_barthag"] = a.get("barthag")
                result.at[idx, "away_tempo"] = a.get("tempo")
                result.at[idx, "away_wab"] = a.get("wab")
                result.at[idx, "away_rank"] = a.get("rank")
                result.at[idx, "away_tor"] = a.get("tor")
                result.at[idx, "away_orb"] = a.get("orb")
                result.at[idx, "away_ftr"] = a.get("ftr", 0.3)  # Default if missing
                result.at[idx, "away_efg"] = a.get("efg", 50.0)  # Default if missing
                result.at[idx, "away_efgd"] = a.get("efgd", 50.0)  # Default if missing
                result.at[idx, "away_drb"] = a.get("drb", 70.0)  # Default if missing
                result.at[idx, "away_three_pt_rate"] = a.get("three_pt_rate", 35.0)  # Default if missing

        return result

    # Last resort: Azure (requires creds)
    reader = get_azure_reader()
    master = reader.read_csv("manifests/canonical_training_data_master.csv")
    if "home_canonical" in master.columns:
        master["home_team"] = master["home_canonical"].astype(str).str.strip()
        master["away_team"] = master["away_canonical"].astype(str).str.strip()
    elif "home_team" in master.columns:
        master["home_team"] = master["home_team"].astype(str).str.strip()
        master["away_team"] = master["away_team"].astype(str).str.strip()

    for _, row in result.iterrows():
        home_name = row["home_team"]
        away_name = row["away_team"]
        matching = master[(master["home_team"] == home_name) & (master["away_team"] == away_name)]
        if matching.empty:
            continue
        latest = matching.iloc[-1]
        for col in [c for c in master.columns if c.startswith("home_") or c.startswith("away_") or c in {"fg_spread", "h1_spread", "fg_spread_home_price", "fg_spread_away_price", "h1_spread_home_price", "h1_spread_away_price"}]:
            result.loc[result.index == row.name, col] = latest.get(col)

    return result


def generate_picks(df: pd.DataFrame, markets: list[MarketType]) -> list[TonightPick]:
    """Generate predictions for tonight's games using v33 formula-based predictions."""
    picks = []

    # Add derived features for v33 predictions
    df = _add_derived_features(df)

    # Create BacktestConfig and Predictor for v33 formulas
    config = BacktestConfig(
        market=MarketType.FG_SPREAD,  # Dummy market (not used by predictor directly)
        seasons=[2026],  # Dummy season
        hca_spread=5.8,
        hca_total=3.4,
        hca_h1_spread=3.6,
    )

    from testing.scripts.run_historical_backtest import NCAAMPredictor
    predictor = NCAAMPredictor(config)

    for market in markets:
        print(f"\n[INFO] Generating {market.value} predictions...")

        # Determine line column and prediction method
        if market == MarketType.FG_SPREAD:
            line_col = "fg_spread"
            predict_func = predictor.predict_spread
        elif market == MarketType.H1_SPREAD:
            line_col = "h1_spread"
            predict_func = predictor.predict_h1_spread
        elif market == MarketType.FG_TOTAL:
            line_col = "fg_total"
            predict_func = predictor.predict_total
        elif market == MarketType.H1_TOTAL:
            line_col = "h1_total"
            predict_func = predictor.predict_h1_total
        else:
            print(f"[WARN] Market {market.value} not supported; skipping.")
            continue

        # Default edge thresholds
        min_edge_points = 5.0  # Conservative threshold for live betting

        for _, game in df.iterrows():
            # Extract required fields
            try:
                home_team = game.get("home_team", "UNKNOWN")
                away_team = game.get("away_team", "UNKNOWN")
                game_date = game.get("game_date", datetime.now().date())
                game_time_utc = game.get("commence_time", "TBD")

                # Convert UTC time to CST
                if game_time_utc and game_time_utc != "TBD":
                    try:
                        # Parse UTC datetime
                        dt_utc = pd.to_datetime(game_time_utc)
                        if dt_utc.tzinfo is None:
                            dt_utc = pytz.UTC.localize(dt_utc)
                        # Convert to CST
                        cst = pytz.timezone("US/Central")
                        dt_cst = dt_utc.astimezone(cst)
                        game_time = dt_cst.strftime("%Y-%m-%d %H:%M %Z")
                    except Exception:
                        game_time = str(game_time_utc)
                else:
                    game_time = "TBD"

                market_line = game.get(line_col)
                if pd.isna(market_line):
                    continue

                # Get required ratings
                home_adj_o = game.get("home_adj_o")
                home_adj_d = game.get("home_adj_d")
                away_adj_o = game.get("away_adj_o")
                away_adj_d = game.get("away_adj_d")

                if any(pd.isna(x) for x in [home_adj_o, home_adj_d, away_adj_o, away_adj_d]):
                    print(f"[SKIP] {away_team} @ {home_team} - missing ratings")
                    continue

                # Build prediction kwargs based on market type
                kwargs = {
                    "home_adj_o": float(home_adj_o),
                    "home_adj_d": float(home_adj_d),
                    "away_adj_o": float(away_adj_o),
                    "away_adj_d": float(away_adj_d),
                    "is_neutral": bool(game.get("neutral", False)),
                }

                # Add optional Four Factors if available
                for factor in ["efg", "efgd", "tor", "orb", "drb", "ftr"]:
                    for side in ["home", "away"]:
                        col = f"{side}_{factor}"
                        val = game.get(col)
                        if not pd.isna(val):
                            kwargs[col] = float(val)

                # Add tempo for totals
                if "total" in market.value:
                    home_tempo = game.get("home_tempo")
                    away_tempo = game.get("away_tempo")
                    if not pd.isna(home_tempo):
                        kwargs["home_tempo"] = float(home_tempo)
                    if not pd.isna(away_tempo):
                        kwargs["away_tempo"] = float(away_tempo)

                    # 3PT rate for totals
                    home_3pt = game.get("home_three_pt_rate")
                    away_3pt = game.get("away_three_pt_rate")
                    if not pd.isna(home_3pt):
                        kwargs["home_three_pt_rate"] = float(home_3pt)
                    if not pd.isna(away_3pt):
                        kwargs["away_three_pt_rate"] = float(away_3pt)

                # Add advanced features for spreads
                if "spread" in market.value:
                    conf_diff = game.get("conf_strength_diff")
                    if not pd.isna(conf_diff):
                        kwargs["conf_strength_diff"] = float(conf_diff)

                    for feat in ["team_depth_rolling", "ast_to_ratio_rolling"]:
                        for side in ["home", "away"]:
                            col = f"{side}_{feat}"
                            val = game.get(col)
                            if not pd.isna(val):
                                kwargs[col] = float(val)

                # Make prediction using v33 formula
                predicted = predict_func(**kwargs)

                edge_points = abs(predicted - float(market_line))
                edge_pct = (edge_points / 11.0) * 100.0  # sigma = 11.0 for spread

                if edge_points < min_edge_points:
                    continue

                # Determine bet side
                if "spread" in market.value:
                    bet_side = "home" if predicted < market_line else "away"
                else:
                    bet_side = "over" if predicted > market_line else "under"

                # Confidence based on edge
                if edge_points >= 7:
                    confidence = "HIGH"
                elif edge_points >= 4:
                    confidence = "MEDIUM"
                else:
                    confidence = "LOW"

                pick = TonightPick(
                    game_date=str(game_date),
                    game_time=str(game_time),
                    home_team=home_team,
                    away_team=away_team,
                    market=market.value,
                    predicted_line=round(predicted, 1),
                    market_line=round(market_line, 1),
                    edge=round(edge_points, 1),
                    bet_side=bet_side,
                    edge_pct=round(edge_pct, 2),
                    confidence=confidence,
                    paper_mode=True,
                )
                picks.append(pick)

            except Exception as e:
                print(f"[WARN] Error processing game: {e}")
                continue

    return picks


def main():
    parser = argparse.ArgumentParser(
        description="Generate tonight's picks using profitable models (paper mode)"
    )
    parser.add_argument(
        "--market",
        choices=["fg_spread", "h1_spread", "fg_total", "h1_total"],
        default=None,
        help="Specific market to generate picks for (default: all profitable)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fetch real games from Odds API (requires ODDS_API_KEY environment variable)"
    )

    args = parser.parse_args()

    # Select markets
    if args.market:
        markets = [MarketType(args.market)]
    else:
        markets = PROFITABLE_MARKETS

    print("\n" + "="*70)
    print("TONIGHT'S PICKS - PAPER MODE")
    print("="*70)
    print(f"Markets: {[m.value for m in markets]}")
    print(f"Live Mode: {args.live}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    # Load games
    print("[INFO] Loading games for tonight...")
    games_df = load_games_for_tonight(live=args.live)

    if games_df.empty:
        print("[WARN] No games found; cannot generate picks")
        return

    print(f"[OK] Loaded {len(games_df)} games")

    # Add ratings
    print("[INFO] Adding team ratings...")
    games_df = add_ratings_to_games(games_df)

    # Generate picks
    print("[INFO] Generating predictions...")
    picks = generate_picks(games_df, markets)

    if not picks:
        print("[WARN] No picks generated (all edges below thresholds)")
        return

    # Output results
    print(f"\n[OK] Generated {len(picks)} picks:\n")

    picks_df = pd.DataFrame([
        {
            "Date": p.game_date,
            "Time": p.game_time,
            "Matchup": f"{p.away_team} @ {p.home_team}",
            "Market": p.market,
            "Predicted": p.predicted_line,
            "Market Line": p.market_line,
            "Edge (pts)": p.edge,
            "Bet": p.bet_side,
            "Edge %": f"{p.edge_pct}%",
            "Confidence": p.confidence,
        }
        for p in picks
    ])

    print(picks_df.to_string(index=False))

    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RESULTS_DIR / f"tonight_picks_{timestamp}.csv"
    picks_df.to_csv(output_file, index=False)

    # Save JSON for integration with betting systems and website
    json_file = RESULTS_DIR / f"tonight_picks_{timestamp}.json"

    # Format matching greenbiersportventures.com/weekly-lineup API
    picks_json = {
        "generated_at": datetime.now(pytz.timezone("US/Central")).isoformat(),
        "model_version": "v33_formula",
        "date": datetime.now(pytz.timezone("US/Central")).strftime("%Y-%m-%d"),
        "picks": []
    }

    for p in picks:
        # Determine fire_rating based on edge
        if p.edge >= 7:
            fire_rating = "MAX"
        elif p.edge >= 5:
            fire_rating = "STRONG"
        elif p.edge >= 3:
            fire_rating = "GOOD"
        else:
            fire_rating = "STANDARD"

        # Format pick label
        if p.bet_side == "home":
            pick_label = p.home_team
        elif p.bet_side == "away":
            pick_label = p.away_team
        else:
            pick_label = p.bet_side.upper()

        # Determine market and period
        market_type = "SPREAD" if "spread" in p.market else "TOTAL"
        period = "1H" if "h1" in p.market else "FG"

        picks_json["picks"].append({
            "time_cst": p.game_time,
            "matchup": f"{p.away_team} @ {p.home_team}",
            "home_team": p.home_team,
            "away_team": p.away_team,
            "period": period,
            "market": market_type,
            "pick": pick_label,
            "pick_odds": "N/A",  # Not available in live mode
            "model_line": p.predicted_line,
            "market_line": p.market_line,
            "edge": f"+{p.edge:.1f}" if p.edge > 0 else f"{p.edge:.1f}",
            "confidence": f"{p.edge_pct:.0f}%",
            "fire_rating": fire_rating,
            "model_version": "v33_formula",
            "is_current_model": True,
        })

    with open(json_file, "w") as f:
        json.dump(picks_json, f, indent=2)

    print(f"\n[OK] Saved picks to {output_file}")
    print(f"[OK] Saved JSON to {json_file}")
    print("\n⚠️  PAPER MODE ONLY - No real money at stake")
    print("Review picks before any real action\n")


if __name__ == "__main__":
    main()
