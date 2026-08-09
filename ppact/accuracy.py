"""
ppact.accuracy - how much accuracy survives deployment

Quantisation loss is a property of the MODEL and the METHOD together, not of
the silicon alone. A convolutional classifier under quantisation-aware training
loses a fraction of a point to INT8; a transformer under post-training
quantisation can lose several. Storing one number per accelerator would tie
those two cases together, and tuning it to fix one application would silently
move every other - which is exactly what happened in revision 3.6.0 and is
recorded in ppact.revisions.

    retention = model family  x  quantisation method  x  precision

Figures are engineering estimates from the published quantisation literature,
not measurements, and they are the values most worth arguing with in this file.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from typing import Dict, Tuple

MODEL_FAMILIES = ("cnn", "detection", "transformer")
METHODS = ("none", "PTQ", "QAT", "QAT_FP16")

# Percentage points lost, by (family, method, precision).
#
# Reading the table: detection heads lose more than classifiers because
# localisation error compounds with confidence error; transformers lose most
# because activation outliers in attention do not quantise gracefully.
# QAT_FP16 keeps the sensitive layers in floating point, which is why it costs
# least in accuracy and most in area and power.
QUANTISATION_LOSS_PP: Dict[Tuple[str, str, str], float] = {}


def _fill():
    base = {
        # family      PTQ   QAT   QAT_FP16
        "cnn":         (1.0, 0.40, 0.25),
        "detection":   (1.4, 0.60, 0.35),
        "transformer": (2.2, 1.00, 0.60),
    }
    # INT4 roughly doubles the INT8 penalty and adds a floor.
    int4_scale, int4_floor = 2.0, 0.8
    for family, (ptq, qat, qatfp) in base.items():
        for method, v in (("PTQ", ptq), ("QAT", qat), ("QAT_FP16", qatfp)):
            QUANTISATION_LOSS_PP[(family, method, "INT8")] = v
            QUANTISATION_LOSS_PP[(family, method, "INT4")] = v * int4_scale + int4_floor
        # Floating point: the method is irrelevant, the arithmetic is not lossy
        for method in METHODS:
            QUANTISATION_LOSS_PP[(family, method, "FP32")] = 0.0
            QUANTISATION_LOSS_PP[(family, method, "FP16")] = 0.1
            QUANTISATION_LOSS_PP[(family, method, "FP16 / BF16")] = 0.1
        # An engine with no quantisation step at all
        QUANTISATION_LOSS_PP[(family, "none", "INT8")] = base[family][0]
        QUANTISATION_LOSS_PP[(family, "none", "INT4")] = base[family][0] * int4_scale + int4_floor


_fill()


CANONICAL_PRECISIONS = ("INT4", "INT8", "FP16", "BF16", "FP32")


def canonical_precision(precision: str) -> str:
    """Reduce a descriptive precision string to the arithmetic it names.

    Library entries carry readable labels - "INT8 (quantisation-aware trained)"
    - and a table cannot be keyed on prose. Matching on the arithmetic token
    keeps both: the label stays readable and the lookup stays exact. Without
    this the lookup missed silently and fell back to the harshest figure, which
    looked like a plausible number and was not the right one.
    """
    upper = precision.upper()
    for token in CANONICAL_PRECISIONS:
        if token in upper:
            return "FP16" if token == "BF16" else token
    return "INT8"


def quantisation_loss_pp(model_family: str, method: str, precision: str) -> float:
    """Points lost, defaulting conservatively when a combination is unlisted."""
    family = model_family if model_family in MODEL_FAMILIES else "cnn"
    key = (family, method, canonical_precision(precision))
    if key in QUANTISATION_LOSS_PP:
        return QUANTISATION_LOSS_PP[key]
    # An unlisted precision string is treated as the harshest INT8 case rather
    # than as zero: a missing entry must not look like a free lunch.
    return QUANTISATION_LOSS_PP[(family, "PTQ", "INT8")]


def print_table() -> None:
    line = "=" * 70
    print(line)
    print(" QUANTISATION LOSS (percentage points)")
    print(line)
    print("  A single number cannot cover a CNN under QAT and a transformer")
    print("  under PTQ. These are estimates from the literature, and they are")
    print("  the figures in this file most worth disagreeing with.\n")
    head = f"  {'family':<14s}" + "".join(f"{m:>12s}" for m in ("PTQ", "QAT", "QAT_FP16"))
    print(head); print("  " + "-" * (len(head) - 2))
    for family in MODEL_FAMILIES:
        row = f"  {family:<14s}"
        for method in ("PTQ", "QAT", "QAT_FP16"):
            row += f"{QUANTISATION_LOSS_PP[(family, method, 'INT8')]:>12.2f}"
        print(row)
    print("\n  INT8 shown. INT4 roughly doubles it and adds 0.8 pp.")
    print("  FP16 costs 0.1 pp whatever the method; FP32 costs nothing.")
