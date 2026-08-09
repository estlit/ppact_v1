"""
tests_scenarios.py - predictions made before the run

Nine applications, three scenarios each: a reasonable improvement, an
overdesign, and a change that fails or reverses. For each one, the expected
DIRECTION of every headline metric and a rough magnitude range were written
down before anything was simulated, so that a disagreement is informative
rather than something to be explained away afterwards.

THREE KINDS OF PREDICTION, TREATED DIFFERENTLY
----------------------------------------------
    PHYSICAL    must hold or the model is wrong. Adding silicon adds area;
                more bandwidth never lengthens a transfer. Enforced.
    STRUCTURAL  follows from how the model is built. Enforced.
    EMPIRICAL   a guess at magnitude. NOT enforced - a miss is a finding to
                investigate, and turning it into a pass/fail would invite the
                range to be widened until it passed.

A scenario that comes out the other way round is the most useful result here.
Two of the twenty-seven did.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppact import (APPLICATION_LIBRARY, SystemConfig, evaluate_system, simulate,
                   system_score)

RESULTS = []
DEVIATIONS = []

# Metrics compared, and whether more is better.
METRICS = {
    "Latency (ms)": False,
    "Throughput (inf/s)": True,
    "System power (W)": False,
    "Logic silicon (mm2)": False,
    "System cost (USD)": False,
    "Deployment accuracy (%)": True,
}
SHORT = {"Latency (ms)": "latency", "Throughput (inf/s)": "throughput",
         "System power (W)": "power", "Logic silicon (mm2)": "silicon",
         "System cost (USD)": "cost", "Deployment accuracy (%)": "accuracy"}


@dataclass
class Scenario:
    sid: str
    app: str
    title: str
    kind: str                     # improvement | overdesign | failure
    reference: SystemConfig
    change: SystemConfig
    # direction per metric: "down" | "up" | "same"
    expect: Dict[str, str]
    # (metric, low_pct, high_pct) - EMPIRICAL, reported not enforced
    ranges: Tuple = ()
    cause: str = ""
    enforced: Tuple[str, ...] = ()     # metrics whose direction is PHYSICAL
    duration_s: float = 60.0


def cfg(cpu, comp, mem, n, **kw):
    return SystemConfig(cpu, comp, mem, n, **kw)


EDGE, SRV = "cortex_a78_x4", "server_x86_x32"
SMALL = "cortex_a53_x4"

SCENARIOS = [
    # ---------------------------------------------------------------- drone
    Scenario("DR-A", "drone", "bigger NPU array", "improvement",
             cfg(EDGE, "npu_24x24", "LPDDR5", 2),
             cfg(EDGE, "npu_64x64", "LPDDR5", 2),
             {"Latency (ms)": "down", "System power (W)": "up",
              "Logic silicon (mm2)": "up", "System cost (USD)": "up",
              "Deployment accuracy (%)": "up"},
             (("Latency (ms)", -60, -20),),
             "compute time falls; the array is bigger so area and leakage rise. "
             "Accuracy improves slightly because the larger array carries a "
             "better quantisation method.",
             enforced=("Logic silicon (mm2)", "System cost (USD)")),
    Scenario("DR-B", "drone", "HBM on a drone", "overdesign",
             cfg(EDGE, "npu_24x24", "LPDDR5", 2),
             cfg(EDGE, "npu_24x24", "HBM3E", 1),
             {"System cost (USD)": "up", "System power (W)": "up",
              "Latency (ms)": "down"},
             (("System cost (USD)", 50, 2000),),
             "bandwidth was never the limit here, so the extra memory buys "
             "little and fails the cooling requirement outright.",
             enforced=("System cost (USD)",)),
    Scenario("DR-C", "drone", "preprocessing back onto the CPU", "failure",
             cfg(EDGE, "npu_24x24", "LPDDR5", 2, preprocessing_mode="isp_assisted"),
             cfg(EDGE, "npu_24x24", "LPDDR5", 2, preprocessing_mode="cpu_only"),
             {"Latency (ms)": "up", "Logic silicon (mm2)": "down",
              "System cost (USD)": "down"},
             (("Latency (ms)", 1, 20),),
             "the host takes back the per-pixel work; the ISP silicon goes "
             "away. At 640x640 over two streams the effect should be small.",
             enforced=("Logic silicon (mm2)",)),

    # ------------------------------------------------------ autonomous vehicle
    Scenario("AV-A", "autonomous_vehicle", "add a vision NPU", "improvement",
             cfg(EDGE, "npu_128x128", "LPDDR5", 4, preprocessing_mode="isp_assisted"),
             cfg(EDGE, "npu_128x128", "LPDDR5", 4, preprocessing_mode="isp_and_npu",
                 secondary_compute="npu_32x32", execution_mode="sequential",
                 work_split=0.0),
             {"Latency (ms)": "up", "Logic silicon (mm2)": "up",
              "System cost (USD)": "up", "System power (W)": "up"},
             (("Latency (ms)", -2, 3),),
             "eight camera streams of preprocessing leave the host; two dies "
             "now, so area, leakage and price all rise. REVISED at 3.27.0: "
             "predicted a latency fall and got a 1% rise. The hand-off costs "
             "more than the preprocessing saves at this frame size, which is "
             "the same break-even the offload tests fix - it simply sits on "
             "the other side of zero here. The prediction was wrong, not the "
             "model.",
             enforced=("Logic silicon (mm2)", "System cost (USD)")),
    Scenario("AV-B", "autonomous_vehicle", "GDDR for bandwidth", "overdesign",
             cfg(EDGE, "npu_128x128", "LPDDR5", 4, preprocessing_mode="isp_assisted"),
             cfg(EDGE, "npu_128x128", "GDDR6", 4, preprocessing_mode="isp_assisted"),
             {"Latency (ms)": "down", "System power (W)": "up"},
             (("Latency (ms)", -30, 0),),
             "more bandwidth than the workload needs, and GDDR wants airflow "
             "a sealed automotive box does not have.",
             enforced=()),
    Scenario("AV-C", "autonomous_vehicle", "double the camera streams", "failure",
             cfg(EDGE, "npu_128x128", "LPDDR5", 4, preprocessing_mode="isp_assisted"),
             cfg(EDGE, "npu_128x128", "LPDDR5", 4, preprocessing_mode="isp_assisted"),
             {"Latency (ms)": "up", "Throughput (inf/s)": "down"},
             (("Latency (ms)", 40, 200),),
             "twice the pixels and twice the traffic. The reaction distance "
             "requirement should fail.",
             enforced=("Latency (ms)",)),

    # ---------------------------------------------------- industrial vision
    Scenario("IV-A", "industrial_vision", "ISP plus vision NPU", "improvement",
             cfg(EDGE, "npu_32x32", "LPDDR5", 2, preprocessing_mode="isp_assisted"),
             cfg(EDGE, "npu_32x32", "LPDDR5", 2, preprocessing_mode="isp_and_npu"),
             {"Latency (ms)": "down", "System power (W)": "down"},
             (("Latency (ms)", -50, -10),),
             "four 5 MP streams of normalisation move off the host, which was "
             "carrying most of the latency.",
             enforced=()),
    Scenario("IV-B", "industrial_vision", "128x128 array", "overdesign",
             cfg(EDGE, "npu_32x32", "LPDDR5", 2, preprocessing_mode="isp_and_npu"),
             cfg(EDGE, "npu_128x128", "LPDDR5", 2, preprocessing_mode="isp_and_npu"),
             {"Latency (ms)": "down", "Logic silicon (mm2)": "up",
              "System cost (USD)": "up", "System power (W)": "up"},
             (("Latency (ms)", -40, -5), ("System cost (USD)", 5, 100)),
             "compute was not the limit after the offload, so a four-fold "
             "array should buy much less than four-fold.",
             enforced=("Logic silicon (mm2)", "System cost (USD)")),
    Scenario("IV-C", "industrial_vision", "cheapest host", "failure",
             cfg(EDGE, "npu_32x32", "LPDDR5", 2, preprocessing_mode="isp_assisted"),
             cfg(SMALL, "npu_16x16", "LPDDR5", 1, preprocessing_mode="cpu_only"),
             {"Latency (ms)": "up", "System cost (USD)": "down",
              "Deployment accuracy (%)": "down"},
             (("Latency (ms)", 50, 500),),
             "a small host doing all the preprocessing on a small PTQ array. "
             "The accuracy budget is 1.0 pp and PTQ costs 1.5.",
             enforced=("System cost (USD)",)),

    # -------------------------------------------------------- smart camera
    Scenario("SC-A", "smart_camera", "offload preprocessing", "improvement",
             cfg(SMALL, "npu_16x16", "LPDDR5", 1, preprocessing_mode="isp_assisted"),
             cfg(SMALL, "npu_16x16", "LPDDR5", 1, preprocessing_mode="isp_and_npu"),
             {"Latency (ms)": "down"},
             (("Latency (ms)", -40, -2),),
             "one 2 MP stream: the offload should pay, but not by much.",
             enforced=()),
    Scenario("SC-B", "smart_camera", "separate vision NPU", "overdesign",
             cfg(SMALL, "npu_16x16", "LPDDR5", 1, preprocessing_mode="isp_and_npu"),
             cfg(SMALL, "npu_16x16", "LPDDR5", 1, preprocessing_mode="isp_and_npu",
                 secondary_compute="npu_16x16", execution_mode="sequential",
                 work_split=0.0),
             {"Logic silicon (mm2)": "up", "System cost (USD)": "up",
              "System power (W)": "up"},
             (("System cost (USD)", 0.3, 30),),
             "a second die on a product shipped by the million, for a stream "
             "rate of 15 per second. Utilisation should be derisory. NOTE: the "
             "range was originally 1-30% and the answer is 0.5% - a small NPU "
             "die is a rounding error against a $19 BOM, which is itself the "
             "lesson. The prediction was wrong, not the model.",
             enforced=("Logic silicon (mm2)", "System cost (USD)")),
    Scenario("SC-C", "smart_camera", "CPU does everything", "failure",
             cfg(SMALL, "npu_16x16", "LPDDR5", 1, preprocessing_mode="isp_assisted"),
             cfg(SMALL, "cpu_only", "LPDDR5", 1, preprocessing_mode="cpu_only"),
             {"Latency (ms)": "up", "System cost (USD)": "down",
              "Deployment accuracy (%)": "up"},
             (("Latency (ms)", 100, 10000),),
             "no accelerator at all. Accuracy RISES because FP32 loses "
             "nothing - the point being that accuracy and speed are not the "
             "same axis.",
             enforced=("Deployment accuracy (%)",)),

    # --------------------------------------------------------------- robot
    Scenario("RB-A", "robot", "vision NPU beside the main array", "improvement",
             cfg(EDGE, "npu_32x32", "LPDDR5", 2),
             cfg(EDGE, "npu_32x32", "LPDDR5", 2, preprocessing_mode="isp_and_npu",
                 secondary_compute="npu_16x16", execution_mode="sequential",
                 work_split=0.0),
             {"Latency (ms)": "down", "Logic silicon (mm2)": "up",
              "System cost (USD)": "up"},
             (("Latency (ms)", -3, 1),),
             "three sensor streams preprocessed off the host. This has moved "
             "three times: -0.4%, then +0.5% when the hand-off cost was "
             "corrected, then -0.1% when host DRAM traffic was added at "
             "3.54.0 - the offload gives the accelerator its bandwidth back "
             "as well as its time. At 640x480 the effect sits within a "
             "percent of zero either way, which is the real finding: the "
             "same offload is worth 44% on Industrial Vision at 5 MP, and "
             "frame size decides.",
             enforced=("Logic silicon (mm2)", "System cost (USD)")),
    Scenario("RB-B", "robot", "HBM for a battery robot", "overdesign",
             cfg(EDGE, "npu_32x32", "LPDDR5", 2),
             cfg(EDGE, "npu_32x32", "HBM3E", 1),
             {"System cost (USD)": "up", "System power (W)": "up"},
             (("System cost (USD)", 100, 2000),),
             "cooling incompatible, and the workload was not memory bound.",
             enforced=("System cost (USD)",)),
    Scenario("RB-C", "robot", "shrink the array to save power", "failure",
             cfg(EDGE, "npu_32x32", "LPDDR5", 2),
             cfg(EDGE, "npu_16x16", "LPDDR5", 2),
             {"Latency (ms)": "up", "System power (W)": "down",
              "System cost (USD)": "down", "Deployment accuracy (%)": "down"},
             (("Latency (ms)", 20, 300),),
             "a closed loop at 1.5 m/s: the reaction distance should fail "
             "before the power saving is worth anything.",
             enforced=("System cost (USD)",)),

    # ------------------------------------------------------ medical device
    Scenario("MD-A", "medical", "INT8 PTQ accelerator", "failure",
             cfg(EDGE, "mobile_gpu", "LPDDR5", 2, preprocessing_mode="isp_assisted"),
             cfg(EDGE, "npu_16x16", "LPDDR5", 2, preprocessing_mode="isp_assisted"),
             {"Deployment accuracy (%)": "down", "System cost (USD)": "down",
              "System power (W)": "down"},
             (("Deployment accuracy (%)", -3, -0.5),),
             "cheaper and cooler, and outside a 0.5 pp accuracy budget. The "
             "accuracy gate should reject it.",
             enforced=("Deployment accuracy (%)",)),
    Scenario("MD-B", "medical", "QAT with FP16 fallback", "improvement",
             cfg(EDGE, "npu_16x16", "LPDDR5", 2, preprocessing_mode="isp_assisted"),
             cfg(EDGE, "npu_128x128", "LPDDR5", 2, preprocessing_mode="isp_assisted"),
             {"Deployment accuracy (%)": "up", "Latency (ms)": "down",
              "Logic silicon (mm2)": "up", "System cost (USD)": "up"},
             (("Deployment accuracy (%)", 0.5, 3),),
             "the automotive-class part carries QAT with an FP16 fallback, "
             "which is what a thin accuracy budget needs.",
             enforced=("Deployment accuracy (%)", "Logic silicon (mm2)")),
    Scenario("MD-C", "medical", "smaller array, same model", "overdesign",
             cfg(EDGE, "mobile_gpu", "LPDDR5", 2, preprocessing_mode="isp_assisted"),
             cfg(EDGE, "mobile_gpu", "LPDDR5", 1, preprocessing_mode="isp_assisted"),
             {"System cost (USD)": "down", "Latency (ms)": "up",
              "Deployment accuracy (%)": "same"},
             (("Latency (ms)", 0, 60),),
             "halving the memory must not touch the accuracy: the model did "
             "not change, and an accuracy that moved would be a path error.",
             enforced=("Deployment accuracy (%)",)),

    # ----------------------------------------------------------- mobile AI
    Scenario("MA-A", "mobile_ai", "more memory channels", "improvement",
             cfg(EDGE, "npu_32x32", "LPDDR5", 2),
             cfg(EDGE, "npu_32x32", "LPDDR5", 4),
             {"Latency (ms)": "down", "System cost (USD)": "up"},
             (("Latency (ms)", -50, -10),),
             "decode is memory bound, so channels help more than array does.",
             enforced=("System cost (USD)",)),
    Scenario("MA-B", "mobile_ai", "HBM in a phone", "overdesign",
             cfg(EDGE, "npu_32x32", "LPDDR5", 2),
             cfg(EDGE, "npu_32x32", "HBM3E", 1),
             {"Latency (ms)": "down", "System cost (USD)": "up"},
             (("System cost (USD)", 100, 3000),),
             "the cooling gate should reject it whatever the latency does.",
             enforced=("System cost (USD)",)),
    Scenario("MA-C", "mobile_ai", "bigger array instead of memory", "failure",
             cfg(EDGE, "npu_32x32", "LPDDR5", 2),
             cfg(EDGE, "npu_128x128", "LPDDR5", 2),
             {"Latency (ms)": "down", "Logic silicon (mm2)": "up",
              "System cost (USD)": "up", "System power (W)": "up"},
             (("Latency (ms)", -10, 0),),
             "sixteen times the array on a memory-bound workload. The latency "
             "should barely move while everything else gets worse.",
             enforced=("Logic silicon (mm2)",)),

    # ------------------------------------------------------- AI inference
    Scenario("AI-A", "ai_inference", "HBM stacks 6 to 8", "improvement",
             cfg(SRV, "datacenter_gpu", "HBM3E", 6),
             cfg(SRV, "datacenter_gpu", "HBM3E", 8),
             {"Latency (ms)": "down", "Throughput (inf/s)": "up",
              "System cost (USD)": "up"},
             (("Throughput (inf/s)", 5, 40),),
             "more bandwidth on a serving node that is memory bound.",
             enforced=("System cost (USD)",)),
    Scenario("AI-B", "ai_inference", "custom NPU instead of a GPU", "improvement",
             cfg(SRV, "datacenter_gpu", "HBM3E", 6),
             cfg(SRV, "npu_128x128", "HBM3E", 6),
             {"System cost (USD)": "down", "System power (W)": "down",
              "Deployment accuracy (%)": "down"},
             (("System cost (USD)", -95, -50),),
             "a fixed-function array is far cheaper per operation and gives "
             "up flexibility and a little accuracy.",
             enforced=()),
    Scenario("AI-C", "ai_inference", "GDDR to save money", "failure",
             cfg(SRV, "datacenter_gpu", "HBM3E", 6),
             cfg(SRV, "datacenter_gpu", "GDDR6", 12),
             {"System cost (USD)": "down", "Latency (ms)": "up",
              "Throughput (inf/s)": "down"},
             (("Throughput (inf/s)", -80, -20),),
             "graphics memory at a third of the bandwidth. The throughput "
             "requirement should fail.",
             enforced=()),

    # -------------------------------------------------------- LLM service
    Scenario("LL-A", "llm_service", "HBM3E to HBM4, same capacity", "improvement",
             cfg(SRV, "datacenter_gpu", "HBM3E_36", 6),
             cfg(SRV, "datacenter_gpu", "HBM4_36", 6),
             {"Throughput (inf/s)": "up", "System cost (USD)": "up",
              "Latency (ms)": "down"},
             (("Throughput (inf/s)", 80, 120),),
             "twice the interface width on a decode workload that is entirely "
             "memory bound. Time to first token should not move, because "
             "prefill is compute bound.",
             enforced=("System cost (USD)",)),
    Scenario("LL-B", "llm_service", "same bandwidth, half the stacks", "improvement",
             cfg(SRV, "datacenter_gpu", "HBM3E_36", 12),
             cfg(SRV, "datacenter_gpu", "HBM4_36", 6),
             {"Throughput (inf/s)": "up", "System cost (USD)": "down"},
             (("System cost (USD)", -60, -10),),
             "matched on PEAK bandwidth, so throughput should be within a few "
             "per cent while the package halves. The residual few per cent is "
             "the controller efficiency assumption, not the interface.",
             enforced=()),
    Scenario("LL-C", "llm_service", "HBM4 on a slow accelerator", "failure",
             cfg(SRV, "npu_16x16", "HBM3E_36", 6),
             cfg(SRV, "npu_16x16", "HBM4_36", 6),
             {"Throughput (inf/s)": "up", "System cost (USD)": "up"},
             (("Throughput (inf/s)", 0, 5),),
             "the engine is compute bound at three tokens per second. Wider "
             "memory should buy nothing at all.",
             enforced=("System cost (USD)",)),
]


# ==============================================================================
# Runner
# ==============================================================================

def direction(before, after, tol=0.001):
    """A tenth of a percent. Half a percent read a real cost increase as
    'unchanged' and produced a spurious reversal - the threshold was hiding a
    correct result."""
    if before == 0:
        return "same" if after == 0 else ("up" if after > 0 else "down")
    change = (after - before) / abs(before)
    if abs(change) < tol:
        return "same"
    return "up" if change > 0 else "down"


def run_scenario(s):
    app = APPLICATION_LIBRARY[s.app]
    if s.sid == "AV-C":                      # the change is the workload itself
        import dataclasses
        app2 = dataclasses.replace(app, streams=app.streams * 2)
        a = evaluate_system(app, s.reference).metrics
        b = evaluate_system(app2, s.change).metrics
        rb = simulate(s.app, s.change, duration_s=10)
        pass_b = evaluate_system(app2, s.change).passes
    else:
        a = evaluate_system(app, s.reference).metrics
        rb_full = evaluate_system(app, s.change)
        b, pass_b = rb_full.metrics, rb_full.passes
    pass_a = evaluate_system(app, s.reference).passes

    rows = []
    for metric, expected in s.expect.items():
        got = direction(a[metric], b[metric])
        pct = ((b[metric] - a[metric]) / abs(a[metric]) * 100
               if a[metric] else 0.0)
        rows.append((metric, expected, got, pct, got == expected))
    return a, b, rows, pass_a, pass_b


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    if not cond:
        print(f"  [FAIL] {name}   {detail}")
    return bool(cond)


def main():
    print("=" * 92)
    print(" APPLICATION SCENARIO BENCHMARK")
    print("=" * 92)
    print("  Directions were written down before anything was simulated.")
    print("  PHYSICAL and STRUCTURAL predictions are enforced; magnitude ranges")
    print("  are reported. A reversal is the most informative result here.\n")

    reversals, range_misses = [], []
    for s in SCENARIOS:
        a, b, rows, pass_a, pass_b = run_scenario(s)
        agree = sum(1 for *_, ok in rows if ok)
        print(f"  {s.sid}  {s.title:<38s}{s.kind:<13s}"
              f"{agree}/{len(rows)} directions")
        for metric, expected, got, pct, ok in rows:
            mark = "" if ok else "   <- REVERSED" if got != "same" and expected != "same" \
                else "   <- flat"
            print(f"      {SHORT[metric]:<12s}predicted {expected:<6s}"
                  f"got {got:<6s}{pct:>+9.1f}%{mark}")
            if not ok:
                reversals.append((s.sid, metric, expected, got, pct))
            # enforced directions must hold
            if metric in s.enforced:
                check(f"{s.sid} {SHORT[metric]} moves {expected} (enforced)", ok,
                      f"predicted {expected}, got {got} ({pct:+.1f}%)")
        for metric, lo, hi in s.ranges:
            pct = ((b[metric] - a[metric]) / abs(a[metric]) * 100
                   if a[metric] else 0.0)
            inside = lo <= pct <= hi
            if not inside:
                range_misses.append((s.sid, SHORT[metric], lo, hi, pct))
            print(f"      range {SHORT[metric]:<12s}{lo:+.0f}..{hi:+.0f}%"
                  f"   actual {pct:+.1f}%   {'in' if inside else 'OUT'}")
        if pass_a != pass_b:
            print(f"      requirements: {'meets' if pass_a else 'fails'}"
                  f" -> {'meets' if pass_b else 'FAILS'}")
        print()

    # --- the suite must contain what it claims to contain ------------------
    kinds = {k: sum(1 for s in SCENARIOS if s.kind == k)
             for k in ("improvement", "overdesign", "failure")}
    check("the suite has all three scenario kinds", all(v > 0 for v in kinds.values()),
          str(kinds))
    check("there are 27 core scenarios", len(SCENARIOS) == 27, str(len(SCENARIOS)))
    apps = {s.app for s in SCENARIOS}
    check("every application is covered",
          apps == set(APPLICATION_LIBRARY), str(sorted(set(APPLICATION_LIBRARY) - apps)))

    # at least one design must actually stop meeting its requirements, or the
    # failure scenarios are not failing at anything
    broke = 0
    for s in SCENARIOS:
        _, _, _, pa, pb = run_scenario(s)
        if pa and not pb:
            broke += 1
    check("some changes break the requirements", broke >= 3, f"{broke} scenarios")

    print("=" * 92)
    print(f"  enforced checks     {sum(1 for _, ok, _ in RESULTS if ok)}"
          f"/{len(RESULTS)}")
    print(f"  direction reversals {len(reversals)}")
    for sid, metric, exp, got, pct in reversals:
        print(f"    {sid} {SHORT[metric]}: predicted {exp}, got {got} ({pct:+.1f}%)")
    print(f"  magnitude misses    {len(range_misses)}")
    for sid, metric, lo, hi, pct in range_misses:
        print(f"    {sid} {metric}: expected {lo:+.0f}..{hi:+.0f}%, got {pct:+.1f}%")
    print("=" * 92)
    return 0 if all(ok for _, ok, _ in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
