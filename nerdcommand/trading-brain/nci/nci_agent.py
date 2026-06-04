"""NCI agent router — flips between Ollama and direct llama-cpp via USE_LOCAL_LLAMA.

Usage:
    from nci_agent import generate, health, backend_name

    # Free-form signal analysis
    signal = generate("AUDCAD ranging 0.00050 for 2h, ATR low, spread 1.2")
    print(signal)  # [AUDCAD] [SHORT] [62%] [break below 0.8920] [close above 0.8935]

    # Analyse a live EA proposal (reads MT4 JSON files directly)
    from nci_live import read_live, read_proposal
    from nci_agent import analyse_live_proposal
    result = analyse_live_proposal()
    print(result)
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


def analyse_live_proposal() -> Optional[str]:
    """Read the current EA signal_proposal.json and return an LLM verdict string."""
    from nci_live import read_live, read_proposal
    proposal = read_proposal()
    if not proposal:
        return None
    live = read_live()
    prompt = proposal.to_agent_prompt(live)
    return generate(prompt)
