"""
ppact.migration - what must be true when a design moves

A student's work is almost never a design from nothing. It is a MOVE: the host
was doing the arithmetic and now an accelerator is, or there was one engine and
now there are two, or the memory changed. Each move has consequences that
follow from the structure and cannot be otherwise, and consequences that depend
on the workload and can go either way.

Separating those two is most of the teaching, and it is also a strong internal
test. An invariant that must hold is a claim about the model that does not
need calibration to check, and there are more of them here than anywhere else
in the package - a migration touches compute, memory, power, area and cost at
once, so a defect in any of them shows up as a broken relation rather than as
an odd number.

    MUST      follows from the structure. A violation is a defect.
    USUALLY   holds for most workloads and not all. A violation is a finding
              to explain, and several of the most useful teaching results in
              this course are exactly these.
    DEPENDS   genuinely either way. Stating it prevents a student from reading
              one run as a rule.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

LINE = "=" * 80

STRENGTHS = ("MUST", "USUALLY", "DEPENDS")


@dataclass(frozen=True)
class Claim:
    strength: str
    metric: str
    direction: str            # "up" | "down" | "same" | "any"
    because: str


@dataclass
class Migration:
    mid: str
    title: str
    description: str
    claims: Tuple[Claim, ...]
    # (application key, before config, after config)
    build: Callable
    teaching_point: str = ""


def _cfg(cpu, comp, mem, n, **kw):
    from .system import SystemConfig
    return SystemConfig(cpu, comp, mem, n, **kw)


def _host_to_accelerator():
    return ("smart_camera",
            _cfg("cortex_a53_x4", "cpu_only", "LPDDR5", 1,
                 preprocessing_mode="cpu_only"),
            _cfg("cortex_a53_x4", "npu_16x16", "LPDDR5", 1,
                 preprocessing_mode="cpu_only"))


def _gpu_to_npu():
    return ("industrial_vision",
            _cfg("cortex_a78_x4", "mobile_gpu", "LPDDR5", 4,
                 preprocessing_mode="isp_assisted"),
            _cfg("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                 preprocessing_mode="isp_assisted"))


def _single_to_dual():
    return ("industrial_vision",
            _cfg("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                 preprocessing_mode="isp_and_npu"),
            _cfg("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                 preprocessing_mode="isp_and_npu",
                 secondary_compute="npu_32x32", execution_mode="parallel",
                 work_split=0.5))


def _host_to_isp():
    return ("industrial_vision",
            _cfg("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                 preprocessing_mode="cpu_only"),
            _cfg("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                 preprocessing_mode="isp_assisted"))


def _narrow_to_wide_memory():
    # The baseline was one LPDDR5 package - 4 GB against a 5 GB requirement,
    # so it could not hold the model and every figure measured from it
    # described a machine that cannot exist. Found at 3.67.0 when an
    # infeasible configuration stopped returning usable numbers.
    return ("mobile_ai",
            _cfg("cortex_a78_x4", "npu_64x64", "LPDDR5", 2),
            _cfg("cortex_a78_x4", "npu_64x64", "LPDDR5", 8))


def _weak_to_strong_host():
    return ("industrial_vision",
            _cfg("cortex_a53_x4", "npu_32x32", "LPDDR5", 4,
                 preprocessing_mode="cpu_only"),
            _cfg("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                 preprocessing_mode="cpu_only"))


def _smaller_node():
    return ("drone",
            _cfg("cortex_a78_x4", "npu_24x24", "LPDDR5", 2, accel_node="N16"),
            _cfg("cortex_a78_x4", "npu_24x24", "LPDDR5", 2, accel_node="N5"))


MIGRATIONS: List[Migration] = [
    Migration(
        "MIG-01", "host arithmetic to an accelerator",
        "The CPU was running the network. Now a fixed-function array is.",
        (Claim("MUST", "Logic silicon (mm2)", "up",
               "an array that did not exist now does"),
         Claim("MUST", "Compute time (ms)", "down",
               "the array does more multiply-accumulates per second than the "
               "host, which is the only reason to add it"),
         Claim("USUALLY", "System cost (USD)", "up",
               "silicon costs money, though on a cheap product the die can be "
               "a rounding error against the bill of materials"),
         Claim("USUALLY", "Energy per inference (mJ)", "down",
               "a fixed-function array spends far less energy per operation "
               "than a general-purpose core"),
         Claim("DEPENDS", "System power (W)", "any",
               "energy per inference falls and the rate rises; which wins "
               "depends on whether the product is throughput-limited or "
               "duty-cycled"),
         Claim("DEPENDS", "Deployment accuracy (%)", "any",
               "an accelerator usually quantises and a host usually does not, "
               "but a host running INT8 and an array running QAT can go "
               "either way")),
        _host_to_accelerator,
        "The move that looks obvious. What is NOT obvious is that the host "
        "keeps its preprocessing, so the latency does not fall by the ratio "
        "of the arithmetic rates."),

    Migration(
        "MIG-02", "general-purpose GPU to a fixed-function array",
        "Same workload, an engine built for it instead of one that can do "
        "anything.",
        (Claim("MUST", "Peak TOPS", "any",
               "nothing forces the array to be larger or smaller than the GPU "
               "it replaces - this is a choice, not a consequence"),
         Claim("USUALLY", "Energy per inference (mJ)", "down",
               "no scheduler, no register file per lane, no caches on the "
               "critical path"),
         Claim("USUALLY", "System cost (USD)", "down",
               "a systolic array spends its silicon on multipliers and a "
               "shader array spends much of it on flexibility"),
         Claim("USUALLY", "Deployment accuracy (%)", "down",
               "the array quantises where the GPU could have run FP16"),
         Claim("DEPENDS", "Latency (ms)", "any",
               "entirely a question of which engine is larger; a small array "
               "replacing a large GPU is slower and that is a valid design")),
        _gpu_to_npu,
        "The trade is efficiency for flexibility, and the accuracy line is "
        "where it is paid. A student who reads only latency will miss it."),

    Migration(
        "MIG-03", "one accelerator to two",
        "The same model split across two engines running in parallel.",
        (Claim("MUST", "Logic silicon (mm2)", "up",
               "a second die is a second die"),
         Claim("MUST", "System cost (USD)", "up",
               "and it costs money whether or not it is used"),
         Claim("MUST", "Compute time (ms)", "down",
               "half the arithmetic each, and the model is the same model - a "
               "split that did not halve the compute would mean the work was "
               "not actually divided"),
         Claim("DEPENDS", "Latency (ms)", "any",
               "the hand-off and the shared memory can cost more than the "
               "split saves - on a narrow bus they usually do"),
         Claim("DEPENDS", "Throughput (inf/s)", "any",
               "a pipeline gains from two stations, and loses if memory was "
               "already the limit")),
        _single_to_dual,
        "The clearest case of an addition that can make a system worse. Two "
        "engines on one memory bus is a different machine from two engines."),

    Migration(
        "MIG-04", "host preprocessing to a fixed-function block",
        "The per-pixel work moves off the CPU.",
        (Claim("MUST", "CPU active (ms)", "down",
               "the host stops doing the per-pixel work"),
         Claim("MUST", "Logic silicon (mm2)", "up",
               "a fixed-function block occupies area whether or not its latency "
               "is hidden, and that area does not depend on how much work it "
               "is given"),
         Claim("USUALLY", "Latency (ms)", "down",
               "on anything above about 300k pixels; below that the dispatch "
               "costs more than the work"),
         Claim("DEPENDS", "System power (W)", "any",
               "the block draws power even when its latency is fully hidden")),
        _host_to_isp,
        "The break-even is a frame size, not a principle. The same move is "
        "worth 44% on a 5 MP stream and nothing at all on a 640x480 one."),

    Migration(
        "MIG-05", "narrow memory to wide",
        "More channels of the same memory.",
        (Claim("MUST", "Effective bandwidth (GB/s)", "up",
               "more channels move more bytes"),
         Claim("MUST", "System cost (USD)", "up",
               "more memory packages, each with its own silicon, substrate and test "
               "cost - a controller does not get cheaper by driving more "
               "of them"),
         Claim("MUST", "Compute time (ms)", "same",
               "the arithmetic did not change, and a model where it does has "
               "a defect"),
         Claim("USUALLY", "Latency (ms)", "down",
               "unless the design was compute bound, in which case nothing "
               "moves"),
         Claim("DEPENDS", "Throughput (inf/s)", "any",
               "only if memory was the pipeline's limiting station")),
        _narrow_to_wide_memory,
        "The move that shows what 'bound by' means. On a compute-bound design "
        "it buys cost and nothing else."),

    Migration(
        "MIG-07", "a weaker host to a stronger one",
        "The accelerator is unchanged. Only the CPU doing the preprocessing, "
        "the dispatch and the post-processing gets faster.",
        (Claim("MUST", "Compute time (ms)", "same",
               "the accelerator did not change, and a model where its "
               "arithmetic moves with the host has something wired wrong"),
         Claim("MUST", "CPU active (ms)", "down",
               "more cores at a higher clock get through the same per-pixel "
               "and per-element work in fewer seconds"),
         Claim("MUST", "Logic silicon (mm2)", "up",
               "a bigger core cluster with bigger caches occupies more area, "
               "and the caches shrink at SRAM rates rather than logic rates"),
         Claim("USUALLY", "Latency (ms)", "down",
               "on any design where the host was doing real work; on one "
               "where the accelerator dominates, nothing moves"),
         Claim("USUALLY", "System cost (USD)", "up",
               "a larger host die costs more, though on a product with a "
               "large bill of materials it can be a small share of it"),
         Claim("DEPENDS", "System power (W)", "any",
               "the host draws more while active and finishes sooner, and "
               "which wins depends on how much of the frame it was holding"),
         Claim("DEPENDS", "Throughput (inf/s)", "any",
               "only if the host was the pipeline's limiting station")),
        _weak_to_strong_host,
        "The move that is invisible on a well-balanced design and decisive on "
        "an unbalanced one. A student who reads only the accelerator's "
        "specification will not see it coming."),

    Migration(
        "MIG-06", "an older process node to a newer one",
        "The same design, fabricated smaller.",
        (Claim("MUST", "Logic silicon (mm2)", "down",
               "the cells are smaller, though SRAM shrinks at roughly half the rate "
               "of logic so an array that is mostly memory shrinks less "
               "than the node number suggests"),
         Claim("MUST", "Compute time (ms)", "down",
               "the clock ceiling is higher"),
         Claim("USUALLY", "System cost (USD)", "up",
               "a smaller die on a much more expensive wafer at a lower yield "
               "is usually a worse deal, which is the opposite of what most "
               "people expect"),
         Claim("USUALLY", "Energy per inference (mJ)", "down",
               "less energy per switch, though SRAM leakage improves far more "
               "slowly than logic and can offset it on an array that is mostly "
               "memory"),
         # Not a DEPENDS. A node changes how fast and how small, never what
         # the network computes, so accuracy moving here would be a defect.
         Claim("MUST", "Deployment accuracy (%)", "same",
               "a process node does not change what the model computes - if "
               "accuracy moves here, a path is wired wrong")),
        _smaller_node,
        "The result students find hardest to believe: shrinking usually makes "
        "a chip more expensive, because SRAM barely shrinks and wafers cost "
        "far more."),
]

BY_ID = {m.mid: m for m in MIGRATIONS}


# A MUST claim is about the SIGN. A change of 0.47% is a rise, and reading it
# as "unchanged" because it is small turned a correct model into a reported
# defect - the accelerator die is simply a small share of a cheap product's
# bill of materials, which is a finding rather than a violation.
#
# A USUALLY claim is about a change big enough to design around, so it keeps a
# visibility threshold and gains a third outcome: essentially unchanged, which
# is neither holding nor failing.
TOLERANCE = {"MUST": 1e-12, "USUALLY": 0.005, "DEPENDS": 0.005}


def _direction(before, after, tol=0.005):
    if before == 0:
        return "same" if after == 0 else ("up" if after > 0 else "down")
    change = (after - before) / abs(before)
    if abs(change) < tol:
        return "same"
    return "up" if change > 0 else "down"


def describe_change(before, after) -> List[str]:
    """Which fields actually differ. Empty means nothing was changed."""
    import dataclasses as _dc
    diffs = []
    for f in _dc.fields(before):
        a, b = getattr(before, f.name), getattr(after, f.name)
        if a != b:
            diffs.append(f"{f.name}: {a} -> {b}")
    return diffs


def check_migration(mid: str, verbose: bool = True) -> List[tuple]:
    """Run one migration and test every claim it makes."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    m = BY_ID[mid]
    app_key, before_cfg, after_cfg = m.build()
    # A move from a configuration to itself is not a move. Reporting "no
    # change" for it looks like a finding about the move rather than about
    # the setup, and a locked prediction at 3.75.0 was wrong for exactly this
    # reason - it proposed 3 nm for a design already on 3 nm.
    if before_cfg == after_cfg:
        if verbose:
            print(f"\n{LINE}")
            print(f" {m.mid}  {m.title}")
            print(LINE)
            print("  NO MIGRATION OCCURRED - the source and target "
                  "configurations")
            print("  are identical. Every claim below would be trivially true "
                  "and")
            print("  none of them would be about the move.")
            print(LINE)
        return []
    app = APPLICATION_LIBRARY[app_key]
    a = evaluate_system(app, before_cfg).metrics
    b = evaluate_system(app, after_cfg).metrics

    results = []
    for c in m.claims:
        if c.metric not in a or c.metric not in b:
            results.append((c, None, None, "metric absent"))
            continue
        got = _direction(a[c.metric], b[c.metric], TOLERANCE[c.strength])
        pct = ((b[c.metric] - a[c.metric]) / abs(a[c.metric]) * 100
               if a[c.metric] else 0.0)
        if c.direction == "any":
            state = "as stated"
        elif got == c.direction:
            state = "holds"
        elif c.strength == "MUST":
            state = "VIOLATED"
        elif got == "same":
            # Right sign, too small to matter, or genuinely flat. Saying it
            # failed would overstate; saying it held would hide that a student
            # cannot design around it.
            state = "too small to matter"
        else:
            state = "does not hold"
        results.append((c, got, pct, state))

    if verbose:
        print(f"\n{LINE}")
        print(f" {m.mid}  {m.title}")
        print(LINE)
        print(f"  {m.description}\n")
        head = (f"  {'':<9s}{'metric':<28s}{'expected':<10s}{'got':<8s}"
                f"{'change':>9s}   status")
        print(head); print("  " + "-" * (len(head) - 2))
        for c, got, pct, state in results:
            gs = got or "-"
            ps = "-" if pct is None else f"{pct:+.1f}%"
            print(f"  {c.strength:<9s}{c.metric:<28s}{c.direction:<10s}"
                  f"{gs:<8s}{ps:>9s}   {state}")
        print()
        for c, got, pct, state in results:
            if state == "too small to matter":
                print(f"  {c.metric} moved {pct:+.2f}% - the right way, and "
                      f"not by enough")
                print(f"    to design around. {c.because}")
            if state in ("VIOLATED", "does not hold"):
                print(f"  {c.metric} went {got}, and the claim was {c.direction}.")
                print(f"    because: {c.because}")
        if m.teaching_point:
            print(f"\n  {m.teaching_point}")
        print(LINE)
    return results


def check_all(verbose: bool = False) -> None:
    """Every migration, with the MUST violations called out."""
    print(f"\n{LINE}")
    print(" MIGRATION CLAIMS")
    print(LINE)
    print("  MUST claims follow from the structure - a violation is a defect.")
    print("  USUALLY claims hold for most workloads; where one fails, the")
    print("  reason is usually the most interesting thing in the run.\n")
    head = (f"  {'id':<8s}{'migration':<42s}{'MUST':>6s}{'USUALLY':>9s}"
            f"{'DEPENDS':>9s}")
    print(head); print("  " + "-" * (len(head) - 2))
    violations = []
    soft = []
    tiny = []
    for m in MIGRATIONS:
        res = check_migration(m.mid, verbose=False)
        counts = {s: [0, 0] for s in STRENGTHS}
        for c, got, pct, state in res:
            counts[c.strength][1] += 1
            if state in ("holds", "as stated"):
                counts[c.strength][0] += 1
            elif state == "VIOLATED":
                violations.append((m.mid, c, got))
            elif state == "too small to matter":
                counts[c.strength][0] += 1
                tiny.append((m.mid, c, pct))
            else:
                soft.append((m.mid, c, got))
        print(f"  {m.mid:<8s}{m.title:<42s}"
              + "".join(f"{counts[s][0]}/{counts[s][1]:<5}" for s in STRENGTHS))

    print()
    print(f"  MUST CLAIMS: ", end="")
    if violations:
        print(f"{len(violations)} VIOLATED - these are defects:")
        for mid, c, got in violations:
            print(f"    {mid}  {c.metric} went {got}, must be {c.direction}")
            print(f"          {c.because}")
    else:
        print("none violated.")
    if soft:
        print(f"\n  {len(soft)} USUALLY claim(s) did not hold. Each is a "
              f"finding, not a defect:")
        for mid, c, got in soft:
            print(f"    {mid}  {c.metric} went {got}, usually {c.direction}")
    if tiny:
        print(f"\n  {len(tiny)} claim(s) held in sign but moved too little to "
              f"design around:")
        for mid, c, pct in tiny:
            print(f"    {mid}  {c.metric} {pct:+.2f}%")
        print("    On a cheap product the accelerator die is a rounding error")
        print("    against the bill of materials. That is a real result and it")
        print("    surprises most people, so it is reported rather than")
        print("    rounded into agreement.")
    print(LINE)


# ==============================================================================
# The node choice
# ==============================================================================
#
# A process node is a design variable like any other, and the one where
# intuition fails hardest. Every axis except cost improves monotonically as the
# node shrinks, and cost turns around - so the cheapest node is not the
# smallest, and where it turns depends on the design.

def node_sweep(app_key: str, config, show: bool = True) -> List[tuple]:
    """The same design on every node in the library.

    Both the accelerator and the host move together. Holding one fixed while
    the other shrinks would answer a question nobody asks.
    """
    from .application import APPLICATION_LIBRARY
    from .process import NODE_LIBRARY
    from .system import evaluate_system
    import dataclasses

    app = APPLICATION_LIBRARY[app_key]
    rows = []
    for name in NODE_LIBRARY:
        cfg = dataclasses.replace(config, accel_node=name, soc_node=name)
        r = evaluate_system(app, cfg)
        m = r.metrics
        rows.append((name, m["Peak TOPS"], m["Logic silicon (mm2)"],
                     m["Latency (ms)"], m["System power (W)"],
                     m["Energy per inference (mJ)"], m["System cost (USD)"],
                     r.passes, m["Logic die cost (USD)"]))
    if not show:
        return rows

    cheapest = min(rows, key=lambda r: r[6])
    smallest = rows[-1]
    print(f"\n{LINE}")
    print(f" PROCESS NODE SWEEP - {app.name}")
    print(LINE)
    from .process import get_node
    head = (f"  {'node':<20s}{'TOPS':>8s}{'silicon':>9s}{'latency':>9s}"
            f"{'mJ/inf':>9s}{'die $':>9s}{'system $':>10s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for name, tops, area, lat, pw, mj, cost, ok, die in rows:
        mark = "  <- lowest recurring" if name == cheapest[0] else ""
        nd = get_node(name)
        label = f"{name} {nd.display or nd.label}"[:19]
        print(f"  {label:<20s}{tops:>8.2f}{area:>9.2f}{lat:>9.3f}"
              f"{mj:>9.2f}{die:>9.3f}{cost:>10.2f}{mark}")

    # The die and the system move by very different amounts, and reporting
    # only one of them misleads in opposite directions.
    base_die, base_sys = rows[0][8], rows[0][6]
    ch_die, ch_sys = cheapest[8], cheapest[6]
    print(f"\n  From {rows[0][0]} to {cheapest[0]}: the logic die costs "
          f"{(ch_die / base_die - 1) * 100:+.1f}% and the")
    print(f"  whole system {(ch_sys / base_sys - 1) * 100:+.1f}%. A node moves "
          f"SILICON and nothing else -")
    print(f"  memory, package, board and assembly are unchanged - so on a "
          f"product")
    print(f"  where the die is a small part of the bill of materials, a large "
          f"die")
    print(f"  saving is a small system saving. Both figures are needed: the "
          f"first")
    print(f"  says what the node did, the second what the product gets.")

    print(f"\n  Every axis except cost improves as the node shrinks. Cost turns")
    print(f"  around: under THIS library's wafer prices and yields, the lowest")
    print(f"  RECURRING MANUFACTURING cost for THIS design is {cheapest[0]} at "
          f"{cheapest[6]:,.2f},")
    print(f"  and the smallest node")
    print(f"  {smallest[0]} costs {smallest[6]:,.2f} - "
          f"{(smallest[6] / cheapest[6] - 1) * 100:.0f}% more for "
          f"{(1 - smallest[2] / cheapest[2]) * 100:.0f}% less silicon. That is "
          f"not a")
    print(f"  statement about what node a commercial part should use: wafer")
    print(f"  prices and yields here are estimates, and a real programme "
          f"weighs")
    print(f"  volume and schedule that this table does not carry.")
    print(f"\n  And it is RECURRING cost only. A mask set, six months of "
          f"physical")
    print(f"  implementation, verification, IP porting and a re-spin allowance "
          f"are")
    print(f"  paid once and rise steeply with the node, so the cheapest node "
          f"to")
    print(f"  MANUFACTURE is often not the cheapest node to SHIP. "
          f"ppact.economics")
    print(f"  amortises them over a volume and answers that question instead.")
    print(f"\n  WHERE the turn happens depends on how much of the die is SRAM,")
    print(f"  because SRAM shrinks at roughly half the rate of logic. Silicon")
    print(f"  cost per unit of function, normalised:")
    _print_turn_curve()
    print(f"  An all-logic die turns at N7 and a mostly-SRAM one at N12. Every")
    print(f"  accelerator in this library sits near two thirds SRAM, which")
    print(f"  lands them all on the same side, so the turn does NOT move")
    print(f"  between the designs here. It would for a part with a different")
    print(f"  mix - the mechanism is real and this library does not exercise")
    print(f"  it, which is worth knowing before carrying the answer anywhere.")
    print(LINE)
    return rows


def turn_curve() -> Dict[str, Dict[str, float]]:
    """Silicon cost per unit of function, by node and by SRAM fraction.

    The mechanism behind the cost turn, isolated from any particular design:
    area times price over yield, for a die that is all logic, half SRAM, or
    almost all SRAM.
    """
    from .process import NODE_LIBRARY, get_node
    out = {}
    for name in NODE_LIBRARY:
        n = get_node(name)
        out[name] = {}
        for frac, label in ((0.0, "all logic"), (0.5, "half"),
                            (0.95, "mostly SRAM")):
            area = (1 - frac) * n.logic_area + frac * n.sram_area
            out[name][label] = area * n.usd_per_mm2 / n.yield_factor
    return out


def _print_turn_curve() -> None:
    curve = turn_curve()
    labels = ("all logic", "half", "mostly SRAM")
    print(f"    {'node':<7s}" + "".join(f"{l:>14s}" for l in labels))
    mins = {l: min(curve, key=lambda n: curve[n][l]) for l in labels}
    for name, row in curve.items():
        line = f"    {name:<7s}"
        for l in labels:
            line += f"{row[l]:>13.4f}" + ("*" if mins[l] == name else " ")
        print(line)
    print(f"    * cheapest for that mix\n")


def cheapest_node(app_key: str, config) -> str:
    """The node with the lowest system cost for this design."""
    return min(node_sweep(app_key, config, show=False), key=lambda r: r[6])[0]


# ==============================================================================
# Design-type presets
# ==============================================================================
#
# Every accelerator in the library sits near two thirds SRAM, so none of them
# shows the cost turn moving. Rather than invent an engine to demonstrate it,
# these presets vary the ONE property that moves it - how much of the die is
# memory - and hold everything else fixed.

DESIGN_TYPES = {
    "compute-heavy": (0.20, "large array, small on-chip buffer. Streams "
                            "weights from memory and spends its silicon on "
                            "multipliers."),
    "balanced": (0.50, "the usual compromise: enough buffer to keep the array "
                       "fed on most layers."),
    "sram-heavy": (0.80, "large on-chip buffer, modest array. Keeps whole "
                         "feature maps resident to avoid refetching them."),
    "control-class": (0.35, "a small controller-class part where neither the "
                            "array nor the buffer dominates."),
}


def design_type_nodes() -> None:
    """Which node is cheapest for each design type, and why it differs.

    Silicon cost per unit of function only - a system total would bury the
    effect under memory and board costs that a node does not touch.
    """
    from .process import NODE_LIBRARY, get_node
    print(f"\n{LINE}")
    print(" CHEAPEST NODE BY DESIGN TYPE")
    print(LINE)
    print("  Silicon cost per unit of function: area x wafer price over yield,")
    print("  for a die of a given SRAM fraction. Everything except the mix is")
    print("  held fixed, so any difference is the mix.\n")
    nodes = list(NODE_LIBRARY)
    head = f"  {'design type':<16s}{'SRAM':>6s}  " + "".join(
        f"{n:>8s}" for n in nodes)
    print(head); print("  " + "-" * (len(head) - 2))
    winners = {}
    for name, (frac, why) in DESIGN_TYPES.items():
        costs = {}
        for n in nodes:
            nd = get_node(n)
            area = (1 - frac) * nd.logic_area + frac * nd.sram_area
            costs[n] = area * nd.usd_per_mm2 / nd.yield_factor
        best = min(costs, key=costs.get)
        winners[name] = best
        line = f"  {name:<16s}{frac * 100:>5.0f}%  "
        for n in nodes:
            line += f"{costs[n]:>7.3f}" + ("*" if n == best else " ")
        print(line)
    print("  * cheapest for that mix\n")
    for name, (frac, why) in DESIGN_TYPES.items():
        print(f"  {name:<16s}{winners[name]:<5s}{why}")
    distinct = len(set(winners.values()))
    print(f"\n  {distinct} different node(s) across {len(DESIGN_TYPES)} design "
          f"types. SRAM shrinks at")
    print("  roughly half the rate of logic, so a die that is mostly memory")
    print("  gains less from a finer node while paying the same wafer price -")
    print("  and turns back to an older node sooner.")
    print("\n  The accelerators in this library all sit near two thirds SRAM,")
    print("  so they land on the same side and the turn does not move between")
    print("  them. The mix is what moves it, not the application.")
    print(LINE)
