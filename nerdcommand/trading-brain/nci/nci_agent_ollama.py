"""Ollama HTTP backend — enforces model + keep_alive on every request."""
import json
import urllib.error
import urllib.request
from typing import Optional

from config import (
    AGENT_MAX_TOKENS,
    AGENT_TEMPERATURE,
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
)

_SYSTEM = (
    "You are the NerdCommand Trading Brain signal engine. "
    "Output only structured trading signals in the format: "
    "[TICKER] [LONG/SHORT] [confidence %] [trigger] [invalidation]. "
    "No prose, no disclaimers."
)


def _post(endpoint: str, payload: dict) -> dict:
    url = f"{OLLAMA_BASE_URL}{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama unreachable at {OLLAMA_BASE_URL}: {e}") from e


def _ensure_model_loaded() -> None:
    """Warm-pin the correct model so it's not evicted mid-session."""
    _post("/api/generate", {
        "model": OLLAMA_MODEL,
        "prompt": "",
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "stream": False,
    })


def generate(prompt: str, system: Optional[str] = None) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "stream": False,
        "options": {
            "num_predict": AGENT_MAX_TOKENS,
            "temperature": AGENT_TEMPERATURE,
        },
        "messages": [
            {"role": "system", "content": system or _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    }
    resp = _post("/api/chat", payload)
    return resp["message"]["content"].strip()


def health() -> bool:
    try:
        resp = _post("/api/tags", {})
        loaded = [m["name"] for m in resp.get("models", [])]
        return any(OLLAMA_MODEL in m for m in loaded)
    except RuntimeError:
        return False


# Warm-pin on import so the model is resident for the session lifetime.
try:
    _ensure_model_loaded()
except RuntimeError:
    pass  # offline — will surface on first generate() call
