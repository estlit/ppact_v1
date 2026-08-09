"""
ppact.runtime - Phase 3: many jobs, not one

Phases 1 and 2 describe a single inference. That is enough to compare designs
and not enough to say how a system behaves, because the two questions a
designer actually asks - what is my throughput, and what is each block doing
with its time - only have answers once jobs arrive continuously.

    total time = first single-job latency + (jobs - 1) x pipeline interval
    interval   = the slowest stage

Three consequences follow, and none of them exist in a single-job model:

    Throughput is set by the SLOWEST STAGE, not by the latency. A design can
    have poor latency and excellent throughput, or the reverse, and a student
    who has only seen latency will assume they move together.

    Utilisation becomes measurable. Busy time divided by an observation
    interval is a real fraction; busy time divided by one job's latency, which
    is what Phase 2 could offer, is not.

    Idle becomes definable. In a single job there is no way to tell idle from
    waiting for work that has not arrived. Over a run there is.

WHAT THIS IS NOT
----------------
Not a cycle-accurate or queueing simulator. There are no request queues, no
arbitration and no contention between stages beyond the interval. Those need a
model this does not have, and the terms that depend on them - bottleneck,
stall, backpressure - are deliberately absent from the output.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .application import APPLICATION_LIBRARY
from .system import SystemConfig, SystemResult, evaluate_system

# The stages a job passes through. Memory is not a stage: its transfers happen
# inside the accelerator's turn and are reported as occupancy, not as a step.
STAGES = ("ISP", "CPU", "Accelerator")

# Memory is a station like the others. It was left out at first, and the
# consequence was that changing LPDDR for HBM moved the latency but not the
# throughput - the transfer occupancy never reached the interval. A memory that
# cannot keep up limits a pipeline exactly as a slow engine does.
_STAGE_METRIC = {
    "ISP": "Stage ISP (ms)",
    "CPU": "Stage CPU (ms)",
    "Accelerator": "Stage accelerator (ms)",
    "Memory": "Stage memory (ms)",
}

# With two engines the accelerator is two stations, not one. A pipeline lets
# the first start the next job while the second finishes this one, so the
# INTERVAL is a max over both even in sequential mode - it is the single-job
# LATENCY that adds them. Conflating the two would make a sequential pair look
# half as fast as it is at steady state.
_STAGE_METRIC_DUAL = {
    "ISP": "Stage ISP (ms)",
    "CPU": "Stage CPU (ms)",
    "Accelerator 1": "Stage accelerator 1 (ms)",
    "Accelerator 2": "Stage accelerator 2 (ms)",
    "Memory": "Stage memory (ms)",
}


@dataclass
class ModuleState:
    name: str
    active_ms: float          # doing work
    wait_ms: float            # blocked on another module within a job
    idle_ms: float            # no work assigned
    utilisation_pct: float
    power_w: float = 0.0

    @property
    def busy_pct(self) -> float:
        total = self.active_ms + self.wait_ms + self.idle_ms
        return (self.active_ms + self.wait_ms) / total * 100.0 if total else 0.0


@dataclass
class RuntimeResult:
    base: SystemResult
    duration_s: float
    jobs: int
    first_latency_ms: float
    interval_ms: float
    fill_ms: float
    steady_ms: float
    drain_ms: float
    total_time_ms: float
    throughput: float
    limiting_stage: str
    modules: Dict[str, ModuleState] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)

    @property
    def app(self):
        return self.base.app


def result_mode(config) -> str:
    """Execution mode of a config, defaulting to single."""
    return (config.execution_mode if getattr(config, "secondary_compute", None)
            else "single")


def simulate(app_key: str, config: SystemConfig, duration_s: float = 60.0,
             jobs: Optional[int] = None) -> RuntimeResult:
    """Run a workload for a fixed wall-clock duration.

    `jobs` overrides the arrival rate when a student wants a fixed count
    instead of a fixed time.
    """
    app = APPLICATION_LIBRARY[app_key]
    base = evaluate_system(app, config)
    m = base.metrics

    latency_ms = m["Latency (ms)"]
    dual = m.get("Secondary die area (mm2)", 0.0) > 0
    table = _STAGE_METRIC_DUAL if dual else _STAGE_METRIC
    stages = {name: m[key] for name, key in table.items()}
    limiting_stage = max(stages, key=lambda k: stages[k])
    interval_ms = max(stages.values())

    # The observation window is fixed. Work arrives at the application's rate,
    # and the system either keeps up or does not - which is the finding, not a
    # reason to stretch the clock. Sizing the window to the work instead would
    # hide exactly the case worth seeing: a design that cannot meet its frame
    # rate would silently be reported as if it had.
    window_ms = duration_s * 1e3
    fill_ms = max(0.0, latency_ms - interval_ms)
    capacity = int((window_ms - fill_ms) / interval_ms) if interval_ms > 0 else 0
    demand = max(1, int(round(app.target_inferences_per_s * duration_s)))
    fixed_jobs = jobs is not None
    if jobs is None:
        jobs = max(0, min(demand, capacity))
    keeps_up = jobs >= demand

    steady_ms = interval_ms * jobs
    drain_ms = 0.0                       # the last job's tail sits inside fill
    if fixed_jobs:
        # A FIXED COUNT finishes when the last job finishes, not when the
        # clock runs out. Dividing by the window gave one job in sixty
        # seconds a throughput of 0.02 per second, which is a statement
        # about the window and not about the design.
        #
        # The first job pays the full latency; each one after it arrives an
        # interval later. Fill is what the pipeline costs before it is full,
        # and it is paid ONCE - a thousand jobs pay it once, not a thousand
        # times, which is the whole reason a long run converges on the
        # capacity.
        total_time_ms = fill_ms + interval_ms * jobs
        throughput = jobs / (total_time_ms / 1e3) if total_time_ms > 0 else 0.0
    else:
        total_time_ms = window_ms
        throughput = jobs / duration_s if duration_s > 0 else 0.0

    # --- module states -------------------------------------------------------
    modules: Dict[str, ModuleState] = {}

    def add(name, active_per_job, wait_per_job, power):
        """Occupancy of one module across the window.

        Active time sums cleanly: a module doing work for a job is not doing
        work for another. Waiting does NOT sum, because several jobs are in
        flight and a module blocked on one of them is simultaneously blocked on
        the others - adding the per-job figures counts the same wall-clock time
        more than once, and can push the total past the window. It is therefore
        capped at whatever the window has left.
        """
        active = min(active_per_job * jobs, total_time_ms)
        wait = min(wait_per_job * jobs, max(0.0, total_time_ms - active))
        idle = max(0.0, total_time_ms - active - wait)
        modules[name] = ModuleState(name, active, wait, idle,
                                    active / total_time_ms * 100.0 if total_time_ms else 0.0,
                                    power)

    r_config = config
    add("CPU", m["Stage CPU (ms)"],
        max(0.0, latency_ms - m["Stage CPU (ms)"]),
        m["  cpu share (%)"] / 100.0 * m["System power (W)"])
    if m["Stage ISP (ms)"] > 0:
        add("ISP", m["Stage ISP (ms)"], 0.0, 0.0)
    if dual:
        # Two engines, reported separately: a second accelerator idle for most
        # of the run is a different design position from one that is busy, and
        # a combined figure hides which of the two was bought for nothing.
        #
        # Waiting is split by cause. Memory wait is time spent without operands;
        # dependency wait is time spent with operands but nothing to do yet,
        # which only happens to the second engine in a sequential pair.
        a1 = m["Stage accelerator 1 (ms)"]
        a2 = m["Stage accelerator 2 (ms)"]
        total_active = max(a1 + a2, 1e-12)
        mem_wait = m["Compute data-wait (ms)"]
        dep_wait = a1 if result_mode(r_config) == "sequential" else 0.0
        # Active time must be the station's occupancy, not a different sum -
        # a module whose busy time disagrees with the stage that produced it
        # cannot be reconciled with any pipeline.
        add("Accelerator 1", a1, mem_wait * a1 / total_active, m["Compute power (W)"])
        add("Accelerator 2", a2, mem_wait * a2 / total_active + dep_wait, 0.0)
    else:
        add("Accelerator", m["Stage accelerator (ms)"],
            m["Compute data-wait (ms)"], m["Compute power (W)"])
    add("Memory", m["Stage memory (ms)"], 0.0, m["Memory power (W)"])

    # --- energy over the run --------------------------------------------------
    # Dynamic energy is per job; static power runs for the whole observation
    # window. Charging static per job would overcount it by exactly the amount
    # the pipeline overlaps.
    dynamic_j = m["Dynamic energy per inference (mJ)"] / 1e3 * jobs
    static_j = m["Static power (W)"] * (total_time_ms / 1e3)
    total_energy_j = dynamic_j + static_j
    average_power = total_energy_j / (total_time_ms / 1e3) if total_time_ms > 0 else 0.0
    # Every module drawing its working power at the same instant. Built from
    # each module's ACTIVE power rather than its per-job average, because
    # summing averages gave a "peak" below the run average once more than one
    # job was in flight.
    peak_power = (m["CPU active power (W)"] + m["Accelerator active power (W)"]
                  + m["Memory active power (W)"] + m["Static power (W)"])
    peak_power = max(peak_power, average_power)

    metrics = {
        "Simulation time (s)": duration_s,
        "Jobs demanded": float(demand),
        "Jobs processed": float(jobs),
        "Capacity (jobs)": float(capacity),
        "Keeps up": 1.0 if keeps_up else 0.0,
        "Average latency (ms)": latency_ms,
        "Pipeline interval (ms)": interval_ms,
        "Throughput (jobs/s)": throughput,
        "Fill time (ms)": fill_ms,
        "Steady time (ms)": steady_ms,
        "Total energy (J)": total_energy_j,
        "Average power (W)": average_power,
        "Peak power (W)": peak_power,
        "Energy per job (mJ)": total_energy_j / jobs * 1e3 if jobs else 0.0,
        "Total DRAM traffic (GB)": m["DRAM traffic (MB)"] * jobs / 1e3,
        "Total DRAM read (GB)": m["DRAM read (MB)"] * jobs / 1e3,
        "Total DRAM write (GB)": m["DRAM write (MB)"] * jobs / 1e3,
        "Memory bandwidth utilisation (%)": (
            m["DRAM traffic (MB)"] * jobs / 1e3
            / max(m["Effective bandwidth (GB/s)"] * duration_s, 1e-12) * 100.0),
        "Concurrent bandwidth demand (GB/s)": (
            m["DRAM traffic (MB)"] / 1e3 / max(interval_ms / 1e3, 1e-12)),
        "Execution mode": 0.0,
        "Thermal margin (%)": m["Thermal margin (%)"],
        "Total silicon (mm2)": m["Total silicon (mm2)"],
        "System cost (USD)": m["System cost (USD)"],
    }
    return RuntimeResult(base, duration_s, jobs, latency_ms, interval_ms,
                         fill_ms, steady_ms, drain_ms, total_time_ms,
                         throughput, limiting_stage, modules, metrics)


# ==============================================================================
# One-screen dashboard
# ==============================================================================

def _bar(pct: float, width: int = 24) -> str:
    from .visual import render_bar
    return render_bar(max(0.0, min(100.0, pct)), 100.0, width)


def _split_bar(active: float, wait: float, idle: float, width: int = 24) -> str:
    """Three states in one bar: work, blocked, nothing to do."""
    total = active + wait + idle
    # States are named, not drawn: the shared layer owns which pattern
    # "blocked" gets, so it cannot differ between two screens.
    from .visual import render_state_bar
    return render_state_bar({"work": active, "blocked": wait}, total, width)


def print_dashboard(r: RuntimeResult, show_scores: bool = True) -> None:
    """Everything a student needs on one screen, and nothing else.

    Deliberately plain. A dashboard that needs explaining defeats its purpose,
    and the numbers here are the ones that change when a design changes.
    """
    app = r.app
    line = "=" * 66
    print(f"\n{line}")
    print(" SYSTEM RUNTIME DASHBOARD")
    print(line)
    print(f"  application      {app.name}")
    print(f"  configuration    {r.base.label}")
    demand = int(r.metrics["Jobs demanded"])
    print(f"  observed over    {r.metrics['Simulation time (s)']:.0f} s")
    print(f"  jobs             {r.jobs:,} processed of {demand:,} demanded"
          + ("" if r.metrics["Keeps up"] else "   <- cannot keep up"))

    print(f"\n  -- module state --------------------------------------------")
    print(f"  {'':<13s}{'work':>6s}{'blocked':>9s}{'idle':>7s}   "
          f"{'# work  ~ blocked  . idle':<26s}")
    for name in ("ISP", "CPU", "Memory", "Accelerator",
                 "Accelerator 1", "Accelerator 2"):
        s = r.modules.get(name)
        if s is None:
            continue
        total = s.active_ms + s.wait_ms + s.idle_ms
        if total <= 0:
            continue
        print(f"  {name:<13s}{s.active_ms / total * 100:>5.0f}%"
              f"{s.wait_ms / total * 100:>8.0f}%{s.idle_ms / total * 100:>6.0f}%   "
              f"{_split_bar(s.active_ms, s.wait_ms, s.idle_ms)}")

    print(f"\n  -- rate ----------------------------------------------------")
    print(f"  latency          {r.first_latency_ms:8.2f} ms   one job, start to finish")
    print(f"  interval         {r.interval_ms:8.2f} ms   set by {r.limiting_stage}")
    print(f"  throughput       {r.throughput:8.1f} /s   "
          f"(needed {r.app.target_inferences_per_s:g})")
    if r.interval_ms < r.first_latency_ms - 1e-9:
        print(f"  ({r.first_latency_ms / r.interval_ms:.1f} jobs are in flight at once, "
              f"which is why throughput")
        print(f"   exceeds one over latency - the two are not the same number)")

    print(f"\n  -- energy and heat -----------------------------------------")
    print(f"  average power    {r.metrics['Average power (W)']:8.2f} W")
    print(f"  peak power       {r.metrics['Peak power (W)']:8.2f} W   "
          f"all modules drawing at once")
    print(f"  total energy     {r.metrics['Total energy (J)']:8.1f} J")
    print(f"  per job          {r.metrics['Energy per job (mJ)']:8.2f} mJ")
    tm = r.metrics["Thermal margin (%)"]
    print(f"  thermal margin   {tm:8.1f} %"
          + ("   cooling assumption exceeded" if tm < 0 else ""))
    cm = r.base.metrics["  compute thermal margin (%)"]
    mm = r.base.metrics["  memory thermal margin (%)"]
    print(f"    compute        {cm:8.1f} %")
    print(f"    memory         {mm:8.1f} %"
          + ("   <- the memory alone is over budget" if mm < 0 <= cm else ""))
    print("  (a margin, not a temperature: a negative figure means the assumed")
    print("   cooling class cannot carry this power density, not that a")
    print("   junction temperature was computed)")

    print(f"\n  -- memory --------------------------------------------------")
    print(f"  read             {r.metrics['Total DRAM read (GB)']:8.1f} GB")
    print(f"  write            {r.metrics['Total DRAM write (GB)']:8.1f} GB")
    print(f"  bandwidth used   {r.metrics['Memory bandwidth utilisation (%)']:8.1f} %"
          f"   of what the memory can deliver")
    print(f"  demand at rate   {r.metrics['Concurrent bandwidth demand (GB/s)']:8.1f} GB/s"
          f" during a pipeline interval")

    print(f"\n  -- build ---------------------------------------------------")
    print(f"  silicon          {r.metrics['Total silicon (mm2)']:8.1f} mm2")
    print(f"  cost             {r.metrics['System cost (USD)']:8.2f} USD")
    print(f"  DRAM traffic     {r.metrics['Total DRAM traffic (GB)']:8.1f} GB "
          f"over the run")

    if show_scores:
        from .game import score_design, AXES, stars
        s = score_design(r.base)
        print(f"\n  -- PPACT ---------------------------------------------------")
        for axis in AXES:
            print(f"  {axis:<13s}{s[axis]:>5.0f}  {_bar(s[axis])}  {stars(s[axis])}")
        print("\n  No overall figure here on purpose: a single score would be an")
        print("  answer, and which of these matters is the student's decision.")
    print(line)


def compare_runs(results: List[RuntimeResult]) -> None:
    """Side by side, one line per design."""
    print("\n" + "=" * 78)
    print(" RUNTIME COMPARISON")
    print("=" * 78)
    w = max(len(r.base.label) for r in results) + 2
    head = (f"  {'configuration':<{w}s}{'latency':>10s}{'interval':>10s}"
            f"{'jobs/s':>9s}{'avg W':>8s}{'energy J':>10s}{'limited by':>14s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for r in results:
        print(f"  {r.base.label:<{w}s}{r.first_latency_ms:>10.2f}"
              f"{r.interval_ms:>10.2f}{r.throughput:>9.1f}"
              f"{r.metrics['Average power (W)']:>8.2f}"
              f"{r.metrics['Total energy (J)']:>10.1f}{r.limiting_stage:>14s}")


# ==============================================================================
# Explaining a latency change
# ==============================================================================

# The terms a latency difference can be made of. If they do not add up to the
# observed change, something is happening that the model is not naming - and an
# unexplained residual is a defect, not a rounding artefact.
LINE = "=" * 66

_DELTA_TERMS = [
    ("CPU work", "CPU active (ms)"),
    ("Preprocessing exposed", "Preprocess exposed (ms)"),
    ("Offload overhead", "Offload overhead (ms)"),
    ("Hand-off", "Handoff (ms)"),
    ("ISP exposed", "ISP exposed (ms)"),
]


def explain_latency_delta(before, after, label_before="baseline",
                          label_after="proposed") -> dict:
    """Break a latency change into named terms, and name the remainder.

    A design that is 0.011 ms slower for no stated reason has not been
    understood. This decomposition exists so that the reason has to be
    somewhere in the list, or the list is wrong.
    """
    b = before.metrics if hasattr(before, "metrics") else before
    a = after.metrics if hasattr(after, "metrics") else after

    def core(m):
        return (m["Compute time (ms)"] + m["Memory time (ms)"]
                - m["Hidden transfer (ms)"])

    parts = {name: a[key] - b[key] for name, key in _DELTA_TERMS}
    parts["Accelerator core"] = core(a) - core(b)
    total = a["Latency (ms)"] - b["Latency (ms)"]
    parts["Unexplained"] = total - sum(parts.values())

    print(f"\n{LINE}")
    print(f" LATENCY CHANGE: {label_before} -> {label_after}")
    print(LINE)
    for name, v in parts.items():
        if abs(v) < 1e-9 and name != "Unexplained":
            continue
        marker = "  <- unaccounted for" if name == "Unexplained" and abs(v) > 1e-6 else ""
        print(f"  {name:<26s}{v:>+10.4f} ms{marker}")
    print("  " + "-" * 40)
    print(f"  {'Net change':<26s}{total:>+10.4f} ms")
    if abs(parts["Unexplained"]) > 1e-6:
        print("\n  The terms do not add up. Treat the difference as a defect in")
        print("  the model rather than as noise.")
    return parts


def print_work_split_analysis(app_key, single_config, dual_config,
                              duration_s: float = 60.0) -> None:
    """Why splitting the work helped, or did not - with each term's standing.

    The dual design is evaluated TWICE, once with the contention estimate
    switched off, so that the model-derived part of the answer and the
    assumption-dependent part can be shown separately. Collapsing them into one
    "memory" line would let a coefficient masquerade as a finding.
    """
    from . import system as _sys
    from .application import APPLICATION_LIBRARY as _APPS
    from .system import evaluate_system as _ev

    app = _APPS[app_key]
    a = _ev(app, single_config).metrics
    saved = _sys.DUAL_MEMORY_CONTENTION
    _sys.DUAL_MEMORY_CONTENTION = 0.0
    try:
        ideal = _ev(app, dual_config).metrics
    finally:
        _sys.DUAL_MEMORY_CONTENTION = saved
    b = _ev(app, dual_config).metrics

    split = b["Work split (MAC fraction)"]
    print(f"\n{LINE}")
    print(" DUAL-ACCELERATOR LATENCY ANALYSIS")
    print(LINE)
    print(f"  primary accelerator   {(1 - split) * 100:5.0f}%")
    print(f"  secondary accelerator {split * 100:5.0f}%\n")

    compute_gain = ideal["Compute time (ms)"] - a["Compute time (ms)"]
    handoff = ideal["Handoff (ms)"] - a["Handoff (ms)"]
    pre_gain = ideal["Preprocess exposed (ms)"] - a["Preprocess exposed (ms)"]
    # Everything the roofline does with a shorter compute term and an unchanged
    # transfer term: the gain the memory refuses to deliver.
    saturation = ((ideal["Latency (ms)"] - a["Latency (ms)"])
                  - compute_gain - handoff - pre_gain)
    controller = b["Latency (ms)"] - ideal["Latency (ms)"]

    # Both endpoints are simulator outputs. They were once tagged "measured",
    # which is the exact confusion the evidence levels exist to prevent.
    rows = [
        ("single-accelerator latency", a["Latency (ms)"], "", "endpoint"),
        ("ideal parallel compute gain", compute_gain, "model-derived", "term"),
        ("shared-bandwidth saturation", saturation, "model-derived", "term"),
        ("preprocessing gain", pre_gain, "model-derived", "term"),
        ("hand-off and synchronisation", handoff, "assumption", "term"),
        ("controller contention estimate", controller, "assumption", "term"),
        ("dual-accelerator latency", b["Latency (ms)"], "", "endpoint"),
    ]
    for label, v, tag, kind in rows:
        if kind == "term" and abs(v) < 1e-9:
            continue
        num = f"{v:>+9.3f}" if kind == "term" else f"{v:>9.3f}"
        print(f"  {label:<32s}{num} ms   {tag}")
    print("  " + "-" * 56)
    print(f"  {'net latency change':<32s}"
          f"{b['Latency (ms)'] - a['Latency (ms)']:>+9.3f} ms")

    print("\n  model-derived  follows from the arithmetic; no coefficient behind it")
    print("  assumption     rests on a chosen coefficient (ppact.coefficients)")
    if controller > 0 and (b["Latency (ms)"] > a["Latency (ms)"] >= ideal["Latency (ms)"]):
        print("\n  NOTE: this design is slower than a single accelerator ONLY")
        print("  because of the contention estimate. Without it the split still")
        print(f"  wins, by {a['Latency (ms)'] - ideal['Latency (ms)']:.3f} ms. "
              f"Treat the reversal as")
        print("  conditional on that coefficient rather than as a finding.")


def print_secondary_activity(result) -> None:
    """What the second accelerator did, and how much of it mattered."""
    m = result.metrics if hasattr(result, "metrics") else result
    if m.get("Secondary die area (mm2)", 0.0) <= 0:
        print("\n  (single accelerator - nothing to report)")
        return
    print(f"\n{LINE}")
    print(" SECONDARY ACCELERATOR ACTIVITY")
    print(LINE)
    print(f"  preprocessing        {m['Secondary preprocess (ms)']:8.3f} ms")
    print(f"  inference share      {m['Secondary inference (ms)']:8.3f} ms")
    print(f"  total active         {m['Secondary active (ms)']:8.3f} ms")
    print(f"  hidden by primary    {m['Secondary hidden (ms)']:8.3f} ms")
    print(f"  exposed to latency   {m['Secondary exposed (ms)']:8.3f} ms")
    print(f"  hand-off             {m['Handoff (ms)']:8.3f} ms")
    print(f"\n  work split           {m['Work split (MAC fraction)']:8.2f} "
          f"of one job's arithmetic")
    print(f"  alternative share    {m['Alternative share (job fraction)']:8.2f} "
          f"of the jobs")
    print("\n  One array cannot preprocess and infer at the same instant, so the")
    print("  two are summed. Overlapping them would need two engines inside the")
    print("  secondary, which this model does not have.")


# ==============================================================================
# Memory exploration
# ==============================================================================

def explore_memory(app_key: str, config: SystemConfig,
                   options=(("LPDDR5", 2), ("LPDDR5", 4), ("GDDR6", 4),
                            ("HBM3E", 1), ("HBM3E", 2)),
                   duration_s: float = 60.0) -> None:
    """The same design on different memory, with the accelerators watched.

    The question a student should leave with is not "which memory is fastest"
    but "were my accelerators waiting". A wide memory is worth its cost when
    the engines were idle for want of operands and worth nothing when they
    were not, and those two situations look identical in a throughput number
    alone.
    """
    import dataclasses
    from .application import APPLICATION_LIBRARY as _A
    app = _A[app_key]
    print(f"\n{'=' * 92}")
    print(f" MEMORY EXPLORATION - {app.name}")
    print(f"{'=' * 92}")
    head = (f"  {'memory':<12s}{'A1 busy':>9s}{'A2 busy':>9s}{'mem wait':>10s}"
            f"{'jobs/s':>9s}{'BW used':>9s}{'mJ/job':>9s}{'cost':>9s}"
            f"{'margin':>9s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for mem, n in options:
        cfg = dataclasses.replace(config, memory=mem, memory_devices=n)
        r = simulate(app_key, cfg, duration_s=duration_s)
        m = r.metrics
        a1 = r.modules.get("Accelerator 1") or r.modules.get("Accelerator")
        a2 = r.modules.get("Accelerator 2")
        total = a1.active_ms + a1.wait_ms + a1.idle_ms
        wait_pct = a1.wait_ms / total * 100.0 if total else 0.0
        print(f"  {mem + ' x' + str(n):<12s}{a1.utilisation_pct:>8.1f}%"
              f"{(a2.utilisation_pct if a2 else 0.0):>8.1f}%"
              f"{wait_pct:>9.1f}%{r.throughput:>9.1f}"
              f"{m['Memory bandwidth utilisation (%)']:>8.1f}%"
              f"{m['Energy per job (mJ)']:>9.2f}{m['System cost (USD)']:>9.2f}"
              f"{m['Thermal margin (%)']:>8.1f}%"
              + ("  cooling exceeded" if m['Thermal margin (%)'] < 0 else ""))
    print("\n  Read the wait column first. Memory that removes a wait you did not")
    print("  have buys nothing but cost, area and heat.")


# ==============================================================================
# LLM traffic
# ==============================================================================

def print_llm_traffic(app_key: str, config: SystemConfig) -> None:
    """Where a token's bandwidth goes, and what limits the rate.

    Stated with its conditions. A tokens-per-second figure means nothing on its
    own: it belongs to a precision, a weight size, a context length, a batch
    size and a memory. Quoting one without them invites it to be read as a
    property of the model rather than of the configuration it came from.
    """
    from .application import APPLICATION_LIBRARY as _A
    from .system import evaluate_system as _ev
    app = _A[app_key]
    if app.workload_class != "text":
        print("\n  (not a text workload - no decode traffic to report)")
        return
    m = _ev(app, config).metrics

    print(f"\n{LINE}")
    print(" LLM MEMORY TRAFFIC")
    print(LINE)
    print(f"  model weights        {m['  weight traffic (MB)'] / 1000:8.2f} GB/token")
    print(f"  weight read factor   {m['Weight read factor']:8.2f}"
          f"        estimated")
    print(f"  KV cache traffic     {m['  KV cache traffic (MB)'] / 1000:8.2f} GB/token")
    print(f"  other traffic        {m['  other traffic (MB)'] / 1000:8.2f} GB/token")
    print("  " + "-" * 46)
    print(f"  total traffic        {m['DRAM traffic (MB)'] / 1000:8.2f} GB/token\n")
    print(f"  effective bandwidth  {m['Effective bandwidth (GB/s)'] / 1000:8.2f} TB/s")
    limit = (m["Effective bandwidth (GB/s)"] * 1e9
             / max(m["DRAM traffic (MB)"] * 1e6, 1e-9))
    print(f"  memory-limited rate  {limit:8.1f} token/s")
    print(f"  achieved rate        {m['Throughput (inf/s)']:8.1f} token/s")

    print(f"\n  prefill (the prompt, processed at once)")
    print(f"    compute            {m['Prefill compute (ms)']:8.2f} ms")
    print(f"    memory             {m['Prefill memory (ms)']:8.2f} ms")
    print(f"    time to first token{m['Time to first token (ms)']:8.2f} ms   "
          f"bound by {'memory' if m['Prefill bound by'] else 'compute'}")

    print(f"\n  conditions - the rate above belongs to all of these:")
    print(f"    precision          {app.model}")
    print(f"    weight size        {app.weight_bytes / 1e9:.1f} GB")
    print(f"    context            {app.context_tokens:,.0f} tokens")
    print(f"    prompt             {app.prefill_tokens:,.0f} tokens")
    print(f"    streams            {app.streams} (single-stream decode)")
    print(f"    memory             {config.memory} x{config.memory_devices}")
    print("\n  Change any one of them and the token rate changes. It is not a")
    print("  property of the model.")


# ==============================================================================
# Serving-efficiency band
# ==============================================================================

def serving_band(app_key: str, config) -> None:
    """The same design under a poor, a typical and a good serving stack.

    The coefficient cannot be pinned from public sources - two deployments
    bracket it between roughly a quarter and two thirds of the memory ceiling,
    and neither states the precision that would settle it. Reporting one number
    would hide that the answer depends on software nobody has specified.
    """
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    from . import system as _S

    app = APPLICATION_LIBRARY[app_key]
    if app.workload_class != "text":
        print("\n  (not a text workload - the serving band does not apply)")
        return
    saved = _S.LLM_SINGLE_STREAM_SERVING_EFFICIENCY
    rows = []
    try:
        for name, eff in _S.LLM_SERVING_EFFICIENCY_BAND.items():
            _S.LLM_SINGLE_STREAM_SERVING_EFFICIENCY = eff
            r = evaluate_system(app, config)
            rows.append((name, eff, r.metrics["Throughput (inf/s)"],
                         r.metrics["Latency (ms)"], r.passes,
                         [g for g, ok in r.gate.items() if not ok]))
    finally:
        _S.LLM_SINGLE_STREAM_SERVING_EFFICIENCY = saved

    print(f"\n{LINE}")
    print(" SERVING-STACK BAND")
    print(LINE)
    print(f"  requirement      {app.target_inferences_per_s:g} tokens/s, "
          f"{app.latency_budget_ms:g} ms\n")
    head = (f"  {'serving stack':<16s}{'efficiency':>11s}{'tokens/s':>11s}"
            f"{'latency ms':>12s}   ships")
    print(head); print("  " + "-" * (len(head) - 2))
    for name, eff, tps, lat, ok, bad in rows:
        print(f"  {name:<16s}{eff:>11.2f}{tps:>11.1f}{lat:>12.2f}   "
              + ("yes" if ok else "no  - " + ", ".join(bad)))
    ships = [r for r in rows if r[4]]
    print()
    if len(ships) == len(rows):
        print("  Ships whatever the serving stack does. The requirement is not")
        print("  sensitive to the one coefficient nobody can pin down.")
    elif not ships:
        print("  Does not ship under any serving stack in the band, so the")
        print("  ambiguity in that coefficient is not what is stopping it.")
    else:
        names = ", ".join(r[0] for r in ships)
        print(f"  Ships only under: {names}.")
        print("  The verdict on this design depends on a coefficient bracketed")
        print("  between 0.28 and 0.64 by two published deployments that do not")
        print("  state their precision. That is a finding about the evidence,")
        print("  not about the hardware - and no amount of further reading")
        print("  narrows it. Measurement would.")
    print(LINE)
