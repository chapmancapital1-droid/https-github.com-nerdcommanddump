"""
Smoke test: the stdlib server actually boots, serves the SPA, and answers the
JSON API over a real socket.
"""

import json
import threading
import urllib.request

import pytest

from nci_dashboard.server import build_server


@pytest.fixture()
def live_server():
    httpd = build_server("127.0.0.1", 0)  # port 0 → OS picks a free port
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read().decode("utf-8")


def _post(url, obj):
    req = urllib.request.Request(
        url, data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def test_index_page_served(live_server):
    status, body = _get(live_server + "/")
    assert status == 200
    assert "Options Assistant" in body
    assert "not investment advice" in body


def test_health_endpoint(live_server):
    status, body = _get(live_server + "/api/health")
    assert status == 200
    assert json.loads(body)["status"] == "ok"


def test_phoenix_endpoint(live_server):
    status, body = _get(live_server + "/api/phoenix")
    assert status == 200
    assert json.loads(body)["meta"]["schema_version"] == "2.1"


def test_strategies_endpoint_returns_cards(live_server):
    status, data = _post(live_server + "/api/strategies", {
        "context": {"symbol": "SPY", "price": 450, "iv_rank": 75, "iv_trend": 0.3,
                    "spot_trend": 0.5, "expected_move": 13, "liquidity_score": 0.95,
                    "news_sentiment": 0.3},
        "prefs": {"symbol": "SPY", "risk_profile": "moderate", "bias": "bullish",
                  "max_loss_dollars": 1000, "time_horizon_days": 30},
    })
    assert status == 200
    assert data["session_id"]
    assert len(data["result"]["recommendations"]) >= 1


def test_market_endpoint_prefills(live_server):
    # No Alpaca keys in the test env → DemoProvider, deterministic values.
    status, body = _get(live_server + "/api/market/SPY")
    assert status == 200
    data = json.loads(body)
    assert set(data) == {"prefill", "source", "as_of", "notes"}
    assert data["source"] == "demo"
    assert "price" in data["prefill"] and "expected_move" in data["prefill"]


def test_health_reports_market_data_source(live_server):
    status, body = _get(live_server + "/api/health")
    assert status == 200
    assert json.loads(body)["market_data"] in ("demo", "alpaca")


def test_unknown_route_404(live_server):
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(live_server + "/api/nope")
    assert e.value.code == 404


import urllib.error  # noqa: E402  (used in test above)
