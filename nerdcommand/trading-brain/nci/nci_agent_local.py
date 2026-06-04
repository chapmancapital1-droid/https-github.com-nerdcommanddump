"""Direct llama-cpp-python backend — loads model once, keeps it resident.

Install GPU wheels (detect CUDA version first):
    nvcc --version
    pip install llama-cpp-python --extra-index-url \
        https://abetlen.github.io/llama-cpp-python/whl/cu121
    # Replace cu121 with cu118, cu122, cu124 etc. to match your toolkit.

Copy model from Ollama cache:
    # Ollama stores blobs in %LOCALAPPDATA%\\Ollama\\models\\blobs\\
    # Find the largest file (that's the GGUF), copy to LOCAL_MODEL_PATH.
"""
from __future__ import annotations

import os
from typing import Optional

from config import (
    AGENT_MAX_TOKENS,
    AGENT_TEMPERATURE,
    LOCAL_CTX_SIZE,
    LOCAL_GPU_LAYERS,
    LOCAL_MODEL_PATH,
    LOCAL_THREADS,
)

_SYSTEM = (
    "You are the NerdCommand Trading Brain signal engine. "
    "Output only structured trading signals in the format: "
    "[TICKER] [LONG/SHORT] [confidence %] [trigger] [invalidation]. "
    "No prose, no disclaimers."
)

_llm = None  # singleton — loaded once at first call


def _get_llm():
    global _llm
    if _llm is not None:
        return _llm

    try:
        from llama_cpp import Llama
    except ImportError as e:
        raise RuntimeError(
            "llama-cpp-python not installed. "
            "Run: pip install llama-cpp-python --extra-index-url "
            "https://abetlen.github.io/llama-cpp-python/whl/cu121"
        ) from e

    if not os.path.exists(LOCAL_MODEL_PATH):
        raise FileNotFoundError(
            f"Model not found at {LOCAL_MODEL_PATH}. "
            "Copy the GGUF from Ollama's blob cache or download separately."
        )

    _llm = Llama(
        model_path=LOCAL_MODEL_PATH,
        n_gpu_layers=LOCAL_GPU_LAYERS,
        n_ctx=LOCAL_CTX_SIZE,
        n_threads=LOCAL_THREADS,
        verbose=False,
    )
    return _llm


def generate(prompt: str, system: Optional[str] = None) -> str:
    llm = _get_llm()
    messages = [
        {"role": "system", "content": system or _SYSTEM},
        {"role": "user",   "content": prompt},
    ]
    resp = llm.create_chat_completion(
        messages=messages,
        max_tokens=AGENT_MAX_TOKENS,
        temperature=AGENT_TEMPERATURE,
    )
    return resp["choices"][0]["message"]["content"].strip()


def health() -> bool:
    try:
        _get_llm()
        return True
    except Exception:
        return False
