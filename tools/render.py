"""Shorthand for `python -m tools.checks.render`.

    python -m tools.render lectern --iso --open

The renderer lives under `checks/` because its other half is a regression check:
`--manifest` fingerprints every block and says which ones moved. But drawing one
block to look at it is something you do constantly while working on a family,
and `tools.checks.render` is a long thing to type for that. This is the same
command under a shorter name; every option is the same and there is nothing here
but the alias.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.checks.render import main

if __name__ == "__main__":
    sys.exit(main())
