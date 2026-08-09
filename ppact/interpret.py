"""
ppact.interpret - is this number normal for this kind of product?

The rest of the package computes values. This module says whether a value is
ordinary, unusual or impossible for the domain it was computed for. A student
who sees a latency of 320 ms has no way to know that industrial inspection
lives between 1 and 30 ms, and a simulator that only produces numbers leaves
them to find that out somewhere else.

WHERE THIS SITS
---------------
NOT in the simulation path. The ranges are never an input to a calculation -
they are consulted AFTER the numbers exist, from the side:

    application scenario + student design
                |
                v
        whole-system simulation
                |
                v
        raw simulation results
                |
                v
          result interpreter   <---- NPU metric reference ranges (this file)
                |
                v
        interpreted evaluation

An earlier version of this note drew the ranges and the simulation as
successive stages, which reads as though the bands feed the model. They do not.
Nothing here changes a computed value.

WHAT IT COMPARES AGAINST - THREE THINGS, NOT ONE
------------------------------------------------
    1. the application's REQUIREMENT   does it ship
    2. the STARTING POINT            is it better or worse than the
                                       architecture the course starts from
    3. the DOMAIN range                is it ordinary for this kind of product

The three answer different questions and can disagree. A design can meet every
requirement, beat the reference, and still sit outside a typical band - or the
reverse. Collapsing them into one verdict would throw away what makes the
comparison worth making.

The ranges are about accelerators - TOPS, TOPS per watt, utilisation - and the
model computes whole systems: host-active time, ISP, memory waiting, pipeline
intervals, dual engines, footprint, cost, thermal margin. Nothing in the table
covers those.

BOUNDARIES, AGAIN
-----------------
Most of the mistakes in this project have been comparisons across different
measurement boundaries, so each mapping below declares which simulator metric
it reads and at which boundary. Where the model's boundary is WIDER than the
range's - system power against accelerator power, for instance - the comparison
is marked and softened rather than made silently.

PROVENANCE
----------
The ranges are a synthesis of published references rather than measurements,
and the source workbook says so. They are recorded as ESTIMATED, and a value
outside a range is a prompt to look, not a verdict.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

LINE = "=" * 78

DOMAINS = ("TinyML / IoT", "Edge AI", "Embedded / Industrial",
           "Server / Datacenter", "Automotive / ADAS")


@dataclass(frozen=True)
class Range:
    metric: str
    unit: str
    bands: Dict[str, Optional[Tuple[float, float]]]
    how_to_read: str
    caveat: str
    # Which simulator metric answers this, and whether the boundaries agree.
    metric_key: str = ""
    boundary_note: str = ""


RANGES: List[Range] = [
    Range("TOPS", "Tera ops/s",
          {"TinyML / IoT": (1e-6, 0.1), "Edge AI": (0.5, 30.0),
           "Embedded / Industrial": (10.0, 200.0),
           "Server / Datacenter": (100.0, 10000.0),
           "Automotive / ADAS": (100.0, 1000.0)},
          "Peak arithmetic capacity, useful only alongside precision.",
          "Dense and sparse TOPS, and INT8 against FP16, are not comparable.",
          metric_key="Peak TOPS",
          boundary_note="Same boundary: both are the accelerator's peak."),

    Range("TOPS/W", "TOPS per watt",
          {"TinyML / IoT": (0.01, 100.0), "Edge AI": (2.0, 30.0),
           "Embedded / Industrial": (1.0, 20.0),
           "Server / Datacenter": (0.2, 10.0),
           "Automotive / ADAS": (1.0, 15.0)},
          "Compute per watt. Higher is generally better.",
          "Board, chip and system power give different answers.",
          metric_key="Peak TOPS / Compute power (W)",
          boundary_note="WIDER on our side: the divisor is accelerator power "
                        "including its idle, where a vendor may quote the chip "
                        "alone. Expect our figure to sit low."),

    Range("Latency", "ms per inference",
          {"TinyML / IoT": (1.0, 500.0), "Edge AI": (2.0, 50.0),
           "Embedded / Industrial": (1.0, 30.0),
           "Server / Datacenter": (0.1, 100.0),
           "Automotive / ADAS": (1.0, 20.0)},
          "Input available to output produced.",
          "Report p50/p95/p99; batch size changes it sharply.",
          metric_key="Latency (ms)",
          boundary_note="WIDER on our side: ours is the AI pipeline including "
                        "host preprocessing and post-processing, where an "
                        "accelerator figure may be tensor-in to tensor-out."),

    Range("Throughput", "inferences/s",
          {"TinyML / IoT": (0.1, 100.0), "Edge AI": (30.0, 500.0),
           "Embedded / Industrial": (100.0, 2000.0),
           "Server / Datacenter": (1000.0, 1000000.0),
           "Automotive / ADAS": (30.0, 2000.0)},
          "Sustained completed inferences per second.",
          "High throughput can come from batching rather than speed.",
          metric_key="Delivered throughput (inf/s)",
          boundary_note="DELIVERED rate - what the system actually completes, "
                        "capped by what arrives. The model also reports a "
                        "single-job rate (one over the latency) and a pipeline "
                        "capacity, and a published throughput figure is "
                        "usually one of those two rather than this one."),

    Range("Accuracy", "%",
          {"TinyML / IoT": (70.0, 98.0), "Edge AI": (80.0, 99.0),
           "Embedded / Industrial": (90.0, 99.9),
           "Server / Datacenter": None,      # model-dependent
           "Automotive / ADAS": None},       # task-level reliability
          "Task quality after quantisation and deployment.",
          "Only comparable on an identical dataset and preprocessing.",
          metric_key="Deployment accuracy (%)",
          boundary_note="Same boundary, but comparability requires the same "
                        "model and dataset - so this is a plausibility check "
                        "and never a score."),

    Range("Memory bandwidth", "GB/s",
          {"TinyML / IoT": (0.001, 1.0), "Edge AI": (5.0, 100.0),
           "Embedded / Industrial": (50.0, 400.0),
           "Server / Datacenter": (500.0, 5000.0),
           "Automotive / ADAS": (100.0, 1000.0)},
          "Ability to feed weights and activations to the compute.",
          "On-chip SRAM bandwidth is not external DRAM bandwidth.",
          metric_key="Effective bandwidth (GB/s)",
          boundary_note="Same boundary: external memory in both cases."),

    Range("Utilisation", "% of peak",
          {"TinyML / IoT": (10.0, 70.0), "Edge AI": (40.0, 85.0),
           "Embedded / Industrial": (50.0, 90.0),
           "Server / Datacenter": (30.0, 90.0),
           "Automotive / ADAS": (50.0, 90.0)},
          "Actual operations over theoretical peak.",
          "Varies enormously by layer; a whole-network figure hides that.",
          metric_key="Arithmetic utilisation (%)",
          boundary_note="DEFINITION TRAP. The model also reports a 'Compute "
                        "utilisation (%)' which is compute time over core "
                        "time - how much of the engine's busy period is "
                        "arithmetic rather than waiting - and that is a "
                        "different quantity entirely. Reading the published "
                        "band against it made four of nine references look "
                        "abnormal when they were not."),
]

# Domain-level context, for the header of a report.
DOMAIN_CONTEXT = {
    "TinyML / IoT": ("Minimum energy, always on", "1 mW - 500 mW",
                     "Peak TOPS is often meaningless at this scale."),
    "Edge AI": ("Real-time inference on a limited power budget", "1 W - 15 W",
                "Memory is usually what limits real performance."),
    "Embedded / Industrial": ("Stable multi-model throughput, deterministic",
                              "10 W - 75 W",
                              "A good average frame rate can hide the "
                              "worst-case latency."),
    "Server / Datacenter": ("Throughput at scale, cost per inference",
                            "75 W - 700 W+",
                            "Batch performance is not interactive latency."),
    "Automotive / ADAS": ("Low-latency safety-critical perception",
                          "30 W - 300 W+",
                          "Peak compute does not guarantee safe real-time "
                          "behaviour."),
}

# Definition, formula, why it matters, good practice, common mistake.
METRIC_GUIDE = {
    "TOPS": (
        "Peak or measured neural-network operations per second.",
        "Peak: MACs per cycle x clock x ops per MAC.",
        "Allows a rough comparison of arithmetic class.",
        "State precision, dense or sparse, batch size, and peak or measured.",
        "Advertising peak TOPS without memory, latency or accuracy."),
    "TOPS/W": (
        "AI compute per watt.",
        "Measured TOPS divided by measured power.",
        "Decides whether a design fits a thermal or battery budget.",
        "Say whether the power is chip, module, board or system.",
        "Dividing chip-only TOPS by board-level power."),
    "Latency": (
        "End-to-end time for one inference.",
        "Output valid time minus input start time.",
        "Real-time control, robotics and ADAS are governed by it.",
        "Fixed input size, one clock, and include pre- and post-processing.",
        "Quoting cycles inside the array while excluding the host."),
    "Throughput": (
        "Completed inferences per second.",
        "Images divided by elapsed seconds.",
        "Shows sustained capacity under a continuous workload.",
        "Keep single-image latency and streaming throughput apart.",
        "Using batch throughput to imply low single-sample latency."),
    "Accuracy": (
        "Task quality after deployment.",
        "Top-1 for classification, mAP for detection.",
        "A fast but inaccurate accelerator is not useful.",
        "Same dataset, preprocessing and quantisation on both sides.",
        "Changing preprocessing between the software and hardware runs."),
    "Memory bandwidth": (
        "Rate of moving weights, activations and outputs.",
        "Bytes transferred divided by elapsed seconds.",
        "Most accelerator performance is limited by data movement.",
        "Compute arithmetic intensity and find which layers are bound by it.",
        "Ignoring weight and activation reads when claiming arithmetic throughput."),
    "Utilisation": (
        "Fraction of peak compute actually used.",
        "Actual operations over peak operations.",
        "Shows the quality of scheduling, tiling and dataflow.",
        "Measure per layer - it varies enormously between them.",
        "Reporting the best layer's utilisation as the whole network's."),
}

DOMAIN_OF_APPLICATION = {
    "drone": "Edge AI", "smart_camera": "Edge AI", "mobile_ai": "Edge AI",
    "robot": "Edge AI",
    "industrial_vision": "Embedded / Industrial",
    "medical": "Embedded / Industrial",
    "autonomous_vehicle": "Automotive / ADAS",
    "ai_inference": "Server / Datacenter",
    "llm_service": "Server / Datacenter",
}


def _value(metrics, key):
    # Arithmetic utilisation - operations achieved over operations possible -
    # is a property of the engine, and is NOT the compute share of core time
    # that the model reports under a similar name.
    if key == "Arithmetic utilisation (%)":
        return metrics.get("Engine arithmetic utilisation (%)")
    if key == "Peak TOPS / Compute power (W)":
        p = metrics.get("Compute power (W)", 0.0)
        return metrics.get("Peak TOPS", 0.0) / p if p > 0 else None
    return metrics.get(key)


# "LOW" reads as a failing grade. Being under a typical band is not a failure -
# a design that meets its latency requirement on less peak compute than usual
# is doing something right, and the word should not say otherwise. Only the
# REQUIREMENT decides whether a product can ship.
VERDICT_WORDS = {
    "BELOW": "Below Typical Range",
    "within": "Within Typical Range",
    "ABOVE": "Above Typical Range",
    "no published band": "No Published Range",
    "not computed": "Not Computed",
}


def verdict(value, band):
    if band is None:
        return "no published band", ""
    lo, hi = band
    if value is None:
        return "not computed", ""
    if value < lo:
        return "BELOW", f"below a typical {lo:g}"
    if value > hi:
        return "ABOVE", f"above a typical {hi:g}"
    return "within", ""


def interpret(app_key: str, config, duration_s: float = 60.0,
              domain: Optional[str] = None, reference=None) -> None:
    """Read a simulation result against three things that answer differently.

    The requirement says whether it ships. The reference says whether it is
    better than where the course starts. The domain band says whether it is
    ordinary. None of the three subsumes the others.
    """
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    from .designs import designs_for

    app = APPLICATION_LIBRARY[app_key]
    dom = domain or DOMAIN_OF_APPLICATION.get(app_key, "Edge AI")
    goal, envelope, risk = DOMAIN_CONTEXT[dom]
    res = evaluate_system(app, config)
    m = res.metrics

    if reference is None:
        try:
            reference = designs_for(app_key)[0].config
        except Exception:
            reference = None
    ref_m = evaluate_system(app, reference).metrics if reference is not None else None
    is_ref = reference is not None and reference == config

    print(f"\n{LINE}")
    print(f" RESULT INTERPRETATION - {app.name}")
    print(LINE)
    print(f"  domain           {dom}")
    print(f"  optimising for   {goal}")
    print(f"  typical envelope {envelope}")
    print(f"  usual risk       {risk}")

    # --- 1. the requirement: does it ship ---------------------------------
    print(f"\n  -- 1. requirements: does it ship? -------------------------")
    for name, ok in res.gate.items():
        print(f"    {name:<18s}{'PASS' if ok else 'FAIL'}")
    print(f"    {'':<18s}{sum(1 for o in res.gate.values() if o)}"
          f"/{len(res.gate)}")

    # --- 2. the reference: better or worse than where we start ------------
    print(f"\n  -- 2. against the starting point ------------------------")
    if ref_m is None:
        print("    No starting point defined for this application.")
    elif is_ref:
        print("    This IS the starting point.")
    else:
        h = f"    {'':<20s}{'this design':>14s}{'reference':>13s}{'change':>10s}"
        print(h)
        for label, key, lower_better in (
                ("latency (ms)", "Latency (ms)", True),
                ("throughput (/s)", "Throughput (inf/s)", False),
                ("power (W)", "System power (W)", True),
                ("cost (USD)", "System cost (USD)", True),
                ("accuracy (%)", "Deployment accuracy (%)", False)):
            a, b = m[key], ref_m[key]
            chg = (a / b - 1) * 100 if b else 0.0
            better = (a < b) if lower_better else (a > b)
            tag = "" if abs(chg) < 0.5 else ("  better" if better else "  worse")
            print(f"    {label:<20s}{a:>14.2f}{b:>13.2f}{chg:>+9.1f}%{tag}")

    # --- 3. the domain band: is it ordinary -------------------------------
    print(f"\n  -- 3. against the typical domain range --------------------")
    head = (f"    {'metric':<20s}{'value':>13s}{'typical band':>20s}   "
            f"interpretation")
    print(head)
    flagged = []
    for r in RANGES:
        band = r.bands.get(dom)
        v = _value(m, r.metric_key)
        state, why = verdict(v, band)
        vs = "-" if v is None else f"{v:,.3g}"
        bs = "-" if band is None else f"{band[0]:g} - {band[1]:g}"
        print(f"    {r.metric:<20s}{vs:>13s}{bs:>20s}   "
              f"{VERDICT_WORDS[state]}")
        if state in ("BELOW", "ABOVE"):
            flagged.append((r, v, why))

    # --- reading the three together ---------------------------------------
    print(f"\n  -- reading the three together ------------------------------")
    ships = res.passes
    ordinary = not flagged
    if ships and ordinary:
        print("    Ships, and ordinary on every axis. Being ordinary is not a")
        print("    recommendation - it means nothing here needs explaining.")
    elif ships and not ordinary:
        print("    Ships, but sits outside a typical band. That is allowed:")
        print("    the requirement is the product's, the band is the market's,")
        print("    and a design can be unusual and correct.")
    elif not ships and ordinary:
        print("    Does NOT ship, though every figure is ordinary for the")
        print("    domain. The band cannot see which requirement failed - look")
        print("    at section 1.")
    else:
        print("    Does not ship, and sits outside a typical band. The two may")
        print("    or may not have the same cause; check section 1 first.")

    for r, v, why in flagged:
        print(f"\n    {r.metric}: {v:,.3g} {r.unit}, {why}.")
        print(f"      This is not a failure by itself. Only the requirements "
              f"in section 1")
        print(f"      decide whether a product can ship.")
        print(f"      {r.how_to_read}")
        if r.boundary_note.startswith(("WIDER", "DEFINITION")):
            print(f"      BOUNDARY: {r.boundary_note}")
        guide = METRIC_GUIDE.get(r.metric)
        if guide:
            print(f"      common mistake: {guide[4]}")

    print(f"\n    what limits it   {res.bound_by} bound"
          + ("   - arithmetic is not the constraint"
             if res.bound_by == "memory" else
             "   - data movement is not the constraint"
             if res.bound_by == "compute" else ""))

    print("\n  The bands are a synthesis of published references, not")
    print("  measurements, and they describe ACCELERATORS while this model")
    print("  computes whole systems. A value outside a band is a prompt to")
    print("  look, never a score - and nothing here changed a computed value.")
    print(LINE)


def explain_metric(name: str) -> None:
    """Definition, formula, why it matters, good practice, common mistake."""
    guide = METRIC_GUIDE.get(name)
    if guide is None:
        print(f"  No guide for '{name}'. Available: {', '.join(METRIC_GUIDE)}")
        return
    definition, formula, why, good, mistake = guide
    print(f"\n{LINE}")
    print(f" {name}")
    print(LINE)
    print(f"  definition      {definition}")
    print(f"  formula         {formula}")
    print(f"  why it matters  {why}")
    print(f"  good practice   {good}")
    print(f"  common mistake  {mistake}")
    band = next((r for r in RANGES if r.metric == name), None)
    if band:
        print(f"\n  typical bands")
        for dom in DOMAINS:
            b = band.bands.get(dom)
            print(f"    {dom:<24s}" + ("-" if b is None
                                       else f"{b[0]:g} - {b[1]:g} {band.unit}"))
        print(f"\n  caveat          {band.caveat}")
    print(LINE)


def from_measurement(clock_mhz: float, cycles_per_image: float,
                     images: int, elapsed_ms: float, ops_per_image: float,
                     power_w: float, label: str = "measurement") -> dict:
    """Turn raw board measurements into the derived metrics.

    Takes what a student can actually read off a board - a clock, a cycle
    count, an image count, a stopwatch and a power meter - and computes the
    rest, so that the derived figures come from one arithmetic rather than from
    several people's habits.
    """
    latency_ms = cycles_per_image / (clock_mhz * 1e6) * 1e3 if clock_mhz else 0.0
    throughput = images / (elapsed_ms / 1e3) if elapsed_ms > 0 else 0.0
    measured_tops = ops_per_image * throughput / 1e12
    tops_per_w = measured_tops / power_w if power_w > 0 else 0.0
    out = {
        "label": label,
        "Latency (ms)": latency_ms,
        "Throughput (inf/s)": throughput,
        "Measured TOPS": measured_tops,
        "TOPS/W": tops_per_w,
        "Measured GOPS": measured_tops * 1e3,
    }
    print(f"\n{LINE}")
    print(f" MEASUREMENT - {label}")
    print(LINE)
    print(f"  clock            {clock_mhz:,.0f} MHz")
    print(f"  cycles/image     {cycles_per_image:,.0f}")
    print(f"  images           {images:,}")
    print(f"  elapsed          {elapsed_ms:,.1f} ms")
    print(f"  power            {power_w:,.2f} W\n")
    print(f"  latency          {latency_ms:,.3f} ms   from cycles and clock")
    print(f"  throughput       {throughput:,.1f} /s   from images and elapsed")
    print(f"  measured TOPS    {measured_tops:,.6g}")
    print(f"  TOPS/W           {tops_per_w:,.6g}")
    print("\n  Latency here is the ACCELERATOR's - cycles over clock - while")
    print("  throughput comes from wall-clock elapsed time and therefore")
    print("  includes the host. They are not two views of one number, and")
    print("  one over the latency will not give the throughput.")
    print(LINE)
    return out
