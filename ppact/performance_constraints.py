"""
ppact.performance_constraints - two constraints, and the room left in each

NAMING
======
    Performance Constraints   the analysis
    Throughput constraint     against the application target rate
    Latency constraint        against the application latency budget
    Slack                     how much room is left in one of them

`Constraint` says WHAT is evaluated; `slack` says HOW MUCH is left. The
screen is named for the first, because a reader arriving at it wants to
know which requirements are being checked before being handed a margin.

WHY THIS IS NOT CALLED STATIC TIMING
====================================
The design came from reading a static timing report, and the vocabulary is
deliberately not borrowed. A chip designer reads "static timing" as clock
edges, setup and hold, and cycle-accurate paths - none of which exists
here. A system architect reads the same words and imports the wrong mental
model.

What this analysis actually does is compare a figure against a stated
constraint and report the difference. "Constraint slack" says that; "static
timing" says something the model cannot deliver.

WHY TWO GRAPHS
==============
A timing report has one graph and one critical path. This model has two,
and they do not share stations:

    latency path        host active -> accelerator core
    throughput path     host, accelerator, ISP, shared memory

Measured across 81 configurations, the throughput-critical station is a
block the latency flow does not draw in 36 of them. Reporting one "critical
path" would be picking one of two answers and hiding the choice.

WHAT THE ORIGINAL ANALOGY OFFERED, AND WHAT IT DID NOT
------------------------------------------------------
Kept, as design rationale: slack is always against a NAMED constraint, and
a report must say which path it is talking about. Those two habits are the
whole value.

Not kept: setup and hold - there is no clock, and nothing arrives too
early. Cycle accuracy - these are analytical estimates over a whole job.
Path enumeration - there are two paths, not a searched set.

WHAT IS NOT DEFINED
-------------------
Per-station latency slack. Splitting a path's slack across its stations
needs a rule for how much of the budget each one owns, and the model has
none. Inventing one at display time is the shape that made `host_demand`
unusable.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

MET = "MET"
VIOLATED = "VIOLATED"
NOT_CONSTRAINED = "NOT CONSTRAINED"


@dataclass(frozen=True)
class StationSlack:
    """Throughput slack for one station, against the required interval."""
    name: str
    station_ms: float
    required_interval_ms: float
    slack_ms: float
    slack_pct: float
    is_critical: bool
    in_latency_flow: bool

    @property
    def status(self) -> str:
        return MET if self.slack_ms >= 0 else VIOLATED


@dataclass(frozen=True)
class PerformanceConstraintView:
    # Throughput graph
    target_rate: Optional[float]
    required_interval_ms: Optional[float]
    stations: Tuple[StationSlack, ...]
    throughput_critical: str

    # Latency graph - a PATH, not a set of stations. Slack belongs to the
    # path because no rule allocates the budget among its stations.
    latency_path: Tuple[str, ...]
    latency_total_ms: float
    latency_budget_ms: Optional[float]
    latency_slack_ms: Optional[float]

    @property
    def throughput_status(self) -> str:
        if self.target_rate is None:
            return NOT_CONSTRAINED
        return (VIOLATED if any(s.slack_ms < 0 for s in self.stations)
                else MET)

    @property
    def latency_status(self) -> str:
        if self.latency_slack_ms is None:
            return NOT_CONSTRAINED
        return MET if self.latency_slack_ms >= 0 else VIOLATED

    @property
    def graphs_disagree(self) -> bool:
        """Whether the two critical answers name different blocks."""
        if not self.throughput_critical or not self.latency_path:
            return False
        return not any(self.throughput_critical.lower() in p.lower()
                       or p.lower() in self.throughput_critical.lower()
                       for p in self.latency_path)


def build_performance_constraints(analysis, flow
                                  ) -> PerformanceConstraintView:
    """Both graphs, from figures the model already computes.

    The throughput stations come from the engine, not from the flow: they
    are a different decomposition, and deriving a rate from flow times
    gave 343.67 inf/s where the engine says 99.73.
    """
    from .application import APPLICATION_LIBRARY

    app = APPLICATION_LIBRARY[analysis.app_key]
    metrics = analysis.current_result.metrics

    rate = getattr(app, "target_inferences_per_s", 0) or None
    budget = getattr(app, "latency_budget_ms", 0) or None

    stations: List[StationSlack] = []
    critical = ""
    interval = 1000.0 / rate if rate else None

    if interval:
        raw = metrics.get("Throughput stations (s)", {})
        drawn = " ".join(s.name for s in flow.stations).lower()
        active = [(n, v * 1e3) for n, v in raw.items() if v > 0]
        for name, ms in active:
            slack = interval - ms
            stations.append(StationSlack(
                name, ms, interval, slack, slack / interval * 100.0,
                False, name.lower() in drawn))
        if stations:
            worst = min(stations, key=lambda s: s.slack_ms)
            stations = [
                StationSlack(s.name, s.station_ms, s.required_interval_ms,
                             s.slack_ms, s.slack_pct, s is worst,
                             s.in_latency_flow)
                for s in stations]
            critical = worst.name

    path = tuple(s.name for s in flow.stations)
    total = float(metrics.get("Latency (ms)", 0.0))
    lat_slack = (budget - total) if budget else None

    return PerformanceConstraintView(
        rate, interval, tuple(stations), critical,
        path, total, budget, lat_slack)


def render_performance_constraints(
        view: PerformanceConstraintView,
        show_title: bool = True) -> List[str]:
    from .visual.text import wrap_text

    # Suppressible, because the chained System Flow task prints its own
    # numbered heading and the two appeared one after the other - the
    # same duplication the balance chart had.
    out = ["PERFORMANCE CONSTRAINTS", ""] if show_title else []
    for line in wrap_text(
            "Two constraints, evaluated separately. They do not share "
            "stations and can name different blocks as critical, so their "
            "slacks are never compared or added.", 66):
        out.append(f"  {line}")
    out.append("")

    # --- throughput graph -------------------------------------------------
    out.append("  THROUGHPUT CONSTRAINT   against the application target "
               "rate")
    if view.target_rate is None:
        out.append("      Target rate                 NOT ESTABLISHED")
        out.append("      Throughput slack            NOT CONSTRAINED")
    else:
        out.append(f"      Target rate                 "
                   f"{view.target_rate:.0f} inf/s")
        out.append(f"      Required interval           "
                   f"{view.required_interval_ms:.3f} ms")
        out.append("")
        out.append(f"      {'station':<20s}{'time':>9s}{'slack':>10s}"
                   f"{'slack':>8s}{'':>4s}")
        out.append(f"      {'':<20s}{'ms':>9s}{'ms':>10s}{'%':>8s}")
        out.append("      " + "-" * 52)
        for s in sorted(view.stations, key=lambda x: x.slack_ms):
            mark = "<" if s.is_critical else " "
            out.append(f"    {mark} {s.name:<20s}{s.station_ms:>9.3f}"
                       f"{s.slack_ms:>10.3f}{s.slack_pct:>8.1f}"
                       f"   {s.status}")
        out.append("")
        out.append(f"      Throughput-critical station "
                   f"{view.throughput_critical}")
        out.append(f"      Throughput constraint       "
                   f"{view.throughput_status}")

    out.append("")

    # --- latency graph ----------------------------------------------------
    out.append("  LATENCY CONSTRAINT      against the application latency "
               "budget")
    out.append(f"      Path                        "
               f"{' -> '.join(view.latency_path)}")
    out.append(f"      Path total                  "
               f"{view.latency_total_ms:.3f} ms")
    if view.latency_budget_ms is None:
        out.append("      Latency budget              NOT ESTABLISHED")
        out.append("      Latency slack               NOT CONSTRAINED")
    else:
        out.append(f"      Latency budget              "
                   f"{view.latency_budget_ms:.3f} ms")
        out.append(f"      Latency constraint slack    "
                   f"{view.latency_slack_ms:+.3f} ms")
        out.append(f"      Latency constraint          "
                   f"{view.latency_status}")
    out.append("")
    # Per-station latency slack is NOT shown, and the absence is stated.
    # An omitted row reads as a quantity that does not apply; this one
    # applies and has no definition.
    out.append("      Per-station latency slack   NOT DEFINED")
    for line in wrap_text(
            "Splitting the path's slack among its stations needs a rule "
            "for how much of the budget each one owns. The model has "
            "none, and inventing one here would be an allocation made at "
            "display time.", 60):
        out.append(f"        {line}")

    out.append("")
    if view.graphs_disagree:
        for line in wrap_text(
                f"THE TWO CONSTRAINTS DISAGREE. "
                f"{view.throughput_critical} is "
                f"throughput-critical and is not on the latency path. "
                f"Neither answer is the critical path; there are two, and "
                f"this design has different ones.", 66):
            out.append(f"  {line}")
    else:
        for line in wrap_text(
                "Both constraints point at the same part of the design "
            "here. "
                "That is not always so - across 81 configurations the "
                "throughput-critical station is absent from the latency "
                "path in 36 of them.", 66):
            out.append(f"  {line}")

    out.append("")
    for line in wrap_text(
            "There is no clock here and nothing arrives too early, so "
            "no setup or hold slack applies. Throughput slack and latency "
            "slack are against different constraints and are never "
            "compared or added.", 66):
        out.append(f"  {line}")
    return out
