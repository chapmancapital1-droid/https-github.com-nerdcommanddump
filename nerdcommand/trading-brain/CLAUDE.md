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

## NCI Live Update

The `nci/` folder bridges the MT4 EA (`mt4/NCI_GodMode_v3_2_Fusion.mq4`) with the LLM brain.

### EA → Python data flow
```
MT4 EA  ──writes──►  NCI_LiveData.json       ──►  nci_live.py (NCILiveData)
                      signal_proposal.json    ──►  nci_live.py (SignalProposal)
                                                         │
                                               nci_signal_approval.py
                                                         │
                                               LLM (Ollama or llama-cpp)
                                                         │
                                               signals/approvals.jsonl
```

### Quick commands
```bash
# Show live account state + current signal proposal from the EA
python nci/nci_live.py

# One-shot LLM second-opinion on the current proposal
python nci/nci_signal_approval.py

# Watch mode — analyse every new bar's proposal as the EA runs
python nci/nci_signal_approval.py --watch

# Dry run (no LLM call, just print proposal)
python nci/nci_signal_approval.py --dry-run

# Free-form signal prompt
python -c "from nci.nci_agent import generate; print(generate('GBPUSD at 1.2700 support, RSI 28'))"

# Switch to direct llama-cpp (after installing wheels + copying model)
set USE_LOCAL_LLAMA=true   # Windows

# Benchmark both backends
python nci/benchmark.py

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
