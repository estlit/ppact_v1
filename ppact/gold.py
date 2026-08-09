"""
ppact.gold - fixed scenarios a design is run against, and what each can settle

Two thousand internal checks establish that the equations are consistent. They
cannot establish the thing an engineer actually wants to know:

    put a real product in, and does the model reach the conclusion a designer
    would reach?

That is a different question and it needs different evidence. These scenarios
are the fixture for asking it: a fixed application, a fixed reference
architecture, and - where one exists - a real company's stated KPI to compare
the direction of the answer against.

THREE LEVELS OF VALIDATION, AND MOST SCENARIOS ONLY REACH TWO
-------------------------------------------------------------
    EQUATION   the arithmetic is self-consistent. Every scenario reaches this
               and it is the weakest of the three.
    SCENARIO   the design meets or misses a requirement, and moves the right
               way against a reference. Every scenario reaches this.
    INDUSTRY   the direction agrees with a real company's stated objective for
               a real product. ONE scenario reaches this.

The last column is the honest one. Of the six scenarios below, five carry
requirements this course wrote, and only GRS-001 carries figures a company
committed to in a proposal. Presenting all six as industry-validated would be
the same error as calling a self-consistent model a verified one - a level
label is a claim, and five of these cannot make it.

Even GRS-001 is limited: the company's numbers are targets in a proposal, not
measurements of a built system, and the workload parameters underneath are
ours. What it can show is that the model moves the way the company expects,
which is worth having and is not validation.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

LINE = "=" * 82

# INDUSTRY-PARTIAL sits between the two because most real cases land there:
# a company KPI exists, and the model can express some of the boundary it is
# measured over but not all. Collapsing that into either neighbour loses the
# distinction that matters - INDUSTRY overclaims, SCENARIO throws away a real
# objective.
LEVELS = ("EQUATION", "SCENARIO", "INDUSTRY-PARTIAL", "INDUSTRY")

# What a case must satisfy before INDUSTRY-PARTIAL becomes INDUSTRY. Written
# down so promotion is a checklist rather than a judgement made once and
# forgotten.
PROMOTION_CRITERIA = (
    "the start and end points of the published latency figure are stated",
    "the same model, input resolution and precision on both sides",
    "the baseline hardware is identified",
    "the target hardware is identified",
    "pure inference is separated from the full pipeline",
    "the accuracy metric uses the same dataset and definition",
    "any power figure names its boundary - chip, module or system",
)


@dataclass
class GoldScenario:
    gid: str
    title: str
    app_key: str
    # The architecture a student's design is compared against. For an
    # industry-anchored scenario this MUST be the company's own baseline: their
    # targets are stated relative to the system they are replacing, and
    # applying "half the power" against a different reference compares a
    # student's design with one machine and their target with another.
    reference_index: int = 0
    use_industry_baseline: bool = False
    # The company case, if there is one. Without it the scenario cannot reach
    # the INDUSTRY level, and says so.
    industry_case: Optional[str] = None
    level: str = "SCENARIO"
    requirement_source: str = ""
    can_settle: str = ""
    cannot_settle: str = ""
    # What stands between this and the next level up. Empty for a scenario
    # already at INDUSTRY, or for one that has no company objective to reach.
    promotion_blockers: Tuple[str, ...] = ()
    modelled: bool = True
    # A case this scenario is ABOUT but cannot use as an objective. Kept
    # separate from industry_case so that naming a company here cannot be
    # mistaken for having an objective the model can check.
    related_case: Optional[str] = None


SCENARIOS: List[GoldScenario] = [
    GoldScenario(
        "GRS-001", "Autonomous agricultural machine", "drone",
        industry_case="IND-10", level="INDUSTRY",
        use_industry_baseline=True,
        requirement_source="A company proposal: latency under 100 ms at the "
                           "sensor-to-decision boundary, half the power of the "
                           "GPU it replaces, accuracy dropping no more than 5 "
                           "points.",
        can_settle="Whether the model moves the way the company expects when "
                   "a GPU is replaced by an on-device accelerator: power down "
                   "substantially, accuracy down slightly, latency inside a "
                   "budget it does not dominate.",
        cannot_settle="Whether the company's numbers are achievable. Their "
                      "targets are aims in a proposal, no system has been "
                      "measured, the workload parameters are ours, and their "
                      "latency boundary is wider than the model reaches."),

    GoldScenario(
        "GRS-002A", "Inspection robot, vision model only", "robot",
        industry_case="IND-04", level="INDUSTRY-PARTIAL",
        use_industry_baseline=True,
        requirement_source="A company proposal: a segmentation model at 20 ms "
                           "on a workstation GPU, 15 ms wanted on an "
                           "on-device accelerator, with accuracy retained to "
                           "99% of the GPU model's.",
        can_settle="Whether a 25% latency improvement is plausible when a "
                   "workstation GPU is replaced by an edge accelerator on one "
                   "segmentation model, and what the accuracy costs.",
        cannot_settle="Whether the published 20 ms and 15 ms are what this "
                      "model computes. The KPI row is named for detection AND "
                      "region-of-interest extraction and the measurement is an "
                      "average over a hundred images, so it is not pure "
                      "inference - but where it starts is not stated. That "
                      "single unknown is why this is PARTIAL and not INDUSTRY.",
        promotion_blockers=(
            "the start point of the 20 ms figure is not stated - it may or may "
            "not include image load and preprocessing",
            "the accuracy metric is described as mAP against the GPU model "
            "rather than against a fixed dataset",
        )),

    GoldScenario(
        "GRS-002B", "Inspection robot, whole product", "robot",
        industry_case=None, level="SCENARIO",
        related_case="IND-04",
        requirement_source="The same proposal, but the product integrates "
                           "camera, LiDAR and non-destructive-evaluation "
                           "sensors on one robot.",
        can_settle="Nothing about the product. It is listed so that the split "
                   "is visible: a single-model KPI and a whole-robot KPI are "
                   "different numbers and the proposal contains both.",
        cannot_settle="The whole of it. Multi-sensor fusion is outside the "
                      "model, so a product-level figure cannot be computed "
                      "here at all - and a report that quietly used the "
                      "vision-only result in its place would be answering a "
                      "different question.",
        modelled=False,
        promotion_blockers=(
            "sensor fusion across camera, LiDAR and NDE is not modelled",
        )),

    GoldScenario(
        "GRS-003", "Industrial vision inspection", "industrial_vision",
        industry_case=None, level="SCENARIO",
        requirement_source="Written for this course from the shape of a "
                           "multi-camera inspection line, with an accuracy "
                           "requirement tight enough to matter.",
        can_settle="Whether the host or the accelerator is the constraint. It "
                   "is the host, and a larger array does not help - which is "
                   "the point of the scenario.",
        cannot_settle="Anything about a real product, and the worst-case "
                      "latency an inspection line actually cares about - this "
                      "model has no tail, only an average."),

    GoldScenario(
        "GRS-004", "Smart camera", "smart_camera",
        industry_case=None, level="SCENARIO",
        requirement_source="Written for this course, with a cost budget tight "
                           "enough that silicon area matters.",
        can_settle="Whether a second die is worth its cost on a product "
                   "shipped by the million. It is a rounding error against "
                   "the bill of materials, which surprises most people.",
        cannot_settle="Anything about a real product, and anything about "
                      "manufacturing yield or supply, which dominate a "
                      "high-volume bill of materials and are absent here."),

    GoldScenario(
        "GRS-005", "Medical imaging", "medical",
        industry_case=None, level="SCENARIO",
        requirement_source="Written for this course, with an accuracy budget "
                           "chosen to be tight.",
        can_settle="Whether an INT8 pipeline fits inside a half-point "
                   "accuracy budget. It does not, and no amount of extra "
                   "compute changes that.",
        cannot_settle="Anything about a real product, and anything about "
                      "clinical acceptability - the accuracy figure here is a "
                      "single percentage standing in for a whole regulatory "
                      "question."),

    GoldScenario(
        "GRS-006", "LLM edge inference", "llm_service",
        industry_case=None, level="SCENARIO",
        requirement_source="Written for this course, with a token rate chosen "
                           "against an early and optimistic version of the "
                           "model - which is why its reference has had to grow "
                           "three times.",
        can_settle="Whether decode is memory bound and by how much, and what "
                   "a wider memory interface buys.",
        cannot_settle="Anything about a real product, and the delivered token "
                      "rate to better than the serving-efficiency band - "
                      "roughly a factor of two."),
]

BY_ID = {s.gid: s for s in SCENARIOS}


def _context(s: GoldScenario):
    """Application key, reference config and whether to clean up afterwards.

    ONE builder call. An earlier version called it from two places and the
    second popped the temporary application the first had registered, so every
    industry-anchored scenario reported n/a.
    """
    if s.use_industry_baseline and s.industry_case:
        from .industry import RUNNABLE
        builder = RUNNABLE.get(s.industry_case)
        if builder is not None:
            app_key, ref_cfg, _ = builder()
            return app_key, ref_cfg, True
    from .designs import designs_for
    return s.app_key, designs_for(s.app_key)[s.reference_index].config, False


def _reference(s: GoldScenario):
    """The architecture to compare against.

    An industry-anchored scenario uses the COMPANY'S baseline, not the
    course's. Their targets are relative to the system they are replacing, and
    reading "half the power" against anything else compares a design with one
    machine and its target with another.
    """
    if s.use_industry_baseline and s.industry_case:
        from .industry import RUNNABLE
        builder = RUNNABLE.get(s.industry_case)
        if builder is not None:
            app_key, ref_cfg, _ = builder()
            from .application import APPLICATION_LIBRARY
            APPLICATION_LIBRARY.pop(app_key, None)
            return ref_cfg
    from .designs import designs_for
    return designs_for(s.app_key)[s.reference_index].config


def _application(s: GoldScenario):
    """The application to run. For an industry scenario, the company's own.

    The course's drone application and the company's agricultural machine are
    different workloads with different requirements. Judging a company target
    against the course's application would be comparing their objective with
    our problem.
    """
    if s.use_industry_baseline and s.industry_case:
        from .industry import RUNNABLE
        builder = RUNNABLE.get(s.industry_case)
        if builder is not None:
            app_key, _, _ = builder()
            return app_key, True
    return s.app_key, False


def run_gold(gid: str, student_config=None, duration_s: float = 60.0) -> dict:
    """Run one scenario and report what it can and cannot settle."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    s = BY_ID[gid]
    app_key, ref_cfg, cleanup = _context(s)
    app = APPLICATION_LIBRARY[app_key]
    cfg = student_config if student_config is not None else ref_cfg
    is_ref = student_config is None or student_config == ref_cfg

    r = evaluate_system(app, cfg)
    ref = evaluate_system(app, ref_cfg)
    m, rm = r.metrics, ref.metrics

    print(f"\n{LINE}")
    print(f" {s.gid}  {s.title}")
    print(LINE)
    level_note = {
        "INDUSTRY": "   - a company objective, and the boundaries line up",
        "INDUSTRY-PARTIAL": "   - a company objective, but only part of its "
                            "boundary is modelled",
        "SCENARIO": "   - no company objective the model can read",
    }[s.level]
    print(f"  validation level   {s.level}{level_note}")
    print(f"  requirements from  {s.requirement_source}")

    # --- 1. does it meet the requirement ---------------------------------
    print(f"\n  1. REQUIREMENTS")
    bad = [g for g, ok in r.gate.items() if not ok]
    print(f"     {sum(1 for o in r.gate.values() if o)}/{len(r.gate)}"
          + ("" if r.passes else "   failing: " + ", ".join(bad)))

    # --- 2. against the reference ----------------------------------------
    print(f"\n  2. AGAINST THE REFERENCE")
    if is_ref:
        print(f"     This IS the starting point.")
    else:
        h = (f"     {'':<18s}{'design':>13s}{'reference':>12s}{'change':>10s}")
        print(h)
        for label, key, lower_better in (
                ("latency (ms)", "Latency (ms)", True),
                ("throughput (/s)", "Throughput (inf/s)", False),
                ("power (W)", "System power (W)", True),
                ("accuracy (%)", "Deployment accuracy (%)", False),
                ("cost (USD)", "System cost (USD)", True)):
            a, b = m[key], rm[key]
            chg = (a / b - 1) * 100 if b else 0.0
            better = (a < b) if lower_better else (a > b)
            tag = "" if abs(chg) < 0.5 else ("  better" if better else "  worse")
            print(f"     {label:<18s}{a:>13.2f}{b:>12.2f}{chg:>+9.1f}%{tag}")

    # --- 3. against the industry objective, where one exists --------------
    print(f"\n  3. AGAINST A COMPANY OBJECTIVE")
    if s.industry_case is None:
        print(f"     None attached. This scenario cannot reach the industry")
        print(f"     level, and a report that implied otherwise would be")
        print(f"     claiming evidence it does not have.")
    else:
        from .industry import CASES, LATENCY_BOUNDARIES
        c = next(x for x in CASES if x.cid == s.industry_case)
        print(f"     case               {c.cid}  {c.company_role}")
        print(f"     KPI boundary       {c.latency_boundary}")
        pw = (1 - m["System power (W)"] / rm["System power (W)"]) * 100
        acc = rm["Deployment accuracy (%)"] - m["Deployment accuracy (%)"]
        for label, got, target, unit, direction in (
                ("power reduction", pw,
                 c.target.get("power_reduction_pct"), "%", "at least"),
                ("accuracy drop", acc, c.target.get("map_drop_pp"), "pp",
                 "no more than")):
            if target is None:
                continue
            ok = got >= target if direction == "at least" else got <= target
            print(f"     {label:<18s}simulated {got:>7.1f}{unit}   "
                  f"company {direction} {target:g}{unit}   "
                  f"{'direction agrees' if ok else 'DIRECTION DISAGREES'}")
        if "latency_ms" in c.target:
            # Only a boundary WIDER than the pipeline is incomparable.
            # AI_PIPELINE and PURE_INFERENCE are what the model reports, and
            # refusing those too would throw away the comparisons that work.
            wider = c.latency_boundary in ("PERCEPTION_DECISION",
                                           "SENSOR_TO_CONTROL")
            if wider:
                print(f"     latency            not compared - the company "
                      f"target is measured at")
                print(f"                        {c.latency_boundary}, wider "
                      f"than the model reaches")
            else:
                got = m["Latency (ms)"]
                tgt = c.target["latency_ms"]
                base = rm["Latency (ms)"]
                impr = (1 - got / base) * 100 if base else 0.0
                want = (1 - tgt / c.baseline.get("latency_ms", tgt)) * 100 \
                    if c.baseline.get("latency_ms") else None
                print(f"     latency            simulated {got:>7.2f} ms   "
                      f"company target {tgt:g} ms")
                if want is not None:
                    print(f"     latency improvement simulated {impr:>6.1f}%   "
                          f"company implies {want:>5.1f}%")
                    print(f"                        boundary {c.latency_boundary}"
                          f" on both sides - comparable")
        print(f"\n     This is DIRECTION AGREEMENT, not validation. The "
              f"company's")
        print(f"     figures are targets in a proposal, no built system has "
              f"been")
        print(f"     measured, and the workload parameters underneath are ours.")

    # --- what this scenario can and cannot settle -------------------------
    print(f"\n  WHAT THIS SCENARIO CAN SETTLE")
    print(f"     {s.can_settle}")
    print(f"\n  WHAT IT CANNOT")
    print(f"     {s.cannot_settle}")
    if s.promotion_blockers:
        nxt = {"SCENARIO": "INDUSTRY-PARTIAL",
               "INDUSTRY-PARTIAL": "INDUSTRY"}.get(s.level)
        print(f"\n  WHAT WOULD PROMOTE IT TO {nxt}")
        for b in s.promotion_blockers:
            print(f"     - {b}")
        print(f"\n     Full checklist in PROMOTION_CRITERIA. Promotion is a "
              f"question")
        print(f"     about the EVIDENCE, never about the model agreeing more "
              f"closely -")
        print(f"     tuning a coefficient until a published figure is matched "
              f"would")
        print(f"     move the number and leave the level exactly where it is.")
    print(LINE)
    if cleanup:
        APPLICATION_LIBRARY.pop(app_key, None)
    return {"gid": gid, "passes": r.passes, "metrics": m, "level": s.level}


def run_all_gold(student_config=None, duration_s: float = 60.0) -> None:
    """Every scenario, with the level counts stated rather than the total."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    print(f"\n{LINE}")
    print(" GOLD REFERENCE SCENARIOS")
    print(LINE)
    head = (f"  {'id':<9s}{'scenario':<32s}{'level':<18s}{'requirements':>12s}"
            f"{'company KPI':>13s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for s in SCENARIOS:
        app_key, ref_cfg, cleanup = _context(s)
        cfg = student_config if student_config is not None else ref_cfg
        try:
            r = evaluate_system(APPLICATION_LIBRARY[app_key], cfg)
            req = f"{sum(1 for o in r.gate.values() if o)}/{len(r.gate)}"
        except Exception:
            req = "n/a"
        finally:
            if cleanup:
                APPLICATION_LIBRARY.pop(app_key, None)
        kpi = s.industry_case or (f"({s.related_case})" if s.related_case
                                  else "-")
        print(f"  {s.gid:<9s}{s.title[:31]:<32s}{s.level:<18s}{req:>12s}"
              f"{kpi:>13s}")

    levels = {lv: sum(1 for s in SCENARIOS if s.level == lv) for lv in LEVELS}
    n_ind = levels.get("INDUSTRY", 0)
    n_part = levels.get("INDUSTRY-PARTIAL", 0)
    print(f"\n  {n_ind} of {len(SCENARIOS)} scenarios reach INDUSTRY - a "
          f"company objective")
    print(f"  whose measurement boundary the model can match. {n_part} carry a "
          f"company")
    print(f"  objective the model can only partly reach, and the rest check a "
          f"design")
    print(f"  against a requirement this course wrote.")
    print(f"\n  A low count is not a defect. Cases where an industrial KPI AND "
          f"its")
    print(f"  measurement boundary are both public are genuinely rare, and "
          f"keeping")
    print(f"  the label for the few that qualify is worth more than applying "
          f"it")
    print(f"  broadly - a level is a claim about evidence, not a description "
          f"of")
    print(f"  ambition.")
    print(LINE)


# Promotion order, in the sequence the evidence makes plausible rather than the
# sequence the structures fit. GRS-002A is closest because a single vision
# model on a single stream is what this model does best; the rest are held up
# by boundaries rather than by architecture.
PROMOTION_QUEUE = (
    ("GRS-002A", "wall-climbing inspection robot",
     "needs the start point of its latency figure. Closest of the four."),
    ("IND-09", "multi-camera heavy equipment robot",
     "structure fits the dual-engine model well, but its power boundary is "
     "unstated and its KPI covers a LiDAR fusion stage that is not modelled."),
    ("IND-05", "drone survey",
     "the patch-level figure is comparable; the whole-frame workflow it sits "
     "inside is a different boundary and needs tiling."),
    ("IND-02", "shipboard LLM",
     "furthest away: no latency figure, no context length, and a concurrency "
     "condition the single-stream model cannot represent."),
)


def print_promotion_queue() -> None:
    print(f"\n{LINE}")
    print(" PROMOTION QUEUE")
    print(LINE)
    print("  What stands between each candidate and an industry-level label.")
    print("  In every case it is EVIDENCE about a measurement boundary, not a")
    print("  missing feature - which is why none of these is a development")
    print("  task.\n")
    for cid, title, blocker in PROMOTION_QUEUE:
        print(f"  {cid:<10s}{title}")
        print(f"    {blocker}\n")
    print("  A candidate is promoted when its boundary becomes known, never")
    print("  when the model's number moves closer to its target.")
    print(LINE)
