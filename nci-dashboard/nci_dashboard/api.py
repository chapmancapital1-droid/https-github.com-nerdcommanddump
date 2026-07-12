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

from .market_data import MarketDataProvider, select_provider
from .paths import (
    BRAIN_STATE_FILENAME,
    DEFAULT_BRAIN_STATE,
    DEFAULT_VERSIONS_INDEX,
    PORTFOLIO_STATE_FILENAME,
    ensure_library_paths,
)
from .state import atomic_write_json, load_json

ensure_library_paths()

# Imports resolve only after ensure_library_paths() has run.
from nci_strategy_selector import (  # noqa: E402
    BacktestEngine,
    BacktestPlan,
    MarketContext,
    MCConfig,
    Portfolio,
    Position,
    QuantumAIBrain,
    RiskProfile,
    StrategyType,
    TradeOutcome,
    UserPreferences,
    curve_from_recommendation,
    strategy_direction,
    synthetic_bars,
    validate,
)
from nci_strategy_selector.reasoning_engine import ReasoningSession  # noqa: E402

DISCLAIMER = "Educational analysis tooling — not investment advice."

DEFAULT_ACCOUNT_SIZE = 100_000.0
TRADING_DAYS_PER_YEAR = 252

# Surfaced verbatim on every backtest response so the engine's honesty about its
# approximations reaches the UI (see backtest.py module docstring).
BACKTEST_HONESTY_NOTES = [
    "Synthetic data — deterministic GBM with regime shifts (reproducible per seed). "
    "This is NOT real market history; it demonstrates the engine, not an edge.",
    "Exit P/L is the payoff curve at the exit-day close: an intrinsic-value-at-expiry "
    "approximation, not a live mark.",
    "Early (max-loss stop) exits ignore the remaining extrinsic value the position would "
    "still carry — real early exits are usually less bad than shown here.",
    "IV is not observable from price bars, so iv_rank is a realized-volatility proxy "
    "(labelled iv_proxy), not a true implied-vol percentile.",
    "Early assignment, dividends, financing, and commissions are ignored.",
]


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
        market_provider: Optional[MarketDataProvider] = None,
        state_dir: Optional[Path] = None,
        fresh: bool = False,
        account_size: float = DEFAULT_ACCOUNT_SIZE,
    ):
        self._lock = threading.Lock()
        self.brain_state_path = Path(brain_state_path)
        self.versions_index_path = Path(versions_index_path)
        # Alpaca when APCA_API_KEY_ID/SECRET are set, else the demo feed.
        self.market = market_provider or select_provider()
        self._selections: dict[str, _Selection] = {}

        # ── durable state (Phase 6/7) ─────────────────────────────────
        # When state_dir is None persistence is disabled entirely (pure
        # in-memory) — this keeps the unit tests hermetic. The server wires the
        # real DEFAULT_STATE_DIR. --fresh (fresh=True) ignores any saved files.
        self.state_dir = Path(state_dir) if state_dir else None
        self._brain_file = (self.state_dir / BRAIN_STATE_FILENAME) if self.state_dir else None
        self._portfolio_file = (
            (self.state_dir / PORTFOLIO_STATE_FILENAME) if self.state_dir else None
        )
        self.loaded_from_disk = {"brain": False, "portfolio": False}

        # Brain: an explicit brain always wins; otherwise load saved state
        # (unless fresh); otherwise start clean.
        if brain is not None:
            self.brain = brain
        else:
            saved = None if fresh else load_json(self._brain_file)
            if saved:
                self.brain = QuantumAIBrain.from_dict(saved)
                self.loaded_from_disk["brain"] = True
            else:
                self.brain = QuantumAIBrain()

        # Portfolio: load saved state (unless fresh), else a fresh book.
        saved_pf = None if fresh else load_json(self._portfolio_file)
        if saved_pf:
            self.portfolio = Portfolio.from_dict(saved_pf)
            self.loaded_from_disk["portfolio"] = True
        else:
            self.portfolio = Portfolio(account_size=float(account_size))

    # ── introspection ────────────────────────────────────────────────

    def health(self) -> dict:
        """Liveness + whether live Claude reasoning is wired up."""
        available = self.brain.claude.available
        return {
            "status": "ok",
            "ai_mode": "live" if available else "offline",
            "claude_available": available,
            "model": self.brain.model,
            "market_data": self.market.name,  # "alpaca" | "demo"
            "disclaimer": DISCLAIMER,
            "active_sessions": len(self._selections),
            "persistence": self.state_dir is not None,
            "loaded_from_disk": dict(self.loaded_from_disk),
            "open_positions": len(self.portfolio.open_positions()),
        }

    def meta(self) -> dict:
        """Enum options so the UI can build its form without hard-coding."""
        return {
            "strategy_types": [s.value for s in StrategyType],
            "risk_profiles": [r.value for r in RiskProfile],
            "biases": ["bullish", "bearish", "neutral"],
            "disclaimer": DISCLAIMER,
        }

    # ── live market data (form pre-fill) ─────────────────────────────

    def market_prefill(self, symbol: str) -> dict:
        """
        Fetch live market context for ``symbol`` from the active provider and
        return ``{prefill, source, as_of, notes}`` for the UI to pre-fill the
        MarketContext form. Raises :class:`ApiError` (404) on unknown/failed
        symbols so the caller can surface a consistent error shape.
        """
        symbol = (symbol or "").strip().upper()
        if not symbol:
            raise ApiError("symbol is required")
        if not symbol.replace(".", "").replace("-", "").isalnum():
            raise ApiError("symbol contains unsupported characters")
        prefill = self.market.fetch(symbol)
        if prefill is None:
            detail = getattr(self.market, "last_error", None)
            msg = f"no market data for '{symbol}'"
            if detail:
                msg += f" ({detail})"
            raise ApiError(msg, status=404)
        return prefill.to_response()

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
            self._persist_brain()

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

    # ── Phase 6a: payoff curve for a stored recommendation ───────────

    def payoff(self, session_id: str, rec_index) -> dict:
        """
        Rebuild the payoff-at-expiry curve for one stored recommendation.

        The curve is reconstructed from the recommendation's real legs and its
        stored ``entry_price`` via :func:`curve_from_recommendation` — the same
        single source of truth the headline numbers come from, so the chart can
        never contradict the card. The grid is centred on the selection's spot
        so the UI can draw a current-spot marker.
        """
        sel = self._selections.get(session_id)
        if sel is None:
            raise ApiError("unknown or expired session_id", status=404)
        try:
            rec_index = int(rec_index)
        except (TypeError, ValueError):
            raise ApiError("rec_index must be an integer")
        recs = sel.result.recommendations
        if not (0 <= rec_index < len(recs)):
            raise ApiError("rec_index out of range")
        rec = recs[rec_index]
        spot = float(sel.context.price)
        curve = curve_from_recommendation(rec, spot=spot)
        return {
            "session_id": session_id,
            "rec_index": rec_index,
            "strategy": rec.strategy.value,
            "symbol": sel.context.symbol,
            "spot": round(spot, 4),
            "entry_price": rec.entry_price,
            "curve": curve.to_dict(),
            "disclaimer": DISCLAIMER,
        }

    # ── Phase 6b: synthetic backtest + Monte Carlo gate ──────────────

    def run_backtest(self, payload: dict) -> dict:
        """
        Run the :class:`BacktestEngine` over deterministic synthetic bars and
        put the trade R-series through the Monte Carlo promotion gate.

        No shared brain state is touched (the engine owns its own selector), so
        this deliberately does NOT hold ``self._lock`` — long backtests must not
        block strategy selection / calibration on other threads.
        """
        symbol = (payload.get("symbol") or "").strip().upper()
        if not symbol:
            raise ApiError("symbol is required")

        years = int(self._num(payload, "years", 3))
        years = max(1, min(5, years))
        try:
            seed = int(payload.get("seed", 7))
        except (TypeError, ValueError):
            raise ApiError("seed must be an integer")

        entry_days = max(1, int(self._num(payload, "entry_every_n_days", 21)))
        holding = max(1, int(self._num(payload, "holding_days", 21)))
        max_loss = self._num(payload, "max_loss_dollars", 5000.0)
        start_price = self._num(payload, "start_price", 100.0)

        bias = (payload.get("bias") or "neutral").strip().lower()
        if bias not in ("bullish", "bearish", "neutral"):
            raise ApiError("bias must be bullish, bearish, or neutral")
        rp_raw = (payload.get("risk_profile") or "moderate").strip().lower()
        try:
            risk_profile = RiskProfile(rp_raw)
        except ValueError:
            raise ApiError(
                f"risk_profile must be one of {[r.value for r in RiskProfile]}"
            )

        days = years * TRADING_DAYS_PER_YEAR
        bars = synthetic_bars(symbol, days=days, seed=seed, start_price=start_price)
        plan = BacktestPlan(
            entry_every_n_days=entry_days,
            holding_days=holding,
            bias=bias,
            risk_profile=risk_profile,
            max_loss_dollars=max_loss,
            time_horizon_days=holding,
        )
        result = BacktestEngine().run(symbol, bars, plan)
        mc = validate(result)

        return {
            "symbol": symbol,
            "params": {
                "years": years,
                "seed": seed,
                "days": days,
                "start_price": start_price,
                **plan.to_dict(),
            },
            "result": result.to_dict(),
            "mc": mc.to_dict(),
            "mc_simulations": MCConfig().simulations,
            "notes": BACKTEST_HONESTY_NOTES,
            "synthetic": True,
            "disclaimer": DISCLAIMER,
        }

    # ── Phase 7: portfolio ───────────────────────────────────────────

    @staticmethod
    def _position_rec_id(pos: Position) -> str:
        """
        Deterministic calibration id for a taken position.

        Derived only from persisted fields (symbol, strategy, opened_at) so it
        is stable across restarts: this lets ``close_position`` re-register the
        prediction and close the calibration loop even after the in-memory
        ``_pending_predictions`` map has been lost to a restart.
        """
        return (
            f"pf:{pos.symbol}:{pos.recommendation.strategy.value}:"
            f"{int(pos.opened_at * 1000)}"
        )

    def _position_view(self, pos: Position, index) -> dict:
        """Enriched, UI-ready view of one position (adds derived fields)."""
        return {
            "index": index,
            "symbol": pos.symbol,
            "strategy": pos.recommendation.strategy.value,
            "direction": strategy_direction(pos.recommendation.strategy),
            "qty": pos.qty,
            "entry_price": pos.recommendation.entry_price,
            "modeled_max_loss": round(pos.modeled_max_loss(), 2),
            "net_greeks": pos.net_greeks().to_dict(),
            "expirations": pos.expirations(),
            "opened_at": pos.opened_at,
            "status": pos.status,
        }

    def _portfolio_payload(self) -> dict:
        """Full serialized portfolio state + aggregates + suggestions for the UI."""
        pf = self.portfolio
        positions = [
            self._position_view(p, i)
            for i, p in enumerate(pf.positions)
            if p.status == "open"
        ]
        closed = [
            self._position_view(p, i)
            for i, p in enumerate(pf.positions)
            if p.status == "closed"
        ]
        return {
            "account_size": pf.account_size,
            "risk_budget_pct": pf.risk_budget_pct,
            "aggregates": pf.aggregates().to_dict(),
            "positions": positions,
            "closed_trades": closed,
            "suggestions": pf.suggest(),
            "disclaimer": DISCLAIMER,
        }

    def portfolio_state(self) -> dict:
        """Return the full serialized portfolio state (consistent snapshot)."""
        with self._lock:
            return self._portfolio_payload()

    def set_account_size(self, payload: dict) -> dict:
        """Edit the account size (rescales the risk budget)."""
        size = self._num(payload, "account_size", required=True)
        if size <= 0:
            raise ApiError("account_size must be a positive number")
        with self._lock:
            self.portfolio.account_size = float(size)
            self._persist_portfolio()
            return self._portfolio_payload()

    def add_position(self, payload: dict) -> dict:
        """
        Add a taken recommendation to the server-side portfolio (Phase 7).

        Two-step by design: on the first call, if ``Portfolio.check`` returns
        warnings and ``confirm`` is not set, the position is NOT added and the
        warnings are returned so the UI can surface them before confirming. Pass
        ``confirm: true`` to add anyway. Adding also registers the prediction so
        the eventual close feeds confidence calibration.
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
        try:
            qty = int(payload.get("qty", 1))
        except (TypeError, ValueError):
            raise ApiError("qty must be an integer")
        if qty < 1:
            raise ApiError("qty must be at least 1")
        confirm = bool(payload.get("confirm", False))
        rec = recs[rec_index]

        with self._lock:
            candidate = Position(recommendation=rec, qty=qty)
            warnings = self.portfolio.check(candidate)
            if warnings and not confirm:
                return {
                    "added": False,
                    "warnings": warnings,
                    "candidate": self._position_view(candidate, index=None),
                    "disclaimer": DISCLAIMER,
                }
            self.portfolio.add(candidate)
            # Close the calibration link (mirrors record_outcome): remember the
            # predicted confidence so the eventual close can calibrate it.
            self.brain.register_prediction(self._position_rec_id(candidate), rec)
            self._persist_portfolio()
            payload_out = self._portfolio_payload()

        return {
            "added": True,
            "warnings": warnings,
            "portfolio": payload_out,
            "disclaimer": DISCLAIMER,
        }

    def close_position(self, payload: dict) -> dict:
        """
        Close an open position at a realized exit P&L (dollars) and feed the
        outcome into the same confidence-calibration loop as ``/api/outcome``.
        """
        try:
            index = int(payload.get("index"))
        except (TypeError, ValueError):
            raise ApiError("index must be an integer")
        exit_pnl = payload.get("exit_pnl")
        if exit_pnl is None:
            raise ApiError("exit_pnl is required")
        try:
            exit_pnl = float(exit_pnl)
        except (TypeError, ValueError):
            raise ApiError("exit_pnl must be a number")

        with self._lock:
            positions = self.portfolio.positions
            if not (0 <= index < len(positions)):
                raise ApiError("position index out of range")
            pos = positions[index]
            if pos.status != "open":
                raise ApiError("position is already closed")
            rec = pos.recommendation

            entry_price = rec.entry_price
            qty = pos.qty or 1
            # Invert the P&L convention used elsewhere: pnl = (exit-entry)*100*qty.
            exit_price = entry_price + (exit_pnl / (100.0 * qty))
            pnl_pct = (
                ((exit_price - entry_price) / entry_price * 100.0) if entry_price else 0.0
            )
            rating = payload.get("user_rating", 5 if exit_pnl > 0 else 3)
            try:
                rating = max(1, min(5, int(rating)))
            except (TypeError, ValueError):
                rating = 5 if exit_pnl > 0 else 3

            rec_id = self._position_rec_id(pos)
            outcome = TradeOutcome(
                recommendation_id=rec_id,
                symbol=pos.symbol,
                strategy=rec.strategy,
                entry_price=entry_price,
                exit_price=round(exit_price, 4),
                pnl=exit_pnl,
                pnl_pct=pnl_pct,
                lessons_learned=(payload.get("lessons_learned") or "").strip(),
                user_rating=rating,
            )
            # Re-register in case a restart dropped the pending prediction, then
            # record: register_prediction + record_trade_outcome close the loop.
            self.brain.register_prediction(rec_id, rec)
            self.brain.record_trade_outcome(outcome)
            self.portfolio.close(index)
            self._persist_brain()
            self._persist_portfolio()

            calibration = self.brain.calibrator.to_dict()
            total_outcomes = len(self.brain.knowledge.trade_outcomes)
            payload_out = self._portfolio_payload()

        return {
            "closed": True,
            "recorded": outcome.to_dict(),
            "calibration": calibration,
            "total_outcomes": total_outcomes,
            "portfolio": payload_out,
            "message": (
                f"Closed {rec.strategy.value} on {pos.symbol} "
                f"(P&L ${exit_pnl:+,.2f}). Calibration updated."
            ),
            "disclaimer": DISCLAIMER,
        }

    # ── persistence helpers (callers hold self._lock) ────────────────

    def _persist_brain(self) -> None:
        if self._brain_file is not None:
            atomic_write_json(self._brain_file, self.brain.to_dict())

    def _persist_portfolio(self) -> None:
        if self._portfolio_file is not None:
            atomic_write_json(self._portfolio_file, self.portfolio.to_dict())

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
