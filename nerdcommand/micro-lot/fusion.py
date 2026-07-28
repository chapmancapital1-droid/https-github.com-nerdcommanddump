"""Signal fusion — aggregate all 4 strategy signals into a single trade decision.

Rules:
  total_conf = sum of confidence weights from agreeing active signals
  total_conf <= CONF_SKIP_MAX  → skip (single low-confidence signal)
  total_conf >= CONF_HIGH_MIN  → full size  (0.07 lots)
  total_conf >= CONF_MED_MIN   → med size   (0.04 lots)
  else                         → skip
"""
from dataclasses import dataclass
from typing import List

from config import (
    CONF_HIGH_MIN, CONF_MED_MIN, CONF_SKIP_MAX,
    LOT_FULL, LOT_MED, LOT_TINY,
)
from strategies import Signal


@dataclass
class FusedSignal:
    direction: int        # 1=buy, -1=sell, 0=flat
    total_conf: float
    lot_size: float       # 0.0 = skip
    signals: List[Signal]
    reason: str

    @property
    def should_trade(self) -> bool:
        return self.lot_size > 0.0


def fuse(signals: List[Signal]) -> FusedSignal:
    """Aggregate strategy signals. Conflicting directions cancel each other."""
    buy_signals  = [s for s in signals if s.direction ==  1]
    sell_signals = [s for s in signals if s.direction == -1]

    buy_conf  = sum(s.confidence for s in buy_signals)
    sell_conf = sum(s.confidence for s in sell_signals)

    if buy_conf > sell_conf:
        direction   = 1
        total_conf  = buy_conf
        active      = buy_signals
    elif sell_conf > buy_conf:
        direction   = -1
        total_conf  = sell_conf
        active      = sell_signals
    else:
        return FusedSignal(0, 0.0, 0.0, signals, "no consensus")

    if total_conf <= CONF_SKIP_MAX:
        return FusedSignal(0, total_conf, 0.0, active,
                           f"conf={total_conf:.2f} below skip threshold {CONF_SKIP_MAX}")

    if total_conf >= CONF_HIGH_MIN:
        lot_size = LOT_FULL
        tier = "HIGH"
    elif total_conf >= CONF_MED_MIN:
        lot_size = LOT_MED + LOT_TINY   # 0.04
        tier = "MED"
    else:
        return FusedSignal(0, total_conf, 0.0, active,
                           f"conf={total_conf:.2f} below med threshold {CONF_MED_MIN}")

    strategies = ", ".join(s.strategy for s in active)
    reason = (f"{tier} conf={total_conf:.2f} dir={'BUY' if direction==1 else 'SELL'} "
              f"via [{strategies}] → {lot_size} lots")
    return FusedSignal(direction, total_conf, lot_size, active, reason)
