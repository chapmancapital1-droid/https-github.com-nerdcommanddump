"""
NCIPhoenixBrain — the facade the EA, dashboard tab, and dev team call.

Decision loop per evaluation (tick, bar close, or timer):

    snapshot ─→ RegimeDetector ─→ HybridOrchestrator ─→ RiskManager ─→ PID
                                     │ (agent + signal)     │ (gates)    │ (size)
                                     └─────────────→ Decision ←──────────┘

Learning loop per closed trade:

    TradeResult ─→ TradeMemory + AgentPool.record_trade + RiskManager
                       │
                       └─→ (periodic) MonteCarloEngine.validate before any
                            agent promotion or parameter change goes live

Persistence:
    * `to_state()` / `load_state()` — full JSON round-trip
    * `save()` / `NCIPhoenixBrain.open()` — file-backed convenience
    * `BrainVersionStore` — snapshot / rollback (see versioning.py)

Educational analysis tooling — not investment advice. The brain proposes;
a human (or the human-approved EA risk envelope) disposes.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .agents.base import BaseTradingAgent
from .agents.library import default_roster
from .memory import TradeMemory
from .models import (
    AgentRecord,
    BrainMeta,
    Decision,
    MarketSnapshot,
    MonteCarloConfig,
    PIDConfig,
    PoolConfig,
    RegimeState,
    RiskConfig,
    Signal,
    TradeResult,
)
from .montecarlo import MonteCarloEngine, MonteCarloReport
from .orchestrator import HybridOrchestrator
from .pid import PIDController
from .pool import AgentPool
from .regime import RegimeDetector
from .risk import RiskManager


class NCIPhoenixBrain:
    def __init__(
        self,
        agents: list[BaseTradingAgent] | None = None,
        meta: BrainMeta | None = None,
        pool_config: PoolConfig | None = None,
        pid_config: PIDConfig | None = None,
        risk_config: RiskConfig | None = None,
        mc_config: MonteCarloConfig | None = None,
        mc_seed: int | None = None,
    ):
        self.meta = meta or BrainMeta()
        roster = agents if agents is not None else default_roster()

        self.detector = RegimeDetector()
        self.memory = TradeMemory()
        self.pool = AgentPool(roster, config=pool_config)
        self.orchestrator = HybridOrchestrator(self.pool, self.memory)
        self.risk = RiskManager(risk_config)
        self.pid = PIDController(pid_config)
        self.montecarlo = MonteCarloEngine(mc_config, seed=mc_seed)

        self.last_regime = RegimeState()
        self.last_decision: Decision | None = None
        self._lot_multiplier = 1.0

    # ------------------------------------------------------------------ decide

    def evaluate(
        self,
        snap: MarketSnapshot,
        minutes_to_news: float | None = None,
        correlation_group: str = "",
    ) -> Decision:
        """One full pass of the decision loop. Never raises on market data."""
        regime = self.detector.detect(snap)
        self.last_regime = regime

        agent, signal, notes = self.orchestrator.choose(
            regime, snap, self.risk.drawdown_pct()
        )

        decision = Decision(
            signal=Signal.FLAT,
            agent=agent.name if agent else "",
            regime=regime.regime,
            rescue_mode=self.orchestrator.rescue_mode,
            reasoning=list(regime.notes) + notes,
        )

        if agent is None or signal is Signal.FLAT:
            decision.reasoning.append("no actionable signal — staying flat")
            self.last_decision = decision
            return decision

        direction = 1 if signal is Signal.LONG else -1
        blocked = self.risk.check(
            news_impact=snap.news_impact,
            minutes_to_news=minutes_to_news,
            direction=direction,
            correlation_group=correlation_group,
        )
        if blocked:
            decision.blocked_by = blocked
            decision.reasoning.append(f"risk gates blocked entry: {blocked}")
            self.last_decision = decision
            return decision

        agent_fraction = agent.risk_fraction(regime, snap)
        decision.signal = signal
        decision.lot_multiplier = round(self._lot_multiplier * agent_fraction, 4)
        decision.reasoning.append(
            f"sizing: pid {self._lot_multiplier:.2f} × agent {agent_fraction:.2f} "
            f"= {decision.lot_multiplier:.2f}× base lot"
        )
        self.last_decision = decision
        return decision

    # ------------------------------------------------------------------- learn

    def record_trade(self, result: TradeResult) -> None:
        """Feed a closed trade into every learning surface at once."""
        self.memory.record(result)
        self.pool.record_trade(result)
        self.risk.record_trade(result)

    def update_equity(self, equity: float) -> None:
        self.risk.update_equity(equity)

    def update_sizing(self, r_per_day: float, dt_days: float = 1.0) -> float:
        """Feed the PID with the latest equity slope; returns new multiplier."""
        self._lot_multiplier = self.pid.update(r_per_day, dt_days)
        return self._lot_multiplier

    def validate_agent(self, agent_name: str) -> MonteCarloReport:
        """Monte-Carlo gate for one agent's realized R-series."""
        return self.montecarlo.validate(self.memory.r_series(agent_name))

    def validate_book(self) -> MonteCarloReport:
        """Monte-Carlo gate over the whole book's R-series."""
        return self.montecarlo.validate(self.memory.r_series())

    # ------------------------------------------------------------- persistence

    def to_state(self) -> dict[str, Any]:
        """Full brain state — the JSON the dashboard tab and versioning use."""
        return {
            "meta": self.meta.to_dict(),
            "pool": self.pool.to_dict(),
            "memory": self.memory.to_dict(),
            "pid": self.pid.state(),
            "risk": self.risk.state(),
            "orchestrator": self.orchestrator.state(),
            "current_state": {
                "regime": self.last_regime.to_dict(),
                "last_decision": (
                    self.last_decision.to_dict() if self.last_decision else None
                ),
                "lot_multiplier": self._lot_multiplier,
                "saved_at": time.time(),
            },
        }

    def load_state(self, state: dict[str, Any]) -> None:
        """Restore pool records, memory, and configs from a state dump."""
        meta = state.get("meta")
        if meta:
            self.meta = BrainMeta.from_dict(meta)

        pool = state.get("pool", {})
        if "config" in pool:
            self.pool.config = PoolConfig.from_dict(pool["config"])
        for name, rec in pool.get("records", {}).items():
            self.pool.records[name] = AgentRecord.from_dict(rec)

        if "memory" in state:
            self.memory = TradeMemory.from_dict(state["memory"])
            # re-point the orchestrator at the restored memory
            self.orchestrator.memory = self.memory

        risk_state = state.get("risk", {})
        if "config" in risk_state:
            self.risk.config = RiskConfig.from_dict(risk_state["config"])
        # Safety-critical: a brain saved halted or in drawdown must reload
        # halted — otherwise the circuit breaker silently resets.
        self.risk.restore(risk_state)

        pid_state = state.get("pid", {})
        if "config" in pid_state:
            self.pid.config = PIDConfig.from_dict(pid_state["config"])
        self.pid._integral = float(pid_state.get("integral", 0.0))
        prev = pid_state.get("prev_error")
        self.pid._prev_error = float(prev) if prev is not None else None

        orch = state.get("orchestrator", {})
        self.orchestrator.rescue_mode = bool(orch.get("rescue_mode", False))
        self.orchestrator._rescue_entered_at_count = int(
            orch.get("rescue_entered_at_count", 0)
        )

        cs = state.get("current_state", {})
        self._lot_multiplier = float(cs.get("lot_multiplier", 1.0))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_state(), indent=2))

    @classmethod
    def open(cls, path: str | Path, **kwargs: Any) -> "NCIPhoenixBrain":
        brain = cls(**kwargs)
        brain.load_state(json.loads(Path(path).read_text()))
        return brain
