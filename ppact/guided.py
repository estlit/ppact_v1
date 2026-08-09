"""
ppact.guided - think first, then read

WHY THE QUESTIONS COME FIRST
============================
A student who reads a result agrees with it. Agreement costs nothing and
changes nothing. A student who commits to an answer and turns out to be
wrong has learned something, and that requires being asked before being
told.

The lessons already work this way. This applies the same shape to a design
COMPARISON, which is the thing a student will actually do after the course:

    question  ->  their own thinking  ->  answer  ->  reason  ->  takeaway

EVERY QUESTION AND EVERY ANSWER IS DERIVED
------------------------------------------
Nothing here is a stored sentence. Each question is generated from the two
designs being compared, and each answer is computed from the same engine
that produced the numbers on screen. A canned question whose answer the
model cannot actually produce would be worse than no question at all: the
student would learn to distrust the one part of the tool that was asking
them to think.

That has a consequence worth stating: a question is only asked when it has
an answer. If a comparison has no budget problem, the budget question is not
asked - rather than asked and answered "no", which teaches a student to
expect the answer to be no.

MODES DIFFER, AND THEY DIFFER FOR A REASON
------------------------------------------
    Education   ask, wait, reveal, explain, one takeaway
    Challenge   ask, take an answer, do NOT reveal - the whole point of a
                challenge is that the student commits first and is marked
    Research    no questions; the analysis directly, because a researcher
                did not come here to be taught
    Validation  no questions and no analysis; pass or fail

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

LINE = "=" * 78
RULE = "-" * 78


@dataclass(frozen=True)
class Question:
    key: str
    text: str
    answer: str
    evidence: str          # the figures the answer rests on


def _wrap(text: str, width: int) -> List[str]:
    from .visual import wrap_text
    return wrap_text(text, width)


# ==============================================================================
# Deriving the questions
# ==============================================================================

def build_questions(app_key: str, before_cfg, after_cfg) -> List[Question]:
    """Ask only what this comparison can answer.

    Each entry checks whether it HAS an answer before adding itself. A
    question asked out of habit and answered "no" teaches a student that the
    answer is usually no.
    """
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    from .decide import headroom, upgrade_ranking, BOTTLENECK_PLAIN

    app = APPLICATION_LIBRARY[app_key]
    ra = evaluate_system(app, before_cfg)
    rb = evaluate_system(app, after_cfg)
    a, b = ra.metrics, rb.metrics
    out: List[Question] = []

    # 1. which is quicker - always answerable when both are feasible
    if "INFEASIBLE" not in ra.status and "INFEASIBLE" not in rb.status:
        la, lb = a["Latency (ms)"], b["Latency (ms)"]
        if abs(lb - la) < 1e-9:
            verdict = "Neither. Single-job latency is unchanged."
        else:
            quicker = "The second design" if lb < la else "The FIRST design"
            verdict = (f"{quicker}. Single-job latency "
                       f"{'improved' if lb < la else 'got worse'} from "
                       f"{la:.2f} ms to {lb:.2f} ms "
                       f"({(lb / la - 1) * 100:+.1f}%).")
        out.append(Question(
            "quicker", "Which design has the lower single-job latency?",
            verdict, f"{la:.3f} ms against {lb:.3f} ms"))

    # 2. the bottleneck - always answerable for a feasible design
    if "INFEASIBLE" not in rb.status:
        hr = headroom(b)
        if hr:
            top = hr[0]
            plain = BOTTLENECK_PLAIN.get(rb.bound_by, "")
            out.append(Question(
                "bottleneck", "What holds most of the time now?",
                f"{top.station.capitalize()}, at {top.share_pct:.1f}% of one "
                f"job. The engine's own limit is {rb.bound_by}"
                + (f" - {plain}." if plain else "."),
                f"{top.station} {top.share_pct:.1f}%, limit {rb.bound_by}"))

    # 3. what to improve next - only when a station clearly dominates
    ranking = upgrade_ranking(b, rb.bound_by)
    if ranking and ranking[0][1] >= 40.0:
        name, share, why = ranking[0]
        rest = 100.0 - share
        out.append(Question(
            "next", "Which part should be improved next, and why?",
            f"{name}. It holds {share:.1f}% of one job, so everything else "
            f"together cannot save more than {rest:.1f}% however much is "
            f"spent on it.",
            f"{name} {share:.1f}%, everything else {rest:.1f}%"))

    # 4. budget - ONLY if there is one to talk about
    failed = sorted(g for g, ok in rb.gate.items() if not ok)
    if failed:
        detail = []
        if "cost" in failed:
            detail.append(f"system cost {b['System cost (USD)']:.2f} USD "
                          f"against a budget of {app.bom_budget_usd:.0f}")
        if "power" in failed:
            detail.append(f"system power {b['System power (W)']:.2f} W "
                          f"against {app.power_budget_w:.0f}")
        out.append(Question(
            "budget", "Does this design meet every requirement?",
            f"No. It fails {', '.join(failed)}."
            + (f" {'; '.join(detail)}." if detail else ""),
            ", ".join(failed)))
    elif ra.passes and rb.passes:
        # both deploy: worth asking, because the answer is not always yes
        out.append(Question(
            "budget", "Does this design meet every requirement?",
            "Yes. Latency, throughput, power, cost, thermal, cooling class "
            "and capacity are all satisfied.",
            "no unmet gate"))

    # 5. what the balance chart adds - only when it adds something
    from .visual import build_balance, overlapping_axes
    bal = build_balance(app_key, [("Starting point", before_cfg),
                                  ("Current design", after_cfg)])
    same = overlapping_axes(bal)
    names = bal.axis_names()
    if len(same) < len(names):
        moved = [n for n in names if n not in same]
        out.append(Question(
            "balance",
            "What does the balance chart add that the numbers do not?",
            f"That the change was UNEVEN across the design. It moved "
            f"{', '.join(moved)} and left {', '.join(same) or 'nothing'} "
            f"where it was. The chart shows that spread at a glance; it "
            f"does not show any physical value.",
            f"moved: {', '.join(moved)}"))
    return out


# ==============================================================================
# The key takeaway
# ==============================================================================

def key_takeaway(app_key: str, before_cfg, after_cfg) -> str:
    """One or two sentences that are TRUE OF THIS COMPARISON.

    Assembled from the figures rather than chosen from a list. A takeaway
    that could be printed under any comparison is a slogan, and a student
    who meets three of those stops reading the last line.
    """
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    from .decide import headroom

    app = APPLICATION_LIBRARY[app_key]
    ra = evaluate_system(app, before_cfg)
    rb = evaluate_system(app, after_cfg)
    if "INFEASIBLE" in rb.status:
        # A takeaway with no figure in it is a sentence, not a finding. The
        # deficit IS available here and is the whole point: the reader needs
        # to know how far short the memory falls, not merely that it does.
        have = rb.metrics.get("Memory capacity (GB)")
        need = (app.weight_bytes + app.kv_cache_bytes
                + app.runtime_overhead_bytes) / 1e9
        detail = ""
        if have is not None:
            detail = (f" The model needs about {need:.1f} GB and this "
                      f"memory holds {have:.1f} GB.")
        return ("The changed design cannot hold its model in memory, so it "
                "has no timing to compare." + detail
                + " Capacity is not a lesser degree of performance - a "
                  "design that cannot hold its weights has no latency at "
                  "all.")

    a, b = ra.metrics, rb.metrics
    la, lb = a["Latency (ms)"], b["Latency (ms)"]
    gain = (1 - lb / la) * 100 if la else 0.0
    cost_delta = b["System cost (USD)"] - a["System cost (USD)"]
    hr = headroom(b)
    top = hr[0] if hr else None
    failed = sorted(g for g, ok in rb.gate.items() if not ok)

    parts: List[str] = []
    if abs(gain) < 1.0:
        parts.append(f"The change moved single-job latency by "
                     f"{gain:+.1f}%, which is nothing")
    else:
        parts.append(f"Single-job latency {'fell' if gain > 0 else 'rose'} "
                     f"{abs(gain):.1f}%")
    if cost_delta > 0.01:
        parts[-1] += f" for {cost_delta:+.2f} USD"
    sentence = parts[0] + "."

    if top is not None:
        was = headroom(a)
        was_top = was[0].station if was else None
        if was_top and was_top != top.station:
            sentence += (f" The limit moved: {was_top} used to hold most of "
                         f"the time and {top.station} now does, at "
                         f"{top.share_pct:.1f}%.")
        else:
            sentence += (f" {top.station.capitalize()} still holds most of "
                         f"the time, at {top.share_pct:.1f}%, so that is "
                         f"where the next change belongs.")
    if failed:
        sentence += (f" It does not deploy: {', '.join(failed)} unmet.")
    return sentence


# ==============================================================================
# The screens
# ==============================================================================

def print_think_first(questions: Sequence[Question]) -> None:
    """The questions, with NO answers on the page."""
    print(f"\n{RULE}")
    print(" THINK BEFORE READING")
    print(RULE)
    print("  Answer these to yourself before going on. A prediction that")
    print("  turns out wrong is the only thing that reliably changes a")
    print("  mind, and it has to be made before the answer is visible.\n")
    for i, q in enumerate(questions, 1):
        for j, line in enumerate(_wrap(q.text, 70)):
            print(f"  {str(i) + '.' if j == 0 else '  ':<4s}{line}")
        print()


def print_answers(questions: Sequence[Question]) -> None:
    print(f"\n{RULE}")
    print(" EXPLANATION")
    print(RULE)
    for i, q in enumerate(questions, 1):
        print(f"\n  Q{i}  {q.text}")
        for line in _wrap(q.answer, 68):
            print(f"      {line}")
        print(f"      [{q.evidence}]")


def print_takeaway(text: str) -> None:
    print(f"\n{RULE}")
    print(" KEY TAKEAWAY")
    print(RULE)
    for line in _wrap(text, 70):
        print(f"  {line}")
    print(RULE)


def guided_comparison(app_key: str, before_cfg, after_cfg, ask_fn=None,
                      mode: str = "education") -> Dict:
    """The whole flow, differing by mode.

    education   ask, wait, reveal, explain, takeaway
    challenge   ask, take an answer, do NOT reveal
    research    no questions; the analysis directly
    validation  neither
    """
    from .decide import explain
    from .visual import build_balance, print_balance

    questions = build_questions(app_key, before_cfg, after_cfg)

    if mode == "validation":
        from .application import APPLICATION_LIBRARY
        from .system import evaluate_system
        r = evaluate_system(APPLICATION_LIBRARY[app_key], after_cfg)
        failed = sorted(g for g, ok in r.gate.items() if not ok)
        print(f"\n  {'PASS' if r.passes else 'FAIL'}"
              + (f"   unmet: {', '.join(failed)}" if failed else ""))
        return {"mode": mode, "questions": [], "revealed": False}

    if mode == "research":
        _standard(app_key, before_cfg, after_cfg)
        return {"mode": mode, "questions": [], "revealed": False}

    print_think_first(questions)

    if mode == "challenge":
        # The answers are NOT shown. A challenge whose answers appear before
        # submission is a worked example with a delay.
        print(f"  Write your answers down and submit them. They are not")
        print(f"  shown here - a challenge that reveals the answer first is")
        print(f"  a worked example with a pause in it.")
        return {"mode": mode, "questions": questions, "revealed": False}

    if ask_fn is not None:
        from .menu import ask_nav
        ask_nav("Ready",
                "Continue when you have made your prediction.",
                ["Show the explanation"], 1)

    print_answers(questions)
    _standard(app_key, before_cfg, after_cfg)
    return {"mode": mode, "questions": questions, "revealed": True}


def _standard(app_key, before_cfg, after_cfg) -> None:
    """One exit point.

    This flow used to assemble its own report - explain, then a balance
    chart, then a takeaway - and it was the ONLY path that included the
    balance chart at all. Assembling here is what let seven other paths
    quietly omit it.
    """
    from .review import build_review, render_standard_engineering_review

    # The common report is produced by `present(outcome)` in the task
    # that called this. Rendering here too printed it twice.
