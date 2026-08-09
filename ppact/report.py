"""
ppact.report - text output

All printing lives here so the models stay free of formatting concerns.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from typing import Sequence

from .memory import AXIS_ORDER, ANCHORS, PPACTResult
from .system import SystemResult


def print_memory_report(res: PPACTResult) -> None:
    s, m, w = res.spec, res.metrics, res.wafer
    line = "=" * 66

    print(f"\n{line}\n [ {s.name} - {s.category} ]\n{line}")
    print(f"  Bus config     : {s.bus_config}")
    print(f"  VDDQ / IO      : {s.vddq_volt} V, {s.io_standard}")
    print(f"  Error control  : {s.error_handling}")
    print(f"  Packaging      : {s.packaging}")

    print(f"\n-- Performance & Power " + "-" * 43)
    print(f"  Package BW     : {m['Package bandwidth (GB/s)']:.1f} GB/s")
    print(f"  System BW      : {m['System bandwidth (GB/s)']:.1f} GB/s "
          f"({s.typical_system_devices} packages)")
    print(f"  Capacity       : {m['Package capacity (GB)']:.1f} GB")
    print(f"  Peak power     : {m['Peak power (W)']:.2f} W "
          f"@ {s.energy_pj_per_bit:.1f} pJ/bit, 100% utilization")

    print(f"\n-- Manufacturing (300 mm wafer) " + "-" * 34)
    print(f"  Die area       : {s.die_area_mm2:.1f} mm2   D0 = {s.defect_density_per_cm2}/cm2")
    print(f"  Gross DPW      : {w.gross_dpw} dies")
    print(f"  Poisson yield  : {w.poisson_yield * 100:.2f}%")
    print(f"  After repair   : {w.effective_yield * 100:.2f}% "
          f"(redundancy rescue {s.redundancy_repair_rate * 100:.0f}%)")
    print(f"  Net good dies  : {w.net_dpw} KGD")

    print(f"\n-- Cost " + "-" * 58)
    print(f"  KGD cost       : ${w.die_cost_usd:.2f} x {s.dies_per_package} die "
          f"= ${m['Silicon cost (USD)']:.2f}")
    print(f"  Assembly       : ${s.package_cost_usd:.2f} "
          f"at {m['Assembly yield (%)']:.1f}% stack yield")
    print(f"  Total          : ${m['Package cost (USD)']:.2f}")
    print(f"  Cost per BW    : ${m['Cost per BW (USD per GB/s)']:.4f} per GB/s   (context only)")
    print(f"  Cost per GB    : ${m['Cost per capacity (USD per GB)']:.2f} per GB        (context only)")

    print(f"\n-- Area & Thermal " + "-" * 48)
    print(f"  Board area     : {s.board_area_mm2:.0f} mm2 "
          f"({m['Board area per BW (mm2 per GB/s)']:.2f} mm2 per GB/s)")
    print(f"  Pkg footprint  : {s.package_footprint_mm2:.0f} mm2")
    print(f"  Power density  : {m['Power density (W per mm2)']:.4f} W/mm2")
    print(f"  Cooling        : {s.cooling_class}")

    print(f"\n-- PPACT scores " + "-" * 50)
    for axis in AXIS_ORDER:
        val = res.scores[axis]
        from .visual import render_bar
        bar = render_bar(val, 100.0, 25).rstrip(".")
        print(f"  {axis:<20s} {val:6.1f}  {bar}")
    if s.notes:
        # Wrapped. A library note is a paragraph and was
        # printed on one line - 233 characters on the
        # widest, which no terminal shows and no reader
        # follows.
        from .visual.text import wrap_text as _wrap
        print()
        for _i, _l in enumerate(_wrap(str(s.notes), 70)):
            print(f"  Note: {_l}" if _i == 0
                  else f"        {_l}")


def print_comparison(results: Sequence[PPACTResult]) -> None:
    if len(results) < 2:
        return
    names = [r.spec.name for r in results]
    print("\n" + "=" * 66)
    print(" [ Side-by-side comparison ]")
    print("=" * 66)
    header = f"{'Metric':<36}" + "".join(f"{n:>14s}" for n in names)
    print(header)
    print("-" * len(header))
    for key in results[0].metrics:
        row = f"{key:<36}"
        for r in results:
            row += f"{r.metrics[key]:>14.3f}"
        print(row)
    print("-" * len(header))
    for axis in AXIS_ORDER:
        row = f"{'SCORE: ' + axis:<36}"
        for r in results:
            row += f"{r.scores[axis]:>14.1f}"
        print(row)


def print_anchor_table() -> None:
    print("\n" + "=" * 66)
    print(" [ Scoring anchors - why each axis is scaled this way ]")
    print("=" * 66)
    for axis, a in ANCHORS.items():
        scale = "log" if a.log_scale else "linear"
        print(f"\n  {axis}")
        print(f"    quantity : {a.label} [{a.unit}], {scale} scale")
        print(f"    0 pts at : {a.at_zero:g}      100 pts at : {a.at_hundred:g}")
        print(f"    reason   : {a.rationale}")


# ==============================================================================

def print_gate(results: Sequence[SystemResult]) -> None:
    app = results[0].app
    print("=" * 78)
    print(f" STAGE 1 - CONSTRAINT GATE : {app.name}")
    print("=" * 78)
    print(f"  Model      : {app.model}")
    print(f"  Required   : {app.target_inferences_per_s:g} inf/s, "
          f"<= {app.latency_budget_ms:g} ms")
    if app.closed_loop:
        print(f"  Closed loop: react within {app.stopping_distance_budget_m:g} m "
              f"at {app.cruise_speed_m_s:g} m/s "
              f"(+{app.control_overhead_ms:g} ms sensor and control)")
    print(f"  Budgets    : {app.power_budget_w:g} W, ${app.bom_budget_usd:,.0f}, "
          f"{app.soc_silicon_budget_mm2:g} mm2 SoC die, {app.board_budget_mm2:g} mm2 board")
    print(f"  Thermal    : {app.cooling}, <= {app.thermal_limit_w_per_mm2:g} W/mm2")
    integ = ("one monolithic die" if app.integration == "monolithic"
             else "separate dies")
    from .process import node_name as _nn
    print(f"  Process    : host {_nn(app.default_soc_node)}, accelerator "
          f"{_nn(app.default_accel_node)}, {integ}")
    print(f"  Accuracy   : model {app.reference_accuracy_pct:g}% reference, "
          f"{app.required_accuracy_pct:g}% required "
          f"({app.reference_accuracy_pct - app.required_accuracy_pct:.1f} pp "
          f"budget for quantisation and operator rewrites)")
    print(f"  Volume     : {app.production_volume:,} units "
          f"(mask/NRE is reported, not gated)")
    print()

    checks = list(results[0].gate)
    head = f"  {'candidate':<44s}" + "".join(f"{c[:7]:>9s}" for c in checks) + "   verdict"
    print(head); print("  " + "-" * (len(head) - 2))
    for r in results:
        row = f"  {r.label:<44s}" + "".join(
            f"{('ok' if r.gate[c] else 'FAIL'):>9s}" for c in checks)
        print(row + ("   PASS" if r.passes else "   REJECTED"))

    print("\n  why each candidate failed:")
    any_fail = False
    for r in results:
        bad = [c for c in checks if not r.gate[c]]
        if not bad:
            continue
        any_fail = True
        detail = []
        for c in bad:
            if c == "power":
                detail.append(f"{r.metrics['System power (W)']:.1f} W > {r.app.power_budget_w:g}")
            elif c == "cost":
                detail.append(f"${r.metrics['System cost (USD)']:,.0f} > ${r.app.bom_budget_usd:,.0f}")
            elif c == "soc_die":
                detail.append(f"SoC die {r.metrics['SoC silicon (mm2)']:.0f} > "
                              f"{r.app.soc_silicon_budget_mm2:g} mm2")
            elif c == "board":
                detail.append(f"{r.metrics['Board area (mm2)']:.0f} > {r.app.board_budget_mm2:g} mm2")
            elif c == "thermal":
                detail.append(f"{r.metrics['Power density (W/mm2)']:.3f} > "
                              f"{r.app.thermal_limit_w_per_mm2:g} W/mm2")
            elif c == "latency":
                detail.append(f"{r.metrics['Latency (ms)']:.1f} > {r.app.latency_budget_ms:g} ms")
            elif c == "throughput":
                detail.append(f"{r.metrics['Throughput (inf/s)']:.1f} < "
                              f"{r.app.target_inferences_per_s:g} inf/s")
            elif c == "capacity":
                detail.append(f"{r.metrics['Memory capacity (GB)']:.1f} GB < "
                              f"{r.app.required_memory_bytes/1e9:.1f} GB needed")
            elif c == "auto_qual":
                detail.append("no automotive-qualified part")
            elif c == "accuracy":
                detail.append(f"accuracy {r.metrics['Deployment accuracy (%)']:.1f}% < "
                              f"{r.app.required_accuracy_pct:g}% required")
            elif c == "reaction":
                detail.append(f"reacts after {r.metrics['Reaction distance (m)']:.2f} m "
                              f"> {r.app.stopping_distance_budget_m:g} m")
        print(f"    {r.label:<44s} {', '.join(detail)}")
    if not any_fail:
        print("    (none - every candidate fits the budgets)")


def print_analysis(results: Sequence[SystemResult]) -> None:
    print("\n" + "=" * 78)
    print(" STAGE 2 - WHERE THE TIME AND ENERGY GO")
    print("=" * 78)
    keys = ["Reference accuracy (%)", "Deployment accuracy (%)",
            "Required accuracy (%)", "Accuracy margin (pp)", "Useful accuracy (%)",
            "Latency (ms)", "End-to-end latency (ms)", "Reaction distance (m)",
            "CPU preprocess (ms)", "CPU dispatch (ms)", "CPU postprocess (ms)",
            "CPU active (ms)", "CPU accelerator-wait (ms)", "CPU latency share (%)",
            "Pixels per stream", "Streams", "Total pixels per job",
            "Preprocess offload (ms)", "Offload calls", "Offload dispatch (ms)",
            "Offload transfer (ms)", "Offload overhead (ms)",
            "ISP active (ms)", "ISP hidden (ms)", "ISP exposed (ms)",
            "ISP energy (mJ)",
            "Accelerator total active (ms)",
            "ISP area (mm2)", "Accelerator area uplift (%)",
            "Compute time (ms)", "Memory time (ms)", "Overlap ratio",
            "Hidden transfer (ms)", "Compute data-wait (ms)",
            "Compute utilisation (%)",
            "Latency contribution, compute (%)",
            "Latency contribution, memory (%)",
            "Arithmetic intensity (MAC/B)", "Ridge point (MAC/B)",
            "Activation reload factor", "Weight fetches",
            "DRAM traffic (MB)", "Peak bandwidth (GB/s)",
            "Effective bandwidth (GB/s)", "Bandwidth efficiency (%)",
            "BW to sustain peak (GB/s)",
            "Effective TOPS", "Peak TOPS",
            "Energy per inference (mJ)", "  compute share (%)", "  memory share (%)",
            "  cpu share (%)", "  static share (%)",
            "Compute power (W)", "Memory power (W)",
            "CPU die area (mm2)", "Accel die area (mm2)", "Accel silicon cost (USD)",
            "Mask/NRE per unit (USD)",
            "Accel MAC area (mm2)", "Accel SRAM area (mm2)",
            "Accel control area (mm2)", "Accel SRAM share (%)",
            "System power (W)", "Thermal margin (%)", "SoC silicon (mm2)", "Memory silicon (mm2)",
            "Total silicon (mm2)", "Board area (mm2)",
            "System cost (USD)", "Power density (W/mm2)"]
    head = f"  {'':<30s}" + "".join(f"{r.label[:16]:>18s}" for r in results)
    print(head); print("  " + "-" * (len(head) - 2))
    for k in keys:
        if not any(k in r.metrics for r in results):
            continue        # undefined for every candidate - omit rather than fake
        row = f"  {k:<30s}"
        for r in results:
            row += f"{r.metrics[k]:>18.3f}" if k in r.metrics else f"{'n/a':>18s}"
        print(row)
    if any(r.status != "OK" for r in results):
        print(f"  {'status':<30s}" + "".join(f"{r.status[:17]:>18s}" for r in results))
    print(f"  {'bottleneck':<30s}" + "".join(f"{r.bound_by:>18s}" for r in results))
    # Imported HERE. The name was imported inside a different function and
    # used in this one, which raises NameError on exactly the path that
    # reaches this line - the comparison table - and nowhere else.
    from .process import node_name as _nn
    print(f"  {'host / accel node':<30s}"
          + "".join(f"{_nn(r.soc_node) + ' / ' + _nn(r.accel_node):>18s}"
                    for r in results))
    print(f"  {'integration':<30s}"
          + "".join(f"{r.integration:>18s}" for r in results))


# ==============================================================================
