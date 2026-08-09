"""
ppact.terminology - one concept, one name, one definition

WHY THIS EXISTS
===============
"Reference design" was removed from this project in one afternoon. It had
arrived the same way: nobody chose it, it was simply the word that came to
hand, and it read as "the recommended architecture" to every student who met
it.

Terminology drifts back. A term is banned, six months pass, somebody writes
the natural phrase, and the philosophy is gone again with no defect to point
at. The only thing that holds is a registry with a check reading it.

WHAT A TERM CARRIES
-------------------
    canonical     the one name used everywhere
    definition    the one sentence, quoted verbatim in every document
    first_use     what to say the first time a reader meets it
    forbidden     names that must never appear for this concept
    reason        why the forbidden names are wrong, not merely disallowed

The reason matters most. A ban without a reason is a rule somebody will
relax under pressure, because they cannot see what it was protecting.

DEFINITIONS ARE REFERENCED, NOT COPIED
--------------------------------------
A definition written twice becomes two definitions. The documents carry the
sentence verbatim and an audit compares them against this file, so an edit
in one place is a failure rather than a divergence nobody notices.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


# The registry has a VERSION. A term changing meaning is a change every
# document and every audit must see; without a version they see it silently
# and disagree about when it happened.
REGISTRY_VERSION = "1.0"

# Which product releases this registry's vocabulary is valid for. A term
# changing meaning at v2.0 must not be read as though it still meant what
# 1.x said - and the audits, the documents and any second Studio product
# all need to see the same answer to that question.
REGISTRY_COMPATIBILITY = "PPACT Studio 1.x"


# Wording that is not wrong, only vague. "Typical" claims a survey nobody
# ran; "standard" claims an authority nobody named. These are DISCOURAGED
# rather than forbidden, because each is occasionally right and a rule that
# cannot say "occasionally" gets ignored the first time it is.
DISCOURAGED = {
    "typical": "claims a survey. Say what it is an example OF.",
    "standard": "claims an authority. Name the standard, or drop the word.",
    "normal": "normal for whom? Say the range or the case.",
    "regular": "same objection as 'normal'.",
    "obviously": "if it were obvious the sentence would not be needed.",
    "simply": "usually precedes something that is not simple.",
    "just": "shrinks whatever follows it, usually unearned.",
}


@dataclass(frozen=True)
class Term:
    key: str
    canonical: str
    definition: str
    reason: str
    forbidden: Tuple[str, ...] = ()
    first_use: str = ""
    # Phrases containing a forbidden name that are nonetheless correct -
    # a denial, or a different concept sharing a word.
    permitted_contexts: Tuple[str, ...] = ()


TERMS: Tuple[Term, ...] = (

    Term(
        key="starting_point",
        canonical="Starting point",
        definition=(
            "A starting point is a predefined initial architecture used "
            "only to make measured changes easier to interpret. It is not a "
            "recommendation, not an optimal design, and not a target "
            "architecture."),
        reason=(
            "In teaching, 'reference' is read as 'the answer'. A student who "
            "takes the baseline for the recommendation has learned the "
            "opposite of what a design-space explorer is for."),
        forbidden=("reference design", "reference architecture",
                   "reference system", "recommended design",
                   "recommended architecture", "optimal design",
                   "golden design", "ideal design", "best design"),
        first_use=(
            "the design this one is measured against, chosen to make the "
            "difference legible"),
        permitted_contexts=("not a recommend", "not an optimal",
                            "never a recommend", "not thereby",
                            "golden model", "golden trace", "golden data",
                            "golden_", "bit-true"),
    ),

    Term(
        key="execution_latency",
        canonical="Execution latency",
        definition=(
            "Execution latency is the time one job takes, from the first "
            "byte in to the last byte out."),
        reason=(
            "Four names for one quantity make two screens look like they "
            "measure different things. They do not, and a reader comparing "
            "them will conclude otherwise."),
        forbidden=("response time", "job time", "execution time",
                   "processing speed"),
        first_use="one job, start to finish",
    ),

    Term(
        key="host_active",
        canonical="Host-active time",
        definition=(
            "Host-active time is the time the host processor spends on "
            "preprocessing, dispatch and postprocessing for a single job."),
        reason=(
            "'CPU time' means something else in every operating system a "
            "reader has used, and 'host time' does not say what the host "
            "was doing."),
        forbidden=("cpu time", "host time", "processor time"),
        first_use="what the host does around the accelerator",
    ),

    Term(
        key="pipeline_throughput",
        canonical="Pipeline capacity",
        definition=(
            "Pipeline capacity is how many jobs the system could complete "
            "per second when they overlap in the pipeline. Delivered "
            "throughput is the smaller of that and the arrival rate."),
        reason=(
            "Capacity and delivered throughput are different numbers, and "
            "calling both 'throughput' hides the case that matters: a "
            "machine that could do more and is not being asked to."),
        forbidden=("max throughput", "actual throughput", "peak throughput"),
        first_use="what the machine could do, against what it is asked to do",
    ),

    Term(
        key="architecture_balance",
        canonical="Architecture Balance",
        definition=(
            "Architecture Balance is a normalized architecture summary. It "
            "shows the relative balance among normalized dimensions and no "
            "physical value, requirement limit, bottleneck or cause."),
        reason=(
            "An experiment put five design questions to this chart and it "
            "answered none of them. Naming it after performance or calling "
            "it a fingerprint invites exactly the reading it cannot "
            "support."),
        forbidden=("architecture fingerprint", "performance summary",
                   "performance profile"),
        first_use="whether a change was even across the design",
    ),

    Term(
        key="deployment_status",
        canonical="Deployment status",
        definition=(
            "Deployment status is READY when every requirement is "
            "satisfied - latency, throughput, power, cost, thermal, cooling "
            "class and capacity - and NOT READY with a named reason "
            "otherwise."),
        reason=(
            "'Ships' reads as a business decision the model has not made. "
            "The model checks requirements; whether a product ships depends "
            "on things it does not know."),
        # "ships" is NOT listed here, deliberately. What was retired was
        # "ships" as a COLUMN HEADING and a verdict, and tests_language L08
        # already governs that precisely, with positive controls. As an
        # ordinary verb - "whether the product ships" - it is correct
        # English and appears in fifty-one places. Banning it here would
        # produce fifty-one false positives, and a check with fifty-one
        # false positives is a check somebody turns off.
        #
        # The rule this registry enforces is about DESIGN terminology. A
        # rule that reaches past its subject stops being obeyed.
        forbidden=("shippable", "production ready", "ready to ship"),
        first_use="whether every requirement is met, and which is not",
    ),

    Term(
        key="published_configuration",
        canonical="Example published configuration",
        definition=(
            "Example published configurations are illustrative examples "
            "derived from publicly available technical information. They "
            "are provided for comparison and education, not as recommended "
            "system designs."),
        reason=(
            "'Typical today' claims to represent the industry. This project "
            "reviews a handful of vendors and is in no position to say what "
            "is typical of anything."),
        forbidden=("typical today", "industry standard design",
                   "state of the art design"),
        first_use="an example built from public information, not a survey",
    ),
)

BY_KEY: Dict[str, Term] = {t.key: t for t in TERMS}

# Kept for callers that imported it before the registry existed.
STARTING_POINT_DEFINITION = BY_KEY["starting_point"].definition


def definition(key: str) -> str:
    return BY_KEY[key].definition


def all_forbidden() -> List[Tuple[str, Term]]:
    return [(phrase, term) for term in TERMS for phrase in term.forbidden]


def permitted(line: str) -> bool:
    """True when a line containing a forbidden phrase is nonetheless right.

    Two cases, and both are the rule rather than exceptions to it:
    a sentence DENYING the quality, and a different concept that happens to
    share a word - a golden model is a verification standard, not a design
    anybody is being steered towards.
    """
    low = line.lower()
    for term in TERMS:
        for ok in term.permitted_contexts:
            if ok.lower() in low:
                return True
    return False


# The revision log is a HISTORY. It records what a defect was called at the
# time it was found, and rewriting it would make the record disagree with
# what actually happened - which is the one thing a revision log must not
# do. Excluded by name rather than by a pattern, so adding a file to this
# list is a decision somebody makes deliberately.
# A HISTORICAL RECORD states past fact, not present policy. Renaming a
# defect in the revision log would make the record disagree with what
# happened, which is the one thing a log must never do. Listed by name so
# adding one is a decision somebody makes rather than a pattern that widens.
HISTORICAL_RECORD = ("revisions.py",)
HISTORICAL_FILES = HISTORICAL_RECORD          # earlier name, kept working


def scan(text: str) -> List[Tuple[str, str, Term]]:
    """Every forbidden phrase in a text, with the line and the term.

    A line is judged WITH ITS NEIGHBOURS, because prose wraps. The
    definition ends "...not a recommendation, not an optimal design, and not
    a target architecture", and wrapped at 74 characters the denial lands on
    one line and the phrase on the next. Judging lines in isolation reported
    the canonical definition as a violation of itself, in three documents at
    once.
    """
    found = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith("#"):
            continue
        window = " ".join(lines[max(0, i - 1):i + 2])
        if permitted(window):
            continue
        low = line.lower()
        for phrase, term in all_forbidden():
            if phrase in low:
                found.append((phrase, line.strip()[:70], term))
    return found


def scan_discouraged(text: str) -> List[Tuple[str, str, str]]:
    """Vague wording, with why it is vague. Reported, not failed."""
    import re
    found = []
    for line in text.split("\n"):
        if line.strip().startswith("#"):
            continue
        for word, why in DISCOURAGED.items():
            if re.search(rf"\b{word}\b", line, re.I):
                found.append((word, line.strip()[:60], why))
    return found


def violations() -> List[str]:
    """The registry must be internally coherent."""
    problems = []
    if not REGISTRY_VERSION:
        problems.append("the registry carries no version")
    if not REGISTRY_COMPATIBILITY:
        problems.append("the registry says nothing about what it is "
                        "compatible with")
    for t in TERMS:
        if not t.first_use:
            problems.append(
                f"{t.key}: no first-appearance wording, so the question "
                f"help and the documents will each invent one")
    seen_canonical = {}
    for t in TERMS:
        if len(t.definition) < 50:
            problems.append(f"{t.key}: the definition says too little")
        if len(t.reason) < 40:
            problems.append(
                f"{t.key}: no reason given - a ban without a reason is a "
                f"rule somebody relaxes under pressure")
        if not t.forbidden:
            problems.append(f"{t.key}: bans nothing, so it governs nothing")
        if t.canonical.lower() in [f.lower() for f in t.forbidden]:
            problems.append(f"{t.key}: bans its own canonical name")
        if t.canonical in seen_canonical:
            problems.append(
                f"{t.key}: canonical name shared with "
                f"{seen_canonical[t.canonical]}")
        seen_canonical[t.canonical] = t.key
        # a forbidden phrase must not be another term's canonical name
        for other in TERMS:
            if other.key == t.key:
                continue
            if other.canonical.lower() in [f.lower() for f in t.forbidden]:
                problems.append(
                    f"{t.key}: forbids {other.canonical!r}, which is "
                    f"{other.key}'s canonical name")
    return problems


def print_glossary() -> None:
    line = "=" * 78
    print(f"\n{line}\n TERMINOLOGY\n{line}")
    print("  One concept, one name, one definition. The forbidden names are")
    print("  listed with the reason they are wrong, because a ban without a")
    print("  reason is a rule somebody relaxes under pressure.\n")
    from .visual import wrap_text
    for t in TERMS:
        print(f"  {t.canonical}")
        for ln in wrap_text(t.definition, 68):
            print(f"    {ln}")
        if t.forbidden:
            print(f"    never: {', '.join(t.forbidden)}")
            for ln in wrap_text(t.reason, 66):
                print(f"      {ln}")
        print()
    print(line)
