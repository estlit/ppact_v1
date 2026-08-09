"""
ppact.charts - matplotlib output

Two views that answer different questions. The spider chart normalizes, so
it shows balance but hides magnitude; the bar panels show absolute values
against the product budget. Measured per GB/s an HBM stack has the best
area efficiency of any DRAM while being the largest in absolute silicon,
which is exactly why both views are required.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np
import matplotlib.pyplot as plt

from .core import PALETTE, _finalize, _display_png
from .memory import AXIS_ORDER, MemorySpec, PPACTResult
from .system import SystemResult, SYSTEM_AXES, score_system


def render_spider(results: Sequence[PPACTResult], path: str = "ppact_spider.png",
                  annotate: bool = True) -> str:
    """Overlay every profile on one set of axes.

    Separate charts are avoided on purpose: the eye compares angles and areas
    poorly across figures, which is exactly how two very different technologies
    can end up looking similar.
    """
    labels = AXIS_ORDER
    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8.5, 8.5), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("white")
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=13, fontweight="bold")
    ax.tick_params(axis="x", pad=22)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=9, color="#777777")
    ax.grid(color="#DDDDDD", linestyle="--", linewidth=1.2)
    ax.spines["polar"].set_color("#BBBBBB")

    for i, res in enumerate(results):
        color = PALETTE[i % len(PALETTE)]
        values = res.score_vector + res.score_vector[:1]
        ax.plot(angles, values, color=color, linewidth=2.5, label=res.spec.name)
        ax.fill(angles, values, color=color, alpha=0.16)
        ax.scatter(angles[:-1], res.score_vector, color=color, s=26, zorder=5)

    # Printing the value at each vertex. With three overlapping polygons the eye
    # cannot reliably trace which edge belongs to which series, and a large
    # polygon reads as "wins everywhere" even where it collapses inward. The
    # numbers remove the ambiguity; a small angular offset per series keeps
    # labels from stacking when two scores are close.
    if annotate:
        spread = np.radians(5.0)
        base = -(len(results) - 1) / 2.0
        for i, res in enumerate(results):
            color = PALETTE[i % len(PALETTE)]
            off = (base + i) * spread
            for ang, val in zip(angles[:-1], res.score_vector):
                ax.text(ang + off, val + 7, f"{val:.0f}",
                        color=color, fontsize=8.5, fontweight="bold",
                        ha="center", va="center", zorder=6,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white",
                                  ec="none", alpha=0.75))

    title = "PPACT Profile: " + " vs ".join(r.spec.name for r in results)
    ax.set_title(title, size=17, fontweight="bold", pad=48)
    ax.legend(loc="upper right", bbox_to_anchor=(1.22, 1.10), frameon=False, fontsize=11)

    fig.text(0.5, 0.015,
             "Basis: one package. Scores use fixed anchors (see ANCHORS) so the "
             "scale stays valid when new memory types are added.",
             ha="center", fontsize=8.5, color="#666666")

    return _finalize(fig, path)


def render_block_diagram(spec: MemorySpec, path: str = "ppact_schematic.png") -> str:
    """Graphviz when available, matplotlib otherwise.

    The original script injected a hard-coded Windows Graphviz path and would
    raise on any other machine. Rendering a diagram is presentation, not the
    point of the simulation, so it must never take the analysis down with it.
    """
    try:
        import graphviz  # noqa: F401
        dot = graphviz.Digraph(comment="Architecture", format="png")
        dot.attr(rankdir="LR", ranksep="1.4", nodesep="0.9", splines="ortho")
        dot.attr("node", shape="box", style="filled", fillcolor="white", color="black",
                 fontname="Helvetica-Bold", fontsize="15", penwidth="2.0",
                 width="3.2", height="1.1")
        dot.attr("edge", color="black", penwidth="2.2", arrowsize="1.2",
                 fontname="Helvetica", fontsize="12")
        dot.node("Host", "Host CPU\\n(Controller)")
        dot.node("NPU", "Neural Processing Unit\\n(Compute Core)")
        dot.node("MEM", f"{spec.name}\\n{spec.bus_config}")
        dot.edge("Host", "NPU", xlabel="Cmd", minlen="2")
        dot.edge("NPU", "MEM", xlabel=f"{spec.bandwidth_gbytes_s:.1f} GB/s",
                 dir="both", minlen="2")
        dot.render(path.rsplit(".", 1)[0], format="png", cleanup=True)
        _display_png(path)
        return path
    except Exception:
        pass  # fall through to the matplotlib renderer

    fig, ax = plt.subplots(figsize=(11, 2.6))
    ax.set_xlim(0, 11); ax.set_ylim(0, 2.6); ax.axis("off")
    boxes = [(0.3, "Host CPU\n(Controller)"),
             (4.0, "Neural Processing Unit\n(Compute Core)"),
             (7.7, f"{spec.name}\n{spec.bus_config}")]
    for x, text in boxes:
        ax.add_patch(plt.Rectangle((x, 0.7), 3.0, 1.2, fill=True, facecolor="white",
                                   edgecolor="black", linewidth=2.0))
        ax.text(x + 1.5, 1.3, text, ha="center", va="center",
                fontsize=11, fontweight="bold")
    ax.annotate("", xy=(4.0, 1.3), xytext=(3.3, 1.3),
                arrowprops=dict(arrowstyle="->", lw=2.2, color="black"))
    ax.text(3.65, 1.55, "Cmd", ha="center", fontsize=9)
    ax.annotate("", xy=(7.7, 1.3), xytext=(7.0, 1.3),
                arrowprops=dict(arrowstyle="<->", lw=2.2, color="black"))
    ax.text(7.35, 1.55, f"{spec.bandwidth_gbytes_s:.1f} GB/s", ha="center", fontsize=9)
    return _finalize(fig, path)


# ==============================================================================

_BAR_SPECS = [
    ("SoC silicon (mm2)", "soc_silicon_budget_mm2", "SoC die area", "mm2"),
    ("Total silicon (mm2)", None, "Total silicon (incl. DRAM)", "mm2"),
    ("Board area (mm2)", "board_budget_mm2", "Board area", "mm2"),
    ("System power (W)", "power_budget_w", "System power", "W"),
    ("System cost (USD)", "bom_budget_usd", "System BOM", "USD"),
    ("Latency (ms)", "latency_budget_ms", "Inference latency", "ms"),
    ("Reaction distance (m)", "stopping_distance_budget_m",
     "Closed-loop reaction distance", "m"),
    ("Power density (W/mm2)", "thermal_limit_w_per_mm2", "Power density", "W/mm2"),
]


def render_bars(results: Sequence[SystemResult], path: str = "system_bars.png") -> str:
    """Absolute magnitudes with the product budget drawn across each panel.

    This view exists because the spider chart cannot show it. Normalized axes
    answer "which is more efficient"; only absolute bars answer "does it fit",
    and a budget line turns that into something a student can read at a glance.
    """
    app = results[0].app
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    labels = [r.label for r in results]
    x = np.arange(len(results))

    for ax in axes.ravel()[len(_BAR_SPECS):]:
        ax.axis("off")
    for ax, (metric, budget_attr, title, unit) in zip(axes.ravel(), _BAR_SPECS):
        vals = [r.metrics[metric] for r in results]
        budget = getattr(app, budget_attr) if budget_attr else None
        colors = [PALETTE[i % len(PALETTE)] if (budget is None or v <= budget)
                  else "#B03030" for i, v in enumerate(vals)]
        ax.bar(x, vals, color=colors, alpha=0.85, width=0.6)
        if budget is not None:
            ax.axhline(budget, color="#B03030", linestyle="--", linewidth=1.6)
            ax.text(len(results) - 0.4, budget, f" budget {budget:g}", color="#B03030",
                    fontsize=8, va="bottom", ha="right")
        top = max(vals + ([budget] if budget is not None else [])) * 1.35
        ax.set_ylim(0, top)
        for xi, v in zip(x, vals):
            ax.text(xi, v + top * 0.02, f"{v:,.4g}", ha="center", fontsize=8.5,
                    fontweight="bold")
        ax.set_title(f"{title}  [{unit}]", fontsize=11, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([l.replace(" + ", "\n+ ") for l in labels], fontsize=8)
        ax.grid(axis="y", color="#EEEEEE", linewidth=1)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)

    fig.suptitle(f"Absolute magnitudes vs product budgets - {app.name}",
                 fontsize=14, fontweight="bold")
    fig.text(0.5, 0.005, "Red bars exceed the budget. This is the view the "
                         "normalized spider chart cannot show.",
             ha="center", fontsize=9, color="#666666")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    return _finalize(fig, path)


def render_system_spider(results: Sequence[SystemResult],
                         path: str = "system_spider.png") -> Optional[str]:
    survivors = [r for r in results if r.passes]
    if not survivors:
        print("\n  (no candidate passed the gate - nothing to plot)")
        return None

    labels = SYSTEM_AXES
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8.5, 8.5), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=13, fontweight="bold")
    ax.tick_params(axis="x", pad=22)
    ax.set_ylim(0, 100); ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=9, color="#777777")
    ax.grid(color="#DDDDDD", linestyle="--", linewidth=1.2)

    spread = np.radians(5.0)
    base = -(len(survivors) - 1) / 2.0
    for i, res in enumerate(survivors):
        score_system(res)
        color = PALETTE[i % len(PALETTE)]
        # An unscored axis breaks the polygon rather than plotting at
        # zero: zero is a score and says the design is as bad as the
        # anchor allows, which nothing has measured.
        vec = [float("nan") if res.scores[a] is None else res.scores[a]
               for a in labels]
        ax.plot(angles, vec + vec[:1], color=color, linewidth=2.5, label=res.label)
        ax.fill(angles, vec + vec[:1], color=color, alpha=0.16)
        ax.scatter(angles[:-1], vec, color=color, s=26, zorder=5)
        import math as _mch
        for ang, val in zip(angles[:-1], vec):
            if _mch.isnan(val):
                ax.text(ang + (base + i) * spread, 7, "n/e", color=color,
                        fontsize=8.5, fontweight="bold", ha="center",
                        va="center", zorder=6,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white",
                                  ec="none", alpha=0.75))
                continue
            ax.text(ang + (base + i) * spread, val + 7, f"{val:.0f}", color=color,
                    fontsize=8.5, fontweight="bold", ha="center", va="center", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))

    ax.set_title(f"PPACT profile - {results[0].app.name}\n"
                 f"({len(survivors)} of {len(results)} candidates passed the gate)",
                 size=15, fontweight="bold", pad=44)
    ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.10), frameon=False, fontsize=10)
    return _finalize(fig, path)


# ==============================================================================
