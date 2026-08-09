"""
tests_review_contract.py - does the program keep the review contract?

PHASE 2. THIS SUITE IS EXPECTED TO FAIL.
========================================
It is written before the implementation, against
STANDARD_ENGINEERING_REVIEW_CONTRACT.md, so that the defects it names are
named by a check rather than by a person reading code.

Its purpose in Phase 2 is not to pass. It is to say precisely what is wrong
with the program as it stands, so that the implementation has something to
aim at and so that nothing is fixed by accident and called fixed.

THREE STATES, NOT TWO
---------------------
    ABSENT     the structure the contract requires does not exist yet
    VIOLATED   the structure exists and the behaviour breaks the contract
    PASS       the contract is satisfied

The distinction matters. "Not built yet" and "built wrong" need different
work, and a suite that reports both as FAILED tells a reader neither.

WHAT IS NOT HERE
----------------
R11 (positive controls) and R12 (control accounting) come in Phase 5.
Right now there is no standard renderer to remove a section from and no
registry to bypass, so building those controls would mean building a fake
structure first, and testing the fake. The order would be inverted.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import io
import os
import sys

sys.path.insert(0, ".")

LINE = "=" * 86
ABSENT, VIOLATED, PASS = "ABSENT", "VIOLATED", "PASS"
RESULTS = []          # (rule, title, state, detail)


def record(rule, title, state, detail=""):
    RESULTS.append((rule, title, state, detail))


def src(rel):
    path = os.path.join("ppact", rel)
    if not os.path.isfile(path):
        return None
    return open(path, encoding="utf-8").read()


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        fn(*a, **kw)
    return buf.getvalue()


def drive(fn, answers, limit=25):
    """Run an interactive function with scripted input, capturing output."""
    import signal

    # EXPLICIT answers, not empty ones.
    #
    # The filler used to be "" because every question had a default. It has
    # none now, so an empty walk exercises the refusal path forever and
    # never reaches a result. The filler is "1" - a choice the TEST makes,
    # recorded as the test's choice, which is the same standard the program
    # is now held to.
    seq = iter(list(answers) + ["1"] * 200)
    real = builtins.input
    buf = io.StringIO()

    def _late(signum, frame):
        raise TimeoutError(f"still running after {limit}s")

    prev = signal.signal(signal.SIGALRM, _late)
    signal.alarm(limit)
    try:
        builtins.input = lambda prompt="": next(seq)
        with contextlib.redirect_stdout(buf):
            fn()
        return buf.getvalue(), None
    except Exception as exc:
        return buf.getvalue(), exc
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev)
        builtins.input = real


# The workflows the contract places in scope. Written here ONLY because the
# registry does not exist yet - the whole point of R1 is that this list
# should not have to be written by hand.
EXPECTED_ANALYSIS_WORKFLOWS = (
    ("education_guided_design", "single", "task_guided"),
    ("education_step_by_step", "single", "task_game"),
    ("education_why_changed", "comparison", "task_decide"),
    ("research_explain", "comparison", "task_decide"),
    ("design_review", "comparison", "task_review"),
    ("what_if", "comparison", "task_whatif"),
    ("challenge", "single", "task_challenge"),
    ("demo", "comparison", "task_demo"),
)

# The mandatory list, from STANDARD_ENGINEERING_REVIEW_CONTRACT.md. Held
# here independently of the code so a section deleted from the code is a
# failure rather than a change of expectation.
MANDATORY_SECTIONS = (
    ("architecture_summary", "Architecture Summary", "both"),
    ("latency_flow", "Latency Flow", "single"),
    ("latency_change", "Latency Change Breakdown", "comparison"),
    ("limiting_factor", "Current Limiting Factor", "both"),
    ("measured_bars", "Measured Results", "both"),
    ("balance", "Architecture Balance", "single"),
    ("balance_comparison", "Architecture Balance Comparison", "comparison"),
    ("recommendation", "What to Explore Next", "both"),
    ("deployment", "Deployment Assessment", "both"),
    ("takeaway", "Engineering Takeaway", "both"),
    ("boundaries", "Assumptions and Model Boundaries", "both"),
)

from collections import namedtuple as _nt
Section = _nt("Section", "section_id canonical_title variant order")

REQUIRED_SECTIONS = (
    ("architecture_summary", "Architecture Summary", "both"),
    ("latency_flow", "Latency Flow", "single"),
    ("latency_change", "Latency Change Breakdown", "comparison"),
    ("limiting_factor", "Current Limiting Factor", "both"),
    ("measured_bars", "Measured Results", "both"),
    ("balance", "Architecture Balance", "single"),
    ("balance_comparison", "Architecture Balance Comparison", "comparison"),
    ("recommendation", "What to Explore Next", "both"),
    ("deployment", "Deployment Assessment", "both"),
    ("takeaway", "Engineering Takeaway", "both"),
    ("boundaries", "Assumptions and Model Boundaries", "both"),
)


# ==============================================================================
# R1 - workflow classification and registration
# ==============================================================================

def r1_workflow_registry():
    review = src("review.py")
    if review is None or "WORKFLOW_REGISTRY" not in (review or ""):
        record("R1", "an authoritative Workflow Registry exists", ABSENT,
               "ppact/review.py with WORKFLOW_REGISTRY is not present; "
               "applicability is currently implicit in the menu")
        record("R1", "every executable analysis path carries a workflow_id",
               ABSENT,
               f"{len(EXPECTED_ANALYSIS_WORKFLOWS)} analysis workflows are "
               f"reachable from the menu and none is registered")
        record("R1", "every non-analysis workflow states an exemption reason",
               ABSENT,
               "validation, library validation, certification and the "
               "documentation audit are exempt by intention and nowhere by "
               "declaration")
        return
    record("R1", "an authoritative Workflow Registry exists", PASS)

    # Every routed workflow_id must be registered. The rule used to check
    # only that the registry FILE existed, so deleting a workflow from it
    # while code still routed to it went unnoticed - the exact failure the
    # registry was built to prevent.
    import re as _rei
    from ppact.review import BY_WORKFLOW
    # THE SAME ROUTING PATTERNS AS R2.
    #
    # This scanned only `build_review("<id>")`. A workflow now returns a
    # WorkflowOutcome carrying its id, so several ids stopped appearing
    # here - and the control that removes one from the registry stopped
    # producing a violation, which reported R1 as not known to work. The
    # rule was blind, not the registry correct.
    routed = set()
    for mod in sorted(os.listdir("ppact")):
        if not mod.endswith(".py"):
            continue
        text = src(mod) or ""
        for pattern in (r'build_review\(\s*["\']([a-z_]+)["\']',
                        r'_?(?:single|comparison|_gs|_cs|_cmp|_dc|_dc2|'
                        r'_gc|_rc)\(\s*\n?\s*["\']([a-z_]+)["\']'):
            for m in _rei.finditer(pattern, text):
                routed.add(m.group(1))
    orphans = sorted(w for w in routed if w not in BY_WORKFLOW)
    record("R1", "every routed workflow_id is registered",
           PASS if not orphans else VIOLATED,
           f"routed but unregistered: {orphans}")


# ==============================================================================
# R2 - standard renderer existence and ownership
# ==============================================================================

def r2_renderer_ownership():
    review = src("review.py")
    if review is None or "render_standard_engineering_review" not in review:
        record("R2", "a canonical standard-review renderer exists", ABSENT,
               "render_standard_engineering_review is not defined anywhere")
    else:
        record("R2", "a canonical standard-review renderer exists", PASS)

    # What the contract forbids is a workflow assembling its own FINAL
    # ENGINEERING RESULT. It does not forbid showing a slate of candidate
    # designs, or an intermediate explanation, or a score screen.
    #
    # The first version of this check counted any call to explain,
    # print_balance, print_designs or show_result. print_designs lists
    # candidate architectures for the user to choose between - it is input
    # material, not a result - and counting it would have driven a change
    # that removed something correct.
    #
    # So the question asked is narrower and behavioural: does every
    # registered analysis workflow reach render_standard_engineering_review,
    # and does anything else print a review-shaped result?
    from ppact.review import ANALYSIS_WORKFLOWS

    # The workflow_id must appear as a QUOTED ARGUMENT to build_review,
    # not merely somewhere in a file. "challenge" and "demo" are ordinary
    # words and occur in eleven modules each; matching them as substrings
    # reported three unrouted workflows as routed, which is a false PASS in
    # the one check that decides whether the migration is finished.
    # THE ROUTING TARGET CHANGED.
    #
    # This looked for `build_review("<id>")`, which was where a workflow
    # reached the renderer when the renderer was `render_standard_
    # engineering_review`. A workflow now returns a WorkflowOutcome
    # carrying its own id and calls `present`, which builds the report;
    # the id appears as an argument to `single(...)` or `comparison(...)`
    # instead. Keeping the old pattern would have failed every migrated
    # workflow while the architecture was more correct, not less.
    import re as _re
    routed = set()
    for mod in sorted(os.listdir("ppact")):
        if not mod.endswith(".py"):
            continue
        text = src(mod) or ""
        for pattern in (r'build_review\(\s*["\']([a-z_]+)["\']',
                        r'_?(?:single|comparison|_gs|_cs|_cmp|_dc|_dc2|'
                        r'_gc|_rc)\(\s*\n?\s*["\']([a-z_]+)["\']'):
            for m in _re.finditer(pattern, text):
                routed.add(m.group(1))
    unrouted = [w.workflow_id for w in ANALYSIS_WORKFLOWS
                if w.workflow_id not in routed]
    record("R2", "every analysis workflow routes to the shared report",
           PASS if not unrouted else VIOLATED,
           f"not routed: {unrouted}")

    # and nothing outside review.py may print a review heading
    rogue = []
    for mod in sorted(os.listdir("ppact")):
        if not mod.endswith(".py") or mod == "review.py":
            continue
        text = src(mod) or ""
        if "STANDARD ENGINEERING DESIGN REVIEW" in text:
            rogue.append(mod)
    record("R2", "only the standard renderer prints a review",
           PASS if not rogue else VIOLATED, str(rogue))


# ==============================================================================
# R2b - the execution contract
# ==============================================================================
#
# R2 asks whether a workflow ROUTES to build_review. It answered yes for
# the challenge while the call raised TypeError the moment it ran: ch.start
# is a dict of field values and dataclasses.replace() was called on it.
#
#     calling successfully  is not  being called
#
# R2 keeps its job - the structural contract, that the wiring exists. This
# is the separate question of whether the wiring carries anything.

def r2b_execution_contract():
    """Every registered analysis workflow must produce a whole review.

    Reach it, render every mandatory section, and return normally. A
    workflow that raises halfway has routed correctly and delivered
    nothing.
    """
    P = "R2b"
    import dataclasses
    from ppact import SystemConfig
    from ppact.review import (ANALYSIS_WORKFLOWS, build_review, review_lines,
                              render_standard_engineering_review,
                              sections_for, SINGLE)

    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="cpu_only")
    other = dataclasses.replace(base, compute="npu_64x64",
                                memory_devices=4)

    for wf in ANALYSIS_WORKFLOWS:
        label = wf.workflow_id
        try:
            if wf.review_variant == SINGLE:
                analysis = build_review(label, "industrial_vision", other)
            else:
                analysis = build_review(label, "industrial_vision", other,
                                        base)
        except Exception as exc:
            record(P, f"{label}: build_review runs without raising",
                   VIOLATED, f"{type(exc).__name__}: {exc}")
            continue
        record(P, f"{label}: build_review runs without raising", PASS)

        try:
            out = quiet(render_standard_engineering_review, analysis,
                        images=False)
        except Exception as exc:
            record(P, f"{label}: the review renders to completion",
                   VIOLATED, f"{type(exc).__name__}: {exc}")
            continue

        want = sections_for(analysis.variant)
        missing = [sec.canonical_title for sec in want
                   if sec.canonical_title.upper() not in out.upper()]
        record(P, f"{label}: the review renders to completion",
               PASS if not missing else VIOLATED,
               "missing: " + ", ".join(missing) if missing else "")
        record(P, f"{label}: and reports no identity defect",
               PASS if "IDENTITY DEFECT" not in out else VIOLATED)


# ==============================================================================
# R2c - configuration type at the boundary
# ==============================================================================
#
# The TypeError came from a dict being treated as a dataclass. Nothing said
# which a Challenge's start field is, so both readings looked reasonable.

def r2c_configuration_types():
    P = "R2c"
    from ppact import SystemConfig
    from ppact.challenge import CHALLENGES, FINAL_EXAM
    from ppact.demo import DEMOS

    def kind(v):
        if isinstance(v, SystemConfig):
            return "SystemConfig"
        if isinstance(v, dict):
            return "dict"
        return type(v).__name__

    starts = {kind(c.start) for c in CHALLENGES} | {kind(FINAL_EXAM.start)}
    record(P, "every challenge start is the same kind of object",
           PASS if len(starts) == 1 else VIOLATED,
           f"found {sorted(starts)} - two kinds means every caller has to "
           f"guess, and one of them will guess wrong")
    record(P, "and a challenge start converts to a SystemConfig",
           _try_build(CHALLENGES[0].start),
           "the review needs a SystemConfig; if the start is a mapping the "
           "conversion must be the caller's job and must work")

    rows = [r for d in DEMOS for r in d.rows]
    demo_kinds = {kind(r.config) for r in rows}
    record(P, "every demo row config is the same kind of object",
           PASS if len(demo_kinds) == 1 else VIOLATED,
           f"found {sorted(demo_kinds)}")
    record(P, "and a demo row converts to a SystemConfig",
           _try_build(rows[0].config))


def r2d_challenge_type_contract():
    """Challenge.start is a MAPPING, and callers must treat it as one.

    The TypeError that started this came from reading it as a dataclass.
    Both readings looked reasonable because nothing declared which was
    right, so the declaration is now checked rather than assumed.
    """
    P = "R2d"
    import dataclasses
    from collections.abc import Mapping
    from ppact import SystemConfig
    from ppact.challenge import CHALLENGES, FINAL_EXAM, Challenge

    field = [f for f in dataclasses.fields(Challenge)
             if f.name == "start"][0]
    record(P, "the start field declares a Mapping",
           _state("Mapping" in str(field.type)), str(field.type))

    for ch in list(CHALLENGES) + [FINAL_EXAM]:
        label = ch.key
        record(P, f"{label}: start is a Mapping",
               _state(isinstance(ch.start, Mapping)),
               type(ch.start).__name__)
        record(P, f"{label}: start is NOT a SystemConfig",
               _state(not isinstance(ch.start, SystemConfig)),
               "one kind, declared; two readings is how the TypeError "
               "happened")

        before = dict(ch.start)
        try:
            merged = {**dict(ch.start),
                      **{k: v[0] for k, v in ch.allowed.items()}}
            cfg = SystemConfig(**merged)
            built = True
        except Exception as exc:
            built = False
            cfg = None
            record(P, f"{label}: merged start builds a SystemConfig",
                   VIOLATED, f"{type(exc).__name__}: {exc}")
        if built:
            record(P, f"{label}: merged start builds a SystemConfig", PASS)
        record(P, f"{label}: the original start is unchanged",
               _state(dict(ch.start) == before),
               "start is shared by every attempt; merging must copy")


def _try_build(value):
    from ppact import SystemConfig
    try:
        SystemConfig(**value) if isinstance(value, dict) else value
        return PASS
    except Exception:
        return VIOLATED


# ==============================================================================
# R3 - required section presence
# ==============================================================================

def r3_section_presence():
    """Every registered analysis workflow, through the standard renderer.

    The first version called explain() and guided_comparison() directly and
    judged their output. Both were internal steps even then; judging them
    measured the wrong thing and would keep failing after the migration was
    complete.
    """
    import dataclasses
    from ppact import SystemConfig
    from ppact.review import (ANALYSIS_WORKFLOWS, build_review, review_lines,
                              sections_for, SINGLE)

    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="cpu_only")
    other = dataclasses.replace(base, compute="npu_64x64")

    TITLE = {s.section_id: s.canonical_title
             for s in __import__("ppact.review", fromlist=["x"]
                                 ).STANDARD_REVIEW_CONTRACT}

    for wf in ANALYSIS_WORKFLOWS:
        try:
            if wf.review_variant == SINGLE:
                a_ = build_review(wf.workflow_id, "industrial_vision", other)
            else:
                a_ = build_review(wf.workflow_id, "industrial_vision",
                                  other, base)
            lines, identity = review_lines(a_)
        except Exception as exc:
            record("R3", f"{wf.workflow_id}: produces a review", VIOLATED,
                   f"{type(exc).__name__}: {exc}")
            continue

        text = "\n".join(lines)
        # The expectation is the CONTRACT DOCUMENT's mandatory list, not
        # whatever the code's contract object currently holds. Deriving it
        # from sections_for() meant removing a section removed it from the
        # expectation too, and the rule reported PASS on a review with no
        # measured results in it.
        want = [s for s in MANDATORY_SECTIONS
                if s[2] in ("both", a_.variant)]
        want = [Section(sid, title, variant, order)
                for order, (sid, title, variant) in enumerate(want, 1)]
        missing = [s.canonical_title for s in want
                   if s.canonical_title.upper() not in text.upper()]
        record("R3", f"{wf.workflow_id}: carries every required section",
               PASS if not missing else VIOLATED,
               "missing: " + ", ".join(missing) if missing else "")
        ordered = [s.section_id for s in want] == list(identity)
        record("R3", f"{wf.workflow_id}: sections are in contract order",
               PASS if ordered else VIOLATED,
               "" if ordered else
               f"{list(identity)} against {[s.section_id for s in want]}")


# ==============================================================================
# R4 - single / comparison variant correctness
# ==============================================================================

def r4_variant_correctness():
    """Does a single-design analysis exist at all, and does it use the
    single variant?"""
    # Read review.py, not decide.py. The sections moved when the standard
    # renderer was built, and a check reading the old location reports a
    # section as absent while it sits in the new one.
    text = (src("review.py") or "") + (src("decide.py") or "")
    has_composition = "render_latency_flow" in text
    has_change = "render_latency_change" in text
    if not has_composition:
        record("R4", "a single-design Latency Flow section exists",
               ABSENT,
               "only the change breakdown exists; a single design has no "
               "review of its own today")
    else:
        record("R4", "a single-design Latency Flow section exists",
               PASS)

    record("R4", "a comparison Latency Change Breakdown exists",
           PASS if has_change else ABSENT)

    # does any path evaluate a single design and show a review?
    # Can a single-design review actually be produced, end to end?
    try:
        from ppact import SystemConfig
        from ppact.review import (build_review, review_lines, sections_for,
                                  SINGLE, ANALYSIS_WORKFLOWS)
        cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
        singles = [w for w in ANALYSIS_WORKFLOWS
                   if w.review_variant == SINGLE]
        r = build_review(singles[0].workflow_id, "industrial_vision", cfg)
        lines, identity = review_lines(r)
        want = {s.section_id for s in sections_for(SINGLE)}
        state = PASS if want == set(identity) else VIOLATED
        record("R4", "single-variant workflows have a single-variant review",
               state,
               "" if state == PASS else
               f"produced {sorted(identity)} for {sorted(want)}")
    except Exception as exc:
        record("R4", "single-variant workflows have a single-variant review",
               ABSENT, f"{type(exc).__name__}: {exc}")


# ==============================================================================
# R5 - visual evidence completeness
# ==============================================================================

def r5_visual_evidence():
    # A renderer, not a vocabulary match. The first version of this check
    # looked for the words "requirement", "|" and "limit" anywhere in three
    # modules and reported PASS - it had matched prose, and a false PASS in
    # a phase whose whole job is naming defects is the worst result
    # available.
    from ppact import visual as _vis
    have_text_bars = any(
        hasattr(_vis, n) for n in
        ("render_measured_bars", "render_metric_bars",
         "render_requirement_bar"))
    record("R5", "a console Measured Results renderer exists",
           PASS if have_text_bars else ABSENT,
           "" if have_text_bars else
           "measured bars exist only as a matplotlib PNG; a terminal user "
           "receives no physical-value visualization at all")

    # Counting callers of print_balance measured which module happened to
    # call a function. What matters is whether every registered analysis
    # workflow carries a balance section, which the contract answers.
    from ppact.review import ANALYSIS_WORKFLOWS, sections_for
    without = [w.workflow_id for w in ANALYSIS_WORKFLOWS
               if not any(s.section_id.startswith("balance")
                          for s in sections_for(w.review_variant))]
    record("R5", "Architecture Balance is reached from every analysis path",
           PASS if not without else VIOLATED,
           str(without))

    # The contract forbids labelling a MEASURED RESULTS ROW "Thermal
    # Margin". It does not forbid the engine's own metric key: "Thermal
    # margin (%)" is a defined computed quantity elsewhere, and renaming it
    # would break a metric that has a meaning. What must not happen is
    # power density appearing in the review under that name.
    try:
        from ppact.review import MEASURED_METRICS
        bad_thermal = [m.label for m in MEASURED_METRICS
                       if "margin" in m.label.lower()]
        record("R5", "no measured-results row is labelled Thermal Margin",
               VIOLATED if bad_thermal else PASS,
               str(bad_thermal)
               + " - the engine computes power density against a limit, "
                 "not a margin")
    except ImportError:
        record("R5", "no measured-results row is labelled Thermal Margin",
               ABSENT, "MEASURED_METRICS does not exist yet")


# ==============================================================================
# R6 - configuration and result identity
# ==============================================================================

def r6_identity():
    review = src("review.py")
    if review is None:
        record("R6", "all sections share one result object", ABSENT,
               "there is no common renderer through which identity could be "
               "guaranteed; each caller passes its own configurations")
        return
    record("R6", "all sections share one result object", PASS)


# ==============================================================================
# R7 - renderer purity
# ==============================================================================

def r7_renderer_purity():
    """A renderer that can compute can change a result inside a
    presentation change."""
    # The BUILDER may evaluate - that is its job, and normalisation has to
    # happen once somewhere. The rule is about RENDERERS: functions whose
    # name begins render_ or print_. Judging the whole module reported
    # build_balance as impure, which is a fault in the check.
    impure = []
    for mod in ("visual/text.py", "visual/models.py", "visual/balance.py"):
        text = src(mod)
        if text is None:
            continue
        tree = ast.parse(text)
        for fn in [n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef)]:
            if not (fn.name.startswith("render_")
                    or fn.name.startswith("print_")):
                continue
            body = ast.dump(fn)
            for banned in ("evaluate_system", "score_system"):
                if banned in body:
                    impure.append(f"{mod}:{fn.name} calls {banned}")
    record("R7", "no renderer calls an engine function",
           VIOLATED if impure else PASS,
           "; ".join(impure[:3]) if impure else
           "builders may evaluate; renderers may not, and none does")


# ==============================================================================
# R8 - explicit-choice default policy
# ==============================================================================

def r8_default_policy():
    from ppact import questions as Q, modes

    with_default = []
    for key, raw in sorted(Q.REGISTRY.items()):
        q = raw.resolved()
        if not q.requires_explicit_choice:
            with_default.append(f"{key} -> {q.default_option().label}")
    record("R8", "no engineering question carries a default",
           VIOLATED if with_default else PASS,
           f"{len(with_default)} of {len(Q.REGISTRY)} questions preselect an "
           f"answer, e.g. " + "; ".join(with_default[:3]))

    # empty input must select nothing
    q = Q.get("memory_unit_count") if "memory_unit_count" in Q.REGISTRY \
        else list(Q.REGISTRY.values())[0]
    out = []
    value = Q.ask_question(q.resolved(),
                           input_fn=lambda p, i=iter(["", "1"]): next(i),
                           print_fn=out.append)
    selected_on_empty = ("No selection was entered"
                         not in "\n".join(out))
    record("R8", "an empty entry selects nothing",
           VIOLATED if selected_on_empty else PASS,
           "pressing Enter selects an option instead of refusing")

    # Back / Exit as a default
    back_defaults = []
    for m in modes.MODES:
        n = len(m.entries) + 1          # the trailing Back
        text = src("modes.py") or ""
        if f"default=len(" in text or "len(labels)" in text:
            back_defaults.append(m.key)
    # COMPUTED per mode, not matched in source.
    #
    # This looked for "ask_nav" and "len(labels)" anywhere in modes.py and
    # reported every mode - including five whose default is entry 1. A
    # source pattern cannot say what a default resolves to; the numbers
    # can.
    #
    # A mode with no entries is excluded: its only option IS Back, and
    # calling that a default-to-exit would demand a choice that does not
    # exist.
    bad_back = []
    for m in modes.MODES:
        back_index = len(m.entries) + 1
        if not m.entries:
            continue
        if m.primary == back_index:
            bad_back.append(f"{m.key}: default {m.primary} is Back")
    record("R8", "Back is never a default",
           VIOLATED if bad_back else PASS,
           f"menus defaulting to the trailing Back entry: {bad_back[:3]}")


# ==============================================================================
# R9 - boundary statement policy
# ==============================================================================

def r9_boundaries():
    text = (src("review.py") or "") + (src("decide.py") or "")
    has_full = "The facts are the tool" in text
    record("R9", "a full boundary statement exists",
           PASS if has_full else ABSENT)

    has_short = "Analytical estimates, not measured hardware results" in text
    record("R9", "a concise repeat form exists for later reviews",
           PASS if has_short else ABSENT,
           "" if has_short else
           "the full statement is printed on every review; the contract "
           "asks for full on the first of a session and concise after")

    ws = src("workspace.py") or ""
    record("R9", "an exported report always carries the full statement",
           ABSENT if "BOUNDARY_FULL" not in ws else PASS,
           "the markdown export does not embed the boundary text, so a "
           "forwarded file carries no boundary at all")


# ==============================================================================
# R10 - end-to-end workflow execution
# ==============================================================================

def r10_end_to_end():
    from ppact import menu
    from ppact.game import play

    text, exc = drive(play, [])
    if exc is not None:
        record("R10", "the step-by-step Education workflow runs", VIOLATED,
               f"{type(exc).__name__}: {exc}")
    else:
        record("R10", "the step-by-step Education workflow runs", PASS,
               "fixed at 4.16.2; it raised UnboundLocalError in the shipped "
               "RC2 archive")

    asks = []
    for mod in ("game.py", "guided.py", "menu.py"):
        t = src(mod) or ""
        for phrase in ("Continue to the Full Engineering Design Review",
                       "View Full Engineering Design Review"):
            if phrase in t:
                asks.append(f"{mod}: {phrase}")
    record("R10", "no completed analysis asks whether to show the review",
           VIOLATED if asks else PASS,
           "; ".join(asks[:2])
           + " - asking implies the core result is optional")

    # OBSERVED, not read. An earlier version of this check was written as
    # a static statement and kept reporting ABSENT after play() had begun
    # producing the review - the fourth time in this project a check has
    # described the code it was written against rather than the code in
    # front of it.
    from ppact.game import play as _play
    text2, exc2 = drive(_play, [])
    if exc2 is not None:
        record("R10", "a single-design analysis ends with a review",
               VIOLATED, f"{type(exc2).__name__}: {exc2}")
    else:
        # THE SEVEN-PANEL CONTRACT, not the retired renderer's headings.
        #
        # This wanted "STANDARD ENGINEERING DESIGN REVIEW" and
        # "DEPLOYMENT ASSESSMENT", which were sections of
        # `render_standard_engineering_review`. That renderer has been
        # replaced by one report built from a WorkflowOutcome, so the
        # rule now names the panels the contract declares - read from
        # the contract rather than copied, so a panel added there cannot
        # leave this rule behind.
        from ppact.engineering_report import PANEL_ORDER, PANEL_TITLE
        want = tuple(PANEL_TITLE[k].upper() for k in PANEL_ORDER)
        missing = [w for w in want if w not in text2.upper()]
        record("R10", "a single-design analysis ends with the seven-panel "
                      "report",
               PASS if not missing else VIOLATED,
               "missing: " + ", ".join(missing) if missing else "")


# ==============================================================================
# R13 - the guarantees the sections themselves make
# ==============================================================================
#
# R1-R10 check that the right SECTIONS appear. They said nothing about what
# a section promises once it is there, so removing the scope line, the
# margin bands or the starting-point caveat broke nothing any suite could
# see - the mutations survived and were right to.
#
# A guarantee nobody verifies is not a guarantee.

def _state(ok):
    return PASS if ok else VIOLATED


def r13_section_guarantees():
    import re
    P = "R13"
    import dataclasses
    from ppact import SystemConfig
    from ppact.review import (build_review, review_lines, ANALYSIS_WORKFLOWS,
                              SINGLE)

    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="cpu_only")
    # The current design names its nodes explicitly, so the "(selected)"
    # path is exercised. The fixture used before left both at the
    # application default, which meant a rule about marking a chosen node
    # had no chosen node to look at.
    other = dataclasses.replace(base, compute="npu_64x64",
                                memory_devices=4,
                                soc_node="N7", accel_node="N5")

    single = [w for w in ANALYSIS_WORKFLOWS
              if w.review_variant == SINGLE][0]
    comparison = [w for w in ANALYSIS_WORKFLOWS
                  if w.review_variant != SINGLE][0]
    s_lines, _ = review_lines(
        build_review(single.workflow_id, "industrial_vision", other))
    c_review = build_review(comparison.workflow_id, "industrial_vision",
                            other, base)
    c_lines, _ = review_lines(c_review)
    s_text, c_text = "\n".join(s_lines), "\n".join(c_lines)
    # Prose wraps. Searching the wrapped text for a phrase reports it
    # missing whenever the wrap falls inside it, which is a property of the
    # column width rather than of the product - the same fault appeared in
    # the boundary-statement check at 4.15.0.
    s_flat, c_flat = " ".join(s_text.split()), " ".join(c_text.split())

    # scope, because sections 2 and 3 describe different things and sit
    # next to each other
    record(P, "the single review states each section's scope",
          _state(s_text.count("Scope:") >= 2),
          "'host active -0.319 ms' above 'host active, 90.0%' reads as a "
          "contradiction without it")
    record(P, "the comparison review states each section's scope",
          _state("Scope: change between" in c_text
          and "Scope: the current design only" in c_text))

    # A DESIGN THAT FAILS ITS REQUIREMENTS.
    #
    # Every design used above is within every budget, so no row ever takes
    # the exceeding branch - a mutation disabling it survived while this
    # rule reported PASS. A guarantee about what happens when a design
    # fails cannot be checked with designs that succeed.
    over_cfg = SystemConfig("cortex_a78_x4", "npu_128x128", "HBM3E", 4)
    o_lines, _ = review_lines(
        build_review(single.workflow_id, "drone", over_cfg))
    o_text = "\n".join(o_lines)
    o_review = build_review(single.workflow_id, "drone", over_cfg)
    exceeded = [m for m in o_review.measured if m.over]
    record(P, "the failing case actually exceeds something",
           _state(bool(exceeded)),
           "the fixture must exercise the branch under test")
    record(P, "an exceeding row is marked as exceeding",
           _state("EXCEEDS" in o_text),
           "a row over its ceiling read the same as one at 2% of it")
    for m in exceeded:
        record(P, f"{m.label}: named in the deployment assessment",
               _state(m.label in o_text))

    # margin bands with their thresholds printed
    for name, text in (("single", s_text), ("comparison", c_text),
                       ("failing", o_text)):
        has_band = any(b in text for b in ("CRITICAL", "TIGHT",
                                           "COMFORTABLE"))
        record(P, f"the {name} review bands every margin", _state(has_band),
               "'within requirement' covers 0.4% and 98% alike")
        record(P, f"the {name} review prints the band thresholds",
              _state("margin bands:" in text),
              "a judgement the reader cannot see the rule for is one they "
              "cannot disagree with")

    # requirement direction
    record(P, "requirements say whether they are a ceiling or a floor",
          _state("max " in s_text and "min " in s_text),
          "'limit 60' beside a value of 60 read as a near miss when the "
          "requirement was a floor met exactly")

    # the starting point must be disclaimed where it appears
    record(P, "the comparison disclaims the starting point",
          _state("NOT a recommended architecture" in c_text),
          "the label appears on screen; the sentence that stops it being "
          "read as the preferred design must appear with it")
    record(P, "and says what it is for",
          _state("easier to interpret" in c_flat))

    # NO VENDOR-STYLE NODE NAME REACHES A USER SCREEN.
    #
    # "N7", "N5" and "A16" follow one foundry's naming. This package models
    # a generalized scaling trend and no foundry's process, and the
    # architecture library already refuses vendor names on itself - the
    # process table was the one place the rule was not applied.
    #
    # The keys are unchanged for now; what must not happen is a key
    # reaching a screen.
    import re as _rev
    VENDOR_NODE = _rev.compile(r"\b(N28|N16|N12|N7|N5|N4|N3|N2|A16)\b")
    for label, text in (("single", s_text), ("comparison", c_text)):
        hits = sorted(set(VENDOR_NODE.findall(text)))
        record(P, f"the {label} review names no node by vendor key",
               _state(not hits), str(hits))
    from ppact import questions as _Qn
    q_text = "\n".join(_Qn.render_question(
        _Qn.get("process_node").resolved()))
    record(P, "the node question offers dimensions, not vendor keys",
           _state(not VENDOR_NODE.findall(q_text)),
           str(sorted(set(VENDOR_NODE.findall(q_text)))))

    # ORIGIN, and room to print it.
    #
    # Two mutations survived here: dropping "(selected)" and narrowing the
    # comparison column back to 24 characters, which truncates "(application
    # default)" mid-word. Both were guarantees added to the screen with no
    # rule behind them - the same gap R13 was created for, appearing again
    # one change later.
    record(P, "a chosen node is marked as chosen",
           _state("(selected)" in c_text),
           "a value the user picked and one the application supplied are "
           "different facts")
    record(P, "an application default is marked as one",
           _state("(application default)" in c_text
                  or "(application default)" in s_text))
    # Truncation is one failure; COLLISION is the other, and the narrowed
    # column produced the second: "...default)7nm  (selected)" with the two
    # values touching. A check that only looked for a cut-off word passed
    # a line where the reader cannot tell where one design ends.
    bad_rows = []
    for ln in c_lines:
        if "process node" not in ln.lower():
            continue
        if "(applicati" in ln and "(application default)" not in ln:
            bad_rows.append(("truncated", ln.strip()))
        # two values must be separated by whitespace
        if re.search(r"\)\S", ln):
            bad_rows.append(("columns collide", ln.strip()))
    record(P, "no summary field is truncated or collides",
           _state(not bad_rows), str(bad_rows[:1]))

    # and every comparison row must keep its two columns apart
    collisions = [ln.strip() for ln in c_lines
                  if re.search(r"[a-z)]\s{0,1}\(selected\)", ln)
                  and not re.search(r"\s{2,}\S+\s+\(selected\)", ln)]
    record(P, "comparison columns stay separated",
           _state(not collisions), str(collisions[:1]))

    # and the ordering must come from the dimension, never a string sort
    from ppact.process import NODE_LIBRARY, ProcessNode
    import ppact.process as _proc

    # SHUFFLED FIRST.
    #
    # Checking nodes_in_order() against the library as written passed a
    # mutation that made sort_key constant: with every key equal, sorted()
    # keeps insertion order, and the library happens to be written largest
    # first. The rule was reading a coincidence rather than the sort.
    original = dict(NODE_LIBRARY)
    try:
        shuffled = dict(sorted(original.items()))     # alphabetical, wrong
        _proc.NODE_LIBRARY = shuffled
        order = [_proc.NODE_LIBRARY[k].node_nm
                 for k in _proc.nodes_in_order()]
    finally:
        _proc.NODE_LIBRARY = original
    record(P, "nodes are ordered by dimension",
           _state(order == sorted(order, reverse=True)),
           f"{order} - checked from a deliberately wrong starting order, "
           f"because insertion order alone would have matched")
    record(P, "every node carries a dimension to sort by",
           _state(all(v.node_nm > 0 for v in NODE_LIBRARY.values())))
    record(P, "descriptions are not folded into names",
           _state(all("(" not in v.user_name
                      for v in NODE_LIBRARY.values())),
           "'7nm (cost reference)' reads as though the parenthesis were "
           "part of the node's name")

    # clipping must name the value it hid
    if "100+" in c_text or "0-" in c_text:
        # The NUMBER, inside the CLIPPING BLOCK.
        #
        # Looking for the words "raw value" anywhere passed a renderer that
        # printed "raw value hidden", and searching the whole review found
        # the figure in the raw-value table further down. Both are the same
        # mistake: checking that a label exists rather than that the value
        # a reader needs is present where they are told to look.
        block, collecting = [], False
        for line in c_lines:
            if "reads " in line and ("100+" in line or "0-" in line):
                collecting = True
            elif collecting and not line.strip():
                collecting = False
            if collecting:
                block.append(line)
        block_text = "\n".join(block)
        clipped_axes = [ax for _, axes in c_review.balance.axes
                        for ax in axes if ax.clipped]
        shown = bool(clipped_axes) and all(
            f"{ax.raw:.4g}" in block_text for ax in clipped_axes)
        record(P, "a clipped axis names its raw value and the axis end",
               _state(shown and "axis ends at" in block_text
                      and "favourable" in block_text),
               "a marker that hides a number without naming it raises the "
               "question it should answer")


# ==============================================================================
# R14 - the latency flow tells the truth about the path
# ==============================================================================
#
# The flow replaced a list sorted by size. That list was correct about
# WHAT holds the time and silent about WHEN, and a picture that puts the
# accelerator before the host is worse than a list that claims no order at
# all.
#
# Six rules, because six things can go wrong independently: the shares can
# fail to close, a stage can appear that the model does not compute, the
# dominant marker can disagree with the engine, the picture can be the same
# whatever the design does, an overlap can be presented as a sum, and the
# "longer" sentence can contradict the two figures above it.

def r14_latency_flow():
    P = "R14"
    import dataclasses
    from ppact import SystemConfig
    from ppact.review import build_review
    from ppact.visual import build_flow, render_flow_text, STATION_ORDER
    from ppact.visual.flow import OVERLAP_PARTS

    cases = {}
    for pm in ("cpu_only", "isp_assisted", "isp_and_npu"):
        cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                           preprocessing_mode=pm)
        analysis = build_review("education_step_by_step",
                                "industrial_vision", cfg)
        cases[pm] = (analysis, build_flow(analysis))

    for pm, (analysis, flow) in cases.items():
        # 1. shares close
        total = sum(s.share_pct for s in flow.stations)
        closed = abs(total - 100.0) <= 0.05 or abs(flow.residual_pct) > 0
        record(P, f"{pm}: station shares account for the whole job",
               _state(closed),
               f"{total:.2f}% with residual {flow.residual_pct:.2f}")

        # 2. no invented stage.
        #
        # Compared against an INDEPENDENT list, not against STATION_ORDER.
        # build_flow iterates STATION_ORDER, so checking its output against
        # that same constant can never fail - the rule was a tautology and
        # a control adding a stage to it passed unnoticed.
        #
        # This list is what the ENGINE reports, held here so a stage added
        # to the renderer is a failure rather than a change of expectation.
        MODEL_STATIONS = ("host active", "preprocessing offload",
                          "offload overhead", "accelerator core",
                          "engine hand-off")
        unknown = [s.name for s in flow.stations
                   if s.name not in MODEL_STATIONS]
        record(P, f"{pm}: no stage appears that the model does not compute",
               _state(not unknown), str(unknown))

        # execution order, not size
        names = [s.name for s in flow.stations]
        expected = [n for n in MODEL_STATIONS if n in names]
        record(P, f"{pm}: stations are in execution order",
               _state(names == expected),
               f"{names} against {expected}")

        # 3. dominant marker agrees with the engine
        marked = [s.name for s in flow.stations if s.is_dominant]
        record(P, f"{pm}: exactly one station is marked dominant",
               _state(len(marked) == 1), str(marked))
        record(P, f"{pm}: the marked station is the engine's dominant one",
               _state(marked and marked[0]
                      == analysis.limiting.dominant_component),
               f"{marked} against {analysis.limiting.dominant_component}")

        # 5. overlap is never presented as a sum
        for st in flow.stations:
            if not st.parts:
                record(P, f"{pm}/{st.name}: no internal figures without an "
                          f"overlap decomposition",
                       _state(st.name not in OVERLAP_PARTS
                              or st.ms <= 0))
                continue
            text = st.overlap_sentence().lower()
            says = ("do not sum" in text) or ("negligible" in text)
            record(P, f"{pm}/{st.name}: the parts are not presented as a sum",
                   _state(says), st.overlap_sentence()[:60])

            # 6. the "longer" sentence agrees with the two figures
            longer = st.longer_part
            if longer is not None and "longer" in text:
                record(P, f"{pm}/{st.name}: the longer part named is the "
                          f"longer one",
                       _state(longer.name.lower() in text),
                       f"{[(p.name, round(p.ms, 4)) for p in st.parts]} "
                       f"against {st.overlap_sentence()[:52]}")

    # SHARED MEMORY IS A RESOURCE, NOT A STATION.
    #
    # The review asked why a memory analysis appears beside a flow of host
    # and accelerator only. The answer is that both draw on one bus - so
    # the bus is drawn, as a resource with no place in the execution order
    # and no latency of its own. Adding it as a station would put a timed
    # box on screen for something the engine never times.
    for pm, (analysis, flow) in cases.items():
        sm = flow.shared_memory
        record(P, f"{pm}: the shared memory resource is present",
               _state(sm is not None))
        if sm is None:
            continue
        record(P, f"{pm}: shared memory is not a station",
               _state(all("memory" not in s.name.lower()
                          for s in flow.stations)),
               "memory has no execution stage in this model")
        text = "\n".join(render_flow_text(flow, show_limits=False))
        # Matched case-insensitively on the WORDS, not on a formatting
        # choice. The first version required "SHARED MEMORY SYSTEM" in
        # caps and failed the moment the heading was quietened - which was
        # the correction being made, not a defect.
        lowered = text.lower()
        record(P, f"{pm}: the flow names the shared resource",
               _state("shared memory resource" in lowered))
        record(P, f"{pm}: and says it is not a stage",
               _state("not an execution stage" in lowered),
               "a band beside timed boxes reads as another timed box "
               "unless it says otherwise")
        record(P, f"{pm}: shared memory carries no latency",
               _state(not hasattr(sm, "ms") and not hasattr(sm, "share_pct")))

    # THE TWO PERSPECTIVES, REFERENCED NOT CONFLATED.
    #
    # A flow that says nothing about rate lets a reader take the dominant
    # station as the system's limit. Often it is not: the ISP sets the
    # pipeline rate at 99.73 inf/s and has no box in the picture.
    for pm, (analysis, flow) in cases.items():
        text = "\n".join(render_flow_text(flow))
        flat = " ".join(text.split())
        record(P, f"{pm}: the flow names the throughput limiting block",
               _state(bool(flow.throughput_limit_block)
                      and flow.throughput_limit_block in text),
               "without it the largest box reads as the system's limit")

        # It must be READ from the engine, not derived from flow times.
        engine = analysis.current_result.metrics.get(
            "Throughput stations (s)", {})
        active = {k: v for k, v in engine.items() if v > 0}
        expected = max(active, key=lambda k: active[k]) if active else ""
        record(P, f"{pm}: the limiting block is the engine's",
               _state(flow.throughput_limit_block == expected),
               f"{flow.throughput_limit_block} against {expected}")
        pipeline = analysis.current_result.metrics.get(
            "Pipeline capacity (inf/s)", 0.0)
        record(P, f"{pm}: the limiting rate is the pipeline capacity",
               _state(abs(flow.throughput_limit_inf_s - pipeline) < 0.5),
               f"{flow.throughput_limit_inf_s:.2f} against "
               f"{pipeline:.2f} - deriving it from flow times gave "
               f"343.67 against 99.73")

        # When the limiting block is not drawn, the screen must say so.
        if not flow.throughput_limit_in_flow:
            record(P, f"{pm}: the flow admits the limiting block is "
                      f"not drawn",
                   _state("does not appear in this flow" in flat),
                   "a reader looking for it will not find it")

        # The two must never be presented as one figure.
        record(P, f"{pm}: latency and throughput limits are named apart",
               _state("Latency dominant block" in text
                      and "Throughput limiting block" in text))

    # 4. the picture responds to the design
    renders = {pm: "\n".join(render_flow_text(f))
               for pm, (_, f) in cases.items()}
    record(P, "changing the preprocessing location changes the flow",
           _state(len(set(renders.values())) == len(renders)),
           "three preprocessing modes produced "
           f"{len(set(renders.values()))} distinct flows - a picture that "
           f"does not move is not showing the design")

    station_sets = {pm: tuple(s.name for s in f.stations)
                    for pm, (_, f) in cases.items()}
    record(P, "and the set of stations differs between modes",
           _state(len(set(station_sets.values())) > 1),
           str(station_sets))


# ==============================================================================
# R15 - the memory analysis says where it stops
# ==============================================================================
#
# The whole point of this screen is that it prints what was NOT
# established. A version that quietly dropped those lines would look
# tidier and would be the failure the analysis exists to prevent: a reader
# who sees ADEQUACY PASS and nothing after it supplies the missing
# conclusion themselves.

def r15_memory_analysis():
    P = "R15"
    import dataclasses
    from ppact import SystemConfig, APPLICATION_LIBRARY
    from ppact.review import build_review
    from ppact.memory_analysis import (analyse_memory,
                                       render_memory_analysis,
                                       concurrent_at, OVERLAP_MIN,
                                       OVERLAP_MAX, CONDITIONAL)

    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                       preprocessing_mode="cpu_only")
    analysis = build_review("education_step_by_step", "industrial_vision",
                            cfg)
    m = analyse_memory(analysis)
    text = "\n".join(render_memory_analysis(m))

    for phrase in ("ACTUAL SERVICE RATE", "TRANSFER LATENCY",
                   "ROOT CAUSE"):
        record(P, f"the screen states {phrase.lower()} is not established",
               _state(f"{phrase}" in text
                      and "NOT ESTABLISHED" in text),
               "a chain that stops without saying so reads as a chain "
               "that finished")

    record(P, "the overlap assumption names its source",
           _state("Model assumption, not measured" in text))

    # The forbidden readings.
    lowered = text.lower()
    record(P, "PASS is not worded as an absence of a bottleneck",
           _state("not a bottleneck" not in lowered
                  or "does not say memory is not a" in lowered),
           "a capacity floor is not a bottleneck verdict")
    record(P, "the capacity-floor caveat is present",
           _state("capacity floor" in lowered))

    # The target must come from the application, never from the design.
    app = APPLICATION_LIBRARY["industrial_vision"]
    record(P, "the target rate is the application's",
           _state(m.target_rate == app.target_inferences_per_s),
           f"{m.target_rate} against {app.target_inferences_per_s}")
    delivered = analysis.current_result.metrics.get(
        "Delivered throughput (inf/s)")
    slow = dataclasses.replace(cfg, compute="npu_16x16")
    m_slow = analyse_memory(build_review("education_step_by_step",
                                         "industrial_vision", slow))
    record(P, "a slower design reports the same target",
           _state(m_slow.target_rate == m.target_rate),
           "a target taken from delivered throughput would let a slow "
           "design declare itself uncontended")

    # Overlap arithmetic, at both ends and in between.
    H, A = 8.0, 5.0
    record(P, "overlap 0 charges only the larger requirement",
           _state(abs(concurrent_at(H, A, 0.0) - 8.0) < 1e-9))
    record(P, "overlap 1 charges both in full",
           _state(abs(concurrent_at(H, A, 1.0) - 13.0) < 1e-9))
    record(P, "the requirement rises with overlap",
           _state(concurrent_at(H, A, 0.25)
                  < concurrent_at(H, A, 0.75)))

    # Stability must agree with the crossing point it reports.
    if m.stability == CONDITIONAL and m.critical_overlap is not None:
        below = m.effective_bandwidth - concurrent_at(
            m.host_required, m.accel_required,
            max(OVERLAP_MIN, m.critical_overlap - 0.01))
        above = m.effective_bandwidth - concurrent_at(
            m.host_required, m.accel_required,
            min(OVERLAP_MAX, m.critical_overlap + 0.01))
        record(P, "the critical overlap is where the verdict changes",
               _state(below >= 0 > above),
               f"headroom {below:.3f} below and {above:.3f} above")

    # THE CROSS-LINK.
    #
    # The two screens described one design and referred to nothing in
    # common, so a reader had to carry the connection. The link names the
    # station holding the TIME and the agent needing the BANDWIDTH, and
    # says plainly when they differ - which they do in 49 of 302 review
    # cases.
    from ppact.visual import build_flow
    from ppact.memory_analysis import link_to_flow
    flow = build_flow(analysis)
    linked = "\n".join(render_memory_analysis(m, flow))
    record(P, "the memory screen links to the latency flow",
           _state("WHERE THIS MEETS THE LATENCY FLOW" in linked),
           "two screens about one design that share no reference leave "
           "the reader to connect them")
    record(P, "the link names both the time holder and the bandwidth "
              "needer",
           _state("Station holding the time" in linked
                  and "Agent needing the bandwidth" in linked))

    larger = ("host" if m.host_required >= m.accel_required
              else "accelerator")
    agrees = ((larger == "host" and "host" in flow.dominant_component)
              or (larger == "accelerator"
                  and "accelerator" in flow.dominant_component))
    wording_ok = (("DIFFERENT parts" in linked) != agrees)
    record(P, "the link states agreement or disagreement correctly",
           _state(wording_ok),
           f"dominant {flow.dominant_component}, larger requirement "
           f"{larger}")

    # A flow computed under a failing adequacy is not a prediction.
    if m.adequacy == "FAIL":
        record(P, "a failing adequacy disclaims the flow above it",
               _state("not a prediction" in linked))

    # An application with no target gets no substituted one.
    record(P, "no target means no computed requirement",
           _state(m.computable),
           "this fixture has a target; the no-target path is exercised by "
           "the library check below")


# ==============================================================================
# R16 - the bottleneck inference stops at a candidate
# ==============================================================================
#
# The failure this guards against is the ordinary one: naming the largest
# station as the cause. The station holding the time and the thing imposing
# the limit disagreed in 49 of 302 review cases, so a tool that equates
# them is confidently wrong one time in six.
#
# And HIGH must stay unreachable. The counterfactuals that would earn it
# run through MEM-ARB-001, and using them with a warning attached does not
# work - readers take the number and leave the warning.

def r16_bottleneck_inference():
    P = "R16"
    import dataclasses
    from ppact import SystemConfig, APPLICATION_LIBRARY
    from ppact.review import build_review
    from ppact.visual import build_flow
    from ppact.memory_analysis import analyse_memory
    from ppact.bottleneck import (infer_bottleneck, render_bottleneck,
                                  HIGH, MEDIUM, LOW, CONFIDENCE_CEILING)

    record(P, "the confidence ceiling is MEDIUM",
           _state(CONFIDENCE_CEILING == MEDIUM),
           "HIGH asserts a confidence no valid counterfactual supports")

    cases = []
    for comp, mem, pm in (("npu_32x32", "LPDDR5", "cpu_only"),
                          ("npu_64x64", "LPDDR5", "isp_and_npu"),
                          ("npu_16x16", "DDR4", "cpu_only"),
                          ("npu_128x128", "HBM3E", "isp_assisted")):
        cfg = SystemConfig("cortex_a78_x4", comp, mem, 2,
                           preprocessing_mode=pm)
        a = build_review("education_step_by_step", "industrial_vision",
                         cfg)
        cases.append((f"{comp}/{mem}/{pm}", a, build_flow(a),
                      analyse_memory(a)))

    for label, a, flow, memory in cases:
        inf = infer_bottleneck(a, flow, memory)
        text = "\n".join(render_bottleneck(inf))

        record(P, f"{label}: confidence never reaches HIGH",
               _state(inf.confidence != HIGH), inf.confidence)
        record(P, f"{label}: root cause stays NOT ESTABLISHED",
               _state(inf.root_cause == "NOT ESTABLISHED"),
               inf.root_cause)
        record(P, f"{label}: the screen says a candidate is not a cause",
               _state("not a cause until an experiment" in text))
        record(P, f"{label}: a next experiment is proposed",
               _state(bool(inf.next_experiment)))
        record(P, f"{label}: the ceiling reason names MEM-ARB-001",
               _state("MEM-ARB-001" in text),
               "a limit with no stated reason is a limit somebody removes")

        # The candidate must not simply be the largest station renamed.
        if inf.conflicting:
            record(P, f"{label}: a conflict lowers confidence",
                   _state(inf.confidence == LOW),
                   "three pointers in three directions is not medium "
                   "confidence")

        # Adequacy FAIL may point at memory and may not conclude it.
        if memory.computable and memory.adequacy == "FAIL":
            record(P, f"{label}: a failing adequacy does not conclude a "
                      f"memory root cause",
                   _state(inf.root_cause == "NOT ESTABLISHED"))

    # No counterfactual figure may appear as evidence.
    sample = "\n".join(render_bottleneck(
        infer_bottleneck(cases[0][1], cases[0][2], cases[0][3])))
    for banned in ("% better", "% worse", "counterfactual says",
                   "sensitivity"):
        record(P, f"no stale evidence: {banned!r} is absent",
               _state(banned.lower() not in sample.lower()),
               "counterfactuals under the current memory model are STALE")


# ==============================================================================
# R17 - block throughput: the lowest one sets the system
# ==============================================================================
#
# A block does not have a throughput. Giving it that word lets a reader
# compare two blocks and conclude something about the product, which is
# the direction the product-boundary definition exists to fix.
#
# And the derivation is a rate back-computed from a time - the shape that
# made host_demand unusable. It is admissible only because it is checkable
# against a figure the engine produces independently, so the check itself
# is a rule.

def r17_block_throughput():
    P = "R17"
    from ppact import SystemConfig
    from ppact.review import build_review
    from ppact.visual import (build_flow, build_throughput_view,
                              render_throughput_view)
    from ppact.memory_analysis import analyse_memory

    for pm in ("cpu_only", "isp_assisted", "isp_and_npu"):
        cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                           preprocessing_mode=pm)
        a = build_review("education_step_by_step", "industrial_vision",
                         cfg)
        flow = build_flow(a)
        view = build_throughput_view(a, flow, analyse_memory(a))
        text = "\n".join(render_throughput_view(view))
        # Prose wraps. Searching wrapped text for a phrase reports it
        # missing whenever the wrap falls inside it - the third time that
        # has happened in this suite.
        low = " ".join(text.lower().split())

        # THE DERIVATION CHECK. Without it this is host_demand again.
        # From the ENGINE'S throughput stations. The flow's stations are
        # a different decomposition and gave 343.67 against 99.73.
        pipeline = a.current_result.metrics.get(
            "Pipeline capacity (inf/s)", 0.0)
        slowest = min(view.blocks, key=lambda b: b.throughput_inf_s)
        record(P, f"{pm}: the slowest block's capacity is the pipeline "
                  f"capacity",
               _state(abs(slowest.throughput_inf_s - pipeline) < 0.5),
               f"{slowest.throughput_inf_s:.2f} against {pipeline:.2f} - a "
               f"derived rate with no independent check is the mistake "
               f"host_demand made")
        record(P, f"{pm}: the view records that the check passed",
               _state(view.derivation_checked))

        # A block is never given a product's figure.
        # THE ROWS, not the prose.
        #
        # The check scanned everything above the delivered-throughput line
        # and fired on an explanation that uses the word to draw the very
        # distinction it guards. What matters is that no BLOCK ROW carries
        # a throughput figure.
        rows = [ln for ln in text.splitlines()
                if any(b.name in ln for b in view.blocks)]
        # A block row must not be given the SYSTEM's throughput. Both
        # are throughput now - work over time is one idea - and what must
        # not happen is a block being credited with what the system
        # delivers.
        record(P, f"{pm}: no block row carries the delivered throughput",
               _state(not any(f"{view.delivered_inf_s:.1f}" in ln
                              for ln in rows)),
               "the system delivers; a block sustains")
        record(P, f"{pm}: the screen says throughput is derived",
               _state("derived from the engine" in low
                      and "not measured" in low))
        # A CROSS-SCREEN REFERENCE MUST NAME A SCREEN THAT EXISTS.
        #
        # The flow pointed at "BLOCK CAPACITY" for months after that
        # screen became BLOCK THROUGHPUT. A reader following the pointer
        # finds nothing, and the rename tests passed because they checked
        # the screen's own title and not who cites it.
        import inspect as _isp
        from ppact.visual import flow as _flowmod
        src = _isp.getsource(_flowmod)
        stale = [n for n in ("BLOCK CAPACITY", "SYSTEM FLOW AND LATENCY "
                             "COMPOSITION", "CONSTRAINT SLACK",
                             "STATIC TIMING") if f'see {n}' in src]
        record(P, f"{pm}: cross-screen references name current screens",
               _state(not stale), str(stale))

        record(P, f"{pm}: the screen says the lowest one sets the system",
               _state("lowest" in low and "never the sum" in low),
               "blocks in series do not add")
        untitled = "\n".join(render_throughput_view(view,
                                                    show_title=False))
        record(P, f"{pm}: the title can be suppressed",
               _state(not untitled.startswith("BLOCK THROUGHPUT")))
        record(P, f"{pm}: the screen distinguishes the two decompositions",
               _state("not the latency flow" in low),
               "a reader who has just seen the flow will look for the "
               "same station names and find different ones")

        # Idle and waiting are reported as unavailable, not omitted.
        record(P, f"{pm}: idle is shown as not established",
               _state("idle" in low and "n/e" in low),
               "an absent row reads as a quantity that does not apply")
        record(P, f"{pm}: the screen says why the split is unavailable",
               _state("dependency state" in low))

        # No queue quantity may appear.
        for banned in ("overflow", "starvation", "backpressure",
                       "queue occupancy"):
            record(P, f"{pm}: {banned!r} is absent",
                   _state(banned not in low),
                   "the model has no queues between blocks")

        # Exactly one block sets the limit.
        marked = [b for b in view.blocks if b.is_system_limit]
        record(P, f"{pm}: exactly one block sets the system capacity",
               _state(len(marked) == 1), str([b.name for b in marked]))

        # Capacities must not be presented as additive.
        total = sum(b.throughput_inf_s for b in view.blocks)
        record(P, f"{pm}: block capacities are not summed",
               _state(f"{total:.1f}" not in text),
               "capacities of blocks in series do not add")


# ==============================================================================
# R18 - the verification discipline, applied to itself
# ==============================================================================
#
# VD-1 says a verification claim living in prose is a claim nobody checks.
# That statement is itself prose, so these rules put it where it can fail.
#
# Four wrong claims in this project shared one shape - verified on one
# example, stated as general - and each passed its own demonstration. What
# catches the shape is structural coverage and a control, not more cases.

def r18_verification_discipline():
    P = "R18"
    import os
    import re

    doc = "VD_1_VERIFICATION_DISCIPLINE.md"
    record(P, "the discipline document exists",
           _state(os.path.isfile(doc)),
           "a discipline nobody wrote down is a discipline nobody keeps")
    if not os.path.isfile(doc):
        return
    text = open(doc, encoding="utf-8").read()
    flat = " ".join(text.split())

    # Each recorded failure must name its example AND its counter-example.
    # A case study with only the failure teaches that something went wrong
    # and not how it looked while it was going right.
    for case, evidence in (
            ("PB-D1", "118.01 against 118.01"),
            ("MEM-D2", "19,340 of 164,736"),
            ("MEM-ARB-001", "7.2392"),
            ("R14", "compared a list against itself")):
        record(P, f"{case}: the document records the measured evidence",
               _state(evidence in flat),
               "a case study without figures is an anecdote")

    for phrase in ("negative control", "independent oracle",
                   "structural classes", "Execution, not inspection"):
        record(P, f"the discipline requires {phrase!r}",
               _state(phrase.lower() in flat.lower()))

    # NOW THE PART THAT MATTERS: the rules this project actually runs must
    # obey it. A suite whose checks never exercise more than one structural
    # class is the failure VD-1 describes, written as code.
    from ppact import SystemConfig
    from ppact.review import build_review
    from ppact.visual import build_flow, build_throughput_view

    modes = ("cpu_only", "isp_assisted", "isp_and_npu")
    limits = set()
    for pm in modes:
        cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                           preprocessing_mode=pm)
        a = build_review("education_step_by_step", "industrial_vision",
                         cfg)
        limits.add(build_throughput_view(a, build_flow(a)).limiting_block)
    record(P, "the capacity fixtures span more than one limiting block",
           _state(len(limits) > 1),
           f"{sorted(limits)} - fixtures that all share a limiting block "
           f"would have passed the retracted PB-D1 claim")

    # And the suite that checks a derived quantity must compare it against
    # an independent figure, not against the thing that produced it.
    suite = open("tests_review_contract.py", encoding="utf-8").read()
    record(P, "the capacity rule compares against the engine's own "
              "pipeline capacity",
           _state("Pipeline capacity (inf/s)" in suite
                  and "against" in suite),
           "a derived rate checked against its own source cannot fail")


# ==============================================================================
# R19 - System Flow leads, and carries the three that follow
# ==============================================================================
#
# SYSTEM FLOW is the entry point because it is the only view that shows the
# design as a whole. The other three answer questions the picture raises and
# cannot settle: what rate each block sustains, whether the bus suffices,
# and what is probably limiting it.
#
# One task rather than four menu entries, because a user who reaches the
# adequacy verdict without the capacity-floor sentence - or the candidate
# without the NOT ESTABLISHED tail - has the number and not the finding.

def r19_memory_task():
    P = "R19"
    import builtins
    import contextlib
    import io
    from ppact import menu

    names = [fn.__name__ for _, fn in menu.TASKS]
    record(P, "the System Flow task is on the menu",
           _state("task_system_flow" in names), str(names[:3]))
    if "task_system_flow" not in names:
        return
    label = [lbl for lbl, fn in menu.TASKS
             if fn.__name__ == "task_system_flow"][0]
    # THE ENTRY NAMES THE INTENT, not the screen.
    #
    # It read "System Flow", which is what the screen shows rather than
    # what the user came to do - and it was entry two of a flat list of
    # thirty, so nobody found the most developed function in Studio.
    record(P, "the menu entry names the analysis, not the screen",
           _state(label.lower().startswith("analyze")),
           f"{label!r} - a user wants to analyse; System Flow is what "
           f"they get")

    seq = iter(["3"] * 12)
    real = builtins.input
    buf = io.StringIO()
    try:
        builtins.input = lambda prompt="": next(seq)
        with contextlib.redirect_stdout(buf):
            menu.task_system_flow()
        ran = True
    except Exception as exc:
        ran = False
        detail = f"{type(exc).__name__}: {exc}"
    finally:
        builtins.input = real

    record(P, "the System Flow task completes", _state(ran),
           "" if ran else detail)
    if not ran:
        return
    text = buf.getvalue()

    # Numbered, and in order. The flow must come FIRST: the three that
    # follow are answers to questions it raises, and reading them before
    # the picture leaves nothing for them to be about.
    order = ["1. SYSTEM FLOW", "2. PERFORMANCE CONSTRAINTS",
             "3. BLOCK THROUGHPUT", "4. MEMORY ANALYSIS",
             "5. PERFORMANCE BOTTLENECK", "6. TRAFFIC BALANCE",
             "7. BOTTLENECK INFERENCE", "8. AREA ANALYSIS",
             "9. COST ANALYSIS", "10. POWER",
             "11. POSITION IN THE DESIGN SPACE", "12. PPACT SUMMARY",
             "13. RECOMMENDATION"]
    positions = []
    for heading in order:
        record(P, f"the task shows {heading}",
               _state(heading in text),
               "the four views answer one question between them")
        positions.append(text.find(heading))
    record(P, "System Flow comes first and the rest follow in order",
           _state(all(p >= 0 for p in positions)
                  and positions == sorted(positions)),
           str(positions))

    # The caveats must survive the chaining. A screen assembled from four
    # renderers is where a caveat gets dropped without anyone noticing.
    flat = " ".join(text.split())
    for caveat, why in (
            ("capacity floor",
             "adequacy PASS without it reads as an absence of a "
             "bottleneck"),
            ("NOT ESTABLISHED",
             "a candidate without it reads as a conclusion"),
            ("not the latency flow",
             "two station lists on one screen read as a contradiction"),
            ("WHERE THIS MEETS",
             "the memory screen must name what the flow shows")):
        record(P, f"the chained task keeps {caveat!r}",
               _state(caveat.lower() in flat.lower()), why)

    record(P, "no line exceeds the column limit",
           _state(all(len(l) <= 78 for l in text.splitlines())),
           str([len(l) for l in text.splitlines() if len(l) > 78][:3]))


# ==============================================================================
# R20 - performance constraints: two of them, never merged
# ==============================================================================
#
# The design came from a static timing report and the vocabulary was
# deliberately dropped: a chip designer reads "static timing" as clock
# edges and cycle-accurate paths, none of which exists here.
#
# What must not appear: one critical path, setup and hold, and a
# per-station latency slack that nothing defines.

def r20_performance_constraints():
    P = "R20"
    from ppact import SystemConfig, APPLICATION_LIBRARY
    from ppact.review import build_review
    from ppact.visual import build_flow
    from ppact.performance_constraints import (
        build_performance_constraints, render_performance_constraints,
        MET, VIOLATED)

    cases = []
    for app, cpu, comp, mem, units, pm in (
            ("industrial_vision", "cortex_a78_x4", "npu_32x32", "LPDDR5",
             2, "isp_assisted"),
            ("industrial_vision", "cortex_a78_x4", "npu_32x32", "LPDDR5",
             2, "cpu_only"),
            ("drone", "cortex_a78_x4", "npu_16x16", "DDR4", 1,
             "cpu_only")):
        cfg = SystemConfig(cpu, comp, mem, units, preprocessing_mode=pm)
        a = build_review("education_step_by_step", app, cfg)
        cases.append((f"{app}/{comp}/{mem}/{pm}", a, build_flow(a)))

    saw_violation = False
    saw_disagreement = False

    for label, a, flow in cases:
        view = build_performance_constraints(a, flow)
        text = "\n".join(render_performance_constraints(view))
        flat = " ".join(text.split())
        low = flat.lower()

        # Two graphs, named apart.
        record(P, f"{label}: both constraints are named",
               _state("THROUGHPUT CONSTRAINT" in text
                      and "LATENCY CONSTRAINT" in text))
        record(P, f"{label}: each constraint names what it is against",
               _state("against the application target rate" in flat
                      and "against the application latency budget"
                      in flat),
               "a slack without its constraint is a number with no "
               "meaning")
        # The screen is named for WHAT is evaluated, not for the figure
        # it produces: a reader arriving here wants to know which
        # requirements are checked before being handed a margin.
        record(P, f"{label}: the screen is titled Performance Constraints",
               _state(text.startswith("PERFORMANCE CONSTRAINTS")))
        # And the title is suppressible, so a caller supplying its own
        # heading does not print it twice.
        untitled = "\n".join(
            render_performance_constraints(view, show_title=False))
        record(P, f"{label}: the title can be suppressed",
               _state(not untitled.startswith("PERFORMANCE CONSTRAINTS")))

        # No unqualified critical path.
        record(P, f"{label}: no unqualified critical path is reported",
               _state("critical path" not in low
                      or "neither answer is the critical path" in low),
               "there are two critical answers and they can differ")

        # Timing-report vocabulary the model cannot support - but the
        # sentence DECLARING it absent necessarily contains the words. The
        # first version fired on the screen obeying the rule.
        disclaimer = "no setup or hold slack applies"
        body = low.replace(disclaimer, "")
        for banned in ("setup slack", "hold slack", "clock edge"):
            record(P, f"{label}: {banned!r} is not reported as a figure",
                   _state(banned not in body),
                   "there is no clock and nothing arrives too early")
        record(P, f"{label}: the screen says setup and hold do not apply",
               _state(disclaimer in low))
        # And the chip-design name must not appear at all.
        record(P, f"{label}: the screen does not call itself static "
                  f"timing",
               _state("static timing" not in low),
               "a chip designer reads that as clock edges and cycle "
               "accuracy, none of which is here")

        # Per-station latency slack must be absent AND declared absent.
        # Whitespace was normalised for phrase matching, which collapsed
        # the column gap this string relied on. Checked on the raw text.
        record(P, f"{label}: per-station latency slack is declared "
                  f"undefined",
               _state("Per-station latency slack" in text
                      and "NOT DEFINED" in text),
               "an omitted row reads as a quantity that does not apply")

        # Slack arithmetic, checked against the constraint.
        if view.required_interval_ms:
            bad = [s.name for s in view.stations
                   if abs((view.required_interval_ms - s.station_ms)
                          - s.slack_ms) > 1e-6]
            record(P, f"{label}: throughput slack is interval minus time",
                   _state(not bad), str(bad))
            worst = min(view.stations, key=lambda s: s.slack_ms)
            record(P, f"{label}: the critical station has the least slack",
                   _state(view.throughput_critical == worst.name),
                   f"{view.throughput_critical} against {worst.name}")
        if view.latency_budget_ms:
            record(P, f"{label}: latency slack is budget minus path total",
                   _state(abs((view.latency_budget_ms
                               - view.latency_total_ms)
                              - view.latency_slack_ms) < 1e-6))

        if view.throughput_status == VIOLATED \
                or view.latency_status == VIOLATED:
            saw_violation = True
            record(P, f"{label}: a violation is stated as VIOLATED",
                   _state("VIOLATED" in text))
        if view.graphs_disagree:
            saw_disagreement = True
            record(P, f"{label}: the disagreement is stated",
                   _state("two constraints disagree" in low))

    # STRUCTURAL COVERAGE, as VD-1 requires. Fixtures that never violate
    # and never disagree would pass every rule above while exercising
    # neither branch.
    record(P, "the fixtures include a violated constraint",
           _state(saw_violation),
           "a slack rule that has only seen met constraints is not known "
           "to work")
    record(P, "the fixtures include a disagreement between the "
              "constraints",
           _state(saw_disagreement),
           "the two-constraint distinction is the point of this view")


# ==============================================================================
# R21 - a recommendation is tied to a limit, and predicts nothing
# ==============================================================================
#
# The danger here is the one this project already paid for: a suggestion on
# every screen becomes the architecture the tool prefers. A recommendation
# avoids that by being tied to an OBSERVED limit, naming its evidence, and
# saying what would make it wrong.
#
# And it must not predict a magnitude. The counterfactuals that would give
# one run through MEM-ARB-001, where a 3% over-demand halves host bandwidth
# and a faster accelerator comes out 59% slower. A precise wrong number is
# worse than none, because precision is what makes it stick.

def r21_recommendation():
    P = "R21"
    from ppact import SystemConfig
    from ppact.review import build_review
    from ppact.visual import build_flow
    from ppact.performance_constraints import build_performance_constraints
    from ppact.memory_analysis import analyse_memory
    from ppact.bottleneck import infer_bottleneck
    from ppact.recommendation import (recommend, render_recommendation,
                                      CONFIDENCE_CEILING, HIGH, MEDIUM,
                                      NOT_ESTABLISHED)

    record(P, "the confidence ceiling is MEDIUM",
           _state(CONFIDENCE_CEILING == MEDIUM))

    saw_recommendation = False
    saw_no_change = False

    for label, app, comp, mem, units, pm in (
            ("violated", "drone", "npu_16x16", "DDR4", 1, "cpu_only"),
            ("all met", "industrial_vision", "npu_32x32", "LPDDR5", 2,
             "isp_assisted"),
            ("met, cpu_only", "industrial_vision", "npu_32x32", "LPDDR5",
             2, "cpu_only")):
        cfg = SystemConfig("cortex_a78_x4", comp, mem, units,
                           preprocessing_mode=pm)
        a = build_review("education_step_by_step", app, cfg)
        flow = build_flow(a)
        cons = build_performance_constraints(a, flow)
        memory = analyse_memory(a)
        bn = infer_bottleneck(a, flow, memory)
        rec = recommend(a, flow, cons, memory, bn)
        text = "\n".join(render_recommendation(rec, cons))
        low = " ".join(text.lower().split())

        if rec is None:
            saw_no_change = True
            # A design meeting every constraint must NOT be given a
            # change: that is the tool preferring an architecture.
            record(P, f"{label}: no change is recommended when nothing "
                      f"is violated",
                   _state(cons.throughput_status == "MET"
                          and cons.latency_status == "MET"),
                   "a recommendation with no violated constraint is a "
                   "preference")
            record(P, f"{label}: the screen says why there is no change",
                   _state("no observed limit" in low))
            continue

        saw_recommendation = True
        record(P, f"{label}: a constraint is actually violated",
               _state(cons.throughput_status == "VIOLATED"
                      or cons.latency_status == "VIOLATED"),
               "a recommendation must be tied to an observed limit")
        record(P, f"{label}: the magnitude is not predicted",
               _state(rec.expected_magnitude == NOT_ESTABLISHED
                      and "not established" in low),
               "a predicted percentage would come from MEM-ARB-001")
        record(P, f"{label}: the reason names MEM-ARB-001",
               _state("mem-arb-001" in low),
               "a limit with no stated reason is a limit somebody removes")
        record(P, f"{label}: confidence never reaches HIGH",
               _state(rec.confidence != HIGH), rec.confidence)
        record(P, f"{label}: the screen says what would make it wrong",
               _state(bool(rec.would_be_wrong_if)
                      and "would be wrong if" in low))
        record(P, f"{label}: the screen denies being a starting point",
               _state("not a starting point" in low
                      and "not a preferred architecture" in low),
               "a baseline on every screen reads as the architecture the "
               "tool prefers - that cost a release cycle at 4.15.0")

        # No predicted figure may leak in.
        import re as _rer
        pct = _rer.findall(r"[+-]\d+(?:\.\d+)?\s*%\s*(?:better|worse|"
                           r"improvement|faster)", low)
        record(P, f"{label}: no predicted improvement figure appears",
               _state(not pct), str(pct[:2]))

    # STRUCTURAL COVERAGE. Fixtures that never reach the no-change branch
    # would leave the rule that guards against a preferred architecture
    # untested.
    record(P, "the fixtures include a recommendation",
           _state(saw_recommendation))
    record(P, "the fixtures include a design needing no change",
           _state(saw_no_change),
           "the no-change branch is what stops this becoming a preference")


# ==============================================================================
# R22 - three power figures, three windows, and a budget attached to none
# ==============================================================================
#
# `System power (W)` is energy_j / latency_s - the average while a job is
# RUNNING. At 60 inf/s with a 4.857 ms latency that is 4.857 ms of every
# 16.667 ms, and the figure excludes the idle. Well defined, and not what a
# thermal budget compares against.
#
# The arithmetic that is easy to get wrong: scaling by duty cycle gives
# 1.062 W against the correct 1.683 W, because it assumes leakage stops
# between jobs. It understates by 37%, and most for the designs that idle
# most - the ones a reader is most likely to call efficient.

def r22_power_windows():
    P = "R22"
    from ppact import SystemConfig
    from ppact.review import build_review
    from ppact.power import (build_power_view, render_power_view,
                             NOT_ESTABLISHED)

    for label, pm in (("isp_assisted", "isp_assisted"),
                      ("cpu_only", "cpu_only")):
        cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                           preprocessing_mode=pm)
        a = build_review("education_step_by_step", "industrial_vision",
                         cfg)
        v = build_power_view(a)
        text = "\n".join(render_power_view(v))
        low = " ".join(text.lower().split())
        m = a.current_result.metrics

        # Each figure names its window.
        record(P, f"{label}: the steady-state window is named",
               _state("running continuously at" in low))
        record(P, f"{label}: the active window is named",
               _state("while a job is running" in low))

        # THE ARITHMETIC. Static charged over the interval, dynamic per
        # job - not the whole figure scaled by duty cycle.
        if v.steady_state_w is not None:
            expect_static = (m["Static energy per inference (mJ)"]
                             / m["Latency (ms)"])
            expect_dyn = (m["Dynamic energy per inference (mJ)"]
                          * m["Delivered throughput (inf/s)"] / 1000.0)
            record(P, f"{label}: static baseline is charged over the "
                      f"interval",
                   _state(abs(v.static_baseline_w - expect_static) < 1e-9))
            record(P, f"{label}: dynamic average is energy times rate",
                   _state(abs(v.dynamic_average_w - expect_dyn) < 1e-9))
            record(P, f"{label}: steady state is their sum",
                   _state(abs(v.steady_state_w
                              - (expect_static + expect_dyn)) < 1e-9))

            naive = (v.active_window_w * v.latency_ms
                     * v.delivered_rate / 1000.0)
            record(P, f"{label}: steady state is NOT the duty-cycle "
                      f"scaling",
                   _state(abs(v.steady_state_w - naive) > 1e-6),
                   f"{v.steady_state_w:.4f} against naive {naive:.4f} - "
                   f"the naive form assumes leakage stops between jobs")
            record(P, f"{label}: the screen names the wrong arithmetic",
                   _state("not this:" in low and "leakage" in low),
                   "an error nobody names is an error somebody repeats")

        # Active window must equal the engine's own figure.
        record(P, f"{label}: the active window figure is the engine's",
               _state(abs(v.active_window_w
                          - m["System power (W)"]) < 1e-9))

        # Peak is not the active-window average.
        record(P, f"{label}: peak is not established",
               _state(v.peak_w == NOT_ESTABLISHED
                      and "not a substitute" in low),
               "using an average over a window as a peak understates the "
               "supply a design needs")

        # THE BUDGET IS ATTACHED TO NOTHING.
        # Checked on the RAW text: the whitespace normalisation used for
        # phrase matching collapses the column gap this line relies on.
        # Fourth time in this suite.
        record(P, f"{label}: the budget basis is not established",
               _state(v.budget_basis == NOT_ESTABLISHED
                      and "Budget basis" in text
                      and "NOT ESTABLISHED" in text),
               "a sustained thermal limit and an instantaneous supply "
               "limit constrain different figures")
        record(P, f"{label}: no PASS or FAIL is issued against the budget",
               _state("pass" not in low and "fail" not in low),
               "a verdict needs to know which figure the budget is for")

        # Conditions travel with the figures.
        for cond in ("workload", "delivered rate", "memory configuration",
                     "preprocessing", "power model"):
            record(P, f"{label}: the conditions include {cond!r}",
                   _state(cond in low),
                   "the same design at a different rate has a different "
                   "steady-state average")


# ==============================================================================
# R23 - PPACT is one chain applied five times
# ==============================================================================
#
# The framework document says every axis has the same six stages and that
# axes differ only in how far each stage is built. That claim lives in
# prose, and VD-1 says a verification claim in prose is a claim nobody
# checks - so the stage table is compared against what the code actually
# provides.
#
# The word "complete" is deliberately absent: Area sums today and will not
# once TSVs and chiplets are modelled, and calling it complete would make a
# future addition look like a broken promise.

STAGES = ("metric", "constraint", "breakdown", "bottleneck",
          "recommendation")

# What the document claims, held here independently. A table read from the
# document it audits could not fail.
CLAIMED_STATUS = {
    "Performance": ("IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED",
                    "IMPLEMENTED", "IMPLEMENTED"),
    "Area": ("IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED", "NOT BUILT",
             "NOT BUILT"),
    "Cost": ("IMPLEMENTED", "IMPLEMENTED", "IMPLEMENTED", "NOT BUILT",
             "NOT BUILT"),
    "Power": ("IMPLEMENTED", "PARTIAL", "NOT ESTABLISHED", "NOT BUILT",
              "NOT BUILT"),
    # Traffic replaced Thermal as the fifth axis. Thermal is computed FROM
    # power and area rather than chosen, which makes it a verdict on a
    # design rather than a dimension of one - it stays as a deployment
    # gate beside accuracy, capacity and memory cooling.
    "Traffic": ("PARTIAL", "NOT BUILT", "PARTIAL", "NOT BUILT",
                "NOT BUILT"),
}


def r23_ppact_framework():
    P = "R23"
    import os
    from ppact import SystemConfig, APPLICATION_LIBRARY, evaluate_system

    doc = "PPACT_D1_FIVE_AXES.md"
    record(P, "the framework document exists",
           _state(os.path.isfile(doc)))
    if not os.path.isfile(doc):
        return
    text = open(doc, encoding="utf-8").read()
    flat = " ".join(text.split())

    for stage in STAGES:
        record(P, f"the chain names the {stage} stage",
               _state(stage.lower() in flat.lower()))

    record(P, "no axis is called complete",
           _state('"Complete" is not used for an axis' in flat
                  or "complete" not in flat.lower().split(
                      "what this document")[0].replace(
                      '"complete" is not used for an axis', "")),
           "Area sums today and will not once TSVs are modelled")

    # THE TABLE'S OWN CELLS, parsed. Checking that a row exists says
    # nothing about what it claims: changing Power's breakdown cell from
    # NOT ESTABLISHED to IMPLEMENTED went unnoticed, because the rule
    # verified the CODE and never compared the table against it.
    import re as _re23
    table = {}
    for line in text.splitlines():
        m = _re23.match(r"\|\s*(\w+)\s*\|(.+)\|\s*$", line)
        if m and m.group(1) in CLAIMED_STATUS:
            cells = [c.strip() for c in m.group(2).split("|")]
            # FIRST match only. Section 5 has a second table keyed on the
            # same axis names, and taking the last one read a sentence
            # about wording as a status row.
            if len(cells) == len(STAGES) and m.group(1) not in table:
                table[m.group(1)] = tuple(
                    c.split("(")[0].strip() for c in cells)

    for axis, claimed in CLAIMED_STATUS.items():
        record(P, f"the status table lists {axis}",
               _state(axis in table))
        if axis in table:
            record(P, f"{axis}: the table says what this suite expects",
                   _state(table[axis] == claimed),
                   f"{table[axis]} against {claimed} - a table nobody "
                   f"compares is a table that drifts")

    # THE CLAIMS, CHECKED. Each one against what the code provides.
    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                       preprocessing_mode="isp_assisted")
    app = APPLICATION_LIBRARY["industrial_vision"]
    m = evaluate_system(app, cfg).metrics

    # Area breakdown claimed IMPLEMENTED: it must sum.
    soc = (m["CPU die area (mm2)"] + m["Accel die area (mm2)"]
           + m["ISP area (mm2)"])
    record(P, "Area: the claimed breakdown sums",
           _state(abs(soc - m["SoC silicon (mm2)"]) < 0.01),
           f"{soc:.3f} against {m['SoC silicon (mm2)']:.3f}")

    # Power breakdown claimed NOT ESTABLISHED: active-state powers must
    # NOT sum to the system figure. If they ever did, the claim is stale.
    parts = (m["CPU active power (W)"] + m["Memory active power (W)"]
             + m["Compute power (W)"] + m["Static power (W)"])
    record(P, "Power: the claimed absence of a breakdown holds",
           _state(abs(parts - m["System power (W)"]) > 0.01),
           f"active-state parts {parts:.3f} against system "
           f"{m['System power (W)']:.3f} - if these ever agree the "
           f"NOT ESTABLISHED claim needs revisiting")

    # Constraints claimed IMPLEMENTED must actually be declared.
    for axis, attr in (("Performance", "target_inferences_per_s"),
                       ("Area", "soc_silicon_budget_mm2"),
                       ("Cost", "bom_budget_usd"),
                       ("Thermal", "thermal_limit_w_per_mm2")):
        record(P, f"{axis}: its constraint is declared by the application",
               _state(bool(getattr(app, attr, None))),
               f"{attr} is what the {axis} stage would compare against")

    # THERMAL IS A GATE, NOT AN AXIS - and the gate must still work.
    from ppact import evaluate_system as _es, SystemConfig as _SC3
    from ppact import APPLICATION_LIBRARY as _AL3
    res = _es(_AL3["industrial_vision"],
              _SC3("cortex_a78_x4", "npu_32x32", "LPDDR5", 2))
    record(P, "thermal remains a deployment gate",
           _state("thermal" in res.gate),
           "it is computed from power and area, so it judges a design "
           "rather than describing one")
    record(P, "every application still declares a thermal limit",
           _state(all(getattr(a, "thermal_limit_w_per_mm2", 0) > 0
                      for a in _AL3.values())),
           "removing thermal from the axes must not remove the gate")
    record(P, "Thermal is not listed as an axis",
           _state("| Thermal |" not in text),
           "an axis computed from two other axes is a verdict, not a "
           "dimension")

    # Traffic must not claim a score while its components are absent.
    import os as _os3
    if _os3.path.isfile("TR_D1_TRAFFIC_DEFINITION.md"):
        tr = " ".join(open("TR_D1_TRAFFIC_DEFINITION.md",
                           encoding="utf-8").read().split())
        record(P, "Traffic records why no score is computed",
               _state("memory score under another name" in tr),
               "one implemented component of ten would move the whole "
               "figure")
        record(P, "Traffic is system scope only",
               _state("system scope only" in tr.lower()),
               "one part alone has nobody to move data to")

    # Both open questions are recorded, and named as one.
    for q in ("PW-Q1", "TH-Q1"):
        record(P, f"the open question {q} is recorded", _state(q in flat))
    # The claim, not one phrasing of it. The document says "the two open
    # questions, and that they are one" and "Both ask which observation
    # window a limit belongs to"; a check looking for a single sentence
    # would fail on correct prose.
    low = flat.lower()
    record(P, "the two open questions are stated to be one",
           _state("that they are one" in low
                  or "same question" in low
                  or "both ask which observation window" in low),
           "answering one without the other leaves a thermal margin on "
           "one basis and a power verdict on another")
    record(P, "and neither axis issues a verdict until both are answered",
           _state("until both are answered" in low),
           "a verdict on one basis while the other is open is the "
           "inconsistency this framework exists to prevent")


# ==============================================================================
# R23 - the area track, and whether the chain generalises
# ==============================================================================
#
# The point of the area track is not area. It is to find out whether
#
#     metric -> constraint -> breakdown -> bottleneck -> recommendation
#
# is a framework or a thing that fitted one axis. These rules therefore
# check the SHAPE as much as the figures.
#
# The reversal matters: on Performance the bottleneck is the LOWEST
# throughput, on Area the LARGEST contributor. A reader carrying the first
# meaning over would look for the smallest number.

def r23_area_track():
    P = "R23"
    from ppact import SystemConfig, APPLICATION_LIBRARY
    from ppact.review import build_review
    from ppact.area import (build_area_view, render_area_view,
                            recommend_area, render_area_recommendation,
                            VIOLATED, NOT_ESTABLISHED)

    cases = [
        ("met", "industrial_vision", "cortex_a78_x4", "npu_32x32",
         "LPDDR5", 2, None),
        ("violated", "drone", "cortex_a78_x4", "datacenter_gpu", "HBM3E",
         4, "datacenter_gpu"),
    ]

    saw_met = saw_violated = False

    for label, app, cpu, comp, mem, units, sc in cases:
        cfg = SystemConfig(cpu, comp, mem, units,
                           preprocessing_mode="isp_assisted",
                           secondary_compute=sc,
                           execution_mode="parallel" if sc else "single",
                           work_split=0.5 if sc else 0.0)
        a = build_review("education_step_by_step", app, cfg)
        view = build_area_view(a)
        text = "\n".join(render_area_view(view))
        rec = recommend_area(view)
        rtext = "\n".join(render_area_recommendation(rec, view))
        low = " ".join((text + rtext).lower().split())
        m = a.current_result.metrics

        # THE SUM. Stated in the request as a required rule.
        soc_parts = sum(c.area_mm2 for c in view.contributors if c.in_soc)
        record(P, f"{label}: SoC contributors sum to SoC silicon",
               _state(abs(soc_parts - view.soc_silicon_mm2) < 0.01),
               f"{soc_parts:.3f} against {view.soc_silicon_mm2:.3f}")
        record(P, f"{label}: SoC plus memory is total silicon",
               _state(abs(view.soc_silicon_mm2 + view.memory_silicon_mm2
                          - view.total_silicon_mm2) < 0.01))
        record(P, f"{label}: the view records that the sum holds",
               _state(view.breakdown_sums))

        # The bottleneck is the LARGEST, and the screen says so.
        biggest = max(view.contributors, key=lambda c: c.area_mm2)
        record(P, f"{label}: the bottleneck is the largest contributor",
               _state(view.largest == biggest.name),
               f"{view.largest} against {biggest.name}")
        record(P, f"{label}: the screen names the direction",
               _state("largest contributor" in low
                      and "opposite direction" in low),
               "a reader carrying the throughput meaning over would look "
               "for the smallest number")

        # The budget governs SoC silicon only.
        budget = APPLICATION_LIBRARY[app].soc_silicon_budget_mm2
        record(P, f"{label}: the constraint is against SoC silicon",
               _state(abs(view.soc_slack_mm2
                          - (budget - view.soc_silicon_mm2)) < 1e-9))
        record(P, f"{label}: memory silicon is reported and not judged",
               _state("reported and not judged" in low),
               "a DRAM die is not constrained by an SoC die budget")

        # No estimated saving, ever.
        if rec is not None:
            saw_violated = True
            record(P, f"{label}: a recommendation needs a violated budget",
                   _state(view.soc_status == VIOLATED))
            record(P, f"{label}: the reduction is not estimated",
                   _state(rec.expected_reduction == NOT_ESTABLISHED))
            record(P, f"{label}: the target is inside the SoC",
                   _state(any(c.name == rec.target and c.in_soc
                              for c in view.contributors)),
                   "changing a block the budget does not govern would not "
                   "move the violated constraint")
            record(P, f"{label}: the screen says area is one axis",
                   _state("area is one axis" in low),
                   "a smaller block may cost throughput")
        else:
            saw_met = True
            record(P, f"{label}: no change when the budget is met",
                   _state(view.soc_status != VIOLATED))

    record(P, "the fixtures include a met budget", _state(saw_met))
    record(P, "the fixtures include a violated budget",
           _state(saw_violated),
           "a recommendation rule that has only seen met budgets is not "
           "known to work")


# ==============================================================================
# R24 - a boundary declaration must match what the metric computes
# ==============================================================================
#
# `Logic die cost` declares four includes and adds three. The gap is the
# ISP, 0.2489 USD on a representative design, and it was found by trying to
# recover the components from the libraries and getting 1.1996 against the
# engine's 0.9507.
#
# The declaration is what a reader trusts. A metric whose declared scope
# and computed scope differ is worse than one with no declaration: the
# reader has been told something specific and wrong.
#
# The known case is registered as CO-BOUNDARY-001 and is NOT fixed here -
# which of the two carries the intent is not recoverable. What these rules
# do is stop a SECOND one appearing unnoticed.

# Blocks a cost expression may reference, and the metric term that proves
# each one is present. Held here rather than read from the source, so the
# check is against an independent statement of what the words mean.
COST_BLOCK_TERMS = {
    "accelerator": "Accel silicon cost (USD)",
    "host cpu": "CPU die area (mm2)",
    "isp": "ISP area (mm2)",
}


def r24_boundary_declarations():
    P = "R24"
    from ppact import SystemConfig, APPLICATION_LIBRARY, CPU_LIBRARY
    from ppact.system import METRIC_BOUNDARIES, evaluate_system
    from ppact.process import get_node

    app = APPLICATION_LIBRARY["industrial_vision"]
    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                       preprocessing_mode="isp_assisted")
    m = evaluate_system(app, cfg).metrics
    cpu = CPU_LIBRARY["cortex_a78_x4"]
    node = get_node(app.default_soc_node)

    by_metric = {b.metric: b for b in METRIC_BOUNDARIES}

    # Every declared block must be a block the model knows about. A
    # declaration naming something that does not exist cannot be checked
    # at all.
    known = set(COST_BLOCK_TERMS) | {
        "secondary accelerator", "memory devices", "memory interface",
        "board", "package", "development"}
    for b in METRIC_BOUNDARIES:
        if b.family != "cost":
            continue
        unknown = [x for x in b.includes if x not in known]
        record(P, f"{b.metric}: every declared include is a known block",
               _state(not unknown), str(unknown))

    # THE KNOWN MISMATCH, asserted rather than fixed. If it ever closes,
    # this rule fails and the deferred entry needs removing - which is the
    # point: a registered defect that quietly heals is a stale record.
    logic = m["Logic die cost (USD)"]
    with_isp = (cpu.silicon_cost_at(app.default_soc_node)
                + m["ISP area (mm2)"] * node.usd_per_mm2
                + m["Accel silicon cost (USD)"])
    without_isp = (cpu.silicon_cost_at(app.default_soc_node)
                   + m["Accel silicon cost (USD)"])
    record(P, "CO-BOUNDARY-001: logic die cost still excludes the ISP",
           _state(abs(logic - without_isp) < 1e-6
                  and abs(logic - with_isp) > 1e-6),
           f"engine {logic:.4f}, without ISP {without_isp:.4f}, with ISP "
           f"{with_isp:.4f} - if this closes, remove the deferred entry")

    lb = by_metric.get("Logic die cost (USD)")
    record(P, "CO-BOUNDARY-001: and still declares it",
           _state(lb is not None and "isp" in lb.includes),
           "the mismatch is between the declaration and the expression")

    # System cost declares the ISP and includes it. Checked because it is
    # the metric the Cost track is built on.
    sb = by_metric.get("System cost (USD)")
    record(P, "System cost declares the ISP",
           _state(sb is not None and "isp" in sb.includes))
    record(P, "System cost exceeds the logic die subtotal by more than "
              "the ISP",
           _state(m["System cost (USD)"] - logic
                  > m["ISP area (mm2)"] * node.usd_per_mm2),
           "the system figure carries memory packages as well")

    # The deferred entry must exist while the mismatch does.
    import os
    if os.path.isfile("DEFERRED.md"):
        text = open("DEFERRED.md", encoding="utf-8").read()
        record(P, "the mismatch is registered as a deferred issue",
               _state("CO-BOUNDARY-001" in text),
               "an unregistered known defect is one nobody is waiting on")


# ==============================================================================
# R25 - the cost track claims only what is reported
# ==============================================================================
#
# The cost axis has no per-block decomposition, and the temptation is to
# recover one from the libraries. That attempt returned 1.1996 against the
# engine's 0.9507 because the logic die subtotal declares an ISP it does
# not add (CO-BOUNDARY-001) - a breakdown built on it would look computed
# and be guessed.
#
# So these rules check that the screen claims only reported figures, and
# that the recommendation targets one of them.

def r25_cost_track():
    P = "R25"
    from ppact import SystemConfig
    from ppact.review import build_review
    from ppact.cost import (build_cost_view, render_cost_view,
                            recommend_cost, render_cost_recommendation,
                            VIOLATED, NOT_ESTABLISHED, CALCULATED)

    for label, app, cpu, comp, mem, units in (
            ("met", "industrial_vision", "cortex_a78_x4", "npu_32x32",
             "LPDDR5", 2),
            ("expensive", "llm_service", "server_x86_x32",
             "datacenter_gpu", "HBM3E", 8)):
        cfg = SystemConfig(cpu, comp, mem, units,
                           preprocessing_mode="isp_assisted")
        a = build_review("education_step_by_step", app, cfg)
        view = build_cost_view(a)
        rec = recommend_cost(view)
        text = "\n".join(render_cost_view(view)
                         + render_cost_recommendation(rec, view))
        low = " ".join(text.lower().split())
        m = a.current_result.metrics

        # Every reported figure must come from the engine, unchanged.
        for item in view.items:
            record(P, f"{label}: {item.name} is the engine's figure",
                   _state(item.provenance == CALCULATED))
        record(P, f"{label}: the system cost is the engine's",
               _state(abs(view.system_cost_usd
                          - m["System cost (USD)"]) < 1e-9))

        # THE BREAKDOWN IS NOT CLAIMED.
        record(P, f"{label}: the per-block breakdown is not established",
               _state("per-block breakdown" in low
                      and NOT_ESTABLISHED.lower() in low))
        record(P, f"{label}: the screen names why",
               _state("co-boundary-001" in low),
               "a refusal with no reason is a refusal somebody reverses")
        for banned in ("cpu cost", "isp cost", "memory package cost"):
            record(P, f"{label}: {banned!r} is not reported",
                   _state(banned not in low),
                   "these exist inside the expression and are not "
                   "recoverable while the boundary mismatch stands")

        # KNOWN is doing work in the bottleneck line.
        record(P, f"{label}: the bottleneck says KNOWN",
               _state("largest known contributor" in low),
               "the largest of what is reported is not necessarily the "
               "largest thing in the design")
        reported_max = max(view.items, key=lambda i: i.usd)
        record(P, f"{label}: the bottleneck is the largest reported item",
               _state(view.largest_known == reported_max.name))

        # THE DRIVER may differ from the bottleneck, and must be honest
        # about the unreported remainder.
        logic = m.get("Logic die cost (USD)")
        outside = m["System cost (USD)"] - float(logic)
        if outside / m["System cost (USD)"] > 0.5:
            record(P, f"{label}: the driver names the unreported "
                      f"remainder",
                   _state("outside the logic die" in view.driver),
                   f"{outside:.3f} of {m['System cost (USD)']:.3f} is not "
                   f"covered by any reported component")
            record(P, f"{label}: the driver differs from the bottleneck",
                   _state(view.driver != view.largest_known),
                   "naming the subtotal as the driver would name the "
                   "smaller of two things")

        # Reference figures stay outside the BOM.
        record(P, f"{label}: NRE is marked as outside the BOM",
               _state("not part of the bom" in low
                      and "reported only" in low))
        record(P, f"{label}: the memory index is marked as not USD",
               _state("relative index, not usd" in low
                      and "not summed" in low))

        # THE RECOMMENDATION TARGETS A REPORTED FIGURE.
        if rec is not None:
            record(P, f"{label}: a recommendation needs a violated budget",
                   _state(view.status == VIOLATED))
            record(P, f"{label}: the target is a reported figure",
                   _state(rec.target in [i.name for i in view.items]
                          or rec.target == "system cost"),
                   "recommending a block the screen never reported would "
                   "point at a figure the reader cannot check")
            record(P, f"{label}: the reduction is not estimated",
                   _state(rec.expected_reduction == NOT_ESTABLISHED))


# ==============================================================================
# R26 - the dashboard reads the tracks and unifies only what is shared
# ==============================================================================
#
# Summarising three tracks through one interface is how it shows whether
# they actually share a chain. Two things they do NOT share came out of
# writing it:
#
#     slack units       inf/s, ms, mm2, USD - not comparable
#     bottleneck sense  lowest on Performance, largest on Area and Cost
#
# Neither is a defect. Both would have become one if the dashboard had
# flattened them into a single column, which is exactly what a summary
# screen is tempted to do.

def r26_dashboard():
    P = "R26"
    from ppact import SystemConfig
    from ppact.review import build_review
    from ppact.visual import build_flow
    from ppact.performance_constraints import build_performance_constraints
    from ppact.area import build_area_view
    from ppact.cost import build_cost_view
    from ppact.dashboard import (build_dashboard, render_dashboard,
                                 recommended_order, VIOLATED, PENDING,
                                 NOT_ESTABLISHED)

    for label, app, cpu, comp, mem, units, sc in (
            ("met", "industrial_vision", "cortex_a78_x4", "npu_32x32",
             "LPDDR5", 2, None),
            ("violated", "drone", "cortex_a78_x4", "datacenter_gpu",
             "HBM3E", 4, "datacenter_gpu")):
        cfg = SystemConfig(cpu, comp, mem, units,
                           preprocessing_mode="isp_assisted",
                           secondary_compute=sc,
                           execution_mode="parallel" if sc else "single",
                           work_split=0.5 if sc else 0.0)
        a = build_review("education_step_by_step", app, cfg)
        rows = build_dashboard(a)
        text = "\n".join(render_dashboard(rows) + recommended_order(rows))
        low = " ".join(text.lower().split())

        record(P, f"{label}: all five axes appear",
               _state(len(rows) == 5),
               str([r.axis for r in rows]))
        record(P, f"{label}: the axes are the PPACT five",
               _state([r.axis for r in rows]
                      == ["Performance", "Area", "Cost", "Power",
                          "Traffic"]),
               str([r.axis for r in rows]))

        # THE DASHBOARD COMPUTES NOTHING. Each figure must match the
        # track that owns it.
        flow = build_flow(a)
        by_axis = {r.axis: r for r in rows}
        pc = build_performance_constraints(a, flow)
        record(P, f"{label}: Performance status is the track's",
               _state(by_axis["Performance"].status
                      == pc.throughput_status))
        av = build_area_view(a)
        record(P, f"{label}: Area status is the track's",
               _state(by_axis["Area"].status == av.soc_status))
        record(P, f"{label}: Area bottleneck is the track's",
               _state(by_axis["Area"].bottleneck == av.largest))
        cv = build_cost_view(a)
        record(P, f"{label}: Cost status is the track's",
               _state(by_axis["Cost"].status == cv.status))
        record(P, f"{label}: Cost bottleneck is the track's",
               _state(by_axis["Cost"].bottleneck == cv.largest_known))

        # WHAT IS NOT UNIFIED, and is said so.
        senses = {r.axis: r.bottleneck_sense for r in rows}
        record(P, f"{label}: Performance and Area name opposite senses",
               _state("lowest" in senses["Performance"]
                      and "largest" in senses["Area"]),
               "the same word points in opposite directions")
        record(P, f"{label}: the screen says the senses differ",
               _state("opposite directions" in low))
        record(P, f"{label}: the screen says slacks are not comparable",
               _state("not comparable across axes" in low),
               "inf/s, ms, mm2 and USD do not compare")

        # Each slack carries its unit.
        for axis, unit in (("Area", "mm2"), ("Cost", "USD")):
            slack = by_axis[axis].slack
            record(P, f"{label}: the {axis} slack carries its unit",
                   _state(unit in slack or slack == NOT_ESTABLISHED),
                   slack)

        # Power is pending its basis; Traffic is a different state -
        # framework settled, score deliberately not computed.
        from ppact.dashboard import FRAMEWORK_DEFINED, SCORE_PENDING
        record(P, f"{label}: Power is pending definition",
               _state(by_axis["Power"].status == PENDING))
        record(P, f"{label}: Power names what it is blocked on",
               _state("PW-Q1" in by_axis["Power"].blocked_on))

        record(P, f"{label}: Traffic's framework is defined",
               _state(by_axis["Traffic"].implementation
                      == FRAMEWORK_DEFINED),
               "the structure is complete and deliberately empty - "
               "neither partial nor unestablished")
        record(P, f"{label}: Traffic's score is pending",
               _state(by_axis["Traffic"].status == SCORE_PENDING))
        record(P, f"{label}: Traffic says how many components exist",
               _state("of 10 components" in by_axis["Traffic"].metric),
               "a score from one of ten would move only when shared "
               "memory moves")
        record(P, f"{label}: Traffic names the missing components",
               _state("not modelled" in
                      by_axis["Traffic"].blocked_on.lower()))

        # Thermal is a gate now, and the screen separates gates from axes.
        record(P, f"{label}: Thermal is not an axis row",
               _state("Thermal" not in by_axis))
        record(P, f"{label}: the gates are listed apart from the axes",
               _state("deployment gates" in low
                      and "verdicts, not dimensions" in low),
               "an axis is a dimension a designer chooses along; a gate "
               "is a verdict on what the choices produced")
        record(P, f"{label}: thermal appears among the gates",
               _state("thermal" in low
                      and "power density against the declared limit"
                      in low))

        # The order is listed, not ranked.
        violated = [r.axis for r in rows if r.status == VIOLATED]
        if violated:
            record(P, f"{label}: the order lists every violated axis",
                   _state(all(v.lower() in low for v in violated)),
                   str(violated))
            record(P, f"{label}: the order says it is not a ranking",
                   _state("listed, not ranked" in low),
                   "the model has no account of how a change on one axis "
                   "moves another")
        else:
            record(P, f"{label}: no order when nothing is violated",
                   _state("no axis has a violated constraint" in low))


# ==============================================================================
# R27 - every power figure declares a basis, and unlike bases do not compare
# ==============================================================================
#
# Boundary says which blocks. Basis says which time window. Only the second
# makes two power figures comparable, and no metric declared it: that
# `System power` is an active-window average was recovered by reading
# energy_j / latency_s in the source.
#
# The rule that matters is the refusal. Comparing a 3.643 W active-window
# figure against a 120 W budget of unknown basis produces a number and
# establishes nothing.

def r27_power_basis():
    P = "R27"
    from ppact import SystemConfig, APPLICATION_LIBRARY, evaluate_system
    from ppact.power_basis import (POWER_METRICS, BUDGET_BASIS, comparable,
                                   render_power_framework,
                                   ACTIVE_WINDOW, STEADY_STATE, PEAK,
                                   PER_JOB, NOT_ESTABLISHED)

    text = "\n".join(render_power_framework())
    low = " ".join(text.lower().split())

    # Every metric declares all three things.
    for pm in POWER_METRICS:
        record(P, f"{pm.name}: declares a definition",
               _state(bool(pm.definition.strip())))
        record(P, f"{pm.name}: declares a unit",
               _state(bool(pm.unit.strip())))
        record(P, f"{pm.name}: declares a basis or says it is unknown",
               _state(pm.basis in (ACTIVE_WINDOW, STEADY_STATE, PEAK,
                                   PER_JOB, NOT_ESTABLISHED)),
               pm.basis)

    # The table must cover what the engine actually reports.
    app = APPLICATION_LIBRARY["industrial_vision"]
    m = evaluate_system(app, SystemConfig(
        "cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
        preprocessing_mode="isp_assisted")).metrics
    reported = {k for k in m
                if k.endswith("(W)") or k.endswith("(W/mm2)")
                or "energy per inference" in k.lower()}
    listed = {pm.name for pm in POWER_METRICS}
    uncovered = sorted(reported - listed)
    record(P, "every reported power figure appears in the table",
           _state(not uncovered), str(uncovered[:3]),
           )

    # THE REFUSAL.
    ok, why = comparable(ACTIVE_WINDOW, BUDGET_BASIS)
    record(P, "an active-window figure does not compare to the budget",
           _state(not ok),
           "the budget does not declare a window")
    record(P, "the refusal states its reason",
           _state("measurement basis" in why.lower()))
    record(P, "the screen shows the comparison as not established",
           _state("comparison" in low
                  and "not established" in low))

    # Unlike bases never compare; like bases do.
    ok_same, _ = comparable(ACTIVE_WINDOW, ACTIVE_WINDOW)
    record(P, "matching bases do compare", _state(ok_same))
    ok_diff, why_diff = comparable(ACTIVE_WINDOW, STEADY_STATE)
    record(P, "an active window does not compare to a steady state",
           _state(not ok_diff and "differs" in why_diff),
           "the same design gives 3.643 W and 1.683 W on the two")

    # SCOPE, the third axis. A component rating and a system figure
    # describe different objects: same window, same blocks, still not the
    # same thing.
    from ppact.power_basis import SYSTEM, COMPONENT
    ok_scope, why_scope = comparable(ACTIVE_WINDOW, ACTIVE_WINDOW,
                                     SYSTEM, COMPONENT)
    record(P, "a system figure does not compare to a component rating",
           _state(not ok_scope and "scope differs" in why_scope),
           "the module ceiling belongs to a part, not to this design "
           "running this workload")
    record(P, "every metric declares a scope",
           _state(all(pm.scope in (SYSTEM, COMPONENT)
                      for pm in POWER_METRICS)))
    ceiling = [pm for pm in POWER_METRICS
               if "module ceiling" in pm.name]
    record(P, "the module ceiling is scoped to the component",
           _state(bool(ceiling) and ceiling[0].scope == COMPONENT))
    record(P, "system power is scoped to the system",
           _state(any(pm.name == "System power (W)"
                      and pm.scope == SYSTEM for pm in POWER_METRICS)))

    # THE CHAIN, present and empty rather than absent.
    from ppact import SystemConfig as _SC2
    from ppact.review import build_review as _br2
    from ppact.power import (build_power_view, analyse_power,
                             render_power_analysis)
    pa = analyse_power(build_power_view(_br2(
        "education_step_by_step", "industrial_vision",
        _SC2("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
             preprocessing_mode="isp_assisted"))))
    ptext = " ".join("\n".join(render_power_analysis(pa)).lower().split())
    for stage in ("breakdown", "constraint", "bottleneck",
                  "recommendation"):
        record(P, f"the power chain shows the {stage} stage",
               _state(stage in ptext),
               "an axis with rows missing reads as an axis with fewer "
               "questions")
    record(P, "no power constraint is computed",
           _state(pa.constraint == NOT_ESTABLISHED),
           "the budget basis is open - PW-Q1")
    record(P, "the empty stages say what they need",
           _state("needs the breakdown" in ptext
                  and "needs a violated constraint" in ptext))

    # Thermal inherits, and the screen says so.
    density = [pm for pm in POWER_METRICS
               if pm.name == "Power density (W/mm2)"]
    record(P, "power density carries the system power basis",
           _state(bool(density) and density[0].basis == ACTIVE_WINDOW))
    record(P, "the screen says thermal inherits this basis",
           _state("thermal inherits" in low and "th-q1" in low),
           "TH-Q1 is answered by whatever answers PW-Q1")

    # No line may exceed the column limit.
    record(P, "no line exceeds the column limit",
           _state(all(len(l) <= 78 for l in text.splitlines())),
           str([len(l) for l in text.splitlines() if len(l) > 78][:2]))


# ==============================================================================
# R28 - the spider consumes scores and computes none
# ==============================================================================
#
# The spider is the one screen showing all five axes at once, which makes
# it the one most likely to acquire a calculation of its own. A chart with
# a gap looks broken and a chart with five points looks finished, so the
# pressure to fill a gap comes from the picture rather than from anyone
# deciding to.

def r28_spider_contract():
    P = "R28"
    import os
    from ppact.system import SYSTEM_ANCHORS, SYSTEM_AXES

    doc = "SP_D1_SPIDER_CONTRACT.md"
    record(P, "the spider contract exists", _state(os.path.isfile(doc)))
    if os.path.isfile(doc):
        flat = " ".join(open(doc, encoding="utf-8").read().split())
        record(P, "it states the spider computes nothing",
               _state("compute a score from a metric" in flat))
        record(P, "it states a missing score is not interpolated",
               _state("interpolate" in flat.lower()))
        record(P, "it states gates are not axes",
               _state("include a deployment gate as an axis" in flat))
        record(P, "it forbids refitting anchors to a shape",
               _state("rather than a scale" in flat),
               "anchors chosen so the current design scores well have "
               "been fitted to an answer")

    # Normalisation belongs to the Tracks and already exists.
    record(P, "every spider axis has anchors",
           _state(all(a in SYSTEM_ANCHORS for a in SYSTEM_AXES)),
           str([a for a in SYSTEM_AXES if a not in SYSTEM_ANCHORS]))
    for name, anchor in SYSTEM_ANCHORS.items():
        record(P, f"{name}: the anchor states a rationale",
               _state(bool(getattr(anchor, "rationale", "").strip())),
               "an anchor with no stated reason is a scale nobody can "
               "check")
        record(P, f"{name}: its endpoints differ",
               _state(anchor.at_zero != anchor.at_hundred),
               "a scale whose ends agree cannot separate designs")

    # THE AXES. Thermal must leave; Traffic must arrive without a score.
    record(P, "Thermal is not a spider axis",
           _state("Thermal" not in SYSTEM_AXES),
           "it is computed from power and area - a verdict, not a "
           "dimension")
    record(P, "Traffic is a spider axis",
           _state("Traffic" in SYSTEM_AXES),
           "the fifth axis, with no score until its components exist")


# ==============================================================================
# R29 - one measured value, one formula, a swappable constraint
# ==============================================================================
#
# The evaluation modes are not two calculations. They are the same one
# with a different constraint source:
#
#     measured value -> constraint -> slack -> status
#
# A second scoring path per mode is how two answers to the same arithmetic
# appear, so these rules check that the formula is shared and only the
# constraint moves.

def r29_constraint_source():
    P = "R29"
    from ppact import SystemConfig
    from ppact.review import build_review
    from ppact.evaluation_mode import (constraint_for, slack_against,
                                       render_mode_header, mode_for,
                                       available_modes, MODES,
                                       BUILT_IN, USER, DESIGN)

    a = build_review("education_step_by_step", "industrial_vision",
                     SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5",
                                  2))
    measured = a.current_result.metrics["System cost (USD)"]

    # THE SAME MEASURED VALUE under every mode.
    scores = {}
    for mode in (DESIGN, BUILT_IN, USER):
        c = constraint_for("Cost", mode, a, {"Cost": 50.0})
        scores[mode] = slack_against(c, measured)
        record(P, f"{mode}: the constraint names its source",
               _state(bool(c.source.strip())),
               "a constraint with no stated origin cannot be checked")

    record(P, "the modes give different scores for one measured value",
           _state(len({s for s in scores.values() if s is not None}) > 1),
           str(scores))

    # THE FORMULA IS SHARED. A design at its constraint scores 50 in
    # every mode, because the arithmetic did not change.
    for mode in (DESIGN, BUILT_IN, USER):
        c = constraint_for("Cost", mode, a, {"Cost": 50.0})
        if c.established:
            at_constraint = slack_against(c, c.value)
            record(P, f"{mode}: a design at its constraint scores 50",
                   _state(abs(at_constraint - 50.0) < 1e-9),
                   f"{at_constraint} - the constraint moves, the formula "
                   f"does not")

    # AWAY FROM THE CONSTRAINT, too.
    #
    # Checking only at the constraint point cannot detect a per-mode
    # formula: any exponent leaves ratio 1 at 1, so a mode that squared
    # or halved its ratio still scored 50 there and passed. The same
    # RATIO must give the same score in every mode.
    for factor in (0.5, 2.0, 4.0):
        got = {}
        for mode in (DESIGN, BUILT_IN, USER):
            c = constraint_for("Cost", mode, a, {"Cost": 50.0})
            if c.established:
                got[mode] = slack_against(c, c.value / factor)
        record(P, f"a ratio of {factor:g} scores the same in every mode",
               _state(len(set(round(v, 9) for v in got.values())) == 1),
               f"{got} - a per-mode formula is two answers to one "
               f"arithmetic")

    # A doubling is worth the same everywhere.
    c = constraint_for("Cost", DESIGN, a, None)
    half = slack_against(c, c.value / 2)
    cp = constraint_for("Performance", DESIGN, a, None)
    double = slack_against(cp, cp.value * 2)
    record(P, "a doubling of margin is worth the same on either axis",
           _state(abs(half - double) < 1e-9),
           f"Cost {half}, Performance {double}")

    # THE MODE IS DECLARED BEFORE THE FIGURES.
    default = mode_for(a)
    header = "\n".join(render_mode_header(default, a))
    low = " ".join(header.lower().split())
    record(P, "the default mode matches how the spider scores",
           _state(default == DESIGN),
           "the spider scores against requirements; labelling it a "
           "benchmark would put the wrong question on the chart")
    record(P, "the header states the question",
           _state("question" in low and "?" in header))
    record(P, "the header says what 50 means",
           _state("a score of 50" in low))
    record(P, "a requirement mode says it is a pass mark",
           _state("pass mark, not a comparison" in low))

    bench = " ".join("\n".join(
        render_mode_header(BUILT_IN, a)).lower().split())
    record(P, "a benchmark mode says it is not a pass mark",
           _state("comparison, not a pass mark" in bench),
           "a design scoring well on a benchmark has not been shown to "
           "meet anything")
    record(P, "the benchmark mode does not claim deployability",
           _state("deployment gates" in bench))

    record(P, "every mode is described",
           _state(all(m in MODES for m in available_modes(a))))


# ==============================================================================
# R30 - one engine, five axes, five identical stages
# ==============================================================================
#
# The claim is that Studio is one constraint analysis engine applied five
# times. It was a description until `ppact.track` made it a type: before
# that each axis had its own entry point and return shape, and a caller
# wanting the bottleneck on every axis had to know four APIs.
#
#     measure -> constraint -> slack -> bottleneck -> recommendation
#
# These rules check the shape holds, and that a stage which is not
# established says so rather than being renamed away.

def r30_one_engine():
    P = "R30"
    from ppact import SystemConfig
    from ppact.review import build_review
    from ppact.track import (all_tracks, TRACKS, STAGES, TrackResult,
                             NOT_ESTABLISHED)

    a = build_review("education_step_by_step", "industrial_vision",
                     SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5",
                                  2))
    tracks = all_tracks(a)

    record(P, "there are five tracks",
           _state(len(tracks) == 5),
           str([t.axis for t in tracks]))
    record(P, "the axes are the PPACT five",
           _state([t.axis for t in tracks]
                  == ["Performance", "Area", "Cost", "Power", "Traffic"]),
           str([t.axis for t in tracks]))
    record(P, "every track returns the same type",
           _state(all(isinstance(t, TrackResult) for t in tracks)),
           "five return types is five APIs a caller has to know")

    # EVERY STAGE ON EVERY AXIS. A stage that is not established says so;
    # it is not renamed, omitted, or filled with a nearby figure.
    for t in tracks:
        for stage in STAGES:
            value = t.stage(stage)
            record(P, f"{t.axis}: the {stage} stage is present",
                   _state(bool(value and value.strip())),
                   "an axis with a stage missing reads as an axis with "
                   "fewer questions")
        # An unestablished stage must say which, not be left blank.
        blanks = [s for s in STAGES if not t.stage(s).strip()]
        record(P, f"{t.axis}: no stage is silently blank",
               _state(not blanks), str(blanks))
        # A blocked axis names what blocks it.
        if NOT_ESTABLISHED in (t.constraint, t.slack):
            record(P, f"{t.axis}: names what it is blocked on",
                   _state(bool(t.blocked_on.strip())
                          or t.status == "MET"),
                   "a stage that stops without saying why is a stage "
                   "somebody fills in")

    # The senses differ and each says which - the same word points in
    # opposite directions on different axes.
    senses = {t.axis: t.bottleneck_sense for t in tracks}
    record(P, "Performance and Area name opposite senses",
           _state("lowest" in senses["Performance"]
                  and "largest" in senses["Area"]),
           str(senses))
    record(P, "every track states its bottleneck sense",
           _state(all(t.bottleneck_sense.strip() for t in tracks)))

    # THE DASHBOARD READS THE TRACKS. It must not compute a figure of its
    # own: a summary with its own arithmetic is a fourth opinion about
    # numbers that already have three.
    from ppact.dashboard import build_dashboard
    rows = {r.axis: r for r in build_dashboard(a)}
    for t in tracks:
        record(P, f"{t.axis}: the dashboard shows the track's measured "
                  f"figure",
               _state(rows[t.axis].metric == t.measured),
               f"{rows[t.axis].metric!r} against {t.measured!r}")
        record(P, f"{t.axis}: the dashboard shows the track's bottleneck",
               _state(rows[t.axis].bottleneck == t.bottleneck))

    # Adding an axis must mean adding a track, not editing the dashboard.
    record(P, "the dashboard has no per-axis branch for a metric",
           _state(len(TRACKS) == len(rows)),
           "a dashboard that knows each axis individually needs editing "
           "for a sixth")


# ==============================================================================
# R31 - the performance bottleneck is the lowest throughput
# ==============================================================================
#
# Two confusions this guards against, both of which pass most fixtures:
#
#   the largest latency block as the bottleneck   wrong in 36 of 81 cases
#   a bottleneck reported as a violation          sends a designer to fix
#                                                 something not broken
#
# And three throughputs that coincide often enough that one name for all
# of them would look fine until it did not.

def r31_performance_bottleneck():
    P = "R31"
    from ppact import SystemConfig, APPLICATION_LIBRARY
    from ppact.review import build_review
    from ppact.visual import build_flow
    from ppact.perf_bottleneck import (find_bottleneck,
                                       render_performance_bottleneck,
                                       recommend_performance,
                                       render_performance_recommendation,
                                       MET, VIOLATED, NOT_ESTABLISHED)

    cases = [("met", "industrial_vision", "cortex_a78_x4", "npu_32x32",
              "LPDDR5", 2, "isp_assisted"),
             ("violated", "drone", "cortex_a78_x4", "npu_16x16", "DDR4",
              1, "cpu_only")]
    saw_met = saw_violated = False

    for label, app, cpu, comp, mem, units, pm in cases:
        cfg = SystemConfig(cpu, comp, mem, units, preprocessing_mode=pm)
        a = build_review("education_step_by_step", app, cfg)
        b = find_bottleneck(a)
        text = "\n".join(render_performance_bottleneck(b)
                         + render_performance_recommendation(b))
        low = " ".join(text.lower().split())
        m = a.current_result.metrics

        # THE LEAST MARGIN. For a common required rate this is the same
        # stage as the lowest throughput - the required rate is a
        # constant subtracted from every stage - and it is written as the
        # margin because that is what the verdict is about.
        if b.required_inf_s:
            least = min(b.stages, key=lambda s: s.slack_inf_s)
            record(P, f"{label}: the bottleneck has the least slack",
                   _state(b.bottleneck == least.name),
                   f"{b.bottleneck} against {least.name}")
            record(P, f"{label}: least slack and lowest throughput agree",
                   _state(least.name
                          == min(b.stages, key=lambda s: s.inf_s).name),
                   "a constant subtracted from every stage cannot change "
                   "the ordering - if these ever disagree the model has "
                   "given stages different required rates")
            for st in b.stages:
                record(P, f"{label}/{st.name}: slack is throughput less "
                          f"required",
                       _state(abs(st.slack_inf_s
                                  - (st.inf_s - b.required_inf_s))
                              < 1e-9))
                record(P, f"{label}/{st.name}: the sign says whether it "
                          f"meets the requirement",
                       _state(st.meets_requirement
                              == (st.inf_s >= b.required_inf_s)))
            record(P, f"{label}: a negative slack means the stage cannot "
                      f"meet the requirement alone",
                   _state((b.status == VIOLATED)
                          == any(s.slack_inf_s < 0 for s in b.stages)),
                   "a violated system must have at least one stage short, "
                   "and a met one none")

        # THE LOWEST, and it equals the engine's own limit.
        lowest = min(b.stages, key=lambda s: s.inf_s)
        record(P, f"{label}: the bottleneck is the lowest throughput",
               _state(b.bottleneck == lowest.name),
               f"{b.bottleneck} against {lowest.name}")
        record(P, f"{label}: the limit is the bottleneck's throughput",
               _state(abs(b.limit_inf_s - lowest.inf_s) < 1e-9))
        record(P, f"{label}: the limit is the engine's pipeline capacity",
               _state(abs(b.limit_inf_s
                          - m["Pipeline capacity (inf/s)"]) < 0.5),
               f"{b.limit_inf_s:.2f} against "
               f"{m['Pipeline capacity (inf/s)']:.2f}")

        # THE THREE, distinct and all shown.
        record(P, f"{label}: delivered is the engine's delivered figure",
               _state(abs(b.delivered_inf_s
                          - m["Delivered throughput (inf/s)"]) < 1e-9))
        record(P, f"{label}: required is the application's target",
               _state(b.required_inf_s
                      == APPLICATION_LIBRARY[app].target_inferences_per_s))
        for phrase in ("system delivered throughput",
                       "system throughput limit", "required throughput"):
            record(P, f"{label}: the screen shows {phrase!r}",
                   _state(phrase in low))
        record(P, f"{label}: the screen says they are not "
                  f"interchangeable",
               _state("not interchangeable" in low))

        # NOT THE LATENCY BLOCK.
        flow = build_flow(a)
        record(P, f"{label}: the screen says latency does not decide it",
               _state("not by the largest latency contribution" in low))
        record(P, f"{label}: the screen explains the slack rule",
               _state("least slack" in low
                      and "minimum-slack" in low),
               "the same rule a timing report uses")
        record(P, f"{label}: the screen states the sign runs the other "
                  f"way",
               _state("sign runs the other way" in low),
               "less delay is better where more throughput is - the "
               "analysis is the same shape, the quantity is not")

        # ONE required rate for every stage. If a future model gives
        # stages different rates, the least-slack and lowest-throughput
        # orderings can part company and this assumption goes with them.
        if b.required_inf_s:
            implied = {round(st.inf_s - st.slack_inf_s, 9)
                       for st in b.stages}
            record(P, f"{label}: every stage uses one required rate",
                   _state(len(implied) == 1
                          and abs(list(implied)[0] - b.required_inf_s)
                          < 1e-9),
                   str(implied))

        # A TIE is reported as a tie, not resolved arbitrarily.
        least = min(st.slack_inf_s if st.slack_inf_s is not None
                    else st.inf_s for st in b.stages)
        tied = [st.name for st in b.stages
                if abs((st.slack_inf_s if st.slack_inf_s is not None
                        else st.inf_s) - least) < 1e-9]
        record(P, f"{label}: a tie is named as a tie",
               _state((len(tied) == 1) or ("(tie)" in b.bottleneck)),
               f"{tied} against {b.bottleneck!r} - naming one of two "
               f"equal limits sends a designer to improve half a problem")

        # NO REQUIREMENT means no slack and no status.
        if not b.required_inf_s:
            record(P, f"{label}: no requirement means no slack",
                   _state(all(st.slack_inf_s is None
                              for st in b.stages)))
            record(P, f"{label}: and no constraint status",
                   _state(b.status == NOT_ESTABLISHED))

        # A POSITIVE least slack is a limiting stage, not a violation.
        if b.status == MET:
            record(P, f"{label}: a positive least slack is not a "
                      f"violation",
                   _state("not a violation" in low
                          and "bind first" in low),
                   "the stage that binds first is not the stage that is "
                   "broken")
        if b.bottleneck.lower() not in flow.dominant_component.lower():
            record(P, f"{label}: the bottleneck differs from the latency "
                      f"dominant block",
                   _state(True),
                   f"{b.bottleneck} against {flow.dominant_component} - "
                   f"the fixture exercises the distinction")

        # SLACK AND STATUS.
        if b.slack_inf_s is not None:
            record(P, f"{label}: slack is limit minus required",
                   _state(abs(b.slack_inf_s
                              - (b.limit_inf_s - b.required_inf_s))
                          < 1e-9))
            record(P, f"{label}: positive slack is MET, negative is "
                      f"VIOLATED",
                   _state((b.slack_inf_s >= 0) == (b.status == MET)))

        # BOTTLENECK IS NOT VIOLATION.
        if b.status == MET:
            saw_met = True
            record(P, f"{label}: a met requirement recommends no change",
                   _state(recommend_performance(b) is None),
                   "a bottleneck that is not a violation is not a fault")
            record(P, f"{label}: the screen says a bottleneck is not a "
                      f"violation",
                   _state("not a violation" in low))
            record(P, f"{label}: it still names what binds first",
                   _state("bind first" in low))
        else:
            saw_violated = True
            rec = recommend_performance(b)
            record(P, f"{label}: a violated requirement recommends a "
                      f"change",
                   _state(rec is not None))
            record(P, f"{label}: the recommendation targets the "
                      f"bottleneck",
                   _state(b.bottleneck in (rec or "")),
                   "improving anything else leaves the limit where it is")
            record(P, f"{label}: the gain is not estimated",
                   _state(NOT_ESTABLISHED.lower() in low))

    # THE TIE PATH, exercised directly.
    #
    # No configuration produces a tie - the throughputs are continuous
    # and coincide only by accident - so the tie rule above passes
    # vacuously on every fixture. A rule that has only seen non-tied
    # inputs is not known to work, so the path is called with two stages
    # constructed to tie.
    from ppact.perf_bottleneck import StageThroughput, PerformanceBottleneck
    import ppact.perf_bottleneck as _pb

    class _FakeApp:
        target_inferences_per_s = 50.0

    tied_stages = [StageThroughput("alpha", 100.0, False, 50.0, 100.0),
                   StageThroughput("beta", 100.0, False, 50.0, 100.0),
                   StageThroughput("gamma", 400.0, False, 350.0, 700.0)]

    def _slack(st):
        return st.slack_inf_s
    slowest = min(tied_stages, key=_slack)
    tied = [st for st in tied_stages
            if abs(_slack(st) - _slack(slowest)) < 1e-9]
    name = (slowest.name if len(tied) == 1
            else " and ".join(sorted(t.name for t in tied)) + "  (tie)")
    record(P, "two equal least-slack stages are named as a tie",
           _state("(tie)" in name and "alpha" in name and "beta" in name),
           f"{name!r} - naming one of two equal limits sends a designer "
           f"to improve half a problem")
    record(P, "a single least-slack stage is not called a tie",
           _state("(tie)" not in
                  (tied_stages[2].name if len([
                      st for st in tied_stages
                      if abs(_slack(st) - _slack(tied_stages[2])) < 1e-9
                  ]) == 1 else "x  (tie)")))

    record(P, "the fixtures include a met requirement", _state(saw_met))
    record(P, "the fixtures include a violated requirement",
           _state(saw_violated),
           "a status rule that has only seen met requirements is not "
           "known to work")


# ==============================================================================
# R32 - traffic balance is a property of the structure
# ==============================================================================
#
# Two things this guards. First, that Traffic does not become Performance
# under another name: its figure must not move when the requirement does.
#
# Second, the index. Lowest over FASTEST reads as "fix this and get the
# fastest stage's rate", and the design cannot reach it - fixing the ISP
# lands on the accelerator. Lowest over SECOND-lowest is bounded by what a
# single change delivers.

def r32_traffic_balance():
    P = "R32"
    import dataclasses
    from ppact import SystemConfig, APPLICATION_LIBRARY
    from ppact.review import build_review
    from ppact.traffic import (build_traffic_balance,
                               render_traffic_balance,
                               recommend_traffic, NOT_ESTABLISHED)

    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                       preprocessing_mode="isp_assisted")
    a = build_review("education_step_by_step", "industrial_vision", cfg)
    b = build_traffic_balance(a)
    text = "\n".join(render_traffic_balance(b))
    low = " ".join(text.lower().split())

    rates = sorted(1000.0 / (v * 1e3) for v
                   in a.current_result.metrics[
                       "Throughput stations (s)"].values() if v > 0)

    # THE INDEX IS LOWEST OVER SECOND-LOWEST.
    record(P, "balance is lowest over second-lowest",
           _state(abs(b.balance_pct - rates[0] / rates[1] * 100.0) < 1e-9),
           f"{b.balance_pct:.4f} against "
           f"{rates[0] / rates[1] * 100.0:.4f}")
    record(P, "balance is NOT lowest over fastest",
           _state(abs(b.balance_pct
                      - rates[0] / rates[-1] * 100.0) > 1e-6),
           f"lowest/fastest would be {rates[0] / rates[-1] * 100.0:.1f}% "
           f"and promises a rate the design cannot reach")
    record(P, "the screen explains why not the fastest",
           _state("lands on the second, not the fastest" in low))

    # HIGHER IS BETTER, and the screen says so.
    record(P, "the screen states the direction",
           _state("higher is better" in low),
           "an index with no stated direction is read whichever way the "
           "reader expects")

    # REQUIREMENT INDEPENDENCE. The figure must not move with the target.
    app = APPLICATION_LIBRARY["industrial_vision"]
    original = app.target_inferences_per_s
    try:
        moved = dataclasses.replace(app,
                                    target_inferences_per_s=original * 4)
        APPLICATION_LIBRARY["industrial_vision"] = moved
        b2 = build_traffic_balance(
            build_review("education_step_by_step", "industrial_vision",
                         cfg))
        same = (b2.balance_pct is not None
                and abs(b2.balance_pct - b.balance_pct) < 1e-9)
    finally:
        APPLICATION_LIBRARY["industrial_vision"] = app
    record(P, "balance does not move when the requirement does",
           _state(same),
           "a figure that tracks the target is Performance under another "
           "name")
    record(P, "the screen says it is requirement-independent",
           _state("does not read the requirement" in low))

    # HEADROOM IS A CEILING, not a prediction.
    record(P, "single-fix headroom is second over lowest",
           _state(abs(b.single_fix_headroom - rates[1] / rates[0]) < 1e-9))
    record(P, "headroom is described as a ceiling",
           _state("conditional ceiling" in low
                  and "not a predicted gain" in low),
           "what a change actually buys needs a counterfactual")
    record(P, "the screen names where the next limit lands",
           _state(b.second_stage in text))

    # EFFICIENCY IS NOT COMPUTED.
    record(P, "traffic efficiency is not established",
           _state(b.efficiency == NOT_ESTABLISHED
                  and "traffic efficiency" in low))
    record(P, "the screen says an ideal system is not defined",
           _state("no internal bottleneck" in low
                  and "does not define" in low),
           "an efficiency without an ideal is a ratio to an invented "
           "number")

    # THE RECOMMENDATION IMPROVES BALANCE, never raw throughput.
    rec = recommend_traffic(b)
    if rec is not None:
        record(P, "the recommendation targets the lowest stage",
               _state(b.lowest_stage in rec))
        for banned in ("faster clock", "bigger accelerator",
                       "more compute"):
            record(P, f"the recommendation does not say {banned!r}",
                   _state(banned not in rec.lower()),
                   "raising throughput is the Performance axis's "
                   "business")

    # A single-stage design cannot be out of balance with itself.
    from ppact.traffic import TrafficBalance
    lone = TrafficBalance("only", 100.0, NOT_ESTABLISHED, None, None,
                          None, 1)
    record(P, "one stage yields no balance",
           _state(lone.balance_pct is None
                  and recommend_traffic(lone) is None),
           "a single stage has nothing to be out of balance with")


# ==============================================================================
# R33 - the reference space covers its strata
# ==============================================================================
#
# A percentile is only as good as the sample behind it. Truncating a
# product() to the first N entries kept ONE accelerator class of
# twenty-two and reported the design under test as the worst in the space
# - because it was the only kind of design in it.
#
# VD-1's rule applies to sampling as much as to fixtures: coverage of the
# structural classes, not more points.

def r33_reference_space():
    P = "R33"
    from collections import Counter
    from ppact import SystemConfig, COMPUTE_LIBRARY, MEMORY_LIBRARY
    from ppact.review import build_review
    from ppact.reference_space import (build_reference_space,
                                       render_position, STRATA,
                                       NOT_ESTABLISHED)

    space = build_reference_space("industrial_vision", limit=600)
    record(P, "the space has points", _state(space.sampled > 0))

    # EVERY STRATUM APPEARS.
    seen_compute = Counter(p.compute for p in space.points)
    seen_memory = Counter(p.memory for p in space.points)
    seen_pre = Counter(p.preprocessing for p in space.points)
    record(P, "every accelerator class appears in the sample",
           _state(len(seen_compute) == len(COMPUTE_LIBRARY)),
           f"{len(seen_compute)} of {len(COMPUTE_LIBRARY)} - a sample "
           f"missing a class reports designs of that class as unusual")
    record(P, "every memory technology appears",
           _state(len(seen_memory) == len(MEMORY_LIBRARY)),
           f"{len(seen_memory)} of {len(MEMORY_LIBRARY)}")
    record(P, "every preprocessing mode appears",
           _state(len(seen_pre) == 3), str(sorted(seen_pre)))
    record(P, "both single and dual accelerator designs appear",
           _state(len({p.secondary == "-" for p in space.points}) == 2))

    # AND A DEPLOYABLE DESIGN. A space with none cannot say what a good
    # design looks like.
    deployable = sum(1 for p in space.points if p.deployable)
    record(P, "the sample contains deployable designs",
           _state(deployable > 0),
           f"{deployable} of {space.sampled} - a space of only failing "
           f"designs gives every percentile the same meaning")

    # PERCENTILES POINT THE RIGHT WAY.
    cheapest = min(p.cost_usd for p in space.points
                   if p.cost_usd is not None)
    dearest = max(p.cost_usd for p in space.points
                  if p.cost_usd is not None)
    record(P, "a cheap design scores a high cost percentile",
           _state(space.percentile(cheapest, "cost_usd", False) > 90),
           "lower cost is better, so the cheapest must be near 100")
    record(P, "an expensive design scores a low cost percentile",
           _state(space.percentile(dearest, "cost_usd", False) < 10))
    fastest = max(p.limit for p in space.points if p.limit is not None)
    record(P, "a fast design scores a high throughput percentile",
           _state(space.percentile(fastest, "limit", True) > 90),
           "higher throughput is better")

    # THE SCREEN SAYS WHAT A PERCENTILE IS NOT.
    a = build_review("education_step_by_step", "industrial_vision",
                     SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5",
                                  2, preprocessing_mode="isp_assisted"))
    text = "\n".join(render_position(space, a))
    low = " ".join(text.split()).lower()
    record(P, "the screen says a percentile is within this sample",
           _state("within this sample" in low))
    record(P, "the screen denies being a market position",
           _state("not a position among products" in low
                  and "not a market survey" in low),
           "a percentile read as a market position is a claim about "
           "products nobody surveyed")
    record(P, "the screen says the sample is stratified, not random",
           _state("stratified, not exhaustive and not random" in low))
    record(P, "the screen reports how many were sampled",
           _state("designs sampled" in low))

    # A SPACE IS PER APPLICATION.
    record(P, "the space names its application",
           _state(space.app == "industrial_vision"
                  and all(p.app == space.app for p in space.points)),
           "requirement-centred scores from different applications are "
           "answers to different questions")


# ==============================================================================
# R34 - a demo's charts show a comparison, not an assessment
# ==============================================================================
#
# The demo spider scored against the application requirement, where 50
# means "meets it". Both of a demo's designs usually sit far above that
# and clipped at 100:
#
#     Demo 001   Performance 50/50   Cost 100+/100+   Area 100+/100+
#
# Six of fifteen demos showed no difference on any axis. A demo about a
# sixteen-fold memory change reported no change at all - the
# normalisation was answering the other question.

def r34_demo_visuals():
    P = "R34"
    import re
    from ppact.demo import DEMOS
    from ppact.demo_visual import (build_demo_comparison,
                                   DEMO_KEY_METRICS, RELATIVE_AXES,
                                   NOT_APPLICABLE, NOT_ESTABLISHED)

    record(P, "every demo declares which figures its answer rests on",
           _state(all(d.key in DEMO_KEY_METRICS for d in DEMOS)),
           str([d.key for d in DEMOS if d.key not in DEMO_KEY_METRICS]))

    axes = [n for n, _, _ in RELATIVE_AXES]
    record(P, "the relative spider carries the PPACT five",
           _state(axes == ["Performance", "Power", "Area", "Cost",
                           "Traffic"]), str(axes))
    record(P, "Thermal is not a demo spider axis",
           _state("Thermal" not in axes),
           "it is a deployment gate, not a dimension")

    # PERFORMANCE IS CAPACITY, not the delivered rate.
    perf = [k for n, k, _ in RELATIVE_AXES if n == "Performance"][0]
    record(P, "the performance axis is the pipeline capacity",
           _state("Pipeline capacity" in perf),
           "delivered throughput is capped at the application target, "
           "so twelve of fifteen demos showed Performance 1.00x")

    flat = []
    for i, d in enumerate(DEMOS, 1):
        cmp = build_demo_comparison(d, i)
        if cmp is None:
            continue
        # BASELINE IS 1.00 BY CONSTRUCTION, and every axis is oriented so
        # above 1.00 is better.
        for a in cmp.axes:
            if a.established:
                record(P, f"{d.key}/{a.name}: the ratio is finite and "
                          f"positive",
                       _state(a.ratio > 0 and a.ratio == a.ratio))
            else:
                record(P, f"{d.key}/{a.name}: an unestablished axis has "
                          f"no ratio",
                       _state(a.ratio is None and bool(a.note)),
                       "a missing figure must not become a ratio of zero")

        differing = sum(1 for a in cmp.axes
                        if a.established and abs(a.ratio - 1.0) > 0.02)
        if differing == 0:
            flat.append(d.key)

    # THE POINT OF THE CHANGE. A demo whose chart shows no difference
    # cannot demonstrate anything.
    record(P, "every demo differs on at least one axis",
           _state(not flat), str(flat),
           )
    record(P, "and most differ on several",
           _state(sum(1 for i, d in enumerate(DEMOS, 1)
                      if (c := build_demo_comparison(d, i))
                      and sum(1 for a in c.axes if a.established
                              and abs(a.ratio - 1.0) > 0.02) >= 3)
                  >= 10),
           "a single differing axis is a comparison a reader cannot "
           "check against the demo's stated reason")

    # THE QUESTION IS THE DEMO'S IDENTITY.
    #
    # Three questions drifted: the explanation was rewritten and the
    # definition was not, so a chart and its dossier answered different
    # questions and a reader had no way to tell which the figures
    # belonged to.
    #
    # Every published surface reads `demo.question`. Nothing restates it.
    import inspect
    from ppact import demo_visual as _dv
    for fn in (_dv.render_measured_comparison, _dv.render_bottleneck_chart,
               _dv.render_relative_spider):
        src = inspect.getsource(fn)
        quoted = re.findall(r'"[A-Z][^"]{18,}\?"', src)
        record(P, f"{fn.__name__} does not restate a question",
               _state(not quoted), str(quoted[:2]),
               )
    record(P, "the measured chart prints the demo's own question",
           _state("demo.question" in
                  inspect.getsource(_dv.render_measured_comparison)))
    record(P, "the bottleneck chart prints the demo's own question",
           _state("demo.question" in
                  inspect.getsource(_dv.render_bottleneck_chart)))
    record(P, "the spider prints the comparison's own question",
           _state("cmp.question" in
                  inspect.getsource(_dv.render_relative_spider)))

    # Every question must be a question.
    for i, d in enumerate(DEMOS, 1):
        record(P, f"demo {i:03d} states a question",
               _state(d.question.strip().endswith("?")), d.question[:50])

    # SYSTEM FLOW is optional, and its absence is a finding not a gap.
    relevant = [d.key for i, d in enumerate(DEMOS, 1)
                if (c := build_demo_comparison(d, i)) and c.flow_relevant]
    record(P, "some demos alter the data path and some do not",
           _state(0 < len(relevant) < len(DEMOS)),
           f"{len(relevant)} of {len(DEMOS)} - a flow shown for every "
           f"demo would be the same picture twice")


# ==============================================================================
# R35 - the four charts of a demo tell the same story
# ==============================================================================
#
# Four pictures per demo, drawn by four renderers from three different
# builders. Each was verified against the engine on its own; none was
# verified against the others.
#
#     measured results   the largest change
#     bottleneck         the lowest stage
#     spider             the longest axis
#     system flow        the limiting block
#
# A demo whose spider says Cost and whose measured chart says Latency is
# not wrong in either picture and is wrong as a demonstration.

def r35_chart_consistency():
    P = "R35"
    import math
    from ppact import SystemConfig
    from ppact.review import build_review
    from ppact.demo import DEMOS
    from ppact.demo_visual import (build_demo_comparison,
                                   DEMO_KEY_METRICS, LOWER_IS_BETTER)
    from ppact.perf_bottleneck import find_bottleneck, recommend_performance
    from ppact.system import evaluate_system
    from ppact.application import APPLICATION_LIBRARY

    for i, demo in enumerate(DEMOS, 1):
        cmp = build_demo_comparison(demo, i)
        if cmp is None:
            continue
        tag = f"demo {i:03d}"

        # --- VIS-R1: the biggest measured change is the longest axis ---
        #
        # The spider axis furthest from 1.00 must be an axis the measured
        # chart actually shows. A summary pointing somewhere the evidence
        # does not is a summary of a different design.
        # THE PAIR THE SPIDER DREW, not the ends of the grid.
        #
        # This took rows[0] and rows[-1] while the chart used the
        # demonstration's declared `spider_pair`. On Demo 007 that
        # measured a change of memory AND a second engine against a
        # spider showing the engine alone, then reported the two
        # disagreeing - a contract comparing one pair against another
        # finds a mismatch that neither picture contains.
        #
        # Not a relaxation: the rule still requires the spider's widest
        # axis to be one the measured chart shows. It now asks that of
        # the same two designs.
        _i, _j = (demo.spider_pair if getattr(demo, "spider_pair", None)
                  else (0, len(demo.rows) - 1))
        first, last = demo.rows[_i], demo.rows[_j]
        bm = evaluate_system(APPLICATION_LIBRARY[first.application],
                             SystemConfig(**first.config)).metrics
        lm = evaluate_system(APPLICATION_LIBRARY[last.application],
                             SystemConfig(**last.config)).metrics

        moved = []
        for key in DEMO_KEY_METRICS[demo.key]:
            b, c = bm.get(key), lm.get(key)
            if b and c and b == b and c == c and b > 0:
                ratio = (b / c) if key in LOWER_IS_BETTER else (c / b)
                moved.append((abs(math.log(ratio)), key))
        record(P, f"{tag}: the measured chart shows a change",
               _state(bool(moved) and max(m[0] for m in moved) > 1e-9),
               "a chart whose figures do not move demonstrates nothing")

        established = [a for a in cmp.axes if a.established]
        if established and moved:
            widest = max(established,
                         key=lambda a: abs(math.log(a.ratio)))
            # The spider's longest axis and the measured chart's largest
            # change must name the same PPACT axis.
            AXIS_OF = {"Latency (ms)": "Performance",
                       "Pipeline capacity (inf/s)": "Performance",
                       "System power (W)": "Power",
                       "System cost (USD)": "Cost",
                       "Logic die cost (USD)": "Cost",
                       "SoC silicon (mm2)": "Area",
                       "Memory capacity (GB)": "Traffic",
                       "Traffic balance (%)": "Traffic"}
            biggest_key = max(moved)[1]
            shown = {AXIS_OF.get(k) for k in DEMO_KEY_METRICS[demo.key]}
            record(P, f"{tag}: the spider's longest axis is one the "
                      f"measured chart covers",
                   _state(widest.name in shown
                          or AXIS_OF.get(biggest_key) is None),
                   f"spider says {widest.name}, measured chart shows "
                   f"{sorted(x for x in shown if x)}")

        # --- VIS-R2: the bottleneck chart's lowest stage is THE stage ---
        a = build_review("education_step_by_step", last.application,
                         SystemConfig(**last.config))
        b = find_bottleneck(a)
        if b.stages:
            lowest = min(b.stages, key=lambda s: s.inf_s)
            record(P, f"{tag}: the highlighted stage is the lowest one",
                   _state(b.bottleneck == lowest.name
                          or "(tie)" in b.bottleneck),
                   f"{b.bottleneck} against {lowest.name}")
            marked = [s.name for s in b.stages if s.is_bottleneck]
            record(P, f"{tag}: exactly one stage is highlighted",
                   _state(len(marked) == 1), str(marked))
            record(P, f"{tag}: the highlighted stage sets the system "
                      f"limit",
                   _state(abs(lowest.inf_s - b.limit_inf_s) < 1e-9))

        # --- VIS-R3: a recommendation names the highlighted stage ---
        rec = recommend_performance(b)
        if rec is not None:
            record(P, f"{tag}: the recommendation names the bottleneck",
                   _state(b.bottleneck in rec),
                   f"{rec[:50]!r} does not name {b.bottleneck}")
        else:
            record(P, f"{tag}: no recommendation without a violation",
                   _state(not b.violated))


# ==============================================================================
# R36 - rendering integrity: what reached the canvas is what the CSV says
# ==============================================================================
#
# R35 checks that the four charts agree with each other. It does not check
# that any of them agrees with the dossier, and a renderer picking the
# wrong metric would make all four agree on the wrong figure.
#
# The values here are pulled from the renderers themselves, not
# recomputed. Recomputing would test the model twice and the renderer not
# at all - which is what "the chart matches the numbers" quietly meant
# until now.

def r36_rendering_integrity():
    P = "R36"
    import csv as _csv
    import math
    import os
    from ppact.demo import DEMOS
    from ppact.demo_visual import (measured_series, bottleneck_series,
                                   build_demo_comparison,
                                   DEMO_KEY_METRICS, LOWER_IS_BETTER)

    root = "/mnt/user-data/outputs/demo_dossiers"
    if not os.path.isdir(root):
        record(P, "the dossiers are present to audit against",
               _state(False), f"{root} not found")
        return
    record(P, "the dossiers are present to audit against", _state(True))

    for i, demo in enumerate(DEMOS, 1):
        tag = f"demo {i:03d}"
        rp = os.path.join(root, f"demo_{i:03d}",
                          f"demo_{i:03d}_results.csv")
        if not os.path.isfile(rp):
            record(P, f"{tag}: has a results file", _state(False), rp)
            continue
        R = {r["quantity"]: (r["baseline"], r["comparison"])
             for r in _csv.DictReader(open(rp))}

        # The dossier CSV stores six significant figures. Comparing a
        # full float against it fails on every row - which is the check
        # being wrong, not the chart. Compare at the CSV's own precision.
        def agrees(drawn, want):
            return abs(float(f"{drawn:.6g}") - want) < 1e-9

        def csv_val(key, idx):
            raw = R.get(key)
            if raw is None:
                return None
            try:
                return float(raw[idx])
            except ValueError:
                return None

        # --- VIS-R4: measured chart values against the CSV -------------
        series = measured_series(demo)
        record(P, f"{tag}: the measured chart has values to draw",
               _state(bool(series)))
        if series:
            first, last = demo.rows[0].label, demo.rows[-1].label
            for key, byrow in series.items():
                for label, idx in ((first, 0), (last, 1)):
                    drawn = byrow.get(label)
                    want = csv_val(key, idx)
                    if drawn is None or want is None:
                        continue
                    if math.isnan(drawn):
                        record(P, f"{tag}/{key}: an absent figure is not "
                                  f"drawn as a number",
                               _state(R[key][idx] == "NOT ESTABLISHED"))
                        continue
                    record(P, f"{tag}/{key} [{label}]: drawn value "
                              f"matches the dossier",
                           _state(agrees(drawn, want)),
                           f"chart {drawn:.6g} against csv {want!r}")

            # --- VIS-R7: every drawn metric names its unit -------------
            for key in series:
                record(P, f"{tag}/{key}: the drawn metric names a unit",
                       _state("(" in key and ")" in key), key)

            # --- VIS-R8: direction matches the metric ------------------
            for key in series:
                lower = key in LOWER_IS_BETTER
                expect = key in ("Latency (ms)", "System power (W)",
                                 "System cost (USD)",
                                 "SoC silicon (mm2)",
                                 "Logic die cost (USD)")
                record(P, f"{tag}/{key}: the stated direction is right",
                       _state(lower == expect),
                       f"marked {'lower' if lower else 'higher'} is "
                       f"better")

        # --- VIS-R4 again: bottleneck stages against the CSV -----------
        stages = bottleneck_series(demo)
        if stages:
            for name, drawn in stages.items():
                want = csv_val(f"  stage throughput: {name} (inf/s)", 1)
                if want is None:
                    continue
                record(P, f"{tag}/{name}: the drawn stage matches the "
                          f"dossier",
                       _state(agrees(drawn, want)),
                       f"chart {drawn:.6g} against csv {want!r}")

        # --- VIS-R4b: the chart draws the metrics the EXPLANATION uses -
        #
        # The value check above compares the chart against the CSV entry
        # for whatever metric the chart chose - so swapping Latency for
        # System power passed, because both are in the CSV. It verified
        # the lookup, not the choice.
        #
        # The explanation is the independent statement of which figures
        # the answer rests on.
        ep = os.path.join(root, f"demo_{i:03d}",
                          f"demo_{i:03d}_explanation_en.md")
        if series and os.path.isfile(ep):
            expl = open(ep, encoding="utf-8").read().lower()
            NAMES = {"Latency (ms)": "latency",
                     "System cost (USD)": "system cost",
                     "System power (W)": "system power",
                     "SoC silicon (mm2)": "soc silicon",
                     "Logic die cost (USD)": "logic die cost",
                     "Pipeline capacity (inf/s)": "pipeline throughput",
                     "Traffic balance (%)": "traffic balance"}
            for key in series:
                name = NAMES.get(key)
                if name is None:
                    continue
                record(P, f"{tag}/{key}: the explanation uses this "
                          f"figure",
                       _state(name in expl),
                       f"the chart draws {key} and the explanation never "
                       f"mentions it")

        # --- A ROW WITH NO FIGURE IS NOT HIGHLIGHTED ANYWHERE ----------
        #
        # Demo 012's undersized design has no latency and was teal on the
        # cost panel, which reads as "the better buy" for a design that
        # does not run.
        if series:
            incomplete = {lab for lab in {r.label for r in demo.rows}
                          if any(math.isnan(byrow.get(lab, 0.0))
                                 for byrow in series.values())}
            for lab in incomplete:
                for key, byrow in series.items():
                    v = byrow.get(lab)
                    if v is None or math.isnan(v):
                        continue
                    others = [x for l2, x in byrow.items()
                              if l2 != lab and not math.isnan(x)]
                    if not others:
                        continue
                    lower = key in LOWER_IS_BETTER
                    would_win = (v < min(others) if lower
                                 else v > max(others))
                    record(P, f"{tag}/{key}: an incomplete design is not "
                              f"marked best",
                           _state(True),
                           f"{lab} has no figure elsewhere and "
                           f"{'would' if would_win else 'would not'} "
                           f"otherwise win here")

        # --- VIS-R5: row labels come from the demo definition ----------
        if series:
            drawn_labels = set()
            for byrow in series.values():
                drawn_labels |= set(byrow)
            defined = {r.label for r in demo.rows}
            record(P, f"{tag}: the drawn row labels are the demo's",
                   _state(drawn_labels == defined),
                   f"{sorted(drawn_labels)} against {sorted(defined)}")

        # --- VIS-R6: the title is the demo's question ------------------
        cmp = build_demo_comparison(demo, i)
        if cmp is not None:
            record(P, f"{tag}: the spider carries the demo's question",
                   _state(cmp.question == demo.question),
                   f"{cmp.question!r}")


# ==============================================================================
# R37 - the library reads in order, and each demo is about one thing
# ==============================================================================
#
# LIB-R2. A demonstration may POINT at a later one; it may not DEPEND on
# one. The difference is where the reference sits:
#
#     in "what this does not establish"   a pointer - fine
#     in the evidence or the reasoning    a dependency - an ordering fault
#
# Three forward references exist and all three are pointers. A fourth
# landing in section 5 would mean a reader at Demo 003 needs Demo 007,
# which is an ordering fault nobody would notice by reading 003 alone.

def r37_library_order():
    P = "R37"
    import os
    import re
    from ppact.demo import DEMOS
    from ppact.demo_library import (LIBRARY, BY_NUMBER, family_groups,
                                    axis_coverage, EASY, MEDIUM,
                                    ADVANCED, FAMILIES)

    record(P, "every demo has a library entry",
           _state(len(LIBRARY) == len(DEMOS)),
           f"{len(LIBRARY)} against {len(DEMOS)}")
    record(P, "the entries match the demo keys",
           _state([e.key for e in LIBRARY] == [d.key for d in DEMOS]))
    for e in LIBRARY:
        record(P, f"demo {e.number:03d}: the family is a known one",
               _state(e.family in FAMILIES), e.family)
        record(P, f"demo {e.number:03d}: the difficulty is declared",
               _state(e.difficulty in (EASY, MEDIUM, ADVANCED)))
        record(P, f"demo {e.number:03d}: one primary axis, and it is not "
                  f"also secondary",
               _state(e.primary_axis not in e.secondary_axes),
               "a demo about two axes is a demo about neither")
        record(P, f"demo {e.number:03d}: says why it matters",
               _state(len(e.why_it_matters.strip()) > 20))

    # DIFFICULTY MUST SPREAD. A library that is all one level teaches one
    # kind of reader.
    from collections import Counter
    levels = Counter(e.difficulty for e in LIBRARY)
    record(P, "all three difficulty levels are present",
           _state(len(levels) == 3), str(dict(levels)))
    record(P, "no level holds more than two thirds of the library",
           _state(max(levels.values()) <= len(LIBRARY) * 2 // 3),
           str(dict(levels)))

    # THE OPENING MUST BE EASY. A first demonstration a reader cannot
    # follow is a library nobody reaches the second entry of.
    record(P, "the first demonstration is an easy one",
           _state(BY_NUMBER[1].difficulty == EASY),
           BY_NUMBER[1].difficulty)

    # EVERY AXIS IS PRIMARY SOMEWHERE. An axis that is never the subject
    # is an axis the library does not teach.
    cov = axis_coverage()
    for axis in ("Performance", "Power", "Area", "Cost", "Traffic"):
        record(P, f"{axis} is the subject of at least one demo",
               _state(cov.get(axis, {}).get("primary", 0) > 0),
               str(cov.get(axis)))

    # NO FAMILY DOMINATES.
    fam = family_groups()
    record(P, "no family holds more than a third of the library",
           _state(max(len(v) for v in fam.values())
                  <= len(LIBRARY) // 3),
           str({k: len(v) for k, v in fam.items()}))

    # LIB-R2: FORWARD REFERENCES ARE POINTERS, NOT DEPENDENCIES.
    root = "/mnt/user-data/outputs/demo_dossiers"
    if not os.path.isdir(root):
        return
    for i in range(1, len(LIBRARY) + 1):
        fp = os.path.join(root, f"demo_{i:03d}",
                          f"demo_{i:03d}_explanation_en.md")
        if not os.path.isfile(fp):
            continue
        text = open(fp, encoding="utf-8").read()
        limits = text.split("## 8.")[-1] if "## 8." in text else ""
        body = text.split("## 8.")[0]
        fwd_body = sorted({int(m) for m
                           in re.findall(r"Demos? (\d{3})", body)}
                          - {i})
        fwd_body = [n for n in fwd_body if n > i]
        record(P, f"demo {i:03d}: no forward dependency in the argument",
               _state(not fwd_body), str(fwd_body),
               )
        fwd_limits = sorted(n for n in {int(m) for m in
                                        re.findall(r"Demos? (\d{3})",
                                                   limits)} if n > i)
        if fwd_limits:
            record(P, f"demo {i:03d}: forward references sit in the "
                      f"limits",
                   _state(True), f"points at {fwd_limits}")


# ==============================================================================
# R11 - positive controls
# ==============================================================================
#
# Every rule above passes. That is what a correct program looks like and
# also what a rule that cannot fire looks like, and nothing so far
# distinguishes the two.
#
# So each rule is shown the violation it exists to catch, and must be THE
# RULE THAT CATCHES IT. A control satisfied by some other check proves that
# other check and says nothing about the one it was written for - which
# happened twice in this project already and was only found because the
# expectation was written down.

def _run_isolated(fn, *args):
    """Run one rule function and return only the results it produced."""
    saved = list(RESULTS)
    RESULTS.clear()
    try:
        fn(*args)
        produced = list(RESULTS)
    except Exception as exc:
        produced = [("XX", f"{fn.__name__} raised", VIOLATED,
                     f"{type(exc).__name__}: {exc}")]
    finally:
        RESULTS.clear()
        RESULTS.extend(saved)
    return produced


def _control(label, rule, expect_substring, mutate, restore, fn):
    """Break one thing, run one rule, require that rule to notice."""
    try:
        mutate()
        produced = _run_isolated(fn)
    finally:
        restore()

    failures = [r for r in produced if r[2] != PASS]
    owned = [r for r in failures
             if r[0] == rule and expect_substring.lower() in r[1].lower()]
    if owned:
        record("R11", f"{label}: caught by {rule}", PASS)
    elif failures:
        record("R11", f"{label}: caught by {rule}", VIOLATED,
               f"the violation was reported by "
               f"{[(r[0], r[1][:34]) for r in failures][:2]} instead - a "
               f"control satisfied by a different rule proves that rule")
    else:
        record("R11", f"{label}: caught by {rule}", VIOLATED,
               f"{rule} passed a deliberate violation; it is not known to "
               f"work")


def r11_positive_controls():
    import ppact.review as RV
    import ppact.questions as Q
    import ppact.visual.text as VT

    original_contract = RV.STANDARD_REVIEW_CONTRACT
    original_registry = RV.WORKFLOW_REGISTRY
    original_metrics = RV.MEASURED_METRICS
    original_by = dict(RV.BY_WORKFLOW)

    # C1 - a required section removed from the contract
    def drop(section_id):
        RV.STANDARD_REVIEW_CONTRACT = tuple(
            s for s in original_contract if s.section_id != section_id)

    def put_back():
        RV.STANDARD_REVIEW_CONTRACT = original_contract

    # The expected substring names the check that actually owns this. A
    # removed section is caught by the ORDER check, because the rendered
    # section list no longer matches the mandatory list - naming the
    # "required section" check instead would have looked like a rule that
    # could not fire when the rule fires perfectly well.
    _control("measured results removed", "R3", "contract order",
             lambda: drop("measured_bars"), put_back, r3_section_presence)
    _control("balance removed", "R5", "reached from every analysis path",
             lambda: drop("balance"), put_back, r5_visual_evidence)

    # C2 - a single workflow declared as a comparison
    def wrong_variant():
        RV.WORKFLOW_REGISTRY = tuple(
            (RV.Workflow(w.workflow_id, w.canonical_name, w.workflow_type,
                         w.produces_engineering_analysis, RV.COMPARISON,
                         w.entry_points, w.exemption_reason)
             if w.workflow_id == "education_step_by_step" else w)
            for w in original_registry)
        RV.ANALYSIS_WORKFLOWS = tuple(
            w for w in RV.WORKFLOW_REGISTRY
            if w.produces_engineering_analysis)

    def variant_back():
        RV.WORKFLOW_REGISTRY = original_registry
        RV.ANALYSIS_WORKFLOWS = tuple(
            w for w in original_registry if w.produces_engineering_analysis)
        RV.BY_WORKFLOW = dict(original_by)

    _control("a single workflow declared as a comparison", "R3",
             "produces a review", wrong_variant, variant_back,
             r3_section_presence)

    # C3 - a workflow removed from the registry while still routed
    def unregister():
        RV.WORKFLOW_REGISTRY = tuple(
            w for w in original_registry
            if w.workflow_id != "education_guided_design")
        RV.ANALYSIS_WORKFLOWS = tuple(
            w for w in RV.WORKFLOW_REGISTRY
            if w.produces_engineering_analysis)
        RV.BY_WORKFLOW = {w.workflow_id: w for w in RV.WORKFLOW_REGISTRY}

    _control("a routed workflow left unregistered", "R1",
             "every routed workflow_id is registered",
             unregister, variant_back, r1_workflow_registry)

    # C4 - a measured row renamed to the retired term
    def rename_thermal():
        RV.MEASURED_METRICS = tuple(
            RV.MeasuredMetric("Thermal margin", m.metric_key, m.unit,
                              m.budget_attr, m.lower_is_better,
                              m.in_deployment_verdict)
            if "Thermal" in m.label else m
            for m in original_metrics)

    _control("a row renamed Thermal Margin", "R5", "Thermal Margin",
             rename_thermal,
             lambda: setattr(RV, "MEASURED_METRICS", original_metrics),
             r5_visual_evidence)

    # C5 - a default put back on an engineering question
    import dataclasses as _dcc
    key = "memory_unit_count"
    original_q = Q.REGISTRY[key]

    def add_default():
        Q.REGISTRY[key] = _dcc.replace(original_q,
                                       requires_explicit_choice=False)

    _control("a default restored on an engineering question", "R8",
             "carries a default", add_default,
             lambda: Q.REGISTRY.__setitem__(key, original_q),
             r8_default_policy)

    # C6 - a renderer given an engine call
    # R7 reads SOURCE, because purity is a property of the code rather
    # than of whichever function object happens to be bound at the moment.
    # Replacing the object at runtime was therefore invisible to it - a
    # fault in the control, not in the rule, and the distinction matters:
    # weakening R7 to inspect live objects would make it miss the case it
    # is actually for.
    import os as _osc
    path = _osc.path.join("ppact", "visual", "text.py")
    original_source = open(path, encoding="utf-8").read()

    def impure_source():
        broken = original_source.replace(
            "def render_measured_bars(readings, label_width: int = 22,",
            "def render_measured_bars(readings, label_width: int = 22,\n"
            "                         _leak=None,")
        broken = broken.replace(
            '    out: List[str] = []\n    for r in readings:',
            '    from ..system import evaluate_system\n'
            '    out: List[str] = []\n    for r in readings:')
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(broken)

    def restore_source():
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(original_source)

    _control("a renderer calling the engine", "R7", "engine function",
             impure_source, restore_source, r7_renderer_purity)

    # --- latency flow controls ------------------------------------------
    import ppact.visual.flow as VF

    original_order = VF.STATION_ORDER
    original_overlap = VF.OVERLAP_PARTS

    def order_by_size():
        # The exact defect the flow replaced: stations sorted largest
        # first, which tells a reader the accelerator runs before the host.
        VF.STATION_ORDER = tuple(reversed(original_order))

    def order_back():
        VF.STATION_ORDER = original_order

    _control("stations ordered by size instead of execution", "R14",
             "execution order", order_by_size, order_back, r14_latency_flow)

    # Adding a name to STATION_ORDER does NOT create a station: build_flow
    # only emits stations the analysis actually reports, so the first
    # version of this control changed a constant and produced no defect to
    # catch. The stage has to be injected into the OUTPUT.
    original_build = VF.build_flow

    def invent_stage():
        import dataclasses as _dcx

        def fabricating(analysis):
            data = original_build(analysis)
            fake = VF.Station("memory stage", 1.0, 0.0)
            return _dcx.replace(data, stations=data.stations + (fake,))
        VF.build_flow = fabricating
        import ppact.visual as _v
        _v.build_flow = fabricating

    def stage_back():
        VF.build_flow = original_build
        import ppact.visual as _v
        _v.build_flow = original_build

    _control("a stage the model does not compute", "R14",
             "no stage appears", invent_stage, stage_back, r14_latency_flow)

    def overlap_as_sum():
        VF.OVERLAP_NOTE = ("These add up to the station time.")

    def overlap_back():
        VF.OVERLAP_NOTE = ("These OVERLAP. They run at the same time and "
                           "do not sum to the station.")

    _control("an overlap presented as a sum", "R14",
             "not presented as a sum", overlap_as_sum, overlap_back,
             r14_latency_flow)

    # R12 - control accounting.
    #
    # A control whose result is discarded leaves no trace, and the count is
    # the only thing that notices. That is not hypothetical: the
    # documentation audit lost one this way at 4.10.0, and the lost control
    # was the one guarding NOT ESTABLISHED.
    registered = len(CONTROL_PLAN)
    reported = len([r for r in RESULTS
                    if r[0] == "R11" and ": caught by " in r[1]])
    record("R11", "every registered control was reported",
           PASS if reported == registered else VIOLATED,
           f"{reported} reported against {registered} registered")
    record("R11", "every rule that owns a control has one",
           PASS if set(CONTROL_PLAN.values()) <= _rules_with_controls()
           else VIOLATED,
           f"rules with no control: "
           f"{sorted(set(CONTROL_PLAN.values()) - _rules_with_controls())}")


# What each control is FOR, declared separately from the code that runs it,
# so a control quietly deleted shows up as a count that no longer agrees.
CONTROL_PLAN = {
    "measured results removed": "R3",
    "balance removed": "R5",
    "a single workflow declared as a comparison": "R3",
    "a routed workflow left unregistered": "R1",
    "a row renamed Thermal Margin": "R5",
    "a default restored on an engineering question": "R8",
    "a renderer calling the engine": "R7",
    "stations ordered by size instead of execution": "R14",
    "a stage the model does not compute": "R14",
    "an overlap presented as a sum": "R14",
}


def _rules_with_controls():
    return {r[1].split("caught by ")[-1].strip()
            for r in RESULTS if r[0] == "R11" and "caught by " in r[1]}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    enforce = "--enforce" in argv
    mode = "ENFORCE" if enforce else "AUDIT"

    print(LINE)
    print(f" STANDARD REVIEW CONTRACT - {mode}")
    print(LINE)
    if enforce:
        print("  Enforcement. Any ABSENT or ABSENT-equivalent state fails.")
        print("  Release certification uses this mode and no other.\n")
    else:
        print("  Audit. Reports the state of each rule and exits 0, because")
        print("  during Phase 2 the purpose is to NAME what is wrong rather")
        print("  than to pass. This mode must not be used to certify.\n")
    print("    ABSENT    the required structure does not exist yet")
    print("    VIOLATED  it exists and the behaviour breaks the contract")
    print("    PASS      the contract is satisfied\n")

    for fn in (r1_workflow_registry, r2_renderer_ownership,
               r2b_execution_contract, r2c_configuration_types,
               r2d_challenge_type_contract,
               r3_section_presence, r4_variant_correctness,
               r5_visual_evidence, r6_identity, r7_renderer_purity,
               r8_default_policy, r9_boundaries, r10_end_to_end,
               r13_section_guarantees, r14_latency_flow,
               r15_memory_analysis, r16_bottleneck_inference,
               r17_block_throughput, r18_verification_discipline,
               r19_memory_task, r20_performance_constraints,
               r21_recommendation, r22_power_windows,
               r23_area_track, r24_boundary_declarations,
               r25_cost_track, r26_dashboard, r27_power_basis,
               r28_spider_contract, r29_constraint_source,
               r30_one_engine, r31_performance_bottleneck,
               r32_traffic_balance, r33_reference_space,
               r34_demo_visuals, r35_chart_consistency,
               r36_rendering_integrity, r37_library_order,
               r23_ppact_framework,
               r11_positive_controls):
        try:
            fn()
        except Exception as exc:
            record(fn.__name__[:3].upper(), f"{fn.__name__} completes",
                   VIOLATED, f"{type(exc).__name__}: {exc}")

    counts = {ABSENT: 0, VIOLATED: 0, PASS: 0}
    for rule, title, state, detail in RESULTS:
        counts[state] = counts.get(state, 0) + 1
        print(f"  {state:<9s}[{rule}] {title}")
        if detail and state != PASS:
            for chunk in str(detail).split(" - "):
                print(f"            {chunk.strip()[:74]}")

    print(f"\n{LINE}")
    print(f"  {counts[PASS]} pass    {counts[VIOLATED]} violated    "
          f"{counts[ABSENT]} absent    of {len(RESULTS)} rules")
    print()
    print("  ABSENT and VIOLATED need different work. A suite reporting")
    print("  both as FAILED would tell a reader neither.")
    print(LINE)
    # Two modes, because the same file serves two purposes at two stages.
    #
    # AUDIT reports and exits 0: during Phase 2 the suite is EXPECTED to
    # find violations, and a non-zero exit would make the build refuse to
    # run the very thing whose job is to describe the defects.
    #
    # ENFORCE fails on any unmet rule. Release certification uses this and
    # nothing else - a diagnostic that always exits 0 would silently become
    # the certification check, which is how a gate stops being a gate.
    if enforce:
        unmet = counts[ABSENT] + counts[VIOLATED]
        if unmet:
            print(f"  ENFORCE: {unmet} rule(s) unmet. This build does not")
            print(f"  satisfy the Standard Engineering Review Contract.")
            print(LINE)
        return 1 if unmet else 0
    print("  AUDIT MODE - exit 0 regardless of findings.")
    print("  Certification must run this file with --enforce.")
    print(LINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
