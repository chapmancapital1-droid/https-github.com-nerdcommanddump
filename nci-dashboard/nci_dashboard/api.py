"""
Dashboard service layer.

Wraps the Phase-4 ``QuantumAIBrain`` and the Phoenix brain-state reader in a
transport-agnostic API so it can be unit-tested without a running HTTP server.
The HTTP handler in ``server.py`` is a thin adapter over this class.

Threading: a single shared ``QuantumAIBrain`` accumulates calibration learning
across requests, so all mutating calls are guarded by a lock.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from .paths import (
    DEFAULT_BRAIN_STATE,
    DEFAULT_VERSIONS_INDEX,
    ensure_library_paths,
)

ensure_library_paths()

# Imports resolve only after ensure_library_paths() has run.
from nci_strategy_selector import (  # noqa: E402
    MarketContext,
    QuantumAIBrain,
    RiskProfile,
    StrategyType,
    TradeOutcome,
    UserPreferences,
)
from nci_strategy_selector.reasoning_engine import ReasoningSession  # noqa: E402

DISCLAIMER = "Educational analysis tooling — not investment advice."


class ApiError(Exception):
    """Raised on bad client input; carries an HTTP status code."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status
        self.message = message


class _Selection:
    """Server-side record of one strategy selection + its dialogue session."""

    __slots__ = ("id", "context", "prefs", "result", "session", "created_at")

    def __init__(
        self,
        sid: str,
        context: MarketContext,
        prefs: UserPreferences,
        result: Any,
        session: ReasoningSession,
    ):
        self.id = sid
        self.context = context
        self.prefs = prefs
        self.result = result
        self.session = session
        self.created_at = time.time()


class DashboardAPI:
    """All dashboard business logic, independent of the web framework."""

    def __init__(
        self,
        brain: Optional[QuantumAIBrain] = None,
        brain_state_path: Path = DEFAULT_BRAIN_STATE,
        versions_index_path: Path = DEFAULT_VERSIONS_INDEX,
    ):
        self._lock = threading.Lock()
        self.brain = brain or QuantumAIBrain()
        self.brain_state_path = Path(brain_state_path)
        self.versions_index_path = Path(versions_index_path)
        self._selections: dict[str, _Selection] = {}

    # ── introspection ────────────────────────────────────────────────

    def health(self) -> dict:
        """Liveness + whether live Claude reasoning is wired up."""
        available = self.brain.claude.available
        return {
            "status": "ok",
            "ai_mode": "live" if available else "offline",
            "claude_available": available,
            "model": self.brain.model,
            "disclaimer": DISCLAIMER,
            "active_sessions": len(self._selections),
        }

    def meta(self) -> dict:
        """Enum options so the UI can build its form without hard-coding."""
        return {
            "strategy_types": [s.value for s in StrategyType],
            "risk_profiles": [r.value for r in RiskProfile],
            "biases": ["bullish", "bearish", "neutral"],
            "disclaimer": DISCLAIMER,
        }

    # ── strategy selection ───────────────────────────────────────────

    def select_strategies(self, payload: dict) -> dict:
        """
        Run ``select_and_reason`` for a market context + user preferences.

        Returns the serialized result plus a ``session_id`` for follow-up
        questions and outcome logging, and stable ``recommendation_id`` values
        on each card.
        """
        context = self._parse_context(payload.get("context", {}))
        prefs = self._parse_prefs(payload.get("prefs", {}))

        with self._lock:
            # use_claude=True: uses live API when a key is set, otherwise the
            # library's deterministic offline template — either way it works.
            result = self.brain.select_and_reason(context, prefs, use_claude=True)
            session = self.brain.start_reasoning_session(context, prefs, result)
            sid = uuid.uuid4().hex[:12]
            self._selections[sid] = _Selection(sid, context, prefs, result, session)

        result_dict = result.to_dict()
        # Attach stable ids the UI echoes back on ask/outcome calls.
        for i, rec in enumerate(result_dict["recommendations"]):
            rec["recommendation_id"] = f"{sid}:{i}"
            rec["within_max_loss"] = rec["max_loss"] <= prefs.max_loss_dollars

        return {
            "session_id": sid,
            "ai_mode": "live" if self.brain.claude.available else "offline",
            "max_loss_dollars": prefs.max_loss_dollars,
            "result": result_dict,
            "disclaimer": DISCLAIMER,
        }

    # ── multi-turn reasoning ─────────────────────────────────────────

    def ask(self, payload: dict) -> dict:
        """Ask a follow-up question against a stored ReasoningSession."""
        sid = payload.get("session_id")
        question = (payload.get("question") or "").strip()
        if not question:
            raise ApiError("question is required")
        sel = self._selections.get(sid)
        if sel is None:
            raise ApiError("unknown or expired session_id", status=404)

        with self._lock:
            answer = sel.session.ask(question)

        return {
            "session_id": sid,
            "answer": answer,
            "transcript": sel.session.transcript(),
            "ai_mode": "live" if self.brain.claude.available else "offline",
        }

    # ── learning loop ────────────────────────────────────────────────

    def record_outcome(self, payload: dict) -> dict:
        """
        Log a realized outcome for one recommendation and feed it back into the
        confidence calibrator so future confidence for that strategy adapts.
        """
        sid = payload.get("session_id")
        sel = self._selections.get(sid)
        if sel is None:
            raise ApiError("unknown or expired session_id", status=404)

        try:
            rec_index = int(payload.get("rec_index", 0))
        except (TypeError, ValueError):
            raise ApiError("rec_index must be an integer")
        recs = sel.result.recommendations
        if not (0 <= rec_index < len(recs)):
            raise ApiError("rec_index out of range")
        rec = recs[rec_index]

        entry_price = rec.entry_price
        exit_price = payload.get("exit_price")
        if exit_price is None:
            raise ApiError("exit_price is required")
        try:
            exit_price = float(exit_price)
        except (TypeError, ValueError):
            raise ApiError("exit_price must be a number")

        # Per-contract P&L, matching the demo's convention (x100 multiplier).
        pnl = (exit_price - entry_price) * 100.0
        pnl_pct = ((exit_price - entry_price) / entry_price * 100.0) if entry_price else 0.0
        rating = payload.get("user_rating", 5 if pnl > 0 else 3)
        try:
            rating = max(1, min(5, int(rating)))
        except (TypeError, ValueError):
            rating = 5 if pnl > 0 else 3

        rec_id = f"{sid}:{rec_index}"
        outcome = TradeOutcome(
            recommendation_id=rec_id,
            symbol=sel.context.symbol,
            strategy=rec.strategy,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            lessons_learned=(payload.get("lessons_learned") or "").strip(),
            user_rating=rating,
        )

        with self._lock:
            # register_prediction closes the calibration loop inside
            # record_trade_outcome (it matches on recommendation_id).
            self.brain.register_prediction(rec_id, rec)
            self.brain.record_trade_outcome(outcome)
            perf = dict(self.brain.knowledge.current_version.strategy_performance)
            calibration = self.brain.calibrator.to_dict()
            total_outcomes = len(self.brain.knowledge.trade_outcomes)

        return {
            "recorded": outcome.to_dict(),
            "strategy_performance": perf,
            "calibration": calibration,
            "total_outcomes": total_outcomes,
            "message": (
                f"Logged {rec.strategy.value} outcome "
                f"(P&L ${pnl:+.2f}). Calibration updated."
            ),
        }

    # ── Phoenix tab (pure reader) ────────────────────────────────────

    def phoenix_state(self) -> dict:
        """Return the raw brain_state.json (DESIGN.md §5.3 data source)."""
        if not self.brain_state_path.exists():
            raise ApiError("brain_state.json not found on the server", status=404)
        try:
            return json.loads(self.brain_state_path.read_text())
        except json.JSONDecodeError as e:
            raise ApiError(f"brain_state.json is not valid JSON: {e}", status=500)

    def phoenix_versions(self) -> list:
        """Version lineage for the Versions panel (versions/index.json)."""
        if not self.versions_index_path.exists():
            return []
        try:
            return json.loads(self.versions_index_path.read_text())
        except json.JSONDecodeError as e:
            raise ApiError(f"versions index is not valid JSON: {e}", status=500)

    # ── input parsing / validation ───────────────────────────────────

    @staticmethod
    def _num(d: dict, key: str, default=None, required=False) -> float:
        if key not in d or d[key] in (None, ""):
            if required:
                raise ApiError(f"'{key}' is required")
            return default
        try:
            return float(d[key])
        except (TypeError, ValueError):
            raise ApiError(f"'{key}' must be a number")

    def _parse_context(self, d: dict) -> MarketContext:
        symbol = (d.get("symbol") or "").strip().upper()
        if not symbol:
            raise ApiError("context.symbol is required")
        event = d.get("event_proximity_days")
        event_val = None if event in (None, "") else self._num(d, "event_proximity_days")
        return MarketContext(
            symbol=symbol,
            price=self._num(d, "price", required=True),
            iv_rank=self._num(d, "iv_rank", 50.0),
            iv_trend=self._num(d, "iv_trend", 0.0),
            spot_trend=self._num(d, "spot_trend", 0.0),
            expected_move=self._num(d, "expected_move", required=True),
            liquidity_score=self._num(d, "liquidity_score", 0.8),
            event_proximity_days=event_val,
            news_sentiment=self._num(d, "news_sentiment", 0.0),
        )

    def _parse_prefs(self, d: dict) -> UserPreferences:
        symbol = (d.get("symbol") or "").strip().upper()
        if not symbol:
            raise ApiError("prefs.symbol is required")
        rp_raw = (d.get("risk_profile") or "moderate").strip().lower()
        try:
            risk_profile = RiskProfile(rp_raw)
        except ValueError:
            raise ApiError(
                f"risk_profile must be one of {[r.value for r in RiskProfile]}"
            )
        bias = (d.get("bias") or "neutral").strip().lower()
        if bias not in ("bullish", "bearish", "neutral"):
            raise ApiError("bias must be bullish, bearish, or neutral")
        return UserPreferences(
            symbol=symbol,
            risk_profile=risk_profile,
            max_loss_pct=self._num(d, "max_loss_pct", 2.0),
            max_loss_dollars=self._num(d, "max_loss_dollars", required=True),
            bias=bias,
            time_horizon_days=int(self._num(d, "time_horizon_days", 30)),
            min_probability_itm=self._num(d, "min_probability_itm", 0.5),
        )
