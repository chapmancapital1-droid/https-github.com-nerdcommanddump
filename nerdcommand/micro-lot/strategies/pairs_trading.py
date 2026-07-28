"""Strategy 4: Pairs Trading — relative-value divergence between correlated assets.

Entry:  pair spread > +2 std dev → long underperformer, short outperformer
        pair spread < -2 std dev → short underperformer, long outperformer
Exit:   spread returns to <1 std dev OR 3 scalps done.
Win rate expectation: 52-58%.
Confidence weight: 1.1x.
"""
import numpy as np

from config import CONF_PAIRS, CORR_LOOKBACK, SPREAD_STD_ENTRY, SPREAD_STD_EXIT
from strategies import Signal


def _spread_z(a: np.ndarray, b: np.ndarray, lookback: int) -> float:
    n = min(len(a), len(b), lookback)
    if n < 20:
        return 0.0
    ratio = np.log(a[-n:]) - np.log(b[-n:])
    mu = ratio.mean()
    std = ratio.std()
    if std < 1e-10:
        return 0.0
    return (ratio[-1] - mu) / std


def compute(close_a: np.ndarray, close_b: np.ndarray,
            sym_a: str, sym_b: str) -> Signal:
    """
    z > +2: A expensive relative to B → short A (outperformer), long B (underperformer)
    z < -2: B expensive relative to A → short B, long A
    direction=1 means long-spread (long A, short B); -1 means short-spread.
    """
    if len(close_a) < 20 or len(close_b) < 20:
        return Signal(0, 0.0, "pairs_trading", "insufficient data")

    z = _spread_z(close_a, close_b, CORR_LOOKBACK)

    if z > SPREAD_STD_ENTRY:
        return Signal(-1, CONF_PAIRS, "pairs_trading",
                      f"short {sym_a}/long {sym_b} z={z:.2f} > {SPREAD_STD_ENTRY}")
    if z < -SPREAD_STD_ENTRY:
        return Signal(1, CONF_PAIRS, "pairs_trading",
                      f"long {sym_a}/short {sym_b} z={z:.2f} < -{SPREAD_STD_ENTRY}")
    return Signal(0, 0.0, "pairs_trading", f"{sym_a}/{sym_b} z={z:.2f} neutral")


def should_exit(close_a: np.ndarray, close_b: np.ndarray) -> bool:
    z = abs(_spread_z(close_a, close_b, CORR_LOOKBACK))
    return z < SPREAD_STD_EXIT


def spread_z(close_a: np.ndarray, close_b: np.ndarray) -> float:
    return _spread_z(close_a, close_b, CORR_LOOKBACK)
