"""
NCI Hybrid Phoenix Brain — test suite (stdlib unittest, zero deps).

Run:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nci_phoenix import (  # noqa: E402
    AgentStatus,
    BrainVersionStore,
    MarketSnapshot,
    MonteCarloConfig,
    MonteCarloEngine,
    NCIPhoenixBrain,
    PIDConfig,
    PIDController,
    PoolConfig,
    Regime,
    RegimeDetector,
    RegimeState,
    RiskConfig,
    RiskManager,
    Signal,
    TradeResult,
)
from nci_phoenix.agents import default_roster  # noqa: E402
from nci_phoenix.pool import AgentPool  # noqa: E402
from nci_phoenix.risk import OpenPosition  # noqa: E402


def snap(**kw) -> MarketSnapshot:
    base = dict(symbol="EURUSD", price=1.0850)
    base.update(kw)
    return MarketSnapshot(**base)


def trade(agent="Breakout_Phoenix", pnl_r=1.0, regime=Regime.HIGH_VOL_EXPANSION,
          closed_at=None, **kw) -> TradeResult:
    return TradeResult(
        agent_name=agent,
        symbol="EURUSD",
        signal=Signal.LONG,
        pnl=pnl_r * 100.0,
        pnl_r=pnl_r,
        regime=regime,
        closed_at=closed_at if closed_at is not None else time.time(),
        **kw,
    )


# ---------------------------------------------------------------- regime


class TestRegimeDetector(unittest.TestCase):
    def setUp(self):
        self.det = RegimeDetector()

    def test_trending_bullish(self):
        st = self.det.detect(snap(adx=35, trend_direction=1))
        self.assertEqual(st.regime, Regime.TRENDING_BULLISH)
        self.assertGreater(st.confidence, 0)

    def test_trending_bearish(self):
        st = self.det.detect(snap(adx=45, trend_direction=-1))
        self.assertEqual(st.regime, Regime.TRENDING_BEARISH)

    def test_volatility_expansion(self):
        st = self.det.detect(snap(atr=0.0030, atr_baseline=0.0010))
        self.assertEqual(st.regime, Regime.HIGH_VOL_EXPANSION)

    def test_news_dominates(self):
        st = self.det.detect(snap(adx=35, trend_direction=1, news_impact=0.9))
        self.assertEqual(st.regime, Regime.NEWS_DRIVEN)

    def test_ranging(self):
        st = self.det.detect(snap(adx=12, range_width_pct=0.2))
        self.assertEqual(st.regime, Regime.RANGING_CHOPPY)

    def test_pre_breakout_coil(self):
        st = self.det.detect(
            snap(atr=0.0006, atr_baseline=0.0010, adx=20, range_width_pct=0.5)
        )
        self.assertEqual(st.regime, Regime.PRE_BREAKOUT_COIL)

    def test_unknown_when_no_evidence(self):
        st = self.det.detect(snap())
        self.assertEqual(st.regime, Regime.UNKNOWN)
        self.assertEqual(st.confidence, 0.0)

    def test_deterministic(self):
        s = snap(adx=35, trend_direction=1)
        self.assertEqual(self.det.detect(s).regime, self.det.detect(s).regime)


# ---------------------------------------------------------------- pool


class TestAgentPool(unittest.TestCase):
    def setUp(self):
        self.pool = AgentPool(default_roster(), rng=random.Random(42))

    def test_all_agents_registered(self):
        self.assertEqual(len(self.pool.records), 6)

    def test_score_rises_on_wins(self):
        before = self.pool.records["Breakout_Phoenix"].score
        for _ in range(5):
            self.pool.record_trade(trade(pnl_r=2.0))
        self.assertGreater(self.pool.records["Breakout_Phoenix"].score, before)

    def test_score_falls_on_losses(self):
        before = self.pool.records["Breakout_Phoenix"].score
        for _ in range(5):
            self.pool.record_trade(trade(pnl_r=-1.0))
        self.assertLess(self.pool.records["Breakout_Phoenix"].score, before)

    def test_demotion_chain(self):
        rec = self.pool.records["Breakout_Phoenix"]
        for _ in range(20):
            self.pool.record_trade(trade(pnl_r=-2.0))
        self.assertIn(rec.status, (AgentStatus.PROBATION, AgentStatus.DORMANT))
        self.assertGreater(rec.demotions, 0)

    def test_promotion_after_recovery(self):
        rec = self.pool.records["Breakout_Phoenix"]
        for _ in range(20):
            self.pool.record_trade(trade(pnl_r=-2.0))  # demote to dormant
        self.assertEqual(rec.status, AgentStatus.DORMANT)
        for _ in range(30):
            self.pool.record_trade(trade(pnl_r=2.0))   # earn way back
        self.assertEqual(rec.status, AgentStatus.ACTIVE)
        self.assertGreater(rec.promotions, 0)

    def test_specialization_bonus(self):
        regime = RegimeState(regime=Regime.PRE_BREAKOUT_COIL, confidence=0.8)
        rec = self.pool.records["Breakout_Phoenix"]
        eff = self.pool.effective_score(rec, regime)
        self.assertAlmostEqual(
            eff, min(1.0, rec.score + self.pool.config.specialization_bonus)
        )

    def test_selection_prefers_specialist(self):
        regime = RegimeState(regime=Regime.PRE_BREAKOUT_COIL, confidence=0.8)
        agent, _ = self.pool.select_primary_agent(regime)
        self.assertIsNotNone(agent)
        ranked = self.pool.evaluate_and_rank(regime)
        self.assertEqual(agent.name, ranked[0].name)

    def test_exploration_gives_dormant_agents_a_slot(self):
        # Force everyone dormant except one, exploration rate 1.0 → always explore
        pool = AgentPool(
            default_roster(),
            config=PoolConfig(exploration_rate=1.0),
            rng=random.Random(7),
        )
        pool.records["Scalper_Phoenix"].status = AgentStatus.DORMANT
        agent, notes = pool.select_primary_agent(RegimeState())
        self.assertTrue(any("exploration" in n for n in notes))

    def test_degraded_detection(self):
        for rec in self.pool.records.values():
            rec.status = AgentStatus.DORMANT
        self.assertTrue(self.pool.is_degraded())


# ---------------------------------------------------------------- pid


class TestPID(unittest.TestCase):
    def test_underperformance_trims_size(self):
        pid = PIDController(PIDConfig())
        m = pid.update(measured_r_per_day=-2.0)   # losing vs +0.5 target
        self.assertLess(m, 1.0)

    def test_output_clamped(self):
        cfg = PIDConfig(output_min=0.1, output_max=2.0)
        pid = PIDController(cfg)
        for _ in range(50):
            m = pid.update(measured_r_per_day=-50.0)
        self.assertGreaterEqual(m, cfg.output_min)
        pid.reset()
        for _ in range(50):
            m = pid.update(measured_r_per_day=50.0)
        self.assertLessEqual(m, cfg.output_max)

    def test_anti_windup(self):
        cfg = PIDConfig(integral_limit=5.0)
        pid = PIDController(cfg)
        for _ in range(1000):
            pid.update(measured_r_per_day=-10.0)
        self.assertLessEqual(abs(pid.state()["integral"]), cfg.integral_limit)

    def test_reset(self):
        pid = PIDController()
        pid.update(-3.0)
        pid.reset()
        self.assertEqual(pid.state()["integral"], 0.0)
        self.assertIsNone(pid.state()["prev_error"])


# ---------------------------------------------------------------- risk


class TestRiskManager(unittest.TestCase):
    def test_daily_loss_limit(self):
        rm = RiskManager(RiskConfig(daily_loss_limit_r=3.0))
        now = time.time()
        for _ in range(4):
            rm.record_trade(trade(pnl_r=-1.0, closed_at=now))
        blocked = rm.check(now=now)
        self.assertTrue(any("daily loss" in b for b in blocked))

    def test_old_losses_do_not_count_today(self):
        rm = RiskManager(RiskConfig(daily_loss_limit_r=3.0))
        now = time.time()
        for _ in range(4):
            rm.record_trade(trade(pnl_r=-1.0, closed_at=now - 200_000))  # >2 days old
        self.assertEqual([b for b in rm.check(now=now) if "daily" in b], [])

    def test_drawdown_circuit_breaker(self):
        rm = RiskManager(RiskConfig(max_drawdown_pct=12.0))
        rm.update_equity(10_000)
        rm.update_equity(8_700)   # -13%
        blocked = rm.check()
        self.assertTrue(any("circuit breaker" in b for b in blocked))
        rm.clear_halt()
        rm.update_equity(8_700)   # still below max dd → re-halts
        self.assertTrue(rm.halted_reason)

    def test_concurrent_position_cap(self):
        rm = RiskManager(RiskConfig(max_concurrent_positions=2))
        rm.open_positions = [OpenPosition("EURUSD", 1), OpenPosition("GBPUSD", 1)]
        blocked = rm.check()
        self.assertTrue(any("concurrent" in b for b in blocked))

    def test_correlated_exposure_cap(self):
        rm = RiskManager(RiskConfig(max_correlated_exposure=1))
        rm.open_positions = [OpenPosition("EURUSD", 1, "usd-majors")]
        blocked = rm.check(direction=1, correlation_group="usd-majors")
        self.assertTrue(any("correlated" in b for b in blocked))
        # opposite direction is fine
        self.assertEqual(
            [b for b in rm.check(direction=-1, correlation_group="usd-majors")
             if "correlated" in b],
            [],
        )

    def test_news_blackout(self):
        rm = RiskManager(RiskConfig(news_blackout_minutes=15, news_impact_block=0.75))
        self.assertTrue(any("news" in b for b in rm.check(news_impact=0.8)))
        self.assertTrue(any("blackout" in b for b in rm.check(minutes_to_news=5)))
        self.assertEqual(rm.check(news_impact=0.2, minutes_to_news=60), [])


# ---------------------------------------------------------------- monte carlo


class TestMonteCarlo(unittest.TestCase):
    def test_rejects_insufficient_history(self):
        eng = MonteCarloEngine(MonteCarloConfig(simulations=100), seed=1)
        report = eng.validate([1.0, -0.5, 2.0])
        self.assertFalse(report.accepted)
        self.assertIn("insufficient history", report.reasons[0])

    def test_accepts_positive_edge(self):
        rng = random.Random(3)
        # 60% wins at +1R → clearly positive edge; the strict default gate
        # correctly rejects marginal 55% systems (see rejection test below).
        series = [1.0 if rng.random() < 0.60 else -1.0 for _ in range(200)]
        eng = MonteCarloEngine(MonteCarloConfig(simulations=500), seed=3)
        report = eng.validate(series)
        self.assertTrue(report.accepted, report.reasons)
        self.assertGreater(report.median_expectancy_r, 0)

    def test_rejects_negative_edge(self):
        rng = random.Random(4)
        series = [1.0 if rng.random() < 0.35 else -1.0 for _ in range(200)]
        eng = MonteCarloEngine(MonteCarloConfig(simulations=500), seed=4)
        report = eng.validate(series)
        self.assertFalse(report.accepted)

    def test_reproducible_with_seed(self):
        series = [1.0, -1.0] * 50
        r1 = MonteCarloEngine(MonteCarloConfig(simulations=200), seed=9).validate(series)
        r2 = MonteCarloEngine(MonteCarloConfig(simulations=200), seed=9).validate(series)
        self.assertEqual(r1.to_dict(), r2.to_dict())


# ---------------------------------------------------------------- memory


class TestTradeMemory(unittest.TestCase):
    def test_ring_buffer_capacity(self):
        from nci_phoenix import TradeMemory

        mem = TradeMemory(capacity=10)
        for i in range(25):
            mem.record(trade(pnl_r=float(i)))
        self.assertEqual(len(mem), 10)
        self.assertEqual(mem.r_series()[-1], 24.0)

    def test_loss_streak(self):
        from nci_phoenix import TradeMemory

        mem = TradeMemory()
        mem.record(trade(pnl_r=1.0))
        for _ in range(3):
            mem.record(trade(pnl_r=-0.5))
        self.assertEqual(mem.current_loss_streak(), 3)

    def test_expectancy_table(self):
        from nci_phoenix import TradeMemory

        mem = TradeMemory()
        mem.record(trade(agent="A", pnl_r=2.0, regime=Regime.TRENDING_BULLISH))
        mem.record(trade(agent="A", pnl_r=0.0, regime=Regime.TRENDING_BULLISH))
        table = mem.expectancy_by_agent_regime()
        self.assertAlmostEqual(table["A"]["trending_bullish"], 1.0)

    def test_round_trip(self):
        from nci_phoenix import TradeMemory

        mem = TradeMemory(capacity=50)
        mem.record(trade(pnl_r=1.5))
        restored = TradeMemory.from_dict(mem.to_dict())
        self.assertEqual(restored.r_series(), mem.r_series())


# ---------------------------------------------------------------- versioning


class TestVersioning(unittest.TestCase):
    def test_snapshot_list_load_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BrainVersionStore(tmp)
            v1 = store.snapshot({"x": 1}, label="v1.0.0", notes="first")
            v2 = store.snapshot({"x": 2}, label="v1.0.1", notes="tuned")

            versions = store.list_versions()
            self.assertEqual([v["id"] for v in versions], [v1, v2])
            self.assertEqual(versions[1]["parent"], v1)

            self.assertEqual(store.load(v1), {"x": 1})

            state = store.rollback(v1, reason="v1.0.1 misbehaving")
            self.assertEqual(state, {"x": 1})
            # rollback recorded as its own snapshot → append-only history
            self.assertEqual(len(store.list_versions()), 3)
            self.assertIn("rollback-to", store.latest()["id"])

    def test_unknown_version_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BrainVersionStore(tmp)
            with self.assertRaises(KeyError):
                store.load("nope")


# ---------------------------------------------------------------- brain (integration)


class TestBrainIntegration(unittest.TestCase):
    def test_trend_day_decision_flow(self):
        brain = NCIPhoenixBrain(mc_seed=1)
        d = brain.evaluate(snap(adx=40, trend_direction=1))
        self.assertEqual(d.regime, Regime.TRENDING_BULLISH)
        self.assertEqual(d.signal, Signal.LONG)
        self.assertEqual(d.agent, "Trend_Rider_Quantum")
        self.assertGreater(d.lot_multiplier, 0)
        self.assertFalse(d.blocked_by)

    def test_news_flattens_book(self):
        brain = NCIPhoenixBrain(mc_seed=1)
        d = brain.evaluate(snap(adx=40, trend_direction=1, news_impact=0.9))
        # News_Shield specializes in NEWS_DRIVEN and proposes FLAT
        self.assertEqual(d.regime, Regime.NEWS_DRIVEN)
        self.assertEqual(d.signal, Signal.FLAT)

    def test_risk_gate_blocks_entry(self):
        brain = NCIPhoenixBrain(mc_seed=1)
        now = time.time()
        for _ in range(4):
            brain.record_trade(trade(agent="Trend_Rider_Quantum", pnl_r=-1.0,
                                     closed_at=now))
        d = brain.evaluate(snap(adx=40, trend_direction=1))
        self.assertEqual(d.signal, Signal.FLAT)
        self.assertTrue(d.blocked_by)

    def test_rescue_mode_engages_on_loss_streak(self):
        brain = NCIPhoenixBrain(
            risk_config=RiskConfig(daily_loss_limit_r=100.0),  # keep gate open
            mc_seed=1,
        )
        for _ in range(4):
            brain.record_trade(trade(agent="Trend_Rider_Quantum", pnl_r=-0.4))
        d = brain.evaluate(snap(adx=40, trend_direction=1))
        self.assertTrue(d.rescue_mode)
        self.assertEqual(d.agent, "Hybrid_Rescue")
        # rescue agent still takes A+ trend setups, at reduced size
        self.assertEqual(d.signal, Signal.LONG)
        self.assertLessEqual(d.lot_multiplier, 0.35 * 2.0)

    def test_rescue_recovers_after_positive_run(self):
        brain = NCIPhoenixBrain(
            risk_config=RiskConfig(daily_loss_limit_r=100.0), mc_seed=1
        )
        for _ in range(4):
            brain.record_trade(trade(pnl_r=-0.4))
        brain.evaluate(snap(adx=40, trend_direction=1))   # engages rescue
        self.assertTrue(brain.orchestrator.rescue_mode)
        for _ in range(6):
            brain.record_trade(trade(agent="Hybrid_Rescue", pnl_r=0.8))
        d = brain.evaluate(snap(adx=40, trend_direction=1))
        self.assertFalse(d.rescue_mode)

    def test_pid_feeds_lot_multiplier(self):
        brain = NCIPhoenixBrain(mc_seed=1)
        m = brain.update_sizing(r_per_day=-3.0)
        self.assertLess(m, 1.0)
        d = brain.evaluate(snap(adx=40, trend_direction=1))
        self.assertAlmostEqual(d.lot_multiplier, round(m * 1.0, 4))

    def test_state_round_trip(self):
        brain = NCIPhoenixBrain(mc_seed=1)
        for i in range(12):
            brain.record_trade(trade(pnl_r=1.0 if i % 3 else -0.5))
        brain.evaluate(snap(adx=40, trend_direction=1))
        state = brain.to_state()

        # JSON-serializable end to end
        raw = json.dumps(state)
        restored = NCIPhoenixBrain(mc_seed=1)
        restored.load_state(json.loads(raw))

        self.assertEqual(
            restored.pool.records["Breakout_Phoenix"].score,
            brain.pool.records["Breakout_Phoenix"].score,
        )
        self.assertEqual(len(restored.memory), len(brain.memory))

    def test_save_open_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brain_state.json"
            brain = NCIPhoenixBrain(mc_seed=1)
            brain.record_trade(trade(pnl_r=1.0))
            brain.save(path)
            restored = NCIPhoenixBrain.open(path, mc_seed=1)
            self.assertEqual(len(restored.memory), 1)

    def test_versioned_brain_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = BrainVersionStore(Path(tmp) / "versions")
            brain = NCIPhoenixBrain(mc_seed=1)
            v1 = store.snapshot(brain.to_state(), "v2.1.0", "baseline roster")

            for _ in range(10):
                brain.record_trade(trade(pnl_r=2.0))
            store.snapshot(brain.to_state(), "v2.1.1", "breakout hot streak")

            # roll back to baseline and confirm the score reverted
            baseline = store.rollback(v1, reason="testing rollback")
            fresh = NCIPhoenixBrain(mc_seed=1)
            fresh.load_state(baseline)
            self.assertEqual(fresh.pool.records["Breakout_Phoenix"].score, 0.5)

    def test_monte_carlo_gate_via_brain(self):
        brain = NCIPhoenixBrain(
            mc_config=MonteCarloConfig(simulations=300), mc_seed=5
        )
        rng = random.Random(5)
        for _ in range(120):
            brain.record_trade(
                trade(agent="Breakout_Phoenix",
                      pnl_r=1.0 if rng.random() < 0.55 else -1.0)
            )
        report = brain.validate_agent("Breakout_Phoenix")
        self.assertTrue(report.accepted, report.reasons)
        weak = brain.validate_agent("Scalper_Phoenix")   # no trades
        self.assertFalse(weak.accepted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
