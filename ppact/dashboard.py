"""
ppact.dashboard - five axes, one interface, and what that reveals

WHY THIS BEFORE POWER AND THERMAL
=================================
Performance, Area and Cost were built to the same chain:

    metric -> constraint -> slack -> status -> bottleneck -> recommendation

Whether they ACTUALLY share it is a different claim, and summarising three
tracks through one interface is how the gaps show. Building Power and
Thermal first would mean discovering the same gaps five times.

WHAT THIS DOES NOT DO
---------------------
Compute anything. Every figure here is read from the track that owns it.
A dashboard that recalculated would be a fourth opinion about numbers that
already have three.

WHAT IT REVEALED
----------------
Two things the tracks did not share until this was written:

    slack units differ per axis        inf/s, ms, mm2, USD - so the
                                       summary carries the unit, and no
                                       cross-axis slack comparison is
                                       offered
    bottleneck direction differs       lowest on Performance, largest on
                                       Area and Cost - so the row says
                                       which sense it means

Neither is a defect. Both would have become one if the dashboard had
flattened them into a single column.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

MET = "MET"
VIOLATED = "VIOLATED"
NOT_ESTABLISHED = "NOT ESTABLISHED"
PENDING = "PENDING DEFINITION"

IMPLEMENTED = "IMPLEMENTED"
PARTIAL = "PARTIAL"
# Traffic is its own state: the framework is settled and the score is not
# computed, which is neither "partial implementation" nor "not
# established" - the structure is complete and deliberately empty.
FRAMEWORK_DEFINED = "FRAMEWORK DEFINED"
SCORE_PENDING = "SCORE PENDING"


@dataclass(frozen=True)
class AxisRow:
    axis: str
    implementation: str

    metric: str                 # the figure, with its unit
    constraint: str             # what it is compared against
    slack: str                  # with unit - these do NOT share one
    status: str

    bottleneck: str
    bottleneck_sense: str       # lowest or largest - they differ
    recommendation: str

    blocked_on: str = ""


def build_dashboard(analysis) -> Tuple[AxisRow, ...]:
    """Read the tracks. Compute nothing.

    Every axis now arrives through ONE protocol - `ppact.track` - rather
    than five per-axis APIs the dashboard had to know individually. When
    it knew them individually, adding an axis meant editing this function;
    now it means adding a track.
    """
    from .track import all_tracks, NOT_ESTABLISHED as TRACK_NE

    rows: List[AxisRow] = []
    for t in all_tracks(analysis):
        # Traffic is its own state: framework settled, score deliberately
        # not computed. Power is pending a definition. Neither is
        # "partially implemented".
        if t.axis == "Traffic":
            impl, status = FRAMEWORK_DEFINED, SCORE_PENDING
        elif t.axis == "Power":
            impl, status = PARTIAL, PENDING
        else:
            impl, status = IMPLEMENTED, t.status
        rows.append(AxisRow(
            axis=t.axis, implementation=impl,
            metric=t.measured, constraint=t.constraint, slack=t.slack,
            status=status, bottleneck=t.bottleneck,
            bottleneck_sense=t.bottleneck_sense,
            recommendation=t.recommendation,
            blocked_on=t.blocked_on))
    return tuple(rows)


def render_dashboard(rows: Tuple[AxisRow, ...],
                     show_title: bool = True) -> List[str]:
    from .visual.text import wrap_text

    out = ["PPACT SUMMARY", ""] if show_title else []

    out.append(f"  {'axis':<13s}{'status':<20s}{'implementation'}")
    out.append("  " + "-" * 50)
    for r in rows:
        out.append(f"  {r.axis:<13s}{r.status:<20s}{r.implementation}")
    out.append("")

    for r in rows:
        out.append(f"  {r.axis.upper()}")
        out.append(f"      metric          {r.metric}")
        out.append(f"      constraint      {r.constraint}")
        out.append(f"      slack           {r.slack}")
        out.append(f"      status          {r.status}")
        out.append(f"      bottleneck      {r.bottleneck}")
        out.append(f"        sense         {r.bottleneck_sense}")
        out.append(f"      recommendation  {r.recommendation}")
        if r.blocked_on:
            # Narrowed from 56: the chained task indents every line by a
            # further two columns, and the longest wrap reached 79 there
            # while fitting here.
            for i, line in enumerate(wrap_text(r.blocked_on, 52)):
                out.append(f"      blocked on      {line}" if i == 0
                           else f"                      {line}")
        out.append("")

    # DEPLOYMENT GATES, listed apart from the axes.
    #
    # An axis is a dimension a designer chooses along. A gate is a verdict
    # on what the choices produced - thermal is computed FROM power and
    # area, which is why it moved here.
    out.append("  DEPLOYMENT GATES - verdicts, not dimensions")
    for name, note in (("accuracy", "the model meets its required "
                                    "accuracy"),
                       ("thermal", "power density against the declared "
                                   "limit"),
                       ("capacity", "the model fits in memory"),
                       ("memory cooling", "the memory can be cooled as "
                                          "configured")):
        out.append(f"      {name:<18s}{note}")
    out.append("")

    # WHAT THE INTERFACE DOES NOT UNIFY, said rather than hidden.
    for line in wrap_text(
            "Slacks are in different units - inf/s, ms, mm2, USD - and "
            "are not comparable across axes. A design with more area "
            "slack than cost slack is not thereby better on area.", 66):
        out.append(f"  {line}")
    out.append("")
    for line in wrap_text(
            "Bottleneck means the LOWEST throughput on Performance and "
            "the LARGEST contributor on Area and Cost. The sense line "
            "says which, because the same word points in opposite "
            "directions.", 66):
        out.append(f"  {line}")
    return out


def recommended_order(rows: Tuple[AxisRow, ...]) -> List[str]:
    """Which violated axis to address first, and why that is not a ranking.

    Ordered by nothing more than which constraints are violated. There is
    no model of how a change on one axis moves another, so this cannot
    say that fixing throughput is worth more than fixing area.
    """
    from .visual.text import wrap_text

    violated = [r for r in rows if r.status == VIOLATED]
    pending = [r for r in rows if r.status == PENDING]

    out = ["  RECOMMENDED ORDER", ""]
    if not violated:
        out.append("      No axis has a violated constraint.")
    else:
        for i, r in enumerate(violated, 1):
            out.append(f"      {i}. {r.axis:<12s}{r.bottleneck}")
        out.append("")
        for line in wrap_text(
                "Listed, not ranked. The model has no account of how a "
                "change on one axis moves another, so this cannot say "
                "which is worth more.", 60):
            out.append(f"      {line}")
    if pending:
        out.append("")
        out.append(f"      Pending definition: "
                   f"{', '.join(r.axis for r in pending)}")
    return out
