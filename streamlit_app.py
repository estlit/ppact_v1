"""
PPACT Studio - Streamlit front end

    streamlit run streamlit_app.py

THIS FILE DISPLAYS. IT DOES NOT COMPUTE.
========================================
Every figure comes from `ppact.view_data`, which the notebook path uses
too. A Streamlit app that computed its own ratios would be a second
engine, and two engines disagree the moment one of them is edited - as a
user reporting different numbers in two places, which is the hardest kind
of defect to reproduce.

The rule is checkable: this file imports `view_data` and the chart
renderers, and nothing else from `ppact`.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from ppact.view_data import (build_demo_view, demo_index,
                             NOT_APPLICABLE)

# The seven verbs, from UI-R4. History has no entries and says so rather
# than looking available.
WORKFLOW = (
    ("Start", "Create or open a design."),
    ("Analyze", "Understand how your design performs and what limits "
                "it."),
    ("Improve", "Try changes and see whether they help."),
    ("Compare", "Put designs side by side and see what differs."),
    ("History", "See how your design changed."),
    ("Learn", "Work through the material, from first lesson to "
              "challenge."),
    ("Verify", "Confirm the analysis is sound and reproducible."),
)
PLANNED = {"History": "Coming in a future release."}

# ORDER: what was measured, then why, then the balance, then the prose.
#
# The explanation was third and is a document about the product rather
# than a reading of this design - a reader who opens it before the flow
# has been given the conclusion before the evidence.
CHART_ORDER = ("measured", "flow", "bottleneck", "spider")
CHART_TITLE = {"measured": "Measured Results",
               "flow": "System Flow",
               "bottleneck": "Bottleneck Analysis",
               "spider": "Architecture Balance"}


def _safe(fn, label):
    """Render one chart. A failure here loses one panel, not the page."""
    try:
        return fn(), ""
    except Exception:
        return None, traceback.format_exc().strip().splitlines()[-1]


def sidebar() -> str:
    """Four headings, not seven verbs.

    The seven-verb menu mixed staged analyses with documents and tools,
    so a reader could not tell which kind of thing an entry was until
    they opened it.
    """
    from ppact.menu_taxonomy import KINDS, of_kind, KIND_MEANING

    st.sidebar.markdown("### PPACT Studio")
    st.sidebar.caption("Constraint-Based Design Assessment")

    sections = ["Home"] + [
        f"{k}  ({len(of_kind(k))})" for k in KINDS]

    # THE SELECTION IS STATE, NOT AN ARGUMENT.
    #
    # This passed `index=0` on every run with no `key`, so any rerun
    # forced the radio back to Home. Answering a question calls
    # `st.rerun()`, which meant choosing an application in Quick Start
    # returned the reader to the front page instead of showing the
    # report - and the workflow could never be finished by hand.
    #
    # The automated walks did not see it: they read the DOM after each
    # click and the app had already re-rendered from Home, so the walk
    # simply found the next question there. A harness that follows
    # whatever is on screen cannot tell being advanced from being sent
    # back.
    #
    # With a `key`, Streamlit owns the selection and `index` is passed
    # only when something else asks for a jump.
    KEY = "section_choice"
    jump = st.session_state.pop("jump_kind", "")
    if jump:
        target = next((s for s in sections if s.startswith(jump)),
                      sections[0])
        st.session_state[KEY] = target
    if KEY not in st.session_state:
        st.session_state[KEY] = sections[0]
    choice = st.sidebar.radio("Sections", sections, key=KEY,
                              label_visibility="collapsed")
    picked = choice.split("  (")[0]
    if picked != "Home":
        st.sidebar.caption(KIND_MEANING[picked])

    # THE LIMITS BELONG ON THE SCREEN.
    #
    # A README nobody opens is a README nobody read. Anyone who reaches a
    # figure in this app should be able to see, without leaving it, that
    # no figure here has been compared against measured hardware.
    st.sidebar.divider()
    st.sidebar.caption("**Public preview**")
    st.sidebar.caption(
        "Analytical model. No figure in this tool has been compared "
        "against a measured system, and no external party has reviewed "
        "it.")
    with st.sidebar.expander("What is not established"):
        st.caption(
            "**Power (PW-Q1).** Whether the power budget is a sustained "
            "or an instantaneous limit is unanswered, so no power "
            "verdict is issued anywhere.")
        st.caption(
            "**Memory arbitration (MEM-ARB-001).** The host memory "
            "demand model is not established; results involving "
            "host-accelerator contention inherit that.")
        st.caption(
            "**Traffic (TR-D1).** Traffic balance is established. The "
            "other nine components of the definition are not.")
        st.caption(
            "Recommendations identify structurally relevant "
            "comparisons. They do not predict a winning design until "
            "the comparison is executed.")
        st.caption("The full register is DEFERRED.md.")

    from ppact.view_data import engine_provenance
    prov = engine_provenance()
    st.sidebar.caption(f"engine {prov['engine']}  ·  model "
                       f"{prov['digest']}")
    return picked



def home_page():
    """What to do first.

    A reader arriving at a seven-verb sidebar has to work out which verb
    contains the thing they want. This asks the question they actually
    have.
    """
    st.title("PPACT Studio")
    st.caption("Constraint-based design assessment for AI hardware "
               "systems")
    st.markdown("### What would you like to do?")

    CHOICES = (
        ("Analyse an AI system",
         "One design, from configuration to conclusion.",
         "Workflow", "task_quickstart"),
        ("Build a design step by step",
         "One decision at a time, with the reason for each.",
         "Workflow", "task_game"),
        ("Try a change and see whether it helped",
         "Change one thing; compare before and after.",
         "Workflow", "task_whatif"),
        ("Explore the demonstration library",
         "Fifteen worked questions, each a verified comparison.",
         "Workflow", "task_demo"),
        ("Read the material",
         "Lessons, worked examples and technology notes.",
         "Reference", ""),
        ("Check the analysis",
         "What has been verified, and what has not.",
         "Utility", ""),
    )
    for label, note, kind, task in CHOICES:
        c1, c2 = st.columns([5, 1])
        c1.markdown(f"**{label}**  \n{note}")
        c1.caption(kind)
        if c2.button("Open", key=f"home_{label[:14]}"):
            st.session_state["jump_kind"] = kind
            st.session_state["jump_task"] = task
            st.rerun()

    st.divider()
    st.caption("Everything else is under the headings on the left. "
               "Workflow items ask questions and end in a result; "
               "Reference items are material to read; Utility items do "
               "one job and report what they found.")


def kind_page(kind: str):
    """Every entry of one kind, and nothing of another."""
    from ppact.menu_taxonomy import of_kind, KIND_MEANING

    st.title(kind)
    st.caption(KIND_MEANING[kind])

    entries = of_kind(kind)
    if not entries:
        st.info("Nothing here yet.")
        return

    labels = [e.title for e in entries]

    # THE SAME TRAP AS THE SIDEBAR. `index` beside a `key` re-asserts a
    # position on every run, so a rerun could send the reader back to
    # the first task in the list. The jump writes the state and `index`
    # is not passed at all.
    key = f"pick_{kind}"
    jump = st.session_state.pop("jump_task", "")
    if jump:
        wanted = next((e.title for e in entries
                       if e.task_id == jump), labels[0])
        st.session_state[key] = wanted
    if key not in st.session_state:
        st.session_state[key] = labels[0]
    pick = st.selectbox("Choose one", labels, key=key)
    entry = entries[labels.index(pick)]
    st.caption(entry.purpose)

    if entry.kind == "Workflow":
        workflow_run(entry)
    else:
        plain_run(entry)



# THE COMMON OUTPUT CONTRACT.
#
# A finished analysis shows the same things in the same order whichever
# workflow produced it. Some menus ending in a table and others in a
# spider is what made the result screen feel like a different program.
RESULT_PANELS = (
    ("Configuration", r"CONFIGURATION|Architecture Summary|"
                      r"Current design|CURRENT DESIGN"),
    ("Measured Results", r"MEASURED RESULTS|Measured Results"),
    ("System Flow", r"SYSTEM FLOW|System Flow"),
    ("Bottleneck", r"BOTTLENECK|Bottleneck|limiting"),
    ("Architecture Balance", r"ARCHITECTURE BALANCE|"
                             r"Architecture Balance|Relative PPACT|"
                             r"BALANCE"),
    ("Engineering Conclusion", r"ENGINEERING CONCLUSION|"
                               r"Engineering conclusion"),
    ("Recommended Next Comparisons", r"RECOMMENDED NEXT|"
                                     r"Recommended next"),
)


def _answers_key(task_id):
    return f"answers_{task_id}"


def workflow_run(entry):
    """A staged analysis: where you are, what you chose, what is next.

    ONE SHAPE FOR EVERY WORKFLOW, including the demonstration library.
    A reader who meets a different interface inside one product meets
    two products; the demonstrations differ in their DATA, not in how
    they are navigated or what they end with.
    """
    import re
    from ppact.text_capture import run_task, options_from

    if entry.task_id == "task_demo":
        demo_workflow()
        return

    akey = _answers_key(entry.task_id)
    if akey not in st.session_state:
        st.session_state[akey] = []
    answers = st.session_state[akey]

    run = run_task(entry.task_id, answers)

    # WHERE YOU ARE. A reader who cannot see the step cannot tell
    # whether the thing is nearly done or has not started.
    if run.completed:
        st.markdown(f"**{entry.title}**  ·  complete")
    else:
        # "step 3" does not say whether the end is near. Where the total
        # is fixed it is shown; where it depends on the reader's own
        # choices, saying so beats inventing a number.
        step_no = len(answers) + 1
        if entry.steps:
            st.markdown(f"**{entry.title}**  ·  step {step_no} of "
                        f"{entry.steps}")
            st.progress(min(step_no / entry.steps, 1.0))
        elif entry.steps_vary:
            st.markdown(f"**{entry.title}**  ·  step {step_no}")
            st.caption("This workflow runs until you choose to finish, "
                       "so there is no fixed number of steps.")
        else:
            st.markdown(f"**{entry.title}**  ·  step {step_no}")
    st.caption(f"workflow `{entry.workflow_id}`  ·  ends in "
               f"{entry.expected_output}")

    # WHAT YOU CHOSE. Without it a reader three steps in has no record
    # of the decisions the result rests on.
    if answers:
        with st.expander(f"Your choices so far ({len(answers)})",
                         expanded=False):
            for i, a in enumerate(answers, 1):
                lbl = st.session_state.get(f"label_{entry.task_id}_{i}",
                                           f"option {a}")
                st.caption(f"{i}. {lbl}")

    # WIDE ENOUGH FOR THE WORDS.
    #
    # At 768 px two narrow columns split "Back" into "Bac / k" and
    # "Restart" into "Res / tart": a column narrower than its label
    # wraps per character.
    c1, c2, _c3 = st.columns([2, 2, 3])
    if c1.button("Back", key=f"back_{entry.task_id}",
                 disabled=not answers, use_container_width=True):
        answers.pop()
        st.rerun()
    if c2.button("Restart", key=f"restart_{entry.task_id}",
                 disabled=not answers, use_container_width=True):
        st.session_state[akey] = []
        st.rerun()

    if run.error:
        st.error(f"{entry.title} stopped: {run.error}")
        return
    if run.truncated:
        st.warning("This workflow asked more questions than a session "
                   "allows and was stopped. Use Restart.")
        return

    if run.needs_input:
        from ppact.text_capture import parse_question
        q = parse_question(run.questions[-1])
        if not q.options:
            st.error("This step asked something with no readable "
                     "options.")
            st.code(run.text, language=None)
            return

        # THE QUESTION ONCE, NOT TWICE.
        #
        # The whole transcript went on screen and the options were then
        # rendered again as radios - the same nine items twice, which
        # makes a reader check whether the two lists agree. The heading
        # and its explanation are shown; the numbered list is the
        # radios.
        if q.title:
            st.markdown(f"### {q.title}")
        # PARAGRAPHS, NOT SOURCE LINES.
        #
        # The prose arrives wrapped at the terminal's width, and one
        # caption per line broke sentences in half with a paragraph gap
        # in the middle: "...designed for. The" / "application supplies
        # the workload...". Lines are rejoined and split on blanks.
        para = " ".join(q.prose)
        for chunk in [c.strip() for c in para.split("  ") if c.strip()]:
            st.caption(chunk)

        # AN EXIT IS NOT A CHOICE.
        #
        # The terminal puts "Back" last in its numbered list, so it
        # arrived as a radio option beside the real answers - and the
        # screen already has a Back button meaning something else. A
        # reader choosing the radio Back to step back would have left
        # the workflow instead.
        EXITS = ("back", "quit", "exit", "cancel", "return", "done"
                 if entry.steps_vary else "\x00")
        answerable = [(i, o) for i, o in enumerate(q.options)
                      if not o.strip().lower().startswith(EXITS)]
        exits = [(i, o) for i, o in enumerate(q.options)
                 if o.strip().lower().startswith(EXITS)]

        labels = [o for _i, o in answerable]
        picked = st.radio("Choose one", labels, index=None,
                          key=f"opt_{entry.task_id}_{len(answers)}")
        choice = picked

        def _go():
            st.session_state[f"label_{entry.task_id}_"
                             f"{len(answers) + 1}"] = choice
            answers.append(str(q.options.index(choice) + 1))

        def _exit(index, label):
            st.session_state[f"label_{entry.task_id}_"
                             f"{len(answers) + 1}"] = label
            answers.append(str(index + 1))

        # ONE CONTINUE, BELOW THE OPTIONS.
        #
        # There were two, above and below, so a nine-option list would
        # not push the button off the screen. Two buttons with one label
        # read as a fault: a reader cannot tell whether they do the same
        # thing, and one of them appeared before the options it was
        # meant to confirm.
        #
        # NOT CHOSEN IS NOT CHOSEN. A pre-selected first option lets a
        # reader continue without deciding and records it as a decision.
        if st.button("Continue", key=f"go_{entry.task_id}_"
                                     f"{len(answers)}",
                     disabled=choice is None, type="primary",
                     use_container_width=True):
            _go()
            st.rerun()

        # The exits, named and separated, below the answers.
        if exits:
            st.caption("Or leave this step:")
            cols = st.columns(min(len(exits), 3))
            for n, (idx, label) in enumerate(exits):
                if cols[n % len(cols)].button(
                        label, key=f"exit_{entry.task_id}_"
                                   f"{len(answers)}_{idx}",
                        use_container_width=True):
                    _exit(idx, label)
                    st.rerun()

        with st.expander("Full transcript"):
            st.code(run.text, language=None)
        return

    # --- complete -----------------------------------------------------
    #
    # THE REPORT COMES FROM THE COMMON BUILDER.
    #
    # This used to scan what the task printed for panel names, so a task
    # that drew no System Flow left the screen without one and the
    # screen reported it as missing. What the task printed is now the
    # transcript; the report is built from the outcome.
    from ppact.outcome import WorkflowOutcome, WorkflowStatus
    from ppact.engineering_report import build_engineering_report
    from ppact.report_render import render_report_streamlit

    outcome = run.outcome
    if not isinstance(outcome, WorkflowOutcome):
        st.error(f"{entry.title} finished without returning a result. "
                 f"A workflow must return a WorkflowOutcome; this one "
                 f"returned {type(outcome).__name__}.")
        st.code(run.text, language=None)
        return
    if outcome.status is not WorkflowStatus.COMPLETED:
        st.info(f"{entry.title}: {outcome.status.value}. No report is "
                f"produced for a workflow that did not complete.")
        st.code(run.text, language=None)
        return

    st.success("Analysis complete.")
    report = build_engineering_report(outcome)
    render_report_streamlit(report, st)
    if report.missing:
        st.warning("Panels that could not be built: "
                   + ", ".join(report.missing))
    with st.expander("Transcript"):
        st.code(run.text, language=None)


def plain_run(entry):
    """Reference and utility: no steps, no contract, just the thing."""
    from ppact.text_capture import run_task, options_from

    akey = _answers_key(entry.task_id)
    if akey not in st.session_state:
        st.session_state[akey] = []
    answers = st.session_state[akey]

    run = run_task(entry.task_id, answers)
    if answers and st.button("Start again",
                             key=f"again_{entry.task_id}"):
        st.session_state[akey] = []
        st.rerun()

    if run.error:
        st.error(f"{entry.title} stopped: {run.error}")
        return
    if run.truncated:
        st.warning("This page asked more questions than a session "
                   "allows and was stopped.")
        return

    if run.text.strip():
        st.code(run.text, language=None)
    for path in run.images:
        if os.path.isfile(path):
            st.image(path, use_container_width=True)

    if run.needs_input:
        opts = options_from(run.questions[-1])
        if not opts:
            st.error("This page asked something with no readable "
                     "options.")
            return
        choice = st.radio("Choose one", opts, index=None,
                          key=f"popt_{entry.task_id}_{len(answers)}")
        if st.button("Show", key=f"pgo_{entry.task_id}_{len(answers)}",
                     disabled=choice is None, type="primary"):
            answers.append(str(opts.index(choice) + 1))
            st.rerun()


def demo_workflow():
    """The demonstration library.

    THE SELECTION IS DEMO-SPECIFIC. THE REPORT IS NOT.

    Choosing which demonstration to read, and its question, family and
    difficulty, are the library's own. Everything after the choice goes
    through the same builder and the same adapter as every workflow -
    a screen that assembled its own Measured Results and its own
    Architecture Balance is how a product becomes two products.
    """
    from ppact.view_data import demo_index, demo_outcome
    from ppact.engineering_report import build_engineering_report
    from ppact.report_render import render_report_streamlit

    index = demo_index()
    labels = [q for _n, q, _f, _d in index]
    if "demo_pick" not in st.session_state:
        st.session_state["demo_pick"] = 0

    st.markdown("**Demo Library**")
    st.caption("workflow `demo`  ·  ends in Comparative Review with "
               "Comparison Closure")

    c1, c2, c3 = st.columns([1, 6, 1])
    if c1.button("◀", disabled=st.session_state["demo_pick"] == 0,
                 help="Previous"):
        st.session_state["demo_pick"] -= 1
        st.rerun()
    if c3.button("▶",
                 disabled=st.session_state["demo_pick"] >= len(index) - 1,
                 help="Next"):
        st.session_state["demo_pick"] += 1
        st.rerun()
    pick = c2.selectbox("Choose a demonstration", labels,
                        index=st.session_state["demo_pick"],
                        label_visibility="collapsed")
    st.session_state["demo_pick"] = labels.index(pick)

    n, question, family, difficulty = index[st.session_state["demo_pick"]]
    st.title(question)
    st.caption(f"Demo {n:03d}  ·  {family}  ·  {difficulty}")

    outcome = demo_outcome(n)

    st.success("Analysis complete.")
    report = build_engineering_report(outcome)
    render_report_streamlit(report, st)
    if report.missing:
        st.warning("Panels that could not be built: "
                   + ", ".join(report.missing))

    # DEMO METADATA ONLY. The prose belongs to the demonstration; the
    # panels do not.
    from ppact.view_data import build_demo_view
    view = build_demo_view(n)
    with st.expander("What this demonstration does not establish"):
        st.markdown(view.explanation_sections.get(
            "What this demonstration does not establish", "-"))



def main():
    st.set_page_config(page_title="PPACT Studio", layout="wide",
                       initial_sidebar_state="expanded")
    picked = sidebar()
    if picked == "Home":
        home_page()
    else:
        kind_page(picked)


main()
