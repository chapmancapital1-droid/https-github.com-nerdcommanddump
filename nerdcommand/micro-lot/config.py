"""NERDCOMMAND Micro-Lot Capital Preservation — all parameters in one place."""
import os

# -- Account -----------------------------------------------------------------
ACCOUNT_BALANCE    = float(os.getenv("ACCOUNT_BALANCE",   "500.0"))
DAILY_TARGET_USD   = float(os.getenv("DAILY_TARGET_USD",  "10.0"))   # +2%
DAILY_MAX_LOSS_USD = float(os.getenv("DAILY_MAX_LOSS_USD", "5.0"))   # -1%
MAX_SCALPS         = int(os.getenv("MAX_SCALPS",           "3"))     # exit after N wins

# -- Position sizing (lots) --------------------------------------------------
LOT_TINY   = 0.01   # low conviction / triangle entry 1
LOT_MED    = 0.03   # triangle entry 2 add-on
LOT_FULL   = 0.07   # full size (= 0.01 + 0.03 + 0.03 pyramid)

# -- Strategy confidence weights ---------------------------------------------
CONF_BREAKOUT  = 1.0
CONF_STAT_ARB  = 1.2
CONF_MEAN_REV  = 0.8
CONF_PAIRS     = 1.1

# Thresholds → position size
CONF_SKIP_MAX  = 0.8   # single RSI only → skip
CONF_MED_MIN   = 1.8   # 2 strategies → 0.04 (= 0.01 entry + 0.03 add)
CONF_HIGH_MIN  = 3.0   # 3+ strategies → 0.07 full

# -- ATR stop ----------------------------------------------------------------
ATR_PERIOD     = 14
ATR_STOP_MULT  = 2.0   # stop = entry ± ATR * 2

# -- Breakout strategy -------------------------------------------------------
BREAKOUT_PERIOD = 20   # 20-day high/low
MA_EXIT_PERIOD  = 50   # exit if price closes below 50-day MA

# -- Mean reversion (RSI) ----------------------------------------------------
RSI_PERIOD      = 14
RSI_OVERSOLD    = 30
RSI_OVERBOUGHT  = 70
RSI_MID         = 50

# -- Statistical arbitrage / Pairs trading -----------------------------------
CORR_LOOKBACK      = 60    # bars for correlation calculation
SPREAD_STD_ENTRY   = 2.0   # enter when spread > 2 std
SPREAD_STD_EXIT    = 1.0   # exit when spread < 1 std

# -- Triangle entry ----------------------------------------------------------
TRIANGLE_ENTRY1_LOTS = 0.01
TRIANGLE_ENTRY2_LOTS = 0.03
TRIANGLE_ENTRY3_LOTS = 0.03
TRIANGLE_FAVOR_PIPS  = 20.0   # pips of favorable move before adding

# -- Instruments -------------------------------------------------------------
FOREX_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCAD"]
PAIRS_MAP   = [("AAPL", "MSFT"), ("JPM", "BAC"), ("XOM", "CVX")]
CRYPTO      = ["BTC-USD", "ETH-USD"]

# -- Data --------------------------------------------------------------------
DATA_PROVIDER = os.getenv("DATA_PROVIDER", "yfinance")   # "yfinance" | "ib"
IB_HOST       = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT       = int(os.getenv("IB_PORT", "7497"))
IB_CLIENT_ID  = int(os.getenv("IB_CLIENT_ID", "1"))

# -- Paths -------------------------------------------------------------------
DB_PATH      = os.getenv("DB_PATH", "trades.db")
LOG_DIR      = os.getenv("LOG_DIR", "logs")
