"""
ppact.visual.balance - one data object, three renderers

WHAT THE EXPERIMENT DECIDED
===========================
An information-transfer experiment put five student questions to three
formats. The result was not the expected one:

    bar only                    2 of 5
    spider only                 0 of 5
    bar + reason breakdown      5 of 5
    all three                   5 of 5, plus a balance summary

Spider answered nothing. Latency is not one of its axes; throughput is, and a
21% latency improvement showed as three points on a different question. It
cannot show a budget, a bottleneck, a cause, or what to change next.

So this module builds the spider and calls it what it is: a BALANCE summary.
It is placed after the explanation and the measured bars, it carries a notice
saying what it cannot show, and it is never described as a performance
summary, a recommendation, or a result.

ONE OBJECT, THREE RENDERERS
---------------------------
The terminal, the PNG and a web view all take the SAME SpiderData. That is
the only mechanical guarantee that they agree - two renderers each computing
their own normalisation will disagree eventually, and they will do it in a
way nobody notices because the two are never on screen together.

The normalisation happens ONCE, here, and each axis carries the formula that
produced it. A reader who recognises "cost 18.82 USD" and sees "92" is owed
an account of how one became the other.

WHAT IS DELIBERATELY NOT CHANGED
--------------------------------
The normalisation formula itself. It compresses a six-fold cost increase into
24 points, which is a real educational problem - and fixing it now would mean
comparing what the old spider communicated against what a new one does, at
the same time as moving the spider's role. One change at a time.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from .models import SpiderAxis, SpiderData
from .text import wrap_text

# Printed directly under every rendering of the balance chart, in every
# renderer. It is not a caveat added out of caution: it is the finding of the
# experiment, and a reader who takes the shape for a result has been misled
# by the chart rather than by their own carelessness.
BALANCE_NOTICE = (
    "This chart summarizes the relative balance among normalized "
    "architectural dimensions. It does not show physical values, "
    "requirement limits, bottlenecks, or the reasons for change. See the "
    "measured bars and reason breakdown for those results."
)

# TWO CHARTS, TWO NAMES.
#
# The single and the comparison chart shared this title and these axis
# names while answering different questions. On one, 50 means the
# requirement is exactly met and 100 is a clipped ceiling; on the other,
# 1.00x means nothing changed and there is no ceiling at all. A reader
# comparing "50" with "0.51x" was comparing two scales.
TITLE = "Architecture Balance - Requirement Headroom"
COMPARISON_TITLE = "Architecture Balance - Relative Change"

# One line, directly under the title. A student should know why they are
# looking at this picture within about five seconds; the notice below tells
# them what it cannot do, which is a different and slower thing to read.
PURPOSE = ("Each axis scores this design against its own requirement. "
           "50 means the requirement is exactly met.")

# The legend for the single chart. Printed with the figure, because a
# spider chart gets screenshotted into a slide and the explanation does
# not travel with it.
# WHICH FIGURE EACH AXIS READS.
#
# "Performance" names three different quantities across this project's
# charts: delivered throughput here, pipeline capacity on the relative
# chart, and the single-job rate on the benchmark one. A reader who saw
# latency improve and Performance stay at 1.00x had no way to learn
# which of the three the axis was reporting.
#
# The axis names stay as they are. The source is stated instead.
SINGLE_LEGEND = (
    "Performance reads delivered throughput, which is capped at the "
    "application's target: a design above its target reports the "
    "target.   ·   Area reads SoC silicon; external memory silicon is "
    "not included.\n"
    "50 = requirement exactly met   ·   above 50 = increasing "
    "headroom   ·   below 50 = requirement shortfall\n"
    "100+ = the score exceeds the displayed axis range; the figure "
    "behind it is printed beside the axis\n"
    "n/e = not established: the axis has no basis on which a score "
    "would be justified, which is not the same as a score of zero")

COMPARISON_LEGEND = (
    "Performance reads sustainable pipeline capacity, not execution "
    "latency and not the capped delivered rate.   ·   Area reads SoC "
    "silicon; external memory silicon is not included.\n"
    "1.00x = no change   ·   above 1.00x = improvement   ·   below "
    "1.00x = degradation\n"
    "No clipping is applied: a ratio has no ceiling. These are not "
    "the 0-100 scores of the requirement chart")

# Printed under the purpose line. A spider chart travels: it gets screenshot
# out of a report and pasted into a slide, and the measured bars do not
# travel with it. This sentence is the only thing that goes where the shape
# goes.
# "Do not use this" and "read this alongside the measurements" are
# different instructions, and the second is the one that is true. The chart
# is useful; it is useful for one thing, and a reader told not to use it
# will use it anyway without the thing that makes it safe.
PURPOSE_CAVEAT = ("Engineering decisions should be based on the measured "
                  "results and analytical explanations provided alongside "
                  "this normalized summary.")

# The normalisation formula is CORRECT to expose and WRONG to open with.
# A student meeting log10 in the first line of a chart stops reading the
# chart. It stays one keystroke away instead of on the page.
FORMULA_HINT = "Press H for the normalization method."

# Marks a value that hit the end of its axis. A score of 100 that was really
# 140 is a lie of omission, and the reader's conclusion - "this axis is as
# good as it gets" - is exactly wrong.
# WHY EACH BLANK AXIS IS BLANK, in the reader's words rather than a
# ticket number. `PW-Q1` and `TR-D1` mean nothing to someone reading a
# chart.
NOT_ESTABLISHED_REASON = {
    "Power": ("The available requirement is a power budget in watts "
              "while the candidate balance metric is energy per "
              "inference in millijoules. Scoring one against the other "
              "would present energy efficiency as budget compliance. "
              "See PW-Q1."),
    "Traffic": ("One component of the intended traffic model is "
                "represented. A point that moved only when shared "
                "memory moved would be a memory score wearing the "
                "label of nine other things. See TR-D1."),
}

def not_established_note(data) -> str:
    """Why the blank axes on this chart are blank, in one string.

    The reasons lived in the text renderer and in the notebook path,
    and the Streamlit panel attached nothing - so a reader of the
    shipped screen met two gaps marked `n/e` with no expansion and no
    reason. `n/e` reads as not evaluated, not applicable, zero or
    error, and the distinction this project drew between those is the
    whole point of the marker.
    """
    blank = []
    for _label, axes in getattr(data, "axes", ()):
        for ax in axes:
            if ax.score is None and ax.name not in blank:
                blank.append(ax.name)
    if not blank:
        return ""
    parts = ["**n/e = not established**"]
    for name in blank:
        reason = NOT_ESTABLISHED_REASON.get(name)
        if reason:
            parts.append(f"**{name}** - {reason}")
    parts.append(
        "Not established is not not applicable and not a score of "
        "zero: the axis has no basis on which a score would be "
        "justified, and inventing one would be the error.")
    return "  \n".join(parts)


CLIP_HIGH = "100+"
CLIP_LOW = "0-"

# Line styles, so the two designs are distinguishable without colour.
LINE_STYLES = ("solid", "dashed", "dashdot", "dotted")


def build_balance(app_key: str, configs: Sequence[Tuple[str, object]],
                  title: str = TITLE) -> SpiderData:
    """Normalise once, here, and record how.

    configs is (label, SystemConfig). The first is treated as the reference,
    which only affects line style and ordering - no axis is measured against
    it.
    """
    from ..application import APPLICATION_LIBRARY
    from ..system import (REQUIREMENT_AXES, requirement_score,
                          evaluate_system, SYSTEM_ANCHORS, SYSTEM_AXES,
                          _AXIS_METRIC, score_system)

    app = APPLICATION_LIBRARY[app_key]
    out: List[Tuple[str, Tuple[SpiderAxis, ...]]] = []
    for label, cfg in configs:
        res = score_system(evaluate_system(app, cfg))
        axes: List[SpiderAxis] = []
        for name in SYSTEM_AXES:
            anchor = SYSTEM_ANCHORS[name]
            # REQUIREMENT-CENTRED. 50 is "meets its requirement", on every
            # axis and every application. The absolute anchors answer a
            # different question and are kept for a benchmark view.
            spec = REQUIREMENT_AXES.get(name)
            if spec is not None:
                metric_key, attr, higher = spec
                actual = res.metrics.get(metric_key)
                need = getattr(app, attr, None)
                score = requirement_score(name, actual, need)
                # THE SCORE BEFORE THE CLIP.
                #
                # `requirement_score` clips to 0-100 and returns only
                # the clipped value, so 145.8 and 175.6 both arrived as
                # 100.0 and the chart could not say which was which.
                # Recomputed here rather than changing the scoring
                # function, whose output is unchanged.
                unclipped = None
                if actual is not None and need:
                    import math as _mb
                    from ..system import REQUIREMENT_K
                    _ratio = ((actual / need) if higher
                              else (need / actual))
                    if _ratio > 0:
                        unclipped = 50.0 + REQUIREMENT_K * _mb.log2(
                            _ratio)
                axes.append(SpiderAxis(
                    name=name, unit=("x requirement"), raw=actual,
                    score=score,
                    formula=(f"score = 50 + 20 x log2("
                             + (f"{metric_key} / {attr}"
                                if higher else f"{attr} / {metric_key}")
                             + "), clipped to 0-100"
                             if score is not None
                             else "NOT ESTABLISHED - no declared "
                                  "requirement"),
                    lower_is_better=not higher, reference=need,
                    unclipped=unclipped,
                    # CLIPPED MEANS THE CLIP MOVED THE NUMBER, not that
                    # the number happens to sit on an end. A design
                    # exactly at 100.0 was reported as clipped and one
                    # at 145.8 was reported the same way.
                    clipped=(unclipped is not None
                             and (unclipped > 100.0
                                  or unclipped < 0.0))))
                continue
            # An axis with an anchor and NO metric renders as a gap, at
            # its own position, labelled. Dropping it would show a
            # four-sided figure and suggest PPACT has four axes; scoring
            # it zero would say the design is as bad as the anchor allows,
            # which is a claim nobody has measured.
            if name not in _AXIS_METRIC:
                axes.append(SpiderAxis(
                    name=name, unit=anchor.unit, raw=None, score=None,
                    formula="NOT ESTABLISHED - " + anchor.rationale,
                    lower_is_better=False, reference=None,
                    clipped=False))
                continue
            raw = res.metrics[_AXIS_METRIC[name]]
            score = res.scores[name]
            lower_better = anchor.at_hundred < anchor.at_zero
            # A score sitting exactly on an end MIGHT be clipped. Recomputing
            # the unclipped fraction is the only way to know, and knowing is
            # the difference between "as good as it gets" and "off the end".
            import math
            lo, hi = anchor.at_zero, anchor.at_hundred
            v = raw
            if anchor.log_scale:
                v, lo, hi = (math.log10(max(v, 1e-9)), math.log10(lo),
                             math.log10(hi))
            unclipped = (v - lo) / (hi - lo) * 100.0
            clipped = unclipped > 100.0 + 1e-9 or unclipped < -1e-9
            formula = (
                f"score = clip(100 x (log10({anchor.label.lower()}) - "
                f"log10({anchor.at_zero:g})) / (log10({anchor.at_hundred:g}) "
                f"- log10({anchor.at_zero:g})), 0, 100)"
                if anchor.log_scale else
                f"score = clip(100 x ({anchor.label.lower()} - "
                f"{anchor.at_zero:g}) / ({anchor.at_hundred:g} - "
                f"{anchor.at_zero:g}), 0, 100)")
            axes.append(SpiderAxis(
                name=name, unit=anchor.unit, raw=raw, score=score,
                formula=formula, lower_is_better=lower_better,
                reference=anchor.at_hundred, clipped=clipped))
        out.append((label, tuple(axes)))
    return SpiderData(title=title, designs=tuple(l for l, _ in configs),
                      axes=tuple(out))


def overlapping_axes(data: SpiderData) -> List[str]:
    """Axes where every design shows the SAME NUMBER on screen.

    Compared on the DISPLAYED value, not the underlying float. A reader
    compares what they can see: two axes labelled 51 and 51 have overlapped
    as far as anybody looking at the chart is concerned, and text saying
    that axis moved contradicts the picture beside it. Found when a guided
    question said Power had moved while the chart showed 51 twice - the
    underlying scores were 51.3 and 50.8.

    An overlap that is not stated is a chart showing one line where the
    legend claims two, and the reader concludes a design is missing.
    """
    if len(data.axes) < 2:
        return []
    names = data.axis_names()
    same = []
    for i, name in enumerate(names):
        # An unscored axis cannot overlap: there is nothing to coincide.
        shown = {("n/e" if axes[i].score is None
                  else f"{axes[i].score:.0f}")
                 for _, axes in data.axes}
        if len(shown) == 1:
            same.append(name)
    return same


def render_balance_text(data: SpiderData, width: int = 30,
                        show_formulas: bool = False,
                        show_title: bool = True) -> List[str]:
    """The terminal renderer. Same object as the PNG takes.

    show_formulas is off by default and reachable from help. The formulas
    are not hidden - they are one keystroke away, which is where a thing
    belongs when it is true, checkable, and off-putting on first sight.
    """
    # The standard review prints its own numbered section heading, so
    # repeating the title here put "ARCHITECTURE BALANCE" on screen twice
    # in a row. Suppressible rather than removed, because the chart is also
    # rendered on its own.
    out = [f"  {data.title.upper()}"] if show_title else []
    out += [f"  {ln}" for ln in wrap_text(PURPOSE, 70)]
    out += [f"  {ln}" for ln in wrap_text(PURPOSE_CAVEAT, 70)]
    out.append("")
    names = data.axis_names()
    label_w = max(len(n) for n in names) + 2 if names else 12

    header = f"  {'axis':<{label_w}s}"
    for label, _ in data.axes:
        header += f"{label[:14]:>16s}"
    out.append(header)
    out.append("  " + "-" * (len(header) - 2))
    # THE MODE, before the figures. A reader who sees 50 and does not
    # know which question the chart answers assumes the one they came
    # looking for.
    from ..evaluation_mode import mode_for, render_mode_header

    for i, name in enumerate(names):
        row = f"  {name:<{label_w}s}"
        for _, axes in data.axes:
            a = axes[i]
            # An axis with no metric shows a gap, not a number. Zero
            # would be a score - it says the design is as bad as the
            # anchor allows - and this one has not been measured.
            # THE CLIP DISCLOSES WHAT IT HID.
            #
            # "100+" alone made a design 27 times inside its area budget
            # and one 78 times inside its cost budget read the same. The
            # score before clipping is printed beside the marker.
            if a.score is None:
                shown = "n/e"
            elif a.clipped and a.score >= 100:
                shown = (f"{CLIP_HIGH} ({a.unclipped:.1f})"
                         if a.unclipped is not None else CLIP_HIGH)
            elif a.clipped:
                shown = (f"{CLIP_LOW} ({a.unclipped:.1f})"
                         if a.unclipped is not None else CLIP_LOW)
            else:
                shown = f"{a.score:.0f}"
            row += f"{shown:>16s}"
        out.append(row)

    # the raw values, because a normalised score without its source is a
    # number nobody can check
    out.append("")
    out.append(f"  {'raw value':<{label_w}s}"
               + "".join(f"{label[:14]:>18s}" for label, _ in data.axes))
    for i, name in enumerate(names):
        row = f"  {name:<{label_w}s}"
        for _, axes in data.axes:
            a = axes[i]
            # the unit is abbreviated to what fits, and a truncated unit
            # is worse than a short one - "mm" for "mm2" reads as a length
            unit = {"inferences per second": "inf/s", "mJ": "mJ",
                    "mm2": "mm2", "USD": "USD", "W/mm2": "W/mm2"}.get(
                        a.unit, a.unit)
            row += (f"{'n/e':>11s} {unit:<6s}" if a.raw is None
                    else f"{a.raw:>11.3g} {unit:<6s}")
        out.append(row)

    same = overlapping_axes(data)
    if same:
        out.append("")
        if len(same) == len(names):
            out += [f"  {line}" for line in wrap_text(
                "The two normalized profiles overlap on all displayed axes. "
                "A single line is drawn where the legend shows two.", 70)]
        else:
            out += [f"  {line}" for line in wrap_text(
                f"The profiles overlap on: {', '.join(same)}.", 70)]

    if data.any_clipped():
        out.append("")
        # Name the axis, the raw value and the end of the range it passed.
        # "100+" alone tells a reader a number was hidden without telling
        # them which number or by how much, which is the question the
        # marker raises.
        for label, axes in data.axes:
            for ax in axes:
                if not ax.clipped:
                    continue
                end = ax.reference
                mark = CLIP_HIGH if ax.score >= 100 else CLIP_LOW
                # "further along" says nothing about DIRECTION, and on an
                # axis where a lower number is favourable a reader cannot
                # tell whether a clipped value was very good or very bad.
                direction = ("lower is favourable" if ax.lower_is_better
                             else "higher is favourable")
                out.append(f"  {ax.name} ({label}) reads {mark}.")
                out.append(f"    raw value      {ax.raw:.4g} {ax.unit}   "
                           f"({direction})")
                out.append(f"    axis ends at   {end:g} {ax.unit}")
                out.append(f"    The value is past the favourable end of "
                           f"the range, so the axis")
                out.append(f"    cannot show how far past it goes.")
                if ax.unclipped is not None:
                    # HOW FAR PAST. 145.8 and 175.6 are both "100+" and
                    # they are not the same statement.
                    out.append(f"    score before clipping "
                               f"{ax.unclipped:.1f}")
        out += [f"  {line}" for line in wrap_text(
            "A clipped score is not a maximum. It means the range stopped, "
            "not that the design did.", 70)]

    # WHY AN AXIS IS BLANK.
    #
    # "n/e" was printed with no expansion. A reader met a three-sided
    # figure and two silent gaps, and nothing said whether the tool had
    # failed, the design had, or the question was still open.
    blank = [ax.name for _label, axes in data.axes for ax in axes
             if ax.score is None]
    if blank:
        out.append("")
        out.append("  n/e = not established")
        for name in dict.fromkeys(blank):
            reason = NOT_ESTABLISHED_REASON.get(name)
            if reason:
                out.append(f"    {name}")
                out += [f"      {line}" for line in wrap_text(reason, 66)]
        out += [f"  {line}" for line in wrap_text(
            "Not established is not not applicable and not a score of "
            "zero: the axis has no basis on which a score would be "
            "justified, and inventing one would be the error.", 70)]

    out.append("")
    out += [f"  {line}" for line in wrap_text(SINGLE_LEGEND.replace(
        "\n", "  "), 70)]

    out.append("")
    out += [f"  {line}" for line in wrap_text(BALANCE_NOTICE, 70)]

    if show_formulas:
        out.append("")
        out.append("  HOW EACH SCORE WAS COMPUTED")
        seen = set()
        for _, axes in data.axes:
            for a in axes:
                if a.name in seen:
                    continue
                seen.add(a.name)
                out.append(f"    {a.name}  ({a.unit},"
                           f" {'lower' if a.lower_is_better else 'higher'}"
                           f" is favourable)")
                for line in wrap_text(a.formula, 66):
                    out.append(f"      {line}")
    else:
        out.append(f"  {FORMULA_HINT}")
    return out


def print_balance(data: SpiderData) -> None:
    for line in render_balance_text(data):
        print(line)


def render_balance_png(data: SpiderData, path: str = "balance.png"
                       ) -> Optional[str]:
    """The PNG renderer. Takes the SAME object; computes nothing."""
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    names = list(data.axis_names())
    if not names:
        return None
    angles = np.linspace(0, 2 * np.pi, len(names), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9.0, 10.5), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), names, fontsize=13,
                      fontweight="bold")
    ax.tick_params(axis="x", pad=22)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.grid(color="#DDDDDD", linestyle="--", linewidth=1.2)

    palette = ["#1F4E79", "#C0504D", "#4F8A47", "#8064A2"]
    for i, (label, axes) in enumerate(data.axes):
        # An unscored axis BREAKS the polygon rather than plotting at the
        # centre. Drawing through zero made the shape read as Traffic
        # scoring 0, which is a claim - it would say the design is as bad
        # as the anchor allows - and nothing has been measured.
        #
        # NaN leaves a gap, the axis keeps its position and label, and the
        # figure stays five-sided so nobody reads PPACT as having four
        # axes.
        vec = [float("nan") if a.score is None else a.score
               for a in axes]
        style = LINE_STYLES[i % len(LINE_STYLES)]
        colour = palette[i % len(palette)]
        # style AND colour: two designs must be distinguishable in a
        # monochrome printout and to a reader who does not see colour the
        # way the author does
        ax.plot(angles, vec + vec[:1], color=colour, linewidth=2.5,
                linestyle=style, label=f"{label}  ({style})")
        ax.fill(angles, vec + vec[:1], color=colour, alpha=0.12)
        # Labels are spread ANGULARLY, not radially. Pushing them outward
        # by index put a clipped "100+" on top of the axis name, which is
        # the one place a reader looks to find out what the number is of.
        spread = np.radians(6.0)
        base = -(len(data.axes) - 1) / 2.0
        for ang, a in zip(angles[:-1], axes):
            # An axis with no metric shows a gap, not a number. Zero
            # would be a score - it says the design is as bad as the
            # anchor allows - and this one has not been measured.
            shown = ("n/e" if a.score is None
                     else (f"{CLIP_HIGH} ({a.unclipped:.0f})"
                           if a.unclipped is not None else CLIP_HIGH)
                     if a.clipped and a.score >= 100
                     else (f"{CLIP_LOW} ({a.unclipped:.0f})"
                           if a.unclipped is not None else CLIP_LOW)
                     if a.clipped else f"{a.score:.0f}")
            r = 6 if a.score is None else min(a.score, 88) + 6
            ax.text(ang + (base + i) * spread, r, shown, color=colour,
                    fontsize=9, fontweight="bold", ha="center", va="center",
                    zorder=6,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white",
                              ec="none", alpha=0.85))

    # The title goes on the FIGURE, not the axes. On a polar axes the title
    # sits just above the topmost tick label and lands on it.
    fig.suptitle(data.title, size=15, fontweight="bold", y=0.975)
    fig.text(0.5, 0.945, PURPOSE, ha="center", va="top", fontsize=10,
             color="#333333")
    # The caveat wraps and sits above the plot area. Printed on one line it
    # ran across the topmost axis label, which is the label a reader needs
    # in order to know what the shape is of.
    caveat = "\n".join(wrap_text(PURPOSE_CAVEAT, 78))
    fig.text(0.5, 0.925, caveat, ha="center", va="top", fontsize=9,
             color="#555555", linespacing=1.35)
    # The legend goes BELOW. Beside the plot it was clipped by the figure
    # edge, and a legend a reader cannot finish reading is a legend that
    # leaves them guessing which line is which.
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06),
              frameon=False, fontsize=10, ncol=len(data.axes))

    notice = "\n".join(wrap_text(BALANCE_NOTICE, 92))
    same = overlapping_axes(data)
    if same:
        extra = ("The two normalized profiles overlap on all displayed axes."
                 if len(same) == len(names)
                 else f"The profiles overlap on: {', '.join(same)}.")
        notice = extra + "\n" + notice
    fig.text(0.5, 0.03, notice, ha="center", va="bottom", fontsize=8.5,
             color="#444444")
    fig.subplots_adjust(bottom=0.22, top=0.82)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def render_balance_web(data: SpiderData) -> Dict:
    """A minimal web-shaped rendering. NOT a user interface.

    It exists to prove one thing: that the same object can feed a third
    renderer without any of them computing. It returns the structure a web
    view would bind to, and deliberately draws nothing.
    """
    return {
        "title": data.title,
        "purpose": PURPOSE,
        "purpose_caveat": PURPOSE_CAVEAT,
        "notice": BALANCE_NOTICE,
        "axes": list(data.axis_names()),
        "series": [
            {"label": label,
             "style": LINE_STYLES[i % len(LINE_STYLES)],
             "scores": [a.score for a in axes],
             "raw": [a.raw for a in axes],
             "units": [a.unit for a in axes],
             "clipped": [a.clipped for a in axes],
             "formulas": [a.formula for a in axes]}
            for i, (label, axes) in enumerate(data.axes)],
        "overlapping": overlapping_axes(data),
    }


# ==============================================================================
# Measured results, as an image
# ==============================================================================
#
# Driven by the SAME MetricReading list the text bars use.
#
# The earlier image came from a separate chart function with its own metric
# list: it showed SoC die area, board area and a reaction distance, and it
# omitted delivered throughput and energy per job. Two pictures of "the
# measured results" that do not contain the same measurements is worse than
# one picture, because a reader who has seen both cannot tell which is the
# result - and each looks complete on its own.

def render_measured_bars_png(readings, path: str = "measured_results.png",
                             title: str = "Measured Results",
                             subtitle: str = "") -> Optional[str]:
    """One panel per metric, in contract order, with the requirement line.

    Computes nothing. It is handed values, units and limits that are
    already final, in the order the contract fixes.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    if not readings:
        return None

    n = len(readings)
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols, 3.1 * rows))
    axes = axes.ravel() if hasattr(axes, "ravel") else [axes]

    START = "#1F4E79"
    CURRENT = "#2E7A80"
    OVER = "#9C2B2B"
    LIMIT = "#9C6B1F"

    for ax, r in zip(axes, readings):
        labels, values, colours = [], [], []
        if getattr(r, "starting_value", None) is not None:
            labels.append("starting point")
            values.append(r.starting_value)
            colours.append(START)
        labels.append("current design")
        values.append(r.value)
        colours.append(OVER if r.over else CURRENT)

        bars = ax.bar(labels, values, color=colours, width=0.55)
        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width() / 2,
                    b.get_height(), f"{v:.4g}", ha="center", va="bottom",
                    fontsize=10, fontweight="bold")

        # A LOG AXIS WHEN THE RATIO IS EXTREME.
        #
        # Total silicon of 3545 mm2 against a 50 mm2 requirement drew the
        # limit line flat on the baseline: the requirement was present,
        # correct, and invisible, and the reader could not see the one thing
        # the panel exists to show. Seventy-one times over is not a slightly
        # worse design, and a linear axis cannot say so.
        span = [v for v in values if v > 0]
        if r.limit is not None and r.limit > 0:
            span.append(r.limit)
        ratio = (max(span) / min(span)) if len(span) > 1 and min(span) > 0 \
            else 1.0
        use_log = ratio > 20.0

        if use_log:
            ax.set_yscale("log")
            ax.set_ylim(min(span) * 0.35, max(span) * 3.0)
            ax.text(0.02, 0.94, "log scale", color="#555555", fontsize=8.5,
                    ha="left", va="top", transform=ax.transAxes,
                    style="italic")

        if r.limit is not None:
            ax.axhline(r.limit, color=LIMIT, linestyle="--", linewidth=1.5)
            # A requirement can be a ceiling or a floor. Saying which turns
            # "60 against a limit of 60" from something that reads as a
            # near-miss into what it is: the requirement met exactly.
            kind = "max" if r.lower_is_better else "min"
            ax.text(1.02, r.limit, f"{kind} {r.limit:g}", color=LIMIT,
                    fontsize=9, va="center",
                    transform=ax.get_yaxis_transform())
            # The verdict sits BELOW the panel, not inside it. Inside, it
            # collided with the value label on exactly the panels where the
            # value is large - which is to say on the panels that matter.
            verdict = ("exceeds requirement" if r.over
                       else "within requirement")
            ax.set_xlabel(verdict, fontsize=9.5, fontweight="bold",
                          color=OVER if r.over else "#2E7A80", labelpad=6)
            if not use_log:
                top = max(max(values), r.limit) * 1.35
                ax.set_ylim(0, top if top > 0 else 1.0)
        else:
            ax.set_xlabel("no requirement stated", fontsize=9.5,
                          color=LIMIT, labelpad=6)
            if not use_log:
                top = max(values) * 1.35 if max(values) > 0 else 1.0
                ax.set_ylim(0, top)
        ax.set_title(f"{r.label}  [{r.unit}]", fontsize=11,
                     fontweight="bold")
        ax.tick_params(axis="x", labelsize=9)
        ax.grid(axis="y", color="#E4E8EB", linewidth=1)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)

    for ax in list(axes)[n:]:
        ax.axis("off")

    fig.suptitle(title, fontsize=15, fontweight="bold", y=0.985)
    if subtitle:
        fig.text(0.5, 0.955, subtitle, ha="center", va="top", fontsize=10,
                 color="#333333")
    fig.text(0.5, 0.012,
             "Values against the application's requirement. 'max' is a "
             "ceiling, 'min' a floor. A bar in the alternate colour exceeds "
             "its requirement. Panels marked 'log scale' span more than a "
             "factor of twenty.",
             ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, 0.035, 1, 0.93))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
