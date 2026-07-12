"""
Regression tests for the code-review findings (2026-07-12 review pass).

Each test locks in the fix for one confirmed finding:
  - rescue mode lockup when the trade ring buffer is full
  - save/load dropping halt, rescue, PID, and loss-window state
  - version-id collisions within the same second
  - Monte Carlo p95 index bias with tiny simulation counts
"""

import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nci_phoenix import (  # noqa: E402
    BrainVersionStore,
    MarketSnapshot,
    MonteCarloConfig,
    NCIPhoenixBrain,
    Regime,
    RiskConfig,
    Signal,
    TradeResult,
)
from nci_phoenix.memory import TradeMemory  # noqa: E402
from nci_phoenix.montecarlo import MonteCarloEngine  # noqa: E402
from nci_phoenix.orchestrator import HybridOrchestrator  # noqa: E402
from nci_phoenix.pool import AgentPool  # noqa: E402
from nci_phoenix.agents.library import default_roster  # noqa: E402


def trade(agent="Trend_Rider_Quantum", pnl_r=1.0, regime=Regime.TRENDING_BULLISH):
    return TradeResult(
        agent_name=agent,
        symbol="EURUSD",
        signal=Signal.LONG,
        pnl=pnl_r * 100,
        pnl_r=pnl_r,
        regime=regime,
    )


def snap(**kw):
    base = dict(
        symbol="EURUSD", price=1.0850, adx=38, trend_direction=1,
        atr=0.0011, atr_baseline=0.0010, session="london",
    )
    base.update(kw)
    return MarketSnapshot(**base)


class TestRescueExitWithFullBuffer(unittest.TestCase):
    """Finding: rescue could never exit once len(memory) hit capacity."""

    def test_rescue_recovers_after_buffer_is_full(self):
        memory = TradeMemory(capacity=5)
        pool = AgentPool(default_roster())
        orch = HybridOrchestrator(pool, memory)

        # Fill the buffer completely with losses → rescue engages at full len.
        for _ in range(5):
            memory.record(trade(pnl_r=-1.0))
        agent, signal, notes = orch.choose(
            regime=_regime_state(), snap=snap(), drawdown_pct=0.0
        )
        self.assertTrue(orch.rescue_mode)

        # Buffer stays pinned at capacity while wins come in — the old
        # len()-based counter froze trades_since at 0 here, locking rescue on.
        for _ in range(6):
            memory.record(trade(agent="Hybrid_Rescue", pnl_r=0.7,
                                regime=Regime.TRENDING_BEARISH))
        agent, signal, notes = orch.choose(
            regime=_regime_state(), snap=snap(), drawdown_pct=0.0
        )
        self.assertFalse(orch.rescue_mode)

    def test_total_recorded_survives_serialization(self):
        memory = TradeMemory(capacity=3)
        for _ in range(7):
            memory.record(trade())
        self.assertEqual(memory.total_recorded, 7)
        restored = TradeMemory.from_dict(memory.to_dict())
        self.assertEqual(restored.total_recorded, 7)
        self.assertEqual(len(restored), 3)


class TestSafetyStateRoundTrip(unittest.TestCase):
    """Finding: halt, rescue, PID, and loss-window state lost on reload."""

    def test_circuit_breaker_survives_reload(self):
        brain = NCIPhoenixBrain()
        brain.update_equity(100_000)
        brain.update_equity(80_000)  # 20% DD >= 12% default → halted
        self.assertIsNotNone(brain.risk.halted_reason)

        brain2 = NCIPhoenixBrain()
        brain2.load_state(brain.to_state())
        self.assertEqual(brain2.risk.halted_reason, brain.risk.halted_reason)
        self.assertEqual(brain2.risk.equity_high_water, 100_000)
        self.assertEqual(brain2.risk.current_equity, 80_000)
        # Reloaded brain must still block trading.
        self.assertTrue(brain2.risk.check())

    def test_rescue_mode_survives_reload(self):
        brain = NCIPhoenixBrain()
        for _ in range(4):
            brain.record_trade(trade(pnl_r=-1.0))
        brain.evaluate(snap())  # engages rescue
        self.assertTrue(brain.orchestrator.rescue_mode)

        brain2 = NCIPhoenixBrain()
        brain2.load_state(brain.to_state())
        self.assertTrue(brain2.orchestrator.rescue_mode)

    def test_pid_state_survives_reload(self):
        brain = NCIPhoenixBrain()
        brain.update_sizing(r_per_day=-1.5)
        self.assertNotEqual(brain.pid._integral, 0.0)

        brain2 = NCIPhoenixBrain()
        brain2.load_state(brain.to_state())
        self.assertEqual(brain2.pid._integral, brain.pid._integral)
        self.assertEqual(brain2.pid._prev_error, brain.pid._prev_error)

    def test_loss_window_ledger_survives_reload(self):
        brain = NCIPhoenixBrain(risk_config=RiskConfig(daily_loss_limit_r=3.0))
        for _ in range(4):
            brain.record_trade(trade(pnl_r=-1.0))
        self.assertTrue(brain.risk.check())  # daily limit tripped

        brain2 = NCIPhoenixBrain()
        brain2.load_state(brain.to_state())
        # The old load_state dropped _closed → limits silently reset.
        self.assertTrue(brain2.risk.check())


class TestVersionIdCollisions(unittest.TestCase):
    """Finding: same label + same second overwrote the earlier snapshot."""

    def test_same_second_snapshots_get_distinct_ids(self):
        brain = NCIPhoenixBrain()
        with tempfile.TemporaryDirectory() as tmp:
            store = BrainVersionStore(tmp)
            ids = [store.snapshot(brain.to_state(), "v1", f"snap {i}")
                   for i in range(3)]
            self.assertEqual(len(set(ids)), 3)
            index_ids = [e["id"] for e in store.list_versions()]
            self.assertEqual(index_ids, ids)
            for vid in ids:
                store.load(vid)  # every snapshot file must exist


class TestMonteCarloP95(unittest.TestCase):
    """Finding: p95 index '-1' returned the max for tiny simulation counts."""

    def test_single_simulation_does_not_wrap_to_max(self):
        engine = MonteCarloEngine(
            MonteCarloConfig(simulations=1, block_size=2), seed=7
        )
        series = [1.0, -1.0] * 15
        report = engine.validate(series)
        # With one path, p95 == median == that path's DD; must not crash
        # or index [-1].
        self.assertGreaterEqual(report.p95_max_drawdown_r, 0.0)

    def test_p95_at_least_median(self):
        engine = MonteCarloEngine(
            MonteCarloConfig(simulations=500, block_size=5), seed=7
        )
        series = [1.5, -1.0, 1.0, -1.0, 2.0] * 10
        report = engine.validate(series)
        self.assertGreaterEqual(
            report.p95_max_drawdown_r, report.median_max_drawdown_r
        )


def _regime_state():
    from nci_phoenix.models import RegimeState
    return RegimeState(regime=Regime.TRENDING_BULLISH, confidence=0.8)


if __name__ == "__main__":
    unittest.main()
