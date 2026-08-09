"""
ppact.flow_map - modules AND the links between them

WHY A LINK IS NOT A MODULE
==========================
The latency flow shows where a job's time goes. The throughput view shows
what each block could sustain. Neither shows the LINK - and a system where
every module is comfortable can still be held up by the path between two
of them.

    CPU        utilisation 11.7%
      |
      | CPU -> memory        load 0.0%
      v
    memory     utilisation  9.4%
      |
      | memory -> accelerator  load 84.3%   <- BOTTLENECK
      v
    accelerator  utilisation 15.1%

Three modules at low utilisation and one link near saturation. Reporting
only the modules would say this design has room everywhere.

WHAT A LINK LOAD IS HERE
------------------------
The bandwidth that agent asks of the shared memory, over the bandwidth
available to it. It is NOT a measured occupancy: there is no queue model,
and the arbitration between host and accelerator carries a recorded defect
(MEM-ARB-001).

Utilisation is `busy` from the throughput view: station time times the
delivered rate. Also analytical.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

NOT_ESTABLISHED = "NOT ESTABLISHED"


@dataclass(frozen=True)
class Module:
    name: str
    utilisation_pct: Optional[float]
    throughput_inf_s: Optional[float]
    is_bottleneck: bool
    # LATENCY SHARE, where the model has one.
    #
    # The latency flow decomposes into two stations here and the
    # throughput view into four, so two modules have a share and two do
    # not. Filling the gap by dividing something would be inventing a
    # figure to complete a box.
    latency_share_pct: Optional[float] = None


@dataclass(frozen=True)
class Link:
    source: str
    target: str
    load_pct: Optional[float]
    demand_gbs: Optional[float]
    available_gbs: Optional[float]
    is_bottleneck: bool
    note: str = ""


@dataclass(frozen=True)
class FlowMap:
    modules: Tuple[Module, ...]
    links: Tuple[Link, ...]
    limiting: str
    limiting_kind: str          # "module" or "link"
    # PIPELINE CAPACITY, and now named for it.
    #
    # This was `delivered_inf_s` while holding the capacity: delivered
    # is min(capacity, target) and a design comfortably above its
    # target would report the target, so a real improvement read as no
    # change. The comment below the assignment said so and the field
    # name said the opposite, which is how a sentence about "the
    # throughput the design can sustain" ended up beside a variable
    # promising a delivered rate.
    capacity_inf_s: float


def build_flow_map(analysis) -> FlowMap:
    """Modules from the throughput view, links from the memory demands.

    Both are analytical. Neither is an occupancy measurement, and the
    screen must say so.
    """
    from .visual import build_throughput_view, build_flow
    from .memory_analysis import analyse_memory

    view = build_throughput_view(analysis, build_flow(analysis))
    mem = analyse_memory(analysis)
    m = analysis.current_result.metrics

    flow = build_flow(analysis)
    # The flow's names differ from the throughput view's: "host active"
    # against "host". Matched on the leading word, and left absent when
    # nothing matches.
    share = {}
    for st in flow.stations:
        share[st.name.split()[0].lower()] = st.share_pct

    # A NaN utilisation is not a utilisation. It arises where the design
    # produces no timing at all - a model that does not fit - and
    # comparing it against a link load silently returned False, so a link
    # at 186.8% was never named as the limit.
    import math as _m

    def _clean(v):
        return None if v is None or (isinstance(v, float)
                                     and _m.isnan(v)) else v

    modules = tuple(
        Module(b.name, _clean(b.busy_pct), _clean(b.throughput_inf_s),
               b.is_system_limit,
               _clean(share.get(b.name.split()[0].lower())))
        for b in view.blocks)

    available = getattr(mem, "effective_bandwidth", None)
    host_need = getattr(mem, "host_required", None)
    accel_need = getattr(mem, "accel_required", None)

    def load(demand):
        if demand is None or not available:
            return None
        return demand / available * 100.0

    links: List[Link] = []
    if any(x.name == "host" for x in modules):
        links.append(Link(
            "host", "shared memory", load(host_need), host_need,
            available, False,
            "Host bandwidth at the application target rate."))
    if any(x.name in ("accelerator", "ISP") for x in modules):
        links.append(Link(
            "shared memory", "accelerator", load(accel_need), accel_need,
            available, False,
            "Accelerator bandwidth at the application target rate."))

    # THE LIMITING ELEMENT may be a link. A module-only view would miss
    # that entirely, which is the reason this exists.
    worst_link = max((l for l in links if l.load_pct is not None),
                     key=lambda l: l.load_pct, default=None)
    worst_module = next((x for x in modules if x.is_bottleneck), None)

    kind, limiting = "module", (worst_module.name if worst_module
                                else NOT_ESTABLISHED)

    # A LINK OVER 100% IS THE LIMIT, whatever the modules say.
    #
    # It is asking for more bandwidth than exists, and no module
    # utilisation can outrank that. Comparing the two figures directly
    # let a link at 186.8% lose to a module whose utilisation was NaN.
    if worst_link is not None:
        module_util = (worst_module.utilisation_pct
                       if worst_module is not None else None)
        if worst_link.load_pct >= 100.0 or (
                module_util is not None
                and worst_link.load_pct > module_util) or (
                module_util is None and worst_module is None):
            kind = "link"
            limiting = f"{worst_link.source} \u2192 {worst_link.target}"

    links = tuple(
        Link(l.source, l.target, l.load_pct, l.demand_gbs,
             l.available_gbs,
             l is worst_link and kind == "link", l.note)
        for l in links)

    # WHEN A LINK IS THE SYSTEM LIMIT, NO MODULE IS.
    #
    # `is_bottleneck` marks the lowest-throughput MODULE, which is a
    # different claim from "this limits the system". Leaving it set
    # while a link held the limit made the comparative screen read
    # "limiting element in both" - reversing the demonstration's
    # conclusion, which is that the bottleneck moved from a link to a
    # module.
    if kind == "link":
        modules = tuple(
            Module(m.name, m.utilisation_pct, m.throughput_inf_s,
                   False, m.latency_share_pct)
            for m in modules)

    # PIPELINE CAPACITY, not the delivered rate.
    #
    # Delivered is min(capacity, target), so a design comfortably above
    # its target reports the target and a real improvement reads as no
    # change. Demo 001 rose 118.0 -> 136.9 and the migration reported
    # "did not touch" because both delivered 60.
    return FlowMap(modules, links, limiting, kind,
                   float(m.get("Pipeline capacity (inf/s)", 0.0)))


def render_flow_map(fm: FlowMap, show_title: bool = True) -> List[str]:
    from .visual.text import wrap_text

    out = ["SYSTEM FLOW MAP", ""] if show_title else []
    for line in wrap_text(
            "Modules and the links between them. A system whose modules "
            "are all comfortable can still be held up by the path "
            "between two of them.", 66):
        out.append(f"  {line}")
    out.append("")

    # THE SHARED BAR, not a local one.
    #
    # Writing `"#" * n + "." * (10 - n)` here made an eighth bar style in
    # a codebase that had spent a release cycle reducing seven to one.
    # Which fill character a reader sees would then depend on which
    # screen they were on.
    from .visual.text import render_bar

    def bar(pct):
        return ("not resolved" if pct is None
                else render_bar(pct, 100.0, 10))

    # PATH ORDER, not throughput order. A map is a picture of where the
    # data goes; sorting the boxes by speed makes it a bar chart with
    # arrows.
    PATH = ("host", "ISP", "shared memory", "accelerator",
            "secondary accelerator")
    order = sorted(fm.modules,
                   key=lambda m: PATH.index(m.name)
                   if m.name in PATH else len(PATH))
    for i, mod in enumerate(order):
        mark = "<" if mod.is_bottleneck else " "
        util = ("not resolved" if mod.utilisation_pct is None
                else f"{mod.utilisation_pct:5.1f}%")
        out.append(f"  {mark} +{'-' * 32}+")
        out.append(f"    | {mod.name:<21s}{util:>9s} |"
                   + ("   MODULE LIMIT" if mod.is_bottleneck else ""))
        out.append(f"    | {bar(mod.utilisation_pct):<30s} |")
        out.append(f"    +{'-' * 32}+")
        link = next((l for l in fm.links if l.source == mod.name), None)
        if link is None and i < len(order) - 1:
            out.append("               |")
        elif link is not None:
            load = ("not resolved" if link.load_pct is None
                    else f"{link.load_pct:.1f}%")
            out.append("               |")
            out.append(f"          {link.source} -> {link.target}"
                       f"   load {load}"
                       + ("   LINK BOTTLENECK"
                          if link.is_bottleneck else ""))
            out.append("               |")
            out.append("               v")
    out.append("")

    out.append(f"  Limiting element            {fm.limiting}")
    out.append(f"  It is a                     {fm.limiting_kind}")
    out.append("")
    for line in wrap_text(
            "Utilisation is station time times the delivered rate. Link "
            "load is bandwidth demanded over bandwidth available. BOTH "
            "ARE ANALYTICAL - there is no queue model, no measured "
            "occupancy, and the arbitration behind the link figures "
            "carries a recorded defect (MEM-ARB-001).", 66):
        out.append(f"  {line}")
    return out


# ==============================================================================
# Bottleneck migration
# ==============================================================================


@dataclass(frozen=True)
class Migration:
    before: str
    after: str
    before_kind: str
    after_kind: str
    moved: bool
    before_util: Optional[float]
    after_util: Optional[float]
    # WHY it did not move. "Unchanged" on its own reads as "nothing
    # happened", and something usually did - the throughput rose and the
    # same element still held the system.
    reason: str = ""


def bottleneck_migration(before_analysis, after_analysis) -> Migration:
    """What was limiting, and what limits now.

    The single most useful sentence a comparison can produce: not that a
    design got faster, but that the thing holding it back changed hands.
    """
    a = build_flow_map(before_analysis)
    b = build_flow_map(after_analysis)

    def util(fm):
        if fm.limiting_kind == "link":
            l = next((x for x in fm.links if x.is_bottleneck), None)
            return l.load_pct if l else None
        m = next((x for x in fm.modules if x.is_bottleneck), None)
        return m.utilisation_pct if m else None

    moved = a.limiting != b.limiting
    if moved:
        reason = (f"Relieving {a.limiting} made {b.limiting} the limit. "
                  f"That is what a change to a limiting element does.")
    else:
        faster = b.capacity_inf_s > a.capacity_inf_s + 1e-9
        slower = b.capacity_inf_s < a.capacity_inf_s - 1e-9
        if faster:
            reason = (f"The change raised the pipeline capacity, but "
                      f"the dominant limiting element remained "
                      f"{b.limiting}.")
        elif slower:
            reason = (f"The change lowered the pipeline capacity and "
                      f"{b.limiting} still holds the system.")
        else:
            reason = (f"The change did not touch {b.limiting}, which "
                      f"limits both designs.")
    return Migration(a.limiting, b.limiting, a.limiting_kind,
                     b.limiting_kind, moved, util(a), util(b), reason)


def render_migration(mig: Migration) -> List[str]:
    from .visual.text import wrap_text

    out = ["BOTTLENECK MIGRATION", ""]
    out.append(f"  Before      {mig.before}"
               f"   ({mig.before_kind}"
               + (f", {mig.before_util:.1f}%)"
                  if mig.before_util is not None else ")"))
    out.append(f"  After       {mig.after}"
               f"   ({mig.after_kind}"
               + (f", {mig.after_util:.1f}%)"
                  if mig.after_util is not None else ")"))
    out.append("")
    out.append(f"  The limit {'MOVED' if mig.moved else 'did NOT move'}"
               + (f": {mig.before} -> {mig.after}" if mig.moved else "."))
    out.append("")
    out.append("  Reason")
    for line in wrap_text(mig.reason, 62):
        out.append(f"      {line}")
    return out


# ==============================================================================
# The block diagram
# ==============================================================================
#
# A table of modules and a table of links is two tables. What a reader
# wants is the picture: where the data goes and where it is held up.
#
# Colour and thickness both carry the load, so the bottleneck is visible
# to a reader who cannot distinguish the colours.

def _load_colour(pct):
    if pct is None:
        return "#8A99A6"
    if pct >= 85.0:
        return "#9C2B2B"
    if pct >= 60.0:
        return "#C4761E"
    return "#2E7A80"


# ONE RENDERER, TWO STYLES.
#
# An experiment needs the same figure with the bottleneck emphasis
# removed, to find out whether the emphasis does any work or whether the
# diagram alone would do. Two rendering functions would drift, so the
# style is a parameter and the algorithm is not touched:
#
#     positions, lines, modules, utilisations, link loads and the
#     bottleneck VALUES are identical
#
#     the red box, the LIMITING ELEMENT badge, the emphasis colour and
#     the heavier border are what change
#
# The consequence is testable: the semantic digest must be the same
# across styles and the image digest must not.
# THE PRODUCT SCREEN IS NOT A STUDY ARM.
#
# The shipped subtitle - "Limiting element: host - it is a module" -
# states the conclusion, which is a good thing for a reader and fatal
# for a blind study asking where the bottleneck is. Removing it from the
# product to suit an experiment would trade the tool's explanatory power
# for a measurement, so the suppression lives in the study styles and
# the product keeps its subtitle.
#
#     PRODUCT_NORMAL        subtitle yes, emphasis yes
#     STUDY_FULL            subtitle no,  emphasis yes
#     STUDY_NO_HIGHLIGHT    subtitle no,  emphasis no
#
# STUDY_FULL is NOT "the current product screen". It is a
# full-information stimulus with the answer-revealing labels
# suppressed, and calling it the product screen would misdescribe what
# the arms compare.
PRODUCT_NORMAL = "product_normal"
STUDY_FULL = "study_full"
STUDY_NO_HIGHLIGHT = "study_no_highlight"

STYLES = (PRODUCT_NORMAL, STUDY_FULL, STUDY_NO_HIGHLIGHT)

# Retained: the product path passes no style and gets the shipped one.
NORMAL = PRODUCT_NORMAL
NO_HIGHLIGHT = STUDY_NO_HIGHLIGHT

STYLE_MEANING = {
    PRODUCT_NORMAL: "the shipped screen: the limiting element is named "
                    "in the subtitle and marked in the diagram",
    STUDY_FULL: "a full-information study stimulus with the "
                "answer-revealing labels suppressed. The emphasis "
                "remains; the subtitle naming the limiting element "
                "does not",
    STUDY_NO_HIGHLIGHT: "the same stimulus without the red box, the "
                        "LIMITING ELEMENT badge or the emphasis "
                        "colour. Every figure is drawn in the same "
                        "place",
}

# THE CONTRACT, declared rather than distributed through the drawing
# code. What each style keeps and what it removes is a decision an
# experiment rests on, and a decision spread over four `if` statements
# is a decision nobody can read.
#
#   subtitle        the line naming the limiting element
#   answer_label    the LIMITING ELEMENT badge
#   highlight       the red box, the heavier border, the colour bands
#   numeric_values  utilisation, latency share, link load
#   layout          positions, arrows, ordering
STYLE_CONTRACT: Dict[str, Dict[str, object]] = {
    PRODUCT_NORMAL: {
        "subtitle": True, "answer_label": True, "highlight": True,
        "numeric_values": True, "layout": True,
        "purpose": "the commercial screen. The limiting element is "
                   "named, because telling a reader the conclusion is "
                   "what the tool is for"},
    STUDY_FULL: {
        "subtitle": False, "answer_label": False, "highlight": True,
        "numeric_values": True, "layout": True,
        "purpose": "the baseline arm. Everything the product shows "
                   "except the words that state the answer, so the "
                   "measurement is of the diagram and not of reading"},
    STUDY_NO_HIGHLIGHT: {
        "subtitle": False, "answer_label": False, "highlight": False,
        "numeric_values": True, "layout": True,
        "purpose": "against STUDY_FULL this isolates the emphasis: the "
                   "same figures in the same places, drawn without the "
                   "red box or the colour"},
}

_NAMES_THE_ANSWER = {k: bool(v["subtitle"])
                     for k, v in STYLE_CONTRACT.items()}
_EMPHASISES = {k: bool(v["highlight"])
               for k, v in STYLE_CONTRACT.items()}


def treatment(style: str) -> Dict[str, bool]:
    """What an experimenter removed, and nothing else.

    Hashed separately from the engineering meaning so a study can show
    that only the treatment changed: the semantic digest is equal across
    styles, this one is not, and the picture follows this one.
    """
    _check_style(style)
    base = STYLE_CONTRACT[PRODUCT_NORMAL]
    here = STYLE_CONTRACT[style]
    return {f"{k}_removed": bool(base[k]) and not bool(here[k])
            for k in ("subtitle", "answer_label", "highlight",
                      "numeric_values", "layout")}


def treatment_digest(style: str, panel_removed: str = "") -> str:
    """A digest of the manipulation, not of the engineering."""
    import hashlib
    import json as _json
    payload = dict(treatment(style))
    payload["panel_removed"] = panel_removed
    return hashlib.sha256(
        _json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _check_style(style: str) -> str:
    if style not in STYLES:
        raise ValueError(f"unknown render style {style!r}")
    return style


def _names_answer(style: str) -> bool:
    """Whether the figure may state the limiting element in words."""
    return _NAMES_THE_ANSWER[_check_style(style)]


def _emphasis(limit: bool, style: str) -> bool:
    """Whether this element is drawn as the limiting one."""
    return bool(limit) and _EMPHASISES[_check_style(style)]


def render_flow_map_png(fm: "FlowMap", path: str,
                        title: str = "",
                        style: str = NORMAL) -> Optional[str]:
    """Modules as boxes, links as weighted arrows.

    Link thickness AND colour scale with load. A reader who cannot tell
    the colours apart still sees the thick arrow.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch
    except ImportError:
        return None

    PATH = ("host", "ISP", "shared memory", "accelerator",
            "secondary accelerator")
    mods = sorted(fm.modules,
                  key=lambda m: PATH.index(m.name)
                  if m.name in PATH else len(PATH))
    n = len(mods)
    if not n:
        return None

    # Height follows the box count. A fixed 1.9 inches of chrome left a
    # third of the canvas empty above the first box.
    step = 2.6
    fig_h = 1.45 + n * step * 0.60
    fig, ax = plt.subplots(figsize=(8.2, fig_h))
    ax.set_xlim(0, 10)
    ax.set_ylim(0.2, n * step + 0.5)
    ax.axis("off")

    link_by_source = {l.source: l for l in fm.links}

    for i, mod in enumerate(mods):
        y = (n - 1 - i) * step + 0.8
        # THE BOX MARKS THE LIMIT. THE BAR MEASURES UTILISATION.
        #
        # They were the same red, so a reader saw a red bar at 43.8% and
        # read "utilisation is dangerous". It is not: the red means
        # ANALYTICAL LIMIT, which is a different statement about a
        # different quantity.
        # THE VALUE IS UNCHANGED; only whether it is emphasised.
        limit = _emphasis(mod.is_bottleneck, style)
        face = "#FBF3F3" if limit else "#F2F6F7"
        edge = "#9C2B2B" if limit else "#7A8894"
        title_col = "#9C2B2B" if limit else "#3A5265"
        BAR = "#5A7A8C"   # neutral on every module, always
        ax.add_patch(FancyBboxPatch(
            (2.4, y), 5.2, 1.35,
            boxstyle="round,pad=0.06", linewidth=2.2 if limit else 1.4,
            facecolor=face, edgecolor=edge, zorder=3))
        ax.text(5.0, y + 1.00, mod.name.upper(), ha="center",
                fontsize=12, fontweight="bold", color=title_col,
                zorder=4)

        util = ("not resolved" if mod.utilisation_pct is None
                else f"{mod.utilisation_pct:.1f}%")
        # "n/e" is developer shorthand. A product screen says what it
        # means: the latency flow and the throughput view decompose
        # differently, so this module has no share of one job's time.
        share = ("not resolved" if mod.latency_share_pct is None
                 else f"{mod.latency_share_pct:.1f}%")
        ax.text(3.0, y + 0.55, f"utilisation  {util}", ha="left",
                fontsize=9.5, color="#333333", zorder=4)
        ax.text(3.0, y + 0.22, f"latency share  {share}", ha="left",
                fontsize=9.5,
                color="#333333" if mod.latency_share_pct is not None
                else "#8A99A6", zorder=4)

        # The utilisation bar, drawn inside the box.
        if mod.utilisation_pct is not None:
            w = 1.6 * min(mod.utilisation_pct, 100.0) / 100.0
            ax.add_patch(FancyBboxPatch(
                (5.9, y + 0.30), 1.6, 0.30, boxstyle="square,pad=0",
                facecolor="#FFFFFF", edgecolor="#C8D2D8",
                linewidth=0.8, zorder=4))
            if w > 0:
                ax.add_patch(FancyBboxPatch(
                    (5.9, y + 0.30), w, 0.30, boxstyle="square,pad=0",
                    facecolor=BAR, edgecolor="none", zorder=5))

        # THE BADGE IS WORDS, THE BOX IS EMPHASIS.
        #
        # "LIMITING ELEMENT" names the answer in text, so it goes
        # wherever the subtitle goes. The red box and the colour stay in
        # STUDY_FULL: that arm asks whether emphasis helps, not whether
        # a label can be read.
        if limit and _names_answer(style):
            ax.text(7.75, y + 0.62, "LIMITING\nELEMENT", ha="left",
                    fontsize=9, fontweight="bold", color="#9C2B2B",
                    linespacing=1.3, zorder=4)

        link = link_by_source.get(mod.name)
        if i < n - 1:
            y_top, y_bot = y, y - step + 1.35
            load = link.load_pct if link else None
            # The link's colour band is emphasis, not value: the load
            # figure beside it is printed either way.
            colour = (_load_colour(load) if style == NORMAL
                      else "#7A8894")
            width = 1.5 + (0.06 * min(load, 100.0) if load else 0.0)
            ax.annotate("", xy=(5.0, y_bot), xytext=(5.0, y_top),
                        arrowprops=dict(arrowstyle="-|>",
                                        linewidth=width, color=colour,
                                        shrinkA=2, shrinkB=2), zorder=2)
            if link is not None:
                label = ("load not resolved" if load is None
                         else f"load {load:.1f}%")
                ax.text(5.25, (y_top + y_bot) / 2, label, ha="left",
                        fontsize=9.5, color=colour,
                        fontweight="bold"
                        if _emphasis(link.is_bottleneck, style)
                        else "normal", zorder=4)
                if link.is_bottleneck:
                    ax.text(5.25, (y_top + y_bot) / 2 - 0.32,
                            "LINK BOTTLENECK", ha="left", fontsize=9,
                            fontweight="bold", color="#9C2B2B",
                            zorder=4)

    # The title grew a configuration label and its descenders reached
    # the subtitle. Separate rows, with room made for both.
    head = title or "System Flow and Bottleneck Map"
    fig.suptitle(head, fontsize=13.5, fontweight="bold", y=0.975)
    # THE SUBTITLE STATES THE CONCLUSION.
    #
    # Right for a reader, fatal for a study asking where the bottleneck
    # is: it would measure whether a participant can read one line.
    if _names_answer(style):
        fig.text(0.5, 0.925,
                 f"Limiting element: {fm.limiting}  ·  it is a "
                 f"{fm.limiting_kind}",
                 ha="center", fontsize=10.5, color="#333333")
    fig.text(0.5, 0.035,
             "Arrow thickness and colour both carry the link load.",
             ha="center", fontsize=9, color="#666666")
    fig.text(0.5, 0.010,
             "Analytical estimates. No queue model, no measured "
             "occupancy - see MEM-ARB-001.",
             ha="center", fontsize=8.5, color="#8A99A6")
    fig.tight_layout(rect=(0.01, 0.06, 0.99, 0.885))
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def render_migration_png(mig: "Migration", path: str,
                         before_label: str = "",
                         after_label: str = "") -> Optional[str]:
    """Where the limit was, and where it went."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch
    except ImportError:
        return None

    fig, ax = plt.subplots(figsize=(8.2, 2.9))
    ax.set_xlim(0, 10); ax.set_ylim(0, 3); ax.axis("off")

    # THE DESIGNS ARE NAMED. A picture that says BEFORE and AFTER loses
    # its context the moment it is pasted into a slide.
    for x, label, name, pct, live in (
            (1.0, (before_label or "STARTING POINT").upper(),
             mig.before, mig.before_util, not mig.moved),
            (6.2, (after_label or "CURRENT DESIGN").upper(),
             mig.after, mig.after_util, True)):
        edge = "#9C2B2B" if live else "#8A99A6"
        face = "#F6DEDE" if live else "#EEF1F3"
        ax.add_patch(FancyBboxPatch(
            (x, 0.7), 2.8, 1.5, boxstyle="round,pad=0.06",
            facecolor=face, edgecolor=edge, linewidth=2.0))
        ax.text(x + 1.4, 1.85, label[:24], ha="center", fontsize=9,
                color="#666666")
        ax.text(x + 1.4, 1.32, name, ha="center", fontsize=13,
                fontweight="bold", color=edge)
        ax.text(x + 1.4, 0.92,
                "n/e" if pct is None else f"{pct:.1f}%",
                ha="center", fontsize=10, color="#333333")

    colour = "#9C2B2B" if mig.moved else "#8A99A6"
    ax.annotate("", xy=(6.0, 1.45), xytext=(4.0, 1.45),
                arrowprops=dict(arrowstyle="-|>", linewidth=2.6,
                                color=colour))
    ax.text(5.0, 1.62, "MOVED" if mig.moved else "UNCHANGED",
            ha="center", fontsize=10.5, fontweight="bold", color=colour)

    fig.suptitle("Bottleneck Migration", fontsize=14, fontweight="bold",
                 y=0.97)
    note = mig.reason
    fig.text(0.5, 0.06, note, ha="center", fontsize=9.5,
             color="#333333")
    fig.tight_layout(rect=(0.01, 0.09, 0.99, 0.90))
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


# ==============================================================================
# ST-11 - the comparative map
# ==============================================================================
#
# A demonstration is a REFERENCE and a CURRENT design. Showing only the
# current one leaves the reader asking the first question they have:
# "what was it before?"
#
# Every figure is therefore `reference -> current`, and a figure that did
# not move is greyed rather than repeated in full - a reader looks for
# what changed before they look at anything else.

CHANGE_EPS = 0.05          # percentage points below which nothing moved


@dataclass(frozen=True)
class ComparedModule:
    name: str
    ref_util: Optional[float]
    cur_util: Optional[float]
    ref_share: Optional[float]
    cur_share: Optional[float]
    ref_limit: bool
    cur_limit: bool

    @property
    def changed(self) -> bool:
        for a, b in ((self.ref_util, self.cur_util),
                     (self.ref_share, self.cur_share)):
            if a is None or b is None:
                if a is not b:
                    return True
                continue
            if abs(a - b) > CHANGE_EPS:
                return True
        return self.ref_limit != self.cur_limit


@dataclass(frozen=True)
class ComparedLink:
    source: str
    target: str
    ref_load: Optional[float]
    cur_load: Optional[float]
    ref_bn: bool
    cur_bn: bool
    # THE NUMERATOR AND THE DENOMINATOR.
    #
    # "load 11.4% -> 1.2%" invites the question it does not answer: where
    # did those come from? Demand barely moved and available bandwidth
    # rose ninefold, which is the whole evidence for why a sixteenfold
    # memory produced a modest speedup. Hiding the denominator hid the
    # argument.
    ref_demand: Optional[float] = None
    cur_demand: Optional[float] = None
    ref_available: Optional[float] = None
    cur_available: Optional[float] = None

    @property
    def changed(self) -> bool:
        if self.ref_load is None or self.cur_load is None:
            return self.ref_load is not self.cur_load
        return (abs(self.ref_load - self.cur_load) > CHANGE_EPS
                or self.ref_bn != self.cur_bn)


@dataclass(frozen=True)
class ComparedFlowMap:
    modules: Tuple[ComparedModule, ...]
    links: Tuple[ComparedLink, ...]
    ref_limiting: str
    cur_limiting: str
    ref_kind: str
    cur_kind: str
    reference_label: str
    current_label: str
    change_summary: Tuple[str, ...] = ()
    key_insight: str = ""

    @property
    def limit_moved(self) -> bool:
        return self.ref_limiting != self.cur_limiting


def build_compared_flow_map(ref_analysis, cur_analysis,
                            reference_label: str = "Reference",
                            current_label: str = "Current"
                            ) -> ComparedFlowMap:
    a, b = build_flow_map(ref_analysis), build_flow_map(cur_analysis)
    ra = {m.name: m for m in a.modules}
    rb = {m.name: m for m in b.modules}

    PATH = ("host", "ISP", "shared memory", "accelerator",
            "secondary accelerator")
    names = sorted(set(ra) | set(rb),
                   key=lambda n: PATH.index(n) if n in PATH else len(PATH))

    mods = tuple(
        ComparedModule(
            n,
            ra[n].utilisation_pct if n in ra else None,
            rb[n].utilisation_pct if n in rb else None,
            ra[n].latency_share_pct if n in ra else None,
            rb[n].latency_share_pct if n in rb else None,
            bool(n in ra and ra[n].is_bottleneck),
            bool(n in rb and rb[n].is_bottleneck))
        for n in names)

    la = {(l.source, l.target): l for l in a.links}
    lb = {(l.source, l.target): l for l in b.links}
    links = tuple(
        ComparedLink(
            s, t,
            la[(s, t)].load_pct if (s, t) in la else None,
            lb[(s, t)].load_pct if (s, t) in lb else None,
            bool((s, t) in la and la[(s, t)].is_bottleneck),
            bool((s, t) in lb and lb[(s, t)].is_bottleneck),
            la[(s, t)].demand_gbs if (s, t) in la else None,
            lb[(s, t)].demand_gbs if (s, t) in lb else None,
            la[(s, t)].available_gbs if (s, t) in la else None,
            lb[(s, t)].available_gbs if (s, t) in lb else None)
        for s, t in sorted(set(la) | set(lb)))

    changes = _describe_change(ref_analysis, cur_analysis)
    insight = _key_insight(mods, links, a, b)
    return ComparedFlowMap(mods, links, a.limiting, b.limiting,
                           a.limiting_kind, b.limiting_kind,
                           reference_label, current_label,
                           changes, insight)


def _describe_change(ref_analysis, cur_analysis) -> Tuple[str, ...]:
    """What was actually altered, from the engine's own figures.

    A title reading "ordinary -> 16x wider" does not say what is sixteen
    times what. A reader has to know what was changed before the figures
    below it mean anything.
    """
    import dataclasses

    a = ref_analysis.current_config
    b = cur_analysis.current_config
    am = ref_analysis.current_result.metrics
    bm = cur_analysis.current_result.metrics

    # THE INTERNAL KEY IS NOT THE PRODUCT WORDING.
    #
    # `preprocessing mode: cpu_only -> isp_and_npu` is the field name and
    # the enum value, both of them written for the code. The keys stay in
    # the export metadata, where a reader who wants them can find them.
    # ONE DISPLAY HELPER, NOT A SECOND TABLE.
    #
    # This module kept its own FIELD and VALUE maps, and they had no
    # entry for the host processor - so a report table read
    # "Cortex-A78 x4" while the figure drawn beside it read
    # "cortex_a78_x4". The audit that reported "raw keys: 0" checked
    # rows and captions and could not see inside a PNG.
    from .engineering_report import FIELD_LABEL, _pretty

    out: List[str] = []
    for f in dataclasses.fields(a):
        va, vb = getattr(a, f.name), getattr(b, f.name)
        if va != vb:
            label = FIELD_LABEL.get(
                f.name, f.name.replace("_", " ").capitalize())
            out.append(f"{label}: {_pretty(f.name, va)} \u2192 "
                       f"{_pretty(f.name, vb)}")

    for label, key, unit in (
            ("Memory bandwidth", "Effective bandwidth (GB/s)", "GB/s"),
            ("Accelerator throughput", "Accel peak (TOPS)", "TOPS")):
        x, y = am.get(key), bm.get(key)
        if x and y and abs(x - y) > 1e-9:
            out.append(f"{label}: {x:,.1f} \u2192 {y:,.1f} {unit}"
                       f"  (\u00d7{y / x:.1f})")
    if not out:
        out.append("No configuration field differs.")
    else:
        out.append("Other architecture choices: unchanged.")
    return tuple(out)


def _key_insight(mods, links, a, b) -> str:
    """One sentence about the CAUSE, not a repetition of the figures.

    A reader who has the numbers still needs to be told what they mean
    together, and that sentence is the one they carry away.
    """
    moved = a.limiting != b.limiting
    biggest = None
    for l in links:
        if l.ref_load is None or l.cur_load is None:
            continue
        if biggest is None or abs(l.cur_load - l.ref_load) > abs(
                biggest.cur_load - biggest.ref_load):
            biggest = l

    if moved:
        def kind_of(fm, name):
            return "link" if fm.limiting_kind == "link" else "module"
        return (f"The limiting element moved from the {a.limiting} "
                f"{kind_of(a, a.limiting)} to the {b.limiting} "
                f"{kind_of(b, b.limiting)}. Relieving one element made "
                f"another the lowest-capacity stage, so the next change "
                f"belongs somewhere else.")

    if biggest is not None and abs(biggest.cur_load
                                   - biggest.ref_load) > 1.0:
        direction = ("fell" if biggest.cur_load < biggest.ref_load
                     else "rose")
        supply = ""
        if (biggest.ref_available and biggest.cur_available
                and abs(biggest.cur_available - biggest.ref_available)
                > 1e-9):
            demand_same = (biggest.ref_demand and biggest.cur_demand
                           and abs(biggest.cur_demand
                                   - biggest.ref_demand) < 0.01)
            if demand_same:
                supply = (" The demand did not change; the available "
                          "bandwidth did.")
        return (f"The {biggest.source} to {biggest.target} load "
                f"{direction} from {biggest.ref_load:.1f}% to "
                f"{biggest.cur_load:.1f}%, and the limiting element "
                f"remained {b.limiting}.{supply} The change removed "
                f"capacity the workload was not using.")

    # THE LIMITING ELEMENT ITSELF, before concluding nothing reached it.
    #
    # This looked only at LINK loads. Replacing a Cortex-A78 with a
    # Cortex-A53 took host utilisation from 50.8% to 100.0% while every
    # link stayed where it was, and the sentence read "the change did
    # not reach the limiting element" about a change made directly to
    # the limiting element. `mods` was passed in and never used.
    lim = next((m for m in mods if m.name == b.limiting), None)
    if (lim is not None and lim.ref_util is not None
            and lim.cur_util is not None
            and abs(lim.cur_util - lim.ref_util) > 1.0):
        if lim.cur_util >= 99.5:
            return (f"{b.limiting} limits both designs and is now fully "
                    f"saturated: its utilisation rose from "
                    f"{lim.ref_util:.1f}% to {lim.cur_util:.1f}%. The "
                    f"change acted directly on the limiting element.")
        direction = ("rose" if lim.cur_util > lim.ref_util else "fell")
        return (f"{b.limiting} limits both designs and its utilisation "
                f"{direction} from {lim.ref_util:.1f}% to "
                f"{lim.cur_util:.1f}%. The change acted directly on the "
                f"limiting element without moving the limit elsewhere.")

    return (f"{b.limiting} limits both designs, no link load moved "
            f"materially, and the utilisation of the limiting element "
            f"is unchanged. The change did not reach the limiting "
            f"element.")


def _pair(a: Optional[float], b: Optional[float], unit="%") -> str:
    def one(v):
        return "not resolved" if v is None else f"{v:.1f}{unit}"
    if a is None and b is None:
        return "not resolved"
    return f"{one(a)} \u2192 {one(b)}"


def _state(pct: Optional[float]) -> str:
    """Three bands, from the FIGURE alone.

    The limiting element used to force this red, so a host at 43.8% got a
    red bar under a legend saying "bottleneck >= 85%". One colour was
    carrying two meanings: how big the number is, and whether this is
    what limits the system. They are separate claims and they now have
    separate encodings - colour for the band, box and badge for the
    limit.
    """
    if pct is None:
        return "none"
    if pct >= 85.0:
        return "high"
    if pct >= 60.0:
        return "warning"
    return "normal"


STATE_COLOUR = {"normal": "#5A7A8C", "warning": "#C4761E",
                "high": "#9C2B2B", "none": "#C8D2D8"}
LIMIT_RED = "#9C2B2B"


def render_compared_flow_map_png(cm: ComparedFlowMap, path: str,
                                 title: str = "") -> Optional[str]:
    """Three columns: starting point, current design, change.

    Two bars stacked from one origin read as two different metrics rather
    than one metric at two times, and a reader had to re-derive which was
    which on every row. POSITION now carries before and after; colour
    carries only the band.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch, Rectangle
    except ImportError:
        return None

    mods = cm.modules
    n = len(mods)
    if not n:
        return None

    GREY, INK, MUTE = "#B3BEC5", "#2F4858", "#6B7A85"
    UP, DOWN = "#C4761E", "#2E7A80"

    # Column geometry, fixed for every row in the figure.
    L_X, R_X, COL_W = 4.30, 7.30, 2.35
    CHG_X = 10.20

    rows_per_mod, rows_per_link = 2, 3
    mod_h = 0.62 + rows_per_mod * 0.62
    link_h = 0.52 + rows_per_link * 0.46
    gap = 0.30
    n_change = len(cm.change_summary)

    linked = sum(1 for m in mods[:-1]
                 if any(l.source == m.name for l in cm.links))
    unlinked = max(0, (n - 1) - linked)
    total = (n * mod_h + linked * (link_h + 2 * gap)
             + unlinked * (0.55 + 2 * gap) + 0.5)
    top = 0.95 + 0.28 * n_change
    fig, ax = plt.subplots(
        figsize=(11.0, 2.9 + total * 0.62 + 0.18 * n_change))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, total + top)
    ax.axis("off")

    y0 = total + top - 0.25
    ax.text(0.3, y0, "DESIGN CHANGE", fontsize=9.5, fontweight="bold",
            color=LIMIT_RED, ha="left")
    for i, line in enumerate(cm.change_summary):
        ax.text(0.3, y0 - 0.30 * (i + 1), line, fontsize=9,
                color=INK if i < n_change - 1 else MUTE, ha="left")

    # COLUMN HEADERS, once. Everything below aligns to them.
    head = total + 0.28
    for x, top_lab, sub, col in ((L_X, "STARTING POINT",
                                  cm.reference_label, MUTE),
                                 (R_X, "CURRENT DESIGN",
                                  cm.current_label, INK)):
        ax.text(x + COL_W / 2, head + 0.26, top_lab, ha="center",
                fontsize=9, fontweight="bold", color=col)
        ax.text(x + COL_W / 2, head, sub[:26], ha="center",
                fontsize=8.5, color=col, style="italic")
    ax.text(CHG_X + 0.55, head + 0.26, "CHANGE", ha="center",
            fontsize=9, fontweight="bold", color=MUTE)

    # Vertical guides, so a row twelve lines down still reads as a column.
    for x in (L_X, R_X):
        ax.plot([x - 0.12, x - 0.12], [0.15, head - 0.18],
                color="#E4EAEE", linewidth=1.0, zorder=1)
    ax.plot([CHG_X - 0.15, CHG_X - 0.15], [0.15, head - 0.18],
            color="#E4EAEE", linewidth=1.0, zorder=1)

    def row(label, y, ref, cur, unit="%", scale=100.0, bar=True):
        """One metric, three columns, aligned inside each."""
        ax.text(L_X - 0.30, y + 0.08, label, ha="right", fontsize=9,
                color=MUTE, zorder=5)
        for x, v in ((L_X, ref), (R_X, cur)):
            if v is None:
                ax.text(x + COL_W / 2, y + 0.08, "\u2014", ha="center",
                        fontsize=9.5, color=GREY, zorder=5)
                continue
            txt = f"{v:,.1f}{unit}"
            ax.text(x + COL_W / 2, y + 0.20, txt, ha="center",
                    fontsize=9.5, color=INK, zorder=5)
            if bar:
                colour = STATE_COLOUR[_state(v)]
                ax.add_patch(Rectangle((x, y), COL_W, 0.13,
                                       facecolor="#EEF2F4",
                                       edgecolor="none", zorder=3))
                ax.add_patch(Rectangle(
                    (x, y), COL_W * min(v / scale, 1.0), 0.13,
                    facecolor=colour, edgecolor="none", zorder=4))
        if ref is not None and cur is not None and unit == "%":
            d = cur - ref
            if abs(d) >= CHANGE_EPS:
                ax.text(CHG_X, y + 0.14,
                        f"{'\u25b2' if d > 0 else '\u25bc'} "
                        f"{abs(d):.1f} pp", ha="left", fontsize=9,
                        fontweight="bold", color=UP if d > 0 else DOWN,
                        zorder=5)

    link_by_source = {l.source: l for l in cm.links}
    y = total - 0.2

    for i, mod in enumerate(mods):
        y -= mod_h
        edge = LIMIT_RED if mod.cur_limit else (
            INK if mod.changed else GREY)
        ax.add_patch(FancyBboxPatch(
            (0.25, y), 11.5, mod_h - 0.10,
            boxstyle="round,pad=0.05",
            linewidth=2.2 if mod.cur_limit else 1.0,
            facecolor="#FCF6F6" if mod.cur_limit else "#FAFBFC",
            edgecolor=edge, zorder=2))
        ax.text(0.55, y + mod_h - 0.42, mod.name.upper(), ha="left",
                fontsize=12, fontweight="bold", color=edge, zorder=5)
        if mod.cur_limit:
            tag = ("NOW THE LIMITING ELEMENT" if not mod.ref_limit
                   else "LIMITING ELEMENT IN BOTH")
            ax.text(0.55, y + mod_h - 0.78, tag, ha="left", fontsize=8.5,
                    fontweight="bold", color=LIMIT_RED, zorder=5)
        elif mod.ref_limit:
            ax.text(0.55, y + mod_h - 0.78, "was the limiting element",
                    ha="left", fontsize=8.5, color=GREY, zorder=5)

        row("utilisation", y + mod_h - 0.72, mod.ref_util, mod.cur_util)
        row("latency share", y + mod_h - 1.34, mod.ref_share,
            mod.cur_share)

        link = link_by_source.get(mod.name)
        if i < n - 1:
            y -= gap
            # A module with no outgoing link reserved a full link block
            # and left a tall empty band with a bare arrow in it. The gap
            # is now the size of what it actually holds.
            block = link_h if link is not None else 0.55
            top_y, bot_y = y, y - block
            # THE CONNECTOR IS THE LINK. Its width is the current load;
            # the numbers below confirm it rather than compete with it.
            lc = (LIMIT_RED if link and link.cur_bn
                  else STATE_COLOUR[_state(link.cur_load if link
                                           else None)])
            w = 1.2 + 0.06 * min(link.cur_load or 0.0, 100.0) \
                if link else 1.2
            ax.annotate("", xy=(1.5, bot_y), xytext=(1.5, top_y),
                        arrowprops=dict(arrowstyle="<|-|>", linewidth=w,
                                        color=lc, shrinkA=1, shrinkB=1),
                        zorder=3)
            if link is not None:
                ax.text(1.9, top_y - 0.22,
                        f"{link.source} \u2194 {link.target}",
                        ha="left", fontsize=9, color=MUTE, zorder=5)
                if link.ref_bn and not link.cur_bn:
                    ax.text(1.9, top_y - 0.48,
                            "WAS THE BOTTLENECK \u00b7 RESOLVED",
                            ha="left", fontsize=8.5, fontweight="bold",
                            color=DOWN, zorder=5)
                elif link.cur_bn:
                    short = (link.cur_load or 0) - 100.0
                    tail = (f" \u00b7 demand exceeds capacity by "
                            f"{short:.1f}%" if short > 0 else "")
                    ax.text(1.9, top_y - 0.48, f"LINK BOTTLENECK{tail}",
                            ha="left", fontsize=8.5, fontweight="bold",
                            color=LIMIT_RED, zorder=5)
                row("demand", top_y - 0.78, link.ref_demand,
                    link.cur_demand, " GB/s", bar=False)
                row("available", top_y - 1.20, link.ref_available,
                    link.cur_available, " GB/s", bar=False)
                row("demand / available", top_y - 1.62, link.ref_load,
                    link.cur_load)
            y = bot_y - gap

    fig.suptitle(title or "System Flow and Bottleneck Map",
                 fontsize=13.5, fontweight="bold", y=0.985)

    def kinded(name, kind):
        if kind == "link":
            return f"LINK {name.replace(chr(0x2192), chr(0x2194))}"
        return f"MODULE {name}"

    moved = (f"Limiting element moved:  "
             f"{kinded(cm.ref_limiting, cm.ref_kind)}"
             f"   \u21e8   {kinded(cm.cur_limiting, cm.cur_kind)}"
             if cm.limit_moved
             else f"Limiting element unchanged:  "
                  f"{kinded(cm.cur_limiting, cm.cur_kind)}")
    fig.text(0.5, 0.955, moved, ha="center", fontsize=10.5,
             fontweight="bold",
             color=LIMIT_RED if cm.limit_moved else MUTE)

    for k, (st, lab) in enumerate((
            ("normal", "< 60%"), ("warning", "60-85%"),
            ("high", "\u2265 85%"))):
        x = 0.06 + 0.085 * k
        fig.patches.append(plt.Rectangle(
            (x, 0.108), 0.016, 0.010, transform=fig.transFigure,
            facecolor=STATE_COLOUR[st], edgecolor="none"))
        fig.text(x + 0.021, 0.107, lab, fontsize=8.5, color=MUTE,
                 ha="left")
    fig.text(0.06 + 0.085 * 3 + 0.02, 0.107,
             "\u00b7  bar colour is the value band; the red box and "
             "badge mark the limiting element",
             fontsize=8.5, color=MUTE, ha="left")

    if cm.key_insight:
        from .visual.text import wrap_text
        lines_ = wrap_text(cm.key_insight, 128)
        fig.text(0.06, 0.080, "KEY INSIGHT", fontsize=9.5,
                 fontweight="bold", color=LIMIT_RED, ha="left")
        for i, ln in enumerate(lines_[:2]):
            fig.text(0.06, 0.058 - 0.018 * i, ln, fontsize=9.5,
                     color=INK, ha="left")

    one_sided = any(
        (m.ref_util is None) != (m.cur_util is None) for m in mods)
    foot = ("\u2014 Not separately resolved for this configuration. "
            "Link demand and capacity remain directly comparable."
            if one_sided else
            "\u2014 not separately resolved by the analytical model.")
    fig.text(0.5, 0.021, foot, ha="center", fontsize=8, color=MUTE)
    fig.text(0.5, 0.006,
             "Link figures are bidirectional aggregates. No queue "
             "model, no measured occupancy - see MEM-ARB-001.",
             ha="center", fontsize=8, color=GREY)
    fig.tight_layout(rect=(0.01, 0.128, 0.99, 0.940))
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path
