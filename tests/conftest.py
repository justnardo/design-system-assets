"""
Make scripts/ importable for the test files.

The scripts live as standalone CLIs (each has a main() and __main__ guard),
but their pure-logic functions are unit-testable. We add scripts/ to the
import path so tests can `import route_asset`, `import review_asset`, etc.
without spawning subprocesses.
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
