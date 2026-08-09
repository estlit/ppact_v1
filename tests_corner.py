"""Corner-case verification for the PPACT model.

The deployment suite checks that the tool runs. This one checks that the
numbers it produces are consistent, which is a different question and the one
that actually matters once the model is being used to teach.

Each PATH is a parameter space explored deliberately rather than sampled. For a
two-parameter space that means the four corners, the four edge midpoints, the
centre, and the points just outside the valid range - twelve or more per path,
not one happy case.

    PATH A  execution model      overlap x workload balance
    PATH B  gate boundaries      each gate at, just under, just over
    PATH C  invariants           identities that must hold everywhere
    PATH D  monotonicity         direction of every knob
    PATH E  degenerate inputs    zeros, extremes, division-by-zero guards
    PATH F  scoring              bounds and saturation of the six game axes

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

import dataclasses
import itertools
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppact import (APPLICATION_LIBRARY, COMPUTE_LIBRARY, CPU_LIBRARY,
                   MEMORY_LIBRARY, NODE_LIBRARY, SystemConfig, evaluate_system,
                   evaluate_with_precision, make_custom_application)
from ppact.game import score_design, overall, AXES, PRECISION_OPTIONS

RESULTS = []
TOL = 1e-9


def check(path, name, cond, detail=""):
    RESULTS.append((path, name, bool(cond), detail))
    if not cond:
        print(f"  [FAIL] {path} {name}   {detail}")
    return bool(cond)


def base(app="drone", compute="npu_32x32", memory="LPDDR5", n=2, **kw):
    return evaluate_system(APPLICATION_LIBRARY[app],
                           SystemConfig("cortex_a78_x4", compute, memory, n, **kw))


# ==============================================================================
# PATH A - execution model: overlap x workload balance
# ==============================================================================
#
# Two parameters, so the space is a rectangle: overlap from 0 to 1, and the
# compute/transfer balance from strongly compute-bound to strongly
# memory-bound. Corners, edges, centre and out-of-range, twelve points.

def path_a():
    P = "A"
    # compute-dominant: small model on a big array. memory-dominant: LLM decode.
    cases = {
        "compute-dominant": ("smart_camera", "npu_16x16", 8),
        "balanced":         ("drone", "npu_32x32", 2),
        "memory-dominant":  ("mobile_ai", "npu_128x128", 1),
    }
    for label, (app, comp, n) in cases.items():
        for ov in (0.0, 0.5, 1.0):
            r = base(app, comp, "LPDDR5", n, overlap_ratio=ov)
            # A roofline is a statement about a machine that runs. One that
            # cannot hold its model has no timing to be inside anything.
            if "INFEASIBLE" in r.status:
                continue
            m = r.metrics
            c, t, h = (m["Compute time (ms)"], m["Memory time (ms)"],
                       m["Hidden transfer (ms)"])
            core = (m["Latency (ms)"] - m["CPU active (ms)"]
                    - m.get("Serving overhead (ms)", 0.0))
            check(P, f"{label} ov={ov} core == c+t-hidden",
                  abs(core - (c + t - h)) < 1e-6, f"{core:.6f} vs {c + t - h:.6f}")
            check(P, f"{label} ov={ov} hidden == ov*min(c,t)",
                  abs(h - ov * min(c, t)) < 1e-6, f"{h:.6f} vs {ov * min(c, t):.6f}")
            check(P, f"{label} ov={ov} core within [max, sum]",
                  max(c, t) - 1e-6 <= core <= c + t + 1e-6, f"core={core:.4f}")

    # the two corners the model used to assume, checked against closed forms
    r1 = base("drone", "npu_32x32", "LPDDR5", 2, overlap_ratio=1.0).metrics
    r0 = base("drone", "npu_32x32", "LPDDR5", 2, overlap_ratio=0.0).metrics
    check(P, "overlap 1 reproduces max()",
          abs((r1["Latency (ms)"] - r1["CPU active (ms)"]
               - r1.get("Serving overhead (ms)", 0.0))
              - max(r1["Compute time (ms)"], r1["Memory time (ms)"])) < 1e-6)
    check(P, "overlap 0 reproduces sum()",
          abs((r0["Latency (ms)"] - r0["CPU active (ms)"]
               - r0.get("Serving overhead (ms)", 0.0))
              - (r0["Compute time (ms)"] + r0["Memory time (ms)"])) < 1e-6)
    check(P, "overlap 0 is never faster than overlap 1",
          r0["Latency (ms)"] >= r1["Latency (ms)"] - 1e-9)

    # out of range: the model must not silently produce nonsense
    for ov in (-0.5, 1.5):
        try:
            m = base("drone", "npu_32x32", "LPDDR5", 2, overlap_ratio=ov).metrics
            core = m["Latency (ms)"]
            sane = 0 < core < 1e6 and m["Hidden transfer (ms)"] >= -1e-9
            check(P, f"out-of-range overlap {ov} stays finite and non-negative", sane,
                  f"latency={core}, hidden={m['Hidden transfer (ms)']}")
        except Exception as exc:
            check(P, f"out-of-range overlap {ov} handled", False, repr(exc))


# ==============================================================================
# PATH B - gate boundaries: at, just under, just over
# ==============================================================================

def path_b():
    P = "B"
    spec = [
        ("power",      "power_budget_w",             "System power (W)",        False),
        ("cost",       "bom_budget_usd",             "System cost (USD)",       False),
        ("board",      "board_budget_mm2",           "Board area (mm2)",        False),
        ("soc_die",    "soc_silicon_budget_mm2",     "SoC silicon (mm2)",       False),
        ("thermal",    "thermal_limit_w_per_mm2",    "Power density (W/mm2)",   False),
        ("latency",    "latency_budget_ms",          "Latency (ms)",            False),
        ("throughput", "target_inferences_per_s",    "Throughput (inf/s)",      True),
        ("accuracy",   "required_accuracy_pct",      "Deployment accuracy (%)", True),
    ]
    app = APPLICATION_LIBRARY["drone"]
    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
    actual = evaluate_system(app, cfg).metrics

    for gate, budget_field, metric, higher_is_better in spec:
        value = actual[metric]
        for label, factor in (("exactly at", 1.0), ("just inside", 1.0001),
                              ("just outside", 0.9999)):
            if higher_is_better:
                budget = value * (2.0 - factor)      # mirror for >= gates
            else:
                budget = value * factor
            tuned = dataclasses.replace(app, **{budget_field: budget})
            r = evaluate_system(tuned, cfg)
            expect = (value >= budget - 1e-12) if higher_is_better else (value <= budget + 1e-12)
            check(P, f"{gate} {label}", r.gate[gate] == expect,
                  f"value={value:.6g} budget={budget:.6g} gate={r.gate[gate]} expected={expect}")

    # capacity: exactly enough, one byte short, one byte over
    llm = APPLICATION_LIBRARY["llm_service"]
    cap = evaluate_system(llm, SystemConfig("server_x86_x32", "npu_128x128",
                                            "HBM3E", 8)).metrics["Memory capacity (GB)"] * 1e9
    for label, need in (("exact", cap), ("one byte short", cap - 1.0),
                        ("one byte over", cap + 1.0)):
        tuned = dataclasses.replace(llm, weight_bytes=need, kv_cache_bytes=0.0,
                                    runtime_overhead_bytes=0.0)
        r = evaluate_system(tuned, SystemConfig("server_x86_x32", "npu_128x128", "HBM3E", 8))
        check(P, f"capacity {label}", r.gate["capacity"] == (cap >= need),
              f"cap={cap:.0f} need={need:.0f} gate={r.gate['capacity']}")


# ==============================================================================
# PATH C - invariants that must hold for every combination
# ==============================================================================

def path_c():
    P = "C"
    combos = list(itertools.product(
        list(APPLICATION_LIBRARY), ["cpu_only", "mobile_gpu", "npu_16x16",
                                    "npu_128x128", "datacenter_gpu"],
        list(MEMORY_LIBRARY), (1, 8)))
    bad_energy = bad_contrib = bad_time = bad_sign = bad_finite = 0
    infeasible = 0
    for app_key, comp, mem, n in combos:
        r = evaluate_system(APPLICATION_LIBRARY[app_key],
                            SystemConfig("cortex_a78_x4", comp, mem, n))
        # A configuration that cannot hold its model has no timing and no
        # energy. Its performance figures are deliberately not-a-number so
        # that nothing downstream can use them, and this loop is downstream.
        if "INFEASIBLE" in r.status:
            infeasible += 1
            continue
        m = r.metrics

        shares = (m["  compute share (%)"] + m["  memory share (%)"]
                  + m["  cpu share (%)"] + m["  static share (%)"])
        if abs(shares - 100.0) > 1e-6:
            bad_energy += 1

        contrib = (m["Latency contribution, compute (%)"]
                   + m["Latency contribution, memory (%)"])
        if not (abs(contrib - 100.0) < 1e-6 or abs(contrib) < 1e-9):
            bad_contrib += 1

        if m["Latency (ms)"] < max(m["Compute time (ms)"], m["Memory time (ms)"]) - 1e-6:
            bad_time += 1

        for key in ("Compute time (ms)", "Memory time (ms)", "Hidden transfer (ms)",
                    "Compute data-wait (ms)", "DRAM traffic (MB)", "System power (W)",
                    "System cost (USD)", "Total silicon (mm2)", "Board area (mm2)"):
            if m[key] < -1e-9:
                bad_sign += 1
            if not (abs(m[key]) < float("inf")) or m[key] != m[key]:
                bad_finite += 1

    total = len(combos) - infeasible
    check(P, "most combinations are feasible and were checked",
          total > len(combos) * 0.5,
          f"{total} of {len(combos)} checked, {infeasible} could not hold "
          f"their model")
    check(P, f"energy shares sum to 100 ({total} combos)", bad_energy == 0, f"{bad_energy} bad")
    check(P, f"latency contributions sum to 100 ({total})", bad_contrib == 0, f"{bad_contrib} bad")
    check(P, f"latency >= max(compute, transfer) ({total})", bad_time == 0, f"{bad_time} bad")
    check(P, f"no negative quantities ({total})", bad_sign == 0, f"{bad_sign} bad")
    check(P, f"no NaN or infinity ({total})", bad_finite == 0, f"{bad_finite} bad")


# ==============================================================================
# PATH D - monotonicity: every knob must move results the right way
# ==============================================================================

def path_d():
    P = "D"
    app = "mobile_ai"

    lat = [base(app, "npu_32x32", "LPDDR5", 2, overlap_ratio=o).metrics["Latency (ms)"]
           for o in (0.0, 0.25, 0.5, 0.75, 1.0)]
    check(P, "more overlap never increases latency",
          all(a >= b - 1e-9 for a, b in zip(lat, lat[1:])), str([round(x, 3) for x in lat]))

    bw = [base(app, "npu_32x32", "LPDDR5", n).metrics["Effective bandwidth (GB/s)"]
          for n in (1, 2, 4, 8)]
    check(P, "more memory packages give more bandwidth",
          all(a < b for a, b in zip(bw, bw[1:])), str([round(x, 1) for x in bw]))

    eff = [base(app, "npu_32x32", "LPDDR5", 2,
                bandwidth_efficiency=e).metrics["Latency (ms)"]
           for e in (0.5, 0.6, 0.7, 0.8, 0.9)]
    check(P, "better bandwidth utilisation never increases latency",
          all(a >= b - 1e-9 for a, b in zip(eff, eff[1:])), str([round(x, 3) for x in eff]))

    order = ["N28", "N16", "N12", "N7", "N5", "N4", "N3", "N2", "A16"]
    areas = [COMPUTE_LIBRARY["npu_32x32"].die_area_at(n) for n in order]
    check(P, "smaller node gives smaller die",
          all(a > b for a, b in zip(areas, areas[1:])), str([round(x, 3) for x in areas]))
    energies = [COMPUTE_LIBRARY["npu_32x32"].energy_pj_per_mac_at(n) for n in order]
    check(P, "smaller node gives lower energy per MAC",
          all(a > b for a, b in zip(energies, energies[1:])))
    permm2 = [NODE_LIBRARY[n].usd_per_mm2 for n in order]
    check(P, "smaller node costs more per good mm2",
          all(a < b for a, b in zip(permm2, permm2[1:])), str([round(x, 3) for x in permm2]))

    sram = [dataclasses.replace(COMPUTE_LIBRARY["npu_32x32"], sram_kb=s)
            for s in (128, 512, 2048, 8192)]
    traffic = []
    saved = COMPUTE_LIBRARY["npu_32x32"]
    for spec in sram:
        COMPUTE_LIBRARY["npu_32x32"] = spec
        traffic.append(base(app, "npu_32x32", "LPDDR5", 2).metrics["DRAM traffic (MB)"])
    COMPUTE_LIBRARY["npu_32x32"] = saved
    check(P, "more on-chip SRAM never increases DRAM traffic",
          all(a >= b - 1e-9 for a, b in zip(traffic, traffic[1:])),
          str([round(x, 1) for x in traffic]))

    prec = ["FP32", "FP16", "INT8", "INT4"]
    acc, tr = [], []
    for p in prec:
        m = evaluate_with_precision(app, "mobile_gpu" if p == "FP32" else "npu_32x32",
                                    "LPDDR5", 2, "N5", p).metrics
        acc.append(m["Deployment accuracy (%)"]); tr.append(m["DRAM traffic (MB)"])
    check(P, "lower precision means less traffic", tr[-1] < tr[-2] < tr[1],
          str([round(x, 1) for x in tr]))
    check(P, "INT4 is less accurate than INT8", acc[-1] < acc[-2],
          f"{acc[-1]:.2f} vs {acc[-2]:.2f}")

    arrays = ["npu_16x16", "npu_20x20", "npu_24x24", "npu_32x32", "npu_64x64", "npu_128x128"]
    ctime = [base("drone", a, "LPDDR5", 2).metrics["Compute time (ms)"] for a in arrays]
    check(P, "a bigger array computes faster",
          all(a > b for a, b in zip(ctime, ctime[1:])), str([round(x, 3) for x in ctime]))


# ==============================================================================
# PATH E - degenerate inputs
# ==============================================================================

def path_e():
    P = "E"
    cases = {
        "zero compute": dict(mac_per_inference=0.0),
        "zero weights": dict(weight_bytes=0.0),
        "zero activations": dict(activation_bytes=0.0),
        "everything zero": dict(mac_per_inference=0.0, weight_bytes=0.0,
                                activation_bytes=0.0, kv_cache_bytes=0.0,
                                runtime_overhead_bytes=0.0),
        "one byte model": dict(weight_bytes=1.0),
        "enormous model": dict(weight_bytes=1e13),
        "single stream": dict(streams=1),
        "many streams": dict(streams=64),
        "zero margin limit": dict(accuracy_margin_limit_pp=0.0),
        "accuracy above 100": dict(reference_accuracy_pct=100.0,
                                   required_accuracy_pct=100.0),
        "zero volume": dict(production_volume=0),
        "tiny working set": dict(activation_working_set_kb=1.0),
        "huge working set": dict(activation_working_set_kb=1e7),
    }
    app = APPLICATION_LIBRARY["drone"]
    for label, kw in cases.items():
        try:
            tuned = dataclasses.replace(app, **kw)
            r = evaluate_system(tuned, SystemConfig("cortex_a78_x4", "npu_32x32",
                                                    "LPDDR5", 2))
            m = r.metrics
            # A model that cannot fit in memory deliberately produces
            # not-a-number for its PERFORMANCE figures, so that nothing
            # downstream can rank or compare a machine which cannot exist.
            # Its physical and economic figures must still be finite - the
            # board has an area and a price whether or not it can run.
            from ppact.system import PERFORMANCE_METRICS
            infeasible = "INFEASIBLE" in r.status
            checked = {k: v for k, v in m.items()
                       if isinstance(v, (int, float))
                       and not (infeasible and k in PERFORMANCE_METRICS)}
            finite = all(v == v and abs(v) < float("inf")
                         for v in checked.values())
            label2 = (f"{label} produces finite numbers"
                      if not infeasible else
                      f"{label} is infeasible and its physical figures are "
                      f"still finite")
            check(P, label2, finite,
                  str([k for k, v in checked.items()
                       if not (v == v and abs(v) < float("inf"))])[:120])
        except Exception as exc:
            check(P, f"{label} does not raise", False, f"{type(exc).__name__}: {exc}")

    # engines with no accelerator SRAM or no MAC array
    for comp in ("cpu_only", "mobile_gpu", "datacenter_gpu"):
        try:
            m = base("drone", comp, "LPDDR5", 1).metrics
            check(P, f"{comp} evaluates", m["Latency (ms)"] > 0)
        except Exception as exc:
            check(P, f"{comp} evaluates", False, f"{type(exc).__name__}: {exc}")

    # every application against every memory at the extremes of device count
    fails = []
    for app_key in APPLICATION_LIBRARY:
        for mem in MEMORY_LIBRARY:
            for n in (1, 8):
                try:
                    evaluate_system(APPLICATION_LIBRARY[app_key],
                                    SystemConfig("cortex_a78_x4", "npu_16x16", mem, n))
                except Exception as exc:
                    fails.append(f"{app_key}/{mem}/{n}: {exc}")
    check(P, "every application x memory x device count evaluates",
          not fails, "; ".join(fails[:3]))

    # a custom application built from nothing
    try:
        make_custom_application("Edge case probe", mac_per_inference=1.0,
                                weight_bytes=1.0, activation_bytes=1.0,
                                activation_working_set_kb=1.0,
                                target_inferences_per_s=1.0, power_budget_w=0.001,
                                bom_budget_usd=0.01, board_budget_mm2=1.0,
                                production_volume=1, register_as="__probe__")
        m = evaluate_system(APPLICATION_LIBRARY["__probe__"],
                            SystemConfig("cortex_a78_x4", "npu_16x16", "LPDDR5", 1)).metrics
        check(P, "degenerate custom application evaluates", m["Latency (ms)"] > 0)
    except Exception as exc:
        check(P, "degenerate custom application evaluates", False, repr(exc))
    finally:
        APPLICATION_LIBRARY.pop("__probe__", None)


# ==============================================================================
# PATH F - scoring bounds and saturation
# ==============================================================================

def path_f():
    P = "F"
    out_of_range = saturated_high = saturated_low = infeasible_skipped = 0
    spreads = []
    for app_key in APPLICATION_LIBRARY:
        for comp in ("cpu_only", "mobile_gpu", "npu_16x16", "npu_32x32",
                     "npu_128x128", "datacenter_gpu"):
            for mem in MEMORY_LIBRARY:
                r = evaluate_system(APPLICATION_LIBRARY[app_key],
                                    SystemConfig("cortex_a78_x4", comp, mem, 2))
                # A design that cannot hold its model has no performance to
                # score. Ranking it against ones that can would put an
                # impossible machine in a league table.
                if "INFEASIBLE" in r.status:
                    infeasible_skipped += 1
                    continue
                s = score_design(r)
                if any(v < -1e-9 or v > 100 + 1e-9 for v in s.values()):
                    out_of_range += 1
                if all(v > 99.9 for v in s.values()):
                    saturated_high += 1
                if all(v < 0.1 for v in s.values()):
                    saturated_low += 1
                spreads.append(max(s.values()) - min(s.values()))
    check(P, "all scores within 0..100", out_of_range == 0, f"{out_of_range} bad")
    check(P, "and infeasible designs were left out of the scoring",
          infeasible_skipped > 0,
          f"{infeasible_skipped} skipped - a machine that cannot hold its "
          f"model does not belong in a ranking")
    check(P, "no design saturates every axis high", saturated_high == 0,
          f"{saturated_high} designs")
    check(P, "no design saturates every axis low", saturated_low == 0,
          f"{saturated_low} designs")
    check(P, "axes discriminate on average",
          sum(spreads) / len(spreads) > 20, f"mean spread {sum(spreads)/len(spreads):.1f}")

    # weighted overall must stay in range for degenerate weight sets
    r = base("drone")
    s = score_design(r)
    for label, w in (("all zero", {a: 0.0 for a in AXES}),
                     ("one axis only", {**{a: 0.0 for a in AXES}, "Cost": 1.0}),
                     ("negative ignored", {**{a: 1.0 for a in AXES}, "Power": 0.0}),
                     ("huge weight", {**{a: 1.0 for a in AXES}, "Accuracy": 1e6})):
        v = overall(s, w)
        check(P, f"overall stays in range: {label}", -1e-9 <= v <= 100 + 1e-9, f"{v}")


def main():
    print("=" * 78)
    print(" CORNER-CASE VERIFICATION")
    print("=" * 78)
    for fn in (path_a, path_b, path_c, path_d, path_e, path_f):
        label = fn.__name__.split("_")[1].upper()
        before = len(RESULTS)
        try:
            fn()
        except Exception as exc:
            check(label, "path completed", False, f"{type(exc).__name__}: {exc}")
        run = RESULTS[before:]
        ok = sum(1 for *_, passed, _ in [(r[0], r[1], r[2], r[3]) for r in run] if passed)
        print(f"  PATH {label}: {ok}/{len(run)} passed")

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r[2])
    print("\n" + "=" * 78)
    print(f" {passed} / {total} checks passed")
    print("=" * 78)
    for path, name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED [{path}] {name}\n           {detail[:200]}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
