"""
ppact.power_basis - which time window a power figure is averaged over

WHY BOUNDARY IS NOT ENOUGH
==========================
Every power metric already declares a BOUNDARY - which blocks it covers.
None declares a BASIS - which time window it averages. Those are different
axes and the second is what makes two power figures comparable or not.

    System power (W)
        boundary   accelerator, CPU, ISP, memory, board
        basis      active-window average       <- not declared anywhere

That `System power` is an active-window average was recovered by reading
`energy_j / latency_s` in the source. The metric itself does not say it,
and a reader comparing it against a 120 W budget has no way to know the
budget and the figure may describe different windows.

THE RULE
--------
Two power figures may be compared only if their bases match. Where they do
not, the comparison is NOT ESTABLISHED and says why - rather than being
performed and quietly meaning nothing.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

NOT_ESTABLISHED = "NOT ESTABLISHED"

# The windows. Not a taxonomy invented here - each is a window the model
# either averages over or cannot.
# SCOPE. A third axis, and not implied by the other two.
#
# `System power` and `Accelerator module ceiling` differ in boundary and
# basis, and also in what they are figures ABOUT: one describes this design
# running this workload, the other describes a part whatever it is put in.
# A component rating does not become a system figure by being reported
# beside one.
SYSTEM = "system"
COMPONENT = "component"

ACTIVE_WINDOW = "active-window average"
STEADY_STATE = "steady-state average"
PEAK = "peak instantaneous"
PER_JOB = "per job"
DERIVED = "derived from another basis"


@dataclass(frozen=True)
class PowerMetric:
    name: str
    definition: str
    unit: str
    basis: str
    boundary_declared: bool
    scope: str = SYSTEM
    note: str = ""


# EVERY power figure the engine reports, with the basis recovered from the
# source. Held here rather than in the engine because adding a field to
# eleven metrics is an engine change, and this file has to exist first to
# say what would go in it.
POWER_METRICS: Tuple[PowerMetric, ...] = (
    PowerMetric(
        "System power (W)",
        "energy for one job divided by that job's latency",
        "W", ACTIVE_WINDOW, True, SYSTEM,
        "The average while a job runs. At 60 inf/s and 4.857 ms latency "
        "that is 4.857 ms of every 16.667 ms; the idle is excluded."),
    PowerMetric(
        "Energy per inference (mJ)",
        "total energy for one job",
        "mJ", PER_JOB, True, SYSTEM,
        "Unaffected by which window a power figure averages over."),
    PowerMetric(
        "Dynamic energy per inference (mJ)",
        "switching energy for one job",
        "mJ", PER_JOB, False, SYSTEM),
    PowerMetric(
        "Static energy per inference (mJ)",
        "leakage energy over one job's latency",
        "mJ", PER_JOB, False, SYSTEM,
        "Leakage does not stop between jobs, so this is not the leakage "
        "of a whole interval."),
    PowerMetric(
        "Accelerator active power (W)",
        "the accelerator die's draw while active",
        "W", ACTIVE_WINDOW, True, COMPONENT),
    PowerMetric(
        "CPU active power (W)",
        "the host's draw while active",
        "W", ACTIVE_WINDOW, False, COMPONENT),
    PowerMetric(
        "Memory active power (W)",
        "the memory devices' draw while active",
        "W", ACTIVE_WINDOW, False, COMPONENT),
    PowerMetric(
        "Compute power (W)", "accelerator draw, averaged",
        "W", NOT_ESTABLISHED, False, COMPONENT,
        "Which window this averages over is not recoverable from the "
        "source without assuming one."),
    PowerMetric(
        "Memory power (W)", "memory draw, averaged",
        "W", NOT_ESTABLISHED, False, COMPONENT,
        "As above."),
    PowerMetric(
        "Static power (W)", "leakage",
        "W", ACTIVE_WINDOW, False, SYSTEM,
        "Reported over the active window, though leakage is continuous."),
    PowerMetric(
        "Accelerator module ceiling (W)",
        "the vendor's rated maximum for the accelerator module",
        "W", PEAK, False, COMPONENT,
        "A RATING, not a measurement. It is the one peak figure here and "
        "it belongs to a part, not to this design running this workload."),
    PowerMetric(
        "Power density (W/mm2)",
        "system power over package footprint",
        "W/mm2", ACTIVE_WINDOW, False, SYSTEM,
        "Inherits its basis from System power. Heat responds to the "
        "steady-state average - TH-Q1."),
)

# The budget. Its basis is the open question.
BUDGET_BASIS = NOT_ESTABLISHED


def comparable(basis_a: str, basis_b: str,
               scope_a: str = SYSTEM, scope_b: str = SYSTEM
               ) -> Tuple[bool, str]:
    """Whether two figures may be compared, and why not when they cannot.

    Not a courtesy check. A 3.643 W active-window figure against a 120 W
    budget of unknown basis is an arithmetic operation that produces a
    number and establishes nothing.
    """
    if basis_a == NOT_ESTABLISHED or basis_b == NOT_ESTABLISHED:
        return False, ("one of the two does not declare a measurement "
                       "basis")
    if basis_a != basis_b:
        return False, (f"measurement basis differs: {basis_a} against "
                       f"{basis_b}")
    if scope_a != scope_b:
        # A component rating and a system figure describe different
        # objects. Same window, same blocks, still not the same thing.
        return False, (f"measurement scope differs: {scope_a} against "
                       f"{scope_b}")
    return True, ""


def render_power_framework(show_title: bool = True) -> List[str]:
    from .visual.text import wrap_text

    out = ["POWER FRAMEWORK", ""] if show_title else []
    for line in wrap_text(
            "Every power figure declares a BOUNDARY - which blocks it "
            "covers - and a BASIS - which time window it averages. The "
            "second is what makes two figures comparable, and none of "
            "these declared it until this table.", 66):
        out.append(f"  {line}")
    out.append("")

    # Names wrap onto their own line: the longest is 34 characters and
    # the basis column pushed the row past 78.
    out.append(f"  {'metric':<36s}{'unit':<8s}{'basis / scope'}")
    out.append("  " + "-" * 62)
    for pm in POWER_METRICS:
        mark = " " if pm.boundary_declared else "*"
        out.append(f" {mark}{pm.name}")
        out.append(f"      {pm.unit:<8s}{pm.basis} / {pm.scope}")
    out.append("  " + "-" * 62)
    out.append("  * boundary not declared by the metric")
    out.append("")

    missing = [pm.name for pm in POWER_METRICS
               if pm.basis == NOT_ESTABLISHED]
    out.append(f"  Basis not established        {len(missing)} of "
               f"{len(POWER_METRICS)}")
    for name in missing:
        out.append(f"      {name}")
    out.append("")

    out.append(f"  Power budget basis          {BUDGET_BASIS}")
    for line in wrap_text(
            "The library declares 120 W and does not say over which "
            "window. Until it does, no power figure is compared against "
            "it - PW-Q1.", 62):
        out.append(f"      {line}")
    out.append("")

    # THE COMPARISON THAT IS REFUSED, shown rather than merely described.
    ok, why = comparable(ACTIVE_WINDOW, BUDGET_BASIS)
    out.append("  System power against the budget")
    out.append(f"      Comparison              "
               f"{'PERFORMED' if ok else NOT_ESTABLISHED}")
    if not ok:
        # The reason goes on its OWN lines, not trailing a 30-column
        # label: wrapping it at 52 still put the first 52 characters
        # after the label and reached 81.
        out.append("      Reason")
        for line in wrap_text(why, 58):
            out.append(f"          {line}")
    out.append("")

    for line in wrap_text(
            "Thermal inherits this. Power density is System power over "
            "footprint, so it carries the active-window basis, and TH-Q1 "
            "is answered by whatever answers PW-Q1.", 66):
        out.append(f"  {line}")
    return out
