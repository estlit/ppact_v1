"""
ppact.bottleneck - what is probably limiting this design, and how sure

WHY NOT JUST THE BIGGEST STATION
================================
    Host active   73.5%
    Accelerator   26.5%

does not make the host the bottleneck. The station holding the time and
the thing imposing the limit are different quantities, and across 302
review cases they disagreed in 49. A tool that names the largest bar as
the cause is right five times in six and confidently wrong the rest.

So this reasons:

    observed symptom -> supporting evidence -> candidate cause
                     -> confidence -> next experiment

and stops at CANDIDATE. Root cause stays NOT ESTABLISHED.

WHY CONFIDENCE CANNOT REACH HIGH
--------------------------------
Counterfactuals would settle most of these questions - halve a station and
watch the total. The model computes them, and they are STALE: they run
through the memory arbitration rule recorded as MEM-ARB-001, where a 3%
aggregate over-demand cuts host bandwidth by half and a faster accelerator
comes out 59% slower.

Using those numbers with a warning attached would not help. Readers take
the number and leave the warning, which this project has watched happen.
So HIGH is unreachable until MEM-D3 gives the memory model a service rate.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"

# The ceiling, and the reason for it. Not a tuning parameter: raising it
# without a valid counterfactual would be asserting a confidence nothing
# supports.
CONFIDENCE_CEILING = MEDIUM
CEILING_REASON = (
    "HIGH requires counterfactual evidence. The counterfactuals this "
    "model can compute run through the memory arbitration rule recorded "
    "as MEM-ARB-001, whose physical realism is not established, so they "
    "are STALE and are not used here.")

# Candidate causes. Named as the part of the architecture a designer would
# act on, not as a metric.
HOST_SIDE = "Host-side processing"
MEMORY_BW = "Shared-memory bandwidth capacity"
ACCEL_COMPUTE = "Accelerator compute"
OFFLOAD_COST = "Preprocessing offload overhead"
UNDETERMINED = "Undetermined"


@dataclass(frozen=True)
class Inference:
    observed: str
    evidence: Tuple[str, ...]
    candidate: str
    confidence: str
    limits: Tuple[str, ...]
    next_experiment: Tuple[str, ...]
    conflicting: bool = False

    root_cause: str = "NOT ESTABLISHED"


def infer_bottleneck(analysis, flow, memory) -> Inference:
    """Reason from the flow and the adequacy verdict. Nothing else.

    Deliberately narrow. Every input here is something the model computes
    without passing through an unestablished arbitration: station shares,
    the engine's own limiting factor, traffic per job, and whether the
    target-rate requirement fits the bus.
    """
    dominant = flow.dominant_component
    share = flow.dominant_share_pct
    limit = flow.analytical_limit

    observed = (f"{dominant.capitalize()} accounts for {share:.1f}% of job "
                f"latency.")

    evidence: List[str] = []
    limits: List[str] = []
    experiments: List[str] = []
    conflicting = False

    # --- adequacy evidence ------------------------------------------------
    if memory is None or not memory.computable:
        evidence.append("Target-rate memory adequacy: NOT COMPUTED "
                        "(no declared application target)")
        limits.append("Without a target rate there is no rate at which to "
                      "ask whether bandwidth suffices.")
        adequacy_says_memory = False
    else:
        evidence.append(f"Target-rate memory adequacy: {memory.adequacy}")
        evidence.append(f"Adequacy stability: {memory.stability}")
        adequacy_says_memory = memory.adequacy == "FAIL"
        if memory.stability == "Conditional":
            limits.append(
                f"The adequacy verdict changes within the contract's "
                f"overlap range; it holds only below "
                f"{memory.critical_overlap * 100:.0f}% overlap, and the "
                f"overlap is assumed rather than measured.")

    evidence.append(f"Analytical limiting factor: {limit}")

    # --- candidate --------------------------------------------------------
    #
    # Adequacy FAIL is strong evidence about memory and is NOT a memory
    # verdict on its own: it is an average-capacity floor, and a design can
    # pass it and still be memory bound.
    if adequacy_says_memory:
        candidate = MEMORY_BW
        evidence.append(
            "The bandwidth needed to sustain the application target "
            "exceeds what the bus provides under the declared "
            "concurrency assumption.")
        if "host" in dominant and limit == "compute":
            # The flow points at the host, the engine's limit at compute,
            # adequacy at memory. Three pointers, three directions.
            conflicting = True
            limits.append(
                "The flow, the analytical limit and the adequacy verdict "
                "point at three different parts of the design. No two of "
                "them agree here.")
    elif "offload overhead" in dominant:
        candidate = OFFLOAD_COST
        evidence.append(
            "Most of the job is spent moving work to the offload engine "
            "rather than doing it.")
    elif "host" in dominant:
        candidate = HOST_SIDE
        if limit in ("compute", "memory"):
            # compute and memory are mechanisms INSIDE the accelerator.
            conflicting = True
            limits.append(
                f"The host holds the time while the engine reports "
                f"{limit} as the limit, which is a mechanism inside the "
                f"accelerator. These point at different parts.")
    elif "accelerator" in dominant:
        candidate = ACCEL_COMPUTE if limit == "compute" else MEMORY_BW
    else:
        candidate = UNDETERMINED

    # --- confidence -------------------------------------------------------
    if conflicting or candidate == UNDETERMINED:
        confidence = LOW
    else:
        confidence = MEDIUM

    limits.append("Actual memory service rate and transfer latency are "
                  "not established.")
    limits.append("Counterfactual evidence is unavailable under the "
                  "current memory model.")

    # --- what would settle it --------------------------------------------
    experiments.append(
        "Model or measure host issue capability, then repeat the "
        "counterfactual analysis (MEM-D3).")
    if candidate == HOST_SIDE:
        experiments.append(
            "Move preprocessing to the ISP and compare: if the host share "
            "falls and total latency follows, host-side processing is "
            "confirmed as the limit rather than merely the largest "
            "station.")
    elif candidate == MEMORY_BW:
        experiments.append(
            "Raise memory bandwidth - more units, or a wider technology - "
            "and compare against raising accelerator throughput. Only one "
            "of the two should help if the candidate is right.")
    elif candidate == ACCEL_COMPUTE:
        experiments.append(
            "Increase the accelerator array while holding memory fixed. "
            "If latency does not fall, the array was not the limit.")
    elif candidate == OFFLOAD_COST:
        experiments.append(
            "Compare against running preprocessing on the host: if total "
            "latency falls, the offload is costing more than it saves.")

    return Inference(
        observed=observed,
        evidence=tuple(evidence),
        candidate=candidate,
        confidence=confidence,
        limits=tuple(limits),
        next_experiment=tuple(experiments),
        conflicting=conflicting)


def render_bottleneck(inf: Inference) -> List[str]:
    from .visual.text import wrap_text

    out = ["BOTTLENECK INFERENCE", ""]
    out.append("  Observed symptom")
    for line in wrap_text(inf.observed, 64):
        out.append(f"      {line}")
    out.append("")
    out.append("  Supporting evidence")
    for item in inf.evidence:
        for i, line in enumerate(wrap_text(item, 62)):
            out.append(f"      {line}" if i == 0 else f"        {line}")
    out.append("")
    out.append(f"  Candidate cause             {inf.candidate}")
    out.append(f"  Confidence                  {inf.confidence}")
    out.append("")
    out.append("  Why confidence is limited")
    for item in inf.limits:
        for i, line in enumerate(wrap_text(item, 62)):
            out.append(f"      {line}" if i == 0 else f"        {line}")
    for line in wrap_text(CEILING_REASON, 62):
        out.append(f"      {line}")
    out.append("")
    # ROOT CAUSE stays here, unmoved. A candidate with evidence beside it
    # reads as a conclusion unless the screen says plainly that it is not
    # one.
    out.append(f"  Root cause                  {inf.root_cause}")
    for line in wrap_text(
            "A candidate is the part of the design the evidence points "
            "at. It is not a cause until an experiment separates it from "
            "the alternatives.", 62):
        out.append(f"      {line}")
    out.append("")
    out.append("  Next experiment")
    for item in inf.next_experiment:
        for i, line in enumerate(wrap_text(item, 62)):
            out.append(f"      {line}" if i == 0 else f"        {line}")
    return out
