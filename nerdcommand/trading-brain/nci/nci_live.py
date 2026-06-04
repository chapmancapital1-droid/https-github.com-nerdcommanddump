"""NCI live feed reader — polls MT4 bridge JSON snapshots from BRIDGE_DATA_DIR."""
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import BRIDGE_DATA_DIR, BRIDGE_POLL_SEC


@dataclass
class Position:
    ticket: int
    symbol: str
    side: str          # "BUY" | "SELL"
    lots: float
    open_price: float
    current_price: float
    profit: float
    swap: float = 0.0
    comment: str = ""


@dataclass
class AccountSnapshot:
    timestamp: float
    balance: float
    equity: float
    floating: float
    daily_pnl: float
    margin_used: float
    margin_free: float
    drawdown_pct: float
    circuit_breaker_locked: bool
    positions: list[Position] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "AccountSnapshot":
        positions = [Position(**p) for p in d.get("positions", [])]
        return cls(
            timestamp=d["timestamp"],
            balance=d["balance"],
            equity=d["equity"],
            floating=d.get("floating", d["equity"] - d["balance"]),
            daily_pnl=d.get("daily_pnl", 0.0),
            margin_used=d.get("margin_used", 0.0),
            margin_free=d.get("margin_free", 0.0),
            drawdown_pct=d.get("drawdown_pct", 0.0),
            circuit_breaker_locked=d.get("circuit_breaker_locked", False),
            positions=positions,
        )

    def format_table(self) -> str:
        cb = "🔴 LOCKED" if self.circuit_breaker_locked else "✅ open"
        lines = [
            f"NCI Live  {time.strftime('%H:%M:%S UTC', time.gmtime(self.timestamp))}",
            f"  Balance   ${self.balance:>10,.2f}",
            f"  Equity    ${self.equity:>10,.2f}",
            f"  Floating  ${self.floating:>+10.2f}",
            f"  Daily P&L ${self.daily_pnl:>+10.2f}",
            f"  DD        {self.drawdown_pct:>6.2f}%   CB {cb}",
            "",
            f"  {'SYM':<10} {'SIDE':<5} {'LOTS':>5} {'ENTRY':>8} {'NOW':>8} {'P&L':>8}",
            "  " + "-" * 52,
        ]
        for p in self.positions:
            lines.append(
                f"  {p.symbol:<10} {p.side:<5} {p.lots:>5.2f} "
                f"{p.open_price:>8.5f} {p.current_price:>8.5f} "
                f"{p.profit:>+8.2f}"
            )
        return "\n".join(lines)


def _latest_snapshot_path(data_dir: str) -> Optional[Path]:
    d = Path(data_dir)
    if not d.exists():
        return None
    files = sorted(d.glob("snapshot_*.json"), reverse=True)
    return files[0] if files else None


def read_latest(data_dir: str = BRIDGE_DATA_DIR) -> Optional[AccountSnapshot]:
    path = _latest_snapshot_path(data_dir)
    if not path:
        return None
    try:
        with open(path) as f:
            return AccountSnapshot.from_dict(json.load(f))
    except Exception:
        return None


def watch(data_dir: str = BRIDGE_DATA_DIR, poll_sec: int = BRIDGE_POLL_SEC):
    """Generator — yields AccountSnapshot each time the bridge writes a new file."""
    seen: Optional[str] = None
    while True:
        path = _latest_snapshot_path(data_dir)
        if path and str(path) != seen:
            snap = read_latest(data_dir)
            if snap:
                seen = str(path)
                yield snap
        time.sleep(poll_sec)


if __name__ == "__main__":
    snap = read_latest()
    if snap:
        print(snap.format_table())
    else:
        print(f"No snapshot found in {BRIDGE_DATA_DIR}")
