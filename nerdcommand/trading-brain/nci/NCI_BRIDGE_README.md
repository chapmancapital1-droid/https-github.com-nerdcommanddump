# nci Bridge — Unified Trading Brain Dashboard

**Central consolidation point for ALL trading brain data from NCI across all versions, all EAs, all sessions, and all data sources.**

```
NCI_GodMode_v3.2_Fusion.mq4    ──┐
NCI_Hybrid_v1.8.mq4            ──┼──► nci_bridge.py ──► nci_bridge_state.json
NCI_ScalpBot_M5_v2.0.mq4       ──┤
Micro-lot framework (SQLite)   ──┤
Backtester results             ──┘
```

## What's Consolidated

### 1. Live Account State (v3.2 EA)
- Balance, equity, margin, drawdown
- Daily trade count, consecutive losses
- ABC market stage (M1 & H4)
- ADX, FER, ATR readings

### 2. Signal Proposals (v3.2 EA)
- Entry signal (BUY/SELL)
- Confluence score (voter count)
- SL/TP pips, risk:reward ratio
- Trade qualification gates
- Approval status

### 3. Rich Signal Data (Hybrid v1.8 EA)
- **Voter breakdown** — labeled list of which indicators fired
- Fired/blocked status with reason
- Spread and HTF gate status
- Buy/sell individual scores

### 4. Runtime Command Overrides (Hybrid v1.8 EA)
- Live min_confluence adjustment
- Max spread override
- Risk % tuning
- Trail step control
- Scalp mode toggle

### 5. Performance Metrics
#### Daily (from SQLite)
- Trades completed today
- Daily P&L (USD)
- Wins/losses and win rate
- Average win/loss USD
- Profit factor (avg_W / avg_L)

#### All-Time
- Total trades across all sessions
- Total P&L (USD)
- Win rate %
- Sharpe ratio

### 6. Position Tracking
- Current open positions
- Open trade details (from trades.db)
- Scalp counts per trade

---

## Installation & Setup

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```
(Already installed if running from nerdcommand environment.)

### 2. Point MT4_FILES_DIR at your MT4 MFiles folder
```bash
# Windows
set MT4_FILES_DIR=C:\Users\<you>\AppData\Roaming\MetaQuotes\Terminal\<ID>\MFiles

# macOS / Linux
export MT4_FILES_DIR="/path/to/mt4/mfiles"
```

Or set in `.env`:
```bash
MT4_FILES_DIR=C:\Users\...\MFiles
BRIDGE_DATA_DIR=C:\...\bridge
BRIDGE_POLL_SEC=2
```

### 3. Point to SQLite trade journal
The bridge auto-detects `trades.db` from the micro-lot framework or creates one in `BRIDGE_DATA_DIR/`.
To use your own:
```bash
export DB_PATH=/path/to/trades.db
```

---

## Usage

### Show Current State (One-Shot)
```bash
python nci_bridge.py
```
Displays rich terminal table with all metrics + persists to `nci_bridge_state.json`.

### Watch Mode (Live Updates)
```bash
python nci_bridge.py --watch
```
Refreshes display every `BRIDGE_POLL_SEC` seconds as EA writes new data.

### Programmatic Access
```python
from nci_bridge import load_bridge_state, format_bridge_table

state = load_bridge_state()
print(format_bridge_table(state))
print(f"Daily P&L: ${state.daily_pnl:.2f}")
print(f"Open positions: {state.open_positions}")
```

### Integration with nci_signal_approval.py
```python
from nci_bridge import load_bridge_state

state = load_bridge_state()
if state.proposal:
    # Use state.proposal.to_agent_prompt(state.live) for LLM second opinion
    prompt = state.proposal.to_agent_prompt(state.live)
```

---

## Data Flow

```
Every MT4 bar tick:
  ├─ NCI_GodMode_v3.2_Fusion writes:
  │  ├─ NCI_LiveData.json (account state + scores)
  │  └─ signal_proposal.json (current proposal)
  │
  ├─ NCI_Hybrid_v1.8 writes:
  │  ├─ NCI_Signal.json (voter breakdown + gates)
  │  └─ NCI_Commands.json (runtime overrides, if changed)
  │
  └─ nci_bridge.py reads all files:
     ├─ Merges into unified NCIBridgeState
     ├─ Queries SQLite for daily/all-time stats
     ├─ Calculates performance metrics
     └─ Persists to nci_bridge_state.json + displays
```

---

## Output Files

### nci_bridge_state.json
Complete unified state snapshot. Updated on every new EA bar.

**Structure:**
```json
{
  "live": {
    "balance": 5000.00,
    "equity": 5150.25,
    "drawdown": -0.005,
    "abc_stage": 1,
    "adx": 25.3,
    "fer": 0.52,
    "buy_score": 12,
    "sell_score": 8,
    "timestamp": "2026-06-04T14:35:22Z"
  },
  "proposal": {
    "symbol": "EURUSD",
    "action": "BUY",
    "confluence": 13,
    "confluence_max": 15,
    "sl_pips": 50.0,
    "tp_pips": 75.0,
    "risk_reward": 1.5,
    "qualifies": true,
    "timestamp": "2026-06-04T14:35:22Z"
  },
  "hybrid_signal": {
    "direction": "BUY",
    "voters": ["DMA", "Stoch", "HTF", "Vol", "RSI+"],
    "fired": true,
    "spread": 1.2,
    "atr": 0.00125
  },
  "command_override": {
    "min_confluence": 11,
    "risk_pct": 0.4
  },
  "daily": {
    "trades": 3,
    "pnl": 125.50,
    "wins": 2,
    "losses": 1,
    "win_rate": 0.667,
    "profit_factor": 1.89
  },
  "all_time": {
    "trades": 127,
    "pnl": 2845.75,
    "wins": 87,
    "losses": 40,
    "win_rate": 0.685,
    "sharpe_ratio": 1.23
  },
  "positions": 1,
  "ea_version": "3.2_Fusion",
  "last_update": "2026-06-04T14:35:22Z"
}
```

---

## Consolidation Across Sessions

### From Prior Sessions
The bridge reads all historical trade data from SQLite. To import trades from prior sessions:

1. **Copy `trades.db`** from old environment to new:
   ```bash
   cp /path/old/trades.db /path/new/trades.db
   ```

2. **Or** restore from backup:
   ```bash
   sqlite3 trades.db < backup.sql
   ```

3. **Verify**:
   ```bash
   sqlite3 trades.db "SELECT COUNT(*) FROM trades;"
   ```

### From Different EAs (v3.2 → v4.0, Hybrid → v4.0, etc.)
- All EAs write to the same `MT4_FILES_DIR`
- nci_bridge reads from all formats in a single poll
- Ensure each EA version writes its JSON files with consistent naming

---

## Extending the Bridge

### Add a New EA Version
1. Create new EA (e.g., `NCI_ScalpBot_v5.mq4`)
2. Write JSON to `MT4_FILES_DIR/` with version-specific name (e.g., `NCI_ScalpBot_v5_Stats.json`)
3. Add parser to `nci_bridge.py`:
   ```python
   @dataclass
   class ScalpBotStats:
       ...
       @classmethod
       def from_dict(cls, d: dict) -> "ScalpBotStats":
           ...
   ```
4. Load in `load_bridge_state()`:
   ```python
   state.scalp_stats = read_scalp_stats()
   ```
5. Add to `to_dict()` and display functions

### Integrate Custom Backtester Results
```python
def read_backtest_results(path: str) -> Dict:
    d = _read_json(path)
    return {
        "strategy": d.get("strategy"),
        "symbol": d.get("symbol"),
        "pnl": d.get("pnl"),
        "win_rate": d.get("win_rate"),
        ...
    }

# In load_bridge_state():
state.backtest_results = read_backtest_results(...)
```

---

## Troubleshooting

### No data showing in bridge
1. **Check MT4_FILES_DIR**: 
   ```bash
   ls $MT4_FILES_DIR/
   ```
   Should show `NCI_LiveData.json` and `signal_proposal.json` if EA is running.

2. **Check EA is writing files**:
   ```bash
   python -c "from nci_bridge import read_live; print(read_live())"
   ```
   If None, EA hasn't written yet or path is wrong.

3. **Verify env vars**:
   ```bash
   python -c "from config import MT4_FILES_DIR, BRIDGE_DATA_DIR; print(MT4_FILES_DIR, BRIDGE_DATA_DIR)"
   ```

### SQLite errors
- Check `DB_PATH` points to valid writable location
- Delete `trades.db` and let it re-create (will lose history)
- Or restore from backup

### Missing voters in hybrid signal
- Ensure `NCI_Hybrid_v1.8.mq4` is the running EA (not v3.2)
- Check `NCI_Signal.json` is being written
- v3.2 won't have voter breakdown (use `confluence` score instead)

---

## Quick Reference

| File | Source | Contains |
|------|--------|----------|
| `NCI_LiveData.json` | v3.2 EA | Account state, ABC stage, scores |
| `signal_proposal.json` | v3.2 EA | Current entry proposal |
| `NCI_Signal.json` | Hybrid v1.8 EA | Rich signal with voter breakdown |
| `NCI_Commands.json` | Hybrid v1.8 EA | Runtime parameter overrides |
| `NCI_Monitor.json` | ScalpBot v2.0 EA | M5 scalp metrics (if applicable) |
| `trades.db` | Micro-lot framework | Complete trade journal (SQLite) |
| `nci_bridge_state.json` | nci Bridge | Unified state snapshot |

---

## Performance Metrics Explained

### Confluence Score
- Voter count out of 15 (DMA, Stoch, DMA slope, AEXD div, Candle, ATR, HTF trend, Robotrick, Vol, RSI slope, MACD, DayRange, MTF, TTF, Vegas)
- Higher = more voters agree = higher confidence

### ABC Market Stage
- **A_CONSOLIDATION**: ADX < 20, FER < 0.45 → low volatility, no entry
- **B_EXPANSION**: ADX ≥ 22, FER ≥ 0.50 → trending, trade
- **C_CONTRACTION**: ADX falling, FER < 0.55 → fade breakdowns, trail

### Profit Factor
- Ratio of average winning trade to average losing trade
- PF > 1.5 = healthy
- PF > 2.0 = excellent

### Sharpe Ratio
- Return per unit of risk
- 1.0+ = acceptable
- 2.0+ = excellent
- Accounts for volatility of returns

---

## Next Steps

1. **Upgrade to v4.0 EA** with WriteLiveData() and WriteSignalJSON() (rich, standardized outputs)
2. **Add web dashboard** (Flask/Vue) to visualize nci_bridge_state.json
3. **Create alerting system** (Slack/email) on trade signals and daily targets hit
4. **Export reports** (PDF, CSV) for trade review and optimization
5. **Multi-chart viewer** (price, signals, indicators) synced with bridge updates
