"""
holdout_adjudication_v1.py - what the disagreements turned out to be

The prediction file is NOT edited. This is the separate record of what each
disagreement was, decided after investigating rather than after seeing.

The runner classifies mechanically from the prediction's own terms. This file
records what investigation found, which is sometimes different - a metric
declared invariant that moves looks like a model defect and can turn out to be
a prediction that named the wrong invariant.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Adjudication:
    pid: str
    mechanical: str          # what the runner said
    adjudicated: str         # what investigation found
    finding: str
    action: str


ADJUDICATIONS: Tuple[Adjudication, ...] = (

    Adjudication(
        "H-01", "DIRECTION DISAGREEMENT", "PREDICTION DEFECT",
        finding="Predicted the capacity would be unchanged; it fell 0.8%. The "
                "second engine launches its own graph, and that launch lands "
                "on the host - which the prediction itself identified as the "
                "limiting station. Adding work to the slowest station makes it "
                "slower. The prediction reasoned correctly about the "
                "bottleneck and then forgot that the second engine also costs "
                "the bottleneck something. Cost was predicted 'up' and moved "
                "0.5%, which is inside the direction tolerance - the die is "
                "small against this product's bill of materials.",
        action="None. The model is right and more careful than the "
               "prediction was."),

    Adjudication(
        "H-05", "MODEL DEFECT", "PREDICTION DEFECT",
        finding="Predicted accuracy must not change when work is split "
                "between a 32x32 and a 16x16 engine. It fell 1.05%. The two "
                "engines are not the same engine at different sizes: the "
                "32x32 is quantisation-aware trained and the 16x16 is "
                "post-training quantised. Running half the work on a "
                "post-training-quantised engine genuinely lowers the "
                "accuracy of the result. The prediction assumed engines "
                "differ only in how many multipliers they have.",
        action="None to the model. Worth recording that 'a second engine does "
               "not change accuracy' - asserted elsewhere in the suite - is "
               "only true when the two engines share a precision, and that "
               "the existing check uses two identical engines and so never "
               "tested the other case."),

    Adjudication(
        "H-06", "DIRECTION DISAGREEMENT", "PREDICTION DEFECT",
        finding="Predicted that moving to 3 nm would raise the peak "
                "arithmetic and lower the compute time. Neither moved, "
                "because mobile_ai already defaults to 3 nm - the change was "
                "a no-op and the prediction never checked the starting point.",
        action="None. A prediction that does not state its baseline is a "
               "prediction about nothing."),
)


def summary():
    from collections import Counter
    return Counter(a.adjudicated for a in ADJUDICATIONS)


if __name__ == "__main__":
    print(f"{'id':<7s}{'runner said':<24s}{'investigation found':<20s}")
    for a in ADJUDICATIONS:
        print(f"{a.pid:<7s}{a.mechanical:<24s}{a.adjudicated:<20s}")
    print()
    for k, v in summary().items():
        print(f"  {k}: {v}")
    print("\n  Zero model defects. Three predictions that were wrong, and one")
    print("  of them - H-05 - found a claim asserted elsewhere in the suite")
    print("  that is narrower than it looks.")
