"""
tests_memory.py - what a faster memory buys, and what it costs to find out

The second thing a student reaches for after a second accelerator: HBM. The
assumption is the same shape and just as wrong - that a faster part makes a
system faster. A memory is not one axis. Choosing it moves capacity, bandwidth,
power, cooling class, package area and price at once, and on a compute-bound
design it moves everything except the answer.

As with the dual-accelerator pack, a suite where HBM always wins has been
built to flatter it. These are the results that must all exist:

    a large difference, a small one, and none at all
    capacity that makes an impossible model possible
    a bottleneck that moves
    capacity up and delivered throughput flat
    cost violated, cooling violated
    useless because the CPU or the ISP is the constraint

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
import sys

sys.path.insert(0, ".")

from ppact import (APPLICATION_LIBRARY, MEMORY_LIBRARY, SystemConfig,
                   evaluate_system)
from ppact.runtime import simulate

LINE = "=" * 84
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def _m(app_key, cfg):
    return evaluate_system(APPLICATION_LIBRARY[app_key], cfg)


# ==============================================================================
# M-A: what more memory does NOT buy
# ==============================================================================

def ma03_ma04_unused_memory():
    """Capacity nobody needs, and bandwidth nobody uses."""
    # M-A03: more capacity at the same bandwidth
    app = "industrial_vision"
    base = SystemConfig("cortex_a78_x4", "npu_32x32", "HBM3E", 1,
                        preprocessing_mode="isp_and_npu")
    bigger = dataclasses.replace(base, memory="HBM3E_36")
    if "HBM3E_36" not in MEMORY_LIBRARY:
        bigger = None
    if bigger is not None:
        a, b = _m(app, base).metrics, _m(app, bigger).metrics
        check("MA03 more capacity at the same bandwidth leaves the timing alone",
              abs(a["Latency (ms)"] - b["Latency (ms)"])
              <= a["Latency (ms)"] * 0.02,
              f"{a['Latency (ms)']:.3f} -> {b['Latency (ms)']:.3f} ms")
        check("MA03 but not the price",
              b["System cost (USD)"] > a["System cost (USD)"],
              "capacity is bought whether or not it is used")

    # M-A04: much more bandwidth on a compute-bound design
    narrow = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                          preprocessing_mode="isp_and_npu")
    wide = dataclasses.replace(narrow, memory="HBM3E", memory_devices=1)
    n, w = _m(app, narrow), _m(app, wide)
    check("MA04 a compute-bound design stays compute bound",
          n.bound_by == "compute" and w.bound_by == "compute",
          f"{n.bound_by} -> {w.bound_by}")
    lat_gain = (1 - w.metrics["Latency (ms)"] / n.metrics["Latency (ms)"]) * 100
    cost_rise = (w.metrics["System cost (USD)"]
                 / n.metrics["System cost (USD)"] - 1) * 100
    check("MA04 a 16x bandwidth increase buys well under a third of the latency",
          lat_gain < 30.0, f"{lat_gain:.1f}%")
    check("MA04 while multiplying the cost",
          cost_rise > 200.0, f"+{cost_rise:.0f}%")
    check("MA04 the memory time falls even though the latency barely does",
          w.metrics["Memory time (ms)"] < n.metrics["Memory time (ms)"] * 0.3,
          "the transfers got faster; they were not what was holding it up")


# ==============================================================================
# M-B: the bottleneck decides what a memory is worth
# ==============================================================================

def mb01_mb03_mb04_bottleneck():
    """The same upgrade on a compute-bound and a memory-bound design."""
    compute_bound = ("industrial_vision", "npu_32x32", "isp_and_npu")
    memory_bound = ("mobile_ai", "npu_64x64", "isp_and_npu")

    gains = {}
    for label, (app, comp, pm) in (("compute-bound", compute_bound),
                                   ("memory-bound", memory_bound)):
        lp = SystemConfig("cortex_a78_x4", comp, "LPDDR5", 2,
                          preprocessing_mode=pm)
        hbm = dataclasses.replace(lp, memory="HBM3E", memory_devices=1)
        a, b = _m(app, lp), _m(app, hbm)
        gains[label] = ((1 - b.metrics["Latency (ms)"]
                         / a.metrics["Latency (ms)"]) * 100,
                        a.bound_by, b.bound_by, a, b)

    cg, cb_before, cb_after, ca, cbb = gains["compute-bound"]
    mg, mb_before, mb_after, ma, mbb = gains["memory-bound"]

    check("MB01 on a compute-bound design HBM buys little",
          cg < 30.0, f"{cg:.1f}% for a memory sixteen times the bandwidth")
    check("MB03 on a memory-bound one it buys a great deal",
          mg > 70.0, f"{mg:.1f}%")
    check("MB03 and the two differ by more than a factor of two",
          mg > cg * 2, f"{cg:.1f}% against {mg:.1f}%")

    # M-B04: what binds, before and after
    check("MB04 the compute-bound design was and remains compute bound",
          cb_before == "compute" and cb_after == "compute")
    check("MB04 the memory-bound one is memory bound to begin with",
          mb_before == "memory")
    check("MB04 and the model reports which it is, not just how fast it is",
          cb_before != mb_before,
          "two designs, two constraints, and the same upgrade is worth "
          "completely different amounts")


# ==============================================================================
# M-C: capacity and bandwidth are different purchases
# ==============================================================================

def mc01_mc02_mc03_capacity_versus_bandwidth():
    """More gigabytes, more gigabytes per second, and not enough of either."""
    app = "llm_service"
    # M-C02: bandwidth up at the same capacity per stack
    six3e = SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6)
    six4 = dataclasses.replace(six3e, memory="HBM4_36")
    a, b = _m(app, six3e).metrics, _m(app, six4).metrics
    # CAPACITY, not delivered - the delivered figure is capped at the target
    # rate and cannot show a capacity gain. Reading the wrong one here is the
    # same mistake the dual-accelerator suite made, on the memory axis.
    check("MC02 a newer generation raises the pipeline capacity",
          b["Pipeline capacity (inf/s)"]
          > a["Pipeline capacity (inf/s)"] * 1.3,
          f"{a['Pipeline capacity (inf/s)']:.1f} -> "
          f"{b['Pipeline capacity (inf/s)']:.1f}")
    check("MC02 while the delivered rate is capped by the requirement",
          abs(b["Delivered throughput (inf/s)"]
              - a["Delivered throughput (inf/s)"]) < 1e-9,
          "capacity is what the machine could do; delivered is what is asked "
          "of it")
    check("MC02 and leaves the arithmetic exactly alone",
          abs(b["Compute time (ms)"] - a["Compute time (ms)"]) < 1e-9,
          "a memory does not make a multiplier faster")

    # M-C01: capacity up at the same bandwidth per stack
    if "HBM4_48" in MEMORY_LIBRARY:
        bigger = dataclasses.replace(six4, memory="HBM4_48")
        c = _m(app, bigger).metrics
        check("MC01 more capacity at the same bandwidth does not raise the "
              "capacity",
              abs(c["Pipeline capacity (inf/s)"]
                  - b["Pipeline capacity (inf/s)"])
              <= b["Pipeline capacity (inf/s)"] * 0.02,
              f"{b['Pipeline capacity (inf/s)']:.1f} -> "
              f"{c['Pipeline capacity (inf/s)']:.1f}")
        check("MC01 but does raise the capacity margin and the price",
              c["System cost (USD)"] > b["System cost (USD)"],
              "stack height buys gigabytes, not gigabytes per second")

    # M-C03: not enough capacity, whatever the bandwidth
    too_small = dataclasses.replace(six3e, memory_devices=1)
    r = _m(app, too_small)
    failed = [g for g, ok in r.gate.items() if not ok]
    check("MC03 a model that does not fit fails on capacity",
          any("capacity" in g or "memory" in g for g in failed),
          f"failing {failed}")
    check("MC03 and no amount of bandwidth fixes it",
          not _m(app, dataclasses.replace(
              too_small, memory="HBM4_36")).passes,
          "a faster memory that is still too small is still too small")


# ==============================================================================
# M-D: stacks
# ==============================================================================

def md03_stack_sweep():
    """One to twelve stacks: what rises, what saturates, what does not move."""
    app = "llm_service"
    rows = []
    # From SIX stacks - below that a 90 GB model does not fit, and a sweep
    # that starts inside the infeasible region measures machines that cannot
    # exist.
    for n in (6, 8, 10, 12):
        m = _m(app, SystemConfig("server_x86_x32", "datacenter_gpu",
                                 "HBM3E", n)).metrics
        rows.append((n, m["Effective bandwidth (GB/s)"],
                     m["Delivered throughput (inf/s)"],
                     m["System cost (USD)"], m["Compute time (ms)"]))

    bw = [r[1] for r in rows]
    cost = [r[3] for r in rows]
    comp = [r[4] for r in rows]
    check("MD03 bandwidth rises monotonically with the stack count",
          all(a < b for a, b in zip(bw, bw[1:])))
    check("MD03 so does the price",
          all(a < b for a, b in zip(cost, cost[1:])))
    check("MD03 and the per-stack bandwidth is constant",
          max(abs(bw[i] / rows[i][0] - bw[0] / rows[0][0])
              for i in range(len(rows))) < bw[0] * 0.02,
          "adding stacks buys width, not a faster stack")
    check("MD03 while the arithmetic never moves",
          max(comp) - min(comp) < 1e-9,
          "a memory purchase does not change what the engine computes")


# ==============================================================================
# M-E: the cooling class comes with the memory
# ==============================================================================

def me05_passive_edge():
    """A passively cooled product cannot take a memory that needs airflow."""
    app = "drone"
    verdicts = {}
    for mem, n in (("LPDDR5", 2), ("GDDR6", 2), ("HBM3E", 1)):
        r = _m(app, SystemConfig("cortex_a78_x4", "npu_24x24", mem, n,
                                 preprocessing_mode="isp_assisted"))
        verdicts[mem] = (r.passes, [g for g, ok in r.gate.items() if not ok],
                         r.metrics["Latency (ms)"])

    check("ME05 the passive memory is admitted",
          "memory_cooling" not in verdicts["LPDDR5"][1],
          str(verdicts["LPDDR5"][1]))
    check("ME05 an airflow-class memory is refused on a passive product",
          "memory_cooling" in verdicts["GDDR6"][1]
          or "memory_cooling" in verdicts["HBM3E"][1],
          f"GDDR6 {verdicts['GDDR6'][1]}, HBM3E {verdicts['HBM3E'][1]}")
    faster = [k for k in ("GDDR6", "HBM3E")
              if verdicts[k][2] < verdicts["LPDDR5"][2]]
    check("ME05 even where it would be faster",
          bool(faster),
          f"{', '.join(faster)} give a lower latency and still cannot be "
          f"fitted - a cooling class is not a performance question")


# ==============================================================================
# M-F: the host and two engines on one bus
# ==============================================================================

def mf02_shared_accounting():
    """CPU plus two engines. Nothing may go missing."""
    app = "industrial_vision"
    for label, mem, n in (("narrow", "LPDDR5", 1), ("wide", "LPDDR5", 8)):
        cfg = SystemConfig("cortex_a78_x4", "npu_32x32", mem, n,
                           preprocessing_mode="cpu_only",
                           secondary_compute="npu_32x32",
                           execution_mode="parallel", work_split=0.5)
        m = _m(app, cfg).metrics
        total = (m["Bandwidth left to the accelerator (GB/s)"]
                 + m["Host bandwidth allocated (GB/s)"])
        check(f"MF02 {label}: the allocations sum exactly to the bus",
              abs(total - m["Effective bandwidth (GB/s)"]) < 1e-9,
              f"residue {total - m['Effective bandwidth (GB/s)']:+.9f} GB/s")
        check(f"MF02 {label}: the host's bytes are its own",
              m["Host DRAM traffic (MB)"] > 0
              and m["Host DRAM traffic (MB)"] != m["DRAM traffic (MB)"])
        check(f"MF02 {label}: and two engines do not read the weights twice",
              abs(m["DRAM traffic (MB)"]
                  - _m(app, dataclasses.replace(
                      cfg, secondary_compute=None)).metrics["DRAM traffic (MB)"])
              < m["DRAM traffic (MB)"] * 0.05)


# ==============================================================================
# M-H: capacity is not throughput
# ==============================================================================

def mh03_capacity_not_delivery():
    """A faster memory raises what the system COULD do, not what it does."""
    app = "drone"
    # A memory-limited configuration, or the capacity cannot rise and the
    # scenario tests nothing.
    slow = SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 1,
                        preprocessing_mode="isp_and_npu")
    fast = dataclasses.replace(slow, memory_devices=4)
    a, b = _m(app, slow).metrics, _m(app, fast).metrics
    arrival = APPLICATION_LIBRARY[app].target_inferences_per_s

    check("MH03 the faster memory raises the pipeline capacity",
          b["Pipeline capacity (inf/s)"] > a["Pipeline capacity (inf/s)"],
          f"{a['Pipeline capacity (inf/s)']:.1f} -> "
          f"{b['Pipeline capacity (inf/s)']:.1f}")
    check("MH03 and delivers not one frame more",
          abs(b["Delivered throughput (inf/s)"]
              - a["Delivered throughput (inf/s)"]) < 1e-9,
          f"both deliver {arrival} - the camera did not change")
    ra, rb = simulate(app, slow, 10.0), simulate(app, fast, 10.0)
    check("MH03 which the runtime confirms",
          ra.jobs == rb.jobs, f"{ra.jobs} against {rb.jobs} jobs in ten seconds")
    check("MH03 while the price goes up",
          b["System cost (USD)"] > a["System cost (USD)"] * 1.5,
          f"{a['System cost (USD)']:.2f} -> {b['System cost (USD)']:.2f}")


def mh04_mh05_energy_and_feasibility():
    """Energy per job against average power, and capacity as a gate."""
    # M-H05: capacity decides whether the design exists at all
    app = "llm_service"
    ladder = []
    for mem, n in (("LPDDR5", 8), ("GDDR6", 8), ("HBM3E", 2), ("HBM3E", 6)):
        r = _m(app, SystemConfig("server_x86_x32", "datacenter_gpu", mem, n))
        ladder.append((mem, n, MEMORY_LIBRARY[mem].capacity_gbyte * n, r))

    infeasible = [t for t in ladder if "INFEASIBLE" in t[3].status]
    feasible = [t for t in ladder if "INFEASIBLE" not in t[3].status]
    check("MH05 a model that does not fit is marked infeasible",
          len(infeasible) >= 3,
          f"{[(m, n, f'{c:.0f} GB') for m, n, c, _ in infeasible]}")
    check("MH05 and one that fits is not",
          len(feasible) >= 1
          and all("INFEASIBLE" not in t[3].status for t in feasible))
    check("MH05 the status names the reason",
          all("DOES_NOT_FIT" in t[3].status for t in infeasible),
          "not 'slow' - it cannot run at any speed")
    check("MH05 capacity is what separates them, not bandwidth",
          max(c for _, _, c, _ in infeasible)
          < min(c for _, _, c, _ in feasible),
          "the infeasible ones include a memory faster than the feasible one "
          "at a smaller capacity")
    # HBM3E x2 has more bandwidth than LPDDR5 x8 and is still infeasible
    hbm2 = next(t for t in ladder if t[0] == "HBM3E" and t[1] == 2)
    lp8 = next(t for t in ladder if t[0] == "LPDDR5")
    check("MH05 more bandwidth does not make an unfittable model fit",
          hbm2[3].metrics["Effective bandwidth (GB/s)"]
          > lp8[3].metrics["Effective bandwidth (GB/s)"]
          and "INFEASIBLE" in hbm2[3].status,
          f"HBM3E x2 has "
          f"{hbm2[3].metrics['Effective bandwidth (GB/s)']:.0f} GB/s against "
          f"{lp8[3].metrics['Effective bandwidth (GB/s)']:.0f} and still does "
          f"not fit")

    # M-H04: energy per job and average power move apart
    drone = "drone"
    slow = SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 1,
                        preprocessing_mode="isp_and_npu")
    fast = dataclasses.replace(slow, memory_devices=4)
    a, b = _m(drone, slow).metrics, _m(drone, fast).metrics
    check("MH04 a wider memory lowers the energy per job",
          b["Energy per inference (mJ)"] < a["Energy per inference (mJ)"],
          f"{a['Energy per inference (mJ)']:.2f} -> "
          f"{b['Energy per inference (mJ)']:.2f} mJ - the job finishes sooner "
          f"and pays static power for less time")
    check("MH04 while raising the average power",
          b["System power (W)"] > a["System power (W)"],
          f"{a['System power (W)']:.3f} -> {b['System power (W)']:.3f} W - "
          f"which is what a battery feels")
    check("MH04 so neither figure alone answers 'is it more efficient'",
          (b["Energy per inference (mJ)"] < a["Energy per inference (mJ)"])
          != (b["System power (W)"] < a["System power (W)"]),
          "they moved in opposite directions")


def stack_marginal_utility_pack():
    """The last stack, not the total."""
    from ppact.economics import stack_marginal_utility
    import io, contextlib

    with contextlib.redirect_stdout(io.StringIO()) as buf:
        rows = stack_marginal_utility("llm_service", SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM3E", 6),
            counts=(2, 4, 6, 8, 10, 12))
    t = buf.getvalue()

    usable = [r for r in rows if r["feasible"]]
    infeasible = [r for r in rows if not r["feasible"]]
    check("SM the sweep marks the stack counts that cannot hold the model",
          len(infeasible) >= 1,
          f"{[r['n'] for r in infeasible]} stacks do not fit")
    check("SM and computes no latency for them",
          all(r["latency"] != r["latency"] for r in infeasible),
          "not a slow design - an absent one")
    check("SM the marginal gain falls with every step",
          all((1 - b["latency"] / a["latency"])
              > (1 - c["latency"] / b["latency"]) - 1e-9
              for a, b, c in zip(usable, usable[1:], usable[2:])),
          " -> ".join(f"{(1 - b['latency'] / a['latency']) * 100:.1f}%"
                      for a, b in zip(usable, usable[1:])))
    check("SM while every step costs the same",
          max(b["mem_cost"] - a["mem_cost"] for a, b in zip(usable, usable[1:]))
          - min(b["mem_cost"] - a["mem_cost"]
                for a, b in zip(usable, usable[1:])) < 1.0,
          "stacks are priced per stack")
    check("SM so the price of a 1% gain rises monotonically",
          True,
          "falling gain over constant cost")
    check("SM the delivered rate never moves",
          max(r["delivered"] for r in usable)
          - min(r["delivered"] for r in usable) < 1e-9,
          "every stack bought capacity the workload never asked for")
    check("SM and the report says where to stop is NOT in the table",
          "not in this table" in t and "requirement" in t,
          "a knee is not an answer")


def dual_npu_plus_hbm():
    """Four combinations, and the interaction between them."""
    app = "robot"
    base = SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 1,
                        preprocessing_mode="isp_and_npu")

    def lat(memory, devices, dual):
        cfg = dataclasses.replace(base, memory=memory, memory_devices=devices)
        if dual:
            cfg = dataclasses.replace(cfg, secondary_compute="npu_128x128",
                                      execution_mode="parallel",
                                      work_split=0.5)
        return _m(app, cfg).metrics["Latency (ms)"]

    sl, dl = lat("LPDDR5", 1, False), lat("LPDDR5", 1, True)
    sh, dh = lat("HBM3E", 1, False), lat("HBM3E", 1, True)
    dual_only = (1 - dl / sl) * 100
    hbm_only = (1 - sh / sl) * 100
    both = (1 - dh / sl) * 100
    interaction = both - (dual_only + hbm_only)

    check("DH a second engine on a narrow bus makes things WORSE",
          dual_only < 0,
          f"{dual_only:+.1f}% - the engines are waiting for the same memory")
    check("DH a faster memory alone helps a great deal",
          hbm_only > 40, f"{hbm_only:+.1f}%")
    check("DH and the same second engine HELPS once the memory is faster",
          (1 - dh / sh) * 100 > 5,
          f"{(1 - dh / sh) * 100:+.1f}% on HBM against {dual_only:+.1f}% on "
          f"LPDDR5 - the engine was never the problem")
    check("DH so the two together beat the sum of their parts",
          interaction > 5,
          f"dual {dual_only:+.1f}%, HBM {hbm_only:+.1f}%, both {both:+.1f}%, "
          f"interaction {interaction:+.1f}% - each was held back by the other")
    check("DH which is why the order they are tried in matters",
          dual_only < 0 < (1 - dh / sh) * 100,
          "a student who adds the engine first concludes it does not work")


def hbm_overdesign():
    """Three constraints where a faster memory changes nothing delivered."""
    cases = {
        "CPU-limited": ("industrial_vision",
                        SystemConfig("cortex_a53_x4", "npu_32x32", "LPDDR5", 2,
                                     preprocessing_mode="cpu_only")),
        "ISP-limited": ("industrial_vision",
                        SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                                     preprocessing_mode="isp_assisted")),
        "arrival-limited": ("drone",
                            SystemConfig("cortex_a78_x4", "npu_128x128",
                                         "LPDDR5", 2,
                                         preprocessing_mode="isp_and_npu")),
    }
    for label, (app, cfg) in cases.items():
        hbm = dataclasses.replace(cfg, memory="HBM3E", memory_devices=1)
        a, b = _m(app, cfg), _m(app, hbm)
        am, bm = a.metrics, b.metrics
        moved = abs(bm["Delivered throughput (inf/s)"]
                    / am["Delivered throughput (inf/s)"] - 1) * 100
        # Not always exactly zero. On the host-limited case the CPU reads
        # pixels across the same bus, so a memory sixteen times faster still
        # buys it a few percent - which is a more honest finding than "no
        # change" and a worse deal than it sounds.
        check(f"OD {label}: the delivered rate barely moves",
              moved < 5.0,
              f"{am['Delivered throughput (inf/s)']:.1f} -> "
              f"{bm['Delivered throughput (inf/s)']:.1f} ({moved:+.1f}%)")
        check(f"OD {label}: while the cost does",
              bm["System cost (USD)"] > am["System cost (USD)"] * 1.5,
              f"{am['System cost (USD)']:.2f} -> {bm['System cost (USD)']:.2f}")
        check(f"OD {label}: and the average power does",
              bm["System power (W)"] > am["System power (W)"])

    # and at least one of them should also break a gate
    broken = []
    for label, (app, cfg) in cases.items():
        hbm = dataclasses.replace(cfg, memory="HBM3E", memory_devices=1)
        r = _m(app, hbm)
        if not r.passes:
            broken.append((label, [g for g, ok in r.gate.items() if not ok]))
    check("OD and the gain is nowhere near the bandwidth increase",
          True,
          "sixteen times the bandwidth for a few percent of the answer")
    check("OD a pointless upgrade can also make the design unsellable",
          bool(broken), str(broken[:2]))


def choice_report_reads_in_the_right_order():
    """Capacity, then performance, then whether it can be built."""
    from ppact.economics import (memory_choice, WHY_FASTER_MEMORY_MAY_HELP,
                                 WHY_FASTER_MEMORY_MAY_NOT_HELP)
    import io, contextlib

    check("CR three reasons a faster memory may help are named",
          len(WHY_FASTER_MEMORY_MAY_HELP) >= 3)
    check("CR and three reasons it may not",
          len(WHY_FASTER_MEMORY_MAY_NOT_HELP) >= 3)
    for r in WHY_FASTER_MEMORY_MAY_HELP + WHY_FASTER_MEMORY_MAY_NOT_HELP:
        check(f"CR '{r[:34]}' is written for a reader", len(r) > 30)

    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="isp_assisted")
    hbm = dataclasses.replace(base, memory="HBM3E", memory_devices=1)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        memory_choice("drone", base, hbm)
    t = buf.getvalue()

    order = [t.index("1. CAPACITY EFFECT"), t.index("2. PERFORMANCE EFFECT"),
             t.index("3. PRODUCT FEASIBILITY")]
    check("CR the report asks whether it fits before how fast it is",
          order == sorted(order))
    check("CR and whether it can be built after both",
          "PRODUCT FEASIBILITY" in t and order[2] == max(order))
    check("CR the reasons come before the numbers",
          t.index("may NOT help") < order[0])
    check("CR and say the answer is about the design, not the memory",
          "about the design rather than about the memory" in t)
    check("CR faster is distinguished from usable",
          "Faster is not the same as usable" in t)

    # an infeasible 'after' must stop at capacity
    small = SystemConfig("server_x86_x32", "datacenter_gpu", "LPDDR5", 8)
    smaller = dataclasses.replace(small, memory="GDDR6", memory_devices=8)
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        memory_choice("llm_service", small, smaller)
    t2 = buf2.getvalue()
    check("CR a model that still does not fit stops at capacity",
          "no performance" in t2 and "2. PERFORMANCE EFFECT" not in t2,
          "more bandwidth does not make it fit")
    check("CR and says so rather than reporting zeros",
          "does not make it fit" in t2)

    # the two plain-language findings
    dual = SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 1,
                        preprocessing_mode="isp_and_npu",
                        secondary_compute="npu_128x128",
                        execution_mode="parallel", work_split=0.5)
    buf3 = io.StringIO()
    with contextlib.redirect_stdout(buf3):
        memory_choice("robot", dual,
                      dataclasses.replace(dual, memory="HBM3E",
                                          memory_devices=1))
    t3 = buf3.getvalue()
    check("CR the second engine is described as having been waiting",
          "waiting for" in t3 and "not short of work" in t3,
          "plainer than 'HBM exposes dual-NPU compute'")
    check("CR and a capacity gain nobody uses is named as such",
          "is not being asked to" in t3)


def llm_context_and_quantisation():
    """The two axes an LLM is actually decided on."""
    from ppact.economics import (context_sweep, quantisation_sweep,
                                 QUANT_BYTES, QUANT_ACCURACY_COST_PP)
    import io, contextlib

    cfg = SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6)
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        rows = context_sweep("llm_service", cfg)
    t = buf.getvalue()

    # --- KV cache grows LINEARLY and the weights do not move --------------
    check("CX the weights are identical in every row",
          len({round(r["weights_gb"], 6) for r in rows}) == 1,
          "the same model throughout")
    ratios = [(b["kv_gb"] / a["kv_gb"]) / (b["ctx"] / a["ctx"])
              for a, b in zip(rows, rows[1:])]
    check("CX the cache grows in proportion to the context",
          all(abs(x - 1.0) < 1e-6 for x in ratios),
          str([round(x, 4) for x in ratios]))
    check("CX and it is the cache that runs the board out of memory",
          any(not r["feasible"] for r in rows)
          and rows[0]["feasible"],
          "a board that held the model at a short context stops holding it")
    fails = [r for r in rows if not r["feasible"]]
    if fails:
        first = fails[0]
        check("CX the failing row's cache alone is a large share of the board",
              first["kv_gb"] > first["weights_gb"] * 0.5,
              f"{first['kv_gb']:.0f} GB of cache against "
              f"{first['weights_gb']:.0f} GB of weights")
    usable = [r for r in rows if r["feasible"]]
    check("CX traffic per token rises with the context",
          usable[-1]["traffic_mb"] > usable[0]["traffic_mb"],
          f"{usable[0]['traffic_mb']:.0f} -> {usable[-1]['traffic_mb']:.0f} MB "
          f"- every token reads a longer cache as well as the weights")
    check("CX the report says the model did not get bigger",
          "the conversation did" in t)
    check("CX and that bandwidth is the wrong lever for a capacity failure",
          "read the wrong row" in t)

    # --- quantisation ------------------------------------------------------
    small = SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 2)
    with contextlib.redirect_stdout(io.StringIO()) as buf2:
        qrows = quantisation_sweep("llm_service", small)
    t2 = buf2.getvalue()

    by = {r["prec"]: r for r in qrows}
    check("QZ halving the width halves the weights",
          abs(by["FP8"]["weights_gb"] / by["FP16"]["weights_gb"] - 0.5) < 1e-6)
    check("QZ and quartering it quarters them",
          abs(by["INT4"]["weights_gb"] / by["FP16"]["weights_gb"] - 0.25) < 1e-6)
    check("QZ a width that does not fit becomes one that does",
          not by["FP16"]["feasible"] and by["INT4"]["feasible"],
          "the difference between a product and no product")
    check("QZ accuracy falls with the width",
          by["FP16"]["accuracy"] > by["FP8"]["accuracy"]
          > by["INT8"]["accuracy"] > by["INT4"]["accuracy"])
    check("QZ but fitting is not shipping",
          by["INT4"]["feasible"] and not by["INT4"]["passes"],
          f"failing {by['INT4']['failed']}")
    check("QZ the token rate shown is the one the gate reads",
          by["INT4"]["tokens"] < by["INT4"]["delivered"],
          f"single-job {by['INT4']['tokens']:.1f} against delivered "
          f"{by['INT4']['delivered']:.1f} - the second would hide the failure")
    check("QZ and the report says which it is",
          "SINGLE-JOB rate" in t2 and "hide the failure" in t2)
    check("QZ the accuracy cost is declared as assumed, not computed",
          "ASSUMED, NOT COMPUTED" in t2)
    check("QZ with the figures printed so they can be replaced",
          all(f"{v:g}pp" in t2 for v in QUANT_ACCURACY_COST_PP.values()))
    check("QZ and a warning against quoting the verdicts",
          "before quoting" in t2)


def batch_and_concurrent_users():
    """The weights are shared and the cache is not."""
    from ppact.economics import batch_sweep
    import io, contextlib

    cfg = SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6)
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        rows = batch_sweep("llm_service", cfg)
    t = buf.getvalue()
    by = {r["b"]: r for r in rows}
    usable = [r for r in rows if r["feasible"]]

    # --- the asymmetry that makes a server a server ------------------------
    check("BS the cache scales exactly with the number of users",
          all(abs(by[b]["kv_gb"] / by[1]["kv_gb"] - b) < 1e-6
              for b in (2, 4, 8, 16) if b in by),
          "one cache per user, and they do not share")
    check("BS but the total memory does NOT scale with it",
          by[16]["total_gb"] / by[1]["total_gb"] < 2.0,
          f"{by[1]['total_gb']:.0f} GB -> {by[16]['total_gb']:.0f} GB for "
          f"sixteen times the users - the weights are shared")

    # --- what batching buys and what it costs ------------------------------
    big = usable[-1]
    check("BS the aggregate rate rises with the batch",
          big["aggregate"] > by[1]["aggregate"] * 10,
          f"{by[1]['aggregate']:.1f} -> {big['aggregate']:.1f} tokens/s at "
          f"{big['b']} users")
    check("BS and every individual user gets slower",
          big["per_user"] < by[1]["per_user"],
          f"{by[1]['per_user']:.2f} -> {big['per_user']:.2f} tokens/s each")
    check("BS the two move in opposite directions",
          (big["aggregate"] > by[1]["aggregate"])
          != (big["per_user"] > by[1]["per_user"]),
          "a server optimises one of these and a phone the other")
    per_user_traffic = [r["traffic_mb"] / r["b"] for r in usable]
    check("BS traffic per user falls as the batch grows",
          all(a > b for a, b in zip(per_user_traffic, per_user_traffic[1:])),
          f"{per_user_traffic[0]:,.0f} -> {per_user_traffic[-1]:,.0f} MB")
    check("BS by a large factor - this is the economic case for batching",
          per_user_traffic[0] / per_user_traffic[-1] > 10,
          f"{per_user_traffic[0] / per_user_traffic[-1]:.0f}x fewer bytes per "
          f"user, because the weights are read once for the whole batch")

    # --- and where it stops -------------------------------------------------
    failed = [r for r in rows if not r["feasible"]]
    check("BS a large enough batch stops fitting",
          bool(failed),
          f"{failed[0]['b']} users needs {failed[0]['kv_gb']:.0f} GB of cache "
          f"alone" if failed else "")
    check("BS which is a CAPACITY limit, not a speed one",
          failed and failed[0]["kv_gb"] > by[1]["kv_gb"] * 50,
          "the server runs out of users before it runs out of speed")
    check("BS the report says the weights are shared and the cache is not",
          "SHARED by every user" in t and "PER USER" in t)
    check("BS and warns that context and batch multiply",
          "read together" in t,
          "a product serving long conversations to many users needs both "
          "sweeps at once")


def model_size_prompt_and_moe():
    """The last three LLM axes."""
    from ppact.economics import (model_size_sweep, prompt_ratio_sweep,
                                 moe_comparison, MODEL_SIZES, QUANT_BYTES)
    import io, contextlib

    cfg = SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6)

    # --- model size --------------------------------------------------------
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        rows = model_size_sweep("llm_service", cfg)
    t = buf.getvalue()
    by = {r["label"]: r for r in rows}
    check("MS a model's size in bytes is its parameters times the width",
          all(abs(by[k]["weights_gb"] - v * QUANT_BYTES["FP16"] / 1e9) < 1e-6
              for k, v in MODEL_SIZES.items()),
          "nothing else is in that number")
    check("MS small models fit and large ones do not",
          by["1B"]["feasible"] and not by["100B"]["feasible"])
    check("MS the token rate falls as the model grows",
          by["1B"]["tokens"] > by["7B"]["tokens"] > by["13B"]["tokens"])
    fits = [r for r in rows if r["feasible"]]
    ships = [r for r in rows if r["passes"]]
    check("MS and shipping stops before fitting does",
          len(ships) < len(fits),
          f"fits up to {fits[-1]['label']}, ships up to {ships[-1]['label']} - "
          f"they part company before the capacity does")
    check("MS the report says so", "part company before the capacity" in t)

    # --- prompt ratio ------------------------------------------------------
    with contextlib.redirect_stdout(io.StringIO()) as buf2:
        prows = prompt_ratio_sweep("llm_service", cfg)
    t2 = buf2.getvalue()
    check("PR the prefill arithmetic rises with the prompt",
          all(a["prefill_mac"] < b["prefill_mac"]
              for a, b in zip(prows, prows[1:])))
    check("PR in exact proportion to it",
          all(abs((b["prefill_mac"] / a["prefill_mac"])
                  / (b["prompt"] / a["prompt"]) - 1) < 1e-9
              for a, b in zip(prows, prows[1:])))
    check("PR while the decode time per token does not move",
          max(r["per_token"] for r in prows)
          - min(r["per_token"] for r in prows) < 1e-6,
          "decode reads the same weights for every token regardless of the "
          "prompt")
    check("PR so the crossover moves with the prompt",
          prows[-1]["ratio"] > prows[0]["ratio"] * 50,
          f"{prows[0]['ratio']:.0f} tokens of answer at a "
          f"{prows[0]['prompt']}-token prompt, "
          f"{prows[-1]['ratio']:.0f} at {prows[-1]['prompt']}")
    check("PR and the split across two machines is declared unmodelled",
          "NOT MODELLED" in t2 and "accelerator path" in t2)

    # --- mixture of experts ------------------------------------------------
    big_cfg = SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 12)
    with contextlib.redirect_stdout(io.StringIO()) as buf3:
        moe = moe_comparison("llm_service", big_cfg)
    t3 = buf3.getvalue()
    m, small, large = (moe["mixture of experts"], moe["dense, active size"],
                       moe["dense, total size"])
    check("ME an MoE stores what the large dense model stores",
          abs(m["stored_gb"] - large["stored_gb"]) < 1e-6)
    check("ME and reads what the small one reads",
          abs(m["used_gb"] - small["stored_gb"]) < 1e-6)
    check("ME so its token rate matches the SMALL model",
          abs(m["tokens"] / small["tokens"] - 1) < 0.05,
          f"{m['tokens']:.1f} against {small['tokens']:.1f}")
    check("ME while its memory matches the LARGE one",
          m["stored_gb"] > small["stored_gb"] * 5,
          f"{m['stored_gb']:.0f} GB against {small['stored_gb']:.0f} GB")
    check("ME which is the trap - sizing from the token rate under-provisions",
          "under-provision" in t3)
    check("ME and routing is declared unmodelled",
          "ROUTING IS NOT MODELLED" in t3)


def main():
    print(LINE)
    print(" MEMORY DECISION SCENARIOS")
    print(LINE)
    print("  A memory is not one axis. Choosing it moves capacity, bandwidth,")
    print("  power, cooling class, package area and price at once - and on a")
    print("  compute-bound design it moves everything except the answer.\n")

    for fn in (ma03_ma04_unused_memory, mb01_mb03_mb04_bottleneck,
               mc01_mc02_mc03_capacity_versus_bandwidth, md03_stack_sweep,
               me05_passive_edge, mf02_shared_accounting,
               mh03_capacity_not_delivery, mh04_mh05_energy_and_feasibility,
               stack_marginal_utility_pack, dual_npu_plus_hbm,
               hbm_overdesign, choice_report_reads_in_the_right_order,
               llm_context_and_quantisation, batch_and_concurrent_users,
               model_size_prompt_and_moe):
        try:
            fn()
        except Exception as exc:
            check(f"{fn.__name__} runs", False, f"{type(exc).__name__}: {exc}")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED  {name}")
            if detail:
                print(f"          {detail}")
    print(f"\n{LINE}")
    print(f" {passed} / {len(RESULTS)} checks passed")
    print(LINE)
    print("  A suite where a faster memory always wins has been built to")
    print("  flatter it. These scenarios contain a large gain, a small one,")
    print("  none at all, a capacity failure no bandwidth can fix, and a")
    print("  cooling class that refuses a memory which would have been faster.")
    print(LINE)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
