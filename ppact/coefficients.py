"""
ppact.coefficients - every number that was chosen rather than derived

A model contains two kinds of number. Some follow from something else: a die
area from a MAC count and a cell size, a transfer time from bytes and a
bandwidth. Others were picked because they seemed about right. Both look
identical in the source, and the difference decides how much weight a result
can carry.

This registry lists the second kind. Each entry records:

    value        what is used
    source       MEASURED | DATASHEET | LITERATURE | ENGINEERING_ESTIMATE
    confidence   HIGH | MEDIUM | LOW
    editable     whether a student is expected to change it and see what happens
    depends_on   which conclusions rest on it

The last field is the one worth reading. A coefficient that nothing depends on
is harmless whatever its value; one that a headline result turns on has to be
declared, because a conclusion is only as firm as the weakest number under it.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

SOURCES = ("MEASURED", "DATASHEET", "LITERATURE", "ENGINEERING_ESTIMATE")
CONFIDENCES = ("HIGH", "MEDIUM", "LOW")


@dataclass(frozen=True)
class Coefficient:
    name: str
    module: str
    value: float
    unit: str
    source: str
    confidence: str
    editable: bool
    note: str
    depends_on: str = ""


COEFFICIENTS: List[Coefficient] = [
    Coefficient(
        "DUAL_MEMORY_CONTENTION", "system", 0.12, "fraction of bandwidth",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Extra loss when two engines issue concurrently, beyond what the "
        "bandwidth arithmetic already accounts for. No bank, row-buffer or "
        "arbitration model stands behind it - it is a correction term, not a "
        "mechanism.",
        "THE SIGN FLIP: whether a dual-accelerator design is SLOWER than a "
        "single one on a narrow bus depends entirely on this number. Set it "
        "to zero and parallel execution wins everywhere, though by much less "
        "on LPDDR than on HBM."),
    Coefficient(
        "PARALLEL_SPLIT_EFFICIENCY", "system", 0.85, "fraction",
        "ENGINEERING_ESTIMATE", "MEDIUM", True,
        "Partitioning, synchronisation and merge cost when one job's "
        "arithmetic is divided between two engines.",
        "How much of a 2x speedup a balanced split actually delivers. Does "
        "not change the direction of any conclusion."),
    Coefficient(
        "DUAL_DISPATCH_US", "system", 60.0, "microseconds per job",
        "ENGINEERING_ESTIMATE", "MEDIUM", True,
        "Cost of handing a job between two accelerators.",
        "Why an unsplit parallel pair is marginally slower than a single "
        "engine."),
    Coefficient(
        "NPU_PREPROCESS_DISPATCH_US", "preprocess", 90.0, "microseconds per call",
        "ENGINEERING_ESTIMATE", "MEDIUM", True,
        "Fixed cost of handing a frame to an accelerator for preprocessing.",
        "THE BREAK-EVEN FRAME SIZE: below roughly 300k total pixels, "
        "offloading preprocessing costs more than it saves."),
    Coefficient(
        "NPU_PREPROCESS_AREA_UPLIFT", "preprocess", 0.08, "fraction of die area",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Extra silicon for preprocessing support on an accelerator that did "
        "not have it.", "Area and cost of NPU-assisted preprocessing."),
    Coefficient(
        "NPU_PREPROCESS_POWER_UPLIFT", "preprocess", 0.06, "fraction of static power",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Extra leakage on an accelerator that carries preprocessing hardware "
        "it would not otherwise need.",
        "The power cost of NPU-assisted preprocessing, and therefore whether "
        "offloading is worth it on a battery-powered product."),
    Coefficient(
        "ISP_PIXELS_PER_SECOND", "preprocess", 2.0e9, "pixels per second",
        "DATASHEET", "MEDIUM", True,
        "Throughput of a modern multi-camera ISP pipeline.",
        "Whether an ISP keeps up with the frame rate, and therefore whether "
        "any of its work is exposed to the latency."),
    Coefficient(
        "ISP_AREA_MM2", "preprocess", 3.2, "mm2 at the reference node",
        "ENGINEERING_ESTIMATE", "MEDIUM", True,
        "Silicon for a fixed-function camera block.",
        "The area and cost of choosing an ISP-assisted design."),
    Coefficient(
        "ISP_STATIC_POWER_W", "preprocess", 0.30, "watts",
        "ENGINEERING_ESTIMATE", "MEDIUM", True,
        "Leakage of a fixed-function camera block, drawn whether or not a "
        "frame is being processed.",
        "Why an ISP-assisted design costs power even when idle, and part of "
        "why adding one is not free on a drone."),
    Coefficient(
        "ISP_ENERGY_PJ_PER_PIXEL", "preprocess", 55.0, "pJ per pixel",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Dynamic energy of ISP processing.",
        "Why an ISP costs energy even when its latency is fully hidden."),
    Coefficient(
        "SYSTOLIC_PERIPHERY", "compute", 1.15, "multiplier on die area",
        "ENGINEERING_ESTIMATE", "MEDIUM", False,
        "Control, sequencing and interface logic around a systolic array.",
        "Accelerator die area, and through it cost."),
    Coefficient(
        "weight_read_factor", "application", 1.05, "reads per token",
        "ENGINEERING_ESTIMATE", "MEDIUM", True,
        "How many times an LLM's weights are actually fetched to produce one "
        "token. One is the ideal; the excess is cache behaviour, tensor-"
        "parallel boundaries and kernel inefficiency, NOT reuse - decode has "
        "none.",
        "LLM token rate, and through it the case for wide memory. At 2.0 "
        "instead of 1.05 an LLM appears to need twice the bandwidth it does."),
    Coefficient(
        "efficient_work_ms", "compute", 3.0, "ms at peak rate (edge GPU)",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "How much work an engine needs before it reaches its stated "
        "utilisation. 3 ms for a general-purpose GPU, 0.4 for a systolic NPU: "
        "a GPU has more to schedule and drains before it fills.",
        "THE ABSOLUTE LATENCY SCALE. Without it an embedded GPU ran YOLOv8s at "
        "320x320 in 0.26 ms, roughly twenty times faster than such a part "
        "measures, and every GPU-to-NPU comparison inherited the error."),
    Coefficient(
        "framework_overhead_ms", "compute", 1.5, "ms per inference (edge GPU)",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Graph launch, runtime and driver cost per inference. 1.5 ms for a GPU "
        "stack, 0.25 for an NPU runtime.",
        "Small-model latency, where it is a large share of the total."),
    Coefficient(
        "module_idle_power_w", "compute", 1.4, "watts (128x128 NPU module)",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Power a MODULE draws doing nothing - die, DRAM, PMIC and interface - "
        "as distinct from die leakage. A part rated '25 TOPS, 5 W' states a "
        "module figure.",
        "Whether a dual-module design looks more or less efficient than the "
        "GPU it replaces. Comparing a module rating against a die leakage "
        "figure mixes two boundaries."),
    Coefficient(
        "BOUND_STRENGTH_THRESHOLDS", "system", 4.0,
        "compute/memory ratio at the strong boundary",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Where a design stops being weakly bound and starts being strongly "
        "bound. The ratio itself is computed; which of five names it gets is "
        "a CHOICE of threshold - 4.0 and 1.25 either side of one, mirrored "
        "below.",
        "The label a student reads, and nothing else. A design at 1.61 is "
        "called weakly compute-bound rather than compute-bound because it "
        "gains 26% from a faster memory, and that boundary was placed by hand "
        "rather than derived."),
    Coefficient(
        "HOST_BALANCE_BAND", "system", 0.25, "fraction either side of equal",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "How far from equal the host's arithmetic and transfers may be before "
        "it is called limited by one of them rather than balanced.",
        "Which of three states a host is reported in. A band of zero would "
        "call a ratio of 1.02 memory-limited and send a student shopping for "
        "memory; a very wide one would call everything balanced and say "
        "nothing."),
    Coefficient(
        "HOST_MEMORY_OVERLAP", "system", 0.70, "fraction hidden",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "How much of the host's own memory traffic is hidden behind its "
        "arithmetic. Preprocessing is sequential and prefetches well, which "
        "argues for a high figure; cache misses on a shared bus argue for a "
        "lower one.",
        "The host's exposed wait, and therefore whether a design is limited "
        "by its CPU or by the bus feeding it. Tested at 0.70, 0.85 and 0.92 - "
        "no starting-point design changes verdict across that range, so nothing "
        "here rests on the exact value."),
    Coefficient(
        "LLM_SINGLE_STREAM_SERVING_EFFICIENCY", "system", 0.45,
        "fraction of the ceiling, SINGLE-STREAM DECODE ONLY",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "What a serving stack delivers against the memory-bound ceiling for "
        "text workloads: scheduler, sampling, detokenisation, framework "
        "dispatch and memory the arithmetic does not see. An allowance for all "
        "of them together, not a model of any.",
        "EVERY LLM TOKEN RATE, and it CANNOT BE PINNED from what is public. "
        "Two independent deployments - an 8B model on one card at 40-60 "
        "tokens per second, and a 32B model on four cards at 60 - imply 0.28 "
        "and 0.32 if their weights are FP8, or 0.54 and 0.64 if FP16. Neither "
        "source states the precision. 0.55 sits at the FP16 end; if the "
        "figures are FP8, which is the likelier deployment for both parts, "
        "this model overstates every LLM token rate by about 1.7x. OPEN."),
    Coefficient(
        "background_power_w", "memory", 5.0, "watts per HBM3E stack",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Power drawn regardless of traffic: refresh across every die, the PHY "
        "and I/O termination. 0.15 W for LPDDR5, 0.85 for GDDR6, 5.0-7.5 for "
        "HBM stacks.",
        "WHETHER HBM COSTS POWER AT ALL. With this term at zero the model said "
        "a drone swapping LPDDR for HBM would draw 8.7% LESS power, because "
        "HBM moves a bit for 3.9 pJ against 5.0. Per bit that is true; per "
        "second sitting there it is not, and a design that is not moving many "
        "bits pays the second figure."),
    Coefficient(
        "HBM4 bandwidth_efficiency", "memory", 0.88, "fraction",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Controller efficiency assumed for HBM4, against 0.85 for HBM3E. The "
        "reasoning is that 32 channels absorb conflicts better than 16 - "
        "plausible, unmeasured.",
        "THE EQUAL-BANDWIDTH COMPARISON: the 3.5% effective-bandwidth edge "
        "HBM4 shows at matched peak comes entirely from this number, not from "
        "the wider interface. Set both to 0.85 and the two match exactly."),
    Coefficient(
        "HBM stack cost", "memory", 112.08, "USD per 24GB stack",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Silicon plus interposer, advanced package and assembly-and-test, over "
        "stack yield. Built from a wafer price and a die area that are both "
        "contract-dependent and not publicly verifiable.",
        "EVERY HBM COST COMPARISON. Quoted with a cost index alongside so a "
        "comparison survives the dollar figure being wrong."),
    Coefficient(
        "bandwidth_efficiency", "memory", 0.72, "fraction (LPDDR5)",
        "LITERATURE", "MEDIUM", True,
        "Share of pin-rate bandwidth a controller actually delivers. GDDR6 "
        "0.80, HBM3E 0.85.",
        "The roofline ridge point, and therefore which designs are memory "
        "bound at all."),
    Coefficient(
        "quantisation loss table", "accuracy", 1.0, "percentage points (CNN, PTQ)",
        "LITERATURE", "MEDIUM", True,
        "Accuracy lost to INT8 conversion, by model family and method. See "
        "ppact.accuracy for the full table.",
        "WHICH ENGINES CAN SHIP: the medical case turns on whether an INT8 "
        "pipeline fits inside a 0.5 pp budget."),
    Coefficient(
        "platform_premium", "compute", 1.30, "multiplier (datacenter GPU)",
        "ENGINEERING_ESTIMATE", "LOW", True,
        "Toolchain, drivers, framework coverage and support, priced into the "
        "part. 1.05 edge NPU, 1.15 mobile GPU.",
        "GPU cost relative to an accelerator of the same die area."),
]

BY_NAME: Dict[str, Coefficient] = {c.name: c for c in COEFFICIENTS}


def print_coefficients(only_load_bearing: bool = False) -> None:
    """List the chosen numbers, loudest first.

    A conclusion that rests on a LOW-confidence estimate is not wrong, but it
    is a different kind of statement from one that falls out of the arithmetic,
    and a student should be able to tell which they are looking at.
    """
    line = "=" * 78
    print(line)
    print(" EMPIRICAL COEFFICIENTS")
    print(line)
    print("  Numbers that were chosen, not derived. Everything else in the")
    print("  model follows from something; these are where judgement entered.\n")
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    for c in sorted(COEFFICIENTS, key=lambda x: (order[x.confidence], x.module)):
        # A dependency written in capitals is one a headline result turns on.
        load_bearing = c.depends_on[:4].isupper() and len(c.depends_on) > 4
        if only_load_bearing and not load_bearing:
            continue
        flag = "  <- a headline result turns on this" if load_bearing else ""
        print(f"  {c.name}  ({c.module}){flag}")
        print(f"    value      {c.value:g} {c.unit}")
        print(f"    source     {c.source}, confidence {c.confidence}, "
              f"{'editable' if c.editable else 'structural'}")
        print(f"    what it is {c.note}")
        if c.depends_on:
            print(f"    supports   {c.depends_on}")
        print()


def provenance(name: str) -> str:
    """A one-line tag for a screen: is this derived or assumed?"""
    c = BY_NAME.get(name)
    if c is None:
        return "model-derived"
    return f"assumption ({c.confidence.lower()} confidence)"
