"""
Multi-turn reasoning engine — Phase 5 "Quantum AI" dialogue layer.

Wraps a strategy selection in a persistent conversation so the user can
interrogate the recommendation ("why not an iron condor?", "what if IV
drops tomorrow?") and the AI answers with full context of the market
snapshot, the user's constraints, and the recommendation set.

Works in two modes:
  - Claude mode: real API calls through ClaudeReasoningClient
  - Offline mode: deterministic template answers so the product still
    functions without a key (clearly labeled as offline)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .claude_client import ClaudeReasoningClient, ClaudeResponse
from .models import (
    MarketContext,
    StrategySelectionResult,
    UserPreferences,
)

SYSTEM_PROMPT = """You are Quantum AI, the options-strategy reasoning layer of the NCI nerdcommand trading assistant.

Rules:
- You explain and stress-test strategy recommendations; you never place trades.
- Ground every answer in the provided market context, user constraints, and recommendation set.
- Quantify when possible (probabilities, breakevens, max loss vs the user's limit).
- Flag risk honestly, including when the user's idea is better than the recommendation.
- Keep answers under 250 words unless asked for depth.
- Always note this is educational analysis, not investment advice, when giving a final verdict."""


@dataclass
class DialogueTurn:
    """One exchange in a reasoning session."""
    role: str  # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, d: dict) -> "DialogueTurn":
        return cls(**d)


class ReasoningSession:
    """
    A persistent multi-turn conversation about one strategy selection.

    Usage:
        session = ReasoningSession(client, context, prefs, result)
        answer = session.ask("Why is the bull put spread ranked above the covered call?")
        answer = session.ask("What happens to it if IV rank drops to 30?")
    """

    def __init__(
        self,
        client: ClaudeReasoningClient,
        context: MarketContext,
        prefs: UserPreferences,
        result: StrategySelectionResult,
    ):
        self.client = client
        self.context = context
        self.prefs = prefs
        self.result = result
        self.turns: list[DialogueTurn] = []
        self.created_at = time.time()

    # ── public API ────────────────────────────────────────────────

    def ask(self, question: str) -> str:
        """Ask a follow-up question; returns the assistant's answer."""
        self.turns.append(DialogueTurn(role="user", content=question))

        if self.client.available:
            answer = self._ask_claude()
        else:
            answer = self._ask_offline(question)

        self.turns.append(DialogueTurn(role="assistant", content=answer))
        return answer

    def transcript(self) -> list[dict]:
        """Full dialogue as dicts (for persistence / dashboard display)."""
        return [t.to_dict() for t in self.turns]

    # ── Claude mode ───────────────────────────────────────────────

    def _ask_claude(self) -> str:
        messages = [{"role": "user", "content": self._grounding_block()}]
        # Replay dialogue so Claude has the full conversation.
        for turn in self.turns:
            messages.append({"role": turn.role, "content": turn.content})

        resp: ClaudeResponse = self.client.complete(
            messages=messages, system=SYSTEM_PROMPT
        )
        if resp.ok and resp.text.strip():
            return resp.text.strip()
        # API failed mid-session — fall back but say so.
        offline = self._ask_offline(self.turns[-1].content)
        return f"[offline fallback — Claude unavailable: {resp.error}]\n{offline}"

    def _grounding_block(self) -> str:
        """Context block sent as the first user message of every API call."""
        recs = "\n".join(
            f"  {i}. {r.strategy.value} — entry ${r.entry_price:.2f}, "
            f"max profit ${r.max_profit:.2f}, max loss ${r.max_loss:.2f}, "
            f"breakeven ${r.breakeven_price:.2f}, P(profit) {r.probability_profit:.0%}, "
            f"confidence {r.confidence_score:.0%}, risk {r.risk_rating}. "
            f"Rationale: {r.reasoning}"
            for i, r in enumerate(self.result.recommendations, 1)
        )
        event = (
            f"{self.context.event_proximity_days:.1f} days"
            if self.context.event_proximity_days is not None
            else "none scheduled"
        )
        return f"""Here is the live selection you are reasoning about. Use it to answer my follow-up questions.

MARKET CONTEXT — {self.context.symbol} @ ${self.context.price:.2f}
  IV rank {self.context.iv_rank:.0f}% (trend {self.context.iv_trend:+.2f}) | spot trend {self.context.spot_trend:+.2f}
  expected move ${self.context.expected_move:.2f} | liquidity {self.context.liquidity_score:.2f}
  next event: {event} | news sentiment {self.context.news_sentiment:+.2f}

MY CONSTRAINTS
  risk profile {self.prefs.risk_profile.value} | bias {self.prefs.bias}
  max loss ${self.prefs.max_loss_dollars:.2f} | horizon {self.prefs.time_horizon_days} days

CURRENT RECOMMENDATIONS
{recs}

Acknowledge silently and answer my questions that follow."""

    # ── offline mode ──────────────────────────────────────────────

    def _ask_offline(self, question: str) -> str:
        """Deterministic template answer keyed on common question shapes."""
        q = question.lower()
        top = self.result.recommendations[0]
        name = top.strategy.value.replace("_", " ")

        if "why" in q and ("rank" in q or "above" in q or "over" in q or "not" in q):
            return (
                f"(offline mode) Ranking driver: {name} scored highest on the "
                f"multi-factor fit — bias alignment ({self.prefs.bias}), IV-rank fit "
                f"({self.context.iv_rank:.0f}%), and your {self.prefs.risk_profile.value} "
                f"risk profile. Lower-ranked strategies lost points on one of those axes. "
                f"Its max loss ${top.max_loss:.2f} sits inside your ${self.prefs.max_loss_dollars:.2f} limit. "
                f"Educational analysis, not investment advice."
            )
        if "iv" in q and ("drop" in q or "fall" in q or "crush" in q or "decrease" in q):
            vega = top.greeks.vega
            direction = "hurts" if vega > 0 else "helps"
            return (
                f"(offline mode) A falling IV rank {direction} the {name}: its vega is "
                f"{vega:+.2f}, so each IV point costs roughly ${abs(vega) * 100:.0f} per "
                f"contract when positive. Premium-selling structures gain from IV crush; "
                f"long-premium structures lose. Educational analysis, not investment advice."
            )
        if "risk" in q or "lose" in q or "loss" in q or "worst" in q:
            return (
                f"(offline mode) Worst case for {name}: ${top.max_loss:.2f} "
                f"({top.max_loss / self.prefs.max_loss_dollars:.0%} of your stated limit), "
                f"hit if {self.context.symbol} moves through the short strike by expiry. "
                f"Breakeven ${top.breakeven_price:.2f}. Educational analysis, not investment advice."
            )
        return (
            f"(offline mode) Top pick is {name} at {top.confidence_score:.0%} confidence — "
            f"max profit ${top.max_profit:.2f} vs max loss ${top.max_loss:.2f}, "
            f"breakeven ${top.breakeven_price:.2f}. Set ANTHROPIC_API_KEY for full AI "
            f"reasoning. Educational analysis, not investment advice."
        )
