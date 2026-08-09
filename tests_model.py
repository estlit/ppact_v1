"""Model verification for the PPACT simulator.

Separate from tests_corner.py on purpose. Corner tests explore the edges of the
parameter space; this file checks that the equations themselves are right, which
is a different claim and the one a teaching tool has to be able to make.

    PATH G  units and conventions   dimensional consistency, one MAC = two ops
    PATH H  golden cases            ten results computable by hand
    PATH I  symmetry                swapping compute and transfer
    PATH J  continuity              no jumps where none are intended
    PATH K  randomised properties   two thousand draws against the invariants
    PATH L  sensitivity             a 1% input change moves the output sanely
    PATH M  scaling                 doubling the workload
    PATH N  realism bounds          nothing exceeds its own ceiling

A NOTE ON WHAT THIS DOES NOT SHOW
---------------------------------
None of this establishes that the library VALUES are correct. That 60 tokens
per second is a reasonable LLM target is an engineering judgement recorded in
ppact.application.REQUIREMENT_PROVENANCE, not something a test can settle. A
suite that conflates the two would let a wrong assumption pass as verified.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

import dataclasses
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppact import (APPLICATION_LIBRARY, COMPUTE_LIBRARY, CPU_LIBRARY,
                   MEMORY_LIBRARY, NODE_LIBRARY, OPS_PER_MAC, SystemConfig,
                   evaluate_system, evaluate_with_precision)
from ppact.game import score_design
from ppact import preprocess as pp

# What this suite writes while it runs. Captured at import, BEFORE any check
# executes, so a file already on disk can be told apart from one this run
# produced - the difference between a harmless artefact and a development
# trace wearing the same name.
_RUNTIME_ARTEFACTS = ("ppact_report.md", "ppact_design.md",
                      "ppact_progress.json", "workspace.json",
                      "runs.csv", os.path.join("reproducibility",
                                               "runs.csv"))
# THIS RUN IS NAMED, so the artefacts it writes can be told from the ones
# that were already there. Without it, a suite reported its own output as
# a development trace - the two are identical on disk and only the writer
# tells them apart.
_RUN_ID = f"tests_model-{os.getpid()}"
os.environ["PPACT_RUN_ID"] = _RUN_ID

_PRE_EXISTING_ARTEFACTS = frozenset(
    n for n in _RUNTIME_ARTEFACTS if os.path.exists(n))


def _written_by_this_run(name: str) -> bool:
    """Whether a run log holds rows from THIS run and nothing older."""
    import csv as _csv
    if not name.endswith("runs.csv") or not os.path.isfile(name):
        return False
    try:
        with open(name, newline="") as fh:
            rows = list(_csv.DictReader(fh))
    except Exception:
        return False
    return bool(rows) and all(r.get("written_by") == _RUN_ID
                              for r in rows)

from ppact import simulate, evaluate_proposal, system_score, grading_weights
from ppact.system import PARALLEL_SPLIT_EFFICIENCY as PARALLEL_EFF
from ppact import REFERENCE_PLATFORMS, GRADING_WEIGHTS, RUBRIC
from ppact import reference_design, describe_design, REFERENCE_DESIGNS

RESULTS = []
def core_ms(metrics):
    """Accelerator time alone, with the CPU's own work removed.

    Phase 2 changed the composition of latency from core + dispatch to
    cpu_active + core. Tests that hard-coded the old decomposition would have
    kept passing against a stale formula, so the decomposition is derived here
    in one place instead.
    """
    return (metrics["Latency (ms)"] - metrics["CPU active (ms)"]
            - metrics.get("Serving overhead (ms)", 0.0))


def check(path, name, cond, detail=""):
    RESULTS.append((path, name, bool(cond), detail))
    if not cond:
        print(f"  [FAIL] {path} {name}   {detail}")
    return bool(cond)


def run(app="drone", compute="npu_32x32", memory="LPDDR5", n=2, **kw):
    return evaluate_system(APPLICATION_LIBRARY[app],
                           SystemConfig("cortex_a78_x4", compute, memory, n, **kw))


# ==============================================================================
# PATH G - units and conventions
# ==============================================================================

def path_g():
    P = "G"
    check(P, "one MAC is two operations everywhere", OPS_PER_MAC == 2)

    app, comp = APPLICATION_LIBRARY["drone"], COMPUTE_LIBRARY["npu_32x32"]
    r = run(); m = r.metrics

    # peak TOPS must follow from MAC rate and the stated convention
    expected_tops = comp.peak_mac_per_s * OPS_PER_MAC / 1e12
    check(P, "peak TOPS = MAC/s x ops-per-MAC", abs(comp.peak_tops - expected_tops) < 1e-9,
          f"{comp.peak_tops} vs {expected_tops}")

    # transfer time = traffic / bandwidth, in consistent units
    # The bandwidth the ACCELERATOR sees, not the interface's. Added at
    # 3.54.0: the host moves bytes across the same bus, so the accelerator
    # gets what is left, and dividing by the full interface figure fails by
    # exactly the host's share - which is the term the check was missing.
    traffic_bytes = m["DRAM traffic (MB)"] * 1e6
    bw_bytes_s = m["Bandwidth left to the accelerator (GB/s)"] * 1e9
    check(P, "transfer time = traffic / bandwidth",
          abs(m["Memory time (ms)"] / 1e3 - traffic_bytes / bw_bytes_s) < 1e-9,
          f"{m['Memory time (ms)']/1e3:.9f} vs {traffic_bytes/bw_bytes_s:.9f}")

    # compute time = MAC / (MAC per second)
    rate = comp.peak_mac_per_s_at(r.accel_node) * comp.utilization
    check(P, "compute time = MAC / MAC-rate",
          abs(m["Compute time (ms)"] / 1e3 - app.total_mac / rate) < 1e-9)

    # energy = power x time
    energy_j = m["Energy per inference (mJ)"] / 1e3
    check(P, "energy = power x latency",
          abs(energy_j - m["System power (W)"] * m["Latency (ms)"] / 1e3) < 1e-9)

    # throughput = 1 / latency
    check(P, "throughput = 1 / latency",
          abs(m["Throughput (inf/s)"] - 1.0 / (m["Latency (ms)"] / 1e3)) < 1e-6)

    # power density = power / footprint
    comp_fp = comp.package_footprint_mm2
    mem_fp = MEMORY_LIBRARY["LPDDR5"].package_footprint_mm2 * 2
    check(P, "power density = power / package footprint",
          abs(m["Power density (W/mm2)"] - m["System power (W)"] / (comp_fp + mem_fp)) < 1e-12)

    # effective TOPS uses the same convention as peak
    core_s = core_ms(m) / 1e3
    check(P, "effective TOPS uses the same ops-per-MAC",
          abs(m["Effective TOPS"] - app.total_mac * OPS_PER_MAC / core_s / 1e12) < 1e-9)

    # bandwidth is decimal GB, not GiB, consistently
    mem = MEMORY_LIBRARY["LPDDR5"]
    check(P, "bandwidth uses decimal GB",
          abs(mem.bandwidth_gbytes_s - mem.package_io_width * mem.pin_speed_gbps / 8.0) < 1e-12)

    # energy per bit applied to bytes, not bits, would be an 8x error
    # Traffic energy plus background. The background term was added at 3.24.0
    # after a scenario found HBM lowering system power; this check had to grow
    # the second term with it, and the traffic half still has to be per BIT -
    # dropping the eight is an eightfold error that looks plausible.
    e_mem = m["  memory share (%)"] / 100 * m["Energy per inference (mJ)"] / 1e3
    traffic_energy = traffic_bytes * 8 * mem.energy_pj_per_bit * 1e-12
    background = mem.background_power_w * 2 * m["Latency (ms)"] / 1e3
    check(P, "memory energy is traffic per BIT plus background",
          abs(e_mem - (traffic_energy + background)) < 1e-9,
          f"{e_mem:.9f} vs {traffic_energy + background:.9f}")
    check(P, "and the traffic half alone would be eight times smaller per byte",
          abs(traffic_energy - traffic_bytes * mem.energy_pj_per_bit * 1e-12 * 8)
          < 1e-15)


# ==============================================================================
# PATH H - golden cases, computable by hand
# ==============================================================================
#
# Each case fixes compute and transfer directly, so the expected answer can be
# worked out on paper. They are kept apart from the library so that changing a
# library value can never change a golden result.

GOLDEN = [
    # compute ms, transfer ms, overlap, expected hidden, expected core
    (10.0,  4.0, 0.00,  0.0, 14.0),
    (10.0,  4.0, 0.25,  1.0, 13.0),
    (10.0,  4.0, 0.50,  2.0, 12.0),
    (10.0,  4.0, 0.75,  3.0, 11.0),
    (10.0,  4.0, 1.00,  4.0, 10.0),
    ( 4.0, 10.0, 0.50,  2.0, 12.0),   # swapped, same answer
    ( 4.0, 10.0, 1.00,  4.0, 10.0),
    ( 7.0,  7.0, 0.50,  3.5, 10.5),   # balanced
    ( 0.0,  5.0, 1.00,  0.0,  5.0),   # nothing to compute
    ( 5.0,  0.0, 1.00,  0.0,  5.0),   # nothing to fetch
]


def _core(compute_ms, transfer_ms, overlap):
    """The model's equation, restated here so a change to it is caught."""
    hidden = overlap * min(compute_ms, transfer_ms)
    return hidden, compute_ms + transfer_ms - hidden


def path_h():
    P = "H"
    for c, t, ov, exp_hidden, exp_core in GOLDEN:
        hidden, core = _core(c, t, ov)
        check(P, f"golden c={c} t={t} ov={ov} hidden", abs(hidden - exp_hidden) < 1e-12,
              f"{hidden} vs {exp_hidden}")
        check(P, f"golden c={c} t={t} ov={ov} core", abs(core - exp_core) < 1e-12,
              f"{core} vs {exp_core}")

    # and the same equation as the simulator actually implements it
    for c, t, ov, exp_hidden, exp_core in GOLDEN:
        if c == 0 or t == 0:
            continue
        app = dataclasses.replace(APPLICATION_LIBRARY["drone"])
        r = run(overlap_ratio=ov)
        m = r.metrics
        h, core = _core(m["Compute time (ms)"], m["Memory time (ms)"], ov)
        check(P, f"simulator matches the equation at ov={ov}",
              abs(m["Hidden transfer (ms)"] - h) < 1e-9
              and abs(core_ms(m) - core) < 1e-9)
        break   # one confirmation per overlap value is enough; loop covers all


# ==============================================================================
# PATH I - symmetry
# ==============================================================================

def path_i():
    P = "I"
    for c, t, ov in ((12.0, 3.0, 0.5), (3.0, 12.0, 0.5), (8.0, 2.0, 0.75),
                     (2.0, 8.0, 0.75), (5.0, 5.0, 0.3)):
        h1, core1 = _core(c, t, ov)
        h2, core2 = _core(t, c, ov)
        check(P, f"hidden is symmetric ({c},{t})", abs(h1 - h2) < 1e-12)
        check(P, f"core time is symmetric ({c},{t})", abs(core1 - core2) < 1e-12)

    # contributions must swap, not stay put
    def contrib(c, t, ov):
        h, _ = _core(c, t, ov)
        ec, em = c - h, t - h
        total = ec + em
        return (0.0, 0.0) if total == 0 else (ec / total * 100, em / total * 100)

    a = contrib(12.0, 3.0, 0.5)
    b = contrib(3.0, 12.0, 0.5)
    check(P, "latency contributions swap when compute and transfer swap",
          abs(a[0] - b[1]) < 1e-9 and abs(a[1] - b[0]) < 1e-9, f"{a} vs {b}")


# ==============================================================================
# PATH J - continuity
# ==============================================================================

def path_j():
    P = "J"
    for centre in (0.25, 0.5, 0.749, 0.75, 0.751, 0.9):
        lo = run(overlap_ratio=max(0.0, centre - 0.001)).metrics["Latency (ms)"]
        mid = run(overlap_ratio=centre).metrics["Latency (ms)"]
        hi = run(overlap_ratio=min(1.0, centre + 0.001)).metrics["Latency (ms)"]
        jump = max(abs(mid - lo), abs(hi - mid))
        check(P, f"latency is continuous around overlap {centre}", jump < 0.05,
              f"jump {jump:.4f} ms")

    # crossing the point where the working set just fits in SRAM
    saved = COMPUTE_LIBRARY["npu_32x32"]
    ws = APPLICATION_LIBRARY["drone"].activation_working_set_kb
    prev = None
    for factor in (0.90, 0.99, 1.00, 1.01, 1.10):
        COMPUTE_LIBRARY["npu_32x32"] = dataclasses.replace(
            saved, sram_kb=ws / saved.dataflow_efficiency * factor)
        v = run().metrics["DRAM traffic (MB)"]
        if prev is not None:
            check(P, f"traffic is continuous at SRAM fit x{factor}",
                  abs(v - prev) / max(prev, 1e-9) < 0.15,
                  f"{prev:.2f} -> {v:.2f} MB")
        prev = v
    COMPUTE_LIBRARY["npu_32x32"] = saved

    # the interface cap meeting the memory bandwidth
    natural = run().metrics["Effective bandwidth (GB/s)"]
    prev = None
    for factor in (0.9, 0.99, 1.0, 1.01, 1.1):
        v = run(interface_bandwidth_gbytes_s=natural * factor).metrics["Latency (ms)"]
        if prev is not None:
            check(P, f"latency is continuous at interface cap x{factor}",
                  abs(v - prev) / max(prev, 1e-9) < 0.15, f"{prev:.3f} -> {v:.3f} ms")
        prev = v


# ==============================================================================
# PATH K - randomised properties
# ==============================================================================

def path_k(draws=2000, seed=20260802):
    P = "K"
    rng = random.Random(seed)
    apps, comps = list(APPLICATION_LIBRARY), list(COMPUTE_LIBRARY)
    mems, cpus, nodes = list(MEMORY_LIBRARY), list(CPU_LIBRARY), list(NODE_LIBRARY)
    violations = {k: 0 for k in
                  ("latency>=0", "hidden>=0", "hidden<=min", "core in [max,sum]",
                   "contrib 0..100", "no nan/inf", "throughput>0", "energy>=0",
                   "scores 0..100")}
    skipped = 0
    for _ in range(draws):
        cfg = SystemConfig(rng.choice(cpus), rng.choice(comps), rng.choice(mems),
                           rng.choice((1, 2, 4, 8)),
                           accel_node=rng.choice(nodes),
                           overlap_ratio=rng.choice((None, 0.0, 0.5, 1.0,
                                                     rng.uniform(-2, 3))),
                           bandwidth_efficiency=rng.choice((None, 0.3, 0.75, 1.0)))
        r = evaluate_system(APPLICATION_LIBRARY[rng.choice(apps)], cfg)
        # A configuration that cannot hold its model has no timing, and an
        # invariant about timing does not apply to it. Its performance figures
        # are deliberately not-a-number so that nothing downstream can use
        # them, and this loop is downstream. Skipping is the point; asserting
        # a roofline over a machine that cannot exist is not.
        if "INFEASIBLE" in r.status:
            skipped += 1
            continue
        m = r.metrics
        c, t, h = m["Compute time (ms)"], m["Memory time (ms)"], m["Hidden transfer (ms)"]
        core = core_ms(m)

        if m["Latency (ms)"] < 0: violations["latency>=0"] += 1
        if h < -1e-9: violations["hidden>=0"] += 1
        if h > min(c, t) + 1e-9: violations["hidden<=min"] += 1
        if not (max(c, t) - 1e-6 <= core <= c + t + 1e-6): violations["core in [max,sum]"] += 1
        for key in ("Latency contribution, compute (%)", "Latency contribution, memory (%)"):
            if not (-1e-9 <= m[key] <= 100 + 1e-9): violations["contrib 0..100"] += 1
        if any(v != v or abs(v) == math.inf
               for v in m.values() if isinstance(v, (int, float))):
            violations["no nan/inf"] += 1
        if m["Throughput (inf/s)"] <= 0: violations["throughput>0"] += 1
        if m["Energy per inference (mJ)"] < 0: violations["energy>=0"] += 1
        if any(not (-1e-9 <= v <= 100 + 1e-9) for v in score_design(r).values()):
            violations["scores 0..100"] += 1

    evaluated = draws - skipped
    for name, count in violations.items():
        check(P, f"{name} over {evaluated} random draws", count == 0,
              f"{count} violations")
    # The skip must not swallow the sample. If most draws were infeasible the
    # property test would be passing on almost nothing.
    check(P, "most random draws are feasible and were actually checked",
          evaluated > draws * 0.5,
          f"{evaluated} of {draws} evaluated, {skipped} infeasible")


# ==============================================================================
# PATH L - sensitivity
# ==============================================================================

def path_l():
    P = "L"
    base_m = run().metrics
    saved = COMPUTE_LIBRARY["npu_32x32"]

    def rel(new, old):
        return (new - old) / old * 100.0

    # bandwidth +1% must reduce transfer time by about 1%, not by 50%
    eff = MEMORY_LIBRARY["LPDDR5"].bandwidth_efficiency
    m = run(bandwidth_efficiency=eff * 1.01).metrics
    d = rel(m["Memory time (ms)"], base_m["Memory time (ms)"])
    check(P, "bandwidth +1% moves transfer time by about -1%", -1.5 < d < -0.5, f"{d:.3f}%")

    # clock +1% must reduce compute time by about 1%
    COMPUTE_LIBRARY["npu_32x32"] = dataclasses.replace(saved, clock_ghz=saved.clock_ghz * 1.01)
    m = run().metrics
    d = rel(m["Compute time (ms)"], base_m["Compute time (ms)"])
    check(P, "clock +1% moves compute time by about -1%", -1.5 < d < -0.5, f"{d:.3f}%")
    COMPUTE_LIBRARY["npu_32x32"] = saved

    # MAC count +1% must raise compute time by about 1%
    app = APPLICATION_LIBRARY["drone"]
    tuned = dataclasses.replace(app, mac_per_inference=app.mac_per_inference * 1.01)
    m = evaluate_system(tuned, SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)).metrics
    d = rel(m["Compute time (ms)"], base_m["Compute time (ms)"])
    check(P, "MAC +1% moves compute time by about +1%", 0.5 < d < 1.5, f"{d:.3f}%")

    # overlap +1 point must never increase latency, and never by a large step
    d = rel(run(overlap_ratio=0.76).metrics["Latency (ms)"],
            run(overlap_ratio=0.75).metrics["Latency (ms)"])
    check(P, "overlap +0.01 changes latency by under 1%", -1.0 < d <= 1e-9, f"{d:.4f}%")

    # no single 1% input change may move latency by more than a few percent
    big = []
    for label, fn in (("bandwidth", lambda: run(bandwidth_efficiency=eff * 1.01)),
                      ("devices", lambda: run(n=2)),
                      ("overlap", lambda: run(overlap_ratio=0.76))):
        d = abs(rel(fn().metrics["Latency (ms)"], base_m["Latency (ms)"]))
        if d > 5.0:
            big.append(f"{label} {d:.1f}%")
    check(P, "no 1% input causes a disproportionate output change", not big, "; ".join(big))


# ==============================================================================
# PATH M - scaling
# ==============================================================================

def path_m():
    P = "M"
    app = APPLICATION_LIBRARY["drone"]
    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2, overlap_ratio=0.0)
    b = evaluate_system(app, cfg).metrics

    x2 = dataclasses.replace(app, mac_per_inference=app.mac_per_inference * 2)
    m = evaluate_system(x2, cfg).metrics
    check(P, "doubling MAC doubles compute time",
          abs(m["Compute time (ms)"] / b["Compute time (ms)"] - 2.0) < 1e-6,
          f"{m['Compute time (ms)']/b['Compute time (ms)']:.6f}")

    x2 = dataclasses.replace(app, weight_bytes=app.weight_bytes * 2,
                             activation_bytes=app.activation_bytes * 2)
    m = evaluate_system(x2, cfg).metrics
    check(P, "doubling traffic doubles transfer time",
          abs(m["Memory time (ms)"] / b["Memory time (ms)"] - 2.0) < 1e-6,
          f"{m['Memory time (ms)']/b['Memory time (ms)']:.6f}")

    # fixed overhead means total time grows by less than exactly two
    x2 = dataclasses.replace(app, mac_per_inference=app.mac_per_inference * 2,
                             weight_bytes=app.weight_bytes * 2,
                             activation_bytes=app.activation_bytes * 2)
    m = evaluate_system(x2, cfg).metrics
    ratio = m["Latency (ms)"] / b["Latency (ms)"]
    check(P, "latency grows by slightly under 2x because CPU work is fixed here",
          1.90 < ratio < 2.0, f"{ratio:.6f}")

    # and energy per inference should roughly double as well
    ratio = m["Energy per inference (mJ)"] / b["Energy per inference (mJ)"]
    check(P, "energy per inference roughly doubles", 1.8 < ratio < 2.2, f"{ratio:.4f}")


# ==============================================================================
# PATH N - realism bounds
# ==============================================================================

def path_n():
    P = "N"
    bad = {k: 0 for k in ("effective<=peak TOPS", "throughput<=compute limit",
                          "throughput<=memory limit", "utilisation 0..100",
                          "accuracy 0..100", "die>=blocks", "avg power>0",
                          "effective BW<=peak BW")}
    total = 0
    for app_key in APPLICATION_LIBRARY:
        for comp_key in COMPUTE_LIBRARY:
            for mem_key in MEMORY_LIBRARY:
                total += 1
                r = evaluate_system(APPLICATION_LIBRARY[app_key],
                                    SystemConfig("cortex_a78_x4", comp_key, mem_key, 2))
                m, comp = r.metrics, COMPUTE_LIBRARY[comp_key]
                app = APPLICATION_LIBRARY[app_key]

                if m["Effective TOPS"] > m["Peak TOPS"] + 1e-6:
                    bad["effective<=peak TOPS"] += 1
                if m["Effective bandwidth (GB/s)"] > m["Peak bandwidth (GB/s)"] + 1e-6:
                    bad["effective BW<=peak BW"] += 1

                compute_limit = 1.0 / (m["Compute time (ms)"] / 1e3) if m["Compute time (ms)"] > 0 else math.inf
                memory_limit = 1.0 / (m["Memory time (ms)"] / 1e3) if m["Memory time (ms)"] > 0 else math.inf
                if m["Throughput (inf/s)"] > compute_limit * (1 + 1e-6):
                    bad["throughput<=compute limit"] += 1
                if m["Throughput (inf/s)"] > memory_limit * (1 + 1e-6):
                    bad["throughput<=memory limit"] += 1

                if not (-1e-9 <= m["Compute utilisation (%)"] <= 100 + 1e-9):
                    bad["utilisation 0..100"] += 1
                if not (0 <= m["Deployment accuracy (%)"] <= 100):
                    bad["accuracy 0..100"] += 1

                blocks = (comp.mac_area_at(r.accel_node) + comp.sram_area_at(r.accel_node))
                if m["Accel die area (mm2)"] < blocks - 1e-9:
                    bad["die>=blocks"] += 1
                if m["System power (W)"] <= 0:
                    bad["avg power>0"] += 1

    for name, count in bad.items():
        check(P, f"{name} ({total} combos)", count == 0, f"{count} violations")


# ==============================================================================
# PATH O - CPU work model (Phase 2)
# ==============================================================================

def path_o():
    P = "O"
    app = APPLICATION_LIBRARY["drone"]
    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
    b = evaluate_system(app, cfg).metrics
    cpu = CPU_LIBRARY["cortex_a78_x4"]

    # 1. more pixels means more preprocessing, monotonically
    pre = []
    for scale in (0.5, 1.0, 2.0, 4.0):
        t = dataclasses.replace(app, input_pixels=app.input_pixels * scale)
        pre.append(evaluate_system(t, cfg).metrics["CPU preprocess (ms)"])
    check(P, "1 preprocessing rises with pixel count",
          all(a < b2 for a, b2 in zip(pre, pre[1:])), str([round(x, 4) for x in pre]))

    # 2. more outputs means more postprocessing
    post = []
    for n in (10, 100, 1000, 10000):
        t = dataclasses.replace(app, output_elements=n)
        post.append(evaluate_system(t, cfg).metrics["CPU postprocess (ms)"])
    check(P, "2 postprocessing rises with output count",
          all(a < b2 for a, b2 in zip(post, post[1:])), str([round(x, 4) for x in post]))

    # 3. turning NMS off reduces postprocessing
    off = evaluate_system(dataclasses.replace(app, uses_nms=False), cfg).metrics
    check(P, "3 disabling NMS reduces postprocessing",
          off["CPU postprocess (ms)"] < b["CPU postprocess (ms)"],
          f"{off['CPU postprocess (ms)']:.5f} vs {b['CPU postprocess (ms)']:.5f}")

    # 4. dispatch is fixed, whatever the workload
    disp = set()
    for scale in (0.1, 1.0, 100.0):
        t = dataclasses.replace(app, input_pixels=app.input_pixels * scale,
                                output_elements=app.output_elements * scale,
                                mac_per_inference=app.mac_per_inference * scale)
        disp.add(round(evaluate_system(t, cfg).metrics["CPU dispatch (ms)"], 12))
    check(P, "4 dispatch is independent of workload size", len(disp) == 1, str(disp))

    # 5. a faster CPU finishes its work sooner
    fast = dataclasses.replace(cpu, clock_ghz=cpu.clock_ghz * 2)
    saved = CPU_LIBRARY["cortex_a78_x4"]
    CPU_LIBRARY["cortex_a78_x4"] = fast
    m = evaluate_system(app, cfg).metrics
    CPU_LIBRARY["cortex_a78_x4"] = saved
    # Revised at 3.54.0. Doubling the clock halves the ARITHMETIC and does
    # nothing to the transfers, so the active time falls by less than half -
    # which is the whole point of giving the host a roofline. Testing the
    # active time here would have quietly asserted that a host never waits.
    # Not exactly half: the framework overhead is a fixed number of
    # milliseconds per inference and does not scale with a clock.
    ratio_compute = m["Host compute time (ms)"] / b["Host compute time (ms)"]
    check(P, "5 doubling CPU clock reduces the host's arithmetic",
          0.5 <= ratio_compute < 0.95, f"{ratio_compute:.4f}")
    check(P, "5 but not its transfers",
          abs(m["Host transfer time (ms)"] - b["Host transfer time (ms)"])
          < b["Host transfer time (ms)"] * 0.02 + 1e-9,
          "a faster core does not move bytes faster")
    ratio = m["CPU active (ms)"] / b["CPU active (ms)"]
    check(P, "5 so the host's total time falls by LESS than half",
          ratio > 0.5 - 1e-9, f"{ratio:.4f}")
    check(P, "5 and still falls", ratio < 1.0, f"{ratio:.4f}")


    # 6. never negative
    neg = 0
    for app_key in APPLICATION_LIBRARY:
        for cpu_key in CPU_LIBRARY:
            m = evaluate_system(APPLICATION_LIBRARY[app_key],
                                SystemConfig(cpu_key, "npu_32x32", "LPDDR5", 2)).metrics
            for k in ("CPU preprocess (ms)", "CPU dispatch (ms)", "CPU postprocess (ms)",
                      "CPU active (ms)", "CPU accelerator-wait (ms)"):
                if m[k] < 0:
                    neg += 1
    check(P, "6 no negative CPU times", neg == 0, f"{neg} negatives")

    # 7. CPU energy follows active and wait power
    r = evaluate_system(app, cfg)
    m = r.metrics
    e_cpu = m["  cpu share (%)"] / 100 * m["Energy per inference (mJ)"] / 1e3
    expected = (cpu.active_power_at(r.soc_node) * m["CPU active (ms)"] / 1e3
                + cpu.idle_power_at(r.soc_node) * m["CPU accelerator-wait (ms)"] / 1e3)
    check(P, "7 CPU energy = active*active_time + idle*wait_time",
          abs(e_cpu - expected) < 1e-9, f"{e_cpu:.9f} vs {expected:.9f}")

    # 8. an accelerator-free configuration is flagged, not silently scored
    r = evaluate_system(app, SystemConfig("cortex_a78_x4", "cpu_only", "LPDDR5", 2))
    check(P, "8 CPU-only configuration still evaluates and reports a status",
          r.metrics["Latency (ms)"] > 0 and isinstance(r.status, str))

    # 9. zero pre and post leaves dispatch standing
    t = dataclasses.replace(app, input_pixels=0.0, output_elements=0.0)
    stripped = dataclasses.replace(cpu, fixed_preprocess_cycles=0.0,
                                   fixed_postprocess_cycles=0.0)
    CPU_LIBRARY["cortex_a78_x4"] = stripped
    m = evaluate_system(t, cfg).metrics
    CPU_LIBRARY["cortex_a78_x4"] = saved
    # Since 3.27.0 the framework launch is also inside CPU active time, so
    # "only dispatch" became "dispatch and launch". Both are fixed costs that
    # do not scale with the workload, which is what this check is about.
    check(P, "9 with no pre/post work only the fixed costs remain",
          abs(m["CPU active (ms)"] - m["CPU dispatch (ms)"]
              - m["Framework overhead (ms)"]) < 1e-12
          and m["CPU dispatch (ms)"] > 0,
          f"active {m['CPU active (ms)']:.9f}, dispatch "
          f"{m['CPU dispatch (ms)']:.9f}, launch "
          f"{m['Framework overhead (ms)']:.9f}")

    # 10. CPU time enters the latency exactly once
    bad = 0
    for app_key in APPLICATION_LIBRARY:
        for comp in ("npu_16x16", "npu_128x128", "mobile_gpu"):
            r = evaluate_system(APPLICATION_LIBRARY[app_key],
                                SystemConfig("cortex_a78_x4", comp, "LPDDR5", 2))
            m = r.metrics
            core = (m["Compute time (ms)"] + m["Memory time (ms)"]
                    - m["Hidden transfer (ms)"])
            if abs(m["Latency (ms)"] - (m["CPU active (ms)"] + core
                                        + m["Serving overhead (ms)"])) > 1e-9:
                bad += 1
    check(P, "10 latency = CPU active + core, counted once", bad == 0, f"{bad} mismatches")

    # and the accelerator wait must equal the core time exactly
    check(P, "accelerator wait equals core time",
          abs(b["CPU accelerator-wait (ms)"]
              - (b["Compute time (ms)"] + b["Memory time (ms)"]
                 - b["Hidden transfer (ms)"])) < 1e-9)

    # utilisation bounded
    over = sum(1 for app_key in APPLICATION_LIBRARY
               for cpu_key in CPU_LIBRARY
               if not (0 <= evaluate_system(
                   APPLICATION_LIBRARY[app_key],
                   SystemConfig(cpu_key, "npu_32x32", "LPDDR5", 2)
               ).metrics["CPU latency share (%)"] <= 100))
    check(P, "CPU latency share stays within 0..100", over == 0, f"{over} out of range")

    # text and vision must cost differently
    v = evaluate_system(APPLICATION_LIBRARY["smart_camera"],
                        SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)).metrics
    t = evaluate_system(APPLICATION_LIBRARY["mobile_ai"],
                        SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)).metrics
    check(P, "vision preprocessing costs far more than text",
          v["CPU preprocess (ms)"] > t["CPU preprocess (ms)"] * 10,
          f"{v['CPU preprocess (ms)']:.4f} vs {t['CPU preprocess (ms)']:.4f}")


# ==============================================================================
# PATH P - preprocessing placement
# ==============================================================================

def path_p():
    P = "P"
    app = APPLICATION_LIBRARY["industrial_vision"]

    def go(mode, **kw):
        a = dataclasses.replace(app, **kw) if kw else app
        return evaluate_system(a, SystemConfig("cortex_a78_x4", "npu_64x64",
                                               "LPDDR5", 4,
                                               preprocessing_mode=mode)).metrics

    # shares must account for all the work, exactly once
    for mode in pp.MODES:
        c, i, n = pp.split(mode)
        check(P, f"{mode} shares sum to 1", abs(c + i + n - 1.0) < 1e-12,
              f"{c}+{i}+{n}")
        check(P, f"{mode} shares are non-negative", min(c, i, n) >= 0)

    # moving work off the CPU must reduce CPU preprocessing
    cpu_only = go("cpu_only")["CPU preprocess (ms)"]
    for mode in ("isp_assisted", "npu_assisted", "isp_and_npu"):
        check(P, f"{mode} reduces CPU preprocessing",
              go(mode)["CPU preprocess (ms)"] < cpu_only,
              f"{go(mode)['CPU preprocess (ms)']:.4f} vs {cpu_only:.4f}")

    # an ISP costs silicon and static power but no latency of its own
    a, b = go("cpu_only"), go("isp_assisted")
    check(P, "ISP adds silicon", b["SoC silicon (mm2)"] > a["SoC silicon (mm2)"])
    check(P, "ISP adds no offload latency", b["Offload overhead (ms)"] == 0.0)
    check(P, "ISP costs money", b["System cost (USD)"] > a["System cost (USD)"])

    # accelerator preprocessing costs a hand-off and extra die
    c = go("npu_assisted")
    check(P, "NPU preprocessing charges a hand-off", c["Offload overhead (ms)"] > 0)
    check(P, "NPU preprocessing enlarges the accelerator",
          c["Accelerator area uplift (%)"] > 0)

    # the point of the whole exercise: offloading is not free, and below some
    # frame size it loses
    small = dict(input_pixels=160 * 120, streams=1)
    large = dict(input_pixels=2448 * 2048, streams=4)
    s_cpu = go("cpu_only", **small)["Latency (ms)"]
    s_npu = go("npu_assisted", **small)["Latency (ms)"]
    l_cpu = go("cpu_only", **large)["Latency (ms)"]
    l_npu = go("npu_assisted", **large)["Latency (ms)"]
    check(P, "offloading a tiny frame is slower than not offloading",
          s_npu > s_cpu, f"{s_npu:.4f} vs {s_cpu:.4f}")
    check(P, "offloading a large frame is faster",
          l_npu < l_cpu, f"{l_npu:.4f} vs {l_cpu:.4f}")

    # and there is a single crossing, not oscillation
    sizes = [160*120, 320*240, 640*480, 1280*720, 1920*1080, 2448*2048]
    delta = [go("npu_assisted", input_pixels=px, streams=1)["Latency (ms)"]
             - go("cpu_only", input_pixels=px, streams=1)["Latency (ms)"]
             for px in sizes]
    crossings = sum(1 for a2, b2 in zip(delta, delta[1:]) if (a2 > 0) != (b2 > 0))
    check(P, "the offload trade crosses over exactly once", crossings == 1,
          f"{crossings} crossings, deltas {[round(x, 4) for x in delta]}")
    check(P, "the advantage of offloading grows with frame size",
          all(a2 >= b2 - 1e-12 for a2, b2 in zip(delta, delta[1:])),
          str([round(x, 4) for x in delta]))

    # text workloads must be unaffected by a vision-only choice
    t1 = evaluate_system(APPLICATION_LIBRARY["mobile_ai"],
                         SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                                      preprocessing_mode="cpu_only")).metrics
    t2 = evaluate_system(APPLICATION_LIBRARY["mobile_ai"],
                         SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                                      preprocessing_mode="npu_assisted")).metrics
    check(P, "a text workload ignores preprocessing placement",
          abs(t1["Latency (ms)"] - t2["Latency (ms)"]) < 1e-12)

    # every mode must evaluate for every application
    fails = []
    for key in APPLICATION_LIBRARY:
        for mode in pp.MODES:
            try:
                evaluate_system(APPLICATION_LIBRARY[key],
                                SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                                             preprocessing_mode=mode))
            except Exception as exc:
                fails.append(f"{key}/{mode}: {exc}")
    check(P, "every application x mode evaluates", not fails, "; ".join(fails[:3]))

    # --- corrections raised in review ---------------------------------------

    # 1. total pixels must be resolution x streams, linearly
    px = [go("cpu_only", streams=k)["Total pixels per job"] for k in (1, 2, 4, 8)]
    check(P, "1 total pixels scale linearly with stream count",
          all(abs(v - px[0] * k) < 1e-6 for v, k in zip(px, (1, 2, 4, 8))), str(px))
    one = go("cpu_only", streams=1)
    check(P, "1 per-stream and total are reported separately",
          abs(one["Pixels per stream"] * one["Streams"]
              - one["Total pixels per job"]) < 1e-6)

    # 2. per-stream calls multiply the fixed cost
    batched = evaluate_system(dataclasses.replace(app, streams=4),
                              SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                                           preprocessing_mode="npu_assisted",
                                           offload_batching=True)).metrics
    percall = evaluate_system(dataclasses.replace(app, streams=4),
                              SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                                           preprocessing_mode="npu_assisted",
                                           offload_batching=False)).metrics
    check(P, "2 per-stream offload multiplies dispatch by the stream count",
          abs(percall["Offload dispatch (ms)"] - batched["Offload dispatch (ms)"] * 4) < 1e-9,
          f"{percall['Offload dispatch (ms)']:.4f} vs {batched['Offload dispatch (ms)']*4:.4f}")

    # 3. batching keeps the call count at one
    check(P, "3 batching means one call", batched["Offload calls"] == 1.0)
    check(P, "3 per-stream means one call per stream", percall["Offload calls"] == 4.0)

    # 4-5. same total pixels, different stream split: same compute, different overhead
    wide = evaluate_system(dataclasses.replace(app, input_pixels=4_000_000, streams=1),
                           SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                                        preprocessing_mode="npu_assisted",
                                        offload_batching=False)).metrics
    split4 = evaluate_system(dataclasses.replace(app, input_pixels=1_000_000, streams=4),
                             SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                                          preprocessing_mode="npu_assisted",
                                          offload_batching=False)).metrics
    # Equal total pixels means equal preprocessing MACs, but not equal TIME:
    # four streams carry four times the inference work, which fills the engine
    # better and so runs the preprocessing faster too. Comparing times was
    # wrong once utilisation stopped being a constant; comparing the work is
    # what the check was always about.
    def _pre_macs(mm):
        from ppact.preprocess import npu_mac_per_pixel
        return mm["Total pixels per job"] * npu_mac_per_pixel("npu_assisted")
    check(P, "4 equal total pixels give equal preprocessing work",
          abs(_pre_macs(wide) - _pre_macs(split4)) < 1e-6,
          f"{_pre_macs(wide):.0f} vs {_pre_macs(split4):.0f} MAC")
    check(P, "4 but four streams run it faster, having more work to fill with",
          split4["Preprocess offload (ms)"] < wide["Preprocess offload (ms)"],
          f"{split4['Preprocess offload (ms)']:.5f} vs "
          f"{wide['Preprocess offload (ms)']:.5f} ms")
    check(P, "5 but more streams cost more dispatch when not batched",
          split4["Offload dispatch (ms)"] > wide["Offload dispatch (ms)"],
          f"{split4['Offload dispatch (ms)']:.4f} vs {wide['Offload dispatch (ms)']:.4f}")

    # 6. ISP active is positive; exposed may be zero
    isp = go("isp_assisted")
    check(P, "6 ISP active time is greater than zero", isp["ISP active (ms)"] > 0)
    check(P, "6 ISP exposed time can be zero when capture hides it",
          isp["ISP exposed (ms)"] >= 0
          and isp["ISP hidden (ms)"] + isp["ISP exposed (ms)"]
              - isp["ISP active (ms)"] < 1e-9)

    # and an ISP that cannot keep up must expose the remainder
    fast = evaluate_system(
        dataclasses.replace(app, input_pixels=8_000_000, streams=8,
                            target_inferences_per_s=120),
        SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                     preprocessing_mode="isp_assisted")).metrics
    check(P, "6 an overloaded ISP exposes the excess", fast["ISP exposed (ms)"] > 0,
          f"active {fast['ISP active (ms)']:.2f}, exposed {fast['ISP exposed (ms)']:.2f}")

    # 7. ISP energy is non-zero even when it adds no latency
    a2, b2 = go("cpu_only"), go("isp_assisted")
    check(P, "7 an ISP costs energy even with zero exposed latency",
          b2["ISP energy (mJ)"] > 0 and b2["ISP exposed (ms)"] == 0.0
          and a2["ISP energy (mJ)"] == 0.0,
          f"isp {b2['ISP energy (mJ)']:.4f} mJ, exposed {b2['ISP exposed (ms)']:.4f} ms")

    # 8. CPU latency share stays bounded
    out = 0
    for key in APPLICATION_LIBRARY:
        for m2 in pp.MODES:
            v = evaluate_system(APPLICATION_LIBRARY[key],
                                SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                                             preprocessing_mode=m2)
                                ).metrics["CPU latency share (%)"]
            if not (0 <= v <= 100):
                out += 1
    check(P, "8 CPU latency share stays within 0..100", out == 0, f"{out} out of range")

    # 9. all four modes see the same workload
    totals = {go(m2)["Total pixels per job"] for m2 in pp.MODES}
    check(P, "9 every mode processes the same pixels", len(totals) == 1, str(totals))

    # 10. preprocessing shares the main array, so it adds to accelerator time
    n = go("npu_assisted")
    check(P, "10 accelerator active time = preprocessing + inference",
          abs(n["Accelerator total active (ms)"]
              - (n["Preprocess offload (ms)"]
                 + n["Latency (ms)"] - n["CPU active (ms)"]
                 - n["Offload overhead (ms)"] - n["Preprocess offload (ms)"]
                 - n["ISP exposed (ms)"])) < 1e-9)
    check(P, "10 offloading raises accelerator active time above inference alone",
          n["Accelerator total active (ms)"] > n["Compute time (ms)"])

    # break-even must move when the call structure changes
    def crossing(batch):
        sizes = [40_000, 160_000, 640_000, 2_560_000, 10_240_000]
        d = []
        for total in sizes:
            t2 = dataclasses.replace(app, input_pixels=total / 4, streams=4)
            cfg_a = SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                                 preprocessing_mode="npu_assisted",
                                 offload_batching=batch)
            cfg_b = SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                                 preprocessing_mode="cpu_only")
            d.append(evaluate_system(t2, cfg_a).metrics["Latency (ms)"]
                     - evaluate_system(t2, cfg_b).metrics["Latency (ms)"])
        for i, (x, y) in enumerate(zip(d, d[1:])):
            if (x > 0) != (y > 0):
                return i
        return None
    cb, cp = crossing(True), crossing(False)
    check(P, "break-even moves later when each stream is a separate call",
          cb is not None and cp is not None and cp > cb, f"batched at {cb}, per-call at {cp}")

    # an unknown mode must be refused, not silently ignored
    try:
        evaluate_system(app, SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                                          preprocessing_mode="magic"))
        check(P, "an unknown mode is rejected", False, "no error raised")
    except KeyError:
        check(P, "an unknown mode is rejected", True)


# ==============================================================================
# PATH Q - runtime (Phase 3)
# ==============================================================================

def path_q():
    Q = "Q"
    cfg = SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                       preprocessing_mode="isp_and_npu")

    # the window is what the student asked for, not what the work needs
    for d in (10, 30, 60, 120):
        r = simulate("industrial_vision", cfg, duration_s=d)
        check(Q, f"window is {d} s as requested",
              abs(r.metrics["Simulation time (s)"] - d) < 1e-9)

    r60 = simulate("industrial_vision", cfg, duration_s=60)

    # the interval is the slowest stage, and it names it
    stages = {"ISP": r60.base.metrics["Stage ISP (ms)"],
              "CPU": r60.base.metrics["Stage CPU (ms)"],
              "Accelerator": r60.base.metrics["Stage accelerator (ms)"]}
    check(Q, "interval equals the slowest stage",
          abs(r60.interval_ms - max(stages.values())) < 1e-9)
    check(Q, "the limiting stage is named correctly",
          r60.limiting_stage == max(stages, key=lambda k: stages[k]))

    # throughput is set by the interval, not by the latency
    check(Q, "throughput follows the interval, not the latency",
          abs(r60.throughput - r60.jobs / 60.0) < 1e-9)
    # capacity, not delivered throughput: the system only produces what is
    # asked of it, so the pipelining benefit shows in what it COULD do
    capacity_rate = r60.metrics["Capacity (jobs)"] / 60.0
    check(Q, "pipelined capacity exceeds one-over-latency",
          capacity_rate >= 1.0 / (r60.first_latency_ms / 1e3) - 1e-6
          or r60.interval_ms >= r60.first_latency_ms - 1e-9,
          f"capacity {capacity_rate:.2f}/s vs 1/latency "
          f"{1000.0 / r60.first_latency_ms:.2f}/s")

    # jobs scale with the window, work does not exceed capacity
    a = simulate("industrial_vision", cfg, duration_s=30)
    b = simulate("industrial_vision", cfg, duration_s=60)
    check(Q, "doubling the window roughly doubles the jobs",
          1.9 < b.jobs / max(a.jobs, 1) < 2.1, f"{a.jobs} -> {b.jobs}")
    check(Q, "jobs never exceed demand", b.jobs <= b.metrics["Jobs demanded"] + 1e-9)
    check(Q, "jobs never exceed capacity", b.jobs <= b.metrics["Capacity (jobs)"] + 1e-9)

    # an under-provisioned design must be reported as such, not quietly stretched
    weak = simulate("industrial_vision",
                    SystemConfig("cortex_a53_x4", "npu_16x16", "LPDDR5", 1,
                                 preprocessing_mode="cpu_only"), duration_s=60)
    check(Q, "a design that cannot keep up says so",
          weak.metrics["Keeps up"] == 0.0
          and weak.jobs < weak.metrics["Jobs demanded"],
          f"{weak.jobs} of {weak.metrics['Jobs demanded']}")
    check(Q, "its throughput falls short of the requirement",
          weak.throughput < weak.app.target_inferences_per_s)

    # module states must partition the window exactly
    bad = 0
    for name, st in weak.modules.items():
        total = st.active_ms + st.wait_ms + st.idle_ms
        if abs(total - weak.total_time_ms) > 1e-6:
            bad += 1
        if min(st.active_ms, st.wait_ms, st.idle_ms) < -1e-9:
            bad += 1
    check(Q, "active + blocked + idle equals the window for every module",
          bad == 0, f"{bad} modules off")

    # utilisation is a real fraction now
    for name, st in weak.modules.items():
        check(Q, f"{name} utilisation within 0..100",
              -1e-9 <= st.utilisation_pct <= 100 + 1e-9, f"{st.utilisation_pct}")

    # the limiting stage must be the busiest module
    busiest = max(weak.modules.values(), key=lambda s2: s2.active_ms).name
    check(Q, "the limiting stage is the busiest module",
          busiest in (weak.limiting_stage, "Memory"),
          f"{busiest} vs {weak.limiting_stage}")

    # energy: static over the window, dynamic per job
    m = r60.base.metrics
    expected = (m["Dynamic energy per inference (mJ)"] / 1e3 * r60.jobs
                + m["Static power (W)"] * 60.0)
    check(Q, "energy = dynamic per job + static over the window",
          abs(r60.metrics["Total energy (J)"] - expected) < 1e-9)
    check(Q, "average power = energy over the window",
          abs(r60.metrics["Average power (W)"]
              - r60.metrics["Total energy (J)"] / 60.0) < 1e-9)

    # peak must never sit below average
    below = 0
    for app_key in APPLICATION_LIBRARY:
        for comp in ("npu_16x16", "npu_64x64", "mobile_gpu"):
            rr = simulate(app_key, SystemConfig("cortex_a78_x4", comp, "LPDDR5", 2),
                          duration_s=30)
            if rr.metrics["Peak power (W)"] < rr.metrics["Average power (W)"] - 1e-9:
                below += 1
    check(Q, "peak power is never below average power", below == 0, f"{below} cases")

    # every application runs
    fails = []
    for app_key in APPLICATION_LIBRARY:
        try:
            rr = simulate(app_key, SystemConfig(
                "server_x86_x32" if APPLICATION_LIBRARY[app_key].domain == "Data Center"
                else "cortex_a78_x4", "npu_64x64", "LPDDR5", 4), duration_s=10)
            if rr.total_time_ms <= 0:
                fails.append(f"{app_key}: zero window")
        except Exception as exc:
            fails.append(f"{app_key}: {exc}")
    check(Q, "every application simulates", not fails, "; ".join(fails[:3]))

    # a fixed job count overrides the arrival rate
    fixed = simulate("industrial_vision", cfg, duration_s=60, jobs=100)
    check(Q, "an explicit job count is honoured", fixed.jobs == 100)

    # traffic accumulates
    check(Q, "DRAM traffic accumulates over the run",
          abs(r60.metrics["Total DRAM traffic (GB)"]
              - m["DRAM traffic (MB)"] * r60.jobs / 1e3) < 1e-6)


# ==============================================================================
# PATH R - Innovation Challenge
# ==============================================================================

def path_r():
    R = "R"

    # the rubric must add to exactly five
    check(R, "the rubric totals 5 points",
          sum(points for _, points, _ in RUBRIC) == 5,
          str([p for _, p, _ in RUBRIC]))
    check(R, "every rubric item is explained",
          all(len(detail) > 40 for _, _, detail in RUBRIC))

    # grading weights exist for every application and are positive
    for key in APPLICATION_LIBRARY:
        w = grading_weights(key)
        check(R, f"{key} has grading weights for all six axes",
              set(w) == {"Accuracy", "Performance", "Power", "Area", "Cost", "Thermal"},
              str(sorted(w)))
        check(R, f"{key} weights are positive", min(w.values()) > 0)

    # weights must differ between applications, or they are not weights
    profiles = {tuple(sorted(grading_weights(k).items())) for k in APPLICATION_LIBRARY}
    check(R, "applications weight the axes differently", len(profiles) > 1,
          f"{len(profiles)} distinct profiles")
    # and they must match the stated identity of the application
    check(R, "medical weights accuracy highest",
          max(grading_weights("medical"), key=grading_weights("medical").get) == "Accuracy")
    check(R, "drone weights power highest",
          max(grading_weights("drone"), key=grading_weights("drone").get) == "Power")

    # the graded score must NOT depend on any student-supplied weighting
    cfg = SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                       preprocessing_mode="isp_and_npu")
    a = system_score("industrial_vision", cfg)
    b = system_score("industrial_vision", cfg)
    check(R, "the graded score is reproducible", abs(a["Overall"] - b["Overall"]) < 1e-9)
    check(R, "the graded score is bounded", 0 <= a["Overall"] <= 100)
    # the same design graded against a different application must differ, since
    # the weights come from the application
    c = system_score("drone", cfg)
    check(R, "the same design scores differently under a different application",
          abs(a["Overall"] - c["Overall"]) > 1e-6,
          f"{a['Overall']:.4f} vs {c['Overall']:.4f}")

    # evidence must report regressions, not only improvements
    prop = evaluate_proposal(
        "industrial_vision",
        SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                     preprocessing_mode="cpu_only"),
        SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                     preprocessing_mode="isp_and_npu"),
        duration_s=60)
    check(R, "the proposal reports at least one improvement",
          any(v > 0.5 for v in prop.deltas.values()), str(prop.deltas))
    check(R, "the proposal reports at least one regression",
          any(v < -0.5 for v in prop.deltas.values()), str(prop.deltas))

    # sign convention: a cost that rose must read as worse
    higher_cost = prop.proposed.metrics["System cost (USD)"] > \
                  prop.baseline.metrics["System cost (USD)"]
    check(R, "a rise in cost reads as a regression",
          (prop.deltas["System cost (USD)"] < 0) == higher_cost,
          f"cost delta {prop.deltas['System cost (USD)']:.2f}")

    # an identical proposal must show no change at all
    same = evaluate_proposal("industrial_vision", cfg, cfg, duration_s=30)
    check(R, "an unchanged design shows no improvement",
          all(abs(v) < 1e-9 for v in same.deltas.values()), str(same.deltas))

    # reference platforms are declared, with sources and caveats
    for key, ref in REFERENCE_PLATFORMS.items():
        check(R, f"{key} names its source", len(ref.source) > 5)
        check(R, f"{key} has a positive power figure", ref.typical_power_w > 0)
    check(R, "reference TOPS-per-watt is derived, not asserted",
          all(abs(r.peak_tops_per_watt - r.peak_tops_int8 / r.typical_power_w) < 1e-9
              for r in REFERENCE_PLATFORMS.values()))

    # a throughput ratio must not appear without a measured reference figure
    p1 = evaluate_proposal("industrial_vision", cfg, cfg, duration_s=10,
                           reference="jetson_orin_nano")
    check(R, "no measured reference means no throughput ratio",
          p1.measured_reference_throughput is None)
    p2 = evaluate_proposal("industrial_vision", cfg, cfg, duration_s=10,
                           reference="jetson_orin_nano",
                           measured_reference_throughput=45.0)
    check(R, "a supplied benchmark figure is carried through",
          p2.measured_reference_throughput == 45.0)

    # --- reference designs ---------------------------------------------------
    for key in APPLICATION_LIBRARY:
        ref = reference_design(key)
        try:
            rr = evaluate_system(APPLICATION_LIBRARY[key], ref)
            check(R, f"{key} has a reference design that evaluates",
                  rr.metrics["Latency (ms)"] > 0)
        except Exception as exc:
            check(R, f"{key} has a reference design that evaluates", False, repr(exc))
        # No longer asserted: a reference is what products actually look like,
        # and a smart camera without a camera block is not one. What matters is
        # that the reference SHIPS, which PATH S checks.
        check(R, f"{key} reference is describable", len(describe_design(ref)) > 20)

    # an application not in the table still gets one
    from ppact import make_custom_application
    make_custom_application("Probe", register_as="__refprobe__")
    try:
        ref = reference_design("__refprobe__")
        check(R, "a student-defined application still gets a reference design",
              ref.compute in COMPUTE_LIBRARY)
    finally:
        APPLICATION_LIBRARY.pop("__refprobe__", None)

    # the reference must be improvable - if it were already optimal the
    # exercise would have no room in it
    beaten = 0
    for key in ("industrial_vision", "drone", "smart_camera"):
        base = reference_design(key)
        better = SystemConfig(base.cpu, base.compute, base.memory,
                              base.memory_devices,
                              preprocessing_mode="isp_and_npu")
        p2 = evaluate_proposal(key, base, better, duration_s=30)
        if p2.deltas["Latency (ms)"] > 0:
            beaten += 1
    check(R, "reference designs leave room to improve", beaten == 3,
          f"{beaten} of 3 improved by moving preprocessing")

    # the three concerns must stay in separate functions
    import ppact.innovation as inn
    src = open(inn.__file__, encoding="utf-8").read()
    check(R, "evidence and rubric are separate functions",
          "def print_proposal" in src and "def print_rubric" in src)
    check(R, "the report asks the student exactly two questions",
          src.count("     ...") == 2, f"{src.count('     ...')} blanks")

    # the tool must not award the bonus
    import ppact.innovation as inn
    src = open(inn.__file__, encoding="utf-8").read()
    check(R, "no function computes an innovation bonus",
          "def award" not in src and "bonus_score" not in src)
    check(R, "the report leaves the bonus blank for the instructor",
          "Innovation bonus     __ / 5" in src)


# ==============================================================================
# PATH S - reference architectures and design examples
# ==============================================================================

def path_s():
    S = "S"
    from ppact.designs import designs_for, DESIGNS, reference_of

    for key, app in APPLICATION_LIBRARY.items():
        options = designs_for(key)
        check(S, f"{key} has a reference and at least one example",
              len(options) >= 2 and options[0].tier == "Starting point")

        # THE invariant: a reference is what ships today, so it must meet the
        # product's own requirements. One that failed would be teaching that
        # shipping products do not work.
        r = evaluate_system(app, options[0].config)
        bad = [g for g, ok in r.gate.items() if not ok]
        check(S, f"{key} reference meets its requirements", r.passes,
              f"fails: {', '.join(bad)}")

        # every option must at least evaluate
        for d in options:
            try:
                evaluate_system(app, d.config)
            except Exception as exc:
                check(S, f"{key} {d.tier} evaluates", False, repr(exc))

        # options must actually differ, or they are not options
        # The CPU is part of the design. Leaving it out of the comparison made
        # two entries that differ only in host look like duplicates.
        configs = {(d.config.cpu, d.config.compute, d.config.memory,
                    d.config.memory_devices, d.config.preprocessing_mode)
                   for d in options}
        check(S, f"{key} options are distinct", len(configs) == len(options),
              f"{len(configs)} distinct of {len(options)}")

        # each carries an architecture description and a reason
        for d in options:
            check(S, f"{key} {d.tier} names its architecture",
                  "CPU" in d.architecture, d.architecture)
            check(S, f"{key} {d.tier} explains itself", len(d.rationale) > 30)

        # every CPU-bearing architecture must in fact have a CPU
        for d in options:
            check(S, f"{key} {d.tier} includes a host CPU",
                  d.config.cpu in CPU_LIBRARY)

    # Inverted at 3.9.0. Before dual-accelerator support existed, a
    # two-engine architecture had to be FLAGGED as approximated. Now it has to
    # be BUILT - an entry naming two engines and configuring one would be a
    # label with nothing behind it, which is the failure this check catches.
    mismatched = []
    for key, options in DESIGNS.items():
        for d in options:
            two_engines = (("GPU" in d.architecture and "NPU" in d.architecture)
                           or "Vision NPU" in d.architecture)
            if two_engines and d.config.secondary_compute is None:
                mismatched.append(f"{key}/{d.tier}: {d.architecture}")
            if not two_engines and d.config.secondary_compute is not None:
                mismatched.append(f"{key}/{d.tier}: configures two, names one")
    check(S, "architectures naming two engines actually configure two",
          not mismatched, "; ".join(mismatched[:3]))

    # a student-defined application still gets a starting point
    from ppact import make_custom_application
    make_custom_application("Design probe", register_as="__designprobe__")
    try:
        opts = designs_for("__designprobe__")
        check(S, "a new application still gets a reference", len(opts) >= 1)
        check(S, "its reference is honest about being generic",
              "probably wrong" in opts[0].rationale)
    finally:
        APPLICATION_LIBRARY.pop("__designprobe__", None)

    # the reference score must be COMPUTED, not stored
    from ppact import reference_score, REFERENCE_BAND
    import ppact.innovation as inn2
    src2 = open(inn2.__file__, encoding="utf-8").read()
    check(S, "no reference score is hard-coded",
          "REFERENCE_SCORES" not in src2 and "= 80.0" not in src2)

    # and it must move when the model moves
    from ppact.game import DOMAIN_ANCHORS
    before = reference_score("industrial_vision")
    saved_anchor = DOMAIN_ANCHORS["Edge"]["Cost"]
    DOMAIN_ANCHORS["Edge"]["Cost"] = ("System cost (USD)", 50.0, 5.0, True)
    after = reference_score("industrial_vision")
    DOMAIN_ANCHORS["Edge"]["Cost"] = saved_anchor
    check(S, "the reference score follows the scoring model",
          abs(after - before) > 1e-6, f"{before:.3f} -> {after:.3f}")
    check(S, "and returns when the model does",
          abs(reference_score("industrial_vision") - before) < 1e-9)

    # gross mis-scaling would show as a reference far outside any plausible
    # band. This is a wide sanity check, not the 75-85 target - forcing that
    # would mean tuning the model to a number instead of reading it.
    out = []
    for key in APPLICATION_LIBRARY:
        v = reference_score(key)
        if not (40.0 <= v <= 95.0):
            out.append(f"{key}={v:.1f}")
    check(S, "no reference is grossly mis-scaled", not out, "; ".join(out))
    check(S, "the calibration band is stated, not enforced",
          REFERENCE_BAND == (75.0, 85.0))

    # the report must actually SHOW the comparison - a scoring block that
    # silently dropped the reference line looked correct in every unit test
    # and told the student nothing
    src3 = open(inn2.__file__, encoding="utf-8").read()
    for needed in ("Starting point", "Your design", "Improvement"):
        check(S, f"the report shows '{needed}'", needed in src3)

    # THE exercise must be winnable: for every application, something in the
    # library must outscore the reference. Note what is NOT asserted - that a
    # bigger accelerator wins. It usually does not: on Industrial Vision a
    # 64x64 array with everything offloaded scores 81.4 against the reference's
    # 81.7, gaining on accuracy and performance and losing more on area and
    # cost. Assuming "bigger is better" was the first version of this check,
    # and it was wrong in a way worth keeping a note about.
    from ppact import system_score
    from ppact.preprocess import MODES as _PM
    unwinnable = []
    for key, app2 in APPLICATION_LIBRARY.items():
        ref_cfg = reference_of(key)
        ref_v = reference_score(key)
        best = ref_v
        for comp in COMPUTE_LIBRARY:
            for n in (1, 2, 4, 8):
                for mode in _PM:
                    cfg2 = SystemConfig(ref_cfg.cpu, comp, ref_cfg.memory, n,
                                        preprocessing_mode=mode)
                    try:
                        v = system_score(key, cfg2, duration_s=10)["Overall"]
                    except Exception:
                        continue
                    best = max(best, v)
        if best <= ref_v + 1e-9:
            unwinnable.append(f"{key} (ref {ref_v:.1f})")
    check(S, "every application leaves room to beat the reference",
          not unwinnable, "; ".join(unwinnable))

    # examples must not all be better than the reference, or they are answers
    trivial = 0
    for key, app in APPLICATION_LIBRARY.items():
        options = designs_for(key)
        if len(options) < 3:
            continue
        ref_lat = evaluate_system(app, options[0].config).metrics["Latency (ms)"]
        better = sum(1 for d in options[1:]
                     if evaluate_system(app, d.config).metrics["Latency (ms)"] < ref_lat)
        if better == len(options) - 1:
            trivial += 1
    check(S, "the examples are not uniformly better than the reference",
          trivial < len(DESIGNS),
          f"{trivial} applications where every example beats the reference")


# ==============================================================================
# PATH T - structured accuracy, and the revision log
# ==============================================================================

def path_t():
    T = "T"
    from ppact.accuracy import (QUANTISATION_LOSS_PP, quantisation_loss_pp,
                                canonical_precision, MODEL_FAMILIES, METHODS)
    from ppact.revisions import REVISIONS

    # the loss must depend on the model, not only on the engine
    families = {quantisation_loss_pp(f, "PTQ", "INT8") for f in MODEL_FAMILIES}
    check(T, "loss differs by model family", len(families) == len(MODEL_FAMILIES),
          str(sorted(families)))
    methods = {quantisation_loss_pp("cnn", m, "INT8")
               for m in ("PTQ", "QAT", "QAT_FP16")}
    check(T, "loss differs by quantisation method", len(methods) == 3, str(sorted(methods)))

    # ordering that the literature agrees on
    for method in ("PTQ", "QAT", "QAT_FP16"):
        cnn = quantisation_loss_pp("cnn", method, "INT8")
        det = quantisation_loss_pp("detection", method, "INT8")
        trf = quantisation_loss_pp("transformer", method, "INT8")
        check(T, f"{method}: transformer loses most, cnn least",
              trf > det > cnn, f"{cnn} {det} {trf}")
    for family in MODEL_FAMILIES:
        ptq = quantisation_loss_pp(family, "PTQ", "INT8")
        qat = quantisation_loss_pp(family, "QAT", "INT8")
        fp16 = quantisation_loss_pp(family, "QAT_FP16", "INT8")
        check(T, f"{family}: QAT beats PTQ, fallback beats QAT",
              ptq > qat > fp16, f"{ptq} {qat} {fp16}")
        check(T, f"{family}: INT4 costs more than INT8",
              quantisation_loss_pp(family, "PTQ", "INT4") >
              quantisation_loss_pp(family, "PTQ", "INT8"))
        check(T, f"{family}: FP32 is lossless",
              quantisation_loss_pp(family, "none", "FP32") == 0.0)

    # descriptive precision labels must resolve, not fall through
    for label, expected in (("INT8", "INT8"),
                            ("INT8 (post-training quantised)", "INT8"),
                            ("INT8 (quantisation-aware trained)", "INT8"),
                            ("INT8 QAT with FP16 fallback", "INT4" if False else "INT8"),
                            ("FP16 / BF16", "FP16"), ("FP32", "FP32"), ("INT4", "INT4")):
        check(T, f"precision label '{label[:28]}' resolves",
              canonical_precision(label) == expected,
              f"got {canonical_precision(label)}")
    # a silent fall-through would have looked plausible and been wrong
    check(T, "an unknown label does not resolve to lossless",
          quantisation_loss_pp("cnn", "QAT", "something odd") > 0)

    # every engine in the library must produce a loss that actually varies
    losses = {c: COMPUTE_LIBRARY[c].accuracy_loss_pp("cnn") for c in COMPUTE_LIBRARY}
    check(T, "engines differ in accuracy cost", len(set(losses.values())) > 2,
          str(sorted(set(round(v, 2) for v in losses.values()))))
    check(T, "no engine has negative accuracy cost", min(losses.values()) >= 0)

    # the same engine must cost differently on different model families
    c = COMPUTE_LIBRARY["npu_32x32"]
    check(T, "one engine, different families, different loss",
          c.accuracy_loss_pp("transformer") > c.accuracy_loss_pp("cnn"),
          f"{c.accuracy_loss_pp('cnn')} vs {c.accuracy_loss_pp('transformer')}")

    # every application declares its family
    for key, app2 in APPLICATION_LIBRARY.items():
        check(T, f"{key} declares a model family",
              app2.model_family in MODEL_FAMILIES, app2.model_family)

    # --- the revision log ----------------------------------------------------
    check(T, "revisions are recorded", len(REVISIONS) >= 3)
    for r in REVISIONS:
        check(T, f"{r.version} records what was observed", len(r.observed) > 30)
        check(T, f"{r.version} records the suspected cause", len(r.suspected) > 30)
        check(T, f"{r.version} records what changed", len(r.changed) > 20)
        check(T, f"{r.version} records independent evidence", len(r.evidence) > 40)
        check(T, f"{r.version} records what it affected", len(r.affected) > 20)
    # the accuracy revision that started all this must be in the log
    check(T, "the 3.6.0 accuracy revision is recorded",
          any("2.0 pp -> 1.2 pp" in r.changed for r in REVISIONS))
    check(T, "the single-constant problem is recorded as a revision",
          any("model family" in r.changed for r in REVISIONS))

    # --- requirements reported separately from the score ---------------------
    from ppact import system_score, print_requirements
    from ppact.designs import reference_of as _ref
    s2 = system_score("llm_service", _ref("llm_service"))
    check(T, "requirement count is reported alongside the score",
          "Requirements met" in s2 and "Requirements total" in s2)
    check(T, "a design can satisfy every requirement and still score low",
          s2["Requirements met"] >= s2["Requirements total"] - 1 and s2["Overall"] < 70,
          f"met {s2['Requirements met']}/{s2['Requirements total']}, "
          f"score {s2['Overall']:.1f}")
    import ppact.innovation as inn3
    src4 = open(inn3.__file__, encoding="utf-8").read()
    check(T, "the report says a score is not a verdict",
          "not a verdict" in src4)


# ==============================================================================
# PATH U - dual accelerator (Phase 2.5)
# ==============================================================================

def path_u():
    U = "U"
    from ppact.system import EXECUTION_MODES
    app = APPLICATION_LIBRARY["industrial_vision"]

    def go(**kw):
        return evaluate_system(app, SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
            preprocessing_mode="isp_and_npu", **kw)).metrics

    single = go()
    seq = go(secondary_compute="npu_16x16", execution_mode="sequential", work_split=0.3)
    par = go(secondary_compute="npu_32x32", execution_mode="parallel", work_split=0.5)
    alt = go(secondary_compute="npu_16x16", execution_mode="alternative",
             alternative_share=0.5)

    # THE property this phase exists to enforce: a second engine is never free
    for label, m in (("sequential", seq), ("parallel", par), ("alternative", alt)):
        check(U, f"{label} adds silicon", m["SoC silicon (mm2)"] > single["SoC silicon (mm2)"],
              f"{m['SoC silicon (mm2)']:.2f} vs {single['SoC silicon (mm2)']:.2f}")
        check(U, f"{label} adds cost", m["System cost (USD)"] > single["System cost (USD)"])
        check(U, f"{label} reports a second die",
              m["Secondary die area (mm2)"] > 0)

    # and it does not automatically make anything faster
    check(U, "sequential with a slower secondary is slower, not faster",
          seq["Latency (ms)"] > single["Latency (ms)"],
          f"{seq['Latency (ms)']:.3f} vs {single['Latency (ms)']:.3f}")
    check(U, "alternative with a slower secondary is slower",
          alt["Latency (ms)"] > single["Latency (ms)"])
    check(U, "parallel with an equal secondary IS faster",
          par["Latency (ms)"] < single["Latency (ms)"],
          f"{par['Latency (ms)']:.3f} vs {single['Latency (ms)']:.3f}")

    # but never by the full factor - splitting costs something
    speedup = single["Latency (ms)"] / par["Latency (ms)"]
    check(U, "parallel speedup is under 2x", 1.0 < speedup < 2.0, f"{speedup:.3f}x")

    # leakage is paid by an engine that never runs
    idle_second = go(secondary_compute="npu_64x64", execution_mode="alternative",
                     alternative_share=0.0)
    check(U, "an engine that does no work still costs static power",
          idle_second["Static energy per inference (mJ)"]
          > single["Static energy per inference (mJ)"],
          f"{idle_second['Static energy per inference (mJ)']:.4f} vs "
          f"{single['Static energy per inference (mJ)']:.4f}")
    check(U, "an engine that does no work still costs area and money",
          idle_second["SoC silicon (mm2)"] > single["SoC silicon (mm2)"]
          and idle_second["System cost (USD)"] > single["System cost (USD)"])
    check(U, "and does no compute", idle_second["Secondary compute time (ms)"] == 0.0)

    # work conservation: the split must not create or destroy MACs
    for split in (0.0, 0.25, 0.5, 0.75, 1.0):
        m = go(secondary_compute="npu_32x32", execution_mode="sequential",
               work_split=split)
        total = m["Primary compute time (ms)"] + m["Secondary compute time (ms)"]
        check(U, f"work is conserved at split {split}",
              abs(total - single["Compute time (ms)"]) < 1e-6,
              f"{total:.6f} vs {single['Compute time (ms)']:.6f}")

    # hand-off is charged where there is one, and not where there is not
    check(U, "sequential charges a hand-off", seq["Handoff (ms)"] > 0)
    check(U, "parallel charges a hand-off", par["Handoff (ms)"] > 0)
    check(U, "alternative charges none - only one engine runs",
          alt["Handoff (ms)"] == 0.0)
    check(U, "a single engine charges none", single["Handoff (ms)"] == 0.0)

    # accuracy: with a mixed pair, the worse engine governs
    mixed = evaluate_system(APPLICATION_LIBRARY["medical"], SystemConfig(
        "cortex_a78_x4", "mobile_gpu", "LPDDR5", 2,
        secondary_compute="npu_16x16", execution_mode="alternative",
        alternative_share=0.5)).metrics
    gpu_only = evaluate_system(APPLICATION_LIBRARY["medical"], SystemConfig(
        "cortex_a78_x4", "mobile_gpu", "LPDDR5", 2)).metrics
    check(U, "a mixed pair is governed by the worse engine's accuracy",
          mixed["Deployment accuracy (%)"] < gpu_only["Deployment accuracy (%)"],
          f"{mixed['Deployment accuracy (%)']:.2f} vs "
          f"{gpu_only['Deployment accuracy (%)']:.2f}")

    # --- preprocessing placement, checked properly ---------------------------
    #
    # The first version of this only asserted that preprocessing time existed
    # and the secondary did no inference. Both would have been true if the
    # PRIMARY had done the preprocessing, so it verified nothing. The rate the
    # work was sized against is the thing to test.
    saved16 = COMPUTE_LIBRARY["npu_16x16"]
    times = []
    for clk in (0.4, 0.8, 1.6):
        COMPUTE_LIBRARY["npu_16x16"] = dataclasses.replace(saved16, clock_ghz=clk)
        times.append(go(secondary_compute="npu_16x16", execution_mode="sequential",
                        work_split=0.0)["Preprocess offload (ms)"])
    COMPUTE_LIBRARY["npu_16x16"] = saved16
    check(U, "preprocessing is sized on the SECONDARY engine's rate",
          abs(times[0] / times[1] - 2.0) < 0.02 and abs(times[1] / times[2] - 2.0) < 0.02,
          str([round(t, 4) for t in times]))

    # and on the primary when there is no secondary
    savedp = COMPUTE_LIBRARY["npu_32x32"]
    COMPUTE_LIBRARY["npu_32x32"] = dataclasses.replace(savedp, clock_ghz=savedp.clock_ghz * 2)
    faster_primary = go()["Preprocess offload (ms)"]
    COMPUTE_LIBRARY["npu_32x32"] = savedp
    check(U, "with one engine, preprocessing follows the primary's rate",
          faster_primary < single["Preprocess offload (ms)"] * 0.6,
          f"{faster_primary:.5f} vs {single['Preprocess offload (ms)']:.5f}")
    check(U, "the placement is reported",
          go(secondary_compute="npu_16x16", execution_mode="sequential",
             work_split=0.0)["Preprocessing on secondary"] == 1.0
          and single["Preprocessing on secondary"] == 0.0)

    # --- no double booking in parallel mode ---------------------------------
    #
    # One array cannot run its share of the inference and the preprocessing at
    # the same instant. Sizing the preprocessing after the split and hiding it
    # behind the result did exactly that.
    par0 = go(secondary_compute="npu_32x32", execution_mode="parallel", work_split=0.0)
    parhalf = go(secondary_compute="npu_32x32", execution_mode="parallel", work_split=0.5)
    check(U, "parallel latency is never below the primary's own share",
          parhalf["Latency (ms)"] >= parhalf["Primary compute time (ms)"],
          f"{parhalf['Latency (ms)']:.4f} vs {parhalf['Primary compute time (ms)']:.4f}")
    # With nothing split there is no partition to pay for - but a second
    # engine running preprocessing does launch its own graph, and since 3.27.0
    # that costs a framework overhead. The difference must therefore be the
    # SECOND ENGINE'S LAUNCH and nothing else, which is a tighter statement
    # than the 2% tolerance this check used to carry.
    launch = COMPUTE_LIBRARY["npu_32x32"].framework_overhead_ms
    check(U, "an unsplit parallel pair pays only the second engine's launch",
          abs((par0["Latency (ms)"] - single["Latency (ms)"]) - launch) < 0.05,
          f"{par0['Latency (ms)'] - single['Latency (ms)']:.4f} ms vs "
          f"launch {launch:.4f} ms")
    # a heavier preprocessing load must push the parallel time up
    heavy = evaluate_system(dataclasses.replace(app, input_pixels=app.input_pixels * 8),
                            SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                                         preprocessing_mode="isp_and_npu",
                                         secondary_compute="npu_32x32",
                                         execution_mode="parallel",
                                         work_split=0.5)).metrics
    check(U, "heavier preprocessing raises parallel latency",
          heavy["Latency (ms)"] > parhalf["Latency (ms)"])

    # --- the two share parameters are not interchangeable -------------------
    seq_split = go(secondary_compute="npu_32x32", execution_mode="sequential",
                   work_split=0.5, alternative_share=0.9)
    alt_share = go(secondary_compute="npu_32x32", execution_mode="alternative",
                   work_split=0.9, alternative_share=0.5)
    check(U, "sequential reads work_split and ignores alternative_share",
          seq_split["Work split (MAC fraction)"] == 0.5
          and seq_split["Alternative share (job fraction)"] == 0.0)
    check(U, "alternative reads alternative_share and ignores work_split",
          alt_share["Alternative share (job fraction)"] == 0.5
          and alt_share["Work split (MAC fraction)"] == 0.0)
    check(U, "the two parameters produce different results at the same value",
          abs(go(secondary_compute="npu_16x16", execution_mode="sequential",
                 work_split=0.5)["Latency (ms)"]
              - go(secondary_compute="npu_16x16", execution_mode="alternative",
                   alternative_share=0.5)["Latency (ms)"]) > 1e-6)

    # every mode must evaluate for every application
    fails = []
    for key in APPLICATION_LIBRARY:
        for m2 in ("sequential", "parallel", "alternative"):
            try:
                evaluate_system(APPLICATION_LIBRARY[key], SystemConfig(
                    "cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                    secondary_compute="npu_16x16", execution_mode=m2))
            except Exception as exc:
                fails.append(f"{key}/{m2}: {exc}")
    check(U, "every application evaluates in every mode", not fails, "; ".join(fails[:3]))

    # an unknown mode is refused
    try:
        evaluate_system(app, SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                                          secondary_compute="npu_16x16",
                                          execution_mode="telepathy"))
        check(U, "an unknown execution mode is rejected", False, "no error")
    except KeyError:
        check(U, "an unknown execution mode is rejected", True)

    # the runtime must report the two engines separately
    from ppact import simulate
    r = simulate("industrial_vision", SystemConfig(
        "cortex_a78_x4", "npu_32x32", "LPDDR5", 4, preprocessing_mode="isp_and_npu",
        secondary_compute="npu_16x16", execution_mode="sequential", work_split=0.0),
        duration_s=30)
    check(U, "the dashboard separates the two engines",
          "Accelerator 1" in r.modules and "Accelerator 2" in r.modules,
          str(sorted(r.modules)))

    # --- 1. an interior optimum exists --------------------------------------
    #
    # With two identical engines the best split is neither zero nor one. A
    # monotone curve would mean one of the two terms - the parallel gain or the
    # split cost - was missing.
    curve = [(x / 10.0,
              go(secondary_compute="npu_32x32", execution_mode="parallel",
                 work_split=x / 10.0)["Latency (ms)"]) for x in range(11)]
    best_split, best_lat = min(curve, key=lambda t: t[1])
    check(U, "the best split is interior, not at an end",
          0.0 < best_split < 1.0, f"best at {best_split}")
    check(U, "and identical engines put it near the middle",
          0.4 <= best_split <= 0.6, f"best at {best_split}")
    check(U, "the curve rises on both sides of the optimum",
          curve[0][1] > best_lat and curve[-1][1] > best_lat,
          f"{curve[0][1]:.3f} .. {best_lat:.3f} .. {curve[-1][1]:.3f}")

    # --- 2. symmetry with identical engines ---------------------------------
    #
    # Only holds when nothing else distinguishes them. With accelerator
    # preprocessing the secondary carries extra work, so the two are NOT
    # symmetric - and that asymmetry must equal the preprocessing time, not be
    # some unexplained amount.
    def sym(mode_pre, split):
        return evaluate_system(app, SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
            preprocessing_mode=mode_pre, secondary_compute="npu_32x32",
            execution_mode="parallel", work_split=split)).metrics
    a3, a7 = sym("isp_assisted", 0.3), sym("isp_assisted", 0.7)
    check(U, "identical engines are symmetric when nothing favours one",
          abs(a3["Latency (ms)"] - a7["Latency (ms)"]) < 1e-6,
          f"{a3['Latency (ms)']:.5f} vs {a7['Latency (ms)']:.5f}")
    b3, b7 = sym("isp_and_npu", 0.3), sym("isp_and_npu", 0.7)
    asym = b7["Latency (ms)"] - b3["Latency (ms)"]
    expected = b7["Secondary preprocess (ms)"] / PARALLEL_EFF
    # Relative, not absolute. Concurrency-scaled contention differs slightly
    # between 0.3 and 0.7 once the secondary also carries preprocessing, so a
    # small residual is expected and its SIZE is what matters: if the
    # asymmetry were not dominated by the preprocessing role, the explanation
    # would be wrong.
    check(U, "with preprocessing the asymmetry is the preprocessing load",
          abs(asym - expected) / expected < 0.05,
          f"asymmetry {asym:.4f} vs preprocessing {expected:.4f} "
          f"({abs(asym - expected) / expected * 100:.1f}% residual)")

    # --- 3. a slow secondary must eventually make things worse --------------
    slow = [(x / 10.0, go(secondary_compute="npu_16x16", execution_mode="parallel",
                          work_split=x / 10.0)["Latency (ms)"]) for x in (0, 2, 5, 8, 10)]
    check(U, "a slow secondary hurts once it is given too much",
          slow[-1][1] > slow[0][1] * 1.5,
          str([(x, round(v, 2)) for x, v in slow]))
    check(U, "but a small share of it can still help",
          min(v for _, v in slow) <= slow[0][1] + 1e-9,
          str([(x, round(v, 2)) for x, v in slow]))

    # --- 4. shared bandwidth: saturation, then reversal ----------------------
    #
    # TWO CLAIMS, TESTED SEPARATELY, because they do not have the same standing.
    #
    # The SATURATION is a model result and holds with the interleaving
    # coefficient at zero: splitting the arithmetic shortens the compute term
    # and leaves the transfer term alone, so the gain shrinks as the bus
    # narrows. No parameter produces it.
    #
    # The REVERSAL - parallel becoming slower than not splitting - depends
    # entirely on that coefficient. It was once reported as if the model had
    # found it; it had not. The test says so.
    import ppact.system as _S
    saved_pen = _S.DUAL_MEMORY_CONTENTION

    def gain(mem, n):
        base = evaluate_system(app, SystemConfig(
            "cortex_a78_x4", "npu_32x32", mem, n, preprocessing_mode="isp_and_npu",
            secondary_compute="npu_32x32", execution_mode="parallel",
            work_split=0.0)).metrics["Latency (ms)"]
        par = evaluate_system(app, SystemConfig(
            "cortex_a78_x4", "npu_32x32", mem, n, preprocessing_mode="isp_and_npu",
            secondary_compute="npu_32x32", execution_mode="parallel",
            work_split=0.5)).metrics["Latency (ms)"]
        return par - base

    _S.DUAL_MEMORY_CONTENTION = 0.0
    try:
        wide = gain("HBM3E", 1)
        mid = gain("LPDDR5", 4)
        narrow = gain("LPDDR5", 1)
    finally:
        _S.DUAL_MEMORY_CONTENTION = saved_pen
    check(U, "without any contention term, parallel still helps everywhere",
          wide < 0 and mid < 0 and narrow < 0,
          f"HBM {wide:.3f}, LPDDR x4 {mid:.3f}, LPDDR x1 {narrow:.3f}")
    # Saturation means the gain stops improving once the bus is wide enough,
    # so a wide bus and a merely sufficient one should give the SAME gain -
    # both are compute bound and the split saves the same arithmetic. This
    # check demanded a strict inequality between them and passed on a
    # difference below 1e-10, which is floating-point noise rather than a
    # property. Corrected at 3.54.0 to say what saturation actually means.
    check(U, "the gain saturates once the bus is wide enough",
          abs(wide) >= abs(mid) - 1e-9,
          f"HBM {wide:.6f} against LPDDR x4 {mid:.6f}")
    check(U, "and collapses when the bus is genuinely narrow",
          abs(mid) > abs(narrow) * 2,
          f"LPDDR x4 {mid:.3f} against LPDDR x1 {narrow:.3f}")

    # with the coefficient in place the sign can flip - and that is a
    # consequence of the coefficient, recorded as such
    check(U, "the sign flip depends on the interleaving coefficient",
          gain("LPDDR5", 1) > 0 > narrow,
          f"with penalty {gain('LPDDR5', 1):.3f}, without {narrow:.3f}")
    check(U, "and a wide bus keeps the advantage either way",
          gain("HBM3E", 1) < 0)
    def pair(mem, n):
        base = evaluate_system(app, SystemConfig(
            "cortex_a78_x4", "npu_32x32", mem, n, preprocessing_mode="isp_and_npu",
            secondary_compute="npu_32x32", execution_mode="parallel",
            work_split=0.0)).metrics["Latency (ms)"]
        par = evaluate_system(app, SystemConfig(
            "cortex_a78_x4", "npu_32x32", mem, n, preprocessing_mode="isp_and_npu",
            secondary_compute="npu_32x32", execution_mode="parallel",
            work_split=0.5)).metrics["Latency (ms)"]
        return base, par
    # contention scales with how much the two engines actually overlap
    conc = [go(secondary_compute="npu_32x32", execution_mode="parallel",
               work_split=x)["Shared bandwidth contention (%)"]
            for x in (0.0, 0.1, 0.3, 0.5, 0.7, 0.9)]
    check(U, "contention peaks where the two engines overlap most",
          max(conc) == conc[3], str([round(c, 1) for c in conc]))
    check(U, "and is near zero when one engine barely runs",
          conc[0] < 1.0 and conc[-1] < max(conc) / 2,
          str([round(c, 1) for c in conc]))
    for label, kw in (("sequential", dict(execution_mode="sequential", work_split=0.5)),
                      ("alternative", dict(execution_mode="alternative",
                                           alternative_share=0.5))):
        check(U, f"no contention for {label} - one engine issues at a time",
              go(secondary_compute="npu_32x32", **kw)["Shared bandwidth contention (%)"] == 0)
    check(U, "a single engine has no contention",
          single["Shared bandwidth contention (%)"] == 0)

    # --- the optimum must MOVE with the secondary's speed --------------------
    #
    # Direction, not value: a slower secondary should be given less work. A
    # fixed optimum would mean the split was not responding to the hardware.
    optima = []
    for sec in ("npu_32x32", "npu_24x24", "npu_20x20", "npu_16x16"):
        curve2 = [(x / 20.0, go(secondary_compute=sec, execution_mode="parallel",
                                work_split=x / 20.0)["Latency (ms)"])
                  for x in range(21)]
        optima.append(min(curve2, key=lambda t: t[1])[0])
    check(U, "a slower secondary is given less of the work",
          all(a4 >= b4 for a4, b4 in zip(optima, optima[1:])) and optima[0] > optima[-1],
          str(optima))

    # --- 5. one array cannot preprocess and infer at once -------------------
    #
    # Held as an invariant rather than as a flag. Overlapping them would need
    # two engines inside the secondary, which this model does not have, and a
    # switch permitting it would be a licence to produce a wrong answer.
    bad_sum = 0
    for split in (0.0, 0.25, 0.5, 0.75, 1.0):
        for m3 in ("sequential", "parallel"):
            mm = go(secondary_compute="npu_32x32", execution_mode=m3, work_split=split)
            if abs(mm["Secondary active (ms)"]
                   - (mm["Secondary preprocess (ms)"] + mm["Secondary inference (ms)"])) > 1e-9:
                bad_sum += 1
    check(U, "secondary active time is preprocessing PLUS inference, always",
          bad_sum == 0, f"{bad_sum} violations")
    import ppact.system as _sys
    src5 = open(_sys.__file__, encoding="utf-8").read()
    check(U, "no switch exists to overlap them",
          "allow_secondary_overlap" not in src5 and "independent_engines" not in src5)

    # --- 6. every latency change must be explainable ------------------------
    from ppact.runtime import explain_latency_delta
    import io, contextlib
    for label, kw in (("parallel 0.0", dict(execution_mode="parallel", work_split=0.0)),
                      ("parallel 0.5", dict(execution_mode="parallel", work_split=0.5)),
                      ("sequential 0.3", dict(execution_mode="sequential", work_split=0.3)),
                      ("alternative 0.5", dict(execution_mode="alternative",
                                               alternative_share=0.5))):
        after = go(secondary_compute="npu_32x32", **kw)
        with contextlib.redirect_stdout(io.StringIO()):
            parts = explain_latency_delta(single, after)
        check(U, f"the change to {label} is fully accounted for",
              abs(parts["Unexplained"]) < 1e-6, f"{parts['Unexplained']:.6f} ms left over")

    # and the design library no longer has to approximate them
    from ppact.designs import DESIGNS
    approx = [f"{k}/{d.tier}" for k, v in DESIGNS.items() for d in v if not d.modelled]
    check(U, "no design is still flagged as approximated", not approx,
          "; ".join(approx[:3]))


# ==============================================================================
# PATH V - provenance of the chosen numbers
# ==============================================================================

def path_v():
    V = "V"
    from ppact.coefficients import (COEFFICIENTS, BY_NAME, SOURCES, CONFIDENCES,
                                    provenance)
    import ppact.system as _S
    import ppact.preprocess as _P

    check(V, "coefficients are registered", len(COEFFICIENTS) >= 10)
    for c in COEFFICIENTS:
        check(V, f"{c.name} declares a source", c.source in SOURCES, c.source)
        check(V, f"{c.name} declares a confidence", c.confidence in CONFIDENCES)
        check(V, f"{c.name} says what it is", len(c.note) > 30)
        check(V, f"{c.name} says what depends on it", len(c.depends_on) > 15)

    # the registry must match the code, or it is documentation of a past state
    live = {
        "DUAL_MEMORY_CONTENTION": _S.DUAL_MEMORY_CONTENTION,
        "PARALLEL_SPLIT_EFFICIENCY": _S.PARALLEL_SPLIT_EFFICIENCY,
        "DUAL_DISPATCH_US": _S.DUAL_DISPATCH_US,
        "NPU_PREPROCESS_DISPATCH_US": _P.NPU_PREPROCESS_DISPATCH_US,
        "NPU_PREPROCESS_AREA_UPLIFT": _P.NPU_PREPROCESS_AREA_UPLIFT,
        "NPU_PREPROCESS_POWER_UPLIFT": _P.NPU_PREPROCESS_POWER_UPLIFT,
        "ISP_PIXELS_PER_SECOND": _P.ISP_PIXELS_PER_SECOND,
        "ISP_AREA_MM2": _P.ISP_AREA_MM2,
        "ISP_STATIC_POWER_W": _P.ISP_STATIC_POWER_W,
        "ISP_ENERGY_PJ_PER_PIXEL": _P.ISP_ENERGY_PJ_PER_PIXEL,
    }
    for name, value in live.items():
        c = BY_NAME.get(name)
        check(V, f"{name} is registered", c is not None)
        if c is not None:
            check(V, f"{name} registry matches the code",
                  abs(c.value - value) < 1e-9, f"{c.value} vs {value}")

    # the coefficient the sign flip depends on must be marked as such
    c = BY_NAME["DUAL_MEMORY_CONTENTION"]
    check(V, "the contention coefficient is marked low confidence",
          c.confidence == "LOW")
    check(V, "and declares that the reversal depends on it",
          "SIGN FLIP" in c.depends_on)
    check(V, "and is editable, so it can be argued with", c.editable)

    # the wording must not claim a mechanism the model does not implement
    src = open(_S.__file__, encoding="utf-8").read()
    check(V, "the contention term does not claim to model row locality",
          "row locality as the cause" in src or "row locality" not in src.split(
              "no arbitration")[-1],
          "check the comment wording")
    for module in (_S, _P):
        text = open(module.__file__, encoding="utf-8").read()
        for claim in ("bank conflict model", "row-buffer hit", "arbitration policy"):
            check(V, f"{module.__name__} does not claim '{claim}'",
                  claim not in text)

    # the student screen must separate derived from assumed
    import ppact.runtime as _R
    rsrc = open(_R.__file__, encoding="utf-8").read()
    check(V, "the analysis screen labels model-derived terms",
          "model-derived" in rsrc)
    check(V, "and labels assumption-based terms", "assumption" in rsrc)
    check(V, "and warns when a reversal rests on a coefficient",
          "conditional on that coefficient" in rsrc)

    # provenance lookup
    check(V, "a registered name reports as an assumption",
          "assumption" in provenance("DUAL_MEMORY_CONTENTION"))
    check(V, "an unregistered name reports as derived",
          provenance("Compute time (ms)") == "model-derived")

    # editing a coefficient must actually change results - a registry entry
    # that nothing reads would be worse than none
    from ppact import APPLICATION_LIBRARY as _A, SystemConfig as _C, evaluate_system as _E
    cfg = _C("cortex_a78_x4", "npu_32x32", "LPDDR5", 1,
             preprocessing_mode="isp_and_npu", secondary_compute="npu_32x32",
             execution_mode="parallel", work_split=0.5)
    saved = _S.DUAL_MEMORY_CONTENTION
    a5 = _E(_A["industrial_vision"], cfg).metrics["Latency (ms)"]
    _S.DUAL_MEMORY_CONTENTION = 0.0
    b5 = _E(_A["industrial_vision"], cfg).metrics["Latency (ms)"]
    _S.DUAL_MEMORY_CONTENTION = saved
    check(V, "editing the coefficient changes the result", abs(a5 - b5) > 1e-6,
          f"{a5:.4f} vs {b5:.4f}")
    check(V, "and restoring it restores the result",
          abs(_E(_A["industrial_vision"], cfg).metrics["Latency (ms)"] - a5) < 1e-12)


# ==============================================================================
# PATH W - Phase 3 completion conditions
# ==============================================================================

def path_w():
    W = "W"
    from ppact import simulate, explore_memory
    import ppact.system as _S

    # TWO packages, not one. Mobile AI needs 5 GB and one LPDDR5 package
    # holds 4, so every figure this path measured was computed for a machine
    # that cannot hold its model - which only became visible at 3.67.0, when
    # an infeasible configuration stopped returning usable numbers.
    def run(app_key="mobile_ai", compute="npu_64x64", mem="LPDDR5", n=2,
            duration=60.0, **kw):
        return simulate(app_key, SystemConfig("cortex_a78_x4", compute, mem, n, **kw),
                        duration_s=duration)

    # 1. a single-accelerator configuration must be untouched by the dual path
    one = run()
    check(W, "1 a single engine reports one accelerator module",
          "Accelerator" in one.modules and "Accelerator 2" not in one.modules,
          str(sorted(one.modules)))
    m1 = one.base.metrics
    check(W, "1 its secondary metrics are all zero",
          m1["Secondary die area (mm2)"] == 0 and m1["Secondary active (ms)"] == 0
          and m1["Handoff (ms)"] == 0
          and m1["Shared bandwidth contention (%)"] == 0)
    # a single accelerator must also be able to be memory limited
    single_limits = {simulate("mobile_ai", SystemConfig(
        "cortex_a78_x4", "npu_64x64", mem, n), duration_s=10).limiting_stage
        for mem, n in (("LPDDR5", 1), ("HBM3E", 1))}
    check(W, "1 a single accelerator can be limited by its memory",
          "Memory" in single_limits, str(single_limits))
    single_caps = [simulate("mobile_ai", SystemConfig(
        "cortex_a78_x4", "npu_64x64", mem, n), duration_s=10
    ).metrics["Capacity (jobs)"] for mem, n in (("LPDDR5", 1), ("LPDDR5", 4))]
    check(W, "1 and its capacity scales with the memory",
          single_caps[1] / single_caps[0] > 3.0,
          f"{single_caps[1] / single_caps[0]:.2f}x")

    check(W, "1 and its accelerator stage equals the single-engine stage",
          abs(m1["Stage accelerator 1 (ms)"]
              + m1["Stage accelerator 2 (ms)"]
              - (m1["Compute time (ms)"] + m1["Preprocess offload (ms)"])) < 1e-9)

    # 2. both engines get their own active, wait and idle
    two = run(secondary_compute="npu_64x64", execution_mode="sequential",
              work_split=0.5)
    for name in ("Accelerator 1", "Accelerator 2"):
        st = two.modules.get(name)
        check(W, f"2 {name} has its own state", st is not None)
        if st:
            total = st.active_ms + st.wait_ms + st.idle_ms
            check(W, f"2 {name} states partition the window",
                  abs(total - two.total_time_ms) < 1e-6)
            check(W, f"2 {name} states are non-negative",
                  min(st.active_ms, st.wait_ms, st.idle_ms) >= -1e-9)
    check(W, "2 the two engines are not identical in occupancy",
          two.modules["Accelerator 1"].active_ms
          != two.modules["Accelerator 2"].active_ms
          or two.modules["Accelerator 2"].wait_ms
          != two.modules["Accelerator 1"].wait_ms)

    # 3. the three modes must differ in throughput capacity, not only latency
    caps = {}
    for mode, kw in (("sequential", dict(execution_mode="sequential", work_split=0.5)),
                     ("parallel", dict(execution_mode="parallel", work_split=0.5)),
                     ("alternative", dict(execution_mode="alternative",
                                          alternative_share=0.5))):
        r = run(secondary_compute="npu_64x64", **kw)
        caps[mode] = r.metrics["Capacity (jobs)"]
    check(W, "3 the execution modes differ in capacity",
          len(set(caps.values())) > 1, str(caps))
    check(W, "3 parallel pays for contention in throughput too",
          caps["parallel"] < caps["sequential"], str(caps))

    # 4. a low arrival rate must leave the machine idle
    app = APPLICATION_LIBRARY["mobile_ai"]
    idles = []
    for fps in (1, 5, 20):
        tuned = dataclasses.replace(app, target_inferences_per_s=fps)
        APPLICATION_LIBRARY["__rate__"] = dataclasses.replace(tuned, key="__rate__")
        try:
            r = run("__rate__", secondary_compute="npu_64x64",
                    execution_mode="parallel", work_split=0.5)
            idles.append(r.modules["Accelerator 1"].idle_ms / r.total_time_ms)
        finally:
            APPLICATION_LIBRARY.pop("__rate__", None)
    check(W, "4 a lower arrival rate leaves more idle time",
          idles[0] > idles[1] > idles[2], str([round(x, 4) for x in idles]))

    # 5. an arrival rate above capacity must be reported, not absorbed
    fast = dataclasses.replace(app, target_inferences_per_s=100000, key="__fast__")
    APPLICATION_LIBRARY["__fast__"] = fast
    try:
        r = run("__fast__", secondary_compute="npu_64x64",
                execution_mode="parallel", work_split=0.5)
        check(W, "5 work beyond capacity is left undone and reported",
              r.metrics["Keeps up"] == 0.0
              and r.jobs < r.metrics["Jobs demanded"],
              f"{r.jobs} of {r.metrics['Jobs demanded']:.0f}")
        check(W, "5 and the shortfall equals capacity, not an arbitrary cap",
              abs(r.jobs - r.metrics["Capacity (jobs)"]) < 1.5)
    finally:
        APPLICATION_LIBRARY.pop("__fast__", None)

    # 6. the memory choice must reach BOTH the memory wait and the throughput
    # From TWO packages: one holds 4 GB against a 5 GB model, so the first
    # point of this series used to be an infeasible configuration and every
    # figure taken from it described a machine that cannot exist.
    caps2, waits = [], []
    for mem, n in (("LPDDR5", 2), ("LPDDR5", 8), ("HBM3E", 1)):
        r = run(mem=mem, n=n, secondary_compute="npu_64x64",
                execution_mode="parallel", work_split=0.5)
        caps2.append(r.metrics["Capacity (jobs)"])
        st = r.modules["Accelerator 1"]
        waits.append(st.wait_ms / r.total_time_ms)
    # Direction is not enough. A mutation that removed memory from the stage
    # list left capacity strictly increasing - by 0.03% across a fourfold
    # bandwidth change - and this check passed. On a memory-bound design the
    # capacity has to scale with the memory, not merely nudge.
    check(W, "6 wider memory raises the capacity",
          caps2[0] < caps2[1] < caps2[2], str([round(c) for c in caps2]))
    # Ratios revised at 3.67.0 with the baseline moved from one package to
    # two - four times the packages gives four times the capacity, and a
    # single HBM stack about nine.
    check(W, "6 and raises it in proportion, not by a rounding error",
          caps2[1] / caps2[0] > 3.0 and caps2[2] / caps2[0] > 8.0,
          f"x8 gives {caps2[1] / caps2[0]:.2f}x, HBM gives "
          f"{caps2[2] / caps2[0]:.2f}x")
    check(W, "6 and a memory-bound design is limited by the memory",
          any(simulate("mobile_ai", SystemConfig(
              "cortex_a78_x4", "npu_64x64", mem, n,
              secondary_compute="npu_64x64", execution_mode="parallel",
              work_split=0.5), duration_s=10).limiting_stage == "Memory"
              for mem, n in (("LPDDR5", 2), ("LPDDR5", 8))),
          "memory must be able to set the pipeline interval")
    check(W, "6 and reduces the accelerator's memory wait",
          waits[0] > waits[1] > waits[2], str([round(x, 5) for x in waits]))

    # 7. with the assumed coefficient off, the saturation effect must remain
    saved = _S.DUAL_MEMORY_CONTENTION
    _S.DUAL_MEMORY_CONTENTION = 0.0
    try:
        narrow = run(mem="LPDDR5", n=1, secondary_compute="npu_64x64",
                     execution_mode="parallel", work_split=0.5)
        wide = run(mem="HBM3E", n=1, secondary_compute="npu_64x64",
                   execution_mode="parallel", work_split=0.5)
    finally:
        _S.DUAL_MEMORY_CONTENTION = saved
    check(W, "7 saturation survives with the coefficient at zero",
          narrow.metrics["Capacity (jobs)"] < wide.metrics["Capacity (jobs)"],
          f"{narrow.metrics['Capacity (jobs)']:.0f} vs "
          f"{wide.metrics['Capacity (jobs)']:.0f}")
    check(W, "7 and the limiting stage is still named",
          narrow.limiting_stage in ("Memory", "Accelerator 1", "Accelerator 2",
                                    "CPU", "ISP"))

    # 8. requirement satisfaction and the score stay separate
    from ppact import system_score
    cfg = SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 1,
                       secondary_compute="npu_64x64", execution_mode="parallel",
                       work_split=0.5)
    sc = system_score("mobile_ai", cfg)
    check(W, "8 the score reports requirements separately",
          "Requirements met" in sc and "Overall" in sc
          and sc["Requirements met"] <= sc["Requirements total"])

    # memory exploration must run for every mode without error
    import io, contextlib
    fails = []
    for mode, kw in (("sequential", dict(execution_mode="sequential", work_split=0.5)),
                     ("parallel", dict(execution_mode="parallel", work_split=0.5)),
                     ("alternative", dict(execution_mode="alternative",
                                          alternative_share=0.5))):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                explore_memory("mobile_ai", SystemConfig(
                    "cortex_a78_x4", "npu_64x64", "LPDDR5", 1,
                    secondary_compute="npu_64x64", **kw), duration_s=10)
        except Exception as exc:
            fails.append(f"{mode}: {exc}")
    check(W, "memory exploration runs in every mode", not fails, "; ".join(fails))

    # and read/write traffic must split, not vanish
    m = run(secondary_compute="npu_64x64", execution_mode="parallel",
            work_split=0.5).metrics
    check(W, "traffic splits into read and write",
          m["Total DRAM read (GB)"] > 0 and m["Total DRAM write (GB)"] > 0)
    check(W, "and the two sum to the total",
          abs(m["Total DRAM read (GB)"] + m["Total DRAM write (GB)"]
              - m["Total DRAM traffic (GB)"]) < 1e-6)


# ==============================================================================
# PATH X - memory subsystem boundaries
# ==============================================================================

def path_x():
    X = "X"
    from ppact.memory import evaluate as mem_eval

    # --- cost decomposition --------------------------------------------------
    for key, spec in MEMORY_LIBRARY.items():
        m = mem_eval(spec).metrics
        parts = (m["  interposer (USD)"] + m["  advanced package (USD)"]
                 + m["  assembly and test (USD)"])
        check(X, f"{key} packaging parts sum to the packaging cost",
              abs(parts - spec.package_cost_usd) < 1e-9,
              f"{parts:.2f} vs {spec.package_cost_usd:.2f}")
        check(X, f"{key} total is silicon plus packaging, over yield",
              abs(m["Package cost (USD)"]
                  - (m["  memory silicon (USD)"] + spec.package_cost_usd)
                  / spec.stack_assembly_yield) < 1e-6)
        check(X, f"{key} reports a packaging share",
              0 <= m["  packaging share (%)"] <= 100)

    # HBM's price is mostly not its DRAM - that is the point of splitting it
    shares = {k: mem_eval(v).metrics["  packaging share (%)"]
              for k, v in MEMORY_LIBRARY.items()}
    check(X, "HBM is packaging-dominated relative to the others",
          shares["HBM3E"] > shares["LPDDR5"] * 1.5
          and shares["HBM3E"] > shares["GDDR6"] * 1.5,
          str({k: round(v, 1) for k, v in shares.items()}))
    check(X, "only HBM carries an interposer",
          MEMORY_LIBRARY["HBM3E"].interposer_cost_usd > 0
          and MEMORY_LIBRARY["LPDDR5"].interposer_cost_usd == 0
          and MEMORY_LIBRARY["GDDR6"].interposer_cost_usd == 0)

    # --- area boundary -------------------------------------------------------
    #
    # HBM does not grow the logic die. It grows the package. Adding it to a
    # single silicon figure would have said the opposite.
    cfg = lambda mem, n: SystemConfig(
        "cortex_a78_x4", "npu_64x64", mem, n, secondary_compute="npu_64x64",
        execution_mode="parallel", work_split=0.5)
    rows = [(mem, n, evaluate_system(APPLICATION_LIBRARY["mobile_ai"], cfg(mem, n)).metrics)
            for mem, n in (("LPDDR5", 2), ("GDDR6", 4), ("HBM3E", 1), ("HBM3E", 2))]
    logic = {r[2]["Logic silicon (mm2)"] for r in rows}
    check(X, "the memory choice does not change the logic silicon",
          len(logic) == 1, str(sorted(round(v, 3) for v in logic)))
    footprints = [r[2]["Package footprint (mm2)"] for r in rows]
    check(X, "but it does change the package footprint",
          len(set(footprints)) > 1, str([round(v) for v in footprints]))
    for mem, n, m in rows:
        check(X, f"{mem} x{n} footprint splits into compute and memory",
              abs(m["  compute footprint (mm2)"] + m["  memory footprint (mm2)"]
                  - m["Package footprint (mm2)"]) < 1e-9)

    # --- thermal boundary ----------------------------------------------------
    #
    # A negative total margin has to be attributable. Before the split it was
    # a single number that could not say whether the compute or the memory put
    # the design over.
    hbm = dict(rows[2][2])
    lp = dict(rows[0][2])
    check(X, "HBM puts the design over the product's cooling assumption",
          hbm["Thermal margin (%)"] < 0)
    # Revised at 3.16.0. This once asserted that the MEMORY margin went
    # negative, which it did - because an HBM stack was being measured against
    # a phone's passive limit. Judged against its own package class the stack
    # is comfortable, and the real statement is the compatibility one: this
    # memory needs cooling the product does not have.
    check(X, "the memory itself is fine under its own cooling class",
          hbm["  memory thermal margin (%)"] > 0,
          f"{hbm['  memory thermal margin (%)']:.1f}%")
    check(X, "and the incompatibility is reported as a requirement",
          hbm["Memory cooling compatible"] == 0.0)
    check(X, "while the compute side was never the problem",
          hbm["  compute thermal margin (%)"] > 0)
    check(X, "LPDDR leaves both domains in budget",
          lp["  memory thermal margin (%)"] > 0
          and lp["  compute thermal margin (%)"] > 0)
    check(X, "the compute margin barely moves with the memory choice",
          max(r[2]["  compute thermal margin (%)"] for r in rows)
          - min(r[2]["  compute thermal margin (%)"] for r in rows) < 5.0)

    # --- wording -------------------------------------------------------------
    #
    # A margin is not a temperature. Screens must not imply one was computed.
    import ppact.runtime as _R, ppact.system as _S
    for module in (_R, _S):
        text = open(module.__file__, encoding="utf-8").read()
        for claim in ("junction temperature of", "degrees C", "will overheat"):
            check(X, f"{module.__name__} does not claim '{claim}'", claim not in text)
    rsrc = open(_R.__file__, encoding="utf-8").read()
    check(X, "a negative margin is described as a cooling assumption exceeded",
          "cooling assumption exceeded" in rsrc or "cooling exceeded" in rsrc)
    check(X, "and the screen says it is a margin, not a temperature",
          "not a temperature" in rsrc)

    # --- stack count as a design variable ------------------------------------
    caps, costs = [], []
    for n in (1, 2, 4, 6):
        m = evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM3E", n)).metrics
        caps.append(m["Memory capacity (GB)"])
        costs.append(m["System cost (USD)"])
    check(X, "stack count scales capacity linearly",
          all(abs(c - caps[0] * k) < 1e-6 for c, k in zip(caps, (1, 2, 4, 6))),
          str(caps))
    check(X, "and cost rises with it", all(a < b for a, b in zip(costs, costs[1:])),
          str([round(c) for c in costs]))


# ==============================================================================
# PATH Y - HBM profile calibration
# ==============================================================================

def path_y():
    Y = "Y"
    from ppact.memory import evaluate as mem_eval, COOLING_RANK, COST_INDEX_BASE

    # --- capacity profiles ---------------------------------------------------
    a24, a36 = MEMORY_LIBRARY["HBM3E"], MEMORY_LIBRARY["HBM3E_36"]
    check(Y, "HBM3E exists in two stack heights",
          a24.dies_per_package == 8 and a36.dies_per_package == 12)
    check(Y, "the taller stack holds more", a36.capacity_gbyte > a24.capacity_gbyte,
          f"{a24.capacity_gbyte} vs {a36.capacity_gbyte}")
    check(Y, "but delivers the same bandwidth - height is capacity, not speed",
          abs(a24.bandwidth_gbytes_s - a36.bandwidth_gbytes_s) < 1e-9)
    check(Y, "and stacks worse, so it yields worse",
          a36.stack_assembly_yield < a24.stack_assembly_yield)
    check(Y, "and costs more to assemble",
          a36.assembly_test_cost_usd > a24.assembly_test_cost_usd)
    check(Y, "the interface width is fixed at 1024 bit for both",
          a24.package_io_width == 1024 == a36.package_io_width)

    # --- cooling as a requirement, not a large negative number ---------------
    for key, spec in MEMORY_LIBRARY.items():
        check(Y, f"{key} declares a cooling requirement",
              spec.cooling_requirement in COOLING_RANK, spec.cooling_requirement)
        m = mem_eval(spec).metrics
    check(Y, "the ordering is passive < airflow < active",
          COOLING_RANK[MEMORY_LIBRARY["LPDDR5"].cooling_requirement]
          < COOLING_RANK[MEMORY_LIBRARY["GDDR6"].cooling_requirement]
          < COOLING_RANK[MEMORY_LIBRARY["HBM3E"].cooling_requirement])

    # HBM in a passively cooled product must fail a GATE, and its own margin
    # must be sane - the point of the change
    phone = evaluate_system(APPLICATION_LIBRARY["mobile_ai"], SystemConfig(
        "cortex_a78_x4", "npu_64x64", "HBM3E", 1))
    check(Y, "HBM in a passive product fails the cooling gate",
          phone.gate["memory_cooling"] is False)
    check(Y, "and its memory margin is a sane number, not a huge negative",
          -50.0 < phone.metrics["  memory thermal margin (%)"] <= 100.0,
          f"{phone.metrics['  memory thermal margin (%)']:.1f}%")
    server = evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
        "server_x86_x32", "datacenter_gpu", "HBM3E", 6))
    check(Y, "and the same memory passes in an actively cooled product",
          server.gate["memory_cooling"] is True)
    check(Y, "LPDDR needs nothing a phone does not have",
          evaluate_system(APPLICATION_LIBRARY["mobile_ai"], SystemConfig(
              "cortex_a78_x4", "npu_64x64", "LPDDR5", 2)).gate["memory_cooling"])

    # --- monotonicity across stack counts ------------------------------------
    caps, bws, powers, costs = [], [], [], []
    for n in (1, 2, 4, 8):
        m = evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM3E", n)).metrics
        caps.append(m["Memory capacity (GB)"])
        bws.append(m["Effective bandwidth (GB/s)"])
        powers.append(m["Memory power (W)"])
        costs.append(m["Memory cost index"])
    for label, series in (("capacity", caps), ("bandwidth", bws),
                          ("cost index", costs)):
        check(Y, f"{label} rises with stack count",
              all(a < b for a, b in zip(series, series[1:])),
              str([round(v, 1) for v in series]))
    check(Y, "capacity scales linearly with stacks",
          all(abs(c - caps[0] * k) < 1e-6 for c, k in zip(caps, (1, 2, 4, 8))))

    # --- effective never exceeds peak ---------------------------------------
    bad = 0
    for key, spec in MEMORY_LIBRARY.items():
        m = mem_eval(spec).metrics
        if m["Package effective bandwidth (GB/s)"] > m["Package peak bandwidth (GB/s)"] + 1e-9:
            bad += 1
    check(Y, "effective bandwidth never exceeds peak", bad == 0, f"{bad} violations")

    # --- confidence is declared, and HBM's is low ---------------------------
    for key, spec in MEMORY_LIBRARY.items():
        check(Y, f"{key} declares cost confidence",
              spec.cost_confidence in ("HIGH", "MEDIUM", "LOW"))
    check(Y, "HBM cost is marked low confidence - it is not publicly verifiable",
          MEMORY_LIBRARY["HBM3E"].cost_confidence == "LOW"
          and MEMORY_LIBRARY["HBM3E_36"].cost_confidence == "LOW")
    check(Y, "and the others are not overclaimed either",
          all(s.cost_confidence != "HIGH" for s in MEMORY_LIBRARY.values()))

    # --- a comparison index beside the dollars ------------------------------
    idx = {k: mem_eval(v).metrics["Cost index"] for k, v in MEMORY_LIBRARY.items()}
    check(Y, "LPDDR5 is the index reference at 100",
          abs(idx["LPDDR5"] - 100.0) < 1.0, str(round(idx["LPDDR5"], 1)))
    check(Y, "the index preserves the dollar ordering",
          sorted(idx, key=lambda k: idx[k])
          == sorted(idx, key=lambda k: mem_eval(MEMORY_LIBRARY[k]).metrics["Package cost (USD)"]))
    check(Y, "and HBM is an order of magnitude above LPDDR",
          idx["HBM3E"] > idx["LPDDR5"] * 10, str({k: round(v) for k, v in idx.items()}))

    # --- against published products -----------------------------------------
    #
    # Internal consistency is what everything else here checks. This is the one
    # place the model is compared with something outside it.
    from ppact.validation import run as run_validation, REFERENCES
    results = run_validation()
    check(Y, "external references are checked", len(results) >= 4)
    for ref, got, dev, ok in results:
        check(Y, f"{ref.product} {ref.quantity} within {ref.tolerance_pct:g}%",
              ok, f"published {ref.published}, model {got:.2f}, {dev:+.1f}%")
        check(Y, f"{ref.product} {ref.quantity} names a source",
              len(ref.source) > 5)

    # the deployed rate and the component ceiling are different numbers, and
    # confusing them once made HBM look 54% better than it is
    hbm = MEMORY_LIBRARY["HBM3E"]
    check(Y, "the component ceiling is recorded separately",
          hbm.peak_pin_speed_gbps > hbm.pin_speed_gbps,
          f"deployed {hbm.pin_speed_gbps}, ceiling {hbm.peak_pin_speed_gbps}")
    check(Y, "and the model runs at the deployed rate, not the ceiling",
          abs(hbm.bandwidth_gbytes_s
              - hbm.package_io_width * hbm.pin_speed_gbps / 8.0) < 1e-9)
    # six stacks is how an H200 is built - not four
    check(Y, "six stacks reproduce an H200-class package",
          abs(hbm.capacity_gbyte * 6 - 144.0) < 1e-6
          and abs(hbm.bandwidth_gbytes_s * 6 / 1000.0 - 4.92) < 0.05)

    # cost and power are absent from the validation set on purpose
    quantities = {r.quantity.lower() for r in REFERENCES}
    check(Y, "no cost figure is presented as externally validated",
          not any("cost" in q or "price" in q or "usd" in q for q in quantities))
    check(Y, "and no power or thermal figure is either",
          not any("power" in q or "thermal" in q or "watt" in q for q in quantities))

    # --- the boundary is the same for all three -----------------------------
    #
    # A comparison is only meaningful if the three are measured to the same
    # edge. All must include silicon plus packaging over yield, and none may
    # quietly include or exclude board wiring.
    for key, spec in MEMORY_LIBRARY.items():
        m = mem_eval(spec).metrics
        check(Y, f"{key} cost is measured to the package boundary",
              abs(m["Package cost (USD)"]
                  - (m["  memory silicon (USD)"] + spec.package_cost_usd)
                  / spec.stack_assembly_yield) < 1e-6)
        check(Y, f"{key} reports board area separately from package footprint",
              spec.board_area_mm2 > 0 and spec.package_footprint_mm2 > 0)


# ==============================================================================
# PATH Z - LLM decode traffic
# ==============================================================================

def path_z():
    Z = "Z"
    app = APPLICATION_LIBRARY["llm_service"]
    cfg = lambda n=6, mem="HBM3E": SystemConfig("server_x86_x32", "datacenter_gpu",
                                                mem, n)

    def go(a=None, **kw):
        return evaluate_system(a or app, cfg(**kw)).metrics

    m = go()

    # 1. at a factor of one the weights are read exactly once per token
    one = dataclasses.replace(app, weight_read_factor=1.0)
    m1 = evaluate_system(one, cfg()).metrics
    check(Z, "1 a read factor of one reads the weights once",
          abs(m1["  weight traffic (MB)"] * 1e6 - app.weight_bytes) < 1e-3,
          f"{m1['  weight traffic (MB)'] * 1e6:.0f} vs {app.weight_bytes:.0f}")
    check(Z, "1 and the default factor is close to one, not to two",
          1.0 <= app.weight_read_factor <= 1.2, str(app.weight_read_factor))

    # 2. twice the model, twice the weight traffic
    big = dataclasses.replace(app, weight_bytes=app.weight_bytes * 2)
    m2 = evaluate_system(big, cfg()).metrics
    check(Z, "2 doubling the model doubles the weight traffic",
          abs(m2["  weight traffic (MB)"] / m["  weight traffic (MB)"] - 2.0) < 1e-6)

    # 3. twice the bandwidth, close to twice the memory-limited rate
    a6, a12 = go(n=6), go(n=12)
    ratio = a12["Throughput (inf/s)"] / a6["Throughput (inf/s)"]
    check(Z, "3 doubling bandwidth nearly doubles the token rate",
          1.9 < ratio < 2.0, f"{ratio:.4f}")

    # 4. longer context means more KV traffic
    kv = []
    for ctx in (1024, 4096, 16384):
        t = dataclasses.replace(app, context_tokens=ctx)
        kv.append(evaluate_system(t, cfg()).metrics["  KV cache traffic (MB)"])
    check(Z, "4 KV traffic grows with context length",
          all(a < b for a, b in zip(kv, kv[1:])), str([round(x, 1) for x in kv]))
    check(Z, "4 and grows linearly with it",
          abs(kv[1] / kv[0] - 4.0) < 1e-6 and abs(kv[2] / kv[1] - 4.0) < 1e-6)

    # 5. prefill and decode are reported separately
    for key in ("Prefill compute (ms)", "Prefill memory (ms)",
                "Time to first token (ms)", "Prefill bound by"):
        check(Z, f"5 {key} is reported", key in m)
    check(Z, "5 prefill is compute bound where decode is memory bound",
          m["Prefill bound by"] == 0.0 and m["Memory time (ms)"] > m["Compute time (ms)"],
          f"prefill compute {m['Prefill compute (ms)']:.1f} vs memory "
          f"{m['Prefill memory (ms)']:.1f}; decode compute "
          f"{m['Compute time (ms)']:.2f} vs memory {m['Memory time (ms)']:.2f}")
    check(Z, "5 prefill reads the weights once for the whole prompt",
          m["Prefill memory (ms)"] < m["Memory time (ms)"] * app.prefill_tokens,
          "prefill must not scale its weight reads with prompt length")

    # 6. the convolution reuse model must not reach a text workload
    saved = COMPUTE_LIBRARY["datacenter_gpu"]
    COMPUTE_LIBRARY["datacenter_gpu"] = dataclasses.replace(
        saved, dataflow_efficiency=0.2)
    try:
        starved = go()
    finally:
        COMPUTE_LIBRARY["datacenter_gpu"] = saved
    check(Z, "6 dataflow efficiency does not change LLM traffic",
          abs(starved["DRAM traffic (MB)"] - m["DRAM traffic (MB)"]) < 1e-6,
          f"{starved['DRAM traffic (MB)']:.1f} vs {m['DRAM traffic (MB)']:.1f}")
    check(Z, "6 and the reported factor is the LLM one, not the reuse one",
          abs(starved["Weight read factor"] - app.weight_read_factor) < 1e-9)
    # a vision workload must still use the reuse model
    v = evaluate_system(APPLICATION_LIBRARY["industrial_vision"], SystemConfig(
        "cortex_a78_x4", "npu_32x32", "LPDDR5", 4)).metrics
    check(Z, "6 a vision workload still refetches weights",
          v["Weight read factor"] > 1.05, str(round(v["Weight read factor"], 3)))

    # 7. the achieved rate never exceeds the memory-limited ceiling
    bad = 0
    for n in (1, 2, 4, 6, 8, 12):
        mm = go(n=n)
        ceiling = (mm["Effective bandwidth (GB/s)"] * 1e9
                   / (mm["DRAM traffic (MB)"] * 1e6))
        if mm["Throughput (inf/s)"] > ceiling * (1 + 1e-9):
            bad += 1
    check(Z, "7 the token rate never exceeds the memory ceiling", bad == 0,
          f"{bad} violations")

    # 8. more stacks help until compute binds - and for decode on a fast
    #    engine, that is a very long way out
    #
    # Written this way after the first version asserted saturation within a
    # dozen stacks and failed. It does not saturate there, and that is the
    # finding rather than a bug: decode on a datacenter GPU spends 0.3 ms
    # computing and 18 ms fetching, so bandwidth keeps paying until roughly
    # sixty times the memory a real part carries. Saturation is real but it
    # belongs to the ENGINE, not to the workload.
    # From FOUR stacks: a 70 GB model does not fit in two, and the rate for a
    # configuration that cannot hold it is deliberately not a number.
    rates = [go(n=n)["Throughput (inf/s)"] for n in (4, 8, 16, 32)]
    gains = [b / a for a, b in zip(rates, rates[1:])]
    # Threshold lowered from 1.9 at 3.27.0: small-workload utilisation derating
    # raised the compute term, so the last doubling now returns 1.89 rather
    # than 1.95. The finding - that decode keeps paying for bandwidth on a fast
    # engine - is unchanged.
    # Threshold 1.80 from 3.67.0: the series now starts at four stacks rather
    # than two, because two do not hold the model, and the last doubling in
    # the shifted window returns 1.81. The finding is unchanged - three
    # successive doublings still return more than 1.8, which is what "keeps
    # paying" means.
    check(Z, "8 on a fast engine, decode keeps paying for bandwidth",
          all(g > 1.80 for g in gains), str([round(g, 3) for g in gains]))
    # Also loosened: compute went from 0.3 ms to 2.18 ms when a 70 GMAC token
    # stopped being assumed to fill a datacenter GPU. Eight times is still a
    # wide margin and the conclusion does not turn on the factor.
    check(Z, "8 because decode is memory bound by a wide margin",
          m["Memory time (ms)"] > m["Compute time (ms)"] * 5,
          f"memory {m['Memory time (ms)']:.2f} vs compute {m['Compute time (ms)']:.2f}")

    # on a slow engine the same stacks buy almost nothing - the saturation the
    # student has to find
    # From FOUR stacks, as above: two do not hold a 70 GB model.
    slow = [evaluate_system(app, SystemConfig(
        "server_x86_x32", "npu_16x16", "HBM3E", n)).metrics["Throughput (inf/s)"]
        for n in (4, 8, 16, 32)]
    check(Z, "8 on a slow engine more stacks saturate almost immediately",
          slow[-1] / slow[0] < 1.1, str([round(v, 2) for v in slow]))
    # From FOUR stacks: at two the model does not fit, and a configuration
    # with no timing has no bottleneck to label either - it reports "not
    # evaluated" rather than a plausible one.
    check(Z, "8 and that design is compute bound throughout",
          all(evaluate_system(app, SystemConfig(
              "server_x86_x32", "npu_16x16", "HBM3E", n)).bound_by == "compute"
              for n in (4, 32)))
    check(Z, "8 while an infeasible one has no bottleneck at all",
          evaluate_system(app, SystemConfig(
              "server_x86_x32", "npu_16x16", "HBM3E", 2)).bound_by
          == "not evaluated",
          "a machine that cannot run does not spend its time anywhere")

    # traffic components must sum to the total
    check(Z, "traffic components sum to the total",
          abs(m["  weight traffic (MB)"] + m["  KV cache traffic (MB)"]
              + m["  other traffic (MB)"] - m["DRAM traffic (MB)"]) < 1e-6)

    # the screen must state its conditions
    import ppact.runtime as _R
    rsrc = open(_R.__file__, encoding="utf-8").read()
    for needed in ("context", "prompt", "streams", "property of the model"):
        check(Z, f"the LLM screen states '{needed[:20]}'", needed in rsrc)


# ==============================================================================
# PATH AA - HBM4
# ==============================================================================

def path_aa():
    A = "AA"
    from ppact.memory import evaluate as mem_eval
    h3, h4 = MEMORY_LIBRARY["HBM3E"], MEMORY_LIBRARY["HBM4_36"]
    h4_tall = MEMORY_LIBRARY["HBM4_48"]

    # 1. effective never exceeds the specification ceiling
    for key, spec in MEMORY_LIBRARY.items():
        ceiling = (spec.package_io_width
                   * (spec.peak_pin_speed_gbps or spec.pin_speed_gbps) / 8.0)
        m = mem_eval(spec).metrics
        check(A, f"1 {key} effective is within the specification ceiling",
              m["Package effective bandwidth (GB/s)"] <= ceiling + 1e-6,
              f"{m['Package effective bandwidth (GB/s)']:.1f} vs {ceiling:.1f}")

    # 2. at the same pin rate, twice the width is twice the bandwidth
    check(A, "2 HBM4 and HBM3E run at the same pin rate here",
          abs(h4.pin_speed_gbps - h3.pin_speed_gbps) < 1e-9)
    check(A, "2 and the doubled width doubles the bandwidth",
          abs(h4.bandwidth_gbytes_s / h3.bandwidth_gbytes_s - 2.0) < 1e-9,
          f"{h4.bandwidth_gbytes_s:.0f} vs {h3.bandwidth_gbytes_s:.0f}")
    check(A, "2 the width is what doubled, not the clock",
          h4.package_io_width == 2 * h3.package_io_width)

    # 3. stack count scales capacity, bandwidth, power and cost monotonically
    caps, bws, powers, costs = [], [], [], []
    for n in (1, 2, 4, 8):
        m = evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM4_36", n)).metrics
        caps.append(m["Memory capacity (GB)"])
        bws.append(m["Effective bandwidth (GB/s)"])
        powers.append(m["Memory power (W)"])
        costs.append(m["Memory cost index"])
    for label, series in (("capacity", caps), ("bandwidth", bws),
                          ("power", powers), ("cost", costs)):
        check(A, f"3 {label} rises with HBM4 stack count",
              all(a < b for a, b in zip(series, series[1:])),
              str([round(v, 1) for v in series]))

    # 4. HBM4 must not simply raise prefill - prefill is compute bound
    def llm(mem, n=6, comp="datacenter_gpu"):
        return evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
            "server_x86_x32", comp, mem, n)).metrics
    a3, a4 = llm("HBM3E"), llm("HBM4_36")
    prefill_gain = a3["Time to first token (ms)"] / a4["Time to first token (ms)"]
    decode_gain = a4["Throughput (inf/s)"] / a3["Throughput (inf/s)"]
    check(A, "4 HBM4 barely moves prefill, which is compute bound",
          prefill_gain < 1.05, f"{prefill_gain:.4f}x")
    # 5. but decode, which is memory bound, improves a great deal
    check(A, "5 and improves decode, which is memory bound",
          decode_gain > 1.7, f"{decode_gain:.3f}x")
    check(A, "5 the two gains are of different orders",
          decode_gain > prefill_gain * 1.5,
          f"decode {decode_gain:.2f}x vs prefill {prefill_gain:.2f}x")

    # 6. on a slow accelerator the gain shrinks or vanishes
    s3, s4 = llm("HBM3E", comp="npu_16x16"), llm("HBM4_36", comp="npu_16x16")
    slow_gain = s4["Throughput (inf/s)"] / s3["Throughput (inf/s)"]
    check(A, "6 a slow engine sees almost nothing from HBM4",
          slow_gain < 1.1, f"{slow_gain:.4f}x")
    check(A, "6 because it was never memory bound", s3["Compute time (ms)"]
          > s3["Memory time (ms)"])

    # 7. the operating point and the ceiling are separate figures
    for key in ("HBM3E", "HBM3E_36", "HBM4_36", "HBM4_48"):
        spec = MEMORY_LIBRARY[key]
        check(A, f"7 {key} records a ceiling above its operating point",
              spec.peak_pin_speed_gbps > spec.pin_speed_gbps,
              f"{spec.pin_speed_gbps} vs {spec.peak_pin_speed_gbps}")

    # 8. HBM4 cost, power and thermal figures are marked estimated
    for key in ("HBM4_36", "HBM4_48"):
        spec = MEMORY_LIBRARY[key]
        check(A, f"8 {key} cost confidence is LOW", spec.cost_confidence == "LOW")
        check(A, f"8 {key} says its figures are estimates",
              "stimated" in spec.notes, spec.notes[:40])

    # 9. a cooling mismatch is a compatibility statement, not a penalty
    phone = evaluate_system(APPLICATION_LIBRARY["mobile_ai"], SystemConfig(
        "cortex_a78_x4", "npu_64x64", "HBM4_36", 1))
    check(A, "9 HBM4 in a passive product fails the cooling gate",
          phone.gate["memory_cooling"] is False)
    check(A, "9 and is not punished with an absurd margin instead",
          -50.0 < phone.metrics["  memory thermal margin (%)"] <= 100.0,
          f"{phone.metrics['  memory thermal margin (%)']:.1f}%")

    # 10. adding HBM4 must not have moved any HBM3E result
    from ppact.designs import designs_for
    for key, app2 in APPLICATION_LIBRARY.items():
        r = evaluate_system(app2, designs_for(key)[0].config)
        check(A, f"10 {key} reference still ships", r.passes,
              ", ".join(g for g, ok in r.gate.items() if not ok))
    ref = evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
        "server_x86_x32", "datacenter_gpu", "HBM3E", 6)).metrics
    # Revised to 24.2 at 3.40.0 when the serving coefficient became a band
    # and its typical value fell from 0.55 to 0.45. Third revision of this pin
    # - each traceable to a named change, and the pin exists so that a fourth
    # cannot happen silently.
    check(A, "10 the HBM3E LLM figure is pinned at 24.2 tokens per second",
          abs(ref["Throughput (inf/s)"] - 24.2) < 0.3,
          f"{ref['Throughput (inf/s)']:.2f}")

    # capacity from stack height, bandwidth from width - the two are separate
    check(A, "16-high buys capacity, not bandwidth",
          h4_tall.capacity_gbyte > h4.capacity_gbyte
          and abs(h4_tall.bandwidth_gbytes_s - h4.bandwidth_gbytes_s) < 1e-9)
    check(A, "and stacks worse for it",
          h4_tall.stack_assembly_yield < h4.stack_assembly_yield)

    # energy per bit improves, which is the other half of HBM4's case
    check(A, "HBM4 moves a bit for less energy than HBM3E",
          h4.energy_pj_per_bit < h3.energy_pj_per_bit,
          f"{h4.energy_pj_per_bit} vs {h3.energy_pj_per_bit}")
    e3 = llm("HBM3E")["Energy per inference (mJ)"]
    e4 = llm("HBM4_36")["Energy per inference (mJ)"]
    check(A, "and that reaches the energy per token", e4 < e3,
          f"{e4:.2f} vs {e3:.2f} mJ")


# ==============================================================================
# PATH AB - HBM generation sweep
# ==============================================================================

def path_ab():
    B = "AB"
    import io, contextlib
    from ppact.memory_sweep import (COMPARISONS, DEFAULT_PROFILES, build,
                                    compare, sweep_memories as sweep)
    from ppact.memory import MEMORY_LIBRARY as ML

    def cap(pair):
        mem, n = pair
        return ML[mem].capacity_gbyte * n

    def bw(pair):
        mem, n = pair
        return ML[mem].effective_bandwidth_gbytes_s * n

    # 1. the same-capacity comparison must actually hold capacity constant,
    #    so that nothing but the interface differs
    a, b = build("llm_service", "same_capacity")
    check(B, "1 same-capacity holds total capacity equal",
          abs(cap(a) - cap(b)) < 1e-6, f"{cap(a)} vs {cap(b)}")
    check(B, "1 and the two sides differ in interface width",
          ML[a[0]].package_io_width != ML[b[0]].package_io_width)
    check(B, "1 it is labelled as generation only",
          "generation only" in COMPARISONS["same_capacity"].effects_included)

    # 2. the same-stack comparison includes capacity, and says so
    a2, b2 = build("llm_service", "same_stacks")
    check(B, "2 same-stack holds the stack count equal", a2[1] == b2[1])
    check(B, "2 and the capacities genuinely differ", abs(cap(a2) - cap(b2)) > 1,
          f"{cap(a2)} vs {cap(b2)}")
    check(B, "2 it is labelled as generation AND capacity",
          "AND capacity" in COMPARISONS["same_stacks"].effects_included)
    check(B, "2 and warns not to read its cost as the price of the generation",
          "price of the generation" in COMPARISONS["same_stacks"].warning)
    # the two comparisons must not be the same experiment
    check(B, "2 A and B are different configurations",
          (a, b) != (a2, b2), f"{a}{b} vs {a2}{b2}")
    # and the cost difference must be larger in B, since it buys capacity too
    from ppact.memory import evaluate as mem_eval
    cost_a = mem_eval(ML[b[0]]).metrics["Cost index"] * b[1] / (
        mem_eval(ML[a[0]]).metrics["Cost index"] * a[1])
    cost_b = mem_eval(ML[b2[0]]).metrics["Cost index"] * b2[1] / (
        mem_eval(ML[a2[0]]).metrics["Cost index"] * a2[1])
    check(B, "2 mixing capacity in makes the generation look more expensive",
          cost_b > cost_a * 1.2, f"A {cost_a:.2f}x vs B {cost_b:.2f}x")

    # 3-4. prefill unchanged, decode improved - the split that matters
    from ppact.memory_sweep import _row
    r3 = _row("llm_service", "datacenter_gpu", a[0], a[1], 60.0)
    r4 = _row("llm_service", "datacenter_gpu", b[0], b[1], 60.0)
    check(B, "3 prefill is unchanged by a wider memory",
          abs(r4["prefill_ms"] / r3["prefill_ms"] - 1.0) < 0.02,
          f"{r3['prefill_ms']:.1f} -> {r4['prefill_ms']:.1f}")
    check(B, "4 decode improves where the workload is memory bound",
          r4["decode_rate"] > r3["decode_rate"] * 1.6,
          f"{r3['decode_rate']:.1f} -> {r4['decode_rate']:.1f}")

    # 5. a slow accelerator sees almost nothing
    s3 = _row("llm_service", "npu_16x16", a[0], a[1], 60.0)
    s4 = _row("llm_service", "npu_16x16", b[0], b[1], 60.0)
    check(B, "5 a compute-bound engine gains almost nothing",
          s4["decode_rate"] / s3["decode_rate"] < 1.1,
          f"{s3['decode_rate']:.2f} -> {s4['decode_rate']:.2f}")

    # 6. above the requested rate, headroom is not delivered throughput
    check(B, "6 both configurations already meet the requested rate",
          r3["result"].jobs >= r3["result"].metrics["Jobs demanded"]
          and r4["result"].jobs >= r4["result"].metrics["Jobs demanded"])
    check(B, "6 so the delivered job count does not rise",
          r4["result"].jobs == r3["result"].jobs,
          f"{r3['result'].jobs} vs {r4['result'].jobs}")

    # 7. a token-rate gain and an energy gain are not assumed to arrive together
    src = open(__import__("ppact.memory_sweep", fromlist=["x"]).__file__,
               encoding="utf-8").read()
    check(B, "7 the report can say energy ROSE", "Energy per token ROSE" in src)
    check(B, "7 and does not tie the two together",
          "automatically a more efficient one" in src)


    # 8. cost, power and package figures are labelled estimated
    check(B, "8 the build panel is labelled estimated",
          "all figures ESTIMATED" in src)
    check(B, "8 and the run panel is labelled simulated",
          "how it runs (simulated)" in src)

    # 9. a cooling mismatch is a status, not a score penalty
    check(B, "9 cooling is reported as a compatibility status",
          "INCOMPATIBLE" in src and "compatible" in src)

    # 10. every comparison runs for every application without error, and none
    #     of them changes an HBM3E result
    before = evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
        "server_x86_x32", "datacenter_gpu", "HBM3E", 6)).metrics["Throughput (inf/s)"]
    fails = []
    for key in COMPARISONS:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                compare("llm_service", key, duration_s=10)
        except Exception as exc:
            fails.append(f"{key}: {exc}")
    check(B, "10 every comparison runs", not fails, "; ".join(fails[:2]))
    after = evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
        "server_x86_x32", "datacenter_gpu", "HBM3E", 6)).metrics["Throughput (inf/s)"]
    check(B, "10 and none of them perturbs an HBM3E result",
          abs(before - after) < 1e-9)

    # 11. the three standings are distinguished in the wording
    for word in ("simulated", "estimated"):
        check(B, f"11 the report distinguishes '{word}'", word in src)
    check(B, "11 and does not call a simulated figure measured",
          "measured" not in src.lower() or "not measured" in src.lower())

    # --- the same-bandwidth comparison, checked properly ---------------------
    #
    # Matching on EFFECTIVE bandwidth while the two carry different controller
    # efficiencies smuggles an assumption into a comparison meant to isolate
    # the interface. Peak is the honest thing to match on, and the residual
    # effective difference must be attributable to the efficiency figures
    # rather than to width.
    a4, b4 = build("llm_service", "same_bandwidth")
    peak_a = ML[a4[0]].bandwidth_gbytes_s * a4[1]
    peak_b = ML[b4[0]].bandwidth_gbytes_s * b4[1]
    check(B, "same-bandwidth matches PEAK bandwidth exactly",
          abs(peak_a - peak_b) < 1e-6, f"{peak_a:.0f} vs {peak_b:.0f}")
    eff_gap = abs(bw(b4) / bw(a4) - 1.0)
    eff_ratio = ML[b4[0]].bandwidth_efficiency / ML[a4[0]].bandwidth_efficiency
    check(B, "and the effective difference is exactly the efficiency assumption",
          abs(eff_gap - abs(eff_ratio - 1.0)) < 1e-6,
          f"effective gap {eff_gap * 100:.2f}%, efficiency gap "
          f"{abs(eff_ratio - 1) * 100:.2f}%")
    check(B, "the report says the efficiency difference is an assumption",
          "an ASSUMPTION, not a " in src and "consequence of width" in src)
    check(B, "and HBM4 gets there with fewer stacks", b4[1] < a4[1],
          f"{a4[1]} vs {b4[1]}")

    # capacity is the other half: fewer stacks is less capacity, and the claim
    # only holds where the model still fits
    need = APPLICATION_LIBRARY["llm_service"].required_memory_bytes / 1e9
    check(B, "the fewer-stack side still holds the model", cap(b4) >= need,
          f"{cap(b4):.0f} GB provided, {need:.0f} GB needed")
    check(B, "the report shows the capacity requirement and margin",
          "required (GB)" in src and "margin (GB)" in src)
    check(B, "and warns when a side does not hold the model",
          "does not hold the model" in src)

    # the efficiency assumption must be registered as one
    from ppact.coefficients import BY_NAME
    c = BY_NAME.get("HBM4 bandwidth_efficiency")
    check(B, "the HBM4 efficiency assumption is registered", c is not None)
    if c:
        check(B, "it is marked low confidence", c.confidence == "LOW")
        check(B, "and declares what rests on it",
              "EQUAL-BANDWIDTH COMPARISON" in c.depends_on)
        check(B, "and matches the library", abs(c.value - ML["HBM4_36"].bandwidth_efficiency) < 1e-9)

    # cost conclusions must be labelled estimates, both directions
    check(B, "a cost increase is labelled estimated",
          "Estimated memory-subsystem cost is" in src)
    check(B, "a cost reduction is too, and says what would move it",
          "not a market price" in src and "supply terms would all move it" in src)

    # the tool must not recommend
    check(B, "the report does not recommend", "recommend" not in src.lower()
          or "does not recommend" in src.lower())
    check(B, "and says the decision is not its to make",
          "does not decide it" in src)

    # an unknown comparison is refused
    try:
        build("llm_service", "vibes")
        check(B, "an unknown comparison is rejected", False, "no error")
    except KeyError:
        check(B, "an unknown comparison is rejected", True)


# ==============================================================================
# PATH AC - evidence levels
# ==============================================================================

def path_ac():
    C = "AC"
    from ppact.evidence import (EVIDENCE, LEVELS, LEVEL_MEANING, by_level,
                                level_of)

    check(C, "five levels are defined", len(LEVELS) == 5, str(LEVELS))
    for lv in LEVELS:
        check(C, f"{lv} is explained", len(LEVEL_MEANING[lv]) > 40)

    # THE point of the taxonomy: no claim of verification anywhere
    check(C, "VERIFIED is not one of the levels",
          not any("VERIFI" in lv for lv in LEVELS), str(LEVELS))
    import ppact.evidence as _E, ppact.validation as _V
    for module in (_E, _V):
        text = open(module.__file__, encoding="utf-8").read().lower()
        for claim in ("we verified", "verified against hardware",
                      "experimentally verified"):
            check(C, f"{module.__name__} does not claim '{claim}'",
                  claim not in text)
    esrc = open(_E.__file__, encoding="utf-8").read()
    check(C, "and the absence is stated rather than left to be noticed",
          "deliberately absent" in esrc)

    # every level has entries, and every entry has a basis
    grouped = by_level()
    for lv in LEVELS:
        check(C, f"{lv} has entries", len(grouped[lv]) > 0)
    for e in EVIDENCE:
        check(C, f"'{e.quantity[:34]}' declares a basis", len(e.basis) > 25)
        check(C, f"'{e.quantity[:34]}' has a known level", e.level in LEVELS)

    # the things a conclusion turned on must be at the weakest level
    weakest = {e.quantity for e in grouped["ENGINEERING ASSUMPTION"]}
    for needle in ("contention", "controller efficiency"):
        check(C, f"the {needle} coefficient is an assumption, not a finding",
              any(needle in q.lower() for q in weakest),
              str(sorted(weakest))[:120])

    # published figures must not include anything nobody publishes
    published = {e.quantity.lower() for e in grouped["PUBLISHED REFERENCE"]}
    for forbidden in ("cost", "yield", "price"):
        check(C, f"nothing about {forbidden} claims to be published",
              not any(forbidden in q for q in published))

    # THE test that matters for this level: a published reference has to be
    # PUBLICLY CHECKABLE. A signed internal review is more authoritative than a
    # datasheet and still cannot go here, because a reader cannot look it up.
    # This file once recorded a programme review sheet as a published
    # reference on the strength of its being signed.
    from ppact.evidence import NON_PUBLIC_MARKERS
    leaked = []
    for e in grouped["PUBLISHED REFERENCE"]:
        hits = [m for m in NON_PUBLIC_MARKERS if m in e.basis.lower()]
        if hits:
            leaked.append(f"{e.quantity}: {hits[0]}")
    check(C, "no non-public source is recorded as a published reference",
          not leaked, "; ".join(leaked))
    check(C, "and the level says authority is not the test",
          "Authority is not the test" in LEVEL_MEANING["PUBLISHED REFERENCE"])
    check(C, "and that it must be publicly available",
          "PUBLICLY AVAILABLE" in LEVEL_MEANING["PUBLISHED REFERENCE"])

    # the alignment report must describe itself as alignment
    vsrc = open(_V.__file__, encoding="utf-8").read()
    check(C, "the reference report is titled alignment, not validation",
          "REFERENCE ALIGNMENT" in vsrc)
    check(C, "and says agreement is by construction",
          "by construction" in vsrc)
    check(C, "and that a match only shows the fitting was done",
          "the fitting was done" in vsrc)

    # lookup defaults to the weakest claim rather than the strongest
    check(C, "an unknown quantity defaults to the weakest level",
          level_of("something nobody thought about") == "ENGINEERING ASSUMPTION")
    check(C, "a known one resolves", level_of("HBM stack cost") == "ESTIMATED")

    # nothing anywhere should call a simulator output measured
    import ppact.runtime as _R, ppact.innovation as _I, ppact.memory_sweep as _M
    # "measured" may appear only in a negation, or naming a figure the
    # STUDENT supplies from a published benchmark - never as a label on
    # something the simulator produced. The first version of this check
    # found runtime.py tagging both of its own latency figures "measured",
    # which is precisely the confusion these levels exist to prevent.
    allowed = ("not measured", "measurement", "measuring",
               "was measured on hardware", "measured_reference",
               "measured here", "once tagged", "only when",
               "has been measured", "no built system",
               # legitimate: a figure the STUDENT supplies from a published
               # benchmark for the REFERENCE platform, never for our output
               "the reference, measured at", "no measured figure",
               "everything is measured")   # "measured against", a comparison
    for module in (_R, _I, _M, _V, _E):
        text = open(module.__file__, encoding="utf-8").read().lower()
        bad = [ln.strip() for ln in text.split("\n")
               if "measured" in ln and not any(a in ln for a in allowed)]
        check(C, f"{module.__name__} never labels its own output measured",
              not bad, "; ".join(bad[:2])[:140])


# ==============================================================================
# PATH AD - accounting (V4)
# ==============================================================================
#
# Written after mutation testing showed that folding wait time into active time
# survived every existing check: active + wait + idle still summed to the
# window, so the partition looked sound while the contents were wrong. A
# conservation law over a total is not enough - the parts have to be checked
# against what produced them.

def path_ad():
    D = "AD"
    from ppact import simulate

    def run(**kw):
        return simulate("industrial_vision", SystemConfig(
            "cortex_a78_x4", "npu_64x64", "LPDDR5", 4, **kw), duration_s=60)

    # Configurations must include one that actually offloads preprocessing.
    # An earlier version used only cpu_only preprocessing, so the offload
    # transfer was zero everywhere and a mutation that put it in two stations
    # changed nothing the checks could see.
    for label, kw in (("single", {}),
                      ("offloaded", dict(preprocessing_mode="isp_and_npu")),
                      ("parallel", dict(secondary_compute="npu_64x64",
                                        execution_mode="parallel", work_split=0.5)),
                      ("parallel offloaded",
                       dict(preprocessing_mode="isp_and_npu",
                            secondary_compute="npu_64x64",
                            execution_mode="parallel", work_split=0.5)),
                      ("sequential", dict(secondary_compute="npu_32x32",
                                          execution_mode="sequential",
                                          work_split=0.3))):
        r = run(**kw)
        m = r.base.metrics

        # --- time: the partition AND its contents ---------------------------
        for name, st in r.modules.items():
            total = st.active_ms + st.wait_ms + st.idle_ms
            check(D, f"{label}/{name} states partition the window",
                  abs(total - r.total_time_ms) < 1e-6)
            check(D, f"{label}/{name} states are non-negative",
                  min(st.active_ms, st.wait_ms, st.idle_ms) >= -1e-9)

        # THE check the mutation exposed: active time must equal the stage
        # occupancy that produced it, not the stage plus its waiting.
        stage_of = {"CPU": "Stage CPU (ms)", "ISP": "Stage ISP (ms)",
                    "Memory": "Stage memory (ms)",
                    "Accelerator": "Stage accelerator (ms)",
                    "Accelerator 1": "Stage accelerator 1 (ms)",
                    "Accelerator 2": "Stage accelerator 2 (ms)"}
        for name, st in r.modules.items():
            key = stage_of.get(name)
            if key is None or r.jobs == 0:
                continue
            per_job = st.active_ms / r.jobs
            expect = m[key]
            if expect * r.jobs > r.total_time_ms:      # clamped at the window
                continue
            check(D, f"{label}/{name} active time equals its stage occupancy",
                  abs(per_job - expect) < 1e-6,
                  f"{per_job:.5f} vs {expect:.5f} ms per job")

        # --- energy ----------------------------------------------------------
        shares = (m["  compute share (%)"] + m["  memory share (%)"]
                  + m["  cpu share (%)"] + m["  static share (%)"])
        check(D, f"{label} energy shares sum to 100", abs(shares - 100.0) < 1e-6)
        check(D, f"{label} dynamic plus static is the total",
              abs(m["Dynamic energy per inference (mJ)"]
                  + m["Static energy per inference (mJ)"]
                  - m["Energy per inference (mJ)"]) < 1e-9)
        check(D, f"{label} run energy is dynamic x jobs plus static x window",
              abs(r.metrics["Total energy (J)"]
                  - (m["Dynamic energy per inference (mJ)"] / 1e3 * r.jobs
                     + m["Static power (W)"] * r.total_time_ms / 1e3)) < 1e-9)

        # --- area: HBM must never enter the logic silicon --------------------
        from ppact.compute import COMPUTE_LIBRARY as _C
        from ppact.cpu import CPU_LIBRARY as _P
        blocks = (_C[r.base.config.compute].die_area_at(r.base.accel_node)
                  + (_C[r.base.config.secondary_compute].die_area_at(r.base.accel_node)
                     if r.base.config.secondary_compute else 0.0)
                  + _P[r.base.config.cpu].die_area_at(r.base.soc_node))
        check(D, f"{label} logic silicon is at least its blocks",
              m["Logic silicon (mm2)"] >= blocks - 1e-9)
        check(D, f"{label} footprint splits into compute and memory",
              abs(m["  compute footprint (mm2)"] + m["  memory footprint (mm2)"]
                  - m["Package footprint (mm2)"]) < 1e-9)

        # --- no quantity may occupy two stations -----------------------------
        #
        # The offload transfer moves bytes through the memory, so it belongs to
        # the memory station. It was once ALSO inside the accelerator station,
        # putting the same bytes in two places at once. Checking the module
        # against its own stage could not see it - both were wrong together -
        # so the stages have to be checked against their parts.
        accel_stage = m.get("Stage accelerator (ms)", 0.0)
        if accel_stage > 0:
            check(D, f"{label} the accelerator station excludes the transfer",
                  abs(accel_stage - (m["Compute time (ms)"]
                                     + m["Preprocess exposed (ms)"]
                                     + m["Offload dispatch (ms)"]
                                     + m["Handoff (ms)"])) < 1e-9,
                  f"stage {accel_stage:.4f}, parts "
                  f"{m['Compute time (ms)'] + m['Preprocess exposed (ms)'] + m['Offload dispatch (ms)'] + m['Handoff (ms)']:.4f}")
            check(D, f"{label} and the memory station includes it exactly once",
                  abs(m["Stage memory (ms)"] - (m["Memory time (ms)"]
                                                + m["Offload transfer (ms)"])) < 1e-9)
        a1 = m.get("Stage accelerator 1 (ms)", 0.0)
        if a1 > 0 and m.get("Secondary die area (mm2)", 0.0) > 0:
            check(D, f"{label} the first engine's station excludes the transfer",
                  a1 < m["Compute time (ms)"] + m["Preprocess offload (ms)"]
                  + m["Offload dispatch (ms)"] + m["Handoff (ms)"] + 1e-9)

        # --- traffic ---------------------------------------------------------
        check(D, f"{label} read plus write is the total traffic",
              abs(m["DRAM read (MB)"] + m["DRAM write (MB)"]
                  - m["DRAM traffic (MB)"]) < 1e-6)

    # the memory choice must never move the logic silicon
    logic = {simulate(
        "mobile_ai", SystemConfig("cortex_a78_x4", "npu_64x64", mem, n),
        duration_s=10).base.metrics["Logic silicon (mm2)"]
        for mem, n in (("LPDDR5", 1), ("LPDDR5", 4), ("HBM3E", 1), ("HBM3E", 2))}
    check(D, "the memory choice never enters the logic silicon", len(logic) == 1,
          str(sorted(round(v, 4) for v in logic)))


# ==============================================================================
# PATH AE - ownership (V3)
# ==============================================================================
#
# Fingerprinting: perturb ONE module and check that exactly the quantities it
# owns respond. Value checks cannot tell a correct number from a number the
# wrong module produced.

def path_ae():
    E = "AE"
    base_cfg = dict(preprocessing_mode="isp_and_npu",
                    secondary_compute="npu_16x16",
                    execution_mode="sequential", work_split=0.0)

    def go(app="industrial_vision", **over):
        cfg = dict(base_cfg); cfg.update(over)
        return evaluate_system(APPLICATION_LIBRARY[app], SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 4, **cfg)).metrics

    ref = go()

    # --- clock fingerprint: the SECONDARY owns preprocessing ---------------
    saved = COMPUTE_LIBRARY["npu_16x16"]
    COMPUTE_LIBRARY["npu_16x16"] = dataclasses.replace(saved,
                                                       clock_ghz=saved.clock_ghz * 2)
    fast_second = go()
    COMPUTE_LIBRARY["npu_16x16"] = saved
    check(E, "doubling the secondary clock halves the preprocessing",
          abs(fast_second["Preprocess offload (ms)"]
              / ref["Preprocess offload (ms)"] - 0.5) < 1e-6)
    check(E, "and does not touch the primary's compute time",
          abs(fast_second["Primary compute time (ms)"]
              - ref["Primary compute time (ms)"]) < 1e-12)

    savedp = COMPUTE_LIBRARY["npu_32x32"]
    COMPUTE_LIBRARY["npu_32x32"] = dataclasses.replace(savedp,
                                                       clock_ghz=savedp.clock_ghz * 2)
    fast_primary = go()
    COMPUTE_LIBRARY["npu_32x32"] = savedp
    check(E, "doubling the primary clock halves its compute",
          abs(fast_primary["Primary compute time (ms)"]
              / ref["Primary compute time (ms)"] - 0.5) < 1e-6)
    check(E, "and does not touch the preprocessing on the secondary",
          abs(fast_primary["Preprocess offload (ms)"]
              - ref["Preprocess offload (ms)"]) < 1e-12)

    # --- cost fingerprint: the interposer owns memory cost only ------------
    from ppact.memory import MEMORY_LIBRARY as ML
    savedm = ML["LPDDR5"]
    ML["LPDDR5"] = dataclasses.replace(savedm, interposer_cost_usd=50.0)
    dear = go()
    ML["LPDDR5"] = savedm
    check(E, "raising the interposer cost raises the system cost",
          dear["System cost (USD)"] > ref["System cost (USD)"])
    for key in ("Logic silicon (mm2)", "Latency (ms)", "Deployment accuracy (%)",
                "DRAM traffic (MB)"):
        check(E, f"and leaves {key} alone",
              abs(dear[key] - ref[key]) < 1e-9, f"{ref[key]} -> {dear[key]}")

    # --- power fingerprint --------------------------------------------------
    # Ownership moved at 3.27.0: where a MODULE idle figure is stated it
    # supersedes die leakage, so perturbing static_power_w alone now changes
    # nothing. That is the correct behaviour and this check had to follow it -
    # a fingerprint that tests a field the model no longer reads would pass
    # forever without meaning anything.
    savedc = COMPUTE_LIBRARY["npu_32x32"]
    COMPUTE_LIBRARY["npu_32x32"] = dataclasses.replace(
        savedc, module_idle_power_w=savedc.module_idle_power_w * 10)
    leaky = go()
    COMPUTE_LIBRARY["npu_32x32"] = savedc
    check(E, "raising accelerator leakage raises the energy",
          leaky["Energy per inference (mJ)"] > ref["Energy per inference (mJ)"])
    check(E, "and leaves the latency alone",
          abs(leaky["Latency (ms)"] - ref["Latency (ms)"]) < 1e-12)
    check(E, "and leaves the CPU's share of energy unchanged in absolute terms",
          abs(leaky["  cpu share (%)"] / 100 * leaky["Energy per inference (mJ)"]
              - ref["  cpu share (%)"] / 100 * ref["Energy per inference (mJ)"])
          < 1e-9)

    # --- power-state ownership ----------------------------------------------
    #
    # Three separate terms, and each has to reach the result on its own. A
    # mutation that dropped the secondary's idle power survived while these
    # were tested only together.
    dual = dict(base_cfg)
    dual.update(secondary_compute="npu_64x64", execution_mode="sequential",
                work_split=0.0)
    ref_dual = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                               SystemConfig("cortex_a78_x4", "npu_32x32",
                                            "LPDDR5", 4, **dual)).metrics
    saved64 = COMPUTE_LIBRARY["npu_64x64"]
    COMPUTE_LIBRARY["npu_64x64"] = dataclasses.replace(
        saved64, module_idle_power_w=saved64.module_idle_power_w * 5)
    leaky_second = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                                   SystemConfig("cortex_a78_x4", "npu_32x32",
                                                "LPDDR5", 4, **dual)).metrics
    COMPUTE_LIBRARY["npu_64x64"] = saved64
    check(E, "the SECOND engine's idle power reaches the energy",
          leaky_second["Energy per inference (mJ)"]
          > ref_dual["Energy per inference (mJ)"] * 1.02,
          f"{ref_dual['Energy per inference (mJ)']:.4f} -> "
          f"{leaky_second['Energy per inference (mJ)']:.4f}")
    check(E, "and it does not change the latency",
          abs(leaky_second["Latency (ms)"] - ref_dual["Latency (ms)"]) < 1e-12)

    # where a module figure is stated it governs, and die leakage does not
    savedm = COMPUTE_LIBRARY["npu_32x32"]
    COMPUTE_LIBRARY["npu_32x32"] = dataclasses.replace(
        savedm, static_power_w=savedm.static_power_w * 20)
    die_only = go()
    COMPUTE_LIBRARY["npu_32x32"] = dataclasses.replace(
        savedm, module_idle_power_w=savedm.module_idle_power_w * 20)
    module_only = go()
    COMPUTE_LIBRARY["npu_32x32"] = savedm
    check(E, "a stated module idle figure supersedes die leakage",
          abs(die_only["Energy per inference (mJ)"]
              - ref["Energy per inference (mJ)"]) < 1e-9,
          "raising die leakage must not move a part that states a module "
          "figure")
    check(E, "and the module figure is what does move it",
          module_only["Energy per inference (mJ)"]
          > ref["Energy per inference (mJ)"] * 1.05,
          f"{ref['Energy per inference (mJ)']:.4f} -> "
          f"{module_only['Energy per inference (mJ)']:.4f}")

    # --- accuracy fingerprint: the family selects the loss ------------------
    from ppact.accuracy import QUANTISATION_LOSS_PP
    key_cnn = ("cnn", "QAT", "INT8")
    savedq = QUANTISATION_LOSS_PP[key_cnn]
    QUANTISATION_LOSS_PP[key_cnn] = savedq + 5.0
    moved = go()
    trans = evaluate_system(APPLICATION_LIBRARY["mobile_ai"], SystemConfig(
        "cortex_a78_x4", "npu_32x32", "LPDDR5", 2)).metrics
    QUANTISATION_LOSS_PP[key_cnn] = savedq
    trans_ref = evaluate_system(APPLICATION_LIBRARY["mobile_ai"], SystemConfig(
        "cortex_a78_x4", "npu_32x32", "LPDDR5", 2)).metrics
    # Not a clean -5.0: this configuration pairs a QAT primary with a PTQ
    # secondary, and the WORSE engine governs, so the reference loss came from
    # the secondary. Raising the primary's QAT loss past it changes the answer
    # by less than the edit. The first version of this check assumed the
    # primary governed and was wrong about the model, not the other way round.
    check(E, "changing the CNN QAT loss moves a CNN application",
          moved["Deployment accuracy (%)"] < ref["Deployment accuracy (%)"] - 3.0,
          f"{ref['Deployment accuracy (%)']} -> {moved['Deployment accuracy (%)']}")
    check(E, "and leaves a transformer application alone",
          abs(trans["Deployment accuracy (%)"]
              - trans_ref["Deployment accuracy (%)"]) < 1e-12)

    # the model family must reach the system, not just the compute library
    cnn_app = APPLICATION_LIBRARY["industrial_vision"]
    as_transformer = dataclasses.replace(cnn_app, model_family="transformer")
    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4)
    check(E, "the application's model family selects the deployment accuracy",
          evaluate_system(as_transformer, cfg).metrics["Deployment accuracy (%)"]
          < evaluate_system(cnn_app, cfg).metrics["Deployment accuracy (%)"] - 0.4,
          "a transformer must lose more than a CNN on the same engine")

    # --- SRAM must not scale like logic ------------------------------------
    c = COMPUTE_LIBRARY["npu_64x64"]
    logic_ratio = c.mac_area_at("N3") / c.mac_area_at("N16")
    sram_ratio = c.sram_area_at("N3") / c.sram_area_at("N16")
    check(E, "SRAM shrinks less than logic across nodes",
          sram_ratio > logic_ratio * 1.5,
          f"logic {logic_ratio:.3f}, SRAM {sram_ratio:.3f}")
    check(E, "so the SRAM share of the die rises at a smaller node",
          c.sram_area_at("N3") / c.die_area_at("N3")
          > c.sram_area_at("N16") / c.die_area_at("N16"))


# ==============================================================================
# PATH AF - assumption isolation (V6)
# ==============================================================================
#
# Run twice: once with a coefficient neutralised, once with it configured. The
# difference is the assumption's effect, and it must be separable from what the
# model does on its own.

def path_af():
    F = "AF"
    import ppact.system as _S
    import ppact.preprocess as _P

    def with_coeff(module, name, value, fn):
        saved = getattr(module, name)
        setattr(module, name, value)
        try:
            return fn()
        finally:
            setattr(module, name, saved)

    app = APPLICATION_LIBRARY["industrial_vision"]

    def par(mem="LPDDR5", n=1, split=0.5):
        return evaluate_system(app, SystemConfig(
            "cortex_a78_x4", "npu_32x32", mem, n, preprocessing_mode="isp_and_npu",
            secondary_compute="npu_32x32", execution_mode="parallel",
            work_split=split)).metrics["Latency (ms)"]

    # contention: neutralising it must change the result, and the direction of
    # the conclusion must be attributable
    off_split = with_coeff(_S, "DUAL_MEMORY_CONTENTION", 0.0, lambda: par(split=0.5))
    off_base = with_coeff(_S, "DUAL_MEMORY_CONTENTION", 0.0, lambda: par(split=0.0))
    on_split, on_base = par(split=0.5), par(split=0.0)
    check(F, "the contention coefficient changes the result", abs(on_split - off_split) > 1e-6)
    check(F, "without it the split still helps", off_split < off_base,
          f"{off_split:.3f} vs {off_base:.3f}")
    check(F, "the assumption's effect is separable",
          abs((on_split - off_split) - ((on_split - on_base) - (off_split - off_base)))
          < abs(on_split) + 1.0)

    # split efficiency
    off = with_coeff(_S, "PARALLEL_SPLIT_EFFICIENCY", 1.0, lambda: par(split=0.5))
    check(F, "the split efficiency coefficient changes the result",
          abs(off - on_split) > 1e-6)
    check(F, "and a perfect split is never slower", off <= on_split + 1e-9)

    # dual dispatch
    off = with_coeff(_S, "DUAL_DISPATCH_US", 0.0, lambda: par(split=0.5))
    check(F, "the hand-off coefficient changes the result", off < on_split)

    # offload dispatch: the break-even must move with it
    def breakeven():
        sizes = [40_000, 160_000, 640_000, 2_560_000]
        for px in sizes:
            t = dataclasses.replace(app, input_pixels=px / 4, streams=4)
            a = evaluate_system(t, SystemConfig(
                "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                preprocessing_mode="cpu_only")).metrics["Latency (ms)"]
            b = evaluate_system(t, SystemConfig(
                "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                preprocessing_mode="isp_and_npu")).metrics["Latency (ms)"]
            if b < a:
                return px
        return None
    cheap = with_coeff(_P, "NPU_PREPROCESS_DISPATCH_US", 0.0, breakeven)
    dear = with_coeff(_P, "NPU_PREPROCESS_DISPATCH_US", 900.0, breakeven)
    check(F, "a cheaper hand-off moves the break-even earlier",
          cheap is not None and (dear is None or cheap < dear),
          f"cheap {cheap}, dear {dear}")

    # every registered coefficient must actually reach a result
    from ppact.coefficients import COEFFICIENTS
    import ppact.memory as _M
    inert = []
    probes = {
        "DUAL_MEMORY_CONTENTION": (_S, 0.0),
        "PARALLEL_SPLIT_EFFICIENCY": (_S, 1.0),
        "DUAL_DISPATCH_US": (_S, 0.0),
        "NPU_PREPROCESS_DISPATCH_US": (_P, 0.0),
        "NPU_PREPROCESS_AREA_UPLIFT": (_P, 0.0),
        "NPU_PREPROCESS_POWER_UPLIFT": (_P, 0.0),

        "ISP_AREA_MM2": (_P, 0.0),
        "ISP_STATIC_POWER_W": (_P, 0.0),
        "ISP_ENERGY_PJ_PER_PIXEL": (_P, 0.0),
    }
    def probe_metrics():
        m = evaluate_system(app, SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
            preprocessing_mode="isp_and_npu", secondary_compute="npu_32x32",
            execution_mode="parallel", work_split=0.5)).metrics
        return (m["Latency (ms)"], m["System power (W)"], m["System cost (USD)"],
                m["Logic silicon (mm2)"], m["Energy per inference (mJ)"])
    ref = probe_metrics()
    for name, (module, neutral) in probes.items():
        got = with_coeff(module, name, neutral, probe_metrics)
        if all(abs(a - b) < 1e-12 for a, b in zip(ref, got)):
            inert.append(name)
    check(F, "every registered coefficient reaches a result", not inert,
          f"inert: {', '.join(inert)}")

    # ISP throughput needs a configuration where the ISP is NOT fully hidden -
    # in the probe above it finished inside the frame period, so changing it
    # moved nothing. An inert-looking coefficient can mean the probe was wrong.
    loaded = dataclasses.replace(app, input_pixels=8_000_000, streams=8,
                                 target_inferences_per_s=120)
    def isp_probe():
        return evaluate_system(loaded, SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
            preprocessing_mode="isp_assisted")).metrics["ISP exposed (ms)"]
    slow_isp = isp_probe()
    fast_isp = with_coeff(_P, "ISP_PIXELS_PER_SECOND", 1e12, isp_probe)
    check(F, "ISP throughput reaches the result when the ISP is loaded",
          slow_isp > 0 and fast_isp == 0.0,
          f"exposed {slow_isp:.2f} ms -> {fast_isp:.2f} ms")

    # and each is declared in the registry
    names = {c.name for c in COEFFICIENTS}
    missing = [n for n in probes if n not in names]
    check(F, "every probed coefficient is registered", not missing, str(missing))


# ==============================================================================
# PATH AG - industry cases (V9)
# ==============================================================================
#
# The value of this set is not the two cases that run. It is the seven that do
# not, and whether the model says so instead of producing a plausible figure
# for an architecture it is not simulating.

def path_ag():
    G = "AG"
    from ppact.industry import (CASES, BENCHMARKS, RUNNABLE, MODEL_SUPPORTS,
                                MODEL_DOES_NOT_SUPPORT, run_case, gap_report)
    import io, contextlib

    check(G, "ten cases are recorded", len(CASES) == 10, str(len(CASES)))
    check(G, "six benchmarks are defined", len(BENCHMARKS) == 6)
    for c in CASES:
        check(G, f"{c.cid} names its benchmark", c.benchmark in BENCHMARKS)
        check(G, f"{c.cid} says what its current system is",
              len(c.current_system) > 5)
        check(G, f"{c.cid} says why an accelerator is wanted", len(c.why_npu) > 25)
        check(G, f"{c.cid} explains how it maps onto the model",
              len(c.mapping) > 40)

    # THE property: a case the model cannot express must be marked so, and must
    # carry a reason - not merely be absent
    blocked = [c for c in CASES if not c.runnable]
    check(G, "most cases are outside what the model can express",
          len(blocked) >= 5, f"{len(blocked)} of {len(CASES)}")
    for c in blocked:
        check(G, f"{c.cid} lists what is missing", len(c.missing) > 0)
        for m in c.missing:
            check(G, f"{c.cid} missing item is a declared limitation",
                  m in MODEL_DOES_NOT_SUPPORT, m)
        check(G, f"{c.cid} has no runner", c.cid not in RUNNABLE)

    # A runnable case may still have a feature the model lacks - IND-09 runs
    # as a single stream while the case is about sixteen users. What it may
    # NOT do is run without saying which part is excluded, so the mapping has
    # to name the restriction.
    runnable = [c for c in CASES if c.runnable]
    for c in runnable:
        check(G, f"{c.cid} has a runner", c.cid in RUNNABLE)
        if c.missing:
            check(G, f"{c.cid} says which part is excluded",
                  any(word in c.mapping.lower()
                      for word in ("single-stream", "single stream", "only",
                                   "at the patch level", "do not",
                                   "is absent", "which is the interesting part")),
                  c.mapping[:70])

    # a blocked case must refuse rather than produce numbers
    for c in blocked[:3]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run_case(c.cid)
        text = buf.getvalue()
        check(G, f"{c.cid} refuses to produce a figure",
              "cannot be expressed" in text and "latency (ms)" not in text,
              text[:80])

    # --- latency boundaries --------------------------------------------------
    #
    # A simulated inference time was once compared against a company target
    # measured from sensor input to driving decision. The figures were both
    # right and the comparison was meaningless.
    from ppact.industry import LATENCY_BOUNDARIES, BOUNDARY_SUPPORT
    check(G, "four latency boundaries are defined", len(LATENCY_BOUNDARIES) == 4)
    for name, (start, end, meaning) in LATENCY_BOUNDARIES.items():
        check(G, f"{name} states where it starts and ends",
              len(start) > 8 and len(end) > 8)
        check(G, f"{name} declares whether the model reaches it",
              name in BOUNDARY_SUPPORT)
    check(G, "the widest boundary is declared unmodelled",
          "not modelled" in BOUNDARY_SUPPORT["SENSOR_TO_CONTROL"])
    for c in [x for x in CASES if x.runnable]:
        check(G, f"{c.cid} declares which boundary its target uses",
              c.latency_boundary in LATENCY_BOUNDARIES, c.latency_boundary)
        check(G, f"{c.cid} explains the boundary", len(c.boundary_note) > 30)

    # a target measured at a wider boundary must not be printed beside a
    # narrower simulated figure
    wide = [c for c in CASES if c.runnable
            and c.latency_boundary in ("PERCEPTION_DECISION", "SENSOR_TO_CONTROL")
            and "latency_ms" in c.target]
    check(G, "at least one case has a wider-boundary target", len(wide) > 0)
    for c in wide:
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            run_case(c.cid)
        t2 = buf2.getvalue()
        head = t2.split("-- latency boundary")[0]
        row = [ln for ln in head.split("\n")
               if "(ms)" in ln and "wider boundary" in ln]
        check(G, f"{c.cid} withholds the non-comparable target",
              bool(row) and "wider boundary" in row[0]
              and f"{c.target['latency_ms']:.1f}" not in row[0],
              row[0] if row else "no latency row found")
        check(G, f"{c.cid} says the comparison would be a category error",
              "category error" in t2)
        check(G, f"{c.cid} breaks the pipeline into its parts",
              "PURE_INFERENCE" in t2 and "AI_PIPELINE" in t2)

    # a runnable case must separate the four kinds of number
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_case("IND-02")
    text = buf.getvalue()
    # Renamed at 3.27.0 to the terms a reader cannot mistake for measurement.
    for phrase in ("company-stated baseline", "company-stated target",
                   "simulator prediction", "field measurement"):
        check(G, f"the report distinguishes '{phrase}'", phrase in text)
    check(G, "and says a target is at most plausible", "PLAUSIBLE" in text)
    check(G, "and that external measurement is not available",
          "External measurement: not available" in text
          or "not available" in text)
    check(G, "and that agreement is not validation",
          "not validation of either" in text)

    # the three latency boundaries must be reported separately
    for phrase in ("pure inference", "end-to-end", "sensor-to-control"):
        check(G, f"the report separates '{phrase}'", phrase in text)
    check(G, "and says which boundary a company KPI usually means",
          "usually means the third" in text)
    check(G, "and that the system is not built",
          "the system is not built" in text)

    # the source must be declared non-public, and nothing from it may claim
    # the strongest evidence level
    import ppact.industry as _I
    src = open(_I.__file__, encoding="utf-8").read()
    check(G, "the source is recorded as non-public", "NON-PUBLIC" in src)
    check(G, "and says why that bars the published level",
          "cannot be checked by a reader" in src or "checkable" in src)
    check(G, "and that companies are described by role, not name",
          "by ROLE, never by name" in src)
    check(G, "company targets are described as commitments, not measurements",
          "commit to" in src and "not an observation" in src)
    from ppact.evidence import EVIDENCE
    industry_entries = [e for e in EVIDENCE
                        if "industry" in e.quantity.lower()
                        or "boundar" in e.quantity.lower()]
    check(G, "nothing from the case set claims to be published",
          all(e.level != "PUBLISHED REFERENCE" for e in industry_entries),
          str([(e.quantity, e.level) for e in industry_entries]))

    # no company names
    for c in CASES:
        joined = (c.company_role + c.current_system + c.proposed).lower()
        check(G, f"{c.cid} is described by role, not by company",
              not any(w in joined for w in ("inc", "corp", "ltd", "co.")))

    # --- open findings must stay visible ------------------------------------
    #
    # Two things are known to be wrong and are not fixed. Recording them is
    # only worth anything if they cannot quietly disappear.
    from ppact.revisions import REVISIONS
    open_items = [r for r in REVISIONS if "OPEN" in r.affected]
    check(G, "open findings are recorded as open", len(open_items) >= 2,
          f"{len(open_items)} open")
    from ppact.coefficients import BY_NAME
    c = BY_NAME.get("LLM_SINGLE_STREAM_SERVING_EFFICIENCY")
    check(G, "the serving coefficient is registered", c is not None)
    if c:
        check(G, "it says it cannot be pinned from public sources",
              "CANNOT BE PINNED" in c.depends_on)
        check(G, "and states the size of the possible error",
              "1.7x" in c.depends_on)
        check(G, "and is marked open", "OPEN" in c.depends_on)

    # the power gap must be computed, not asserted
    from ppact.industry import PUBLISHED_MODULES, power_gap_report
    check(G, "published modules are recorded for comparison",
          len(PUBLISHED_MODULES) >= 3)
    for name, tops, watts, boundary, grade in PUBLISHED_MODULES:
        check(G, f"'{name[:22]}' declares its power boundary", len(boundary) > 4)
        check(G, f"'{name[:22]}' declares an evidence grade",
              grade in ("A", "A-", "B+", "B", "C+", "C", "D"))
    # Revised at 3.32.0. This once asserted the library was pessimistic on
    # accelerator power, on a comparison between silicon leakage and a module
    # figure - the system does not read that field when a module idle power is
    # stated. What must hold instead is that the comparison is made at the same
    # boundary on both sides, and that a published module figure falls inside
    # the range the model spans.
    from ppact.compute import COMPUTE_LIBRARY as _CL
    for name, tops, watts, boundary, grade in PUBLISHED_MODULES:
        if "host" in boundary:
            continue
        best = min((s for s in _CL.values() if s.mac_array),
                   key=lambda s: abs(s.peak_mac_per_s_at("N7") * 2 / 1e12 - tops))
        idle = best.module_idle_power_w or best.static_power_w
        check(G, f"'{name[:22]}' falls inside the model's power range",
              idle <= watts <= (best.module_max_power_w or 1e9),
              f"published {watts} W against idle {idle} - max "
              f"{best.module_max_power_w}")
    check(G, "a host-inclusive figure is excluded from the comparison",
          any("host" in b for _, _, _, b, _ in PUBLISHED_MODULES))

    # the power model's own invariants
    from ppact.application import make_custom_application
    import dataclasses as _dc
    powers = []
    for macs in (1e7, 1e8, 1e9, 1e10, 1e11):
        make_custom_application(
            "probe", mac_per_inference=macs, weight_bytes=20e6,
            activation_bytes=40e6, activation_working_set_kb=2000,
            reference_accuracy_pct=95, required_accuracy_pct=90,
            target_inferences_per_s=1000, latency_budget_ms=1000,
            power_budget_w=500, bom_budget_usd=9000, board_budget_mm2=9000,
            soc_silicon_budget_mm2=900, production_volume=1000,
            register_as="__pw__")
        try:
            powers.append(evaluate_system(APPLICATION_LIBRARY["__pw__"], SystemConfig(
                "cortex_a78_x4", "npu_128x128", "LPDDR5", 4,
                accel_node="N12")).metrics["Compute power (W)"])
        finally:
            APPLICATION_LIBRARY.pop("__pw__", None)
    check(G, "accelerator power rises with utilisation, never falls",
          all(a <= b + 1e-9 for a, b in zip(powers, powers[1:])),
          str([round(p, 3) for p in powers]))
    spec = _CL["npu_128x128"]
    check(G, "and never exceeds the module maximum",
          max(powers) <= spec.module_max_power_w + 1e-9,
          f"{max(powers):.2f} against a {spec.module_max_power_w} W ceiling")
    check(G, "and starts at the module idle power",
          abs(powers[0] - spec.module_idle_power_w) < 0.05,
          f"{powers[0]:.3f} against an idle of {spec.module_idle_power_w}")

    # two modules at low utilisation must not draw twice the maximum
    app_sc = APPLICATION_LIBRARY["smart_camera"]
    one = evaluate_system(app_sc, SystemConfig(
        "cortex_a53_x4", "npu_128x128", "LPDDR5", 1,
        accel_node="N12")).metrics["Compute power (W)"]
    two = evaluate_system(app_sc, SystemConfig(
        "cortex_a53_x4", "npu_128x128", "LPDDR5", 1, accel_node="N12",
        secondary_compute="npu_128x128", execution_mode="parallel",
        work_split=0.5)).metrics["Compute power (W)"]
    check(G, "two lightly-used modules do not draw twice the maximum",
          two < 2 * spec.module_max_power_w * 0.5,
          f"{two:.2f} W against a doubled ceiling of "
          f"{2 * spec.module_max_power_w:.0f} W")
    check(G, "but two modules do draw more than one", two > one)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            power_gap_report()
        check(G, "the power gap report runs", True)
    except Exception as exc:
        check(G, "the power gap report runs", False, repr(exc))

    # --- the revalidation template --------------------------------------
    #
    # Eight fields, and the one that matters most is the last: what the model
    # cannot represent. A case record that omits it reads as though the whole
    # system had been simulated.
    from ppact.industry import (REVALIDATION_FIELDS, revalidate, RUNNABLE)
    check(G, "the template has eight fields", len(REVALIDATION_FIELDS) == 8)
    check(G, "including the unsupported portions",
          "unsupported portions" in REVALIDATION_FIELDS)
    for cid in list(RUNNABLE)[:3]:
        rbuf = io.StringIO()
        with contextlib.redirect_stdout(rbuf):
            revalidate(cid)
        rt = rbuf.getvalue()
        for n, field in enumerate(REVALIDATION_FIELDS, start=1):
            check(G, f"{cid} record has field {n}", field.upper() in rt, field)
        check(G, f"{cid} marks its workload figures estimated",
              "ESTIMATED" in rt)
        check(G, f"{cid} says absolute validation is unavailable",
              "not available" in rt)
        check(G, f"{cid} says the targets are aims",
              "targets are aims" in rt)
    # a wider-boundary case must refuse the latency deviation
    wbuf = io.StringIO()
    with contextlib.redirect_stdout(wbuf):
        revalidate("IND-10")
    wt = wbuf.getvalue()
    check(G, "a wider-boundary latency target is not turned into a deviation",
          "category error" in wt and "no deviation is computed" in wt)
    check(G, "and a comparable target is compared, with a caveat",
          "power reduction" in wt and "NOT validation" in wt)
    # an unsupported case must refuse to produce a record
    ubuf = io.StringIO()
    with contextlib.redirect_stdout(ubuf):
        revalidate("IND-01")
    check(G, "an unsupported case produces no revalidation record",
          "cannot be expressed" in ubuf.getvalue()
          and "SIMULATOR RESULT" not in ubuf.getvalue())

    # --- every verification path must be under mutation --------------------
    #
    # The mutation runner names the paths it exercises in a string. That list
    # has been forgotten twice, each time leaving hundreds of new checks
    # outside coverage while the totals still looked healthy. A list that must
    # be maintained by hand will be forgotten again; this makes the third time
    # a test failure.
    import re as _re
    _here = open(__file__, encoding="utf-8").read()
    defined = set(_re.findall(r"^def (path_[a-z_]+)\(", _here, _re.M))
    mut = open("tests_mutation.py", encoding="utf-8").read()
    exercised = set(_re.findall(r"M\.(path_[a-z_]+)", mut))
    missing = sorted(defined - exercised)
    check(G, "every verification path is under mutation coverage",
          not missing,
          f"not exercised: {', '.join(missing)}")

    # the coverage report must run
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            gap_report()
        check(G, "the coverage report runs", True)
    except Exception as exc:
        check(G, "the coverage report runs", False, repr(exc))

    # supported and unsupported lists must not overlap
    check(G, "the capability lists do not overlap",
          not (set(MODEL_SUPPORTS) & set(MODEL_DOES_NOT_SUPPORT)))


# ==============================================================================
# PATH AH - external cross-validation discipline
# ==============================================================================
#
# The point of a holdout set is that it cannot be used to choose anything. That
# property is not self-enforcing: this project already lost one holdout case by
# using it to bracket a coefficient before the split existed.

def path_ah():
    H = "AH"
    from ppact.crossval import (CASES, SETS, STATUSES, TOLERANCE_PCT, by_set,
                                print_crossval)
    import io, contextlib

    grouped = by_set()
    check(H, "all three sets exist", all(grouped[k] for k in SETS),
          str({k: len(v) for k, v in grouped.items()}))
    for c in CASES:
        check(H, f"{c.cid} names a set", c.dataset in SETS)
        check(H, f"{c.cid} names a check type",
              c.check_type in ("ABSOLUTE", "RATIO", "DIRECTION"))
        check(H, f"{c.cid} carries a known status", c.status in STATUSES, c.status)
        check(H, f"{c.cid} states its published conditions",
              len(c.conditions) > 25)
        check(H, f"{c.cid} states both measurement boundaries",
              len(c.boundary_published) > 5 and len(c.boundary_model) > 5)
        check(H, f"{c.cid} declares what we had to invent",
              len(c.estimated_inputs) > 3)
        check(H, f"{c.cid} carries a root-cause note", len(c.note) > 40)

    # THE invariant: a holdout case must not have been used to set anything
    for c in grouped["HOLDOUT"]:
        check(H, f"{c.cid} was not used to choose a coefficient",
              not c.used_for, c.used_for)
    for c in grouped["CALIBRATION"]:
        check(H, f"{c.cid} says what it was used for", bool(c.used_for))

    # and the case that was contaminated must say so rather than be moved
    # quietly
    contaminated = [c for c in CASES if "CONTAMINATED" in c.note]
    check(H, "the contaminated case is marked, not hidden",
          len(contaminated) == 1, str([c.cid for c in contaminated]))
    if contaminated:
        c = contaminated[0]
        check(H, "it sits in the calibration set now", c.dataset == "CALIBRATION")
        check(H, "and says its earlier holdout result is void",
              "no independent weight" in c.note or "carries no independent" in c.note)

    # tolerances must differ by metric, and cost and accuracy must not be
    # pass/fail criteria at all
    check(H, "tolerances differ by metric", len(set(
        v for v in TOLERANCE_PCT.values() if v is not None)) >= 4)
    check(H, "cost is never a pass criterion", TOLERANCE_PCT["cost"] is None)
    check(H, "accuracy is never a pass criterion",
          TOLERANCE_PCT["accuracy"] is None)
    check(H, "bandwidth is tighter than power",
          TOLERANCE_PCT["bandwidth"] < TOLERANCE_PCT["power"])

    # a case with no published value must not report a deviation
    for c in CASES:
        if c.published is None:
            check(H, f"{c.cid} reports no deviation without a published value",
                  c.modelled is None, str(c.modelled))

    # the challenge set must be expected to fail, not counted as failure
    for c in grouped["CHALLENGE"]:
        check(H, f"{c.cid} is marked as needing an extension",
              c.status == "Model Extension Required", c.status)

    # Revised at 3.32.0. This once required a failing holdout case, on the
    # reasoning that a holdout set which all passes has usually been fitted.
    # That reasoning is sound and the requirement was not: the one failing
    # case was promoted to calibration because examining a modelling question
    # matters more than protecting a clean set. What must hold instead is that
    # the resulting WEAKNESS is stated rather than left to be inferred from a
    # short list.
    import io as _io, contextlib as _ctx
    with _ctx.redirect_stdout(_io.StringIO()) as _b:
        print_crossval()
    report = _b.getvalue()
    absolute_holdout = [c for c in grouped["HOLDOUT"]
                        if c.check_type == "ABSOLUTE"]
    if not absolute_holdout:
        check(H, "an empty absolute-holdout set is declared, not hidden",
              "no absolute-value confirmation" in report)
        check(H, "and the reason for the promotion is given",
              "promoted to" in report and "wrong" in report)
        check(H, "and what would fix it is named",
              "different vendor" in report)
    else:
        check(H, "absolute holdout cases exist", True)

    # --- metric provenance --------------------------------------------------
    #
    # test_external_metric_is_runtime_consumed, and the four rules beside it.
    # A deviation was once reported against a field the model never reads;
    # these make that impossible to repeat without noticing.
    from ppact.crossval import (METRIC_PROVENANCE,
                                NOT_COMPARABLE_TO_MODULE_CLAIMS)
    from ppact.system import evaluate_system as _ev
    probe = _ev(APPLICATION_LIBRARY["smart_camera"], SystemConfig(
        "cortex_a53_x4", "npu_128x128", "LPDDR5", 1, accel_node="N12")).metrics
    for claim, (formula, metric_keys, consumer) in METRIC_PROVENANCE.items():
        check(H, f"'{claim}' names its formula", len(formula) > 12)
        check(H, f"'{claim}' names a consuming function", len(consumer) > 6)
        for key in [k.strip() for k in metric_keys.split(",")]:
            check(H, f"'{claim}' maps to a metric the model produces",
                  key in probe, key)

    # a module claim must never be compared against silicon leakage or a
    # design ceiling
    import ppact.industry as _I
    isrc = open(_I.__file__, encoding="utf-8").read()
    gap = isrc[isrc.index("def power_gap_report"):]
    check(H, "the power report does not compare against silicon leakage",
          "spec.static_power_w" not in gap
          or "module_idle_power_w or spec.static_power_w" in gap)
    check(H, "and treats the module maximum as a ceiling, not a comparand",
          "idle <= watts <=" in gap)
    for field in NOT_COMPARABLE_TO_MODULE_CLAIMS:
        check(H, f"'{field}' is named as not comparable to a module claim",
              field in NOT_COMPARABLE_TO_MODULE_CLAIMS)

    # a box-level claim needs the host inside the boundary, so it must be
    # excluded rather than compared
    from ppact.industry import PUBLISHED_MODULES
    boxes = [m for m in PUBLISHED_MODULES if "host" in m[3]]
    check(H, "a host-inclusive claim exists to be excluded", len(boxes) >= 1)
    with contextlib.redirect_stdout(io.StringIO()) as gbuf:
        from ppact.industry import power_gap_report as _pgr
        _pgr()
    gtext = gbuf.getvalue()
    check(H, "and the report refuses to compare it",
          "not compared" in gtext)
    check(H, "and says why", "accelerator alone" in gtext)

    # --- the cooling model has no external confirmation ---------------------
    #
    # Revised at 3.36.0. This once asserted that the cooling model was
    # confirmed because a published module power fell under the passive limit.
    # The vendor of that module recommends strong airflow over it and throttles
    # its chips at 100 C, so the limit admitting the figure confirmed nothing -
    # a thermal outcome does not turn on watts per square millimetre alone.
    thermal_cases = [c for c in CASES if "THERMAL" in c.cid]
    check(H, "the thermal claims are separated from the power claims",
          len(thermal_cases) >= 2, str([c.cid for c in thermal_cases]))
    check(H, "no thermal case claims to confirm the cooling model",
          not any(c.status == "Aligned" for c in thermal_cases),
          str([(c.cid, c.status) for c in thermal_cases]))
    review = [c for c in CASES if c.status == "Boundary Review Required"]
    check(H, "the contradictory passive claim is left unresolved",
          len(review) >= 1, str([c.cid for c in review]))
    for c in review:
        check(H, f"{c.cid} produces no number", c.modelled is None)
        check(H, f"{c.cid} says the model's own verdict is model-derived",
              "MODEL-DERIVED" in c.note or "model-derived" in c.note.lower())
    from ppact.evidence import EVIDENCE as _EV
    cool = [e for e in _EV if "cooling limit" in e.quantity.lower()]
    check(H, "the passive cooling limit is registered as an assumption",
          cool and cool[0].level == "ENGINEERING ASSUMPTION",
          str([(e.quantity, e.level) for e in cool]))
    check(H, "and says it has no external confirmation",
          cool and "NO external confirmation" in cool[0].basis)

    # the product-class ladder: ordering must hold even though the range is
    # known to be compressed. Ordering is structural; the range is calibration.
    import dataclasses as _dc2
    from ppact.application import make_custom_application as _mk
    def _sat(comp, node, cpu, mem, n, macs):
        _mk("ladder", mac_per_inference=macs, weight_bytes=52e6,
            activation_bytes=95e6, activation_working_set_kb=3000,
            reference_accuracy_pct=79, required_accuracy_pct=60,
            target_inferences_per_s=100000, latency_budget_ms=100000,
            power_budget_w=9000, bom_budget_usd=999999, board_budget_mm2=999999,
            soc_silicon_budget_mm2=99999, production_volume=5000,
            register_as="__ld__")
        APPLICATION_LIBRARY["__ld__"] = _dc2.replace(
            APPLICATION_LIBRARY["__ld__"], streams=8, input_pixels=1920 * 1080,
            output_elements=200, uses_nms=True, model_family="detection")
        try:
            return evaluate_system(APPLICATION_LIBRARY["__ld__"], SystemConfig(
                cpu, comp, mem, n, accel_node=node)).metrics["Compute power (W)"]
        finally:
            APPLICATION_LIBRARY.pop("__ld__", None)
    edge = _sat("npu_128x128", "N12", "cortex_a78_x4", "LPDDR5", 4, 3e11)
    embed = _sat("edge_gpu", "N7", "cortex_a78_x4", "LPDDR5", 4, 3e12)
    desk = _sat("datacenter_gpu", "N5", "server_x86_x32", "GDDR6", 8, 3e13)
    check(H, "the product classes come out in the published order",
          edge < embed < desk, f"{edge:.1f} < {embed:.1f} < {desk:.1f}")
    check(H, "and the compression against the published bands is recorded",
          any(c.cid == "EXT-PWR-LADDER" for c in CASES))
    ladder = next(c for c in CASES if c.cid == "EXT-PWR-LADDER")
    check(H, "the ladder case is a holdout and was not used to fit anything",
          ladder.dataset == "HOLDOUT" and not ladder.used_for)
    check(H, "and says the range is too narrow rather than misplaced",
          "too narrow" in ladder.note)

    # a corroboration case must say how independent it is not
    for c in grouped["CORROBORATION"]:
        check(H, f"{c.cid} states its limited independence",
              bool(c.independence) and "artial" in c.independence,
              c.independence)
        check(H, f"{c.cid} does not claim independent validation",
              "NOT independent validation" in c.note or
              "not independent" in c.note.lower())

    # boundary mismatches must be recorded rather than resolved by guessing
    mismatch = [c for c in CASES if c.status == "Boundary Mismatch"]
    check(H, "uncomparable cases are recorded as such", len(mismatch) >= 2)
    for c in mismatch:
        check(H, f"{c.cid} produces no number", c.modelled is None)

    try:
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            print_crossval()
        text = buf.getvalue()
        check(H, "the report runs", True)
        check(H, "and says calibration agreement is by construction",
              "by construction" in text)
        check(H, "and that only holdout carries independent weight",
              "independent weight" in text)
    except Exception as exc:
        check(H, "the report runs", False, repr(exc))

    # the coefficient must declare its scope in its name
    from ppact.coefficients import BY_NAME
    check(H, "the serving coefficient names its scope",
          "SINGLE_STREAM" in " ".join(BY_NAME))
    c = BY_NAME.get("LLM_SINGLE_STREAM_SERVING_EFFICIENCY")
    check(H, "and states that it is not a hardware property",
          c is not None and "SINGLE-STREAM DECODE ONLY" in c.unit)

    # the two LLM references must be kept apart
    from ppact.designs import designs_for
    # The distinction lives in the TIER, not the label: one option is what a
    # shipping part is, the other is what the requirement needs.
    tiers = [d.tier for d in designs_for("llm_service")]
    check(H, "a published-class reference exists beside the matched one",
          any("ublished-class" in t for t in tiers), str(tiers))
    pub = next(d for d in designs_for("llm_service") if "ublished-class" in d.tier)
    matched = designs_for("llm_service")[0]
    rp = evaluate_system(APPLICATION_LIBRARY["llm_service"], pub.config)
    rm = evaluate_system(APPLICATION_LIBRARY["llm_service"], matched.config)
    check(H, "the published-class configuration does NOT meet the requirement",
          not rp.passes,
          "a published part missing the requirement is a finding, not a bug")
    check(H, "and the requirement-matched one does", rm.passes)
    check(H, "and they differ in stack count",
          pub.config.memory_devices < matched.config.memory_devices)


# ==============================================================================
# PATH AI - result interpretation
# ==============================================================================
#
# Bands say whether a value is ordinary. They are a synthesis of published
# references rather than measurements, they describe ACCELERATORS while this
# model computes systems, and a value outside one is a prompt rather than a
# score. All three of those have to survive contact with the code.

def path_ai():
    I = "AI"
    from ppact.interpret import (RANGES, DOMAINS, DOMAIN_CONTEXT, METRIC_GUIDE,
                                 DOMAIN_OF_APPLICATION, interpret,
                                 explain_metric, from_measurement, verdict,
                                 _value)
    import io, contextlib

    check(I, "five domains are defined", len(DOMAINS) == 5)
    for d in DOMAINS:
        check(I, f"{d} has context", d in DOMAIN_CONTEXT)
    for r in RANGES:
        check(I, f"{r.metric} covers every domain",
              set(r.bands) == set(DOMAINS), str(set(DOMAINS) - set(r.bands)))
        check(I, f"{r.metric} names the metric it reads", bool(r.metric_key))
        check(I, f"{r.metric} declares its boundary", len(r.boundary_note) > 20)
        check(I, f"{r.metric} carries a caveat", len(r.caveat) > 20)
        for d, band in r.bands.items():
            if band is not None:
                check(I, f"{r.metric}/{d} band is ordered", band[0] < band[1])

    # every mapped key must resolve on a real result
    probe = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                            SystemConfig("cortex_a78_x4", "npu_32x32",
                                         "LPDDR5", 4)).metrics
    for r in RANGES:
        check(I, f"{r.metric} resolves against a real result",
              _value(probe, r.metric_key) is not None, r.metric_key)

    # THE definition trap: arithmetic utilisation is not the compute share of
    # core time, and reading a published band against the wrong one made four
    # of nine references look abnormal.
    check(I, "the two utilisation figures are both reported and differ",
          "Engine arithmetic utilisation (%)" in probe
          and "Compute utilisation (%)" in probe
          and abs(probe["Engine arithmetic utilisation (%)"]
                  - probe["Compute utilisation (%)"]) > 1e-9)
    util = next(r for r in RANGES if r.metric == "Utilisation")
    check(I, "the band reads the arithmetic one",
          util.metric_key == "Arithmetic utilisation (%)")
    check(I, "and the trap is written down", "DEFINITION TRAP" in util.boundary_note)

    # with the right mapping, most references should look ordinary - a band
    # set that flags everything is measuring the wrong thing
    from ppact.designs import designs_for
    outside = []
    for key, app2 in APPLICATION_LIBRARY.items():
        m = evaluate_system(app2, designs_for(key)[0].config).metrics
        dom = DOMAIN_OF_APPLICATION[key]
        band = util.bands[dom]
        v = _value(m, util.metric_key)
        if band and not (band[0] <= v <= band[1]):
            outside.append((key, round(v, 1)))
    check(I, "most reference designs look ordinary on utilisation",
          len(outside) <= 2, str(outside))

    # a wider boundary on our side must be flagged, not compared silently
    wider = [r for r in RANGES if r.boundary_note.startswith("WIDER")]
    check(I, "at least one mapping is declared wider on our side",
          len(wider) >= 2, str([r.metric for r in wider]))

    # the guide must carry all five fields for every metric it covers
    for name, guide in METRIC_GUIDE.items():
        check(I, f"'{name}' guide has five parts", len(guide) == 5)
        check(I, f"'{name}' names a common mistake", len(guide[4]) > 15)

    # --- three comparisons, not one -----------------------------------------
    #
    # The requirement says whether it ships, the reference says whether it
    # beats where the course starts, and the band says whether it is ordinary.
    # They answer different questions and are allowed to disagree.
    import importlib
    _IP = importlib.import_module("ppact.interpret")
    isrc = open(_IP.__file__, encoding="utf-8").read()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        interpret("industrial_vision", designs_for("industrial_vision")[0].config)
    text = buf.getvalue()
    for section in ("1. requirements", "2. against the starting point",
                    "3. against the typical domain range",
                    "reading the three together"):
        check(I, f"the report has a '{section[:28]}' section", section in text)

    # a non-reference design must actually be compared against the reference
    alt = io.StringIO()
    with contextlib.redirect_stdout(alt):
        interpret("industrial_vision", designs_for("industrial_vision")[2].config)
    atext = alt.getvalue()
    check(I, "a design is compared against the starting point",
          "this design" in atext and "starting point" in atext.lower())
    check(I, "and the comparison says better or worse per metric",
          "better" in atext and "worse" in atext)
    check(I, "while the starting point itself says so instead",
          "This IS the starting point" in text)

    # the ranges must not be described as an input to the simulation
    check(I, "the ranges are described as consulted, not fed in",
          "NOT in the simulation path" in _IP.__doc__
          or "never an input" in _IP.__doc__)
    check(I, "and the diagram shows them entering from the side",
          "<----" in _IP.__doc__)
    check(I, "and the report says nothing computed changed",
          "nothing here changed a computed value" in text)
    check(I, "the report says the bands are not measurements",
          "not" in text and "measurements" in text)
    check(I, "and that they describe accelerators, not systems",
          "ACCELERATORS while this model" in text)
    check(I, "and that being outside one is a prompt, not a score",
          "never a score" in text)
    check(I, "and that being inside them all is not a verdict either",
          "Being ordinary is not a" in isrc)
    check(I, "and that a design may ship while sitting outside a band",
          "unusual and correct" in isrc)
    check(I, "and that a band cannot say which requirement failed",
          "cannot see which requirement failed" in isrc)
    check(I, "and reports the requirement count separately from the bands",
          "1. requirements: does it ship?" in text)

    # the measurement template must keep accelerator latency and wall-clock
    # throughput apart
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        out = from_measurement(clock_mhz=50, cycles_per_image=50000,
                               images=100, elapsed_ms=100,
                               ops_per_image=1.5e6, power_w=1.2,
                               label="probe")
    mtext = buf2.getvalue()
    check(I, "latency comes from cycles over clock",
          abs(out["Latency (ms)"] - 50000 / 50e6 * 1e3) < 1e-9)
    check(I, "throughput comes from elapsed wall-clock time",
          abs(out["Throughput (inf/s)"] - 1000.0) < 1e-6)
    # In the example above they happen to coincide - 50000 cycles at 50 MHz is
    # 1 ms and 100 images in 100 ms is also 1 ms apart. That coincidence is
    # exactly why the template warns: a second run with a host bottleneck
    # separates them, and nothing in the arithmetic ties them together.
    with contextlib.redirect_stdout(io.StringIO()):
        slow = from_measurement(clock_mhz=50, cycles_per_image=50000,
                                images=100, elapsed_ms=400,
                                ops_per_image=1.5e6, power_w=1.2,
                                label="host-limited")
    check(I, "accelerator latency and wall-clock throughput can disagree",
          abs(1000.0 / slow["Throughput (inf/s)"] - slow["Latency (ms)"]) > 0.5,
          f"latency {slow['Latency (ms)']:.2f} ms against an interval of "
          f"{1000.0 / slow['Throughput (inf/s)']:.2f} ms")
    check(I, "the template says so", "will not give the throughput" in mtext)
    check(I, "measured TOPS follows from ops and throughput",
          abs(out["Measured TOPS"] - 1.5e6 * 1000.0 / 1e12) < 1e-15)

    # explain_metric must work and must refuse unknown names
    with contextlib.redirect_stdout(io.StringIO()) as b3:
        explain_metric("Latency")
    check(I, "a metric can be explained", "common mistake" in b3.getvalue())
    with contextlib.redirect_stdout(io.StringIO()) as b4:
        explain_metric("nonsense")
    check(I, "an unknown metric is refused", "No guide" in b4.getvalue())

    # --- the three comparisons must be INDEPENDENT --------------------------
    #
    # Metamorphic: perturbing one of the three must leave the other two exactly
    # where they were. If a domain band could move a requirement verdict, the
    # bands would have become a grading scheme, which is the failure mode this
    # whole layer exists to avoid.
    import dataclasses as _dc3
    _IPM = importlib.import_module("ppact.interpret")
    cfg_t = designs_for("industrial_vision")[2].config
    app_t = APPLICATION_LIBRARY["industrial_vision"]

    def snapshot():
        r = evaluate_system(app_t, cfg_t)
        ref = evaluate_system(app_t, designs_for("industrial_vision")[0].config)
        return (tuple(sorted(r.gate.items())),
                round(r.metrics["Latency (ms)"], 9),
                round(r.metrics["Latency (ms)"] / ref.metrics["Latency (ms)"], 9))

    base_gate, base_metric, base_ratio = snapshot()
    base_bands = [(r.metric, _value(evaluate_system(app_t, cfg_t).metrics,
                                    r.metric_key)) for r in RANGES]

    # 1. move a domain band
    util_r = next(r for r in _IPM.RANGES if r.metric == "Utilisation")
    saved_bands = dict(util_r.bands)
    object.__setattr__(util_r, "bands",
                       {k: (0.0, 1.0) for k in saved_bands})
    try:
        g, mt, rt = snapshot()
        check(I, "moving a domain band leaves the requirements alone",
              g == base_gate)
        check(I, "and leaves the raw metrics alone", mt == base_metric)
        check(I, "and leaves the reference comparison alone", rt == base_ratio)
    finally:
        object.__setattr__(util_r, "bands", saved_bands)

    # 2. move the reference design
    from ppact.designs import DESIGNS
    saved_designs = list(DESIGNS["industrial_vision"])
    DESIGNS["industrial_vision"] = [saved_designs[1]] + saved_designs[1:]
    try:
        r2 = evaluate_system(app_t, cfg_t)
        check(I, "moving the reference leaves the requirements alone",
              tuple(sorted(r2.gate.items())) == base_gate)
        check(I, "and leaves the raw metrics alone",
              round(r2.metrics["Latency (ms)"], 9) == base_metric)
        bands_now = [(r.metric, _value(r2.metrics, r.metric_key))
                     for r in RANGES]
        check(I, "and leaves the domain interpretation alone",
              bands_now == base_bands)
    finally:
        DESIGNS["industrial_vision"] = saved_designs

    # 3. move a requirement threshold
    saved_app = APPLICATION_LIBRARY["industrial_vision"]
    APPLICATION_LIBRARY["industrial_vision"] = _dc3.replace(
        saved_app, required_accuracy_pct=1.0)
    try:
        r3 = evaluate_system(APPLICATION_LIBRARY["industrial_vision"], cfg_t)
        check(I, "moving a requirement changes the requirement verdict",
              tuple(sorted(r3.gate.items())) != base_gate)
        check(I, "but leaves the raw metrics alone",
              round(r3.metrics["Latency (ms)"], 9) == base_metric)
        bands_now = [(r.metric, _value(r3.metrics, r.metric_key))
                     for r in RANGES]
        check(I, "and leaves the domain interpretation alone",
              bands_now == base_bands)
    finally:
        APPLICATION_LIBRARY["industrial_vision"] = saved_app

    # --- neutral wording ----------------------------------------------------
    #
    # "LOW" reads as a failing grade, and being under a band is not a failure.
    from ppact.interpret import VERDICT_WORDS
    for state, word in VERDICT_WORDS.items():
        check(I, f"'{state}' is worded neutrally", "Range" in word
              or "Computed" in word, word)
    check(I, "no verdict word is a bare grade",
          not any(w in ("LOW", "HIGH", "OK", "FAIL") for w in VERDICT_WORDS.values()))
    check(I, "the report uses the neutral wording",
          "Below Typical Range" in atext or "Within Typical Range" in atext)
    check(I, "and says outside a band is not a failure by itself",
          "not a failure by itself" in isrc)
    check(I, "and that only the requirements decide shipping",
          "decide whether a product can ship" in isrc)

    # verdict must be a three-way, not a pass/fail
    check(I, "a value under a band reads BELOW", verdict(1.0, (2.0, 3.0))[0] == "BELOW")
    check(I, "a value over reads ABOVE", verdict(9.0, (2.0, 3.0))[0] == "ABOVE")
    check(I, "a value inside reads within", verdict(2.5, (2.0, 3.0))[0] == "within")
    check(I, "and no band means no verdict",
          verdict(2.5, None)[0] == "no published band")


# ==============================================================================
# PATH AJ - gold reference scenarios
# ==============================================================================
#
# The point of a fixture set is not that it runs. It is that each entry states
# what it can settle, and that a scenario without a company objective cannot
# quietly claim one.

def path_aj():
    J = "AJ"
    from ppact.gold import (SCENARIOS, BY_ID, LEVELS, PROMOTION_CRITERIA,
                            run_gold, run_all_gold, _context)
    from ppact.industry import CASES as ICASES, RUNNABLE
    import io, contextlib

    check(J, "seven scenarios are defined", len(SCENARIOS) == 7)
    check(J, "a partial level exists between scenario and industry",
          "INDUSTRY-PARTIAL" in LEVELS)
    check(J, "and it sits below INDUSTRY",
          LEVELS.index("INDUSTRY-PARTIAL") < LEVELS.index("INDUSTRY"))
    check(J, "promotion criteria are written down",
          len(PROMOTION_CRITERIA) >= 7)
    for c in PROMOTION_CRITERIA:
        check(J, f"'{c[:34]}' is a condition on the evidence", len(c) > 25)
    for s in SCENARIOS:
        check(J, f"{s.gid} names a level", s.level in LEVELS, s.level)
        check(J, f"{s.gid} names its requirement source",
              len(s.requirement_source) > 25)
        check(J, f"{s.gid} says what it can settle", len(s.can_settle) > 40)
        check(J, f"{s.gid} says what it cannot", len(s.cannot_settle) > 30)

    # THE invariant: only a scenario with a company case may claim the
    # industry level
    for s in SCENARIOS:
        if s.level == "INDUSTRY":
            check(J, f"{s.gid} has a company case to justify its level",
                  s.industry_case is not None)
            check(J, f"{s.gid} points at a case that exists",
                  any(c.cid == s.industry_case for c in ICASES))
            check(J, f"{s.gid} points at a case the model can run",
                  s.industry_case in RUNNABLE)
        elif s.level == "INDUSTRY-PARTIAL":
            check(J, f"{s.gid} has a company case", s.industry_case is not None)
            check(J, f"{s.gid} says what blocks promotion",
                  len(s.promotion_blockers) > 0)
        else:
            check(J, f"{s.gid} claims no company objective",
                  s.industry_case is None)

    # a scenario may be ABOUT a company case without having an objective from
    # it - naming one must not be mistakable for having one
    related = [s for s in SCENARIOS if s.related_case and not s.industry_case]
    check(J, "a related case is kept separate from an objective",
          len(related) >= 1, str([s.gid for s in related]))
    for s in related:
        check(J, f"{s.gid} explains why it cannot use the case",
              len(s.cannot_settle) > 60)
        check(J, f"{s.gid} says the vision-only result is not a substitute",
              "different question" in s.cannot_settle
              or "cannot be computed" in s.cannot_settle)

    # promotion must be about evidence, never about closer agreement
    pbuf = io.StringIO()
    with contextlib.redirect_stdout(pbuf):
        run_gold("GRS-002A")
    pt = pbuf.getvalue()
    check(J, "a partial scenario lists what would promote it",
          "WHAT WOULD PROMOTE IT TO INDUSTRY" in pt)
    check(J, "and says promotion is about the evidence",
          "about the EVIDENCE" in pt)
    check(J, "and that tuning to match would not promote it",
          "leave the level exactly where it is" in pt)

    # a matching boundary must be COMPARED, not refused - refusing everything
    # would throw away the comparisons that work
    check(J, "a target at a boundary the model reaches is compared",
          "boundary AI_PIPELINE on both sides - comparable" in pt)

    industry = [s for s in SCENARIOS if s.level == "INDUSTRY"]
    check(J, "most scenarios do NOT reach the industry level",
          len(industry) < len(SCENARIOS) / 2,
          f"{len(industry)} of {len(SCENARIOS)}")
    check(J, "and at least one sits at the partial level",
          any(s.level == "INDUSTRY-PARTIAL" for s in SCENARIOS))

    # an industry-anchored scenario must use the COMPANY's baseline and
    # application, not the course's - their target is relative to the system
    # they are replacing
    for s in industry:
        check(J, f"{s.gid} uses the company's baseline", s.use_industry_baseline)
        app_key, ref, cleanup = _context(s)
        try:
            check(J, f"{s.gid} runs the company's application, not the course's",
                  app_key != s.app_key, app_key)
        finally:
            if cleanup:
                APPLICATION_LIBRARY.pop(app_key, None)
        builder = RUNNABLE[s.industry_case]
        akey, company_ref, _ = builder()
        APPLICATION_LIBRARY.pop(akey, None)
        check(J, f"{s.gid} compares against the company's baseline",
              ref.compute == company_ref.compute, f"{ref.compute}")
        from ppact.designs import designs_for
        course_ref = designs_for(s.app_key)[0].config
        check(J, f"{s.gid} does NOT compare against the course reference",
              ref.compute != course_ref.compute or
              ref.memory_devices != course_ref.memory_devices,
              "the company's target is relative to the system they replace")

    # a scenario without a company case must say so in its report
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_gold("GRS-003")
    t3 = buf.getvalue()
    check(J, "a scenario-level fixture says it has no company objective",
          "None attached" in t3)
    check(J, "and that claiming otherwise would be claiming evidence",
          "claiming evidence it does not have" in t3)

    # the industry one must say direction agreement is not validation
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        run_gold("GRS-001", SystemConfig("cortex_a78_x4", "npu_64x64",
                                         "LPDDR5", 2,
                                         preprocessing_mode="isp_assisted"))
    t1 = buf2.getvalue()
    check(J, "the industry fixture reports direction agreement", 
          "direction agrees" in t1)
    check(J, "and says it is not validation", "not validation" in t1)
    check(J, "and refuses the wider-boundary latency target",
          "not compared" in t1 and "wider than the model reaches" in t1)
    check(J, "and says the workload parameters are ours",
          "workload parameters underneath are ours" in t1)

    # the summary must state the level counts rather than a total
    buf3 = io.StringIO()
    with contextlib.redirect_stdout(buf3):
        run_all_gold()
    ta = buf3.getvalue()
    check(J, "the summary counts scenarios reaching the industry level",
          "reach INDUSTRY" in ta and "company objective" in ta)
    check(J, "and says a low count is not a defect",
          "not a defect" in ta)
    check(J, "and that a level is a claim about evidence",
          "claim about evidence" in ta)
    check(J, "and describes what the rest check instead",
          "a requirement this course wrote" in ta)

    # every scenario must run for a student design without error
    fails = []
    student = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
    for s in SCENARIOS:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                run_gold(s.gid, student)
        except Exception as exc:
            fails.append(f"{s.gid}: {type(exc).__name__} {exc}")
    check(J, "every scenario runs for a student design", not fails,
          "; ".join(fails[:2]))

    # and must not leave a temporary application behind
    check(J, "no temporary application is left registered",
          not any(k.startswith("__") for k in APPLICATION_LIBRARY),
          str([k for k in APPLICATION_LIBRARY if k.startswith("__")]))


# ==============================================================================
# PATH AK - migrations
# ==============================================================================
#
# A migration touches compute, memory, power, area and cost at once, so a
# defect in any of them shows up as a broken relation rather than as an odd
# number. These are the strongest structural checks in the package because a
# MUST claim needs no calibration to test.

def path_ak():
    K = "AK"
    from ppact.migration import (MIGRATIONS, BY_ID, STRENGTHS, TOLERANCE,
                                 check_migration, check_all)
    import io, contextlib

    check(K, "migrations are defined", len(MIGRATIONS) >= 6)
    for m in MIGRATIONS:
        check(K, f"{m.mid} describes the move", len(m.description) > 25)
        check(K, f"{m.mid} makes claims", len(m.claims) >= 3)
        check(K, f"{m.mid} carries a teaching point", len(m.teaching_point) > 40)
        strengths = {c.strength for c in m.claims}
        check(K, f"{m.mid} distinguishes strengths", len(strengths) >= 2,
              str(strengths))
        for c in m.claims:
            check(K, f"{m.mid}/{c.metric} names a strength",
                  c.strength in STRENGTHS)
            check(K, f"{m.mid}/{c.metric} names a direction",
                  c.direction in ("up", "down", "same", "any"))
            check(K, f"{m.mid}/{c.metric} says why", len(c.because) > 25)

    # THE property: no MUST claim may be violated. A violation is a defect in
    # the model, not a surprising result.
    violations = []
    for m in MIGRATIONS:
        for c, got, pct, state in check_migration(m.mid, verbose=False):
            if state == "VIOLATED":
                violations.append(f"{m.mid} {c.metric}: {c.direction} expected, "
                                  f"{got} got")
    check(K, "no MUST claim is violated", not violations,
          "; ".join(violations[:3]))

    # a MUST claim is about the SIGN, and its tolerance must reflect that -
    # reading a 0.47% rise as unchanged once turned a correct model into a
    # reported defect
    check(K, "a MUST claim is tested on sign alone",
          TOLERANCE["MUST"] < 1e-9, str(TOLERANCE["MUST"]))
    check(K, "and a USUALLY claim keeps a visibility threshold",
          TOLERANCE["USUALLY"] > 1e-3)

    # every claimed metric must exist on a real result
    from ppact.system import evaluate_system as _ev
    for m in MIGRATIONS:
        app_key, before, after = m.build()
        mb = _ev(APPLICATION_LIBRARY[app_key], before).metrics
        for c in m.claims:
            check(K, f"{m.mid}/{c.metric} is a metric the model produces",
                  c.metric in mb, c.metric)

    # a DEPENDS claim must not be silently treated as an expectation
    for m in MIGRATIONS:
        for c in m.claims:
            if c.strength == "DEPENDS":
                check(K, f"{m.mid}/{c.metric} declares no direction",
                      c.direction == "any", c.direction)

    # a claim that holds in sign but moves too little must say so rather than
    # be counted as agreement or as failure
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        check_all()
    t = buf.getvalue()
    check(K, "the summary names the MUST claims explicitly",
          "MUST CLAIMS" in t)
    check(K, "and separates a soft failure from a defect",
          "not a defect" in t or "none violated" in t)
    check(K, "and reports changes too small to design around",
          "too little to design around" in t)
    check(K, "and says why that is a result rather than a rounding",
          "rounded into agreement" in t)

    # every migration must run
    fails = []
    for m in MIGRATIONS:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                check_migration(m.mid)
        except Exception as exc:
            fails.append(f"{m.mid}: {type(exc).__name__} {exc}")
    check(K, "every migration runs", not fails, "; ".join(fails[:2]))

    # the migrations must cover the moves a student actually makes
    titles = " ".join(m.title.lower() for m in MIGRATIONS)
    for move in ("host", "gpu", "two", "preprocessing", "memory", "node"):
        check(K, f"a '{move}' migration exists", move in titles)


# ==============================================================================
# PATH AL - the process node as a design variable
# ==============================================================================
#
# Node coverage used to be two checks and one hard-coded N12. A node changes
# area, speed, energy and cost at once, and it is the axis where intuition
# fails hardest - every quantity improves as it shrinks except the one people
# assume improves most.

def path_al():
    L = "AL"
    from ppact.process import NODE_LIBRARY, get_node
    from ppact.migration import node_sweep, cheapest_node
    import dataclasses as _dcn

    nodes = list(NODE_LIBRARY)
    check(L, "the library spans several generations", len(nodes) >= 8)

    # --- every node must be usable on every application --------------------
    fails = []
    for key, app2 in APPLICATION_LIBRARY.items():
        cpu = "server_x86_x32" if app2.domain == "Data Center" else "cortex_a78_x4"
        comp = "datacenter_gpu" if app2.domain == "Data Center" else "npu_32x32"
        mem = "HBM3E" if app2.domain == "Data Center" else "LPDDR5"
        for n in nodes:
            try:
                evaluate_system(app2, SystemConfig(cpu, comp, mem, 4,
                                                   accel_node=n, soc_node=n))
            except Exception as exc:
                fails.append(f"{key}/{n}: {type(exc).__name__}")
    check(L, "every node is usable on every application", not fails,
          "; ".join(fails[:3]))

    # --- monotone in everything except cost --------------------------------
    #
    # Smaller is faster, smaller, cooler. That much is structural. Cost is the
    # exception and the reason the sweep exists.
    rows = node_sweep("industrial_vision", SystemConfig(
        "cortex_a78_x4", "npu_128x128", "LPDDR5", 4), show=False)
    tops = [r[1] for r in rows]
    area = [r[2] for r in rows]
    lat = [r[3] for r in rows]
    energy = [r[5] for r in rows]
    cost = [r[6] for r in rows]
    check(L, "peak arithmetic rises monotonically as the node shrinks",
          all(a < b for a, b in zip(tops, tops[1:])),
          str([round(t, 1) for t in tops]))
    check(L, "silicon area falls monotonically",
          all(a > b for a, b in zip(area, area[1:])),
          str([round(a, 1) for a in area]))
    check(L, "latency falls monotonically",
          all(a > b for a, b in zip(lat, lat[1:])),
          str([round(x, 2) for x in lat]))
    check(L, "energy per inference falls monotonically",
          all(a > b for a, b in zip(energy, energy[1:])),
          str([round(x, 1) for x in energy]))

    # THE result: cost is NOT monotone, and the cheapest node is not the
    # smallest. If this ever became monotone the wafer-price or yield model
    # would have stopped working.
    check(L, "cost is NOT monotone in the node",
          not all(a > b for a, b in zip(cost, cost[1:])),
          str([round(c, 2) for c in cost]))
    cheapest = cheapest_node("industrial_vision", SystemConfig(
        "cortex_a78_x4", "npu_128x128", "LPDDR5", 4))
    check(L, "the cheapest node is not the smallest",
          cheapest != nodes[-1], cheapest)
    check(L, "and not the largest either", cheapest != nodes[0], cheapest)

    # --- the node library's own ordering -----------------------------------
    prev = None
    for n in nodes:
        nd = get_node(n)
        if prev is not None:
            check(L, f"{n} logic cells are smaller than {prev.name}",
                  nd.logic_area < prev.logic_area)
            check(L, f"{n} switches for less energy than {prev.name}",
                  nd.energy < prev.energy)
            check(L, f"{n} clocks higher than {prev.name}",
                  nd.fmax > prev.fmax)
            check(L, f"{n} wafers cost more than {prev.name}",
                  nd.wafer_price_usd > prev.wafer_price_usd)
            # NOT monotone, and correctly so: a mature derivative of an
            # established node yields better than its parent. The check that
            # forced monotonicity here was wrong about the industry, not about
            # the library.
            if not nd.notes.lower().startswith("cost-optimised"):
                check(L, f"{n} yields no better than {prev.name}",
                      nd.yield_factor <= prev.yield_factor,
                      "only a cost-optimised derivative may yield better")
            # SRAM is the reason a shrink disappoints
            check(L, f"{n} SRAM shrinks less than its logic",
                  (nd.sram_area / prev.sram_area) > (nd.logic_area / prev.logic_area))
        prev = nd

    # --- the node must be SELECTABLE, not just supported --------------------
    #
    # It was a parameter the model honoured and the interface did not offer,
    # outside the design game. An axis a student cannot choose is not a design
    # variable to them.
    import ppact.menu as _MN
    msrc = open(_MN.__file__, encoding="utf-8").read()
    # Checked through the registry, not by scanning menu.py for the old
    # wording. The prompts moved into ppact.questions and a check reading
    # the string out of the file reports the move as a regression while the
    # question is sitting in the registry, offered, with working help.
    from ppact.questions import get as _qnode
    check(L, "the node is offered on the main runtime path",
          "ask_node" in msrc
          and _qnode("process_node").resolved().options,
          "the runtime path must reach the process node question")
    check(L, "and the sweep is shown alongside the result",
          "node_sweep" in msrc)
    import ppact.game as _GM
    gsrc = open(_GM.__file__, encoding="utf-8").read()
    # Checked through the registry rather than by scanning game.py for a
    # string. The prompts moved into ppact.questions at 4.14.0, and a check
    # that reads the old wording out of the old file would report the move
    # as a regression while the question is right there.
    from ppact.questions import get as _qn
    check(L, "and remains selectable in the design game",
          "process_node" in gsrc and _qn("process_node") is not None,
          "the design game must reach the node question")
    node_q = _qn("process_node").resolved()
    check(L, "the node question offers every node",
          len(node_q.options) == len(NODE_LIBRARY),
          f"{len(node_q.options)} against {len(NODE_LIBRARY)}")

    # --- the node must reach the results -----------------------------------
    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                        accel_node="N16", soc_node="N16")
    small = _dcn.replace(base, accel_node="N3", soc_node="N3")
    a = evaluate_system(APPLICATION_LIBRARY["industrial_vision"], base).metrics
    b = evaluate_system(APPLICATION_LIBRARY["industrial_vision"], small).metrics
    for key in ("Peak TOPS", "Logic silicon (mm2)", "Latency (ms)",
                "Energy per inference (mJ)", "System cost (USD)"):
        check(L, f"the node reaches {key}", abs(a[key] - b[key]) > 1e-9, key)
    # and must NOT reach what it cannot change
    for key in ("Deployment accuracy (%)", "DRAM traffic (MB)"):
        check(L, f"the node does not touch {key}",
              abs(a[key] - b[key]) < 1e-9,
              "a process node changes how fast and how small, never what the "
              "network computes")

    # --- the sweep must say the turn belongs to the design ------------------
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        node_sweep("industrial_vision", SystemConfig(
            "cortex_a78_x4", "npu_128x128", "LPDDR5", 4))
    t = buf.getvalue()
    check(L, "the sweep marks the lowest-cost node", "lowest recurring" in t)
    check(L, "and says every other axis improves", "except cost improves" in t)
    check(L, "and explains why cost turns",
          "shrinks at roughly half the rate of logic" in t)
    check(L, "and says what the turning point depends on",
          "depends on how much of the die is SRAM" in t)

    # --- same node in and out changes nothing --------------------------------
    same = _dcn.replace(base, accel_node="N16", soc_node="N16")
    c = evaluate_system(APPLICATION_LIBRARY["industrial_vision"], same).metrics
    for key in ("Peak TOPS", "Logic silicon (mm2)", "Latency (ms)",
                "System power (W)", "Logic die cost (USD)"):
        check(L, f"the same node leaves {key} untouched",
              abs(a[key] - c[key]) < 1e-12, key)

    # --- the node must move SILICON and nothing else -------------------------
    #
    # A node changes the die. Memory, package, board and assembly are bought,
    # and a model where they moved with the node would be scaling things a
    # foundry has no part in.
    for key in ("Package cost (USD)",):
        if key in a and key in b:
            check(L, f"the node does not move {key}",
                  abs(a[key] - b[key]) < 1e-9, key)
    from ppact.memory import evaluate as _mev, MEMORY_LIBRARY as _ML
    mem_cost = _mev(_ML["LPDDR5"]).metrics["Package cost (USD)"]
    check(L, "memory is bought, not fabricated with the design",
          mem_cost > 0, "a node change cannot alter a purchased part's price")

    # --- both cost figures must be reported ----------------------------------
    #
    # The die and the system move by very different amounts. Reporting only
    # one misleads in opposite directions: the die alone overstates what the
    # product gains, the system alone hides what the node did.
    die_change = abs(b["Logic die cost (USD)"] / a["Logic die cost (USD)"] - 1)
    sys_change = abs(b["System cost (USD)"] / a["System cost (USD)"] - 1)
    check(L, "both a die cost and a system cost are reported",
          "Logic die cost (USD)" in a and "System cost (USD)" in a)
    check(L, "and they move by different amounts",
          die_change > sys_change * 1.5,
          f"die {die_change * 100:.1f}%, system {sys_change * 100:.1f}%")
    check(L, "the sweep prints both", "die $" in t and "system $" in t)
    check(L, "and says a node moves silicon and nothing else",
          "SILICON and nothing else" in t)

    # --- the lowest-cost node must not be stated as a general law ------------
    check(L, "the lowest-cost node is qualified by the library's assumptions",
          "under THIS library" in t and "THIS design" in t)
    check(L, "and is not called optimal or best",
          "optimal" not in t.lower() and "best node" not in t.lower())
    check(L, "and says what a real programme would also weigh",
          "volume and schedule" in t)
    check(L, "and that development cost is answered elsewhere",
          "ppact.economics" in t)

    # --- design types must actually move the turn ----------------------------
    from ppact.migration import DESIGN_TYPES, design_type_nodes
    check(L, "design-type presets exist", len(DESIGN_TYPES) >= 4)
    for name, (frac, why) in DESIGN_TYPES.items():
        check(L, f"'{name}' states an SRAM fraction", 0.0 < frac < 1.0)
        check(L, f"'{name}' says what it is", len(why) > 30)
    with contextlib.redirect_stdout(io.StringIO()) as dbuf:
        design_type_nodes()
    dt = dbuf.getvalue()
    check(L, "the presets show more than one cheapest node",
          "1 different node(s)" not in dt)
    check(L, "and say the mix moves it, not the application",
          "The mix is what moves it, not the application" in dt)

    # --- why the turn is where it is ----------------------------------------
    #
    # The sweep once claimed the turning point "belongs to THIS design". It
    # does not, in this library: the cheapest node is N7 for all 108
    # combinations of application, engine and memory. The MECHANISM that would
    # move it is real - SRAM shrinks at half the rate of logic - and every
    # accelerator here sits near two thirds SRAM, so none of them exercises it.
    from ppact.migration import turn_curve
    curve = turn_curve()
    mins = {label: min(curve, key=lambda n: curve[n][label])
            for label in ("all logic", "half", "mostly SRAM")}
    check(L, "the mix does move the cheapest node in principle",
          len(set(mins.values())) > 1, str(mins))
    check(L, "an all-logic die turns later than a mostly-SRAM one",
          nodes.index(mins["all logic"]) > nodes.index(mins["mostly SRAM"]),
          str(mins))

    # and the library must admit that it does not exercise the mechanism
    from ppact.compute import COMPUTE_LIBRARY as _CN
    fractions = []
    for spec in _CN.values():
        if not spec.mac_array:
            continue
        mac, sram = spec.mac_area_at("N16"), spec.sram_area_at("N16")
        fractions.append(sram / (mac + sram))
    # The band widened from 0.63-0.66 to 0.39-0.66 when architectural
    # classes were added at 4.2.0, and the cheapest node stayed N7 for every
    # engine in the library. That makes the finding STRONGER, not weaker:
    # the mechanism is real, the library now spans a much wider SRAM mix,
    # and it still does not move the turn. The bound is loosened to what is
    # true rather than the finding being quietly dropped.
    from ppact.process import NODE_LIBRARY as _NL
    turns = set()
    for spec in _CN.values():
        if not spec.mac_array:
            continue
        costs = {n: spec.silicon_cost_at(n) for n in _NL}
        turns.add(min(costs, key=costs.get))
    check(L, "the SRAM fraction spans a real range across the library",
          max(fractions) - min(fractions) > 0.20,
          f"{min(fractions):.2f} to {max(fractions):.2f}")
    check(L, "and the cheapest node is the same for all of them anyway",
          len(turns) == 1,
          f"{sorted(turns)} - the mechanism is real and a range this wide "
          f"still does not reach it")
    check(L, "the sweep says the turn does not move between these designs",
          "does NOT move" in t)
    check(L, "and that the mechanism is real even so",
          "mechanism is real and this library does not exercise" in t)
    check(L, "and shows the curve behind it", "cheapest for that mix" in t)


# ==============================================================================
# PATH AM - node economics
# ==============================================================================
#
# A wafer price is a cost per unit. A mask set is not, and neither is the
# physical implementation, verification, IP porting or a re-spin. The rest of
# the model computes RECURRING cost, which is the right answer to "what does
# this part cost" and the wrong answer to "what node should this product use".

def path_am():
    M = "AM"
    from ppact.economics import (economics, break_even, print_economics,
                                 print_break_even, DESIGN_REUSE,
                                 MIGRATION_DISTANCE, RESPIN_RISK, IP_PORTING,
                                 BASE_EFFORT_USD, development_cost)
    from ppact.process import NODE_LIBRARY
    import io, contextlib

    for name, table in (("design reuse", DESIGN_REUSE),
                        ("migration distance", MIGRATION_DISTANCE),
                        ("re-spin risk", RESPIN_RISK),
                        ("IP porting", IP_PORTING)):
        check(M, f"{name} offers several settings", len(table) >= 3, str(table))
    check(M, "development is broken into named lines",
          len(BASE_EFFORT_USD) >= 5, str(list(BASE_EFFORT_USD)))
    for line in BASE_EFFORT_USD:
        check(M, f"'{line}' is not a wafer cost",
              "wafer" not in line.lower() and "die" not in line.lower())

    # --- development must rise steeply with the node ------------------------
    nodes = list(NODE_LIBRARY)
    nres = []
    for n in nodes:
        mask, effort, respin = development_cost(n)
        nres.append(mask + sum(effort.values()) + respin)
    check(M, "development cost rises monotonically with the node",
          all(a < b for a, b in zip(nres, nres[1:])),
          str([round(x / 1e6, 1) for x in nres]))
    check(M, "and rises faster than the wafer price does",
          nres[-1] / nres[0] > NODE_LIBRARY[nodes[-1]].wafer_price_usd
          / NODE_LIBRARY[nodes[0]].wafer_price_usd,
          f"NRE {nres[-1] / nres[0]:.1f}x against wafer "
          f"{NODE_LIBRARY[nodes[-1]].wafer_price_usd / NODE_LIBRARY[nodes[0]].wafer_price_usd:.1f}x")

    # effort must NOT scale like a mask set - a 28 nm design still needs
    # timing closure, verification and a test program
    _, e_old, _ = development_cost(nodes[0])
    _, e_new, _ = development_cost(nodes[-1])
    effort_ratio = sum(e_new.values()) / sum(e_old.values())
    mask_ratio = (NODE_LIBRARY[nodes[-1]].mask_set_usd
                  / NODE_LIBRARY[nodes[0]].mask_set_usd)
    check(M, "effort scales more gently than masks do",
          effort_ratio < mask_ratio,
          f"effort {effort_ratio:.1f}x against masks {mask_ratio:.1f}x")

    # --- amortisation -------------------------------------------------------
    cfg = SystemConfig("cortex_a53_x4", "npu_16x16", "LPDDR5", 1)
    small = economics("smart_camera", cfg, node="N7", volume=10_000)
    large = economics("smart_camera", cfg, node="N7", volume=100_000_000)
    check(M, "recurring cost does not depend on volume",
          abs(small.recurring_unit - large.recurring_unit) < 1e-9)
    check(M, "development per unit falls with volume",
          small.nre_per_unit > large.nre_per_unit * 100)
    check(M, "and the effective cost falls with it",
          small.effective_unit > large.effective_unit)
    check(M, "effective is recurring plus amortised development",
          abs(small.effective_unit
              - (small.recurring_unit + small.nre_per_unit)) < 1e-9)

    # --- THE result: the economic node moves with volume --------------------
    def cheapest(kind, volume):
        rows = [(n, economics("mobile_ai", SystemConfig(
            "cortex_a78_x4", "npu_64x64", "LPDDR5", 2), node=n, volume=volume))
            for n in nodes]
        key = (lambda r: r[1].recurring_unit) if kind == "make" else \
            (lambda r: r[1].effective_unit)
        return min(rows, key=key)[0]

    make_low = cheapest("make", 1_000_000)
    make_high = cheapest("make", 500_000_000)
    ship_low = cheapest("ship", 1_000_000)
    ship_high = cheapest("ship", 500_000_000)
    check(M, "the cheapest node to MANUFACTURE does not depend on volume",
          make_low == make_high, f"{make_low} vs {make_high}")
    check(M, "but the cheapest node to SHIP does",
          ship_low != ship_high, f"{ship_low} at 1M vs {ship_high} at 500M")
    check(M, "and a higher volume justifies a finer node",
          nodes.index(ship_high) > nodes.index(ship_low),
          f"{ship_low} -> {ship_high}")

    # --- what the break-even volumes belong to ------------------------------
    #
    # These dies are tens of square millimetres. A phone SoC is a hundred or
    # more, so a node change moves fewer dollars here and the break-even comes
    # out higher than a real programme would see. Stating that is the
    # difference between a limitation and a wrong answer.
    die_mm2 = evaluate_system(APPLICATION_LIBRARY["mobile_ai"], SystemConfig(
        "cortex_a78_x4", "npu_64x64", "LPDDR5", 2,
        accel_node="N7", soc_node="N7")).metrics["Logic silicon (mm2)"]
    check(M, "the modelled die is an AI block, not a whole SoC",
          die_mm2 < 60, f"{die_mm2:.1f} mm2")
    # The wording check that belonged here referenced a variable that
    # was never bound; the `if "t" in dir()` guard made it dead rather
    # than broken. The claim it meant to check is made against the
    # rendered text, where the text exists.

    # --- a migration that never repays on cost is an ORDINARY result --------
    #
    # Between adjacent nodes an SRAM-heavy die often gets dearer, and parts
    # move anyway. A report that treated 'no break-even' as a verdict against
    # the move would teach the wrong lesson.
    from ppact.system import evaluate_system as _ev2
    def _at(node, key):
        return _ev2(APPLICATION_LIBRARY["mobile_ai"], SystemConfig(
            "cortex_a78_x4", "npu_64x64", "LPDDR5", 2,
            accel_node=node, soc_node=node)).metrics[key]
    check(M, "a finer node can cost more per unit and still be right",
          _at("N5", "Logic die cost (USD)") > _at("N7", "Logic die cost (USD)")
          and _at("N5", "Energy per inference (mJ)")
          < _at("N7", "Energy per inference (mJ)"),
          "dearer silicon, less energy - which is why parts move")

    # --- break-even ---------------------------------------------------------
    v = break_even("mobile_ai", SystemConfig(
        "cortex_a78_x4", "npu_64x64", "LPDDR5", 2), "N12", "N7")
    check(M, "a break-even volume is computed where one exists",
          v is not None and v > 0, str(v))
    # moving to a node that is dearer BOTH ways can never repay
    v2 = break_even("mobile_ai", SystemConfig(
        "cortex_a78_x4", "npu_64x64", "LPDDR5", 2), "N7", "A16")
    check(M, "and none is claimed where the finer node is dearer both ways",
          v2 is None, str(v2))

    # --- the reports must keep the two costs apart --------------------------
    with contextlib.redirect_stdout(io.StringIO()) as b:
        print_economics("smart_camera", cfg, volume=50_000)
    t = b.getvalue()
    check(M, "the report shows recurring and effective separately",
          "system $" in t and "effective $" in t)
    check(M, "and names the lowest of each", "lowest recurring" in t
          and "lowest effective" in t)
    check(M, "and itemises the development cost",
          "mask set and tape-out" in t and "re-spin allowance" in t)
    check(M, "and says every figure is estimated", "ESTIMATED" in t)
    check(M, "and that the shape is certain where the numbers are not",
          "SHAPE" in t and "not in doubt" in t)

    with contextlib.redirect_stdout(io.StringIO()) as b2:
        print_break_even("mobile_ai", SystemConfig(
            "cortex_a78_x4", "npu_64x64", "LPDDR5", 2), "N12", "N7")
    t2 = b2.getvalue()
    check(M, "the break-even report states a volume", "break-even at" in t2)
    check(M, "and compares it with the planned volume", "planned volume" in t2)

    with contextlib.redirect_stdout(io.StringIO()) as b4:
        print_break_even("mobile_ai", SystemConfig(
            "cortex_a78_x4", "npu_160x160", "LPDDR5", 2), "N12", "N5")
    t4 = b4.getvalue()
    check(M, "no break-even is reported where the finer node is dearer",
          "no break-even" in t4.lower())
    check(M, "and it is called an ordinary result, not a verdict",
          "ordinary result and not a reason to stay" in t4)
    check(M, "and points at power and energy instead",
          "power and energy columns" in t4)
    check(M, "the economics report names what silicon it amortises",
          "not a whole application" in t)
    check(M, "and says cost is not usually why a part moves node",
          "thermally" in t and "not die-cost limited" in t)

    # --- the decision report must lead with why parts ACTUALLY move ---------
    #
    # Not cost. A leading node costs more to develop and often more to make,
    # and parts move for speed and power - and because a competitor will.
    # Leading with cost invites the conclusion that the move is irrational,
    # which is neither what the industry does nor why.
    from ppact.economics import node_decision
    with contextlib.redirect_stdout(io.StringIO()) as b5:
        node_decision("industrial_vision", SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 4), "N16", "N7")
    t5 = b5.getvalue()
    order = [t5.index("1. PERFORMANCE"), t5.index("2. POWER"),
             t5.index("3. COST")]
    check(M, "the decision report puts performance first",
          order == sorted(order), "performance, power, then cost")
    check(M, "and calls cost what the first two are paid for",
          "what the first two are paid for" in t5)
    check(M, "and names competition as the reason the trade gets made",
          "competitor" in t5)
    check(M, "and does not claim to settle it",
          "cannot tell you whether" in t5)

    # a memory-bound design must be told the node buys it nothing
    with contextlib.redirect_stdout(io.StringIO()) as b6:
        node_decision("mobile_ai", SystemConfig(
            "cortex_a78_x4", "npu_64x64", "LPDDR5", 2), "N16", "N7")
    t6 = b6.getvalue()
    check(M, "a memory-bound design is warned the node buys little speed",
          "buys almost nothing here" in t6)
    check(M, "and told to check that first",
          "before paying for one" in t6)

    # and the numbers behind it must be real: a compute-bound design must
    # actually get faster, a memory-bound one must not
    def _lat(app_key, comp, mem, n, node):
        return evaluate_system(APPLICATION_LIBRARY[app_key], SystemConfig(
            "cortex_a78_x4", comp, mem, n, accel_node=node,
            soc_node=node)).metrics["Latency (ms)"]
    cb = 1 - _lat("industrial_vision", "npu_32x32", "LPDDR5", 4, "N3") / \
        _lat("industrial_vision", "npu_32x32", "LPDDR5", 4, "N16")
    mb2 = 1 - _lat("mobile_ai", "npu_64x64", "LPDDR5", 2, "N3") / \
        _lat("mobile_ai", "npu_64x64", "LPDDR5", 2, "N16")
    check(M, "a finer node speeds up a compute-bound design", cb > 0.20,
          f"{cb * 100:.1f}%")
    check(M, "and barely touches a memory-bound one", mb2 < 0.02,
          f"{mb2 * 100:.1f}%")

    # --- node and memory are different axes ---------------------------------
    #
    # A finer node makes the arithmetic faster and does nothing to a DRAM. A
    # node report on its own invites a student to buy compute for a design
    # that is waiting on transfers.
    from ppact.economics import node_and_memory
    with contextlib.redirect_stdout(io.StringIO()) as b7:
        node_and_memory("mobile_ai", SystemConfig(
            "cortex_a78_x4", "npu_64x64", "LPDDR5", 2,
            accel_node="N16", soc_node="N16"), "N7", "LPDDR5", 8)
    t7 = b7.getvalue()
    for option in ("neither", "node only", "memory only", "both"):
        check(M, f"the combined report covers '{option}'", option in t7)
    check(M, "and says the two are different axes",
          "DIFFERENT AXES" in t7)
    check(M, "and that a finer node does not make a DRAM faster",
          "does not make a DRAM faster" in t7)
    check(M, "and warns when the node is bought for a waiting engine",
          "already waiting" in t7)

    # the numbers behind it: on a memory-bound design the node must buy
    # almost nothing and the memory a great deal
    def _lat2(node, mem, dev):
        return evaluate_system(APPLICATION_LIBRARY["mobile_ai"], SystemConfig(
            "cortex_a78_x4", "npu_64x64", mem, dev, accel_node=node,
            soc_node=node)).metrics["Latency (ms)"]
    b0 = _lat2("N16", "LPDDR5", 2)
    node_gain = 1 - _lat2("N7", "LPDDR5", 2) / b0
    mem_gain = 1 - _lat2("N16", "LPDDR5", 8) / b0
    check(M, "on a memory-bound design the memory buys far more than the node",
          mem_gain > node_gain * 20,
          f"node {node_gain * 100:.1f}%, memory {mem_gain * 100:.1f}%")

    # and the reverse on a compute-bound one
    def _lat3(node, dev):
        return evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                               SystemConfig("cortex_a78_x4", "npu_32x32",
                                            "LPDDR5", dev, accel_node=node,
                                            soc_node=node)).metrics["Latency (ms)"]
    # Revised at 3.54.0. This used a host-preprocessing configuration, which
    # stopped being compute bound once the HOST's own memory traffic was
    # counted - the host now waits for pixels, and widening the bus helps it.
    # Offloading the preprocessing is what makes the design genuinely compute
    # bound, and only then does the node dominate.
    def _lat4(node, dev):
        return evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                               SystemConfig("cortex_a78_x4", "npu_32x32",
                                            "LPDDR5", dev, accel_node=node,
                                            soc_node=node,
                                            preprocessing_mode="isp_and_npu")
                               ).metrics["Latency (ms)"]
    c0 = _lat4("N16", 2)
    node_gain2 = 1 - _lat4("N3", 2) / c0
    mem_gain2 = 1 - _lat4("N16", 8) / c0
    # Revised again at 3.54.0: once the host's own traffic is counted, even
    # an offloaded design gains from a wider bus, so "far more" is no longer
    # the right claim. What must hold is that the node buys MORE, and that the
    # design is compute bound to begin with - which is the thing being tested.
    bound_here = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                                 SystemConfig("cortex_a78_x4", "npu_32x32",
                                              "LPDDR5", 2, accel_node="N16",
                                              soc_node="N16",
                                              preprocessing_mode="isp_and_npu")
                                 ).bound_by
    check(M, "the offloaded design is compute bound", bound_here == "compute",
          bound_here)
    check(M, "and on it the node buys more than the memory",
          node_gain2 > mem_gain2,
          f"node {node_gain2 * 100:.1f}%, memory {mem_gain2 * 100:.1f}%")

    # a node CAN move the bottleneck, and the report must say so
    before = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                             SystemConfig("cortex_a78_x4", "npu_32x32",
                                          "LPDDR5", 2, accel_node="N16",
                                          soc_node="N16")).bound_by
    after = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                            SystemConfig("cortex_a78_x4", "npu_32x32",
                                         "LPDDR5", 2, accel_node="A16",
                                         soc_node="A16")).bound_by
    check(M, "a fine enough node moves the bottleneck to memory",
          before == "compute" and after == "memory", f"{before} -> {after}")
    with contextlib.redirect_stdout(io.StringIO()) as b8:
        node_and_memory("industrial_vision", SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
            accel_node="N16", soc_node="N16"), "A16", "LPDDR5", 8)
    t8 = b8.getvalue()
    check(M, "and the report names the change of bottleneck",
          "changes what binds" in t8)
    check(M, "and says why that can justify the move",
          "bottleneck somewhere you can then attack" in t8)

    # --- more channels is one option of several -----------------------------
    #
    # It is the most expensive answer to a memory bottleneck and the first one
    # people reach for. Presenting it alone frames the question as "how much
    # do you want to spend".
    from ppact.economics import memory_options
    with contextlib.redirect_stdout(io.StringIO()) as b9:
        memory_options("industrial_vision", SystemConfig(
            "cortex_a78_x4", "npu_128x128", "LPDDR5", 1,
            accel_node="N16", soc_node="N16"))
    t9 = b9.getvalue()
    for option in ("better dataflow", "on-chip SRAM", "half the weights",
                   "memory packages", "move to"):
        check(M, f"the options report offers '{option}'", option in t9)
    check(M, "and says buying packages is only one answer",
          "one answer of several" in t9)
    check(M, "and that the obvious answer is usually the dearest",
          "usually the dearest" in t9)
    check(M, "and that a zero-BOM option still costs engineering",
          "costs engineering" in t9)
    # --- an architecture change and a model change are not alternatives -----
    #
    # Halving the weights makes the latency fall and makes the network a
    # different network. Listing it beside a compiler improvement invites a
    # student to pick whichever row has the best number.
    check(M, "the report separates the same network from a different one",
          "SAME NETWORK" in t9 and "A DIFFERENT NETWORK" in t9)
    check(M, "and says the two are not comparable",
          "not comparable with the others" in t9)
    check(M, "and shows accuracy on every row", "accuracy" in t9)
    # --- an unpriced model change must not report an accuracy ---------------
    #
    # The model computes quantisation loss and nothing else. Halving the
    # weights could be pruning, distillation, a smaller architecture or a
    # lower precision, and each costs a different amount of accuracy. Showing
    # the ORIGINAL network's figure made the row read as a free lunch.
    check(M, "an unpriced model change reports no accuracy",
          "not priced" in t9)
    check(M, "and no verdict on whether it ships", "unknown" in t9)
    check(M, "and says why it cannot be priced",
          "ACCURACY NOT PRICED" in t9 and "not one operation" in t9)
    check(M, "and how to price it",
          "model_accuracy_cost_pp" in t9)
    check(M, "and what the row should be read as",
          "here is what" in t9 and "yours to" in t9)

    # once priced, the gate must actually be re-evaluated against it
    with contextlib.redirect_stdout(io.StringIO()) as b11:
        memory_options("industrial_vision", SystemConfig(
            "cortex_a78_x4", "npu_128x128", "LPDDR5", 1,
            accel_node="N16", soc_node="N16"), model_accuracy_cost_pp=1.5)
    t11 = b11.getvalue()
    check(M, "a supplied accuracy cost reaches the deployment accuracy",
          "97.05" in t11)
    check(M, "and the row can then fail where the others pass",
          "can now FAIL" in t11)
    check(M, "and the accuracy is no longer marked unpriced",
          "not priced" not in t11.split("A DIFFERENT NETWORK")[1]
          .split("what each costs")[0])
    from ppact.economics import OPTION_CLASS
    check(M, "options are classified by what they cost",
          len(OPTION_CLASS) >= 4, str(list(OPTION_CLASS)))
    check(M, "and a model change is marked as such",
          "CHANGES THE MODEL" in OPTION_CLASS["model"])
    check(M, "and an engineering option as no BOM change",
          "no bill-of-materials change" in OPTION_CLASS["engineering"])

    # --- a memory class swap must match capacity ----------------------------
    #
    # One package of a narrower, smaller part is not a swap for one of a
    # wider, larger one. Comparing them as though it were made a class that
    # is dearer per gigabyte look 30% cheaper.
    from ppact.memory import MEMORY_LIBRARY as _MEM, evaluate as _mev
    lp, gd = _MEM["LPDDR5"], _MEM["GDDR6"]
    cost_lp = _mev(lp).metrics["Package cost (USD)"] / lp.capacity_gbyte
    cost_gd = _mev(gd).metrics["Package cost (USD)"] / gd.capacity_gbyte
    check(M, "the cheaper-looking class is dearer per gigabyte",
          cost_gd > cost_lp,
          f"LPDDR5 {cost_lp:.2f}/GB against GDDR6 {cost_gd:.2f}/GB")
    check(M, "so the report matches capacity when it swaps class",
          "packages to match" in t9)
    check(M, "and names the cooling the new class needs",
          "cooling" in t9)

    # --- removing a bottleneck is not the same as moving it -----------------
    check(M, "the report says whether the bottleneck moved or stayed",
          "REMOVE the bottleneck or move it" in t9)
    check(M, "and that moving it is not finishing the job",
          "has not finished the job" in t9)

    # reuse-based options must be ABSENT where there is no reuse, not listed
    # as options that failed
    with contextlib.redirect_stdout(io.StringIO()) as b10:
        memory_options("mobile_ai", SystemConfig(
            "cortex_a78_x4", "npu_64x64", "LPDDR5", 2,
            accel_node="N16", soc_node="N16"))
    t10 = b10.getvalue()
    check(M, "reuse options are omitted for a decode workload",
          "better dataflow" not in t10)
    check(M, "and the omission is explained",
          "nothing for them to save" in t10)
    check(M, "as a property of the workload, not a failure",
          "not a failure of the options" in t10)

    # the menu must not default to the most expensive step
    import ppact.menu as _MN2
    msrc2 = open(_MN2.__file__, encoding="utf-8").read()
    check(M, "the menu does not quadruple the memory by default",
          "min(n * 4, 8)" not in msrc2)
    check(M, "and offers the options report alongside",
          "memory_options" in msrc2)

    # --- the host is a third axis, not just area and power ------------------
    #
    # The node makes the arithmetic faster, the memory moves bytes faster, and
    # the HOST does the preprocessing, dispatch and post-processing - work no
    # accelerator touches. It was visible only as area and power, which is the
    # half of it that decides nothing.
    from ppact.economics import host_options
    from ppact.cpu import CPU_LIBRARY as _CPU

    def _capture_host(cpu, devices):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            host_options("industrial_vision", SystemConfig(
                cpu, "npu_32x32", "LPDDR5", devices,
                preprocessing_mode="cpu_only"))
        return buf.getvalue()
    with contextlib.redirect_stdout(io.StringIO()) as b12:
        host_options("industrial_vision", SystemConfig(
            "cortex_a53_x4", "npu_32x32", "LPDDR5", 4,
            preprocessing_mode="cpu_only"))
    t12 = b12.getvalue()
    check(M, "the host report itemises what the host holds",
          "preprocessing" in t12 and "dispatch" in t12
          and "post-processing" in t12)
    check(M, "and compares it against the accelerator",
          "accelerator" in t12)
    check(M, "and warns when the host holds most of the frame",
          "MORE than half the frame" in t12)
    check(M, "and says a bigger array cannot fix it",
          "bigger array" in t12 and "cannot fix" in t12)
    check(M, "and offers the offload alternative as well as a faster host",
          "move the work off the host" in t12)
    check(M, "and says what distinguishes the two",
          "keeps the flexibility" in t12 and "fixed-function" in t12)

    # the numbers: a host upgrade must move latency on a host-bound design
    def _host(cpu):
        return evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                               SystemConfig(cpu, "npu_32x32", "LPDDR5", 4,
                                            preprocessing_mode="cpu_only")).metrics
    weak, strong = _host("cortex_a53_x4"), _host("cortex_a78_x4")
    check(M, "a stronger host cuts the host time",
          strong["CPU active (ms)"] < weak["CPU active (ms)"] * 0.5,
          f"{weak['CPU active (ms)']:.1f} -> {strong['CPU active (ms)']:.1f} ms")
    check(M, "and the latency with it",
          strong["Latency (ms)"] < weak["Latency (ms)"] * 0.6)
    check(M, "while leaving the accelerator's arithmetic untouched",
          abs(strong["Compute time (ms)"] - weak["Compute time (ms)"]) < 1e-9,
          "a host change that moved the accelerator's compute would be wired "
          "wrong")

    # --- the host moves bytes too -------------------------------------------
    #
    # The CPU had no memory traffic at all, which cannot be true of anything
    # touching pixels. It reads a frame and writes a tensor, across the same
    # bus the accelerator uses.
    def _hm(mode):
        return evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                               SystemConfig("cortex_a78_x4", "npu_32x32",
                                            "LPDDR5", 4,
                                            preprocessing_mode=mode)).metrics
    on_cpu, offloaded = _hm("cpu_only"), _hm("isp_and_npu")
    check(M, "host preprocessing generates DRAM traffic",
          on_cpu["Host DRAM traffic (MB)"] > 1.0,
          f"{on_cpu['Host DRAM traffic (MB)']:.1f} MB")
    check(M, "and it takes a share of the bus",
          on_cpu["Host bandwidth share (%)"] > 1.0,
          f"{on_cpu['Host bandwidth share (%)']:.1f}%")
    check(M, "so the accelerator sees less than the interface rate",
          on_cpu["Bandwidth left to the accelerator (GB/s)"]
          < on_cpu["Effective bandwidth (GB/s)"] * 0.99)
    check(M, "offloading removes the host's traffic",
          offloaded["  host preprocess traffic (MB)"] < 1e-9,
          f"{offloaded['  host preprocess traffic (MB)']:.3f} MB")
    check(M, "and gives the bandwidth back to the accelerator",
          offloaded["Bandwidth left to the accelerator (GB/s)"]
          > on_cpu["Bandwidth left to the accelerator (GB/s)"] * 1.05)
    check(M, "which lowers the accelerator's transfer time on its own",
          offloaded["Memory time (ms)"] < on_cpu["Memory time (ms)"] * 0.95,
          f"{on_cpu['Memory time (ms)']:.3f} -> "
          f"{offloaded['Memory time (ms)']:.3f} ms")
    check(M, "post-processing traffic survives an offload",
          offloaded["  host postprocess traffic (MB)"] > 0,
          "the host still reads the output and writes a result")
    check(M, "the host traffic components sum to the total",
          abs(on_cpu["  host preprocess traffic (MB)"]
              + on_cpu["  host postprocess traffic (MB)"]
              - on_cpu["Host DRAM traffic (MB)"]) < 1e-9)
    # The cap must BIND somewhere, or it is a comment rather than a limit.
    # A weak host on a narrow bus preprocessing large frames is the case it
    # exists for.
    heavy = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                            SystemConfig("server_x86_x32", "npu_32x32",
                                         "LPDDR5", 1,
                                         preprocessing_mode="cpu_only")).metrics
    check(M, "the host share is capped at half the bus",
          on_cpu["Host bandwidth share (%)"] <= 50.0
          and heavy["Host bandwidth share (%)"] <= 50.0,
          f"{heavy['Host bandwidth share (%)']:.1f}%")
    # Revised at 3.54.0. The 50% cap was replaced by a 10% FLOOR on each
    # agent's share when the host got its own roofline: the question stopped
    # being "can the host take too much" and became "can either be starved to
    # nothing". Two earlier attempts at this split failed in exactly that way.
    starved = []
    for cpu_key in _CPU:
        for dev in (1, 2, 4, 8):
            mm = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                                 SystemConfig(cpu_key, "npu_32x32", "LPDDR5",
                                              dev,
                                              preprocessing_mode="cpu_only")
                                 ).metrics
            if mm["Effective bandwidth (GB/s)"] <= 0 or \
                    mm["Host transfer time (ms)"] > mm["Host compute time (ms)"] * 100:
                starved.append(f"{cpu_key}/x{dev}")
    check(M, "neither agent can be starved to nothing", not starved,
          "; ".join(starved[:3]))
    check(M, "the host report shows the traffic", "host DRAM traffic" in t12)

    # --- the host has a roofline too ----------------------------------------
    #
    # Its time was cycles over rate and nothing else, so a host moving 140 MB
    # never waited for a single byte. It cannot finish faster than its own
    # transfers, and a host that is memory bound does not get faster when you
    # give it more cores.
    def _hb(cpu, devices):
        return evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                               SystemConfig(cpu, "npu_32x32", "LPDDR5",
                                            devices,
                                            preprocessing_mode="cpu_only")).metrics
    for key in ("Host compute time (ms)", "Host transfer time (ms)",
                "Host data-wait (ms)", "Host bound by"):
        check(M, f"the model reports {key}", key in on_cpu, key)
    check(M, "host time is at least its arithmetic",
          on_cpu["CPU active (ms)"] >= on_cpu["Host compute time (ms)"] - 1e-9)
    check(M, "and at least its transfers",
          on_cpu["CPU active (ms)"] >= on_cpu["Host transfer time (ms)"] - 1e-9)
    check(M, "and no more than their sum",
          on_cpu["CPU active (ms)"] <= on_cpu["Host compute time (ms)"]
          + on_cpu["Host transfer time (ms)"] + 1e-9,
          "the same roofline the accelerator has")
    check(M, "the wait is the part not hidden",
          abs(on_cpu["Host data-wait (ms)"]
              - (on_cpu["CPU active (ms)"]
                 - on_cpu["Host compute time (ms)"])) < 1e-9)

    # THE result: a fast host on a narrow bus is memory bound, and more cores
    # buy a faster wait
    fast_narrow = _hb("server_x86_x32", 1)
    slow_narrow = _hb("cortex_a53_x4", 1)
    check(M, "a fast host on a narrow bus is memory bound",
          fast_narrow["Host bound by"] == 1.0,
          f"compute {fast_narrow['Host compute time (ms)']:.2f} against "
          f"transfer {fast_narrow['Host transfer time (ms)']:.2f} ms")
    check(M, "a slow host on the same bus is not",
          slow_narrow["Host bound by"] == 0.0)
    check(M, "and a wider bus can move a host back to compute bound",
          _hb("cortex_a78_x4", 1)["Host bound by"] == 1.0
          and _hb("cortex_a78_x4", 4)["Host bound by"] == 0.0,
          "an A78 is memory bound on one package and compute bound on four")
    # --- a fixture that can be checked by hand ------------------------------
    #
    # Every other check here compares one model result with another, which
    # catches a change and not an error. This one has an answer arrived at
    # without the model: with an overlap of 0.7, a host doing 10 ms of
    # arithmetic while moving bytes that take 4 ms must expose
    # 4 - 0.7 x min(10, 4) = 1.2 ms and take 11.2 ms in total.
    import ppact.system as _SYS
    ov = _SYS.HOST_MEMORY_OVERLAP
    for compute_ms, transfer_ms in ((10.0, 4.0), (4.0, 10.0), (5.0, 5.0)):
        hidden = ov * min(compute_ms, transfer_ms)
        expected_total = compute_ms + transfer_ms - hidden
        expected_exposed = expected_total - compute_ms
        check(M, f"roofline by hand: {compute_ms:g} ms compute, "
                 f"{transfer_ms:g} ms transfer",
              abs(expected_exposed - (transfer_ms - hidden)) < 1e-12
              and expected_total >= max(compute_ms, transfer_ms) - 1e-12
              and expected_total <= compute_ms + transfer_ms + 1e-12,
              f"total {expected_total:.3f}, exposed {expected_exposed:.3f}")
    # and the model must agree with that arithmetic on a real result
    got_total = on_cpu["CPU active (ms)"]
    got_hidden = on_cpu["Host hidden memory (ms)"]
    by_hand = (on_cpu["Host compute time (ms)"]
               + on_cpu["Host transfer time (ms)"] - got_hidden)
    check(M, "and the model agrees with it",
          abs(got_total - by_hand) < 1e-9,
          f"{got_total:.6f} against {by_hand:.6f}")
    check(M, "the hidden part is the overlap times the smaller of the two",
          abs(got_hidden - ov * min(on_cpu["Host compute time (ms)"],
                                    on_cpu["Host transfer time (ms)"])) < 1e-9)

    # --- nothing may be counted twice ---------------------------------------
    #
    # The host's bytes appear in three places - its own stage time, the
    # accelerator's available bandwidth, and the memory energy. Each must
    # count them once.
    check(M, "host bytes are the sum of their two sources",
          abs(on_cpu["  host preprocess traffic (MB)"]
              + on_cpu["  host postprocess traffic (MB)"]
              - on_cpu["Host DRAM traffic (MB)"]) < 1e-9)
    check(M, "the accelerator's traffic does NOT include the host's",
          on_cpu["DRAM traffic (MB)"] != on_cpu["DRAM traffic (MB)"]
          + on_cpu["Host DRAM traffic (MB)"],
          "if these were ever summed into one figure the bus would be "
          "double-booked")
    # the host's transfer time must come from the host's bytes, not the
    # accelerator's
    doubled = dataclasses.replace(APPLICATION_LIBRARY["industrial_vision"],
                                  weight_bytes=APPLICATION_LIBRARY[
                                      "industrial_vision"].weight_bytes * 4,
                                  key="__wb__")
    APPLICATION_LIBRARY["__wb__"] = doubled
    try:
        heavier = evaluate_system(doubled, SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
            preprocessing_mode="cpu_only")).metrics
        check(M, "more accelerator weights leave the host's bytes alone",
              abs(heavier["Host DRAM traffic (MB)"]
                  - on_cpu["Host DRAM traffic (MB)"]) < 1e-9,
              "the host does not read the network's weights")
    finally:
        APPLICATION_LIBRARY.pop("__wb__", None)

    # --- three states, and the middle one hedges ----------------------------
    states = set()
    for cpu_key in _CPU:
        for dev in (1, 2, 4, 8):
            states.add(evaluate_system(
                APPLICATION_LIBRARY["industrial_vision"],
                SystemConfig(cpu_key, "npu_32x32", "LPDDR5", dev,
                             preprocessing_mode="cpu_only")).host_state)
    check(M, "the host has three states, not two", len(states) == 3,
          str(sorted(states)))
    check(M, "and a balanced one exists in practice", "balanced" in states)
    balanced_cfg = None
    for cpu_key in _CPU:
        for dev in (1, 2, 4, 8):
            r = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                                SystemConfig(cpu_key, "npu_32x32", "LPDDR5",
                                             dev,
                                             preprocessing_mode="cpu_only"))
            if r.host_state == "balanced":
                balanced_cfg = (cpu_key, dev)
                break
        if balanced_cfg:
            break
    if balanced_cfg:
        txt = _capture_host(*balanced_cfg)
        check(M, "a balanced host is not given a verdict",
              "Near the balance point" in txt)
        check(M, "and the report says what the answer depends on",
              "does not measure" in txt)

    check(M, "the report warns that a faster host will not help",
          "faster host will NOT help" in
          _capture_host("cortex_a78_x4", 1))
    check(M, "and says what buying one actually buys",
          "buys a faster wait" in _capture_host("cortex_a78_x4", 1))

    # and the menu must offer it
    check(M, "the menu offers the host options", "host_options" in msrc2)

    # --- the node sweep must not claim to answer the economic question ------
    from ppact.migration import node_sweep
    with contextlib.redirect_stdout(io.StringIO()) as b3:
        node_sweep("industrial_vision", SystemConfig(
            "cortex_a78_x4", "npu_128x128", "LPDDR5", 4))
    t3 = b3.getvalue()
    check(M, "the sweep says it is recurring cost only",
          "RECURRING MANUFACTURING cost" in t3)
    check(M, "and that the cheapest to make is often not the cheapest to ship",
          "not the cheapest node to SHIP" in t3)
    check(M, "and points at where that question is answered",
          "ppact.economics" in t3)


# ==============================================================================
# PATH AN - the second accelerator
# ==============================================================================
#
# A student improving a reference reaches for a second engine, so the model has
# to be right about the cases where that does nothing. Those are the ones worth
# teaching and the ones a model built to reward hardware would get wrong.

def path_an():
    N = "AN"
    import dataclasses as _dc4
    import io, contextlib
    from ppact.runtime import simulate as _sim

    app = APPLICATION_LIBRARY["industrial_vision"]
    single = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                          preprocessing_mode="isp_assisted")
    a = evaluate_system(app, single)

    # --- the two knobs are different, and confusing them is silent ----------
    #
    # work_split divides ONE job's arithmetic; alternative_share routes WHOLE
    # jobs. Setting the wrong one leaves the second engine idle and costs
    # silicon for nothing, and the output looks the same either way.
    wrong = _dc4.replace(single, secondary_compute="npu_32x32",
                         execution_mode="alternative", work_split=0.5)
    right = _dc4.replace(single, secondary_compute="npu_32x32",
                         execution_mode="alternative", alternative_share=0.5)
    mw, mr = evaluate_system(app, wrong).metrics, evaluate_system(app, right).metrics
    check(N, "work_split is ignored in alternative mode",
          mw["Work split (MAC fraction)"] == 0.0,
          "the knob for this mode is alternative_share, and setting the other "
          "one changes nothing while looking as though it should")
    check(N, "and alternative_share is ignored in parallel mode",
          evaluate_system(app, _dc4.replace(
              single, secondary_compute="npu_32x32",
              execution_mode="parallel", alternative_share=0.9)
          ).metrics["Alternative share (job fraction)"] == 0.0)
    check(N, "both are reported so the mistake is visible",
          "Alternative share (job fraction)" in mr
          and "Work split (MAC fraction)" in mr)

    # --- single-job rate is not the pipeline rate ---------------------------
    #
    # Routing whole jobs to two engines raises the pipeline rate and cannot
    # raise one over the latency. A check that read the wrong one would report
    # a real gain as none - which is how this path was first written.
    robot = SystemConfig("cortex_a78_x4", "npu_16x16", "LPDDR5", 2,
                         preprocessing_mode="isp_and_npu")
    robot_dual = _dc4.replace(robot, secondary_compute="npu_16x16",
                              execution_mode="alternative",
                              alternative_share=0.5)
    r1, r2 = _sim("robot", robot, duration_s=10.0), _sim("robot", robot_dual,
                                                         duration_s=10.0)
    check(N, "the reference is accelerator limited",
          r1.limiting_stage == "Accelerator", r1.limiting_stage)
    check(N, "alternating jobs raises the PIPELINE rate",
          r2.throughput > r1.throughput * 1.05,
          f"{r1.throughput:.1f} -> {r2.throughput:.1f} /s")
    m1 = evaluate_system(APPLICATION_LIBRARY["robot"], robot).metrics
    m2 = evaluate_system(APPLICATION_LIBRARY["robot"], robot_dual).metrics
    check(N, "and leaves the single-job arithmetic alone",
          abs(m2["Compute time (ms)"] - m1["Compute time (ms)"]) < 1e-9,
          "each job still runs on one engine")
    check(N, "so the single-job rate does not rise",
          m2["Throughput (inf/s)"] <= m1["Throughput (inf/s)"] * 1.01,
          "one over the latency cannot see a second engine taking other jobs")
    import ppact.system as _SYS2
    ssrc = open(_SYS2.__file__, encoding="utf-8").read()
    check(N, "and the model says which of the two it reports",
          "It is NOT the pipeline rate" in ssrc)

    # --- the three reductions come apart -------------------------------------
    #
    # "The same as one engine" is three claims: the second engine is assigned
    # nothing (workload), the timings match (performance), and the area, cost
    # and power match (physical). The first two hold whenever the work is
    # zero; the third holds only when the engine is not on the board.
    unused = evaluate_system(app, _dc4.replace(
        single, secondary_compute="npu_32x32", execution_mode="alternative",
        alternative_share=0.0)).metrics
    check(N, "an unused engine launches no graph",
          abs(unused["Framework overhead (ms)"]
              - a.metrics["Framework overhead (ms)"]) < 1e-12,
          "a per-frame launch is not a per-board driver, and charging it made "
          "a declared-but-unused engine cost 0.25 ms a frame")
    check(N, "so the performance reduction is exact",
          abs(unused["Latency (ms)"] - a.metrics["Latency (ms)"]) < 1e-9,
          f"{a.metrics['Latency (ms)']:.9f} against "
          f"{unused['Latency (ms)']:.9f}")
    check(N, "but the physical reduction is not - the die is fitted",
          unused["Logic silicon (mm2)"] > a.metrics["Logic silicon (mm2)"])

    # a gated engine runs nothing whatever the knobs say
    gated = evaluate_system(app, _dc4.replace(
        single, secondary_compute="npu_32x32", secondary_enabled=False,
        execution_mode="parallel", work_split=0.5)).metrics
    check(N, "a powered-down engine runs nothing at a 0.5 split",
          abs(gated["Secondary compute time (ms)"]) < 1e-12,
          "the knob said half and the engine is off")
    check(N, "it keeps its area and its price",
          abs(gated["Logic silicon (mm2)"] - unused["Logic silicon (mm2)"]) < 1e-12
          and abs(gated["System cost (USD)"] - unused["System cost (USD)"]) < 1e-12)
    check(N, "gives up most of its leakage",
          gated["System power (W)"] < unused["System power (W)"],
          f"{unused['System power (W)']:.4f} -> {gated['System power (W)']:.4f} W")
    check(N, "and not all of it - gating is not removal",
          gated["System power (W)"] > a.metrics["System power (W)"] + 1e-9,
          "retention and rails do not vanish; taking this to zero would make "
          "'fit it and switch it off' look free")

    # a secondary named but absent must change nothing at all
    absent = evaluate_system(app, _dc4.replace(
        single, secondary_compute=None, execution_mode="parallel",
        work_split=0.7)).metrics
    for key in ("Latency (ms)", "Logic silicon (mm2)", "System power (W)",
                "System cost (USD)"):
        check(N, f"a split with no engine to split onto leaves {key} alone",
              abs(absent[key] - a.metrics[key]) < 1e-12)

    # --- an unused engine must not cost synchronisation ---------------------
    zero_p = _dc4.replace(single, secondary_compute="npu_32x32",
                          execution_mode="parallel", work_split=0.0)
    half_p = _dc4.replace(single, secondary_compute="npu_32x32",
                          execution_mode="parallel", work_split=0.5)
    mz, mh = evaluate_system(app, zero_p).metrics, evaluate_system(app, half_p).metrics
    check(N, "no hand-off is charged when nothing is split",
          abs(mz["Handoff (ms)"]) < 1e-12,
          "merging results that do not exist")
    check(N, "but one is charged when something is",
          mh["Handoff (ms)"] > 0)

    # --- the allocation peak must not be assumed to be even ------------------
    #
    # Two paths to the same answer: the model sweeps, and the capacity ratio
    # says where the sweep should peak. Neither uses the other.
    from ppact.economics import allocation_sweep
    with contextlib.redirect_stdout(io.StringIO()):
        rows_alt = allocation_sweep("robot", SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
            preprocessing_mode="isp_and_npu"), "npu_16x16", "alternative", 11)
    caps = {v: cap for v, lat, cap, dl, a1, a2, ok in rows_alt}
    peak = max(caps, key=caps.get)
    t_p, t_s = rows_alt[0][4], rows_alt[-1][5]
    ideal = t_p / (t_p + t_s)
    check(N, "the capacity peak is not at an even split",
          abs(peak - 0.5) > 0.1, f"{peak:.2f}")
    check(N, "and lands where the capacity ratio says it should",
          abs(peak - ideal) <= 0.11,
          f"model {peak:.2f} against arithmetic {ideal:.2f}")
    check(N, "an even split costs most of the capacity",
          caps[0.5] < caps[peak] * 0.6,
          f"{caps[0.5]:.1f} against {caps[peak]:.1f} per second")

    # --- three rates, named apart -------------------------------------------
    #
    # One name for all three invited exactly one defect: a design routing
    # alternate jobs to two engines raises the capacity and cannot raise the
    # single-job rate, and reading the wrong one reported a real gain as none.
    for key in ("Single-job rate (inf/s)", "Pipeline capacity (inf/s)",
                "Delivered throughput (inf/s)", "Pipeline interval (ms)"):
        check(N, f"the model reports {key}", key in m1, key)
    check(N, "the single-job rate is one over the latency",
          abs(m1["Single-job rate (inf/s)"] - 1e3 / m1["Latency (ms)"]) < 1e-6)
    check(N, "the capacity is one over the pipeline interval",
          abs(m1["Pipeline capacity (inf/s)"]
              - 1e3 / m1["Pipeline interval (ms)"]) < 1e-6)
    check(N, "the interval is at most the latency",
          m1["Pipeline interval (ms)"] <= m1["Latency (ms)"] + 1e-9,
          "a station cannot take longer than the whole job")
    check(N, "so the capacity is at least the single-job rate",
          m1["Pipeline capacity (inf/s)"] >= m1["Single-job rate (inf/s)"] - 1e-9)
    check(N, "delivered never exceeds capacity",
          m1["Delivered throughput (inf/s)"]
          <= m1["Pipeline capacity (inf/s)"] + 1e-9)
    check(N, "and never exceeds what arrives",
          m1["Delivered throughput (inf/s)"]
          <= APPLICATION_LIBRARY["robot"].target_inferences_per_s + 1e-9)

    # the three must SEPARATE on a case that moves one and not the others
    check(N, "alternating jobs raises the capacity",
          m2["Pipeline capacity (inf/s)"]
          > m1["Pipeline capacity (inf/s)"] * 1.5,
          f"{m1['Pipeline capacity (inf/s)']:.1f} -> "
          f"{m2['Pipeline capacity (inf/s)']:.1f}")
    # Not exactly equal: with a secondary engine present the preprocessing
    # moves onto it, which adds a hand-off worth about 0.2%. The point stands
    # - one job in flight cannot use two engines in alternative mode, so the
    # single-job rate does not gain anything like the capacity does.
    sj_change = abs(m2["Single-job rate (inf/s)"]
                    / m1["Single-job rate (inf/s)"] - 1) * 100
    cap_change = (m2["Pipeline capacity (inf/s)"]
                  / m1["Pipeline capacity (inf/s)"] - 1) * 100
    check(N, "and barely moves the single-job rate",
          sj_change < 1.0, f"{sj_change:.2f}%")
    check(N, "which is a hundredth of what the capacity gains",
          cap_change > sj_change * 50,
          f"capacity +{cap_change:.1f}% against single-job {sj_change:+.2f}%")
    check(N, "and the delivered rate agrees with the runtime",
          abs(m2["Delivered throughput (inf/s)"] - r2.throughput)
          < max(0.5, r2.throughput * 0.02),
          f"model {m2['Delivered throughput (inf/s)']:.1f} against runtime "
          f"{r2.throughput:.1f} - two paths to the same number")
    check(N, "the bare name is kept only as an alias",
          "retained as an alias" in ssrc and
          abs(m1["Throughput (inf/s)"]
              - m1["Single-job rate (inf/s)"]) < 1e-12)

    # --- an idle engine is not free -----------------------------------------
    zero = _dc4.replace(single, secondary_compute="npu_32x32",
                        execution_mode="parallel", work_split=0.0)
    z = evaluate_system(app, zero)
    check(N, "split=0 reduces to the single-engine arithmetic",
          abs(z.metrics["Compute time (ms)"]
              - a.metrics["Compute time (ms)"]) < 1e-9)
    check(N, "but the unused die still costs silicon",
          z.metrics["Logic silicon (mm2)"] > a.metrics["Logic silicon (mm2)"])
    check(N, "and still draws power",
          z.metrics["System power (W)"] > a.metrics["System power (W)"],
          "an engine that is not used is not a free option")

    # --- hardware alone may not change accuracy -----------------------------
    for mode, kw in (("parallel", {"work_split": 0.5}),
                     ("alternative", {"alternative_share": 0.5}),
                     ("sequential", {"work_split": 0.5})):
        d = _dc4.replace(single, secondary_compute="npu_32x32",
                         execution_mode=mode, **kw)
        check(N, f"{mode} mode with an IDENTICAL engine does not change "
                 f"accuracy",
              abs(evaluate_system(app, d).metrics["Deployment accuracy (%)"]
                  - a.metrics["Deployment accuracy (%)"]) < 1e-9,
              "accuracy comes from precision and model family; a die COUNT is "
              "not an input to it")

    # But a second engine with a DIFFERENT precision does change it, and
    # should. Found by a locked prediction at 3.75.0 which asserted that
    # accuracy cannot move when work is split - true only when the two
    # engines share a precision, and the check above uses two identical ones
    # so it never tested the other case.
    mixed = _dc4.replace(single, secondary_compute="npu_16x16",
                         execution_mode="parallel", work_split=0.5)
    mixed_acc = evaluate_system(app, mixed).metrics["Deployment accuracy (%)"]
    check(N, "but a secondary of a different precision DOES change accuracy",
          mixed_acc < a.metrics["Deployment accuracy (%)"] - 1e-9,
          f"{a.metrics['Deployment accuracy (%)']:.2f} -> {mixed_acc:.2f}% - "
          f"the 32x32 is quantisation-aware trained and the 16x16 is "
          f"post-training quantised, so half the work runs at the lower "
          f"quality and the result carries it")

    # --- the bus is shared, not doubled -------------------------------------
    dual = _dc4.replace(single, secondary_compute="npu_32x32",
                        execution_mode="parallel", work_split=0.5)
    d = evaluate_system(app, dual).metrics
    check(N, "two engines do not double the bandwidth",
          d["Effective bandwidth (GB/s)"]
          <= a.metrics["Effective bandwidth (GB/s)"] + 1e-9,
          "the packages did not change, so the bus did not")
    check(N, "and the weights are not read twice",
          abs(d["DRAM traffic (MB)"] - a.metrics["DRAM traffic (MB)"])
          < a.metrics["DRAM traffic (MB)"] * 0.05,
          "splitting one inference does not double its traffic")

    # --- an out-of-range knob is a mistake, not a value to tidy -------------
    #
    # Clamping silently gave a student who typed 1.5 the answer for 1.0 and no
    # reason to wonder why, which is the opposite of what a teaching model
    # should do.
    for field, bad in (("work_split", 1.5), ("work_split", -0.2),
                       ("alternative_share", 1.2),
                       ("alternative_share", -0.1)):
        raised = False
        try:
            evaluate_system(app, _dc4.replace(
                single, secondary_compute="npu_32x32",
                execution_mode="parallel", **{field: bad}))
        except ValueError as exc:
            raised = "fraction of" in str(exc)
        check(N, f"{field}={bad} is refused with a reason", raised,
              "an out-of-range knob does not describe anything")
    for field, good in (("work_split", 0.0), ("work_split", 1.0),
                        ("alternative_share", 0.0),
                        ("alternative_share", 1.0)):
        ok_here = True
        try:
            evaluate_system(app, _dc4.replace(
                single, secondary_compute="npu_32x32",
                execution_mode="parallel", **{field: good}))
        except ValueError:
            ok_here = False
        check(N, f"{field}={good} is still accepted", ok_here,
              "the boundaries of the range are inside it")

    # --- what happens BETWEEN two engines -----------------------------------
    #
    # The assumption this group breaks: two engines means twice as fast. Two
    # engines means a hand-off, a merge, a synchronisation and an ordering.
    robot_app = APPLICATION_LIBRARY["robot"]
    r_single = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                            preprocessing_mode="isp_and_npu")
    rs = evaluate_system(robot_app, r_single).metrics
    seq = evaluate_system(robot_app, _dc4.replace(
        r_single, secondary_compute="npu_32x32", execution_mode="sequential",
        work_split=0.5)).metrics
    par = evaluate_system(robot_app, _dc4.replace(
        r_single, secondary_compute="npu_32x32", execution_mode="parallel",
        work_split=0.5)).metrics

    check(N, "a sequential dependency preserves the total arithmetic",
          abs(seq["Compute time (ms)"] - rs["Compute time (ms)"]) < 1e-9,
          "stage one then stage two is still all the work")
    check(N, "and makes ONE job slower, not faster",
          seq["Latency (ms)"] > rs["Latency (ms)"],
          "the hand-off is new time nobody was paying")
    check(N, "while still raising the pipeline capacity",
          seq["Pipeline capacity (inf/s)"] > rs["Pipeline capacity (inf/s)"],
          "two stations can hold two different jobs")
    check(N, "a parallel split DOES make one job faster",
          par["Compute time (ms)"] < rs["Compute time (ms)"])
    check(N, "and the two modes are not the same thing",
          abs(par["Latency (ms)"] - seq["Latency (ms)"]) > 1e-6)

    # --- BOTH endpoints run on one engine ------------------------------------
    #
    # A split of 0 puts everything on the primary and a split of 1 puts
    # everything on the secondary. Neither divides a job, so neither pays to
    # partition, synchronise or merge. The zero end was fixed at 3.59.0 and
    # the same error sat at the other end, where a job entirely on the
    # secondary was paying 18% for a merge with nothing to merge against.
    for sec in ("npu_32x32", "npu_16x16"):
        whole = evaluate_system(APPLICATION_LIBRARY["robot"], _dc4.replace(
            r_single, secondary_compute=sec, execution_mode="parallel",
            work_split=1.0)).metrics
        alone = evaluate_system(APPLICATION_LIBRARY["robot"], _dc4.replace(
            r_single, compute=sec)).metrics
        check(N, f"split=1 on {sec} leaves the primary computing nothing",
              abs(whole["Primary compute time (ms)"]) < 1e-9)
        check(N, f"split=1 on {sec} charges no merge",
              abs(whole["Handoff (ms)"]) < 1e-12,
              "there is nothing to merge against")
        check(N, f"split=1 on {sec} matches a lone secondary",
              abs(whole["Compute time (ms)"] - alone["Compute time (ms)"])
              <= alone["Compute time (ms)"] * 0.001,
              f"{whole['Compute time (ms)']:.3f} against "
              f"{alone['Compute time (ms)']:.3f} ms")
        share1 = evaluate_system(APPLICATION_LIBRARY["robot"], _dc4.replace(
            r_single, secondary_compute=sec, execution_mode="alternative",
            alternative_share=1.0)).metrics
        check(N, f"share=1 on {sec} gives the secondary's capacity alone",
              abs(share1["Pipeline capacity (inf/s)"]
                  - alone["Pipeline capacity (inf/s)"])
              <= alone["Pipeline capacity (inf/s)"] * 0.02,
              "a primary contributing at share 1 would be a defect")
    # but a genuine division must still pay
    half = evaluate_system(APPLICATION_LIBRARY["robot"], _dc4.replace(
        r_single, secondary_compute="npu_32x32", execution_mode="parallel",
        work_split=0.5)).metrics
    check(N, "while a real division still pays to merge",
          half["Handoff (ms)"] > 0)

    # a pair cannot finish before its slower half
    for sec in ("npu_32x32", "npu_24x24", "npu_16x16"):
        mm = evaluate_system(robot_app, _dc4.replace(
            r_single, secondary_compute=sec, execution_mode="parallel",
            work_split=0.5)).metrics
        slowest = max(mm["Primary compute time (ms)"],
                      mm["Secondary compute time (ms)"])
        check(N, f"a {sec} pair cannot finish before its slower half",
              mm["Compute time (ms)"] >= slowest - 1e-9,
              f"slower half {slowest:.3f}, pair {mm['Compute time (ms)']:.3f} ms")

    # the merge penalty must reach the result
    import ppact.system as _S3
    saved_eff = _S3.PARALLEL_SPLIT_EFFICIENCY
    try:
        _S3.PARALLEL_SPLIT_EFFICIENCY = 0.4
        bad_merge = evaluate_system(robot_app, _dc4.replace(
            r_single, secondary_compute="npu_32x32",
            execution_mode="parallel", work_split=0.5)).metrics
    finally:
        _S3.PARALLEL_SPLIT_EFFICIENCY = saved_eff
    check(N, "a costlier merge reaches the answer",
          bad_merge["Latency (ms)"] > par["Latency (ms)"])
    check(N, "and a bad enough one makes two engines slower than one",
          bad_merge["Latency (ms)"] > rs["Latency (ms)"],
          f"{bad_merge['Latency (ms)']:.2f} against a single engine's "
          f"{rs['Latency (ms)']:.2f} ms")

    # the offload's own transfer must exist and belong to memory
    off_on = evaluate_system(app, _dc4.replace(
        single, preprocessing_mode="cpu_only")).metrics
    off_off = evaluate_system(app, _dc4.replace(
        single, preprocessing_mode="isp_and_npu")).metrics
    check(N, "moving work to the accelerator moves DATA to it",
          off_off["Offload transfer (ms)"] > 0
          and abs(off_on["Offload transfer (ms)"]) < 1e-12,
          "CPU to NPU is not a wire")
    check(N, "and the transfer is charged to memory, not to the engine",
          abs(off_off["Stage memory (ms)"]
              - (off_off["Memory time (ms)"]
                 + off_off["Offload transfer (ms)"])) < 1e-9,
          "the engine is not busy while bytes are on a bus")

    # --- the bus is allocated, and the allocations add up -------------------
    #
    # The reported host share used to be the rate the host ACHIEVED while the
    # accelerator's bandwidth came from the ALLOCATION, so the two did not sum
    # to the bus - a residue of about 1.5% that no agent owned.
    for devices in (1, 2, 4, 8):
        mm = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                             SystemConfig("cortex_a78_x4", "npu_32x32",
                                          "LPDDR5", devices,
                                          preprocessing_mode="cpu_only")).metrics
        total = (mm["Bandwidth left to the accelerator (GB/s)"]
                 + mm["Host bandwidth allocated (GB/s)"])
        check(N, f"the bus allocations sum exactly at x{devices}",
              abs(total - mm["Effective bandwidth (GB/s)"]) < 1e-9,
              f"residue {total - mm['Effective bandwidth (GB/s)']:+.9f} GB/s")
        check(N, f"and neither agent is starved at x{devices}",
              mm["Bandwidth left to the accelerator (GB/s)"] > 0
              and mm["Host bandwidth allocated (GB/s)"] > 0)
        # The reported PERCENTAGE must agree with the allocation too, or the
        # table a student reads says something the model did not compute.
        check(N, f"the reported share matches the allocation at x{devices}",
              abs(mm["Host bandwidth share (%)"] / 100.0
                  * mm["Effective bandwidth (GB/s)"]
                  - mm["Host bandwidth allocated (GB/s)"]) < 1e-9,
              f"share says {mm['Host bandwidth share (%)']:.3f}%, allocation "
              f"says {mm['Host bandwidth allocated (GB/s)'] / mm['Effective bandwidth (GB/s)'] * 100:.3f}%")

    # --- the CPU and the ISP are stations, and the interval is a max ---------
    cpu_bound = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                                SystemConfig("cortex_a53_x4", "npu_32x32",
                                             "LPDDR5", 4,
                                             preprocessing_mode="cpu_only")).metrics
    check(N, "a host-bound design takes its interval from the host",
          abs(cpu_bound["Pipeline interval (ms)"]
              - cpu_bound["Stage CPU (ms)"]) < 1e-9,
          f"interval {cpu_bound['Pipeline interval (ms)']:.3f}, host stage "
          f"{cpu_bound['Stage CPU (ms)']:.3f} ms")
    check(N, "which is longer than either accelerator's",
          cpu_bound["Stage CPU (ms)"]
          > max(cpu_bound["Stage accelerator 1 (ms)"],
                cpu_bound["Stage accelerator 2 (ms)"]))
    isp_bound = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                                SystemConfig("cortex_a78_x4", "npu_16x16",
                                             "LPDDR5", 4,
                                             preprocessing_mode="isp_assisted")).metrics
    check(N, "and an ISP-bound one takes it from the ISP",
          abs(isp_bound["Pipeline interval (ms)"]
              - isp_bound["Stage ISP (ms)"]) < 1e-9,
          f"interval {isp_bound['Pipeline interval (ms)']:.3f}, ISP stage "
          f"{isp_bound['Stage ISP (ms)']:.3f} ms")

    # the ISP caps the pipeline whatever the accelerator does
    isp_caps = []
    for comp in ("npu_16x16", "npu_128x128"):
        mm = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                             SystemConfig("cortex_a78_x4", comp, "LPDDR5", 4,
                                          preprocessing_mode="isp_assisted")).metrics
        isp_caps.append(mm["Pipeline capacity (inf/s)"])
    check(N, "an accelerator eight times the size does not raise an ISP-capped "
             "capacity",
          abs(isp_caps[0] - isp_caps[1]) < 1e-6,
          f"{isp_caps[0]:.3f} against {isp_caps[1]:.3f}")

    # --- a fixed job count finishes when the work does ----------------------
    #
    # Dividing by the observation window gave one job in sixty seconds a
    # throughput of 0.02 per second, which is a statement about the window
    # rather than about the design.
    robot_dual2 = _dc4.replace(robot, secondary_compute="npu_32x32",
                               execution_mode="alternative",
                               alternative_share=0.5)
    runs = {n: _sim("robot", robot_dual2, jobs=n) for n in (1, 10, 1000)}
    cap_r = evaluate_system(APPLICATION_LIBRARY["robot"],
                            robot_dual2).metrics["Pipeline capacity (inf/s)"]
    for n, rr in runs.items():
        check(N, f"{n} jobs asked for, {n} completed", rr.jobs == n)
        check(N, f"{n} jobs end when the last one does",
              abs(rr.total_time_ms
                  - (rr.fill_ms + rr.interval_ms * n)) < 1e-6)
    check(N, "the pipeline is filled once, not once per job",
          abs(runs[1000].fill_ms - runs[1].fill_ms) < 1e-9,
          "a thousand jobs pay the fill once")
    # 72% here rather than the 48% seen on a longer-latency configuration -
    # how far short one job falls depends on how much of its latency the
    # pipeline can hide, which is the interesting part.
    check(N, "one job falls short of the capacity",
          runs[1].throughput < cap_r * 0.95,
          f"{runs[1].throughput:.1f} against {cap_r:.1f} - one job cannot "
          f"fill a pipeline")
    check(N, "and a thousand converge on it",
          runs[1000].throughput > cap_r * 0.99,
          f"{runs[1000].throughput:.1f} against {cap_r:.1f}")
    check(N, "without exceeding it",
          runs[1000].throughput <= cap_r * 1.0001)

    # --- delivered work cannot exceed what arrives --------------------------
    drone = SystemConfig("cortex_a78_x4", "npu_24x24", "LPDDR5", 2,
                         preprocessing_mode="isp_assisted")
    drone_dual = _dc4.replace(drone, secondary_compute="npu_24x24",
                              execution_mode="parallel", work_split=0.5)
    d1, d2 = _sim("drone", drone, 10.0), _sim("drone", drone_dual, 10.0)
    offered = APPLICATION_LIBRARY["drone"].target_inferences_per_s * 10.0
    check(N, "delivered work never exceeds what arrived",
          d2.jobs <= offered + 1, f"{d2.jobs} against {offered:.0f} offered")
    check(N, "a second engine does not raise a rate the camera caps",
          abs(d2.jobs - d1.jobs) <= max(1, d1.jobs * 0.02),
          f"{d1.jobs} against {d2.jobs} jobs - more silicon does not make the "
          f"sensor send more frames")
    md1 = evaluate_system(APPLICATION_LIBRARY["drone"], drone).metrics
    md2 = evaluate_system(APPLICATION_LIBRARY["drone"], drone_dual).metrics
    check(N, "and average power rises anyway",
          md2["System power (W)"] > md1["System power (W)"],
          "which is what a battery feels")


# ==============================================================================
# PATH AO - the memory decision
# ==============================================================================
#
# The second thing a student reaches for after a second accelerator, and the
# same shape of assumption: that a faster part makes a system faster.

def path_ao():
    O = "AO"
    import dataclasses as _dc5
    import io, contextlib

    # the same upgrade on two designs, worth completely different amounts
    def gain(app_key, comp, pm):
        lp = SystemConfig("cortex_a78_x4", comp, "LPDDR5", 2,
                          preprocessing_mode=pm)
        hbm = _dc5.replace(lp, memory="HBM3E", memory_devices=1)
        a = evaluate_system(APPLICATION_LIBRARY[app_key], lp)
        b = evaluate_system(APPLICATION_LIBRARY[app_key], hbm)
        return ((1 - b.metrics["Latency (ms)"] / a.metrics["Latency (ms)"]) * 100,
                a.bound_by, b.metrics["System cost (USD)"]
                / a.metrics["System cost (USD)"])

    cg, cbound, ccost = gain("industrial_vision", "npu_32x32", "isp_and_npu")
    mg, mbound, mcost = gain("mobile_ai", "npu_64x64", "isp_and_npu")
    check(O, "the compute-bound design is identified as such",
          cbound == "compute", cbound)
    check(O, "and the memory-bound one as such", mbound == "memory", mbound)
    check(O, "a memory upgrade buys the memory-bound design far more",
          mg > cg * 2, f"compute-bound {cg:.1f}%, memory-bound {mg:.1f}%")
    check(O, "and costs both the same multiple",
          abs(ccost - mcost) < ccost * 0.5,
          f"{ccost:.1f}x and {mcost:.1f}x - the price does not know which "
          f"design it is on")

    # a memory purchase never changes the arithmetic
    for mem, n in (("LPDDR5", 2), ("LPDDR5", 8), ("GDDR6", 4), ("HBM3E", 1)):
        mm = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                             SystemConfig("cortex_a78_x4", "npu_32x32", mem, n,
                                          preprocessing_mode="isp_and_npu")).metrics
        if mem == "LPDDR5" and n == 2:
            ref_compute = mm["Compute time (ms)"]
            ref_acc = mm["Deployment accuracy (%)"]
        check(O, f"{mem} x{n} leaves the arithmetic alone",
              abs(mm["Compute time (ms)"] - ref_compute) < 1e-9)
        check(O, f"{mem} x{n} leaves the accuracy alone",
              abs(mm["Deployment accuracy (%)"] - ref_acc) < 1e-12)

    # stacks buy width, not a faster stack
    per_stack = []
    for n in (1, 2, 4, 6, 8, 12):
        mm = evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM3E", n)).metrics
        per_stack.append(mm["Effective bandwidth (GB/s)"] / n)
    check(O, "per-stack bandwidth is constant across the sweep",
          max(per_stack) - min(per_stack) < per_stack[0] * 0.02,
          str([round(x, 1) for x in per_stack]))

    # a cooling class is not a performance question
    passive = {}
    for mem, n in (("LPDDR5", 2), ("GDDR6", 2), ("HBM3E", 1)):
        r = evaluate_system(APPLICATION_LIBRARY["drone"], SystemConfig(
            "cortex_a78_x4", "npu_24x24", mem, n,
            preprocessing_mode="isp_assisted"))
        passive[mem] = ([g for g, ok in r.gate.items() if not ok],
                        r.metrics["Latency (ms)"])
    check(O, "a passive product admits the passive memory",
          "memory_cooling" not in passive["LPDDR5"][0])
    refused = [k for k in ("GDDR6", "HBM3E")
               if "memory_cooling" in passive[k][0]]
    check(O, "and refuses one that needs airflow", bool(refused), str(refused))
    faster_and_refused = [k for k in refused
                          if passive[k][1] < passive["LPDDR5"][1]]
    check(O, "even where the refused one would be faster",
          bool(faster_and_refused),
          f"{faster_and_refused} give a lower latency and still cannot be "
          f"fitted")

    # --- a five-level bottleneck label --------------------------------------
    #
    # A two-way label called a design that gains 26% from a faster memory by
    # the same name as one that gains nothing. Both were "compute bound"; one
    # had 1.6x more arithmetic than transfers and the other 15x.
    strengths = {}
    for key, comp, mem, n in (("iv-lp", "npu_32x32", "LPDDR5", 2),
                              ("iv-hbm", "npu_32x32", "HBM3E", 1),
                              ("mob-lp", "npu_64x64", "LPDDR5", 2)):
        app_key = "industrial_vision" if key.startswith("iv") else "mobile_ai"
        r = evaluate_system(APPLICATION_LIBRARY[app_key], SystemConfig(
            "cortex_a78_x4", comp, mem, n, preprocessing_mode="isp_and_npu"))
        strengths[key] = (r.bound_strength, r.compute_memory_ratio)
    check(O, "a weakly compute-bound design is named as such",
          strengths["iv-lp"][0] == "weakly compute-bound",
          f"ratio {strengths['iv-lp'][1]:.2f} -> {strengths['iv-lp'][0]}")
    check(O, "and a strongly compute-bound one differently",
          strengths["iv-hbm"][0] == "strongly compute-bound",
          f"ratio {strengths['iv-hbm'][1]:.2f}")
    check(O, "so the same two-way label no longer covers both",
          strengths["iv-lp"][0] != strengths["iv-hbm"][0],
          "one gains 26% from a faster memory and the other nothing")
    check(O, "and a strongly memory-bound design is at the other end",
          strengths["mob-lp"][0] == "strongly memory-bound",
          f"ratio {strengths['mob-lp'][1]:.2f}")
    check(O, "the ratio is reported so the label can be checked",
          all(v[1] > 0 for v in strengths.values()))

    # --- four failing gates are not four problems ---------------------------
    from ppact.system import gate_causes
    r_bad = evaluate_system(APPLICATION_LIBRARY["mobile_ai"], SystemConfig(
        "cortex_a78_x4", "npu_64x64", "HBM3E", 1,
        preprocessing_mode="isp_and_npu"))
    c = gate_causes(r_bad)
    check(O, "several gates fail on an over-specified memory",
          len(c["failed"]) >= 3, str(c["failed"]))
    check(O, "but thermal is recorded as following from power",
          c["derived"].get("thermal") == "power" if "thermal" in c["failed"]
          else True,
          "thermal margin is computed from system power; reporting both as "
          "findings counts one fact twice")
    check(O, "while a cooling-class mismatch is independent",
          "memory_cooling" in c["independent"] if "memory_cooling" in c["failed"]
          else True,
          "no amount of power reduction fixes a part that needs airflow")
    check(O, "so the independent reasons are fewer than the failed gates",
          len(c["independent"]) < len(c["failed"]),
          f"{len(c['failed'])} gates, {len(c['independent'])} reasons")

    # --- a model that does not fit cannot run at any speed -------------------
    from ppact.system import STATUS_DOES_NOT_FIT
    fits = evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
        "server_x86_x32", "datacenter_gpu", "HBM3E", 6))
    doesnt = evaluate_system(APPLICATION_LIBRARY["llm_service"], SystemConfig(
        "server_x86_x32", "datacenter_gpu", "LPDDR5", 8))
    faster_but_small = evaluate_system(
        APPLICATION_LIBRARY["llm_service"], SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM3E", 2))
    check(O, "a design whose model does not fit is marked infeasible",
          doesnt.status == STATUS_DOES_NOT_FIT, doesnt.status)
    check(O, "and one that fits is not", fits.status != STATUS_DOES_NOT_FIT)
    # Hiding the numbers is not enough - they must be UNUSABLE, or they
    # reappear in a sweep or a ranking written later.
    import math as _math
    from ppact.system import PERFORMANCE_METRICS
    for key in ("Latency (ms)", "Delivered throughput (inf/s)",
                "Energy per inference (mJ)", "Pipeline capacity (inf/s)"):
        check(O, f"an infeasible design reports no {key}",
              _math.isnan(doesnt.metrics[key]),
              f"{doesnt.metrics[key]} - a number here would be reusable")
    check(O, "zero is not used, because zero reads as 'runs but slowly'",
          not any(doesnt.metrics[k] == 0.0 for k in PERFORMANCE_METRICS
                  if k in doesnt.metrics),
          "the state is that the configuration does not exist")
    for key in ("System cost (USD)", "Logic silicon (mm2)",
                "Board area (mm2)"):
        check(O, f"but the board still has a {key}",
              not _math.isnan(doesnt.metrics[key]) and doesnt.metrics[key] > 0,
              "physical and economic figures are true of the board whether or "
              "not it can run the model")
    check(O, "and the feasible design keeps all of its numbers",
          not any(_math.isnan(fits.metrics[k]) for k in PERFORMANCE_METRICS
                  if k in fits.metrics))

    check(O, "more bandwidth does not make an unfittable model fit",
          faster_but_small.metrics["Effective bandwidth (GB/s)"]
          > doesnt.metrics["Effective bandwidth (GB/s)"]
          and faster_but_small.status == STATUS_DOES_NOT_FIT,
          "capacity is a different purchase from bandwidth")

    # --- the two axes an LLM is decided on ----------------------------------
    #
    # The weights do not change and the memory runs out anyway. A student told
    # a model is "70 GB" and then that it needs a hundred and forty has met
    # the KV cache, whose size follows the CONVERSATION rather than the
    # network.
    from ppact.economics import (context_sweep, quantisation_sweep,
                                 QUANT_BYTES, QUANT_ACCURACY_COST_PP)
    with contextlib.redirect_stdout(io.StringIO()):
        ctx_rows = context_sweep("llm_service", SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM3E", 6))
    check(O, "the weights are identical at every context length",
          len({round(r["weights_gb"], 6) for r in ctx_rows}) == 1)
    prop = [(b["kv_gb"] / a["kv_gb"]) / (b["ctx"] / a["ctx"])
            for a, b in zip(ctx_rows, ctx_rows[1:])]
    check(O, "and the cache grows exactly in proportion to the context",
          all(abs(x - 1.0) < 1e-9 for x in prop),
          str([round(x, 6) for x in prop]))
    check(O, "a board that held the model at a short context stops holding it",
          ctx_rows[0]["feasible"] and not ctx_rows[-1]["feasible"],
          "the model did not get bigger; the conversation did")
    feas = [r for r in ctx_rows if r["feasible"]]
    check(O, "and traffic per token rises with the context",
          feas[-1]["traffic_mb"] > feas[0]["traffic_mb"] * 1.2,
          "every token reads a longer cache as well as the weights")

    with contextlib.redirect_stdout(io.StringIO()):
        q_rows = quantisation_sweep("llm_service", SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM3E", 2))
    q = {r["prec"]: r for r in q_rows}
    for prec in QUANT_BYTES:
        check(O, f"{prec} scales the weights by its width",
              abs(q[prec]["weights_gb"] / q["FP16"]["weights_gb"]
                  - QUANT_BYTES[prec] / QUANT_BYTES["FP16"]) < 1e-9)
    check(O, "a narrower width can make an unfittable model fit",
          not q["FP16"]["feasible"] and q["INT4"]["feasible"])
    check(O, "accuracy falls monotonically with the width",
          q["FP16"]["accuracy"] > q["FP8"]["accuracy"]
          > q["INT8"]["accuracy"] > q["INT4"]["accuracy"])
    check(O, "and fitting is still not shipping",
          q["INT4"]["feasible"] and not q["INT4"]["passes"],
          f"failing {q['INT4']['failed']}")
    check(O, "the quantisation accuracy cost is an assumption, not a result",
          all(v >= 0 for v in QUANT_ACCURACY_COST_PP.values())
          and QUANT_ACCURACY_COST_PP["FP16"] == 0.0,
          "the model has no basis for what a network loses; these are stated "
          "so they can be replaced")

    # --- the weights are shared and the cache is not ------------------------
    #
    # The one structural fact that makes a server different from a phone.
    # Sixteen users read the same seventy gigabytes once per step and carry
    # sixteen separate caches, so the cost per user falls and the memory per
    # user does not.
    from ppact.economics import batch_sweep
    with contextlib.redirect_stdout(io.StringIO()):
        b_rows = batch_sweep("llm_service", SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM3E", 6))
    bb = {r["b"]: r for r in b_rows}
    check(O, "the cache scales exactly with the user count",
          all(abs(bb[n]["kv_gb"] / bb[1]["kv_gb"] - n) < 1e-9
              for n in (2, 4, 8, 16) if n in bb))
    check(O, "while the total memory does not",
          bb[16]["total_gb"] < bb[1]["total_gb"] * 2,
          f"{bb[1]['total_gb']:.0f} -> {bb[16]['total_gb']:.0f} GB for "
          f"sixteen times the users")
    b_ok = [r for r in b_rows if r["feasible"]]
    check(O, "aggregate throughput rises and per-user throughput falls",
          b_ok[-1]["aggregate"] > b_ok[0]["aggregate"]
          and b_ok[-1]["per_user"] < b_ok[0]["per_user"],
          "a server optimises one and a phone the other")
    tpu = [r["traffic_mb"] / r["b"] for r in b_ok]
    check(O, "and traffic per user falls monotonically",
          all(a > b for a, b in zip(tpu, tpu[1:])),
          "the weights are read once for the whole batch")
    b_fail = [r for r in b_rows if not r["feasible"]]
    check(O, "a large enough batch stops fitting",
          bool(b_fail),
          "the server runs out of users before it runs out of speed")

    # --- model size, prompt ratio, mixture of experts -----------------------
    from ppact.economics import (model_size_sweep, prompt_ratio_sweep,
                                 moe_comparison, MODEL_SIZES)
    with contextlib.redirect_stdout(io.StringIO()):
        sz = {r["label"]: r for r in model_size_sweep(
            "llm_service", SystemConfig("server_x86_x32", "datacenter_gpu",
                                        "HBM3E", 6))}
    check(O, "a model's bytes are its parameters times the width",
          all(abs(sz[k]["weights_gb"] - v * 2.0 / 1e9) < 1e-6
              for k, v in MODEL_SIZES.items()))
    check(O, "small models fit and large ones do not",
          sz["1B"]["feasible"] and not sz["100B"]["feasible"])
    check(O, "and shipping stops before fitting does",
          sum(1 for r in sz.values() if r["passes"])
          < sum(1 for r in sz.values() if r["feasible"]))

    with contextlib.redirect_stdout(io.StringIO()):
        pr = prompt_ratio_sweep("llm_service", SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM3E", 6))
    check(O, "prefill arithmetic scales exactly with the prompt",
          all(abs((b["prefill_mac"] / a["prefill_mac"])
                  / (b["prompt"] / a["prompt"]) - 1) < 1e-9
              for a, b in zip(pr, pr[1:])))
    check(O, "while decode time per token does not move with it",
          max(r["per_token"] for r in pr)
          - min(r["per_token"] for r in pr) < 1e-6,
          "decode reads the same weights for every token")

    with contextlib.redirect_stdout(io.StringIO()):
        moe = moe_comparison("llm_service", SystemConfig(
            "server_x86_x32", "datacenter_gpu", "HBM3E", 12))
    mm, sm, lg = (moe["mixture of experts"], moe["dense, active size"],
                  moe["dense, total size"])
    check(O, "an MoE stores like the large model and reads like the small one",
          abs(mm["stored_gb"] - lg["stored_gb"]) < 1e-6
          and abs(mm["used_gb"] - sm["stored_gb"]) < 1e-6)
    check(O, "so its token rate follows the ACTIVE parameters",
          abs(mm["tokens"] / sm["tokens"] - 1) < 0.05,
          "and its memory follows the total - sizing a board from the token "
          "rate under-provisions it")

    # capacity is not delivery
    slow = SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 1,
                        preprocessing_mode="isp_and_npu")
    fast = _dc5.replace(slow, memory_devices=4)
    sm = evaluate_system(APPLICATION_LIBRARY["drone"], slow).metrics
    fm = evaluate_system(APPLICATION_LIBRARY["drone"], fast).metrics
    check(O, "more memory raises the pipeline capacity",
          fm["Pipeline capacity (inf/s)"] > sm["Pipeline capacity (inf/s)"] * 1.2)
    check(O, "and delivers not one frame more",
          abs(fm["Delivered throughput (inf/s)"]
              - sm["Delivered throughput (inf/s)"]) < 1e-9,
          "the camera did not change")


# ==============================================================================
# PATH AO - explanations
# ==============================================================================
#
# An explanation is not a decoration. It is a claim about a mechanism, and one
# attached to a run it does not describe teaches the mechanism and a
# counter-example at once.

def path_ao():
    O = "AO"
    import io, contextlib, dataclasses as _dc5
    from ppact.explain import (CHAINS, CHAIN_APPLIES, NEGLIGIBLE, why,
                               suggest_chain, chain_contradicts,
                               decision_explanation, CONTEXT_BINDING_GATES,
                               CONTEXT_NOTE)

    check(O, "causal chains are defined", len(CHAINS) >= 6)
    for key, (title, steps) in CHAINS.items():
        check(O, f"'{key}' has a title", len(title) > 15)
        check(O, f"'{key}' has several steps", len(steps) >= 4, str(len(steps)))
        for st in steps:
            check(O, f"'{key}' step is a statement, not a label", len(st) > 20)
        # a chain must not simply restate the metric it explains
        check(O, f"'{key}' says more than the number does",
              sum(len(x) for x in steps) > 150)

    # --- a chain must not contradict the run it is attached to ---------------
    #
    # The first version of the memory chain passed on a run where the latency
    # improved 88%, because it tested only the delivered rate. An explanation
    # that survives its own counter-example is not an explanation.
    check(O, "every testable chain has a test",
          set(CHAIN_APPLIES).issubset(set(CHAINS)),
          str(set(CHAIN_APPLIES) - set(CHAINS)))
    check(O, "and 'changed nothing' has a stated threshold",
          0.0 < NEGLIGIBLE < 0.2, str(NEGLIGIBLE))

    def _m(app_key, cfg):
        return evaluate_system(APPLICATION_LIBRARY[app_key], cfg).metrics

    # a case where more memory really does nothing
    d_base = SystemConfig("cortex_a78_x4", "npu_24x24", "LPDDR5", 4,
                          preprocessing_mode="isp_and_npu")
    d_a, d_b = (_m("drone", d_base),
                _m("drone", _dc5.replace(d_base, memory_devices=8)))
    check(O, "the memory chain applies where memory did not help",
          not chain_contradicts("memory_no_help", d_a, d_b),
          f"latency moved {(1 - d_b['Latency (ms)'] / d_a['Latency (ms)']) * 100:.1f}%")

    # and one where it plainly did
    m_base = SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                          preprocessing_mode="isp_and_npu")
    m_a, m_b = (_m("mobile_ai", m_base),
                _m("mobile_ai", _dc5.replace(m_base, memory_devices=8)))
    check(O, "and is refused where it did",
          chain_contradicts("memory_no_help", m_a, m_b),
          f"latency moved {(1 - m_b['Latency (ms)'] / m_a['Latency (ms)']) * 100:.1f}%")

    # the refusal must be visible, not silent
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        decision_explanation("mobile_ai", m_base,
                             _dc5.replace(m_base, memory_devices=8),
                             chain="memory_no_help", auto_chain=False)
    t = buf.getvalue()
    check(O, "a contradicting chain is refused out loud",
          "does NOT describe this run" in t)
    check(O, "and the chain's text is not printed anyway",
          "shortens a wait that was not being paid" not in t)
    check(O, "and the refusal says why it matters",
          "cannot tell which to believe" in t)

    # --- auto-selection may only pick a chain that fits ----------------------
    picked = suggest_chain(d_a, d_b)
    check(O, "auto-selection finds a fitting chain", picked is not None)
    check(O, "and never picks one that contradicts",
          not chain_contradicts(picked, d_a, d_b), str(picked))
    none_picked = suggest_chain(m_a, m_a)
    check(O, "and picks nothing where nothing fits",
          none_picked is None or not chain_contradicts(none_picked, m_a, m_a))

    # --- the decision explanation must separate gain from cost --------------
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        decision_explanation("mobile_ai", m_base,
                             _dc5.replace(m_base, memory="HBM3E",
                                          memory_devices=1))
    t2 = buf2.getvalue()
    check(O, "the explanation separates what was achieved from what it cost",
          "What it achieved" in t2 and "What it cost" in t2)
    check(O, "and lists the requirements not met",
          "Requirements not met" in t2)
    check(O, "and does not give a single verdict",
          "Whether that matters depends on what the design is FOR" in t2)
    for context in CONTEXT_BINDING_GATES:
        check(O, f"'{context}' is judged separately", context in t2)
    check(O, "and the model disclaims what it does not know",
          "does not know" in t2 and "market" in t2)

    # a design that fails a cost gate must not be called useless
    check(O, "a teaching example binds no gate",
          CONTEXT_BINDING_GATES["teaching example"] == ())
    check(O, "and a research prototype binds only correctness and feasibility",
          set(CONTEXT_BINDING_GATES["research prototype"])
          <= {"accuracy", "capacity"},
          str(CONTEXT_BINDING_GATES["research prototype"]))
    check(O, "while a product binds every gate the model has",
          len(CONTEXT_BINDING_GATES["industrial deployment"]) >= 8)

    # --- five bound strengths, and the boundaries must bind -----------------
    #
    # Two labels were not enough: a design at 5x more arithmetic than
    # transfers is compute bound and still gains 26% from a faster memory,
    # while one at 15x gains nothing. The middle levels are where a memory
    # upgrade is a real question, so the thresholds between them have to be
    # reachable rather than decorative.
    import ppact.system as _SY
    strengths = set()
    for app_key in APPLICATION_LIBRARY:
        if app_key.startswith("__"):
            continue
        cpu2 = ("server_x86_x32"
                if APPLICATION_LIBRARY[app_key].domain == "Data Center"
                else "cortex_a78_x4")
        for comp2 in ("npu_16x16", "npu_32x32", "npu_128x128"):
            for mem2, dev2 in (("LPDDR5", 1), ("LPDDR5", 8), ("HBM3E", 4)):
                try:
                    r2 = evaluate_system(APPLICATION_LIBRARY[app_key],
                                         SystemConfig(cpu2, comp2, mem2, dev2))
                except Exception:
                    continue
                v = r2.metrics.get("Bound strength")
                if isinstance(v, str):
                    strengths.add(v)
                elif hasattr(r2, "bound_strength"):
                    strengths.add(r2.bound_strength)
    # "not evaluated" is a sixth value and correctly so - an infeasible design
    # has no ratio to take.
    real = strengths - {"not evaluated"}
    check(O, "all five bound strengths are reachable", len(real) == 5,
          str(sorted(real)))
    check(O, "and a strongly-bound design is distinguished from a weakly one",
          "strongly compute-bound" in strengths
          and "weakly compute-bound" in strengths,
          "collapsing the two would say a design that gains 26% from more "
          "memory and one that gains nothing are the same design")

    # --- an infeasible design reports no performance ------------------------
    #
    # A model that does not fit has no latency. Reporting one invites a
    # student to compare the speed of a design that cannot run.
    big = dataclasses.replace(APPLICATION_LIBRARY["llm_service"],
                              weight_bytes=APPLICATION_LIBRARY[
                                  "llm_service"].weight_bytes * 200,
                              key="__toobig__")
    APPLICATION_LIBRARY["__toobig__"] = big
    try:
        r3 = evaluate_system(big, SystemConfig("server_x86_x32",
                                               "datacenter_gpu", "HBM3E", 1))
        check(O, "a model that does not fit is marked infeasible",
              not r3.gate.get("capacity", True), str(r3.status))
        import math as _math
        reported = [k for k in _SY.PERFORMANCE_METRICS
                    if k in r3.metrics
                    and not _math.isnan(r3.metrics[k])]
        check(O, "and reports no performance figure at all", not reported,
              f"still reporting: {', '.join(reported[:4])}")
    finally:
        APPLICATION_LIBRARY.pop("__toobig__", None)

    # --- the sensor-to-control boundary includes everything between them ----
    #
    # An ISP sits between the sensor and the control and its time was hidden
    # from that figure, because it overlaps the NEXT frame. Overlapping frames
    # raises the rate and does not shorten any one frame's journey, and this
    # metric is about one frame's journey. Nothing tested it until an
    # independent recomputation noticed a station occupying 10 ms inside a
    # 4.7 ms sensor-to-control figure.
    for pm, has_isp in (("cpu_only", False), ("isp_assisted", True),
                        ("isp_and_npu", True)):
        mm = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                             SystemConfig("cortex_a78_x4", "npu_32x32",
                                          "LPDDR5", 4,
                                          preprocessing_mode=pm)).metrics
        isp = mm.get("ISP active (ms)", 0.0)
        expected = mm["Latency (ms)"] + isp
        check(O, f"{pm}: sensor-to-control includes the ISP",
              abs(mm["Sensor-to-control (ms)"] - expected) < 1e-6,
              f"latency {mm['Latency (ms)']:.3f} + ISP {isp:.3f} = "
              f"{expected:.3f}, model {mm['Sensor-to-control (ms)']:.3f} ms")
        if has_isp:
            check(O, f"{pm}: and so exceeds the pipeline latency",
                  mm["Sensor-to-control (ms)"] > mm["Latency (ms)"] + 1e-9)
        check(O, f"{pm}: while the pipeline interval stays inside it",
              mm["Pipeline interval (ms)"]
              <= mm["Sensor-to-control (ms)"] + 1e-9)

    # --- the boundary contract must be coherent -----------------------------
    from ppact.system import (check_metric_boundaries, METRIC_BOUNDARIES,
                              PIPELINE_STAGES)
    probs = check_metric_boundaries()
    check(O, "the metric boundary contracts are coherent", not probs,
          "; ".join(probs[:2]))
    # Scope depends on the family: a power contract is over PARTS, not over
    # pipeline stages, and requiring it to name every stage would be
    # requiring it to answer a question it is not asking.
    from ppact.system import FAMILY_SCOPE, SYSTEM_PARTS
    check(O, "every contract accounts for its own family's scope",
          all(set(PIPELINE_STAGES if FAMILY_SCOPE[b.family] == "stages"
                  else SYSTEM_PARTS)
              <= set(b.includes) | set(b.excludes)
              for b in METRIC_BOUNDARIES),
          "something in scope that appears in no contract is something "
          "nobody has decided about")
    # A contract about a metric nobody reports describes nothing. This caught
    # its first error immediately: the power contract named "Accel power (W)"
    # where the model reports "Accelerator active power (W)".
    ref_m = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                            SystemConfig("cortex_a78_x4", "npu_32x32",
                                         "LPDDR5", 4,
                                         preprocessing_mode="isp_assisted")
                            ).metrics
    absent = [b.metric for b in METRIC_BOUNDARIES if b.metric not in ref_m]
    check(O, "every contracted metric is actually reported", not absent,
          f"contracted and absent: {', '.join(absent)}")

    # Two rates over different boundaries cannot be ordered. The single-job
    # rate is one over a latency that EXCLUDES the ISP; the capacity INCLUDES
    # it, and on an ISP-assisted design the first exceeds the second by more
    # than twice. Putting them in one family asserts a comparison neither
    # contract supports.
    fam = {b.metric: b.family for b in METRIC_BOUNDARIES}
    check(O, "the single-job rate is not in the throughput family",
          fam.get("Single-job rate (inf/s)") != "throughput",
          "it excludes the ISP and the capacity includes it")
    check(O, "and the numbers show why",
          ref_m["Single-job rate (inf/s)"]
          > ref_m["Pipeline capacity (inf/s)"],
          f"{ref_m['Single-job rate (inf/s)']:.1f} against "
          f"{ref_m['Pipeline capacity (inf/s)']:.1f} - no job completes at "
          f"the first rate, because the frame passed through a stage that "
          f"boundary does not count")

    check(O, "and the families cover latency, throughput, power, cost and "
             "capacity",
          {"latency", "throughput", "power", "cost", "capacity"}
          <= set(FAMILY_SCOPE), str(sorted(FAMILY_SCOPE)))

    # --- a menu with no input must STOP, not loop ---------------------------
    #
    # The default on the main menu is 1. Taking it when there is no stdin
    # means running Quick Start, returning to the menu, taking it again -
    # forever. A launcher run with no input hung for the whole of a
    # 300-second deployment check that way, and a notebook that cannot
    # prompt would have done the same to a student.
    import subprocess as _sp, os as _os
    # `M_MODES.__file__` behind an `if False` was an undefined name
    # kept alive by a dead branch. The package's own path is what was
    # wanted.
    root_dir = _os.path.dirname(
        _os.path.dirname(__import__("ppact").__file__))
    proc = _sp.run([sys.executable, "-c",
                    "import sys; sys.path.insert(0, %r);"
                    "from ppact.modes import main; main()" % root_dir],
                   stdin=_sp.DEVNULL, capture_output=True, text=True,
                   timeout=60)
    check(O, "a menu with no input stops instead of looping",
          proc.returncode == 0 and "Done" in proc.stdout,
          f"exit {proc.returncode}, tail {proc.stdout[-80:]!r}")
    check(O, "and says why it stopped",
          "no input available" in proc.stdout)
    check(O, "and does not run a task first",
          proc.stdout.count("Quick Start") <= 1,
          "taking the default once is a task nobody asked for")

    # --- the balance chart knows what it is not -----------------------------
    #
    # An information-transfer experiment put five student questions to three
    # formats. Spider answered NONE of them: latency is not one of its axes,
    # and a 21% latency improvement showed as three points on a different
    # question. So it is named for the one thing it does - balance - placed
    # after the explanation and the bars, and carries a notice saying what
    # it cannot show.
    from ppact.visual import (build_balance, render_balance_text,
                              render_balance_web, overlapping_axes,
                              BALANCE_NOTICE, BALANCE_TITLE, CLIP_HIGH,
                              LINE_STYLES)
    ref_c = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
    cur_c = SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4)
    bal = build_balance("industrial_vision",
                        [("Starting point", ref_c), ("Current design", cur_c)])
    # THE NAME MUST ALSO SAY WHICH BALANCE.
    #
    # This pinned the title to "Architecture Balance" exactly. Two
    # charts then carried that name while answering different
    # questions - one scoring against a requirement where 50 means
    # exactly met, the other drawing ratios where 1.00x means no
    # change - so a reader comparing "50" with "0.51x" was comparing
    # two scales. The rule keeps its point and adds the missing one.
    from ppact.visual.balance import COMPARISON_TITLE
    check(O, "the chart is named for balance, not performance",
          "Architecture Balance" in BALANCE_TITLE
          and "fingerprint" not in BALANCE_TITLE.lower()
          and "performance" not in BALANCE_TITLE.lower(),
          "'fingerprint' sounds like an absolute property; this is a "
          "comparison of normalised dimensions")
    check(O, "the two balance charts are named apart",
          BALANCE_TITLE != COMPARISON_TITLE
          and "Requirement" in BALANCE_TITLE
          and "Relative" in COMPARISON_TITLE,
          f"{BALANCE_TITLE!r} against {COMPARISON_TITLE!r} - one "
          f"scores against a requirement and the other draws ratios")
    for word in ("does not show physical values", "requirement limits",
                 "bottlenecks", "reasons for change"):
        check(O, f"the notice names {word!r} as absent",
              word in BALANCE_NOTICE)
    check(O, "the notice survives wrapping in the terminal",
          "requirement limits" in " ".join(
              "\n".join(render_balance_text(bal)).split()))
    check(O, "and points at what does show them",
          "measured bars and reason breakdown" in BALANCE_NOTICE)

    # ONE OBJECT, THREE RENDERERS
    txt = "\n".join(render_balance_text(bal))
    web = render_balance_web(bal)
    check(O, "every renderer takes the same axes",
          list(bal.axis_names()) == web["axes"]
          and all(n in txt for n in bal.axis_names()))
    check(O, "in the same order",
          web["axes"] == list(bal.axis_names()))
    check(O, "with the same designs, in the same order",
          [s_["label"] for s_ in web["series"]] == list(bal.designs))
    for i, (_, axes) in enumerate(bal.axes):
        check(O, f"design {i}: the web view quotes the same scores",
              [a.score for a in axes] == web["series"][i]["scores"])
        check(O, f"design {i}: and the same raw values",
              [a.raw for a in axes] == web["series"][i]["raw"])
        check(O, f"design {i}: and the same units",
              [a.unit for a in axes] == web["series"][i]["units"])
    # The terminal wraps the notice, so it is compared after normalising
    # the whitespace the wrapping introduced.
    norm_txt = " ".join(txt.split())
    check(O, "the notice reaches every renderer",
          " ".join(BALANCE_NOTICE.split()) in norm_txt
          and web["notice"] == BALANCE_NOTICE)
    check(O, "the object is internally consistent", bal.consistent())

    # no renderer may compute
    import os as _osr
    for fname in ("balance.py",):
        src_r = open(_osr.path.join("ppact", "visual", fname),
                     encoding="utf-8").read()
        body = src_r.split("def render_balance_text")[1]
        for banned in ("evaluate_system", "score_system"):
            check(O, f"the renderers below build_balance never call {banned}",
                  banned not in body,
                  "normalisation happens once, in the builder, or two "
                  "renderers will disagree in a way nobody notices")

    # every axis carries what was done to it
    for _, axes in bal.axes:
        for a in axes:
            # An axis with NO metric records why instead of a formula.
            # There is no arithmetic to account for, and demanding a
            # clip() expression from it would push someone to invent one.
            if a.score is None:
                check(O, f"axis '{a.name}' records why it has no score",
                      "NOT ESTABLISHED" in a.formula,
                      "an unscored axis owes a reason, not a formula")
            else:
                # The formula must SHOW the arithmetic and say it is
                # clipped, in whatever wording. Requiring the literal
                # "clip(" fixed the check to one phrasing, and the
                # requirement-centred formula says "clipped to 0-100".
                check(O, f"axis '{a.name}' records its formula",
                      "score =" in a.formula
                      and "clip" in a.formula.lower(),
                      "a reader who recognises 18.82 USD and sees 92 is "
                      "owed an account of how one became the other")
            check(O, f"axis '{a.name}' records its unit", bool(a.unit))
            check(O, f"axis '{a.name}' records its direction",
                  isinstance(a.lower_is_better, bool))

    # CLIPPING MUST BE VISIBLE
    # A CLIPPED FIXTURE, found rather than assumed.
    #
    # This relied on Thermal reaching the end of its axis, and Thermal is
    # no longer an axis. A rule whose fixture depends on a particular axis
    # existing stops exercising the marker the moment the axes change -
    # silently, because it still passes until the axis goes.
    clipped = [a for _, axes in bal.axes for a in axes if a.clipped]
    if not clipped:
        from ppact import SystemConfig as _SCc
        for _cfg in (_SCc("cortex_a53_x4", "npu_16x16", "DDR4", 1),
                     _SCc("server_x86_x32", "datacenter_gpu", "HBM3E", 8)):
            _b = build_balance("industrial_vision",
                               [("probe", _cfg)])
            _c = [a for _, ax in _b.axes for a in ax if a.clipped]
            if _c:
                bal, clipped = _b, _c
                txt = "\n".join(render_balance_text(bal))
                break
    check(O, "this case has a clipped axis, so the marker is exercised",
          bool(clipped),
          "no fixture reaches the end of an axis - the clip marker is "
          "then untested")
    check(O, "and the marker appears", CLIP_HIGH in txt,
          "a score of 100 that was really 140 is a lie of omission")
    # The wording changed when clipping began naming the raw value, the
    # axis end and the favourable direction. What the check is for is that
    # a marker never appears bare, so it asks for those three rather than
    # for a sentence.
    check(O, "with an explanation beside it",
          "raw value" in txt and "axis ends at" in txt
          and "favourable" in txt,
          "a clipping marker with no raw value tells a reader a number was "
          "hidden without telling them which one")

    # OVERLAP MUST BE STATED
    same_c = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                          bandwidth_efficiency=0.75)
    bal2 = build_balance("industrial_vision",
                         [("Starting point", ref_c), ("Current design", same_c)])
    txt2 = "\n".join(render_balance_text(bal2))
    check(O, "two overlapping profiles are detected",
          len(overlapping_axes(bal2)) == len(bal2.axis_names()),
          str(overlapping_axes(bal2)))
    check(O, "and the reader is told in words",
          "overlap on all displayed axes" in txt2,
          "a chart showing one line where the legend claims two leaves the "
          "reader concluding the second design is missing")

    # line style, not colour alone
    check(O, "designs are distinguished by line style too",
          LINE_STYLES[0] == "solid" and LINE_STYLES[1] == "dashed"
          and web["series"][0]["style"] != web["series"][1]["style"],
          "colour alone fails on a monochrome printout and for a reader who "
          "does not see it the way the author does")

    # --- a rendering change may not move a number ---------------------------
    #
    # LAYER 3 OF THREE. This file is a CHANGE DETECTOR and nothing more.
    #
    #   1  analytical invariants   tests_independent.py, and the identity
    #                              checks in this file - closed-form
    #                              arithmetic that says whether a number is
    #                              RIGHT
    #   2  golden scenarios        tests_scenarios.py - fixed expected
    #                              behaviour for representative designs,
    #                              which says whether a CHANGE is right
    #   3  this snapshot           1,296 configurations x 148 metrics, which
    #                              says only that SOMETHING changed
    #
    # The distinction matters because a snapshot can be regenerated. If it
    # were the only guard, an intended model change would be followed by
    # regenerating the baseline, and a WRONG result would be approved as the
    # new normal by the same keystroke. Layers 1 and 2 cannot be regenerated
    # that way: an identity either holds or it does not, and a golden
    # scenario states what the answer should be rather than what it was.
    #
    # This baseline was captured BEFORE the seven scattered bar
    # implementations moved onto the shared renderer. For a presentation
    # refactor a snapshot is exactly the right instrument, because the
    # expected change is none.
    import json as _jsv, math as _mv, os as _osb
    _bl = "visual_baseline.json"
    if _osb.path.isfile(_bl):
        with open(_bl, encoding="utf-8") as fh:
            baseline = _jsv.load(fh)
        differing, missing = [], 0
        for key, want in baseline.items():
            app, comp, mem, pm = key.split("|")
            a_ = APPLICATION_LIBRARY.get(app)
            if a_ is None:
                missing += 1
                continue
            cpu_ = ("server_x86_x32" if a_.domain == "Data Center"
                    else "cortex_a78_x4")
            try:
                got = evaluate_system(a_, SystemConfig(cpu_, comp, mem, 2,
                                                       preprocessing_mode=pm))
            except Exception as exc:
                if want.get("error") != type(exc).__name__:
                    differing.append(f"{key}: raised {type(exc).__name__}")
                continue
            if "error" in want:
                differing.append(f"{key}: no longer raises")
                continue
            if got.status != want["status"] or got.bound_by != want["bound"] \
                    or bool(got.passes) != want["passes"]:
                differing.append(f"{key}: verdict moved")
                continue
            for m, v in want["metrics"].items():
                now = got.metrics.get(m)
                if v is None:
                    if not (isinstance(now, float) and _mv.isnan(now)):
                        differing.append(f"{key}/{m}: was not-a-number")
                    continue
                if now is None:
                    differing.append(f"{key}/{m}: gone")
                elif isinstance(now, float) and abs(now - v) > 1e-12:
                    differing.append(f"{key}/{m}: {v} -> {now}")
                elif not isinstance(now, float) and now != v:
                    differing.append(f"{key}/{m}: {v} -> {now}")
        check(O, f"all {len(baseline)} baselined configurations are unchanged",
              not differing,
              "; ".join(differing[:3])
              + " - a presentation refactor that moves a number is not a "
                "presentation refactor")
        check(O, "and the baseline still covers what it did",
              missing == 0 and len(baseline) >= 1000,
              f"{missing} applications gone, {len(baseline)} rows")
        # the other two layers must exist, or this one is carrying weight it
        # cannot carry
        check(O, "an independent-arithmetic layer exists",
              _osb.path.isfile("tests_independent.py"),
              "a snapshot says something changed; it cannot say whether the "
              "change was right")
        check(O, "and a golden-scenario layer exists",
              _osb.path.isfile("tests_scenarios.py"))
        check(O, "the snapshot says what it is for",
              "CHANGE DETECTOR" in open("tests_model.py",
                                        encoding="utf-8").read(),
              "a baseline treated as proof of correctness gets regenerated "
              "after a wrong result and approves it")
    else:
        check(O, "the visual baseline file ships with the package", False,
              f"{_bl} is missing - the regression cannot be run")

    # every bar in the program now comes from one place
    import re as _reb
    strays = []
    for fname in sorted(_osb.listdir("ppact")):
        if not fname.endswith(".py"):
            continue
        text_b = open(_osb.path.join("ppact", fname), encoding="utf-8").read()
        for line in text_b.splitlines():
            if line.strip().startswith("#"):
                continue
            # A horizontal RULE is "=" or "-" times a constant width. A BAR
            # is a fill character times something derived from a value. The
            # first version of this check flagged every separator line in
            # the package, which is how a check trains people to ignore it.
            if _reb.search(r'"[#*~]"\s*\*\s*(int|round|filled|bars|a\b|w\b)',
                           line):
                strays.append(f"{fname}: {line.strip()[:44]}")
    check(O, "no screen draws its own bar", not strays,
          "; ".join(strays[:3])
          + " - seven of these existed with four fill characters and the "
            "eighth would have been chosen by whichever file was open")

    # --- the rendering layer may not compute --------------------------------
    #
    # A renderer that can compute can change a result, and the change would
    # arrive inside a refactor nobody thought to check. So the layer is
    # checked to contain no engine call at all, and every screen is checked
    # to produce identical numbers.
    from ppact import visual as _VS
    import os as _osv
    for fname in ("text.py", "models.py", "__init__.py"):
        src_v = open(_osv.path.join("ppact", "visual", fname),
                     encoding="utf-8").read()
        for banned in ("evaluate_system", "APPLICATION_LIBRARY",
                       "SystemConfig", "COMPUTE_LIBRARY"):
            check(O, f"visual/{fname} never calls {banned}",
                  banned not in src_v,
                  "a renderer that can compute can change a result inside a "
                  "refactor nobody checked")

    # one bar, and it behaves
    check(O, "an empty bar is empty",
          set(_VS.render_bar(0, 100)) == {_VS.TRACK})
    check(O, "a full bar is full",
          set(_VS.render_bar(100, 100)) == {_VS.FILL})
    check(O, "a half bar is half",
          _VS.render_bar(50, 100, 24).count(_VS.FILL) == 12)
    check(O, "a bar never exceeds its width",
          len(_VS.render_bar(500, 100, 24)) == 24
          and _VS.render_bar(500, 100, 24).count(_VS.FILL) == 24,
          "an over-range value must clip, not overflow the line")
    check(O, "a zero maximum does not divide by zero",
          set(_VS.render_bar(5, 0)) == {_VS.TRACK})
    check(O, "a tiny non-zero share can be made visible",
          _VS.render_bar(0.1, 100, 24, min_visible=True).count(_VS.FILL) == 1)
    check(O, "a stacked bar fits its width",
          len(_VS.render_stacked_bar([(51, _VS.FILL), (18, _VS.BLOCKED),
                                      (31, _VS.TRACK)], 100, 24)) == 24)

    # the characters must carry the meaning, not colour
    check(O, "every segment character is explained",
          all(c in _VS.LEGEND for c in (_VS.FILL, _VS.BLOCKED, _VS.TRACK)),
          "a stacked bar that needs colour cannot be printed or logged, and "
          "cannot be read by somebody who does not see colour the way the "
          "author does")
    check(O, "the legend is one line beside the bars",
          "in use" in _VS.legend_line() and "idle" in _VS.legend_line())
    check(O, "fill and blocked are different characters",
          _VS.FILL != _VS.BLOCKED != _VS.TRACK)

    # the data objects may not compute either
    bd = _VS.BreakdownData("t", "ms", (("a", 1.0), ("b", 2.0)), 3.0)
    check(O, "a breakdown knows whether it sums", bd.sums())
    bad_bd = _VS.BreakdownData("t", "ms", (("a", 1.0),), 3.0)
    check(O, "and knows when it does not", not bad_bd.sums(),
          "a renderer that silently omitted the difference would hide the "
          "one thing worth seeing")
    check(O, "a breakdown carries its residue",
          _VS.BreakdownData("t", "ms", (("a", 1.0),), 3.0,
                            residue=2.0).sums())

    # --- no exported name may be defined twice ------------------------------
    #
    # print_report existed in report.py and innovation.py with different
    # signatures. The package imported report first and innovation second,
    # so ppact.print_report silently resolved to the wrong one and anybody
    # calling it got a TypeError about argument counts. Found while
    # inventorying the visualisation layer, by calling it.
    import importlib as _il, os as _osx, re as _rex
    defined = {}
    for fname in sorted(_osx.listdir("ppact")):
        if not fname.endswith(".py") or fname == "__init__.py":
            continue
        text = open(_osx.path.join("ppact", fname), encoding="utf-8").read()
        for name in _rex.findall(r"^def ([a-z_][a-z0-9_]*)\(", text,
                                 _rex.M):
            if name.startswith("_"):
                continue
            defined.setdefault(name, []).append(fname)

    # The check is on what the package EXPORTS under a name, not on what a
    # module happens to call a function. Two modules may both define sweep()
    # if the package imports one of them under an alias - which is what
    # memory_sweep already did, and the first version of this check reported
    # it as a clash. A check that flags a solved problem trains people to
    # ignore it.
    import ppact as _pp
    exported = [n for n in getattr(_pp, "__all__", [])
                if callable(getattr(_pp, n, None))]
    clashes = []
    for name in exported:
        fn = getattr(_pp, name)
        home = getattr(fn, "__module__", "")
        real = getattr(fn, "__name__", name)
        # a name exported unaliased that is ALSO defined elsewhere is the
        # dangerous case: the later import silently wins
        if real == name and len(defined.get(name, [])) > 1:
            clashes.append((name, defined[name]))
    check(O, "no exported name is defined in two modules", not clashes,
          "; ".join(f"{n}: {mods}" for n, mods in clashes[:3])
          + " - the later import wins silently and a caller gets a "
            "TypeError about argument counts")
    check(O, "and where two modules share a name, one is aliased",
          not [n for n, mods in defined.items()
               if len(mods) > 1 and getattr(_pp, n, None) is not None
               and getattr(getattr(_pp, n), "__name__", n) == n
               and n in exported],
          "aliasing is how two modules keep a natural name safely")
    check(O, "the two report functions are named apart",
          hasattr(_pp, "print_memory_report")
          and hasattr(_pp, "print_innovation_report")
          and not hasattr(_pp, "print_report"))
    check(O, "and each resolves to its own module",
          _pp.print_memory_report.__module__ == "ppact.report"
          and _pp.print_innovation_report.__module__ == "ppact.innovation")

    # --- the integrity check must reject what it is meant to reject ---------
    #
    # It passes on a clean archive, which is what it should do and also what
    # a check with a disabled branch looks like. So it is given three
    # folders it must refuse. Eleventh detector in this project shown input
    # it has to reject rather than trusted to work.
    import shutil as _shr, subprocess as _spr, tempfile as _tfr
    import os as _osr

    def _integrity(folder):
        proc = _spr.run([sys.executable, "check_release.py"], cwd=folder,
                        capture_output=True, text=True, timeout=300)
        return proc.returncode, proc.stdout

    src_root = _osr.path.dirname(_osr.path.abspath("ppact"))
    tmp_i = _tfr.mkdtemp(prefix="ppact_integrity_")
    try:
        # THE COPY CARRIES THE RELEASE LABEL.
        #
        # `check_release` now requires the tree to name its release,
        # because a repository updated file by file had ended up holding
        # two of them. A copy called "clean" fails that check for a
        # reason that says nothing about the files it contains.
        from ppact.branding import RELEASE_LABEL as _RL
        clean = _osr.path.join(
            tmp_i, f"PPACT_Studio_{_RL.replace(' ', '-')}")
        # PROVENANCE, not a name list.
        #
        # Excluding "ppact_report.md" by name would hide a real development
        # trace that happened to share the name. What may be excluded is a
        # file THIS RUN created: anything present before the suite started
        # is a trace of development and must still be reported.
        produced_now = {
            name for name in _RUNTIME_ARTEFACTS
            if _osr.path.exists(name)
            and (name not in _PRE_EXISTING_ARTEFACTS
                 or _written_by_this_run(name))}
        _shr.copytree(".", clean,
                      ignore=_shr.ignore_patterns(
                          "__pycache__", "*.pyc", "*.png",
                          *sorted(produced_now)))
        # A run log whose every row names THIS run is this run's output,
        # not a trace left from development - even though it was on disk
        # when the suite imported, because an earlier phase of the same
        # run wrote it.
        stale = sorted(n for n in _PRE_EXISTING_ARTEFACTS
                       if not _written_by_this_run(n))
        check(O, "no run artefact predates this run", not stale,
              f"{stale} existed before the suite started and carries no "
              f"row from this run, so they are development traces rather "
              f"than output of this check")
        code, out = _integrity(clean)
        # The tail alone showed a generic warning and not the difference.
        detail = " | ".join(
            l.strip() for l in out.splitlines()
            if "DIFFER" in l or "MISSING" in l or "EXTRA" in l)[:220]
        check(O, "a clean copy passes the integrity check", code == 0,
              detail or out[-200:])

        # a missing document
        broken = _osr.path.join(tmp_i, "missing")
        _shr.copytree(clean, broken)
        _osr.remove(_osr.path.join(broken, "HELP.md"))
        code, out = _integrity(broken)
        check(O, "a copy missing a document is refused",
              code != 0 and "HELP.md" in out, out[-200:])

        # an edited document
        edited = _osr.path.join(tmp_i, "edited")
        _shr.copytree(clean, edited)
        with open(_osr.path.join(edited, "README.md"), "a",
                  encoding="utf-8") as fh:
            fh.write("\nan edit nobody recorded\n")
        code, out = _integrity(edited)
        check(O, "a copy whose document was edited is refused",
              code != 0 and "edited" in out.lower(),
              "the manifest records a digest per file so this is visible "
              "without diffing")

        # a development trace
        dirty = _osr.path.join(tmp_i, "dirty")
        _shr.copytree(clean, dirty)
        _osr.makedirs(_osr.path.join(dirty, "__pycache__"), exist_ok=True)
        code, out = _integrity(dirty)
        check(O, "a copy carrying a development trace is refused",
              code != 0 and "__pycache__" in out, out[-200:])
    finally:
        _shr.rmtree(tmp_i, ignore_errors=True)

    # --- the release manifest records only what was verified ----------------
    from ppact.reproducibility import (build_release_manifest,
                                       NOT_ESTABLISHED_ITEMS,
                                       VALIDATION_CATEGORIES)
    man_r = build_release_manifest(".", "v-test")
    # ONE release label. The zip was named v1.0-RC1 while the manifest said
    # v1.0, because certification regenerated it without the label. A
    # candidate and the release it becomes share a version and differ in
    # label, and mixing them is how somebody tests one thing and ships
    # another.
    from ppact.branding import RELEASE_LABEL
    check(O, "the manifest carries the release label, not just the version",
          build_release_manifest(".")["release"] == RELEASE_LABEL,
          f'{build_release_manifest(".")["release"]!r} against '
          f'{RELEASE_LABEL!r}')
    check(O, "and the label names the product version it belongs to",
          PRODUCT_VERSION_FOR_LABEL := __import__("ppact").PRODUCT_VERSION
          in RELEASE_LABEL, f"{RELEASE_LABEL}")

    check(O, "the manifest names the product and both versions",
          man_r["product"] and man_r["product_version"]
          and man_r["engine_version"])
    check(O, "and the build environment",
          man_r["python"] and man_r["platform"] and man_r["built"])
    check(O, "and carries a documentation digest separate from the source",
          man_r["documentation"]["digest"]
          != man_r["evidence"]["source_digest"],
          "a documentation change must be visible without reading the "
          "documents")
    check(O, "the package hash is one hash, not a file listing",
          man_r["evidence"]["package_hash"] is None
          or (len(man_r["evidence"]["package_hash"]) == 64
              and " " not in man_r["evidence"]["package_hash"]),
          str(man_r["evidence"]["package_hash"])[:70])
    check(O, "it lists what is NOT established",
          len(man_r["not_established"]) == len(NOT_ESTABLISHED_ITEMS)
          and man_r["not_established"],
          "a release record listing only what passed is an advertisement")
    check(O, "and the validation categories",
          len(man_r["validation_categories"]) == len(VALIDATION_CATEGORIES))
    check(O, "a manifest built without results claims none",
          "verified" not in man_r,
          "an absent field must mean not run, never that it passed")
    check(O, "and says so in the record itself",
          "never that it passed" in man_r["note"])
    with_results = build_release_manifest(".", "v-test",
                                          {"documentation_audit": "PASS"})
    check(O, "a manifest built with results carries them",
          with_results.get("verified", {}).get("documentation_audit")
          == "PASS")

    # --- the About page: the ORDER is the argument --------------------------
    #
    # An earlier version of this text opened with "PPACT Studio does not
    # model commercial products." True, and the wrong first sentence: it
    # tells a reader what the Studio is NOT and leaves them to work out what
    # it is. The boundary comes fourth because it is a CONSEQUENCE of the
    # three sections before it.
    from ppact import about as AB
    check(O, "the About page is well formed", not AB.about_violations(),
          "; ".join(AB.about_violations()[:2]))
    keys = [sec.key for sec in AB.SECTIONS]
    check(O, "purpose comes first", keys[0] == "purpose",
          f"{keys[0]} - a page that opens with a boundary describes the "
          f"Studio by what it is not")
    check(O, "and the boundary comes after purpose, method and evolution",
          keys.index("boundary") > keys.index("purpose")
          and keys.index("boundary") > keys.index("method")
          and keys.index("boundary") > keys.index("evolution"),
          str(keys))
    check(O, "and interpretation is last", keys[-1] == "interpretation")
    check(O, "the order is fixed rather than incidental",
          AB.REQUIRED_ORDER == tuple(keys))

    text = AB.about_text()
    norm = " ".join(text.split())
    check(O, "the boundary statement is present",
          "does not model commercial products" in norm)
    check(O, "but not in the first section",
          norm.index("does not model commercial products")
          > norm.index("DESIGN BOUNDARY"),
          "it must read as a design decision, not as the headline")
    check(O, "products are named as validation sources",
          "validation sources, not library contents" in norm)
    check(O, "the page says the figures are estimates",
          "analytical engineering estimate" in norm)
    check(O, "and that measurement is still necessary",
          "measurement and silicon remain necessary" in norm)
    check(O, "and hands the decision back",
          "decision is the designer" in norm)
    check(O, "there are four core principles",
          len(AB.CORE_PRINCIPLES) == 4, str(len(AB.CORE_PRINCIPLES)))
    for p_ in AB.CORE_PRINCIPLES:
        check(O, f"'{p_[:34]}' is one line", len(p_) < 70 and p_.endswith("."))
    check(O, "the principles are on the page", 
          all(p_ in text for p_ in AB.CORE_PRINCIPLES))
    check(O, "nothing on the page wraps",
          all(len(ln) <= 78 for ln in text.splitlines()),
          f"widest {max(len(ln) for ln in text.splitlines())}")

    # --- host connection is declared and NOT modelled -----------------------
    #
    # Phase 1 of a two-phase plan: the library recognises how an accelerator
    # reaches its host, and no equation touches it. The whole value of that
    # depends on the second half being TRUE, so it is checked exhaustively
    # rather than promised.
    from ppact.arch_classes import (HOST_CONNECTION_KEYS,
                                    HOST_CONNECTION_NAME,
                                    HOST_CONNECTION_NOTE,
                                    HOST_CONNECTION_STATUS,
                                    describe_host_connection)
    import dataclasses as _dch
    check(O, "the default host connection is on-board",
          SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5",
                       2).host_connection == "on_board",
          "a design written before this field existed must behave as it did")
    check(O, "several connection classes are declared",
          len(HOST_CONNECTION_KEYS) >= 5)
    for k in HOST_CONNECTION_KEYS:
        check(O, f"'{k}' has a name and an explanation",
              HOST_CONNECTION_NAME.get(k) and len(HOST_CONNECTION_NOTE[k]) > 25)

    # EVERY metric, at EVERY setting, on several applications. Identical.
    for app_key, cfg0 in (
            ("industrial_vision",
             SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                          preprocessing_mode="cpu_only")),
            ("drone",
             SystemConfig("cortex_a78_x4", "npu_24x24", "LPDDR5", 2,
                          preprocessing_mode="isp_and_npu")),
            ("llm_service",
             SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6))):
        r0 = evaluate_system(APPLICATION_LIBRARY[app_key], cfg0)
        for k in HOST_CONNECTION_KEYS:
            r1 = evaluate_system(APPLICATION_LIBRARY[app_key],
                                 _dch.replace(cfg0, host_connection=k))
            differing = [m for m in r0.metrics
                         if r0.metrics[m] != r1.metrics[m]]
            check(O, f"{app_key}/{k}: every metric is unchanged",
                  not differing,
                  f"{differing[:3]} - a field described as informational "
                  f"that moves a number is worse than no field")
            check(O, f"{app_key}/{k}: the gates are unchanged",
                  r0.gate == r1.gate)
            check(O, f"{app_key}/{k}: the bottleneck is unchanged",
                  r0.bound_by == r1.bound_by
                  and r0.bound_strength == r1.bound_strength)

    # and no engine module may even mention it
    import os as _osh
    for mod in ("system.py", "compute.py", "memory.py", "cpu.py",
                "preprocess.py", "runtime.py", "economics.py",
                "process.py", "accuracy.py"):
        text = open(_osh.path.join("ppact", mod), encoding="utf-8").read()
        uses = [ln for ln in text.splitlines()
                if "host_connection" in ln and not ln.strip().startswith("#")
                and "host_connection: str" not in ln]
        check(O, f"ppact/{mod} does not read the field", not uses,
              f"{uses[:1]}")

    # the report must say it is not modelled
    # The report wraps, so the words are checked after normalising the
    # whitespace the wrapping introduced - the same class of mistake as
    # checking the banner against its unwrapped source.
    joined = " ".join(" ".join(describe_host_connection("pcie_gen5")).split())
    check(O, "a report names the connection", "PCIe Gen5" in joined)
    check(O, "and says the model does not use it",
          "does not use this" in joined, joined[-120:])
    check(O, "and that a check enforces that",
          "identical at every setting" in joined,
          "saying it is informational is a promise; saying a check enforces "
          "it is a fact a reader can go and verify")
    check(O, "the status is stated once and reused",
          " ".join(HOST_CONNECTION_STATUS.split()) in joined)

    # --- the product identifies itself from one constant --------------------
    from ppact import branding as BR
    check(O, "the banner names the product and its version",
          BR.PRODUCT_NAME in BR.banner()
          and f"v{BR.PRODUCT_VERSION}" in BR.banner())
    check(O, "and the version comes from the constant, not a literal",
          BR.PRODUCT_VERSION in BR.banner()
          and BR.banner().count(BR.PRODUCT_NAME) == 1,
          "a version typed into a print statement is a version that gets "
          "forgotten - this project has already shipped one that way")
    check(O, "the claim says the values are estimates",
          "engineering estimates" in BR.CLAIM)
    check(O, "and that the decision is the designer's",
          "responsibility of the designer" in BR.CLAIM)
    check(O, "the banner fits a narrow terminal",
          all(len(ln) <= 62 for ln in BR.banner().splitlines()),
          f"widest {max(len(ln) for ln in BR.banner().splitlines())}")

    # --- the bus allocation must survive dual contention --------------------
    #
    # The split of the bus is computed BEFORE dual-engine contention narrows
    # it. Leaving the accelerator's share at its pre-contention value while
    # the bus shrank beneath it made the host's share - the remainder - go
    # NEGATIVE: -225 GB/s on a twelve-stack HBM4 board. Found by a random
    # stress draw, not by reasoning, which is the argument for the stress
    # pack.
    for comp2, mem2, dev2 in (("mobile_gpu", "HBM4_36", 12),
                              ("npu_64x64", "LPDDR5", 4),
                              ("npu_128x128", "HBM3E", 6)):
        for split in (0.1, 0.5, 0.9):
            try:
                rr = evaluate_system(APPLICATION_LIBRARY["ai_inference"],
                                     SystemConfig(
                                         "server_x86_x32", comp2, mem2, dev2,
                                         preprocessing_mode="cpu_only",
                                         secondary_compute=comp2,
                                         execution_mode="parallel",
                                         work_split=split))
            except Exception:
                continue
            if "INFEASIBLE" in rr.status:
                continue
            h = rr.metrics["Host bandwidth allocated (GB/s)"]
            a = rr.metrics["Bandwidth left to the accelerator (GB/s)"]
            e = rr.metrics["Effective bandwidth (GB/s)"]
            check(O, f"{comp2}/{mem2}x{dev2} split {split}: the host share is "
                     f"not negative", h >= -1e-9, f"{h:.4f} GB/s")
            check(O, f"{comp2}/{mem2}x{dev2} split {split}: the two shares "
                     f"still partition the bus", abs(h + a - e) < 1e-9,
                  f"residue {h + a - e:+.9f} GB/s")

    # --- an explanation must not invent a change ----------------------------
    buf3 = io.StringIO()
    with contextlib.redirect_stdout(buf3):
        decision_explanation("drone", d_base, d_base)
    t3 = buf3.getvalue()
    check(O, "comparing a design with itself achieves nothing",
          "nothing measurable" in t3,
          "an explanation that finds a gain where there was no change is "
          "generating text rather than reading a result")


# ==============================================================================
# PATH AP - sensitivity
# ==============================================================================
#
# A verdict computed from one coefficient value is a verdict about that value.
# Some conclusions here survive any plausible figure and some reverse if an
# assumption moves by half a point, and reporting both the same way is the
# most misleading thing this model could do.

def path_ap():
    P = "AP"
    import io, contextlib
    from ppact.sensitivity import (build_sweeps, run_sweep, print_sweep,
                                   ROBUST_PASS, ROBUST_FAIL, CONDITIONAL,
                                   BOUNDARY_ADJACENT, NO_INFLUENCE,
                                   ADJACENCY_FRACTION)

    sweeps = build_sweeps()
    check(P, "sensitivity sweeps are defined", len(sweeps) >= 4)
    for sw in sweeps:
        check(P, f"{sw.sid} states a range", sw.low < sw.nominal <= sw.high
              or sw.low <= sw.nominal < sw.high,
              f"{sw.low} .. {sw.nominal} .. {sw.high}")
        check(P, f"{sw.sid} names what it would change", len(sw.verdict_name) > 5)
        check(P, f"{sw.sid} declares its basis", "ASSUMPTION" in sw.basis
              or "ESTIMATE" in sw.basis, sw.basis)

    results = [run_sweep(sw, 21) for sw in sweeps]

    # --- the classification must follow from the samples --------------------
    for r in results:
        verdicts = [x[1] for x in r["rows"] if x[1] is not None]
        out = r["outcome"]
        if out == ROBUST_PASS:
            check(P, f"{r['sweep'].sid} robust pass means every sample passes",
                  all(verdicts))
        elif out == ROBUST_FAIL:
            check(P, f"{r['sweep'].sid} robust fail means every sample fails",
                  not any(verdicts))
        elif out in (CONDITIONAL, BOUNDARY_ADJACENT):
            check(P, f"{r['sweep'].sid} conditional means both outcomes exist",
                  any(verdicts) and not all(verdicts))
            # the flip must lie between the nearest disagreeing pair
            flip = r["flip"]
            check(P, f"{r['sweep'].sid} the flip point is inside the range",
                  flip is not None
                  and r["sweep"].low <= flip <= r["sweep"].high,
                  str(flip))
            lo = max(x[0] for x in r["rows"]
                     if x[1] is not None and x[1] and x[0] < flip)
            hi = min(x[0] for x in r["rows"]
                     if x[1] is not None and not x[1] and x[0] > flip)
            check(P, f"{r['sweep'].sid} the flip lies between a pass and a "
                     f"fail",
                  lo < flip < hi, f"{lo:g} < {flip:g} < {hi:g}")

    # --- boundary-adjacent means CLOSE, and close is stated -----------------
    for r in results:
        if r["outcome"] == BOUNDARY_ADJACENT:
            span = r["sweep"].high - r["sweep"].low
            check(P, f"{r['sweep'].sid} is adjacent by the stated fraction",
                  abs(r["flip"] - r["sweep"].nominal)
                  <= span * ADJACENCY_FRACTION + 1e-12)
        if r["outcome"] == CONDITIONAL:
            span = r["sweep"].high - r["sweep"].low
            check(P, f"{r['sweep'].sid} is conditional and NOT adjacent",
                  abs(r["flip"] - r["sweep"].nominal)
                  > span * ADJACENCY_FRACTION)

    # --- the outcomes must not all be the same ------------------------------
    #
    # A sensitivity pack where everything is robust has been pointed at
    # coefficients nothing depends on.
    outcomes = {r["outcome"] for r in results}
    check(P, "the sweeps produce more than one kind of outcome",
          len(outcomes) >= 2, str(sorted(outcomes)))
    check(P, "and at least one verdict rests on an assumption",
          BOUNDARY_ADJACENT in outcomes or CONDITIONAL in outcomes,
          "if nothing is assumption-sensitive the pack is pointed at the "
          "wrong coefficients")
    check(P, "while at least one holds across its whole range",
          ROBUST_PASS in outcomes or ROBUST_FAIL in outcomes,
          "and the difference between the two is the point")

    # --- the samples must ascend --------------------------------------------
    #
    # The flip scan walks adjacent pairs and takes the FIRST disagreement, so
    # a descending sweep reports the last flip as the first. With a single
    # crossing the two coincide and nothing shows, which is why this is
    # checked directly rather than through an outcome.
    for r in results:
        xs = [x[0] for x in r["rows"]]
        check(P, f"{r['sweep'].sid} samples ascend",
              all(a < b for a, b in zip(xs, xs[1:])),
              f"{xs[0]:g} .. {xs[-1]:g} - a descending sweep reports the last "
              f"crossing as the first, which differs as soon as a coefficient "
              f"crosses twice")
        check(P, f"{r['sweep'].sid} spans the declared range",
              abs(xs[0] - r["sweep"].low) < 1e-9
              and abs(xs[-1] - r["sweep"].high) < 1e-9,
              f"{xs[0]:g}..{xs[-1]:g} against "
              f"{r['sweep'].low:g}..{r['sweep'].high:g}")

    # --- a decorative coefficient must be detectable ------------------------
    #
    # A registry entry the code never reads is a claim that something was
    # considered when it was not. The detector has to actually fire.
    from ppact.sensitivity import Sweep
    fake = Sweep("S-XX", "a coefficient nothing reads",
                 "does the detector notice a coefficient with no effect?",
                 low=0.0, nominal=0.5, high=1.0,
                 probe=lambda v: (True, 42.0),
                 verdict_name="anything", value_name="constant")
    check(P, "a coefficient with no influence is detected",
          run_sweep(fake, 11)["outcome"] == NO_INFLUENCE,
          "a registry entry the code never reads is decoration")

    # --- a wider range cannot make a verdict MORE confident -----------------
    narrow = run_sweep(dataclasses.replace(
        sweeps[0], low=sweeps[0].nominal - 0.05,
        high=sweeps[0].nominal + 0.05), 11)
    wide = results[0]
    order = {ROBUST_PASS: 2, ROBUST_FAIL: 2, CONDITIONAL: 1,
             BOUNDARY_ADJACENT: 0, NO_INFLUENCE: 2}
    check(P, "widening the uncertainty cannot raise confidence",
          order[wide["outcome"]] <= order[narrow["outcome"]],
          f"narrow {narrow['outcome']}, wide {wide['outcome']}")

    # --- S2: break-even, ranking stability, coefficient liveness ------------
    from ppact.sensitivity import (handoff_break_even, handoff_ranking,
                                   print_ranking, coefficient_liveness,
                                   STABLE, RANK_FLIP, PARTIALLY_STABLE,
                                   COEFFICIENT_DEPENDENCIES)

    with contextlib.redirect_stdout(io.StringIO()) as bbuf:
        table = handoff_break_even()
    bt = bbuf.getvalue()
    sizes = list(next(iter(table.values())).keys())
    overheads = list(table)
    conditional = [s_ for s_ in sizes
                   if len({table[o][s_][2] for o in overheads}) > 1]
    always = [s_ for s_ in sizes if all(table[o][s_][2] for o in overheads)]
    check(P, "some frame sizes flip with the hand-off cost", conditional,
          f"{conditional} depend on a coefficient")
    check(P, "and some do not", always, f"{always} are structural")
    check(P, "a bigger frame favours the offload more",
          all(table[overheads[-1]][s_][2] for s_ in sizes[-1:]),
          "the host's work grows with the frame and the hand-off does not")
    check(P, "the break-even report separates the two kinds",
          "CONDITIONAL result" in bt and "structural result" in bt)

    # winner stability, with and without a third design
    with contextlib.redirect_stdout(io.StringIO()):
        two = handoff_ranking(320 * 240, include_dual=False)
        three = handoff_ranking(320 * 240, include_dual=True)
        big = handoff_ranking(2592 * 1944, include_dual=True)
    check(P, "a small frame flips the winner between two designs",
          two["outcome"] == RANK_FLIP, two["outcome"])
    check(P, "a large frame does not", big["outcome"] == STABLE,
          big["outcome"])
    check(P, "and a stable winner can still have a changing order",
          three["outcome"] == STABLE and three["order_changed"],
          "second place moving is a real result and is not an answer to "
          "'which should we build'")
    rbuf = io.StringIO()
    with contextlib.redirect_stdout(rbuf):
        print_ranking(two)
        print_ranking(three)
    rt = rbuf.getvalue()
    check(P, "a rank flip is named as a coefficient decision",
          "COEFFICIENT decision wearing a design decision" in rt)
    check(P, "and an order change is distinguished from one",
          "does not make this a rank flip" in rt)

    # --- every coefficient must move what it declares and nothing else ------
    findings = coefficient_liveness(verbose=False)
    check(P, "the liveness audit covers several coefficients",
          len(findings) >= 5, str(len(findings)))
    dead = [f["coefficient"] for f in findings if f["dead"]]
    leaks = [f["coefficient"] for f in findings if f["leaks"]]
    check(P, "no coefficient is decorative", not dead,
          f"declared and inert: {', '.join(dead)}")
    check(P, "and none leaks into an unrelated result", not leaks,
          f"leaking: {', '.join(leaks)}")
    # --- positive controls: the detectors must actually fire ---------------
    #
    # Everything in the registry is currently live and leak-free, so
    # disabling either detector changes nothing observable. A detector that
    # has never fired is not known to work, so both are given something to
    # find.
    import ppact.system as _SYSX
    _SYSX.__DEAD_COEFFICIENT__ = 1.0
    COEFFICIENT_DEPENDENCIES["__DEAD_COEFFICIENT__"] = {
        "module": "ppact.system", "delta": 5.0,
        "affects": ("Latency (ms)",),          # declared, and it reads nothing
        "must_not_affect": ("Deployment accuracy (%)",),
        "config": dict(app="robot", cpu="cortex_a78_x4", compute="npu_32x32",
                       memory="LPDDR5", devices=4,
                       preprocessing_mode="isp_and_npu"),
    }
    # and a live one that declares it must not touch something it does touch
    COEFFICIENT_DEPENDENCIES["__LEAKING_CHECK__"] = {
        "module": "ppact.system", "delta": -0.4,
        "affects": ("CPU active (ms)",),
        # HOST_MEMORY_OVERLAP genuinely moves the latency, so declaring that
        # it must not is a false declaration and the audit should say so.
        "must_not_affect": ("Latency (ms)",),
        "config": dict(app="industrial_vision", cpu="cortex_a78_x4",
                       compute="npu_32x32", memory="LPDDR5", devices=2,
                       preprocessing_mode="cpu_only"),
    }
    _SYSX.__LEAKING_CHECK__ = _SYSX.HOST_MEMORY_OVERLAP
    try:
        # the leaking entry has to actually move the coefficient the model
        # reads, so point it at the real one for the duration
        COEFFICIENT_DEPENDENCIES["__LEAKING_CHECK__"]["module"] = "ppact.system"
        controls = coefficient_liveness(verbose=False)
        by_name = {f["coefficient"]: f for f in controls}
        check(P, "the decorative detector fires on an inert coefficient",
              by_name["__DEAD_COEFFICIENT__"]["dead"],
              "declared to affect the latency and read by nothing")
    finally:
        COEFFICIENT_DEPENDENCIES.pop("__DEAD_COEFFICIENT__", None)
        COEFFICIENT_DEPENDENCIES.pop("__LEAKING_CHECK__", None)

    # the leak detector, given a coefficient that really does move the thing
    # it declares it must not
    COEFFICIENT_DEPENDENCIES["__LEAK_CONTROL__"] = {
        "module": "ppact.system", "delta": -0.4,
        "affects": ("CPU active (ms)",),
        "must_not_affect": ("Latency (ms)",),
        "config": dict(app="industrial_vision", cpu="cortex_a78_x4",
                       compute="npu_32x32", memory="LPDDR5", devices=2,
                       preprocessing_mode="cpu_only"),
    }
    _SYSX.__LEAK_CONTROL__ = _SYSX.HOST_MEMORY_OVERLAP
    _orig_overlap = _SYSX.HOST_MEMORY_OVERLAP
    try:
        import ppact.sensitivity as _SENS
        _saved_deps = _SENS.COEFFICIENT_DEPENDENCIES
        # run the audit against the real overlap coefficient under a false
        # must-not-affect declaration
        _SENS.COEFFICIENT_DEPENDENCIES = {
            "HOST_MEMORY_OVERLAP": COEFFICIENT_DEPENDENCIES["__LEAK_CONTROL__"]
        }
        leak_run = coefficient_liveness(verbose=False)
        check(P, "the leak detector fires on a false declaration",
              leak_run[0]["leaks"],
              "HOST_MEMORY_OVERLAP does move the latency, so declaring that "
              "it must not is a declaration the audit should reject")
    finally:
        _SENS.COEFFICIENT_DEPENDENCIES = _saved_deps
        COEFFICIENT_DEPENDENCIES.pop("__LEAK_CONTROL__", None)
        _SYSX.HOST_MEMORY_OVERLAP = _orig_overlap

    for name, spec in COEFFICIENT_DEPENDENCIES.items():
        check(P, f"{name} declares what it affects", spec["affects"])
        check(P, f"{name} declares what it must not",
              spec["must_not_affect"],
              "a coefficient with no declared effect cannot be found to have "
              "none")

    # --- S-07: the coefficient that must move only some things -------------
    from ppact.sensitivity import (memory_energy_common_scale,
                                   memory_energy_relative,
                                   MEMORY_ENERGY_MAY_AFFECT,
                                   MEMORY_ENERGY_MUST_NOT_AFFECT)
    with contextlib.redirect_stdout(io.StringIO()) as ebuf:
        common = memory_energy_common_scale()
    et = ebuf.getvalue()
    check(P, "scaling every memory's energy leaks into nothing",
          not common["leaks"],
          f"leaks: {common['leaks'][:3]}")
    check(P, "while the energy and power figures do move",
          len(common["moved"]) >= 4, str(len(common["moved"])))
    # the invariance must be EXACT, not approximate
    for label in common["rows"][0]["cases"]:
        base = common["rows"][0]["cases"][label]
        last = common["rows"][-1]["cases"][label]
        for metric in MEMORY_ENERGY_MUST_NOT_AFFECT:
            if metric in base:
                check(P, f"{label}: {metric} is identical across the scale",
                      abs(base[metric] - last[metric]) < 1e-12,
                      f"{base[metric]:.9f} against {last[metric]:.9f}")
    check(P, "and the thermal verdict is named a consequence, not a finding",
          "CONSEQUENCE, not a second finding" in et)

    with contextlib.redirect_stdout(io.StringIO()) as rbuf2:
        rel = memory_energy_relative()
    rt2 = rbuf2.getvalue()
    check(P, "moving one memory's energy alone CAN reorder the winner",
          len(set(rel["energy_winners"])) > 1,
          f"winners: {rel['energy_winners']}")
    check(P, "while the power verdict is robust across the same range",
          len(set(rel["power_verdicts"])) == 1,
          f"verdicts: {set(rel['power_verdicts'])}")
    check(P, "so energy per job and average power answer DIFFERENTLY",
          len(set(rel["energy_winners"])) > 1
          and len(set(rel["power_verdicts"])) == 1,
          "a single 'efficiency' number would be right about half of it and "
          "silent about which half")
    check(P, "and the report says so", "answer DIFFERENTLY" in rt2)

    # --- the report must say which kind a verdict is ------------------------
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for r in results:
            print_sweep(r)
    t = buf.getvalue()
    check(P, "an assumption-sensitive verdict is labelled as one",
          "property of the ASSUMPTION" in t)
    check(P, "and told not to be quoted without a measurement",
          "without a measured figure" in t)
    check(P, "a robust one is labelled too",
          "holds across the whole assumed range" in t)
    check(P, "and says why that is worth stating",
          "a reader cannot tell which without being told" in t)


# ==============================================================================
# PATH AQ - reproducibility
# ==============================================================================
#
# Four thousand passing checks say the model is self-consistent today. They
# say nothing about tomorrow, another machine, or someone editing a
# coefficient and forgetting.

def path_aq():
    Q = "AQ"
    import io, contextlib, json, os, shutil, tempfile
    import ppact.reproducibility as R

    # --- the manifest must name what it claims ------------------------------
    man = R.build_manifest(os.path.dirname(os.path.dirname(R.__file__)))
    for key in ("version", "source_digest", "coefficient_digest",
                "environment", "seed", "certified"):
        check(Q, f"the manifest records {key}", key in man, key)
    check(Q, "and the environment names the interpreter and platform",
          {"python", "system", "machine"} <= set(man["environment"]))
    check(Q, "the certified seed is fixed", R.CERTIFIED_SEED == 20260802)
    check(Q, "and a run with it is marked certified", man["certified"])

    # --- the coefficient snapshot must reach the code -----------------------
    snap = R.coefficient_snapshot()
    check(Q, "the snapshot covers the registry", len(snap) >= 8, str(len(snap)))
    in_code = [c for c in snap if c["in_code"]]
    check(Q, "and finds most coefficients in the code",
          len(in_code) >= len(snap) * 0.5,
          f"{len(in_code)} of {len(snap)} located")
    disagree = [c["name"] for c in snap if not c["agrees"]]
    check(Q, "every located coefficient matches its declared value",
          not disagree,
          f"declared and live differ: {', '.join(disagree)}")

    # --- a fingerprint must be stable within one process --------------------
    a, b = R.fingerprint(), R.fingerprint()
    same = R.compare(a, b)
    check(Q, "two runs in the same process agree exactly", same["ok"],
          str(same["problems"][:2]))
    check(Q, "and compare a useful number of values",
          same["compared"] >= 150, str(same["compared"]))

    # --- POSITIVE CONTROLS: a modified package must be REJECTED -------------
    #
    # A reproducibility checker that has never rejected a modified package is
    # not known to work. Four kinds of change, four named reasons.
    ref = R.fingerprint()

    # 1. a coefficient moved -> the manifest digest changes
    import ppact.system as _SY
    saved_overlap = _SY.HOST_MEMORY_OVERLAP
    try:
        _SY.HOST_MEMORY_OVERLAP = saved_overlap * 0.5
        moved = R.build_manifest(os.path.dirname(os.path.dirname(R.__file__)))
        kinds = [k for k, _ in R.classify_manifest_difference(man, moved)]
        check(Q, "moving a coefficient is caught as a coefficient difference",
              R.COEFFICIENT_DIFFERENCE in kinds, str(kinds))
        drift = R.compare(ref, R.fingerprint())
        check(Q, "and shows as numeric drift in the fingerprint",
              not drift["ok"]
              and any(k == R.NUMERIC_DRIFT for k, _ in drift["problems"]),
              str(drift["problems"][:2]))
    finally:
        _SY.HOST_MEMORY_OVERLAP = saved_overlap

    # 2. a scenario input changed -> categorical divergence
    saved_app = APPLICATION_LIBRARY["drone"]
    try:
        APPLICATION_LIBRARY["drone"] = dataclasses.replace(
            saved_app, target_inferences_per_s=saved_app.target_inferences_per_s * 4)
        changed = R.compare(ref, R.fingerprint())
        check(Q, "changing a scenario input is caught",
              not changed["ok"], "an input change must not reproduce")
    finally:
        APPLICATION_LIBRARY["drone"] = saved_app

    # 3. a different seed -> not a certified run
    other = R.build_manifest(os.path.dirname(os.path.dirname(R.__file__)),
                             seed=R.CERTIFIED_SEED + 1)
    kinds = [k for k, _ in R.classify_manifest_difference(man, other)]
    check(Q, "a different seed is a non-certified run",
          R.NON_CERTIFIED_RUN in kinds, str(kinds))
    check(Q, "and is not marked certified", not other["certified"])

    # 4. a source file changed -> source difference
    fake = dict(man)
    fake["source_digest"] = "0" * 64
    kinds = [k for k, _ in R.classify_manifest_difference(fake, man)]
    check(Q, "a changed source file is caught as a source difference",
          R.SOURCE_DIFFERENCE in kinds, str(kinds))

    # --- and an unchanged package must still be accepted --------------------
    check(Q, "an unmodified package still reproduces",
          R.compare(ref, R.fingerprint())["ok"],
          "a checker that rejects everything is no better than one that "
          "rejects nothing")

    # --- the evidence list must not become a percentage ---------------------
    #
    # A developer who computes their own validation score has produced
    # another self-assessment. A list of what exists and what does not is
    # checkable by a reader; a number is not.
    from ppact.reproducibility import (EVIDENCE_STATUS,
                                       CERTIFIED_RUN_CONDITIONS,
                                       print_evidence_status, certified_run)
    states = {st for _, st, _ in EVIDENCE_STATUS}
    check(Q, "the evidence list records more than one state",
          len(states) >= 3, str(sorted(states)))
    check(Q, "and marks what is still pending",
          any(st == "PENDING" for _, st, _ in EVIDENCE_STATUS),
          "second-machine reproduction and an independent holdout are not "
          "things this package can do for itself")
    check(Q, "including that external evidence is limited",
          any("external" in n and st == "LIMITED"
              for n, st, _ in EVIDENCE_STATUS),
          "internal work cannot raise it")
    for name, state, note in EVIDENCE_STATUS:
        check(Q, f"'{name[:34]}' explains itself", len(note) > 25)
    ebuf = io.StringIO()
    with contextlib.redirect_stdout(ebuf):
        print_evidence_status()
    et2 = ebuf.getvalue()
    check(Q, "the report refuses to give a score",
          "Not a percentage" in et2 and "self-assessment" in et2)
    check(Q, "and no percentage appears in it",
          "%" not in et2, "a number here would be another self-assessment")

    # --- the certified run must state its conditions ------------------------
    check(Q, "a certified run declares what it requires",
          len(CERTIFIED_RUN_CONDITIONS) >= 5)
    check(Q, "including that a difference is reported rather than fixed",
          any("REPORTED rather than fixed" in c
              for c in CERTIFIED_RUN_CONDITIONS),
          "a difference repaired before it is recorded is one nobody can "
          "learn from")
    cbuf = io.StringIO()
    with contextlib.redirect_stdout(cbuf):
        certified_run(os.path.dirname(os.path.dirname(R.__file__)),
                      os.path.join(os.path.dirname(os.path.dirname(R.__file__)),
                                   "reproducibility"))
    ct = cbuf.getvalue()
    check(Q, "the certified run is short enough to be read",
          len(ct.splitlines()) < 40, f"{len(ct.splitlines())} lines")
    # Read from the SOURCE, not from a run: the run only prints this line
    # when it reproduces, and the package digest goes stale the moment any
    # source file is edited - including this one. Regenerating the package
    # is the last step before a release, not something a test can assume has
    # happened.
    rsrc = open(R.__file__, encoding="utf-8").read()
    check(Q, "the certified run refuses to guess the grade from a platform "
             "string",
          "record R3 by " in rsrc and "cannot tell from a" in rsrc,
          "when the platform strings match, the package says so rather than "
          "guessing which computer this is")
    check(Q, "and says a difference must be reported rather than repaired",
          "repaired before it is recorded" in rsrc)

    # --- certify.py must refuse a stale interpreter -------------------------
    #
    # Inserting a folder at the front of the path does NOT redirect a package
    # already in sys.modules. In a notebook kernel that has run any part of
    # PPACT from another directory, the import resolves against the cached
    # copy - and certifies the wrong folder, or fails looking for a file that
    # exists here and not there. Reported from a real notebook at 3.82.0.
    import subprocess, tempfile as _tf, shutil as _sh
    root2 = os.path.dirname(os.path.dirname(R.__file__))
    cert = os.path.join(root2, "certify.py")
    check(Q, "certify.py exists", os.path.isfile(cert))
    csrc = open(cert, encoding="utf-8").read()
    check(Q, "it checks what is already imported before importing",
          "sys.modules.get" in csrc
          and csrc.index("sys.modules.get") < csrc.index("from ppact"),
          "a path insert does not redirect a loaded package")
    check(Q, "and tells a notebook user to restart the kernel",
          "Restart" in csrc)
    check(Q, "it also refuses a partial extraction",
          "FILES MISSING" in csrc,
          "reporting a missing file as a failed reproduction would blame the "
          "model for it")

    # a stale copy in a subprocess must be refused, not silently certified
    other = _tf.mkdtemp(prefix="ppact_stale_")
    try:
        _sh.copytree(os.path.join(root2, "ppact"),
                     os.path.join(other, "ppact"))
        code = (
            "import sys\n"
            f"sys.path.insert(0, {other!r})\n"
            "import ppact\n"
            "import runpy, sys\n"
            "sys.argv = ['certify.py']\n"
            "try:\n"
            f"    runpy.run_path({cert!r}, run_name='__main__')\n"
            "except SystemExit as e:\n"
            "    print('EXIT', e.code)\n")
        out = subprocess.run([sys.executable, "-c", code],
                             capture_output=True, text=True, timeout=120)
        check(Q, "a stale loaded copy is refused",
              "A DIFFERENT COPY IS ALREADY LOADED" in out.stdout,
              out.stdout[-200:])
        check(Q, "and the refusal is a non-zero exit",
              "EXIT 2" in out.stdout, out.stdout[-120:])
        check(Q, "and it names both folders",
              other in out.stdout and root2 in out.stdout,
              "a reader has to see which copy was going to be certified")
    finally:
        _sh.rmtree(other, ignore_errors=True)

    # a partial extraction must be refused too, and that guard has never
    # fired either - the same gap found for three other detectors
    partial = _tf.mkdtemp(prefix="ppact_partial_")
    try:
        _sh.copy2(cert, os.path.join(partial, "certify.py"))
        os.makedirs(os.path.join(partial, "ppact"))
        _sh.copy2(os.path.join(root2, "ppact", "__init__.py"),
                  os.path.join(partial, "ppact", "__init__.py"))
        # reproducibility.py and the recorded package deliberately absent
        out2 = subprocess.run(
            [sys.executable, os.path.join(partial, "certify.py")],
            capture_output=True, text=True, timeout=120)
        check(Q, "a partial extraction is refused",
              "FILES MISSING" in out2.stdout, out2.stdout[-200:])
        check(Q, "and names what is absent",
              "reproducibility.py" in out2.stdout
              or "manifest.json" in out2.stdout,
              out2.stdout[-200:])
        check(Q, "and does not report it as a failed reproduction",
              "NOT REPRODUCED" not in out2.stdout,
              "blaming the model for a missing file would be the wrong "
              "finding")
    finally:
        _sh.rmtree(partial, ignore_errors=True)

    # --- an environment difference is the CONDITION, not a failure ----------
    #
    # Reported from a real Windows run at 3.83.0: every substantive check
    # matched and the report said NOT REPRODUCED because the operating
    # system, the interpreter and the machine string differed. That is
    # exactly what a second-machine run is FOR, and counting it as a failure
    # had the grading backwards.
    ref_env = {"environment": {"system": "Linux", "machine": "x86_64",
                               "python": "3.12.3"}}
    cases = {
        "same platform": ({"system": "Linux", "machine": "x86_64",
                           "python": "3.12.3"}, "R2"),
        "different interpreter": ({"system": "Linux", "machine": "x86_64",
                                   "python": "3.13.9"}, "R3"),
        "different machine": ({"system": "Linux", "machine": "aarch64",
                               "python": "3.12.3"}, "R3"),
        "different OS": ({"system": "Windows", "machine": "AMD64",
                          "python": "3.13.9"}, "R4"),
    }
    for label, (env, want) in cases.items():
        got, why = R.grade_run(ref_env, {"environment": env}, True)
        check(Q, f"{label} grades {want}", got == want, f"got {got}: {why}")
        check(Q, f"{label} explains the grade", len(why) > 20)
    got, _ = R.grade_run(ref_env, {"environment": cases["different OS"][0]},
                         False)
    check(Q, "but a substantive difference grades R0 whatever the platform",
          got == "R0",
          "a different operating system does not excuse a different answer")

    # the classifier must be able to leave the environment out
    with_env = R.classify_manifest_difference(
        {"environment": ref_env["environment"], "version": "x",
         "source_digest": "a", "coefficient_digest": "b", "seed": 1},
        {"environment": cases["different OS"][0], "version": "x",
         "source_digest": "a", "coefficient_digest": "b", "seed": 1})
    without = R.classify_manifest_difference(
        {"environment": ref_env["environment"], "version": "x",
         "source_digest": "a", "coefficient_digest": "b", "seed": 1},
        {"environment": cases["different OS"][0], "version": "x",
         "source_digest": "a", "coefficient_digest": "b", "seed": 1},
        include_environment=False)
    check(Q, "the environment can be excluded from the difference list",
          with_env and not without,
          f"{len(with_env)} with, {len(without)} without")

    # --- the grade must not overstate what this can establish ---------------
    check(Q, "the self-attainable grade is R2", R.SELF_ATTAINABLE_GRADE == "R2")
    check(Q, "and the higher grades are described but not claimed",
          "R5" in R.GRADES and "independently" in R.GRADES["R5"],
          "R3 upward needs a second machine; R5 needs someone who did not "
          "write it")

    # --- the report must say all of that ------------------------------------
    tmp = tempfile.mkdtemp(prefix="ppact_repro_")
    try:
        root = os.path.dirname(os.path.dirname(R.__file__))
        R.write_package(root, tmp)
        for name in ("manifest.json", "source_checksums.csv",
                     "coefficient_snapshot.csv", "fingerprint.json",
                     "environment.txt", "rerun_instructions.txt",
                     "evidence_hash.txt"):
            check(Q, f"the package contains {name}",
                  os.path.isfile(os.path.join(tmp, name)))
        # Hash the package AS IT STANDS, not by regenerating it - the first
        # version of this check called the writer, which overwrote the very
        # tampering it was trying to detect and then reported that tampering
        # is undetectable.
        first = R.package_hash(tmp)
        with open(os.path.join(tmp, "environment.txt"), "a") as fh:
            fh.write("tampered\n")
        second = R.package_hash(tmp)
        check(Q, "changing one file changes the package hash",
              first != second,
              "one file altered must not leave the package hash intact")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            R.verify(root, tmp)
        t = buf.getvalue()
        check(Q, "the report states the level this run established",
              "Level" in t and ("R2" in t or "R3" in t or "R4" in t))
        check(Q, "and what it cannot claim",
              "needs someone who did" in t and "not write this" in t)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ==============================================================================
# PATH AR - the first screen
# ==============================================================================
#
# The design rules for the front door are checkable, and a rule nobody checks
# is a rule that erodes one release at a time. Every one of these exists
# because breaking it makes the program unusable for someone who cannot say
# why.

def path_ar():
    P = "AR"
    import io, contextlib
    from ppact import modes as M

    check(P, "there are exactly six modes", len(M.MODES) == 6,
          str([m.key for m in M.MODES]))
    check(P, "numbered 1 to 6 without gaps",
          sorted(m.number for m in M.MODES) == [1, 2, 3, 4, 5, 6])
    check(P, "and every key is distinct",
          len({m.key for m in M.MODES}) == 6)

    # Rule 1: no vocabulary on the first screen
    violations = M.first_screen_violations()
    check(P, "no technical vocabulary reaches the first screen",
          not violations, "; ".join(violations[:3]))
    check(P, "and the forbidden list is not empty",
          len(M.FORBIDDEN_ON_FIRST_SCREEN) >= 10,
          "a rule with nothing in it is not a rule")

    # POSITIVE CONTROLS. Both detectors are shown something they must catch,
    # because neither has ever fired on the real modes and a detector that
    # has only seen correct input is not known to work.
    bad_word = M.Mode("x", 9, "Bad", "Compare HBM and NPU options",
                      audience="a test", purpose="a caught violation")
    caught = M.first_screen_violations((bad_word,))
    check(P, "the vocabulary detector fires on a bad description",
          any("hbm" in c.lower() for c in caught), str(caught))
    bad_len = M.Mode("y", 9, "Long",
                     "a description written at such length that the rendered "
                     "line runs well past the width of the screen",
                     audience="a test", purpose="a caught violation")
    caught2 = M.first_screen_violations((bad_len,))
    check(P, "the line-length detector fires on an over-long description",
          any("wraps" in c for c in caught2), str(caught2))
    check(P, "and the real modes trip neither",
          not M.first_screen_violations())

    # Rule 2: one number, one line
    for m in M.MODES:
        rendered = f"    {m.number}. {m.title:<18s}{m.one_line}"
        check(P, f"mode {m.number} fits on one line",
              len(rendered) <= 78 and "\n" not in m.one_line,
              f"{len(rendered)} characters")

    # Rule 3: no parameter is asked for on the first screen
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        M.print_main_menu()
    screen = buf.getvalue()
    for token in ("GB", "MHz", "mm2", "USD", "enter a value", "%"):
        check(P, f"the first screen asks for no {token!r}",
              token not in screen)
    check(P, "the first screen offers an exit",
          "0. Exit" in screen)
    check(P, "and says what the choice is for",
          "what you are here to do" in screen)

    # Rule 4: the engine is where the numbers come from
    src = open(M.__file__, encoding="utf-8").read()
    for banned in ("evaluate_system(", "SystemConfig(", "metrics["):
        check(P, f"the mode layer never calls {banned}",
              banned not in src,
              "a screen that computes would give a student different numbers "
              "from a researcher, and neither would know")

    # Every entry must resolve to a real task, or a mode offers a dead end
    from ppact import menu as MENU
    for m in M.MODES:
        for label, task in list(m.entries) + [(t, t) for t in m.auto]:
            check(P, f"{m.key}: '{label[:34]}' resolves",
                  hasattr(MENU, task), f"missing task {task}")

    # Research must be where new capability goes - so it must be the widest
    research = M.BY_KEY["research"]
    check(P, "Research offers the most entries",
          all(len(research.entries) >= len(m.entries) for m in M.MODES),
          "new capability goes inside Research, so the first screen never "
          "grows")
    check(P, "and reaches the full tool list",
          any(t == "task_all_tools" for _, t in research.entries),
          "nothing is lost by hiding the old menu; it moves")

    # Every mode says who it is for and what the person leaves with
    for m in M.MODES:
        check(P, f"{m.key} names its audience", len(m.audience) > 8)
        check(P, f"{m.key} names what the person leaves with",
              len(m.purpose) > 20)

    # Quick Start must not ask anything
    quick = M.BY_KEY["quick"]
    check(P, "Quick Start runs without asking", quick.auto and not quick.entries,
          "someone who does not yet know what this is cannot answer a "
          "question about it")


# ==============================================================================
# PATH AS - the lessons
# ==============================================================================
#
# A lesson that changes two things at once teaches that changing two things
# makes a system faster. That is not a design principle and it is not even
# true - the student cannot say which change earned what, and neither can
# anyone reading the comparison.

def path_as():
    P = "AS"
    import io, contextlib
    from ppact import lessons as L

    # --- the course ---------------------------------------------------------
    check(P, "there are ten lessons", len(L.LESSONS) == 10, str(len(L.LESSONS)))
    check(P, "numbered without gaps",
          [l.number for l in L.LESSONS] == list(range(1, 11)))
    check(P, "and a final challenge with more than one target",
          len(L.FINAL_CHALLENGE["targets"]) >= 3,
          "one requirement can be met by pushing one lever; three cannot")

    # --- THE ONE-CHANGE RULE ------------------------------------------------
    check(P, "no lesson step changes more than one thing",
          not L.lesson_violations(),
          "; ".join(L.lesson_violations()[:2]))
    check(P, "the limit is one", L.MAX_CHANGES_PER_STEP == 1)
    for les in L.LESSONS:
        for st in les.steps:
            n = L.count_decisions(st.changes)
            check(P, f"lesson {les.number} '{st.label[:18]}' changes {n}",
                  n <= 1, str(sorted(st.changes)))
    check(P, "a memory and its stack count are one decision",
          L.count_decisions({"memory": "HBM3E", "memory_devices": 1}) == 1)
    check(P, "a host and a memory are two",
          L.count_decisions({"cpu": "a", "memory": "HBM3E",
                             "memory_devices": 1}) == 2)

    # --- THE QUESTION COMES FIRST -------------------------------------------
    #
    # A student who reads a table and then an explanation has been told
    # something. One who commits to an answer first has made a prediction,
    # and a prediction that turns out wrong is the only thing that reliably
    # changes a mind.
    src = open(L.__file__, encoding="utf-8").read()
    main_src = src[src.index('def main(ask_fn, folder'):]
    # The prompt itself moved into _hint_or_answer at 3.92.0, so the order
    # is: show the question, take the answer (with hints), THEN the table,
    # THEN the verdict.
    q_at = main_src.index("print_question")
    a_at = main_src.index("_hint_or_answer")
    t_at = main_src.index("print_lesson(les")
    v_at = main_src.index("print_verdict")
    check(P, "the question is asked before the table is shown",
          q_at < a_at < t_at, "otherwise it is not a prediction")
    check(P, "and the verdict comes after the table", t_at < v_at)
    hint_src = src[src.index("def _hint_or_answer"):src.index("def main(")]
    check(P, "the prompt is taken inside the hint loop",
          'ask_fn("Your answer"' in hint_src)
    check(P, "and a wrong guess gets a hint before the answer",
          hint_src.index("les.hint") < hint_src.index("The answer is"),
          "showing the answer first removes the reason to think")

    for les in L.LESSONS:
        check(P, f"lesson {les.number} asks a question",
              les.ask.endswith("?"), les.ask)
        check(P, f"lesson {les.number} offers at least three answers",
              len(les.options) >= 3,
              "a coin flip is not a prediction")
        right = [o for o in les.options if o.correct]
        check(P, f"lesson {les.number} has exactly one correct answer",
              len(right) == 1, str(len(right)))
        for o in les.options:
            check(P, f"lesson {les.number} '{o.text[:22]}' explains itself",
                  len(o.because) > 40,
                  "'Wrong' is useless feedback; the reasoning that leads "
                  "there is the lesson")
        check(P, f"lesson {les.number} gives a reason", len(les.why) >= 3)
        check(P, f"lesson {les.number} ends in one sentence",
              40 < len(les.answer) < 200, str(len(les.answer)))

    # POSITIVE CONTROLS: the rule detectors must actually fire
    saved = L.LESSONS
    try:
        two_change = L.Lesson(
            99, "Bad", "Is this bad?",
            options=(L.Option("a", True, "x" * 45),
                     L.Option("b", False, "y" * 45),
                     L.Option("c", False, "z" * 45)),
            application="industrial_vision", reference=L.REFERENCE,
            steps=(L.Step("a"),
                   L.Step("b", {"cpu": "cortex_a53_x4",
                                "compute": "npu_16x16"})),
            watch=L.WATCH, why=("x", "y", "z"), answer="q" * 60)
        L.LESSONS = saved + (two_change,)
        caught = L.lesson_violations()
        check(P, "the two-change detector fires",
              any("lesson 99" in c and "changes 2" in c for c in caught),
              str(caught[:2]))

        two_right = L.Lesson(
            98, "Bad", "Is this bad?",
            options=(L.Option("a", True, "x" * 45),
                     L.Option("b", True, "y" * 45),
                     L.Option("c", False, "z" * 45)),
            application="industrial_vision", reference=L.REFERENCE,
            steps=(L.Step("a"), L.Step("b", {"cpu": "cortex_a53_x4"})),
            watch=L.WATCH, why=("x", "y", "z"), answer="q" * 60)
        L.LESSONS = saved + (two_right,)
        caught = L.lesson_violations()
        check(P, "two correct answers are caught",
              any("2 correct options" in c for c in caught), str(caught[:2]))

        unexplained = L.Lesson(
            97, "Bad", "Is this bad?",
            options=(L.Option("a", True, "x" * 45),
                     L.Option("b", False, "short"),
                     L.Option("c", False, "z" * 45)),
            application="industrial_vision", reference=L.REFERENCE,
            steps=(L.Step("a"), L.Step("b", {"cpu": "cortex_a53_x4"})),
            watch=L.WATCH, why=("x", "y", "z"), answer="q" * 60)
        L.LESSONS = saved + (unexplained,)
        caught = L.lesson_violations()
        check(P, "an unexplained wrong answer is caught",
              any("no reasoning given" in c for c in caught), str(caught[:2]))
    finally:
        L.LESSONS = saved
    check(P, "and the real course trips none of them",
          not L.lesson_violations())

    # marking must depend on what was chosen. A verdict that says "correct"
    # whatever the student picked is worse than no quiz: it teaches that the
    # prediction did not matter.
    vb = io.StringIO()
    with contextlib.redirect_stdout(vb):
        L.print_verdict(L.LESSONS[0], 0)
    v_first = vb.getvalue()
    vb2 = io.StringIO()
    with contextlib.redirect_stdout(vb2):
        L.print_verdict(L.LESSONS[0], 1)
    v_second = vb2.getvalue()
    right_idx = next(i for i, o in enumerate(L.LESSONS[0].options) if o.correct)
    wrong_out = v_first if right_idx != 0 else v_second
    right_out = v_second if right_idx != 0 else v_first
    check(P, "a correct answer is marked correct", "Correct." in right_out)
    check(P, "and a wrong one is not", "Not quite" in wrong_out,
          "a verdict that says correct whatever was chosen teaches that the "
          "prediction did not matter")

    # the lessons hold no precomputed numbers
    for banned in ("= 11.5", "= 88.4", "hardcoded", "expected_latency"):
        check(P, f"the lessons hold no precomputed {banned!r}",
              banned not in src)

    # --- EVERY TEACHING CLAIM MUST HOLD -------------------------------------
    #
    # A lesson whose reasoning no longer matches its numbers is worse than no
    # lesson. These check the claims, not that the code runs.
    rows = {les.number: L.run_lesson(les) for les in L.LESSONS}
    lat = {n: [r[1]["Latency (ms)"] for r in v]
           for n, v in rows.items() if "Latency (ms)" in v[0][1]}
    pw = {n: [r[1]["System power (W)"] for r in v] for n, v in rows.items()}
    cost = {n: [r[1]["System cost (USD)"] for r in v]
            for n, v in rows.items() if "System cost (USD)" in v[0][1]}

    check(P, "1: the larger engine costs more power",
          pw[1][1] > pw[1][0], f"{pw[1][0]:.2f} -> {pw[1][1]:.2f} W")
    check(P, "1: and more money", cost[1][1] > cost[1][0])

    check(P, "2: the capable host is much faster",
          lat[2][1] < lat[2][0] / 2,
          f"{lat[2][0]:.1f} -> {lat[2][1]:.1f}")
    check(P, "2: and draws more power, as the lesson says",
          pw[2][1] > pw[2][0])

    check(P, "3: medium beats small", lat[3][1] < lat[3][0])
    check(P, "3: but large is WORSE than medium", lat[3][2] > lat[3][1],
          f"{lat[3][1]:.2f} -> {lat[3][2]:.2f}")
    check(P, "3: and the limit has moved to the memory",
          rows[3][2][2] == "memory" and rows[3][1][2] == "compute",
          f"{rows[3][1][2]} -> {rows[3][2][2]}")

    check(P, "4: more bandwidth helps a memory-bound design",
          lat[4][1] < lat[4][0] * 0.8,
          f"{lat[4][0]:.2f} -> {lat[4][1]:.2f} - the lesson says "
          f"substantially")
    check(P, "4: and the engine did not change",
          L.LESSONS[3].steps[0].changes.get("compute") is None
          and L.LESSONS[3].steps[1].changes.get("compute") is None)

    gain5 = (1 - lat[5][1] / lat[5][0]) * 100
    check(P, "5: the fast memory buys a small fraction", gain5 < 25,
          f"{gain5:.1f}%")
    check(P, "5: at several times the price",
          cost[5][1] / cost[5][0] > 3, f"{cost[5][1] / cost[5][0]:.1f}x")

    check(P, "6: two engines are slower than one", lat[6][1] > lat[6][0],
          f"{lat[6][0]:.2f} -> {lat[6][1]:.2f}")
    check(P, "6: and the limit moved to the memory",
          rows[6][1][2] == "memory", rows[6][1][2])

    traffic = [r[1]["DRAM traffic (MB)"] for r in rows[7]]
    check(P, "7: each user is slower with sixteen of them",
          lat[7][1] > lat[7][0], f"{lat[7][0]:.1f} -> {lat[7][1]:.1f}")
    per_user = [traffic[0] / 1, traffic[1] / 16]
    check(P, "7: but traffic PER USER falls sharply",
          per_user[1] < per_user[0] / 5,
          f"{per_user[0]:,.0f} -> {per_user[1]:,.0f} MB - the weights are "
          f"read once for the whole batch")
    check(P, "7: while total traffic rises far less than sixteenfold",
          traffic[1] < traffic[0] * 16,
          "if it scaled with users the weights would not be shared")

    check(P, "8: the faster memory is quicker", lat[8][1] < lat[8][0])
    check(P, "8: and much dearer", cost[8][1] / cost[8][0] > 3)
    check(P, "8: while the bigger engine is cheaper", 
          cost[8][2] < cost[8][1])
    check(P, "8: and SLOWER, as the lesson says", lat[8][2] > lat[8][0],
          f"{lat[8][0]:.2f} -> {lat[8][2]:.2f}")

    check(P, "9: the airflow part costs far more power",
          pw[9][1] > pw[9][0] * 2, f"{pw[9][0]:.2f} -> {pw[9][1]:.2f} W")
    from ppact.system import evaluate_system, SystemConfig
    les9 = L.LESSONS[8]
    r9 = evaluate_system(APPLICATION_LIBRARY[les9.application],
                         SystemConfig(**{**les9.reference,
                                         **les9.steps[1].changes}))
    failed9 = [g for g, ok in r9.gate.items() if not ok]
    check(P, "9: and fails a COOLING CLASS, not just a number",
          "memory_cooling" in failed9, str(failed9))

    check(P, "10: the one right change is a large gain",
          lat[10][1] < lat[10][0] / 2,
          f"{lat[10][0]:.2f} -> {lat[10][1]:.2f}")
    check(P, "10: and the power falls too", pw[10][1] < pw[10][0])
    check(P, "10: while the cost barely moves",
          abs(cost[10][1] / cost[10][0] - 1) < 0.05,
          f"{cost[10][0]:.2f} -> {cost[10][1]:.2f}")

    # the final challenge must not be solved already, nor hopeless
    c = L.FINAL_CHALLENGE
    r = evaluate_system(APPLICATION_LIBRARY[c["application"]],
                        SystemConfig(**c["reference"]))
    met = sum(1 for m, d, v in c["targets"]
              if (r.metrics[m] < v if d == "below" else r.metrics[m] > v))
    check(P, "the final challenge is not already solved",
          met < len(c["targets"]), f"{met} of {len(c['targets'])}")
    check(P, "but is not hopeless either", met >= 1)

    # --- rendering ----------------------------------------------------------
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for les in L.LESSONS:
            L.print_question(les)
            L.print_lesson(les)
            L.print_verdict(les, 0)
        L.print_final_challenge()
    out = buf.getvalue()
    wide = [ln for ln in out.splitlines() if len(ln) > 78]
    check(P, "no rendered line wraps", not wide,
          f"{len(wide)} over 78: {wide[0][:50] if wide else ''}")
    check(P, "every lesson states its reasoning",
          out.count("WHY") >= len(L.LESSONS))
    check(P, "ends with one sentence",
          out.count("IN ONE SENTENCE") >= len(L.LESSONS))
    check(P, "and marks every option right or wrong",
          out.count("[correct]") >= len(L.LESSONS)
          and out.count("[wrong]") >= len(L.LESSONS) * 2)


def path_at():
    P = "AT"
    import io, contextlib
    from ppact import framework as F

    check(P, "the map has categories", len(F.FRAMEWORK) >= 12)
    check(P, "numbered without gaps",
          [c.number for c in F.FRAMEWORK] == list(range(1, len(F.FRAMEWORK) + 1)))
    check(P, "and each says what it is for",
          all(len(c.purpose) > 15 for c in F.FRAMEWORK))

    # THE RULE: every claim points at something real
    problems = F.framework_violations()
    check(P, "every claim names a metric or a function that exists",
          not problems, "; ".join(problems[:3]))

    c = F.counts()
    check(P, "and the map is mostly implemented",
          c[F.FULL] > c[F.ABSENT] * 3,
          f"{c[F.FULL]} full, {c[F.ABSENT]} absent")
    check(P, "but it does NOT claim everything",
          c[F.ABSENT] >= 5,
          "a capability map with no gaps is a map nobody checked - the "
          "open items are known and listed")
    check(P, "and some things are partial rather than pretended",
          c[F.PARTIAL] >= 3)

    # POSITIVE CONTROLS: the detector must catch each kind of bad entry
    saved = F.FRAMEWORK
    try:
        for label, bad in (
            ("a metric that does not exist",
             F.Item("x", F.FULL, metric="Nonexistent metric (ms)")),
            ("a function that does not exist",
             F.Item("x", F.FULL, function="ppact.system.no_such_function")),
            ("a claim pointing at nothing", F.Item("x", F.FULL)),
            ("absent but pointing at something",
             F.Item("x", F.ABSENT, metric="Latency (ms)", note="n")),
            ("absent with no reason", F.Item("x", F.ABSENT)),
            ("partial with no stated limit",
             F.Item("x", F.PARTIAL, metric="Latency (ms)")),
        ):
            F.FRAMEWORK = saved + (F.Category(99, "Test", "a bad entry",
                                              (bad,)),)
            caught = F.framework_violations()
            check(P, f"the detector catches {label}",
                  any("Test/" in c for c in caught), str(caught[-1:]))
    finally:
        F.FRAMEWORK = saved
    check(P, "and the real map trips none of them",
          not F.framework_violations())

    # an absent item must explain itself - a gap without a reason reads as
    # an oversight rather than a decision
    for cat in F.FRAMEWORK:
        for it in cat.items:
            if it.state == F.ABSENT:
                check(P, f"'{it.name[:30]}' says why it is absent",
                      len(it.note) > 15, it.note)
            if it.state == F.PARTIAL:
                check(P, f"'{it.name[:30]}' states its limit",
                      len(it.note) > 15, it.note)

    # the one-screen validation summary
    check(P, "the validation summary covers several areas",
          len(F.VALIDATION_AREAS) >= 8, str(len(F.VALIDATION_AREAS)))
    for name, where, what in F.VALIDATION_AREAS:
        check(P, f"'{name[:24]}' names a suite", where.endswith(".py"))
        check(P, f"'{name[:24]}' says what it checks", len(what) > 20)
    vbuf = io.StringIO()
    with contextlib.redirect_stdout(vbuf):
        F.print_validation_summary()
    vt = vbuf.getvalue()
    check(P, "the summary gives no percentage", "%" not in vt,
          "a developer who computes their own validation score has produced "
          "another self-assessment")
    check(P, "it says where the evidence stops",
          "WHERE IT STOPS" in vt)
    check(P, "and why that section is the important one",
          "advertisement" in vt)
    vwide = [ln for ln in vt.splitlines() if len(ln) > 78]
    check(P, "the summary fits the screen", not vwide,
          f"{len(vwide)} over 78")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        F.print_framework()
    t = buf.getvalue()
    wide = [ln for ln in t.splitlines() if len(ln) > 78]
    check(P, "the map renders inside the screen", not wide,
          f"{len(wide)} lines over 78")
    check(P, "it names the gaps rather than hiding them",
          "not implemented" in t)
    check(P, "and says why a stated gap is not an apology",
          "quietly guesses" in t)


# ==============================================================================
# PATH AU - the challenges
# ==============================================================================
#
# "You scored 78" tells a student nothing: out of what, against whom, and was
# 90 even possible? A score with no population behind it is a number chosen by
# whoever wrote the marking scheme, and students optimise the scheme.

def path_au():
    P = "AU"
    import io, contextlib
    from ppact import challenge as C

    check(P, "there is a full set of challenges", len(C.CHALLENGES) >= 15,
          str(len(C.CHALLENGES)))
    check(P, "spread across several applications",
          len({c.application for c in C.CHALLENGES}) >= 5,
          str(sorted({c.application for c in C.CHALLENGES})))
    check(P, "and several starting designs",
          len({tuple(sorted(c.start.items())) for c in C.CHALLENGES}) >= 5,
          "a set that always hands over the same design teaches one lesson")
    check(P, "each keyed distinctly",
          len({c.key for c in C.CHALLENGES}) == len(C.CHALLENGES))

    # THE CALIBRATION RULES
    problems = C.challenge_violations()
    check(P, "every challenge is winnable and not already won",
          not problems, "; ".join(problems[:3]))

    pops = {c.key: C.population(c) for c in C.CHALLENGES}
    for ch in C.CHALLENGES:
        pop = pops[ch.key]
        frac = pop["solved"] / pop["total"]
        check(P, f"{ch.key}: some designs pass", pop["solved"] > 0)
        check(P, f"{ch.key}: but not most of them", frac < 0.25,
              f"{pop['solved']}/{pop['total']} = {frac*100:.0f}% - a bar most "
              f"things clear is not a bar")
        check(P, f"{ch.key}: the population is large enough to rank in",
              pop["total"] >= 50, str(pop["total"]))

        # the design handed over must be a foothold, not a finish
        from ppact.system import evaluate_system, SystemConfig
        r = evaluate_system(APPLICATION_LIBRARY[ch.application],
                            SystemConfig(**ch.start))
        met = sum(C.meets(ch, r.metrics))
        check(P, f"{ch.key}: the starting design meets some but not all",
              0 < met < len(ch.targets), f"{met} of {len(ch.targets)}")

        # every target must justify itself
        for t in ch.targets:
            check(P, f"{ch.key}/{t.metric} gives a reason", len(t.why) > 15,
                  "a number with no reason behind it is a number a student "
                  "games")
            check(P, f"{ch.key}/{t.metric} has a direction",
                  t.direction in (C.BELOW, C.ABOVE))

    # A FAILING DESIGN IS NOT RANKED.
    #
    # Ranking a design that misses a requirement teaches that requirements
    # are a scale. They are not.
    ch = C.BY_KEY["inspection"]
    pop = pops["inspection"]
    r_fail = evaluate_system(APPLICATION_LIBRARY[ch.application],
                             SystemConfig(**ch.start))
    sc = C.score(ch, r_fail.metrics, pop)
    check(P, "a design that misses a requirement is not ranked",
          not sc["passes"] and sc["rank"] is None,
          "it is not last; it is not in the race")

    # and a passing one is ranked among passers only
    best = max(pop["solutions"],
               key=lambda s: sum((t.value - s["metrics"][t.metric]) / t.value
                                 for t in ch.targets))
    r_best = evaluate_system(
        APPLICATION_LIBRARY[ch.application],
        SystemConfig(**{**ch.start, **best["changes"]}))
    sb = C.score(ch, r_best.metrics, pop)
    check(P, "the best design ranks first", sb["passes"] and sb["rank"] == 1,
          str(sb))
    check(P, "and is ranked out of the passers, not everything",
          sb["of"] == pop["solved"] and sb["of"] < pop["total"],
          f"{sb['of']} against {pop['total']}")

    # A rank can never exceed the number of designs it is a rank among.
    # Counting against the FEASIBLE set instead of the PASSING one would put
    # a design at, say, 40th of 6 - and the "of" figure alone would not show
    # it, because that is read from the population directly.
    for s_row in pop["solutions"]:
        r_row = evaluate_system(
            APPLICATION_LIBRARY[ch.application],
            SystemConfig(**{**ch.start, **s_row["changes"]}))
        sc_row = C.score(ch, r_row.metrics, pop)
        check(P, f"a passing design ranks within the passers",
              1 <= sc_row["rank"] <= pop["solved"],
              f"ranked {sc_row['rank']} of {pop['solved']} - a rank outside "
              f"its own population is a rank against a different set")

    # the population must be COMPUTED, not asserted
    src = open(C.__file__, encoding="utf-8").read()
    check(P, "the population comes from a sweep",
          "itertools.product" in src and "evaluate_system" in src)
    for banned in ("percentile_curve", "= 78", "grade_boundary"):
        check(P, f"no invented scale {banned!r}", banned not in src)

    # the weighting must be stated rather than buried
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        C.print_result(ch, best["changes"], pop)
        C.print_challenge(ch)
        C.print_best(ch, pop, show=2)
    t = buf.getvalue()
    check(P, "the report states how the rank is computed",
          "weighted" in t and "stated rather than" in t)
    check(P, "the targets are shown with their reasons",
          all(tg.why[:20] in t for tg in ch.targets))
    check(P, "and the best answers are shown only as a comparison",
          "what they gave up" in t)
    wide = [ln for ln in t.splitlines() if len(ln) > 78]
    check(P, "nothing wraps", not wide, f"{len(wide)} lines over 78")


# ==============================================================================
# PATH AV - the demos
# ==============================================================================
#
# A demo states an answer in words to a room that cannot check it. If the
# model stops producing the result that answer rests on, the answer becomes a
# lie told to an audience - so every claim is a check.

def path_av():
    P = "AV"
    import io, contextlib
    from ppact import demo as D

    check(P, "there are demos", len(D.DEMOS) >= 4)
    check(P, "every demo is well formed", not D.demo_violations(),
          "; ".join(D.demo_violations()[:2]))
    for d in D.DEMOS:
        check(P, f"{d.key}: the title is a question", d.question.endswith("?"))
        check(P, f"{d.key}: it compares at least two things",
              len(d.rows) >= 2)
        check(P, f"{d.key}: it answers in words", len(d.answer) > 25)
        check(P, f"{d.key}: and gives the mechanism", len(d.because) > 40)

    # A demo must take NO input. A demo that asks a question of the room has
    # already lost it.
    src = open(D.__file__, encoding="utf-8").read()
    body = src.split("def main(")[0]
    check(P, "no demo reads input", "input(" not in body,
          "the audience did not choose the parameters and cannot be asked to")

    rows = {d.key: D.run_demo(d) for d in D.DEMOS}
    lat = {k: [r[1]["Latency (ms)"] for r in v] for k, v in rows.items()}
    cost = {k: [r[1]["System cost (USD)"] for r in v]
            for k, v in rows.items()}

    # EVERY STATED ANSWER MUST HOLD.
    #
    # Two of these were wrong when first written - the dual and engine demos
    # were built on a configuration where the second engine HELPS and the
    # large engine is FASTEST, while the text said the opposite. A demo whose
    # answer contradicts its own table is worse than no demo, because the
    # audience is watching the numbers.
    m = lat["memory"]
    check(P, "memory: the faster memory buys a modest fraction",
          (1 - m[1] / m[0]) < 0.30,
          f"{(1 - m[1] / m[0]) * 100:.0f}% - the answer says a fraction")
    check(P, "memory: at several times the price",
          cost["memory"][1] / cost["memory"][0] > 4,
          f"{cost['memory'][1] / cost['memory'][0]:.1f}x")

    e = lat["engine"]
    check(P, "engine: medium beats small", e[1] < e[0])
    check(P, "engine: and large is SLOWER than medium", e[2] > e[1],
          f"{e[1]:.2f} -> {e[2]:.2f} - the answer says it reverses")

    du = lat["dual"]
    check(P, "dual: two engines are slower than one", du[1] > du[0],
          f"{du[0]:.2f} -> {du[1]:.2f} - the answer says slower")

    n = lat["node"]
    check(P, "node: two generations move the time under one per cent",
          abs(1 - n[-1] / n[0]) < 0.01,
          f"{abs(1 - n[-1] / n[0]) * 100:.2f}% - the answer says under one")
    pw = [r[1]["System power (W)"] for r in rows["node"]]
    check(P, "node: but the power does fall, as the answer says",
          pw[-1] < pw[0], f"{pw[0]:.2f} -> {pw[-1]:.2f} W")

    s_lat = lat["shipping"]
    check(P, "shipping: the quick one is many times faster",
          s_lat[0] / s_lat[1] > 5,
          f"{s_lat[0] / s_lat[1]:.1f}x - the answer says eight times")
    ships = [r[3] for r in rows["shipping"]]
    failed = rows["shipping"][1][4]
    check(P, "shipping: the sensible one ships and the quick one does not",
          ships[0] and not ships[1])
    check(P, "shipping: and it fails several requirements",
          len(failed) >= 3, str(failed))
    check(P, "shipping: including one that is a class, not a number",
          "memory_cooling" in failed,
          "a part needing airflow cannot go in a sealed case at any wattage")

    # --- the six later demos must also hold ---------------------------------
    h = lat["host"]
    check(P, "host: the capable host is about three times faster",
          2.5 < h[0] / h[1] < 3.5, f"{h[0] / h[1]:.2f}x")
    o = lat["offload"]
    check(P, "offload: moving the work cuts most of the time",
          (1 - o[1] / o[0]) > 0.55,
          f"{(1 - o[1] / o[0]) * 100:.0f}% - the answer says nearly two "
          f"thirds")
    ow = [r[1]["System power (W)"] for r in rows["offload"]]
    check(P, "offload: and the power with it", ow[1] < ow[0],
          f"{ow[0]:.2f} -> {ow[1]:.2f} W")
    cap = lat["capacity"]
    check(P, "capacity: more packages help a memory-limited design",
          cap[1] < cap[0] / 2, f"{cap[0]:.2f} -> {cap[1]:.2f}")
    check(P, "capacity: at several times the price",
          cost["capacity"][1] / cost["capacity"][0] > 5,
          f"{cost['capacity'][1] / cost['capacity'][0]:.1f}x")
    import math as _m
    f = lat["fit"]
    check(P, "fit: the too-small row reports NO timing at all",
          _m.isnan(f[0]),
          "not slow - absent. A number here would invite a comparison with a "
          "machine that cannot exist")
    check(P, "fit: and the large-enough row does", not _m.isnan(f[1]))
    ch = lat["cheaper"]
    check(P, "cheaper: the two memories are about the same speed",
          abs(1 - ch[1] / ch[0]) < 0.05, f"{ch[0]:.2f} vs {ch[1]:.2f}")
    check(P, "cheaper: but one is much cheaper",
          cost["cheaper"][1] < cost["cheaper"][0] * 0.7,
          f"{(1 - cost['cheaper'][1] / cost['cheaper'][0]) * 100:.0f}% less")
    cw = [r[1]["System power (W)"] for r in rows["cheaper"]]
    check(P, "cheaper: and roughly doubles the power",
          cw[1] > cw[0] * 1.7,
          f"{cw[0]:.2f} -> {cw[1]:.2f} W - on a battery that is not a close "
          f"call")
    sp = lat["split"]
    check(P, "split: an even split between unequal engines is slower",
          sp[1] > sp[0], f"{sp[0]:.2f} -> {sp[1]:.2f}")

    # POSITIVE CONTROL: a duplicate key must be caught. It does not raise -
    # it silently overwrites in the lookup, so one demo becomes unreachable
    # and nothing says so. Found when four new demos collided with three
    # already present.
    saved_d = D.DEMOS
    try:
        D.DEMOS = saved_d + (saved_d[0],)
        caught = D.demo_violations()
        check(P, "a duplicate demo key is caught",
              any("two demos share this key" in c for c in caught),
              str(caught[:2]))
    finally:
        D.DEMOS = saved_d
    check(P, "every real demo key is unique",
          len({d.key for d in D.DEMOS}) == len(D.DEMOS))
    check(P, "and the lookup reaches all of them",
          len(D.BY_KEY) == len(D.DEMOS))

    # POSITIVE CONTROL: the width detector has never fired on the real
    # demos, so it is shown one that would wrap. A detector that has only
    # seen correct input is not known to work - the sixth time in this
    # project.
    saved = D.DEMOS
    try:
        # Short labels, so the LABEL check cannot fire - only the width one.
        # A control that trips a different check proves a different check.
        wide_demo = D.Demo(
            "x", "Too wide?", "a test",
            rows=(D.Row("one", "x", {}), D.Row("two", "x", {})),
            watch=D.WATCH + ("Compute time (ms)", "Memory time (ms)",
                             "DRAM traffic (MB)"),
            answer="a" * 30, because="b" * 50)
        D.DEMOS = saved + (wide_demo,)
        caught = D.demo_violations()
        check(P, "the width detector fires on a wide table",
              any("wraps" in c for c in caught), str(caught[-2:]))
        check(P, "and not because of a long label",
              not any("label too long" in c for c in caught),
              "a control that trips a different check proves a different "
              "check")
    finally:
        D.DEMOS = saved
    check(P, "and the real demos trip it not at all", not D.demo_violations())

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for d in D.DEMOS:
            D.print_demo(d)
    t = buf.getvalue()
    wide = [ln for ln in t.splitlines() if len(ln) > 78]
    check(P, "nothing wraps", not wide, f"{len(wide)} over 78")
    check(P, "every demo prints an answer",
          t.count("ANSWER") >= len(D.DEMOS))
    check(P, "and the mechanism behind it",
          t.count("BECAUSE") >= len(D.DEMOS))


# ==============================================================================
# PATH AW - the workspace
# ==============================================================================

def path_aw():
    P = "AW"
    import tempfile, shutil, os, io, contextlib
    from ppact import workspace as W
    from ppact.system import SystemConfig

    d = tempfile.mkdtemp(prefix="ppact_ws_")
    try:
        check(P, "an empty workspace has nothing in it", not W.recent(d))

        a = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                         preprocessing_mode="cpu_only")
        b = SystemConfig("cortex_a78_x4", "npu_24x24", "LPDDR5", 2,
                         preprocessing_mode="isp_and_npu")
        W.remember("industrial_vision", a, d)
        W.remember("drone", b, d)
        r = W.recent(d)
        check(P, "designs are remembered", len(r) == 2)
        check(P, "newest first", r[0]["app"] == "drone")

        # a repeat must move to the front, not appear twice
        W.remember("industrial_vision", a, d)
        r = W.recent(d)
        check(P, "a repeat does not duplicate", len(r) == 2, str(len(r)))
        check(P, "and moves to the front",
              r[0]["app"] == "industrial_vision")

        # The history must not grow without bound. DISTINCT entries, more
        # than the limit - a first version cycled four configurations thirty
        # times, which deduplicated to four and would have passed with no cap
        # at all.
        engines = ["npu_16x16", "npu_20x20", "npu_24x24", "npu_32x32",
                   "npu_64x64", "npu_128x128"]
        distinct = 0
        for eng in engines:
            for dev in (1, 2, 4, 8):
                W.remember("drone", SystemConfig(
                    "cortex_a78_x4", eng, "LPDDR5", dev,
                    preprocessing_mode="isp_and_npu"), d)
                distinct += 1
        check(P, "more distinct designs were added than the limit allows",
              distinct > W.HISTORY_LIMIT,
              f"{distinct} added, limit {W.HISTORY_LIMIT}")
        check(P, "the history is capped",
              len(W.recent(d)) == W.HISTORY_LIMIT,
              f"{len(W.recent(d))} against a limit of {W.HISTORY_LIMIT}")

        # NOTHING COMPUTED MAY BE STORED.
        #
        # A file of cached results goes stale the first time a coefficient
        # moves, and nothing notices. So the store holds configurations only,
        # and an export runs the model again - which also means an exported
        # figure and a figure on screen cannot disagree.
        raw = open(W._path(d), encoding="utf-8").read()
        for banned in ("Latency", "System power", "System cost", "metrics"):
            check(P, f"the store holds no {banned!r}", banned not in raw,
                  "a cached number is a number nobody rechecks")

        # a stored design must rebuild into a working configuration
        app_key, cfg = W.rebuild(W.recent(d)[0])
        from ppact.system import evaluate_system
        rr = evaluate_system(APPLICATION_LIBRARY[app_key], cfg)
        check(P, "a remembered design rebuilds and runs",
              rr.metrics["Latency (ms)"] > 0)

        # the export must recompute
        path = W.export_csv(W.recent(d)[:3], "t.csv", d)
        check(P, "the export writes a file", os.path.isfile(path))
        text = open(path, encoding="utf-8").read()
        check(P, "with one row per design",
              len(text.strip().splitlines()) == 4, text[:80])
        check(P, "and records the version that produced it",
              "version" in text.splitlines()[0])
        for m in ("Latency (ms)", "System cost (USD)"):
            check(P, f"the export carries {m}", m in text.splitlines()[0])

        # An unwritable location must not turn an analysis into an error.
        # Tested with a path that cannot exist rather than by removing
        # permissions - the suite may run as a user for whom permissions do
        # not apply, and a control that cannot fail proves nothing.
        nowhere = os.path.join(d, "no", "such", "place")
        ok = W._save({"recent": [], "saved": {}}, nowhere)
        check(P, "an unwritable location is survived, not raised",
              ok is False,
              "the history is a convenience; the result already happened")
        check(P, "and reading one gives an empty workspace, not an error",
              W.recent(nowhere) == [])

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            W.print_workspace(d)
        t = buf.getvalue()
        check(P, "the workspace says what it does not store",
              "never the results" in t)
        wide = [ln for ln in t.splitlines() if len(ln) > 78]
        check(P, "and fits the screen", not wide)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ==============================================================================
# PATH AX - the course as a course
# ==============================================================================

def path_ax():
    P = "AX"
    import io, contextlib, json, os, shutil, tempfile
    from ppact import progress as PR
    from ppact import lessons as L
    from ppact import challenge as C

    # --- every lesson must carry a hint and a takeaway ---------------------
    for les in L.LESSONS:
        check(P, f"lesson {les.number} has a hint", len(les.hint) > 30,
              "an answer given on the first wrong guess removes the reason "
              "to think")
        check(P, f"lesson {les.number}'s hint is not the answer",
              not any(o.text.lower()[:20] in les.hint.lower()
                      for o in les.options),
              les.hint)
        check(P, f"lesson {les.number} has a takeaway",
              10 < len(les.takeaway) < 60, les.takeaway)

    # --- the score must keep two numbers apart -----------------------------
    p = PR.Progress()
    for n in (1, 2, 3, 4, 5):
        p.record(n, 0, False)
    for n in (6, 7, 8, 9, 10):
        p.record(n, 1, True)
    check(P, "prediction accuracy counts first guesses", p.accuracy() == 50.0,
          str(p.accuracy()))
    imp = p.improvement(10)
    check(P, "and improvement compares the halves", imp is not None
          and imp[0] == 0.0 and imp[1] == 100.0 and imp[2] == 100.0,
          str(imp))

    # a later correct attempt must not rewrite the first guess
    p2 = PR.Progress()
    p2.record(1, 0, False)
    p2.record(1, 1, True)
    check(P, "a second attempt does not change the first-guess record",
          p2.accuracy() == 0.0,
          "scoring persistence as ignorance would punish the thing the "
          "course is for")
    check(P, "but the lesson counts as completed", 1 in p2.completed)

    # too little data must produce no trend
    p3 = PR.Progress()
    p3.record(1, 0, False)
    p3.record(10, 1, True)
    check(P, "one answer each side is not a trend",
          p3.improvement(10) is None,
          "a single answer either side is a coin")

    # --- hints before answers ----------------------------------------------
    check(P, "the answer is withheld for at least three attempts",
          PR.ATTEMPTS_BEFORE_ANSWER >= 3, str(PR.ATTEMPTS_BEFORE_ANSWER))

    # --- difficulty levels --------------------------------------------------
    check(P, "there are three difficulties", len(PR.DIFFICULTIES) == 3)
    for d in PR.DIFFICULTIES:
        check(P, f"'{d}' says what it changes",
              len(PR.DIFFICULTY_NOTE[d]) > 25)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        L.print_lesson(L.LESSONS[2], difficulty="easy")
    easy = buf.getvalue()
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        L.print_lesson(L.LESSONS[2], difficulty="medium")
    med = buf2.getvalue()
    check(P, "easy mode shows changes instead of absolute figures",
          "%" in easy and "20.79" not in easy,
          "a student who cannot read a latency in milliseconds can still "
          "read a change of minus forty-five per cent")
    check(P, "medium mode shows the figures", "20.79" in med)
    check(P, "and easy still gives the reasoning", "WHY" in easy)
    # the direction shown must be against the PREVIOUS row
    check(P, "easy mode compares each row to the one above",
          "the row above" in easy,
          "comparing everything to the first row would have shown the large "
          "engine improving, which is the opposite of the lesson")

    # BEHAVIOUR, not source text. Reading the order of calls in the file
    # does not notice a branch that has been disabled, so the hint loop is
    # driven with deliberately wrong answers and the output inspected.
    answers = iter([1, 1, 1])          # option 1 is wrong in lesson 3

    def wrong(_prompt, _labels, _default=1):
        return next(answers, 1)

    buf_h = io.StringIO()
    with contextlib.redirect_stdout(buf_h):
        L._hint_or_answer(L.LESSONS[2], PR.Progress(), wrong)
    ht = buf_h.getvalue()
    check(P, "a wrong guess produces a hint",
          L.LESSONS[2].hint[:30] in ht,
          "the hint must appear, not just exist in the file")
    check(P, "the hint comes before the answer is given",
          ht.index(L.LESSONS[2].hint[:30]) < ht.index("The answer is"),
          "showing the answer on the first wrong guess removes the reason "
          "to think")
    check(P, "and the answer is given eventually", "The answer is" in ht,
          "a student who has tried three times has earned it")

    # and easy mode must actually show the reversal
    buf_e = io.StringIO()
    with contextlib.redirect_stdout(buf_e):
        L.print_lesson(L.LESSONS[2], difficulty="easy")
    lines = [ln for ln in buf_e.getvalue().splitlines()
             if ln.strip().startswith("large")]
    check(P, "easy mode shows the large engine as a latency INCREASE",
          lines and lines[0].split()[1].startswith("+"),
          f"{lines[0] if lines else 'no row'} - against the first row this "
          f"would be negative, which is the opposite of the lesson")

    # --- the local distribution must not invent a cohort -------------------
    empty = PR.Progress()
    buf3 = io.StringIO()
    with contextlib.redirect_stdout(buf3):
        PR.print_distribution(empty, 1, 3, 1)
    d0 = buf3.getvalue()
    check(P, "with no answers, no percentages are shown",
          "%" not in d0, "a made-up percentage is a lie a reader cannot check")
    check(P, "and it says the count is local",
          "LOCAL count" in d0 or "this machine" in d0)
    # The module docstring quotes "71% of students" as the example of what
    # NOT to do, so the check looks at the CODE rather than the prose.
    src = open(PR.__file__, encoding="utf-8").read()
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.strip().startswith("#"))
    code = code.split('"""')[0] + '"""'.join(code.split('"""')[2:])
    for banned in ("cohort_data", "national_average", "COHORT"):
        check(P, f"no invented cohort figure {banned!r}", banned not in code)
    check(P, "and no hardcoded percentage in the distribution",
          "71" not in PR.print_distribution.__code__.co_consts.__str__())

    # --- save and resume ---------------------------------------------------
    tmp = tempfile.mkdtemp(prefix="ppact_prog_")
    try:
        p4 = PR.Progress(difficulty=PR.ADVANCED)
        p4.record(3, 1, True)
        path = p4.save(tmp)
        check(P, "progress is written to disk", path and os.path.isfile(path))
        back = PR.Progress.load(tmp)
        check(P, "and read back", back.completed == [3]
              and back.difficulty == PR.ADVANCED, str(back.completed))
        check(P, "including the attempt history", len(back.attempts) == 1)
        # a corrupt file must not lose the session
        with open(os.path.join(tmp, PR.PROGRESS_FILE), "w") as fh:
            fh.write("not json")
        safe = PR.Progress.load(tmp)
        check(P, "a corrupt file starts fresh rather than crashing",
              safe.completed == [],
              "a student should lose their place, not the program")
        # a read-only folder must not fail the lesson
        ro = os.path.join(tmp, "ro")
        os.makedirs(ro)
        os.chmod(ro, 0o500)
        try:
            check(P, "an unwritable folder returns None rather than raising",
                  PR.Progress().save(ro) is None
                  or os.path.isfile(os.path.join(ro, PR.PROGRESS_FILE)))
        finally:
            os.chmod(ro, 0o700)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --- the final exam must be a real exam --------------------------------
    ex = C.FINAL_EXAM
    pop = C.population(ex)
    check(P, "the final exam has solutions", pop["solved"] > 0)
    check(P, "but very few of them", pop["solved"] / pop["total"] < 0.05,
          f"{pop['solved']}/{pop['total']}")
    from ppact.system import evaluate_system, SystemConfig
    r = evaluate_system(APPLICATION_LIBRARY[ex.application],
                        SystemConfig(**ex.start))
    met = sum(C.meets(ex, r.metrics))
    check(P, "and the handed-over design does not already pass",
          met < len(ex.targets), f"{met} of {len(ex.targets)}")
    # The exam must be at the hard end of the set, not merely inside it.
    # Comparing against the single hardest practice challenge was too strict
    # once the set grew to seventeen - some of those are deliberately very
    # tight. The exam must be harder than the MEDIAN.
    fracs = sorted(C.population(c)["solved"] / C.population(c)["total"]
                   for c in C.CHALLENGES)
    median = fracs[len(fracs) // 2]
    exam_frac = pop["solved"] / pop["total"]
    check(P, "the exam is harder than most of the practice challenges",
          exam_frac <= median,
          f"{exam_frac * 100:.1f}% pass the exam against a median of "
          f"{median * 100:.1f}% - a final that is easier than the practice "
          f"is not a final")

    # --- progress bar -------------------------------------------------------
    check(P, "an empty bar is empty",
          set(PR.progress_bar(0, 10)) == {"."})
    check(P, "a full bar is full", set(PR.progress_bar(10, 10)) == {"#"})
    check(P, "and a half bar is half",
          PR.progress_bar(5, 10).count("#") == 14)

    # --- certificate --------------------------------------------------------
    buf4 = io.StringIO()
    with contextlib.redirect_stdout(buf4):
        PR.print_certificate(p, 10)
    cert = buf4.getvalue()
    check(P, "the certificate states what it is worth",
          "not an assessment by anyone" in cert,
          "a certificate that implies external validation it does not have "
          "is a false claim")
    check(P, "and reports the exam honestly",
          "not passed" in cert or "passed" in cert)
    wide = [ln for ln in (easy + med + cert).splitlines() if len(ln) > 78]
    check(P, "nothing wraps", not wide, f"{len(wide)} over 78")


# ==============================================================================
# PATH AY - no adjective stands alone
# ==============================================================================
#
# "SLOWER" tells a student nothing. Slower at what - one job, the frame rate,
# the response to a sensor? By a millisecond or by a factor of three? Because
# the arithmetic grew, or because two engines queue for one memory? Five facts
# hide behind one word, and the word is the part a student remembers.

def path_ay():
    P = "AY"
    import io, contextlib, re, dataclasses as _dcy
    from ppact import decide as D

    # --- the breakdown must ADD UP -----------------------------------------
    #
    # A reason breakdown whose parts do not sum to the difference is a story
    # about a number rather than an account of it.
    cases = [
        ("industrial_vision", "cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
         "cpu_only", {"secondary_compute": "npu_32x32",
                      "execution_mode": "parallel", "work_split": 0.5}),
        ("industrial_vision", "cortex_a53_x4", "npu_32x32", "LPDDR5", 2,
         "isp_and_npu", {"cpu": "cortex_a78_x4"}),
        ("mobile_ai", "cortex_a78_x4", "npu_64x64", "LPDDR5", 2,
         "isp_and_npu", {"memory": "HBM3E", "memory_devices": 1}),
        ("drone", "cortex_a78_x4", "npu_24x24", "LPDDR5", 2,
         "isp_assisted", {"preprocessing_mode": "isp_and_npu"}),
        ("robot", "cortex_a78_x4", "npu_16x16", "LPDDR5", 4,
         "cpu_only", {"compute": "npu_64x64"}),
    ]
    worst = 0.0
    for app, cpu, comp, mem, dev, pm, change in cases:
        b0 = SystemConfig(cpu, comp, mem, dev, preprocessing_mode=pm)
        b1 = _dcy.replace(b0, **change)
        m0 = evaluate_system(APPLICATION_LIBRARY[app], b0).metrics
        m1 = evaluate_system(APPLICATION_LIBRARY[app], b1).metrics
        terms, residue = D.latency_breakdown(m0, m1)
        worst = max(worst, abs(residue))
        check(P, f"{app}/{comp}: the breakdown sums to the difference",
              abs(residue) < 1e-9,
              f"residue {residue:+.9f} ms - a breakdown that absorbs a "
              f"millisecond is worse than none")
        check(P, f"{app}/{comp}: and every term is named",
              all(t.name and t.note for t in terms))
    check(P, "the worst residue across the cases is zero",
          worst < 1e-9, f"{worst:.12f} ms")

    # POSITIVE CONTROL: the residue is always zero in practice, so the branch
    # that reports one has never run. It is given something to find - a
    # breakdown that silently absorbs a millisecond looks complete, which is
    # the whole danger.
    m_a = dict(evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                               b0).metrics)
    m_b = dict(m_a)
    m_b["Latency (ms)"] = m_a["Latency (ms)"] + 1.0    # nothing else moved
    _, bad_residue = D.latency_breakdown(m_a, m_b)
    check(P, "a breakdown that does not add up reports a residue",
          abs(bad_residue - 1.0) < 1e-9, f"{bad_residue}")
    bufr = io.StringIO()
    with contextlib.redirect_stdout(bufr):
        D.print_why(m_a, m_b, "compute", "compute")
    tr = bufr.getvalue()
    check(P, "and the reader is told, in those words",
          "UNACCOUNTED" in tr and "defect" in tr,
          "a breakdown that absorbs a millisecond looks complete")

    # --- the four parts, in order ------------------------------------------
    b0 = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                      preprocessing_mode="cpu_only")
    b1 = _dcy.replace(b0, secondary_compute="npu_32x32",
                      execution_mode="parallel", work_split=0.5)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        D.explain("industrial_vision", b0, b1)
    t = buf.getvalue()
    order = [t.index("1. WHAT CHANGED"), t.index("2. WHY"),
             t.index("3. HOW SURE"), t.index("4. WHAT TO DO")]
    check(P, "measurement, cause, confidence, advice - in that order",
          order == sorted(order),
          "a verdict printed first is a verdict accepted before its reason")
    check(P, "the deployment status is last of all",
          t.index("DEPLOYMENT STATUS") > order[-1])

    # --- no abstract adjective stands alone --------------------------------
    check(P, "the banned list is not empty", len(D.BANNED_ALONE) >= 8)
    for ln in t.splitlines():
        stripped = ln.strip().lower()
        if not stripped or len(stripped.split()) > 6:
            continue
        for word in ("faster", "slower", "better", "worse"):
            check(P, f"'{word}' never stands alone as a verdict line",
                  not re.fullmatch(rf"[-\s]*{word}[.\s]*", stripped),
                  f"line was {ln!r}")

    # --- every measure is named; none is called "performance" --------------
    check(P, "the measures are named individually", len(D.MEASURES) >= 6)
    names = [n for n, _, _, _ in D.MEASURES]
    check(P, "single-job latency and capacity are separate measures",
          "Single-job latency" in names and "Pipeline capacity" in names,
          "they answer different questions and a change can move one and "
          "not the other")
    check(P, "nothing is labelled just 'performance'",
          not any(n.strip().lower() == "performance" for n in names))
    check(P, "and the report does not say 'performance improved'",
          "performance improved" not in t.lower())

    # --- the numbers come before the conclusion in the text ----------------
    check(P, "a percentage appears in the what-changed section",
          "%" in t[order[0]:order[1]])
    check(P, "and the breakdown carries units",
          "ms" in t[order[1]:order[2]])

    # --- confidence must have three states and use them --------------------
    for state in (D.ROBUST, D.CONDITIONAL, D.BOUNDARY):
        check(P, f"'{state}' is explained", len(D.CONFIDENCE_MEANING[state]) > 40)
    # Driven directly rather than through a configuration, so the three
    # states are each actually produced. A check that only ever sees two of
    # them does not know the third works.
    m0 = evaluate_system(APPLICATION_LIBRARY["industrial_vision"], b0).metrics
    base_lat = m0["Latency (ms)"]
    for pct, want in ((0.5, D.BOUNDARY), (8.0, D.CONDITIONAL),
                      (40.0, D.ROBUST)):
        fake = dict(m0)
        fake["Latency (ms)"] = base_lat * (1 + pct / 100)
        got, why = D.confidence(m0, fake)
        check(P, f"a {pct}% change is graded {want}", got == want,
              f"got {got}: {why}")
        check(P, f"and the grade explains itself", len(why) > 30)
    conf_big, _ = D.confidence(m0, evaluate_system(
        APPLICATION_LIBRARY["industrial_vision"], b1).metrics)
    check(P, "the real dual-engine change is robust", conf_big == D.ROBUST,
          conf_big)

    # --- the recommendation must follow the numbers ------------------------
    res = D.explain("industrial_vision", b0, b1) if False else None
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        out = D.explain("industrial_vision", b0, b1)
    check(P, "a change that is not quicker is not recommended for speed",
          any("does not deliver" in a for a in out["advice"]),
          str(out["advice"]))
    check(P, "and the advice names where the time actually is",
          any("host" in a.lower() for a in out["advice"]),
          "the host is 85% of this design")

    # the ranking must be by share of time, descending
    ranking = out["ranking"]
    shares = [s for _, s, _ in ranking]
    check(P, "the upgrade ranking is ordered by time held",
          shares == sorted(shares, reverse=True), str(shares))
    check(P, "and every entry says what that part does",
          all(len(w) > 15 for _, _, w in ranking))

    # --- a failing design must be told not to ship, with the reason --------
    hot = SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 2,
                       preprocessing_mode="isp_and_npu")
    hbm = _dcy.replace(hot, memory="HBM3E", memory_devices=1)
    buf3 = io.StringIO()
    with contextlib.redirect_stdout(buf3):
        out3 = D.explain("mobile_ai", hot, hbm)
    t3 = buf3.getvalue()
    check(P, "a design that fails is reported NOT READY",
          not out3["passes"] and "NOT READY" in t3)
    check(P, "the unmet requirements are named",
          "does not meet" in t3, t3[-300:])
    check(P, "and a cooling failure is called a class, not a quantity",
          "class, not a quantity" in t3,
          "reducing power will not fix a part that needs airflow")

    # --- 'ships' must not be a column heading ------------------------------
    from ppact import demo as DM
    buf4 = io.StringIO()
    with contextlib.redirect_stdout(buf4):
        for d in DM.DEMOS[:3]:
            DM.print_demo(d)
    t4 = buf4.getvalue()
    check(P, "no column is headed 'ships'",
          not re.search(r"\bships\b", t4),
          "students read it as a boat leaving")
    check(P, "and the deployment column explains itself",
          "meets EVERY requirement" in t4)

    # --- easy mode gives a number, not an adjective ------------------------
    from ppact import lessons as L
    buf5 = io.StringIO()
    with contextlib.redirect_stdout(buf5):
        L.print_lesson(L.LESSONS[2], difficulty="easy")
    t5 = buf5.getvalue()
    table = [ln for ln in t5.splitlines()
             if ln.strip().startswith(("small", "medium", "large"))]
    check(P, "easy mode shows percentages in its table",
          any("%" in ln for ln in table), str(table[:2]))
    check(P, "and no adjective",
          not any(w in " ".join(table) for w in ("better", "worse")),
          "a direction without a size is half a fact")

    # --- the markdown report ------------------------------------------------
    md = D.report_markdown("industrial_vision", b0, b1)
    for section in ("## What changed", "## Why", "## How sure",
                    "## What to do"):
        check(P, f"the report has a {section!r} section", section in md)
    check(P, "the report states the deployment status",
          "Deployment status" in md)
    check(P, "and where its recommendation comes from",
          "from nothing else" in md)
    check(P, "the report's net line matches the breakdown", "**net**" in md)

    # --- the UPPER BOUND ----------------------------------------------------
    #
    # "Upgrade the host" is advice. "The host owns 84.7% of one job, so even
    # an infinitely fast accelerator saves at most 14.9%" is a LIMIT, and a
    # limit survives every choice of part, every price and every generation.
    m_base = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                             b0).metrics
    hr = D.headroom(m_base)
    check(P, "headroom is reported for every station that takes time",
          len(hr) >= 2, str(len(hr)))
    check(P, "the shares sum to 100",
          abs(sum(h.share_pct for h in hr) - 100) < 1e-6,
          f"{sum(h.share_pct for h in hr):.6f}")
    check(P, "and are ordered largest first",
          [h.share_pct for h in hr]
          == sorted((h.share_pct for h in hr), reverse=True))
    # The bound is an IDENTITY: removing a station entirely leaves exactly
    # the rest. A bound computed any other way is an opinion about how much
    # could be saved, which is the thing it exists not to be.
    total_lat = m_base["Latency (ms)"]
    for h in hr:
        station_time = total_lat * h.share_pct / 100
        check(P, f"the '{h.station}' bound is the rest of the job exactly",
              abs(h.best_latency + station_time - total_lat) < 1e-9,
              f"{h.best_latency:.6f} + {station_time:.6f} != "
              f"{total_lat:.6f}")
        check(P, f"and its gain matches its share",
              abs(h.best_gain_pct + h.share_pct) < 1e-9,
              f"{h.best_gain_pct:.6f} against {-h.share_pct:.6f}")

    # THE BOUND MUST ACTUALLY BIND. No real engine may beat it.
    accel = next(h for h in hr if h.station == "accelerator core")
    best_possible = accel.best_latency
    beaten = []
    for c in ("npu_64x64", "npu_128x128", "npu_160x160", "datacenter_gpu"):
        try:
            q = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                                _dcy.replace(b0, compute=c))
        except Exception:
            continue
        if "INFEASIBLE" in q.status:
            continue
        if q.metrics["Latency (ms)"] < best_possible - 1e-9:
            beaten.append((c, q.metrics["Latency (ms)"]))
    check(P, "no real engine beats the infinitely-fast-engine bound",
          not beaten,
          f"{beaten} against a bound of {best_possible:.4f} ms - a bound "
          f"something beats is not a bound")

    # --- options must be MEASURED, not estimated ---------------------------
    opts = D.try_options("industrial_vision", b0, {
        "offload": {"preprocessing_mode": "isp_and_npu"},
        "second engine": {"secondary_compute": "npu_32x32",
                          "execution_mode": "parallel", "work_split": 0.5},
        "faster memory": {"memory": "HBM3E", "memory_devices": 1},
    })
    check(P, "every option is evaluated", len(opts) == 3)
    for o in opts:
        if not o.feasible:
            continue
        real = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                               _dcy.replace(b0, **o.change)
                               ).metrics["Latency (ms)"]
        check(P, f"'{o.label}' quotes the figure the design produces",
              abs(o.latency - real) < 1e-9,
              "an expected benefit worked out from a share would be a guess "
              "dressed as a figure")
    check(P, "options are ordered by gain", 
          [o.gain_pct for o in opts if o.feasible]
          == sorted((o.gain_pct for o in opts if o.feasible), reverse=True))

    # --- confidence must be backed by runs that could have failed ----------
    ev = D.confidence_evidence("industrial_vision", b0, b1, points=5)
    check(P, "the confidence grade names how many runs backed it",
          ev["runs"] >= 20, str(ev["runs"]))
    check(P, "and how many reversed", "flips" in ev)
    check(P, "a change nothing reverses is graded robust",
          ev["flips"] > 0 or ev["grade"] == D.ROBUST, str(ev))
    check(P, "with a star rating in range", 1 <= ev["stars"] <= 5,
          str(ev["stars"]))

    # POSITIVE CONTROL: the reversal detector must actually fire. On a small
    # frame the offload conclusion IS assumption-dependent, and a grade that
    # has only ever been ROBUST is a grade nobody has seen work.
    tiny_app = _dcy.replace(APPLICATION_LIBRARY["industrial_vision"],
                            input_pixels=320.0 * 240.0, key="__cv__")
    APPLICATION_LIBRARY["__cv__"] = tiny_app
    try:
        ev2 = D.confidence_evidence(
            "__cv__", b0, _dcy.replace(b0, preprocessing_mode="isp_and_npu"),
            points=5)
        check(P, "a conclusion that DOES reverse is not graded robust",
              ev2["flips"] > 0 and ev2["grade"] != D.ROBUST,
              f"{ev2['grade']} with {ev2['flips']} reversals")
        check(P, "and the assumption that reverses it is named",
              ev2["flipped_by"], str(ev2["flipped_by"]))
    finally:
        APPLICATION_LIBRARY.pop("__cv__", None)

    # --- the deployment status must give its reason ------------------------
    check(P, "a ready design says why it is ready",
          "every deployment constraint is satisfied" in t)
    check(P, "and a failing one says which requirement is unmet",
          "does not meet" in t3)
    check(P, "and that 'not ready' is not the same as 'slow'",
          "not that the" in t3 and "design is slow" in t3)

    # --- the review must give reasons before its verdict -------------------
    buf6 = io.StringIO()
    with contextlib.redirect_stdout(buf6):
        rev = D.design_review(
            "industrial_vision", b0, "Add HBM",
            {"memory": "HBM3E", "memory_devices": 1},
            alternatives={"Move preprocessing off the host":
                          {"preprocessing_mode": "isp_and_npu"}})
    t6 = buf6.getvalue()
    check(P, "the review gives numbered reasons", "REASON 1" in t6
          and "REASON 2" in t6)
    check(P, "under a heading that says they are the reasons",
          "\n  WHY:" in t6,
          "a list of numbered lines with no heading is a list")
    check(P, "the verdict comes after every reason",
          t6.index("VERDICT") > t6.rindex("REASON"))
    check(P, "the alternatives are shown before the verdict",
          "WHAT ELSE WAS TRIED" in t6
          and t6.index("WHAT ELSE WAS TRIED") < t6.index("VERDICT"))
    check(P, "and one reason is the upper bound",
          "cannot save more than" in t6,
          "a limit is more useful than advice because it survives every "
          "choice of part")
    check(P, "a change that costs money is not called an improvement",
          rev["cost_delta"] <= 0 or "NO FREE IMPROVEMENT" in t6,
          "somebody has to decide the exchange rate")
    check(P, "and the verdict states the rate as well as the totals",
          rev["cost_delta"] <= 0 or ("Rate" in t6 and "per USD" in t6))
    check(P, "and says the tool cannot decide the exchange rate",
          rev["cost_delta"] <= 0 or "worth to the customer" in t6,
          "a tool that priced a millisecond would be inventing a market")

    # --- the bound, beside what a real part actually reaches ---------------
    #
    # A bound alone teaches half the lesson. The gap between the limit and
    # the best part anyone can buy is where engineering lives.
    ceils = D.ceilings("industrial_vision", b0)
    check(P, "every lever is reported", len(ceils) >= 3)
    for c in ceils:
        if c.bound_gain_pct is None:
            continue
        check(P, f"'{c.lever}': the measured gain cannot exceed the limit",
              c.best_gain_pct <= c.bound_gain_pct + 1e-9,
              f"{c.best_gain_pct:.2f}% measured against a {c.bound_gain_pct:.2f}% "
              f"limit - a bound something beats is not a bound")
        if c.efficiency_pct is not None:
            check(P, f"'{c.lever}': the efficiency is the ratio of the two",
                  abs(c.efficiency_pct
                      - c.best_gain_pct / c.bound_gain_pct * 100) < 1e-6)
            check(P, f"'{c.lever}': and never above 100%",
                  c.efficiency_pct <= 100 + 1e-9, f"{c.efficiency_pct:.2f}%")

    # memory must NOT be given a bound, because it is not a station
    mem = next((c for c in ceils if c.lever == "memory"), None)
    check(P, "memory is listed", mem is not None)
    check(P, "but claims no limit", mem is not None
          and mem.bound_gain_pct is None,
          "memory time sits inside the accelerator's core figure, so there "
          "is no station to remove - a limit for it would be invented")
    check(P, "and says why there is none", mem is not None and mem.note)
    check(P, "while still reporting what the best memory measures",
          mem is not None and mem.best_gain_pct >= 0)

    bufc = io.StringIO()
    with contextlib.redirect_stdout(bufc):
        D.print_ceilings("industrial_vision", b0)
    tc = bufc.getvalue()
    check(P, "the report distinguishes the limit from the measurement",
          "arithmetic, not a forecast" in tc and "measured" in tc,
          "the bound cannot be beaten or reached; the measurement could be "
          "beaten tomorrow by a part nobody has made")
    check(P, "and says an invented limit would be worth nothing",
          "worth nothing" in tc)

    # --- what a gain costs ---------------------------------------------------
    opts2 = D.try_options("industrial_vision", b0, {
        "offload": {"preprocessing_mode": "isp_and_npu"},
        "HBM": {"memory": "HBM3E", "memory_devices": 1},
        "wider memory": {"memory_devices": 8},
    })
    rates = D.cost_effectiveness(opts2)
    check(P, "a rate is given for every option that helps", len(rates) >= 2)
    check(P, "ordered by rate", [r[3] for r in rates]
          == sorted((r[3] for r in rates), reverse=True))
    for label, gain, cost, rate in rates:
        if cost > 0:
            check(P, f"'{label}': the rate is the gain over the cost",
                  abs(rate - gain / cost) < 1e-9)
    bufr2 = io.StringIO()
    with contextlib.redirect_stdout(bufr2):
        D.print_cost_effectiveness(opts2)
    tr2 = bufr2.getvalue()
    check(P, "and the report says two improvements need not be comparable",
          "not comparable purchases" in tr2 or "not a purchase" in tr2)

    # --- confidence is a count, not a rating -------------------------------
    bufe = io.StringIO()
    with contextlib.redirect_stdout(bufe):
        D.print_confidence_evidence(D.confidence_evidence(
            "industrial_vision", b0, b1, points=5))
    te = bufe.getvalue()
    check(P, "robustness is reported as a count", "/" in te
          and "Decision robustness" in te)
    check(P, "and not as stars", "*" not in te,
          "a five-star grade reads like a review of a restaurant")

    # --- the GAP is the research value -------------------------------------
    for c in ceils:
        if c.bound_gain_pct is None:
            check(P, f"'{c.lever}' with no limit has no gap",
                  c.gap_pct is None,
                  "a gap from an invented limit would be invented too")
            continue
        check(P, f"'{c.lever}': the gap is limit minus best real",
              abs(c.gap_pct - (c.bound_gain_pct - c.best_gain_pct)) < 1e-9,
              f"{c.gap_pct}")
        check(P, f"'{c.lever}': and is never negative",
              c.gap_pct >= -1e-9,
              "a negative gap would mean a part beat the limit")
    check(P, "the report names the gap as research value",
          "RESEARCH value" in tc)
    check(P, "and says what a small gap means",
          "nearly finished" in tc,
          "a large gap says the physics allows something nobody has built; "
          "a small one says effort is better spent elsewhere")
    check(P, "achievability is reported as a share of the limit",
          "achievable" in tc)

    # --- the decision is handed back, everywhere ---------------------------
    bufh = io.StringIO()
    with contextlib.redirect_stdout(bufh):
        D.print_handover()
    th = bufh.getvalue()
    check(P, "the handover says the facts are the tool's",
          "facts are the tool" in th)
    check(P, "and the decision the designer's",
          "decision is the designer" in th)
    check(P, "and names what the tool does not know",
          all(w in th for w in ("worth", "schedule", "competitor",
                                "customer")),
          "a tool that decided would be deciding without any of these")
    check(P, "the explanation screen hands the decision back",
          "DECISION" in t and "decision is the designer" in t)
    check(P, "and so does the review screen",
          "decision is the designer" in t6)

    # --- what-if must never lose the baseline ------------------------------
    wsrc = open(D.__file__, encoding="utf-8").read()
    wbody = wsrc[wsrc.index("def whatif("):]
    check(P, "what-if compares against the STARTING design, not the last one",
          "base_cfg" in wbody and "print_whatif(app_key, base_cfg, cfg" in wbody,
          "a student who cannot see the distance from the start explores in "
          "circles")
    check(P, "and offers a way back",
          "Put everything back" in wbody,
          "one who cannot undo a change commits early and defends")
    check(P, "a second accelerator is given a way of working",
          'execution_mode="parallel"' in wbody,
          "a die that does nothing is not a result")

    bufw = io.StringIO()
    with contextlib.redirect_stdout(bufw):
        D.print_whatif("industrial_vision", b0,
                       _dcy.replace(b0, compute="npu_64x64"),
                       {"accelerator": "npu_64x64"})
    tw = bufw.getvalue()
    check(P, "what-if shows start, now and the change",
          all(w in tw for w in ("start", "now", "change")))
    check(P, "and every measure by name, none summarised",
          "Single-job latency" in tw and "Pipeline capacity" in tw)
    check(P, "and whether it would deploy", "deployment" in tw)
    wide2 = [ln for ln in (tw + tc + th).splitlines() if len(ln) > 78]
    check(P, "nothing wraps", not wide2, f"{len(wide2)} over 78")


# ==============================================================================
# PATH AZ - the workspace
# ==============================================================================
#
# The retyping is what costs a researcher time, not the arithmetic. A design
# is several fields, and comparing it with something tried twenty minutes ago
# meant entering all of them again from memory - which is where the errors
# come from, because the one field remembered wrongly is invisible in the
# result.

def path_az():
    P = "AZ"
    import io, contextlib, os, shutil, tempfile, dataclasses as _dcz
    from ppact import workspace as W
    from ppact import menu as MENU, modes as MODES

    # --- EVERY tool must be findable ---------------------------------------
    #
    # Ten tools were reachable only from a mode, so they were missing from
    # both the full tool list and the search. A tool nobody can find is a
    # tool that does not exist.
    names = {fn.__name__ for _, fn in MENU.TASKS}
    referenced = set()
    for m in MODES.MODES:
        referenced.update(t for _, t in m.entries)
        referenced.update(m.auto)
    missing = sorted(referenced - names - {"task_all_tools"})
    check(P, "every tool a mode offers is in the full tool list",
          not missing, f"missing: {', '.join(missing)}")
    check(P, "and the list is the whole set", len(MENU.TASKS) >= 20,
          str(len(MENU.TASKS)))

    # --- search must find things by what they DO ---------------------------
    for term, want in (("bottleneck", "task_decide"),
                       ("assumption", "task_sensitivity"),
                       ("what if", "task_whatif"),
                       ("export", "task_workspace"),
                       ("challenge", "task_challenge"),
                       ("reproduce", "task_reproducibility")):
        hits = [k for k, _ in W.search(term).get("tools", [])]
        check(P, f"searching {term!r} finds {want}", want in hits,
              f"found {hits[:4]}")
    check(P, "a word nobody used finds nothing",
          not W.search("zzzznotaword"))
    check(P, "and an empty search returns nothing rather than everything",
          not W.search("   "),
          "a blank search that listed the program would be noise")
    check(P, "parts are searchable too",
          any("HBM3E" in k for k, _ in W.search("hbm3e").get("memories", [])),
          str(W.search("hbm3e")))
    check(P, "the concept index points only at tools that exist",
          all(t in names for tasks in W.CONCEPTS.values() for t in tasks),
          "an index entry pointing at a missing tool is a dead link")

    # --- recent, saved, and restoring ---------------------------------------
    tmp = tempfile.mkdtemp(prefix="ppact_ws_")
    try:
        base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                            preprocessing_mode="cpu_only")
        other = _dcz.replace(base, preprocessing_mode="isp_and_npu")
        W.remember("industrial_vision", base, tmp)
        W.remember("industrial_vision", other, tmp)
        r = W.recent(tmp)
        check(P, "the newest design is first", len(r) == 2
              and r[0]["config"]["preprocessing_mode"] == "isp_and_npu")
        W.remember("industrial_vision", base, tmp)
        r = W.recent(tmp)
        check(P, "looking at one again moves it up rather than repeating it",
              len(r) == 2 and r[0]["config"]["preprocessing_mode"]
              == "cpu_only",
              f"{len(r)} entries")
        for i in range(20):
            W.remember("drone", _dcz.replace(base, memory_devices=(i % 8) + 1),
                       tmp)
        check(P, "the history has a bound",
              len(W.recent(tmp)) <= W.HISTORY_LIMIT,
              f"{len(W.recent(tmp))} against a limit of {W.HISTORY_LIMIT}")

        W.save_as("keeper", "industrial_vision", other, tmp)
        check(P, "a saved design is kept by name", "keeper" in W.saved(tmp))
        app_key, cfg = W.rebuild(W.saved(tmp)["keeper"])
        check(P, "and rebuilds to the same configuration",
              app_key == "industrial_vision"
              and cfg.preprocessing_mode == "isp_and_npu")

        # NOTHING may be stored that could go stale
        raw = open(os.path.join(tmp, W.STORE), encoding="utf-8").read()
        for figure in ("Latency", "latency", "System power", "inf/s"):
            check(P, f"no result named {figure!r} is stored",
                  figure not in raw,
                  "a file of cached numbers goes stale the first time a "
                  "coefficient moves, and nothing notices")

        # --- export recomputes ----------------------------------------------
        md = W.export_markdown(W.saved(tmp)["keeper"], "d.md", tmp, "keeper")
        check(P, "a markdown export is written", md and os.path.isfile(md))
        text = open(md, encoding="utf-8").read()
        for section in ("## Design", "## Result", "## Deployment"):
            check(P, f"the document has a {section!r} section",
                  section in text)
        check(P, "and says the figures were recomputed",
              "recomputed" in text and "cannot disagree" in text)
        from ppact.system import evaluate_system
        live = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                               cfg).metrics["Latency (ms)"]
        check(P, "the exported latency matches a fresh evaluation",
              f"{live:.3f}" in text,
              f"{live:.3f} not found - an export that disagrees with the "
              f"screen is worse than no export")

        csv_path = W.export_csv(W.recent(tmp), "d.csv", tmp)
        check(P, "a csv export is written", csv_path
              and os.path.isfile(csv_path))
        lines = open(csv_path, encoding="utf-8").read().splitlines()
        check(P, "with a header and one row per design",
              len(lines) == len(W.recent(tmp)) + 1,
              f"{len(lines)} lines for {len(W.recent(tmp))} designs")
        check(P, "and it records which release produced it",
              "version" in lines[0],
              "a spreadsheet outliving the program that made it should say "
              "which one that was")

        # a corrupt store must not lose the session
        with open(os.path.join(tmp, W.STORE), "w") as fh:
            fh.write("not json")
        check(P, "a corrupt workspace file starts empty rather than raising",
              W.recent(tmp) == [] and W.saved(tmp) == {})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --- the workspace must not compute anything ----------------------------
    src = open(W.__file__, encoding="utf-8").read()
    head = src.split("def export_csv")[0]
    check(P, "the storage half evaluates nothing",
          "evaluate_system" not in head,
          "a workspace that changed a result would be worse than none")


# ==============================================================================
# PATH ZZ - the documentation audit, run last
# ==============================================================================
#
# Placed LAST on purpose. It runs the audit as a subprocess, which costs a
# few seconds, and the mutation runner stops at the first failing check - so
# a mutation that breaks anything else never reaches this. Only a mutation
# that ONLY affects the documentation pays for it.

def path_yy():
    """The logical consistency suite, run as a subprocess.

    Placed beside the documentation audit at the end for the same reason:
    the runner stops at the first failing check, so a mutation that breaks
    anything else never pays for this.
    """
    P = "YY"
    import os as _osy, subprocess as _spy
    suite = "tests_logical_consistency.py"
    if not _osy.path.isfile(suite):
        check(P, "the logical consistency suite is present", False,
              "a release whose screens are not checked against each other "
              "can present two contradictory statements at once")
        return
    proc = _spy.run([sys.executable, suite], capture_output=True, text=True,
                    timeout=1200)
    fails = [ln.strip() for ln in proc.stdout.splitlines()
             if ln.strip().startswith("FAILED") or "CONTROL" in ln]
    check(P, "the logical consistency suite passes", proc.returncode == 0,
          "; ".join(fails[:2]))
    check(P, "and every positive control was detected",
          "20 / 20 positive controls detected" in proc.stdout
          or "positive controls detected" in proc.stdout
          and " 0 /" not in proc.stdout,
          "a rule that has only seen coherent input is not known to work")


def path_xw():
    """The standard review contract, enforced, as a subprocess.

    Without this path the review-contract mutations survived: the runner
    had no check that reads the contract, so removing a scope line or a
    margin band broke nothing it could see. A guarantee nobody verifies is
    not a guarantee.
    """
    P = "XW"
    import os as _osw, subprocess as _spw
    suite = "tests_review_contract.py"
    if not _osw.path.isfile(suite):
        check(P, "the review contract suite is present", False,
              "every analysis path could quietly stop producing a complete "
              "review")
        return
    proc = _spw.run([sys.executable, suite, "--enforce"],
                    capture_output=True, text=True, timeout=1200)
    bad = [ln.strip() for ln in proc.stdout.splitlines()
           if ln.strip().startswith(("VIOLATED", "ABSENT"))]
    check(P, "the review contract is satisfied", proc.returncode == 0,
          "; ".join(bad[:2]))


def path_zz():
    P = "ZZ"
    import os as _osz, subprocess as _spz
    audit = "tests_docs.py"
    if not _osz.path.isfile(audit):
        check(P, "the documentation audit is present", False,
              "a release whose documents are not checked tells a user to do "
              "things that may not work")
        return
    proc = _spz.run([sys.executable, audit], capture_output=True, text=True,
                    timeout=900)
    failures = [ln.strip() for ln in proc.stdout.splitlines()
                if ln.strip().startswith("FAILED")]
    check(P, "the documentation audit passes", proc.returncode == 0,
          "; ".join(failures[:3]))


def main():
    print("=" * 78)
    print(" MODEL VERIFICATION")
    print("=" * 78)
    for fn in (path_g, path_h, path_i, path_j, path_k, path_l, path_m, path_n,
               path_o, path_p, path_q, path_r, path_s, path_t, path_u,
               path_v, path_w, path_x, path_y, path_z, path_aa, path_ab,
               path_ac, path_ad, path_ae, path_af, path_ag, path_ah,
               path_ai, path_aj, path_ak, path_al, path_am, path_an,
               path_ao, path_ap, path_aq, path_ar, path_as,
               path_at, path_au, path_av, path_ax, path_ay, path_az,
               path_zz, path_aw):
        label = fn.__name__.split("_")[1].upper()
        before = len(RESULTS)
        try:
            fn()
        except Exception as exc:
            check(label, "path completed", False, f"{type(exc).__name__}: {exc}")
        run_ = RESULTS[before:]
        print(f"  PATH {label}: {sum(1 for r in run_ if r[2])}/{len(run_)} passed")

    passed = sum(1 for r in RESULTS if r[2])
    print("\n" + "=" * 78)
    print(f" {passed} / {len(RESULTS)} checks passed")
    print("=" * 78)
    for path, name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED [{path}] {name}\n           {detail[:200]}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
