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

The `nci/` folder contains the live data feed and signal engine.

### Quick commands
```bash
# Check live account snapshot
python nci/nci_live.py

# Run a signal (Ollama by default)
python -c "from nci.nci_agent import generate; print(generate('GBPUSD at 1.2700 support, RSI 28'))"

# Switch to direct llama-cpp (after installing wheels + copying model)
set USE_LOCAL_LLAMA=true   # Windows
# or
export USE_LOCAL_LLAMA=true  # Linux/Mac

# Benchmark both backends
python nci/benchmark.py

# Loss pattern analysis
python nci/analysis/loss_pattern.py
```

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
