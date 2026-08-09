"""
ppact.economics - the cost that does not depend on how many you build

A wafer price is a cost per unit. A mask set is not, and neither is the six
months of physical implementation, the timing closure, the power and signal
integrity work, the memory compilers, the analogue and PHY blocks that have to
be re-qualified, the EDA licences, the test program, the prototype wafers, or
the re-spin that is always possible. Those are paid once, before the first
unit ships, and they rise steeply with the node.

The rest of the model computes RECURRING cost - what each unit costs to make.
That is the right answer to "what does this part cost" and the wrong answer to
"what node should this product use", because at low volume the development
cost of a leading-edge node can exceed everything else combined.

    effective unit cost = recurring manufacturing + development / volume

The consequence is the result this module exists to show: the economic node
depends on how many you build, and a design that is cheaper to manufacture on
a finer node can be more expensive to SHIP on it.

EVERY FIGURE HERE IS AN ESTIMATE
--------------------------------
Mask set prices are quoted in public and vary by a factor of two between
sources; design and verification effort depends on a team; re-spin probability
is a judgement. The SHAPE - development cost rising steeply with the node,
amortising away with volume - is not in doubt. The numbers are.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

LINE = "=" * 80

# How much of a full new design is being done. A team porting a proven design
# to a new node does far less than one starting from nothing.
DESIGN_REUSE = {
    "new design": 1.00,
    "partial reuse": 0.55,
    "full reuse": 0.30,
}

# How far the node moved. A port across several generations means new memory
# compilers, new analogue, new PHY, and a physical implementation that cannot
# be carried over.
MIGRATION_DISTANCE = {
    "same node": 0.15,
    "one generation": 0.60,
    "several generations": 1.00,
}

# Probability-weighted cost of needing another mask set and another cycle.
RESPIN_RISK = {"low": 0.10, "medium": 0.25, "high": 0.45}

# Analogue, PHY and mixed-signal blocks do not port. This is how much of that
# work the design needs.
IP_PORTING = {"none": 0.0, "partial": 0.5, "extensive": 1.0}

# Base effort at the reference node, in dollars, before the node multiplier.
# Each is a line a real programme carries and none of them is a wafer cost.
BASE_EFFORT_USD = {
    "physical implementation": 3.0e6,
    "verification and DFT": 2.2e6,
    "EDA licences and compute": 1.4e6,
    "IP licensing and porting": 2.6e6,
    "prototype and qualification": 1.1e6,
}


@dataclass
class Economics:
    node: str
    volume: int
    recurring_unit: float
    die_unit: float
    mask_usd: float
    effort: Dict[str, float]
    respin_usd: float
    total_nre: float
    nre_per_unit: float
    effective_unit: float


def development_cost(node: str, reuse: str = "new design",
                     migration: str = "one generation",
                     respin: str = "medium",
                     ip_porting: str = "partial") -> Tuple[float, Dict[str, float], float]:
    """One-time cost of taking a design to a node.

    Returns the mask cost, the effort lines, and the probability-weighted
    re-spin allowance. The node multiplier is the mask factor, which rises
    faster than linearly with the generation and is the closest thing the
    process library has to a complexity index.
    """
    from .process import get_node
    nd = get_node(node)
    # Effort does NOT scale with mask cost. A mask set at 28 nm is 4% of one
    # at 3 nm; the physical implementation is not 4% of the work. Timing
    # closure, verification and a test program are needed at every node, and
    # what the finer node adds is difficulty rather than existence - so effort
    # carries a floor and scales gently above it.
    effort_factor = 0.30 + 0.70 * max(nd.mask_factor, 0.02)
    scale = DESIGN_REUSE[reuse] * MIGRATION_DISTANCE[migration] * effort_factor
    effort = {}
    for name, base in BASE_EFFORT_USD.items():
        weight = IP_PORTING[ip_porting] if "IP" in name else 1.0
        effort[name] = base * scale * weight
    # A re-spin costs another mask set and another pass of physical work.
    respin_usd = RESPIN_RISK[respin] * (nd.mask_set_usd
                                        + effort["physical implementation"])
    return nd.mask_set_usd, effort, respin_usd


def economics(app_key: str, config, node: Optional[str] = None,
              volume: Optional[int] = None, reuse: str = "new design",
              migration: str = "one generation", respin: str = "medium",
              ip_porting: str = "partial") -> Economics:
    """Recurring cost, development cost, and what a unit actually costs."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    node = node or config.accel_node or app.default_accel_node
    cfg = dataclasses.replace(config, accel_node=node, soc_node=node)
    m = evaluate_system(app, cfg).metrics
    vol = int(volume or app.production_volume)

    mask, effort, respin_usd = development_cost(node, reuse, migration,
                                                respin, ip_porting)
    total = mask + sum(effort.values()) + respin_usd
    per_unit = total / max(vol, 1)
    return Economics(node=node, volume=vol,
                     recurring_unit=m["System cost (USD)"],
                     die_unit=m["Logic die cost (USD)"],
                     mask_usd=mask, effort=effort, respin_usd=respin_usd,
                     total_nre=total, nre_per_unit=per_unit,
                     effective_unit=m["System cost (USD)"] + per_unit)


def break_even(app_key: str, config, node_a: str, node_b: str, **kw) -> Optional[float]:
    """Volume at which node_b becomes the cheaper choice than node_a.

    None when it never does - which happens whenever the finer node is both
    dearer to make and dearer to develop, and is a perfectly ordinary result.
    """
    a = economics(app_key, config, node=node_a, **kw)
    b = economics(app_key, config, node=node_b, **kw)
    d_recurring = b.recurring_unit - a.recurring_unit
    d_nre = b.total_nre - a.total_nre
    if d_recurring >= 0:
        return None           # dearer per unit AND dearer to develop
    v = d_nre / (-d_recurring)
    return v if v > 0 else 0.0


def print_economics(app_key: str, config, volume: Optional[int] = None,
                    reuse: str = "new design",
                    migration: str = "one generation",
                    respin: str = "medium",
                    ip_porting: str = "partial") -> None:
    """Every node, with development cost amortised over a stated volume."""
    from .application import APPLICATION_LIBRARY
    from .process import NODE_LIBRARY, get_node

    app = APPLICATION_LIBRARY[app_key]
    vol = int(volume or app.production_volume)
    rows = [economics(app_key, config, node=n, volume=vol, reuse=reuse,
                      migration=migration, respin=respin,
                      ip_porting=ip_porting)
            for n in NODE_LIBRARY]

    print(f"\n{LINE}")
    print(f" PROCESS NODE ECONOMICS - {app.name}")
    print(LINE)
    print(f"  planned volume     {vol:,} units")
    print(f"  design reuse       {reuse}")
    print(f"  node migration     {migration}")
    print(f"  re-spin risk       {respin}")
    print(f"  IP porting         {ip_porting}\n")

    head = (f"  {'node':<20s}{'die $':>9s}{'system $':>10s}"
            f"{'NRE $M':>9s}{'NRE/unit':>10s}{'effective $':>12s}")
    print(head); print("  " + "-" * (len(head) - 2))
    cheap_recurring = min(rows, key=lambda r: r.recurring_unit)
    cheap_effective = min(rows, key=lambda r: r.effective_unit)
    for r in rows:
        nd = get_node(r.node)
        label = f"{r.node} {nd.display or nd.label}"[:19]
        mark = ""
        if r.node == cheap_effective.node:
            mark = "  <- lowest effective"
        elif r.node == cheap_recurring.node:
            mark = "  <- lowest recurring"
        print(f"  {label:<20s}{r.die_unit:>9.3f}{r.recurring_unit:>10.2f}"
              f"{r.total_nre / 1e6:>9.1f}{r.nre_per_unit:>10.2f}"
              f"{r.effective_unit:>12.2f}{mark}")

    print(f"\n  -- what the development cost is made of, at "
          f"{cheap_effective.node} --")
    e = cheap_effective
    print(f"     {'mask set and tape-out':<32s}{e.mask_usd / 1e6:>8.1f} M")
    for name, usd in e.effort.items():
        print(f"     {name:<32s}{usd / 1e6:>8.1f} M")
    print(f"     {'re-spin allowance':<32s}{e.respin_usd / 1e6:>8.1f} M")
    print(f"     {'total':<32s}{e.total_nre / 1e6:>8.1f} M")

    print(f"\n  -- reading it ---------------------------------------------")
    if cheap_recurring.node == cheap_effective.node:
        print(f"     At {vol:,} units the same node - {cheap_effective.node} - "
              f"is cheapest")
        print(f"     both to manufacture and to ship. Development is "
              f"{e.nre_per_unit / e.effective_unit * 100:.0f}% of the")
        print(f"     effective unit cost.")
    else:
        print(f"     The cheapest node to MANUFACTURE is "
              f"{cheap_recurring.node} at "
              f"{cheap_recurring.recurring_unit:,.2f} per unit.")
        print(f"     The cheapest node to SHIP at {vol:,} units is "
              f"{cheap_effective.node} at")
        print(f"     {cheap_effective.effective_unit:,.2f}, because "
              f"development is "
              f"{cheap_recurring.nre_per_unit:,.2f} per unit on the")
        print(f"     first and {cheap_effective.nre_per_unit:,.2f} on the "
              f"second. At a different volume")
        print(f"     the answer changes, which is the point.")

    print(f"\n  -- what silicon this amortises ----------------------------")
    print(f"     The accelerator and the host cluster, not a whole "
          f"application")
    print(f"     processor. These dies are tens of square millimetres where a "
          f"phone")
    print(f"     SoC is a hundred or more, so a node change moves fewer "
          f"dollars")
    print(f"     here than it would across a full chip and the break-even "
          f"volumes")
    print(f"     are correspondingly higher. Read them as belonging to an AI "
          f"block.")
    print(f"\n  -- and cost is not usually why a part moves node ----------")
    print(f"     A migration that never repays on cost can still be the right")
    print(f"     decision. Between adjacent nodes the die often costs MORE - "
          f"SRAM")
    print(f"     shrinks at half the rate of logic while the wafer price "
          f"doubles -")
    print(f"     and the reason to move is power and speed. A phone is "
          f"thermally")
    print(f"     limited, not die-cost limited, which is why leading nodes "
          f"ship in")
    print(f"     volumes far below any cost break-even.")

    print(f"\n  Every figure here is ESTIMATED. Mask prices vary by a factor "
          f"of two")
    print(f"  between public sources, design effort depends on a team, and a "
          f"re-spin")
    print(f"  probability is a judgement. The SHAPE - development rising "
          f"steeply")
    print(f"  with the node and amortising away with volume - is not in "
          f"doubt. The")
    print(f"  numbers are.")
    print(LINE)


def print_break_even(app_key: str, config, node_a: str, node_b: str,
                     **kw) -> None:
    """How many units justify moving from one node to another."""
    from .application import APPLICATION_LIBRARY
    app = APPLICATION_LIBRARY[app_key]
    a = economics(app_key, config, node=node_a, **kw)
    b = economics(app_key, config, node=node_b, **kw)
    v = break_even(app_key, config, node_a, node_b, **kw)

    print(f"\n{LINE}")
    print(f" NODE MIGRATION BREAK-EVEN - {node_a} to {node_b}")
    print(LINE)
    print(f"  {'':<24s}{node_a:>14s}{node_b:>14s}")
    print(f"  {'recurring per unit':<24s}{a.recurring_unit:>14.2f}"
          f"{b.recurring_unit:>14.2f}")
    print(f"  {'development (M USD)':<24s}{a.total_nre / 1e6:>14.1f}"
          f"{b.total_nre / 1e6:>14.1f}")
    d_rec = b.recurring_unit - a.recurring_unit
    d_nre = b.total_nre - a.total_nre
    print(f"\n  moving to {node_b} changes the recurring cost by "
          f"{d_rec:+,.2f} per unit")
    print(f"  and the development cost by {d_nre / 1e6:+,.1f} M")
    if v is None:
        print(f"\n  There is no break-even. {node_b} costs MORE per unit as "
              f"well as more")
        print(f"  to develop, so no volume repays it on cost alone.")
        print(f"\n  That is an ordinary result and not a reason to stay. "
              f"Between")
        print(f"  adjacent nodes an SRAM-heavy die often gets DEARER - memory "
              f"cells")
        print(f"  shrink at about half the rate of logic while the wafer price")
        print(f"  climbs - and parts move anyway, for power and speed. Compare "
              f"the")
        print(f"  power and energy columns in the node sweep before concluding "
              f"the")
        print(f"  move is wrong.")
    else:
        print(f"\n  break-even at {v:,.0f} units")
        planned = app.production_volume
        if planned >= v:
            print(f"  The planned volume of {planned:,} is above it, so the "
                  f"move repays")
            print(f"  itself on cost alone.")
        else:
            print(f"  The planned volume of {planned:,} is BELOW it. On cost "
                  f"alone the")
            print(f"  move does not repay itself - it would need "
                  f"{v / max(planned, 1):.1f} times the volume.")
    print(LINE)


# ==============================================================================
# Why a part actually moves node
# ==============================================================================
#
# Not to save money. A leading node costs more to develop and, between adjacent
# generations, often more to manufacture as well - SRAM shrinks at about half
# the rate of logic while the wafer price climbs. Parts move for speed and for
# power, and they move because a competitor will.
#
# So the decision is reported in that order: what performance buys, what power
# buys, and what it costs. Leading with cost invites the conclusion that the
# move is irrational, which is not what the industry does or why.

def node_decision(app_key: str, config, from_node: str, to_node: str,
                  volume: Optional[int] = None, **kw) -> None:
    """The three reasons in the order they actually decide things."""
    from .application import APPLICATION_LIBRARY
    from .process import get_node
    from .system import evaluate_system
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    vol = int(volume or app.production_volume)
    a = evaluate_system(app, dataclasses.replace(
        config, accel_node=from_node, soc_node=from_node))
    b = evaluate_system(app, dataclasses.replace(
        config, accel_node=to_node, soc_node=to_node))
    ma, mb = a.metrics, b.metrics
    ea = economics(app_key, config, node=from_node, volume=vol, **kw)
    eb = economics(app_key, config, node=to_node, volume=vol, **kw)

    def pct(key):
        return (mb[key] / ma[key] - 1) * 100 if ma[key] else 0.0

    nd_a, nd_b = get_node(from_node), get_node(to_node)
    print(f"\n{LINE}")
    print(f" NODE DECISION - {app.name}")
    print(f" {from_node} {nd_a.display or nd_a.label}  ->  "
          f"{to_node} {nd_b.display or nd_b.label}")
    print(LINE)

    # --- 1. speed --------------------------------------------------------
    print(f"  1. PERFORMANCE - usually the first reason")
    print(f"     {'peak arithmetic':<26s}{ma['Peak TOPS']:>10.2f}"
          f"{mb['Peak TOPS']:>10.2f}{pct('Peak TOPS'):>+9.1f}%")
    print(f"     {'compute time (ms)':<26s}{ma['Compute time (ms)']:>10.3f}"
          f"{mb['Compute time (ms)']:>10.3f}{pct('Compute time (ms)'):>+9.1f}%")
    print(f"     {'latency (ms)':<26s}{ma['Latency (ms)']:>10.3f}"
          f"{mb['Latency (ms)']:>10.3f}{pct('Latency (ms)'):>+9.1f}%")
    if abs(pct("Latency (ms)")) < 1.0:
        print(f"     The arithmetic got faster and the LATENCY did not. This "
              f"design is")
        print(f"     {a.bound_by} bound, so a finer node buys almost nothing "
              f"here - the")
        print(f"     first thing to check before paying for one.")

    # --- 2. power --------------------------------------------------------
    print(f"\n  2. POWER - usually the second, and often the binding one")
    print(f"     {'system power (W)':<26s}{ma['System power (W)']:>10.2f}"
          f"{mb['System power (W)']:>10.2f}{pct('System power (W)'):>+9.1f}%")
    print(f"     {'energy per inference (mJ)':<26s}"
          f"{ma['Energy per inference (mJ)']:>10.2f}"
          f"{mb['Energy per inference (mJ)']:>10.2f}"
          f"{pct('Energy per inference (mJ)'):>+9.1f}%")
    print(f"     {'thermal headroom (%)':<26s}{ma['Thermal margin (%)']:>10.1f}"
          f"{mb['Thermal margin (%)']:>10.1f}")
    if app.cooling == "passive":
        print(f"     This product is passively cooled, so power is a hard "
              f"limit rather")
        print(f"     than a running cost. That is what usually decides the "
              f"node.")

    # --- 3. cost, which is the price paid --------------------------------
    print(f"\n  3. COST - what the first two are paid for")
    print(f"     {'logic die (USD)':<26s}"
          f"{ma['Logic die cost (USD)']:>10.3f}"
          f"{mb['Logic die cost (USD)']:>10.3f}"
          f"{pct('Logic die cost (USD)'):>+9.1f}%")
    print(f"     {'system (USD)':<26s}{ma['System cost (USD)']:>10.2f}"
          f"{mb['System cost (USD)']:>10.2f}{pct('System cost (USD)'):>+9.1f}%")
    print(f"     {'development (M USD)':<26s}{ea.total_nre / 1e6:>10.1f}"
          f"{eb.total_nre / 1e6:>10.1f}"
          f"{(eb.total_nre / ea.total_nre - 1) * 100:>+9.1f}%")
    print(f"     {'at ' + format(vol, ',') + ' units (USD)':<26s}"
          f"{ea.effective_unit:>10.2f}{eb.effective_unit:>10.2f}"
          f"{(eb.effective_unit / ea.effective_unit - 1) * 100:>+9.1f}%")

    # --- the verdict, which is not the cheapest option --------------------
    print(f"\n  -- reading the three together ------------------------------")
    faster = pct("Latency (ms)") < -1.0
    cooler = pct("System power (W)") < -1.0
    dearer = eb.effective_unit > ea.effective_unit
    if faster or cooler:
        gains = " and ".join(
            [x for x in (f"{-pct('Latency (ms)'):.0f}% faster" if faster else "",
                         f"{-pct('System power (W)'):.0f}% cooler" if cooler else "")
             if x])
        print(f"     {to_node} is {gains}, and costs "
              f"{(eb.effective_unit / ea.effective_unit - 1) * 100:+.0f}% more "
              f"per unit")
        print(f"     at this volume. Whether that is worth paying is a question "
              f"about")
        print(f"     the market, not about the silicon: a competitor shipping "
              f"the")
        print(f"     faster, cooler part sets the price the slower one can "
              f"command.")
        print(f"     This model can tell you the trade. It cannot tell you "
              f"whether")
        print(f"     your competitors will make it.")
    elif dearer:
        print(f"     {to_node} is neither faster nor cooler here, and costs "
              f"more. On")
        print(f"     this design there is no case for the move.")
    else:
        print(f"     {to_node} is cheaper without being faster or cooler, "
              f"which usually")
        print(f"     means the design was not limited by the node in the first "
              f"place.")
    print(LINE)


# ==============================================================================
# Node and memory together
# ==============================================================================
#
# A finer node makes the arithmetic faster and does nothing to the memory. The
# memory generation is a separate axis - a different supplier, a different
# interface, a different package - and improving one while the other binds buys
# nothing.
#
# So the node decision is incomplete on its own. The question a designer
# actually faces has four answers, and three of them are usually wrong.

def _bound_label(res) -> str:
    return res.bound_by


def node_and_memory(app_key: str, config, to_node: str,
                    to_memory: Optional[str] = None,
                    to_devices: Optional[int] = None,
                    volume: Optional[int] = None, **kw) -> None:
    """Node, memory, both, or neither - and what each is worth.

    The node improves compute. The memory improves transfers. Which one is
    worth paying for depends on which of them the design is waiting on, and
    that can change once the other is fixed.
    """
    from .application import APPLICATION_LIBRARY
    from .process import get_node
    from .memory import MEMORY_LIBRARY
    from .system import evaluate_system
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    vol = int(volume or app.production_volume)
    from_node = config.accel_node or app.default_accel_node
    to_memory = to_memory or config.memory
    to_devices = to_devices or config.memory_devices

    options = {
        "neither": dataclasses.replace(config, accel_node=from_node,
                                       soc_node=from_node),
        "node only": dataclasses.replace(config, accel_node=to_node,
                                         soc_node=to_node),
        "memory only": dataclasses.replace(config, accel_node=from_node,
                                           soc_node=from_node,
                                           memory=to_memory,
                                           memory_devices=to_devices),
        "both": dataclasses.replace(config, accel_node=to_node,
                                    soc_node=to_node, memory=to_memory,
                                    memory_devices=to_devices),
    }
    results = {k: evaluate_system(app, c) for k, c in options.items()}
    base = results["neither"]
    bm = base.metrics

    nd_f, nd_t = get_node(from_node), get_node(to_node)
    print(f"\n{LINE}")
    print(f" NODE AND MEMORY - {app.name}")
    print(LINE)
    print(f"  logic node     {from_node} {nd_f.display or nd_f.label}  ->  "
          f"{to_node} {nd_t.display or nd_t.label}")
    print(f"  memory         {config.memory} x{config.memory_devices}  ->  "
          f"{to_memory} x{to_devices}")
    print(f"\n  These are DIFFERENT AXES. A process node is where the logic is")
    print(f"  fabricated; a memory generation is a part bought from a memory")
    print(f"  supplier with its own interface and package. Neither implies the")
    print(f"  other, and a finer node does not make a DRAM faster.\n")

    head = (f"  {'change':<14s}{'bound by':<10s}{'latency':>9s}{'tok or inf/s':>13s}"
            f"{'power W':>9s}{'system $':>10s}   ships")
    print(head); print("  " + "-" * (len(head) - 2))
    for name in ("neither", "node only", "memory only", "both"):
        r = results[name]
        m = r.metrics
        print(f"  {name:<14s}{_bound_label(r):<10s}{m['Latency (ms)']:>9.3f}"
              f"{m['Throughput (inf/s)']:>13.1f}{m['System power (W)']:>9.2f}"
              f"{m['System cost (USD)']:>10.2f}   "
              f"{'yes' if r.passes else 'no'}")

    def gain(name, key="Latency (ms)"):
        return (1 - results[name].metrics[key] / bm[key]) * 100

    print(f"\n  -- what each is worth -------------------------------------")
    n_only, m_only, both = gain("node only"), gain("memory only"), gain("both")
    print(f"     node only     {n_only:>6.1f}% less latency")
    print(f"     memory only   {m_only:>6.1f}%")
    print(f"     both          {both:>6.1f}%")

    print(f"\n  -- reading it ---------------------------------------------")
    # A five-point threshold rather than two: a change worth less than a
    # twentieth of the other is not a close call, and calling 2.8% against
    # 31.2% "both help" would be reading a rounding as a trade-off.
    if base.bound_by == "memory" and n_only < max(2.0, m_only * 0.2):
        print(f"     The design is MEMORY bound, so the finer node buys "
              f"{n_only:.1f}% and")
        print(f"     the memory buys {m_only:.1f}%. Paying for the node "
              f"without the memory")
        print(f"     is paying for arithmetic that is already waiting.")
    elif base.bound_by == "compute" and m_only < max(2.0, n_only * 0.2):
        print(f"     The design is COMPUTE bound, so the memory buys "
              f"{m_only:.1f}% and the")
        print(f"     node buys {n_only:.1f}%. The memory is not what is "
              f"holding it up.")
    else:
        print(f"     Both help, which usually means neither dominates and the")
        print(f"     answer is a budget question rather than a bottleneck one.")

    if both > 1.0 and n_only + m_only > 0:
        interaction = both - (n_only + m_only)
        if interaction < -2.0:
            print(f"\n     Doing both gives {both:.1f}%, LESS than the "
                  f"{n_only + m_only:.1f}% the two")
            print(f"     changes give separately. Once the first bottleneck "
                  f"moves, the")
            print(f"     second is what remains - the gains do not add.")
        elif interaction > 2.0:
            print(f"\n     Doing both gives {both:.1f}%, MORE than the "
                  f"{n_only + m_only:.1f}% of the two")
            print(f"     separately: each was being held back by the other.")

    after = results["node only"]
    if base.bound_by != after.bound_by:
        print(f"\n     The node changes what binds: {base.bound_by} before, "
              f"{after.bound_by} after.")
        print(f"     That is the useful thing the sweep cannot show - a node "
              f"that")
        print(f"     buys little today can be the right move if it moves the")
        print(f"     bottleneck somewhere you can then attack.")

    e_base = economics(app_key, options["neither"], node=from_node,
                       volume=vol, **kw)
    e_both = economics(app_key, options["both"], node=to_node, volume=vol, **kw)
    print(f"\n     cost of doing both, at {vol:,} units: "
          f"{e_base.effective_unit:,.2f} -> {e_both.effective_unit:,.2f}")
    print(f"     ({(e_both.effective_unit / e_base.effective_unit - 1) * 100:+.0f}%, "
          f"development included)")
    print(LINE)


# ==============================================================================
# What to do about a memory bottleneck
# ==============================================================================
#
# Buying more channels is the most expensive answer and the first one people
# reach for. It is one of five, and two of the others cost nothing on the bill
# of materials at all.
#
#   more channels     bandwidth up, cost and board area up
#   faster class      a different memory generation - bandwidth up, cost up,
#                     and sometimes a cooling class the product cannot carry
#   more on-chip SRAM buffer more of the working set, refetch less. Costs die
#                     area, not memory packages
#   less traffic      a smaller model or a lower precision moves fewer bytes.
#                     Costs accuracy
#   better dataflow   the same silicon, scheduled better. Costs engineering
#                     and nothing else
#
# The last is free in every sense the model can see, which is exactly why it
# should be checked before the first.

# What kind of change an option is. The distinction matters more than the
# numbers: a compiler improvement and a smaller model are not comparable
# choices, and putting them in one list invites a student to pick whichever
# row has the best latency.
OPTION_CLASS = {
    "engineering": "no bill-of-materials change; costs engineering time",
    "silicon": "die area, not memory packages",
    "bom": "bill-of-materials cost, board area and power",
    "model": "CHANGES THE MODEL - a different accuracy point, not a "
             "different implementation of the same one",
}


def memory_options(app_key: str, config, volume: Optional[int] = None,
                   model_accuracy_cost_pp: Optional[float] = None) -> None:
    """Ways to address a memory bottleneck, grouped by what they actually cost.

    Architecture options implement the SAME network. A model option implements
    a DIFFERENT one, and comparing their latencies as though they were
    alternatives is comparing a faster car with a shorter journey.
    """
    from .application import APPLICATION_LIBRARY
    from .compute import COMPUTE_LIBRARY
    from .memory import MEMORY_LIBRARY, evaluate as mem_eval
    from .system import evaluate_system
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    base = evaluate_system(app, config)
    bm = base.metrics
    arch, model_opts = [], []

    reuse_available = app.workload_class != "text"
    spec = COMPUTE_LIBRARY[config.compute]

    if reuse_available and spec.dataflow_efficiency < 0.95:
        better = dataclasses.replace(
            spec, dataflow_efficiency=min(0.95, spec.dataflow_efficiency * 1.15))
        COMPUTE_LIBRARY["__df__"] = better
        try:
            cfg = dataclasses.replace(config, compute="__df__")
            arch.append(("better dataflow", "engineering", cfg,
                         evaluate_system(app, cfg), ""))
        finally:
            COMPUTE_LIBRARY.pop("__df__", None)

    if reuse_available and spec.sram_kb > 0:
        bigger = dataclasses.replace(spec, sram_kb=spec.sram_kb * 2)
        COMPUTE_LIBRARY["__sram__"] = bigger
        try:
            cfg = dataclasses.replace(config, compute="__sram__")
            arch.append(("2x on-chip SRAM", "silicon", cfg,
                         evaluate_system(app, cfg), ""))
        finally:
            COMPUTE_LIBRARY.pop("__sram__", None)

    cfg = dataclasses.replace(config, memory_devices=config.memory_devices * 2)
    arch.append((f"{config.memory_devices * 2} memory packages", "bom", cfg,
                 evaluate_system(app, cfg), ""))

    # A different memory class is only a comparison if the capacity matches.
    # One package of a narrower, smaller part is not a swap for one of a wider,
    # larger one, and the cost difference that falls out of pretending it is
    # says nothing.
    order = ["LPDDR5", "GDDR6", "HBM3E", "HBM4_36"]
    if config.memory in order and order.index(config.memory) + 1 < len(order):
        nxt = order[order.index(config.memory) + 1]
        here_gb = MEMORY_LIBRARY[config.memory].capacity_gbyte * config.memory_devices
        per_pkg = MEMORY_LIBRARY[nxt].capacity_gbyte
        matched = max(1, int(round(here_gb / per_pkg)))
        cfg = dataclasses.replace(config, memory=nxt, memory_devices=matched)
        note = (f"{matched} packages to match {here_gb:.0f} GB; "
                f"needs {MEMORY_LIBRARY[nxt].cooling_requirement} cooling")
        arch.append((f"move to {nxt}", "bom", cfg,
                     evaluate_system(app, cfg), note))

    # Halving the weights is not one operation. Pruning, distillation, a
    # smaller architecture and a lower precision all halve the bytes and cost
    # entirely different amounts of accuracy, and this model computes only
    # quantisation loss - so it CANNOT price this row. The accuracy has to come
    # from the person proposing the change, or the row is a free lunch.
    if app.weight_bytes > 0:
        lighter = dataclasses.replace(app, weight_bytes=app.weight_bytes * 0.5,
                                      key="__q__")
        if model_accuracy_cost_pp is not None:
            lighter = dataclasses.replace(
                lighter,
                reference_accuracy_pct=lighter.reference_accuracy_pct
                - model_accuracy_cost_pp)
        APPLICATION_LIBRARY["__q__"] = lighter
        try:
            model_opts.append(("half the weights", "model", config,
                               evaluate_system(lighter, config),
                               "a smaller model or a lower precision"))
        finally:
            APPLICATION_LIBRARY.pop("__q__", None)

    print(f"\n{LINE}")
    print(f" MEMORY BOTTLENECK OPTIONS - {app.name}")
    print(LINE)
    print(f"  bound by {base.bound_by}. Buying packages is one answer of "
          f"several,")
    print(f"  and usually the dearest.")
    if not reuse_available:
        print(f"\n  This is an autoregressive decode workload, so the two "
              f"options that")
        print(f"  work by REUSING data - a better schedule and a bigger "
              f"on-chip buffer -")
        print(f"  are not listed. Every weight is read exactly once per token "
              f"by")
        print(f"  construction, so there is nothing for them to save. A "
              f"property of")
        print(f"  the workload, not a failure of the options.")

    def _row(label, klass, cfg, res, note, priced=True):
        m = res.metrics
        dl = (m["Latency (ms)"] / bm["Latency (ms)"] - 1) * 100
        dc = (m["System cost (USD)"] / bm["System cost (USD)"] - 1) * 100
        # An unpriced model change has no accuracy the model can report.
        # Printing the ORIGINAL network's figure would read as a prediction
        # about the smaller one, and the ships column would inherit it.
        acc = f"{m['Deployment accuracy (%)']:>10.2f}" if priced else f"{'not priced':>10s}"
        ships = ("yes" if res.passes else "no") if priced else "unknown"
        print(f"  {label:<22s}{m['Latency (ms)']:>9.3f}{dl:>+8.1f}%"
              f"{m['System cost (USD)']:>10.2f}{dc:>+8.1f}%"
              f"{acc}{res.bound_by:>9s}   {ships}")
        if note:
            print(f"    {note}")

    head = (f"  {'option':<22s}{'latency':>9s}{'change':>9s}{'cost $':>10s}"
            f"{'change':>9s}{'accuracy':>10s}{'bound by':>9s}   ships")
    print(f"\n  -- SAME NETWORK, different implementation -----------------")
    print(head); print("  " + "-" * (len(head) - 2))
    _row("as it is", "", config, base, "")
    for label, klass, cfg, res, note in arch:
        _row(label, klass, cfg, res, note)

    if model_opts:
        print(f"\n  -- A DIFFERENT NETWORK ------------------------------------")
        print(f"  Not an alternative to the rows above. These change what is")
        print(f"  computed, so their latency is not comparable with the "
              f"others -")
        print(f"  it is a faster car against a shorter journey.")
        print(head); print("  " + "-" * (len(head) - 2))
        for label, klass, cfg, res, note in model_opts:
            _row(label, klass, cfg, res, note,
                 priced=model_accuracy_cost_pp is not None)
        if model_accuracy_cost_pp is None:
            print(f"\n    ACCURACY NOT PRICED. Halving the weights is not one "
                  f"operation:")
            print(f"    pruning, distillation, a smaller architecture and a "
                  f"lower")
            print(f"    precision all halve the bytes and cost different "
                  f"amounts of")
            print(f"    accuracy. This model computes quantisation loss and "
                  f"nothing")
            print(f"    else, so the accuracy column above is the ORIGINAL "
                  f"network's -")
            print(f"    it is not a prediction about the smaller one.")
            print(f"\n    Read this row as: 'if you can halve the weights, "
                  f"here is what")
            print(f"    the latency does'. What it costs to halve them is "
                  f"yours to")
            print(f"    supply - pass model_accuracy_cost_pp and the gates "
                  f"will be")
            print(f"    re-evaluated against it.")
        else:
            base_acc = bm["Deployment accuracy (%)"]
            got = model_opts[0][3]
            print(f"\n    Accuracy cost supplied: {model_accuracy_cost_pp:.2f} "
                  f"pp. Deployment accuracy")
            print(f"    {base_acc:.2f}% -> {got.metrics['Deployment accuracy (%)']:.2f}%, "
                  f"and the gates are evaluated against it -")
            print(f"    which is why this row can now FAIL where the others "
                  f"pass.")

    print(f"\n  -- what each costs ----------------------------------------")
    for label, klass, cfg, res, note in arch + model_opts:
        print(f"    {label:<22s}{OPTION_CLASS[klass]}")

    print(f"\n  -- does it REMOVE the bottleneck or move it? --------------")
    for label, klass, cfg, res, note in arch:
        if res.bound_by != base.bound_by:
            print(f"    {label:<22s}{base.bound_by} -> {res.bound_by}   "
                  f"moved, not removed")
        else:
            gain = (1 - res.metrics["Latency (ms)"] / bm["Latency (ms)"]) * 100
            print(f"    {label:<22s}still {res.bound_by} bound"
                  + (f", {gain:.1f}% better" if gain > 0.5 else ", no change"))
    print(f"\n    An option that moves the bottleneck has not finished the "
          f"job -")
    print(f"    it has changed which question to ask next.")

    print(f"\n  An option costing nothing on the bill of materials is not "
          f"free: it")
    print(f"  costs engineering, and a compiler improvement that has not been")
    print(f"  done is not the same as one that has. But it should be ruled out")
    print(f"  before a package is bought.")
    print(LINE)


# ==============================================================================
# The host as an axis
# ==============================================================================
#
# A student choosing an accelerator has three axes, not two. The node makes the
# arithmetic faster, the memory moves bytes faster, and the HOST does the
# preprocessing, the dispatch and the post-processing - work that no
# accelerator touches and that can be most of a frame.
#
# The host was previously visible only as area and power. That is the half of
# it that does not decide anything.

def host_options(app_key: str, config, volume: Optional[int] = None) -> None:
    """What the host is holding, and what a different one would change."""
    from .application import APPLICATION_LIBRARY
    from .cpu import CPU_LIBRARY
    from .system import evaluate_system
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    base = evaluate_system(app, config)
    bm = base.metrics

    print(f"\n{LINE}")
    print(f" HOST OPTIONS - {app.name}")
    print(LINE)
    print(f"  The accelerator computes the network. The host does everything")
    print(f"  around it - laying out and normalising pixels, launching the "
          f"job,")
    print(f"  running non-maximum suppression, formatting the result. None of")
    print(f"  that is touched by a faster accelerator.\n")

    print(f"  -- what the host is holding now ---------------------------")
    print(f"     preprocessing        {bm['CPU preprocess (ms)']:>8.3f} ms")
    print(f"     dispatch             {bm['CPU dispatch (ms)']:>8.3f} ms")
    print(f"     post-processing      {bm['CPU postprocess (ms)']:>8.3f} ms")
    print(f"     host total           {bm['CPU active (ms)']:>8.3f} ms   "
          f"{bm['CPU latency share (%)']:.1f}% of the latency")
    print(f"     host DRAM traffic    {bm['Host DRAM traffic (MB)']:>8.2f} MB  "
          f"{bm['Host bandwidth share (%)']:.1f}% of the bus")
    if bm["Host bandwidth share (%)"] > 1.0:
        print(f"     The accelerator sees "
              f"{bm['Bandwidth left to the accelerator (GB/s)']:.1f} GB/s "
              f"rather than the interface's")
        print(f"     full rate, because the host is reading pixels across the "
              f"same bus.")
    print(f"     accelerator          {bm['Compute time (ms)']:>8.3f} ms")
    print(f"\n     arithmetic           {bm['Host compute time (ms)']:>8.3f} ms")
    print(f"     transfers, hidden    {bm['Host hidden memory (ms)']:>8.3f} ms")
    print(f"     transfers, exposed   {bm['Host data-wait (ms)']:>8.3f} ms")
    print(f"     host stage total     {bm['CPU active (ms)']:>8.3f} ms")
    print(f"     the host is          {base.host_state.upper()}")
    if base.host_state == "balanced":
        print(f"     Near the balance point. Which side it falls on depends "
              f"on how")
        print(f"     well the host's reads overlap its arithmetic, which this "
              f"model")
        print(f"     represents with one coefficient and does not measure.")
    if bm["Host bound by"]:
        print(f"     A faster host will NOT help. It is already waiting for "
              f"the bus,")
        print(f"     and more cores wait faster. Widen the memory or move the "
              f"work.")
    if bm["CPU latency share (%)"] > 50:
        print(f"\n     The host holds MORE than half the frame. A bigger array")
        print(f"     cannot fix this, and buying one is the most common "
              f"mistake")
        print(f"     this simulator exists to make visible.")

    rows = []
    for key, spec in CPU_LIBRARY.items():
        if spec.automotive_grade is False and app.domain != "Data Center":
            continue
        cfg = dataclasses.replace(config, cpu=key)
        rows.append((spec.name, key, cfg, evaluate_system(app, cfg)))

    print(f"\n  -- what a different host would change ---------------------")
    head = (f"  {'host':<20s}{'host ms':>9s}{'of which wait':>14s}{'state':>8s}"
            f"{'latency':>9s}{'change':>9s}{'cost $':>9s}   ships")
    print(head); print("  " + "-" * (len(head) - 2))
    for name, key, cfg, res in rows:
        m = res.metrics
        dl = (m["Latency (ms)"] / bm["Latency (ms)"] - 1) * 100
        mark = "  <- current" if key == config.cpu else ""
        print(f"  {name:<20s}{m['CPU active (ms)']:>9.3f}"
              f"{m['Host data-wait (ms)']:>14.3f}"
              f"{res.host_state.split('-')[0]:>8s}"
              f"{m['Latency (ms)']:>9.3f}{dl:>+8.1f}%"
              f"{m['System cost (USD)']:>9.2f}   "
              f"{'yes' if res.passes else 'no':<4s}{mark}")
    if any(r[3].metrics["Host bound by"] for r in rows):
        print(f"\n    A host marked MEMORY bound is waiting for the bus, not "
              f"running")
        print(f"    out of cycles. Buying a faster one buys a faster wait.")

    # --- and the option that costs no host at all -------------------------
    from .preprocess import MODES
    print(f"\n  -- or move the work off the host entirely -----------------")
    for mode in MODES:
        if mode == config.preprocessing_mode:
            continue
        try:
            cfg = dataclasses.replace(config, preprocessing_mode=mode)
            res = evaluate_system(app, cfg)
        except Exception:
            continue
        m = res.metrics
        dl = (m["Latency (ms)"] / bm["Latency (ms)"] - 1) * 100
        print(f"  {MODES[mode]['label']:<34s}{m['CPU active (ms)']:>9.3f} ms"
              f"{dl:>+9.1f}% latency"
              f"{m['System cost (USD)']:>9.2f}   "
              f"{'yes' if res.passes else 'no'}")

    print(f"\n  A faster host and an offload both remove the same work. The")
    print(f"  first keeps the flexibility and costs power on every frame; the")
    print(f"  second is fixed-function and costs silicon whether or not it is")
    print(f"  used. Which is right depends on how much else the host has to "
          f"do,")
    print(f"  and this model only sees the inference.")
    print(LINE)


# ==============================================================================
# Splitting work between two unequal engines
# ==============================================================================
#
# Two assumptions a student brings to a second accelerator, and both are
# usually wrong:
#
#     "give each engine half the work"
#     "a slower second engine still helps a bit"
#
# The first is right only when the engines are identical. The second fails
# once the slow engine's share makes it the bottleneck, and past that point a
# second accelerator makes the system worse than having none.

def allocation_sweep(app_key: str, config, secondary: str,
                     mode: str = "alternative", points: int = 11) -> list:
    """Sweep the share or split and report where the capacity peaks."""
    from .application import APPLICATION_LIBRARY
    from .compute import COMPUTE_LIBRARY
    from .system import evaluate_system
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    knob = "alternative_share" if mode == "alternative" else "work_split"
    rows = []
    for i in range(points):
        v = i / (points - 1)
        cfg = dataclasses.replace(config, secondary_compute=secondary,
                                  execution_mode=mode, **{knob: v})
        r = evaluate_system(app, cfg)
        m = r.metrics
        rows.append((v, m["Latency (ms)"], m["Pipeline capacity (inf/s)"],
                     m["Delivered throughput (inf/s)"],
                     m["Stage accelerator 1 (ms)"],
                     m["Stage accelerator 2 (ms)"], r.passes))

    p_spec, s_spec = COMPUTE_LIBRARY[config.compute], COMPUTE_LIBRARY[secondary]
    print(f"\n{LINE}")
    print(f" ALLOCATION SWEEP - {app.name}")
    print(LINE)
    print(f"  primary        {p_spec.name}")
    print(f"  secondary      {s_spec.name}")
    print(f"  mode           {mode}  ({knob})")
    if mode == "alternative":
        print(f"\n  Whole jobs are routed to one engine or the other. The "
              f"latency below")
        print(f"  is a MEAN over jobs, not any one job's - with unequal "
              f"engines the")
        print(f"  distribution is bimodal and no job experiences the average.")
    else:
        print(f"\n  ONE job's arithmetic is divided between the two engines, "
              f"so the")
        print(f"  latency below is a real job's and the engines run "
              f"concurrently.")

    head = (f"\n  {knob:>16s}{'latency':>10s}{'capacity':>10s}"
            f"{'delivered':>11s}{'engine 1':>10s}{'engine 2':>10s}")
    print(head); print("  " + "-" * (len(head) - 3))
    best_cap = max(rows, key=lambda r: r[2])
    best_lat = min(rows, key=lambda r: r[1])
    for v, lat, cap, deliv, a1, a2, ok in rows:
        mark = ""
        if v == best_cap[0]:
            mark += "  <- most capacity"
        if v == best_lat[0]:
            mark += "  <- lowest latency"
        print(f"  {v:>16.2f}{lat:>10.2f}{cap:>10.2f}{deliv:>11.2f}"
              f"{a1:>10.2f}{a2:>10.2f}{mark}")

    # Where SHOULD the peak be? For alternative mode it is the capacity ratio,
    # which can be worked out without the model and compared against it.
    if mode == "alternative":
        t_p = rows[0][4]
        t_s = rows[-1][5]
        ideal = t_p / (t_p + t_s) if (t_p + t_s) > 0 else 0.0
        print(f"\n  -- where the peak should be -------------------------------")
        print(f"     engine 1 takes {t_p:.2f} ms a job, engine 2 takes "
              f"{t_s:.2f} ms.")
        print(f"     Balanced when each finishes its queue at the same time, "
              f"which")
        print(f"     puts the secondary's share at {t_p:.2f} / "
              f"({t_p:.2f} + {t_s:.2f}) = {ideal:.2f}.")
        print(f"     The sweep peaks at {best_cap[0]:.2f}. That figure comes "
              f"from the")
        print(f"     model and this one does not, so they are two paths to the "
              f"same")
        print(f"     answer rather than one.")
        if abs(best_cap[0] - 0.5) > 0.1:
            print(f"\n     Note that it is NOT 0.5. Giving each engine half "
                  f"the jobs")
            print(f"     saturates the slower one while the faster one waits, "
                  f"and costs")
            print(f"     {(1 - rows[points // 2][2] / best_cap[2]) * 100:.0f}% "
                  f"of the capacity available at the peak.")
    else:
        single = rows[0]
        worse = [r for r in rows if r[1] > single[1]]
        print(f"\n  -- is the second engine worth using at all? ---------------")
        print(f"     At a split of 0 the design is the single-engine one: "
              f"{single[1]:.2f} ms.")
        print(f"     The best split found is {best_lat[0]:.2f} at "
              f"{best_lat[1]:.2f} ms.")
        if best_lat[0] <= 1e-9:
            print(f"     The best split is ZERO - this secondary is slow "
                  f"enough that")
            print(f"     using it costs more than it saves at every share. It "
                  f"still")
            print(f"     occupies silicon, still leaks, and still had to be "
                  f"bought.")
        else:
            # The LAST split that still beats the single engine, not the first
            # one that does not - the curve is not monotone and reporting the
            # first worse point named 0.10 while 0.20 to 0.40 were better.
            better = [r[0] for r in rows if r[1] < single[1] - 1e-9]
            gain = (1 - best_lat[1] / single[1]) * 100
            print(f"     Using it is worth {gain:.0f}% at best.")
            if better:
                print(f"     It beats the single engine only between "
                      f"{min(better):.2f} and {max(better):.2f};")
                print(f"     outside that the pair is SLOWER than having one "
                      f"engine. A second")
                print(f"     accelerator is not free insurance - used wrongly "
                      f"it makes the")
                print(f"     system worse than not having one at all.")
    print(f"\n  These are the lowest simulated figures under THIS workload and")
    print(f"  these assumptions, not a recommendation. A different frame size "
          f"or")
    print(f"  a different memory moves the peak.")
    print(LINE)
    return rows


# ==============================================================================
# Reduction to a single engine
# ==============================================================================
#
# "The same as one engine" is three different claims and they come apart:
#
#   WORKLOAD    the second engine is assigned nothing, so it computes nothing
#               and moves no bytes
#   PERFORMANCE latency, capacity and delivered rate match the single design
#   PHYSICAL    area, cost and power match it too
#
# The first two hold whenever the work is zero. The third holds ONLY when the
# engine is not on the board, and a report that ran them together would teach
# that "we do not use it" and "we do not fit it" cost the same.

def reduction_check(app_key: str, single_config, secondary: str) -> None:
    """Which of the three reductions hold, for each way of not using an engine."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    base = evaluate_system(app, single_config)
    bm = base.metrics

    states = [
        ("not installed", single_config),
        ("split = 0", dataclasses.replace(
            single_config, secondary_compute=secondary,
            execution_mode="parallel", work_split=0.0)),
        ("share = 0", dataclasses.replace(
            single_config, secondary_compute=secondary,
            execution_mode="alternative", alternative_share=0.0)),
        ("installed, gated", dataclasses.replace(
            single_config, secondary_compute=secondary,
            secondary_enabled=False, execution_mode="parallel",
            work_split=0.5)),
        ("installed, used", dataclasses.replace(
            single_config, secondary_compute=secondary,
            execution_mode="parallel", work_split=0.5)),
    ]

    print(f"\n{LINE}")
    print(f" REDUCTION TO A SINGLE ENGINE - {app.name}")
    print(LINE)
    print(f"  'The same as one engine' is three claims, and they come apart.")
    print(f"  An engine that is fitted and never used is not the same product")
    print(f"  as one that was never fitted.\n")

    head = (f"  {'state':<20s}{'workload':>10s}{'performance':>13s}"
            f"{'physical':>10s}   what differs")
    print(head); print("  " + "-" * (len(head) - 2))
    for label, cfg in states:
        r = evaluate_system(app, cfg)
        m = r.metrics
        workload = (abs(m["Secondary compute time (ms)"]) < 1e-12
                    and abs(m["Handoff (ms)"]) < 1e-12)
        perf = (abs(m["Latency (ms)"] - bm["Latency (ms)"]) < 1e-9
                and abs(m["Pipeline capacity (inf/s)"]
                        - bm["Pipeline capacity (inf/s)"]) < 1e-9)
        physical = (abs(m["Logic silicon (mm2)"] - bm["Logic silicon (mm2)"]) < 1e-12
                    and abs(m["System cost (USD)"] - bm["System cost (USD)"]) < 1e-12
                    and abs(m["System power (W)"] - bm["System power (W)"]) < 1e-12)
        diffs = []
        if not physical:
            if m["Logic silicon (mm2)"] > bm["Logic silicon (mm2)"] + 1e-12:
                diffs.append(f"+{m['Logic silicon (mm2)'] - bm['Logic silicon (mm2)']:.2f} mm2")
            if m["System power (W)"] > bm["System power (W)"] + 1e-6:
                diffs.append(f"+{m['System power (W)'] - bm['System power (W)']:.3f} W")
        if not perf:
            diffs.append(f"latency {m['Latency (ms)'] - bm['Latency (ms)']:+.3f} ms")
        print(f"  {label:<20s}{('yes' if workload else 'no'):>10s}"
              f"{('yes' if perf else 'no'):>13s}{('yes' if physical else 'no'):>10s}"
              f"   {', '.join(diffs) if diffs else '-'}")

    print(f"\n  -- reading it ---------------------------------------------")
    print(f"     Only the first row reduces physically. The two zero-work rows")
    print(f"     reduce in workload and performance and still carry the die,")
    print(f"     its price and its leakage - a design decision that has been")
    print(f"     made and not used.")
    print(f"     The gated row keeps the die and the price and gives up most")
    print(f"     of the leakage. Not all: power gating leaves retention, and a")
    print(f"     model that took it to zero would make 'fit it and switch it")
    print(f"     off' look free.")
    print(LINE)


# ==============================================================================
# Reading a comparison without mixing up its three questions
# ==============================================================================
#
# A design can improve on the reference, sit inside every typical band, and
# still not ship. Those are three different questions and a report that
# collapses them into "better" or "worse" teaches a student to answer the
# wrong one.

def compare_proposal(app_key: str, reference, proposal,
                    volume: Optional[int] = None) -> None:
    """Requirements, reference, and domain - kept apart, and audited."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    from .interpret import RANGES, DOMAIN_OF_APPLICATION, verdict, _value

    app = APPLICATION_LIBRARY[app_key]
    a, b = evaluate_system(app, reference), evaluate_system(app, proposal)
    am, bm = a.metrics, b.metrics

    print(f"\n{LINE}")
    print(f" DESIGN COMPARISON - {app.name}")
    print(LINE)

    # --- 1. does it ship ---------------------------------------------------
    print(f"  1. REQUIREMENTS - can this be sold?")
    failed = [g for g, ok in b.gate.items() if not ok]
    print(f"     {sum(1 for o in b.gate.values() if o)}/{len(b.gate)}"
          + (f"   failing: {', '.join(failed)}" if failed else "   all met"))

    # --- 2. is it better than what we had ----------------------------------
    print(f"\n  2. AGAINST THE REFERENCE - is it an improvement?")
    axes = (("latency", "Latency (ms)", True),
            ("pipeline capacity", "Pipeline capacity (inf/s)", False),
            ("delivered", "Delivered throughput (inf/s)", False),
            ("energy per job", "Energy per inference (mJ)", True),
            ("average power", "System power (W)", True),
            ("accuracy", "Deployment accuracy (%)", False),
            ("cost", "System cost (USD)", True))
    better, worse = [], []
    for label, key, lower_better in axes:
        x, y = am[key], bm[key]
        chg = (y / x - 1) * 100 if x else 0.0
        is_better = (y < x) if lower_better else (y > x)
        tag = "" if abs(chg) < 0.5 else ("  better" if is_better else "  worse")
        if abs(chg) >= 0.5:
            (better if is_better else worse).append(label)
        print(f"     {label:<20s}{x:>12.3f}{y:>12.3f}{chg:>+9.1f}%{tag}")

    # Energy per job and average power are NOT one axis. A design can improve
    # one and worsen the other, and it did - repeatedly - in the dual-engine
    # scenarios.
    if ("energy per job" in better) != ("average power" in better):
        print(f"\n     Energy per job and average power moved in OPPOSITE")
        print(f"     directions. They are different questions: energy per job")
        print(f"     is what a fixed amount of work costs, average power is")
        print(f"     what the battery feels. Neither is 'power improved'.")

    # --- 3. is it ordinary --------------------------------------------------
    dom = DOMAIN_OF_APPLICATION.get(app_key, "Edge AI")
    print(f"\n  3. AGAINST THE {dom.upper()} RANGE - is it ordinary?")
    outside = []
    for r in RANGES:
        band = r.bands.get(dom)
        v = _value(bm, r.metric_key)
        state, why = verdict(v, band)
        if state in ("BELOW", "ABOVE"):
            outside.append(f"{r.metric} {state.lower()}")
    print(f"     {'everything inside the usual bands' if not outside else ', '.join(outside)}")

    # --- what the three say together ---------------------------------------
    print(f"\n  -- the three do not have to agree ------------------------")
    if failed and better:
        print(f"     Better than the reference on {', '.join(better[:3])} and "
              f"it does NOT ship:")
        print(f"     {', '.join(failed)} fails. An improvement is not a "
              f"product.")
    elif failed:
        print(f"     Does not ship, and is not an improvement either.")
    elif better and worse:
        print(f"     Ships. Better on {', '.join(better[:3])}, worse on "
              f"{', '.join(worse[:3])} -")
        print(f"     which of those matters is a question about the product, "
              f"not the silicon.")
    elif better and not worse:
        # This is the case to be suspicious of.
        print(f"     EVERY axis improved and none got worse. That happens, and")
        print(f"     it is also what a mismatched comparison looks like. "
              f"Before")
        print(f"     believing it, check that both designs were measured over")
        print(f"     the SAME workload, precision, memory capacity, cooling")
        print(f"     class and cost scope. A boundary that moved between the")
        print(f"     two would produce exactly this table.")
    else:
        print(f"     Ships, and is not better than what it replaces.")
    print(LINE)


# ==============================================================================
# What the LAST stack bought
# ==============================================================================
#
# A total tells a student that more is better. A margin tells them where it
# stops being worth it, and those are different lessons from the same sweep.

def stack_marginal_utility(app_key: str, config, memory: str = "HBM3E",
                           counts=(4, 6, 8, 10, 12)) -> list:
    """Per-stack figures, and what each additional stack cost to gain."""
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY, evaluate as mem_eval
    from .system import evaluate_system, show
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    mem = MEMORY_LIBRARY[memory]
    per_pkg = mem_eval(mem).metrics["Package cost (USD)"]
    rows = []
    for n in counts:
        r = evaluate_system(app, dataclasses.replace(
            config, memory=memory, memory_devices=n))
        m = r.metrics
        rows.append({
            "n": n, "result": r,
            "capacity_gb": mem.capacity_gbyte * n,
            "bandwidth": m["Effective bandwidth (GB/s)"],
            "latency": m["Latency (ms)"],
            "pipeline": m["Pipeline capacity (inf/s)"],
            "delivered": m["Delivered throughput (inf/s)"],
            "power": m["System power (W)"],
            "energy": m["Energy per inference (mJ)"],
            "mem_cost": per_pkg * n,
            "feasible": "INFEASIBLE" not in r.status,
        })

    print(f"\n{LINE}")
    print(f" STACK MARGINAL UTILITY - {app.name}, {mem.name}")
    print(LINE)
    head = (f"  {'stacks':>7s}{'GB':>7s}{'GB/s':>9s}{'latency':>9s}"
            f"{'pipeline':>10s}{'delivered':>11s}{'W':>8s}{'mem $':>10s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for r in rows:
        if not r["feasible"]:
            print(f"  {r['n']:>7d}{r['capacity_gb']:>7.0f}"
                  f"{r['bandwidth']:>9.0f}"
                  + f"{'INFEASIBLE - model does not fit':>39s}")
            continue
        print(f"  {r['n']:>7d}{r['capacity_gb']:>7.0f}{r['bandwidth']:>9.0f}"
              f"{r['latency']:>9.2f}{r['pipeline']:>10.1f}"
              f"{r['delivered']:>11.1f}{r['power']:>8.1f}"
              f"{r['mem_cost']:>10.0f}")

    usable = [r for r in rows if r["feasible"]]
    if len(usable) < 2:
        print("\n  Fewer than two feasible points - no margin to report.")
        print(LINE)
        return rows

    print(f"\n  -- what each ADDITIONAL step bought ------------------------")
    head2 = (f"  {'step':>12s}{'latency gain':>14s}{'cost rise':>12s}"
             f"{'$ per 1% gain':>16s}")
    print(head2); print("  " + "-" * (len(head2) - 2))
    for a, b in zip(usable, usable[1:]):
        gain = (1 - b["latency"] / a["latency"]) * 100
        rise = b["mem_cost"] - a["mem_cost"]
        per = (rise / gain) if gain > 0.05 else None
        print(f"  {f'{a[chr(34)+chr(34)] if False else a['n']} -> {b['n']}':>12s}"
              f"{gain:>13.1f}%{rise:>11.0f}"
              + (f"{per:>16.0f}" if per is not None
                 else f"{'no gain to buy':>16s}"))

    print(f"\n  -- reading it ---------------------------------------------")
    print(f"     The total says more is better. The margin says where it")
    print(f"     stops being worth it, and only the second is a design")
    print(f"     decision.")
    flat = [(a["n"], b["n"]) for a, b in zip(usable, usable[1:])
            if (1 - b["latency"] / a["latency"]) * 100 < 1.0]
    if flat:
        first = flat[0]
        print(f"     Past {first[0]} stacks the latency moves less than 1% per")
        print(f"     step while the memory bill keeps rising.")
    if all(abs(r["delivered"] - usable[0]["delivered"]) < 1e-9 for r in usable):
        print(f"     And the DELIVERED rate never moved at all - every stack")
        print(f"     on this list bought capacity the workload never asked")
        print(f"     for.")
    print(f"\n     Where to stop is not in this table. It depends on the")
    print(f"     requirement and on how many are being built, and a student")
    print(f"     who reads a knee here as 'the answer' has skipped both.")
    print(LINE)
    return rows


# ==============================================================================
# Choosing a memory, in the order the question is actually decided
# ==============================================================================
#
# A student who picks HBM and reads a latency has learnt that faster memory is
# faster. The three things they need to separate are whether the model FITS,
# whether the system got QUICKER, and whether the product can still be BUILT -
# and a design can pass the first two and fail the third.

WHY_FASTER_MEMORY_MAY_HELP = (
    "the model does not fit in the memory you have",
    "the accelerator is waiting for data rather than computing",
    "two accelerators are sharing a memory system that is already full",
)

WHY_FASTER_MEMORY_MAY_NOT_HELP = (
    "the CPU is the slowest station, and it is not waiting for this memory",
    "a fixed-function block such as an ISP sets the frame rate",
    "the sensor or the user is not asking for more work than is already done",
)


def memory_choice(app_key: str, before, after) -> None:
    """Before you look at the number, why did you change the memory?"""
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .system import evaluate_system, show, gate_causes

    app = APPLICATION_LIBRARY[app_key]
    a, b = evaluate_system(app, before), evaluate_system(app, after)
    am, bm = a.metrics, b.metrics
    m_before = MEMORY_LIBRARY[before.memory]
    m_after = MEMORY_LIBRARY[after.memory]

    print(f"\n{LINE}")
    print(f" MEMORY CHOICE - {app.name}")
    print(f" {m_before.name} x{before.memory_devices}  ->  "
          f"{m_after.name} x{after.memory_devices}")
    print(LINE)

    print(f"  A faster memory MAY help when:")
    for r in WHY_FASTER_MEMORY_MAY_HELP:
        print(f"    - {r}")
    print(f"\n  It may NOT help when:")
    for r in WHY_FASTER_MEMORY_MAY_NOT_HELP:
        print(f"    - {r}")
    print(f"\n  Which of those is true here decides the answer, and it is a")
    print(f"  question about the design rather than about the memory.\n")

    # --- 1. does the model fit --------------------------------------------
    print(f"  1. CAPACITY EFFECT - does the model fit?")
    for label, res, cfg in (("before", a, before), ("after", b, after)):
        mem = MEMORY_LIBRARY[cfg.memory]
        installed = mem.capacity_gbyte * cfg.memory_devices
        fits = "INFEASIBLE" not in res.status
        print(f"     {label:<8s}{installed:>7.0f} GB installed   "
              f"{'fits' if fits else 'DOES NOT FIT'}")
    if "INFEASIBLE" in a.status and "INFEASIBLE" not in b.status:
        print(f"     The change made an impossible design possible. Nothing")
        print(f"     below would have existed before it.")
    elif "INFEASIBLE" in b.status:
        print(f"     The model still does not fit, so there is no performance")
        print(f"     to report. More bandwidth does not make it fit.")
        print(LINE)
        return

    # --- 2. did it get quicker --------------------------------------------
    print(f"\n  2. PERFORMANCE EFFECT - did the system get quicker?")
    if "INFEASIBLE" in a.status:
        print(f"     No before-figure: the earlier design could not run.")
    else:
        for label, key in (("latency", "Latency (ms)"),
                           ("pipeline capacity", "Pipeline capacity (inf/s)"),
                           ("delivered throughput",
                            "Delivered throughput (inf/s)"),
                           ("energy per job", "Energy per inference (mJ)")):
            chg = ((bm[key] / am[key] - 1) * 100) if am[key] else 0.0
            print(f"     {label:<22s}{show(am[key]):>12s} -> "
                  f"{show(bm[key]):>12s}{chg:>+9.1f}%")
        cap_gain = (bm["Pipeline capacity (inf/s)"]
                    / am["Pipeline capacity (inf/s)"] - 1) * 100
        del_gain = (bm["Delivered throughput (inf/s)"]
                    / am["Delivered throughput (inf/s)"] - 1) * 100
        lat_gain = (1 - bm["Latency (ms)"] / am["Latency (ms)"]) * 100
        if lat_gain > 5.0:
            print(f"\n     Each job finishes {lat_gain:.0f}% sooner. The "
                  f"accelerator was")
            print(f"     waiting for data, and the faster memory removes "
                  f"enough of")
            print(f"     that wait for the compute to be used.")
            if before.secondary_compute:
                print(f"     There are two accelerators here, and this is "
                      f"where the")
                print(f"     second one starts earning its place: it was "
                      f"waiting for")
                print(f"     memory, not short of work.")
        if cap_gain > 5.0 and del_gain < 1.0:
            print(f"\n     But the DELIVERED rate did not move. The machine "
                  f"could now")
            print(f"     do {cap_gain:.0f}% more and is not being asked to - "
                  f"the system was")
            print(f"     waiting for the CPU, the ISP, or incoming data "
                  f"instead.")
            print(f"     Whether that is worth paying for depends on whether "
                  f"the")
            print(f"     latency mattered or only the frame rate did.")
        elif lat_gain <= 5.0 and cap_gain <= 5.0:
            print(f"\n     Neither the latency nor the capacity moved much. "
                  f"The memory")
            print(f"     became faster and the system was waiting for "
                  f"something else.")

    # --- 3. can it still be built -----------------------------------------
    print(f"\n  3. PRODUCT FEASIBILITY - can it still be built and sold?")
    for label, res in (("before", a), ("after", b)):
        failed = [g for g, ok in res.gate.items() if not ok]
        print(f"     {label:<8s}" + ("all requirements met" if not failed
                                     else f"FAILS: {', '.join(failed)}"))
    causes = gate_causes(b)
    if causes["failed"]:
        print()
        for g in causes["independent"]:
            note = causes["kinds"].get(g, "")
            print(f"     {g}" + (f"   {note}" if note else ""))
        for g, parent in causes["derived"].items():
            print(f"     {g}   follows from {parent}")
        print(f"\n     Faster is not the same as usable. A design can improve")
        print(f"     on every timing above and still be one nobody can ship.")
    print(LINE)


# ==============================================================================
# Context length: the axis that surprises everyone
# ==============================================================================
#
# The weights do not change. A student who has learnt that a model is "70 GB"
# is then told the same model needs a hundred and forty, and the reason is a
# cache whose size follows the CONVERSATION rather than the network.
#
# Almost everything a person needs to know about serving an LLM is visible in
# one sweep of this axis: what the weights cost, what the cache costs, when
# the two stop fitting, and what a wider memory does about it.

def context_sweep(app_key: str, config,
                  contexts=(4096, 16384, 65536, 131072, 262144, 524288)) -> list:
    """Same model, same board, longer and longer conversations."""
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .system import evaluate_system, show
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    mem = MEMORY_LIBRARY[config.memory]
    installed = mem.capacity_gbyte * config.memory_devices
    rows = []
    for ctx in contexts:
        kv = app.kv_bytes_per_token * ctx
        tuned = dataclasses.replace(app, context_tokens=ctx,
                                    kv_cache_bytes=kv, key="__ctx__")
        APPLICATION_LIBRARY["__ctx__"] = tuned
        try:
            r = evaluate_system(tuned, config)
            rows.append({
                "ctx": ctx, "kv_gb": kv / 1e9,
                "weights_gb": app.weight_bytes / 1e9,
                "total_gb": (app.weight_bytes + kv
                             + app.runtime_overhead_bytes) / 1e9,
                "latency": r.metrics["Latency (ms)"],
                "tokens": r.metrics["Delivered throughput (inf/s)"],
                "traffic_mb": r.metrics["DRAM traffic (MB)"],
                "feasible": "INFEASIBLE" not in r.status,
            })
        finally:
            APPLICATION_LIBRARY.pop("__ctx__", None)

    print(f"\n{LINE}")
    print(f" CONTEXT LENGTH SWEEP - {app.name}")
    print(LINE)
    print(f"  memory        {mem.name} x{config.memory_devices} "
          f"= {installed:.0f} GB")
    print(f"  weights       {app.weight_bytes / 1e9:.0f} GB - the SAME model "
          f"in every row below\n")
    head = (f"  {'context':>9s}{'weights':>10s}{'KV cache':>10s}{'total':>9s}"
            f"{'fits':>7s}{'tokens/s':>11s}{'traffic MB':>12s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for r in rows:
        print(f"  {r['ctx']:>9d}{r['weights_gb']:>9.0f}G{r['kv_gb']:>9.1f}G"
              f"{r['total_gb']:>8.1f}G{('yes' if r['feasible'] else 'NO'):>7s}"
              + (f"{show(r['tokens'], '{:.1f}'):>11s}"
                 f"{r['traffic_mb']:>12.0f}" if r["feasible"]
                 else f"{'-':>11s}{'-':>12s}"))

    usable = [r for r in rows if r["feasible"]]
    print(f"\n  -- what changed and what did not --------------------------")
    print(f"     The weights never moved. The cache grew with the "
          f"conversation,")
    print(f"     LINEARLY - twice the context is twice the cache - and it is "
          f"the")
    print(f"     cache that runs the board out of memory.")
    if usable and len(usable) < len(rows):
        last = usable[-1]
        first_fail = next(r for r in rows if not r["feasible"])
        print(f"\n     This board holds the model to {last['ctx']} tokens. At "
              f"{first_fail['ctx']} the")
        print(f"     cache alone is {first_fail['kv_gb']:.0f} GB and nothing "
              f"fits. The model did not")
        print(f"     get bigger; the conversation did.")
    if len(usable) >= 2:
        a0, a1 = usable[0], usable[-1]
        print(f"\n     Traffic per token rose "
              f"{(a1['traffic_mb'] / a0['traffic_mb'] - 1) * 100:.0f}% across "
              f"the range, because")
        print(f"     every token now reads a longer cache as well as the "
              f"weights.")
        print(f"     That is why a long conversation is slower on the same "
              f"machine.")
    print(f"\n  Capacity here is the whole answer. A faster memory does not")
    print(f"  make a longer conversation fit, and a student who reaches for")
    print(f"  bandwidth when the failure is capacity has read the wrong row.")
    print(LINE)
    return rows


# ==============================================================================
# Quantisation: the lever everyone reaches for, and what it actually costs
# ==============================================================================

QUANT_BYTES = {"FP16": 2.0, "FP8": 1.0, "INT8": 1.0, "INT4": 0.5}
# Accuracy cost is NOT derived - it depends on the network, the calibration
# and the method, and this model has no basis for any of them. These are
# ENGINEERING ASSUMPTIONS, stated so a reader can replace them.
QUANT_ACCURACY_COST_PP = {"FP16": 0.0, "FP8": 0.3, "INT8": 0.8, "INT4": 3.5}


def quantisation_sweep(app_key: str, config,
                       precisions=("FP16", "FP8", "INT8", "INT4")) -> list:
    """The same network at four widths: what fits, what it costs, what it loses."""
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .system import evaluate_system, show
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    mem = MEMORY_LIBRARY[config.memory]
    installed = mem.capacity_gbyte * config.memory_devices
    base_bytes = QUANT_BYTES["FP16"]
    rows = []
    for prec in precisions:
        scale = QUANT_BYTES[prec] / base_bytes
        tuned = dataclasses.replace(
            app,
            weight_bytes=app.weight_bytes * scale,
            kv_cache_bytes=app.kv_cache_bytes * scale,
            kv_bytes_per_token=app.kv_bytes_per_token * scale,
            reference_accuracy_pct=app.reference_accuracy_pct
            - QUANT_ACCURACY_COST_PP[prec],
            key="__q__")
        APPLICATION_LIBRARY["__q__"] = tuned
        try:
            r = evaluate_system(tuned, config)
            rows.append({
                "prec": prec, "scale": scale,
                "weights_gb": tuned.weight_bytes / 1e9,
                "total_gb": (tuned.weight_bytes + tuned.kv_cache_bytes
                             + tuned.runtime_overhead_bytes) / 1e9,
                "latency": r.metrics["Latency (ms)"],
                # The SINGLE-JOB rate, because that is what the requirement
                # is written against for an interactive service and what the
                # gate reads. The delivered figure is capped at the target and
                # would show 35 for a design that fails at 31.6.
                "tokens": r.metrics["Single-job rate (inf/s)"],
                "delivered": r.metrics["Delivered throughput (inf/s)"],
                "power": r.metrics["System power (W)"],
                "accuracy": r.metrics["Deployment accuracy (%)"],
                "acc_cost": QUANT_ACCURACY_COST_PP[prec],
                "feasible": "INFEASIBLE" not in r.status,
                "passes": r.passes,
                "failed": [g for g, ok in r.gate.items() if not ok],
            })
        finally:
            APPLICATION_LIBRARY.pop("__q__", None)

    print(f"\n{LINE}")
    print(f" QUANTISATION SWEEP - {app.name}")
    print(LINE)
    print(f"  memory        {mem.name} x{config.memory_devices} "
          f"= {installed:.0f} GB")
    print(f"  the same network at four widths\n")
    head = (f"  {'precision':>10s}{'weights':>10s}{'total':>9s}{'fits':>7s}"
            f"{'tokens/s':>16s}{'accuracy':>10s}{'ships':>8s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for r in rows:
        print(f"  {r['prec']:>10s}{r['weights_gb']:>9.0f}G{r['total_gb']:>8.0f}G"
              f"{('yes' if r['feasible'] else 'NO'):>7s}"
              f"{show(r['tokens'], '{:.1f}'):>16s}"
              f"{show(r['accuracy'], '{:.2f}'):>10s}"
              f"{('yes' if r['passes'] else 'no'):>8s}")

    print(f"\n  -- what quantisation is trading ---------------------------")
    print(f"     Halving the width halves the bytes, so it halves what has "
          f"to")
    print(f"     be STORED and what has to be MOVED. Both effects are real "
          f"and")
    print(f"     they arrive together, which is why this is the lever people")
    print(f"     reach for first.")
    fits = [r for r in rows if r["feasible"]]
    if fits and len(fits) < len(rows):
        print(f"\n     On this board {rows[0]['prec']} does not fit and "
              f"{fits[0]['prec']} does. That is not a")
        print(f"     speed improvement - it is the difference between a "
              f"product and")
        print(f"     no product.")
    lost = [r for r in fits if not r["passes"]]
    if lost:
        reasons = sorted({g for r in lost for g in r["failed"]})
        print(f"\n     But {', '.join(r['prec'] for r in lost)} fits and does "
              f"NOT ship: {', '.join(reasons)}.")
        if "throughput" in reasons:
            slow = [r for r in lost if "throughput" in r["failed"]]
            print(f"     The token rate column is the SINGLE-JOB rate, which "
                  f"is what")
            print(f"     an interactive requirement is written against. A "
                  f"delivered")
            print(f"     figure would read {slow[0]['delivered']:.0f} here - "
                  f"capped at what is asked")
            print(f"     for - and would hide the failure entirely.")
        if "accuracy" in reasons:
            print(f"     Quantisation bought the capacity by giving up "
                  f"accuracy, and")
            print(f"     this product's accuracy requirement is what it gave "
                  f"up. The")
            print(f"     lever that made the model fit is the one that made "
                  f"it unusable.")
    print(f"\n     ACCURACY COST IS ASSUMED, NOT COMPUTED. The figures used "
          f"are")
    print(f"     " + ", ".join(f"{k} {v:g}pp"
                               for k, v in QUANT_ACCURACY_COST_PP.items())
          + ".")
    print(f"     What a network actually loses depends on the network, the")
    print(f"     calibration and the method, and this model has no basis for")
    print(f"     any of them. Replace them with measured figures before "
          f"quoting")
    print(f"     any of the verdicts above.")
    print(LINE)
    return rows


# ==============================================================================
# Batch and concurrent users
# ==============================================================================
#
# The one structural fact that makes an LLM server different from a single
# user's machine: the WEIGHTS ARE SHARED and the CACHE IS NOT. Sixteen users
# read the same seventy gigabytes of weights once per step and carry sixteen
# separate caches, so the cost per user falls and the memory per user does not.
#
# That asymmetry explains almost everything about how these machines are
# sized, and a single-stream model cannot show it.

def batch_sweep(app_key: str, config,
                batches=(1, 2, 4, 8, 16, 32, 64, 128)) -> list:
    """More users at once: what is shared, what is not, and what it costs."""
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .system import evaluate_system, show
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    mem = MEMORY_LIBRARY[config.memory]
    installed = mem.capacity_gbyte * config.memory_devices
    rows = []
    # The per-user cache is derived from the per-token cost and the context,
    # not from the application's kv_cache_bytes - that figure is described in
    # the library as an aggregate for batched serving, and using it as a
    # per-user number would multiply an already-multiplied quantity.
    per_user_kv = app.kv_bytes_per_token * app.context_tokens

    for b in batches:
        # The weights are read ONCE per step however many users are served.
        # The cache, the activations and the arithmetic all scale with the
        # batch, and so does the traffic that is not weights.
        tuned = dataclasses.replace(
            app,
            kv_cache_bytes=per_user_kv * b,
            kv_bytes_per_token=app.kv_bytes_per_token * b,
            activation_bytes=app.activation_bytes * b,
            mac_per_inference=app.mac_per_inference * b,
            target_inferences_per_s=app.target_inferences_per_s,
            key="__batch__")
        APPLICATION_LIBRARY["__batch__"] = tuned
        try:
            r = evaluate_system(tuned, config)
            m = r.metrics
            feasible = "INFEASIBLE" not in r.status
            rows.append({
                "b": b,
                "kv_gb": per_user_kv * b / 1e9,
                "total_gb": (app.weight_bytes + per_user_kv * b
                             + app.runtime_overhead_bytes) / 1e9,
                "step_ms": m["Latency (ms)"],
                "per_user": m["Single-job rate (inf/s)"],
                "aggregate": (m["Single-job rate (inf/s)"] * b
                              if feasible else float("nan")),
                "weight_mb": m.get("  weight traffic (MB)", float("nan")),
                "traffic_mb": m["DRAM traffic (MB)"],
                "power": m["System power (W)"],
                "feasible": feasible,
                "passes": r.passes,
            })
        finally:
            APPLICATION_LIBRARY.pop("__batch__", None)

    print(f"\n{LINE}")
    print(f" BATCH SWEEP - {app.name}")
    print(LINE)
    print(f"  memory        {mem.name} x{config.memory_devices} "
          f"= {installed:.0f} GB")
    print(f"  weights       {app.weight_bytes / 1e9:.0f} GB, SHARED by every "
          f"user in the batch")
    print(f"  cache         {per_user_kv / 1e9:.2f} GB PER USER at "
          f"{app.context_tokens} tokens of context\n")
    head = (f"  {'users':>7s}{'cache':>9s}{'total':>9s}{'fits':>6s}"
            f"{'step ms':>10s}{'tok/s each':>13s}{'tok/s total':>13s}"
            f"{'traffic MB':>12s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for r in rows:
        if not r["feasible"]:
            print(f"  {r['b']:>7d}{r['kv_gb']:>8.1f}G{r['total_gb']:>8.0f}G"
                  f"{'NO':>6s}{'model does not fit':>48s}")
            continue
        print(f"  {r['b']:>7d}{r['kv_gb']:>8.1f}G{r['total_gb']:>8.0f}G"
              f"{'yes':>6s}{r['step_ms']:>10.1f}{r['per_user']:>13.2f}"
              f"{r['aggregate']:>13.1f}{r['traffic_mb']:>12.0f}")

    usable = [r for r in rows if r["feasible"]]
    print(f"\n  -- what batching is trading -------------------------------")
    if len(usable) >= 2:
        a0, a1 = usable[0], usable[-1]
        print(f"     Serving {a1['b']} users instead of {a0['b']} multiplies "
              f"the total rate by")
        print(f"     {a1['aggregate'] / a0['aggregate']:.1f}x and divides each "
              f"user's rate by "
              f"{a0['per_user'] / a1['per_user']:.1f}x. Every user waits")
        print(f"     longer and the machine does far more work, which is the "
              f"whole")
        print(f"     of why a server batches and a phone does not.")
        traffic_per_user = [r["traffic_mb"] / r["b"] for r in usable]
        print(f"\n     Traffic per user falls from "
              f"{traffic_per_user[0]:,.0f} MB to {traffic_per_user[-1]:,.0f} "
              f"MB")
        print(f"     because the weights are read once for the whole batch. "
              f"That is")
        print(f"     the entire economic case for batching, and it is a "
              f"property of")
        print(f"     the MEMORY rather than of the arithmetic.")
    infeasible = [r for r in rows if not r["feasible"]]
    if infeasible:
        print(f"\n     But the cache does not share. At {infeasible[0]['b']} "
              f"users it alone is")
        print(f"     {infeasible[0]['kv_gb']:.0f} GB and the model stops "
              f"fitting - which is why a server")
        print(f"     runs out of USERS before it runs out of speed.")
    failing = [r for r in usable if not r["passes"]]
    if failing and usable[0]["passes"]:
        print(f"\n     And {failing[0]['b']} users already breaks a "
              f"requirement while still")
        print(f"     fitting: a batch large enough to be efficient can be too")
        print(f"     large to be responsive.")
    print(f"\n  This sweep holds the CONTEXT fixed. Long conversations and "
          f"many")
    print(f"  users multiply, so a product that serves both needs the two")
    print(f"  sweeps read together rather than one at a time.")
    print(LINE)
    return rows


# ==============================================================================
# Model size, prompt ratio, and mixture-of-experts
# ==============================================================================

# Parameter counts, and the bytes they occupy at a given width. A student who
# has only ever seen "70B" does not know what that costs until it is a number
# of gigabytes on a board that either holds it or does not.
MODEL_SIZES = {
    "1B": 1e9, "3B": 3e9, "7B": 7e9, "13B": 13e9,
    "30B": 30e9, "70B": 70e9, "100B": 100e9,
}


def model_size_sweep(app_key: str, config, precision: str = "FP16",
                     sizes=None) -> list:
    """The same board against seven model sizes."""
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .system import evaluate_system, show
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    mem = MEMORY_LIBRARY[config.memory]
    installed = mem.capacity_gbyte * config.memory_devices
    bytes_per_param = QUANT_BYTES[precision]
    sizes = sizes or MODEL_SIZES
    # Scale the arithmetic and the cache with the parameter count, holding
    # the shape of the workload fixed - the point of this sweep is size.
    ref_params = 70e9
    rows = []
    for label, params in sizes.items():
        scale = params / ref_params
        tuned = dataclasses.replace(
            app,
            weight_bytes=params * bytes_per_param,
            mac_per_inference=app.mac_per_inference * scale,
            kv_cache_bytes=app.kv_cache_bytes * scale,
            kv_bytes_per_token=app.kv_bytes_per_token * scale,
            key="__sz__")
        APPLICATION_LIBRARY["__sz__"] = tuned
        try:
            r = evaluate_system(tuned, config)
            rows.append({
                "label": label, "params": params,
                "weights_gb": params * bytes_per_param / 1e9,
                "total_gb": (params * bytes_per_param + tuned.kv_cache_bytes
                             + app.runtime_overhead_bytes) / 1e9,
                "tokens": r.metrics["Single-job rate (inf/s)"],
                "feasible": "INFEASIBLE" not in r.status,
                "passes": r.passes,
                "failed": [g for g, ok in r.gate.items() if not ok],
            })
        finally:
            APPLICATION_LIBRARY.pop("__sz__", None)

    print(f"\n{LINE}")
    print(f" MODEL SIZE SWEEP - {precision} on {mem.name} "
          f"x{config.memory_devices} = {installed:.0f} GB")
    print(LINE)
    head = (f"  {'model':>8s}{'weights':>10s}{'total':>9s}{'fits':>7s}"
            f"{'tokens/s':>16s}{'ships':>8s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for r in rows:
        print(f"  {r['label']:>8s}{r['weights_gb']:>9.0f}G{r['total_gb']:>8.0f}G"
              f"{('yes' if r['feasible'] else 'NO'):>7s}"
              f"{show(r['tokens'], '{:.1f}'):>16s}"
              f"{('yes' if r['passes'] else 'no'):>8s}")

    fits = [r for r in rows if r["feasible"]]
    ships = [r for r in rows if r["passes"]]
    print(f"\n  -- reading it ---------------------------------------------")
    if fits:
        print(f"     This board holds up to {fits[-1]['label']} at "
              f"{precision}. Beyond that the")
        print(f"     answer is not 'slower' - there is no answer.")
    if ships and len(ships) < len(fits):
        first_lost = next(r for r in fits if not r["passes"])
        print(f"     It SHIPS up to {ships[-1]['label']}. At "
              f"{first_lost['label']} the model still fits and")
        print(f"     fails on {', '.join(first_lost['failed'])} - fitting and "
              f"shipping are")
        print(f"     different questions and they part company before the "
              f"capacity does.")
    print(f"\n     At {precision} a parameter costs "
          f"{QUANT_BYTES[precision]:g} bytes, so a model's size in")
    print(f"     gigabytes is its parameter count times that and nothing "
          f"else.")
    print(f"     Halving the width moves every row in this table up one line.")
    print(LINE)
    return rows


def prompt_ratio_sweep(app_key: str, config,
                       prompts=(32, 128, 512, 2048, 8192)) -> list:
    """Prefill and decode are different machines' problems."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    rows = []
    for p in prompts:
        tuned = dataclasses.replace(app, prefill_tokens=p, key="__pf__")
        APPLICATION_LIBRARY["__pf__"] = tuned
        try:
            m = evaluate_system(tuned, config).metrics
            # Prefill processes the whole prompt in one pass: its arithmetic
            # is the per-token cost times the prompt, and the weights are read
            # ONCE for all of it. So its time follows the compute rate, where
            # decode's follows the memory rate.
            prefill_mac = tuned.mac_per_inference * p
            compute_rate = (tuned.mac_per_inference / (m["Compute time (ms)"] / 1e3)
                            if m["Compute time (ms)"] > 0 else 0.0)
            prefill_ms = (prefill_mac / compute_rate * 1e3
                          if compute_rate > 0 else float("nan"))
            rows.append({
                "prompt": p,
                "prefill_mac": prefill_mac,
                "prefill_ms": prefill_ms,
                "per_token": m["Latency (ms)"],
                "ratio": prefill_ms / m["Latency (ms)"] if m["Latency (ms)"] else 0.0,
                "compute": m["Compute time (ms)"],
                "memory": m["Memory time (ms)"],
            })
        finally:
            APPLICATION_LIBRARY.pop("__pf__", None)

    print(f"\n{LINE}")
    print(f" PROMPT LENGTH SWEEP - {app.name}")
    print(LINE)
    print(f"  Prefill reads the prompt and is COMPUTE bound: every token "
          f"attends")
    print(f"  to every earlier one and the weights are read once for all of")
    print(f"  them. Decode emits one token at a time and is MEMORY bound: the")
    print(f"  same weights are read again for each.\n")
    head = (f"  {'prompt':>9s}{'prefill GMAC':>15s}{'prefill ms':>13s}"
            f"{'decode ms/token':>18s}{'tokens of answer':>19s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for r in rows:
        print(f"  {r['prompt']:>9d}{r['prefill_mac'] / 1e9:>15.0f}"
              f"{r['prefill_ms']:>13.1f}{r['per_token']:>18.2f}"
              f"{r['ratio']:>18.0f}")

    print(f"\n  The last column is how many tokens of answer it takes for "
          f"decode")
    print(f"  to cost as much as the prompt did. Below that number the "
          f"product")
    print(f"  is a PREFILL machine; above it, a DECODE machine.")
    print(f"\n  -- reading it ---------------------------------------------")
    print(f"     The prefill arithmetic rises with the prompt and the decode")
    print(f"     time does not - they are two different workloads sharing one")
    print(f"     machine, and a design tuned for one is not tuned for the")
    print(f"     other.")
    print(f"     A long prompt with a short answer is a compute problem. A")
    print(f"     short prompt with a long answer is a memory problem. Most")
    print(f"     products are somewhere between and the ratio decides which")
    print(f"     hardware wins.")
    print(f"\n     NOT MODELLED: this simulator has ONE accelerator path per")
    print(f"     inference, so it cannot send prefill to one machine and")
    print(f"     decode to another - which is exactly what a large deployment")
    print(f"     does, and exactly because the two differ this much.")
    print(LINE)
    return rows


def moe_comparison(app_key: str, config, total_params: float = 120e9,
                   active_params: float = 12e9,
                   precision: str = "FP16") -> dict:
    """Dense against mixture-of-experts: memory follows total, compute active."""
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .system import evaluate_system, show
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    mem = MEMORY_LIBRARY[config.memory]
    installed = mem.capacity_gbyte * config.memory_devices
    bpp = QUANT_BYTES[precision]
    ref = 70e9

    out = {}
    for label, params_stored, params_used in (
            ("dense, active size", active_params, active_params),
            ("dense, total size", total_params, total_params),
            ("mixture of experts", total_params, active_params)):
        tuned = dataclasses.replace(
            app,
            weight_bytes=params_stored * bpp,
            # Only the experts actually selected do arithmetic, and only their
            # weights are READ - but every expert must be resident, because
            # which ones are needed is not known until the token arrives.
            mac_per_inference=app.mac_per_inference * (params_used / ref),
            weight_read_factor=app.weight_read_factor
            * (params_used / params_stored),
            key="__moe__")
        APPLICATION_LIBRARY["__moe__"] = tuned
        try:
            r = evaluate_system(tuned, config)
            out[label] = {
                "stored_gb": params_stored * bpp / 1e9,
                "used_gb": params_used * bpp / 1e9,
                "tokens": r.metrics["Single-job rate (inf/s)"],
                "traffic_mb": r.metrics["DRAM traffic (MB)"],
                "feasible": "INFEASIBLE" not in r.status,
                "result": r,
            }
        finally:
            APPLICATION_LIBRARY.pop("__moe__", None)

    print(f"\n{LINE}")
    print(f" DENSE AGAINST MIXTURE OF EXPERTS")
    print(LINE)
    print(f"  memory        {mem.name} x{config.memory_devices} "
          f"= {installed:.0f} GB")
    print(f"  total         {total_params / 1e9:.0f}B parameters")
    print(f"  active        {active_params / 1e9:.0f}B per token\n")
    head = (f"  {'design':<22s}{'stored':>9s}{'read/token':>13s}"
            f"{'fits':>7s}{'tokens/s':>16s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for label, r in out.items():
        print(f"  {label:<22s}{r['stored_gb']:>8.0f}G{r['used_gb']:>12.0f}G"
              f"{('yes' if r['feasible'] else 'NO'):>7s}"
              f"{show(r['tokens'], '{:.1f}'):>16s}")

    print(f"\n  -- what a mixture of experts actually changes --------------")
    print(f"     Memory follows the TOTAL and arithmetic follows the ACTIVE.")
    print(f"     Every expert has to be resident, because which ones a token")
    print(f"     needs is not known until it arrives - so an MoE costs a "
          f"large")
    print(f"     model's memory and a small model's compute.")
    moe, small, big = (out["mixture of experts"],
                       out["dense, active size"], out["dense, total size"])
    print(f"\n     It reads {moe['used_gb']:.0f} GB per token like the "
          f"{small['stored_gb']:.0f}B dense model and")
    print(f"     stores {moe['stored_gb']:.0f} GB like the "
          f"{big['stored_gb']:.0f}B one. A student who sizes the board from")
    print(f"     the token rate will under-provision it by "
          f"{moe['stored_gb'] / moe['used_gb']:.0f} times.")
    print(f"\n     ROUTING IS NOT MODELLED. A real MoE also pays to choose "
          f"the")
    print(f"     experts, and its traffic depends on how well consecutive "
          f"tokens")
    print(f"     reuse the same ones - which this model does not represent at")
    print(f"     all. The memory-against-compute asymmetry above is the part")
    print(f"     that is structural; the rest is not here.")
    print(LINE)
    return out
