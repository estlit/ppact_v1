"""
ppact.visual.models - what a renderer is given

WHY THESE EXIST
===============
Today a screen computes a result and formats it in the same breath. That
works until a second renderer appears - a PNG chart, a web page - and then
the same quantity gets formatted twice, differently, and the two disagree in
a way nobody notices because they are never on screen together.

So a screen builds one of these objects, and a renderer draws it. Terminal,
PNG and any future renderer take the SAME object, which is the only
mechanical guarantee that they agree.

WHAT A DATA OBJECT MAY NOT DO
-----------------------------
Compute. These carry values that have already been computed and the labels
and units that belong to them. A normalisation IS carried out here - a
spider chart needs one - but it is carried out ONCE, in one place, and the
formula is recorded on the axis so a reader can see what was done to the
number they recognise.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class MetricBarData:
    """Named engineering values with their units, for a bar chart.

    Values stay in PHYSICAL units. A bar chart exists to show the actual
    figure; normalising it would make it a worse spider chart.
    """
    title: str
    metric: str
    unit: str
    series: Tuple[Tuple[str, float], ...]   # (design name, value)
    lower_is_better: bool = True

    def maximum(self) -> float:
        vals = [v for _, v in self.series
                if isinstance(v, float) and not math.isnan(v)]
        return max(vals) if vals else 0.0


@dataclass(frozen=True)
class BreakdownData:
    """Parts that sum to a whole, for a reason-breakdown bar.

    The residue is carried rather than dropped. A breakdown whose parts do
    not sum to the whole is a story about a number, and a renderer that
    silently omitted the difference would hide exactly that.
    """
    title: str
    unit: str
    parts: Tuple[Tuple[str, float], ...]
    total: float
    residue: float = 0.0

    def sums(self, tolerance: float = 1e-9) -> bool:
        return abs(sum(v for _, v in self.parts) + self.residue
                   - self.total) < tolerance


@dataclass(frozen=True)
class SpiderAxis:
    """One axis of a spider chart, and what was done to the number.

    Every axis stores the formula that produced its score, because a reader
    who recognises 'latency 11.5 ms' and sees '38' on a chart is owed an
    explanation of how one became the other. An axis without its formula is
    a shape.
    """
    name: str
    unit: str
    raw: float                 # the engineering value, as computed
    score: float               # 0-100, outward is always better
    formula: str               # how raw became score, in words
    lower_is_better: bool
    reference: float           # what the score is measured against
    # WHAT THE CLIP HID.
    #
    # An axis at 100 was shown as "100+" and the number behind it was
    # discarded, so a design 27 times inside its area budget and one 78
    # times inside its cost budget looked identical. The score before
    # clipping is kept so the chart can say what it pinned.
    unclipped: Optional[float] = None
    clipped: bool = False      # the raw value fell outside the axis range


@dataclass(frozen=True)
class SpiderData:
    """Two or more designs on the same normalised axes.

    Outward is better on EVERY axis. Mixing directions - latency inward,
    throughput outward - produces a shape a reader cannot compare, and they
    will compare it anyway.
    """
    title: str
    designs: Tuple[str, ...]
    axes: Tuple[Tuple[str, Tuple[SpiderAxis, ...]], ...]  # design -> axes

    def axis_names(self) -> Tuple[str, ...]:
        return tuple(a.name for a in self.axes[0][1]) if self.axes else ()

    def consistent(self) -> bool:
        """Every design must carry the same axes in the same order."""
        if not self.axes:
            return False
        first = self.axis_names()
        return all(tuple(a.name for a in axes) == first
                   for _, axes in self.axes)

    def any_clipped(self) -> bool:
        return any(a.clipped for _, axes in self.axes for a in axes)
