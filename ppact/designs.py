"""
ppact.designs - starting points and design examples

A student needs somewhere to start that is not a blank page and not an answer.
Three tiers do that:

    REFERENCE        what a product in this category typically looks like today.
                     The starting point, not a target.
    DESIGN EXAMPLES  directions the architecture could go. Called examples
                     rather than recommendations on purpose: a name like
                     "recommended" turns a reference point into an answer, and
                     the student stops designing and starts copying.
    STUDENT DESIGN   whatever they build, evaluated by the simulator.

WHAT THIS MODEL CANNOT REPRESENT
--------------------------------
There is ONE accelerator block. Architectures with two - "CPU + GPU + NPU", or
a Vision NPU beside a Main NPU - cannot be built here, and pretending otherwise
would be worse than saying so. Each entry therefore carries the architecture it
represents AND a flag for whether the model actually captures it:

    modelled = True     the configuration is the architecture
    modelled = False    the configuration is the closest single-accelerator
                        stand-in, and the second engine is absent

Where preprocessing moves onto the accelerator, that IS modelled - as work on
the main array, which cannot overlap with inference. A separate vision NPU
would overlap, at the cost of its own area, power and price. That difference is
real and is not in here.

CPU IS ALWAYS PRESENT. Every entry has a host, because every one of these
products has one.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .application import APPLICATION_LIBRARY
from .system import SystemConfig, evaluate_system


@dataclass(frozen=True)
class DesignOption:
    tier: str                 # Reference | Example A | Example B | Example C
    label: str                # Low power, High performance, Balanced
    architecture: str         # as a product datasheet would describe it
    config: SystemConfig
    rationale: str
    modelled: bool = True     # False when a second accelerator is missing


def _d(tier, label, arch, cfg, why, modelled=True):
    return DesignOption(tier, label, arch, cfg, why, modelled)


DESIGNS: Dict[str, List[DesignOption]] = {

    "drone": [
        _d("Starting point", "Example published configuration", "CPU + NPU",
           SystemConfig("cortex_a78_x4", "npu_24x24", "LPDDR5", 2),
           "A companion module sized to meet the reaction distance, with "
           "preprocessing on the host because there is no camera block to put "
           "it on. A shipping product clears its own safety requirement - a "
           "reference that did not would not be a reference."),
        _d("Example A", "Low power", "CPU + ISP + NPU",
           SystemConfig("cortex_a53_x4", "npu_24x24", "LPDDR5", 1,
                        preprocessing_mode="isp_assisted"),
           "A cheaper host and a camera block. Check the reaction distance "
           "before assuming the saving is free."),
        _d("Example B", "High performance", "CPU + ISP + Vision NPU + Main NPU",
           SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 2,
                        preprocessing_mode="isp_and_npu",
                        secondary_compute="npu_16x16", execution_mode="sequential",
                        work_split=0.0),
           "Everything off the host, with a small vision engine beside the main "
           "array so preprocessing does not compete with inference. Two dies, "
           "so two lots of area, leakage and price."),
        _d("Example C", "Balanced", "CPU + ISP + NPU",
           SystemConfig("cortex_a78_x4", "npu_24x24", "LPDDR5", 2,
                        preprocessing_mode="isp_assisted"),
           "A middle array with the camera block doing what it can."),
    ],

    "smart_camera": [
        _d("Starting point", "Example published configuration", "CPU + ISP + NPU",
           SystemConfig("cortex_a53_x4", "npu_16x16", "LPDDR5", 1,
                        preprocessing_mode="isp_assisted"),
           "The standard fixed-camera SoC: cheap host, camera block, small "
           "accelerator."),
        _d("Example A", "Low power", "CPU + ISP + NPU",
           SystemConfig("cortex_a53_x4", "npu_16x16", "LPDDR5", 1,
                        preprocessing_mode="isp_and_npu"),
           "Move the last of the preprocessing off the host without buying a "
           "bigger array."),
        _d("Example B", "High performance", "CPU + ISP + Vision NPU + Main NPU",
           SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="isp_and_npu",
                        secondary_compute="npu_16x16", execution_mode="sequential",
                        work_split=0.0),
           "A vision engine beside the main array. Ask whether the BOM survives "
           "two dies."),
        _d("Example C", "Balanced", "CPU + ISP + NPU",
           SystemConfig("cortex_a53_x4", "npu_24x24", "LPDDR5", 1,
                        preprocessing_mode="isp_and_npu"),
           "A modest step up on the same cheap host."),
    ],

    "industrial_vision": [
        _d("Starting point", "Example published configuration", "CPU + ISP + NPU",
           SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="isp_assisted"),
           "A vision controller with a camera block. The host still normalises "
           "every frame, and there are four of them."),
        _d("Example A", "Low power", "CPU + ISP + Main NPU",
           SystemConfig("cortex_a53_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="isp_assisted"),
           "A cheaper host and a bigger array - the opposite trade to the usual "
           "instinct."),
        _d("Example B", "High performance", "CPU + ISP + Vision NPU + Main NPU",
           SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                        preprocessing_mode="isp_and_npu",
                        secondary_compute="npu_24x24", execution_mode="sequential",
                        work_split=0.0),
           "A dedicated vision engine feeding the main array. Check what now "
           "limits throughput - it may not be either accelerator."),
        _d("Example C", "Balanced", "CPU + ISP + NPU",
           SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                        preprocessing_mode="isp_and_npu"),
           "Mid array, offloaded preprocessing, more memory channels."),
    ],

    "robot": [
        _d("Starting point", "Example published configuration", "CPU + NPU",
           SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2),
           "A general compute board with an accelerator bolted on."),
        _d("Example A", "Low power", "CPU + ISP + NPU",
           SystemConfig("cortex_a53_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="isp_assisted"),
           "Battery powered, so the host is the first thing to shrink."),
        _d("Example B", "High performance", "CPU + Vision NPU + Main NPU",
           SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                        preprocessing_mode="isp_and_npu",
                        secondary_compute="npu_20x20", execution_mode="sequential",
                        work_split=0.0),
           "Three sensor streams fused, with a vision engine handling the front "
           "end. Reaction distance is the constraint to watch."),
        _d("Example C", "Balanced", "CPU + ISP + NPU",
           SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="isp_and_npu"),
           "Same silicon, preprocessing moved."),
    ],

    "autonomous_vehicle": [
        _d("Starting point", "Example published configuration", "CPU + GPU + NPU",
           SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 4,
                        preprocessing_mode="isp_assisted",
                        secondary_compute="mobile_gpu", execution_mode="alternative",
                        alternative_share=0.05),
           "An ADAS SoC with both a GPU and an accelerator. The GPU is mostly "
           "there for planning and rendering rather than for the network - only "
           "the few layers the fixed-function array cannot take land on it. "
           "It costs area, price and leakage regardless. Push that share up and "
           "watch the reaction distance: at a tenth, this design stops "
           "clearing its own safety requirement."),
        _d("Example A", "Low power", "CPU + NPU",
           SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                        preprocessing_mode="isp_and_npu"),
           "A smaller array with everything offloaded. Cheaper and cooler - if "
           "it still reacts in time."),
        _d("Example B", "High performance", "CPU + GPU + Vision NPU + Main NPU",
           SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 8,
                        preprocessing_mode="isp_and_npu",
                        secondary_compute="npu_32x32", execution_mode="sequential",
                        work_split=0.0),
           "Eight cameras fully offloaded onto a vision engine, with the memory "
           "to feed them."),
        _d("Example C", "Balanced", "CPU + NPU + GDDR",
           SystemConfig("cortex_a78_x4", "npu_128x128", "GDDR6", 4,
                        preprocessing_mode="isp_and_npu"),
           "Trade board area and heat for bandwidth. Note the qualification "
           "gate before assuming this ships."),
    ],

    "mobile_ai": [
        _d("Starting point", "Example published configuration", "CPU + GPU + NPU",
           SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                        secondary_compute="mobile_gpu", execution_mode="alternative",
                        alternative_share=0.25),
           "A phone SoC with a GPU and an NPU. A quarter of the work lands on "
           "the GPU, and both draw leakage all day."),
        _d("Example A", "Low power", "CPU + GPU + NPU",
           SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                        secondary_compute="mobile_gpu", execution_mode="alternative",
                        alternative_share=0.25),
           "More memory channels rather than more array - this workload is "
           "bound by capacity and bandwidth, not arithmetic."),
        _d("Example B", "High performance", "CPU + GPU + Larger NPU",
           SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
                        secondary_compute="mobile_gpu", execution_mode="alternative",
                        alternative_share=0.25),
           "A bigger array beside the same GPU. Check whether it changes "
           "anything before paying for it."),
        _d("Example C", "Balanced", "CPU + NPU",
           SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 8),
           "Capacity first. Eight packages is a lot of board for a phone."),
    ],

    "medical": [
        _d("Starting point", "Example published configuration", "CPU + GPU",
           SystemConfig("cortex_a78_x4", "mobile_gpu", "LPDDR5", 2,
                        preprocessing_mode="isp_assisted"),
           "A GPU, because the accuracy budget is half a percentage point and "
           "an INT8 pipeline does not fit inside it."),
        _d("Example A", "Low power", "CPU + GPU",
           SystemConfig("cortex_a78_x4", "mobile_gpu", "LPDDR5", 1,
                        preprocessing_mode="isp_and_npu"),
           "Fewer memory packages, preprocessing offloaded."),
        _d("Example B", "High performance", "CPU + GPU + Specialised NPU",
           SystemConfig("cortex_a78_x4", "mobile_gpu", "LPDDR5", 4,
                        preprocessing_mode="isp_and_npu",
                        secondary_compute="npu_32x32", execution_mode="sequential",
                        work_split=0.0),
           "More bandwidth, with an INT8 engine doing the preprocessing. Note "
           "what the accuracy gate does with a mixed pair: the worse engine "
           "governs, because every job has to clear the bar."),
        _d("Example C", "Balanced", "CPU + GPU + GDDR",
           SystemConfig("cortex_a78_x4", "mobile_gpu", "GDDR6", 2,
                        preprocessing_mode="isp_and_npu"),
           "Bandwidth without more packages."),
    ],

    "ai_inference": [
        _d("Starting point", "Example published configuration", "CPU + GPU + HBM",
           SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 8),
           "A general accelerator card with stacked memory. Eight stacks "
           "rather than six because the model serves requests ONE AT A TIME - "
           "batching is not represented, and an unbatched GPU reaches a small "
           "fraction of its peak. A real serving node would batch and need "
           "less. This is the pessimistic reading, and it is labelled as one."),
        _d("Example A", "Low power", "CPU + GPU + GDDR",
           SystemConfig("server_x86_x32", "datacenter_gpu", "GDDR6", 8),
           "Graphics memory instead of stacks: much cheaper, and the throughput "
           "requirement is where it fails."),
        _d("Example B", "High performance", "CPU + GPU + HBM",
           SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 12),
           "More stacks still. Watch the power ceiling on the slot."),
        _d("Example C", "Balanced", "CPU + Customised NPU + HBM",
           SystemConfig("server_x86_x32", "npu_128x128", "HBM3E", 6),
           "A fixed-function array instead of a GPU. Cheaper per operation, "
           "less flexible."),
    ],

    "llm_service": [
        # TWO references, kept apart on purpose. Moving the reference from six
        # stacks to eight because six missed the requirement is how a design
        # gets fitted to a target, and from outside it looks identical to
        # honest engineering. So both are shown: what a published part is, and
        # what the requirement needs.
        _d("Starting point", "Requirement-matched", "CPU + GPU + HBM",
           SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 10),
           "Ten 24 GB stacks - the smallest configuration that meets the "
           "token-rate requirement at the TYPICAL serving efficiency. This "
           "reference has now moved three times: six to eight when serving "
           "losses were added, eight to ten when the coefficient was widened "
           "into a band and its typical value fell. Each move is traceable to "
           "a named model change, and the pattern is itself worth noticing - a "
           "reference that has to grow every time the model gets more honest "
           "is telling you the requirement was set against an optimistic "
           "model. Compare with the published-class option below: a real "
           "H200-class part carries six."),
        _d("Published-class reference", "What a shipping part is", "CPU + GPU + HBM",
           SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6),
           "Six 24 GB stacks, matching an H200-class package. Simulated 29.6 "
           "tokens per second against a 35 requirement - it does not meet it, "
           "and that is reported rather than fixed."),
        _d("Example A", "Low power", "CPU + GPU + less HBM",
           SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 4),
           "Four stacks: 96 GB. Cheaper and cooler, and a 70B model with its "
           "KV cache no longer fits - which is the point of trying it."),
        _d("Example B", "High performance", "CPU + Transformer accelerator",
           SystemConfig("server_x86_x32", "npu_128x128", "HBM3E", 10),
           "A dedicated array. Decode is memory bound, so ask what the array "
           "actually buys."),
        _d("Example C", "Balanced", "CPU + Custom NPU + HBM",
           SystemConfig("server_x86_x32", "npu_128x128", "HBM3E", 6),
           "The same array on less memory - which is the wall here."),
    ],
}


def designs_for(app_key: str) -> List[DesignOption]:
    """Reference and examples for an application, or a derived pair for a
    student-defined one."""
    if app_key in DESIGNS:
        return DESIGNS[app_key]
    app = APPLICATION_LIBRARY[app_key]
    if app.domain == "Data Center":
        base = SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6)
        alt = SystemConfig("server_x86_x32", "npu_128x128", "HBM3E", 6)
    else:
        base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
        alt = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                           preprocessing_mode="isp_and_npu")
    return [
        _d("Starting point", "Derived", "CPU + NPU", base,
           "No reference exists for an application that did not exist until "
           "now. This is a generic starting point and is probably wrong for "
           "your product - which is the exercise."),
        _d("Example A", "Offloaded", "CPU + ISP + NPU", alt,
           "Preprocessing moved off the host."),
    ]


def reference_of(app_key: str) -> SystemConfig:
    return designs_for(app_key)[0].config


def print_designs(app_key: str, evaluate: bool = True) -> None:
    """Show the reference and the examples, with numbers if asked."""
    app = APPLICATION_LIBRARY[app_key]
    line = "=" * 78
    print(f"\n{line}")
    print(f" REFERENCE AND DESIGN EXAMPLES - {app.name}")
    print(line)
    print("  The reference is where products in this category are today.")
    print("  The examples are directions, not recommendations: copying one is")
    print("  not the exercise, beating them is.\n")

    for d in designs_for(app_key):
        flag = "" if d.modelled else "   [approximated: one accelerator only]"
        print(f"  {d.tier:<12s}{d.label:<18s}{d.architecture}{flag}")
        print(f"  {'':<12s}{_short(d.config)}")
        print(f"  {'':<12s}{d.rationale}")
        if evaluate:
            r = evaluate_system(app, d.config)
            m = r.metrics
            verdict = "meets requirements" if r.passes else (
                "fails: " + ", ".join(g for g, ok in r.gate.items() if not ok))
            print(f"  {'':<12s}latency {m['Latency (ms)']:.2f} ms, "
                  f"{m['System power (W)']:.2f} W, "
                  f"{m['Total silicon (mm2)']:.0f} mm2, "
                  f"${m['System cost (USD)']:.2f}  -  {verdict}")
        print()


def _short(cfg: SystemConfig) -> str:
    from .compute import COMPUTE_LIBRARY as C
    from .cpu import CPU_LIBRARY as P
    from .memory import MEMORY_LIBRARY as M
    return (f"{P[cfg.cpu].name} + {C[cfg.compute].name} + "
            f"{M[cfg.memory].name} x{cfg.memory_devices}, "
            f"preprocessing: {cfg.preprocessing_mode}")


def compare_with_examples(app_key: str, student: SystemConfig,
                          duration_s: float = 60.0) -> None:
    """Reference, examples and the student's design, side by side."""
    from .runtime import simulate
    app = APPLICATION_LIBRARY[app_key]
    rows = [(d.tier, d.label, d.config) for d in designs_for(app_key)]
    rows.append(("Your design", "", student))

    line = "=" * 92
    print(f"\n{line}")
    print(f" REFERENCE vs EXAMPLES vs YOUR DESIGN - {app.name}")
    print(line)
    head = (f"  {'':<14s}{'latency':>10s}{'jobs/s':>9s}{'power':>8s}"
            f"{'energy/job':>12s}{'silicon':>10s}{'cost':>9s}{'ok':>5s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for tier, label, cfg in rows:
        r = simulate(app_key, cfg, duration_s=duration_s)
        m = r.metrics
        print(f"  {tier:<14s}{r.first_latency_ms:>10.2f}{r.throughput:>9.1f}"
              f"{m['Average power (W)']:>8.2f}{m['Energy per job (mJ)']:>12.2f}"
              f"{m['Total silicon (mm2)']:>10.0f}{m['System cost (USD)']:>9.2f}"
              f"{('yes' if r.base.passes else 'no'):>5s}")
    print("\n  Beating an example on one axis is easy. Beating the reference on")
    print("  the axes this application actually weighs is the exercise.")
