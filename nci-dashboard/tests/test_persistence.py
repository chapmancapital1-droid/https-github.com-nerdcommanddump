"""Phase 6/7 — durable state: mutate → new Api instance → state survives; --fresh ignores."""

from nci_dashboard.api import DashboardAPI
from nci_dashboard.paths import BRAIN_STATE_FILENAME, PORTFOLIO_STATE_FILENAME
from _helpers import BULLISH, make_api


def _mutate(api):
    """Take a trade and close it → mutates both portfolio and brain calibration."""
    sid = api.select_strategies(BULLISH)["session_id"]
    api.add_position({"session_id": sid, "rec_index": 0, "qty": 1})
    idx = api.portfolio_state()["positions"][0]["index"]
    api.close_position({"index": idx, "exit_pnl": 150.0})


def test_state_round_trips_across_instances(tmp_path):
    sd = tmp_path / "state"
    api = make_api(state_dir=sd)
    _mutate(api)

    assert (sd / BRAIN_STATE_FILENAME).exists()
    assert (sd / PORTFOLIO_STATE_FILENAME).exists()

    # A brand-new Api pointed at the same dir restores both.
    api2 = DashboardAPI(state_dir=sd)
    assert api2.loaded_from_disk == {"brain": True, "portfolio": True}
    assert len(api2.brain.knowledge.trade_outcomes) == 1
    assert len(api2.portfolio.closed_trades) == 1
    # calibration survived too
    assert api2.brain.calibrator.to_dict()


def test_account_size_edit_persists(tmp_path):
    sd = tmp_path / "state"
    api = make_api(state_dir=sd)
    api.set_account_size({"account_size": 250000})
    api2 = DashboardAPI(state_dir=sd)
    assert api2.portfolio.account_size == 250000


def test_fresh_ignores_saved_state(tmp_path):
    sd = tmp_path / "state"
    api = make_api(state_dir=sd)
    _mutate(api)
    assert (sd / PORTFOLIO_STATE_FILENAME).exists()

    fresh = DashboardAPI(state_dir=sd, fresh=True)
    assert fresh.loaded_from_disk == {"brain": False, "portfolio": False}
    assert len(fresh.portfolio.open_positions()) == 0
    assert len(fresh.portfolio.closed_trades) == 0
    assert len(fresh.brain.knowledge.trade_outcomes) == 0


def test_no_state_dir_disables_persistence(tmp_path):
    api = make_api()  # state_dir=None
    assert api.health()["persistence"] is False
    sid = api.select_strategies(BULLISH)["session_id"]
    api.add_position({"session_id": sid, "rec_index": 0, "qty": 1})
    # nothing written anywhere; a fresh in-memory Api starts empty
    assert make_api().health()["open_positions"] == 0


def test_corrupt_state_file_falls_back(tmp_path):
    sd = tmp_path / "state"
    sd.mkdir(parents=True)
    (sd / BRAIN_STATE_FILENAME).write_text("{not valid json")
    (sd / PORTFOLIO_STATE_FILENAME).write_text("garbage")
    # Boot must not crash; falls back to fresh instances.
    api = DashboardAPI(state_dir=sd)
    assert api.loaded_from_disk == {"brain": False, "portfolio": False}
    assert len(api.portfolio.open_positions()) == 0
