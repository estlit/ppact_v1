"""
ppact.innovation - starting points, evidence, and the Innovation Challenge

THREE THINGS, KEPT APART
------------------------
    1. SIMULATOR   facts only. Latency, power, area, cost, thermal,
                   utilisation, and the difference between two designs.
                   Fully automatic, no judgement anywhere in it.

    2. ASSIGNMENT  the student explains. Why change the architecture, and
                   what was traded away. Two questions, written by hand.

    3. GRADING     the instructor awards 0-5. Whether an application is
                   genuinely new, and whether a comparison is fair, are not
                   things a tool can decide.

They were previously one menu entry, which blurred a real distinction: a number
the simulator computed and a judgement someone made were arriving on the same
screen, and a student could reasonably have taken the second for the first.

A student does not start from a blank page either. Choosing an application
produces a STARTING POINT - a plain, working, deliberately unoptimised
system. The exercise is to change it and show what the change did.

That separation is the whole point. An idea is not worth marks; a design change
defended with numbers is. So this module computes the before-and-after, lays
out the comparison against a published platform, and prints the rubric - and
then stops, because deciding whether an application is genuinely new, or
whether a comparison is fair, is a judgement a tool cannot make and should not
pretend to.

TWO KINDS OF WEIGHTING, DELIBERATELY DIFFERENT
----------------------------------------------
Exploration uses the STUDENT's priorities: that is what makes "no right answer"
true, because two people can weigh power and accuracy differently and both be
defensible.

Grading uses the APPLICATION's priorities, fixed here. A mark computed from
weights the candidate chose is not a mark, it is a self-assessment - a student
could score full marks by declaring that the only thing that matters is the
axis their design happens to win.

A NOTE ON COMPARING WITH PRODUCTS
---------------------------------
Published TOPS figures are PEAK, frequently counted with sparsity, and say
nothing about a particular workload. The numbers this simulator produces are
workload-derived. Putting them side by side without saying so would teach a
bad habit, so throughput comparison requires the student to supply a published
BENCHMARK measurement - the tool will not invent one.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .application import APPLICATION_LIBRARY
from .system import SystemConfig, evaluate_system
from .runtime import simulate, RuntimeResult

LINE = "=" * 74


# ==============================================================================
# Grading weights - a property of the application, not of the candidate
# ==============================================================================

GRADING_WEIGHTS: Dict[str, Dict[str, float]] = {
    "drone":              {"Power": 3.0, "Performance": 2.0, "Thermal": 1.5,
                           "Accuracy": 1.0, "Cost": 1.0, "Area": 1.5},
    "autonomous_vehicle": {"Accuracy": 3.0, "Performance": 3.0, "Thermal": 2.0,
                           "Power": 1.0, "Cost": 0.5, "Area": 0.5},
    "industrial_vision":  {"Performance": 3.0, "Accuracy": 2.5, "Cost": 1.5,
                           "Power": 0.5, "Area": 0.5, "Thermal": 1.0},
    "smart_camera":       {"Cost": 3.0, "Power": 2.0, "Area": 2.0,
                           "Accuracy": 1.0, "Performance": 1.0, "Thermal": 1.0},
    "mobile_ai":          {"Power": 2.5, "Cost": 2.0, "Area": 2.0,
                           "Performance": 1.5, "Accuracy": 1.0, "Thermal": 1.0},
    "robot":              {"Performance": 2.0, "Power": 2.0, "Accuracy": 2.0,
                           "Cost": 1.5, "Area": 1.0, "Thermal": 1.5},
    "medical":            {"Accuracy": 4.0, "Performance": 2.0, "Thermal": 1.0,
                           "Cost": 0.5, "Power": 0.5, "Area": 0.5},
    "ai_inference":       {"Performance": 3.0, "Power": 2.0, "Cost": 2.0,
                           "Thermal": 1.0, "Accuracy": 1.0, "Area": 0.5},
    "llm_service":        {"Performance": 3.0, "Cost": 2.0, "Power": 2.0,
                           "Thermal": 1.0, "Accuracy": 1.0, "Area": 0.5},
}

DEFAULT_WEIGHTS = {"Accuracy": 1.0, "Performance": 1.0, "Power": 1.0,
                   "Area": 1.0, "Cost": 1.0, "Thermal": 1.0}


def grading_weights(app_key: str) -> Dict[str, float]:
    return GRADING_WEIGHTS.get(app_key, dict(DEFAULT_WEIGHTS))


# ==============================================================================
# Published reference platforms
# ==============================================================================

@dataclass(frozen=True)
class ReferencePlatform:
    name: str
    category: str
    peak_tops_int8: float
    typical_power_w: float
    memory: str
    memory_bandwidth_gb_s: float
    source: str
    caveat: str = ""

    @property
    def peak_tops_per_watt(self) -> float:
        return self.peak_tops_int8 / self.typical_power_w if self.typical_power_w else 0.0


# Vendor-published headline figures, recorded as such. None of these were
# measured here, and every one of them is a PEAK number under conditions the
# vendor chose.
REFERENCE_PLATFORMS: Dict[str, ReferencePlatform] = {
    "jetson_orin_nano": ReferencePlatform(
        "Jetson Orin Nano 8GB", "Edge module", 40.0, 15.0, "LPDDR5", 68.0,
        "vendor datasheet",
        "TOPS is a sparse INT8 figure; dense workloads see roughly half."),
    "jetson_orin_nx": ReferencePlatform(
        "Jetson Orin NX 16GB", "Edge module", 100.0, 25.0, "LPDDR5", 102.4,
        "vendor datasheet",
        "Same sparsity caveat. Power is the configurable ceiling, not typical."),
    "edge_tpu": ReferencePlatform(
        "Coral Edge TPU", "USB / M.2 accelerator", 4.0, 2.0, "host memory", 0.0,
        "vendor datasheet",
        "No local DRAM: the host feeds it, so system bandwidth is not its own."),
    "hailo8": ReferencePlatform(
        "Hailo-8", "M.2 accelerator", 26.0, 2.5, "host memory", 0.0,
        "vendor datasheet",
        "Dataflow architecture; TOPS compares poorly with a systolic array."),
    "k230": ReferencePlatform(
        "Kendryte K230", "MCU-class SoC", 6.0, 2.0, "LPDDR4", 12.8,
        "vendor material, figures vary by source",
        "Published numbers differ between sources; treat as approximate."),
    "rpi5_ai_kit": ReferencePlatform(
        "Raspberry Pi 5 + AI Kit", "Hobby / education", 13.0, 8.0, "LPDDR4X", 17.0,
        "vendor datasheet",
        "System power includes the host board, unlike a bare module."),
}


# ==============================================================================
# Starting-point designs
# ==============================================================================
#
# One per application: something that works and is obviously improvable. The
# point is not to hand out a good answer but a starting position, so that the
# student is comparing against something rather than inventing from nothing.
# Every one of them leaves preprocessing on the CPU, which is the first thing
# worth questioning.

REFERENCE_DESIGNS: Dict[str, SystemConfig] = {
    "drone":              SystemConfig("cortex_a53_x4", "npu_16x16", "LPDDR5", 1),
    "autonomous_vehicle": SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4),
    "industrial_vision":  SystemConfig("cortex_a78_x4", "npu_16x16", "LPDDR5", 2),
    "smart_camera":       SystemConfig("cortex_a53_x4", "npu_16x16", "LPDDR5", 1),
    "mobile_ai":          SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2),
    "robot":              SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2),
    "medical":            SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2),
    "ai_inference":       SystemConfig("server_x86_x32", "datacenter_gpu", "GDDR6", 8),
    "llm_service":        SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6),
}


def reference_design(app_key: str) -> SystemConfig:
    """The starting point for this application.

    Delegates to ppact.designs, which holds the starting point and the
    design examples together - they belong in one place, because a reference
    that drifts away from the examples beside it stops being a starting point
    and becomes a fourth option.
    """
    from .designs import reference_of
    return reference_of(app_key)


def describe_design(config: SystemConfig) -> str:
    from .compute import COMPUTE_LIBRARY as _C
    from .cpu import CPU_LIBRARY as _P
    from .memory import MEMORY_LIBRARY as _M
    return (f"{_P[config.cpu].name}, {_C[config.compute].name}, "
            f"{_M[config.memory].name} x{config.memory_devices}, "
            f"preprocessing on {config.preprocessing_mode}")


# ==============================================================================
# Baseline versus proposal
# ==============================================================================

METRICS_OF_INTEREST = [
    ("Latency (ms)", "Average latency (ms)", False),
    ("Throughput (jobs/s)", "Throughput (jobs/s)", True),
    ("Average power (W)", "Average power (W)", False),
    ("Energy per job (mJ)", "Energy per job (mJ)", False),
    ("Total silicon (mm2)", "Total silicon (mm2)", False),
    ("System cost (USD)", "System cost (USD)", False),
]


@dataclass
class Proposal:
    app_key: str
    baseline: RuntimeResult
    proposed: RuntimeResult
    deltas: Dict[str, float] = field(default_factory=dict)
    reference: Optional[str] = None
    measured_reference_throughput: Optional[float] = None


def evaluate_proposal(app_key: str, baseline: SystemConfig, proposed: SystemConfig,
                      duration_s: float = 60.0,
                      reference: Optional[str] = None,
                      measured_reference_throughput: Optional[float] = None) -> Proposal:
    """Run both designs and record what changed, in both directions."""
    b = simulate(app_key, baseline, duration_s=duration_s)
    p = simulate(app_key, proposed, duration_s=duration_s)

    deltas = {}
    for label, key, higher_better in METRICS_OF_INTEREST:
        bv, pv = b.metrics[key], p.metrics[key]
        if bv == 0:
            deltas[label] = 0.0
            continue
        change = (pv - bv) / bv * 100.0
        # Reported as improvement, so a cost that went up reads negative.
        deltas[label] = change if higher_better else -change
    return Proposal(app_key, b, p, deltas, reference, measured_reference_throughput)


def print_proposal(prop: Proposal) -> None:
    app = APPLICATION_LIBRARY[prop.app_key]
    b, p = prop.baseline, prop.proposed

    print(f"\n{LINE}")
    print(" INNOVATION PROPOSAL - EVIDENCE")
    print(LINE)
    print(f"  application    {app.name}")
    print(f"  baseline       {b.base.label}")
    print(f"                 preprocessing: {b.base.config.preprocessing_mode}")
    print(f"  proposed       {p.base.label}")
    print(f"                 preprocessing: {p.base.config.preprocessing_mode}")

    print(f"\n  {'metric':<24s}{'baseline':>12s}{'proposed':>12s}{'change':>12s}")
    print("  " + "-" * 60)
    for label, key, _ in METRICS_OF_INTEREST:
        d = prop.deltas[label]
        arrow = "better" if d > 0.5 else ("worse" if d < -0.5 else "same")
        print(f"  {label:<24s}{b.metrics[key]:>12.2f}{p.metrics[key]:>12.2f}"
              f"{d:>+11.1f}%  {arrow}")

    print(f"\n  where the work moved")
    for name in ("ISP", "CPU", "Memory", "Accelerator",
                 "Accelerator 1", "Accelerator 2"):
        bs, ps = b.modules.get(name), p.modules.get(name)
        if bs is None and ps is None:
            continue
        bu = bs.utilisation_pct if bs else 0.0
        pu = ps.utilisation_pct if ps else 0.0
        width = 20
        from .visual import render_bar
        bar_b = render_bar(bu, 100.0, width).rstrip(".")
        bar_p = render_bar(pu, 100.0, width).rstrip(".")
        print(f"    {name:<12s}{bu:>5.0f}% {bar_b:<20s}  ->{pu:>5.0f}% {bar_p}")

    print(f"\n  limited by     {b.limiting_stage}  ->  {p.limiting_stage}")

    if p.base.metrics.get("Secondary die area (mm2)", 0.0) > 0:
        from .runtime import print_secondary_activity, explain_latency_delta
        print_secondary_activity(p.base)
        explain_latency_delta(b.base, p.base, "baseline", "your design")

    if prop.reference:
        print_reference_comparison(prop)

    print(f"\n  A change that improves one axis and worsens another is not a")
    print(f"  failure of the design. Which trade this application can accept is")
    print(f"  the argument to make, and it is yours to make - not the tool's.")
    print(LINE)


def print_reference_comparison(prop: Proposal) -> None:
    ref = REFERENCE_PLATFORMS[prop.reference]
    p = prop.proposed
    m = p.base.metrics

    print(f"\n  comparison with a published platform")
    print(f"    {ref.name}  ({ref.category})")
    print(f"    source: {ref.source}")
    if ref.caveat:
        print(f"    caveat: {ref.caveat}")

    print(f"\n    {'':<26s}{'reference':>14s}{'your design':>14s}")
    print("    " + "-" * 54)
    print(f"    {'peak INT8 TOPS':<26s}{ref.peak_tops_int8:>14.1f}"
          f"{m['Peak TOPS']:>14.1f}")
    print(f"    {'power (W)':<26s}{ref.typical_power_w:>14.1f}"
          f"{p.metrics['Average power (W)']:>14.1f}")
    print(f"    {'peak TOPS per watt':<26s}{ref.peak_tops_per_watt:>14.2f}"
          f"{m['Peak TOPS'] / max(p.metrics['Average power (W)'], 1e-9):>14.2f}")
    if ref.memory_bandwidth_gb_s > 0:
        print(f"    {'memory bandwidth (GB/s)':<26s}{ref.memory_bandwidth_gb_s:>14.1f}"
              f"{m['Effective bandwidth (GB/s)']:>14.1f}")

    print(f"\n    on THIS workload, your design achieves "
          f"{p.throughput:.1f} jobs/s at "
          f"{p.metrics['Average power (W)']:.2f} W.")
    if prop.measured_reference_throughput:
        r = prop.measured_reference_throughput
        print(f"    the reference, measured at {r:.1f} jobs/s on a published")
        print(f"    benchmark, gives a ratio of {p.throughput / r:.2f}x.")
    else:
        print(f"    No measured figure was supplied for the reference, so no")
        print(f"    throughput ratio is shown. Peak TOPS is not a substitute:")
        print(f"    it is a ceiling under vendor-chosen conditions and says")
        print(f"    nothing about this workload. Find a published benchmark")
        print(f"    result and pass it in.")


# ==============================================================================
# Scoring
# ==============================================================================

RUBRIC = [
    ("New application", 1,
     "An application meaningfully different from the nine in the library - "
     "agriculture, marine, space, logistics, semiconductor inspection. Not a "
     "relabelling of one that is already there."),
    ("System change", 1,
     "The architecture actually changed: a block moved, was added or was "
     "removed. Re-tuning a parameter is not a system change."),
    ("PPACT evidence", 2,
     "Simulator output showing what improved AND what got worse. A proposal "
     "that reports only gains has not been examined."),
    ("External comparison", 1,
     "A published product, paper, open-source platform or benchmark, with the "
     "source named and its measurement conditions stated."),
]


def print_rubric() -> None:
    print(f"\n{LINE}")
    print(" INNOVATION CHALLENGE (+5)")
    print(LINE)
    print("  The simulator computes the evidence. The bonus is awarded by the")
    print("  instructor: whether an application is genuinely new, and whether a")
    print("  comparison is fair, are judgements no tool can make.\n")
    for name, points, detail in RUBRIC:
        print(f"  {name:<22s}+{points}")
        print(f"    {detail}\n")
    print(f"  Final score = System PPACT score (0-100) + Innovation bonus (0-5)")
    print(LINE)


def system_score(app_key: str, config: SystemConfig,
                 duration_s: float = 60.0) -> Dict[str, float]:
    """The graded score, using the APPLICATION's weights, not the student's.

    A score computed from weights the candidate chose would let them declare
    that the only axis that matters is the one their design wins.
    """
    from .game import score_design, overall, AXES
    r = simulate(app_key, config, duration_s=duration_s)
    axes = score_design(r.base)
    w = grading_weights(app_key)
    total = overall(axes, w)
    gate_ok = r.base.passes
    met = sum(1 for ok in r.base.gate.values() if ok)
    return {**axes, "Overall": total,
            "Meets requirements": 1.0 if gate_ok else 0.0,
            "Requirements met": float(met),
            "Requirements total": float(len(r.base.gate)),
            "Throughput met": 1.0 if r.metrics["Keeps up"] else 0.0}


# Margins worth showing beside the gate, because "passes" and "passes with
# nothing to spare" are different engineering positions and the gate cannot
# tell them apart.
MARGIN_ROWS = [
    ("accuracy", "Deployment accuracy (%)", "required_accuracy_pct", True, "%"),
    ("throughput", "Throughput (inf/s)", "target_inferences_per_s", True, "/s"),
    ("power", "System power (W)", "power_budget_w", False, "W"),
    ("cost", "System cost (USD)", "bom_budget_usd", False, "USD"),
    ("board", "Board area (mm2)", "board_budget_mm2", False, "mm2"),
    ("thermal", "Power density (W/mm2)", "thermal_limit_w_per_mm2", False, "W/mm2"),
]


def print_requirements(app_key: str, config: SystemConfig,
                       duration_s: float = 60.0) -> None:
    """Requirement satisfaction, separately from any score.

    A PPACT score and a requirement check answer different questions. A design
    can meet every requirement and score 54 because the scale it sits on is
    wide; another can score 85 and not ship. Reporting them together, with the
    margin on each, stops the score being read as a verdict on whether the
    system works.
    """
    app = APPLICATION_LIBRARY[app_key]
    r = simulate(app_key, config, duration_s=duration_s)
    m = r.base.metrics

    print(f"\n{LINE}")
    print(" REQUIREMENTS")
    print(LINE)
    met = sum(1 for ok in r.base.gate.values() if ok)
    print(f"  {met} of {len(r.base.gate)} satisfied"
          + ("" if r.base.passes else "   <- this design does not ship"))
    print(f"\n  {'':<12s}{'achieved':>14s}{'required':>14s}{'margin':>12s}")
    print("  " + "-" * 54)
    for gate, key, budget_field, higher_better, unit in MARGIN_ROWS:
        if gate not in r.base.gate or key not in m:
            continue
        got, need = m[key], getattr(app, budget_field)
        if need == 0:
            continue
        margin = (got / need - 1.0) * 100.0 if higher_better else (1.0 - got / need) * 100.0
        flag = "" if r.base.gate[gate] else "  FAIL"
        print(f"  {gate:<12s}{got:>14.2f}{need:>14.2f}{margin:>+11.1f}%{flag}")
    print("\n  A margin near zero is not a failure. It is a design with nothing")
    print("  left to give, which is a different thing to argue about than one")
    print("  with room to spare.")


# A shipping reference typically lands here. It is a diagnostic band, NOT a
# target: the reference score is computed by the same formula as everything
# else, and if it falls outside this range the right response is to look at the
# anchors or at the reference, not to move the number.
REFERENCE_BAND = (75.0, 85.0)


def reference_score(app_key: str, duration_s: float = 60.0) -> float:
    """The starting point's score, computed - never stored.

    Storing it would let the reference drift away from the model: change a
    scoring anchor and every design moves except the one everything is measured
    against.
    """
    from .designs import reference_of
    return system_score(app_key, reference_of(app_key), duration_s)["Overall"]


def print_calibration() -> None:
    """Where every reference lands, and whether the ruler looks right.

    A reference that scores 40 is not a bad product; it is a sign the scale was
    built for something else. This is the check for that, and it reports rather
    than corrects - the numbers here came out of the model and moving them by
    hand would defeat the point of having one.
    """
    lo, hi = REFERENCE_BAND
    print(f"\n{LINE}")
    print(" REFERENCE CALIBRATION")
    print(LINE)
    print(f"  A reference is a shipping product, so it should score in the")
    print(f"  {lo:.0f}-{hi:.0f} band: good enough to be sold, not so good that a")
    print(f"  student cannot improve on it. Outside that band, look at the")
    print(f"  anchors before blaming the design.\n")
    print(f"  {'application':<22s}{'score':>8s}   note")
    print("  " + "-" * 62)
    for key, app in APPLICATION_LIBRARY.items():
        v = reference_score(key)
        if v < lo:
            note = "below band - little headroom to lose"
        elif v > hi:
            note = "above band - hard for a student to beat"
        else:
            note = ""
        print(f"  {app.name:<22s}{v:>8.1f}   {note}")


def print_innovation_report(app_key: str, config: SystemConfig,
                 prop: Optional[Proposal] = None,
                 duration_s: float = 60.0) -> None:
    """Report layout: everything factual is generated, two questions are not.

    The student writes only WHY and WHAT WAS TRADED. Everything above those two
    headings came out of the simulator, and everything below them is a mark the
    instructor gives - neither is theirs to supply.
    """
    app = APPLICATION_LIBRARY[app_key]
    s = system_score(app_key, config, duration_s)
    r = simulate(app_key, config, duration_s=duration_s)

    print(f"\n{LINE}")
    print(" FINAL PROJECT REPORT")
    print(LINE)
    print(f"  Application          {app.name}")
    print(f"  Model                {app.model}")
    print(f"  Configuration        {r.base.label}")
    from .process import node_name as _nn
    print(f"    process            host {_nn(r.base.soc_node)}, "
          f"accelerator {_nn(r.base.accel_node)}, {r.base.integration}")
    print(f"    preprocessing      {config.preprocessing_mode}")

    print(f"\n  Results over {duration_s:g} s")
    print(f"    latency            {r.first_latency_ms:.2f} ms")
    print(f"    throughput         {r.throughput:.1f} /s "
          f"(needed {app.target_inferences_per_s:g})")
    print(f"    average power      {r.metrics['Average power (W)']:.2f} W")
    print(f"    total energy       {r.metrics['Total energy (J)']:.1f} J")
    print(f"    silicon            {r.metrics['Total silicon (mm2)']:.1f} mm2")
    print(f"    cost               {r.metrics['System cost (USD)']:.2f} USD")
    print(f"    thermal margin     {r.metrics['Thermal margin (%)']:.1f} %")

    print_requirements(app_key, config, duration_s)

    print(f"\n  PPACT, weighted for this application")
    print(f"  (a score, not a verdict on whether the system works - that is")
    print(f"   the requirements block above)")
    w = grading_weights(app_key)
    for axis in ("Accuracy", "Performance", "Power", "Area", "Cost", "Thermal"):
        print(f"    {axis:<18s}{s[axis]:>6.0f}   weight {w[axis]:.1f}")
    print(f"    {'System PPACT score':<18s}{s['Overall']:>6.0f} / 100")
    if not s["Meets requirements"]:
        print(f"    (this design does not meet the product requirements)")

    if prop is not None:
        print_proposal(prop)

    print(f"\n{LINE}")
    print(" TO BE WRITTEN BY THE STUDENT")
    print(LINE)
    print("  Everything above this line was generated. These two are not, and")
    print("  they are what the exercise is actually about.\n")
    print("  1. Why did you change the architecture, and why does this change")
    print("     suit THIS application in particular?")
    print("     ...\n")
    print("  2. What got worse, and why is that acceptable here?")
    print("     ...\n")
    print(LINE)
    print(" SCORING")
    print(LINE)
    ref_v = reference_score(app_key, duration_s)
    delta = s["Overall"] - ref_v
    # "Starting point" reads as the recommended one. It is a starting
    # point chosen to make a change legible, and a student whose design
    # differs from it has not thereby made a mistake.
    print(f"  Starting point       {ref_v:5.1f} / 100   scored the same way, "
          f"not a recommendation")
    print(f"  Your design          {s['Overall']:5.1f} / 100")
    print(f"  Improvement          {delta:+5.1f}")
    if delta <= 0:
        print(f"  (your design scores no higher than the starting point. That is a")
        print(f"   result, not a failure - say what you were trading for.)")
    print()
    print(f"  System PPACT score   {s['Overall']:.0f} / 100   computed by the simulator")
    print(f"  Innovation bonus     __ / 5     awarded by the instructor")
    print(f"  Final score          __ / 105")
    print(LINE)
