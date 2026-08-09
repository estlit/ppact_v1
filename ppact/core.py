"""
ppact.core - shared primitives

Environment detection, figure display, the colour palette, and the Anchor
type every scoring axis is built on. This module knows nothing about
memory, compute or applications; everything else imports from it.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


def in_notebook() -> bool:
    """True when running inside Jupyter, JupyterLab, or Google Colab."""
    if "google.colab" in sys.modules:
        return True
    try:
        shell = get_ipython().__class__.__name__   # noqa: F821  (IPython builtin)
    except NameError:
        return False
    return shell in ("ZMQInteractiveShell", "Shell", "GoogleColabShell")


def in_colab() -> bool:
    return "google.colab" in sys.modules


import matplotlib
if not in_notebook():
    # Outside a notebook, force a non-interactive backend so the module runs on
    # a headless machine. Inside a notebook the backend is left alone: whatever
    # it happens to be, _finalize() displays the saved PNG rather than relying
    # on plt.show(), so rendering works either way.
    matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ==============================================================================

PALETTE = ["#1E4976", "#C0504D", "#4F8A3D", "#7A5195"]

# Displayed size relative to the figure's native pixel size. The PNG on disk is
# always written at full resolution; only the on-screen rendering is scaled, so
# nothing about the layout changes. Shrinking figsize instead would keep font
# sizes fixed in points, making labels grow relative to the plot and eventually
# collide.
FIGURE_SCALE = 0.7


def set_figure_scale(scale: float) -> None:
    """Change how large figures appear in the notebook. 1.0 is native size."""
    global FIGURE_SCALE
    if not 0.1 <= scale <= 2.0:
        raise ValueError("scale must be between 0.1 and 2.0")
    FIGURE_SCALE = float(scale)


def _png_pixel_size(path: str):
    """Read width/height straight from the PNG header (no Pillow dependency)."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
    except Exception:
        return None


def _finalize(fig, path: str) -> str:
    """Save the figure, then display it in a notebook.

    The figure is written to disk first and the saved PNG is what gets
    displayed, deliberately. plt.show() depends on an interactive backend
    being active, and that is not something this module can count on:

      * a non-interactive backend may already be locked in from an earlier
        import in the same kernel session (backends do not reset per cell),
      * some kernels resolve to Agg when no GUI toolkit is installed,
      * "%matplotlib inline" may simply never have been run.

    In any of those cases plt.show() emits "FigureCanvasAgg is non-interactive"
    and draws nothing. Displaying the saved file works under every backend,
    including Agg. The figure is then closed so an active inline backend does
    not render it a second time at the end of the cell.
    """
    fig.savefig(path, bbox_inches="tight", dpi=150)

    if in_notebook():
        _display_png(path)

    plt.close(fig)
    return path


def _display_png(path: str) -> None:
    """Display a PNG in a notebook, scaled to FIGURE_SCALE.

    Works for any PNG, including ones Graphviz produced outside matplotlib.
    """
    if not in_notebook():
        return
    try:
        from IPython.display import display, Image
        size = _png_pixel_size(path)
        if size and FIGURE_SCALE != 1.0:
            display(Image(filename=path, width=int(size[0] * FIGURE_SCALE)))
        else:
            display(Image(filename=path))
    except Exception:
        pass



@dataclass(frozen=True)
class Anchor:
    """Maps a physical quantity onto 0..100.

    `at_zero`  -> the value that scores 0
    `at_hundred` -> the value that scores 100
    Set `log_scale=True` when the quantity spans orders of magnitude.
    """
    label: str
    unit: str
    at_zero: float
    at_hundred: float
    log_scale: bool = False
    rationale: str = ""

    def score(self, value: float) -> float:
        lo, hi = self.at_zero, self.at_hundred
        if self.log_scale:
            value, lo, hi = math.log10(max(value, 1e-9)), math.log10(lo), math.log10(hi)
        frac = (value - lo) / (hi - lo)
        return float(np.clip(frac * 100.0, 0.0, 100.0))


