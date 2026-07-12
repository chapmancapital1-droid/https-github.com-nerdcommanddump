"""
Trade memory — the brain's learning substrate.

Ring buffer of the last N closed trades (default 250) plus aggregate
pattern statistics the orchestrator and dashboard query:

  * per (agent, regime) expectancy — which agent actually earns in which tape
  * streak tracking — consecutive wins/losses feeding rescue triggers
  * rolling R-series export — the input to Monte Carlo validation

Serializes to a plain dict for the brain-state JSON.
"""

from __future__ import annotations

from collections import deque

from .models import TradeResult


class TradeMemory:
    def __init__(self, capacity: int = 250):
        self.capacity = capacity
        self._trades: deque[TradeResult] = deque(maxlen=capacity)
        # Monotonic lifetime counter — unlike len(), never capped by the ring
        # buffer, so "trades since X" stays correct after the buffer fills.
        self.total_recorded = 0

    # -- writes -------------------------------------------------------------

    def record(self, result: TradeResult) -> None:
        self._trades.append(result)
        self.total_recorded += 1

    # -- reads --------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._trades)

    def r_series(self, agent_name: str | None = None) -> list[float]:
        """Chronological R-multiples, optionally for one agent (MC input)."""
        return [
            t.pnl_r
            for t in self._trades
            if agent_name is None or t.agent_name == agent_name
        ]

    def current_loss_streak(self) -> int:
        streak = 0
        for t in reversed(self._trades):
            if t.pnl_r < 0:
                streak += 1
            else:
                break
        return streak

    def expectancy_by_agent_regime(self) -> dict[str, dict[str, float]]:
        """{agent: {regime: mean R}} — the pattern table the tab renders."""
        sums: dict[tuple[str, str], list[float]] = {}
        for t in self._trades:
            sums.setdefault((t.agent_name, t.regime.value), []).append(t.pnl_r)
        out: dict[str, dict[str, float]] = {}
        for (agent, regime), rs in sums.items():
            out.setdefault(agent, {})[regime] = round(sum(rs) / len(rs), 4)
        return out

    def recent(self, n: int = 20) -> list[TradeResult]:
        return list(self._trades)[-n:]

    # -- persistence -----------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "capacity": self.capacity,
            "total_recorded": self.total_recorded,
            "trades": [t.to_dict() for t in self._trades],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TradeMemory":
        mem = cls(capacity=int(d.get("capacity", 250)))
        for td in d.get("trades", []):
            mem.record(TradeResult.from_dict(td))
        # Restore the lifetime counter (record() above counted only the
        # buffered trades; older states without the field keep that count).
        mem.total_recorded = int(d.get("total_recorded", mem.total_recorded))
        return mem
