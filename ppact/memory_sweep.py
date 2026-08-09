"""
ppact.memory_sweep - HBM3E against HBM4, with the effects kept apart

A comparison is only worth reading if you know what is being held constant.
Putting a 24 GB HBM3E stack beside a 36 GB HBM4 stack mixes three different
things - a wider interface, more capacity, and a different package - and
attributes all of it to "HBM4".

Four comparisons, each holding something different:

    A  SAME CAPACITY      the generation effect alone. 36 GB either way, so
                          any difference comes from the 2048-bit interface.
    B  SAME STACK COUNT   generation AND capacity together. Labelled as such,
                          because six HBM4 stacks hold half again as much.
    C  MINIMUM TO FIT     the fewest stacks of each that hold the model. This
                          is the product question: what does it take to ship.
    D  SAME BANDWIDTH     fewer wide stacks against more narrow ones. Shows
                          what the interface buys in package terms rather
                          than in throughput.

The tool reports facts and does not recommend. Whether doubling the memory
subsystem cost is worth doubling the decode rate depends on what the product
is for, and that is not a question a table can answer.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

LINE = "=" * 78


@dataclass(frozen=True)
class Comparison:
    key: str
    title: str
    holds_constant: str
    effects_included: str
    warning: str = ""


COMPARISONS: Dict[str, Comparison] = {
    "same_capacity": Comparison(
        "same_capacity", "A - same total capacity",
        "total memory capacity",
        "generation only: interface width, channels, energy per bit",
        ""),
    "same_stacks": Comparison(
        "same_stacks", "B - same stack count",
        "number of stacks",
        "generation AND capacity",
        "The HBM4 side holds more. Do not read the cost difference as the "
        "price of the generation - part of it buys capacity."),
    "minimum_fit": Comparison(
        "minimum_fit", "C - fewest stacks that hold the model",
        "the requirement, not the configuration",
        "generation, capacity and stack count together",
        "The two sides may differ in every dimension. This is the product "
        "question - what does it take to ship - not a controlled comparison."),
    "same_bandwidth": Comparison(
        "same_bandwidth", "D - same total bandwidth",
        "aggregate bandwidth",
        "package and cost effects of a wider interface",
        "Throughput should be nearly identical by construction. What to read "
        "here is stack count, footprint and cost."),
}


def _capacity_gb(memory_library, mem: str, n: int) -> float:
    return memory_library[mem].capacity_gbyte * n


def _bandwidth(memory_library, mem: str, n: int) -> float:
    return memory_library[mem].effective_bandwidth_gbytes_s * n


# Which HBM3E profile each comparison should use. Comparison A needs equal
# capacity per stack so that only the interface differs; comparison B is
# deliberately the opposite - the 24 GB part against the 36 GB one, which is
# how a real generation upgrade actually arrives, capacity and all. Using the
# same pair for both made A and B identical and mislabelled one of them.
DEFAULT_PROFILES = {
    "same_capacity": ("HBM3E_36", "HBM4_36"),
    "same_stacks": ("HBM3E", "HBM4_36"),
    "minimum_fit": ("HBM3E", "HBM4_36"),
    "same_bandwidth": ("HBM3E_36", "HBM4_36"),
}


def build(app_key: str, comparison: str, hbm3e: Optional[str] = None,
          hbm4: Optional[str] = None) -> Tuple[Tuple[str, int], Tuple[str, int]]:
    """Pick the two configurations this comparison calls for."""
    if hbm3e is None or hbm4 is None:
        d3, d4 = DEFAULT_PROFILES.get(comparison, ("HBM3E_36", "HBM4_36"))
        hbm3e, hbm4 = hbm3e or d3, hbm4 or d4
    from .memory import MEMORY_LIBRARY
    from .application import APPLICATION_LIBRARY

    if comparison == "same_stacks":
        return (hbm3e, 6), (hbm4, 6)

    if comparison == "same_capacity":
        # Equal total capacity, so any difference is the interface.
        a = MEMORY_LIBRARY[hbm3e].capacity_gbyte
        b = MEMORY_LIBRARY[hbm4].capacity_gbyte
        n4 = 6
        n3 = max(1, int(round(b * n4 / a)))
        return (hbm3e, n3), (hbm4, n4)

    if comparison == "minimum_fit":
        need = APPLICATION_LIBRARY[app_key].required_memory_bytes / 1e9
        out = []
        for mem in (hbm3e, hbm4):
            n = 1
            while _capacity_gb(MEMORY_LIBRARY, mem, n) < need and n < 64:
                n += 1
            out.append((mem, n))
        return out[0], out[1]

    if comparison == "same_bandwidth":
        # HBM4 is twice as wide, so half as many stacks reach the same rate.
        n4 = 6
        target = _bandwidth(MEMORY_LIBRARY, hbm4, n4)
        n3 = max(1, int(round(target / MEMORY_LIBRARY[hbm3e].effective_bandwidth_gbytes_s)))
        return (hbm3e, n3), (hbm4, n4)

    raise KeyError(f"Unknown comparison '{comparison}'. "
                   f"Available: {', '.join(COMPARISONS)}")


def _row(app_key, compute, mem, n, duration_s):
    from .system import SystemConfig, evaluate_system
    from .application import APPLICATION_LIBRARY
    from .runtime import simulate
    from .innovation import system_score
    app = APPLICATION_LIBRARY[app_key]
    cpu = "server_x86_x32" if app.domain == "Data Center" else "cortex_a78_x4"
    cfg = SystemConfig(cpu, compute, mem, n)
    r = simulate(app_key, cfg, duration_s=duration_s)
    m = r.base.metrics
    accel = r.modules.get("Accelerator") or r.modules.get("Accelerator 1")
    window = r.total_time_ms or 1.0
    return {
        "config": cfg, "result": r, "metrics": m,
        "prefill_ms": m.get("Time to first token (ms)", 0.0),
        "decode_rate": m["Throughput (inf/s)"],
        "inter_token_ms": (1000.0 / m["Throughput (inf/s)"]
                           if m["Throughput (inf/s)"] > 0 else 0.0),
        "memory_wait_pct": accel.wait_ms / window * 100.0 if accel else 0.0,
        "accel_util_pct": accel.utilisation_pct if accel else 0.0,
        "energy_per_token_mj": m["Energy per inference (mJ)"],
        "cost_index": m["Memory cost index"],
        "footprint_mm2": m["  memory footprint (mm2)"],
        "cooling_ok": m["Memory cooling compatible"] == 1.0,
        "capacity_gb": m["Memory capacity (GB)"],
        "bandwidth_gbs": m["Effective bandwidth (GB/s)"],
        "requirements": (int(sum(1 for ok in r.base.gate.values() if ok)),
                         len(r.base.gate)),
        "score": system_score(app_key, cfg, duration_s)["Overall"],
        "stacks": n,
    }


def _delta(a: float, b: float) -> str:
    if a == 0:
        return "     -"
    return f"{(b / a - 1.0) * 100:+6.1f}%"


def compare(app_key: str, comparison: str = "same_capacity",
            compute: str = "datacenter_gpu", duration_s: float = 60.0,
            hbm3e: Optional[str] = None, hbm4: Optional[str] = None) -> None:
    """Three panels: how it runs, what it costs to build, and whether it ships."""
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .compute import COMPUTE_LIBRARY

    spec = COMPARISONS[comparison]
    (m3, n3), (m4, n4) = build(app_key, comparison, hbm3e, hbm4)
    a = _row(app_key, compute, m3, n3, duration_s)
    b = _row(app_key, compute, m4, n4, duration_s)
    app = APPLICATION_LIBRARY[app_key]

    print(f"\n{LINE}")
    print(f" HBM GENERATION COMPARISON - {app.name}")
    print(LINE)
    print(f"  {spec.title}")
    print(f"    holds constant   {spec.holds_constant}")
    print(f"    effects included {spec.effects_included}")
    if spec.warning:
        print(f"    note             {spec.warning}")
    print(f"\n  accelerator        {COMPUTE_LIBRARY[compute].name}")
    print(f"  left               {MEMORY_LIBRARY[m3].name} x{n3}")
    print(f"  right              {MEMORY_LIBRARY[m4].name} x{n4}")

    # Peak and effective, separately. Matching on the effective figure while
    # the two sides carry different efficiency assumptions would smuggle an
    # assumption into a comparison meant to isolate the interface.
    e3, e4 = MEMORY_LIBRARY[m3].bandwidth_efficiency, MEMORY_LIBRARY[m4].bandwidth_efficiency
    peak3 = MEMORY_LIBRARY[m3].bandwidth_gbytes_s * n3
    peak4 = MEMORY_LIBRARY[m4].bandwidth_gbytes_s * n4
    print(f"\n  -- bandwidth -----------------------------------------------")
    hb = f"  {'':<26s}{'HBM3E':>12s}{'HBM4':>12s}"
    print(hb); print("  " + "-" * (len(hb) - 2))
    print(f"  {'peak (GB/s)':<26s}{peak3:12.0f}{peak4:12.0f}")
    print(f"  {'effective (GB/s)':<26s}{a['bandwidth_gbs']:12.0f}"
          f"{b['bandwidth_gbs']:12.0f}")
    print(f"  {'controller efficiency':<26s}{e3:12.2f}{e4:12.2f}")
    if abs(e3 - e4) > 1e-9:
        print(f"    the two efficiencies differ - an ASSUMPTION, not a "
              f"consequence of width.")
        print(f"    at equal efficiency the effective figures would match to "
              f"{abs(peak4 / peak3 - 1) * 100:.1f}%.")

    # Capacity is the other half of a bandwidth-matched comparison. Half the
    # stacks is half the capacity, and "the same bandwidth from fewer stacks"
    # is only true where the model still fits.
    need_gb = app.required_memory_bytes / 1e9
    print(f"\n  -- capacity ------------------------------------------------")
    print(f"  {'required (GB)':<26s}{need_gb:12.0f}{need_gb:12.0f}")
    print(f"  {'provided (GB)':<26s}{a['capacity_gb']:12.0f}{b['capacity_gb']:12.0f}")
    print(f"  {'margin (GB)':<26s}{a['capacity_gb'] - need_gb:+12.0f}"
          f"{b['capacity_gb'] - need_gb:+12.0f}")
    if b["capacity_gb"] < need_gb or a["capacity_gb"] < need_gb:
        print("    one side does not hold the model. The bandwidth comparison")
        print("    below is arithmetic, not a choice available to a designer.")

    print(f"\n  -- how it runs (simulated) ---------------------------------")
    h = f"  {'':<26s}{'HBM3E':>12s}{'HBM4':>12s}{'change':>10s}"
    print(h); print("  " + "-" * (len(h) - 2))
    for label, key, fmt in (
            ("prefill / TTFT (ms)", "prefill_ms", "{:12.1f}"),
            ("decode rate (tok/s)", "decode_rate", "{:12.1f}"),
            ("inter-token (ms)", "inter_token_ms", "{:12.2f}"),
            ("memory wait (%)", "memory_wait_pct", "{:12.1f}"),
            ("accelerator busy (%)", "accel_util_pct", "{:12.1f}")):
        print(f"  {label:<26s}" + fmt.format(a[key]) + fmt.format(b[key])
              + f"{_delta(a[key], b[key]):>10s}")

    print(f"\n  -- what it costs to build (all figures ESTIMATED) -----------")
    for label, key, fmt in (
            ("energy per token (mJ)", "energy_per_token_mj", "{:12.1f}"),
            ("memory cost index", "cost_index", "{:12.0f}"),
            ("memory footprint (mm2)", "footprint_mm2", "{:12.0f}"),
            ("stacks", "stacks", "{:12.0f}")):
        print(f"  {label:<26s}" + fmt.format(a[key]) + fmt.format(b[key])
              + f"{_delta(a[key], b[key]):>10s}")
    print(f"  {'cooling':<26s}{('compatible' if a['cooling_ok'] else 'INCOMPATIBLE'):>12s}"
          f"{('compatible' if b['cooling_ok'] else 'INCOMPATIBLE'):>12s}")

    print(f"\n  -- whether it ships ----------------------------------------")
    print(f"  {'requirements satisfied':<26s}"
          f"{a['requirements'][0]:>7d}/{a['requirements'][1]:<4d}"
          f"{b['requirements'][0]:>7d}/{b['requirements'][1]:<4d}")
    print(f"  {'system PPACT score':<26s}{a['score']:12.1f}{b['score']:12.1f}"
          f"{_delta(a['score'], b['score']):>10s}")
    print("  (requirements and score answer different questions and are kept "
          "apart)")

    _interpret(a, b, app)
    print(LINE)


def _interpret(a, b, app) -> None:
    """State what happened. No recommendation."""
    print(f"\n  -- what happened -------------------------------------------")
    ma, mb = a["metrics"], b["metrics"]
    lines: List[str] = []

    if abs(b["prefill_ms"] - a["prefill_ms"]) / max(a["prefill_ms"], 1e-9) < 0.02:
        lines.append("Prefill did not improve: it is compute bound, and a wider "
                     "memory does not touch it.")
    if b["decode_rate"] > a["decode_rate"] * 1.05:
        lines.append("Decode throughput rose because the workload stayed memory "
                     "bound on both sides.")
    elif ma["Compute time (ms)"] > ma["Memory time (ms)"]:
        lines.append("The accelerator is compute bound. Additional memory "
                     "bandwidth does not change the achieved rate.")
    else:
        lines.append("Decode throughput did not rise materially.")

    demanded = a["result"].metrics["Jobs demanded"]
    if (a["result"].jobs >= demanded and b["result"].jobs >= demanded):
        lines.append("Both configurations already meet the requested rate. The "
                     "faster memory adds headroom, not delivered throughput.")

    if b["energy_per_token_mj"] < a["energy_per_token_mj"] * 0.95:
        lines.append("Energy per token fell, from fewer picojoules per bit and "
                     "less time spent leaking.")
    elif b["energy_per_token_mj"] > a["energy_per_token_mj"]:
        lines.append("Energy per token ROSE. A faster memory is not "
                     "automatically a more efficient one.")

    if b["cost_index"] > a["cost_index"] * 1.05:
        lines.append(f"Estimated memory-subsystem cost is "
                     f"{(b['cost_index'] / a['cost_index'] - 1) * 100:.0f}% higher. "
                     f"This is a model figure, not a market price.")
    elif b["cost_index"] < a["cost_index"] * 0.95:
        lines.append(f"Estimated memory-subsystem cost is "
                     f"{(1 - b['cost_index'] / a['cost_index']) * 100:.0f}% lower. "
                     f"Estimated: stack price, early-production yield, base die "
                     f"and supply terms would all move it.")
    for text in lines:
        print(f"    {text}")
    if b["stacks"] < a["stacks"] and b["capacity_gb"] >= app.required_memory_bytes / 1e9:
        print("\n    Under the selected capacity requirement and cost assumptions,")
        print("    HBM4 reaches approximately the same effective bandwidth with")
        print(f"    {a['stacks']} stacks reduced to {b['stacks']}, lowering estimated")
        print("    memory-subsystem cost and package footprint while preserving")
        print("    decode performance.")
    print("\n    Whether that trade is worth making depends on what the product")
    print("    is for. The tool does not decide it.")


def sweep_memories(app_key: str = "llm_service",
                   compute: str = "datacenter_gpu",
          duration_s: float = 60.0) -> None:
    """All four comparisons in order."""
    for key in COMPARISONS:
        compare(app_key, key, compute, duration_s)
