"""Phase 6b — backtest endpoint: determinism per seed + MC report present."""

import pytest

from nci_dashboard.api import ApiError
from _helpers import make_api

BASE = {
    "symbol": "SPY", "years": 3, "bias": "neutral",
    "risk_profile": "moderate", "max_loss_dollars": 5000,
}


def test_backtest_shape_and_mc_present():
    api = make_api()
    d = api.run_backtest({**BASE, "seed": 7})

    assert d["symbol"] == "SPY" and d["synthetic"] is True
    assert d["notes"], "honesty notes must be surfaced"

    st = d["result"]["stats"]
    for k in ("total_trades", "win_rate", "expectancy", "profit_factor",
              "max_drawdown"):
        assert k in st
    assert isinstance(d["result"]["equity_curve"], list) and d["result"]["equity_curve"]
    assert isinstance(d["result"]["trades"], list)

    mc = d["mc"]
    for k in ("accepted", "simulations", "ruin_probability",
              "median_expectancy_r", "reasons"):
        assert k in mc
    assert mc["simulations"] > 0
    assert isinstance(mc["accepted"], bool)


def test_backtest_deterministic_per_seed():
    api = make_api()
    a = api.run_backtest({**BASE, "seed": 7})
    b = api.run_backtest({**BASE, "seed": 7})
    assert a["result"] == b["result"]
    assert a["mc"] == b["mc"]


def test_backtest_seed_changes_series():
    api = make_api()
    a = api.run_backtest({**BASE, "seed": 7})
    b = api.run_backtest({**BASE, "seed": 123})
    # Different seeds → different synthetic bars → different outcome.
    assert a["result"] != b["result"]


def test_backtest_years_clamped_1_to_5():
    api = make_api()
    assert api.run_backtest({**BASE, "years": 99})["params"]["years"] == 5
    assert api.run_backtest({**BASE, "years": 0})["params"]["years"] == 1


def test_backtest_requires_symbol():
    with pytest.raises(ApiError):
        make_api().run_backtest({"years": 3})


def test_backtest_bad_bias_raises():
    with pytest.raises(ApiError):
        make_api().run_backtest({**BASE, "bias": "yolo"})
