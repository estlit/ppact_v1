"""
ppact.demo_visual - a demo's charts, as a relative comparison

WHY DEMOS NEEDED A DIFFERENT CHART
==================================
The spider scores against the application's requirement, where 50 means
"meets it exactly". That is right for assessing a design and wrong for a
demonstration, because a demo's two designs usually sit far above the
requirement and both clip at 100:

    Demo 001   Performance 50 / 50    Cost 100+ / 100+   Area 100+ / 100+
               "The two normalized profiles overlap on all displayed axes."

A demo about a sixteen-fold memory change showed no difference at all. The
normalisation was not wrong; it was answering the other question.

Here the BASELINE is 1.00x on every axis and the comparison is a ratio to
it. Nothing clips, because a ratio has no ceiling.

    Performance   comparison / baseline      higher is better
    Power         baseline / comparison      less power is better
    Area          baseline / comparison
    Cost          baseline / comparison
    Traffic       comparison balance / baseline balance

Every axis is oriented so ABOVE 1.00 IS BETTER. Without that a reader has
to remember which way each axis runs, and a spider is exactly the shape
that discourages remembering.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

NOT_ESTABLISHED = "NOT ESTABLISHED"
NOT_APPLICABLE = "NOT APPLICABLE"

# Axis -> (metric, higher_is_better_in_the_metric)
# PERFORMANCE IS THE PIPELINE CAPACITY, not the delivered rate.
#
# Delivered throughput is min(capacity, what the application asks for), so
# any design comfortably above its target reports the target. Across the
# fifteen demos that made twelve of them show Performance 1.00x - a
# sixteen-fold memory change reported as no change at all.
#
# Capacity is what the structure could sustain, which is what a demo
# altering the structure is demonstrating.
RELATIVE_AXES: Tuple[Tuple[str, str, bool], ...] = (
    ("Performance", "Pipeline capacity (inf/s)", True),
    ("Power", "System power (W)", False),
    ("Area", "SoC silicon (mm2)", False),
    ("Cost", "System cost (USD)", False),
    # Traffic is computed from the balance, not a metric.
    ("Traffic", "", True),
)

# A demo shows a system flow only when the change alters the data path.
# Everything else would be the same picture twice.
FLOW_RELEVANT_FIELDS = ("preprocessing_mode", "secondary_compute",
                        "execution_mode", "work_split", "memory",
                        "memory_devices")


@dataclass(frozen=True)
class RelativeAxis:
    name: str
    baseline_value: Optional[float]
    comparison_value: Optional[float]
    ratio: Optional[float]          # >1 is better, on every axis
    unit: str
    note: str = ""

    @property
    def established(self) -> bool:
        return self.ratio is not None


@dataclass(frozen=True)
class DemoComparison:
    demo_key: str
    demo_number: int
    question: str
    baseline_label: str
    comparison_label: str
    axes: Tuple[RelativeAxis, ...]
    flow_relevant: bool
    changed_fields: Tuple[str, ...]


def _traffic_balance(analysis) -> Optional[float]:
    from .traffic import build_traffic_balance
    return build_traffic_balance(analysis).balance_pct


def relative_axes(base, comp) -> List["RelativeAxis"]:
    """The five relative axes for two completed analyses.

    Lifted out of `build_demo_comparison` so a report built
    from a WorkflowOutcome uses the SAME construction as a
    demonstration. Two copies would drift, and a chart is the
    one place a difference is invisible.

    The slice stops before the demo-specific work: taking the
    whole body carried `first.config` in with it and raised
    NameError on the first call.
    """
    bm = base.current_result.metrics
    cm = comp.current_result.metrics
    axes: List[RelativeAxis] = []
    for name, key, higher in RELATIVE_AXES:
        if name == "Traffic":
            b, c = _traffic_balance(base), _traffic_balance(comp)
            unit = "% balance"
        else:
            b, c = bm.get(key), cm.get(key)
            unit = key[key.find("(") + 1:key.find(")")] if "(" in key else ""

        ratio = None
        note = ""
        if b is None or c is None:
            note = "not computed for one of the two designs"
        elif (isinstance(b, float) and math.isnan(b)) or \
                (isinstance(c, float) and math.isnan(c)):
            # A design that cannot run has no ratio. Reporting one would
            # compare a machine that works with one that does not.
            note = "one design produces no figure"
        elif b <= 0 or c <= 0:
            note = "a zero or negative figure has no ratio"
        else:
            ratio = (c / b) if higher else (b / c)
        axes.append(RelativeAxis(name, b, c, ratio, unit, note))

    return axes


def build_demo_comparison(demo, number: int) -> Optional[DemoComparison]:
    """Baseline is the first row, comparison the last.

    Returns None when a demo has nothing to compare - a single row, or two
    rows on different applications. A manufactured partner would be a
    comparison the demo never made.
    """
    from .review import build_review
    from .system import SystemConfig

    if len(demo.rows) < 2:
        return None
    # THE PAIR THE DEMONSTRATION DECLARES, or the ends when it declares
    # none. Taking first-to-last across a 2x2 crossed both axes at
    # once and drew a picture of a question the demo was not asking.
    pair = getattr(demo, "spider_pair", None)
    if pair and max(pair) < len(demo.rows):
        first, last = demo.rows[pair[0]], demo.rows[pair[1]]
    else:
        first, last = demo.rows[0], demo.rows[-1]
    if first.application != last.application:
        return None

    base_cfg = SystemConfig(**first.config)
    comp_cfg = SystemConfig(**last.config)
    base = build_review("education_step_by_step", first.application,
                        base_cfg)
    comp = build_review("education_step_by_step", last.application,
                        comp_cfg)
    bm, cm = base.current_result.metrics, comp.current_result.metrics

    axes = relative_axes(base, comp)
    changed = tuple(f for f in FLOW_RELEVANT_FIELDS
                    if first.config.get(f) != last.config.get(f))
    return DemoComparison(
        demo_key=demo.key, demo_number=number, question=demo.question,
        baseline_label=first.label, comparison_label=last.label,
        axes=tuple(axes), flow_relevant=bool(changed),
        changed_fields=changed)


def render_relative_spider(cmp: DemoComparison, path: str
                           ) -> Optional[str]:
    """Baseline at 1.00x, comparison relative to it.

    An unestablished axis BREAKS the polygon rather than plotting at the
    centre: the centre is a ratio of zero, which would say the comparison
    is infinitely worse.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None

    names = [a.name for a in cmp.axes]
    n = len(names)
    ang = [i / n * 2 * math.pi for i in range(n)]
    ang += ang[:1]

    raw = [a.ratio if a.established else float("nan") for a in cmp.axes]

    # A LOG RADIAL SCALE, because ratios are multiplicative.
    #
    # On a linear scale one large ratio flattens everything else: a demo
    # with Traffic at 9.44x pushed Cost 0.18x, Power 0.65x and Area 1.00x
    # into a knot at the centre with their labels overlapping. Four of the
    # fifteen were unreadable that way.
    #
    # Log also makes the scale symmetric about the baseline: 0.5x and 2.0x
    # sit the same distance from 1.00x, which is what "half as good" and
    # "twice as good" should look like.
    ratios = [math.log10(r) if r == r and r > 0 else float("nan")
              for r in raw]
    ones = [0.0] * n

    finite = [r for r in ratios if r == r]
    reach = max([abs(v) for v in finite] + [math.log10(1.3)])
    hi, lo = reach * 1.20, -reach * 1.20

    fig, ax = plt.subplots(figsize=(8.6, 8.2),
                           subplot_kw=dict(polar=True))
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(ang[:-1])
    ax.set_xticklabels(names, fontsize=12, fontweight="bold")
    ax.set_ylim(lo, hi)
    # Ticks are RATIOS, not their logarithms - a reader should never see
    # a log axis label on a chart whose subject is "how many times".
    ticks, labels_r = [], []
    for mult in (0.1, 0.2, 0.25, 0.5, 1.0, 2.0, 4.0, 10.0):
        v = math.log10(mult)
        if lo <= v <= hi:
            ticks.append(v)
            labels_r.append(f"{mult:g}x")
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels_r, fontsize=8.5, color="#666666")

    ax.plot(ang, ones + ones[:1], color="#2E5C8A", linewidth=2.2,
            linestyle="-", label=f"{cmp.baseline_label}  (baseline, 1.00x)")
    ax.plot(ang, ratios + ratios[:1], color="#9C2B2B", linewidth=2.6,
            linestyle="--", label=f"{cmp.comparison_label}")
    ax.fill(ang, ratios + ratios[:1], color="#9C2B2B", alpha=0.10)

    for a, angle, r in zip(cmp.axes, ang[:-1], ratios):
        if not a.established:
            ax.text(angle, 0.0, "n/e", color="#7A8894", fontsize=10,
                    fontweight="bold", ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              ec="none"))
            continue
        ax.text(angle, r, f"{a.ratio:.2f}x", color="#9C2B2B", fontsize=10,
                fontweight="bold", ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                          ec="none", alpha=0.9))

    # A CHART BUILT FROM A WORKFLOW IS NOT A DEMONSTRATION.
    #
    # The report passed demo_number=0 because it has no demonstration,
    # and the chart printed "Demo 000" beside a screen headed
    # "Demo 001" - two identifiers for one thing. A number of 0 means
    # there is no demonstration, and the title says so.
    # THE NAME SAYS WHICH CHART THIS IS.
    #
    # This and the requirement chart shared the title "Architecture
    # Balance" and the same five axis names while answering different
    # questions: there 50 means the requirement is exactly met and 100
    # is a clipped ceiling; here 1.00x means nothing changed and there
    # is no ceiling. A reader comparing "50" with "0.51x" was comparing
    # two scales.
    from .visual.balance import COMPARISON_TITLE
    heading = (COMPARISON_TITLE if not cmp.demo_number
               else f"Demo {cmp.demo_number:03d}  ·  {COMPARISON_TITLE}")
    fig.suptitle(heading,
                 fontsize=14, fontweight="bold", y=0.98)
    fig.text(0.5, 0.935, cmp.question, ha="center", fontsize=11,
             color="#333333")
    # Two short lines, not one long one: at 8.6 inches the single line
    # ran the full width and read as a paragraph rather than a caption.
    # WHICH FIGURE EACH AXIS READS.
    #
    # "Performance" names a different quantity on each of this
    # project's charts - pipeline capacity here, delivered throughput
    # on the requirement chart. A reader who watched latency improve
    # and saw Performance fall had no way to learn which one this axis
    # was reporting.
    fig.text(0.5, 0.087,
             "Performance reads sustainable pipeline capacity, not "
             "execution latency.  Area reads SoC silicon, not memory "
             "silicon.",
             ha="center", fontsize=9, color="#555555")
    fig.text(0.5, 0.065,
             "Baseline is 1.00x on every axis. Further out is better.",
             ha="center", fontsize=9.5, color="#333333")
    fig.text(0.5, 0.043,
             "The scale is logarithmic: 0.5x and 2x sit equally far "
             "from 1x. No clipping - a ratio has no ceiling.",
             ha="center", fontsize=9, color="#333333")
    fig.text(0.5, 0.021,
             "n/e = not established: no basis on which a score would "
             "be justified. Not a score of zero.",
             ha="center", fontsize=8.5, color="#666666")
    # THE LEGEND SITS ABOVE THE CHART, not beside its top-left axis.
    #
    # Anchored to the upper right of the polar axes, the legend's
    # second row ran into the `Performance` label at the top of the
    # circle once the comparison labels grew - a workflow label reads
    # "NPU 32x32 / LPDDR5  /  ISP and NPU assisted", forty-three
    # characters against the fourteen a demonstration row uses.
    #
    # Centred above the plot and given room by the layout rectangle,
    # which is the fix that survives a longer label. Shrinking the type
    # would trade one legibility problem for another.
    # MEASURED, not guessed. `bbox_to_anchor` is in AXES coordinates
    # and the polar axes fill the plotting area, so 1.02 put the
    # legend's lower edge two per cent above the circle - which is
    # where the `Performance` label sits. The label needs clearing too.
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.10),
              ncol=1, frameon=False, fontsize=9.5,
              handlelength=2.2, borderaxespad=0.0)
    fig.tight_layout(rect=(0.02, 0.09, 1, 0.83))
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


# ==============================================================================
# Measured results, per demo
# ==============================================================================
#
# NOT every metric on every demo. A demo about process node cost and a demo
# about preprocessing placement prove different claims, and a fixed set of
# bars would bury the one figure that matters under four that do not move.
#
# The metrics below are chosen per demo to be the ones its stated answer
# rests on. That is an editorial judgement, written here rather than
# derived, because nothing in the demo data says which figure carries its
# conclusion.

# Five entries were revised after a cross-chart check: the spider's
# longest axis named a quantity the measured chart did not show. A summary
# pointing at evidence the reader was not given is a summary of a
# different design.
DEMO_KEY_METRICS: Dict[str, Tuple[str, ...]] = {
    "memory":   ("Latency (ms)", "System cost (USD)"),
    "engine":   ("Latency (ms)", "Pipeline capacity (inf/s)",
                 "Traffic balance (%)"),
    "dual":     ("Latency (ms)", "Traffic balance (%)"),
    "node":     ("Latency (ms)", "SoC silicon (mm2)"),
    "order":    ("Latency (ms)", "System cost (USD)",
                 "SoC silicon (mm2)"),
    "finest":   ("Latency (ms)", "System cost (USD)",
                 "SoC silicon (mm2)"),
    # TRAFFIC BALANCE IS THIS DEMONSTRATION'S POINT.
    #
    # Demo 007 asks when a second engine is worth having, and its
    # answer is "only once the memory can feed it": the pair raises
    # bandwidth demand and the balance follows. The spider named
    # Traffic as the widest change while the measured chart showed
    # latency and cost, so a reader could not check the claim the
    # picture was making. Cost and latency stay - nothing is removed.
    "together": ("Latency (ms)", "System cost (USD)",
                 "Traffic balance (%)"),
    "shipping": ("Latency (ms)", "System power (W)",
                 "System cost (USD)"),
    "host":     ("Latency (ms)", "System cost (USD)"),
    "offload":  ("Latency (ms)", "System power (W)",
                 "SoC silicon (mm2)"),
    "capacity": ("Latency (ms)", "System cost (USD)"),
    "fit":      ("Latency (ms)", "Memory capacity (GB)",
                 "System cost (USD)"),
    "cheaper":  ("System cost (USD)", "System power (W)"),
    "split":    ("Latency (ms)", "Pipeline capacity (inf/s)"),
    "nodecost": ("Logic die cost (USD)", "Latency (ms)",
                 "SoC silicon (mm2)"),
}

LOWER_IS_BETTER = ("Latency (ms)", "System power (W)",
                   "System cost (USD)", "SoC silicon (mm2)",
                   "Logic die cost (USD)")


def measured_series(demo) -> Optional[Dict[str, Dict[str, float]]]:
    """The exact numbers the measured chart will draw.

    Extracted so a rule can compare what REACHED THE CANVAS against the
    dossier CSV. Recomputing the values in the test would check the model
    twice and the renderer not at all.
    """
    import math as _m
    from .system import SystemConfig, evaluate_system
    from .application import APPLICATION_LIBRARY
    from .review import build_review
    from .traffic import build_traffic_balance

    keys = DEMO_KEY_METRICS.get(demo.key)
    if not keys:
        return None
    out: Dict[str, Dict[str, float]] = {k: {} for k in keys}
    for r in demo.rows:
        m = evaluate_system(APPLICATION_LIBRARY[r.application],
                            SystemConfig(**r.config)).metrics
        for k in keys:
            if k == "Traffic balance (%)":
                v = build_traffic_balance(build_review(
                    "education_step_by_step", r.application,
                    SystemConfig(**r.config))).balance_pct
            else:
                v = m.get(k)
            out[k][r.label] = (float("nan") if v is None
                               or (isinstance(v, float) and _m.isnan(v))
                               else float(v))
    return out


def bottleneck_series(demo, row_index: int = -1
                      ) -> Optional[Dict[str, float]]:
    """The stage throughputs the bottleneck chart will draw."""
    from .system import SystemConfig
    from .review import build_review
    from .perf_bottleneck import find_bottleneck

    row = demo.rows[row_index]
    b = find_bottleneck(build_review("education_step_by_step",
                                     row.application,
                                     SystemConfig(**row.config)))
    return {s.name: s.inf_s for s in b.stages} if b.stages else None


def render_measured_comparison(demo, number: int, path: str
                               ) -> Optional[str]:
    """The figures the demo's answer actually rests on, every row.

    All rows, not just the first and last: a demo with three rows is
    usually showing a turning point, and the middle row is where it turns.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None
    from .system import SystemConfig, evaluate_system
    from .application import APPLICATION_LIBRARY

    keys = DEMO_KEY_METRICS.get(demo.key)
    if not keys:
        return None

    from .review import build_review
    from .traffic import build_traffic_balance

    labels, series = [], {k: [] for k in keys}
    for r in demo.rows:
        m = evaluate_system(APPLICATION_LIBRARY[r.application],
                            SystemConfig(**r.config)).metrics
        labels.append(r.label)
        for k in keys:
            if k == "Traffic balance (%)":
                # Not an engine metric - a track figure, computed here so
                # the chart can show what the spider's Traffic axis means.
                v = build_traffic_balance(build_review(
                    "education_step_by_step", r.application,
                    SystemConfig(**r.config))).balance_pct
            else:
                v = m.get(k)
            series[k].append(
                float("nan") if v is None
                or (isinstance(v, float) and math.isnan(v)) else float(v))

    n = len(keys)
    fig, axes = plt.subplots(1, n, figsize=(4.6 * n, 5.2))
    if n == 1:
        axes = [axes]
    for ax, k in zip(axes, keys):
        vals = series[k]
        finite = [v for v in vals if v == v]
        best = (min(finite) if k in LOWER_IS_BETTER else max(finite)) \
            if finite else None

        # A ROW WITH NO FIGURE ANYWHERE is not highlighted anywhere.
        #
        # Demo 012's undersized design has no latency, and teal on its
        # cheaper cost read as "the better buy" - for the design that
        # does not run. Teal means best value shown; a design missing a
        # figure has not been shown to be best at anything.
        incomplete = {j for j in range(len(labels))
                      if any(series[kk][j] != series[kk][j]
                             for kk in keys)}
        colours = ["#8A99A6" if j in incomplete
                   else ("#2E7A80" if v == best else "#8A99A6")
                   for j, v in enumerate(vals)]
        x = list(range(len(labels)))
        ax.bar(x, [0 if v != v else v for v in vals], color=colours,
               width=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=9, rotation=15, ha="right")
        ax.set_title(k, fontsize=11, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)
        for xi, v in zip(x, vals):
            if v != v:
                # A missing figure is labelled, not drawn as a zero bar.
                ax.text(xi, 0, "no figure", ha="center", va="bottom",
                        fontsize=9, color="#9C2B2B", fontweight="bold")
            else:
                # PRECISION FOLLOWS THE SPREAD. Two decimals rendered
                # 19.432 and 19.433 as the same number on a demo whose
                # whole point is a sub-1% difference.
                # One finite value has no spread, and the rule then
                # chose four decimals for a lone bar. Fall back to two.
                spread = ((max(finite) - min(finite)) / max(finite)
                          if len(finite) > 1 and max(finite) else 1.0)
                nd = 2 if spread > 0.02 else (3 if spread > 0.002 else 4)
                label = f"{v:,.{nd}f}"
                if best and v != best and spread <= 0.02:
                    delta = (v - best) / best * 100.0
                    label += f"\n({delta:+.2f}%)"
                ax.text(xi, v, label, ha="center", va="bottom",
                        fontsize=9)
        # Headroom above the tallest bar, because a two-line label with a
        # delta grew into the panel title.
        if finite:
            ax.set_ylim(0, max(finite) * 1.22)
        arrow = "lower is better" if k in LOWER_IS_BETTER \
            else "higher is better"
        ax.set_xlabel(arrow, fontsize=8.5, color="#666666")

    # The subtitle sat at 0.925 and the title's own descenders reach it.
    # Title and question on separate rows, with the figure tall enough to
    # hold both.
    fig.suptitle(f"Demo {number:03d}  ·  Measured Results",
                 fontsize=14, fontweight="bold", y=0.975)
    # The demo's own question, never a restatement. When the explanation
    # was rewritten and the definition was not, a chart and its dossier
    # answered different questions - the reader has no way to tell which
    # one the figures belong to.
    fig.text(0.5, 0.905, demo.question, ha="center", fontsize=11,
             color="#333333")
    fig.text(0.5, 0.015,
             "Only the figures this demonstration's answer rests on. "
             "Teal marks the best value shown.",
             ha="center", fontsize=9, color="#666666")
    fig.tight_layout(rect=(0.01, 0.05, 0.99, 0.86))
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


# ==============================================================================
# Throughput bottleneck
# ==============================================================================


def render_bottleneck_chart(demo, number: int, path: str,
                            row_index: int = -1) -> Optional[str]:
    """Stage throughput against the required rate.

    The bottleneck is the LEAST SLACK stage, which for a common required
    rate is the lowest throughput. The latency-dominant block is a
    different thing and is deliberately absent: across 81 configurations
    the two named different blocks in 36.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    from .system import SystemConfig
    from .review import build_review
    from .perf_bottleneck import find_bottleneck, MET, VIOLATED

    row = demo.rows[row_index]
    a = build_review("education_step_by_step", row.application,
                     SystemConfig(**row.config))
    b = find_bottleneck(a)
    if not b.stages:
        return None

    stages = sorted(b.stages, key=lambda s: s.inf_s)
    names = [s.name for s in stages]
    vals = [s.inf_s for s in stages]
    colours = ["#9C2B2B" if s.is_bottleneck else "#2E7A80"
               for s in stages]

    fig, ax = plt.subplots(figsize=(9.6, 5.4))
    y = list(range(len(names)))[::-1]
    ax.barh(y, vals, color=colours, height=0.55)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=11)
    ax.set_xlabel("throughput  (inf/s)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)

    for yi, s in zip(y, stages):
        tag = f"{s.inf_s:,.1f}"
        if s.slack_inf_s is not None:
            tag += f"    slack {s.slack_inf_s:+,.1f}"
        # Offset from the AXIS, not from the bar: a bar at 2% of the
        # range put its label inside itself, unreadable against the fill.
        span = max(vals)
        ax.text(s.inf_s + span * 0.02, yi, tag, va="center", fontsize=9.5,
                color="#9C2B2B" if s.is_bottleneck else "#333333",
                fontweight="bold" if s.is_bottleneck else "normal")

    if b.required_inf_s:
        ax.axvline(b.required_inf_s, color="#3A5265", linestyle="--",
                   linewidth=1.6)
        ax.text(b.required_inf_s, len(names) - 0.35,
                f" required {b.required_inf_s:,.0f} inf/s",
                fontsize=9.5, color="#3A5265", va="bottom")

    ax.set_xlim(0, max(vals) * 1.35)
    status = b.status
    fig.suptitle(f"Demo {number:03d}  ·  Throughput Bottleneck",
                 fontsize=14, fontweight="bold", y=0.975)
    fig.text(0.5, 0.905, f"{row.label}  -  {demo.question}",
             ha="center", fontsize=10.5, color="#333333")
    foot = (f"Bottleneck: {b.bottleneck}    "
            f"System limit: {b.limit_inf_s:,.1f} inf/s    "
            f"Constraint: {status}")
    fig.text(0.5, 0.045, foot, ha="center", fontsize=10,
             fontweight="bold",
             color="#9C2B2B" if status == VIOLATED else "#2E7A80")
    fig.text(0.5, 0.012,
             "The bottleneck is the stage with the least slack, not the "
             "block holding the most latency.",
             ha="center", fontsize=8.5, color="#666666")
    fig.tight_layout(rect=(0.02, 0.08, 0.98, 0.86))
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def render_demo_charts(demo, number: int, out_dir: str = "outputs/demos"
                       ) -> Dict[str, str]:
    """Every chart a demo supports, under its own directory.

    Per-demo filenames, because the previous behaviour wrote
    `review_balance.png` for all fifteen and a run of the library left
    only the last one on disk.

    Returns a status per chart. NOT APPLICABLE and MISSING are different
    findings: a system flow that would show the same picture twice is not
    a gap.
    """
    cmp = build_demo_comparison(demo, number)
    d = os.path.join(out_dir, f"demo_{number:03d}")
    os.makedirs(d, exist_ok=True)
    stem = os.path.join(d, f"demo_{number:03d}")
    out: Dict[str, str] = {}

    # EACH CHART IS ATTEMPTED INDEPENDENTLY.
    #
    # A rendering failure in one used to abort the whole set, so a broken
    # spider cost the user the measured results and the bottleneck too -
    # three pictures lost to one fault. A chart that fails reports
    # MISSING and the others still arrive.
    def _try(fn, *a):
        try:
            return fn(*a) or "MISSING"
        except Exception as exc:
            return f"MISSING: {type(exc).__name__}"

    # ORDER: evidence, then mechanism, then summary.
    #
    #     measured results   what was observed
    #     bottleneck         why it happened
    #     spider             the shape of it
    #
    # The spider was first and a summary shown first reads as evidence.
    # A reader who sees five ratios before any measured figure has been
    # given the conclusion before the data.
    out["measured_results"] = _try(
        render_measured_comparison, demo, number,
        f"{stem}_measured_results.png")

    out["bottleneck"] = _try(render_bottleneck_chart, demo, number,
                             f"{stem}_bottleneck.png")

    if cmp is None:
        out["ppact_spider"] = NOT_APPLICABLE + ": nothing to compare"
    else:
        out["ppact_spider"] = _try(render_relative_spider, cmp,
                                   f"{stem}_ppact_spider.png")

    # SYSTEM FLOW only when the change alters the data path. Two identical
    # pictures side by side would say a change happened where none did.
    if cmp is not None and cmp.flow_relevant:
        out["system_flow"] = _try(_render_demo_flow, demo, number,
                                  f"{stem}_system_flow.png")
    else:
        changed = ", ".join(cmp.changed_fields) if cmp else ""
        out["system_flow"] = (
            NOT_APPLICABLE + ": the change does not alter the data path"
            if not changed else NOT_APPLICABLE)
    return out


def _render_demo_flow(demo, number: int, path: str) -> Optional[str]:
    from .system import SystemConfig
    from .review import build_review
    from .visual import build_flow, render_flow_png

    row = demo.rows[-1]
    a = build_review("education_step_by_step", row.application,
                     SystemConfig(**row.config))
    try:
        return render_flow_png(build_flow(a), path)
    except Exception:
        return None
