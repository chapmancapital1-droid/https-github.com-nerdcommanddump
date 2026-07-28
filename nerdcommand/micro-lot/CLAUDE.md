# NERDCOMMAND Micro-Lot Capital Preservation

Working directory: `nerdcommand/micro-lot/`

## Architecture

```
data_feed.py   →  yfinance / IB API  (OHLCV bars)
strategies/    →  4 signal generators
fusion.py      →  confidence aggregation → lot size
risk.py        →  triangle entry, ATR stop, daily limits
position_tracker.py  →  SQLite trade journal
main.py        →  event loop
backtest.py    →  historical simulation
```

## Quick Start

```bash
pip install yfinance numpy

# Single scan (paper mode)
python main.py --once

# Continuous loop (5-min heartbeat)
python main.py

# Backtest
python backtest.py --strategy breakout --symbol EURUSD=X --period 2y
python backtest.py --strategy mean_rev --symbol BTC-USD
python backtest.py --strategy stat_arb --sym-a AAPL --sym-b MSFT
python backtest.py --strategy breakout --walk-forward
```

## Position Sizing (confidence tiers)

| Total conf | Lot size | Strategies |
|-----------|---------|------------|
| ≤ 0.8     | skip    | single RSI only |
| ≥ 1.8     | 0.04    | 2 strategies agree |
| ≥ 3.0     | 0.07    | 3+ strategies agree |

## Triangle Entry

1. Entry 1: 0.01 lots at signal
2. Entry 2: +0.03 lots after +20 pip favorable move
3. Entry 3: +0.03 lots after +40 pip favorable move
- If stop hit at any stage: close ALL, do not average down

## Daily Limits

- Target: +$10 → reduce risk / stop for day
- Max loss: -$5 → STOP TRADING
- Max scalps: 3 wins → stand down

## Environment Variables

```
DATA_PROVIDER=yfinance        # or "ib"
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1
ACCOUNT_BALANCE=500.0
DAILY_TARGET_USD=10.0
DAILY_MAX_LOSS_USD=5.0
MAX_SCALPS=3
DB_PATH=trades.db
LOG_DIR=logs
```

## File Map

| File | Purpose |
|------|---------|
| `config.py` | All parameters (edit here only) |
| `strategies/__init__.py` | `Signal` dataclass |
| `strategies/breakout.py` | 20-day high/low breakout |
| `strategies/mean_reversion.py` | RSI 30/70 mean reversion |
| `strategies/stat_arb.py` | Z-score pair spread arb |
| `strategies/pairs_trading.py` | Relative-value pairs |
| `fusion.py` | Aggregate signals → position size |
| `risk.py` | Triangle entry + ATR stop + daily limits |
| `position_tracker.py` | SQLite trade log |
| `data_feed.py` | yfinance / IB data provider |
| `main.py` | Trading loop |
| `backtest.py` | Historical simulation |
