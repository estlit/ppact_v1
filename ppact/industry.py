"""
ppact.industry - real company cases, and what the model cannot represent

Nine NPU adoption cases, grouped into six benchmarks. Each carries what the
company says it has now, what it is aiming for, and - the field that matters
most here - whether this simulator can express the architecture at all.

FOUR DIFFERENT NUMBERS, NEVER MIXED
-----------------------------------
    MEASURED BASELINE   what the company reports its current system does
    COMPANY TARGET      what the proposal commits to
    SIMULATOR RESULT    what this model computes
    FIELD MEASUREMENT   what the built system actually does - absent

Only the third is ours. The first two come from proposals and are objectives
rather than observations; a proposal's target is a commitment, not a
measurement, and treating one as ground truth would let the model be tuned
until it agreed with an aspiration.

SOURCE - NON-PUBLIC
-------------------
Company proposals and programme review documents. These are NOT public. That
matters twice over:

    Nothing drawn from them may be recorded as a PUBLISHED REFERENCE, whatever
    its standing. A signed advisory review is authoritative and still cannot be
    checked by a reader, and being checkable is what the strongest evidence
    level is for.

    Companies are described by ROLE, never by name, and no figure here should
    be reproduced outside a setting where the originals are already available.

The KPI figures are the companies' own: baselines they report and targets they
commit to. Neither is a measurement made here.

    MEASURED BASELINE   the company's report of its current system
    COMPANY TARGET      a commitment in a proposal, not an observation
    SIMULATOR RESULT    computed here, inheriting every assumption below
    FIELD MEASUREMENT   absent - none of these systems is built

WHAT THIS FILE IS REALLY FOR
----------------------------
Six of the nine cases need something the model does not have. Listing what is
missing is more useful than producing numbers for architectures that are not
being simulated - a plausible figure for a three-accelerator system computed by
a two-accelerator model would be worse than no figure.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

LINE = "=" * 86

# ==============================================================================
# Latency measurement boundaries
# ==============================================================================
#
# A latency figure means nothing without its start and end points, and this
# file previously compared a simulated inference time of 2.64 ms against a
# company target of 100 ms as though they measured the same thing. They do not.
# The KPI review for that case had already required the two to be separated.
#
# Four boundaries, from narrowest to widest. A comparison is only valid between
# figures on the same row.

LATENCY_BOUNDARIES = {
    "PURE_INFERENCE": (
        "input tensor ready", "output tensor produced",
        "The compute and memory model. What an accelerator datasheet quotes."),
    "AI_PIPELINE": (
        "camera frame received", "detection and post-processing complete",
        "Preprocessing plus inference plus post-processing. What this "
        "simulator reports as latency."),
    "PERCEPTION_DECISION": (
        "sensor data received", "driving decision produced",
        "The AI pipeline plus sensor fusion. Fusion is approximated here."),
    "SENSOR_TO_CONTROL": (
        "a change in the world", "a control command leaves the system",
        "The whole loop, including actuation. NOT modelled."),
}

BOUNDARY_SUPPORT = {
    "PURE_INFERENCE": "supported",
    "AI_PIPELINE": "supported",
    "PERCEPTION_DECISION": "approximate - fusion is not modelled",
    "SENSOR_TO_CONTROL": "not modelled - no actuation",
}

# What the model can express today. Anything outside this list means a case
# cannot be run, only described.
MODEL_SUPPORTS = (
    "one host CPU",
    "up to two accelerators",
    "one model per run",
    "one memory type",
    "single-stream arrival at a fixed rate",
    "vision or text workloads",
    "ISP or accelerator preprocessing",
)

MODEL_DOES_NOT_SUPPORT = (
    "three or more accelerators",
    "different models on different accelerators at once",
    "sensor fusion of two modalities",
    "image tiling for frames larger than memory",
    "retrieval or vector search as a pipeline stage",
    "concurrent users and percentile latency",
    "burst arrival",
    "accuracy metrics other than a single percentage",
)


@dataclass
class IndustryCase:
    cid: str
    company_role: str            # the application, not the company name
    benchmark: str
    current_system: str
    why_npu: str
    proposed: str
    workload: str
    # Reported figures. Units in the key so nothing is guessed later.
    baseline: Dict[str, float] = field(default_factory=dict)
    target: Dict[str, float] = field(default_factory=dict)
    # Empty until a built system is measured.
    field_measurement: Dict[str, float] = field(default_factory=dict)
    missing: Tuple[str, ...] = ()      # what the model cannot express
    runnable: bool = False
    mapping: str = ""                  # how it maps onto the model, if at all
    # Which boundary the company's latency target is measured at. Comparing a
    # simulated figure against a target on a different row is not a
    # disagreement about the model, it is a category error.
    latency_boundary: str = ""
    boundary_note: str = ""


CASES: List[IndustryCase] = [
    IndustryCase(
        "IND-01", "HBM4 hybrid bonding stack diagnosis",
        "Real-time vision inspection",
        "RTX 3090, FP32",
        "250 ms per die stack is longer than the bonding cycle allows.",
        "three models - detector, classifier and segmenter - on an INT8 NPU",
        "YOLOv8-n detection, ResNet-18 pass/fail, U-Net height segmentation",
        {"latency_ms": 250.0, "classify_accuracy_pct": 87.0},
        {"latency_ms": 100.0, "classify_accuracy_pct": 90.0,
         "height_error_um": 35.0},
        missing=("different models on different accelerators at once",
                 "accuracy metrics other than a single percentage"),
        runnable=False,
        mapping="Three models on one frame, and one of the targets is a "
                "physical height error in micrometres. Running the detector "
                "alone would answer a third of the question and look like an "
                "answer to all of it."),

    IndustryCase(
        "IND-02", "Shipboard route-hazard LLM", "Local LLM service",
        "external LLM API over a satellite link",
        "The link is the bottleneck and the vessel wants local inference.",
        "Qwen-8B on a local NPU",
        "route hazard summary and question answering",
        {},
        {"tokens_per_s": 120.0, "concurrent_responses": 4.0,
         "json_schema_success_pct": 99.0, "evidence_match_pct": 95.0},
        latency_boundary="AI_PIPELINE",
        boundary_note="Tokens per second, not a latency target.",
        missing=("concurrent users and percentile latency",),
        runnable=True,
        mapping="Runnable as SINGLE-STREAM decode of an 8B model, which is the "
                "part that decides whether the target is reachable at all. The "
                "four concurrent responses are outside the model, and the "
                "JSON and evidence figures are not PPACT quantities."),

    IndustryCase(
        "IND-03", "Acoustic road surface sensing", "Multimodal edge AI",
        "single-board computer",
        "250 ms and 8 W with two sensor modalities to run.",
        "vision MobileNet and ultrasonic 1D-CNN, fused",
        "camera plus ultrasonic, two models, one decision",
        {"latency_ms": 250.0, "power_w": 8.0, "accuracy_pct": 98.0},
        {"latency_ms": 175.0, "power_w": 5.6, "accuracy_pct": 93.0},
        missing=("sensor fusion of two modalities",
                 "different models on different accelerators at once"),
        runnable=False,
        mapping="The parallel mode splits ONE model across two engines. Two "
                "different models feeding a fusion step is a different "
                "structure, and the accuracy of a fused decision is not the "
                "accuracy of either input."),

    IndustryCase(
        "IND-04", "Wall-climbing inspection robot",
        "Real-time vision inspection",
        "RTX 3090",
        "The robot has to screen on the wall, not carry a workstation.",
        "YOLO11x-seg on an on-device NPU",
        "crack segmentation and region-of-interest extraction, one model",
        {"latency_ms": 20.0},
        {"latency_ms": 15.0, "map_retention_pct": 99.0},
        latency_boundary="AI_PIPELINE",
        boundary_note="Stated as an average over 100 images, so it includes the whole per-image path rather than the accelerator alone.",
        missing=(),
        runnable=True,
        mapping="One model, one stream, a latency target and an accuracy "
                "retention target. This is the case the model fits best."),

    IndustryCase(
        "IND-05", "Drone infrastructure survey", "Large-image edge analysis",
        "high-specification GPU laptop",
        "13 fps at 200 W, and the imagery cannot leave the site.",
        "MLX-A1 edge box, 80 TOPS, 70 W envelope",
        "DeepLabV3+ on MobileNetV2, 40000x40000 px tiled to 1024x1024",
        {"fps": 13.0, "memory_gb": 1.5, "power_w": 200.0, "mpa_pct": 90.0},
        {"fps": 17.5, "memory_gb": 1.0, "power_w": 70.0, "mpa_pct": 90.0,
         "patch_latency_ms": 40.0},
        latency_boundary="PURE_INFERENCE",
        boundary_note="40 ms is quoted for one 1024x1024 patch at a fixed input resolution - the narrowest boundary, and the one the model reports most directly.",
        missing=("image tiling for frames larger than memory",),
        runnable=True,
        mapping="Runnable AT THE PATCH LEVEL - one 1024x1024 tile, which is "
                "how the company states its latency target. The whole-frame "
                "question, where tiles trade against memory, is the part the "
                "model cannot express."),

    IndustryCase(
        "IND-06", "Clinical trial research RAG", "Accelerated RAG",
        "L40S GPU",
        "GPU cost, and clinical data that cannot leave the site.",
        "RNGD NXT server, HBM3 48 GB, FP8",
        "embedding retrieval then generation",
        {"answer_quality": 0.77, "recall_at_10": 0.85},
        {"answer_quality": 0.73, "ttft_s": 3.0, "query_latency_s": 10.0,
         "recall_at_10": 0.81},
        missing=("retrieval or vector search as a pipeline stage",
                 "accuracy metrics other than a single percentage"),
        runnable=False,
        mapping="Time to first token exists here. Recall@10 and a graded "
                "answer-quality score do not, and reporting TTFT alone would "
                "imply the retrieval half had been evaluated."),

    IndustryCase(
        "IND-07", "Sovereign legal agent", "Accelerated RAG",
        "GPU inference with a separate search tier",
        "Operating cost, and a sovereignty requirement on the whole stack.",
        "vector-database processor plus an inference NPU, two stages",
        "vector retrieval then generation",
        {},
        {"citation_accuracy_pct": 70.0, "factuality_pct": 60.0,
         "sovereign_stack_pct": 90.0},
        missing=("retrieval or vector search as a pipeline stage",
                 "accuracy metrics other than a single percentage"),
        runnable=False,
        mapping="The two-accelerator model fits the SHAPE - one engine per "
                "stage - but a vector-database processor is not an arithmetic "
                "array and its cost and power models do not apply. Sovereign "
                "stack ratio is a procurement measure, not a PPACT one."),

    IndustryCase(
        "IND-08", "Proactive tutoring LLM", "Local LLM service",
        "cloud GPU, BF16",
        "Per-call cost and student data leaving the institution.",
        "RNGD FP8, multi-instance across eight cards",
        "Qwen3-8B interrupt inference and Qwen3-32B solution generation",
        {"p95_latency_ms": 3173.0, "math_accuracy_pct": 59.1,
         "concurrent_users": 4.0},
        {"p95_latency_ms": 2500.0, "math_accuracy_pct": 70.0,
         "concurrent_users": 16.0},
        missing=("concurrent users and percentile latency",),
        runnable=False,
        mapping="The whole KPI set is about tail latency under sixteen "
                "concurrent users on eight cards. A single-stream model has "
                "no p95 to report, and reporting a mean instead would answer "
                "a question nobody asked."),

    IndustryCase(
        "IND-09", "Heavy equipment robot, camera and LiDAR fusion",
        "Autonomous physical AI",
        "GPU, Orin class",
        "Three cameras at 1080p run the GPU hot around the clock outdoors.",
        "FPGA-NPU hybrid: two 25 TOPS NPU modules plus LiDAR fusion",
        "YOLOv8-m across three 1080p cameras, fused with LiDAR",
        {"fps": 15.0, "map50": 0.76, "inference_per_watt_x": 1.0},
        {"fps": 30.0, "map50": 0.75, "inference_per_watt_x": 3.0,
         "gpu_load_reduction_pct": 30.0},
        latency_boundary="PERCEPTION_DECISION",
        boundary_note="The project title names camera and LiDAR fusion on an "
                      "FPGA-NPU hybrid, so the throughput target belongs to a "
                      "perception pipeline wider than the detector.",
        missing=("sensor fusion of two modalities",),
        runnable=True,
        mapping="The DETECTION half runs: the same model on two engines in "
                "parallel, which is what the dual-accelerator mode describes. "
                "The LiDAR fusion and the FPGA stage do not, so the figures "
                "below cover part of the pipeline the KPI measures. An earlier "
                "version of this entry described it as plain parallel YOLO, "
                "which the project title does not support."),

    IndustryCase(
        "IND-10", "Autonomous agricultural vehicle", "Autonomous physical AI",
        "embedded GPU module",
        "Cloud round trips break the control loop and the machine cannot "
        "carry the power.",
        "application processor with an on-device NPU",
        "YOLOv8s at 320x320 for people and vehicles",
        {"latency_ms": 150.0, "map_pct": 92.0},
        {"latency_ms": 100.0, "map_drop_pp": 5.0, "power_reduction_pct": 50.0},
        latency_boundary="PERCEPTION_DECISION",
        boundary_note="The KPI review for this project required the END-TO-END "
                      "system latency and the pure NPU inference latency to be "
                      "reported separately. The 100 ms target is the former. "
                      "Comparing it against a simulated inference time - which "
                      "this file once did - compares different measurements.",
        missing=("control actuation and RTK/LiDAR fusion in the loop",),
        runnable=True,
        mapping="The AI pipeline runs: preprocessing, inference and "
                "post-processing. Sensor fusion is approximate and control "
                "actuation is absent, so the simulated figure is a PART of the "
                "100 ms budget, not a competitor to it."),
]


BENCHMARKS = {
    "Real-time vision inspection": "latency, parallel accelerators, accuracy",
    "Autonomous physical AI": "reaction time, power, sensor input",
    "Multimodal edge AI": "parallel execution, fusion, power",
    "Large-image edge analysis": "memory capacity, tiling, frame rate",
    "Local LLM service": "time to first token, decode, concurrent users",
    "Accelerated RAG": "retrieval plus inference, recall, factuality",
}


def gap_report() -> None:
    """What can be run, what cannot, and precisely why not."""
    runnable = [c for c in CASES if c.runnable]
    blocked = [c for c in CASES if not c.runnable]

    print(LINE)
    print(" INDUSTRY CASES - MODEL COVERAGE")
    print(LINE)
    print(f"  {len(CASES)} cases across {len(BENCHMARKS)} benchmarks.")
    print(f"  {len(runnable)} can be expressed by this model, {len(blocked)} cannot.\n")
    print("  Figures below are MEASURED BASELINE and COMPANY TARGET taken")
    print("  from NON-PUBLIC company proposals and programme reviews. They are")
    print("  the companies' own numbers - a baseline they report and a target")
    print("  they commit to - and neither is a measurement made here. Because")
    print("  the sources are not public, nothing from them is recorded as a")
    print("  published reference, however authoritative it may be.\n")

    print(f"  {'id':<9s}{'application':<34s}{'benchmark':<30s}status")
    print("  " + "-" * 84)
    for c in CASES:
        print(f"  {c.cid:<9s}{c.company_role:<34s}{c.benchmark:<30s}"
              f"{'runnable' if c.runnable else 'NOT EXPRESSIBLE'}")

    print(f"\n  what is missing, by case")
    seen = {}
    for c in blocked:
        for m in c.missing:
            seen.setdefault(m, []).append(c.cid)
    for gap, ids in sorted(seen.items(), key=lambda t: -len(t[1])):
        print(f"    {gap:<52s}{', '.join(ids)}")

    print(f"\n  the model can express")
    for s in MODEL_SUPPORTS:
        print(f"    {s}")
    print(f"\n  it cannot express")
    for s in MODEL_DOES_NOT_SUPPORT:
        print(f"    {s}")

    print(f"\n  A case marked NOT EXPRESSIBLE gets no simulated figure. Running")
    print(f"  a three-accelerator inspection system through a two-accelerator")
    print(f"  model would produce a number, and the number would be about a")
    print(f"  different machine.")
    print(LINE)


def print_case(cid: str) -> None:
    c = next(x for x in CASES if x.cid == cid)
    print(f"\n{LINE}")
    print(f" {c.cid}  {c.company_role}")
    print(LINE)
    print(f"  benchmark        {c.benchmark}")
    print(f"  current system   {c.current_system}")
    print(f"  why an NPU       {c.why_npu}")
    print(f"  proposed         {c.proposed}")
    print(f"  workload         {c.workload}")
    if c.baseline:
        print(f"\n  measured baseline (company-reported)")
        for k, v in c.baseline.items():
            print(f"    {k:<28s}{v:>10.1f}")
    if c.target:
        print(f"\n  company target (an aim, not a measurement)")
        for k, v in c.target.items():
            print(f"    {k:<28s}{v:>10.1f}")
    if c.field_measurement:
        print(f"\n  field measurement")
        for k, v in c.field_measurement.items():
            print(f"    {k:<28s}{v:>10.1f}")
    else:
        print(f"\n  field measurement            none - the system is not built")
    if c.missing:
        print(f"\n  the model cannot express")
        for m in c.missing:
            print(f"    {m}")
    print(f"\n  mapping          {c.mapping}")
    print(LINE)


# ==============================================================================
# Running the two cases the model can express
# ==============================================================================
#
# Both are built as custom applications from the case description rather than
# borrowed from the library, so that the requirement figures are the company's
# and not ours. The GPU baseline and the NPU proposal differ only in the
# accelerator, which is what the case is about.

def _mk(name, key, **kw):
    from .application import make_custom_application, APPLICATION_LIBRARY
    import dataclasses
    # Anything make_custom_application does not take is applied afterwards by
    # replacing the frozen record, so a case can set fields the builder was
    # never given a parameter for.
    import inspect
    accepted = set(inspect.signature(make_custom_application).parameters)
    extra = {k: kw.pop(k) for k in list(kw) if k not in accepted}
    make_custom_application(name=name, register_as=key, **kw)
    if extra:
        APPLICATION_LIBRARY[key] = dataclasses.replace(
            APPLICATION_LIBRARY[key], **extra)
    return key


def _shipboard():
    """IND-02. Qwen-8B, single-stream decode, 120 tokens per second wanted."""
    from .system import SystemConfig
    key = _mk("Shipboard route-hazard LLM", "__ind02__",
              mac_per_inference=8e9, weight_bytes=8e9, activation_bytes=48e6,
              activation_working_set_kb=8192,
              reference_accuracy_pct=93.0, required_accuracy_pct=88.0,
              target_inferences_per_s=120.0,      # company target, tokens/s
              latency_budget_ms=20.0,
              power_budget_w=200.0, bom_budget_usd=8000.0,
              board_budget_mm2=4000.0, soc_silicon_budget_mm2=900.0,
              production_volume=2_000,
              workload_class="text", model_family="transformer",
              weight_read_factor=1.05, context_tokens=4096,
              kv_bytes_per_token=0.06e6, prefill_tokens=1024,
              kv_cache_bytes=2.0e9, runtime_overhead_bytes=2.0e9,
              input_pixels=0, tokens_per_inference=1)
    return (key,
            SystemConfig("server_x86_x32", "datacenter_gpu", "GDDR6", 8),
            SystemConfig("server_x86_x32", "npu_128x128", "HBM3E", 2))


def _climbing_robot():
    """IND-04. One segmentation model, 20 ms on an RTX 3090, 15 ms wanted."""
    from .system import SystemConfig
    key = _mk("Wall-climbing inspection robot", "__ind04__",
              mac_per_inference=28e9, weight_bytes=110e6,
              activation_bytes=180e6, activation_working_set_kb=6000,
              reference_accuracy_pct=95.0, required_accuracy_pct=94.0,
              target_inferences_per_s=50.0,
              latency_budget_ms=15.0,             # company target
              power_budget_w=60.0, bom_budget_usd=1500.0,
              board_budget_mm2=1500.0, soc_silicon_budget_mm2=400.0,
              production_volume=3_000,
              streams=1, input_pixels=1920 * 1080, output_elements=150,
              uses_nms=True, model_family="detection")
    # RTX 3090 baseline is far above anything in the library; the Orin-class
    # edge GPU is the nearest available and UNDERSTATES the baseline, so the
    # improvement here is a lower bound rather than a prediction.
    return (key,
            SystemConfig("cortex_a78_x4", "edge_gpu", "GDDR6", 2,
                         preprocessing_mode="cpu_only"),
            SystemConfig("cortex_a78_x4", "npu_160x160", "LPDDR5", 4,
                         preprocessing_mode="isp_and_npu"))


def _drone_survey():
    """IND-05, AT PATCH LEVEL. One 1024x1024 tile, 40 ms wanted, under 70 W."""
    from .system import SystemConfig
    key = _mk("Drone survey, one 1024x1024 tile", "__ind05__",
              mac_per_inference=9.5e9,            # DeepLabV3+ MobileNetV2
              weight_bytes=22e6, activation_bytes=130e6,
              activation_working_set_kb=4000,
              reference_accuracy_pct=92.0, required_accuracy_pct=90.0,
              target_inferences_per_s=17.5,       # company target, fps
              latency_budget_ms=40.0,             # company target, per patch
              power_budget_w=70.0,                # company target
              bom_budget_usd=3000.0, board_budget_mm2=2000.0,
              soc_silicon_budget_mm2=500.0, production_volume=1_000,
              streams=1, input_pixels=1024 * 1024, output_elements=1,
              uses_nms=False, model_family="cnn")
    # MLX-A1 is an 80 TOPS box; npu_160x160 is the nearest match. The GPU
    # laptop baseline is again above anything in the library.
    return (key,
            SystemConfig("cortex_a78_x4", "edge_gpu", "GDDR6", 4,
                         preprocessing_mode="cpu_only"),
            SystemConfig("cortex_a78_x4", "npu_160x160", "LPDDR5", 4,
                         preprocessing_mode="isp_and_npu"))


def _heavy_robot():
    """IND-09. The same detector on two engines in parallel - the dual case."""
    from .system import SystemConfig
    key = _mk("Multi-camera heavy equipment robot", "__ind09__",
              mac_per_inference=8.0e9,            # YOLOv8-m
              weight_bytes=52e6, activation_bytes=95e6,
              activation_working_set_kb=3000,
              reference_accuracy_pct=79.0, required_accuracy_pct=75.0,
              target_inferences_per_s=30.0,       # company target
              latency_budget_ms=60.0,
              power_budget_w=45.0, bom_budget_usd=1200.0,
              board_budget_mm2=1400.0, soc_silicon_budget_mm2=350.0,
              production_volume=5_000,
              streams=3, input_pixels=1920 * 1080, output_elements=200,
              uses_nms=True, model_family="detection",
              capture_latency_ms=33.0,    # 30 fps rolling shutter, estimated
              control_latency_ms=10.0)
    # Orin-class GPU against two 25 TOPS modules. npu_128x128 at N12 gives
    # 35 TOPS, the closest the library has to a DX-M1.
    return (key,
            SystemConfig("cortex_a78_x4", "edge_gpu", "LPDDR5", 4,
                         preprocessing_mode="cpu_only"),
            SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 4,
                         accel_node="N12", preprocessing_mode="isp_assisted",
                         secondary_compute="npu_128x128",
                         execution_mode="parallel", work_split=0.5))


def _agricultural():
    """IND-10. YOLOv8s at 320x320, 150 ms on a GPU, 100 ms wanted."""
    from .system import SystemConfig
    key = _mk("Autonomous agricultural vehicle", "__ind10__",
              mac_per_inference=2.7e9,            # YOLOv8s at 320x320
              weight_bytes=22e6, activation_bytes=45e6,
              activation_working_set_kb=1800,
              reference_accuracy_pct=92.0,        # company GPU baseline mAP
              required_accuracy_pct=87.0,         # 5 pp drop allowed
              target_inferences_per_s=10.0,
              latency_budget_ms=100.0,            # company target
              power_budget_w=40.0, bom_budget_usd=900.0,
              board_budget_mm2=1200.0, soc_silicon_budget_mm2=300.0,
              production_volume=30_000,
              streams=2, input_pixels=320 * 320, output_elements=150,
              uses_nms=True, model_family="detection",
              closed_loop=True, cruise_speed_m_s=3.0,
              control_overhead_ms=20.0, stopping_distance_budget_m=0.45,
              capture_latency_ms=33.0,    # 30 fps camera, estimated
              control_latency_ms=20.0)
    return (key,
            SystemConfig("cortex_a78_x4", "edge_gpu", "LPDDR5", 4,
                         preprocessing_mode="cpu_only"),
            SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 2,
                         preprocessing_mode="isp_assisted"))


RUNNABLE = {"IND-02": _shipboard, "IND-04": _climbing_robot,
            "IND-05": _drone_survey, "IND-09": _heavy_robot,
            "IND-10": _agricultural}


def run_case(cid: str, duration_s: float = 60.0) -> None:
    """Baseline, proposal and company target, side by side and labelled."""
    from .system import evaluate_system
    from .application import APPLICATION_LIBRARY
    if cid not in RUNNABLE:
        c = next(x for x in CASES if x.cid == cid)
        print(f"\n  {cid} cannot be expressed by this model.")
        for m in c.missing:
            print(f"    missing: {m}")
        print(f"    {c.mapping}")
        return

    c = next(x for x in CASES if x.cid == cid)
    app_key, ref_cfg, new_cfg = RUNNABLE[cid]()
    try:
        app = APPLICATION_LIBRARY[app_key]
        a = evaluate_system(app, ref_cfg)
        b = evaluate_system(app, new_cfg)

        print(f"\n{LINE}")
        print(f" {c.cid}  {c.company_role}")
        print(LINE)
        print(f"  baseline architecture   {c.current_system}")
        print(f"  proposed architecture   {c.proposed}\n")

        rows = [
            ("pure inference (ms)", "Pure inference (ms)", None, False),
            ("end-to-end (ms)", "End-to-end pipeline (ms)", "latency_ms", False),
            ("sensor-to-control (ms)", "Sensor-to-control (ms)", None, False),
            ("throughput (/s)", "Throughput (inf/s)", "fps", True),
            ("power (W)", "System power (W)", "power_w", False),
            ("accuracy (%)", "Deployment accuracy (%)", "accuracy_pct", True),
            ("cost (USD)", "System cost (USD)", None, False),
        ]
        # A throughput-oriented claim is about work per joule, not about watts.
        # Comparing watts made a design that does three times the work in a
        # third of the time look worse, which is arithmetic rather than
        # engineering.
        ipw_a = a.metrics["Throughput (inf/s)"] / max(a.metrics["System power (W)"], 1e-9)
        ipw_b = b.metrics["Throughput (inf/s)"] / max(b.metrics["System power (W)"], 1e-9)
        print(f"  {'':<20s}{'baseline':>12s}{'proposal':>12s}{'change':>10s}"
              f"{'company target':>17s}")
        print("  " + "-" * 72)
        for label, key, tkey, higher in rows:
            av, bv = a.metrics[key], b.metrics[key]
            chg = (bv / av - 1) * 100 if av else 0.0
            tgt = c.target.get(tkey) if tkey else None
            # A target measured at a wider boundary is not comparable with the
            # figure on this row, so it is withheld rather than printed beside
            # it where it invites the comparison.
            if (tkey == "latency_ms"
                    and c.latency_boundary in ("PERCEPTION_DECISION",
                                               "SENSOR_TO_CONTROL")):
                tstr = f"{'wider boundary':>17s}"
            else:
                tstr = f"{tgt:>17.1f}" if tgt is not None else f"{'-':>17s}"
            print(f"  {label:<20s}{av:>12.2f}{bv:>12.2f}{chg:>+9.1f}%{tstr}")

        # Some companies state a RATE OF CHANGE rather than an absolute, and
        # a percentage target has to be compared against a percentage.
        deltas = [
            ("power reduction (%)", "power_reduction_pct",
             (1 - b.metrics["System power (W)"] / a.metrics["System power (W)"]) * 100),
            ("inferences per watt (x)", "inference_per_watt_x",
             ipw_b / max(ipw_a, 1e-9)),
            ("accuracy drop (pp)", "map_drop_pp",
             a.metrics["Deployment accuracy (%)"] - b.metrics["Deployment accuracy (%)"]),
            ("accuracy retention (%)", "map_retention_pct",
             b.metrics["Deployment accuracy (%)"] / a.metrics["Deployment accuracy (%)"] * 100),
        ]
        shown = [(label, c.target[tk], got) for label, tk, got in deltas
                 if tk in c.target and got is not None]
        if shown:
            print(f"\n  {'change against a stated target':<32s}{'simulated':>12s}"
                  f"{'company target':>17s}")
            print("  " + "-" * 62)
            for label, tgt, got in shown:
                print(f"  {label:<32s}{got:>12.1f}{tgt:>17.1f}")

        # --- what the latency figures above actually measure ---------------
        if c.latency_boundary:
            start, end, meaning = LATENCY_BOUNDARIES[c.latency_boundary]
            print(f"\n  -- latency boundary ----------------------------------")
            print(f"  the company target is measured at   {c.latency_boundary}")
            print(f"    from   {start}")
            print(f"    to     {end}")
            print(f"    status {BOUNDARY_SUPPORT[c.latency_boundary]}")
            print(f"\n  what this simulator reports as latency is AI_PIPELINE:")
            print(f"    preprocessing {b.metrics['CPU preprocess (ms)']:8.3f} ms")
            print(f"    inference     {b.metrics['Compute time (ms)']:8.3f} ms"
                  f"   (PURE_INFERENCE)")
            print(f"    memory wait   {b.metrics['Compute data-wait (ms)']:8.3f} ms")
            print(f"    post-process  {b.metrics['CPU postprocess (ms)']:8.3f} ms")
            print(f"    total         {b.metrics['Latency (ms)']:8.3f} ms"
                  f"   (AI_PIPELINE)")
            if c.latency_boundary in ("PERCEPTION_DECISION", "SENSOR_TO_CONTROL"):
                print(f"\n  The target is measured at a WIDER boundary than the")
                print(f"  simulator reaches. The figure above is a PART of that")
                print(f"  budget, not a competitor to it - sensor fusion is")
                print(f"  approximate here and actuation is absent. Comparing")
                print(f"  the two directly is a category error, and this file")
                print(f"  made it before the boundaries were written down.")
            if c.boundary_note:
                print(f"\n  {c.boundary_note}")

        print(f"\n  requirements  baseline {'meets' if a.passes else 'FAILS'}"
              f"   proposal {'meets' if b.passes else 'FAILS'}")
        for name, res in (("baseline", a), ("proposal", res_b := b)):
            bad = [g for g, ok in res.gate.items() if not ok]
            if bad:
                print(f"    {name} fails: {', '.join(bad)}")

        print(f"\n  latency boundaries")
        print(f"    pure inference     the accelerator alone")
        print(f"    end-to-end         plus host preprocessing, framework and")
        print(f"                       postprocessing")
        print(f"    sensor-to-control  plus capture and actuation, where the")
        print(f"                       application states them")
        print(f"    A company KPI usually means the third. A datasheet figure")
        print(f"    means the first. They differ by an order of magnitude.")

        print(f"\n  the four numbers, kept apart")
        print(f"    company-stated baseline   reported by the company, secondary")
        print(f"    company-stated target     an aim from a proposal")
        print(f"    simulator prediction      computed here, from a model built from")
        print(f"                        the case description - so it inherits")
        print(f"                        every assumption in that description")
        print(f"    field measurement   none: the system is not built")
        print(f"\n  direction agreement is reportable; target consistency is at")
        print(f"  most PLAUSIBLE. External measurement: not available. A")
        print(f"  prediction close to a target is not validation of either -")
        print(f"  both could be wrong in the same direction.")
        print(LINE)
    finally:
        APPLICATION_LIBRARY.pop(app_key, None)


# ==============================================================================
# Accelerator power against published modules
# ==============================================================================
#
# The compute library has never been compared with a real module's power. This
# does that arithmetic and reports the gap rather than closing it, because
# closing it means changing every accelerator entry and that needs its own
# check.

PUBLISHED_MODULES = [
    # name, TOPS, module power W, boundary, grade
    ("25 TOPS vision module", 25.0, 3.0, "module, typical", "C+"),
    ("25 TOPS M.2 module", 25.0, 5.0, "module", "C"),
    ("80 TOPS edge box", 80.0, 70.0, "box including host", "C"),
]


def power_gap_report() -> None:
    """What a published module draws, against what the library says."""
    from .compute import COMPUTE_LIBRARY
    print(LINE)
    print(" ACCELERATOR POWER AGAINST PUBLISHED MODULES")
    print(LINE)
    print("  Compared at the MODULE boundary on both sides. An earlier version")
    print("  of this report put silicon leakage beside a module figure and")
    print("  concluded the model was pessimistic; the system does not use that")
    print("  field when a module idle power is stated, so the comparison")
    print("  measured something the model never reads.\n")
    head = (f"  {'published module':<24s}{'TOPS':>7s}{'W':>7s}"
            f"   {'nearest library part':<20s}{'TOPS':>7s}{'idle W':>8s}"
            f"{'max W':>8s}{'verdict':>14s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for name, tops, watts, boundary, grade in PUBLISHED_MODULES:
        best, best_gap = None, None
        for key, spec in COMPUTE_LIBRARY.items():
            if spec.mac_array == 0:
                continue
            t = spec.peak_mac_per_s_at("N7") * 2 / 1e12
            gap = abs(t - tops)
            if best_gap is None or gap < best_gap:
                best, best_gap, best_t = key, gap, t
        spec = COMPUTE_LIBRARY[best]
        idle = spec.module_idle_power_w or spec.static_power_w
        mx = spec.module_max_power_w
        # A figure that includes the host is not a module figure, and the
        # library part is only the accelerator. Comparing them would repeat
        # the boundary error this report was rewritten to remove.
        comparable = "host" not in boundary
        if not comparable:
            verdict = "not compared"
        else:
            verdict = ("inside" if idle <= watts <= (mx if mx > 0 else 1e9)
                       else "OUTSIDE")
        print(f"  {name:<24s}{tops:>7.0f}{watts:>7.1f}"
              f"   {spec.name:<20s}{best_t:>7.1f}{idle:>8.2f}{mx:>8.1f}"
              f"{verdict:>14s}")
        if not comparable:
            print(f"      boundary: {boundary} - the library part is the "
                  f"accelerator alone")
    print("\n  'inside' means the published module figure falls between the")
    print("  library part's idle power and its rated maximum - the model spans")
    print("  the published value rather than having to hit it, which is the")
    print("  most a range can be asked to confirm.")
    print(LINE)


# ==============================================================================
# Scenario revalidation - the full record for one case
# ==============================================================================
#
# The template. Everything a company case needs before its numbers mean
# anything: what the reference was, where the KPI is measured, what workload,
# what direction was expected, what the model gives, what the company aims for,
# and - the field that matters most - which parts of their system this model
# cannot represent at all.

REVALIDATION_FIELDS = (
    "starting point",
    "measurement boundary",
    "workload",
    "expected direction",
    "simulator result",
    "company target",
    "deviation analysis",
    "unsupported portions",
)


def revalidate(cid: str, duration_s: float = 60.0) -> None:
    """One case, recorded in full."""
    from .system import evaluate_system
    from .application import APPLICATION_LIBRARY

    c = next(x for x in CASES if x.cid == cid)
    print(f"\n{LINE}")
    print(f" SCENARIO REVALIDATION - {c.cid}  {c.company_role}")
    print(LINE)

    if cid not in RUNNABLE:
        print(f"  This case cannot be expressed by the model.")
        for m in c.missing:
            print(f"    missing: {m}")
        print(f"\n  {c.mapping}")
        print(LINE)
        return

    app_key, ref_cfg, new_cfg = RUNNABLE[cid]()
    try:
        app = APPLICATION_LIBRARY[app_key]
        a, b = evaluate_system(app, ref_cfg), evaluate_system(app, new_cfg)
        am, bm = a.metrics, b.metrics

        print(f"  1. STARTING POINT ARCHITECTURE")
        print(f"     company's current   {c.current_system}")
        print(f"     modelled as         {ref_cfg.cpu} + {ref_cfg.compute} + "
              f"{ref_cfg.memory} x{ref_cfg.memory_devices}")
        print(f"     proposed            {c.proposed}")
        print(f"     modelled as         {new_cfg.cpu} + {new_cfg.compute} + "
              f"{new_cfg.memory} x{new_cfg.memory_devices}")

        print(f"\n  2. MEASUREMENT BOUNDARY")
        if c.latency_boundary:
            start, end, meaning = LATENCY_BOUNDARIES[c.latency_boundary]
            print(f"     company KPI is      {c.latency_boundary}")
            print(f"       from {start}")
            print(f"       to   {end}")
            print(f"     model reaches       {BOUNDARY_SUPPORT[c.latency_boundary]}")
        else:
            print(f"     not a latency-governed case")
        print(f"     model reports       AI_PIPELINE - preprocessing, "
              f"inference, post-processing")

        print(f"\n  3. WORKLOAD")
        print(f"     {c.workload}")
        print(f"     modelled as         {app.mac_per_inference / 1e9:.1f} GMAC, "
              f"{app.weight_bytes / 1e6:.0f} MB weights, {app.streams} stream(s)")
        print(f"     ESTIMATED           the MAC count and weight size are ours, "
              f"not the company's")

        print(f"\n  4. EXPECTED DIRECTION")
        for label, key, expect in (
                ("latency", "Latency (ms)", "down or acceptable"),
                ("power", "System power (W)", "down"),
                ("accuracy", "Deployment accuracy (%)", "slightly down"),
                ("silicon", "Logic silicon (mm2)", "up or unchanged")):
            got = ("down" if bm[key] < am[key] * 0.995 else
                   "up" if bm[key] > am[key] * 1.005 else "unchanged")
            print(f"     {label:<12s}expected {expect:<20s}got {got}")

        print(f"\n  5. SIMULATOR RESULT")
        for label, key, fmt in (
                ("pure inference", "Compute time (ms)", "{:10.3f} ms"),
                ("AI pipeline", "Latency (ms)", "{:10.3f} ms"),
                ("throughput", "Throughput (inf/s)", "{:10.1f} /s"),
                ("system power", "System power (W)", "{:10.2f} W"),
                ("accuracy", "Deployment accuracy (%)", "{:10.2f} %")):
            print(f"     {label:<16s}baseline " + fmt.format(am[key])
                  + "   proposal " + fmt.format(bm[key]))

        print(f"\n  6. COMPANY TARGET")
        for k, v in c.target.items():
            print(f"     {k:<28s}{v:>10.1f}")
        if not c.target:
            print(f"     none stated in a form the model can read")

        print(f"\n  7. DEVIATION ANALYSIS")
        wide = c.latency_boundary in ("PERCEPTION_DECISION", "SENSOR_TO_CONTROL")
        if wide and "latency_ms" in c.target:
            print(f"     The latency target is measured at a WIDER boundary "
                  f"than the")
            print(f"     model reaches, so no deviation is computed for it. "
                  f"Comparing")
            print(f"     {bm['Latency (ms)']:.2f} ms of AI pipeline against a "
                  f"{c.target['latency_ms']:.0f} ms sensor-to-control")
            print(f"     budget would be a category error.")
        if "power_reduction_pct" in c.target:
            got = (1 - bm["System power (W)"] / am["System power (W)"]) * 100
            tgt = c.target["power_reduction_pct"]
            print(f"     power reduction     simulated {got:5.1f}%   "
                  f"company target {tgt:5.1f}%")
            print(f"     Direction agrees. This is NOT validation: the target "
                  f"is an aim")
            print(f"     in a proposal and the simulated figure rests on a "
                  f"workload we")
            print(f"     estimated.")

        print(f"\n  8. UNSUPPORTED PORTIONS")
        if c.missing:
            for m in c.missing:
                print(f"     {m}")
        else:
            print(f"     none identified")
        print(f"\n     {c.mapping}")

        print(f"\n  STATUS")
        print(f"     direction agreement    yes")
        print(f"     absolute validation    not available - no field "
              f"measurement exists")
        print(f"     evidence               company proposal, NON-PUBLIC, "
              f"targets are aims")
        print(LINE)
    finally:
        APPLICATION_LIBRARY.pop(app_key, None)


def revalidate_all(duration_s: float = 60.0) -> None:
    for c in CASES:
        if c.cid in RUNNABLE:
            revalidate(c.cid, duration_s)
