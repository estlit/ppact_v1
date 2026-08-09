"""
ppact.study_cases - the stimulus set for a blind user study

WHAT THIS FILE IS AND IS NOT
============================
It defines the designs a participant would be shown and the answer the
engine gives for each. It does not contain results, because there are
none: a user study needs users, and no participant has seen any of this.

Each case is verified to produce the condition it claims. A stimulus set
whose "host-limited" case is not host-limited would measure the
participants against the wrong answer, and that error is invisible once
the numbers exist.

THE CONDITIONS THE SET MUST COVER
---------------------------------
The bottleneck in each place it can be, a case where it moves, and the
cases where a reader is most likely to go wrong: a design that just
passes, one far inside its budget, and two designs that differ barely
at all.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class StudyCase:
    """One design, or one pair, shown to a participant.

    `expected_*` are what the engine says. They are the marking key, not
    a claim about what is true of real hardware.
    """
    case_id: str
    condition: str
    app_key: str
    config: Dict
    starting_config: Optional[Dict] = None
    note: str = ""

    @property
    def comparative(self) -> bool:
        return self.starting_config is not None


BASE = dict(memory_devices=2)

CASES: Tuple[StudyCase, ...] = (
    # --- the bottleneck in each place it can be --------------------
    StudyCase(
        "BN-HOST", "bottleneck: host", "industrial_vision",
        dict(cpu="cortex_a53_x4", compute="npu_16x16",
             memory="LPDDR5", preprocessing_mode="cpu_only", **BASE),
        note="a small host doing its own preprocessing"),
    StudyCase(
        "BN-MEM", "bottleneck: shared memory", "industrial_vision",
        dict(cpu="cortex_a53_x4", compute="npu_16x16",
             memory="LPDDR4", preprocessing_mode="isp_assisted",
             **BASE),
        note="preprocessing moved off the host, older memory"),
    StudyCase(
        "BN-ACCEL", "bottleneck: accelerator", "industrial_vision",
        dict(cpu="cortex_a78_x4", compute="npu_16x16",
             memory="LPDDR5", preprocessing_mode="cpu_only", **BASE),
        note="a capable host and a small engine"),
    StudyCase(
        "BN-ISP", "bottleneck: ISP", "industrial_vision",
        dict(cpu="cortex_a53_x4", compute="npu_16x16",
             memory="LPDDR5", preprocessing_mode="isp_assisted",
             **BASE),
        note="preprocessing moved to a fixed-function block"),

    # --- the bottleneck moves --------------------------------------
    StudyCase(
        "MOVE-1", "the bottleneck moves", "industrial_vision",
        dict(cpu="cortex_a78_x4", compute="npu_16x16",
             memory="LPDDR5", preprocessing_mode="cpu_only", **BASE),
        starting_config=dict(
            cpu="cortex_a53_x4", compute="npu_16x16", memory="LPDDR5",
            preprocessing_mode="cpu_only", **BASE),
        note="a larger host: does the limit move, and where to"),

    # --- the cases where a reader is most likely to go wrong -------
    StudyCase(
        "MARGIN-TIGHT", "just inside every requirement",
        "industrial_vision",
        dict(cpu="cortex_a53_x4", compute="npu_16x16",
             memory="LPDDR5", preprocessing_mode="isp_assisted",
             **BASE),
        note="passes, and with little room"),
    StudyCase(
        "MARGIN-WIDE", "far inside every requirement",
        "industrial_vision",
        dict(cpu="server_x86_x32", compute="npu_64x64",
             memory="HBM3E", memory_devices=4,
             preprocessing_mode="isp_and_npu"),
        note="passes everything by a wide margin. The question is "
             "whether a reader still proposes a change"),
    StudyCase(
        "NEAR-IDENTICAL", "two designs that barely differ",
        "industrial_vision",
        dict(cpu="cortex_a78_x4", compute="npu_16x16",
             memory="LPDDR5", memory_devices=2,
             preprocessing_mode="cpu_only"),
        starting_config=dict(
            cpu="cortex_a78_x4", compute="npu_16x16", memory="LPDDR5",
            memory_devices=1, preprocessing_mode="cpu_only"),
        note="one package apart. A reader who reports a large "
             "difference has read the chart and not the figures"),
)


# The questions, fixed so every participant is asked the same thing in
# the same words.
QUESTIONS: Tuple[Tuple[str, str], ...] = (
    ("Q1", "Where is the bottleneck?"),
    ("Q2", "Which module would you improve first?"),
    ("Q3", "Would adding memory help?"),
    ("Q4", "Would a larger accelerator help?"),
    ("Q5", "Which change gives the most for its cost?"),
)


def engine_answer(case: StudyCase) -> Dict:
    """What the engine says, for marking. Computed, never stored.

    Storing an answer would let the marking key drift from the model:
    improving the engine would leave a study marked against the old one.
    """
    from .flow_map import build_flow_map, bottleneck_migration
    from .closure import build_closure
    from .review import build_review
    from .system import SystemConfig

    cur = build_review("education_step_by_step", case.app_key,
                       SystemConfig(**case.config))
    fm = build_flow_map(cur)
    out = {
        "case_id": case.case_id,
        "condition": case.condition,
        "bottleneck": fm.limiting,
        "bottleneck_kind": fm.limiting_kind,
        "utilisations": {m.name: m.utilisation_pct
                         for m in fm.modules},
    }
    if case.comparative:
        ref = build_review("education_step_by_step", case.app_key,
                           SystemConfig(**case.starting_config))
        mig = bottleneck_migration(ref, cur)
        out["bottleneck_before"] = mig.before
        out["bottleneck_moved"] = mig.moved
        out["migration_reason"] = mig.reason
        cl = build_closure(ref, cur, [])
    else:
        cl = build_closure(cur, cur, [])
    out["recommendations"] = [
        {"title": p.title, "priority": p.priority,
         "rules": list(p.origin_rule_ids)}
        for p in cl.next_comparisons]
    out["first_recommendation"] = (cl.next_comparisons[0].title
                                   if cl.next_comparisons else None)
    return out


def verify_cases() -> Tuple[Tuple[str, bool, str], ...]:
    """Does each case produce the condition it claims?

    A stimulus set whose host-limited case is not host-limited marks
    every participant against the wrong answer, and the error is
    invisible once the numbers exist.
    """
    results = []
    for case in CASES:
        try:
            a = engine_answer(case)
        except Exception as exc:
            results.append((case.case_id, False,
                            f"{type(exc).__name__}: {exc}"))
            continue
        want = case.condition
        got = a["bottleneck"]
        if want.startswith("bottleneck: "):
            target = want.split(": ", 1)[1]
            ok = got == target
            why = f"claims {target}, the engine says {got}"
        elif want == "the bottleneck moves":
            ok = bool(a.get("bottleneck_moved"))
            why = (f"{a.get('bottleneck_before')} -> {got}, "
                   f"moved={a.get('bottleneck_moved')}")
        else:
            ok = True
            why = f"limiting element {got}"
        results.append((case.case_id, ok, why))
    return tuple(results)
