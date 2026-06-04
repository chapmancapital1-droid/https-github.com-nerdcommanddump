"""SQLite trade journal — logs every entry, exit, P&L, strategy, and reason."""
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from config import DB_PATH

logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,
    direction   INTEGER NOT NULL,   -- 1=buy, -1=sell
    lots        REAL    NOT NULL,
    entry_price REAL    NOT NULL,
    entry_time  TEXT    NOT NULL,
    exit_price  REAL,
    exit_time   TEXT,
    pnl_pips    REAL,
    pnl_usd     REAL,
    strategy    TEXT,
    reason      TEXT,
    scalp_count INTEGER DEFAULT 0
);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript(DDL)
    logger.info("Trade DB ready: %s", DB_PATH)


def log_entry(symbol: str, direction: int, lots: float, entry_price: float,
              strategy: str) -> int:
    sql = """INSERT INTO trades (symbol, direction, lots, entry_price, entry_time, strategy)
             VALUES (?, ?, ?, ?, ?, ?)"""
    with _conn() as con:
        cur = con.execute(sql, (symbol, direction, lots, entry_price,
                                datetime.utcnow().isoformat(), strategy))
        trade_id = cur.lastrowid
    logger.info("Trade #%d opened: %s %s %.2f lots @ %.5f",
                trade_id, symbol, "BUY" if direction == 1 else "SELL", lots, entry_price)
    return trade_id


def log_exit(trade_id: int, exit_price: float, pnl_pips: float,
             pnl_usd: float, reason: str, scalp_count: int = 0) -> None:
    sql = """UPDATE trades SET exit_price=?, exit_time=?, pnl_pips=?, pnl_usd=?,
             reason=?, scalp_count=? WHERE id=?"""
    with _conn() as con:
        con.execute(sql, (exit_price, datetime.utcnow().isoformat(),
                          pnl_pips, pnl_usd, reason, scalp_count, trade_id))
    logger.info("Trade #%d closed: reason=%s  pips=%.1f  usd=%.2f",
                trade_id, reason, pnl_pips, pnl_usd)


def daily_pnl(date: Optional[str] = None) -> float:
    d = date or datetime.utcnow().strftime("%Y-%m-%d")
    sql = "SELECT COALESCE(SUM(pnl_usd), 0) FROM trades WHERE entry_time LIKE ?"
    with _conn() as con:
        row = con.execute(sql, (f"{d}%",)).fetchone()
    return float(row[0])


def open_trades() -> List[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM trades WHERE exit_price IS NULL ORDER BY id"
        ).fetchall()


def recent_trades(n: int = 20) -> List[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
