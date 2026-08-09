"""
ppact.recommendation - what to change next, and how sure that is

WHY THIS IS THE LAST SCREEN AND NOT THE FIRST
=============================================
Everything before it answers "why is this design like this". This one
answers "what would you change", which is the question a designer actually
came with - and it is last because an answer without the reasoning above it
is a recommendation the reader cannot check.

WHAT IT REFUSES TO DO
---------------------
Predict the improvement. The counterfactuals that would give a number run
through the memory arbitration rule recorded as MEM-ARB-001, where a 3%
over-demand halves host bandwidth and a faster accelerator comes out 59%
slower. A predicted percentage from that model would be precise and wrong,
and precision is what makes it stick.

So the expected effect is DESCRIBED - which constraint would move, and in
which direction - and the magnitude says NOT ESTABLISHED.

WHY A RECOMMENDATION IS NOT A STARTING POINT
--------------------------------------------
This project spent a release cycle removing a design that appeared on every
screen, because a baseline shown everywhere reads as the architecture the
tool prefers whatever the label beside it says.

A recommendation is a different thing: it is tied to an observed limit,
names what evidence supports it, and says what would have to be true for it
to be wrong. Those three are what stop it becoming a default.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"

# The same ceiling the bottleneck inference carries, for the same reason.
CONFIDENCE_CEILING = MEDIUM

NOT_ESTABLISHED = "NOT ESTABLISHED"

# What a designer can act on, per block. The action names a component, not
# a metric: "raise the accelerator's throughput" is something to buy or
# build; "reduce accelerator time" is a restatement of the problem.
ACTIONS = {
    "host": ("Move preprocessing off the host, or use a faster host "
             "processor"),
    "ISP": ("Raise ISP throughput, or move preprocessing back to the "
            "host"),
    "accelerator": ("Use a larger accelerator class, or split work across "
                    "two engines"),
    "secondary accelerator": ("Rebalance the work split between the two "
                              "engines"),
    "shared memory": ("Add memory units, or move to a wider memory "
                      "technology"),
}


@dataclass(frozen=True)
class Recommendation:
    action: str
    target_block: str
    reason: str
    expected_effect: str
    expected_magnitude: str
    confidence: str
    would_be_wrong_if: Tuple[str, ...]
    alternatives: Tuple[str, ...]


def recommend(analysis, flow, constraints, memory=None, bottleneck=None
              ) -> Optional[Recommendation]:
    """One recommendation, tied to an observed limit.

    Returns None when nothing is limiting: a design meeting every
    constraint with room to spare has no next change that this analysis
    can justify, and inventing one would be the tool preferring an
    architecture.
    """
    wrong_if: List[str] = []
    alternatives: List[str] = []

    tp_violated = constraints.throughput_status == "VIOLATED"
    lat_violated = constraints.latency_status == "VIOLATED"

    if not (tp_violated or lat_violated):
        # Nothing to fix. The critical station is still worth naming,
        # because it is what would bind first - but that is a fact, not a
        # recommendation.
        return None

    if tp_violated:
        block = constraints.throughput_critical
        action = ACTIONS.get(block, f"Raise the throughput of {block}")
        reason = (f"The throughput constraint is violated and {block} has "
                  f"the least slack against the required interval.")
        effect = ("The throughput constraint would move. Whether it is "
                  "then met depends on how far the change goes.")
        wrong_if.append(
            f"{block} is not actually the slowest stage - the throughput "
            f"stations are analytical estimates, not measurements.")
        if constraints.graphs_disagree:
            wrong_if.append(
                "The latency constraint is limited by a different part of "
                "the design, so this change may not help the latency at "
                "all.")
            alternatives.append(
                f"For latency, the path is "
                f"{' -> '.join(constraints.latency_path)}; a change there "
                f"is a separate decision.")
    else:
        # Latency violated, throughput met. The path has no per-station
        # slack, so the dominant station is the honest target.
        block = flow.dominant_component
        action = ACTIONS.get(block.split()[0],
                             f"Reduce the time spent in {block}")
        reason = (f"The latency constraint is violated and {block} holds "
                  f"{flow.dominant_share_pct:.1f}% of one job.")
        effect = ("The latency path would shorten. The throughput "
                  "constraint is already met and would not be the "
                  "binding one.")
        wrong_if.append(
            f"{block} holds the most time and may not be what imposes the "
            f"limit - the analytical limiting factor here is "
            f"{flow.analytical_limit}.")

    if memory is not None and memory.computable \
            and memory.adequacy == "FAIL":
        wrong_if.append(
            "Target-rate memory adequacy has failed, so the station times "
            "this recommendation rests on were computed under a bandwidth "
            "the design cannot sustain.")
        alternatives.append(
            "Address memory adequacy first: the figures above may change "
            "once the bus can carry the target rate.")

    # Confidence. Never HIGH, and lowered when the evidence disagrees with
    # itself.
    confidence = MEDIUM
    if bottleneck is not None and bottleneck.confidence == LOW:
        confidence = LOW
        wrong_if.append(
            "The bottleneck evidence points in more than one direction, "
            "so the block named here is one candidate among several.")

    return Recommendation(
        action=action,
        target_block=block,
        reason=reason,
        expected_effect=effect,
        expected_magnitude=NOT_ESTABLISHED,
        confidence=confidence,
        would_be_wrong_if=tuple(wrong_if),
        alternatives=tuple(alternatives))


def render_recommendation(rec: Optional[Recommendation],
                          constraints=None) -> List[str]:
    from .visual.text import wrap_text

    out = ["RECOMMENDATION", ""]

    if rec is None:
        out.append("  No change is recommended.")
        out.append("")
        for line in wrap_text(
                "Every constraint is met with room left. There is no "
                "observed limit for a recommendation to be tied to, and "
                "naming a change anyway would be this tool preferring an "
                "architecture rather than reporting one.", 66):
            out.append(f"  {line}")
        if constraints is not None and constraints.throughput_critical:
            out.append("")
            out.append(f"  Would bind first            "
                       f"{constraints.throughput_critical}")
            out.append("      A fact about the current design, not a "
                       "change to make.")
        return out

    # Wrapped. The action names a component and a route to it, so it is
    # a sentence rather than a label, and on one line it ran past 78.
    out.append("  Change")
    for line in wrap_text(rec.action, 62):
        out.append(f"      {line}")
    out.append(f"  Target                      {rec.target_block}")
    out.append("")
    out.append("  Reason")
    for line in wrap_text(rec.reason, 62):
        out.append(f"      {line}")
    out.append("")
    out.append("  Expected effect")
    for line in wrap_text(rec.expected_effect, 62):
        out.append(f"      {line}")
    out.append("")
    # THE MAGNITUDE IS NOT PREDICTED, and the reason is named. A blank
    # here would read as an oversight; a number would be precise and
    # wrong, and precision is what makes a wrong figure stick.
    out.append(f"  Expected improvement        {rec.expected_magnitude}")
    for line in wrap_text(
            "A predicted percentage would come from counterfactuals that "
            "run through the memory arbitration rule recorded as "
            "MEM-ARB-001, whose physical realism is not established.", 62):
        out.append(f"      {line}")
    out.append("")
    out.append(f"  Confidence                  {rec.confidence}")
    out.append("")
    out.append("  This would be wrong if")
    for item in rec.would_be_wrong_if:
        for i, line in enumerate(wrap_text(item, 62)):
            out.append(f"      {line}" if i == 0 else f"        {line}")
    if rec.alternatives:
        out.append("")
        out.append("  Also consider")
        for item in rec.alternatives:
            for i, line in enumerate(wrap_text(item, 62)):
                out.append(f"      {line}" if i == 0 else f"        {line}")
    out.append("")
    for line in wrap_text(
            "A recommendation is tied to an observed limit. It is not a "
            "starting point, not a preferred architecture, and not a "
            "design the tool would choose.", 66):
        out.append(f"  {line}")
    return out
