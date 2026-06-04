"""Central config for NCI live update. All values overridable via env vars."""
import os

# -- Backend toggle ----------------------------------------------------------
# Set USE_LOCAL_LLAMA=true once llama-cpp wheels are installed + model copied.
# Leave false to stay on Ollama (safe default).
USE_LOCAL_LLAMA = os.getenv("USE_LOCAL_LLAMA", "false").lower() == "true"

# -- Ollama ------------------------------------------------------------------
OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL",   "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL",      "qwen2.5-coder:7b")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "60m")   # prevents eviction
OLLAMA_TIMEOUT    = int(os.getenv("OLLAMA_TIMEOUT", "60"))  # seconds

# -- Local llama-cpp ---------------------------------------------------------
LOCAL_MODEL_PATH = os.getenv(
    "LOCAL_MODEL_PATH",
    r"D:\NERDCOMMANDCLAUDEBRAIN\models\qwen2.5-coder-7b-instruct-q4_k_m.gguf",
)
LOCAL_GPU_LAYERS  = int(os.getenv("LOCAL_GPU_LAYERS",  "35"))   # tune to VRAM
LOCAL_CTX_SIZE    = int(os.getenv("LOCAL_CTX_SIZE",    "4096"))
LOCAL_THREADS     = int(os.getenv("LOCAL_THREADS",     "6"))

# -- MT4 EA live data --------------------------------------------------------
# NCI_GodMode_v3_2_Fusion.mq4 writes these files on every new bar.
# Default path = MT4 portable mode MFiles folder. Override to your instance path:
#   %APPDATA%\MetaQuotes\Terminal\<INSTANCE_ID>\MFiles\
MT4_FILES_DIR = os.getenv(
    "MT4_FILES_DIR",
    r"D:\NERDCOMMANDCLAUDEBRAIN\mt4_files",
)

# v3.2 Fusion EA outputs
NCI_LIVE_JSON      = os.path.join(MT4_FILES_DIR, "NCI_LiveData.json")
SIGNAL_PROPOSAL_JSON = os.path.join(MT4_FILES_DIR, "signal_proposal.json")

# Hybrid v1.8 EA outputs (rich signal + command overrides)
NCI_SIGNAL_JSON    = os.path.join(MT4_FILES_DIR, "NCI_Signal.json")
NCI_COMMANDS_JSON  = os.path.join(MT4_FILES_DIR, "NCI_Commands.json")

# ScalpBot v2.0 EA outputs
NCI_MONITOR_JSON   = os.path.join(MT4_FILES_DIR, "NCI_Monitor.json")

# nci Bridge
BRIDGE_POLL_SEC    = int(os.getenv("BRIDGE_POLL_SEC", "2"))
BRIDGE_DATA_DIR = os.getenv(
    "BRIDGE_DATA_DIR", r"D:\NERDCOMMANDCLAUDEBRAIN\bridge"
)
BRIDGE_STATE_FILE  = os.path.join(BRIDGE_DATA_DIR, "nci_bridge_state.json")

# -- Agent -------------------------------------------------------------------
AGENT_MAX_TOKENS  = int(os.getenv("AGENT_MAX_TOKENS",  "512"))
AGENT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0.1"))

# -- Output paths ------------------------------------------------------------
SIGNAL_LOG_DIR = os.getenv(
    "SIGNAL_LOG_DIR", r"D:\NERDCOMMANDCLAUDEBRAIN\signals"
)
ANALYSIS_DIR = os.getenv(
    "ANALYSIS_DIR", r"D:\NERDCOMMANDCLAUDEBRAIN\analysis"
)
