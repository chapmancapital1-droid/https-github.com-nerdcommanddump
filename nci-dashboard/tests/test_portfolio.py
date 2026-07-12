"""Phase 7 — portfolio add/check/close flow, warnings, and calibration linkage."""

import pytest

from nci_dashboard.api import ApiError
from _helpers import BULLISH, make_api


def test_clean_add_has_no_warnings():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    res = api.add_position({"session_id": sid, "rec_index": 0, "qty": 1})
    assert res["added"] is True
    assert res["warnings"] == []
    ps = api.portfolio_state()
    assert len(ps["positions"]) == 1
    assert ps["positions"][0]["modeled_max_loss"] > 0
    assert ps["suggestions"]


def test_add_preview_returns_warnings_without_adding_then_confirm():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    # A huge quantity blows the risk budget → check() warns, position NOT added.
    prev = api.add_position({"session_id": sid, "rec_index": 0, "qty": 100})
    assert prev["added"] is False
    assert prev["warnings"], "over-budget size must produce warnings"
    assert api.portfolio_state()["aggregates"]["open_positions"] == 0

    # Confirm adds it anyway (warnings acknowledged).
    conf = api.add_position(
        {"session_id": sid, "rec_index": 0, "qty": 100, "confirm": True}
    )
    assert conf["added"] is True
    assert conf["portfolio"]["aggregates"]["open_positions"] == 1


def test_close_moves_position_and_feeds_calibration():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    api.add_position({"session_id": sid, "rec_index": 0, "qty": 1})
    ps = api.portfolio_state()
    idx = ps["positions"][0]["index"]
    strat = ps["positions"][0]["strategy"]

    before = len(api.brain.knowledge.trade_outcomes)
    res = api.close_position({"index": idx, "exit_pnl": 300.0})
    assert res["closed"] is True
    assert res["recorded"]["pnl"] == 300.0
    assert res["total_outcomes"] == before + 1
    # Position moved from open to closed.
    assert res["portfolio"]["aggregates"]["open_positions"] == 0
    assert len(res["portfolio"]["closed_trades"]) == 1
    # register_prediction linked the calibration loop (observe ran for this strat).
    assert strat in res["calibration"]
    assert res["calibration"][strat]["samples"] == 1


def test_close_requires_pnl_and_valid_index():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    api.add_position({"session_id": sid, "rec_index": 0, "qty": 1})
    with pytest.raises(ApiError):
        api.close_position({"index": 0})  # no exit_pnl
    with pytest.raises(ApiError):
        api.close_position({"index": 99, "exit_pnl": 1})  # out of range


def test_close_already_closed_raises():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    api.add_position({"session_id": sid, "rec_index": 0, "qty": 1})
    api.close_position({"index": 0, "exit_pnl": 10.0})
    with pytest.raises(ApiError):
        api.close_position({"index": 0, "exit_pnl": 10.0})


def test_add_unknown_session_404():
    with pytest.raises(ApiError) as e:
        make_api().add_position({"session_id": "nope", "rec_index": 0, "qty": 1})
    assert e.value.status == 404


def test_set_account_size_rescales_budget():
    api = make_api()
    ps = api.set_account_size({"account_size": 50000})
    assert ps["account_size"] == 50000
    assert ps["aggregates"]["risk_budget"] == pytest.approx(50000 * 0.15)
    with pytest.raises(ApiError):
        api.set_account_size({"account_size": -5})


def test_greeks_scale_with_quantity():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    api.add_position({"session_id": sid, "rec_index": 0, "qty": 3, "confirm": True})
    pos = api.portfolio_state()["positions"][0]
    rec = api.select_strategies(BULLISH)  # fresh single-unit greeks reference
    # position greeks are per-unit greeks * qty (delta sign preserved)
    assert pos["qty"] == 3
    assert pos["net_greeks"]["delta"] == pytest.approx(
        rec["result"]["recommendations"][0]["greeks"]["delta"] * 3, abs=1e-6
    )
