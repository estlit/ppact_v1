"""
ppact.game - guided design exploration for students meeting PPACT for the first time

The full model reports around forty numbers. That is right for someone auditing
the physics and wrong for someone meeting the idea for the first time, who will
read forty numbers and take away none of them. This layer shows six bars, a set
of stars and one sentence.

ONE DELIBERATE DEPARTURE
------------------------
The overall score is computed from priorities the STUDENT declares, not from a
fixed formula. A single objective score would quietly become the right answer:
90 beats 88, and the exercise collapses into maximising one number. Weighted by
declared priorities, two students can reach the same score with opposite designs
and both be defensible - which is the actual lesson, and the thing they have to
argue in the report.

The tool never names a recommended device. It reports what the design is, and
leaves what it should be to the student.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
from typing import Dict, List, Optional, Tuple

from .application import APPLICATION_LIBRARY, make_custom_application
from .compute import COMPUTE_LIBRARY
from .cpu import CPU_LIBRARY
from .memory import MEMORY_LIBRARY
from .process import NODE_LIBRARY
from .system import SystemConfig, evaluate_system, SYSTEM_ANCHORS
from .preprocess import MODES as PREPROCESSING_MODES
# Module level, not inside play(). A name imported inside a function is a
# LOCAL name for that whole function, so a use ABOVE the import raises
# UnboundLocalError - at run time, on the one path that reaches it, which is
# how this survived every suite until a user walked the menu.
from .questions import (get as _q, ask_question, navigate,
                        memory_context, memory_summary,
                        memory_unit_count_question, Option as _Opt)
from .core import in_notebook

LINE = "=" * 66


# ==============================================================================
# Precision as a student choice
# ==============================================================================
#
# In the full model precision is a fixed property of the engine. Here it is a
# knob, because "what does INT4 actually cost me" is one of the questions worth
# asking. The three effects are kept separate so none of them is a surprise:
# accuracy, energy per operation, and the bytes a weight occupies.

PRECISION_OPTIONS: Dict[str, Dict[str, float]] = {
    "FP32": {"extra_loss_pp": -1.0, "energy_x": 2.60, "weight_bytes_x": 4.0,
             "note": "Full precision. Nothing is lost and nothing is saved."},
    "FP16": {"extra_loss_pp": -0.9, "energy_x": 1.40, "weight_bytes_x": 2.0,
             "note": "Half precision. Accuracy essentially intact."},
    "INT8": {"extra_loss_pp": 0.0, "energy_x": 1.00, "weight_bytes_x": 1.0,
             "note": "The edge default. The engine's own quantisation loss applies."},
    "INT4": {"extra_loss_pp": 1.5, "energy_x": 0.65, "weight_bytes_x": 0.5,
             "note": "Half the weight traffic, at a real accuracy cost."},
}

# What each engine class can actually execute. Offering FP32 on a systolic INT8
# array would be a lie the student cannot detect.
SUPPORTED_PRECISION: Dict[str, Tuple[str, ...]] = {
    "Edge NPU": ("INT8", "INT4"),
    "Automotive NPU": ("FP16", "INT8", "INT4"),
    "Mobile GPU": ("FP32", "FP16", "INT8"),
    "Datacenter": ("FP32", "FP16", "INT8"),
    "No accelerator": ("FP32", "FP16"),
}

AXES = ["Accuracy", "Performance", "Power", "Area", "Cost", "Thermal"]

PHILOSOPHIES = {
    "Performance": "Performance-oriented",
    "Accuracy": "Accuracy-oriented",
    "Power": "Power-efficient",
    "Cost": "Cost-efficient",
    "Area": "Area-efficient",
    "Thermal": "Thermally conservative",
}


# ==============================================================================
# Scoring
# ==============================================================================

def _bounded(value: float, zero: float, hundred: float, log: bool = False) -> float:
    import math
    if log:
        value, zero, hundred = (math.log10(max(v, 1e-9)) for v in (value, zero, hundred))
    frac = (value - zero) / (hundred - zero)
    return max(0.0, min(100.0, frac * 100.0))


# Absolute anchors, but scoped BY DOMAIN.
#
# Anchoring to each product's own budget was tried first and was wrong: an
# application with generous budgets pushed every design to five stars and the
# display stopped saying anything.
#
# A single absolute set across all nine was wrong in the other direction. A
# datacenter node legitimately draws 290 W and costs $12,000, which on an edge
# scale is zero on two axes - so the starting points for AI Inference and LLM
# Service scored 38 and 30. That is not a judgement on those designs; it is the
# ruler being the wrong length. A drone module and a rack accelerator are not
# on one scale and pretending they are makes one of them meaningless.
#
# Within a domain the anchors stay absolute, so two designs for the same
# application remain directly comparable - which is what the exercise needs.
# Across domains they are not comparable, and should not be.
DOMAIN_ANCHORS = {
    "Edge": {
        #             metric,                      0 points,  100 points, log
        "Power":       ("System power (W)",            200.0,        0.5, True),
        "Area":        ("Board area (mm2)",           4000.0,       50.0, True),
        "Cost":        ("System cost (USD)",          5000.0,        5.0, True),
        "Thermal":     ("Power density (W/mm2)",        0.60,      0.002, True),
    },
    "Data Center": {
        "Power":       ("System power (W)",           2000.0,       30.0, True),
        "Area":        ("Board area (mm2)",          40000.0,      400.0, True),
        "Cost":        ("System cost (USD)",         200000.0,    1000.0, True),
        "Thermal":     ("Power density (W/mm2)",        1.20,      0.010, True),
    },
}
# A student-defined application inherits the anchors of its domain; one marked
# "Custom" is treated as Edge, which is where most invented products sit.
GAME_ANCHORS = DOMAIN_ANCHORS["Edge"]


def anchors_for(app) -> dict:
    return DOMAIN_ANCHORS.get(app.domain, DOMAIN_ANCHORS["Edge"])


def score_design(result) -> Dict[str, float]:
    """Six numbers on one 0-100 scale, all meaning 'higher is better'.

    Accuracy is the exception and is scored against the REQUIREMENT, not
    absolutely: meeting it is 70, the margin limit is 100, and beyond that it
    flattens. Accuracy the product cannot use is not an achievement, and a
    flat top is what stops a high-precision engine collecting credit for it.
    """
    m = result.metrics
    app = result.app

    margin = m["Accuracy margin (pp)"]
    limit = max(app.accuracy_margin_limit_pp, 0.1)
    if margin < 0:
        accuracy = max(0.0, 70.0 + margin / limit * 70.0)
    else:
        accuracy = 70.0 + min(margin / limit, 1.0) * 30.0

    # Performance is measured against the REQUIREMENT, not on an absolute
    # scale. Frames per second and tokens per second are not the same quantity
    # and no fixed ceiling is meaningful for both: 5000 frames/s is unremarkable
    # and 5000 tokens/s single-stream does not exist. What both share is a
    # target the product has to hit, so the ratio to that target is the honest
    # unit-free measure. Half the requirement scores zero; four times it scores
    # full marks and stops - headroom beyond that is not something the product
    # can spend.
    required = max(app.target_inferences_per_s, 1e-9)
    ratio = m["Throughput (inf/s)"] / required
    performance = _bounded(ratio, 0.5, 4.0, log=True)

    scores = {"Accuracy": accuracy, "Performance": performance}
    for axis, (key, zero, hundred, log) in anchors_for(app).items():
        scores[axis] = _bounded(m[key], zero, hundred, log)
    return scores


def stars(score: float) -> str:
    # Was a star rating. Stars read like a review of a restaurant and
    # invite comparison with things that have nothing to do with this - the
    # same objection that removed a star rating from the confidence report
    # at 3.95.0. The score itself is printed beside this.
    from .visual import render_rating
    return render_rating(score, 100.0, 5)


def bar(score: float, width: int = 30) -> str:
    from .visual import render_bar
    return render_bar(score, 100.0, width)


def overall(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    total = sum(weights.values())
    if total <= 0:
        return sum(scores.values()) / len(scores)
    return sum(scores[a] * weights.get(a, 0.0) for a in AXES) / total


def describe_philosophy(weights: Dict[str, float], scores: Dict[str, float]) -> str:
    """Name the design from what the student prioritised and what they got.

    Deliberately descriptive. It is a label for the report to argue with, not a
    verdict on the design.
    """
    ranked = sorted(AXES, key=lambda a: -weights.get(a, 0.0))
    top, second = ranked[0], ranked[1]
    spread = max(scores.values()) - min(scores.values())
    if weights.get(top, 0) - weights.get(second, 0) < 0.5 and spread < 25:
        return "Balanced"
    return PHILOSOPHIES[top]


# ==============================================================================
# Presentation
# ==============================================================================

def show_result(result, weights: Optional[Dict[str, float]] = None,
                show_detail: bool = False) -> Dict[str, float]:
    scores = score_design(result)
    app = result.app

    # The title says what this IS. "RESULT" reads as the answer, and a
    # priority-weighted score is not the answer - it is what the score looks
    # like under one particular ordering of what matters.
    print(f"\n{LINE}")
    print(f" PRIORITY-WEIGHTED EDUCATION SCORE - {app.name}")
    print(f"{LINE}")
    print(f"  {result.label}")
    from .process import node_name as _nn
    print(f"  host {_nn(result.soc_node)}, accelerator {_nn(result.accel_node)}, "
          f"{result.integration}\n")

    for axis in AXES:
        print(f"  {axis:<13s}{scores[axis]:5.0f}  {bar(scores[axis])}  "
              f"{stars(scores[axis])}")

    if not result.passes:
        failed = [g for g, ok in result.gate.items() if not ok]
        print(f"\n  Does not meet the requirement: {', '.join(failed)}")
        print("  The scores above still describe the design; they just describe")
        print("  a design this product cannot ship.")

    if weights:
        print(f"\n  Overall, weighted by your priorities : "
              f"{overall(scores, weights):.0f} / 100")
        order = sorted(AXES, key=lambda a: -weights.get(a, 0))
        print(f"  Your priorities  : {' > '.join(order[:3])}")
        print(f"  Design philosophy: {describe_philosophy(weights, scores)}")
        print("\n  This score reflects the selected priority order.")
        print("  It is not a universal ranking of architectures and does not")
        print("  replace the engineering design review.")
        print("\n  Two designs can score the same with opposite choices.")
        print("  What you have to defend is the priority order, not the")
        print("  number.")

    if show_detail:
        m = result.metrics
        print(f"\n  {'accuracy':<22s}{m['Deployment accuracy (%)']:8.2f} %   "
              f"(need {app.required_accuracy_pct:g})")
        print(f"  {'throughput':<22s}{m['Throughput (inf/s)']:8.1f} /s  "
              f"(need {app.target_inferences_per_s:g})")
        print(f"  {'system power':<22s}{m['System power (W)']:8.2f} W   "
              f"(budget {app.power_budget_w:g})")
        print(f"  {'board area':<22s}{m['Board area (mm2)']:8.0f} mm2 "
              f"(budget {app.board_budget_mm2:g})")
        print(f"  {'system cost':<22s}{m['System cost (USD)']:8.2f} USD "
              f"(budget {app.bom_budget_usd:g})")
        print(f"  {'power density':<22s}{m['Power density (W/mm2)']:8.4f} W/mm2 "
              f"(limit {app.thermal_limit_w_per_mm2:g})")
    return scores


def show_memory(result) -> None:
    """Five memory figures, deliberately without an aggregate.

    A "Memory Score" would be a second number to optimise alongside the overall
    one, and the same objection applies: it turns a judgement into a target.
    These five are diagnostic - they explain WHY a design scored as it did, so
    a student who is puzzled by a low Performance bar can find the reason.
    """
    m = result.metrics
    app = result.app
    mem = MEMORY_LIBRARY[result.config.memory]
    print(f"\n{LINE}")
    print(f" MEMORY - {mem.name} x{result.config.memory_devices}")
    print(f"{LINE}")
    print(f"  peak bandwidth      {m['Peak bandwidth (GB/s)']:10.1f} GB/s")
    print(f"  utilisation         {m['Bandwidth efficiency (%)']:10.1f} %"
          f"   (refresh, bank conflicts, turnaround)")
    print(f"  effective bandwidth {m['Effective bandwidth (GB/s)']:10.1f} GB/s")
    print(f"  needed to sustain   {m['BW to sustain peak (GB/s)']:10.1f} GB/s"
          f"   for this accelerator at full rate")
    print(f"  capacity            {m['Memory capacity (GB)']:10.1f} GB"
          f"     (model needs {app.required_memory_bytes / 1e9:.1f})")
    print(f"  memory power        {m['Memory power (W)']:10.2f} W"
          f"      ({m['  memory share (%)']:.0f}% of system energy)")
    print(f"  DRAM traffic        {m['DRAM traffic (MB)']:10.1f} MB per inference")
    supply = (m["Effective bandwidth (GB/s)"]
              / max(m["BW to sustain peak (GB/s)"], 1e-9))
    print(f"\n  supply ratio        {supply:10.2f}"
          f"   {'the accelerator is fed' if supply >= 1 else 'the accelerator is starved'}")

    print(f"\n  --- host CPU ---")
    print(f"  preprocess on CPU   {m['CPU preprocess (ms)']:10.3f} ms")
    if m["Preprocess offload (ms)"] > 0 or m["Offload overhead (ms)"] > 0:
        print(f"  preprocess offloaded{m['Preprocess offload (ms)']:10.3f} ms")
        print(f"  hand-off overhead   {m['Offload overhead (ms)']:10.3f} ms"
              f"   (dispatch + transfer, per frame)")
    print(f"  dispatch            {m['CPU dispatch (ms)']:10.3f} ms   (fixed, independent of size)")
    print(f"  postprocess         {m['CPU postprocess (ms)']:10.3f} ms")
    print(f"  active              {m['CPU active (ms)']:10.3f} ms")
    print(f"  waiting on accel.   {m['CPU accelerator-wait (ms)']:10.3f} ms")
    print(f"  share of latency    {m['CPU latency share (%)']:10.1f} %")
    print("  (share of one job's latency, not utilisation - utilisation needs")
    print("   an interval with more than one job in it, which is Phase 3)")
    if m["ISP active (ms)"] > 0:
        print(f"\n  --- ISP ---")
        print(f"  active              {m['ISP active (ms)']:10.3f} ms")
        print(f"  hidden by capture   {m['ISP hidden (ms)']:10.3f} ms")
        print(f"  exposed to latency  {m['ISP exposed (ms)']:10.3f} ms")
    if m["Offload calls"] > 0:
        print(f"\n  --- offload to the accelerator ---")
        print(f"  frame              {m['Pixels per stream']:11,.0f} px x "
              f"{m['Streams']:.0f} streams = {m['Total pixels per job']:,.0f} px")
        print(f"  calls               {m['Offload calls']:10.0f}"
              f"   (batched into one, or one per stream)")
        print(f"  dispatch            {m['Offload dispatch (ms)']:10.3f} ms")
        print(f"  transfer            {m['Offload transfer (ms)']:10.3f} ms")
        print(f"  preprocessing       {m['Preprocess offload (ms)']:10.3f} ms")
        print("  (preprocessing reuses the main array, so it cannot overlap")
        print("   with inference - accelerator active time is the sum)")

    print(f"\n  --- where the time goes ---")
    print(f"  compute             {m['Compute time (ms)']:10.2f} ms")
    print(f"  transfer            {m['Memory time (ms)']:10.2f} ms")
    print(f"  hidden by overlap   {m['Hidden transfer (ms)']:10.2f} ms"
          f"   (overlap {m['Overlap ratio']:.2f})")
    print(f"  accelerator waiting {m['Compute data-wait (ms)']:10.2f} ms")
    print(f"  utilisation         {m['Compute utilisation (%)']:10.1f} %")
    print(f"\n  latency contribution   compute "
          f"{m['Latency contribution, compute (%)']:5.1f} %   memory "
          f"{m['Latency contribution, memory (%)']:5.1f} %")
    print("  (contribution to exposed time, not a queueing bottleneck - that")
    print("   would need arbitration and queue models this does not have)")


def compare_designs(results, weights: Optional[Dict[str, float]] = None) -> None:
    """Put several designs beside each other, one line of stars per axis."""
    print(f"\n{LINE}")
    print(" COMPARISON")
    print(f"{LINE}")
    all_scores = [score_design(r) for r in results]
    width = max(len(r.label) for r in results) + 2
    print(f"  {'design':<{width}s}" + "".join(f"{a[:9]:>11s}" for a in AXES)
          + ("      overall" if weights else ""))
    print("  " + "-" * (width + 11 * len(AXES) + (13 if weights else 0)))
    for r, s in zip(results, all_scores):
        row = f"  {r.label:<{width}s}" + "".join(f"{stars(s[a]):>11s}" for a in AXES)
        if weights:
            row += f"{overall(s, weights):>13.0f}"
        print(row + ("" if r.passes else "   (does not meet requirement)"))


# ==============================================================================
# The guided flow
# ==============================================================================

def _ask(prompt: str, options: List[str], default: int = 1) -> int:
    while True:
        for i, text in enumerate(options, 1):
            print(f"    {i}. {text}")
        try:
            raw = input(f"\n  {prompt} [{default}]: ").strip()
        except Exception:
            print(f"  (no input - using {default})")
            return default
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print(f"\n  Enter a number from 1 to {len(options)}.\n")


def _build_custom() -> str:
    """Ask for a product definition instead of picking one off the shelf."""
    print(f"\n{LINE}\n DEFINE YOUR PRODUCT\n{LINE}")
    print("  Answer as a product planner would. Nothing here is checked for")
    print("  realism - if the requirements cannot be met by anything, that is")
    print("  a finding, and it is the finding worth writing about.\n")

    def _num(prompt: str, default: float) -> float:
        try:
            raw = input(f"  {prompt} [{default:g}]: ").strip()
        except Exception:
            return default
        try:
            return float(raw) if raw else default
        except ValueError:
            print(f"    not a number - using {default:g}")
            return default

    name = "Custom Application"
    try:
        entered = input("  Product name [Custom Application]: ").strip()
        name = entered or name
    except Exception:
        pass

    mac = _num("Compute per inference, GMAC", 2.0) * 1e9
    weights = _num("Model size, MB", 10.0) * 1e6
    fps = _num("Inferences per second required", 30.0)
    ref = _num("Model accuracy before deployment, %", 97.0)
    req = _num("Accuracy the product requires, %", 94.0)
    power = _num("Power budget, W", 10.0)
    bom = _num("BOM budget, USD", 100.0)
    board = _num("Board area budget, mm2", 500.0)
    volume = int(_num("Lifetime volume, units", 500000))

    make_custom_application(
        name=name, mac_per_inference=mac, weight_bytes=weights,
        activation_bytes=weights * 2.5, activation_working_set_kb=max(256.0, weights / 8e3),
        reference_accuracy_pct=ref, required_accuracy_pct=req,
        target_inferences_per_s=fps, latency_budget_ms=max(1.0, 1000.0 / fps),
        power_budget_w=power, bom_budget_usd=bom, board_budget_mm2=board,
        production_volume=volume)
    print(f"\n  {name} registered. Accuracy budget "
          f"{ref - req:.1f} pp, {fps:g} inf/s inside {power:g} W and ${bom:,.0f}.")
    return "custom"


def _ask_priorities() -> Dict[str, float]:
    print(f"\n{LINE}")
    print(" STEP 4. WHAT MATTERS TO YOU")
    print(f"{LINE}")
    print("  Before seeing a total, say what this product is for. The overall")
    print("  score is computed from YOUR priorities, so a design that suits your")
    print("  goals scores well even if another design would suit different ones.\n")
    presets = {
        "Balanced - nothing dominates": {a: 1.0 for a in AXES},
        "Battery powered - power first": {"Power": 3.0, "Thermal": 2.0, "Cost": 1.5,
                                          "Accuracy": 1.0, "Performance": 1.0, "Area": 1.0},
        "Safety critical - accuracy and speed first": {"Accuracy": 3.0, "Performance": 2.5,
                                                       "Thermal": 1.0, "Power": 1.0,
                                                       "Cost": 0.5, "Area": 0.5},
        "High volume consumer - cost first": {"Cost": 3.0, "Area": 2.0, "Power": 1.5,
                                              "Accuracy": 1.0, "Performance": 1.0,
                                              "Thermal": 1.0},
        "Throughput at any price": {"Performance": 3.0, "Accuracy": 1.5, "Cost": 0.3,
                                    "Power": 0.5, "Area": 0.5, "Thermal": 0.5},
    }
    # Score-only. The prompt says so, because a user who cannot tell a
    # choice that changes the design from one that changes the marking will
    # eventually believe the tool preferred a design.
    import dataclasses as _dcw
    keys = list(presets)
    priority_q = _dcw.replace(
        _q("design_priority"),
        options=tuple(_Opt(k, k) for k in keys),
        default=1, option_builder=None)
    return presets[ask_question(priority_q)]


def play(app_key: Optional[str] = None):
    """Four steps: application, system, result, priorities.

    RETURNS ITS FINAL STATE.

    A caller used to read the outcome by watching which engine function
    was called, which meant the identity of the design depended on the
    order of calls rather than on what the game decided. The game knows
    what it built and now says so:

        design completed   COMPLETED / SINGLE, with the configuration
        user left          CANCELLED / SINGLE, with none
    """
    print(f"\n{LINE}")
    print(" EdgeChipLab AI Accelerator Design Simulator")
    print(f"{LINE}")
    print("  Choose an application, design a system, see what you traded away.")
    print("  There is no correct answer. There is an answer you can defend.")

    # ---- STEP 1 ----
    if app_key is None:
        print(f"\n{LINE}\n STEP 1. APPLICATION\n{LINE}")
        keys, labels = [], []
        for domain in ("Edge", "Data Center"):
            first = True
            for k, a in APPLICATION_LIBRARY.items():
                if a.domain != domain:
                    continue
                prefix = f"[{domain}] " if first else " " * (len(domain) + 3)
                keys.append(k)
                labels.append(f"{prefix}{a.name:<22s} {a.model}")
                first = False
        keys.append("__custom__")
        labels.append("[Custom]      Define your own product")
        import dataclasses as _dca
        app_q = _dca.replace(
            _q("application"),
            options=tuple(_Opt(k, lbl) for k, lbl in zip(keys, labels)),
            default=1, option_builder=None)
        chosen = ask_question(app_q)
        app_key = _build_custom() if chosen == "__custom__" else chosen
    app = APPLICATION_LIBRARY[app_key]

    print(f"\n  {app.name}")
    print(f"  model     : {app.model}")
    print(f"  needs     : {app.required_accuracy_pct:g}% accuracy, "
          f"{app.target_inferences_per_s:g} inferences/s")
    print(f"  budgets   : {app.power_budget_w:g} W, ${app.bom_budget_usd:,.0f}, "
          f"{app.board_budget_mm2:g} mm2 board")

    # ---- STEP 2 ----
    print(f"\n{LINE}\n STEP 2. DESIGN THE SYSTEM\n{LINE}")
    # Every prompt below comes from ppact.questions. A prompt written here
    # would be a prompt nothing holds to the standard - which is how the
    # eleven that preceded these came to be four bare integers under a
    # variable name.

    comp = ask_question(_q("accelerator_class"))
    print()
    mem = ask_question(_q("memory_type"))
    print()

    # The memory specification comes BEFORE the count. A count is
    # meaningless without the thing being counted.
    for line in memory_context(mem):
        print(f"  {line}")
    print()
    n_mem = ask_question(memory_unit_count_question(mem))
    print()
    for line in memory_summary(mem, n_mem):
        print(f"  {line}")
    print()

    u = ask_question(_q("bandwidth_utilisation"))
    print()
    node = ask_question(_q("process_node"))

    category = COMPUTE_LIBRARY[comp].category
    allowed = SUPPORTED_PRECISION.get(category, ("INT8",))
    print()
    print()
    modes = list(PREPROCESSING_MODES)
    if APPLICATION_LIBRARY[app_key].workload_class == "vision":
        pmode = ask_question(_q("preprocessing_location"))
        if pmode in ("npu_assisted", "isp_and_npu") and APPLICATION_LIBRARY[app_key].streams > 1:
            print()
            batching = ask_question(_q("offload_handoff"))
        else:
            batching = True
    else:
        pmode = "cpu_only"
        batching = True
        print("    (text workload - preprocessing placement does not apply)")
    print()
    import dataclasses as _dcp
    prec_q = _dcp.replace(
        _q("precision"),
        options=tuple(_Opt(p, p, PRECISION_OPTIONS[p]["note"])
                      for p in allowed),
        default=min(2, len(allowed)), option_builder=None)
    prec = ask_question(prec_q)

    # ---- STEP 3 ----
    result = evaluate_with_precision(app_key, comp, mem, n_mem, node, prec, u,
                                     pmode, batching)
    print(f"\n{LINE}\n STEP 3. RESULT\n{LINE}")
    print(f"  precision {prec} - {PRECISION_OPTIONS[prec]['note']}")
    show_result(result, show_detail=True)
    show_memory(result)

    # ---- STEP 4 ----
    weights = _ask_priorities()
    show_result(result, weights=weights)

    # ---- STEP 5 ----
    #
    # The standard review is produced automatically. It is not offered.
    #
    # The earlier version asked "Continue to the Full Engineering Design
    # Review?" and defaulted to yes. Asking at all says the core result is
    # optional, and a user who answers no has completed an analysis and
    # received a score.
    return _standard_review(app_key, comp, mem, n_mem, node, prec, u,
                            pmode, batching)


def _standard_review(app_key, comp, mem, n_mem, node, prec, u, pmode,
                     batching) -> None:
    """One design, one single-variant review, through the one entry point.

    No starting configuration is manufactured. A single analysis does not
    silently become a comparison.

    That distinction cost a release cycle: a baseline shown on every screen
    is read as the architecture the tool prefers, whatever the label beside
    it says. A starting point exists to make a measured change easier to
    interpret. It is not a recommendation, not an optimal design, and not a
    target architecture - and reintroducing it through a default comparison
    would undo the whole of 4.15.0.
    """
    from .review import build_review, render_standard_engineering_review

    cfg = SystemConfig(
        "server_x86_x32" if APPLICATION_LIBRARY[app_key].domain
        == "Data Center" else "cortex_a78_x4",
        comp, mem, n_mem, soc_node=node, accel_node=node,
        preprocessing_mode=pmode, offload_batching=batching,
        bandwidth_efficiency=u)

    from .outcome import single as _gs, SelectedAnswer as _GA
    from .present import present as _present
    _out = _gs("education_step_by_step", app_key, cfg,
               (_GA(1, "Application", str(app_key)),
                _GA(2, "Accelerator", str(getattr(cfg, "compute", ""))),
                _GA(3, "Memory Technology",
                    str(getattr(cfg, "memory", ""))),
                _GA(4, "Memory Devices",
                    str(getattr(cfg, "memory_devices", "")))))
    _present(_out)
    return _out


def evaluate_with_precision(app_key: str, compute: str, memory: str,
                            memory_devices: int = 1, node: Optional[str] = None,
                            precision: str = "INT8",
                            bandwidth_efficiency: Optional[float] = None,
                            preprocessing_mode: str = "cpu_only",
                            offload_batching: bool = True):
    """Evaluate one design with precision as an explicit choice.

    Precision touches three things at once and the model has to reflect all
    three, or the student learns a false lesson: accuracy, energy per
    operation, and how many bytes a weight occupies in DRAM.
    """
    app = APPLICATION_LIBRARY[app_key]
    opt = PRECISION_OPTIONS[precision]

    comp = COMPUTE_LIBRARY[compute]
    tuned = dataclasses.replace(
        comp,
        precision=precision,
        energy_pj_per_mac=comp.energy_pj_per_mac * opt["energy_x"],
    )
    scaled_app = dataclasses.replace(
        app,
        weight_bytes=app.weight_bytes * opt["weight_bytes_x"],
        kv_cache_bytes=app.kv_cache_bytes * opt["weight_bytes_x"],
    )

    saved = COMPUTE_LIBRARY[compute]
    COMPUTE_LIBRARY[compute] = tuned
    try:
        cfg = SystemConfig(_default_cpu(app), compute, memory, memory_devices,
                           accel_node=node,
                           bandwidth_efficiency=bandwidth_efficiency,
                           preprocessing_mode=preprocessing_mode,
                           offload_batching=offload_batching)
        return evaluate_system(scaled_app, cfg)
    finally:
        COMPUTE_LIBRARY[compute] = saved


def _default_cpu(app) -> str:
    return ("server_x86_x32" if app.domain == "Data Center" else "cortex_a78_x4")
