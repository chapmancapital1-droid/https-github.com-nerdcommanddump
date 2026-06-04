"""NCI agent router — flips between Ollama and direct llama-cpp via USE_LOCAL_LLAMA.

Usage:
    from nci_agent import generate, health, backend_name

    signal = generate("AUDCAD has been ranging 0.00050 pips for 2h, ATR low, spread 1.2")
    print(signal)  # [AUDCAD] [SHORT] [62%] [break below 0.8920] [close above 0.8935]
"""
from typing import Optional

from config import USE_LOCAL_LLAMA

if USE_LOCAL_LLAMA:
    import nci_agent_local as _backend
    backend_name = "llama-cpp-direct"
else:
    import nci_agent_ollama as _backend
    backend_name = "ollama"


def generate(prompt: str, system: Optional[str] = None) -> str:
    return _backend.generate(prompt, system=system)


def health() -> bool:
    return _backend.health()
