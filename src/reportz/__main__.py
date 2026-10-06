"""Executable entrypoint for python -m reportz."""

import sys
from reportz.cli import main

if __name__ == "__main__":
    sys.exit(main())
