"""NCI nerdcommand options-assistant visual dashboard (stdlib-only web layer)."""

from .api import DashboardAPI, ApiError, DISCLAIMER
from .server import build_server, main

__all__ = ["DashboardAPI", "ApiError", "DISCLAIMER", "build_server", "main"]
__version__ = "1.0.0"
