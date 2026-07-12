"""Phase 6a — payoff endpoint: shape + SVG-relevant invariants."""

import pytest

from nci_dashboard.api import ApiError
from _helpers import BULLISH, make_api


def test_payoff_shape_and_invariants():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    p = api.payoff(sid, 0)

    assert p["session_id"] == sid and p["rec_index"] == 0
    assert p["symbol"] == "SPY" and p["spot"] > 0
    c = p["curve"]
    for k in ("prices", "pnl", "breakevens", "max_profit", "max_loss",
              "unbounded_gain", "unbounded_loss"):
        assert k in c, f"missing curve key {k}"

    # SVG draws prices[i] -> pnl[i]: the two series must be parallel and dense.
    assert len(c["prices"]) == len(c["pnl"]) > 2
    # prices are the x-grid, monotonically increasing.
    assert c["prices"] == sorted(c["prices"])
    lo, hi = min(c["prices"]), max(c["prices"])
    # breakevens must fall inside the sampled window (they're drawn as markers).
    for be in c["breakevens"]:
        assert lo <= be <= hi
    # max_profit / max_loss are the window extremes of the pnl series.
    assert c["max_profit"] == pytest.approx(max(c["pnl"]), abs=1e-3)
    assert c["max_loss"] == pytest.approx(min(c["pnl"]), abs=1e-3)


def test_payoff_all_recommendations_chartable():
    api = make_api()
    data = api.select_strategies(BULLISH)
    sid = data["session_id"]
    for i in range(len(data["result"]["recommendations"])):
        c = api.payoff(sid, i)["curve"]
        assert len(c["prices"]) == len(c["pnl"])


def test_payoff_bad_index_raises():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    with pytest.raises(ApiError):
        api.payoff(sid, 99)


def test_payoff_unknown_session_404():
    with pytest.raises(ApiError) as e:
        make_api().payoff("nope", 0)
    assert e.value.status == 404


def test_payoff_non_integer_index_raises():
    api = make_api()
    sid = api.select_strategies(BULLISH)["session_id"]
    with pytest.raises(ApiError):
        api.payoff(sid, "abc")
