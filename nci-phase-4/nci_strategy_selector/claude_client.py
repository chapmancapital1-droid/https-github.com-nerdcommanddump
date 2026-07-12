"""
Claude API client — zero-dependency wrapper for the Anthropic Messages API.

Uses stdlib urllib so the package keeps its no-pip-install property.
Reads ANTHROPIC_API_KEY from the environment; degrades gracefully to
offline mode when the key is missing or the network call fails, so the
strategy selector keeps working without AI reasoning.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 1024
MAX_RETRIES = 3
RETRY_BACKOFF_S = 2.0


@dataclass
class ClaudeResponse:
    """Result of one Claude call."""
    text: str
    model: str
    ok: bool
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class ClaudeReasoningClient:
    """
    Minimal Claude Messages API client.

    Usage:
        client = ClaudeReasoningClient()
        if client.available:
            resp = client.complete(system="...", messages=[{"role": "user", "content": "..."}])
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout_s: float = 30.0,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s

    @property
    def available(self) -> bool:
        """True when an API key is configured."""
        return bool(self.api_key)

    def complete(
        self,
        messages: list[dict],
        system: str | None = None,
        temperature: float = 0.3,
    ) -> ClaudeResponse:
        """
        Call the Messages API. Returns ClaudeResponse with ok=False (never
        raises) on any failure so callers can fall back cleanly.
        """
        if not self.available:
            return ClaudeResponse(
                text="", model=self.model, ok=False,
                error="no API key configured (set ANTHROPIC_API_KEY)",
            )

        body: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            body["system"] = system

        last_error = "unknown error"
        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    ANTHROPIC_API_URL,
                    data=json.dumps(body).encode("utf-8"),
                    headers={
                        "content-type": "application/json",
                        "x-api-key": self.api_key,
                        "anthropic-version": ANTHROPIC_VERSION,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                text = "".join(
                    block.get("text", "")
                    for block in payload.get("content", [])
                    if block.get("type") == "text"
                )
                usage = payload.get("usage", {})
                return ClaudeResponse(
                    text=text,
                    model=payload.get("model", self.model),
                    ok=True,
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                )
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                # Retry only on rate limit / server errors.
                if e.code not in (429, 500, 502, 503, 529):
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_error = f"network error: {e}"
            except (json.JSONDecodeError, KeyError) as e:
                last_error = f"malformed response: {e}"
                break
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_S * (2 ** attempt))

        return ClaudeResponse(text="", model=self.model, ok=False, error=last_error)
