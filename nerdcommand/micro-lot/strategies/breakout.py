"""Strategy 1: Breakout Trader — 20-day high/low breakout.

Entry:  price crosses above PERIOD-day high  → BUY
        price crosses below PERIOD-day low   → SELL
Exit:   price closes below 50-day MA (for longs) OR 3 scalps done.
Win rate expectation: 50-55%.
"""
import numpy as np

from config import BREAKOUT_PERIOD, CONF_BREAKOUT, MA_EXIT_PERIOD
from strategies import Signal


def compute(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> Signal:
    needed = BREAKOUT_PERIOD + 1
    if len(close) < needed:
        return Signal(0, 0.0, "breakout", "insufficient data")

    period_high = high[-needed:-1].max()
    period_low  = low[-needed:-1].min()
    cur = close[-1]
    prev = close[-2]

    if prev <= period_high and cur > period_high:
        return Signal(1, CONF_BREAKOUT, "breakout",
                      f"broke above {BREAKOUT_PERIOD}d high {period_high:.5f}")
    if prev >= period_low and cur < period_low:
        return Signal(-1, CONF_BREAKOUT, "breakout",
                      f"broke below {BREAKOUT_PERIOD}d low {period_low:.5f}")
    return Signal(0, 0.0, "breakout", "no breakout")


def should_exit(close: np.ndarray, direction: int) -> bool:
    if len(close) < MA_EXIT_PERIOD:
        return False
    ma50 = close[-MA_EXIT_PERIOD:].mean()
    if direction == 1:
        return close[-1] < ma50
    return close[-1] > ma50
