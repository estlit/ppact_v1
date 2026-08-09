"""
ppact.perf_bottleneck - what limits system throughput

THREE THROUGHPUTS, NEVER MIXED
==============================
    delivered     what the system provides now
    limit         the most this structure could sustain
    required      what the application asks for

They coincide often enough that one name for all three would pass most
fixtures, which is why they are separated here rather than where a defect
would show it.

    delivered 60.0    limit 99.7    required 60.0

THE BOTTLENECK IS THE LOWEST THROUGHPUT
---------------------------------------
Not the largest latency contribution. On the same design the host holds
73.5% of one job and the ISP sets the rate at 99.7 inf/s - the ISP is the
bottleneck and has no box in the latency flow at all.

Across 81 configurations the throughput-critical stage is absent from the
latency path in 36 of them. A tool equating the two is wrong more than a
third of the time.

BOTTLENECK IS NOT VIOLATION
---------------------------
A stage can be the first to bind and still leave the requirement met:

    bottleneck              YES   the ISP binds first
    constraint violation    NO    99.7 available against 60 required

Reporting the first as though it were the second sends a designer to fix
something that is not broken.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

MET = "MET"
VIOLATED = "VIOLATED"
NOT_ESTABLISHED = "NOT ESTABLISHED"


@dataclass(frozen=True)
class StageThroughput:
    """One stage, with its margin against the required throughput.

    SLACK, not margin. The two words were both in use - `slack` in the
    performance, area and cost constraints, `margin` for the measured
    results bands and the thermal gate - and a third meaning would have
    made neither reliable. Slack is distance to a constraint; margin is
    a band.

    Slack here is a stage's throughput less what the application
    requires, so the bottleneck is the stage with the LEAST slack, as a
    critical path is the one with the least timing slack.

    THE SIGN IS OPPOSITE to a timing report's, and deliberately. There,
    less delay is better and slack is required minus arrival. Here more
    throughput is better and slack is throughput minus required. The
    analysis is the same shape; the quantity is not the same quantity.

    Ordering by slack and by throughput give the same answer - the
    required rate is a constant subtracted from every stage - so slack
    adds no ranking. It adds a per-stage figure a reader can check the
    verdict against, and a sign.
    """
    name: str
    inf_s: float
    is_bottleneck: bool
    slack_inf_s: Optional[float] = None
    slack_pct: Optional[float] = None

    @property
    def meets_requirement(self) -> Optional[bool]:
        if self.slack_inf_s is None:
            return None
        return self.slack_inf_s >= 0


@dataclass(frozen=True)
class PerformanceBottleneck:
    stages: Tuple[StageThroughput, ...]

    delivered_inf_s: float
    limit_inf_s: Optional[float]
    required_inf_s: Optional[float]

    bottleneck: str
    slack_inf_s: Optional[float]

    @property
    def status(self) -> str:
        if self.slack_inf_s is None:
            return NOT_ESTABLISHED
        return MET if self.slack_inf_s >= 0 else VIOLATED

    @property
    def violated(self) -> bool:
        return self.status == VIOLATED


def find_bottleneck(analysis) -> PerformanceBottleneck:
    """From the ENGINE'S throughput stations, not the latency flow.

    The two are different decompositions. Deriving a rate from latency
    flow times gave 343.67 inf/s where the engine says 99.73, agreeing
    only when the ISP happened to be idle.
    """
    from .application import APPLICATION_LIBRARY

    app = APPLICATION_LIBRARY[analysis.app_key]
    m = analysis.current_result.metrics
    raw = m.get("Throughput stations (s)", {})

    stages: List[StageThroughput] = []
    for name, seconds in raw.items():
        # A stage at zero is not a stage with infinite throughput; it is
        # a stage that is not configured.
        if seconds <= 0:
            continue
        stages.append(StageThroughput(name, 1000.0 / (seconds * 1e3),
                                      False))

    required = getattr(app, "target_inferences_per_s", 0) or None

    limit = bottleneck = None
    if stages:
        # LEAST MARGIN, which for a common required rate is the same
        # stage as the lowest throughput. Written as the margin because
        # that is the quantity the verdict is about, and because it keeps
        # its meaning if a future model gives stages different required
        # rates.
        def _slack(st):
            return (st.inf_s - required) if required else st.inf_s
        slowest = min(stages, key=_slack)
        # A TIE is reported as a tie. Picking one arbitrarily would name
        # a stage the model has no reason to prefer, and a reader acting
        # on it would improve one of two equal limits.
        tied = [st for st in stages
                if abs(_slack(st) - _slack(slowest)) < 1e-9]
        stages = [
            StageThroughput(
                s.name, s.inf_s, s is slowest,
                (s.inf_s - required) if required else None,
                ((s.inf_s - required) / required * 100.0
                 if required else None))
            for s in stages]
        limit = slowest.inf_s
        bottleneck = (slowest.name if len(tied) == 1
                      else " and ".join(sorted(t.name for t in tied))
                      + "  (tie)")

    slack = (limit - required) if (limit and required) else None

    return PerformanceBottleneck(
        stages=tuple(stages),
        delivered_inf_s=float(m.get("Delivered throughput (inf/s)", 0.0)),
        limit_inf_s=limit,
        required_inf_s=required,
        bottleneck=bottleneck or NOT_ESTABLISHED,
        slack_inf_s=slack)


def render_performance_bottleneck(b: PerformanceBottleneck,
                                  show_title: bool = True) -> List[str]:
    from .visual.text import wrap_text

    out = ["PERFORMANCE BOTTLENECK", ""] if show_title else []

    out.append(f"  {'stage':<20s}{'throughput':>11s}{'slack':>10s}"
               f"{'slack':>8s}  {'status'}")
    out.append(f"  {'':<20s}{'inf/s':>11s}{'inf/s':>10s}{'%':>8s}")
    out.append("  " + "-" * 60)
    for s in sorted(b.stages, key=lambda x: (x.slack_inf_s
                                             if x.slack_inf_s is not None
                                             else x.inf_s)):
        mark = "<" if s.is_bottleneck else " "
        if s.slack_inf_s is None:
            out.append(f"  {mark} {s.name:<18s}{s.inf_s:>11.1f}"
                       f"{'n/e':>10s}{'n/e':>8s}  {NOT_ESTABLISHED}")
        else:
            out.append(f"  {mark} {s.name:<18s}{s.inf_s:>11.1f}"
                       f"{s.slack_inf_s:>+10.1f}{s.slack_pct:>+8.1f}"
                       f"  {MET if s.meets_requirement else VIOLATED}")
    out.append("")
    for line in wrap_text(
            "Slack is a stage's throughput less the required rate, and "
            "the bottleneck is the stage with the LEAST slack. This is "
            "STA-style minimum-slack analysis applied to throughput "
            "stages - the same shape, and the sign runs the other way "
            "because more throughput is better where less delay is.", 66):
        out.append(f"  {line}")
    out.append("")
    for line in wrap_text(
            "Margin is a stage's throughput less the required rate. The "
            "bottleneck is the stage with the LEAST margin - the same "
            "rule a timing report uses to find a critical path.", 66):
        out.append(f"  {line}")
    out.append("")

    # THE THREE, listed together so they cannot be confused by being
    # reported in different places.
    out.append(f"  System delivered throughput  "
               f"{b.delivered_inf_s:>8.1f} inf/s")
    out.append(f"  System throughput limit      "
               f"{b.limit_inf_s:>8.1f} inf/s"
               if b.limit_inf_s is not None else
               f"  System throughput limit      {NOT_ESTABLISHED}")
    out.append(f"  Required throughput          "
               f"{b.required_inf_s:>8.1f} inf/s"
               if b.required_inf_s is not None else
               f"  Required throughput          {NOT_ESTABLISHED}")
    if b.slack_inf_s is not None:
        out.append(f"  Throughput slack             "
                   f"{b.slack_inf_s:>+8.1f} inf/s")
    out.append(f"  Status                       {b.status}")
    out.append("")
    for line in wrap_text(
            "Delivered is what the system provides now; the limit is the "
            "most this structure could sustain; required is what the "
            "application asks. Three figures, and they are not "
            "interchangeable.", 66):
        out.append(f"  {line}")
    out.append("")

    out.append(f"  Throughput bottleneck        {b.bottleneck}")
    if b.limit_inf_s is not None:
        out.append(f"  Bottleneck throughput        "
                   f"{b.limit_inf_s:>8.1f} inf/s")
    out.append("")
    for line in wrap_text(
            "The throughput bottleneck is determined by the lowest stage "
            "throughput, not by the largest latency contribution. A stage "
            "holding most of one job's time may not be the one setting "
            "the rate.", 66):
        out.append(f"  {line}")
    out.append("")

    # BOTTLENECK IS NOT VIOLATION.
    out.append("  Interpretation")
    if b.status == MET:
        for line in wrap_text(
                f"{b.bottleneck} is the first stage that reaches full "
                f"utilisation as demand increases. The current "
                f"requirement is still satisfied - a bottleneck is not a "
                f"violation.", 62):
            out.append(f"      {line}")
    elif b.status == VIOLATED:
        for line in wrap_text(
                f"{b.bottleneck} holds the system below what the "
                f"application requires. This is a violation, not only a "
                f"bottleneck.", 62):
            out.append(f"      {line}")
    else:
        out.append("      No required throughput is declared, so there is")
        out.append("      nothing to be met or violated.")
    return out


def recommend_performance(b: PerformanceBottleneck) -> Optional[str]:
    """Only when the requirement is violated.

    A design meeting its requirement has no observed limit to be tied to,
    and naming a change anyway is the tool preferring an architecture.
    """
    if not b.violated:
        return None
    return (f"Increase {b.bottleneck} throughput, or reduce the work "
            f"assigned to it.")


def render_performance_recommendation(b: PerformanceBottleneck
                                      ) -> List[str]:
    from .visual.text import wrap_text

    out = ["PERFORMANCE RECOMMENDATION", ""]
    rec = recommend_performance(b)
    if rec is None:
        out.append("  No performance change is recommended.")
        out.append("")
        if b.bottleneck != NOT_ESTABLISHED:
            out.append(f"      {b.bottleneck} would bind first if demand "
                       f"increases.")
            out.append("      A fact about the current design, not a "
                       "change to make.")
        return out

    out.append("  Change")
    for line in wrap_text(rec, 62):
        out.append(f"      {line}")
    out.append(f"  Target                       {b.bottleneck}")
    out.append("")
    out.append(f"  Expected improvement         {NOT_ESTABLISHED}")
    for line in wrap_text(
            "How much a change buys needs a counterfactual, and the ones "
            "this model computes run through an arbitration rule whose "
            "physical realism is not established - MEM-ARB-001.", 62):
        out.append(f"      {line}")
    return out
