"""NERDCOMMAND Micro-Lot Capital Preservation — main trading loop.

Run:
    python main.py            # live paper/sim mode
    python main.py --once     # single scan, no loop

Each iteration:
  1. Fetch OHLCV data for all instruments
  2. Run all 4 strategy signals
  3. Fuse signals → position size decision
  4. Risk checks (daily limits, scalp count)
  5. Open / manage / close positions
  6. Log to SQLite
"""
import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from config import (
    CRYPTO, FOREX_PAIRS, LOG_DIR, PAIRS_MAP,
)
from data_feed import get_feed
from fusion import fuse
from position_tracker import daily_pnl, init_db, log_entry, log_exit, open_trades
from risk import RiskManager, atr
from strategies import Signal
from strategies import breakout, mean_reversion, pairs_trading, stat_arb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(LOG_DIR) / "micro_lot.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

SCAN_INTERVAL_SEC = 300   # 5-minute heartbeat


def _collect_signals(feed) -> list[Signal]:
    signals: list[Signal] = []

    # --- Breakout: all forex pairs ---
    for sym in FOREX_PAIRS:
        try:
            bars = feed.fetch(sym + "=X", period="60d", interval="1d")
            sig = breakout.compute(bars["close"], bars["high"], bars["low"])
            if sig.is_active:
                logger.info("[breakout] %s: %s", sym, sig.reason)
                signals.append(sig)
        except Exception as exc:
            logger.debug("Breakout fetch error %s: %s", sym, exc)

    # --- Mean reversion: crypto ---
    for sym in CRYPTO:
        try:
            bars = feed.fetch(sym, period="60d", interval="1d")
            sig = mean_reversion.compute(bars["close"])
            if sig.is_active:
                logger.info("[mean_rev] %s: %s", sym, sig.reason)
                signals.append(sig)
        except Exception as exc:
            logger.debug("Mean-rev fetch error %s: %s", sym, exc)

    # --- Stat arb + pairs trading: equity pairs ---
    for sym_a, sym_b in PAIRS_MAP:
        try:
            bars_a = feed.fetch(sym_a, period="90d", interval="1d")
            bars_b = feed.fetch(sym_b, period="90d", interval="1d")
            n = min(len(bars_a["close"]), len(bars_b["close"]))
            ca, cb = bars_a["close"][-n:], bars_b["close"][-n:]

            sig_sa = stat_arb.compute(ca, cb, sym_a, sym_b)
            sig_pt = pairs_trading.compute(ca, cb, sym_a, sym_b)
            for sig in (sig_sa, sig_pt):
                if sig.is_active:
                    logger.info("[%s] %s/%s: %s", sig.strategy, sym_a, sym_b, sig.reason)
                    signals.append(sig)
        except Exception as exc:
            logger.debug("Pair fetch error %s/%s: %s", sym_a, sym_b, exc)

    return signals


def _get_reference_atr(feed) -> float:
    """Quick ATR estimate from EURUSD for stop sizing."""
    try:
        bars = feed.fetch("EURUSD=X", period="30d", interval="1d")
        return atr(bars["high"], bars["low"], bars["close"])
    except Exception:
        return 0.001


def run_once(risk: RiskManager, feed) -> None:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    dpnl = daily_pnl(today)

    if risk.daily_pnl != dpnl:
        risk.daily_pnl = dpnl

    logger.info("=== Scan  daily_pnl=%.2f  scalps=%d ===", risk.daily_pnl, risk.scalp_count)

    # Check open positions first
    open_list = open_trades()
    if open_list:
        logger.info("%d open trade(s) — holding", len(open_list))
        return

    if not risk.can_trade():
        return

    signals = _collect_signals(feed)
    if not signals:
        logger.info("No active signals this scan")
        return

    fused = fuse(signals)
    logger.info("Fusion: %s", fused.reason)

    if not fused.should_trade:
        return

    cur_atr = _get_reference_atr(feed)
    pos = risk.open_position(fused.direction, 1.0, cur_atr)   # price=1.0 placeholder
    strategy_names = ", ".join(s.strategy for s in fused.signals)
    log_entry("FUSED", fused.direction, fused.lot_size, 1.0, strategy_names)
    logger.info("Position opened: dir=%d  lots=%.2f  atr=%.5f",
                fused.direction, fused.lot_size, cur_atr)


def main() -> None:
    parser = argparse.ArgumentParser(description="NERDCOMMAND Micro-Lot Trader")
    parser.add_argument("--once", action="store_true", help="Single scan then exit")
    args = parser.parse_args()

    init_db()
    feed = get_feed()
    risk = RiskManager()

    logger.info("NERDCOMMAND Micro-Lot Trader starting")

    if args.once:
        run_once(risk, feed)
        return

    while True:
        try:
            run_once(risk, feed)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            break
        except Exception as exc:
            logger.error("Scan error: %s", exc, exc_info=True)
        time.sleep(SCAN_INTERVAL_SEC)


if __name__ == "__main__":
    main()
