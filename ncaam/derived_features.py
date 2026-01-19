from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from ncaam.types import MarketOdds, TeamRatingsLike


def _get_attr(obj: object, name: str):
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def compute_matchup_features(
    *,
    home: TeamRatingsLike | Mapping[str, object] | object,
    away: TeamRatingsLike | Mapping[str, object] | object,
    odds: MarketOdds | Mapping[str, object] | object,
) -> dict[str, float | None]:
    """Compute the derived features used by JSON linear model artifacts.

    This mirrors the feature definitions used in training/backtests and is shared
    across scripts and the prediction service.
    """

    home_adj_o = _get_attr(home, "adj_o")
    home_adj_d = _get_attr(home, "adj_d")
    away_adj_o = _get_attr(away, "adj_o")
    away_adj_d = _get_attr(away, "adj_d")

    home_net = (
        (home_adj_o - home_adj_d) if (home_adj_o is not None and home_adj_d is not None) else None
    )
    away_net = (
        (away_adj_o - away_adj_d) if (away_adj_o is not None and away_adj_d is not None) else None
    )

    fg_spread = _get_attr(odds, "spread")
    h1_spread = _get_attr(odds, "spread_1h")
    fg_total = _get_attr(odds, "total")
    h1_total = _get_attr(odds, "total_1h")

    home_efg = _get_attr(home, "efg")
    home_efgd = _get_attr(home, "efgd")
    away_efg = _get_attr(away, "efg")
    away_efgd = _get_attr(away, "efgd")

    home_tor = _get_attr(home, "tor")
    away_tor = _get_attr(away, "tor")

    home_orb = _get_attr(home, "orb")
    home_drb = _get_attr(home, "drb")
    away_orb = _get_attr(away, "orb")
    away_drb = _get_attr(away, "drb")

    home_ftr = _get_attr(home, "ftr")
    away_ftr = _get_attr(away, "ftr")

    home_rank = _get_attr(home, "rank")
    away_rank = _get_attr(away, "rank")

    home_wab = _get_attr(home, "wab")
    away_wab = _get_attr(away, "wab")

    home_tempo = _get_attr(home, "tempo")
    away_tempo = _get_attr(away, "tempo")

    home_three_pt_rate = _get_attr(home, "three_pt_rate")
    away_three_pt_rate = _get_attr(away, "three_pt_rate")

    home_two_pt_pct = _get_attr(home, "two_pt_pct")
    away_two_pt_pct = _get_attr(away, "two_pt_pct")

    def _safe_sub(a, b):
        if a is None or b is None:
            return None
        return float(a) - float(b)

    def _safe_add(a, b):
        if a is None or b is None:
            return None
        return float(a) + float(b)

    net_diff = (
        _safe_sub(home_net, away_net) if home_net is not None and away_net is not None else None
    )

    barthag_diff = _safe_sub(_get_attr(home, "barthag"), _get_attr(away, "barthag"))

    efg_diff = None
    if None not in (home_efg, away_efgd, away_efg, home_efgd):
        efg_diff = (float(home_efg) - float(away_efgd)) - (float(away_efg) - float(home_efgd))

    tor_diff = _safe_sub(away_tor, home_tor)

    orb_diff = None
    if None not in (home_orb, away_drb, away_orb, home_drb):
        orb_diff = (float(home_orb) - float(away_drb)) - (float(away_orb) - float(home_drb))

    ftr_diff = _safe_sub(home_ftr, away_ftr)
    rank_diff = _safe_sub(away_rank, home_rank)
    wab_diff = _safe_sub(home_wab, away_wab)

    tempo_avg = None
    if home_tempo is not None and away_tempo is not None:
        tempo_avg = (float(home_tempo) + float(away_tempo)) / 2.0

    home_eff = _safe_add(home_adj_o, away_adj_d)
    away_eff = _safe_add(away_adj_o, home_adj_d)

    three_pt_rate_avg = None
    if home_three_pt_rate is not None and away_three_pt_rate is not None:
        three_pt_rate_avg = (float(home_three_pt_rate) + float(away_three_pt_rate)) / 2.0
        if three_pt_rate_avg > 2.0:
            three_pt_rate_avg = three_pt_rate_avg / 100.0

    two_pt_pct_avg = None
    if home_two_pt_pct is not None and away_two_pt_pct is not None:
        two_pt_pct_avg = (float(home_two_pt_pct) + float(away_two_pt_pct)) / 2.0

    return {
        "fg_spread": fg_spread,
        "h1_spread": h1_spread,
        "fg_total": fg_total,
        "h1_total": h1_total,
        "net_diff": net_diff,
        "barthag_diff": barthag_diff,
        "efg_diff": efg_diff,
        "tor_diff": tor_diff,
        "orb_diff": orb_diff,
        "ftr_diff": ftr_diff,
        "rank_diff": rank_diff,
        "wab_diff": wab_diff,
        "tempo_avg": tempo_avg,
        "home_eff": home_eff,
        "away_eff": away_eff,
        "three_pt_rate_avg": three_pt_rate_avg,
        "two_pt_pct_avg": two_pt_pct_avg,
    }


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features used by retrained models (DataFrame form).

    This is the canonical implementation; backtests and scripts should call this
    instead of maintaining divergent feature code.
    """

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
