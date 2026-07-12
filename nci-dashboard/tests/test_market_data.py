"""
Unit tests for the live market-data provider layer.

No live network: AlpacaProvider is exercised against canned JSON fixtures of the
Alpaca snapshot / bars / options-snapshot responses by monkeypatching
``urllib.request.urlopen``. Covers provider selection, snapshot/options
parsing, the spot_trend / iv_rank / expected_move / liquidity derivations,
DemoProvider determinism, and the /api/market endpoint shape + error path.
"""

import io
import json
from datetime import date

import pytest

from nci_dashboard.paths import ensure_library_paths

ensure_library_paths()

from nci_dashboard import market_data as md
from nci_dashboard.api import ApiError, DashboardAPI
from nci_dashboard.market_data import (
    AlpacaProvider,
    DemoProvider,
    MarketPrefill,
    alpaca_keys_present,
    choose_expiry,
    derive_iv_rank,
    derive_liquidity,
    derive_spot_trend,
    parse_occ_symbol,
    select_provider,
)


# ── provider selection ─────────────────────────────────────────────
def test_select_provider_demo_without_keys():
    assert isinstance(select_provider({}), DemoProvider)
    assert select_provider({}).name == "demo"


def test_select_provider_alpaca_with_apca_keys():
    env = {"APCA_API_KEY_ID": "k", "APCA_API_SECRET_KEY": "s"}
    assert isinstance(select_provider(env), AlpacaProvider)


def test_select_provider_alpaca_with_alt_key_names():
    env = {"ALPACA_API_KEY_ID": "k", "ALPACA_API_SECRET_KEY": "s"}
    assert isinstance(select_provider(env), AlpacaProvider)


def test_alpaca_keys_present_requires_both():
    assert alpaca_keys_present({"APCA_API_KEY_ID": "k"}) is False
    assert alpaca_keys_present({"APCA_API_SECRET_KEY": "s"}) is False
    assert alpaca_keys_present({}) is False


# ── OCC parsing + expiry selection ─────────────────────────────────
def test_parse_occ_symbol():
    info = parse_occ_symbol("AAPL240119C00190000")
    assert info["underlying"] == "AAPL"
    assert info["expiry"] == date(2024, 1, 19)
    assert info["right"] == "C"
    assert info["strike"] == 190.0


def test_parse_occ_symbol_put_and_fractional_strike():
    info = parse_occ_symbol("SPY240621P00447500")
    assert info["right"] == "P"
    assert info["strike"] == 447.5


def test_parse_occ_symbol_rejects_junk():
    assert parse_occ_symbol("not-an-occ") is None
    assert parse_occ_symbol("") is None


def test_choose_expiry_prefers_third_friday():
    today = date(2024, 1, 2)
    expiries = [date(2024, 1, 5), date(2024, 1, 19), date(2024, 2, 16)]
    # 2024-01-19 and 2024-02-16 are 3rd Fridays; nearest monthly wins.
    assert choose_expiry(expiries, today) == date(2024, 1, 19)


def test_choose_expiry_falls_back_to_nearest_future():
    today = date(2024, 1, 2)
    expiries = [date(2024, 1, 5), date(2024, 1, 12)]  # no 3rd Fridays
    assert choose_expiry(expiries, today) == date(2024, 1, 5)


# ── pure derivations ───────────────────────────────────────────────
def test_derive_spot_trend_uptrend_positive():
    # last close well above the SMA → strongly positive, clamped ≤ 1.
    closes = [100.0] * 19 + [110.0]
    trend, note = derive_spot_trend(closes)
    assert trend > 0 and trend <= 1.0
    assert "SMA" in note


def test_derive_spot_trend_flat_is_zero():
    trend, _ = derive_spot_trend([50.0] * 20)
    assert trend == pytest.approx(0.0)


def test_derive_spot_trend_downtrend_clamped():
    closes = [200.0] * 19 + [150.0]  # −25% vs SMA, saturates to −1
    trend, _ = derive_spot_trend(closes)
    assert trend == pytest.approx(-1.0)


def test_derive_spot_trend_insufficient_history():
    trend, note = derive_spot_trend([100.0])
    assert trend == 0.0 and "insufficient" in note


def test_derive_iv_rank_maps_band_and_labels_estimated():
    rank, note = derive_iv_rank(0.30)  # midpoint of 10–50% band → 50
    assert rank == pytest.approx(50.0)
    assert "ESTIMATED" in note
    assert derive_iv_rank(0.05)[0] == 0.0     # below floor clamps to 0
    assert derive_iv_rank(0.90)[0] == 100.0   # above ceil clamps to 100


def test_derive_liquidity_tight_vs_wide():
    tight, _ = derive_liquidity([0.01, 0.02])   # ~1.5% spread → near 1
    wide, _ = derive_liquidity([0.30])          # ≥25% → 0
    assert tight > 0.9
    assert wide == pytest.approx(0.0)


def test_derive_liquidity_no_quotes_defaults():
    score, note = derive_liquidity([])
    assert score == pytest.approx(0.7) and "default" in note.lower()


# ── AlpacaProvider against canned fixtures (mocked urllib) ─────────
SNAPSHOT_FIXTURE = {
    "latestTrade": {"t": "2024-06-14T19:59:59.9Z", "p": 450.0, "s": 100},
    "latestQuote": {"bp": 449.9, "ap": 450.1},
    "dailyBar": {"o": 448.0, "h": 451.0, "l": 447.5, "c": 450.0, "v": 1000000},
    "prevDailyBar": {"c": 447.0},
}

# 20 sessions, last close (460) above the SMA → positive spot_trend.
BARS_FIXTURE = {
    "bars": [{"t": f"2024-05-{i:02d}", "c": 440.0} for i in range(1, 20)]
    + [{"c": 460.0}],
    "symbol": "SPY",
}

# ATM (450) call + put for a 3rd-Friday expiry (2024-06-21), plus a wing.
OPTIONS_FIXTURE = {
    "snapshots": {
        "SPY240621C00450000": {
            "latestQuote": {"bp": 6.4, "ap": 6.6},
            "latestTrade": {"p": 6.5},
            "greeks": {"delta": 0.51},
            "impliedVolatility": 0.28,
        },
        "SPY240621P00450000": {
            "latestQuote": {"bp": 6.0, "ap": 6.2},
            "latestTrade": {"p": 6.1},
            "greeks": {"delta": -0.49},
            "impliedVolatility": 0.30,
        },
        "SPY240621C00460000": {
            "latestQuote": {"bp": 2.0, "ap": 2.2},
            "impliedVolatility": 0.26,
        },
    }
}


class _FakeResponse(io.BytesIO):
    """Context-manager BytesIO standing in for an urlopen() response."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


def _make_router(mapping, today=date(2024, 6, 1)):
    """
    Build a fake ``urlopen`` that routes by URL substring to a fixture, and
    pins ``choose_expiry``'s notion of "today" so the monthly is in the future.
    """
    # Longest needle first so "/options/snapshots/" wins over "/snapshot".
    ordered = sorted(mapping.items(), key=lambda kv: -len(kv[0]))

    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        for needle, payload in ordered:
            if needle in url:
                return _FakeResponse(json.dumps(payload).encode("utf-8"))
        raise AssertionError(f"unexpected URL: {url}")
    return fake_urlopen


def test_alpaca_fetch_parses_all_fields(monkeypatch):
    monkeypatch.setattr(
        md.urllib.request, "urlopen",
        _make_router({
            "/snapshot": SNAPSHOT_FIXTURE,
            "/bars": BARS_FIXTURE,
            "/options/snapshots/": OPTIONS_FIXTURE,
        }),
    )
    p = AlpacaProvider(key_id="k", secret_key="s", retry_backoff_s=0).fetch("SPY")
    assert p is not None
    assert p.source == "alpaca"
    assert p.price == 450.0
    # spot_trend positive (last close above SMA)
    assert p.spot_trend > 0
    # expected_move ≈ ATM straddle mid = 6.5 + 6.1 = 12.6
    assert p.expected_move == pytest.approx(12.6, abs=0.01)
    # iv_rank estimated from mean ATM IV (0.29) mapped on 10–50% band ≈ 47.5
    assert 40 < p.iv_rank < 55
    # liquidity from ~0.2-wide markets on ~6.x mids (~3% spread) → tight → high
    assert p.liquidity_score > 0.8
    # iv_trend unknown → 0
    assert p.iv_trend == 0.0
    # provenance timestamp from the trade
    assert p.as_of.startswith("2024-06-14T19:59:59")
    # notes flag the estimated iv_rank + unknown iv_trend
    joined = " ".join(p.notes).lower()
    assert "estimated" in joined and "iv_trend" in joined


def test_alpaca_fetch_snapshot_wrapped_by_symbol(monkeypatch):
    wrapped = {"SPY": SNAPSHOT_FIXTURE}
    monkeypatch.setattr(
        md.urllib.request, "urlopen",
        _make_router({
            "/snapshot": wrapped,
            "/bars": BARS_FIXTURE,
            "/options/snapshots/": OPTIONS_FIXTURE,
        }),
    )
    p = AlpacaProvider(key_id="k", secret_key="s", retry_backoff_s=0).fetch("SPY")
    assert p is not None and p.price == 450.0


def test_alpaca_returns_none_on_http_error(monkeypatch):
    import urllib.error

    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(md.urllib.request, "urlopen", boom)
    prov = AlpacaProvider(key_id="k", secret_key="s", retry_backoff_s=0)
    assert prov.fetch("NOPE") is None
    assert "404" in (prov.last_error or "")


def test_alpaca_retries_then_succeeds_on_429(monkeypatch):
    import urllib.error
    calls = {"n": 0}

    def flaky(req, timeout=None):
        url = req.full_url
        if "/snapshot" in url and calls["n"] == 0:
            calls["n"] += 1
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
        router = _make_router({
            "/snapshot": SNAPSHOT_FIXTURE, "/bars": BARS_FIXTURE,
            "/options/snapshots/": OPTIONS_FIXTURE,
        })
        return router(req, timeout)

    monkeypatch.setattr(md.urllib.request, "urlopen", flaky)
    prov = AlpacaProvider(key_id="k", secret_key="s", retry_backoff_s=0)
    p = prov.fetch("SPY")
    assert p is not None and calls["n"] == 1  # one retry happened


def test_alpaca_degrades_when_options_missing(monkeypatch):
    monkeypatch.setattr(
        md.urllib.request, "urlopen",
        _make_router({
            "/snapshot": SNAPSHOT_FIXTURE,
            "/bars": BARS_FIXTURE,
            "/options/snapshots/": {"snapshots": {}},
        }),
    )
    p = AlpacaProvider(key_id="k", secret_key="s", retry_backoff_s=0).fetch("SPY")
    assert p is not None
    assert p.iv_rank == 50.0                       # fallback default
    assert p.expected_move == pytest.approx(18.0)  # 4% of 450
    assert any("options chain unavailable" in n for n in p.notes)


# ── DemoProvider determinism ───────────────────────────────────────
def test_demo_provider_is_deterministic():
    a = DemoProvider().fetch("ZZZZ")
    b = DemoProvider().fetch("ZZZZ")
    assert a.prefill_fields() == b.prefill_fields()
    assert a.source == "demo"


def test_demo_provider_known_symbol_anchor():
    p = DemoProvider().fetch("SPY")
    assert p.price == 548.20 and p.source == "demo"
    assert any("demo" in n.lower() for n in p.notes)


def test_demo_provider_synth_values_in_range():
    p = DemoProvider().fetch("WXYZ")
    f = p.prefill_fields()
    assert 40 <= f["price"] <= 400
    assert 0 <= f["iv_rank"] <= 100
    assert -1 <= f["spot_trend"] <= 1
    assert 0 <= f["liquidity_score"] <= 1


def test_demo_provider_empty_symbol_none():
    assert DemoProvider().fetch("") is None


# ── /api/market endpoint via DashboardAPI ──────────────────────────
def _demo_api() -> DashboardAPI:
    return DashboardAPI(market_provider=DemoProvider())


def test_market_prefill_endpoint_shape():
    resp = _demo_api().market_prefill("SPY")
    assert set(resp) == {"prefill", "source", "as_of", "notes"}
    assert resp["source"] == "demo"
    assert set(resp["prefill"]) == {
        "price", "iv_rank", "iv_trend", "spot_trend",
        "expected_move", "liquidity_score",
    }
    assert isinstance(resp["notes"], list) and resp["notes"]


def test_market_prefill_empty_symbol_raises():
    with pytest.raises(ApiError):
        _demo_api().market_prefill("")


def test_market_prefill_bad_symbol_chars_raises():
    with pytest.raises(ApiError):
        _demo_api().market_prefill("../etc")


def test_market_prefill_failed_fetch_is_404():
    class _NullProvider(DemoProvider):
        name = "demo"

        def fetch(self, symbol):
            self.last_error = "simulated feed outage"
            return None

    api = DashboardAPI(market_provider=_NullProvider())
    with pytest.raises(ApiError) as e:
        api.market_prefill("SPY")
    assert e.value.status == 404
    assert "simulated feed outage" in e.value.message


def test_health_reports_market_source():
    assert _demo_api().health()["market_data"] == "demo"


def test_prefill_to_response_roundtrip():
    pf = MarketPrefill(
        price=100.0, iv_rank=50.0, iv_trend=0.0, spot_trend=0.2,
        expected_move=4.0, liquidity_score=0.9, source="demo",
        as_of="2024-06-14T00:00:00Z", notes=["n1"],
    )
    r = pf.to_response()
    assert r["prefill"]["price"] == 100.0
    assert r["notes"] == ["n1"]
