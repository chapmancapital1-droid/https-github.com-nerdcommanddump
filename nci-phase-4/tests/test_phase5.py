"""
Phase 5 tests: Claude client, multi-turn reasoning, confidence calibration.

The Claude API is never actually called — tests use a stub client so the
suite is deterministic and offline.
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nci_strategy_selector import (
    StrategyType,
    RiskProfile,
    MarketContext,
    UserPreferences,
    TradeOutcome,
    QuantumAIBrain,
    ClaudeReasoningClient,
    ConfidenceCalibrator,
    ReasoningSession,
)
from nci_strategy_selector.claude_client import ClaudeResponse


class StubClaudeClient(ClaudeReasoningClient):
    """Fake client that records calls and returns canned answers."""

    def __init__(self, canned_text="Stubbed AI reasoning.", fail=False):
        super().__init__(api_key="stub-key")
        self.canned_text = canned_text
        self.fail = fail
        self.calls: list[dict] = []

    def complete(self, messages, system=None, temperature=0.3):
        self.calls.append({"messages": messages, "system": system})
        if self.fail:
            return ClaudeResponse(text="", model=self.model, ok=False, error="stub failure")
        return ClaudeResponse(text=self.canned_text, model=self.model, ok=True)


def make_context(**overrides) -> MarketContext:
    base = dict(
        symbol="SPY", price=450.0, iv_rank=65, iv_trend=0.2,
        spot_trend=0.4, expected_move=12.0, liquidity_score=0.92,
    )
    base.update(overrides)
    return MarketContext(**base)


def make_prefs(**overrides) -> UserPreferences:
    base = dict(
        symbol="SPY", risk_profile=RiskProfile.MODERATE,
        max_loss_pct=2.0, max_loss_dollars=1000.0,
        bias="bullish", time_horizon_days=30,
    )
    base.update(overrides)
    return UserPreferences(**base)


def make_outcome(rec_id: str, strategy: StrategyType, pnl: float) -> TradeOutcome:
    return TradeOutcome(
        recommendation_id=rec_id,
        symbol="SPY",
        strategy=strategy,
        entry_price=1.0,
        exit_price=1.0 + pnl / 100,
        pnl=pnl,
        pnl_pct=pnl,
        lessons_learned="",
        user_rating=5 if pnl > 0 else 2,
    )


class TestClaudeClient(unittest.TestCase):
    def test_unavailable_without_key(self):
        client = ClaudeReasoningClient(api_key="")
        self.assertFalse(client.available)

    def test_complete_without_key_returns_error_not_raise(self):
        client = ClaudeReasoningClient(api_key="")
        resp = client.complete(messages=[{"role": "user", "content": "hi"}])
        self.assertFalse(resp.ok)
        self.assertIn("API key", resp.error)

    def test_available_with_key(self):
        client = ClaudeReasoningClient(api_key="sk-test")
        self.assertTrue(client.available)


class TestClaudeIntegration(unittest.TestCase):
    def test_select_and_reason_uses_claude_when_available(self):
        stub = StubClaudeClient(canned_text="AI says: bull put spread fits best.")
        brain = QuantumAIBrain(claude_client=stub)
        result = brain.select_and_reason(make_context(), make_prefs(), use_claude=True)

        self.assertEqual(len(stub.calls), 1)
        self.assertIn("bull put spread fits best", result.ai_reasoning)

    def test_select_and_reason_falls_back_on_api_failure(self):
        stub = StubClaudeClient(fail=True)
        brain = QuantumAIBrain(claude_client=stub)
        result = brain.select_and_reason(make_context(), make_prefs(), use_claude=True)

        # Falls back to template, labeled with the failure
        self.assertIn("Claude unavailable", result.ai_reasoning)
        self.assertIn("Market Assessment", result.ai_reasoning)

    def test_offline_client_uses_template(self):
        brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
        result = brain.select_and_reason(make_context(), make_prefs(), use_claude=True)
        self.assertIn("Market Assessment", result.ai_reasoning)


class TestReasoningSession(unittest.TestCase):
    def _make_session(self, client) -> ReasoningSession:
        brain = QuantumAIBrain(claude_client=client)
        context, prefs = make_context(), make_prefs()
        result = brain.select_and_reason(context, prefs, use_claude=False)
        return brain.start_reasoning_session(context, prefs, result)

    def test_multi_turn_history_grows(self):
        session = self._make_session(StubClaudeClient())
        session.ask("Why this ranking?")
        session.ask("What if IV drops?")
        # 2 user + 2 assistant turns
        self.assertEqual(len(session.turns), 4)
        roles = [t.role for t in session.turns]
        self.assertEqual(roles, ["user", "assistant", "user", "assistant"])

    def test_claude_receives_grounding_and_history(self):
        stub = StubClaudeClient()
        session = self._make_session(stub)
        session.ask("Why this ranking?")
        session.ask("What about theta?")

        second_call = stub.calls[1]["messages"]
        # grounding block + 3 dialogue turns (u, a, u)
        self.assertEqual(len(second_call), 4)
        self.assertIn("MARKET CONTEXT", second_call[0]["content"])
        self.assertEqual(second_call[-1]["content"], "What about theta?")

    def test_offline_answers_are_deterministic_and_labeled(self):
        session = self._make_session(ClaudeReasoningClient(api_key=""))
        answer = session.ask("What's the worst case loss?")
        self.assertIn("offline mode", answer)
        self.assertIn("$", answer)

    def test_api_failure_mid_session_falls_back_with_label(self):
        stub = StubClaudeClient(fail=True)
        session = self._make_session(stub)
        answer = session.ask("Why this ranking?")
        self.assertIn("offline fallback", answer)

    def test_transcript_serializes(self):
        session = self._make_session(StubClaudeClient())
        session.ask("Why?")
        transcript = session.transcript()
        self.assertEqual(len(transcript), 2)
        self.assertIn("role", transcript[0])
        self.assertIn("content", transcript[0])


class TestConfidenceCalibration(unittest.TestCase):
    def test_neutral_below_min_samples(self):
        cal = ConfidenceCalibrator()
        strategy = StrategyType.BULL_CALL_SPREAD
        cal.observe(strategy, 0.9, make_outcome("r1", strategy, -50))
        cal.observe(strategy, 0.9, make_outcome("r2", strategy, -50))
        # Only 2 samples — no adjustment yet
        self.assertEqual(cal.adjust(strategy, 0.8), 0.8)

    def test_overconfidence_gets_trimmed(self):
        cal = ConfidenceCalibrator()
        strategy = StrategyType.BULL_CALL_SPREAD
        # Predicted 90% confidence, but everything loses
        for i in range(10):
            cal.observe(strategy, 0.9, make_outcome(f"r{i}", strategy, -50))
        adjusted = cal.adjust(strategy, 0.8)
        self.assertLess(adjusted, 0.8)

    def test_underconfidence_gets_boosted(self):
        cal = ConfidenceCalibrator()
        strategy = StrategyType.IRON_CONDOR
        # Predicted 50% confidence, but everything wins
        for i in range(10):
            cal.observe(strategy, 0.5, make_outcome(f"r{i}", strategy, 50))
        adjusted = cal.adjust(strategy, 0.6)
        self.assertGreater(adjusted, 0.6)

    def test_adjusted_confidence_stays_in_bounds(self):
        cal = ConfidenceCalibrator()
        strategy = StrategyType.IRON_CONDOR
        for i in range(20):
            cal.observe(strategy, 0.3, make_outcome(f"r{i}", strategy, 50))
        self.assertLessEqual(cal.adjust(strategy, 0.99), 1.0)
        self.assertGreaterEqual(cal.adjust(strategy, 0.01), 0.05)

    def test_calibration_round_trips_serialization(self):
        cal = ConfidenceCalibrator()
        strategy = StrategyType.BULL_CALL_SPREAD
        for i in range(5):
            cal.observe(strategy, 0.8, make_outcome(f"r{i}", strategy, 50))
        restored = ConfidenceCalibrator.from_dict(cal.to_dict())
        self.assertEqual(
            restored.records[strategy.value].factor,
            cal.records[strategy.value].factor,
        )


class TestCalibrationLoopThroughBrain(unittest.TestCase):
    def test_prediction_outcome_loop(self):
        brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
        context, prefs = make_context(), make_prefs()
        result = brain.select_and_reason(context, prefs, use_claude=False)
        top = result.recommendations[0]

        # User takes the trade — register the prediction
        brain.register_prediction("trade-1", top)
        self.assertIn("trade-1", brain._pending_predictions)

        # Trade closes — calibration observes automatically
        brain.record_trade_outcome(make_outcome("trade-1", top.strategy, -50))
        self.assertNotIn("trade-1", brain._pending_predictions)
        self.assertEqual(brain.calibrator.records[top.strategy.value].samples, 1)

    def test_unregistered_outcome_does_not_calibrate(self):
        brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
        brain.record_trade_outcome(
            make_outcome("unknown-id", StrategyType.COVERED_CALL, 50)
        )
        self.assertEqual(len(brain.calibrator.records), 0)

    def test_calibration_survives_serialization(self):
        brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
        strategy = StrategyType.BULL_CALL_SPREAD
        for i in range(5):
            brain.calibrator.observe(strategy, 0.9, make_outcome(f"r{i}", strategy, -50))

        state = brain.to_dict()
        brain2 = QuantumAIBrain.from_dict(state)
        self.assertIn(strategy.value, brain2.calibrator.records)
        self.assertEqual(
            brain2.calibrator.records[strategy.value].samples, 5
        )

    def test_calibrated_confidence_affects_future_selections(self):
        brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
        context, prefs = make_context(), make_prefs()

        baseline = brain.select_and_reason(context, prefs, use_claude=False)
        top_strategy = baseline.recommendations[0].strategy
        baseline_conf = baseline.recommendations[0].confidence_score

        # Hammer the top strategy with losses at high predicted confidence
        for i in range(10):
            brain.calibrator.observe(
                top_strategy, 0.95, make_outcome(f"r{i}", top_strategy, -50)
            )

        rerun = brain.select_and_reason(context, prefs, use_claude=False)
        rerun_conf = {
            r.strategy: r.confidence_score for r in rerun.recommendations
        }.get(top_strategy)

        if rerun_conf is not None:
            self.assertLess(rerun_conf, baseline_conf)


if __name__ == "__main__":
    unittest.main()
