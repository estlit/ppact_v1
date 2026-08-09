"""
ppact.traffic - how evenly the internal throughput is distributed

WHAT THIS IS NOT
================
Not Performance under another name. Performance asks whether the system
meets a requirement; this asks how the internal stages sit relative to
each other, and the answer does not change when the requirement does.

    Performance   can the system deliver what is required?
    Traffic       how balanced is the internal distribution?

WHY NOT SLOWEST OVER FASTEST
----------------------------
The obvious index is the slowest stage over the fastest:

    ISP 99.7 / shared memory 639.6 = 15.6%

It reads as "fixing the ISP would get you 639.6". It would not. Fixing the
ISP lands on the accelerator at 397.0, so the figure promises an
improvement the design cannot reach. THE FASTEST STAGE IS NOT AN IDEAL
SYSTEM: a machine where every stage ran at 639.6 is a different machine,
not a better version of this one.

    Traffic Balance = lowest / SECOND-lowest = 99.7 / 397.0 = 25.1%

That one is bounded by what a single change can actually deliver.

TRAFFIC EFFICIENCY IS NOT ESTABLISHED
-------------------------------------
    efficiency = system throughput / ideal throughput

needs an ideal: a hypothetical system with no internal bottleneck, which
the model does not define. `Ideal core time` exists and is the accelerator's
ideal, not the system's. Until a reference exists, this stays absent
rather than being approximated by the fastest stage.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

NOT_ESTABLISHED = "NOT ESTABLISHED"


@dataclass(frozen=True)
class TrafficBalance:
    lowest_stage: str
    lowest_inf_s: Optional[float]
    second_stage: str
    second_inf_s: Optional[float]

    balance_pct: Optional[float]
    single_fix_headroom: Optional[float]   # second / lowest, a ceiling

    stage_count: int

    # The one that is not computed, and why.
    efficiency: str = NOT_ESTABLISHED


def build_traffic_balance(analysis) -> TrafficBalance:
    """Lowest over second-lowest. Requirement-independent by construction.

    Nothing here reads the application: a design's internal balance is
    the same whether it is asked for 20 inferences a second or 200.
    """
    m = analysis.current_result.metrics
    raw = m.get("Throughput stations (s)", {})
    rates = sorted((1000.0 / (v * 1e3), k) for k, v in raw.items()
                   if v > 0)

    if len(rates) < 2:
        # One stage cannot be out of balance with itself.
        only = rates[0][1] if rates else NOT_ESTABLISHED
        return TrafficBalance(only, rates[0][0] if rates else None,
                              NOT_ESTABLISHED, None, None, None,
                              len(rates))

    (lo_rate, lo_name), (sec_rate, sec_name) = rates[0], rates[1]
    balance = lo_rate / sec_rate * 100.0 if sec_rate > 0 else None
    headroom = sec_rate / lo_rate if lo_rate > 0 else None
    return TrafficBalance(lo_name, lo_rate, sec_name, sec_rate,
                          balance, headroom, len(rates))


def render_traffic_balance(b: TrafficBalance,
                           show_title: bool = True) -> List[str]:
    from .visual.text import wrap_text

    out = ["TRAFFIC BALANCE", ""] if show_title else []

    if b.balance_pct is None:
        out.append(f"  Traffic balance             {NOT_ESTABLISHED}")
        out.append(f"      {b.stage_count} throughput stage(s) - balance "
                   f"needs at least two.")
        return out

    out.append(f"  Lowest stage                {b.lowest_stage}, "
               f"{b.lowest_inf_s:.1f} inf/s")
    out.append(f"  Second-lowest stage         {b.second_stage}, "
               f"{b.second_inf_s:.1f} inf/s")
    out.append(f"  Traffic balance             {b.balance_pct:.1f}%")
    out.append("")
    for line in wrap_text(
            "Lowest over second-lowest. At 100% the two bind together and "
            "no single stage dominates; low figures mean one stage is far "
            "behind the rest. Higher is better.", 66):
        out.append(f"  {line}")
    out.append("")

    # A CEILING, not a prediction.
    out.append(f"  Single-fix headroom         "
               f"{b.single_fix_headroom:.2f}x")
    for line in wrap_text(
            f"Removing {b.lowest_stage} as a limit could raise the system "
            f"rate to at most {b.second_inf_s:.1f} inf/s, where "
            f"{b.second_stage} binds instead. A conditional ceiling, not "
            f"a predicted gain - what a change actually buys needs a "
            f"counterfactual this model cannot supply.", 62):
        out.append(f"      {line}")
    out.append("")

    out.append(f"  Traffic efficiency          {b.efficiency}")
    for line in wrap_text(
            "System throughput over IDEAL throughput needs a "
            "hypothetical system with no internal bottleneck, which the "
            "model does not define. Using the fastest stage as the ideal "
            "would give 15.6% "
            "here and promise an improvement the design cannot reach - "
            "fixing the lowest stage lands on the second, not the "
            "fastest.", 62):
        out.append(f"      {line}")
    out.append("")

    for line in wrap_text(
            "Traffic does not read the requirement. The same design has "
            "the same balance whether it is asked for 20 inferences a "
            "second or 200 - that is Performance's question, and this is "
            "a property of the structure.", 66):
        out.append(f"  {line}")
    return out


def recommend_traffic(b: TrafficBalance) -> Optional[str]:
    """Improving balance, never raising throughput for its own sake.

    A recommendation to add compute belongs to Performance. Here the only
    change that counts is one that brings the lowest stage closer to the
    rest.
    """
    if b.balance_pct is None or b.balance_pct >= 90.0:
        return None
    return (f"Raise {b.lowest_stage} throughput toward "
            f"{b.second_inf_s:.1f} inf/s, or move work off it. The system "
            f"is limited by one stage more than by its structure.")
