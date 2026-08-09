"""
ppact.about - what this is, how it works, and how it changes

WHY THE ORDER OF THIS PAGE IS THE POINT
=======================================
An earlier version of this text opened with "PPACT Studio does not model
commercial products." That sentence is true and it is the wrong first
sentence: it tells a reader what the Studio is NOT, and leaves them to work
out what it is.

The order below is deliberate and is checked:

    1  PURPOSE          what this is for
    2  METHOD           how it goes about it
    3  EVOLUTION        how it changes, and what changes it
    4  DESIGN BOUNDARY  what it deliberately does not do
    5  INTERPRETATION   what a reader should do with a number from it

The boundary comes fourth because it is a CONSEQUENCE of the first three. A
tool built to explore architecture, using analytical models, refined by
public industrial information, does not model commercial products - and once
the first three are said, the fourth reads as a design decision rather than
an apology.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

LINE = "=" * 78


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    paragraphs: Tuple[str, ...]


SECTIONS: Tuple[Section, ...] = (

    Section("purpose", "PURPOSE", (
        "PPACT Studio is a platform for exploring AI system architecture. "
        "It exists for the part of a project that happens before anything "
        "is built: choosing what kind of system to make, and finding out "
        "what each choice costs on the axes that decide whether a product "
        "ships.",

        "Those axes are performance, power, area, cost and thermal. A "
        "design is not fast or slow - it is fast, hot, large, dear and hard "
        "to cool in some combination, and the interesting question is "
        "always what a change buys on one and charges on another.",

        "It is used for teaching, for research, and for the earliest stage "
        "of architectural work, where the alternatives are still open and "
        "the cost of exploring them is a few minutes rather than a "
        "tape-out.",
    )),

    Section("method", "METHOD", (
        "The Studio works from analytical engineering models. It computes "
        "each design from its parts - the arithmetic a workload needs, the "
        "data it moves, what the host does before the accelerator sees "
        "anything, what the memory can deliver - and compares designs on "
        "the same basis.",

        "Every conclusion is traced back to a measurement. A change is "
        "reported as what moved, by how much, why, and only then what to do "
        "about it. Where a result depends on an assumption, the Studio says "
        "which assumption and how far the conclusion survives being moved.",

        "It also states what it cannot tell you. A limit - the most a "
        "station could give back if it took no time at all - is worth more "
        "than a recommendation, because it holds for any part at any price.",
    )),

    Section("evolution", "EVOLUTION", (
        "The architectural library is not fixed. It is reviewed against "
        "publicly available industrial information, and grows when that "
        "review finds a concept it cannot express.",

        "The review works one way only. Public specifications are read, the "
        "architectural concepts behind them are extracted, and generalized "
        "CLASSES are added - a performance band, a memory generation, a "
        "deployment shape. What is never added is the product itself.",

        "Where the library falls short, the gap is written down rather than "
        "filled with something that resembles a solution. A recorded gap is "
        "useful; a class invented to close one is not, and looks like "
        "progress.",
    )),

    Section("boundary", "DESIGN BOUNDARY", (
        "PPACT Studio does not model commercial products. It models AI "
        "system architectural design spaces, informed by publicly available "
        "industrial information.",

        "Commercial products are validation sources, not library contents. "
        "No vendor name and no product name appears among the things a user "
        "can select, and a check enforces that.",

        "This follows from everything above rather than standing on its "
        "own. A tool built to explore architecture, using analytical "
        "models, refined by public information, could not reproduce a "
        "commercial part even if it wanted to - the figures that would be "
        "needed are not public, and inventing them would make an estimate "
        "indistinguishable from a measurement.",
    )),

    Section("interpretation", "INTERPRETATION", (
        "Every number the Studio reports is an analytical engineering "
        "estimate. It is computed, not measured, and it is intended for "
        "comparing architectures rather than for predicting a part.",

        "A result here narrows the question. It does not answer it. "
        "Implementation, measurement and silicon remain necessary, and no "
        "amount of work inside this program substitutes for any of them.",

        "What the Studio does not know is as important as what it "
        "computes: what a millisecond is worth, what the schedule allows, "
        "what a competitor is shipping, what a customer will pay. Those "
        "decide an answer as much as the arithmetic does. The facts are the "
        "tool's; the decision is the designer's.",
    )),
)

BY_KEY = {s.key: s for s in SECTIONS}

# The order the sections must appear in. Checked, because the order IS the
# argument: putting the boundary first would describe the Studio by what it
# is not.
REQUIRED_ORDER = ("purpose", "method", "evolution", "boundary",
                  "interpretation")

CORE_PRINCIPLES = (
    "Architecture before implementation.",
    "Engineering evidence before intuition.",
    "Vendor-neutral architectural exploration.",
    "Continuous refinement through public industrial information.",
)


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
    return lines or [""]


def about_text() -> str:
    from .branding import PRODUCT_NAME, PRODUCT_VERSION
    from . import __version__

    out = [LINE, f"{'ABOUT ' + PRODUCT_NAME:^78}", LINE, ""]
    for s in SECTIONS:
        out.append(f"  {s.title}")
        for para in s.paragraphs:
            out.append("")
            out += [f"    {line}" for line in _wrap(para, 70)]
        out.append("")
    out.append(f"  CORE PRINCIPLES")
    out.append("")
    for p in CORE_PRINCIPLES:
        out.append(f"    - {p}")
    out += ["",
            f"  Product v{PRODUCT_VERSION}   Engine {__version__}",
            LINE]
    return "\n".join(out)


def print_about() -> None:
    print(about_text())


def about_violations() -> List[str]:
    """The order is the argument. So is saying all five things."""
    problems = []
    keys = [s.key for s in SECTIONS]
    if tuple(keys) != REQUIRED_ORDER:
        problems.append(
            f"the sections are in the order {keys}, not {list(REQUIRED_ORDER)}"
            f" - the boundary must not come before the purpose, or the page "
            f"describes the Studio by what it is not")
    for s in SECTIONS:
        if len(s.paragraphs) < 2:
            problems.append(f"{s.key}: one paragraph is a heading, not a "
                            f"section")
        for i, para in enumerate(s.paragraphs):
            if len(para) < 80:
                problems.append(f"{s.key}[{i}]: too short to say anything")
    if len(CORE_PRINCIPLES) < 4:
        problems.append("fewer than four core principles")
    text = about_text()
    for line in text.splitlines():
        if len(line) > 78:
            problems.append(f"a line runs to {len(line)} characters")
            break
    return problems
