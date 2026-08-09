"""
ppact.menu_taxonomy - what kind of thing each menu entry is

WHY THIS EXISTS
===============
Twenty-eight menu entries sat in one list, and an earlier audit reported
that twenty-two of them "do not correspond to any workflow_id". That
framing was wrong: a validation summary, an industry case reader and a
grading rubric are not defective workflows, they are not workflows at
all. The defect was never that they lack a workflow id - it was that
nothing told a reader which kind of thing they had opened.

    WORKFLOW    a staged analysis: question -> answer -> result
    REFERENCE   material to read: examples, notes, documentation
    UTILITY     a tool that does one job: validate, export, check
    SYSTEM      about the program itself: version, scope, licence

Only WORKFLOW gets a staged interface and the common output contract.
Forcing "Step 3 of 8" onto a rubric would be inventing a structure that
is not there.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

WORKFLOW = "Workflow"
REFERENCE = "Reference"
UTILITY = "Utility"
SYSTEM = "System"

KINDS = (WORKFLOW, REFERENCE, UTILITY, SYSTEM)

KIND_MEANING = {
    WORKFLOW: "a staged analysis: it asks, you answer, and it ends in a "
              "result",
    REFERENCE: "material to read - examples, notes, documentation",
    UTILITY: "a tool that does one job and reports what it found",
    SYSTEM: "about the program itself",
}


@dataclass(frozen=True)
class Entry:
    """One menu entry, classified.

    `workflow_id` is filled only for WORKFLOW entries, and its absence
    elsewhere is not a gap - a reference page has no workflow because it
    is not one.
    """
    task_id: str
    title: str
    kind: str
    purpose: str
    workflow_id: str = ""
    required_input: str = ""
    expected_output: str = ""
    # HOW MANY STEPS, where the number is fixed.
    #
    # "step 3" alone does not say whether the end is near. Some
    # workflows ask a fixed set and can say "of 5"; what-if asks until
    # the reader chooses Done and cannot, so it says so rather than
    # inventing a total.
    steps: int = 0
    steps_vary: bool = False


ENTRIES: Tuple[Entry, ...] = (
    # ---------------------------------------------------------------
    # WORKFLOW - the eight registered analyses
    # ---------------------------------------------------------------
    Entry("task_quickstart", "Quick Start", WORKFLOW,
          "One design, analysed end to end, with nothing to choose.",
          "quick_start", "an application",
          "Standard Engineering Review", steps=1),
    Entry("task_game", "Step-by-Step Design", WORKFLOW,
          "Build a system one decision at a time, with the reason for "
          "each shown before you choose.",
          "education_step_by_step",
          "application, host, accelerator, memory, packages",
          "Standard Engineering Review", steps=9),
    Entry("task_custom", "Build a Custom Design", WORKFLOW,
          "Choose every part yourself and see the result.",
          "custom_design",
          "application and a full configuration",
          "Standard Engineering Review", steps=5),
    # THE REGISTRY NAMES THE ENTRY POINT, and it says task_guided.
    #
    # `education_guided_design` was mapped to `task_custom` on the
    # strength of its name. The registry declares its entry point, and
    # reading that would have shown the mismatch immediately.
    Entry("task_guided", "Guided Comparison", WORKFLOW,
          "Choose a baseline and a comparison, then think it through "
          "before reading the answer.",
          "education_guided_design",
          "application and two accelerator classes",
          "Comparative Review", steps=4),
    Entry("task_whatif", "Try a Change", WORKFLOW,
          "Change one thing at a time and see whether it helped.",
          "what_if", "a starting design and one change",
          "Comparative Review", steps_vary=True),
    Entry("task_review", "Review a Proposed Change", WORKFLOW,
          "Have a proposed change assessed before you make it.",
          "design_review", "a design and a proposal",
          "Comparative Review", steps=2),
    Entry("task_decide", "Explain This Result", WORKFLOW,
          "Find out why a figure is what it is.",
          "education_why_changed", "two designs",
          "Comparative Review", steps=7),
    Entry("task_challenge", "Take a Challenge", WORKFLOW,
          "Solve a set problem and see how it is marked.",
          "challenge", "a challenge and a configuration",
          "Standard Engineering Review with a mark", steps_vary=True),
    Entry("task_demo", "Demo Library", WORKFLOW,
          "A verified comparison, worked through.",
          "demo", "a demonstration",
          "Comparative Review with Comparison Closure", steps=1),

    # ---------------------------------------------------------------
    # REFERENCE - material to read
    # ---------------------------------------------------------------
    Entry("task_designs", "Example Designs", REFERENCE,
          "Designs that already work, to start from or to read."),
    Entry("task_lessons", "Learning Path", REFERENCE,
          "The course, in order. Each lesson stands alone."),
    Entry("task_innovation", "Innovation Challenge", REFERENCE,
          "An open brief: change what you like and write it up."),
    Entry("task_interpret", "Interpret a Result", REFERENCE,
          "How to read a result against what its application needs."),
    Entry("task_industry", "Industry Cases", REFERENCE,
          "What the model can and cannot express about real products."),
    Entry("task_memory", "Memory Technologies", REFERENCE,
          "Memory generations side by side, at component level."),
    Entry("task_memory_generations", "Memory Generations", REFERENCE,
          "HBM3E against HBM4 on a language model."),
    Entry("task_framework", "What This Model Analyses", REFERENCE,
          "What is inside the model, and what is not."),

    # ---------------------------------------------------------------
    # UTILITY - one job, one report
    # ---------------------------------------------------------------
    Entry("task_workspace", "Saved Designs", UTILITY,
          "Open, search and export designs you built earlier."),
    Entry("task_sweep", "Explore Design Space", UTILITY,
          "Search the space and rank what meets the requirements."),
    Entry("task_sensitivity", "How Solid Is This Result?", UTILITY,
          "How far a verdict survives its assumptions."),
    Entry("task_explain", "Why Did This Number Change?", UTILITY,
          "Attribute a difference to what caused it."),
    Entry("task_evaluate", "Evaluate Against Candidates", UTILITY,
          "Your application against the default candidates."),
    Entry("task_validation_summary", "Check What Was Verified", UTILITY,
          "What has been checked, and what has not."),
    Entry("task_reproducibility", "Reproduce a Run", UTILITY,
          "Whether a rerun agrees with the recorded one."),
    Entry("task_gold", "Gold Scenarios", UTILITY,
          "Reference cases and the results they must produce."),
    Entry("task_migration", "Migration Invariants", UTILITY,
          "What must still hold when a design moves platform."),
    Entry("task_rubric", "Instructor Tools", UTILITY,
          "Grading rubric and marking guidance."),

    # ---------------------------------------------------------------
    # SYSTEM
    # ---------------------------------------------------------------
    Entry("task_about", "About Studio", SYSTEM,
          "What this is, how to read it, and what it does not "
          "establish."),
)

BY_TASK: Dict[str, Entry] = {e.task_id: e for e in ENTRIES}


def of_kind(kind: str) -> List[Entry]:
    return [e for e in ENTRIES if e.kind == kind]


def workflow_entries() -> List[Entry]:
    """The staged analyses, and only those."""
    return of_kind(WORKFLOW)


def unregistered_workflows() -> List[str]:
    """Workflow entries whose id is not in the engine's registry."""
    from .review import ANALYSIS_WORKFLOWS
    known = {w.workflow_id for w in ANALYSIS_WORKFLOWS}
    return [e.workflow_id for e in workflow_entries()
            if e.workflow_id not in known]


def unexposed_workflow_ids() -> List[str]:
    """Registered workflows no menu entry reaches."""
    from .review import ANALYSIS_WORKFLOWS
    exposed = {e.workflow_id for e in workflow_entries()}
    return [w.workflow_id for w in ANALYSIS_WORKFLOWS
            if w.workflow_id not in exposed]
