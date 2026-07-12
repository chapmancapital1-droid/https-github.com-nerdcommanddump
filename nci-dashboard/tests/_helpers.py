"""Shared test helpers for the Phase 6/7 suites."""

from nci_dashboard.api import DashboardAPI
from nci_dashboard.paths import ensure_library_paths

ensure_library_paths()
from nci_strategy_selector import QuantumAIBrain  # noqa: E402
from nci_strategy_selector.claude_client import ClaudeReasoningClient  # noqa: E402


BULLISH = {
    "context": {
        "symbol": "SPY", "price": 450, "iv_rank": 75, "iv_trend": 0.3,
        "spot_trend": 0.5, "expected_move": 13, "liquidity_score": 0.95,
        "event_proximity_days": None, "news_sentiment": 0.3,
    },
    "prefs": {
        "symbol": "SPY", "risk_profile": "moderate", "bias": "bullish",
        "max_loss_dollars": 5000, "max_loss_pct": 2.0, "time_horizon_days": 30,
    },
}


def make_api(**kwargs) -> DashboardAPI:
    """Offline-pinned API (empty key → deterministic, no network)."""
    brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
    return DashboardAPI(brain=brain, **kwargs)
