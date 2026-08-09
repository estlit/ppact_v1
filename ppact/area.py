"""
ppact.area - the Performance chain, applied to area

WHY THIS EXISTS
===============
Not to add an area feature. To find out whether the analysis chain built
for Performance is a FRAMEWORK or a thing that fitted one axis.

    metric -> constraint -> breakdown -> bottleneck -> recommendation

Area is the honest first test: its breakdown sums exactly in 216 of 216
configurations, its budget is declared, and it carries no
measurement-basis question. If the chain does not fit here, it does not
generalise, and that is worth knowing before Cost, Power and Thermal are
built on it.

WHAT "BOTTLENECK" MEANS ON THIS AXIS
------------------------------------
On Performance the bottleneck is the LOWEST throughput - the block that
holds the system back. On Area it is the LARGEST contributor - the block
that uses the most of the budget.

Opposite directions, same role: the thing to change first. Calling both
"bottleneck" is deliberate, and the screen says which sense it means,
because a reader carrying the Performance meaning over would look for the
smallest number.

WHAT IS NOT DONE
----------------
No estimated saving. Predicting how much area a change would free needs a
counterfactual, and the same refusal applies here as on Performance:
`Expected reduction: NOT ESTABLISHED`.

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

# What a designer can act on, per contributor.
ACTIONS = {
    "host CPU": ("Use a smaller host processor, or move work off it so a "
                 "smaller one suffices"),
    "accelerator": ("Use a smaller accelerator class, or a finer process "
                    "node"),
    "secondary accelerator": ("Remove the second engine, or make it "
                              "smaller than the first"),
    "ISP": ("Remove the ISP and preprocess on the host, if the throughput "
            "constraint allows it"),
    "memory silicon": ("Use fewer memory units, or a denser memory "
                       "technology"),
}


@dataclass(frozen=True)
class AreaContributor:
    name: str
    area_mm2: float
    share_pct: float
    is_largest: bool
    in_soc: bool


@dataclass(frozen=True)
class AreaView:
    contributors: Tuple[AreaContributor, ...]
    soc_silicon_mm2: float
    memory_silicon_mm2: float
    total_silicon_mm2: float
    board_area_mm2: float

    soc_budget_mm2: Optional[float]
    soc_slack_mm2: Optional[float]
    largest: str

    breakdown_sums: bool
    board_budget_mm2: Optional[float] = None

    @property
    def soc_status(self) -> str:
        if self.soc_budget_mm2 is None:
            return NOT_CONSTRAINED
        return MET if self.soc_slack_mm2 >= 0 else VIOLATED


def build_area_view(analysis) -> AreaView:
    """Contributors, the SoC budget, and the largest of them.

    The budget governs SOC SILICON, not total silicon. A DRAM die is not
    constrained by an SoC die budget, and attaching it there produced a
    screen reading EXCEEDS by 78.4% while the deployment gate correctly
    said READY.
    """
    from .application import APPLICATION_LIBRARY

    app = APPLICATION_LIBRARY[analysis.app_key]
    m = analysis.current_result.metrics

    soc = float(m.get("SoC silicon (mm2)", 0.0))
    memory = float(m.get("Memory silicon (mm2)", 0.0))
    total = float(m.get("Total silicon (mm2)", 0.0))
    board = float(m.get("Board area (mm2)", 0.0))

    raw = [
        ("host CPU", float(m.get("CPU die area (mm2)", 0.0)), True),
        ("accelerator", float(m.get("Accel die area (mm2)", 0.0)), True),
        ("secondary accelerator",
         float(m.get("Secondary die area (mm2)", 0.0)), True),
        ("ISP", float(m.get("ISP area (mm2)", 0.0)), True),
        ("memory silicon", memory, False),
    ]
    # A contributor at zero is omitted rather than drawn at 0.0%: an ISP
    # that is not configured is not a block using none of the budget.
    present = [(n, a, in_soc) for n, a, in_soc in raw if a > 0]

    contributors: List[AreaContributor] = []
    for name, area, in_soc in present:
        share = area / total * 100.0 if total > 0 else 0.0
        contributors.append(AreaContributor(name, area, share, False,
                                            in_soc))
    largest_name = ""
    if contributors:
        biggest = max(contributors, key=lambda c: c.area_mm2)
        contributors = [
            AreaContributor(c.name, c.area_mm2, c.share_pct,
                            c is biggest, c.in_soc)
            for c in contributors]
        largest_name = biggest.name

    # The check that makes the breakdown reportable at all.
    soc_parts = sum(c.area_mm2 for c in contributors if c.in_soc)
    sums = (abs(soc_parts - soc) < 0.01
            and abs(soc + memory - total) < 0.01)

    budget = getattr(app, "soc_silicon_budget_mm2", None)
    slack = (budget - soc) if budget else None

    return AreaView(tuple(contributors), soc, memory, total, board,
                    budget, slack, largest_name, sums,
                    getattr(app, "board_area_budget_mm2", None))


def render_area_view(view: AreaView, show_title: bool = True
                     ) -> List[str]:
    from .visual.text import wrap_text

    out = ["AREA ANALYSIS", ""] if show_title else []

    out.append("  BREAKDOWN")
    out.append(f"      {'contributor':<24s}{'mm2':>10s}{'share':>9s}")
    out.append("      " + "-" * 45)
    for c in view.contributors:
        mark = "<" if c.is_largest else " "
        scope = "" if c.in_soc else "   (not SoC)"
        out.append(f"    {mark} {c.name:<24s}{c.area_mm2:>10.2f}"
                   f"{c.share_pct:>8.1f}%{scope}")
    out.append("      " + "-" * 45)
    out.append(f"      {'SoC silicon':<24s}{view.soc_silicon_mm2:>10.2f}")
    out.append(f"      {'Memory silicon':<24s}"
               f"{view.memory_silicon_mm2:>10.2f}")
    out.append(f"      {'Total silicon':<24s}"
               f"{view.total_silicon_mm2:>10.2f}")
    out.append(f"      {'Board area':<24s}{view.board_area_mm2:>10.2f}")
    if not view.breakdown_sums:
        out.append("")
        out.append("      BREAKDOWN DEFECT: the contributors do not sum "
                   "to the totals.")
    out.append("")

    out.append("  AREA CONSTRAINT   against the SoC silicon budget")
    if view.soc_budget_mm2 is None:
        out.append("      SoC silicon budget      NOT ESTABLISHED")
        out.append(f"      Status                  {NOT_CONSTRAINED}")
    else:
        out.append(f"      SoC silicon             "
                   f"{view.soc_silicon_mm2:>10.2f} mm2")
        out.append(f"      SoC silicon budget      "
                   f"{view.soc_budget_mm2:>10.2f} mm2")
        out.append(f"      Slack                   "
                   f"{view.soc_slack_mm2:>+10.2f} mm2")
        out.append(f"      Status                  {view.soc_status}")
    out.append("")
    # The budget governs SoC silicon only, and the screen says so: the
    # alternative reading produced EXCEEDS by 78.4% beside a READY gate.
    for line in wrap_text(
            "The budget governs SoC silicon. Memory silicon is reported "
            "and not judged against it: a DRAM die is not constrained by "
            "an SoC die budget, and one HBM stack would exceed it on its "
            "own.", 62):
        out.append(f"      {line}")
    if view.board_budget_mm2 is None:
        out.append("")
        out.append("      Board area budget       NOT ESTABLISHED")
        out.append("      Board area is reported and not judged.")
    out.append("")

    out.append(f"  AREA BOTTLENECK             {view.largest}")
    for line in wrap_text(
            "The LARGEST contributor - the opposite direction from the "
            "throughput bottleneck, which is the lowest. Same role: the "
            "thing to change first.", 62):
        out.append(f"      {line}")
    return out


@dataclass(frozen=True)
class AreaRecommendation:
    action: str
    target: str
    reason: str
    expected_reduction: str
    would_be_wrong_if: Tuple[str, ...]


def recommend_area(view: AreaView) -> Optional[AreaRecommendation]:
    """Tied to a violated budget, or nothing.

    The same rule Performance follows: a design inside its budget has no
    observed limit, and naming a change anyway is the tool preferring an
    architecture.
    """
    if view.soc_status != VIOLATED or not view.largest:
        return None

    target = view.largest
    wrong: List[str] = []
    if not any(c.name == target and c.in_soc
               for c in view.contributors):
        # The largest contributor overall may be memory, which the SoC
        # budget does not govern. Recommending a change to it would not
        # move the violated constraint.
        soc_only = [c for c in view.contributors if c.in_soc]
        if soc_only:
            target = max(soc_only, key=lambda c: c.area_mm2).name
        wrong.append(
            f"The largest contributor overall is {view.largest}, which "
            f"the SoC budget does not govern. This targets the largest "
            f"SoC contributor instead.")

    wrong.append(
        "Area is one axis. A smaller block may cost throughput, and this "
        "recommendation does not check that.")

    return AreaRecommendation(
        action=ACTIONS.get(target, f"Reduce the area of {target}"),
        target=target,
        reason=(f"The SoC silicon budget is exceeded and {target} is the "
                f"largest contributor within it."),
        expected_reduction=NOT_ESTABLISHED,
        would_be_wrong_if=tuple(wrong))


def render_area_recommendation(rec: Optional[AreaRecommendation],
                               view: AreaView) -> List[str]:
    from .visual.text import wrap_text

    out = ["AREA RECOMMENDATION", ""]
    if rec is None:
        out.append("  No change is recommended.")
        out.append("")
        for line in wrap_text(
                "The SoC silicon budget is met. There is no observed "
                "limit for a recommendation to be tied to.", 66):
            out.append(f"  {line}")
        if view.largest:
            out.append("")
            out.append(f"  Largest contributor         {view.largest}")
            out.append("      A fact about the current design, not a "
                       "change to make.")
        return out

    out.append("  Change")
    for line in wrap_text(rec.action, 62):
        out.append(f"      {line}")
    out.append(f"  Target                      {rec.target}")
    out.append("")
    out.append("  Reason")
    for line in wrap_text(rec.reason, 62):
        out.append(f"      {line}")
    out.append("")
    out.append(f"  Expected reduction          {rec.expected_reduction}")
    for line in wrap_text(
            "How much area a change frees needs a counterfactual. The "
            "same refusal applies here as on the performance axis.", 62):
        out.append(f"      {line}")
    out.append("")
    out.append("  This would be wrong if")
    for item in rec.would_be_wrong_if:
        for i, line in enumerate(wrap_text(item, 62)):
            out.append(f"      {line}" if i == 0 else f"        {line}")
    return out
