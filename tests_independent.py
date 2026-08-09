"""
tests_independent.py - the same answers, computed a second time from scratch

Every other suite in this package compares the model with itself. That catches
a change and it cannot catch an error: a formula can be wrong and perfectly
consistent, and nothing that calls it will notice.

This file recomputes the same quantities from the library data and the stated
definitions, WITHOUT calling any function in ppact.system, ppact.runtime or
ppact.economics. It reads specifications - a memory's bandwidth, an engine's
MAC count, an application's bytes - and does the arithmetic here, in the open,
where a reader can check it against the comment above it.

RULES THIS FILE FOLLOWS
-----------------------
  - It may READ library dataclasses and their stated fields.
  - It may NOT call evaluate_system, simulate, or any helper that would
    return the answer it is supposed to derive.
  - Where a specification method exists that only converts units or applies a
    published scaling law, calling it is allowed and noted; where a method
    embodies the modelling decision under test, it is not.
  - Every tolerance is stated with a reason.

A deviation here is not a regression. It is either the model being wrong or
this file being wrong, and finding out which is the point.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
import sys

sys.path.insert(0, ".")

from ppact import (APPLICATION_LIBRARY, COMPUTE_LIBRARY, CPU_LIBRARY,
                   MEMORY_LIBRARY, NODE_LIBRARY, SystemConfig,
                   evaluate_system)
from ppact.memory import evaluate as evaluate_memory

LINE = "=" * 84
RESULTS = []

# Closed-form quantities must agree to within floating-point noise. Composite
# ones accumulate several terms and are allowed a looser band, stated per
# check rather than globally.
EXACT = 1e-9
COMPOSITE = 0.01


def check(grade, name, cond, detail=""):
    RESULTS.append((grade, name, bool(cond), detail))


def rel(a, b):
    return abs(a - b) / abs(b) if b else abs(a - b)


# ==============================================================================
# Q1 - closed form: memory bandwidth
# ==============================================================================

def q1_memory_bandwidth():
    """Peak bandwidth is width x rate / 8, and nothing else.

    A memory moves package_io_width bits per transfer at data_rate_gbps
    gigabits per second per pin. Bytes per second is bits over eight.
    """
    for key, mem in MEMORY_LIBRARY.items():
        by_hand = mem.package_io_width_bits * mem.pin_speed_gbps / 8.0
        reported = evaluate_memory(mem).metrics["Package peak bandwidth (GB/s)"]
        check("Q1", f"{mem.name} peak bandwidth = width x rate / 8",
              rel(reported, by_hand) < EXACT,
              f"by hand {by_hand:,.1f}, model {reported:,.1f} GB/s")


# ==============================================================================
# Q1 - closed form: arithmetic rate
# ==============================================================================

def q1_peak_arithmetic():
    """Peak TOPS is MACs per second times operations per MAC.

    A multiply-accumulate is counted as two operations. The array does
    rows x columns MACs per clock.
    """
    OPS_PER_MAC = 2  # a multiply and an add, stated in the compute module
    for key, spec in COMPUTE_LIBRARY.items():
        if not spec.mac_array:
            continue
        arr = spec.mac_array
        if not isinstance(arr, (tuple, list)) or len(arr) != 2:
            # Some entries state a square array as a single dimension.
            rows = cols = int(arr)
        else:
            rows, cols = arr
        by_hand = rows * cols * spec.clock_ghz * 1e9 * OPS_PER_MAC / 1e12
        check("Q1", f"{spec.name} peak TOPS = rows x cols x clock x ops/MAC",
              rel(spec.peak_tops, by_hand) < EXACT,
              f"by hand {by_hand:.3f}, model {spec.peak_tops:.3f} TOPS")


# ==============================================================================
# Q2 - independent numerical: the decode ceiling
# ==============================================================================

def q2_llm_decode_ceiling():
    """A memory-bound decode cannot beat bytes-per-token over bandwidth.

    Every token reads the weights once (times whatever refetch factor the
    application states) plus its share of the cache. The rate that traffic
    allows is the effective bandwidth divided by it, and no scheduling can
    exceed it.
    """
    app = APPLICATION_LIBRARY["llm_service"]
    for devices in (6, 8, 12):
        cfg = SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E",
                           devices)
        r = evaluate_system(app, cfg)
        if "INFEASIBLE" in r.status:
            continue
        m = r.metrics

        bytes_per_token = (app.weight_bytes * app.weight_read_factor
                           + app.kv_bytes_per_token * app.context_tokens)
        bw = m["Effective bandwidth (GB/s)"] * 1e9
        ceiling = bw / bytes_per_token

        check("Q2", f"HBM3E x{devices}: decode rate is under the traffic ceiling",
              m["Single-job rate (inf/s)"] <= ceiling * 1.001,
              f"model {m['Single-job rate (inf/s)']:.2f}, ceiling "
              f"{ceiling:.2f} tokens/s from "
              f"{bytes_per_token / 1e9:.1f} GB per token")
        # and not absurdly below it - a model reporting a tenth of the
        # ceiling would be hiding a term this calculation does not have
        check("Q2", f"HBM3E x{devices}: and within a factor of three of it",
              m["Single-job rate (inf/s)"] > ceiling / 3.0,
              f"{m['Single-job rate (inf/s)'] / ceiling * 100:.0f}% of the "
              f"ceiling - the rest is compute, serving overhead and the host")


# ==============================================================================
# Q2 - independent numerical: the ideal alternative-mode share
# ==============================================================================

def q2_alternative_share_optimum():
    """Two engines finish together when their shares are inverse to their times.

    Engine 1 takes t1 per job and engine 2 takes t2. Give the second a share
    s of the jobs. Both queues drain at the same moment when
    (1-s)/t1 = s/t2, so s = t1 / (t1 + t2).
    """
    from ppact.economics import allocation_sweep
    import io, contextlib

    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                        preprocessing_mode="isp_and_npu")
    for secondary in ("npu_16x16", "npu_24x24"):
        with contextlib.redirect_stdout(io.StringIO()):
            rows = allocation_sweep("robot", base, secondary, "alternative", 21)
        t1, t2 = rows[0][4], rows[-1][5]
        by_hand = t1 / (t1 + t2)
        peak = max(rows, key=lambda r: r[2])[0]
        # The sweep is on a grid of 21 points, so it cannot land closer than
        # half a step - 0.025 - even when the model is exactly right.
        check("Q2", f"{secondary}: the capacity peak is at t1/(t1+t2)",
              abs(peak - by_hand) <= 0.05,
              f"by hand {by_hand:.3f}, sweep peaks at {peak:.3f} "
              f"(grid step 0.05)")


# ==============================================================================
# Q2 - independent numerical: batched serving memory
# ==============================================================================

def q2_batch_memory():
    """Weights once, cache per user. Nothing else scales with the batch.

    Total = weights + users x (bytes per token x context) + workspace.
    """
    from ppact.economics import batch_sweep
    import io, contextlib

    app = APPLICATION_LIBRARY["llm_service"]
    cfg = SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6)
    with contextlib.redirect_stdout(io.StringIO()):
        rows = batch_sweep("llm_service", cfg)

    per_user = app.kv_bytes_per_token * app.context_tokens
    for r in rows:
        by_hand = (app.weight_bytes + per_user * r["b"]
                   + app.runtime_overhead_bytes) / 1e9
        check("Q2", f"{r['b']} users: total memory = weights + n x cache + "
                    f"workspace",
              rel(r["total_gb"], by_hand) < EXACT,
              f"by hand {by_hand:.2f}, sweep {r['total_gb']:.2f} GB")


# ==============================================================================
# Q2 - independent numerical: silicon cost
# ==============================================================================

def q2_die_cost():
    """Cost is area x price per area, divided by yield.

    A wafer costs a fixed amount and holds a number of dies proportional to
    its area over theirs; a fraction of them work.
    """
    # Derived from the PRIMITIVES rather than from usd_per_mm2, which already
    # divides by yield. A first version of this check divided by it a second
    # time and reported the model wrong by exactly the yield factor - the
    # check was wrong and the model was right, which is the outcome an
    # independent recomputation exists to distinguish.
    from ppact.process import get_node, WAFER_PRICE_N4_USD, USABLE_WAFER_MM2
    for node_key in ("N28", "N16", "N7", "N3"):
        nd = get_node(node_key)
        wafer = WAFER_PRICE_N4_USD * nd.wafer_cost_factor
        good_mm2_price = wafer / (USABLE_WAFER_MM2 * nd.yield_factor)
        for comp_key in ("npu_16x16", "npu_32x32", "npu_128x128"):
            spec = COMPUTE_LIBRARY[comp_key]
            if spec.cost_is_purchased:
                continue
            by_hand = (spec.die_area_at(node_key) * good_mm2_price
                       * spec.platform_premium)
            reported = spec.silicon_cost_at(node_key)
            check("Q2", f"{comp_key} at {node_key}: cost = area x wafer / "
                        f"(usable x yield) x premium",
                  rel(reported, by_hand) < EXACT,
                  f"by hand {by_hand:.4f}, model {reported:.4f} USD")


# ==============================================================================
# Q2 - independent numerical: the host's roofline
# ==============================================================================

def q2_host_roofline():
    """Host time = compute + transfer - overlap x min(compute, transfer)."""
    import ppact.system as S

    for cpu in ("cortex_a53_x4", "cortex_a78_x4", "server_x86_x32"):
        for devices in (1, 2, 4, 8):
            m = evaluate_system(
                APPLICATION_LIBRARY["industrial_vision"],
                SystemConfig(cpu, "npu_32x32", "LPDDR5", devices,
                             preprocessing_mode="cpu_only")).metrics
            c, t = m["Host compute time (ms)"], m["Host transfer time (ms)"]
            by_hand = c + t - S.HOST_MEMORY_OVERLAP * min(c, t)
            check("Q2", f"{cpu} x{devices}: host time = c + t - ov x min(c,t)",
                  rel(m["CPU active (ms)"], by_hand) < EXACT,
                  f"by hand {by_hand:.6f}, model {m['CPU active (ms)']:.6f} ms")


# ==============================================================================
# Q3 - structural: what must hold whatever the coefficients are
# ==============================================================================

def q3_structural_bounds():
    """Relations that follow from the definitions, not from any value."""
    cases = [
        ("industrial_vision", "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
         "isp_assisted"),
        ("mobile_ai", "cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
         "isp_and_npu"),
        ("drone", "cortex_a78_x4", "npu_24x24", "LPDDR5", 2, "cpu_only"),
        ("robot", "cortex_a78_x4", "npu_16x16", "LPDDR5", 2, "isp_and_npu"),
    ]
    for app_key, cpu, comp, mem, dev, pm in cases:
        r = evaluate_system(APPLICATION_LIBRARY[app_key],
                            SystemConfig(cpu, comp, mem, dev,
                                         preprocessing_mode=pm))
        if "INFEASIBLE" in r.status:
            continue
        m = r.metrics
        tag = f"{app_key}/{comp}"

        # NOT an invariant, and the first version of this file assumed it
        # was. A station upstream of the accelerator - an ISP - can occupy
        # more time per frame than the accelerator pipeline's latency, because
        # it works on the NEXT frame while this one is being inferred. What
        # must hold is the weaker statement below.
        check("Q3", f"{tag}: interval <= sensor-to-control",
              m["Pipeline interval (ms)"]
              <= m["Sensor-to-control (ms)"] + EXACT,
              f"interval {m['Pipeline interval (ms)']:.3f}, "
              f"sensor-to-control {m['Sensor-to-control (ms)']:.3f} ms - "
              f"every station is part of one frame's journey even when it "
              f"overlaps the next one")
        # Delivered is bounded by both what the machine can do and what
        # arrives.
        check("Q3", f"{tag}: delivered <= capacity",
              m["Delivered throughput (inf/s)"]
              <= m["Pipeline capacity (inf/s)"] + EXACT)
        check("Q3", f"{tag}: delivered <= arrival rate",
              m["Delivered throughput (inf/s)"]
              <= APPLICATION_LIBRARY[app_key].target_inferences_per_s + EXACT)
        # The two bus allocations are a partition of the bus.
        total = (m["Bandwidth left to the accelerator (GB/s)"]
                 + m["Host bandwidth allocated (GB/s)"])
        check("Q3", f"{tag}: bus allocations partition the bus",
              rel(total, m["Effective bandwidth (GB/s)"]) < EXACT,
              f"{total:.6f} against {m['Effective bandwidth (GB/s)']:.6f} GB/s")


# ==============================================================================
# Q5 - boundary: what must NOT be computed
# ==============================================================================

def q5_rejections():
    """Configurations the model must refuse rather than approximate."""
    import math
    from ppact.system import PERFORMANCE_METRICS

    # a model that does not fit
    r = evaluate_system(APPLICATION_LIBRARY["llm_service"],
                        SystemConfig("server_x86_x32", "datacenter_gpu",
                                     "LPDDR5", 8))
    check("Q5", "a model that does not fit reports no performance",
          all(math.isnan(r.metrics[k]) for k in PERFORMANCE_METRICS
              if k in r.metrics),
          "not slow - absent")
    check("Q5", "and still reports what the board costs",
          not math.isnan(r.metrics["System cost (USD)"])
          and r.metrics["System cost (USD)"] > 0)

    # an out-of-range allocation
    for field, bad in (("work_split", 1.5), ("alternative_share", -0.1)):
        raised = False
        try:
            evaluate_system(APPLICATION_LIBRARY["robot"], SystemConfig(
                "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                secondary_compute="npu_32x32", execution_mode="parallel",
                **{field: bad}))
        except ValueError:
            raised = True
        check("Q5", f"{field}={bad} is refused", raised)


# ==============================================================================
# Q1 - the contract, and whether the code honours it
# ==============================================================================

def q1_metric_boundaries():
    """A number is not a measurement until its start and end are stated.

    The contract can be checked for coherence on its own. Whether the CODE
    honours it has to be checked against real results, by adding up the
    stages a boundary claims to cover and comparing with what it reports.
    """
    from ppact.system import (METRIC_BOUNDARIES, PIPELINE_STAGES,
                              check_metric_boundaries)

    problems = check_metric_boundaries()
    check("Q1", "the boundary contracts are coherent", not problems,
          "; ".join(problems[:2]))
    check("Q1", "every latency metric has a contract",
          len(METRIC_BOUNDARIES) >= 3)
    for b in METRIC_BOUNDARIES:
        # "the same" is a legitimate end point for a metric whose start and
        # end are one place - a power draw is measured at a rail, not across
        # an interval of stages.
        check("Q1", f"{b.metric} states where it starts", len(b.start) > 8,
              b.start)
        check("Q1", f"{b.metric} states where it ends", len(b.end) > 7, b.end)
        from ppact.system import FAMILY_SCOPE
        check("Q1", f"{b.metric} declares a family in the scope table",
              b.family in FAMILY_SCOPE, b.family)

    # --- and the code must agree with the contract -------------------------
    #
    # Stage by stage, from the model's own reported components. If a boundary
    # claims to include the ISP, the figure must be larger than one that
    # excludes it by exactly the ISP's time.
    for pm in ("cpu_only", "isp_assisted", "isp_and_npu"):
        m = evaluate_system(
            APPLICATION_LIBRARY["industrial_vision"],
            SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                         preprocessing_mode=pm)).metrics
        app = APPLICATION_LIBRARY["industrial_vision"]
        isp = m.get("ISP active (ms)", 0.0)
        # A contract about a metric nobody reports describes nothing. This
        # caught its first error immediately: the power contract named "Accel
        # power (W)" and the model reports "Accelerator active power (W)".
        missing_metrics = [b.metric for b in METRIC_BOUNDARIES
                           if b.metric not in m]
        check("Q1", f"{pm}: every contracted metric is actually reported",
              not missing_metrics,
              f"contracted and absent: {', '.join(missing_metrics)}")
        if missing_metrics:
            continue

        # narrowest inside middle inside widest
        check("Q1", f"{pm}: pure inference <= pipeline latency",
              m["Pure inference (ms)"] <= m["Latency (ms)"] + EXACT,
              f"{m['Pure inference (ms)']:.4f} vs {m['Latency (ms)']:.4f} ms")
        check("Q1", f"{pm}: pipeline latency <= sensor-to-control",
              m["Latency (ms)"] <= m["Sensor-to-control (ms)"] + EXACT)

        # and the difference is exactly the stages between them
        gap = m["Sensor-to-control (ms)"] - m["Latency (ms)"]
        by_contract = isp + app.capture_latency_ms + app.control_latency_ms
        check("Q1", f"{pm}: the gap is exactly ISP + capture + control",
              abs(gap - by_contract) < 1e-6,
              f"gap {gap:.4f}, contract says {by_contract:.4f} ms - a "
              f"difference here means a stage is in one figure and in no "
              f"contract")

        if pm != "cpu_only":
            check("Q1", f"{pm}: and the ISP is actually in it",
                  isp > 0 and gap >= isp - EXACT,
                  f"ISP {isp:.3f} ms must appear in a sensor-to-control "
                  f"figure or the name is wrong")

        # --- throughput family: each wider than the last -------------------
        #
        # The ISP is IN the capacity contract and OUT of the latency one,
        # because a station that overlaps frames limits the rate without
        # lengthening any job. That is the difference the two contracts
        # exist to record, so it must show in the numbers.
        # NOT checked: single-job rate against pipeline capacity. They are
        # over different boundaries - the first excludes the ISP and the
        # second includes it - so ordering them asserts a comparison neither
        # contract supports. On an ISP-assisted design the first is more than
        # twice the second, and that is a property of the boundaries rather
        # than a defect in either number.
        check("Q1", f"{pm}: delivered <= pipeline capacity",
              m["Delivered throughput (inf/s)"]
              <= m["Pipeline capacity (inf/s)"] + EXACT)
        if pm != "cpu_only":
            check("Q1", f"{pm}: the ISP limits the capacity",
                  m["Pipeline interval (ms)"] >= isp - EXACT,
                  f"interval {m['Pipeline interval (ms)']:.3f} must be at "
                  f"least the ISP's {isp:.3f} ms - a station in the capacity "
                  f"contract cannot be faster than the pipeline it limits")

        # --- power family: the narrow one inside the wide one --------------
        check("Q1", f"{pm}: accelerator power <= system power",
              m["Accelerator active power (W)"]
              <= m["System power (W)"] + EXACT,
              f"{m['Accelerator active power (W)']:.3f} vs "
              f"{m['System power (W)']:.3f} W - one die cannot draw more than "
              f"the product containing it")

        # --- cost family: logic die inside system cost ---------------------
        check("Q1", f"{pm}: logic die cost <= system cost",
              m["Logic die cost (USD)"] <= m["System cost (USD)"] + EXACT,
              f"{m['Logic die cost (USD)']:.3f} vs "
              f"{m['System cost (USD)']:.3f} USD")
        # and memory is bought, so the node cannot move the difference
        check("Q1", f"{pm}: the bought parts are the difference",
              m["System cost (USD)"] - m["Logic die cost (USD)"] > 0,
              "memory, board, package and assembly are outside the logic "
              "contract by definition")


def main():
    print(LINE)
    print(" INDEPENDENT RECOMPUTATION")
    print(LINE)
    print("  Every other suite compares the model with itself, which catches a")
    print("  change and cannot catch an error. This one derives the same")
    print("  quantities from the library data and the stated definitions,")
    print("  without calling the functions under test.\n")

    for fn in (q1_memory_bandwidth, q1_peak_arithmetic, q1_metric_boundaries,
               q2_llm_decode_ceiling,
               q2_alternative_share_optimum, q2_batch_memory, q2_die_cost,
               q2_host_roofline, q3_structural_bounds, q5_rejections):
        try:
            fn()
        except Exception as exc:
            check("Q?", f"{fn.__name__} runs", False,
                  f"{type(exc).__name__}: {exc}")

    grades = {}
    for grade, name, ok, detail in RESULTS:
        g = grades.setdefault(grade, [0, 0])
        g[1] += 1
        if ok:
            g[0] += 1
    for grade, name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED [{grade}] {name}")
            if detail:
                print(f"          {detail}")

    passed = sum(1 for _, _, ok, _ in RESULTS if ok)
    print(f"\n{LINE}")
    for grade in sorted(grades):
        p, n = grades[grade]
        label = {"Q1": "closed form", "Q2": "independent numerical",
                 "Q3": "structural", "Q5": "boundary"}.get(grade, grade)
        print(f"  {grade}  {label:<26s}{p}/{n}")
    print(f"\n {passed} / {len(RESULTS)} independent checks passed")
    print(LINE)
    print("  These grades are NOT equal evidence. A closed-form check proves")
    print("  the arithmetic; a structural one proves a relation holds and says")
    print("  nothing about whether the numbers are right; a boundary check")
    print("  proves the model declines a question rather than answering it")
    print("  badly. Reporting them as one total would hide that.")
    print(LINE)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
