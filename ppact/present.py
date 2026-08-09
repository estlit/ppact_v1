"""
ppact.present - show a finished workflow, whichever interface is running

WHY ONE ENTRY POINT
===================
Terminal and notebook each called `render_standard_engineering_review`
directly, so the panels a reader saw depended on what that function drew
rather than on the report contract. Streamlit had already moved to the
common builder, which left the product with two answers to the same
question.

    outcome -> build_engineering_report -> adapter

A workflow calls `present(outcome)` and stops caring where it is
running. Which adapter runs is decided here, once.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from typing import Optional

from .outcome import WorkflowOutcome, WorkflowStatus


def present(outcome: Optional[WorkflowOutcome]) -> bool:
    """Build the report for a completed workflow and show it.

    Returns False when there is nothing to show, and says why rather
    than printing an empty screen.
    """
    if not isinstance(outcome, WorkflowOutcome):
        print("\n  This workflow returned no result, so there is no "
              "report to show.")
        return False
    if outcome.status is not WorkflowStatus.COMPLETED:
        print(f"\n  {outcome.workflow_id}: {outcome.status.value}. "
              f"A report needs a completed workflow.")
        return False

    from .engineering_report import build_engineering_report
    report = build_engineering_report(outcome)

    try:
        from .core import in_notebook
        notebook = bool(in_notebook())
    except Exception:
        notebook = False

    if notebook:
        from .report_render import render_report_jupyter
        if render_report_jupyter(report):
            return True
        # IPython missing is not a reason to show nothing.

    from .report_render import render_report_text
    for line in render_report_text(report):
        print(line)
    return True
