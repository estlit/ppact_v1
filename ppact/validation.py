"""
ppact.validation - the model beside published products

NOT verification. The figures below were used to FIT the model, so agreement is
by construction: a profile adjusted until it matches a datasheet has been
aligned, not confirmed. Verification would mean measuring hardware or checking
against a golden model, and neither happened here. See ppact.evidence for the
levels this project uses and why VERIFIED is not among them.

Internal consistency is checkable by a test suite. Agreement with reality is
not, and the only honest substitute is to write down what published products
say and record where the model lands against them - including where it does
not.

Each reference records what is being compared, the published figure, its
source, and a tolerance. A comparison that fails is kept in the list rather
than removed, because a known discrepancy is information and a deleted one is
not.

WHAT THIS CAN AND CANNOT SETTLE
-------------------------------
Capacity and bandwidth are published and can be checked. Cost, power and
thermal figures are contract-dependent or not published at all, and no amount
of comparison will settle them - they stay marked as estimates in
ppact.coefficients and are deliberately absent here.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass(frozen=True)
class Reference:
    product: str
    quantity: str
    published: float
    unit: str
    source: str
    tolerance_pct: float
    note: str = ""


# Published figures. Capacity and bandwidth only - the things a vendor states
# and a reader can check.
REFERENCES: List[Reference] = [
    Reference("NVIDIA H200", "HBM3E capacity", 141.0, "GB",
              "vendor product page", 5.0,
              "Six 24 GB stacks: 144 GB nominal, 141 GB usable. The 2% held "
              "back is ECC and redundancy, which the model does not deduct."),
    Reference("NVIDIA H200", "memory bandwidth", 4.80, "TB/s",
              "vendor product page", 5.0,
              "Six stacks at roughly 6.25 Gbps. The HBM3E component ceiling is "
              "9.6 Gbps; shipping designs back off for power and thermal "
              "reasons, and the model uses the deployed rate."),
    Reference("AMD MI300X", "HBM3 capacity", 192.0, "GB",
              "vendor product page", 8.0,
              "Eight stacks. Included as a range check rather than an exact "
              "match: MI300X is HBM3, not HBM3E."),
    Reference("Micron HBM3E", "bandwidth per stack (spec)", 1.2, "TB/s",
              "vendor product page", 10.0,
              "The component ceiling at 9.6 Gbps, which the model records "
              "separately from the rate it uses. A vendor press account makes "
              "the same distinction: six stacks would give 7.2 TB/s in theory "
              "and an H200 delivers 4.8."),
    Reference("Micron HBM4", "bandwidth per stack (spec)", 2.8, "TB/s",
              "vendor product page", 10.0,
              "At the cited >11 Gbps over 2048 bits. The model records this as "
              "the ceiling and runs at 6.4 Gbps, which is where SK hynix "
              "demonstrated 1.6 TB/s per stack - HBM4 widens the pipe rather "
              "than raising the clock, and that is where its power advantage "
              "comes from."),
    Reference("SK hynix HBM4", "demonstrated bandwidth per stack", 1.6, "TB/s",
              "CES 2026 demonstration", 8.0,
              "The operating point, as distinct from the specification "
              "maximum above."),
    Reference("Memory-bound decode example", "tokens/s at 300 GB/s", 19.0,
              "tokens/s", "published technical example", 12.0,
              "A 16 GB model over 300 GB/s. The published figure is bytes over "
              "bandwidth and nothing else, so the model's memory-limited "
              "CEILING is what should match - the delivered rate is lower by "
              "the host overhead the example omits."),
    Reference("Memory-bound decode example", "tokens/s at 1.5 TB/s", 94.0,
              "tokens/s", "published technical example", 12.0,
              "The same model over 1.5 TB/s. Five times the bandwidth, five "
              "times the rate - which is the point of the example."),
    # RANGE CHECKS rather than alignments. These are deployment outcomes with
    # an unstated precision, so the model is asked to land inside a bracket
    # rather than on a number - a tighter test would be false precision.
    Reference("Single-card 8B deployment", "serving efficiency", 0.41,
              "fraction of ceiling", "vendor-published deployment figure", 65.0,
              "40-60 tokens per second against a ceiling of 181 (FP8) or 92 "
              "(FP16). The wide tolerance is the precision ambiguity, not "
              "slack in the model."),
    Reference("Four-card 32B deployment", "serving efficiency", 0.48,
              "fraction of ceiling", "customer evaluation, vendor-published",
              65.0,
              "60 tokens per second against a ceiling of 187 (FP8) or 94 "
              "(FP16). Independent of the single-card case above, and it "
              "brackets the same way."),
    Reference("JEDEC HBM4", "interface width", 2048.0, "bit",
              "JEDEC specification, April 2025", 0.1,
              "Doubled from HBM3E across 32 channels."),
]


def check_h200(memory_library) -> dict:
    """Six 24 GB HBM3E stacks, as an H200 is actually built."""
    h = memory_library["HBM3E"]
    return {"capacity_gb": h.capacity_gbyte * 6,
            "bandwidth_tbs": h.bandwidth_gbytes_s * 6 / 1000.0}


def check_mi300x(memory_library) -> dict:
    """Eight 24 GB stacks."""
    h = memory_library["HBM3E"]
    return {"capacity_gb": h.capacity_gbyte * 8}


def check_hbm4_spec(memory_library) -> dict:
    h = memory_library["HBM4_36"]
    speed = h.peak_pin_speed_gbps or h.pin_speed_gbps
    return {"bandwidth_tbs": h.package_io_width * speed / 8.0 / 1000.0,
            "width_bit": float(h.package_io_width)}


def check_hbm4_deployed(memory_library) -> dict:
    h = memory_library["HBM4_36"]
    return {"bandwidth_tbs": h.bandwidth_gbytes_s / 1000.0}


def check_decode_ceiling(bandwidth_gb_s: float, weight_gb: float = 16.0) -> float:
    """Memory-limited token rate: bytes per token over bandwidth.

    Deliberately arithmetic rather than a simulator call - the published
    example is arithmetic too, and a check that ran the model against itself
    would confirm nothing.
    """
    return bandwidth_gb_s / weight_gb


def _serving() -> float:
    from .system import LLM_SINGLE_STREAM_SERVING_EFFICIENCY
    return LLM_SINGLE_STREAM_SERVING_EFFICIENCY


def check_stack_spec(memory_library) -> dict:
    """The component ceiling, not the deployed rate."""
    h = memory_library["HBM3E"]
    speed = h.peak_pin_speed_gbps or h.pin_speed_gbps
    return {"bandwidth_tbs": h.package_io_width * speed / 8.0 / 1000.0}


def run(memory_library=None) -> List[tuple]:
    """Compare and return (reference, modelled, deviation %, within tolerance)."""
    if memory_library is None:
        from .memory import MEMORY_LIBRARY as memory_library
    h200 = check_h200(memory_library)
    mi300 = check_mi300x(memory_library)
    spec = check_stack_spec(memory_library)
    modelled = {
        ("NVIDIA H200", "HBM3E capacity"): h200["capacity_gb"],
        ("NVIDIA H200", "memory bandwidth"): h200["bandwidth_tbs"],
        ("AMD MI300X", "HBM3 capacity"): mi300["capacity_gb"],
        ("Micron HBM3E", "bandwidth per stack (spec)"): spec["bandwidth_tbs"],
        ("Micron HBM4", "bandwidth per stack (spec)"):
            check_hbm4_spec(memory_library)["bandwidth_tbs"],
        ("SK hynix HBM4", "demonstrated bandwidth per stack"):
            check_hbm4_deployed(memory_library)["bandwidth_tbs"],
        ("JEDEC HBM4", "interface width"):
            check_hbm4_spec(memory_library)["width_bit"],
        ("Memory-bound decode example", "tokens/s at 300 GB/s"):
            check_decode_ceiling(300.0),
        ("Memory-bound decode example", "tokens/s at 1.5 TB/s"):
            check_decode_ceiling(1500.0),
        ("Single-card 8B deployment", "serving efficiency"): _serving(),
        ("Four-card 32B deployment", "serving efficiency"): _serving(),
    }
    out = []
    for ref in REFERENCES:
        got = modelled[(ref.product, ref.quantity)]
        dev = (got / ref.published - 1.0) * 100.0
        out.append((ref, got, dev, abs(dev) <= ref.tolerance_pct))
    return out


def print_validation() -> None:
    line = "=" * 84
    print(line)
    print(" REFERENCE ALIGNMENT")
    print(line)
    print("  Capacity and bandwidth beside published products. The model was")
    print("  fitted to these, so agreement is alignment rather than evidence -")
    print("  what a mismatch would show is an error, what a match shows is that")
    print("  the fitting was done. Cost, power and thermal figures are absent")
    print("  because they are not published and cannot be aligned to anything.\n")
    head = (f"  {'product':<16s}{'quantity':<30s}{'published':>11s}"
            f"{'model':>10s}{'dev':>9s}{'':>6s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for ref, got, dev, ok in run():
        print(f"  {ref.product:<16s}{ref.quantity:<30s}"
              f"{ref.published:>11.2f}{got:>10.2f}{dev:>+8.1f}%"
              f"{('  aligned' if ok else '  OUT'):>10s}")
    print()
    for ref, got, dev, ok in run():
        if ref.note:
            print(f"  {ref.product} - {ref.quantity}")
            print(f"    {ref.note}\n")
