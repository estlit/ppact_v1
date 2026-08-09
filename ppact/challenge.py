"""
ppact.challenge - a task with a bar, and a ranking that means something

WHY A RANK NEEDS A POPULATION
=============================
"You scored 78" tells a student nothing. Seventy-eight out of what, against
whom, and was 90 even possible? A score with no population behind it is a
number chosen by whoever wrote the marking scheme, and students learn very
quickly to optimise the scheme rather than the design.

So every challenge here computes its own population: the whole set of designs
reachable from the starting point using the choices the student is allowed to
make. A rank is a position among designs that actually exist and actually
meet the requirements. When a student is told they are in the top 10%, that
is 10% of a real set, and the best possible answer is a design somebody could
have built.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
It does not award points for elegance, effort, or explanation. A tool cannot
judge those and pretending otherwise puts a number on a guess. The instructor
rubric exists for exactly that, and is kept separate.

It also does not hide the targets, weight them secretly, or round a near-miss
up. A requirement is met or it is not; that is what a requirement is.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
import itertools
from dataclasses import dataclass
from typing import Mapping, Dict, List, Optional, Tuple

LINE = "=" * 78

BELOW = "below"
ABOVE = "above"


@dataclass(frozen=True)
class Target:
    metric: str
    direction: str
    value: float
    why: str            # why a product would ask for this


@dataclass(frozen=True)
class Challenge:
    key: str
    title: str
    brief: str          # the situation, in a sentence a student can picture
    application: str
    # THE CONTRACT: a MAPPING of field values, never a SystemConfig.
    #
    # dataclasses.replace() was called on it and raised TypeError on the
    # one path that reaches it - after a student finishes a challenge. Both
    # readings looked reasonable because nothing said which was right.
    #
    # Callers build a config with: SystemConfig(**{**ch.start, **changes})
    # and must not mutate ch.start, which is shared by every attempt.
    start: Mapping[str, object]         # the config they are handed
    targets: Tuple[Target, ...]
    allowed: Dict       # what they may change, and to what
    hint: str = ""


# What a student may change. Kept small on purpose: a search space of a few
# hundred is one a person can reason about, and one where a rank is
# meaningful. Everything else is held, so a comparison stays a comparison.
STANDARD_ALLOWED = {
    "compute": ["npu_16x16", "npu_20x20", "npu_24x24", "npu_32x32",
                "npu_64x64", "npu_128x128"],
    "cpu": ["cortex_a53_x4", "cortex_a78_x4"],
    "preprocessing_mode": ["cpu_only", "isp_assisted", "isp_and_npu"],
    "memory_devices": [1, 2, 4, 8],
    "memory": ["LPDDR5", "GDDR6"],
}


CHALLENGES: Tuple[Challenge, ...] = (

    Challenge(
        "inspection", "The inspection line",
        brief="A camera above a conveyor has to decide pass or fail before "
              "the part reaches the reject arm. The line runs on a shared "
              "supply and the customer has a price in mind.",
        application="industrial_vision",
        start=dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
                   memory_devices=2, preprocessing_mode="cpu_only"),
        targets=(
            Target("Latency (ms)", BELOW, 6.0,
                   "the part is past the arm after this long"),
            Target("System power (W)", BELOW, 3.0,
                   "the cabinet has no fan and a shared supply"),
            Target("System cost (USD)", BELOW, 20.0,
                   "there are forty of these on the line"),
        ),
        allowed=STANDARD_ALLOWED,
        hint="Lesson 5 asked which station is actually in the way.",
    ),

    Challenge(
        "drone", "The inspection drone",
        brief="A drone follows a power line and flags damaged insulators. "
              "It carries its own battery and its own heat.",
        application="drone",
        start=dict(cpu="cortex_a78_x4", compute="npu_24x24", memory="LPDDR5",
                   memory_devices=2, preprocessing_mode="cpu_only"),
        targets=(
            Target("Latency (ms)", BELOW, 12.0,
                   "it has to react while the fault is still in frame"),
            Target("System power (W)", BELOW, 3.0,
                   "every watt is flight time"),
            Target("System cost (USD)", BELOW, 22.0,
                   "these get crashed"),
        ),
        allowed=STANDARD_ALLOWED,
        hint="More engine is not the only lever, and it is rarely the "
             "cheapest one.",
    ),

    Challenge(
        "camera", "The battery camera",
        brief="A doorbell camera wakes on motion, decides whether it is a "
              "person, and goes back to sleep. It runs on cells the owner "
              "changes twice a year.",
        application="smart_camera",
        start=dict(cpu="cortex_a53_x4", compute="npu_16x16", memory="LPDDR5",
                   memory_devices=1, preprocessing_mode="cpu_only"),
        targets=(
            Target("Latency (ms)", BELOW, 8.0,
                   "the visitor has walked away by then"),
            Target("System power (W)", BELOW, 2.0,
                   "the battery has to last the season"),
            Target("System cost (USD)", BELOW, 15.0,
                   "it competes on shelf price"),
        ),
        allowed=STANDARD_ALLOWED,
        hint="An engine that finishes sooner spends less time drawing "
       "power. Check both columns before choosing.",
    ),
)

# --- the rest of the set -----------------------------------------------------
#
# Fifteen in total. Every target was DERIVED rather than chosen: the whole
# option space was evaluated for each application, the deployable designs
# collected, and the thresholds placed so that the design handed over meets
# one or two of three and between 3% and 8% of deployable designs meet all
# three. A bar picked by hand is a bar picked to feel right, and the two are
# not the same.

def _c(key, title, brief, app, start, targets, hint):
    return Challenge(key, title, brief, app, start,
                     tuple(Target(m, BELOW, v, w) for m, v, w in targets),
                     STANDARD_ALLOWED, hint)


MORE_CHALLENGES = (
    _c("drone_endurance", "The endurance drone",
       "A survey drone that has to stay up for a full transect. Weight is "
       "battery and battery is time in the air.",
       "drone",
       dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 12.93, "the fault has to still be in frame"),
        ("System power (W)", 3.14, "every watt is flight time"),
        ("System cost (USD)", 18.22, "these are lost regularly")),
       "The frame is large. Ask what the host is doing with every pixel."),

    _c("drone_quick", "The obstacle drone",
       "A drone flying between trees. It has to see a branch and act before "
       "it arrives, and it starts with an engine too small for the job.",
       "drone",
       dict(cpu="cortex_a78_x4", compute="npu_16x16", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 4.74, "a branch at speed gives you this long"),
        ("System power (W)", 3.14, "still a battery, still flight time"),
        ("System cost (USD)", 18.22, "still crashed into things regularly")),
       "A bigger engine is one lever. It is not the only one, and it is not "
       "free."),

    _c("drone_wide", "The drone that was over-specified",
       "Somebody fitted eight memory packages before asking what the design "
       "was waiting for. It works, and it costs.",
       "drone",
       dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
            memory_devices=8, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 4.74, "unchanged from the obstacle brief"),
        ("System power (W)", 2.81, "the memory is drawing it"),
        ("System cost (USD)", 36.30, "and eight packages cost real money")),
       "Removing something can be the change that helps."),

    _c("robot_arm", "The pick-and-place arm",
       "An arm that has to see a part and close on it before the belt moves "
       "it away. Shared cabinet, shared supply.",
       "robot",
       dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 9.34, "the belt does not wait"),
        ("System power (W)", 3.35, "the cabinet is sealed"),
        ("System cost (USD)", 18.62, "there are twelve arms")),
       "Which station holds most of one job?"),

    _c("robot_small", "The arm with the small engine",
       "The same arm, fitted with the cheapest accelerator on the shelf.",
       "robot",
       dict(cpu="cortex_a78_x4", compute="npu_16x16", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 8.86, "the belt still does not wait"),
        ("System power (W)", 3.12, "the cabinet is still sealed"),
        ("System cost (USD)", 20.37, "and the budget has not moved")),
       "Two of three are already met. Find out which change fixes the third "
       "without losing them."),

    _c("robot_host", "The arm with the modest host",
       "The same arm again, this time with a small host processor.",
       "robot",
       dict(cpu="cortex_a53_x4", compute="npu_32x32", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 8.86, "the belt has not slowed down for you"),
        ("System power (W)", 3.12, "the cabinet is still sealed"),
        ("System cost (USD)", 20.37, "and the budget has not moved")),
       "Lesson 2 asked what the host does before the accelerator sees "
       "anything."),

    _c("camera_shelf", "The camera that has to hit a price",
       "A doorbell camera competing on shelf price against a dozen others "
       "that all claim the same features.",
       "smart_camera",
       dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 4.74, "the visitor walks away"),
        ("System power (W)", 1.56, "cells changed twice a year"),
        ("System cost (USD)", 18.52, "shelf price decides this one")),
       "The cheapest part is not always the cheapest design."),

    _c("camera_modest", "The camera on a small host",
       "The same camera with a modest host processor, which the team chose "
       "to save power.",
       "smart_camera",
       dict(cpu="cortex_a53_x4", compute="npu_32x32", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 4.74, "still a visitor walking away"),
        ("System power (W)", 1.68, "the saving has to be real"),
        ("System cost (USD)", 10.18, "under half the last brief's 18.52")),
       "Saving power on one station can cost more of it on another."),

    _c("camera_big", "The camera with too much engine",
       "Somebody fitted the largest accelerator available to a doorbell.",
       "smart_camera",
       dict(cpu="cortex_a78_x4", compute="npu_128x128", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 4.74, "unchanged from the shelf-price brief"),
        ("System power (W)", 1.56, "the engine is drawing it"),
        ("System cost (USD)", 18.52, "and the die is paying for it")),
       "Going backwards is a legitimate design move."),

    _c("medical_scanner", "The bedside scanner",
       "A handheld ultrasound that flags a finding while the probe is still "
       "on the patient. It is a medical device, so the accuracy requirement "
       "is not negotiable.",
       "medical",
       dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 1.76, "the operator is moving the probe"),
        ("System power (W)", 4.93, "handheld, and it gets warm"),
        ("System cost (USD)", 38.98, "reimbursement sets this")),
       "One requirement here cannot be traded at all. Find it before "
       "spending anything."),

    _c("medical_wide", "The scanner with wide memory",
       "The same scanner, fitted with eight memory packages by a team that "
       "assumed the images were the problem.",
       "medical",
       dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
            memory_devices=8, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 1.76, "unchanged from the bedside brief"),
        ("System power (W)", 4.93, "unchanged from the bedside brief"),
        ("System cost (USD)", 38.98, "and eight packages are not free")),
       "Was the memory ever the thing in the way?"),

    _c("vision_cheap", "The inspection line on a budget",
       "The same inspection line, but the customer has halved the price they "
       "will pay per station.",
       "industrial_vision",
       dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 4.51, "the reject arm has not moved"),
        ("System power (W)", 6.94, "the cabinet can take more than you think"),
        ("System cost (USD)", 12.83, "this is the one that changed")),
       "Which of the three is actually binding?"),

    _c("vision_small", "The inspection line with a small engine",
       "The same line, fitted with the cheapest accelerator, which does not "
       "keep up.",
       "industrial_vision",
       dict(cpu="cortex_a78_x4", compute="npu_16x16", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 3.50, "1 ms tighter than the 4.51 ms brief"),
        ("System power (W)", 6.07, "a real cabinet limit"),
        ("System cost (USD)", 34.07, "and a real budget")),
       "Two are met already. The third needs the station that holds most of "
       "the time."),

    _c("mobile_assistant", "The phone assistant",
       "An on-device assistant that has to answer while the user is still "
       "holding the phone up, on a battery, in a case with no airflow.",
       "mobile_ai",
       dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
            memory_devices=2, preprocessing_mode="cpu_only"),
       (("Latency (ms)", 19.45, "the user is waiting"),
        ("System power (W)", 2.80, "and holding it against their ear"),
        ("System cost (USD)", 36.27, "a phone bill of materials")),
       "This one is memory bound to start with. Check before assuming."),
)

CHALLENGES = CHALLENGES + MORE_CHALLENGES


FINAL_EXAM = Challenge(
    "final", "The final design challenge",
    brief="Everything the course covered, at once. A vision system that has "
          "to be quick, cool, and cheap enough to build forty of. Only four "
          "designs in the allowed set manage all three.",
    application="industrial_vision",
    start=dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
               memory_devices=2, preprocessing_mode="cpu_only"),
    targets=(
        # Tightened at 3.97.0 when the practice set grew to seventeen: the
        # exam has to be harder than most of them, and at 5.0 ms it was not.
        Target("Latency (ms)", BELOW, 4.5,
               "the part is past the reject arm after this long"),
        Target("System power (W)", BELOW, 3.0,
               "a sealed cabinet with no fan"),
        Target("System cost (USD)", BELOW, 25.0,
               "forty units on one line"),
    ),
    allowed={
        "compute": ["npu_16x16", "npu_24x24", "npu_32x32", "npu_64x64",
                    "npu_128x128"],
        "cpu": ["cortex_a53_x4", "cortex_a78_x4"],
        "memory": ["LPDDR5", "GDDR6"],
        "memory_devices": [1, 2, 4],
        "preprocessing_mode": ["cpu_only", "isp_assisted", "isp_and_npu"],
    },
    hint="Every lesson asked the same question in a different form: what is "
         "this design waiting for?",
)


BY_KEY = {c.key: c for c in CHALLENGES}
BY_KEY[FINAL_EXAM.key] = FINAL_EXAM



def _config(ch: Challenge, changes: Optional[Dict] = None):
    from .system import SystemConfig
    merged = dict(ch.start)
    merged.update(changes or {})
    return SystemConfig(**merged)


def meets(ch: Challenge, metrics: Dict) -> List[bool]:
    out = []
    for t in ch.targets:
        got = metrics[t.metric]
        out.append(got < t.value if t.direction == BELOW else got > t.value)
    return out


def population(ch: Challenge) -> Dict:
    """Every design reachable with the allowed choices.

    Computed, not assumed. A rank against an invented curve is a rank against
    nothing, and a student who is told the best possible latency is 4 ms
    should be able to ask which design achieves it and get an answer.
    """
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    app = APPLICATION_LIBRARY[ch.application]
    keys = list(ch.allowed)
    feasible, solutions = [], []
    for combo in itertools.product(*(ch.allowed[k] for k in keys)):
        changes = dict(zip(keys, combo))
        try:
            r = evaluate_system(app, _config(ch, changes))
        except Exception:
            continue
        if "INFEASIBLE" in r.status:
            continue
        met = meets(ch, r.metrics)
        row = {"changes": changes,
               "metrics": {t.metric: r.metrics[t.metric] for t in ch.targets},
               "met": met, "all": all(met)}
        feasible.append(row)
        if all(met):
            solutions.append(row)
    return {"feasible": feasible, "solutions": solutions,
            "total": len(feasible), "solved": len(solutions)}


def score(ch: Challenge, metrics: Dict, pop: Dict) -> Dict:
    """A rank among designs that MEET the requirements, on total margin.

    Only solutions are ranked. A design that misses a requirement is not
    ninetieth out of a hundred - it is not in the race, and telling a student
    otherwise teaches that requirements are a scale.
    """
    met = meets(ch, metrics)
    if not all(met):
        return {"passes": False, "met": met, "rank": None,
                "of": pop["solved"], "margin": None}

    def total_margin(m):
        # how far inside every requirement, as a fraction of the requirement.
        # Equal weight, stated: no target is secretly worth more than another.
        return sum((t.value - m[t.metric]) / t.value for t in ch.targets)

    mine = total_margin(metrics)
    better = sum(1 for s in pop["solutions"]
                 if total_margin(s["metrics"]) > mine)
    return {"passes": True, "met": met, "rank": better + 1,
            "of": pop["solved"], "margin": mine}


def print_challenge(ch: Challenge) -> None:
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    print(f"\n{LINE}")
    print(f" CHALLENGE  {ch.title}")
    print(LINE)
    for line in _wrap(ch.brief, 72):
        print(f"  {line}")
    print()
    print(f"  What has to be true:")
    for t in ch.targets:
        print(f"    {t.metric:<22s}{t.direction} {t.value:g}")
        for line in _wrap(t.why, 62):
            print(f"        {line}")

    r = evaluate_system(APPLICATION_LIBRARY[ch.application], _config(ch))
    met = meets(ch, r.metrics)
    print(f"\n  The design you are handed:")
    for t, ok in zip(ch.targets, met):
        print(f"    {t.metric:<22s}{r.metrics[t.metric]:>10.2f}   "
              f"{'meets it' if ok else 'DOES NOT'}")
    print(f"\n  {sum(met)} of {len(met)} met.")

    print(f"\n  What you may change:")
    from .questions import field_display_name, field_option_labels
    for k, vals in ch.allowed.items():
        # Labelled option names are longer than raw values, so the line
        # that fitted before now runs past 78 columns. Wrapped under the
        # field name rather than truncated: a list of what you MAY change
        # is not useful with items missing from it.
        shown = field_option_labels(k, vals[:3])
        more = f"  (+{len(vals) - 3} more)" if len(vals) > 3 else ""
        print(f"    {field_display_name(k)}")
        for line in _wrap(shown + more, 66):
            print(f"      {line}")
    if ch.hint:
        print()
        for line in _wrap(ch.hint, 72):
            print(f"  {line}")
    print(LINE)


def print_result(ch: Challenge, changes: Dict, pop: Optional[Dict] = None
                 ) -> Dict:
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    pop = pop or population(ch)
    r = evaluate_system(APPLICATION_LIBRARY[ch.application],
                        _config(ch, changes))
    sc = score(ch, r.metrics, pop)

    print(f"\n{LINE}")
    print(f" RESULT  {ch.title}")
    print(LINE)
    print(f"  You changed:")
    for k, v in changes.items():
        print(f"    {k:<22s}{ch.start.get(k)} -> {v}")
    if not changes:
        print(f"    nothing")

    print()
    for t, ok in zip(ch.targets, sc["met"]):
        got = r.metrics[t.metric]
        slack = (t.value - got) / t.value * 100
        print(f"  {t.metric:<22s}{got:>10.2f}  against {t.value:<8g}"
              f"{'PASS' if ok else 'FAIL':>6s}  {slack:+6.1f}%")

    print()
    if sc["passes"]:
        print(f"  PASS - every requirement met.")
        print(f"  Ranked {sc['rank']} of {sc['of']} designs that also meet "
              f"them,")
        print(f"  out of {pop['total']} that were possible at all.")
        print(f"\n  The rank is on total margin, every requirement weighted")
        print(f"  the same. That is a choice, and it is stated rather than")
        print(f"  buried: a design that is barely inside all three ranks")
        print(f"  below one that is comfortably inside all three.")
    else:
        missed = [t.metric for t, ok in zip(ch.targets, sc["met"]) if not ok]
        print(f"  FAIL - {', '.join(missed)} not met.")
        print(f"\n  Not ranked. A design that misses a requirement is not")
        print(f"  last; it is not in the race. {pop['solved']} designs in the")
        print(f"  allowed set do meet all three, so this is achievable.")
    print(LINE)
    return sc


def print_best(ch: Challenge, pop: Optional[Dict] = None, show: int = 3
               ) -> None:
    """What the best answers look like. Shown AFTER an attempt, not before."""
    pop = pop or population(ch)
    if not pop["solutions"]:
        print("\n  No design in the allowed set meets every requirement.")
        return

    def total_margin(m):
        return sum((t.value - m[t.metric]) / t.value for t in ch.targets)

    best = sorted(pop["solutions"],
                  key=lambda s: total_margin(s["metrics"]), reverse=True)
    print(f"\n{LINE}")
    print(f" WHAT THE BEST ANSWERS LOOK LIKE")
    print(LINE)
    for i, s in enumerate(best[:show], 1):
        diffs = {k: v for k, v in s["changes"].items()
                 if v != ch.start.get(k)}
        desc = (", ".join(f"{k}={v}" for k, v in diffs.items())
                or "the design as handed over")
        wrapped = _wrap(desc, 70)
        print(f"  {i}. {wrapped[0]}")
        for extra in wrapped[1:]:
            print(f"     {extra}")
        for t in ch.targets:
            print(f"       {t.metric:<22s}{s['metrics'][t.metric]:>10.2f}")
        print()
    print(f"  {pop['solved']} of {pop['total']} possible designs meet every")
    print(f"  requirement. If your answer is not among these, it is worth")
    print(f"  asking what they gave up that you did not, and whether that")
    print(f"  trade would survive a real customer.")
    print(LINE)


def _wrap(text: str, width: int) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def challenge_violations() -> List[str]:
    """A challenge must be winnable, and must not be won already."""
    problems = []
    for ch in CHALLENGES:
        from .application import APPLICATION_LIBRARY
        from .system import evaluate_system
        r = evaluate_system(APPLICATION_LIBRARY[ch.application], _config(ch))
        met = sum(meets(ch, r.metrics))
        if met == len(ch.targets):
            problems.append(
                f"{ch.key}: the starting design already meets everything - "
                f"there is nothing to do")
        if met == 0:
            problems.append(
                f"{ch.key}: the starting design meets nothing - a student "
                f"with no foothold stops")
        pop = population(ch)
        if pop["solved"] == 0:
            problems.append(f"{ch.key}: no allowed design meets the targets")
        elif pop["solved"] > pop["total"] * 0.5:
            problems.append(
                f"{ch.key}: {pop['solved']} of {pop['total']} designs pass - "
                f"a bar most things clear is not a bar")
        for t in ch.targets:
            if not t.why:
                problems.append(
                    f"{ch.key}/{t.metric}: no reason given. A number with no "
                    f"reason behind it is a number a student games")
    return problems


def main(ask_fn):
    """The challenge list. Returns what was submitted.

    SINGLE, BECAUSE THE REGISTRY SAYS SO.

    The challenge hands the reader a design that does not quite do the
    job and asks them to change it, which reads like a comparison. The
    engine's workflow registry declares `challenge` single-design, and
    it refuses a starting configuration:

        'challenge' is a single-design workflow and was given a
        starting configuration. A single analysis does not silently
        become a comparison.

    That refusal is the engine's decision about what this workflow
    means, and it outranks a reading of the screen. Making it a
    comparison is a registry change, not a UI change, and is recorded as
    an open question rather than worked around here.

    Marking is separate from analysis: a design can be analysed whether
    or not it clears the bar, and the score travels as a note rather
    than as the status.
    """
    from .menu import ask

    while True:
        print(f"\n{LINE}")
        print(f" CHALLENGES")
        print(LINE)
        print(f"  Each one hands you a working design that does not quite do")
        print(f"  the job, and a list of what has to be true.\n")
        labels = [c.title for c in CHALLENGES] + ["Back"]
        pick = ask_fn("Which challenge", labels, 1)
        if pick > len(CHALLENGES):
            return
        ch = CHALLENGES[pick - 1]
        print_challenge(ch)

        changes = {}
        # Through the registry. Both the field name and the option labels
        # come from the question that already governs that field, so the
        # student sees "Memory Unit Count" and "4 packages" rather than
        # "memory_devices" and "4".
        from .questions import field_question, ask_question
        for field_name, options in ch.allowed.items():
            print()
            current = ch.start.get(field_name)
            chosen = ask_question(
                field_question(field_name, options, current))
            if chosen != "__keep__" and chosen != current:
                changes[field_name] = chosen

        print("\n  Working out how your design compares...")
        pop = population(ch)
        print_result(ch, changes, pop)
        # The challenge score is a marking device. The engineering result
        # is the standard review, and a student who met a target without
        # seeing why has learned to hit a number.
        # ch.start is a DICT of field values, not a SystemConfig.
        # dataclasses.replace() was called on it and raised TypeError on
        # the one path that reaches it - after a student has finished a
        # challenge, which is the worst moment available.
        from .system import SystemConfig
        from .review import build_review, render_standard_engineering_review
        final = dict(ch.start)
        final.update(changes)
        start_cfg = SystemConfig(**ch.start)
        final_cfg = SystemConfig(**final)
        if ask_fn("Show the best answers", ["Yes", "No"], 2) == 1:
            print_best(ch, pop)
        from .outcome import single as _cs, SelectedAnswer as _CA
        from .present import present as _present
        # MARKING IS NOT THE STATUS. A design is analysed whether or not
        # it clears the bar, so the score travels as a note.
        _out = _cs(
            "challenge", ch.application, final_cfg,
            (_CA(1, "Challenge", ch.title),
             _CA(2, "Changes",
                 ", ".join(f"{k}={v}" for k, v in changes.items())
                 or "none")),
            note=f"challenge: {ch.title}; started from {start_cfg}")
        _present(_out)
        return _out
