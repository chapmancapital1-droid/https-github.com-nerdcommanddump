"""Strategy 3: Crypto / high-volatility RSI mean reversion.

Entry:  RSI(14) < 30 (oversold) → BUY
        RSI(14) > 70 (overbought) → SELL
Exit:   RSI crosses 50 OR 3 scalps done.
Win rate expectation: 48-52%.
"""
import numpy as np

from config import CONF_MEAN_REV, RSI_MID, RSI_OVERBOUGHT, RSI_OVERSOLD, RSI_PERIOD
from strategies import Signal


def _rsi(close: np.ndarray, period: int) -> float:
    if len(close) < period + 1:
        return 50.0
    delta = np.diff(close[-(period + 1):])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain.mean()
    avg_loss = loss.mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute(close: np.ndarray) -> Signal:
    if len(close) < RSI_PERIOD + 1:
        return Signal(0, 0.0, "mean_reversion", "insufficient data")

    rsi = _rsi(close, RSI_PERIOD)
    prev_rsi = _rsi(close[:-1], RSI_PERIOD)

    if prev_rsi >= RSI_OVERSOLD and rsi < RSI_OVERSOLD:
        return Signal(1, CONF_MEAN_REV, "mean_reversion",
                      f"RSI crossed below {RSI_OVERSOLD} ({rsi:.1f})")
    if prev_rsi <= RSI_OVERBOUGHT and rsi > RSI_OVERBOUGHT:
        return Signal(-1, CONF_MEAN_REV, "mean_reversion",
                      f"RSI crossed above {RSI_OVERBOUGHT} ({rsi:.1f})")
    return Signal(0, 0.0, "mean_reversion", f"RSI={rsi:.1f} neutral")


def should_exit(close: np.ndarray, direction: int) -> bool:
    if len(close) < RSI_PERIOD + 2:
        return False
    rsi = _rsi(close, RSI_PERIOD)
    prev_rsi = _rsi(close[:-1], RSI_PERIOD)
    if direction == 1:
        return prev_rsi < RSI_MID and rsi >= RSI_MID
    return prev_rsi > RSI_MID and rsi <= RSI_MID


def rsi_value(close: np.ndarray) -> float:
    return _rsi(close, RSI_PERIOD)
