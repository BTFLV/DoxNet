#!/usr/bin/env python3
"""Backward-compatible entry point.

Kept so existing `python DoxNet.py ...` invocations keep working. New
installs should use the `doxnet` console command (`pip install .`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from doxnet.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
