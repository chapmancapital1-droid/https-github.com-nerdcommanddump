"""
Unit tests for the dashboard service layer (transport-agnostic).

These force the offline reasoning path (no ANTHROPIC_API_KEY) so they are
deterministic and never touch the network — proving the dashboard works with
no API key, which is a hard requirement.
"""

import pytest

from nci_dashboard.api import ApiError, DashboardAPI, DISCLAIMER
from nci_dashboard.paths import ensure_library_paths

ensure_library_paths()
from nci_strategy_selector import QuantumAIBrain, RiskProfile, StrategyType
from nci_strategy_selector.claude_client import ClaudeReasoningClient


def make_api() -> DashboardAPI:
    """API instance pinned to offline mode (empty API key)."""
    brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
    return DashboardAPI(brain=brain)


BULLISH = {
    "context": {
        "symbol": "SPY", "price": 450, "iv_rank": 75, "iv_trend": 0.3,
        "spot_trend": 0.5, "expected_move": 13, "liquidity_score": 0.95,
        "event_proximity_days": None, "news_sentiment": 0.3,
    },
    "prefs": {
        "symbol": "SPY", "risk_profile": "moderate", "bias": "bullish",
        "max_loss_dollars": 1000, "max_loss_pct": 2.0, "time_horizon_days": 30,
    },
}


# ── introspection ──────────────────────────────────────────────────

def test_health_offline_shape():
    h = make_api().health()
    assert h["status"] == "ok"
    assert h["ai_mode"] == "offline"
    assert h["claude_available"] is False
    assert h["disclaimer"] == DISCLAIMER


def test_meta_lists_all_enums():
    m = make_api().meta()
    assert len(m["strategy_types"]) == len(list(StrategyType)) == 13
    assert set(m["risk_profiles"]) == {r.value for r in RiskProfile}
    assert m["biases"] == ["bullish", "bearish", "neutral"]


# ── strategy selection ─────────────────────────────────────────────

def test_select_returns_expected_shape():
    data = make_api().select_strategies(BULLISH)
    assert "session_id" in data and data["ai_mode"] == "offline"
    r = data["result"]
    assert r["symbol"] == "SPY"
    assert isinstance(r["recommendations"], list) and r["recommendations"]
    rec = r["recommendations"][0]
    for k in ("strategy", "max_profit", "max_loss", "breakeven_price",
              "probability_profit", "greeks", "confidence_score", "reasoning",
              "risk_rating", "recommendation_id", "within_max_loss"):
        assert k in rec, f"missing {k}"
    for gk in ("delta", "gamma", "theta", "vega", "rho"):
        assert gk in rec["greeks"]
    assert rec["recommendation_id"].startswith(data["session_id"])
    assert r["ai_reasoning"]  # offline template still produces reasoning


def test_recommendations_ranked_by_confidence_desc():
    recs = make_api().select_strategies(BULLISH)["result"]["recommendations"]
    confs = [r["confidence_score"] for r in recs]
    assert confs == sorted(confs, reverse=True)


def test_max_loss_filter_reflected():
    """Every returned rec must fit within the user's max-loss limit."""
    payload = {**BULLISH, "prefs": {**BULLISH["prefs"], "max_loss_dollars": 300}}
    data = make_api().select_strategies(payload)
    limit = data["max_loss_dollars"]
    assert limit == 300
    for rec in data["result"]["recommendations"]:
        assert rec["max_loss"] <= limit
        assert rec["within_max_loss"] is True


def test_impossible_limit_returns_no_recs_with_reasoning():
    payload = {**BULLISH, "prefs": {**BULLISH["prefs"], "max_loss_dollars": 1}}
    data = make_api().select_strategies(payload)
    assert data["result"]["recommendations"] == []
    assert "risk gate" in data["result"]["ai_reasoning"].lower()


# ── validation ─────────────────────────────────────────────────────

def test_missing_symbol_raises():
    with pytest.raises(ApiError):
        make_api().select_strategies({"context": {"price": 1}, "prefs": {}})


def test_bad_risk_profile_raises():
    bad = {**BULLISH, "prefs": {**BULLISH["prefs"], "risk_profile": "yolo"}}
    with pytest.raises(ApiError):
        make_api().select_strategies(bad)


def test_missing_required_price_raises():
    bad = {"context": {"symbol": "SPY", "expected_move": 5},
           "prefs": BULLISH["prefs"]}
    with pytest.raises(ApiError):
        make_api().select_strategies(bad)


# ── multi-turn reasoning ───────────────────────────────────────────

def test_ask_offline_returns_answer_and_grows_transcript():
    api = make_api()
    data = api.select_strategies(BULLISH)
    sid = data["session_id"]
    a1 = api.ask({"session_id": sid, "question": "Why is the top pick ranked first?"})
    assert a1["answer"] and "offline" in a1["answer"].lower()
    assert len(a1["transcript"]) == 2
    a2 = api.ask({"session_id": sid, "question": "What if IV drops?"})
    assert len(a2["transcript"]) == 4


def test_ask_unknown_session_raises_404():
    with pytest.raises(ApiError) as e:
        make_api().ask({"session_id": "nope", "question": "hi"})
    assert e.value.status == 404


def test_ask_requires_question():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    with pytest.raises(ApiError):
        api.ask({"session_id": sid, "question": "   "})


# ── learning loop ──────────────────────────────────────────────────

def test_record_outcome_updates_performance_and_calibration():
    api = make_api()
    data = api.select_strategies(BULLISH)
    sid = data["session_id"]
    top = data["result"]["recommendations"][0]
    res = api.record_outcome({
        "session_id": sid, "rec_index": 0,
        "exit_price": top["entry_price"] + 1.0,
        "user_rating": 5, "lessons_learned": "worked well",
    })
    assert res["total_outcomes"] == 1
    assert top["strategy"] in res["strategy_performance"]
    perf = res["strategy_performance"][top["strategy"]]
    assert perf["count"] == 1 and perf["wins"] == 1
    assert res["recorded"]["pnl"] == pytest.approx(100.0)


def test_record_outcome_requires_exit_price():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    with pytest.raises(ApiError):
        api.record_outcome({"session_id": sid, "rec_index": 0})


def test_record_outcome_bad_index_raises():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    with pytest.raises(ApiError):
        api.record_outcome({"session_id": sid, "rec_index": 99, "exit_price": 1})


# ── Phoenix reader ─────────────────────────────────────────────────

def test_phoenix_state_shape():
    state = make_api().phoenix_state()
    assert state["meta"]["schema_version"] == "2.1"
    assert "records" in state["pool"]
    assert "current_state" in state


def test_phoenix_versions_is_list():
    versions = make_api().phoenix_versions()
    assert isinstance(versions, list) and versions
    assert "id" in versions[0]
