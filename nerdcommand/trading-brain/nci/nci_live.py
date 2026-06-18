"""NCI live feed reader — consumes JSON written by NCI_GodMode_v3_2_Fusion.mq4.

The EA writes two files on every new bar:
  NCI_LiveData.json     — account state, ABC stage, ADX, FER, buy/sell scores
  signal_proposal.json  — proposed trade with confluence, SL/TP, R:R, qualifies flag

Point MT4_FILES_DIR at the MT4 terminal's MFiles folder (portable mode default or
%APPDATA%\\MetaQuotes\\Terminal\\<INSTANCE_ID>\\MFiles\\).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import (
    BRIDGE_POLL_SEC,
    NCI_LIVE_JSON,
    SIGNAL_PROPOSAL_JSON,
)

# ABC stage labels mirror the EA
STAGE_LABEL = {0: "A_CONSOLIDATION", 1: "B_EXPANSION", 2: "C_CONTRACTION"}


@dataclass
class NCILiveData:
    """Parsed NCI_LiveData.json — emitted by the EA on every new bar."""
    balance: float
    equity: float
    margin: float
    drawdown: float           # fraction, e.g. -0.002 = -0.2%
    trades_daily: int
    consec_losses: int
    abc_stage: int            # 0=A 1=B 2=C
    abc_stage_h4: int
    adx: float
    fer: float
    buy_score: int            # of 15
    sell_score: int           # of 15
    atr: float
    timestamp: str

    @classmethod
    def from_dict(cls, d: dict) -> "NCILiveData":
        return cls(
            balance=d.get("balance", 0.0),
            equity=d.get("equity", 0.0),
            margin=d.get("margin", 0.0),
            drawdown=d.get("drawdown", 0.0),
            trades_daily=d.get("trades_daily", 0),
            consec_losses=d.get("consec_losses", 0),
            abc_stage=d.get("abc_stage", 0),
            abc_stage_h4=d.get("abc_stage_h4", 0),
            adx=d.get("adx", 0.0),
            fer=d.get("fer", 0.0),
            buy_score=d.get("buy_score", 0),
            sell_score=d.get("sell_score", 0),
            atr=d.get("atr", 0.0),
            timestamp=d.get("timestamp", ""),
        )

    def format_table(self) -> str:
        stage  = STAGE_LABEL.get(self.abc_stage,    "?")
        stageh4 = STAGE_LABEL.get(self.abc_stage_h4, "?")
        dd_pct = self.drawdown * 100
        bar = lambda score: ("█" * score) + ("░" * (15 - score))
        return "\n".join([
            f"╔══ NCI LIVE  {self.timestamp} ══╗",
            f"  Balance  ${self.balance:>10,.2f}",
            f"  Equity   ${self.equity:>10,.2f}   DD {dd_pct:>+.2f}%",
            f"  Margin   ${self.margin:>10,.2f}",
            f"",
            f"  Stage (M1): {stage}",
            f"  Stage (H4): {stageh4}",
            f"  ADX {self.adx:>5.1f}   FER {self.fer:>5.3f}   ATR {self.atr:.5f}",
            f"",
            f"  BUY  [{bar(self.buy_score)}] {self.buy_score:>2}/15",
            f"  SELL [{bar(self.sell_score)}] {self.sell_score:>2}/15",
            f"",
            f"  Open trades: {self.trades_daily}   Consec losses: {self.consec_losses}",
            f"╚{'═'*44}╝",
        ])


@dataclass
class SignalProposal:
    """Parsed signal_proposal.json — proposed trade from the EA."""
    symbol: str
    action: str           # "BUY" | "SELL"
    mode: str             # ABC stage label
    godmode_score: float  # confluence / 15 * 10
    confluence: int
    confluence_max: int
    abc_stage: str
    sl_pips: float
    tp_pips: float
    risk_reward: float
    qualifies: bool
    timestamp: str
    approved: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "SignalProposal":
        return cls(
            symbol=d.get("symbol", ""),
            action=d.get("action", ""),
            mode=d.get("mode", ""),
            godmode_score=d.get("godmode_score", 0.0),
            confluence=d.get("confluence", 0),
            confluence_max=d.get("confluence_max", 15),
            abc_stage=d.get("abc_stage", ""),
            sl_pips=d.get("sl_pips", 0.0),
            tp_pips=d.get("tp_pips", 0.0),
            risk_reward=d.get("risk_reward", 0.0),
            qualifies=d.get("qualifies", False),
            timestamp=d.get("timestamp", ""),
            approved=d.get("approved", False),
        )

    def to_agent_prompt(self, live: Optional[NCILiveData] = None) -> str:
        """Format as a prompt for the NCI LLM agent."""
        ctx = ""
        if live:
            ctx = (
                f" ABC={STAGE_LABEL.get(live.abc_stage,'?')},"
                f" ADX={live.adx:.1f},"
                f" FER={live.fer:.3f},"
                f" ATR={live.atr:.5f},"
                f" open_trades={live.trades_daily},"
                f" consec_losses={live.consec_losses}"
            )
        return (
            f"{self.symbol} {self.action} proposal:"
            f" confluence {self.confluence}/{self.confluence_max},"
            f" SL={self.sl_pips:.0f}p, TP={self.tp_pips:.0f}p, R:R={self.risk_reward:.2f},"
            f" stage={self.abc_stage}, qualifies={self.qualifies}.{ctx}"
            f" Assess this trade. Output: APPROVE or REJECT, then one-line reason."
        )

    def format_table(self) -> str:
        q = "✅ QUALIFIES" if self.qualifies else "❌ NOT QUALIFYING"
        a = "✅ APPROVED" if self.approved else "⏳ PENDING"
        return "\n".join([
            f"  Signal: {self.symbol} {self.action}",
            f"  Mode:   {self.mode}",
            f"  Score:  {self.confluence}/{self.confluence_max}  ({self.godmode_score:.1f}/10)",
            f"  SL:     {self.sl_pips:.0f} pips   TP: {self.tp_pips:.0f} pips   R:R {self.risk_reward:.2f}",
            f"  Gate:   {q}",
            f"  LLM:    {a}",
        ])


def _read_json(path: str) -> Optional[dict]:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def read_live(path: str = NCI_LIVE_JSON) -> Optional[NCILiveData]:
    d = _read_json(path)
    return NCILiveData.from_dict(d) if d else None


def read_proposal(path: str = SIGNAL_PROPOSAL_JSON) -> Optional[SignalProposal]:
    d = _read_json(path)
    return SignalProposal.from_dict(d) if d else None


def watch(poll_sec: int = BRIDGE_POLL_SEC):
    """Generator — yields (NCILiveData, SignalProposal) each time the EA writes new data."""
    seen_ts: Optional[str] = None
    while True:
        live = read_live()
        if live and live.timestamp != seen_ts:
            seen_ts = live.timestamp
            proposal = read_proposal()
            yield live, proposal
        time.sleep(poll_sec)


if __name__ == "__main__":
    live = read_live()
    proposal = read_proposal()

    if live:
        print(live.format_table())
    else:
        print(f"[NCI] No live data at {NCI_LIVE_JSON}")
        print(f"      Set MT4_FILES_DIR env var to your MT4 terminal's MFiles folder.")

    if proposal:
        print()
        print(proposal.format_table())
