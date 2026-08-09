"""
ppact.preprocess - where the preprocessing runs

Adding an accelerator is not a decision a student should make in the abstract.
The decision that actually exists is narrower and more interesting: which
preprocessing work moves off the CPU, and onto what.

    CPU only      everything on the host
    ISP assisted  the camera block does resize, colour and noise reduction
    NPU assisted  the accelerator does them, at the cost of a hand-off
    ISP and NPU   both

The hand-off is the point. Moving work to an accelerator costs a dispatch and a
transfer, and below some image size that cost exceeds what the move saves. A
model without that overhead would teach the opposite of the truth - that
offloading always helps - which is exactly the conclusion this is meant to
prevent.

An ISP is fixed-function and sits in the sensor path, so its work is treated as
hidden behind capture rather than added to latency. It is not free: it costs
silicon and static power whether or not a given frame needs it.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class PreprocessFunction:
    """One preprocessing step, described relative to the CPU cost of all of them.

    cpu_share sums to 1.0 across the table, so the per-pixel CPU cost in the CPU
    library stays the calibration point and this table only says how it splits.
    """
    name: str
    cpu_share: float          # fraction of the total per-pixel CPU cost
    npu_mac_per_pixel: float  # cost if the accelerator does it instead
    isp_capable: bool         # a fixed-function camera block can do it
    npu_capable: bool


PREPROCESS_FUNCTIONS: Dict[str, PreprocessFunction] = {
    "resize":           PreprocessFunction("Resize", 0.32, 4.0, True, True),
    "color_conversion": PreprocessFunction("Colour conversion", 0.20, 2.0, True, True),
    "noise_reduction":  PreprocessFunction("Noise reduction", 0.24, 6.0, True, True),
    "normalization":    PreprocessFunction("Normalisation", 0.16, 1.0, False, True),
    "roi_extraction":   PreprocessFunction("ROI extraction", 0.08, 0.5, False, True),
}

MODES: Dict[str, Dict[str, str]] = {
    "cpu_only": {
        "label": "CPU only",
        "notes": "Everything on the host. No extra silicon, no hand-off, and the "
                 "CPU carries the whole per-pixel cost."},
    "isp_assisted": {
        "label": "ISP assisted",
        "notes": "A fixed-function camera block takes resize, colour conversion "
                 "and noise reduction. Its work hides behind capture, so it "
                 "costs area and static power rather than latency."},
    "npu_assisted": {
        "label": "NPU assisted",
        "notes": "The accelerator takes the same work plus normalisation and "
                 "ROI. Fast per pixel, but every frame pays a dispatch and a "
                 "transfer - which is why small frames come out slower."},
    "isp_and_npu": {
        "label": "ISP and NPU",
        "notes": "The camera block handles what it can and the accelerator takes "
                 "the rest. The CPU is left with almost nothing, and the system "
                 "carries both the ISP silicon and the hand-off."},
}

# Cost of running an ISP block, at the reference node.
ISP_AREA_MM2 = 3.2
ISP_STATIC_POWER_W = 0.30
ISP_ENERGY_PJ_PER_PIXEL = 55.0

# What preprocessing support adds to an accelerator that did not have it.
NPU_PREPROCESS_AREA_UPLIFT = 0.08      # +8% die area
NPU_PREPROCESS_POWER_UPLIFT = 0.06     # +6% static power
# Per CALL, not per job. Whether four camera streams are one call or four is a
# design decision, and it changes the fixed cost by a factor of four - large
# enough to move the break-even frame size. Charging it once regardless was
# simply wrong.
NPU_PREPROCESS_DISPATCH_US = 90.0

# An ISP is a real pipeline stage with a real throughput, not a free box. Its
# work is usually hidden behind sensor capture, but "hidden" and "zero" are
# different claims and only one of them is true.
ISP_PIXELS_PER_SECOND = 2.0e9   # a modern multi-camera ISP pipeline

# NPU-assisted preprocessing REUSES THE MAIN ARRAY. Preprocessing and inference
# therefore cannot run at the same time, and the accelerator's active time is
# the sum of the two. A separate vision NPU could overlap them, at the cost of
# its own area, static power and price; that is a different block and is not
# what this mode models.
NPU_PREPROCESSING_SHARES_MAIN_ARRAY = True


def split(mode: str) -> Tuple[float, float, float]:
    """Return the (cpu, isp, npu) share of the per-pixel preprocessing cost."""
    if mode not in MODES:
        raise KeyError(f"Unknown preprocessing mode '{mode}'. "
                       f"Available: {', '.join(MODES)}")
    cpu = isp = npu = 0.0
    for fn in PREPROCESS_FUNCTIONS.values():
        if mode == "cpu_only":
            cpu += fn.cpu_share
        elif mode == "isp_assisted":
            if fn.isp_capable:
                isp += fn.cpu_share
            else:
                cpu += fn.cpu_share
        elif mode == "npu_assisted":
            if fn.npu_capable:
                npu += fn.cpu_share
            else:
                cpu += fn.cpu_share
        else:   # isp_and_npu
            if fn.isp_capable:
                isp += fn.cpu_share
            elif fn.npu_capable:
                npu += fn.cpu_share
            else:
                cpu += fn.cpu_share
    return cpu, isp, npu


def npu_mac_per_pixel(mode: str) -> float:
    """Accelerator work per pixel for whatever this mode moved onto it."""
    if mode == "npu_assisted":
        return sum(f.npu_mac_per_pixel for f in PREPROCESS_FUNCTIONS.values()
                   if f.npu_capable)
    if mode == "isp_and_npu":
        return sum(f.npu_mac_per_pixel for f in PREPROCESS_FUNCTIONS.values()
                   if f.npu_capable and not f.isp_capable)
    return 0.0


def uses_isp(mode: str) -> bool:
    return mode in ("isp_assisted", "isp_and_npu")


def uses_npu_preprocessing(mode: str) -> bool:
    return mode in ("npu_assisted", "isp_and_npu")


def print_modes() -> None:
    print("=" * 78)
    print(" PREPROCESSING PLACEMENT")
    print("=" * 78)
    print("  Which module does the work before inference. The accelerator is")
    print("  faster per pixel and charges a hand-off for every frame, so the")
    print("  answer depends on how many pixels there are.\n")
    head = f"  {'mode':<16s}{'CPU':>7s}{'ISP':>7s}{'NPU':>7s}   what moves"
    print(head); print("  " + "-" * (len(head) - 2))
    for key, meta in MODES.items():
        cpu, isp, npu = split(key)
        moved = []
        for fn in PREPROCESS_FUNCTIONS.values():
            if key == "cpu_only":
                continue
            if uses_isp(key) and fn.isp_capable:
                moved.append(f"{fn.name}->ISP")
            elif uses_npu_preprocessing(key) and fn.npu_capable:
                moved.append(f"{fn.name}->NPU")
        print(f"  {meta['label']:<16s}{cpu:>7.2f}{isp:>7.2f}{npu:>7.2f}   "
              f"{', '.join(moved) if moved else 'nothing'}")
    print()
    for key, meta in MODES.items():
        print(f"  {meta['label']}")
        print(f"    {meta['notes']}\n")
