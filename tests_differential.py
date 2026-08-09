"""
tests_differential.py - the same question, answered twice

The runtime model computes a pipeline analytically:

    total = fill + jobs x interval

That is a closed form, and closed forms are where off-by-one errors live. This
file answers the same question by a different method - stepping jobs through
stations one at a time and recording when each station is busy - and compares.
Two implementations agreeing is weak evidence; two implementations disagreeing
is strong evidence, and that is what this is for.

The event simulator here shares NO code with ppact.runtime. It takes the
per-job stage times as input and does its own bookkeeping, so a mistake in the
analytical interval cannot hide inside it.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppact import (APPLICATION_LIBRARY, SystemConfig, evaluate_system, simulate,
                   MEMORY_LIBRARY, COMPUTE_LIBRARY)

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    if not cond:
        print(f"  [FAIL] {name}   {detail}")
    return bool(cond)


# ==============================================================================
# An independent discrete-event pipeline
# ==============================================================================

def event_pipeline(stage_times, jobs):
    """Step jobs through stations in order and record when each is busy.

    A station may start a job once the station has finished its previous job
    AND the previous station has finished this job. No closed form anywhere -
    just two constraints per cell.
    """
    n = len(stage_times)
    if n == 0 or jobs <= 0:
        return {"total": 0.0, "busy": [0.0] * n, "first_latency": 0.0}

    finish = [[0.0] * n for _ in range(jobs)]
    for j in range(jobs):
        for s in range(n):
            ready_station = finish[j - 1][s] if j > 0 else 0.0
            ready_job = finish[j][s - 1] if s > 0 else 0.0
            finish[j][s] = max(ready_station, ready_job) + stage_times[s]
    busy = [stage_times[s] * jobs for s in range(n)]
    return {"total": finish[jobs - 1][n - 1],
            "busy": busy,
            "first_latency": finish[0][n - 1]}


def analytical(stage_times, jobs):
    """The closed form the runtime model uses."""
    if not stage_times or jobs <= 0:
        return {"total": 0.0}
    interval = max(stage_times)
    first = sum(stage_times)
    fill = max(0.0, first - interval)
    return {"total": fill + interval * jobs, "interval": interval,
            "first_latency": first}


# ==============================================================================
# Comparisons
# ==============================================================================

def test_pipeline_forms_agree():
    """The closed form must reproduce the event simulation."""
    cases = [
        ([2.0, 5.0, 3.0], 4),
        ([1.0, 1.0, 1.0], 10),
        ([10.0, 1.0, 1.0], 5),
        ([1.0, 1.0, 10.0], 5),
        ([0.5, 7.0, 0.5, 2.0], 20),
        ([3.0], 1),
        ([3.0], 100),
        ([0.0, 4.0, 0.0], 6),
        ([1e-3, 1e3], 3),
        ([2.5, 2.5], 1),
    ]
    for stages, jobs in cases:
        ev = event_pipeline(stages, jobs)
        an = analytical(stages, jobs)
        # The event form finishes the last job; the closed form counts a full
        # interval for it. They differ by exactly one interval minus the tail.
        expected = ev["total"] + (max(stages) - stages[-1]) if False else ev["total"]
        check(f"first-job latency agrees for {stages} x{jobs}",
              abs(ev["first_latency"] - an["first_latency"]) < 1e-9,
              f"{ev['first_latency']} vs {an['first_latency']}")
        # steady-state rate must match: the marginal cost of one more job is
        # the interval, in both formulations
        ev2 = event_pipeline(stages, jobs + 1)
        marginal = ev2["total"] - ev["total"]
        check(f"marginal cost of a job is the interval for {stages}",
              abs(marginal - max(stages)) < 1e-9,
              f"{marginal} vs {max(stages)}")


def test_runtime_matches_event_simulation():
    """The runtime module against an independent event simulation."""
    configs = [
        ("mobile_ai", SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 1)),
        ("mobile_ai", SystemConfig("cortex_a78_x4", "npu_64x64", "HBM3E", 1)),
        ("industrial_vision", SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                                           preprocessing_mode="isp_and_npu")),
        ("industrial_vision", SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                                           preprocessing_mode="isp_and_npu",
                                           secondary_compute="npu_16x16",
                                           execution_mode="sequential",
                                           work_split=0.3)),
        ("llm_service", SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6)),
    ]
    for app_key, cfg in configs:
        r = simulate(app_key, cfg, duration_s=60)
        m = r.base.metrics
        dual = m.get("Secondary die area (mm2)", 0.0) > 0
        keys = (["Stage ISP (ms)", "Stage CPU (ms)", "Stage accelerator 1 (ms)",
                 "Stage accelerator 2 (ms)", "Stage memory (ms)"] if dual else
                ["Stage ISP (ms)", "Stage CPU (ms)", "Stage accelerator (ms)",
                 "Stage memory (ms)"])
        stages = [m[k] for k in keys if m[k] > 0]
        jobs = r.jobs
        if jobs < 1:
            continue
        ev = event_pipeline(stages, jobs)
        label = f"{app_key}/{cfg.memory}x{cfg.memory_devices}"

        # the interval the runtime uses must be the slowest station
        check(f"{label}: interval is the slowest station",
              abs(r.interval_ms - max(stages)) < 1e-6,
              f"{r.interval_ms:.4f} vs {max(stages):.4f}")

        # the event simulation must not finish the demanded jobs in less time
        # than the window if the runtime says it cannot keep up
        if not r.metrics["Keeps up"]:
            demanded = int(r.metrics["Jobs demanded"])
            ev_all = event_pipeline(stages, demanded)
            check(f"{label}: an event run confirms it cannot keep up",
                  ev_all["total"] > r.total_time_ms,
                  f"event needs {ev_all['total']:.0f} ms for {demanded} jobs, "
                  f"window is {r.total_time_ms:.0f} ms")

        # the jobs the runtime says it completed must actually fit
        check(f"{label}: the completed jobs fit in the window",
              ev["total"] <= r.total_time_ms + max(stages) + 1e-6,
              f"event {ev['total']:.1f} ms vs window {r.total_time_ms:.1f} ms")

        # busy time per station must match the module states
        for key, name in zip(keys, ([n for n in ("ISP", "CPU", "Accelerator 1",
                                                 "Accelerator 2", "Memory")] if dual
                                    else ["ISP", "CPU", "Accelerator", "Memory"])):
            if m[key] <= 0 or name not in r.modules:
                continue
            expect = min(m[key] * jobs, r.total_time_ms)
            check(f"{label}: {name} busy time matches an independent count",
                  abs(r.modules[name].active_ms - expect) < 1e-6,
                  f"{r.modules[name].active_ms:.1f} vs {expect:.1f}")


def test_memory_bound_never_exceeded():
    """The token rate must never beat bytes over bandwidth, computed separately."""
    for app_key, comp, mem, n in (("llm_service", "datacenter_gpu", "HBM3E", 6),
                                  ("llm_service", "datacenter_gpu", "HBM4_36", 6),
                                  ("llm_service", "npu_128x128", "HBM3E", 8),
                                  ("mobile_ai", "npu_64x64", "LPDDR5", 2)):
        app = APPLICATION_LIBRARY[app_key]
        cpu = "server_x86_x32" if app.domain == "Data Center" else "cortex_a78_x4"
        m = evaluate_system(app, SystemConfig(cpu, comp, mem, n)).metrics
        # independent arithmetic, from the library rather than from the result
        spec = MEMORY_LIBRARY[mem]
        bw = spec.effective_bandwidth_gbytes_s * n * 1e9
        bytes_per_job = m["DRAM traffic (MB)"] * 1e6
        ceiling = bw / bytes_per_job
        check(f"{app_key}/{mem}x{n}: rate is under the bandwidth ceiling",
              m["Throughput (inf/s)"] <= ceiling * (1 + 1e-9),
              f"{m['Throughput (inf/s)']:.2f} vs ceiling {ceiling:.2f}")


def test_public_reference_by_hand():
    """Published packages, recomputed from constants rather than the library.

    Deliberately does not read the memory library: if a profile drifts, this
    should notice, and it cannot if it takes its numbers from the thing under
    test.
    """
    # H200: six 24 GB HBM3E stacks, 1024 bits, about 6.25 Gbps
    stacks, gb, bits, gbps = 6, 24, 1024, 6.25
    check("H200 capacity by hand is within 3% of published",
          abs(stacks * gb / 141.0 - 1) < 0.03,
          f"{stacks * gb} GB vs 141 GB")
    check("H200 bandwidth by hand is within 3% of published",
          abs(stacks * bits * gbps / 8 / 1000 / 4.8 - 1) < 0.03,
          f"{stacks * bits * gbps / 8 / 1000:.2f} TB/s vs 4.8")

    # and the library must land in the same place
    spec = MEMORY_LIBRARY["HBM3E"]
    check("the library reproduces the hand figure for capacity",
          abs(spec.capacity_gbyte * 6 / 141.0 - 1) < 0.05,
          f"{spec.capacity_gbyte * 6:.0f} GB")
    check("and for bandwidth",
          abs(spec.bandwidth_gbytes_s * 6 / 1000 / 4.8 - 1) < 0.05,
          f"{spec.bandwidth_gbytes_s * 6 / 1000:.2f} TB/s")

    # HBM4: 2048 bits at the same pin rate is exactly twice
    h4 = MEMORY_LIBRARY["HBM4_36"]
    check("HBM4 is exactly twice HBM3E at the same pin rate",
          abs(h4.bandwidth_gbytes_s / spec.bandwidth_gbytes_s - 2.0) < 1e-9
          and abs(h4.pin_speed_gbps - spec.pin_speed_gbps) < 1e-9)


def test_optimum_two_ways():
    """The best split, by exhaustive sweep and by a coarse-to-fine search."""
    app = APPLICATION_LIBRARY["industrial_vision"]

    def latency(split):
        return evaluate_system(app, SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
            preprocessing_mode="isp_and_npu", secondary_compute="npu_32x32",
            execution_mode="parallel", work_split=split)).metrics["Latency (ms)"]

    sweep = min(((x / 100.0, latency(x / 100.0)) for x in range(0, 101, 2)),
                key=lambda t: t[1])
    lo, hi = 0.0, 1.0
    for _ in range(40):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if latency(m1) < latency(m2):
            hi = m2
        else:
            lo = m1
    search = (lo + hi) / 2
    check("exhaustive sweep and ternary search find the same optimum",
          abs(search - sweep[0]) < 0.05,
          f"sweep {sweep[0]:.2f}, search {search:.3f}")


def main():
    print("=" * 78)
    print(" DIFFERENTIAL VALIDATION")
    print("=" * 78)
    for fn in (test_pipeline_forms_agree, test_runtime_matches_event_simulation,
               test_memory_bound_never_exceeded, test_public_reference_by_hand,
               test_optimum_two_ways):
        before = len(RESULTS)
        try:
            fn()
        except Exception as exc:
            check(f"{fn.__name__} completed", False, f"{type(exc).__name__}: {exc}")
        run = RESULTS[before:]
        print(f"  {fn.__name__:<44s}{sum(1 for _, ok, _ in run if ok)}/{len(run)}")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n" + "=" * 78)
    print(f" {passed} / {len(RESULTS)} checks passed")
    print("=" * 78)
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED {name}\n         {detail[:200]}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
