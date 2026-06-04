"""Risk management: triangle entry state machine, unified ATR trailing stop,
3-trade scalp counter, and daily P&L limits.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import numpy as np

from config import (
    ATR_PERIOD, ATR_STOP_MULT,
    DAILY_MAX_LOSS_USD, DAILY_TARGET_USD,
    LOT_TINY, MAX_SCALPS,
    TRIANGLE_ENTRY2_LOTS, TRIANGLE_ENTRY3_LOTS, TRIANGLE_FAVOR_PIPS,
)

logger = logging.getLogger(__name__)


class TriangleState(Enum):
    FLAT       = auto()
    ENTRY1     = auto()   # 0.01 lots in
    ENTRY2     = auto()   # 0.04 lots in (added 0.03)
    ENTRY3     = auto()   # 0.07 lots in (added 0.03 more)
    CLOSED     = auto()


@dataclass
class TrianglePosition:
    direction: int          # 1=long, -1=short
    entry_price: float
    state: TriangleState = TriangleState.ENTRY1
    total_lots: float = LOT_TINY
    stop_price: float = 0.0
    highest_favorable: float = 0.0   # tracks best price for add-on trigger

    def pip_move(self, current_price: float) -> float:
        """Favorable pip movement from entry (positive = in our direction)."""
        raw = (current_price - self.entry_price) * self.direction
        return raw * 10_000   # approximate pip conversion (works for 4-decimal pairs)

    def update_stop(self, current_price: float, atr: float) -> None:
        """Trail stop only in favorable direction."""
        stop_dist = atr * ATR_STOP_MULT
        if self.direction == 1:
            candidate = current_price - stop_dist
            if candidate > self.stop_price:
                self.stop_price = candidate
        else:
            candidate = current_price + stop_dist
            if self.stop_price == 0.0 or candidate < self.stop_price:
                self.stop_price = candidate

    def is_stopped(self, current_price: float) -> bool:
        if self.stop_price == 0.0:
            return False
        if self.direction == 1:
            return current_price <= self.stop_price
        return current_price >= self.stop_price


@dataclass
class RiskManager:
    daily_pnl: float = 0.0
    scalp_count: int = 0
    position: Optional[TrianglePosition] = None

    def reset_daily(self) -> None:
        self.daily_pnl = 0.0
        self.scalp_count = 0
        logger.info("Daily counters reset")

    @property
    def daily_limit_hit(self) -> bool:
        return self.daily_pnl <= -DAILY_MAX_LOSS_USD

    @property
    def daily_target_hit(self) -> bool:
        return self.daily_pnl >= DAILY_TARGET_USD

    @property
    def scalp_limit_hit(self) -> bool:
        return self.scalp_count >= MAX_SCALPS

    def can_trade(self) -> bool:
        if self.daily_limit_hit:
            logger.warning("Daily loss limit reached — trading halted")
            return False
        if self.daily_target_hit:
            logger.info("Daily target hit — reducing risk")
            return False
        if self.scalp_limit_hit:
            logger.info("3-scalp limit hit — standing down")
            return False
        return self.position is None

    def open_position(self, direction: int, entry_price: float, atr: float) -> TrianglePosition:
        pos = TrianglePosition(direction=direction, entry_price=entry_price,
                               total_lots=LOT_TINY)
        pos.update_stop(entry_price, atr)
        pos.highest_favorable = entry_price
        self.position = pos
        logger.info("Triangle entry 1: %s @ %.5f  stop=%.5f  lots=%.2f",
                    "BUY" if direction == 1 else "SELL", entry_price,
                    pos.stop_price, pos.total_lots)
        return pos

    def tick(self, current_price: float, atr: float) -> dict:
        """Call on every price update. Returns action dict."""
        pos = self.position
        if pos is None or pos.state == TriangleState.CLOSED:
            return {"action": "none"}

        pos.update_stop(current_price, atr)

        if pos.is_stopped(current_price):
            result = self._close_position(current_price, reason="stop_hit")
            return {"action": "close", **result}

        pips = pos.pip_move(current_price)

        if pos.state == TriangleState.ENTRY1 and pips >= TRIANGLE_FAVOR_PIPS:
            pos.total_lots += TRIANGLE_ENTRY2_LOTS
            pos.state = TriangleState.ENTRY2
            logger.info("Triangle add-on 2: +%.2f lots @ %.5f  total=%.2f",
                        TRIANGLE_ENTRY2_LOTS, current_price, pos.total_lots)
            return {"action": "add", "lots": TRIANGLE_ENTRY2_LOTS, "price": current_price}

        if pos.state == TriangleState.ENTRY2 and pips >= TRIANGLE_FAVOR_PIPS * 2:
            pos.total_lots += TRIANGLE_ENTRY3_LOTS
            pos.state = TriangleState.ENTRY3
            logger.info("Triangle add-on 3: +%.2f lots @ %.5f  total=%.2f  FULL",
                        TRIANGLE_ENTRY3_LOTS, current_price, pos.total_lots)
            return {"action": "add", "lots": TRIANGLE_ENTRY3_LOTS, "price": current_price}

        return {"action": "hold", "pips": pips, "stop": pos.stop_price}

    def record_scalp_win(self, pnl: float) -> None:
        self.daily_pnl += pnl
        self.scalp_count += 1
        logger.info("Scalp win #%d  pnl=+%.2f  daily=%.2f", self.scalp_count, pnl, self.daily_pnl)
        if self.position:
            self._close_position(0.0, reason="scalp_win")

    def close_for_exit_signal(self, current_price: float) -> dict:
        return self._close_position(current_price, reason="exit_signal")

    def _close_position(self, current_price: float, reason: str) -> dict:
        pos = self.position
        if pos is None:
            return {}
        pnl_pips = pos.pip_move(current_price)
        pos.state = TriangleState.CLOSED
        self.position = None
        logger.info("Position closed: reason=%s  pips=%.1f  lots=%.2f",
                    reason, pnl_pips, pos.total_lots)
        return {"reason": reason, "pips": pnl_pips, "lots": pos.total_lots}


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
        period: int = ATR_PERIOD) -> float:
    """Compute current ATR value (Wilder's method, simplified)."""
    n = min(len(high), len(low), len(close), period + 1)
    if n < 2:
        return 0.001
    tr = np.maximum(high[-n:] - low[-n:],
         np.maximum(abs(high[-n:] - np.roll(close[-n:], 1)),
                    abs(low[-n:]  - np.roll(close[-n:], 1))))
    return float(tr[1:].mean())
