"""
HybridOrchestrator — decides WHO trades and WHETHER we're in rescue mode.

Rescue mode triggers when any of:
  * loss streak >= rescue_loss_streak (from TradeMemory)
  * the pool is degraded (no ACTIVE agents)
  * drawdown crosses rescue_drawdown_pct (before the hard circuit breaker)

While in rescue mode the designated rescue agent (conservative generalist)
takes the book, and normal selection resumes only after a recovery trade
count with net-positive R.
"""

from __future__ import annotations

from .agents.base import BaseTradingAgent
from .memory import TradeMemory
from .models import MarketSnapshot, RegimeState, Signal
from .pool import AgentPool


class HybridOrchestrator:
    def __init__(
        self,
        pool: AgentPool,
        memory: TradeMemory,
        rescue_agent_name: str = "Hybrid_Rescue",
        rescue_loss_streak: int = 4,
        rescue_drawdown_pct: float = 8.0,
        recovery_trades: int = 5,
    ):
        self.pool = pool
        self.memory = memory
        self.rescue_agent_name = rescue_agent_name
        self.rescue_loss_streak = rescue_loss_streak
        self.rescue_drawdown_pct = rescue_drawdown_pct
        self.recovery_trades = recovery_trades

        self.rescue_mode = False
        # Lifetime trade count when rescue started. Uses memory.total_recorded
        # (monotonic), NOT len(memory): the ring buffer pins len() at capacity,
        # which froze trades_since at 0 and locked rescue mode on permanently.
        self._rescue_entered_at_count = 0

    # -- rescue state machine ------------------------------------------------

    def _should_enter_rescue(self, drawdown_pct: float) -> str | None:
        if self.memory.current_loss_streak() >= self.rescue_loss_streak:
            return (
                f"loss streak {self.memory.current_loss_streak()} "
                f">= {self.rescue_loss_streak}"
            )
        if self.pool.is_degraded():
            return "agent pool degraded (no active agents)"
        if drawdown_pct >= self.rescue_drawdown_pct:
            return f"drawdown {drawdown_pct:.1f}% >= {self.rescue_drawdown_pct}%"
        return None

    def _should_exit_rescue(self) -> bool:
        trades_since = self.memory.total_recorded - self._rescue_entered_at_count
        if trades_since < self.recovery_trades:
            return False
        # Judge recovery on the buffered tail (capped at capacity if the
        # rescue stretch outlived the ring buffer).
        recent = self.memory.recent(min(trades_since, self.memory.capacity))
        net_r = sum(t.pnl_r for t in recent)
        return net_r > 0 and self.memory.current_loss_streak() == 0

    # -- main entry -------------------------------------------------------------

    def choose(
        self,
        regime: RegimeState,
        snap: MarketSnapshot,
        drawdown_pct: float,
    ) -> tuple[BaseTradingAgent | None, Signal, list[str]]:
        """Return (agent, proposed signal, reasoning notes)."""
        notes: list[str] = []

        if self.rescue_mode and self._should_exit_rescue():
            self.rescue_mode = False
            notes.append("rescue recovery complete → normal selection resumed")

        if not self.rescue_mode:
            reason = self._should_enter_rescue(drawdown_pct)
            if reason:
                self.rescue_mode = True
                self._rescue_entered_at_count = self.memory.total_recorded
                notes.append(f"RESCUE MODE engaged: {reason}")

        if self.rescue_mode:
            agent = self.pool.agents.get(self.rescue_agent_name)
            if agent is None:
                notes.append("rescue agent missing — standing down flat")
                return None, Signal.FLAT, notes
            signal = agent.propose(regime, snap)
            notes.append(f"rescue agent {agent.name} proposes {signal.value}")
            return agent, signal, notes

        agent, sel_notes = self.pool.select_primary_agent(regime)
        notes.extend(sel_notes)
        if agent is None:
            return None, Signal.FLAT, notes

        signal = agent.propose(regime, snap)
        notes.append(f"{agent.name} proposes {signal.value} in {regime.regime.value}")
        return agent, signal, notes

    def state(self) -> dict:
        return {
            "rescue_mode": self.rescue_mode,
            "rescue_agent": self.rescue_agent_name,
            "rescue_entered_at_count": self._rescue_entered_at_count,
            "loss_streak": self.memory.current_loss_streak(),
            "pool_health": self.pool.health(),
        }
