"""
ppact.outcome - what a workflow returns when it finishes

WHY THIS IS EXPLICIT
====================
An earlier attempt read a workflow's configuration by replacing
`build_review` and `evaluate_system` while it ran and recording the
arguments. That worked and it should not survive: it made the report
depend on which module bound which name, on the order of calls, and on
the last capture happening to be the final design.

The evidence was immediate. Watching `build_review` alone missed
`task_custom`, which reaches the engine another way. Patching
`system.evaluate_system` still missed it, because `workflow` had already
bound the name. Each fix was another module to remember.

    workflow    decides what was configured, and says so
    view data   computes
    renderer    displays

A workflow now returns this object. Nothing infers it.

THIS IS A DTO
-------------
Data and nothing else. No engine call, no computation, no rendering. A
result object that can compute is a result object that eventually does,
and then the boundary this file exists to draw is gone.

STARTING POINT AND CURRENT DESIGN ARE DECLARED
----------------------------------------------
Which design is the reference is a decision the workflow makes, not
something to be worked out from the order two configurations happened to
be evaluated in. A single-design workflow has no starting point and says
so with None; a comparison has both and names them.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class WorkflowVariant(str, Enum):
    """Single design, or a design against a reference.

    An Enum rather than a string: `variant="comparision"` passed every
    check and produced a report with no reference, because nothing was
    comparing it against a known set.
    """
    SINGLE = "single"
    COMPARISON = "comparison"


class WorkflowStatus(str, Enum):
    """How the workflow ended.

    CANCELLED and FAILED are separate from IN_PROGRESS: a user who left
    and a workflow that broke are different facts, and a screen that
    conflates them tells the reader the wrong thing.
    """
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


# Retained so existing call sites read the same. No new code uses them.
SINGLE = WorkflowVariant.SINGLE
COMPARISON = WorkflowVariant.COMPARISON
COMPLETE = WorkflowStatus.COMPLETED
IN_PROGRESS = WorkflowStatus.IN_PROGRESS


@dataclass(frozen=True)
class SelectedAnswer:
    """One question and what the user chose, in their words.

    `label` is what the screen showed - "Cortex-A78 x4", not "1". A
    trace of index numbers cannot be read a week later, and cannot
    survive an option being reordered.
    """
    step: int
    question: str
    label: str
    value: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class WorkflowOutcome:
    """What a workflow produced. The only thing a report is built from.

    `current_config` is the design the report is about.
    `starting_config` is the reference it is compared against, and is
    None for a single-design workflow - not an empty config, because an
    empty config is a design and None is the absence of one.
    """
    workflow_id: str
    status: WorkflowStatus
    variant: WorkflowVariant
    app_key: str
    current_config: Optional[Any]
    starting_config: Optional[Any] = None
    selected_answers: Tuple[SelectedAnswer, ...] = ()
    # NAMES, not a count. "6" says a workflow took six steps; the names
    # say which decisions the design rests on.
    completed_steps: Tuple[str, ...] = ()
    note: str = ""

    def __post_init__(self):
        if not isinstance(self.variant, WorkflowVariant):
            raise TypeError(
                f"variant must be a WorkflowVariant, got "
                f"{self.variant!r}")
        if not isinstance(self.status, WorkflowStatus):
            raise TypeError(
                f"status must be a WorkflowStatus, got {self.status!r}")
        # A COMPARISON WITHOUT A REFERENCE IS NOT A COMPARISON, and a
        # single design with one is a comparison nobody declared. Both
        # were possible while the identity was inferred.
        if (self.variant is WorkflowVariant.COMPARISON
                and self.starting_config is None):
            raise ValueError(
                f"{self.workflow_id}: a comparison must name its "
                f"starting point")
        if (self.variant is WorkflowVariant.SINGLE
                and self.starting_config is not None):
            raise ValueError(
                f"{self.workflow_id}: a single-design outcome must not "
                f"carry a starting point")
        if (self.status is WorkflowStatus.COMPLETED
                and self.current_config is None):
            raise ValueError(
                f"{self.workflow_id}: a completed workflow must return "
                f"a configuration")

    @property
    def comparative(self) -> bool:
        return self.variant is WorkflowVariant.COMPARISON

    # --- serialisation ------------------------------------------------
    #
    # A result that cannot be written down cannot be saved, revisited,
    # shared or replayed - and History, which the menu already lists as
    # planned, needs exactly this.

    def to_dict(self) -> Dict[str, Any]:
        def cfg(c):
            return None if c is None else dataclasses.asdict(c)
        return {
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "variant": self.variant.value,
            "app_key": self.app_key,
            "current_config": cfg(self.current_config),
            "starting_config": cfg(self.starting_config),
            "selected_answers": [a.to_dict()
                                 for a in self.selected_answers],
            "completed_steps": list(self.completed_steps),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowOutcome":
        from .system import SystemConfig

        def cfg(v):
            return None if v is None else SystemConfig(**v)
        return cls(
            workflow_id=d["workflow_id"],
            status=WorkflowStatus(d["status"]),
            variant=WorkflowVariant(d["variant"]),
            app_key=d["app_key"],
            current_config=cfg(d["current_config"]),
            starting_config=cfg(d["starting_config"]),
            selected_answers=tuple(
                SelectedAnswer(**a) for a in d["selected_answers"]),
            completed_steps=tuple(d["completed_steps"]),
            note=d.get("note", ""))


def single(workflow_id: str, app_key: str, config,
           answers: Tuple[SelectedAnswer, ...] = (),
           steps: Tuple[str, ...] = (),
           note: str = "") -> WorkflowOutcome:
    return WorkflowOutcome(
        workflow_id=workflow_id, status=WorkflowStatus.COMPLETED,
        variant=WorkflowVariant.SINGLE, app_key=app_key,
        current_config=config, selected_answers=answers,
        completed_steps=steps or tuple(a.question for a in answers),
        note=note)


def comparison(workflow_id: str, app_key: str, starting, current,
               answers: Tuple[SelectedAnswer, ...] = (),
               steps: Tuple[str, ...] = (),
               note: str = "") -> WorkflowOutcome:
    return WorkflowOutcome(
        workflow_id=workflow_id, status=WorkflowStatus.COMPLETED,
        variant=WorkflowVariant.COMPARISON, app_key=app_key,
        current_config=current, starting_config=starting,
        selected_answers=answers,
        completed_steps=steps or tuple(a.question for a in answers),
        note=note)


def in_progress(workflow_id: str, app_key: str = "",
                answers: Tuple[SelectedAnswer, ...] = ()
                ) -> WorkflowOutcome:
    """A workflow that has not finished. It has no report yet."""
    return WorkflowOutcome(
        workflow_id=workflow_id, status=WorkflowStatus.IN_PROGRESS,
        variant=WorkflowVariant.SINGLE, app_key=app_key,
        current_config=None, selected_answers=answers,
        completed_steps=tuple(a.question for a in answers))


def cancelled(workflow_id: str, app_key: str = "") -> WorkflowOutcome:
    """A user who left. Not a failure, and not still running."""
    return WorkflowOutcome(
        workflow_id=workflow_id, status=WorkflowStatus.CANCELLED,
        variant=WorkflowVariant.SINGLE, app_key=app_key,
        current_config=None)
