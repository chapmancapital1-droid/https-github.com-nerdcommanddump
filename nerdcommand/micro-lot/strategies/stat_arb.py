"""Strategy 2: Statistical Arbitrage — pair correlation z-score divergence.

Entry:  spread z-score > +2 → short the spread (short A, long B)
        spread z-score < -2 → long the spread (long A, short B)
Exit:   |z-score| < 1 (reversion) OR 3 scalps done.
Win rate expectation: 55-60%.
Confidence weight: 1.2 (highest, market-neutral).
"""
import numpy as np

from config import CONF_STAT_ARB, CORR_LOOKBACK, SPREAD_STD_ENTRY, SPREAD_STD_EXIT
from strategies import Signal


def _z_score(a: np.ndarray, b: np.ndarray, lookback: int) -> float:
    n = min(len(a), len(b), lookback)
    if n < 20:
        return 0.0
    ratio = np.log(a[-n:]) - np.log(b[-n:])
    mu  = ratio.mean()
    std = ratio.std()
    if std < 1e-10:
        return 0.0
    return (ratio[-1] - mu) / std


def compute(close_a: np.ndarray, close_b: np.ndarray,
            sym_a: str, sym_b: str) -> Signal:
    if len(close_a) < 20 or len(close_b) < 20:
        return Signal(0, 0.0, "stat_arb", "insufficient data")

    z = _z_score(close_a, close_b, CORR_LOOKBACK)

    if z > SPREAD_STD_ENTRY:
        return Signal(-1, CONF_STAT_ARB, "stat_arb",
                      f"{sym_a}/{sym_b} spread z={z:.2f} > {SPREAD_STD_ENTRY} → short spread")
    if z < -SPREAD_STD_ENTRY:
        return Signal(1, CONF_STAT_ARB, "stat_arb",
                      f"{sym_a}/{sym_b} spread z={z:.2f} < -{SPREAD_STD_ENTRY} → long spread")
    return Signal(0, 0.0, "stat_arb", f"{sym_a}/{sym_b} z={z:.2f} neutral")


def should_exit(close_a: np.ndarray, close_b: np.ndarray) -> bool:
    z = abs(_z_score(close_a, close_b, CORR_LOOKBACK))
    return z < SPREAD_STD_EXIT


def z_score(close_a: np.ndarray, close_b: np.ndarray) -> float:
    return _z_score(close_a, close_b, CORR_LOOKBACK)
