"""
Path wiring so the two sibling library packages import without installation.

The dashboard lives at ``<repo>/nci-dashboard/`` and consumes:
  - ``<repo>/nci-phase-4/nci_strategy_selector``
  - ``<repo>/nci-hybrid-phoenix/nci_phoenix``

Both packages are stdlib-only and are added to ``sys.path`` here rather than
being copied or modified, preserving their zero-dependency property.
"""

from __future__ import annotations

import sys
from pathlib import Path

# nci-dashboard/nci_dashboard/paths.py -> parents[2] == repo root
PKG_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = PKG_DIR.parent
REPO_ROOT = DASHBOARD_DIR.parent

PHASE4_ROOT = REPO_ROOT / "nci-phase-4"
PHOENIX_ROOT = REPO_ROOT / "nci-hybrid-phoenix"

STATIC_DIR = PKG_DIR / "static"
DATA_DIR = DASHBOARD_DIR / "data"

DEFAULT_BRAIN_STATE = DATA_DIR / "brain_state.json"
DEFAULT_VERSIONS_INDEX = DATA_DIR / "versions_index.json"

# Runtime state persisted across restarts (Phase 6/7) — QuantumAIBrain state
# (calibration + knowledge) and the server-side Portfolio. This is runtime data,
# not repo content, so ``data/state/`` is git-ignored.
DEFAULT_STATE_DIR = DATA_DIR / "state"
BRAIN_STATE_FILENAME = "brain.json"
PORTFOLIO_STATE_FILENAME = "portfolio.json"


def ensure_library_paths() -> None:
    """Prepend the two library package roots to ``sys.path`` (idempotent)."""
    for root in (PHASE4_ROOT, PHOENIX_ROOT):
        p = str(root)
        if p not in sys.path:
            sys.path.insert(0, p)
