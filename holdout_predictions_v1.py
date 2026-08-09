"""
holdout_predictions_v1.py - predictions written before the runs

WHAT THIS FILE IS, AND WHAT IT IS NOT
=====================================
It is a locked prediction file: each scenario states, before the model is
run, what direction the metrics should move, over which measurement boundary,
and where a range can be justified by arithmetic done here rather than by the
engine.

It is NOT a blind holdout when I write it. I can run the model at any moment,
and a prediction written by whoever can also execute is not independent
however carefully it is worded. Calling this "blind" would be the exact
circularity the exercise exists to remove.

What it honestly is:

    - a PRE-REGISTRATION. The prediction is fixed, hashed and never edited.
      When a result disagrees, the disagreement is classified rather than
      the prediction quietly adjusted.
    - a mechanism someone else can use blind. An author who does not run the
      engine gets a genuine holdout from the same file.

Each prediction records BASIS, which is the only defence available to a
single author:

    ARITHMETIC   derived here from library data, without the engine. The
                 strongest kind: it can be wrong, and it cannot be fitted.
    STRUCTURAL   follows from a definition or a conservation law.
    JUDGEMENT    an expectation with no derivation behind it. Weakest, and
                 marked so that a hit is not counted as evidence.

And CONTAMINATION, where a scenario reuses a configuration whose result has
already been seen in this project. Those are recorded as CORROBORATION, never
as holdout, because a prediction made after seeing a neighbouring result is
not a prediction.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# The measurement boundary each prediction is written against. Omitting this
# is how the sensor-to-control defect survived three thousand checks.
BOUNDARIES = ("pure inference", "pipeline latency", "sensor-to-control",
              "pipeline capacity", "delivered throughput", "capacity fit",
              "memory subsystem", "silicon and cost")

BASIS = ("ARITHMETIC", "STRUCTURAL", "JUDGEMENT")
GRADE = ("HOLDOUT", "CORROBORATION")


@dataclass(frozen=True)
class Prediction:
    pid: str
    description: str
    config: Dict            # what to build
    boundary: str
    basis: str
    grade: str
    # direction per metric: "down", "up", "same", "any"
    directions: Dict[str, str]
    # optional numeric range, only where BASIS is ARITHMETIC
    ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    expected_limiting_stage: Optional[str] = None
    must_not_change: Tuple[str, ...] = ()
    feasible: bool = True
    reasoning: str = ""
    contamination: str = ""


PREDICTIONS: Tuple[Prediction, ...] = (

    Prediction(
        "H-01", "A second accelerator on a host-limited inspection design",
        config=dict(app="industrial_vision", cpu="cortex_a53_x4",
                    compute="npu_24x24", memory="LPDDR5", devices=2,
                    preprocessing_mode="cpu_only",
                    change=dict(secondary_compute="npu_24x24",
                                execution_mode="alternative",
                                alternative_share=0.5)),
        boundary="pipeline capacity", basis="STRUCTURAL", grade="HOLDOUT",
        directions={"Pipeline capacity (inf/s)": "same",
                    "Logic silicon (mm2)": "up",
                    "System cost (USD)": "up",
                    "Deployment accuracy (%)": "same"},
        expected_limiting_stage="CPU",
        must_not_change=("Deployment accuracy (%)", "Compute time (ms)"),
        reasoning="A small host doing per-pixel work on a five-megapixel "
                  "stream should be the slowest station. If it is, the "
                  "accelerator count cannot move the interval - the capacity "
                  "is one over the CPU stage either way."),

    Prediction(
        "H-02", "Four times the memory packages on a compute-bound drone",
        config=dict(app="drone", cpu="cortex_a78_x4", compute="npu_24x24",
                    memory="LPDDR5", devices=2,
                    preprocessing_mode="isp_and_npu",
                    change=dict(memory_devices=8)),
        boundary="pipeline latency", basis="ARITHMETIC", grade="HOLDOUT",
        directions={"Latency (ms)": "down",
                    "Compute time (ms)": "same",
                    "System cost (USD)": "up"},
        ranges={"Latency (ms)": (-8.0, 0.0)},
        must_not_change=("Compute time (ms)", "Peak TOPS",
                         "Deployment accuracy (%)"),
        reasoning="Derived here: at two packages the transfer time is a small "
                  "fraction of the compute time, and four times the bandwidth "
                  "can remove at most the exposed part of it. With an overlap "
                  "of 0.85 the exposed transfer is under a tenth of the core "
                  "time, so the latency should fall by single digits and not "
                  "by tens of per cent."),

    Prediction(
        "H-03", "A 30B model at FP16 on four HBM3E stacks",
        config=dict(app="llm_service", cpu="server_x86_x32",
                    compute="datacenter_gpu", memory="HBM3E", devices=4,
                    scale_weights_to_gb=60.0),
        boundary="capacity fit", basis="ARITHMETIC", grade="HOLDOUT",
        directions={},
        feasible=True,
        reasoning="Four HBM3E stacks hold 96 GB. Sixty gigabytes of weights "
                  "plus a 0.65 GB cache at the default context plus four "
                  "gigabytes of workspace is about 65 GB, so it should fit "
                  "with room. Arithmetic done here from the library's "
                  "capacity_gbyte and the application's per-token cache."),

    Prediction(
        "H-04", "The same 30B model at a 256k context",
        config=dict(app="llm_service", cpu="server_x86_x32",
                    compute="datacenter_gpu", memory="HBM3E", devices=4,
                    scale_weights_to_gb=60.0, context_tokens=262144),
        boundary="capacity fit", basis="ARITHMETIC", grade="HOLDOUT",
        directions={},
        feasible=False,
        reasoning="The cache at 262144 tokens is 160000 bytes per token times "
                  "the context, which is 41.9 GB. Sixty plus forty-two plus "
                  "four is 106 GB against 96 installed, so it should NOT fit. "
                  "This is the prediction I most want to be wrong about, "
                  "because the margin is only ten gigabytes and an "
                  "unaccounted term would show up here first."),

    Prediction(
        "H-05", "An unequal parallel split on a mid-size vision workload",
        config=dict(app="smart_camera", cpu="cortex_a78_x4",
                    compute="npu_32x32", memory="LPDDR5", devices=2,
                    preprocessing_mode="isp_and_npu",
                    change=dict(secondary_compute="npu_16x16",
                                execution_mode="parallel", work_split=0.5)),
        boundary="pipeline latency", basis="ARITHMETIC", grade="HOLDOUT",
        directions={"Latency (ms)": "up"},
        must_not_change=("Deployment accuracy (%)",),
        reasoning="A 16x16 array has a quarter the multipliers of a 32x32. "
                  "Giving it half the work makes it the slower half by a "
                  "factor of four, and a parallel pair cannot finish before "
                  "its slower half. Half the work on a quarter of the engine "
                  "takes twice as long as all the work on the whole one, so "
                  "an even split here should be WORSE than a single 32x32."),

    Prediction(
        "H-06", "A finer node on a memory-bound mobile design",
        config=dict(app="mobile_ai", cpu="cortex_a78_x4", compute="npu_64x64",
                    memory="LPDDR5", devices=2,
                    preprocessing_mode="isp_and_npu",
                    change=dict(accel_node="N3", soc_node="N3")),
        boundary="pipeline latency", basis="STRUCTURAL", grade="HOLDOUT",
        directions={"Latency (ms)": "same",
                    "Compute time (ms)": "down",
                    "Peak TOPS": "up",
                    "Deployment accuracy (%)": "same"},
        must_not_change=("Deployment accuracy (%)", "DRAM traffic (MB)"),
        reasoning="A node makes arithmetic faster and does nothing to a DRAM. "
                  "On a design where the transfers dominate, the compute term "
                  "should shrink and the latency should barely move. The "
                  "traffic must not change at all - a node does not alter what "
                  "is computed."),
)


def _hash() -> str:
    """SHA-256 of this file, so an edit after the fact is visible."""
    import hashlib
    with open(__file__, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


if __name__ == "__main__":
    print(f"predictions: {len(PREDICTIONS)}")
    for p in PREDICTIONS:
        print(f"  {p.pid}  {p.basis:<10s}{p.grade:<14s}{p.description}")
    print(f"\nsha256: {_hash()}")
