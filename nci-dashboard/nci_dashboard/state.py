"""
Durable state persistence for the dashboard (Phase 6/7).

Small, dependency-free JSON persistence with **atomic** writes: serialize to a
sibling temporary file in the same directory, then ``os.replace`` it over the
target. ``os.replace`` is atomic on POSIX and Windows, so a crash mid-write can
never leave a half-written state file — the reader either sees the old complete
file or the new complete file.

Callers are expected to hold their own lock while writing, so concurrent
mutations serialize a consistent snapshot; this module only guarantees the
write itself is atomic.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional


def atomic_write_json(path: Path, obj: Any) -> None:
    """Serialize ``obj`` to ``path`` atomically (tmp file + ``os.replace``)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, separators=(",", ":"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_json(path: Optional[Path]) -> Optional[Any]:
    """
    Load JSON from ``path``. Returns ``None`` if the file is absent, unreadable,
    or corrupt — a corrupt state file must never crash boot; the caller falls
    back to a fresh instance.
    """
    if path is None:
        return None
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
