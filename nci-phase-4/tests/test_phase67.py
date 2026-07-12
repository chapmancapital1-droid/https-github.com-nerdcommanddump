"""
Phase 6/7 tests: payoff engine, backtest engine, portfolio engine.

Covers:
  * payoff shape sanity for every StrategyType (straddle V, condor plateau,
    breakevens bracketing strikes, credit-spread max loss = width - credit,
    debit-spread max profit = width - debit, unbounded flags);
  * curve-vs-analytic reconciliation (recommendation numbers derive from the
    same curve the chart uses);
  * backtest determinism per seed, max-loss exit honoured, stat sanity;
  * Monte Carlo validation accepting a profitable and rejecting a losing series;
  * portfolio net-Greeks addition and budget / concentration / expiry / direction
    warnings;
  * serialization round-trips for every new dataclass.
"""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nci_strategy_selector import (
    MarketContext, UserPreferences, RiskProfile, StrategyType,
    StrategySelector, GreeksSummary,
    # payoff
    Leg, PayoffCurve, build_legs, payoff_curve, default_price_range,
    bachelier_price, net_entry_price, reconcile_payoff, curve_from_recommendation,
    CONTRACT_MULTIPLIER,
    # backtest
    Bar, BacktestPlan, BacktestTrade, BacktestResult, BacktestEngine,
    MCConfig, MCReport, synthetic_bars, bars_from_csv, realized_vol,
    reconstruct_context, validate,
    # portfolio
    Position, Portfolio, PortfolioAggregates, strategy_direction,
)


def ctx(price=100.0, em=5.0, **kw):
    base = dict(
        symbol="SPY", price=price, iv_rank=50, iv_trend=0.0,
        spot_trend=0.0, expected_move=em, liquidity_score=0.95,
    )
    base.update(kw)
    return MarketContext(**base)


def prefs(**kw):
    base = dict(
        symbol="SPY", risk_profile=RiskProfile.MODERATE,
        max_loss_pct=2.0, max_loss_dollars=100000.0,
        bias="neutral", time_horizon_days=30,
    )
    base.update(kw)
    return UserPreferences(**base)


def strikes_of(legs, right=None):
    return sorted(l.strike for l in legs if right is None or l.right == right)


# ── Bachelier pricing ─────────────────────────────────────────────────
class TestBachelier(unittest.TestCase):
    def test_put_call_parity(self):
        c = bachelier_price(100.0, 95.0, 5.0, "call")
        p = bachelier_price(100.0, 95.0, 5.0, "put")
        self.assertAlmostEqual(c - p, 100.0 - 95.0, places=6)

    def test_atm_call_equals_atm_put(self):
        c = bachelier_price(100.0, 100.0, 5.0, "call")
        p = bachelier_price(100.0, 100.0, 5.0, "put")
        self.assertAlmostEqual(c, p, places=6)
        self.assertGreater(c, 0.0)

    def test_deep_itm_call_near_intrinsic(self):
        c = bachelier_price(100.0, 50.0, 5.0, "call")
        self.assertAlmostEqual(c, 50.0, places=2)


# ── payoff shapes ─────────────────────────────────────────────────────
class TestPayoffShapes(unittest.TestCase):
    def _recon(self, st, **cxkw):
        c, p = ctx(**cxkw), prefs()
        legs = build_legs(st, c, p)
        return legs, reconcile_payoff(st, c, p, legs=legs)

    def test_all_strategies_produce_a_curve(self):
        for st in StrategyType:
            legs, r = self._recon(st)
            self.assertGreater(len(legs), 0, st)
            self.assertEqual(len(r.curve.prices), len(r.curve.pnl), st)
            self.assertGreaterEqual(r.max_profit, 0.0, st)
            self.assertGreaterEqual(r.max_loss, 0.0, st)

    def test_long_straddle_v_shape(self):
        legs, r = self._recon(StrategyType.LONG_STRADDLE)
        curve = r.curve
        # minimum P/L is at (or very near) the strike; wings are higher
        k = strikes_of(legs)[0]
        i_min = min(range(len(curve.pnl)), key=lambda i: curve.pnl[i])
        self.assertAlmostEqual(curve.prices[i_min], k, delta=k * 0.05)
        self.assertGreater(curve.pnl[0], curve.pnl[i_min])
        self.assertGreater(curve.pnl[-1], curve.pnl[i_min])
        # two breakevens bracketing the strike; unbounded upside
        self.assertEqual(len(curve.breakevens), 2)
        self.assertLess(curve.breakevens[0], k)
        self.assertGreater(curve.breakevens[1], k)
        self.assertTrue(curve.unbounded_gain)
        self.assertFalse(curve.unbounded_loss)

    def test_iron_condor_plateau_and_breakevens(self):
        legs, r = self._recon(StrategyType.IRON_CONDOR)
        curve = r.curve
        short_put = max(l.strike for l in legs if l.right == "put" and l.side == "short")
        short_call = min(l.strike for l in legs if l.right == "call" and l.side == "short")
        # flat max-profit plateau between the short strikes
        plateau = [curve.pnl[i] for i, pr in enumerate(curve.prices)
                   if short_put < pr < short_call]
        self.assertGreater(len(plateau), 1)
        self.assertAlmostEqual(max(plateau), min(plateau), delta=1.0)
        self.assertAlmostEqual(max(plateau), curve.max_profit, delta=1.0)
        # two breakevens, each between a short strike and its wing
        self.assertEqual(len(curve.breakevens), 2)
        self.assertLess(curve.breakevens[0], short_put)
        self.assertGreater(curve.breakevens[1], short_call)
        self.assertFalse(curve.unbounded_gain)
        self.assertFalse(curve.unbounded_loss)

    def test_credit_spread_max_loss_is_width_minus_credit(self):
        # bull put spread: width - credit, x100
        c, p = ctx(), prefs()
        legs = build_legs(StrategyType.BULL_PUT_SPREAD, c, p)
        entry = net_entry_price(legs, c.price, c.expected_move, p.time_horizon_days)
        width = max(strikes_of(legs)) - min(strikes_of(legs))
        credit = -entry  # entry is negative for a credit
        r = reconcile_payoff(StrategyType.BULL_PUT_SPREAD, c, p, legs=legs)
        expected_max_loss = (width - credit) * CONTRACT_MULTIPLIER
        self.assertAlmostEqual(r.max_loss, expected_max_loss, delta=1.0)
        self.assertAlmostEqual(r.max_profit, credit * CONTRACT_MULTIPLIER, delta=1.0)

    def test_debit_spread_max_profit_is_width_minus_debit(self):
        c, p = ctx(), prefs()
        legs = build_legs(StrategyType.BULL_CALL_SPREAD, c, p)
        entry = net_entry_price(legs, c.price, c.expected_move, p.time_horizon_days)
        width = max(strikes_of(legs)) - min(strikes_of(legs))
        r = reconcile_payoff(StrategyType.BULL_CALL_SPREAD, c, p, legs=legs)
        self.assertGreater(entry, 0.0)  # a debit
        self.assertAlmostEqual(r.max_profit, (width - entry) * CONTRACT_MULTIPLIER, delta=1.0)
        self.assertAlmostEqual(r.max_loss, entry * CONTRACT_MULTIPLIER, delta=1.0)

    def test_short_straddle_unbounded_loss(self):
        _, r = self._recon(StrategyType.SHORT_STRADDLE)
        self.assertTrue(r.curve.unbounded_loss)
        self.assertFalse(r.curve.unbounded_gain)

    def test_short_call_side_unbounded_via_bear_call_is_bounded(self):
        # bear call spread is a *defined-risk* credit spread — not unbounded
        _, r = self._recon(StrategyType.BEAR_CALL_SPREAD)
        self.assertFalse(r.curve.unbounded_loss)
        self.assertFalse(r.curve.unbounded_gain)

    def test_strangle_breakevens_bracket_both_strikes(self):
        legs, r = self._recon(StrategyType.LONG_STRANGLE)
        ks = strikes_of(legs)
        self.assertEqual(len(r.curve.breakevens), 2)
        self.assertLess(r.curve.breakevens[0], ks[0])
        self.assertGreater(r.curve.breakevens[1], ks[-1])

    def test_covered_call_profit_capped(self):
        legs, r = self._recon(StrategyType.COVERED_CALL)
        # capped upside (short call), no unbounded gain
        self.assertFalse(r.curve.unbounded_gain)
        self.assertGreater(r.max_profit, 0.0)


# ── reconciliation ────────────────────────────────────────────────────
class TestReconciliation(unittest.TestCase):
    def setUp(self):
        self.selector = StrategySelector()

    def test_recommendation_numbers_match_curve(self):
        c, p = ctx(price=450.0, em=12.0), prefs(max_loss_dollars=100000.0)
        for st in StrategyType:
            rec = self.selector.build_recommendation(st, c, p, fit_score=1.0, reasoning="x")
            recon = reconcile_payoff(st, c, p)
            self.assertAlmostEqual(rec.max_loss, round(recon.max_loss, 2), delta=0.01, msg=st)
            self.assertAlmostEqual(rec.max_profit, round(recon.max_profit, 2), delta=0.01, msg=st)
            self.assertAlmostEqual(rec.entry_price, round(recon.entry_price, 2), delta=0.01, msg=st)

    def test_legs_carry_side_and_are_priceable(self):
        c, p = ctx(), prefs()
        rec = self.selector.build_recommendation(
            StrategyType.IRON_CONDOR, c, p, fit_score=1.0, reasoning="x")
        for leg in rec.legs:
            self.assertIn("side", leg)
            self.assertIn(leg["side"], ("long", "short"))
            self.assertIn("right", leg)
            self.assertIn("strike", leg)
            self.assertIn("qty", leg)

    def test_curve_from_recommendation_reproduces_numbers(self):
        c, p = ctx(price=250.0, em=9.0), prefs(max_loss_dollars=100000.0)
        rec = self.selector.build_recommendation(
            StrategyType.BULL_CALL_SPREAD, c, p, fit_score=1.0, reasoning="x")
        curve = curve_from_recommendation(rec, spot=c.price)
        self.assertAlmostEqual(max(curve.max_profit, 0.0), rec.max_profit, delta=1.0)
        self.assertAlmostEqual(abs(min(curve.max_loss, 0.0)), rec.max_loss, delta=1.0)


# ── backtest ──────────────────────────────────────────────────────────
class TestBacktest(unittest.TestCase):
    def test_synthetic_bars_deterministic_per_seed(self):
        a = synthetic_bars("SPY", 300, seed=42, start_price=400.0)
        b = synthetic_bars("SPY", 300, seed=42, start_price=400.0)
        self.assertEqual([x.close for x in a], [x.close for x in b])
        c = synthetic_bars("SPY", 300, seed=43, start_price=400.0)
        self.assertNotEqual([x.close for x in a], [x.close for x in c])

    def test_synthetic_bars_skip_weekends(self):
        bars = synthetic_bars("SPY", 20, seed=1)
        import datetime as dt
        for bar in bars:
            self.assertLess(dt.date.fromisoformat(bar.date).weekday(), 5)

    def test_backtest_is_deterministic(self):
        bars = synthetic_bars("SPY", 500, seed=7, start_price=400.0)
        plan = BacktestPlan(bias="neutral", max_loss_dollars=5000.0)
        r1 = BacktestEngine().run("SPY", bars, plan)
        r2 = BacktestEngine().run("SPY", bars, plan)
        self.assertEqual(r1.stats, r2.stats)
        self.assertEqual([t.pnl for t in r1.trades], [t.pnl for t in r2.trades])

    def test_backtest_produces_trades_and_stats(self):
        bars = synthetic_bars("SPY", 500, seed=7, start_price=400.0)
        res = BacktestEngine().run("SPY", bars, BacktestPlan(bias="neutral"))
        self.assertGreater(res.stats["total_trades"], 0)
        self.assertGreaterEqual(res.stats["win_rate"], 0.0)
        self.assertLessEqual(res.stats["win_rate"], 1.0)
        self.assertEqual(len(res.equity_curve), len(bars))

    def test_max_loss_stop_is_honoured(self):
        bars = synthetic_bars("SPY", 500, seed=3, start_price=400.0)
        stop = 500.0
        plan = BacktestPlan(bias="neutral", max_loss_dollars=10000.0,
                            max_loss_stop=stop, holding_days=21)
        res = BacktestEngine().run("SPY", bars, plan)
        stopped = [t for t in res.trades if t.exit_reason == "max_loss_stop"]
        self.assertGreater(len(stopped), 0, "expected at least one stop-out over 2y")
        for t in stopped:
            # exit is booked on the breach day: realized loss <= -stop (approx)
            self.assertLessEqual(t.pnl, -stop + 1e-6)

    def test_iv_proxy_gate_reduces_entries(self):
        bars = synthetic_bars("SPY", 500, seed=9, start_price=400.0)
        base = BacktestEngine().run("SPY", bars, BacktestPlan(bias="neutral"))
        gated = BacktestEngine().run(
            "SPY", bars, BacktestPlan(bias="neutral", iv_proxy_min=80.0))
        self.assertLessEqual(gated.stats["total_trades"], base.stats["total_trades"])

    def test_realized_vol_positive_on_moving_series(self):
        closes = [100.0 * (1.01 ** i) for i in range(40)]
        self.assertGreater(realized_vol(closes), 0.0)

    def test_reconstruct_context_labels_iv_proxy(self):
        bars = synthetic_bars("SPY", 120, seed=5, start_price=100.0)
        c = reconstruct_context("SPY", bars, 100, vol_history=[0.1, 0.2, 0.3])
        self.assertGreaterEqual(c.iv_rank, 0.0)
        self.assertLessEqual(c.iv_rank, 100.0)
        self.assertGreater(c.expected_move, 0.0)

    def test_bars_from_csv_roundtrip(self):
        import tempfile, os
        bars = synthetic_bars("SPY", 10, seed=1)
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as fh:
            fh.write("date,open,high,low,close,volume\n")
            for b in bars:
                fh.write(f"{b.date},{b.open},{b.high},{b.low},{b.close},{b.volume}\n")
            path = fh.name
        try:
            loaded = bars_from_csv(path)
            self.assertEqual(len(loaded), len(bars))
            self.assertAlmostEqual(loaded[0].close, bars[0].close, places=4)
        finally:
            os.unlink(path)


# ── Monte Carlo gate ──────────────────────────────────────────────────
class TestMonteCarlo(unittest.TestCase):
    def _result(self, pnls):
        trades = [
            BacktestTrade(f"2022-01-{(i % 27) + 1:02d}", f"2022-02-{(i % 27) + 1:02d}",
                          "iron_condor", -1.0, 100.0, 101.0, pnl, "horizon")
            for i, pnl in enumerate(pnls)
        ]
        return BacktestResult("SPY", trades, [0.0], {})

    def test_accepts_profitable_series(self):
        pnls = ([100.0] * 28) + ([-80.0] * 12)
        rep = validate(self._result(pnls))
        self.assertTrue(rep.accepted, rep.reasons)
        self.assertGreater(rep.median_expectancy_r, 0.0)
        self.assertLessEqual(rep.ruin_probability, 0.02)

    def test_rejects_losing_series(self):
        pnls = ([-100.0] * 24) + ([50.0] * 16)
        rep = validate(self._result(pnls))
        self.assertFalse(rep.accepted)

    def test_insufficient_history_is_rejected(self):
        rep = validate(self._result([100.0] * 5))
        self.assertFalse(rep.accepted)
        self.assertEqual(rep.simulations, 0)

    def test_validate_is_deterministic(self):
        pnls = ([100.0] * 28) + ([-80.0] * 12)
        r1 = validate(self._result(pnls))
        r2 = validate(self._result(pnls))
        self.assertEqual(r1.to_dict(), r2.to_dict())

    def test_validate_on_real_backtest(self):
        bars = synthetic_bars("SPY", 504, seed=7, start_price=400.0)
        res = BacktestEngine().run("SPY", bars, BacktestPlan(bias="neutral"))
        rep = validate(res)
        self.assertIsInstance(rep, MCReport)
        self.assertGreater(rep.simulations, 0)
        self.assertTrue(rep.reasons)


# ── portfolio ─────────────────────────────────────────────────────────
class TestPortfolio(unittest.TestCase):
    def setUp(self):
        self.selector = StrategySelector()

    def _rec(self, st, symbol="SPY", price=100.0):
        c = ctx(symbol=symbol, price=price, em=5.0)
        p = prefs(symbol=symbol, max_loss_dollars=100000.0)
        return self.selector.build_recommendation(st, c, p, fit_score=1.0, reasoning="x")

    def test_net_greeks_add_with_quantity(self):
        rec = self._rec(StrategyType.BULL_CALL_SPREAD)
        pf = Portfolio(account_size=100000.0)
        pf.add(Position(rec, qty=2))
        pf.add(Position(rec, qty=3))
        net = pf.net_greeks()
        self.assertAlmostEqual(net.delta, rec.greeks.delta * 5, places=4)
        self.assertAlmostEqual(net.vega, rec.greeks.vega * 5, places=4)

    def test_closed_positions_excluded_from_aggregates(self):
        rec = self._rec(StrategyType.BULL_CALL_SPREAD)
        pf = Portfolio(account_size=100000.0)
        pf.add(Position(rec, qty=1))
        pf.add(Position(rec, qty=1))
        before = pf.total_max_loss()
        pf.close(0)
        self.assertAlmostEqual(pf.total_max_loss(), before / 2, delta=0.01)
        self.assertEqual(len(pf.closed_trades), 1)

    def test_budget_warning_triggers(self):
        # small account so budget is tight
        rec = self._rec(StrategyType.LONG_STRADDLE, price=100.0)
        pf = Portfolio(account_size=2000.0)  # budget = 300
        cand = Position(rec, qty=10)          # max loss ~ 4000 >> 300
        warnings = pf.check(cand)
        self.assertTrue(any("BUDGET" in w for w in warnings), warnings)

    def test_concentration_warning_triggers(self):
        rec = self._rec(StrategyType.IRON_CONDOR, symbol="SPY", price=100.0)
        pf = Portfolio(account_size=100000.0)  # budget 15000
        # load SPY up near single-name cap already
        pf.add(Position(rec, qty=20))
        cand = Position(self._rec(StrategyType.IRON_CONDOR, symbol="SPY"), qty=20)
        warnings = pf.check(cand)
        self.assertTrue(any("CONCENTRATION" in w for w in warnings), warnings)

    def test_direction_warning_triggers(self):
        pf = Portfolio(account_size=100000.0)
        bull = self._rec(StrategyType.BULL_CALL_SPREAD, symbol="AAA")
        pf.add(Position(bull, qty=30))
        cand = Position(self._rec(StrategyType.BULL_PUT_SPREAD, symbol="BBB"), qty=30)
        warnings = pf.check(cand)
        self.assertTrue(any("DIRECTION" in w for w in warnings), warnings)

    def test_expiry_cluster_warning_triggers(self):
        pf = Portfolio(account_size=100000.0)
        # all near-expiry structures stack into the same expiry window
        rec = self._rec(StrategyType.IRON_CONDOR, symbol="SPY")
        pf.add(Position(rec, qty=15))
        cand = Position(self._rec(StrategyType.IRON_CONDOR, symbol="QQQ"), qty=15)
        warnings = pf.check(cand)
        self.assertTrue(any("EXPIRY" in w for w in warnings), warnings)

    def test_clean_candidate_has_no_warnings(self):
        pf = Portfolio(account_size=1000000.0)  # huge budget
        cand = Position(self._rec(StrategyType.BULL_CALL_SPREAD), qty=1)
        self.assertEqual(pf.check(cand), [])

    def test_suggest_flags_over_budget(self):
        rec = self._rec(StrategyType.LONG_STRADDLE, price=100.0)
        pf = Portfolio(account_size=2000.0)
        pf.add(Position(rec, qty=10))
        sug = pf.suggest()
        self.assertTrue(any("budget" in s.lower() for s in sug), sug)

    def test_suggest_flat_portfolio(self):
        pf = Portfolio(account_size=100000.0)
        self.assertTrue(any("flat" in s.lower() for s in pf.suggest()))

    def test_strategy_direction_map(self):
        self.assertEqual(strategy_direction(StrategyType.BULL_CALL_SPREAD), "bullish")
        self.assertEqual(strategy_direction(StrategyType.BEAR_CALL_SPREAD), "bearish")
        self.assertEqual(strategy_direction(StrategyType.IRON_CONDOR), "neutral")


# ── serialization round-trips ─────────────────────────────────────────
class TestSerialization(unittest.TestCase):
    def test_leg_roundtrip(self):
        leg = Leg("call", 100.0, 2, "short", "near", "SPY")
        self.assertEqual(Leg.from_dict(leg.to_dict()), leg)

    def test_payoff_curve_roundtrip(self):
        c, p = ctx(), prefs()
        legs = build_legs(StrategyType.IRON_CONDOR, c, p)
        entry = net_entry_price(legs, c.price, c.expected_move, p.time_horizon_days)
        curve = payoff_curve(legs, entry, default_price_range(legs, c.price))
        back = PayoffCurve.from_dict(curve.to_dict())
        self.assertEqual(back.breakevens, [round(b, 4) for b in curve.breakevens])
        self.assertEqual(back.unbounded_gain, curve.unbounded_gain)

    def test_backtest_plan_roundtrip(self):
        plan = BacktestPlan(bias="bullish", iv_proxy_min=60.0,
                            risk_profile=RiskProfile.AGGRESSIVE)
        back = BacktestPlan.from_dict(plan.to_dict())
        self.assertEqual(back.bias, "bullish")
        self.assertEqual(back.risk_profile, RiskProfile.AGGRESSIVE)
        self.assertEqual(back.iv_proxy_min, 60.0)

    def test_backtest_result_roundtrip(self):
        bars = synthetic_bars("SPY", 300, seed=2, start_price=400.0)
        res = BacktestEngine().run("SPY", bars, BacktestPlan(bias="neutral"))
        back = BacktestResult.from_dict(res.to_dict())
        self.assertEqual(len(back.trades), len(res.trades))
        self.assertEqual(back.stats["total_trades"], res.stats["total_trades"])

    def test_mc_config_roundtrip(self):
        cfg = MCConfig(simulations=1000, seed=99)
        back = MCConfig.from_dict(cfg.to_dict())
        self.assertEqual(back.simulations, 1000)
        self.assertEqual(back.seed, 99)

    def test_portfolio_roundtrip(self):
        selector = StrategySelector()
        c, p = ctx(), prefs(max_loss_dollars=100000.0)
        rec = selector.build_recommendation(
            StrategyType.IRON_CONDOR, c, p, fit_score=1.0, reasoning="x")
        pf = Portfolio(account_size=100000.0)
        pf.add(Position(rec, qty=2))
        pf.add(Position(rec, qty=1))
        pf.close(1)
        back = Portfolio.from_dict(pf.to_dict())
        self.assertEqual(back.account_size, pf.account_size)
        self.assertEqual(len(back.positions), 2)
        self.assertEqual(len(back.closed_trades), 1)
        self.assertAlmostEqual(back.net_greeks().delta, pf.net_greeks().delta, places=4)

    def test_position_roundtrip(self):
        selector = StrategySelector()
        c, p = ctx(), prefs(max_loss_dollars=100000.0)
        rec = selector.build_recommendation(
            StrategyType.BULL_PUT_SPREAD, c, p, fit_score=1.0, reasoning="x")
        pos = Position(rec, qty=3, symbol="SPY")
        back = Position.from_dict(pos.to_dict())
        self.assertEqual(back.qty, 3)
        self.assertEqual(back.symbol, "SPY")
        self.assertEqual(back.recommendation.strategy, StrategyType.BULL_PUT_SPREAD)


if __name__ == "__main__":
    unittest.main()
