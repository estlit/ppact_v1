"""
ppact.visual.flow - where one job's time goes, in the order it happens

WHY THIS IS NOT THE OLD COMPOSITION LIST
========================================
The composition section printed stations sorted by size. That is the right
order for "what should I change next" and the wrong order for "what happens
to a job", and it was doing both jobs at once.

`headroom()` returns largest first. Drawn that way, a flow tells a reader
the accelerator runs before the host.

OVERLAP IS NOT A SUM
--------------------
Two stations decompose further, and in both cases the parts run
concurrently:

    accelerator core   arithmetic 2.519 + memory wait 1.564 = 4.082
                       station is 2.910

    host active        host compute 7.239 + host transfer 4.115 = 11.354
                       station is 8.474

A reader shown two numbers under a heading will add them. So the review
says, in words, that they overlap and do not sum - and says which is longer
HERE, computed, because across twelve representative configurations memory
wait was the longer in four of them.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# EXECUTION ORDER. Not size, not the order headroom() happens to return.
# A station absent from a configuration is skipped; one present with zero
# time is omitted rather than drawn empty.
STATION_ORDER = (
    "host active",
    "preprocessing offload",
    "offload overhead",
    "accelerator core",
    "engine hand-off",
)

# The two stations whose internals overlap, and the metrics that describe
# them. Nothing else has an internal decomposition, and a station without
# one shows no internal figures rather than an empty note.
OVERLAP_PARTS: Dict[str, Tuple[Tuple[str, str], Tuple[str, str]]] = {
    "accelerator core": (("arithmetic", "Compute time (ms)"),
                         ("memory wait", "Memory time (ms)")),
    "host active": (("host compute", "Host compute time (ms)"),
                    ("host transfer", "Host transfer time (ms)")),
}

OVERLAP_NOTE = ("These OVERLAP. They run at the same time and do not sum "
                "to the station.")


@dataclass(frozen=True)
class OverlapPart:
    name: str
    ms: float


@dataclass(frozen=True)
class Station:
    name: str
    ms: float
    share_pct: float
    is_dominant: bool = False
    parts: Tuple[OverlapPart, ...] = ()

    @property
    def longer_part(self) -> Optional[OverlapPart]:
        """Which of the two is longer HERE.

        Computed rather than asserted. A fixed sentence saying arithmetic
        is longer would be false in a third of configurations, which is the
        same failure as a recommendation quoting a share no station holds.
        """
        if len(self.parts) != 2:
            return None
        a, b = self.parts
        if abs(a.ms - b.ms) < 1e-9:
            return None
        return a if a.ms > b.ms else b

    def overlap_sentence(self) -> str:
        """What the two parts mean, given what they actually are here.

        A part at 0.000 ms described as "overlapping" reads as a
        contradiction: nothing overlaps with nothing. When one part is
        negligible against the station the sentence says so instead, which
        is both true and the more useful fact.
        """
        if not self.parts:
            return ""
        small = [p for p in self.parts
                 if self.ms > 0 and p.ms / self.ms < 0.005]
        if len(small) == 1:
            other = [p for p in self.parts if p is not small[0]][0]
            return (f"{small[0].name.capitalize()} is negligible here, so "
                    f"this station is {other.name} almost entirely.")
        longer = self.longer_part
        if longer is None:
            return (f"{OVERLAP_NOTE} Neither is longer here - they are "
                    f"the same to the precision shown.")
        return f"{OVERLAP_NOTE} {longer.name.capitalize()} is the longer here."


@dataclass(frozen=True)
class SharedMemory:
    """The bus both agents pull on. NOT a station.

    Memory has no execution stage in this model and drawing one would put
    a box on screen for something the engine does not time. But leaving it
    off entirely left a reader asking why a memory analysis appears beside
    a flow containing only a host and an accelerator - which is the
    question the 302-case review produced first.

    So it is drawn as a SHARED RESOURCE the stations draw on, with no
    position in the execution order and no latency of its own.
    """
    host_traffic_mb: float
    accel_traffic_mb: float
    effective_bandwidth: float
    technology: str
    units: int


@dataclass(frozen=True)
class FlowData:
    app_name: str
    total_ms: float
    stations: Tuple[Station, ...]
    dominant_component: str
    dominant_share_pct: float
    analytical_limit: str
    analytical_limit_plain: str = ""
    residual_pct: float = 0.0
    # The THROUGHPUT limit, referenced rather than computed here.
    #
    # A flow that says nothing about the rate lets a reader take the
    # dominant station as the system's limit. It often is not: the ISP
    # sets the pipeline rate at 99.73 inf/s and has no box in this
    # picture at all.
    throughput_limit_block: str = ""
    throughput_limit_inf_s: float = 0.0
    throughput_limit_in_flow: bool = True
    # Last, with a default: a shared resource is not required for a flow
    # to be valid, and putting it before the required fields broke the
    # dataclass ordering.
    shared_memory: Optional[SharedMemory] = None

    def consistent(self) -> List[str]:
        """What must hold before this is drawn.

        Returned rather than raised: a caller that wants to render an
        inconsistent flow at least knows it is doing so, and a check can
        read the list.
        """
        problems = []
        total = sum(s.share_pct for s in self.stations)
        if abs(total - 100.0) > 0.05 and abs(self.residual_pct) < 1e-9:
            problems.append(
                f"shares total {total:.2f}% with no residual recorded")
        seen = [s.name for s in self.stations]
        expected = [n for n in STATION_ORDER if n in seen]
        if seen != expected:
            problems.append(
                f"stations are not in execution order: {seen}")
        for s in self.stations:
            if s.parts and len(s.parts) != 2:
                problems.append(f"{s.name}: overlap needs exactly two parts")
            if s.parts and s.name not in OVERLAP_PARTS:
                problems.append(
                    f"{s.name}: has parts and is not an overlap station")
        return problems


def build_flow(analysis) -> FlowData:
    """Build the flow from a finished ReviewAnalysis.

    Computes nothing from the engine. Every figure is already in the
    analysis; this reorders and labels them, which is what lets a check
    require that no renderer calls the engine.
    """
    from ..application import APPLICATION_LIBRARY

    metrics = analysis.current_result.metrics
    total = float(metrics.get("Latency (ms)", 0.0))
    by_name = {name: (ms, pct)
               for name, ms, pct in analysis.latency_composition}

    dominant = analysis.limiting.dominant_component

    stations: List[Station] = []
    for name in STATION_ORDER:
        if name not in by_name:
            continue
        ms, pct = by_name[name]
        # A station with no time is omitted rather than drawn empty. A box
        # holding 0.0% invites the reader to wonder what it is waiting for.
        if ms <= 0.0 and pct <= 0.0:
            continue
        parts: Tuple[OverlapPart, ...] = ()
        if name in OVERLAP_PARTS:
            got = []
            for label, key in OVERLAP_PARTS[name]:
                value = metrics.get(key)
                if value is None:
                    got = []
                    break
                got.append(OverlapPart(label, float(value)))
            parts = tuple(got)
        stations.append(Station(name, ms, pct, name == dominant, parts))

    accounted = sum(s.share_pct for s in stations)
    residual = 0.0 if abs(accounted - 100.0) <= 0.05 else 100.0 - accounted

    # Read from the engine's own throughput stations. Not derived from
    # the flow's station times: those are a different decomposition and
    # deriving a rate from them gave 343.67 inf/s where the engine says
    # 99.73, agreeing only when the ISP happened to be idle.
    throughput_stations = metrics.get("Throughput stations (s)", {})
    limit_block, limit_rate, limit_in_flow = "", 0.0, True
    active = {k: v for k, v in throughput_stations.items() if v > 0}
    if active:
        limit_block = max(active, key=lambda k: active[k])
        limit_rate = 1000.0 / (active[limit_block] * 1e3)
        # Whether the block that sets the rate is even drawn here. The
        # honest answer is often no.
        drawn = " ".join(s.name for s in stations).lower()
        limit_in_flow = limit_block.lower() in drawn

    cfg = analysis.current_config
    shared = SharedMemory(
        host_traffic_mb=metrics.get("Host DRAM traffic (MB)", 0.0),
        accel_traffic_mb=metrics.get("DRAM traffic (MB)", 0.0),
        effective_bandwidth=metrics.get("Effective bandwidth (GB/s)", 0.0),
        technology=getattr(cfg, "memory", ""),
        units=getattr(cfg, "memory_devices", 0))

    return FlowData(
        app_name=analysis.app_name,
        total_ms=total,
        stations=tuple(stations),
        shared_memory=shared,
        dominant_component=dominant,
        dominant_share_pct=analysis.limiting.dominant_share_pct,
        analytical_limit=analysis.limiting.analytical_limit,
        analytical_limit_plain=analysis.limiting.analytical_limit_plain,
        residual_pct=residual,
        throughput_limit_block=limit_block,
        throughput_limit_inf_s=limit_rate,
        throughput_limit_in_flow=limit_in_flow)


BAR_WIDTH = 22
FILL = "#"


def render_flow_text(data: FlowData, width: int = BAR_WIDTH,
                     show_limits: bool = True) -> List[str]:
    """Vertical. A horizontal chain passes 78 columns at four stations."""
    from .text import wrap_text

    out: List[str] = []
    out.append(f"one job: {data.total_ms:.3f} ms")
    out.append("")

    for i, s in enumerate(data.stations):
        filled = max(1, int(round(width * s.share_pct / 100.0))) \
            if s.share_pct > 0 else 0
        bar = FILL * filled
        # The marker goes BEFORE the bar, not after it.
        #
        # Trailing it pushed the line to 81 characters whenever a station
        # held most of the job - which is exactly when the marker appears.
        # The 78-column rule caught it, and shortening the bar instead
        # would have made the longest bar the shortest-looking.
        mark = "> " if s.is_dominant else "  "
        out.append(f"{mark}{s.name:<24s}{s.ms:>8.3f} ms{s.share_pct:>7.1f}%"
                   f"  {bar}")
        for part in s.parts:
            out.append(f"      {part.name:<20s}{part.ms:>8.3f} ms")
        if s.is_dominant:
            out.append(f"      dominant station")
        if s.parts:
            for line in wrap_text(s.overlap_sentence(), 62):
                out.append(f"      {line}")
        if i < len(data.stations) - 1:
            # Under the station name, not right-aligned in a wide field:
            # the arrow marks the path between two boxes and belongs
            # beneath the first of them.
            out.append("    |")
            out.append("    v")

    if abs(data.residual_pct) > 1e-9:
        out.append("")
        out.append(f"  {'unaccounted':<24s}{'':>8s}   "
                   f"{data.residual_pct:>7.1f}%")
        out.append("  Printed rather than absorbed: a flow that quietly "
                   "closed a gap")
        out.append("  would look complete.")

    sm = data.shared_memory
    if sm is not None:
        # A RAIL, not a box.
        #
        # Drawn with a heavy border, a full-caps heading and four lines of
        # explanation, it read louder than the stations - and memory is
        # not the subject of this picture. The reading order has to be
        # dominant station, then flow, then the shared relationship, and
        # the earlier form put memory close to first.
        #
        # The verdict text moved to the memory analysis, where the verdict
        # belongs. One line stays here to say what kind of thing this is.
        # ONE rail, not a bounded block. Dotted rules above and below
        # closed it into a box again, which is the shape a station has.
        # A resource that everything touches is drawn as a line, not as a
        # container.
        title = f" Shared memory resource · {sm.technology} x{sm.units} "
        pad = max(0, 62 - len(title))
        out.append("")
        out.append("  " + "." * (pad // 2) + title
                   + "." * (pad - pad // 2))
        out.append(f"   Host {sm.host_traffic_mb:.2f} MB/job · "
                   f"Accelerator {sm.accel_traffic_mb:.2f} MB/job · "
                   f"{sm.effective_bandwidth:.2f} GB/s")
        out.append("   Shared resource; not an execution stage.")

    if data.throughput_limit_block:
        out.append("")
        out.append(f"  Latency dominant block        "
                   f"{data.dominant_component}, "
                   f"{data.dominant_share_pct:.1f}%")
        out.append(f"  Throughput limiting block     "
                   f"{data.throughput_limit_block}, "
                   f"{data.throughput_limit_inf_s:.1f} inf/s")
        if not data.throughput_limit_in_flow:
            # The block setting the rate has no box above. Saying so is
            # the point: a reader looking for it will not find it, and
            # would otherwise assume the largest box is the limit.
            out.append(f"     {data.throughput_limit_block} does not "
                       f"appear in this flow. Throughput and")
            out.append(f"     latency are decomposed differently; see "
                       f"BLOCK THROUGHPUT.")
        elif data.throughput_limit_block.lower() \
                not in data.dominant_component.lower():
            out.append("     These are different blocks. The one holding "
                       "the time is not")
            out.append("     the one setting the rate.")

    if not show_limits:
        return out

    out.append("")
    out.append(f"  {'Dominant latency component':<30s}"
               f"{data.dominant_component}, "
               f"{data.dominant_share_pct:.1f}%")
    out.append(f"  {'Analytical limiting factor':<30s}"
               f"{data.analytical_limit}")
    if data.analytical_limit not in data.dominant_component:
        for line in wrap_text(
                "These are different quantities and they differ here. The "
                "station holding the time is not the one imposing the "
                "limit.", 66):
            out.append(f"  {line}")
    return out


def render_flow_png(data: FlowData, path: str = "latency_flow.png"
                    ) -> Optional[str]:
    """A FLOW DIAGRAM: boxes, straight connectors, arrowheads.

    The first version drew horizontal bars. Bars answer "how much" and say
    nothing about order, and the text version had the connectors while the
    image - the thing that ends up in a slide - did not. What was promised
    was a flow.

    Optional. Its absence is not a failure: the text flow is the contract,
    the same rule Measured Results follows.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch, FancyArrow
    except ImportError:
        return None
    if not data.stations:
        return None

    from .text import wrap_text

    DOM_EDGE, DOM_FILL = "#9C2B2B", "#F3E3E3"
    EDGE, FILL = "#2E7A80", "#E4F0F0"
    LINK = "#3A5265"

    n = len(data.stations)
    box_h, gap = 0.95, 1.05
    step = box_h + gap
    # A CONSTANT canvas height.
    #
    # Sizing the figure to the station count made a two-station diagram
    # render at twice the scale of a four-station one, so a contact sheet
    # of a hundred cases showed some boxes large and some small with
    # nothing meaning it. The drawing area is fixed and the stations are
    # centred in it.
    # Height follows the CONTENT, with the drawing area anchored at the
    # top so boxes render at the same scale whatever the station count.
    # A constant height left half a page blank on a two-station flow.
    MAX_STATIONS = 5
    fig_h = n * step + 5.6
    fig, ax = plt.subplots(figsize=(9.0, fig_h))
    ax.axis("off")
    ax.set_xlim(0, 10)
    # Room below the last station for the shared-memory band.
    band_bottom = MAX_STATIONS * step - (n - 1) * step - box_h - 1.9
    ax.set_ylim(0, MAX_STATIONS * step + 1.2)

    x0, x1 = 1.0, 7.6
    mid = (x0 + x1) / 2
    # Centred, so a short flow sits in the middle rather than being
    # stretched to fill the page.
    # Stations start at the top. Centring them left a large blank band
    # above every short flow, and the shared-memory band ended up far
    # below the boxes it belongs to.
    top = MAX_STATIONS * step

    for i, st in enumerate(data.stations):
        y = top - i * step - box_h
        dom = st.is_dominant
        ax.add_patch(FancyBboxPatch(
            (x0, y), x1 - x0, box_h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=2.2 if dom else 1.4,
            edgecolor=DOM_EDGE if dom else EDGE,
            facecolor=DOM_FILL if dom else FILL))
        ax.text(mid, y + box_h * 0.66, st.name, ha="center", va="center",
                fontsize=12, fontweight="bold", color="#1B2B36")
        ax.text(mid, y + box_h * 0.30,
                f"{st.ms:.3f} ms   ·   {st.share_pct:.1f}%",
                ha="center", va="center", fontsize=10.5, color="#333333")
        if dom:
            ax.text(x1 + 0.2, y + box_h * 0.5, "DOMINANT", ha="left",
                    va="center", fontsize=9.5, fontweight="bold",
                    color=DOM_EDGE)
        if st.parts:
            # BELOW the box, inside the drawing. Placed to the right it ran
            # off the canvas, and the part that vanished was the second
            # figure - the one that makes the pair mean anything.
            note = "   ".join(f"{p.name} {p.ms:.3f} ms" for p in st.parts)
            ax.text(mid, y - 0.14, note, ha="center", va="top",
                    fontsize=9, color="#555555")

        # A straight connector and a real arrowhead between boxes. The
        # order is the thing this picture exists to carry.
        if i < n - 1:
            y_bot = y
            ax.add_patch(FancyArrow(
                mid, y_bot - 0.08, 0, -(gap - 0.30),
                width=0.012, head_width=0.16, head_length=0.20,
                length_includes_head=True, color=LINK))

    # THE SHARED RESOURCE.
    #
    # Drawn as a band the stations feed, not as a box in the chain: memory
    # has no execution stage here and giving it one would put a timed box
    # on screen for something the engine never times. Without it a reader
    # asked why a memory analysis sits beside a flow of host and
    # accelerator only - the first question the 302-case review produced.
    sm = data.shared_memory
    if sm is not None:
        # Directly beneath the last station, not at the page foot: a
        # shared resource sitting a screen away from what draws on it
        # reads as a separate topic.
        last_y = top - (n - 1) * step - box_h
        band_y = last_y - 1.35
        # Two hairlines and text between them. No fill, no rounded box,
        # nothing that could be mistaken for a station.
        for dy in (0.42, 0.0):
            ax.plot([x0 - 0.4, x1 + 0.4], [band_y + dy, band_y + dy],
                    linestyle=(0, (1, 3)), linewidth=0.8,
                    color="#9AA7B2", zorder=0)
        ax.text(mid, band_y + 0.30,
                f"Shared memory resource · {sm.technology} ×{sm.units}",
                ha="center", va="center", fontsize=8.5, color="#6B7A88")
        ax.text(mid, band_y + 0.13,
                f"Host {sm.host_traffic_mb:.2f} MB/job · "
                f"Accelerator {sm.accel_traffic_mb:.2f} MB/job · "
                f"{sm.effective_bandwidth:.2f} GB/s",
                ha="center", va="center", fontsize=7.5, color="#8A99A6")
        # Dotted feeds from every station to the band: a shared resource
        # is drawn on by all of them, not passed through by one.
        for i, st in enumerate(data.stations):
            y = top - i * step - box_h
            ax.plot([x1 + 0.05, x1 + 0.05],
                    [y + box_h * 0.5, band_y + 0.42],
                    linestyle=(0, (1, 4)), linewidth=0.6,
                    color="#B4BEC7", zorder=0)
        ax.text(mid, band_y - 0.13,
                "Shared resource; not an execution stage.",
                ha="center", va="top", fontsize=7, color="#9AA7B2")

    fig.suptitle("SYSTEM FLOW AND LATENCY COMPOSITION", fontsize=14,
                 fontweight="bold", y=0.985)
    # Title, subtitle and total on SEPARATE rows. Printed together they
    # overlapped, and the line that vanished was the total the shares are
    # shares OF.
    fig.text(0.5, 0.955, f"One job: {data.total_ms:.3f} ms",
             ha="center", va="top", fontsize=11, color="#333333")
    fig.text(0.5, 0.932, "Execution order: top to bottom",
             ha="center", va="top", fontsize=10, color="#555555")

    foot = [f"Latency dominant block:  {data.dominant_component}, "
            f"{data.dominant_share_pct:.1f}%"]
    if data.throughput_limit_block:
        line = (f"Throughput limiting block:  "
                f"{data.throughput_limit_block}, "
                f"{data.throughput_limit_inf_s:.1f} inf/s")
        if not data.throughput_limit_in_flow:
            line += "   (not drawn above - see BLOCK THROUGHPUT)"
        foot.append(line)
    foot += [
        f"Analytical limiting factor:  {data.analytical_limit}",
        # ROOT CAUSE is not asserted. Naming one would need a
        # counterfactual - halve a station and watch the total - and
        # the model has not been asked that question here.
        "Root cause:  NOT ESTABLISHED  (requires counterfactual "
        "verification)"]
    base = 0.175
    dy = 0.026
    for k, line in enumerate(foot):
        fig.text(0.06, base - k * dy, line, ha="left", va="top",
                 fontsize=9.5, color="#333333")

    overlaps = [st for st in data.stations if st.parts]
    if overlaps:
        note = ("Figures inside a station overlap: they run at the same "
                "time and do not sum to the station.")
        for k, line in enumerate(wrap_text(note, 88)):
            fig.text(0.06, base - (len(foot) + 0.3 + k) * dy, line,
                     ha="left", va="top", fontsize=8.5, color="#666666")

    # The footer grew by a line when the throughput limit was added, and
    # the last caveat was cut off the page.
    fig.subplots_adjust(top=0.88, bottom=0.32, left=0.02, right=0.98)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ==============================================================================
# Block capacity - PB-D2
# ==============================================================================
#
# A block does not have a throughput. It has a CAPACITY: the rate it alone
# could sustain. Throughput is what the system delivers, and giving a block
# that word invites a reader to compare two blocks and conclude something
# about the product, which is backwards.
#
# The derivation is a rate back-computed from a time, which is the same
# shape as `host_demand` - the quantity that turned out to be a balance
# point rather than a demand. It is admitted here for one reason: it is
# CHECKABLE. The slowest block's derived capacity equals the engine's
# independently computed pipeline capacity, exactly. host_demand had no
# such check, and its circularity surfaced only when someone capped a
# bandwidth with it.
#
# It is still labelled derived, never measured.

@dataclass(frozen=True)
class BlockThroughput:
    """What one block can process per second.

    Called throughput, not capacity. Work over time is one idea whatever
    the block does - instructions, inferences, images, transactions - and
    two words for it invited the reading that a block's "capacity" was a
    different kind of quantity from the system's "throughput". It is the
    same kind; what differs is the scope.

    The SYSTEM's throughput is the LOWEST of these, not the sum and not
    the highest.
    """
    name: str
    station_ms: float
    throughput_inf_s: float     # 1000 / station_ms
    busy_pct: float             # station_ms * delivered_rate / 1000
    is_system_limit: bool       # the lowest throughput sets the system

    # Not computed, and not omitted. An absent row reads as a quantity
    # that does not apply; these apply and are unavailable.
    idle_pct: None = None
    waiting_pct: None = None


@dataclass(frozen=True)
class ThroughputView:
    blocks: Tuple[BlockThroughput, ...]
    delivered_inf_s: float
    system_throughput_inf_s: float
    limiting_block: str
    memory_utilisation_pct: Optional[float] = None
    derivation_checked: bool = False


def build_throughput_view(analysis, flow=None, memory=None
                          ) -> ThroughputView:
    """Per-block throughput and busy, from the ENGINE'S THROUGHPUT STATIONS.

    Not from the latency flow. The two decompositions answer different
    questions and do not share a station list: the ISP sets the pipeline
    rate and has no box in the flow at all. Deriving a capacity from a
    flow station gave 343.67 inf/s where the engine says 99.73, and it
    agreed only when the ISP happened to be idle.

    `flow` is accepted and unused, so callers that pass it keep working.

    `idle` and `waiting` are deliberately absent: their sum is 1 - busy
    and the split needs the REASON a block is not working, which the model
    does not carry.
    """
    metrics = analysis.current_result.metrics
    delivered = float(metrics.get("Delivered throughput (inf/s)", 0.0))
    pipeline = float(metrics.get("Pipeline capacity (inf/s)", 0.0))
    stations = metrics.get("Throughput stations (s)", {})

    blocks = []
    for name, seconds in stations.items():
        ms = seconds * 1e3
        # A station at zero is omitted: an ISP that is not configured is
        # not a block with infinite capacity.
        if ms <= 0:
            continue
        tput = 1000.0 / ms
        busy = ms * delivered / 1000.0 * 100.0
        blocks.append(BlockThroughput(name, ms, tput, busy, False))

    if blocks:
        # The LOWEST throughput sets the system. Not the highest, and
        # never the sum: blocks in series do not add.
        slowest = min(blocks, key=lambda b: b.throughput_inf_s)
        blocks = tuple(
            BlockThroughput(b.name, b.station_ms, b.throughput_inf_s,
                            b.busy_pct, b is slowest)
            for b in blocks)
        limiting = slowest.name
        # The check that makes this derivation admissible at all.
        checked = abs(slowest.throughput_inf_s - pipeline) < 0.5
    else:
        blocks, limiting, checked = tuple(), "", False

    util = None
    if memory is not None and memory.computable \
            and memory.effective_bandwidth > 0:
        util = (memory.concurrent_requirement
                / memory.effective_bandwidth * 100.0)

    return ThroughputView(blocks, delivered, pipeline, limiting, util,
                          checked)


def render_throughput_view(view: ThroughputView,
                           show_title: bool = True) -> List[str]:
    from .text import wrap_text

    # Suppressible: the chained System Flow task prints its own numbered
    # heading, and the two appeared one after the other.
    out = ["BLOCK THROUGHPUT", ""] if show_title else []
    # Said before the table, not after it. A reader who has just seen the
    # latency flow will otherwise look for the same station names and find
    # different ones - and conclude the tool contradicts itself.
    for line in wrap_text(
            "These are the THROUGHPUT stations, which are not the latency "
            "flow's stations. The two decompositions answer different "
            "questions: the flow shows where one job's time goes, this "
            "shows what rate each block could sustain. A block can set "
            "the system rate and have no box in the flow - the ISP does.",
            66):
        out.append(f"  {line}")
    out.append("")
    out.append(f"  {'block':<24s}{'throughput':>12s}{'busy':>9s}"
               f"{'idle':>9s}{'waiting':>10s}")
    out.append(f"  {'':<24s}{'inf/s':>12s}{'%':>9s}{'%':>9s}{'%':>10s}")
    out.append("  " + "-" * 64)
    for b in view.blocks:
        # The marker goes BEFORE the row, not after it: trailing it pushed
        # the line to 82 columns, and it appears on the widest row by
        # definition - the one that sets the limit.
        mark = "> " if b.is_system_limit else "  "
        out.append(f"{mark}{b.name:<24s}{b.throughput_inf_s:>12.1f}"
                   f"{b.busy_pct:>9.1f}{'n/e':>9s}{'n/e':>10s}")
        if b.is_system_limit:
            out.append(f"      lowest throughput - sets the system")
    out.append("")
    out.append(f"  System delivered throughput   "
               f"{view.delivered_inf_s:8.1f} inf/s")
    out.append(f"  System throughput             "
               f"{view.system_throughput_inf_s:8.1f} inf/s"
               f"   (set by {view.limiting_block})")
    if view.memory_utilisation_pct is not None:
        out.append(f"  Shared memory utilisation     "
                   f"{view.memory_utilisation_pct:8.1f} %"
                   f"   at the application target")
    out.append("")
    for line in wrap_text(
            "Block throughput is derived from the engine's own station "
            "times - the rate a block alone could sustain - not measured. "
            "The system's throughput is the LOWEST of them, never the sum: "
            "blocks in series do not add.", 66):
        out.append(f"  {line}")
    out.append("")
    out.append("  n/e = NOT ESTABLISHED")
    for line in wrap_text(
            "Idle and waiting sum to what is left of busy, and the split "
            "between them needs the reason a block is not working. The "
            "model carries no dependency state, so neither is reported "
            "rather than one being guessed.", 66):
        out.append(f"  {line}")
    if not view.derivation_checked:
        out.append("")
        out.append("  DERIVATION UNCHECKED: the lowest block throughput "
                   "does not")
        out.append("  match the engine's pipeline capacity.")
    return out
