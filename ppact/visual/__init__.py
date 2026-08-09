"""
ppact.visual - the rendering layer

Screens pass VALUES here and get characters or a figure back. They do not
decide what a bar looks like, and they do not compute anything on the way.

    text.py     terminal rendering: bars, stacked bars, progress, wrapping
    models.py   the data objects a renderer takes

The separation matters for a reason beyond tidiness: a renderer that cannot
compute cannot change a result. Every screen in this program is checked to
produce identical numbers before and after this layer existed.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from .text import (FILL, TRACK, BLOCKED, IDLE, DEFAULT_WIDTH, LEGEND,
                   render_bar, render_stacked_bar, render_progress,
                   render_rating, render_labelled_bars, wrap_text,
                   legend_line, render_state_bar, state_legend,
                   render_measured_bars, measured_bars_legend,
                   margin_band, margin_legend, MARGIN_BANDS,
                   REQUIREMENT_MARK,
                   STATE_PATTERN, STATE_MEANING, STATE_ORDER)
from .models import BreakdownData, MetricBarData, SpiderData, SpiderAxis
from .flow import (build_flow, render_flow_text, render_flow_png,
                   FlowData, Station, STATION_ORDER, OVERLAP_PARTS,
                   build_throughput_view, render_throughput_view,
                   BlockThroughput, ThroughputView)
from .balance import (BALANCE_NOTICE, TITLE as BALANCE_TITLE,
                      PURPOSE as BALANCE_PURPOSE, FORMULA_HINT,
                      CLIP_HIGH,
                      CLIP_LOW, LINE_STYLES, build_balance,
                      overlapping_axes, render_balance_text, print_balance,
                      render_balance_png, render_balance_web,
                      render_measured_bars_png)

__all__ = [
    "FILL", "TRACK", "BLOCKED", "IDLE", "DEFAULT_WIDTH", "LEGEND",
    "render_bar", "render_stacked_bar", "render_progress", "render_rating",
    "render_labelled_bars", "wrap_text", "legend_line",
    "render_measured_bars", "measured_bars_legend",
    "margin_band", "margin_legend", "MARGIN_BANDS",
    "REQUIREMENT_MARK",
    "render_state_bar", "state_legend", "STATE_PATTERN",
    "STATE_MEANING", "STATE_ORDER",
    "BreakdownData", "MetricBarData", "SpiderData", "SpiderAxis",
    "BALANCE_NOTICE", "BALANCE_TITLE", "BALANCE_PURPOSE",
    "FORMULA_HINT", "CLIP_HIGH", "CLIP_LOW",
    "LINE_STYLES", "build_balance", "overlapping_axes",
    "render_balance_text", "print_balance", "render_balance_png",
    "render_balance_web",
    "build_flow", "render_flow_text", "render_flow_png",
    "FlowData", "Station", "STATION_ORDER", "OVERLAP_PARTS",
    "build_throughput_view", "render_throughput_view",
    "BlockThroughput", "ThroughputView", "render_measured_bars_png",
]
