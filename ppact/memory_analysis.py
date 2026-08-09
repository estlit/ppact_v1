"""
ppact.memory_analysis - what can be said about memory, and where it stops

WHY THIS SCREEN LOOKS UNUSUAL
=============================
Most tools print

    Memory bottleneck   32%

and a reader takes it as a measurement. This screen prints what was
computed, and then prints where the reasoning ran out.

That is not modesty. Three separate questions were being answered by one
number, and separating them is what the whole MEM-D investigation
established:

    Is average bandwidth sufficient at the target?   COMPUTED
    How long does a transfer actually take?          NOT ESTABLISHED
    Why is the design slow?                          NOT ESTABLISHED

The second needs a service rate, which needs an issue capability the model
does not carry. Deriving it from the requirement gives

    transfer = bytes / (bytes * R) = 1 / R

so every design with the same target reports the same transfer time
whatever its memory. That was computed, observed, and rejected.

THE REASONING FLOW
------------------
The screen is drawn as a chain because the chain is the point: each step
depends on the one above, and the reader should see WHERE it stops rather
than being handed a verdict with no visible support.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# The contract's overlap range. A verdict that holds across all of it is
# stable; one that changes inside it depends on a number nobody measured.
OVERLAP_MIN = 0.25
OVERLAP_MAX = 1.00
OVERLAP_DEFAULT = 1.00      # conservative end, and an ASSUMPTION

STABLE_PASS = "Stable PASS"
CONDITIONAL = "Conditional"
STABLE_FAIL = "Stable FAIL"

NOT_ESTABLISHED = "NOT ESTABLISHED"


@dataclass(frozen=True)
class MemoryAnalysis:
    app_name: str
    target_rate: Optional[float]

    host_bytes_per_job: float
    accel_bytes_per_job: float

    host_required: Optional[float]      # GB/s at the target
    accel_required: Optional[float]
    effective_bandwidth: float
    overlap: float

    concurrent_requirement: Optional[float]
    headroom: Optional[float]
    adequacy: Optional[str]             # PASS / FAIL / None
    stability: Optional[str]
    critical_overlap: Optional[float]

    @property
    def computable(self) -> bool:
        return self.target_rate is not None and self.target_rate > 0


def concurrent_at(host_req: float, accel_req: float, overlap: float
                  ) -> float:
    """How much of the two requirements is wanted at the same moment.

    At overlap 1.0 both are charged in full - the conservative end. At 0
    only the larger applies, because a stage running alone contends with
    nothing.
    """
    larger, smaller = max(host_req, accel_req), min(host_req, accel_req)
    return larger + overlap * smaller


def analyse_memory(analysis, overlap: float = OVERLAP_DEFAULT
                   ) -> MemoryAnalysis:
    """Build the memory picture from a finished ReviewAnalysis.

    The target rate comes from the APPLICATION. It is never taken from the
    evaluated design's delivered throughput or pipeline capacity: a slow
    design would then report a small requirement and call itself
    uncontended, which is the circularity this analysis exists to avoid.
    """
    from .application import APPLICATION_LIBRARY

    app = APPLICATION_LIBRARY[analysis.app_key]
    metrics = analysis.current_result.metrics
    R = getattr(app, "target_inferences_per_s", 0) or None

    host_bytes = metrics.get("Host DRAM traffic (MB)", 0.0) * 1e6
    accel_bytes = metrics.get("DRAM traffic (MB)", 0.0) * 1e6
    B = metrics.get("Effective bandwidth (GB/s)", 0.0)

    if not R:
        # No substituted rate. An application with no declared target has
        # no target-rate requirement, and inventing one would put a number
        # where a question belongs.
        return MemoryAnalysis(
            analysis.app_name, None, host_bytes, accel_bytes,
            None, None, B, overlap, None, None, None, None, None)

    host_req = host_bytes * R / 1e9
    accel_req = accel_bytes * R / 1e9
    conc = concurrent_at(host_req, accel_req, overlap)
    headroom = B - conc
    adequacy = "PASS" if headroom >= 0 else "FAIL"

    # Stability, from the exact crossing rather than sampled points.
    larger, smaller = max(host_req, accel_req), min(host_req, accel_req)
    if smaller <= 0:
        ov_crit = None
        stability = STABLE_PASS if B >= larger else STABLE_FAIL
    else:
        ov_crit = (B - larger) / smaller
        if ov_crit >= OVERLAP_MAX:
            stability = STABLE_PASS
        elif ov_crit < OVERLAP_MIN:
            stability = STABLE_FAIL
        else:
            stability = CONDITIONAL

    return MemoryAnalysis(
        analysis.app_name, R, host_bytes, accel_bytes,
        host_req, accel_req, B, overlap, conc, headroom, adequacy,
        stability, ov_crit if stability == CONDITIONAL else None)


def link_to_flow(mem: MemoryAnalysis, flow) -> List[str]:
    """What the two screens say about each other.

    Side by side they described one design and referred to nothing in
    common, so a reader had to carry the connection themselves. These are
    the two facts that connect them - and the second is the interesting
    one, because it is often a disagreement:

        the station holding the TIME
        the agent needing the BANDWIDTH

    Across 302 review cases they disagreed in 49. The accelerator holds
    most of the job while the host needs more of the bus, or the reverse.
    A screen that let a reader assume they always coincide would be wrong
    one time in six.
    """
    from .visual.text import wrap_text

    if not mem.computable or flow is None or not flow.stations:
        return []

    larger = ("host" if mem.host_required >= mem.accel_required
              else "accelerator")
    dominant = flow.dominant_component
    agrees = ((larger == "host" and "host" in dominant)
              or (larger == "accelerator" and "accelerator" in dominant))

    out = ["", "  WHERE THIS MEETS THE LATENCY FLOW", ""]
    out.append(f"      Station holding the time    {dominant}, "
               f"{flow.dominant_share_pct:.1f}%")
    out.append(f"      Agent needing the bandwidth {larger}, "
               f"{max(mem.host_required, mem.accel_required):.2f} GB/s")
    out.append("")
    if agrees:
        sentence = (f"The same part of the design holds the time and needs "
                    f"the bandwidth here. That is not always so, and the "
                    f"screen does not assume it.")
    else:
        sentence = (f"These point at DIFFERENT parts. {dominant.capitalize()} "
                    f"holds the time; the {larger} needs more of the bus. "
                    f"Neither figure predicts the other, and reading one as "
                    f"the other is how a memory upgrade gets bought for a "
                    f"compute-bound design.")
    for line in wrap_text(sentence, 62):
        out.append(f"      {line}")

    if mem.adequacy == "FAIL":
        out.append("")
        for line in wrap_text(
                "Adequacy FAILED, so the flow above was computed under a "
                "bandwidth the design cannot sustain at its target. Its "
                "station times are not a prediction of what this design "
                "would do.", 62):
            out.append(f"      {line}")
    return out


PASS_WORDING = ("Average bandwidth capacity is sufficient at the "
                "application target rate.")
FAIL_WORDING = ("Average bandwidth capacity is insufficient under the "
                "declared concurrency assumption.")


def render_memory_analysis(m: MemoryAnalysis, flow=None) -> List[str]:
    """The reasoning flow, top to bottom, ending where it ends.

    Pass `flow` to append the cross-link: without it the two screens sit
    side by side describing one design and referring to nothing in common.
    """
    from .visual.text import wrap_text

    out: List[str] = []
    out.append("MEMORY ANALYSIS")
    out.append("")
    # Says what it is analysing. The flow now names the shared resource in
    # one quiet line and leaves the explanation here, which is where the
    # judgement about that resource belongs.
    for line in wrap_text(
            "This analysis evaluates the shared memory resource used by "
            "the host and the accelerator.", 66):
        out.append(f"  {line}")
    out.append("")
    # Says what is being analysed. The flow now only marks the shared
    # resource; the sentence explaining what to do about it belongs with
    # the verdict, which is here.
    for line in wrap_text(
            "This analysis evaluates the shared memory resource used by "
            "the host and accelerator.", 66):
        out.append(f"  {line}")
    out.append("")

    if not m.computable:
        out.append("  Application target throughput      NOT ESTABLISHED")
        out.append("  Target-rate bandwidth requirement  NOT COMPUTED")
        out.append("")
        for line in wrap_text(
                "This application declares no target rate, so there is no "
                "rate at which to ask whether bandwidth is sufficient. No "
                "substitute is used.", 66):
            out.append(f"  {line}")
        return out

    out.append(f"  Application target          "
               f"{m.target_rate:.0f} inferences/s")
    out.append(f"  Host traffic per job        "
               f"{m.host_bytes_per_job / 1e6:.2f} MB")
    out.append(f"  Accelerator traffic per job "
               f"{m.accel_bytes_per_job / 1e6:.2f} MB")
    out.append("      |")
    out.append("      v")
    out.append("  BANDWIDTH REQUIRED AT TARGET")
    out.append(f"      host                    {m.host_required:8.2f} GB/s")
    out.append(f"      accelerator             {m.accel_required:8.2f} GB/s")
    out.append(f"      concurrent              "
               f"{m.concurrent_requirement:8.2f} GB/s")
    out.append(f"      available               "
               f"{m.effective_bandwidth:8.2f} GB/s")
    out.append(f"      headroom                {m.headroom:+8.2f} GB/s")
    out.append("      |")
    out.append("      v")
    out.append(f"  ADEQUACY                    {m.adequacy}")
    for line in wrap_text(
            PASS_WORDING if m.adequacy == "PASS" else FAIL_WORDING, 62):
        out.append(f"      {line}")
    out.append("      |")
    out.append("      v")
    out.append(f"  ADEQUACY STABILITY          {m.stability}")
    if m.stability == CONDITIONAL and m.critical_overlap is not None:
        out.append(f"      critical overlap        "
                   f"{m.critical_overlap:.2f}")
        for line in wrap_text(
                f"The verdict depends on an unmeasured assumption: PASS "
                f"below {m.critical_overlap * 100:.0f}% overlap, FAIL "
                f"above it.", 62):
            out.append(f"      {line}")
    elif m.stability == STABLE_PASS:
        out.append("      The verdict holds across every overlap "
                   "assumption")
        out.append("      the contract considers.")
    else:
        out.append("      The verdict holds across every overlap "
                   "assumption,")
        out.append("      so no concurrency assumption rescues it.")
    out.append("      |")
    out.append("      v")

    # WHERE THE REASONING STOPS. Printed as part of the chain, not as a
    # footnote: a reader who sees ADEQUACY PASS and nothing after it will
    # supply the missing conclusion themselves.
    out.append("  ACTUAL SERVICE RATE         NOT ESTABLISHED")
    for line in wrap_text(
            "The model has no issue-capability figure for the host, so "
            "what the memory system actually delivers is unknown.", 62):
        out.append(f"      {line}")
    out.append("      |")
    out.append("      v")
    out.append("  TRANSFER LATENCY            NOT ESTABLISHED")
    for line in wrap_text(
            "Not derived from this analysis. A requirement divided into "
            "bytes returns the target period and nothing about memory.",
            62):
        out.append(f"      {line}")
    out.append("      |")
    out.append("      v")
    out.append("  ROOT CAUSE                  NOT ESTABLISHED")
    for line in wrap_text(
            "Requires counterfactual verification under a service-rate "
            "model that does not exist yet.", 62):
        out.append(f"      {line}")
    out.append("")
    out.append(f"  Memory activity overlap assumption   "
               f"{m.overlap * 100:.0f}%")
    out.append("  Source                               Model assumption, "
               "not measured")
    out.append("")
    for line in wrap_text(
            "Adequacy is a capacity floor. It does not say memory is not "
            "a bottleneck: burst collisions, memory latency, imperfect "
            "overlap and arbitration delay all sit outside it, and a "
            "design can pass this check and still be memory bound.", 66):
        out.append(f"  {line}")
    out += link_to_flow(m, flow)
    return out
