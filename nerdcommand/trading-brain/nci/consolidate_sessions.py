"""Data consolidation utility — merge trading brain data from all Claude sessions.

Imports and consolidates:
  - Trade history from previous sessions (SQLite)
  - JSON snapshots from prior runs
  - Backtester results
  - Signal logs
  - Strategy parameters

Usage:
  python consolidate_sessions.py --import-db /path/old/trades.db
  python consolidate_sessions.py --import-json /path/old/nci_bridge_state.json
  python consolidate_sessions.py --import-all /path/old/trading-brain
  python consolidate_sessions.py --merge-history
"""
import argparse
import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from config import BRIDGE_DATA_DIR, MT4_FILES_DIR

# -- Archive locations --------------------------------------------------------

SESSIONS_ARCHIVE = os.path.join(BRIDGE_DATA_DIR, "session_archives")
IMPORTED_TRADES_DB = os.path.join(BRIDGE_DATA_DIR, "imported_trades.db")
CONSOLIDATED_HISTORY = os.path.join(BRIDGE_DATA_DIR, "consolidated_history.jsonl")


# -- Schema for unified trade log -----------------------------------------------

DDL_UNIFIED_TRADES = """
CREATE TABLE IF NOT EXISTS consolidated_trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT,              -- Claude session ID or EA instance
    symbol          TEXT    NOT NULL,
    direction       INTEGER NOT NULL,  -- 1=buy, -1=sell
    lots            REAL    NOT NULL,
    entry_price     REAL    NOT NULL,
    entry_time      TEXT    NOT NULL,
    exit_price      REAL,
    exit_time       TEXT,
    pnl_pips        REAL,
    pnl_usd         REAL,
    strategy        TEXT,               -- e.g., "PORT_GODMODE", "PORT_SCALP"
    reason          TEXT,               -- exit reason
    scalp_count     INTEGER DEFAULT 0,
    ea_version      TEXT,               -- "3.2_Fusion", "1.8_Hybrid", "2.0_ScalpBot"
    port_name       TEXT,               -- which entry port fired
    confluence_score INTEGER,           -- voter count at entry
    abc_stage       TEXT,               -- market regime at entry
    imported_at     TEXT NOT NULL       -- when imported
);

CREATE INDEX IF NOT EXISTS idx_session_id ON consolidated_trades(session_id);
CREATE INDEX IF NOT EXISTS idx_symbol ON consolidated_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_entry_time ON consolidated_trades(entry_time);
"""


# -- Import Utilities -------------------------------------------------------

def _ensure_db(path: str) -> sqlite3.Connection:
    """Create DB and tables if not exists."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(DDL_UNIFIED_TRADES)
    conn.commit()
    return conn


def _copy_json_snapshot(src_path: str, session_id: str) -> str:
    """Archive JSON snapshot and return path."""
    os.makedirs(SESSIONS_ARCHIVE, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    basename = os.path.basename(src_path)
    name, ext = os.path.splitext(basename)
    dest = os.path.join(SESSIONS_ARCHIVE, f"{session_id}_{ts}_{name}{ext}")
    shutil.copy2(src_path, dest)
    return dest


def import_trades_db(src_db_path: str, session_id: str, ea_version: str = "unknown") -> int:
    """Import trade records from old session's DB."""
    if not os.path.exists(src_db_path):
        print(f"❌ Source DB not found: {src_db_path}")
        return 0

    try:
        src = sqlite3.connect(src_db_path)
        src.row_factory = sqlite3.Row
        old_trades = src.execute(
            "SELECT * FROM trades ORDER BY id"
        ).fetchall()
        src.close()
    except Exception as e:
        print(f"❌ Error reading source DB: {e}")
        return 0

    if not old_trades:
        print(f"ℹ️  No trades found in {src_db_path}")
        return 0

    dest = _ensure_db(IMPORTED_TRADES_DB)
    now = datetime.utcnow().isoformat()
    imported = 0

    for row in old_trades:
        try:
            dest.execute(
                """INSERT INTO consolidated_trades
                   (session_id, symbol, direction, lots, entry_price, entry_time,
                    exit_price, exit_time, pnl_pips, pnl_usd, strategy, reason,
                    scalp_count, ea_version, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, row["symbol"], row["direction"], row["lots"],
                 row["entry_price"], row["entry_time"], row.get("exit_price"),
                 row.get("exit_time"), row.get("pnl_pips"), row.get("pnl_usd"),
                 row.get("strategy"), row.get("reason"), row.get("scalp_count", 0),
                 ea_version, now)
            )
            imported += 1
        except Exception as e:
            print(f"⚠️  Skipped trade (error): {e}")

    dest.commit()
    dest.close()
    return imported


def import_bridge_state(src_json_path: str, session_id: str) -> bool:
    """Archive nci_bridge_state.json snapshot."""
    if not os.path.exists(src_json_path):
        print(f"❌ JSON snapshot not found: {src_json_path}")
        return False

    try:
        with open(src_json_path) as f:
            data = json.load(f)
        dest = _copy_json_snapshot(src_json_path, session_id)
        print(f"✅ Archived snapshot to {dest}")
        return True
    except Exception as e:
        print(f"❌ Error importing JSON: {e}")
        return False


def import_signal_logs(src_dir: str, session_id: str) -> int:
    """Archive signal approval logs."""
    signal_log = os.path.join(src_dir, "signals", "approvals.jsonl")
    if not os.path.exists(signal_log):
        return 0

    try:
        with open(signal_log) as src:
            lines = src.readlines()

        os.makedirs(SESSIONS_ARCHIVE, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(SESSIONS_ARCHIVE, f"{session_id}_{ts}_approvals.jsonl")

        with open(dest, "w") as f:
            f.writelines(lines)

        print(f"✅ Imported {len(lines)} signal records")
        return len(lines)
    except Exception as e:
        print(f"❌ Error importing signals: {e}")
        return 0


def merge_all_trades() -> Dict:
    """Merge consolidated_trades DB with current trades.db."""
    try:
        conn = _ensure_db(IMPORTED_TRADES_DB)
        rows = conn.execute(
            "SELECT COUNT(*) as cnt, SUM(pnl_usd) as total_pnl FROM consolidated_trades"
        ).fetchone()
        conn.close()

        return {
            "total_trades": rows["cnt"],
            "total_pnl": rows["total_pnl"] or 0.0,
            "db_path": IMPORTED_TRADES_DB,
        }
    except Exception as e:
        print(f"❌ Error merging: {e}")
        return {}


def report_consolidation() -> None:
    """Show summary of consolidated data."""
    try:
        conn = _ensure_db(IMPORTED_TRADES_DB)

        total = conn.execute("SELECT COUNT(*) as cnt FROM consolidated_trades").fetchone()
        by_session = conn.execute(
            "SELECT session_id, COUNT(*) as cnt, SUM(pnl_usd) as pnl FROM consolidated_trades GROUP BY session_id"
        ).fetchall()
        by_ea = conn.execute(
            "SELECT ea_version, COUNT(*) as cnt, SUM(pnl_usd) as pnl FROM consolidated_trades GROUP BY ea_version"
        ).fetchall()

        print("\n" + "=" * 70)
        print("NCI BRIDGE — DATA CONSOLIDATION REPORT")
        print("=" * 70)

        print(f"\nTotal Consolidated Trades: {total['cnt']}")

        print("\nBy Session:")
        for row in by_session:
            print(f"  {row[0]:40} {row[1]:>4} trades  ${row[2]:>10,.2f} P&L")

        print("\nBy EA Version:")
        for row in by_ea:
            print(f"  {row[0]:40} {row[1]:>4} trades  ${row[2]:>10,.2f} P&L")

        print(f"\nConsolidated DB: {IMPORTED_TRADES_DB}")
        print(f"Session Archives: {SESSIONS_ARCHIVE}")
        print("=" * 70 + "\n")

        conn.close()
    except Exception as e:
        print(f"❌ Error reporting: {e}")


# -- CLI -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Consolidate trading brain data from multiple Claude sessions"
    )
    parser.add_argument(
        "--import-db",
        help="Import trades from old session DB (path/to/trades.db)"
    )
    parser.add_argument(
        "--import-json",
        help="Archive nci_bridge_state.json from old session"
    )
    parser.add_argument(
        "--import-signals",
        help="Import signal approval logs (path/to/trading-brain)"
    )
    parser.add_argument(
        "--import-all",
        help="Import all data from old trading-brain directory"
    )
    parser.add_argument(
        "--session-id",
        default=datetime.utcnow().strftime("session_%Y%m%d_%H%M%S"),
        help="Session identifier (default: timestamp)"
    )
    parser.add_argument(
        "--ea-version",
        default="unknown",
        help="EA version (e.g., 3.2_Fusion, 1.8_Hybrid)"
    )
    parser.add_argument(
        "--merge-history",
        action="store_true",
        help="Report consolidated history"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Show consolidation report"
    )

    args = parser.parse_args()

    if args.import_db:
        print(f"📥 Importing trades from {args.import_db}...")
        count = import_trades_db(args.import_db, args.session_id, args.ea_version)
        print(f"✅ Imported {count} trades")

    if args.import_json:
        print(f"📥 Importing JSON snapshot {args.import_json}...")
        import_bridge_state(args.import_json, args.session_id)

    if args.import_signals:
        print(f"📥 Importing signals from {args.import_signals}...")
        count = import_signal_logs(args.import_signals, args.session_id)

    if args.import_all:
        print(f"📥 Importing all data from {args.import_all}...")

        old_db = os.path.join(args.import_all, "trades.db")
        if os.path.exists(old_db):
            count = import_trades_db(old_db, args.session_id, args.ea_version)
            print(f"✅ Imported {count} trades")

        old_json = os.path.join(args.import_all, "nci_bridge_state.json")
        if os.path.exists(old_json):
            import_bridge_state(old_json, args.session_id)

        count = import_signal_logs(args.import_all, args.session_id)

    if args.merge_history:
        print("🔄 Merging all session history...")
        result = merge_all_trades()
        if result:
            print(f"✅ Merged {result['total_trades']} trades")
            print(f"   Total P&L: ${result['total_pnl']:,.2f}")

    if args.report:
        report_consolidation()

    if not any([args.import_db, args.import_json, args.import_signals,
                args.import_all, args.merge_history, args.report]):
        parser.print_help()


if __name__ == "__main__":
    main()
