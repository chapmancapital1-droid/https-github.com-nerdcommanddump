# NerdCommand Trading Brain

## Role
Trading analysis assistant. Market data, signals, strategy, and position management only.
Do not drift into general coding, content, or unrelated tasks — redirect to the appropriate project.

## Model routing
| Task | Model |
|------|-------|
| Quick lookups, price checks, single-indicator reads | Haiku (`/model haiku`) |
| Multi-indicator analysis, strategy reasoning, backtests | Sonnet (default) |
| Full portfolio review, novel strategy design | Sonnet — confirm before long runs |

## NCI Live Update & Bridge Dashboard

The `nci/` folder provides **nci Bridge** — the unified central hub for all trading brain data across all versions, sessions, and EAs.

### Architecture
```
NCI_GodMode_v3.2_Fusion.mq4  ┐
NCI_Hybrid_v1.8.mq4          │
NCI_ScalpBot_M5_v2.0.mq4     ├──► nci_bridge.py ──► nci_bridge_state.json
Micro-lot framework (SQLite) │    (unified consolidation)
Backtester results           ┘    
                                     ↓
                          LLM brain (nci_signal_approval.py)
                                     ↓
                          signals/approvals.jsonl
```

### nci Bridge — Central Consolidation
**Read:** [`NCI_BRIDGE_README.md`](nci/NCI_BRIDGE_README.md)

The bridge consolidates:
- **Live data**: Account state, ABC stage, ADX, FER, confluence scores (v3.2 EA)
- **Rich signals**: Voter breakdown, gates, fired/blocked status (Hybrid v1.8 EA)
- **Runtime overrides**: Command parameters (Hybrid v1.8 EA)
- **Performance metrics**: Daily & all-time P&L, win rates, profit factor, Sharpe (SQLite)
- **Position tracking**: Open trades, scalp counts, trade journal

### Quick commands
```bash
# Show current unified state (one-shot)
python nci/nci_bridge.py

# Watch mode — auto-refresh as EA writes new data
python nci/nci_bridge.py --watch

# Show legacy live data only (v3.2 signals)
python nci/nci_live.py

# LLM second-opinion on current proposal
python nci/nci_signal_approval.py

# Watch mode — analyse every new bar as EA runs
python nci/nci_signal_approval.py --watch

# Consolidate data from previous Claude sessions
python nci/consolidate_sessions.py --import-all /path/old/trading-brain
python nci/consolidate_sessions.py --report

# Loss pattern analysis
python nci/analysis/loss_pattern.py
```

### Setup: point MT4_FILES_DIR at the EA's output folder
The EA writes `NCI_LiveData.json` and `signal_proposal.json` to MT4's MFiles folder.
Set the env var before running any nci/ script:
```cmd
set MT4_FILES_DIR=C:\Users\<you>\AppData\Roaming\MetaQuotes\Terminal\<ID>\MFiles
```
Or use portable mode path: `<MT4_INSTALL>\MFiles\`

### Backend toggle
| Env var | Value | Effect |
|---------|-------|--------|
| `USE_LOCAL_LLAMA` | `false` (default) | Ollama HTTP via localhost:11434 |
| `USE_LOCAL_LLAMA` | `true` | Direct llama-cpp-python (model resident in RAM/VRAM) |

### Ollama setup (permanent keep_alive fix)
Set `OLLAMA_KEEP_ALIVE=2h` as a system env var in the Ollama service so the model
survives restarts. Code already sends `keep_alive: 60m` on every request, but the
service-level env var is the permanent fix.

### llama-cpp-python setup
```bash
# 1. Find your CUDA version
nvcc --version   # e.g. "release 12.1"

# 2. Install GPU wheels (replace cu121 as needed)
pip install llama-cpp-python --extra-index-url \
    https://abetlen.github.io/llama-cpp-python/whl/cu121

# 3. Copy GGUF from Ollama blob cache
#    Blobs live in: %LOCALAPPDATA%\Ollama\models\blobs\
#    Find the largest file (~4GB) — that's qwen2.5-coder-7b-instruct-q4_k_m.gguf
#    Copy to D:\NERDCOMMANDCLAUDEBRAIN\models\

# 4. Test
python -c "from nci.nci_agent_local import health; print(health())"

# 5. Flip the toggle
set USE_LOCAL_LLAMA=true
```

## Static context rules
- Summarize tool outputs over 500 lines; never dump raw data into context
- No external API calls unless the tool is listed in `.claude/settings.json`
- When uncertain about a signal: state confidence + what data would resolve it
- Prefer tables and bullet points for market data

## Output format
- Signals: `[TICKER] [LONG/SHORT] [confidence %] [trigger] [invalidation]`
- Summaries: max 5 bullet points unless asked for more
- Never include raw JSON or full API responses — extract relevant fields only

## Session habits
- Run `/compact` when context exceeds ~20 turns
- Run `/clear` before switching to NerdCommand Studios
- Use `/model haiku` for quick checks, switch back to Sonnet for deep analysis
