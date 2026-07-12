"""Entry point: ``python3 -m nci_dashboard``."""

import sys

from .server import main

if __name__ == "__main__":
    sys.exit(main())
