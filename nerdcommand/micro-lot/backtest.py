"""Simple event-driven backtester for the micro-lot framework.

Usage:
    python backtest.py                     # default: EURUSD breakout, 2yr
    python backtest.py --strategy mean_rev --symbol BTC-USD
    python backtest.py --strategy stat_arb --sym-a AAPL --sym-b MSFT

Walk-forward: splits history into train/test windows and reports out-of-sample.
"""
import argparse
import logging
import sys
from dataclasses import dataclass, field
from typing import List

import numpy as np

from config import (
    ATR_PERIOD, ATR_STOP_MULT,
    BREAKOUT_PERIOD, CONF_BREAKOUT, CONF_MEAN_REV, CONF_PAIRS, CONF_STAT_ARB,
    CORR_LOOKBACK, DAILY_MAX_LOSS_USD, DAILY_TARGET_USD, LOT_TINY, MA_EXIT_PERIOD,
    MAX_SCALPS, RSI_OVERBOUGHT, RSI_OVERSOLD, RSI_PERIOD,
)
from data_feed import get_feed
from risk import atr
from strategies import breakout, mean_reversion, pairs_trading, stat_arb

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-8s %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger(__name__)

PIP_VALUE_USD = 10.0    # $10 per pip per standard lot → $0.10 per pip for 0.01 lot


@dataclass
class BacktestResult:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pips: float = 0.0
    max_drawdown: float = 0.0
    peak_pnl: float = 0.0
    pnl_history: List[float] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.wins / self.total_trades

    @property
    def avg_pips(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.total_pips / self.total_trades

    @property
    def pnl_usd(self) -> float:
        return self.total_pips * LOT_TINY * PIP_VALUE_USD

    def record_trade(self, pips: float) -> None:
        self.total_trades += 1
        self.total_pips += pips
        if pips > 0:
            self.wins += 1
        else:
            self.losses += 1
        running_pnl = self.total_pips * LOT_TINY * PIP_VALUE_USD
        self.pnl_history.append(running_pnl)
        if running_pnl > self.peak_pnl:
            self.peak_pnl = running_pnl
        dd = self.peak_pnl - running_pnl
        if dd > self.max_drawdown:
            self.max_drawdown = dd

    def print_summary(self, label: str = "") -> None:
        tag = f"[{label}] " if label else ""
        print(f"\n{tag}=== Backtest Results ===")
        print(f"  Trades:      {self.total_trades}  (W={self.wins} L={self.losses})")
        print(f"  Win rate:    {self.win_rate*100:.1f}%")
        print(f"  Total pips:  {self.total_pips:.1f}")
        print(f"  P&L USD:     ${self.pnl_usd:.2f}")
        print(f"  Avg pips:    {self.avg_pips:.1f}")
        print(f"  Max DD:      ${self.max_drawdown:.2f}")


def _pip_diff(entry: float, exit_price: float, direction: int) -> float:
    return (exit_price - entry) * direction * 10_000


def backtest_breakout(close: np.ndarray, high: np.ndarray,
                      low: np.ndarray) -> BacktestResult:
    result = BacktestResult()
    in_trade = False
    direction = 0
    entry_price = 0.0
    stop = 0.0

    needed = max(BREAKOUT_PERIOD, MA_EXIT_PERIOD, ATR_PERIOD) + 2
    for i in range(needed, len(close)):
        c = close[:i+1]
        h = high[:i+1]
        l = low[:i+1]
        price = close[i]

        if in_trade:
            cur_atr = atr(h, l, c)
            new_stop = price - direction * cur_atr * ATR_STOP_MULT
            if direction == 1 and new_stop > stop:
                stop = new_stop
            elif direction == -1 and (stop == 0 or new_stop < stop):
                stop = new_stop

            stopped = (direction == 1 and price <= stop) or \
                      (direction == -1 and price >= stop)
            ma_exit = breakout.should_exit(c, direction)

            if stopped or ma_exit:
                pips = _pip_diff(entry_price, price, direction)
                result.record_trade(pips)
                in_trade = False
        else:
            sig = breakout.compute(c, h, l)
            if sig.is_active:
                in_trade = True
                direction = sig.direction
                entry_price = price
                cur_atr = atr(h, l, c)
                stop = price - direction * cur_atr * ATR_STOP_MULT

    return result


def backtest_mean_reversion(close: np.ndarray) -> BacktestResult:
    result = BacktestResult()
    in_trade = False
    direction = 0
    entry_price = 0.0

    for i in range(RSI_PERIOD + 5, len(close)):
        c = close[:i+1]
        price = close[i]

        if in_trade:
            if mean_reversion.should_exit(c, direction):
                pips = _pip_diff(entry_price, price, direction)
                result.record_trade(pips)
                in_trade = False
        else:
            sig = mean_reversion.compute(c)
            if sig.is_active:
                in_trade = True
                direction = sig.direction
                entry_price = price

    return result


def backtest_stat_arb(close_a: np.ndarray, close_b: np.ndarray) -> BacktestResult:
    result = BacktestResult()
    in_trade = False
    direction = 0
    entry_a = entry_b = 0.0

    for i in range(CORR_LOOKBACK + 5, len(close_a)):
        ca = close_a[:i+1]
        cb = close_b[:i+1]

        if in_trade:
            if stat_arb.should_exit(ca, cb):
                pips_a = _pip_diff(entry_a, ca[-1], direction)
                pips_b = _pip_diff(entry_b, cb[-1], -direction)
                result.record_trade((pips_a + pips_b) / 2)
                in_trade = False
        else:
            sig = stat_arb.compute(ca, cb, "A", "B")
            if sig.is_active:
                in_trade = True
                direction = sig.direction
                entry_a = ca[-1]
                entry_b = cb[-1]

    return result


def walk_forward(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                 window: int = 252, step: int = 63) -> None:
    """Walk-forward test on breakout strategy."""
    print("\n=== Walk-Forward Test (Breakout) ===")
    i = window
    period_num = 0
    while i + step <= len(close):
        period_num += 1
        train = slice(0, i)
        test  = slice(i, i + step)
        r = backtest_breakout(close[test], high[test], low[test])
        r.print_summary(f"OOS {period_num} bars {i}-{i+step}")
        i += step


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="breakout",
                        choices=["breakout", "mean_rev", "stat_arb", "pairs"])
    parser.add_argument("--symbol",  default="EURUSD=X")
    parser.add_argument("--sym-a",   default="AAPL")
    parser.add_argument("--sym-b",   default="MSFT")
    parser.add_argument("--period",  default="2y")
    parser.add_argument("--walk-forward", action="store_true")
    args = parser.parse_args()

    feed = get_feed()

    if args.strategy in ("stat_arb", "pairs"):
        logger.info("Fetching %s and %s", args.sym_a, args.sym_b)
        bars_a = feed.fetch(args.sym_a, period=args.period, interval="1d")
        bars_b = feed.fetch(args.sym_b, period=args.period, interval="1d")
        n = min(len(bars_a["close"]), len(bars_b["close"]))
        ca, cb = bars_a["close"][-n:], bars_b["close"][-n:]

        if args.strategy == "stat_arb":
            result = backtest_stat_arb(ca, cb)
            result.print_summary("stat_arb")
        else:
            fn = pairs_trading
            result = BacktestResult()
            in_trade = False
            direction = 0
            entry_a = entry_b = 0.0
            for i in range(CORR_LOOKBACK + 5, n):
                _ca, _cb = ca[:i+1], cb[:i+1]
                if in_trade:
                    if fn.should_exit(_ca, _cb):
                        pips = (_pip_diff(entry_a, _ca[-1], direction) +
                                _pip_diff(entry_b, _cb[-1], -direction)) / 2
                        result.record_trade(pips)
                        in_trade = False
                else:
                    sig = fn.compute(_ca, _cb, args.sym_a, args.sym_b)
                    if sig.is_active:
                        in_trade, direction = True, sig.direction
                        entry_a, entry_b = _ca[-1], _cb[-1]
            result.print_summary("pairs_trading")
    else:
        logger.info("Fetching %s", args.symbol)
        bars = feed.fetch(args.symbol, period=args.period, interval="1d")
        close = bars["close"]
        high  = bars.get("high", close)
        low   = bars.get("low",  close)

        if args.strategy == "mean_rev":
            result = backtest_mean_reversion(close)
            result.print_summary("mean_reversion")
        else:
            result = backtest_breakout(close, high, low)
            result.print_summary("breakout")
            if args.walk_forward:
                walk_forward(close, high, low)


if __name__ == "__main__":
    main()
