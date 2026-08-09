"""
ppact.power - three power figures, over three different observation windows

WHY THREE
=========
`System power (W)` was one number doing two jobs and answering neither
question cleanly. It is

    energy_j / latency_s

which is the average over the interval a job is ACTUALLY RUNNING. At a
target rate of 60 inf/s and a latency of 4.857 ms, a job runs for 4.857 ms
of every 16.667 ms and the machine idles for the rest. The engine's figure
does not include the idle.

That is not a defect - it is a well-defined quantity - but it is not what a
thermal budget compares against, and calling it "system power" invited the
comparison.

    active-window average    3.643 W    while a job is running
    steady-state average     1.683 W    running continuously at the target
    peak                     NOT ESTABLISHED

THE ARITHMETIC THAT IS EASY TO GET WRONG
----------------------------------------
Scaling the active-window figure by duty cycle:

    3.643 x 4.857 / 16.667 = 1.062 W

is WRONG. It assumes every watt stops during the idle gap, including
leakage. Static power does not stop. The correct form separates them:

    static baseline   = static energy per job / latency      0.877 W
    dynamic average   = dynamic energy per job x rate        0.806 W
    steady-state      = sum                                  1.683 W

The naive figure understates by 37%, and it understates most for the
designs that idle most - the ones a reader is most likely to call
efficient.

PEAK IS NOT THE ACTIVE-WINDOW AVERAGE
-------------------------------------
Peak needs a moment when every block is drawing at once, which needs a
concurrency profile the model does not have. The active-window average is
an average over a window; using it as a peak would understate the supply a
design needs.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

NOT_ESTABLISHED = "NOT ESTABLISHED"

ACTIVE_WINDOW = "active-window average"
STEADY_STATE = "steady-state average"


@dataclass(frozen=True)
class PowerView:
    """The three figures, each with the window it is averaged over."""

    # What the engine already computes.
    active_window_w: float
    latency_ms: float

    # Steady state, at the delivered rate.
    steady_state_w: Optional[float]
    static_baseline_w: Optional[float]
    dynamic_average_w: Optional[float]
    delivered_rate: Optional[float]

    # Energy, unchanged by any of this.
    energy_per_job_mj: float
    dynamic_energy_mj: float
    static_energy_mj: float

    # Conditions the figures are only meaningful under.
    workload: str
    memory_config: str
    preprocessing: str

    # Budget: deliberately unattached. See below.
    declared_budget_w: Optional[float]

    peak_w: str = NOT_ESTABLISHED
    budget_basis: str = NOT_ESTABLISHED


def build_power_view(analysis) -> PowerView:
    """Both averages, from energy figures the engine already separates.

    The steady-state figure is NOT the active-window figure scaled by duty
    cycle: that treats leakage as though it stopped between jobs.
    """
    from .application import APPLICATION_LIBRARY

    app = APPLICATION_LIBRARY[analysis.app_key]
    m = analysis.current_result.metrics
    cfg = analysis.current_config

    active = float(m.get("System power (W)", 0.0))
    latency_ms = float(m.get("Latency (ms)", 0.0))
    rate = m.get("Delivered throughput (inf/s)")
    energy = float(m.get("Energy per inference (mJ)", 0.0))
    dyn = m.get("Dynamic energy per inference (mJ)")
    sta = m.get("Static energy per inference (mJ)")

    steady = static_w = dyn_w = None
    if (rate and latency_ms > 0 and dyn is not None
            and sta is not None):
        # Static power is charged over the WHOLE interval, because leakage
        # does not stop between jobs. Dynamic energy is charged per job.
        static_w = float(sta) / latency_ms
        dyn_w = float(dyn) * float(rate) / 1000.0
        steady = static_w + dyn_w

    return PowerView(
        active_window_w=active,
        latency_ms=latency_ms,
        steady_state_w=steady,
        static_baseline_w=static_w,
        dynamic_average_w=dyn_w,
        delivered_rate=float(rate) if rate else None,
        energy_per_job_mj=energy,
        dynamic_energy_mj=float(dyn) if dyn is not None else 0.0,
        static_energy_mj=float(sta) if sta is not None else 0.0,
        workload=analysis.app_name,
        memory_config=f"{cfg.memory} x{cfg.memory_devices}",
        preprocessing=cfg.preprocessing_mode,
        declared_budget_w=getattr(app, "power_budget_w", None))


@dataclass(frozen=True)
class PowerAnalysis:
    """The chain, on the power axis, as far as it can go.

    Breakdown, constraint, bottleneck and recommendation - the same four
    Area and Cost have. Three of them stop early here, and the screen says
    where rather than omitting the row.
    """
    view: PowerView
    breakdown: str
    constraint: str
    bottleneck: str
    recommendation: str
    blocked_on: str


def analyse_power(view: PowerView) -> PowerAnalysis:
    """No constraint is computed. The budget's basis is not established,
    and comparing across bases produces a number that means nothing."""
    from .power_basis import comparable, ACTIVE_WINDOW, BUDGET_BASIS

    ok, why = comparable(ACTIVE_WINDOW, BUDGET_BASIS)
    return PowerAnalysis(
        view=view,
        breakdown=NOT_ESTABLISHED,
        constraint=(NOT_ESTABLISHED if not ok else "computed"),
        bottleneck=NOT_ESTABLISHED,
        recommendation=NOT_ESTABLISHED,
        blocked_on=why or "")


def render_power_analysis(a: PowerAnalysis) -> List[str]:
    """The four stages, and where each one stops."""
    from .visual.text import wrap_text

    out = ["POWER ANALYSIS", ""]
    for line in wrap_text(
            "The same chain as Area and Cost. Three of its four stages "
            "stop early on this axis, and each says where.", 66):
        out.append(f"  {line}")
    out.append("")

    out.append(f"  BREAKDOWN                   {a.breakdown}")
    for line in wrap_text(
            "Active-state powers exist per block and do not sum to any "
            "system average - CPU 3.200 + memory 3.881 + compute 0.961 + "
            "static 0.877 gives 8.919 W against a system figure of 3.643. "
            "They are reference values, not a decomposition.", 60):
        out.append(f"      {line}")
    out.append("")

    out.append(f"  CONSTRAINT                  {a.constraint}")
    if a.blocked_on:
        out.append("      Reason")
        for line in wrap_text(a.blocked_on, 58):
            out.append(f"          {line}")
    for line in wrap_text(
            "The library declares 120 W and does not say over which "
            "window. Comparing a 3.643 W active-window figure against it "
            "would produce a number and establish nothing - PW-Q1.", 60):
        out.append(f"      {line}")
    out.append("")

    out.append(f"  BOTTLENECK                  {a.bottleneck}")
    out.append("      Needs the breakdown above.")
    out.append("")
    out.append(f"  RECOMMENDATION              {a.recommendation}")
    out.append("      Needs a violated constraint, and there is no "
               "constraint.")
    out.append("")
    for line in wrap_text(
            "This is what the chain looks like on an axis whose "
            "measurement basis is open. The stages are present and "
            "empty, which is the honest shape - an axis with three rows "
            "missing would read as an axis with three fewer questions.",
            66):
        out.append(f"  {line}")
    return out


def render_power_view(view: PowerView) -> List[str]:
    from .visual.text import wrap_text

    out = ["SYSTEM POWER", ""]
    for line in wrap_text(
            "Three figures over three windows. A power number without its "
            "observation window is not comparable to anything.", 66):
        out.append(f"  {line}")
    out.append("")

    out.append(f"  Steady-state average        "
               f"{view.steady_state_w:8.3f} W"
               if view.steady_state_w is not None
               else "  Steady-state average        NOT COMPUTED")
    if view.steady_state_w is not None:
        out.append(f"      running continuously at "
                   f"{view.delivered_rate:.0f} inf/s")
        out.append(f"      static baseline         "
                   f"{view.static_baseline_w:8.3f} W")
        out.append(f"      dynamic average         "
                   f"{view.dynamic_average_w:8.3f} W")
    out.append("")
    out.append(f"  Active-window average       "
               f"{view.active_window_w:8.3f} W")
    out.append(f"      while a job is running, over "
               f"{view.latency_ms:.3f} ms")
    out.append("")
    out.append(f"  Peak power                  {view.peak_w}")
    for line in wrap_text(
            "A peak needs a moment when every block draws at once, which "
            "needs a concurrency profile this model does not carry. The "
            "active-window figure is an average over a window and is not "
            "a substitute.", 60):
        out.append(f"      {line}")
    out.append("")

    # The naive scaling, named so it is not rediscovered.
    if view.steady_state_w is not None and view.delivered_rate:
        naive = (view.active_window_w * view.latency_ms
                 * view.delivered_rate / 1000.0)
        out.append(f"  Not this:  active x duty cycle = {naive:.3f} W")
        for line in wrap_text(
                "Scaling the active-window figure by duty cycle assumes "
                "every watt stops in the idle gap, including leakage. It "
                "understates most for the designs that idle most.", 60):
            out.append(f"      {line}")
        out.append("")

    out.append(f"  Energy per job              "
               f"{view.energy_per_job_mj:8.3f} mJ")
    out.append(f"      dynamic {view.dynamic_energy_mj:.3f}  "
               f"static {view.static_energy_mj:.3f}")
    out.append("      Unaffected by which window the power is averaged "
               "over.")
    out.append("")

    # THE BUDGET IS NOT ATTACHED. Which figure it constrains is a
    # statement about what the budget means, and the library does not say.
    out.append("  BUDGET")
    if view.declared_budget_w is None:
        out.append("      Declared power budget   NOT ESTABLISHED")
    else:
        out.append(f"      Declared power budget   "
                   f"{view.declared_budget_w:8.3f} W")
    out.append(f"      Budget basis            {view.budget_basis}")
    for line in wrap_text(
            "The library does not say whether this budget is a sustained "
            "thermal limit or an instantaneous supply limit. Those "
            "constrain different figures above, so it is compared against "
            "neither until the library says which.", 60):
        out.append(f"      {line}")
    out.append("")

    out.append("  CONDITIONS")
    out.append(f"      Workload                {view.workload}")
    out.append(f"      Delivered rate          "
               f"{view.delivered_rate:.0f} inf/s"
               if view.delivered_rate else
               "      Delivered rate          NOT ESTABLISHED")
    out.append(f"      Memory configuration    {view.memory_config}")
    out.append(f"      Preprocessing           {view.preprocessing}")
    out.append(f"      Power model             activity-weighted "
               f"analytical estimate")
    for line in wrap_text(
            "The same design at a different rate has a different "
            "steady-state average. These figures travel with their "
            "conditions or not at all.", 60):
        out.append(f"      {line}")
    return out
