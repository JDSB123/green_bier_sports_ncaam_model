#!/usr/bin/env python3
"""
Train independent market models from the canonical master dataset.

- Uses manifests/canonical_training_data_master.csv only (local or Azure).
- Trains per-market models with market-appropriate feature sets.
- Evaluates ROI on a holdout season and selects best feature set + edge threshold.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from testing.azure_data_reader import get_azure_reader
from testing.data_window import CANONICAL_START_SEASON, default_backtest_seasons, enforce_min_season

MODEL_DIR = ROOT_DIR / "models" / "linear"
RESULTS_DIR = ROOT_DIR / "testing" / "results" / "training"

MODEL_DIR.mkdir(parents=True, exist_ok=True)


def load_canonical_master() -> pd.DataFrame:
    """Load canonical master from local mirror or Azure."""
    reader = get_azure_reader()
    local_master = ROOT_DIR / "manifests" / "canonical_training_data_master.csv"
    if local_master.exists():
        df = pd.read_csv(local_master)
    else:
        # Try canonical/ path first (Azure), then manifests/ path
        try:
            df = reader.read_csv("canonical/canonical_training_data_master.csv")
        except FileNotFoundError:
            df = reader.read_csv("manifests/canonical_training_data_master.csv")

    # Normalize dates
    if "game_date" in df.columns:
        df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    elif "date" in df.columns:
        df["game_date"] = pd.to_datetime(df["date"], errors="coerce")

    if "season" in df.columns:
        df = df[df["season"] >= CANONICAL_START_SEASON]

    # Actual results
    if "actual_margin" not in df.columns and {"home_score", "away_score"}.issubset(df.columns):
        df["actual_margin"] = df["home_score"] - df["away_score"]
    if "actual_total" not in df.columns and {"home_score", "away_score"}.issubset(df.columns):
        df["actual_total"] = df["home_score"] + df["away_score"]

    if "h1_actual_margin" not in df.columns and {"home_h1", "away_h1"}.issubset(df.columns):
        df["h1_actual_margin"] = df["home_h1"] - df["away_h1"]
    if "h1_actual_total" not in df.columns and {"home_h1", "away_h1"}.issubset(df.columns):
        df["h1_actual_total"] = df["home_h1"] + df["away_h1"]

    return df


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features for market models."""
    df = df.copy()

    def _col(name: str) -> pd.Series:
        if name in df.columns:
            return df[name]
        return pd.Series(np.nan, index=df.index)

    home_adj_o = _col("home_adj_o")
    home_adj_d = _col("home_adj_d")
    away_adj_o = _col("away_adj_o")
    away_adj_d = _col("away_adj_d")

    df["net_diff"] = (home_adj_o - home_adj_d) - (away_adj_o - away_adj_d)
    df["barthag_diff"] = _col("home_barthag") - _col("away_barthag")

    df["efg_diff"] = (_col("home_efg") - _col("away_efgd")) - (_col("away_efg") - _col("home_efgd"))
    df["tor_diff"] = _col("away_tor") - _col("home_tor")
    df["orb_diff"] = (_col("home_orb") - _col("away_drb")) - (_col("away_orb") - _col("home_drb"))
    df["ftr_diff"] = _col("home_ftr") - _col("away_ftr")

    df["rank_diff"] = _col("away_rank") - _col("home_rank")
    df["wab_diff"] = _col("home_wab") - _col("away_wab")

    df["tempo_avg"] = (_col("home_tempo") + _col("away_tempo")) / 2.0
    df["home_eff"] = home_adj_o + away_adj_d
    df["away_eff"] = away_adj_o + home_adj_d
    three_pt_rate_avg = (_col("home_three_pt_rate") + _col("away_three_pt_rate")) / 2.0
    three_pt_rate_avg = three_pt_rate_avg.where(three_pt_rate_avg <= 2.0, three_pt_rate_avg / 100.0)
    df["three_pt_rate_avg"] = three_pt_rate_avg
    df["two_pt_pct_avg"] = (_col("home_two_pt_pct") + _col("away_two_pt_pct")) / 2.0

    def _odds_to_prob(series: pd.Series) -> pd.Series:
        def _calc(value: float) -> float | None:
            if pd.isna(value):
                return None
            if value >= 100:
                return 100.0 / (value + 100.0)
            return abs(value) / (abs(value) + 100.0)

        return series.apply(_calc)

    if "moneyline_home_price" in df.columns:
        df["ml_implied_home"] = _odds_to_prob(df["moneyline_home_price"])
    if "moneyline_away_price" in df.columns:
        df["ml_implied_away"] = _odds_to_prob(df["moneyline_away_price"])

    return df


def standardize(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Standardize features and return (Xz, means, stds)."""
    means = np.nanmean(X, axis=0)
    stds = np.nanstd(X, axis=0)
    stds = np.where(stds == 0, 1.0, stds)
    Xz = (X - means) / stds
    return Xz, means, stds


def fit_linear_model(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Fit linear regression with standardization."""
    Xz, means, stds = standardize(X)
    Xb = np.column_stack([np.ones(len(Xz)), Xz])
    weights = np.linalg.lstsq(Xb, y, rcond=None)[0]
    intercept = float(weights[0])
    coef = weights[1:]
    return coef, intercept, means, stds


def sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-z))


def fit_logistic_model(
    X: np.ndarray,
    y: np.ndarray,
    lr: float = 0.1,
    max_iter: int = 800,
    reg: float = 1e-3,
) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Fit logistic regression with simple gradient descent."""
    Xz, means, stds = standardize(X)
    Xb = np.column_stack([np.ones(len(Xz)), Xz])
    weights = np.zeros(Xb.shape[1])

    for _ in range(max_iter):
        p = sigmoid(Xb @ weights)
        grad = (Xb.T @ (p - y)) / len(y)
        grad[1:] += reg * weights[1:]
        weights -= lr * grad

    intercept = float(weights[0])
    coef = weights[1:]
    return coef, intercept, means, stds


def predict_linear(
    X: np.ndarray,
    coef: np.ndarray,
    intercept: float,
    means: np.ndarray,
    stds: np.ndarray,
) -> np.ndarray:
    Xz = (X - means) / stds
    return Xz @ coef + intercept


def predict_logistic(
    X: np.ndarray,
    coef: np.ndarray,
    intercept: float,
    means: np.ndarray,
    stds: np.ndarray,
) -> np.ndarray:
    Xz = (X - means) / stds
    return sigmoid(Xz @ coef + intercept)


def margin_to_prob(margins: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        sigma = 1.0
    scale = sigma * math.sqrt(2.0)
    return np.array([0.5 * (1.0 + math.erf(margin / scale)) for margin in margins], dtype=float)


def american_odds_to_prob(american_odds: float) -> float | None:
    if pd.isna(american_odds):
        return None
    if american_odds >= 100:
        return 100.0 / (american_odds + 100.0)
    return abs(american_odds) / (abs(american_odds) + 100.0)


def american_odds_to_decimal(american_odds: float) -> float | None:
    if pd.isna(american_odds):
        return None
    if american_odds >= 100:
        return (american_odds / 100.0) + 1.0
    return (100.0 / abs(american_odds)) + 1.0


def calculate_profit(outcome: str, wager: float, odds: float) -> float | None:
    decimal_odds = american_odds_to_decimal(odds)
    if decimal_odds is None:
        return None
    if outcome == "WIN":
        return wager * (decimal_odds - 1.0)
    if outcome == "LOSS":
        return -wager
    return 0.0


def determine_outcome_spread(bet_side: str, market_line: float, actual_margin: float) -> str:
    if bet_side == "home":
        diff = actual_margin - (-market_line)
    else:
        diff = -actual_margin - market_line
    if abs(diff) < 0.001:
        return "PUSH"
    return "WIN" if diff > 0 else "LOSS"


def determine_outcome_total(bet_side: str, market_line: float, actual_total: float) -> str:
    if bet_side == "over":
        diff = actual_total - market_line
    else:
        diff = market_line - actual_total
    if abs(diff) < 0.001:
        return "PUSH"
    return "WIN" if diff > 0 else "LOSS"


def determine_outcome_moneyline(bet_side: str, actual_margin: float) -> str:
    if actual_margin > 0:
        return "WIN" if bet_side == "home" else "LOSS"
    if actual_margin < 0:
        return "WIN" if bet_side == "away" else "LOSS"
    return "PUSH"


def simulate_spread_total_bets(
    df: pd.DataFrame,
    predictions: np.ndarray,
    line_col: str,
    price_col: str,
    alt_price_col: str,
    result_col: str,
    sigma: float,
    min_edge: float,
    bet_type: str,
    wager: float = 100.0,
) -> dict[str, float]:
    total_bets = 0
    wins = 0
    losses = 0
    pushes = 0
    profit_total = 0.0

    for i, (_, row) in enumerate(df.iterrows()):
        market_line = row.get(line_col)
        if pd.isna(market_line):
            continue

        predicted = predictions[i]
        edge = abs(predicted - market_line) / sigma * 100.0
        if edge < min_edge:
            continue

        if bet_type == "spread":
            bet_side = "home" if predicted < market_line else "away"
        else:
            bet_side = "over" if predicted > market_line else "under"

        odds = row.get(price_col if bet_side in ["home", "over"] else alt_price_col)
        if pd.isna(odds):
            continue

        actual = row.get(result_col)
        if pd.isna(actual):
            continue

        if bet_type == "spread":
            outcome = determine_outcome_spread(bet_side, market_line, actual)
        else:
            outcome = determine_outcome_total(bet_side, market_line, actual)

        profit = calculate_profit(outcome, wager, odds)
        if profit is None:
            continue

        total_bets += 1
        profit_total += profit
        if outcome == "WIN":
            wins += 1
        elif outcome == "LOSS":
            losses += 1
        else:
            pushes += 1

    total_wagered = total_bets * wager
    roi = (profit_total / total_wagered * 100.0) if total_wagered > 0 else 0.0
    win_rate = (wins / (wins + losses) * 100.0) if (wins + losses) > 0 else 0.0

    return {
        "total_bets": total_bets,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "total_profit": profit_total,
        "roi": roi,
        "win_rate": win_rate,
    }


def simulate_moneyline_bets(
    df: pd.DataFrame,
    predictions: np.ndarray,
    price_home_col: str,
    price_away_col: str,
    result_col: str,
    min_edge: float,
    wager: float = 100.0,
) -> dict[str, float]:
    total_bets = 0
    wins = 0
    losses = 0
    pushes = 0
    profit_total = 0.0

    for i, (_, row) in enumerate(df.iterrows()):
        home_price = row.get(price_home_col)
        away_price = row.get(price_away_col)
        if pd.isna(home_price) or pd.isna(away_price):
            continue

        prob_home = predictions[i]
        dec_home = american_odds_to_decimal(home_price)
        dec_away = american_odds_to_decimal(away_price)
        if dec_home is None or dec_away is None:
            continue
        prob_away = 1.0 - prob_home

        ev_home = prob_home * (dec_home - 1.0) - (1.0 - prob_home)
        ev_away = prob_away * (dec_away - 1.0) - (1.0 - prob_away)
        best_ev = max(ev_home, ev_away)
        if best_ev * 100.0 < min_edge:
            continue

        if ev_home >= ev_away:
            bet_side = "home"
            odds = home_price
        else:
            bet_side = "away"
            odds = away_price

        actual_margin = row.get(result_col)
        if pd.isna(actual_margin):
            continue

        outcome = determine_outcome_moneyline(bet_side, actual_margin)
        profit = calculate_profit(outcome, wager, odds)
        if profit is None:
            continue

        total_bets += 1
        profit_total += profit
        if outcome == "WIN":
            wins += 1
        elif outcome == "LOSS":
            losses += 1
        else:
            pushes += 1

    total_wagered = total_bets * wager
    roi = (profit_total / total_wagered * 100.0) if total_wagered > 0 else 0.0
    win_rate = (wins / (wins + losses) * 100.0) if (wins + losses) > 0 else 0.0

    return {
        "total_bets": total_bets,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "total_profit": profit_total,
        "roi": roi,
        "win_rate": win_rate,
    }


@dataclass
class MarketSpec:
    name: str
    target_col: str
    line_col: str | None
    price_home_col: str
    price_away_col: str
    sigma: float
    model_type: str  # "linear" or "logistic"
    target_mode: str  # "raw", "residual", "win_prob"
    feature_sets: list[list[str]]
    bet_type: str  # "spread", "total", "moneyline"
    edge_grid: list[float]


SPREAD_BASE_FEATURE_SETS = [
    ["net_diff", "barthag_diff"],
    ["net_diff", "barthag_diff", "efg_diff", "tor_diff", "orb_diff", "ftr_diff"],
    ["net_diff", "barthag_diff", "efg_diff", "tor_diff", "orb_diff", "ftr_diff", "rank_diff", "wab_diff"],
]

TOTAL_BASE_FEATURE_SETS = [
    ["tempo_avg", "home_eff", "away_eff"],
    ["tempo_avg", "home_eff", "away_eff", "three_pt_rate_avg", "two_pt_pct_avg"],
    ["tempo_avg", "home_eff", "away_eff", "three_pt_rate_avg", "two_pt_pct_avg", "barthag_diff"],
]

MONEYLINE_FEATURE_SETS = [
    ["net_diff", "barthag_diff"],
    ["net_diff", "barthag_diff", "efg_diff", "tor_diff"],
    ["net_diff", "barthag_diff", "efg_diff", "tor_diff", "rank_diff", "wab_diff"],
    ["ml_implied_home", "net_diff", "barthag_diff"],
    ["ml_implied_home", "net_diff", "barthag_diff", "efg_diff", "tor_diff"],
    ["ml_implied_home", "net_diff", "barthag_diff", "efg_diff", "tor_diff", "rank_diff", "wab_diff"],
]

def _with_line(base_sets: list[list[str]], line_col: str) -> list[list[str]]:
    return [[line_col] + feats for feats in base_sets]


def build_market_specs() -> dict[str, MarketSpec]:
    return {
        "fg_spread": MarketSpec(
            name="fg_spread",
            target_col="actual_margin",
            line_col="fg_spread",
            price_home_col="fg_spread_home_price",
            price_away_col="fg_spread_away_price",
            sigma=11.0,
            model_type="linear",
            target_mode="residual",
            feature_sets=_with_line(SPREAD_BASE_FEATURE_SETS, "fg_spread"),
            bet_type="spread",
            edge_grid=[1.5, 2.0, 3.0, 5.0, 7.0, 10.0],
        ),
        "fg_total": MarketSpec(
            name="fg_total",
            target_col="actual_total",
            line_col="fg_total",
            price_home_col="fg_total_over_price",
            price_away_col="fg_total_under_price",
            sigma=8.0,
            model_type="linear",
            target_mode="residual",
            feature_sets=_with_line(TOTAL_BASE_FEATURE_SETS, "fg_total"),
            bet_type="total",
            edge_grid=[1.5, 2.0, 3.0, 5.0, 7.0, 10.0],
        ),
        "fg_moneyline": MarketSpec(
            name="fg_moneyline",
            target_col="actual_margin",
            line_col=None,
            price_home_col="moneyline_home_price",
            price_away_col="moneyline_away_price",
            sigma=11.0,
            model_type="linear",
            target_mode="raw",
            feature_sets=MONEYLINE_FEATURE_SETS,
            bet_type="moneyline",
            edge_grid=[1.0, 2.0, 3.0, 5.0, 7.0, 10.0],
        ),
        "h1_spread": MarketSpec(
            name="h1_spread",
            target_col="h1_actual_margin",
            line_col="h1_spread",
            price_home_col="h1_spread_home_price",
            price_away_col="h1_spread_away_price",
            sigma=11.0,
            model_type="linear",
            target_mode="residual",
            feature_sets=_with_line(SPREAD_BASE_FEATURE_SETS, "h1_spread"),
            bet_type="spread",
            edge_grid=[1.5, 2.0, 3.0, 5.0, 7.0, 10.0],
        ),
        "h1_total": MarketSpec(
            name="h1_total",
            target_col="h1_actual_total",
            line_col="h1_total",
            price_home_col="h1_total_over_price",
            price_away_col="h1_total_under_price",
            sigma=8.0,
            model_type="linear",
            target_mode="residual",
            feature_sets=_with_line(TOTAL_BASE_FEATURE_SETS, "h1_total"),
            bet_type="total",
            edge_grid=[1.5, 2.0, 3.0, 5.0, 7.0, 10.0],
        ),
        "h1_moneyline": MarketSpec(
            name="h1_moneyline",
            target_col="h1_actual_margin",
            line_col=None,
            price_home_col="h1_moneyline_home_price",
            price_away_col="h1_moneyline_away_price",
            sigma=8.0,
            model_type="linear",
            target_mode="raw",
            feature_sets=MONEYLINE_FEATURE_SETS,
            bet_type="moneyline",
            edge_grid=[1.0, 2.0, 3.0, 5.0, 7.0, 10.0],
        ),
    }


def split_train_valid(
    df: pd.DataFrame,
    holdout_season: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    seasons = sorted(df["season"].dropna().unique().tolist())
    if not seasons:
        return df, df

    if holdout_season is None:
        holdout_season = seasons[-1]

    train_df = df[df["season"] != holdout_season].copy()
    valid_df = df[df["season"] == holdout_season].copy()

    if train_df.empty or valid_df.empty:
        df_sorted = df.sort_values("game_date")
        cut = int(len(df_sorted) * 0.8)
        train_df = df_sorted.iloc[:cut].copy()
        valid_df = df_sorted.iloc[cut:].copy()

    return train_df, valid_df


def evaluate_feature_set(
    spec: MarketSpec,
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    feature_set: list[str],
    min_bets: int,
) -> dict[str, float]:
    cols = feature_set + [spec.target_col]
    if spec.line_col:
        cols.append(spec.line_col)
    cols.extend([spec.price_home_col, spec.price_away_col])
    missing_cols = [col for col in cols if col not in train_df.columns]
    if missing_cols:
        return {}

    train_df = train_df.dropna(subset=cols)
    valid_df = valid_df.dropna(subset=cols)
    if train_df.empty or valid_df.empty:
        return {}

    X_train = train_df[feature_set].to_numpy(dtype=float)
    X_valid = valid_df[feature_set].to_numpy(dtype=float)

    line_train = train_df[spec.line_col].to_numpy(dtype=float) if spec.line_col else None
    line_valid = valid_df[spec.line_col].to_numpy(dtype=float) if spec.line_col else None

    if spec.target_mode == "residual":
        if line_train is None or line_valid is None:
            return {}
        if spec.bet_type == "spread":
            y_train = train_df[spec.target_col].to_numpy(dtype=float) - (-line_train)
            y_valid = valid_df[spec.target_col].to_numpy(dtype=float) - (-line_valid)
        else:
            y_train = train_df[spec.target_col].to_numpy(dtype=float) - line_train
            y_valid = valid_df[spec.target_col].to_numpy(dtype=float) - line_valid
    elif spec.target_mode == "win_prob":
        y_train = (train_df[spec.target_col] > 0).astype(float).to_numpy()
        y_valid = (valid_df[spec.target_col] > 0).astype(float).to_numpy()
    else:
        y_train = train_df[spec.target_col].to_numpy(dtype=float)
        y_valid = valid_df[spec.target_col].to_numpy(dtype=float)

    if spec.model_type == "linear":
        coef, intercept, means, stds = fit_linear_model(X_train, y_train)
        preds_raw = predict_linear(X_valid, coef, intercept, means, stds)
        if spec.bet_type == "moneyline":
            preds_valid = margin_to_prob(preds_raw, spec.sigma)
            mae = float(np.mean(np.abs(preds_raw - y_valid)))
        elif spec.target_mode == "residual":
            if spec.bet_type == "spread":
                preds_valid = line_valid - preds_raw
            else:
                preds_valid = line_valid + preds_raw
            mae = float(np.mean(np.abs(preds_raw - y_valid)))
        else:
            preds_valid = preds_raw
            mae = float(np.mean(np.abs(preds_raw - y_valid)))
        log_loss = None
    else:
        y_bin = (y_train > 0).astype(float)
        coef, intercept, means, stds = fit_logistic_model(X_train, y_bin)
        preds_valid = predict_logistic(X_valid, coef, intercept, means, stds)
        y_valid_bin = (y_valid > 0).astype(float)
        eps = 1e-6
        log_loss = float(-np.mean(y_valid_bin * np.log(preds_valid + eps) + (1 - y_valid_bin) * np.log(1 - preds_valid + eps)))
        mae = None

    best = {
        "roi": -999.0,
        "min_edge": None,
        "total_bets": 0,
        "win_rate": 0.0,
        "mae": mae,
        "log_loss": log_loss,
        "coef": coef,
        "intercept": intercept,
        "means": means,
        "stds": stds,
        "preds_valid": preds_valid,
    }

    for edge in spec.edge_grid:
        if spec.bet_type == "moneyline":
            summary = simulate_moneyline_bets(
                valid_df,
                preds_valid,
                spec.price_home_col,
                spec.price_away_col,
                spec.target_col,
                edge,
            )
        else:
            summary = simulate_spread_total_bets(
                valid_df,
                preds_valid,
                spec.line_col,
                spec.price_home_col,
                spec.price_away_col,
                spec.target_col,
                spec.sigma,
                edge,
                spec.bet_type,
            )

        if summary["total_bets"] < min_bets:
            continue

        if summary["roi"] > best["roi"]:
            best.update(summary)
            best["min_edge"] = edge

    if best["min_edge"] is None:
        return {}

    return best


def save_model(
    spec: MarketSpec,
    feature_set: list[str],
    metrics: dict[str, float],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "market": spec.name,
        "model_type": spec.model_type,
        "target_mode": spec.target_mode,
        "feature_names": feature_set,
        "weights": [float(x) for x in metrics["coef"]],
        "intercept": float(metrics["intercept"]),
        "means": [float(x) for x in metrics["means"]],
        "stds": [float(x) for x in metrics["stds"]],
        "metadata": {
            "min_edge": metrics.get("min_edge"),
            "roi": round(metrics.get("roi", 0.0), 2),
            "total_bets": int(metrics.get("total_bets", 0)),
            "win_rate": round(metrics.get("win_rate", 0.0), 2),
            "mae": metrics.get("mae"),
            "log_loss": metrics.get("log_loss"),
            "sigma": spec.sigma,
            "saved_at": datetime.now(UTC).isoformat(),
        },
    }
    path = output_dir / f"{spec.name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def load_model(market: str, allow_linear: bool = False):
    # Backwards-compatible wrapper for older backtesting code.
    # The JSON model format and inference live in `ncaam.linear_json_model`.
    from ncaam.linear_json_model import load_linear_json_model

    return load_linear_json_model(MODEL_DIR / f"{market}.json", allow_linear=allow_linear)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train independent market models (canonical master)")
    parser.add_argument("--seasons", default=None, help="Comma-separated seasons (default: canonical window)")
    parser.add_argument("--holdout-season", type=int, default=None, help="Holdout season for validation")
    parser.add_argument("--markets", default=None, help="Comma-separated markets to train (default: all)")
    parser.add_argument("--min-bets", type=int, default=50, help="Minimum bets required to select a model")
    parser.add_argument("--output-dir", default=None, help="Output directory for models")

    args = parser.parse_args()

    seasons = (
        [int(s.strip()) for s in args.seasons.split(",")]
        if args.seasons
        else default_backtest_seasons()
    )
    seasons = enforce_min_season(seasons)

    df = load_canonical_master()
    df = df[df["season"].isin(seasons)].copy()
    df = add_derived_features(df)
    df = df.dropna(subset=["game_date"])

    specs = build_market_specs()
    if "h1_total" in specs and specs["h1_total"].line_col not in df.columns:
        alt_col = "h1_total_h1_total"
        if alt_col in df.columns:
            specs["h1_total"].line_col = alt_col
            specs["h1_total"].feature_sets = _with_line(TOTAL_BASE_FEATURE_SETS, alt_col)
    if args.markets:
        requested = {m.strip() for m in args.markets.split(",")}
        specs = {k: v for k, v in specs.items() if k in requested}

    output_dir = Path(args.output_dir) if args.output_dir else MODEL_DIR
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    summary = {}

    print("=" * 72)
    print("INDEPENDENT MODEL TRAINING (CANONICAL MASTER)")
    print("=" * 72)
    print(f"Seasons: {seasons}")
    if args.holdout_season:
        print(f"Holdout season: {args.holdout_season}")

    for name, spec in specs.items():
        print("\n" + "-" * 72)
        print(f"Market: {name}")

        if spec.price_home_col not in df.columns or spec.price_away_col not in df.columns:
            print(f"[WARN] Missing odds columns for {name}; skipping.")
            continue

        train_df, valid_df = split_train_valid(df, args.holdout_season)

        best_feature_set = None
        best_metrics = None

        for feature_set in spec.feature_sets:
            metrics = evaluate_feature_set(spec, train_df, valid_df, feature_set, args.min_bets)
            if not metrics:
                continue

            if best_metrics is None or metrics["roi"] > best_metrics["roi"]:
                best_metrics = metrics
                best_feature_set = feature_set

        if not best_metrics or not best_feature_set:
            print("[WARN] No viable model found (insufficient data).")
            continue

        model_path = save_model(spec, best_feature_set, best_metrics, output_dir)

        summary[name] = {
            "features": best_feature_set,
            "min_edge": best_metrics.get("min_edge"),
            "roi": round(best_metrics.get("roi", 0.0), 2),
            "total_bets": int(best_metrics.get("total_bets", 0)),
            "win_rate": round(best_metrics.get("win_rate", 0.0), 2),
            "mae": best_metrics.get("mae"),
            "log_loss": best_metrics.get("log_loss"),
            "model_path": str(model_path),
        }

        mae_display = best_metrics.get("mae")
        if mae_display is not None:
            print(f"MAE: {mae_display:.2f}")
        log_loss_display = best_metrics.get("log_loss")
        if log_loss_display is not None:
            print(f"Log Loss: {log_loss_display:.4f}")
        print(f"Best ROI: {best_metrics.get('roi', 0.0):+.2f}%")
        print(f"Best min_edge: {best_metrics.get('min_edge')}")
        print(f"Bets: {best_metrics.get('total_bets')} | Win Rate: {best_metrics.get('win_rate', 0.0):.1f}%")
        print(f"Saved: {model_path}")

    summary_path = RESULTS_DIR / f"training_summary_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print("\nTraining summary saved:", summary_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
