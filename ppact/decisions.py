"""
ppact.decisions - configuration diff normalised to design decisions

CONFIGURATION DIFF IS NOT DESIGN DECISION DIFF
==============================================
Adding a second engine sets `secondary_compute`, `execution_mode` and
`work_split`. Shrinking the process sets `accel_node` and `soc_node`.
Counting fields calls the first three changes and the second two; a
reader made one decision each time.

A check written on raw fields therefore reports demonstrations as
mixed when they are not, and a legend written on raw fields spills
internal parameters onto a chart. Both want the decision.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

# One decision, the fields it moves, and how to say it on a chart.
#
# `fields` is the set a decision touches. A decision is recognised when
# every field it owns has changed; the remaining fields are then taken
# from what is left, so an unlisted field is reported rather than
# silently folded into a neighbouring decision.
# A DEFINING FIELD, AND THE FIELDS THAT RIDE WITH IT.
#
# Requiring every field of a decision to differ missed the decision
# whenever one of them happened to match: adding a second engine sets
# `work_split` to 0.5 and the design without one already carries 0.5 as
# its default, so "all three differ" was false and the change was
# reported as two unclassified fields instead of one decision.
#
# The first field is the one that defines the decision. The rest are
# absorbed when they also differ, and ignored when they do not.
DECISIONS: Tuple[Tuple[str, frozenset, str], ...] = (
    ("ADD_SECOND_ENGINE",
     frozenset({"secondary_compute"}),
     "second engine"),
    ("CHANGE_PROCESS_NODE",
     frozenset({"accel_node"}), "process node"),
    ("CHANGE_ACCELERATOR", frozenset({"compute"}), "accelerator"),
    ("CHANGE_HOST", frozenset({"cpu"}), "host processor"),
    ("CHANGE_MEMORY_TECHNOLOGY", frozenset({"memory"}), "memory"),
    ("CHANGE_PACKAGE_COUNT",
     frozenset({"memory_devices"}), "memory packages"),
    ("MOVE_PREPROCESSING",
     frozenset({"preprocessing_mode"}), "preprocessing"),
    ("CHANGE_HOST_CONNECTION",
     frozenset({"host_connection"}), "host connection"),
    ("CHANGE_OFFLOAD_BATCHING",
     frozenset({"offload_batching"}), "offload batching"),
)

# Fields that move because a decision was taken, not as decisions.
RIDERS: Dict[str, frozenset] = {
    "ADD_SECOND_ENGINE": frozenset({"execution_mode", "work_split",
                                    "alternative_share"}),
    "CHANGE_PROCESS_NODE": frozenset({"soc_node"}),
}

BY_ID = {d[0]: d for d in DECISIONS}


def field_diff(a: Dict, b: Dict) -> List[str]:
    """Which configuration fields differ, ignoring absent-vs-None."""
    keys = set(a) | set(b)
    return sorted(k for k in keys if a.get(k) != b.get(k))


def decisions_between(a: Dict, b: Dict) -> List[str]:
    """The design decisions two configurations differ by.

    Returns decision ids. A field belonging to no declared decision is
    returned as `UNCLASSIFIED:<field>` rather than dropped: an
    unrecognised change is a gap in this table, and hiding it would
    make the table look complete.
    """
    remaining = set(field_diff(a, b))
    found: List[str] = []
    for did, fields, _label in DECISIONS:
        if fields <= remaining:
            found.append(did)
            remaining -= fields
            remaining -= RIDERS.get(did, frozenset())
    for field in sorted(remaining):
        found.append(f"UNCLASSIFIED:{field}")
    return found


def describe(a: Dict, b: Dict) -> str:
    """What changed, in the words a designer would use.

    Short enough for a chart legend: the decision, not its fields.
    """
    parts = []
    for did in decisions_between(a, b):
        if did.startswith("UNCLASSIFIED:"):
            parts.append(did.split(":", 1)[1].replace("_", " "))
            continue
        parts.append(BY_ID[did][2])
    return ", ".join(parts)


def config_of(obj) -> Dict:
    """A plain dict from a SystemConfig or a mapping."""
    import dataclasses
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if dataclasses.is_dataclass(obj):
        return {k: v for k, v in dataclasses.asdict(obj).items()
                if v is not None}
    return {}


def decision_summary(a, b) -> str:
    """`describe`, accepting SystemConfig objects."""
    return describe(config_of(a), config_of(b))
