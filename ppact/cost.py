"""
ppact.cost - the analysis chain on the cost axis, built on what is known

WHY THIS IS SHORTER THAN THE AREA TRACK
=======================================
Area had a per-block decomposition that summed in 216 of 216
configurations. Cost does not: the engine reports the accelerator's
silicon cost, a logic-die subtotal and the system total, and the CPU, ISP
and memory package terms exist only inside the expression.

They could be recovered from the libraries. The attempt returned 1.1996
against the engine's 0.9507, because `Logic die cost` declares an ISP it
does not add - CO-BOUNDARY-001. Recovering figures from a source whose
declaration and expression disagree would produce a breakdown that looks
computed and is guessed.

So the breakdown here is what the engine states, and the rest is NOT
ESTABLISHED. That is a smaller screen than Area's and an honest one.

WHAT COST BOTTLENECK MEANS
--------------------------
    Performance   the LOWEST throughput
    Area          the LARGEST contributor
    Cost          the LARGEST known contributor

"Known" is doing work in that third line. With three figures rather than a
decomposition, the largest of them is the largest of what is reported - not
necessarily the largest thing in the design.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

MET = "MET"
VIOLATED = "VIOLATED"
NOT_CONSTRAINED = "NOT CONSTRAINED"
NOT_ESTABLISHED = "NOT ESTABLISHED"

CALCULATED = "CALCULATED"


@dataclass(frozen=True)
class CostItem:
    name: str
    usd: float
    provenance: str
    is_largest: bool
    in_system_cost: bool


@dataclass(frozen=True)
class CostView:
    items: Tuple[CostItem, ...]
    system_cost_usd: float
    budget_usd: Optional[float]
    slack_usd: Optional[float]
    largest_known: str

    nre_per_unit_usd: Optional[float]
    memory_cost_index: Optional[float]

    # What drives the system cost, which is not always the largest
    # reported figure.
    driver: str = NOT_ESTABLISHED
    driver_reason: str = ""

    @property
    def status(self) -> str:
        if self.budget_usd is None:
            return NOT_CONSTRAINED
        return MET if self.slack_usd >= 0 else VIOLATED


def build_cost_view(analysis) -> CostView:
    from .application import APPLICATION_LIBRARY

    app = APPLICATION_LIBRARY[analysis.app_key]
    m = analysis.current_result.metrics

    system = float(m.get("System cost (USD)", 0.0))
    items: List[CostItem] = []
    for name, key in (("accelerator silicon", "Accel silicon cost (USD)"),
                      ("logic die subtotal", "Logic die cost (USD)")):
        value = m.get(key)
        if value is not None:
            items.append(CostItem(name, float(value), CALCULATED, False,
                                  True))

    if items:
        biggest = max(items, key=lambda i: i.usd)
        items = [CostItem(i.name, i.usd, i.provenance, i is biggest,
                          i.in_system_cost) for i in items]
        largest = biggest.name
    else:
        largest = ""

    budget = getattr(app, "bom_budget_usd", None)
    slack = (budget - system) if budget else None

    # THE DRIVER, from what the reported figures leave unexplained.
    #
    # The largest reported figure is the logic die subtotal at 0.951 USD
    # against a system cost of 19.066. The other 18.115 is not reported as
    # a component, and it is 95% of the total - so naming the subtotal as
    # the cost driver would name the smaller of two things.
    logic = m.get("Logic die cost (USD)")
    driver, reason = NOT_ESTABLISHED, ""
    if logic is not None and system > 0:
        outside = system - float(logic)
        share = outside / system * 100.0
        if share > 50.0:
            driver = "outside the logic die"
            reason = (f"{outside:.3f} USD of {system:.3f} - {share:.0f}% "
                      f"of the system cost - is not covered by any "
                      f"reported component. The system cost expression "
                      f"puts memory packages there. That is where the "
                      f"cost is, and it is not the largest REPORTED "
                      f"figure.")
        else:
            driver = "the logic die"
            reason = (f"The logic die is {float(logic) / system * 100:.0f}% "
                      f"of the system cost, more than everything else "
                      f"combined.")

    return CostView(tuple(items), system, budget, slack, largest,
                    m.get("Mask/NRE per unit (USD)"),
                    m.get("Memory cost index"), driver, reason)


def render_cost_view(view: CostView, show_title: bool = True
                     ) -> List[str]:
    from .visual.text import wrap_text

    out = ["COST ANALYSIS", ""] if show_title else []

    out.append("  WHAT IS REPORTED")
    for i in view.items:
        mark = "<" if i.is_largest else " "
        out.append(f"    {mark} {i.name:<26s}{i.usd:>10.3f} USD"
                   f"   {i.provenance}")
    out.append(f"      {'system cost':<26s}{view.system_cost_usd:>10.3f}"
               f" USD   {CALCULATED}")
    out.append("")
    out.append(f"  Per-block breakdown         {NOT_ESTABLISHED}")
    for line in wrap_text(
            "The CPU, ISP and memory package terms exist inside the "
            "system cost expression and are not reported separately. "
            "Recovering them from the libraries returned 1.1996 against "
            "the engine's 0.9507, because the logic die subtotal declares "
            "an ISP it does not add (CO-BOUNDARY-001). A breakdown built "
            "on that would look computed and be guessed.", 62):
        out.append(f"      {line}")
    out.append("")

    out.append("  COST CONSTRAINT   against the BOM budget")
    if view.budget_usd is None:
        out.append(f"      BOM budget              {NOT_ESTABLISHED}")
        out.append(f"      Status                  {NOT_CONSTRAINED}")
    else:
        out.append(f"      System cost             "
                   f"{view.system_cost_usd:>10.3f} USD")
        out.append(f"      BOM budget              "
                   f"{view.budget_usd:>10.3f} USD")
        out.append(f"      Slack                   "
                   f"{view.slack_usd:>+10.3f} USD")
        out.append(f"      Status                  {view.status}")
    out.append("")

    out.append(f"  COST BOTTLENECK             {view.largest_known}")
    for line in wrap_text(
            "The largest KNOWN contributor. With three figures rather "
            "than a decomposition, this is the largest of what is "
            "reported, not necessarily the largest thing in the design.",
            62):
        out.append(f"      {line}")
    out.append("")

    # THE DRIVER. Named separately from the bottleneck because they can
    # differ: the largest reported figure is a subtotal, and what actually
    # drives the system cost is the part neither figure covers.
    out.append(f"  COST DRIVER                 {view.driver}")
    for line in wrap_text(view.driver_reason, 62):
        out.append(f"      {line}")
    out.append("")

    # OUTSIDE THE BOM. Both are reported and neither belongs in the sum.
    out.append("  REFERENCE INFORMATION - not part of the BOM")
    if view.nre_per_unit_usd is not None:
        out.append(f"      Mask/NRE per unit       "
                   f"{view.nre_per_unit_usd:>10.3f} USD")
        for line in wrap_text(
                "Amortised over lifetime volume and reported only. A team "
                "buying an existing SoC pays none of it; a team taping one "
                "out pays it whatever the BOM says.", 58):
            out.append(f"        {line}")
    if view.memory_cost_index is not None:
        out.append(f"      Memory cost index       "
                   f"{view.memory_cost_index:>10.3f}")
        out.append("        A relative index, not USD. It is not summed "
                   "with the")
        out.append("        figures above.")
    return out


@dataclass(frozen=True)
class CostRecommendation:
    action: str
    target: str
    reason: str
    expected_reduction: str
    would_be_wrong_if: Tuple[str, ...]


def recommend_cost(view: CostView) -> Optional[CostRecommendation]:
    """Tied to a violated budget, or nothing."""
    if view.status != VIOLATED:
        return None

    wrong = [
        "The per-block breakdown is not established, so the largest "
        "reported figure may not be the largest actual contributor - "
        f"the cost driver here is {view.driver}.",
        "Cost is one axis. A cheaper part may cost throughput or area, "
        "and this recommendation does not check that.",
    ]
    return CostRecommendation(
        action=("Reduce the system bill of materials - fewer or cheaper "
                "memory packages, a smaller accelerator, or a cheaper "
                "host processor"),
        target=view.largest_known or "system cost",
        reason=(f"The BOM budget is exceeded by "
                f"{abs(view.slack_usd):.3f} USD."),
        expected_reduction=NOT_ESTABLISHED,
        would_be_wrong_if=tuple(wrong))


def render_cost_recommendation(rec: Optional[CostRecommendation],
                               view: CostView) -> List[str]:
    from .visual.text import wrap_text

    out = ["COST RECOMMENDATION", ""]
    if rec is None:
        out.append("  No change is recommended.")
        out.append("")
        for line in wrap_text(
                "The BOM budget is met. There is no observed limit for a "
                "recommendation to be tied to.", 66):
            out.append(f"  {line}")
        return out

    out.append("  Change")
    for line in wrap_text(rec.action, 62):
        out.append(f"      {line}")
    out.append(f"  Largest known contributor   {rec.target}")
    out.append("")
    out.append("  Reason")
    for line in wrap_text(rec.reason, 62):
        out.append(f"      {line}")
    out.append("")
    out.append(f"  Expected reduction          {rec.expected_reduction}")
    out.append("")
    out.append("  This would be wrong if")
    for item in rec.would_be_wrong_if:
        for i, line in enumerate(wrap_text(item, 62)):
            out.append(f"      {line}" if i == 0 else f"        {line}")
    return out
