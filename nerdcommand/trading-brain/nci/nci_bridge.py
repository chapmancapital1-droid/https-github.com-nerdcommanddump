"""nci Bridge — Unified Trading Brain Dashboard

Consolidates ALL trading data from:
  - NCI_GodMode_v3_2_Fusion.mq4 (current EA)
  - NCI_Hybrid_v1.8.mq4 (rich dashboard signals)
  - NCI_ScalpBot_M5_v2.0.mq4 (M5 scalp metrics)
  - NCI_GodMode_v3.mq4 (legacy)
  - All JSON outputs (LiveData, Signals, Commands)
  - SQLite trade journal (position_tracker)
  - Backtester results and performance analytics

Outputs unified JSON and rich terminal display.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import (
    BRIDGE_POLL_SEC,
    NCI_LIVE_JSON,
    SIGNAL_PROPOSAL_JSON,
    BRIDGE_DATA_DIR,
    MT4_FILES_DIR,
)

# -- Constants ----------------------------------------------------------------

STAGE_LABEL = {0: "A_CONSOLIDATION", 1: "B_EXPANSION", 2: "C_CONTRACTION"}

# All possible JSON files the EA can write (across versions)
JSON_VERSIONS = {
    "v3.2_live": "NCI_LiveData.json",
    "v3.2_signal": "signal_proposal.json",
    "v1.8_live": "NCI_Signal.json",  # Hybrid rich signal
    "v1.8_cmd": "NCI_Commands.json",  # Hybrid runtime commands
    "v2.0_monitor": "NCI_Monitor.json",  # ScalpBot M5 stats
}

# -- Dataclasses for v3.2 EA Data -----------------------------------------------

@dataclass
class NCILiveData:
    """Parsed NCI_LiveData.json from v3.2 EA."""
    balance: float
    equity: float
    margin: float
    drawdown: float
    trades_daily: int
    consec_losses: int
    abc_stage: int
    abc_stage_h4: int
    adx: float
    fer: float
    buy_score: int
    sell_score: int
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


@dataclass
class SignalProposal:
    """Parsed signal_proposal.json from v3.2 EA."""
    symbol: str
    action: str
    mode: str
    godmode_score: float
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


@dataclass
class HybridSignal:
    """Parsed NCI_Signal.json from Hybrid v1.8 EA (RICH voter breakdown)."""
    timestamp: str
    symbol: str
    direction: str
    score: int
    max_score: int
    fired: bool
    blocked_reason: Optional[str]
    voters: List[str] = field(default_factory=list)
    spread: float = 0.0
    atr: float = 0.0
    buy_score: int = 0
    sell_score: int = 0
    htf_buy: bool = False
    htf_sell: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "HybridSignal":
        return cls(
            timestamp=d.get("ts", ""),
            symbol=d.get("pair", ""),
            direction=d.get("direction", ""),
            score=d.get("score", 0),
            max_score=d.get("max", 15),
            fired=d.get("fired", False),
            blocked_reason=d.get("blocked_reason"),
            voters=d.get("voters", []),
            spread=d.get("spread", 0.0),
            atr=d.get("atr", 0.0),
            buy_score=d.get("buy_score", 0),
            sell_score=d.get("sell_score", 0),
            htf_buy=d.get("htf_buy", False),
            htf_sell=d.get("htf_sell", False),
        )


@dataclass
class CommandOverride:
    """Parsed NCI_Commands.json from Hybrid v1.8 EA (runtime parameters)."""
    min_confluence: Optional[int] = None
    max_spread: Optional[float] = None
    risk_pct: Optional[float] = None
    trail_step: Optional[float] = None
    scalp_mode: Optional[bool] = None
    timestamp: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "CommandOverride":
        return cls(
            min_confluence=d.get("min_confluence"),
            max_spread=d.get("max_spread"),
            risk_pct=d.get("risk_pct"),
            trail_step=d.get("trail_step"),
            scalp_mode=d.get("scalp_mode"),
            timestamp=d.get("timestamp", ""),
        )


# -- Unified Bridge State -------------------------------------------------------

@dataclass
class NCIBridgeState:
    """Complete unified state of all trading brain data."""
    # v3.2 EA current data
    live: Optional[NCILiveData] = None
    proposal: Optional[SignalProposal] = None

    # Hybrid v1.8 rich data
    hybrid_signal: Optional[HybridSignal] = None
    command_override: Optional[CommandOverride] = None

    # Performance aggregates (from SQLite)
    daily_trades: int = 0
    daily_pnl: float = 0.0
    daily_wins: int = 0
    daily_losses: int = 0
    open_positions: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0

    # Historical stats (all-time)
    total_trades: int = 0
    total_pnl: float = 0.0
    all_time_wins: int = 0
    all_time_losses: int = 0
    all_time_win_rate: float = 0.0
    sharpe_ratio: float = 0.0

    # Metadata
    last_update: str = ""
    ea_version: str = "unknown"
    active_ports: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "live": asdict(self.live) if self.live else None,
            "proposal": asdict(self.proposal) if self.proposal else None,
            "hybrid_signal": asdict(self.hybrid_signal) if self.hybrid_signal else None,
            "command_override": asdict(self.command_override) if self.command_override else None,
            "daily": {
                "trades": self.daily_trades,
                "pnl": self.daily_pnl,
                "wins": self.daily_wins,
                "losses": self.daily_losses,
                "win_rate": round(self.win_rate, 4),
                "avg_win": round(self.avg_win, 2),
                "avg_loss": round(self.avg_loss, 2),
                "profit_factor": round(self.profit_factor, 2),
            },
            "all_time": {
                "trades": self.total_trades,
                "pnl": round(self.total_pnl, 2),
                "wins": self.all_time_wins,
                "losses": self.all_time_losses,
                "win_rate": round(self.all_time_win_rate, 4),
                "sharpe_ratio": round(self.sharpe_ratio, 2),
            },
            "positions": self.open_positions,
            "last_update": self.last_update,
            "ea_version": self.ea_version,
            "active_ports": self.active_ports,
        }


# -- I/O Utilities ---------------------------------------------------------------

def _read_json(path: str) -> Optional[dict]:
    """Safely read JSON file."""
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _write_json(path: str, data: dict) -> None:
    """Write JSON file atomically."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# -- Data Loaders ---------------------------------------------------------------

def read_live(path: str = NCI_LIVE_JSON) -> Optional[NCILiveData]:
    """Read v3.2 live data."""
    d = _read_json(path)
    return NCILiveData.from_dict(d) if d else None


def read_proposal(path: str = SIGNAL_PROPOSAL_JSON) -> Optional[SignalProposal]:
    """Read v3.2 signal proposal."""
    d = _read_json(path)
    return SignalProposal.from_dict(d) if d else None


def read_hybrid_signal(path: Optional[str] = None) -> Optional[HybridSignal]:
    """Read Hybrid v1.8 rich signal (NCI_Signal.json)."""
    if path is None:
        path = os.path.join(MT4_FILES_DIR, "NCI_Signal.json")
    d = _read_json(path)
    return HybridSignal.from_dict(d) if d else None


def read_commands(path: Optional[str] = None) -> Optional[CommandOverride]:
    """Read Hybrid v1.8 command overrides (NCI_Commands.json)."""
    if path is None:
        path = os.path.join(MT4_FILES_DIR, "NCI_Commands.json")
    d = _read_json(path)
    return CommandOverride.from_dict(d) if d else None


def _query_trades_db(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Query trades database."""
    try:
        # Try to use micro-lot DB if available
        db_path = os.getenv("DB_PATH", os.path.join(BRIDGE_DATA_DIR, "trades.db"))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception:
        return []


def _calc_daily_stats() -> Dict[str, Any]:
    """Calculate today's stats from SQLite."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    rows = _query_trades_db(
        "SELECT pnl_usd, pnl_pips FROM trades WHERE exit_time IS NOT NULL AND exit_time LIKE ?",
        (f"{today}%",)
    )

    if not rows:
        return {
            "trades": 0,
            "pnl": 0.0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
        }

    pnls = [r["pnl_usd"] or 0.0 for r in rows]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_pnl = sum(pnls)
    win_rate = len(wins) / len(pnls) if pnls else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses)) / len(losses) if losses else 0.0
    profit_factor = avg_win / avg_loss if avg_loss > 0 else 0.0

    return {
        "trades": len(rows),
        "pnl": total_pnl,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
    }


def _calc_all_time_stats() -> Dict[str, Any]:
    """Calculate all-time stats from SQLite."""
    rows = _query_trades_db(
        "SELECT pnl_usd, pnl_pips FROM trades WHERE exit_time IS NOT NULL"
    )

    if not rows:
        return {
            "trades": 0,
            "pnl": 0.0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
        }

    pnls = [r["pnl_usd"] or 0.0 for r in rows]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_pnl = sum(pnls)
    win_rate = len(wins) / len(pnls) if pnls else 0.0

    # Simple Sharpe (returns / std dev)
    if pnls:
        mean_ret = sum(pnls) / len(pnls)
        variance = sum((p - mean_ret) ** 2 for p in pnls) / len(pnls)
        std_dev = variance ** 0.5
        sharpe = (mean_ret / std_dev) if std_dev > 0 else 0.0
    else:
        sharpe = 0.0

    return {
        "trades": len(rows),
        "pnl": total_pnl,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "sharpe_ratio": sharpe,
    }


# -- Main Bridge Functions -------------------------------------------------------

def load_bridge_state() -> NCIBridgeState:
    """Load complete unified state from all sources."""
    state = NCIBridgeState()

    # Load v3.2 EA data
    state.live = read_live()
    state.proposal = read_proposal()

    # Load Hybrid v1.8 data
    state.hybrid_signal = read_hybrid_signal()
    state.command_override = read_commands()

    # Load SQLite stats
    daily = _calc_daily_stats()
    state.daily_trades = daily.get("trades", 0)
    state.daily_pnl = daily.get("pnl", 0.0)
    state.daily_wins = daily.get("wins", 0)
    state.daily_losses = daily.get("losses", 0)
    state.win_rate = daily.get("win_rate", 0.0)
    state.avg_win = daily.get("avg_win", 0.0)
    state.avg_loss = daily.get("avg_loss", 0.0)
    state.profit_factor = daily.get("profit_factor", 0.0)

    all_time = _calc_all_time_stats()
    state.total_trades = all_time.get("trades", 0)
    state.total_pnl = all_time.get("pnl", 0.0)
    state.all_time_wins = all_time.get("wins", 0)
    state.all_time_losses = all_time.get("losses", 0)
    state.all_time_win_rate = all_time.get("win_rate", 0.0)
    state.sharpe_ratio = all_time.get("sharpe_ratio", 0.0)

    # Open positions
    open_rows = _query_trades_db("SELECT COUNT(*) as cnt FROM trades WHERE exit_time IS NULL")
    state.open_positions = open_rows[0]["cnt"] if open_rows else 0

    # Metadata
    if state.live:
        state.ea_version = "3.2_Fusion"
    state.last_update = datetime.utcnow().isoformat()

    return state


def persist_bridge_state(state: NCIBridgeState) -> str:
    """Write unified state to JSON and return file path."""
    os.makedirs(BRIDGE_DATA_DIR, exist_ok=True)
    path = os.path.join(BRIDGE_DATA_DIR, "nci_bridge_state.json")
    _write_json(path, state.to_dict())
    return path


def format_bridge_table(state: NCIBridgeState) -> str:
    """Rich terminal display of unified state."""
    lines = [
        "╔" + "═" * 66 + "╗",
        "║" + " NCI BRIDGE — UNIFIED TRADING BRAIN DASHBOARD ".center(66) + "║",
        "╠" + "═" * 66 + "╣",
    ]

    # Live Data Section
    if state.live:
        stage = STAGE_LABEL.get(state.live.abc_stage, "?")
        stageh4 = STAGE_LABEL.get(state.live.abc_stage_h4, "?")
        dd_pct = state.live.drawdown * 100
        bar = lambda s: ("█" * s) + ("░" * (15 - s))

        lines.extend([
            "║ ACCOUNT STATE                                                  ║",
            f"║   Balance: ${state.live.balance:>12,.2f}   Equity: ${state.live.equity:>12,.2f}  ║",
            f"║   Margin:  ${state.live.margin:>12,.2f}   DD: {dd_pct:>+6.2f}%                    ║",
            "║                                                                ║",
            f"║   ABC Stage (M1): {stage:<25} (H4): {stageh4}      ║",
            f"║   ADX {state.live.adx:>5.1f}  FER {state.live.fer:>6.3f}  ATR {state.live.atr:>8.5f}                      ║",
            "║                                                                ║",
            f"║   BUY  [{bar(state.live.buy_score)}] {state.live.buy_score:>2}/15   (Score {state.live.buy_score * 10 / 15:.0f}/10)       ║",
            f"║   SELL [{bar(state.live.sell_score)}] {state.live.sell_score:>2}/15   (Score {state.live.sell_score * 10 / 15:.0f}/10)       ║",
            "║                                                                ║",
        ])

        if state.proposal:
            lines.extend([
                f"║ SIGNAL PROPOSAL: {state.proposal.symbol:6} {state.proposal.action:4}                         ║",
                f"║   Confluence: {state.proposal.confluence:>2}/{state.proposal.confluence_max}  Gate: {'✅' if state.proposal.qualifies else '❌'}  RR: {state.proposal.risk_reward:>4.2f}  ║",
                f"║   SL: {state.proposal.sl_pips:>6.0f}p   TP: {state.proposal.tp_pips:>6.0f}p                                 ║",
            ])

    if state.hybrid_signal:
        lines.extend([
            "║                                                                ║",
            f"║ HYBRID v1.8 SIGNAL (Voter Breakdown)                           ║",
            f"║   {state.hybrid_signal.direction:4} {state.hybrid_signal.symbol:6}  Score: {state.hybrid_signal.score:>2}/{state.hybrid_signal.max_score}  Fired: {'✅' if state.hybrid_signal.fired else '❌'}       ║",
            f"║   Voters: {', '.join(state.hybrid_signal.voters)[:48]:48}║",
            f"║   Spread: {state.hybrid_signal.spread:>6.1f}  ATR: {state.hybrid_signal.atr:>8.5f}  HTF: {state.hybrid_signal.htf_buy or state.hybrid_signal.htf_sell}              ║",
        ])

    # Stats Section
    lines.extend([
        "║                                                                ║",
        "║ TODAY'S PERFORMANCE                                            ║",
        f"║   Trades: {state.daily_trades:>2}   P&L: ${state.daily_pnl:>10.2f}   Win%: {state.win_rate * 100:>5.1f}%       ║",
        f"║   Wins: {state.daily_wins:>2}  Losses: {state.daily_losses:>2}  PF: {state.profit_factor:>4.2f}  Avg W/L: ${state.avg_win:>7.2f}/${state.avg_loss:>7.2f}  ║",
        "║                                                                ║",
        "║ ALL-TIME PERFORMANCE                                           ║",
        f"║   Trades: {state.total_trades:>4}   P&L: ${state.total_pnl:>10.2f}   Win%: {state.all_time_win_rate * 100:>5.1f}%       ║",
        f"║   Wins: {state.all_time_wins:>4}  Losses: {state.all_time_losses:>4}  Sharpe: {state.sharpe_ratio:>6.2f}                    ║",
        "║                                                                ║",
        f"║ Open Positions: {state.open_positions:>2}   EA: {state.ea_version:15}                        ║",
        f"║ Last Update: {state.last_update[:19]:45}║",
        "╚" + "═" * 66 + "╝",
    ])

    return "\n".join(lines)


def watch(poll_sec: int = BRIDGE_POLL_SEC):
    """Generator — yields NCIBridgeState each time data updates."""
    seen_live_ts: Optional[str] = None
    while True:
        state = load_bridge_state()
        if state.live and state.live.timestamp != seen_live_ts:
            seen_live_ts = state.live.timestamp
            persist_bridge_state(state)
            yield state
        time.sleep(poll_sec)


# -- CLI -----------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        print("🔴 NCI Bridge — WATCH MODE (press Ctrl+C to exit)")
        print()
        try:
            for state in watch():
                print("\033[2J\033[H")  # Clear screen
                print(format_bridge_table(state))
        except KeyboardInterrupt:
            print("\n✋ Stopped.")
    else:
        state = load_bridge_state()
        persist_bridge_state(state)
        print(format_bridge_table(state))
