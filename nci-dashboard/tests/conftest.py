"""Make the ``nci_dashboard`` package importable regardless of CWD."""

import sys
from pathlib import Path

DASHBOARD_ROOT = Path(__file__).resolve().parent.parent
if str(DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_ROOT))
