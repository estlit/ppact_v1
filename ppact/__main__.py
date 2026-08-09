"""Terminal entry point.

    python3 -m ppact

The README documented `python3 -m ppact.menu`, which exits silently: the
module has no __main__ block, so running it imports and returns. A
documented command that does nothing is worse than no command, because
the reader concludes the tool is broken rather than that the docs are.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

import sys

from .menu import main_menu

if __name__ == "__main__":
    sys.exit(main_menu())
