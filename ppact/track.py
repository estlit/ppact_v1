"""
ppact.track - the five stages, identical on every axis

WHY THIS EXISTS
===============
The claim was that Studio is one constraint analysis engine applied five
times. In code it was not: each axis had its own entry point, its own
return type, and its own idea of what a stage was called.

    Performance   build_performance_constraints
    Area          build_area_view      recommend_area
    Cost          build_cost_view      recommend_cost
    Power         build_power_view     analyse_power

Four shapes for one pattern. A caller wanting "the bottleneck on every
axis" had to know four APIs, and a sixth axis would have added a fifth.

    measure -> constraint -> slack -> bottleneck -> recommendation

Every axis produces that, and this module is where that stops being a
description and becomes a type. Each Track keeps its own analysis - this
adapts, it does not recompute.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
Fill a stage in. An axis whose bottleneck is not established reports
NOT ESTABLISHED at that stage, and the uniform shape is what makes the gap
visible rather than hiding it behind a differently-named function.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

NOT_ESTABLISHED = "NOT ESTABLISHED"
NOT_BUILT = "NOT BUILT"

MET = "MET"
VIOLATED = "VIOLATED"
NOT_CONSTRAINED = "NOT CONSTRAINED"

# The five stages, in order. Named once so no axis can invent a sixth or
# skip one.
STAGES = ("measured", "constraint", "slack", "bottleneck",
          "recommendation")


@dataclass(frozen=True)
class TrackResult:
    """One axis, through the five stages. Same type for every axis."""
    axis: str

    measured: str               # the figure, with unit
    constraint: str             # what it is held to
    slack: str                  # with unit - axes do NOT share one
    status: str                 # MET / VIOLATED / NOT CONSTRAINED
    bottleneck: str
    bottleneck_sense: str       # lowest or largest - they differ
    recommendation: str

    blocked_on: str = ""

    def stage(self, name: str) -> str:
        return {"measured": self.measured, "constraint": self.constraint,
                "slack": self.slack, "bottleneck": self.bottleneck,
                "recommendation": self.recommendation}[name]


def _performance(analysis) -> TrackResult:
    from .visual import build_flow
    from .performance_constraints import build_performance_constraints

    flow = build_flow(analysis)
    c = build_performance_constraints(analysis, flow)
    worst = (min(c.stations, key=lambda s: s.slack_ms)
             if c.stations else None)
    delivered = analysis.current_result.metrics.get(
        "Delivered throughput (inf/s)", 0.0)
    return TrackResult(
        "Performance",
        measured=f"{delivered:.1f} inf/s delivered",
        constraint=(f"target {c.target_rate:.0f} inf/s"
                    if c.target_rate else NOT_ESTABLISHED),
        slack=(f"{worst.slack_ms:+.3f} ms" if worst else NOT_ESTABLISHED),
        status=c.throughput_status,
        bottleneck=c.throughput_critical or NOT_ESTABLISHED,
        bottleneck_sense="lowest throughput",
        recommendation=("see the recommendation screen"
                        if c.throughput_status == VIOLATED
                        else "none - constraint met"))


def _area(analysis) -> TrackResult:
    from .area import build_area_view, recommend_area

    v = build_area_view(analysis)
    rec = recommend_area(v)
    return TrackResult(
        "Area",
        measured=f"{v.soc_silicon_mm2:.2f} mm2 SoC silicon",
        constraint=(f"SoC budget {v.soc_budget_mm2:.0f} mm2"
                    if v.soc_budget_mm2 else NOT_ESTABLISHED),
        slack=(f"{v.soc_slack_mm2:+.2f} mm2"
               if v.soc_slack_mm2 is not None else NOT_ESTABLISHED),
        status=v.soc_status,
        bottleneck=v.largest or NOT_ESTABLISHED,
        bottleneck_sense="largest contributor",
        recommendation=(rec.action if rec else "none - constraint met"))


def _cost(analysis) -> TrackResult:
    from .cost import build_cost_view, recommend_cost

    v = build_cost_view(analysis)
    rec = recommend_cost(v)
    return TrackResult(
        "Cost",
        measured=f"{v.system_cost_usd:.2f} USD system cost",
        constraint=(f"BOM budget {v.budget_usd:.0f} USD"
                    if v.budget_usd else NOT_ESTABLISHED),
        slack=(f"{v.slack_usd:+.2f} USD"
               if v.slack_usd is not None else NOT_ESTABLISHED),
        status=v.status,
        bottleneck=v.largest_known or NOT_ESTABLISHED,
        bottleneck_sense="largest KNOWN contributor",
        recommendation=(rec.action if rec else "none - constraint met"))


def _power(analysis) -> TrackResult:
    from .power import build_power_view, analyse_power

    v = build_power_view(analysis)
    a = analyse_power(v)
    return TrackResult(
        "Power",
        measured=(f"{v.steady_state_w:.3f} W steady-state average"
                  if v.steady_state_w is not None else NOT_ESTABLISHED),
        constraint=(f"declared {v.declared_budget_w:.0f} W, basis "
                    f"{NOT_ESTABLISHED}"
                    if v.declared_budget_w else NOT_ESTABLISHED),
        slack=NOT_ESTABLISHED,
        status=NOT_CONSTRAINED,
        bottleneck=a.bottleneck,
        bottleneck_sense="no per-block decomposition",
        recommendation=a.recommendation,
        blocked_on="PW-Q1: is the budget a sustained or an instantaneous "
                   "limit?")


def _traffic(analysis) -> TrackResult:
    from .memory_analysis import analyse_memory

    mem = analyse_memory(analysis)
    util = None
    if mem.computable and mem.effective_bandwidth > 0:
        util = mem.concurrent_requirement / mem.effective_bandwidth * 100
    return TrackResult(
        "Traffic",
        measured=(f"shared memory {util:.1f}% utilised - 1 of 10 "
                  f"components" if util is not None else NOT_ESTABLISHED),
        constraint=NOT_ESTABLISHED,
        slack=NOT_ESTABLISHED,
        status=NOT_CONSTRAINED,
        bottleneck=NOT_ESTABLISHED,
        bottleneck_sense="needs more than one component",
        recommendation=NOT_ESTABLISHED,
        blocked_on="Bus, AXI/NoC, DMA, cache, buffers, arbitration, "
                   "waiting and idle are not modelled. TR-D1.")


# Order fixed here, so a caller never depends on dictionary order.
TRACKS: Tuple[Tuple[str, Callable], ...] = (
    ("Performance", _performance),
    ("Area", _area),
    ("Cost", _cost),
    ("Power", _power),
    ("Traffic", _traffic),
)


def all_tracks(analysis) -> Tuple[TrackResult, ...]:
    return tuple(fn(analysis) for _, fn in TRACKS)
