"""
ppact.evaluation_mode - what a score is relative TO

WHY THREE MODES AND NOT ONE
===========================
A score has no meaning without a reference, and there are two different
kinds of reference that a single chart quietly conflated:

    benchmark     what else exists      "is this a good NPU"
    requirement   what this needs       "is this good enough for THIS"

The same hardware answers those differently. 120 inf/s is generous for
industrial vision at a 60 inf/s target and short for a service needing
500. Neither answer is wrong; they are answers to different questions.

WHAT WENT WRONG BEFORE
----------------------
The spider used absolute anchors and was read as a design assessment. A
design sitting exactly on its requirement scored anywhere from 0.0 to
83.5 depending on the application, because the anchors did not know what
the application asked for.

BENCHMARK AND REQUIREMENT ARE NEVER MIXED
-----------------------------------------
A benchmark is a COMPARISON. A requirement is a PASS MARK. Scoring against
one and reading it as the other is the failure this module exists to
prevent, so they do not share a scoring path.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

BUILT_IN = "built-in benchmark"
USER = "user benchmark"
DESIGN = "design assessment"

NOT_ESTABLISHED = "NOT ESTABLISHED"


# ==============================================================================
# One measured value, one constraint, one slack
# ==============================================================================
#
# The two modes are not two calculations. They are the SAME calculation
# with a different constraint source:
#
#     measured value  ->  constraint  ->  slack  ->  status
#
# Benchmark supplies the constraint from a reference; design assessment
# supplies it from the application. Nothing downstream changes, which is
# why the modes cannot disagree about arithmetic - only about what the
# design is being held to.
#
# The generalisation is deliberate. A timing report computes measured
# delay against required time and reports slack; this computes measured
# throughput, area or cost against a constraint and reports slack. What
# differs between the two modes is what "required" means, and that is a
# choice a user makes rather than a property of the design.


@dataclass(frozen=True)
class Constraint:
    """What a measured value is held to, and where that came from."""
    axis: str
    value: Optional[float]
    source: str
    higher_is_better: bool
    unit: str = ""

    @property
    def established(self) -> bool:
        return self.value is not None and self.value > 0


def constraint_for(axis: str, mode_key: str, analysis,
                   user_reference: Optional[Dict[str, float]] = None
                   ) -> Constraint:
    """The constraint an axis is held to, under the chosen mode.

    ONE function, because the modes differ in nothing else. A second
    scoring path per mode is how two answers to the same arithmetic
    appear.
    """
    from .system import REQUIREMENT_AXES, SYSTEM_ANCHORS
    from .application import APPLICATION_LIBRARY

    spec = REQUIREMENT_AXES.get(axis)
    higher = spec[2] if spec else True

    if mode_key == DESIGN:
        if spec is None:
            return Constraint(axis, None,
                              "no requirement declared for this axis",
                              higher)
        app = APPLICATION_LIBRARY[analysis.app_key]
        return Constraint(axis, getattr(app, spec[1], None),
                          f"application requirement ({spec[1]})", higher)

    if mode_key == USER:
        value = (user_reference or {}).get(axis)
        return Constraint(
            axis, value,
            "user reference" if value else "no user reference set",
            higher)

    # Built-in benchmark: the absolute anchor's hundred-point end is the
    # reference. It is a comparison point, not a pass mark, and the mode
    # header says so.
    anchor = SYSTEM_ANCHORS.get(axis)
    if anchor is None:
        return Constraint(axis, None, "no anchor for this axis", higher)
    return Constraint(axis, anchor.at_hundred,
                      "built-in benchmark anchor", higher, anchor.unit)


def slack_against(constraint: Constraint, measured: Optional[float]
                  ) -> Optional[float]:
    """Ratio-based slack, in the same 50-at-the-constraint scale.

    Identical arithmetic in every mode. The constraint moved; the formula
    did not.
    """
    import math

    if measured is None or not constraint.established or measured <= 0:
        return None
    ratio = (measured / constraint.value if constraint.higher_is_better
             else constraint.value / measured)
    if ratio <= 0:
        return None
    return max(0.0, min(100.0, 50.0 + 20.0 * math.log2(ratio)))


@dataclass(frozen=True)
class EvaluationMode:
    key: str
    title: str
    question: str
    reference: str
    score_means_50: str


MODES: Dict[str, EvaluationMode] = {
    BUILT_IN: EvaluationMode(
        BUILT_IN, "PPACT Benchmark",
        "Where does this design sit among designs generally?",
        "the built-in absolute anchors",
        "the midpoint of the anchor range - NOT a pass mark"),
    USER: EvaluationMode(
        USER, "PPACT Benchmark - user reference",
        "How does this design compare to a reference the user chose?",
        "a user-declared reference product or figure set",
        "equal to the reference"),
    DESIGN: EvaluationMode(
        DESIGN, "PPACT Design Assessment",
        "Does this design meet what this application requires?",
        "the application's declared requirements",
        "meets the requirement exactly"),
}

# THE DEFAULT IS DESIGN ASSESSMENT, not the benchmark.
#
# Every application in the library declares requirements, and the spider
# already scores against them - 50 means "meets the requirement" on every
# axis. Defaulting to the benchmark would label that chart with the wrong
# question, which is the exact confusion this module exists to end.
#
# The benchmark becomes the default only for a design with no declared
# requirements, and no such design exists in the library today.
DEFAULT_MODE = DESIGN


def mode_for(analysis, requested: Optional[str] = None) -> str:
    """Which mode applies. Requirements do not silently override a choice.

    An application with declared requirements makes DESIGN available and
    does not select it: a user comparing hardware wants the benchmark
    even when the application has a target, and switching under them
    would change what the numbers mean without saying so.
    """
    if requested in MODES:
        return requested
    # Fall back to the benchmark only when there is nothing to assess
    # against: a requirement-centred score needs a requirement.
    return (DESIGN if DESIGN in available_modes(analysis)
            else BUILT_IN)


def available_modes(analysis) -> List[str]:
    from .system import REQUIREMENT_AXES
    from .application import APPLICATION_LIBRARY

    modes = [BUILT_IN, USER]
    app = APPLICATION_LIBRARY[analysis.app_key]
    if any(getattr(app, attr, None)
           for _, attr, _ in REQUIREMENT_AXES.values()):
        modes.append(DESIGN)
    return modes


def render_mode_header(mode_key: str, analysis=None) -> List[str]:
    """What question this chart is answering, before any figure.

    Printed first because a reader who sees 50 and does not know the mode
    will assume the one they came looking for.
    """
    from .visual.text import wrap_text

    mode = MODES[mode_key]
    out = [f"  EVALUATION MODE   {mode.title}", ""]
    out.append(f"      Question        {mode.question}")
    out.append(f"      Scored against  {mode.reference}")
    out.append(f"      A score of 50   {mode.score_means_50}")
    out.append("")
    if mode_key != DESIGN:
        for line in wrap_text(
                "A benchmark is a comparison, not a pass mark. A design "
                "scoring well here has not been shown to meet any "
                "application's requirements - see the deployment gates "
                "for that.", 62):
            out.append(f"      {line}")
    else:
        for line in wrap_text(
                "A requirement is a pass mark, not a comparison. A design "
                "scoring 60 here is not better hardware than one scoring "
                "40 for a harder application.", 62):
            out.append(f"      {line}")
    if analysis is not None:
        others = [MODES[m].title for m in available_modes(analysis)
                  if m != mode_key]
        if others:
            out.append("")
            out.append(f"      Also available  {', '.join(others)}")
    return out
