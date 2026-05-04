from __future__ import annotations

import pandas as pd


def simple_moving_average(closes: list[float], window: int) -> float:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(closes) < window:
        raise ValueError(f"need at least {window} closes to calculate SMA")

    series = pd.Series(closes, dtype="float64")
    value = series.rolling(window=window).mean().iloc[-1]
    if pd.isna(value):
        raise ValueError(f"could not calculate SMA{window}")
    return float(value)
