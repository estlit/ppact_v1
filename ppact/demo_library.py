"""
ppact.demo_library - the fifteen as one library

Individual QA asks whether a demonstration is right. This asks whether the
set is a set: whether the lessons repeat, whether the axes are covered,
whether a reader can go from one to fifteen without needing sixteen.

WHY A FAMILY AND A DIFFICULTY ARE DECLARED, NOT DERIVED
=======================================================
Nothing in the demo data says a demonstration is about memory or is
advanced. Deriving a family from the changed configuration field would
call 011 and 012 the same thing - both change package count - when one is
about bandwidth and the other about a capacity failure.

These are editorial, one line each, written where they can be argued with.

FORWARD REFERENCES
------------------
A demonstration may POINT at a later one; it may not DEPEND on one. The
difference is which section the reference sits in:

    in "what this does not establish"   a pointer - fine
    in the evidence or the reasoning    a dependency - an ordering fault

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

EASY, MEDIUM, ADVANCED = "Easy", "Medium", "Advanced"

FAMILIES = ("Memory", "Node", "Parallel", "Host", "Placement",
            "Traffic", "Packaging")


@dataclass(frozen=True)
class LibraryEntry:
    number: int
    key: str
    family: str
    difficulty: str
    primary_axis: str
    secondary_axes: Tuple[str, ...]
    complexity: str          # what a reader must hold at once
    why_it_matters: str


LIBRARY: Tuple[LibraryEntry, ...] = (
    LibraryEntry(1, "memory", "Memory", EASY, "Performance",
                 ("Cost",), "one decision, two designs",
                 "The most visible upgrade on a datasheet, priced "
                 "against what it actually bought."),
    LibraryEntry(2, "engine", "Parallel", EASY, "Traffic",
                 ("Performance",), "one decision, three designs, a turn",
                 "The first place a designer spends, and the point where "
                 "spending more stops working."),
    LibraryEntry(3, "dual", "Parallel", MEDIUM, "Traffic",
                 ("Performance",), "one decision, a shared resource",
                 "Why two of something is not twice something."),
    LibraryEntry(4, "node", "Node", MEDIUM, "Area",
                 ("Performance",), "one decision, three designs",
                 "A year of a team's work, and what it moves."),
    LibraryEntry(5, "order", "Placement", MEDIUM, "Area",
                 ("Performance", "Cost"),
                 "three options against a baseline",
                 "How to choose between upgrades rather than buying the "
                 "largest."),
    LibraryEntry(6, "finest", "Node", ADVANCED, "Area",
                 ("Performance", "Cost"),
                 "three designs, a turn in performance",
                 "Where the assumption that finer is faster stops "
                 "holding."),
    LibraryEntry(7, "together", "Parallel", ADVANCED, "Cost",
                 ("Performance",), "TWO decisions, four designs",
                 "That upgrades have an order, and the order matters "
                 "more than either one."),
    LibraryEntry(8, "shipping", "Traffic", MEDIUM, "Traffic",
                 ("Cost", "Power"), "one decision, four gates",
                 "That a well-balanced design can still fail its checks."),
    LibraryEntry(9, "host", "Host", EASY, "Performance",
                 ("Cost",), "one decision, two designs",
                 "That the accelerator is not automatically the "
                 "suspect."),
    LibraryEntry(10, "offload", "Placement", MEDIUM, "Area",
                 ("Performance", "Power"), "one decision, a new stage",
                 "That where work runs is a decision with a price."),
    LibraryEntry(11, "capacity", "Packaging", MEDIUM, "Cost",
                 ("Performance",), "one decision, two effects at once",
                 "That more memory buys two different things."),
    LibraryEntry(12, "fit", "Packaging", ADVANCED, "Traffic",
                 ("Cost",), "one decision, an ABSENT figure",
                 "What Studio does when a question has no answer."),
    LibraryEntry(13, "cheaper", "Memory", MEDIUM, "Power",
                 ("Cost",), "one decision, no performance change",
                 "What decides when the limiting stage is untouched."),
    LibraryEntry(14, "split", "Parallel", MEDIUM, "Performance",
                 (), "one decision, an unequal pair",
                 "Why an even split between unequal parts is not even."),
    LibraryEntry(15, "nodecost", "Node", ADVANCED, "Area",
                 ("Performance", "Cost"),
                 "four designs, a turn in cost",
                 "That the economic optimum node is not the newest."),
)

BY_NUMBER: Dict[int, LibraryEntry] = {e.number: e for e in LIBRARY}


def difficulty_table() -> List[Tuple[int, str, str, str]]:
    return [(e.number, e.difficulty, e.family, e.complexity)
            for e in LIBRARY]


def family_groups() -> Dict[str, List[int]]:
    out: Dict[str, List[int]] = {}
    for e in LIBRARY:
        out.setdefault(e.family, []).append(e.number)
    return out


def axis_coverage() -> Dict[str, Dict[str, int]]:
    """Primary and secondary counts per axis.

    A count of appearances says which axis is drawn most. A count of
    PRIMARY appearances says which axis each demonstration is about, and
    they are different numbers.
    """
    out: Dict[str, Dict[str, int]] = {}
    for e in LIBRARY:
        out.setdefault(e.primary_axis, {"primary": 0, "secondary": 0})
        out[e.primary_axis]["primary"] += 1
        for a in e.secondary_axes:
            out.setdefault(a, {"primary": 0, "secondary": 0})
            out[a]["secondary"] += 1
    return out
