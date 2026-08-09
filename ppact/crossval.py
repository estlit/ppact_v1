"""
ppact.crossval - external cases, split so that none of them can be fitted twice

Internal tests find errors inside the model. External cases find terms that are
not in it at all - which is what happened when a published deployment figure
showed the model producing 93% of a memory ceiling that no real system reaches.
A whole serving stack was missing and nothing inside could have noticed.

THE SPLIT THAT MAKES THIS WORTH DOING
-------------------------------------
    CALIBRATION   used to set coefficients. Agreement here proves nothing;
                  the model was fitted to it.
    HOLDOUT       never used to set anything. Agreement here is the only
                  evidence in the project that is not circular.
    CHALLENGE     outside what the model can express. Expected to fail, and
                  the failures rank what to build next.

A case cannot move from HOLDOUT to CALIBRATION quietly. If one is used to
choose a value it becomes calibration permanently, and its earlier holdout
result is void.

THREE KINDS OF CHECK
--------------------
    ABSOLUTE    conditions and boundary clear enough to compare numbers
    RATIO       only a before/after ratio is public
    DIRECTION   structure known, no usable quantity - check the sign only

Tolerances differ by metric because the underlying uncertainties do. Applying
one figure to bandwidth arithmetic and to a power claim would make one of them
meaningless.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

LINE = "=" * 84

# Per-metric tolerance. Wide is not slack - it is the uncertainty in the
# published figure, and pretending otherwise would turn a pass into a fiction.
TOLERANCE_PCT = {
    "bandwidth": 5.0,
    "capacity": 5.0,
    "memory_ceiling": 5.0,
    "throughput": 30.0,
    "latency": 30.0,
    "power": 40.0,
    "perf_per_watt": 35.0,
    "cost": None,          # never a pass/fail criterion
    "accuracy": None,      # only comparable on an identical model and dataset
}

STATUSES = (
    "Aligned",                    # boundary matches, inside tolerance
    "Boundary Review Required",   # looks comparable and is not yet
    "Directionally Aligned",      # sign right, absolute check impossible
    "Deviation Explained",        # outside tolerance, cause decomposed
    "Calibration Candidate",      # a missing term or coefficient found
    "Boundary Mismatch",          # the comparison cannot be made
    "Model Extension Required",   # outside the model's scope
)

# A note on "Boundary Review Required". It was added after a cooling case was
# marked Aligned because a power density fell under a passive limit. The vendor
# whose product it was recommends strong airflow over that same module and
# throttles the chips at 100 C. The arithmetic was right and the conclusion did
# not follow: a thermal outcome depends on heatsink area and resistance,
# ambient temperature, natural against forced convection, chassis, sustained
# against burst load, junction temperature and the host's own heat, and a
# single watts-per-square-millimetre limit represents none of them. A limit
# that happens to admit a vendor's figure has not confirmed anything.

# CORROBORATION is a fourth set, not a second kind of holdout. When one source
# makes several claims and one of them is used to fit a coefficient, the others
# are not independent - they share every assumption the source made. Calling
# them holdout would overstate what agreement with them shows.
SETS = ("CALIBRATION", "HOLDOUT", "CORROBORATION", "CHALLENGE")


# ==============================================================================
# Metric provenance
# ==============================================================================
#
# A rule added after a deviation was reported against a library field the model
# never reads. Before an external claim can be compared with anything, the
# chain from the claim to the function that consumes it has to be written down.
# If it cannot be, no deviation may be reported - the comparison would be
# measuring a field rather than a model.

METRIC_PROVENANCE = {
    "module average power": (
        "module idle + utilisation x dynamic + interface",
        "Compute power (W)",
        "evaluate_system"),
    "system power": (
        "compute + memory + cpu + static, over latency",
        "System power (W)",
        "evaluate_system"),
    "memory ceiling": (
        "effective bandwidth / bytes per job",
        "Effective bandwidth (GB/s), DRAM traffic (MB)",
        "evaluate_system"),
    "delivered token rate": (
        "ideal core + serving overhead, then one over interval",
        "Throughput (inf/s)",
        "evaluate_system, simulate"),
    "peak arithmetic rate": (
        "MAC array x clock x 2, derated by node",
        "Peak TOPS",
        "evaluate_system"),
}

# Fields that exist in the library but are NOT what a module-boundary claim
# should be compared against. Named so the mistake cannot be repeated quietly.
NOT_COMPARABLE_TO_MODULE_CLAIMS = (
    "static_power_w",       # silicon leakage; unused when a module idle exists
    "module_max_power_w",   # a design limit, not an operating figure
)


@dataclass
class CrossCase:
    cid: str
    title: str
    grade: str                    # A / A- / B+ / B / C+ / C / D
    dataset: str                  # CALIBRATION | HOLDOUT | CHALLENGE
    check_type: str               # ABSOLUTE | RATIO | DIRECTION
    metric: str                   # key into TOLERANCE_PCT
    conditions: str               # what the published figure was measured under
    published: Optional[float]
    unit: str
    boundary_published: str
    boundary_model: str
    estimated_inputs: str         # what WE had to invent to run it
    status: str
    note: str
    modelled: Optional[float] = None
    used_for: str = ""            # which coefficient, if calibration
    independence: str = ""        # for corroboration: how independent it is not


CASES: List[CrossCase] = [
    # ---------------------------------------------------------- CALIBRATION
    CrossCase(
        "EXT-006", "Memory-bound decode arithmetic", "C", "CALIBRATION",
        "ABSOLUTE", "memory_ceiling",
        "A 16 GB model read once per token, at 300 GB/s and at 1.5 TB/s.",
        19.0, "tokens/s",
        "bytes over bandwidth, nothing else",
        "the model's memory-limited ceiling",
        "None - both sides are arithmetic.",
        "Aligned",
        "Matched to within 1.3%. This confirms the roofline and nothing "
        "beyond it: a published figure that is itself a calculation cannot "
        "test anything the calculation omits.",
        modelled=18.75, used_for="none - confirmed an existing term"),

    CrossCase(
        "EXT-005", "Single-card 8B deployment", "C+", "CALIBRATION",
        "ABSOLUTE", "throughput",
        "Llama-class 8B, single user, about 1.5 TB/s. Precision NOT stated.",
        50.0, "tokens/s",
        "delivered single-stream rate",
        "throughput after the serving-overhead term",
        "Weight precision, context length, sampling and framework - none is "
        "published, and the first three change the answer by more than the "
        "tolerance.",
        "Calibration Candidate",
        "Found the missing term. The model produced 93% of the ceiling; no "
        "deployment does. Used to introduce the serving-overhead term, so "
        "agreement here is by construction and proves nothing.",
        used_for="LLM_SINGLE_STREAM_SERVING_EFFICIENCY"),

    CrossCase(
        "EXT-001", "Four-card 32B deployment", "A-", "CALIBRATION",
        "ABSOLUTE", "throughput",
        "EXAONE-class 32B, four cards tensor-parallel, 4K context. Precision "
        "NOT stated.",
        60.0, "tokens/s",
        "decode throughput at a stated context",
        "throughput after the serving-overhead term",
        "Precision, batch size, tensor-parallel communication cost.",
        "Deviation Explained",
        "CONTAMINATED. This was intended as holdout and was used at 3.30.0 to "
        "bracket the serving coefficient before the split existed, so it is "
        "calibration now and permanently. Its throughput result carries no "
        "independent weight. Its performance-per-watt claim was NOT used and "
        "stays available as holdout - listed separately below.",
        used_for="LLM_SINGLE_STREAM_SERVING_EFFICIENCY (bracketing)"),

    # -------------------------------------------------------------- HOLDOUT
    CrossCase(
        "EXT-001-PW", "Four-card 32B, performance per watt", "A-", "HOLDOUT",
        "RATIO", "perf_per_watt",
        "2.25x performance per watt against a GPU platform that is not fully "
        "specified.",
        2.25, "x versus GPU",
        "rack or server comparison - exact boundary unclear",
        "system power over throughput, both engines at the same boundary",
        "The GPU baseline part, card counts on both sides, and whether host "
        "CPU and memory are inside the power boundary.",
        "Boundary Mismatch",
        "Not evaluated. The baseline platform is unspecified, so a ratio "
        "computed here would be against a machine of our choosing rather than "
        "theirs. Recorded as a boundary mismatch instead of producing a number "
        "that would look like agreement."),

    CrossCase(
        "EXT-010-A", "25 TOPS module, product class", "C+", "CALIBRATION",
        "ABSOLUTE", "throughput",
        "A 25 TOPS vision module, vendor-stated.",
        25.0, "TOPS",
        "peak arithmetic rate",
        "peak TOPS of the nearest library part at a comparable node",
        "Which node the real part is built on.",
        "Aligned",
        "Used to place the library's parts against a real product class. The "
        "nearest entry gives 35 TOPS at N12 - the right order, and the reason "
        "an Orin-class GPU and an 80 TOPS box were added at 3.26.0.",
        modelled=35.4, used_for="product-class placement"),

    CrossCase(
        "EXT-010-B", "25 TOPS module, typical power", "C+", "CALIBRATION",
        "ABSOLUTE", "power",
        "About 3 W typical at the MODULE boundary: silicon, regulators, "
        "memory interface and board.",
        3.0, "W",
        "module average under a typical load",
        "accelerator power, which is module idle plus dynamic",
        "The utilisation the vendor calls typical.",
        "Aligned",
        "The model gives 1.5 W at low load and 3.0 W at high load on the "
        "nearest part - the published typical figure sits inside the range the "
        "model spans rather than at a point it must hit.",
        modelled=3.0, used_for="module power profile"),

    CrossCase(
        "EXT-010-C", "25 TOPS module, operating range", "C+", "CORROBORATION",
        "ABSOLUTE", "power",
        "A 2-5 W operating range from the same vendor material as the typical "
        "figure above.",
        None, "W, range 2-5",
        "module operating range",
        "accelerator power across the utilisation sweep",
        "None.",
        "Aligned",
        "The model spans 1.4 W at idle to 3.6 W at saturation, inside the "
        "published range and below the module ceiling. NOT independent "
        "validation: the same source supplied the typical figure used to place "
        "the profile, so this shows internal consistency rather than external "
        "agreement.",
        independence="Partial - same source as the calibration claim above."),

    CrossCase(
        "EXT-012", "Fanless multi-channel edge system", "B+", "HOLDOUT",
        "RATIO", "throughput",
        "123% higher multi-channel throughput than a prior platform; whole "
        "system under 30 W, fanless.",
        None, "x versus prior platform",
        "system benchmark; prior platform not identified",
        "not evaluated",
        "Everything: the prior platform, channel count, model and precision.",
        "Boundary Mismatch",
        "Two independent claims in one sentence, and '123% higher' is "
        "ambiguous between 2.23x and 1.23x. Neither can be checked without the "
        "baseline platform. Left unevaluated on purpose - guessing which "
        "reading was meant would manufacture a result."),

    CrossCase(
        "EXT-002", "Production search summarisation", "A-", "HOLDOUT",
        "DIRECTION", "power",
        "About 500M tokens/day in production at 180 W with a claimed TCO "
        "reduction of half or more.",
        None, "direction only",
        "accelerator or server - not stated",
        "direction of system power against a GPU alternative",
        "Model size, precision, concurrency and the GPU baseline.",
        "Directionally Aligned",
        "The model agrees that a fixed-function part serving a fixed token "
        "load draws less than a general-purpose GPU doing the same work. That "
        "is all this case can support; the 180 W figure has no stated "
        "boundary."),

    CrossCase(
        "EXT-PWR-MEMRYX", "Per-chip average power, independent vendor", "C+",
        "HOLDOUT", "ABSOLUTE", "power",
        "0.5-3 W per chip depending on the workload, 0.6-2 W per chip average, "
        "vendor-published.",
        1.3, "W per chip average",
        "one accelerator chip",
        "accelerator power divided by the array count",
        "Which workload the vendor averaged over.",
        "Aligned",
        "The narrowest and therefore the most usable of this vendor's claims: "
        "a chip average, with no board auxiliaries inside it. Four chips at "
        "0.6-2 W gives 2.4-8 W, which is consistent with their 6-8 W module "
        "figure sitting at the top of that span.",
        modelled=0.9),

    CrossCase(
        "EXT-PWR-MEMRYX-MODULE", "Four-chip module power, inferred", "C+",
        "HOLDOUT", "ABSOLUTE", "power",
        "6-8 W average for the four-chip M.2 module, vendor-published, and "
        "2.4-8 W inferred from the per-chip range.",
        7.0, "W",
        "M.2 module: four chips plus board auxiliaries",
        "accelerator module average power under a multi-camera load",
        "The workload, and what share of the module figure is auxiliaries "
        "rather than chips.",
        "Deviation Explained",
        "The model gives 2.5-2.7 W for a 33-35 TOPS part where the vendor "
        "publishes 6-8 W at 24 TOPS. NOT corrected: a second vendor at the "
        "same class publishes about 3 W, so the two disagree by more than the "
        "model differs from either.",
        modelled=2.7),

    CrossCase(
        "EXT-THERMAL-MEMRYX", "Cooling determines performance", "C+",
        "HOLDOUT", "DIRECTION", "power",
        "The vendor's own documentation requires each chip to stay below 100 C "
        "and states it throttles to half frequency above that, with a "
        "recommendation for strong airflow over the module.",
        None, "direction only",
        "sustained thermal operation in a host chassis",
        "the cooling compatibility gate",
        "Heatsink area and resistance, ambient temperature, chassis and "
        "airflow - none published.",
        "Directionally Aligned",
        "What this supports is that cooling GOVERNS whether the rated "
        "performance is reached, which the gate does represent. What it does "
        "NOT support is the claim this file previously made: that a 6-8 W "
        "module is passively coolable. The vendor recommends airflow for the "
        "same part. The earlier Aligned verdict came from a power density "
        "falling under a passive limit, which is arithmetic about a quantity "
        "the thermal outcome does not turn on."),

    CrossCase(
        "EXT-THERMAL-PASSIVE-CLAIM", "Passive-only operation at 6-8 W", "C",
        "HOLDOUT", "DIRECTION", "power",
        "A comparison table describes the module as fan-less with a passive "
        "heatsink; the same vendor's support documentation recommends strong "
        "airflow.",
        None, "not established",
        "unclear - the two statements describe different conditions",
        "not evaluated",
        "Everything about the thermal environment.",
        "Boundary Review Required",
        "Left unresolved on purpose. Marketing copy and support documentation "
        "disagree, and neither states an ambient temperature, a chassis or a "
        "sustained load. The model's own verdict - that 8 W over this "
        "footprint clears a passive limit - is MODEL-DERIVED and was wrongly "
        "reported as external confirmation at 3.34.0."),

    CrossCase(
        "EXT-PWR-SPREAD", "Two vendors at the same TOPS class", "C+",
        "HOLDOUT", "RATIO", "power",
        "One vendor states about 3 W typical for a 25 TOPS module; another "
        "states 6-8 W for a 24 TOPS module. Same form factor, same class.",
        2.3, "x between vendors at one TOPS class",
        "module in both cases",
        "not applicable - this measures the published record, not the model",
        "None.",
        "Boundary Mismatch",
        "THE most useful result in the holdout set, and it is not about the "
        "model at all. Two vendors at the same TOPS class differ by more than "
        "twice, so 'watts per TOPS for a 25 TOPS module' is not a quantity "
        "with a single value. Calibrating the library to either one would have "
        "been fitting to a vendor rather than to a product class, and the "
        "model sitting near the low end is within the spread rather than wrong."),

    CrossCase(
        "EXT-PWR-LADDER", "Three product classes, published power bands",
        "C+", "HOLDOUT", "RATIO", "power",
        "An M.2 edge module at 6-8 W passively cooled; an embedded GPU module "
        "at 15-60 W; a desktop or server GPU at 100-450 W. Three classes, "
        "three cooling regimes, from one comparison table.",
        39.3, "x from the smallest class to the largest",
        "device power in its intended role",
        "accelerator power with each part driven to saturation",
        "The workload each vendor averaged over - almost certainly not the "
        "same one, and each class is designed for a different size of job.",
        "Deviation Explained",
        "Ordering right, range compressed. The model spans 3.6 W to 54.7 W "
        "where the published bands span 7 to 275 - 15x against 39x - and the "
        "understatement GROWS with class size: half at the edge, a fifth at "
        "the top. A ladder is a stronger test than any single point because it "
        "cannot be satisfied by fitting one part, and this one says the "
        "library's power range is too narrow rather than misplaced. NOT "
        "corrected: three points from one comparison table, each under an "
        "unstated workload, is too thin to reshape every accelerator entry.",
        modelled=15.3),

    # ------------------------------------------------------------ CHALLENGE
    CrossCase(
        "CH-01", "Multimodal sensor fusion", "B", "CHALLENGE",
        "DIRECTION", "latency",
        "Vision and acoustic models feeding one fused decision.",
        None, "n/a", "fused decision", "not expressible",
        "everything - the architecture is outside the model",
        "Model Extension Required",
        "Two different models on two engines with a fusion stage. The parallel "
        "mode splits ONE model. Expected to fail; it ranks first among the "
        "extensions because two case-database entries need it."),

    CrossCase(
        "CH-02", "Retrieval-augmented generation", "B", "CHALLENGE",
        "DIRECTION", "latency",
        "Vector retrieval then generation, with recall and factuality targets.",
        None, "n/a", "end-to-end query", "not expressible",
        "everything - the architecture is outside the model",
        "Model Extension Required",
        "Retrieval is not a pipeline stage here, and recall at ten has no "
        "counterpart. Reporting time-to-first-token alone would imply the "
        "retrieval half had been evaluated."),

    CrossCase(
        "CH-03", "Concurrent users and tail latency", "B", "CHALLENGE",
        "DIRECTION", "latency",
        "Sixteen concurrent users with a p95 latency target.",
        None, "n/a", "p95 across users", "not expressible",
        "everything - the architecture is outside the model",
        "Model Extension Required",
        "The LLM path is single-stream. A p95 has no meaning without a "
        "distribution, and reporting a mean instead would answer a different "
        "question."),

    CrossCase(
        "CH-04", "Sensor-embedded NPU", "B", "CHALLENGE",
        "DIRECTION", "power",
        "Inference inside the image sensor, removing a separate accelerator.",
        None, "n/a", "camera product", "not expressible",
        "everything - the architecture is outside the model",
        "Model Extension Required",
        "The model has no place to put compute inside the sensor, and the "
        "interesting effects - host CPU load and network traffic - are not "
        "quantities it carries."),

    CrossCase(
        "CH-05", "Network and host offload effects", "B", "CHALLENGE",
        "DIRECTION", "power",
        "On-device analytics reducing uplink traffic and server load.",
        None, "n/a", "site or fleet", "not expressible",
        "everything - the model carries no network or server-side quantity",
        "Model Extension Required",
        "Network traffic and server-side load are outside a single-device "
        "PPACT model entirely. Listed so the boundary is explicit rather than "
        "implied by absence."),
]


def by_set() -> Dict[str, List[CrossCase]]:
    out = {k: [] for k in SETS}
    for c in CASES:
        out[c.dataset].append(c)
    return out


def print_crossval() -> None:
    grouped = by_set()
    total = len(CASES)
    print(LINE)
    print(" EXTERNAL SCENARIO CROSS-VALIDATION")
    print(LINE)
    print("  Calibration cases were used to set coefficients, so agreement")
    print("  with them is by construction. Only the holdout results carry")
    print("  independent weight, and the challenge set is expected to fail.\n")
    for name in SETS:
        items = grouped[name]
        pct = len(items) / total * 100
        print(f"  {name}  ({len(items)} of {total}, {pct:.0f}%)")
        for c in items:
            pub = f"{c.published:g} {c.unit}" if c.published is not None else "-"
            got = f"{c.modelled:g}" if c.modelled is not None else "-"
            dev = ("-" if (c.published in (None, 0) or c.modelled is None)
                   else f"{(c.modelled / c.published - 1) * 100:+.1f}%")
            tol = TOLERANCE_PCT.get(c.metric)
            print(f"    {c.cid:<12s}[{c.grade:<2s}] {c.check_type:<9s}"
                  f"{c.title[:30]:<32s}")
            print(f"      published {pub:<18s}model {got:<10s}dev {dev:<9s}"
                  f"tolerance {('n/a' if tol is None else f'{tol:g}%')}")
            print(f"      status    {c.status}")
            if c.used_for:
                print(f"      used for  {c.used_for}")
            if c.independence:
                print(f"      caution   {c.independence}")
        print()

    print("  -- what the holdout set actually says ----------------------")
    hold = grouped["HOLDOUT"]
    for c in hold:
        print(f"    {c.cid:<12s}{c.status}")
    failing = [c for c in hold if c.status in ("Deviation Explained",
                                               "Calibration Candidate")]
    mismatched = [c for c in hold if c.status == "Boundary Mismatch"]
    directional = [c for c in hold if c.status == "Directionally Aligned"]
    absolute = [c for c in hold if c.check_type == "ABSOLUTE"]
    print(f"\n    {len(hold)} holdout cases: {len(failing)} the model fails, "
          f"{len(mismatched)} cannot be compared at all,")
    print(f"    {len(directional)} support a direction only, and "
          f"{len(absolute)} allow an absolute check.")
    if not absolute:
        print("\n    HOW WEAK THIS IS, STATED PLAINLY: the holdout set provides")
        print("    no absolute-value confirmation at all. The one case that did")
        print("    was promoted to calibration, because leaving a modelling")
        print("    question unexamined to protect a clean holdout is the wrong")
        print("    trade. The cost is that nothing here independently confirms")
        print("    a number, and the set needs a source from a vendor that took")
        print("    no part in any calibration.")
    else:
        print(f"\n    WHAT THE {len(absolute)} ABSOLUTE CASE(S) SHOW: an "
              f"independent vendor")
        print("    at the same product class, used in no calibration. The model")
        print("    sits below its published figure - and below it by less than")
        print("    the two vendors differ from each other, which is the more")
        print("    useful result. Watts per TOPS at a given class is not a")
        print("    quantity with one value, so fitting to either vendor would")
        print("    have moved the model away from the other by as much.")
    print("\n    A holdout set where most cases are uncomparable is itself a")
    print("    finding: the published record rarely states the boundary a")
    print("    comparison needs.")
    print(LINE)
