"""
ppact.view_data - one computation, two screens

WHY THIS LAYER EXISTS
=====================
A notebook renderer and a Streamlit renderer that each compute their own
figures are two engines wearing one name. They agree until one is changed,
and the disagreement surfaces as a user reporting different numbers in
two places - which is the hardest kind of defect to reproduce.

    core engine
        |
    view data          <- everything computed, nothing displayed
        |
    +---+---+
    |       |
 notebook  streamlit   <- display only

A renderer may format, colour, lay out and paginate. It may not compute.

WHAT COUNTS AS COMPUTING
------------------------
Deriving a ratio, choosing which stage is the bottleneck, deciding what a
metric's unit is, picking which figures matter for a demonstration. All of
that is here. `f"{value:.2f}"` is formatting and belongs in a renderer.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

NOT_ESTABLISHED = "NOT ESTABLISHED"
NOT_APPLICABLE = "NOT APPLICABLE"


@dataclass(frozen=True)
class ChartData:
    """One chart's inputs. No figure, no colours, no file."""
    kind: str                    # measured | bottleneck | spider | flow
    title: str
    subtitle: str
    series: Dict[str, Dict[str, Optional[float]]]
    units: Dict[str, str]
    lower_is_better: Tuple[str, ...]
    highlight: Tuple[str, ...]   # which row(s) to mark
    status: str                  # GENERATED | NOT APPLICABLE | MISSING
    note: str = ""


@dataclass(frozen=True)
class DemoView:
    """Everything a screen needs to show one demonstration."""
    number: int
    key: str
    question: str
    short_answer: str
    family: str
    difficulty: str
    primary_axis: str
    why_it_matters: str
    primary_lesson: str

    baseline_label: str
    comparison_label: str
    decision: str
    derived: Tuple[str, ...]

    charts: Tuple[ChartData, ...]
    gates: Dict[str, Tuple[bool, bool]]
    explanation_sections: Dict[str, str]

    @property
    def chart(self) -> Dict[str, ChartData]:
        return {c.kind: c for c in self.charts}


def _section(text: str, heading: str) -> str:
    import re
    m = re.search(rf"## {re.escape(heading)}\n\n(.*?)(\n## |\Z)",
                  text, re.S)
    return m.group(1).strip() if m else ""


def build_demo_view(demo_id: int, dossier_root: str = "") -> DemoView:
    """One demonstration, computed once.

    The explanation is READ from its dossier rather than regenerated -
    it is edited prose, and a renderer that rebuilt it would show a
    different text from the published one.
    """
    import os
    from .demo import DEMOS
    from .demo_library import BY_NUMBER
    from .demo_decisions import DECISIONS
    from .demo_visual import (measured_series, bottleneck_series,
                              build_demo_comparison, DEMO_KEY_METRICS,
                              LOWER_IS_BETTER)
    from .perf_bottleneck import find_bottleneck
    from .review import build_review
    from .system import SystemConfig, evaluate_system
    from .application import APPLICATION_LIBRARY

    demo = DEMOS[demo_id - 1]
    entry = BY_NUMBER[demo_id]
    dec = DECISIONS[demo.key]
    cmp = build_demo_comparison(demo, demo_id)

    charts: List[ChartData] = []

    # --- measured ---------------------------------------------------
    ms = measured_series(demo) or {}
    charts.append(ChartData(
        kind="measured", title="Measured Results",
        subtitle=demo.question,
        series={k: dict(v) for k, v in ms.items()},
        units={k: k[k.find("(") + 1:k.find(")")] if "(" in k else ""
               for k in ms},
        lower_is_better=tuple(k for k in ms if k in LOWER_IS_BETTER),
        highlight=(), status="GENERATED" if ms else "MISSING",
        note="Only the figures this demonstration's answer rests on."))

    # --- bottleneck --------------------------------------------------
    row = demo.rows[-1]
    a = build_review("education_step_by_step", row.application,
                     SystemConfig(**row.config))
    b = find_bottleneck(a)
    stages = bottleneck_series(demo) or {}
    charts.append(ChartData(
        kind="bottleneck", title="Throughput Bottleneck",
        subtitle=f"{row.label} - {demo.question}",
        series={"throughput": {k: v for k, v in stages.items()},
                "slack": {s.name: s.slack_inf_s for s in b.stages}},
        units={"throughput": "inf/s", "slack": "inf/s"},
        lower_is_better=(),
        highlight=(b.bottleneck,) if b.bottleneck else (),
        status="GENERATED" if stages else "MISSING",
        note=f"Required {b.required_inf_s:.0f} inf/s. "
             f"Constraint {b.status}." if b.required_inf_s else ""))

    # --- relative spider ---------------------------------------------
    if cmp is None:
        charts.append(ChartData(
            "spider", "Relative PPACT", demo.question, {}, {}, (), (),
            NOT_APPLICABLE, "nothing to compare"))
    else:
        charts.append(ChartData(
            kind="spider", title="Relative PPACT",
            subtitle=demo.question,
            series={"ratio": {ax.name: ax.ratio for ax in cmp.axes},
                    "baseline": {ax.name: ax.baseline_value
                                 for ax in cmp.axes},
                    "comparison": {ax.name: ax.comparison_value
                                   for ax in cmp.axes}},
            units={ax.name: ax.unit for ax in cmp.axes},
            lower_is_better=(), highlight=(), status="GENERATED",
            note="Baseline is 1.00x. Further out is better on every "
                 "axis. The scale is logarithmic."))

    # --- system flow --------------------------------------------------
    if cmp is not None and cmp.flow_relevant:
        charts.append(ChartData(
            "flow", "System Flow", demo.question, {}, {}, (), (),
            "GENERATED", "The change alters the data path."))
    else:
        charts.append(ChartData(
            "flow", "System Flow", demo.question, {}, {}, (), (),
            NOT_APPLICABLE,
            "The change does not alter the data path, so the picture "
            "would be the same twice."))

    # --- gates ---------------------------------------------------------
    first = demo.rows[0]
    br = evaluate_system(APPLICATION_LIBRARY[first.application],
                         SystemConfig(**first.config))
    cr = evaluate_system(APPLICATION_LIBRARY[row.application],
                         SystemConfig(**row.config))
    gates = {g: (bool(br.gate[g]), bool(cr.gate.get(g, False)))
             for g in sorted(br.gate)}

    # --- explanation ----------------------------------------------------
    sections: Dict[str, str] = {}
    short = ""
    root = dossier_root or "/mnt/user-data/outputs/demo_dossiers"
    fp = os.path.join(root, f"demo_{demo_id:03d}",
                      f"demo_{demo_id:03d}_explanation_en.md")
    if os.path.isfile(fp):
        text = open(fp, encoding="utf-8").read()
        for h in ("1. Question", "2. Short answer", "3. What changed",
                  "4. What the results show", "5. Why it happened",
                  "6. Bottleneck interpretation", "7. Design lesson",
                  "8. What this demonstration does not establish"):
            sections[h.split(". ", 1)[1]] = _section(text, h)
        sections["Why this question matters"] = _section(
            text, "Why this question matters")
        short = sections.get("Short answer", "")

    return DemoView(
        number=demo_id, key=demo.key, question=demo.question,
        short_answer=short, family=entry.family,
        difficulty=entry.difficulty, primary_axis=entry.primary_axis,
        why_it_matters=entry.why_it_matters,
        primary_lesson="", baseline_label=first.label,
        comparison_label=row.label, decision=dec["decision"],
        derived=tuple(dec["derived"]), charts=tuple(charts),
        gates=gates, explanation_sections=sections)


def demo_index() -> List[Tuple[int, str, str, str]]:
    """(number, question, family, difficulty) for the library screen."""
    from .demo import DEMOS
    from .demo_library import BY_NUMBER
    return [(i, d.question, BY_NUMBER[i].family, BY_NUMBER[i].difficulty)
            for i, d in enumerate(DEMOS, 1)]


def flow_map_rows(demo_id: int):
    """Comparative rows: every figure as reference and current.

    A single-design table beside a comparative picture would answer a
    different question from the one the picture answers.
    """
    from .demo import DEMOS
    from .flow_map import build_compared_flow_map
    from .review import build_review
    from .system import SystemConfig

    demo = DEMOS[demo_id - 1]
    b = build_review("education_step_by_step", demo.rows[0].application,
                     SystemConfig(**demo.rows[0].config))
    c = build_review("education_step_by_step", demo.rows[-1].application,
                     SystemConfig(**demo.rows[-1].config))
    cm = build_compared_flow_map(b, c, demo.rows[0].label,
                                 demo.rows[-1].label)
    mods = [(m.name, m.ref_util, m.cur_util, m.ref_share, m.cur_share,
             m.ref_limit, m.cur_limit, m.changed) for m in cm.modules]
    # Demand and capacity travel with the load. A percentage without its
    # numerator and denominator is a figure a reader cannot check.
    links = [(l.source, l.target, l.ref_load, l.cur_load, l.ref_bn,
              l.cur_bn, l.changed, l.ref_demand, l.cur_demand,
              l.ref_available, l.cur_available) for l in cm.links]
    return (mods, links, cm.ref_limiting, cm.cur_limiting,
            cm.ref_kind, cm.cur_kind, cm.reference_label,
            cm.current_label, cm.change_summary, cm.key_insight)


def migration_rows(demo_id: int):
    """Before, after, whether it moved, and what that means."""
    from .demo import DEMOS
    from .flow_map import bottleneck_migration
    from .review import build_review
    from .system import SystemConfig

    demo = DEMOS[demo_id - 1]
    b = build_review("education_step_by_step", demo.rows[0].application,
                     SystemConfig(**demo.rows[0].config))
    c = build_review("education_step_by_step", demo.rows[-1].application,
                     SystemConfig(**demo.rows[-1].config))
    mig = bottleneck_migration(b, c)
    return mig.before, mig.after, mig.moved, mig.reason


def flow_map_png(demo_id: int, out_dir: str = "") -> Dict[str, str]:
    """The block diagram and the migration, as files a screen can show."""
    import os
    import tempfile
    from .demo import DEMOS
    from .flow_map import (build_flow_map, render_flow_map_png,
                           bottleneck_migration, render_migration_png)
    from .review import build_review
    from .system import SystemConfig

    demo = DEMOS[demo_id - 1]
    d = out_dir or os.path.join(tempfile.gettempdir(), "ppact_flowmap")
    os.makedirs(d, exist_ok=True)

    b = build_review("education_step_by_step", demo.rows[0].application,
                     SystemConfig(**demo.rows[0].config))
    c = build_review("education_step_by_step", demo.rows[-1].application,
                     SystemConfig(**demo.rows[-1].config))

    out = {}
    # THE COMPARATIVE MAP. A demonstration is a reference and a current
    # design; showing only the current one leaves the reader asking the
    # first question they have - what was it before?
    from .flow_map import (build_compared_flow_map,
                           render_compared_flow_map_png)
    cm = build_compared_flow_map(b, c, demo.rows[0].label,
                                 demo.rows[-1].label)
    p = render_compared_flow_map_png(
        cm, os.path.join(d, f"map_{demo_id:03d}.png"),
        "System Flow and Bottleneck Map")
    out["map"] = p or "MISSING"
    p = render_migration_png(
        bottleneck_migration(b, c),
        os.path.join(d, f"mig_{demo_id:03d}.png"),
        demo.rows[0].label, demo.rows[-1].label)
    out["migration"] = p or "MISSING"
    return out


def closure_rows(demo_id: int):
    """The comparison closure, as rows a renderer can lay out.

    Every comparison screen calls THIS. A recommendation rule written per
    screen is a rule that drifts per screen.
    """
    import dataclasses
    from .demo import DEMOS
    from .closure import build_closure
    from .flow_map import build_compared_flow_map
    from .review import build_review
    from .system import SystemConfig

    demo = DEMOS[demo_id - 1]
    b = build_review("education_step_by_step", demo.rows[0].application,
                     SystemConfig(**demo.rows[0].config))
    c = build_review("education_step_by_step", demo.rows[-1].application,
                     SystemConfig(**demo.rows[-1].config))
    cm = build_compared_flow_map(b, c, demo.rows[0].label,
                                 demo.rows[-1].label)
    changed = [f.name for f in dataclasses.fields(SystemConfig)
               if demo.rows[0].config.get(f.name)
               != demo.rows[-1].config.get(f.name)]
    cl = build_closure(b, c, changed, cm.key_insight)
    return (list(cl.conclusion), cl.key_insight,
            [(p.title, p.reason, p.priority, p.already_explored,
              p.rule_id, list(p.origin_rule_ids), p.current_value,
              list(p.alternatives), p.target_die,
              list(p.origin_reasons), list(p.omitted_reasons),
              p.family)
             for p in cl.next_comparisons],
            cl.modify_prompt, cl.free_question_prompt,
            [(p.title, p.rule_id, p.suppressed_because,
              p.would_appear_if) for p in cl.not_recommended],
            cl.limiting_element, cl.limiting_kind,
            [(t.stage, t.before, t.after, list(t.removed), t.note)
             for t in cl.trace])


def recommendation_checksum(demo_id: int) -> str:
    """A digest of what was recommended, not of how it looks.

    Pairs with the model digest: if the model moves and this does not,
    the change did not reach the recommendations; if this moves and the
    model did not, something non-deterministic got in.
    """
    import hashlib
    r = closure_rows(demo_id)
    # THE DIGEST COVERS WHAT WAS SAID, not only what was chosen.
    #
    # Reason, rank, hidden reasons and the trace were outside it, so a
    # reworded reason or a reordered trace would not have shown as a
    # change while the document claimed the reasons were identical.
    conclusion, insight, proposals, modify, ask, hidden, lim, kind, tr \
        = r
    parts = [f"limit:{lim}:{kind}"]
    for (title, reason, prio, expl, rule, origins, cur, alts, die,
         orig_reasons, omitted, fam) in proposals:
        parts.append(f"{'+'.join(origins)}>{rule}:{title}:{reason}:"
                     f"{prio}:{expl}:{cur}:{','.join(alts)}:{die}:"
                     f"{orig_reasons}:{omitted}:{fam}")
    for title, rule, why, would in hidden:
        parts.append(f"hidden:{rule}:{title}:{why}:{would}")
    for stage, before, after, removed, note in tr:
        parts.append(f"trace:{stage}:{before}:{after}:"
                     f"{','.join(removed)}")
    parts += list(conclusion)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def engine_provenance() -> Dict[str, str]:
    """Which engine produced what is on screen.

    A figure in a paper and a figure on screen can differ for one honest
    reason - the engine moved - and a reader can only tell if the screen
    says which engine it was.
    """
    import datetime
    from . import __version__, PRODUCT_VERSION
    from .reproducibility import source_checksums

    try:
        import hashlib
        # (path, sha256, size) tuples.
        rows = source_checksums(".")
        joined = "".join(sorted(r[1] for r in rows))
        digest = hashlib.sha256(joined.encode()).hexdigest()[:12]
    except Exception:
        digest = "not available"
    return {"engine": str(__version__), "product": str(PRODUCT_VERSION),
            "digest": digest,
            "generated": datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M")}


def demo_outcome(demo_id: int):
    """The WorkflowOutcome for one demonstration.

    THE UI DOES NOT BUILD ENGINE OBJECTS.

    The Streamlit screen was constructing SystemConfig from the demo's
    rows, which put configuration assembly in the interface - one edit
    away from the interface deciding what a design is.
    """
    from .demo import DEMOS
    from .outcome import comparison, SelectedAnswer
    from .system import SystemConfig

    demo = DEMOS[demo_id - 1]
    first, last = demo.rows[0], demo.rows[-1]
    return comparison(
        "demo", last.application,
        SystemConfig(**first.config), SystemConfig(**last.config),
        (SelectedAnswer(1, "Demonstration", demo.question),
         SelectedAnswer(2, "Starting point", first.label),
         SelectedAnswer(3, "Current design", last.label)))
