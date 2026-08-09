"""
ppact.test_registry - what each validation step is, and what it is not

WHY THIS EXISTS
===============
Three sets were all eighteen and none of them matched:

    discovered   18 files named tests_*.py
    registered   18 entries in verify_release
    reported     18 results in the verification record

    registered but not reported   menu paths
    reported but not registered   quick start example

A count is not a set. Both mismatches were invisible because nothing
compared members - only totals, and only by accident.

Worse: the record named engine 4.17.3 and the engine was 4.17.3, so every
integrity check treated it as evidence about this build. Registering a
suite changes what verification MEANS and changes no engine file. Freshness
keyed on the engine version cannot see that.

WHAT A REGISTRY ENTRY MUST SAY
------------------------------
Not just that a suite exists. What it ESTABLISHES, what it DOES NOT, what
must be true for its assertions to be reached, and whether its power to
detect a defect has ever been demonstrated.

"tests_dual 212 PASS" was reported for many releases without anyone stating
what those 212 do not cover. A number nobody can bound is not evidence.

STATUS STARTS AT PROVISIONAL
----------------------------
Every entry begins PROVISIONAL, including the suites that have found real
defects. Marking them VALID at registration would record a judgement nobody
made, and this registry exists because unexamined judgements were being
carried forward.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

REGISTRY_VERSION = "1.0"

# What produces release evidence. Not only test files: the record contained
# an entry that no suite list mentioned, because it runs as a release step.
TEST_SUITE = "TEST_SUITE"
RELEASE_STEP = "RELEASE_STEP"
REPRODUCTION_STEP = "REPRODUCTION_STEP"
MANUAL_REVIEW = "MANUAL_REVIEW"

# How a step checks. Declared, because a structural check that claims
# execution success is the failure that produced this registry: R2 saw
# build_review in the source and reported PASS while the call raised
# TypeError the moment it ran.
STATIC_STRUCTURE = "STATIC_STRUCTURE"
UNIT_BEHAVIOUR = "UNIT_BEHAVIOUR"
INTEGRATION = "INTEGRATION"
END_TO_END = "END_TO_END"
OUTPUT_CONTRACT = "OUTPUT_CONTRACT"
MUTATION = "MUTATION"
REPRODUCTION = "REPRODUCTION"

# Status. Everything starts PROVISIONAL.
PROVISIONAL = "PROVISIONAL"
VALID = "VALID"
UPDATE_REQUIRED = "UPDATE_REQUIRED"
DUPLICATE = "DUPLICATE"
OBSOLETE = "OBSOLETE"
UNTRUSTED = "UNTRUSTED"

STATUSES = (PROVISIONAL, VALID, UPDATE_REQUIRED, DUPLICATE, OBSOLETE,
            UNTRUSTED)


@dataclass(frozen=True)
class ValidationStep:
    suite_id: str
    display_name: str
    kind: str
    entry_command: str
    methods: Tuple[str, ...]

    establishes: Tuple[str, ...]
    does_not_establish: Tuple[str, ...]
    preconditions: Tuple[str, ...] = ()

    required_for_release: bool = True
    execution_order: int = 0
    timeout_s: int = 900
    dependencies: Tuple[str, ...] = ()

    # Whether this step has ever been shown to fail on a real defect.
    # "no positive control" is not "invalid" - it is "power unproven", and
    # the distinction matters because deleting a suite for want of a
    # control would remove checks that have caught defects.
    positive_control_ids: Tuple[str, ...] = ()
    discriminating_power_established: bool = False
    power_evidence: str = ""

    reviewed_engine_version: str = ""
    reviewed_contract_version: str = ""
    last_manual_review_release: str = ""
    status: str = PROVISIONAL
    owner: str = "Roger Kim"
    notes: str = ""

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"{self.suite_id}: unknown status "
                             f"{self.status!r}")
        if not self.establishes:
            raise ValueError(
                f"{self.suite_id}: says nothing about what it establishes, "
                f"so its pass count cannot be read")
        if not self.does_not_establish:
            raise ValueError(
                f"{self.suite_id}: states no limit. A number nobody can "
                f"bound is not evidence")
        if self.positive_control_ids and \
                not self.discriminating_power_established:
            raise ValueError(
                f"{self.suite_id}: names controls but does not claim the "
                f"power they would demonstrate")
        if self.discriminating_power_established and not self.power_evidence:
            raise ValueError(
                f"{self.suite_id}: claims discriminating power without "
                f"saying what demonstrated it")


# ==============================================================================
# The registry
# ==============================================================================
#
# Written from the T1 inventory, describing the state AS IT IS. Nothing here
# is tidied up first: a registry that recorded a cleaned-up picture would
# have nothing left to audit.

VALIDATION_STEPS: Tuple[ValidationStep, ...] = (

    ValidationStep(
        "streamlit", "Streamlit QA", TEST_SUITE, "tests_streamlit.py",
        (STATIC_STRUCTURE, INTEGRATION),
        establishes=(
            "The Streamlit app parses, launches and answers",
            "It imports the view layer and calls no engine entry point",
            "All fifteen demonstrations build a complete view",
            "The notebook and Streamlit paths read the same figures"),
        does_not_establish=(
            "That a label is legible in a browser",
            "That a table does not scroll sideways at 768 px",
            "That a chart fits its container",
            "Anything a person at a screen would see"),
        required_for_release=False,
        execution_order=260,
        reviewed_engine_version="4.19.0",
        reviewed_contract_version="Revision 4",
        status="PROVISIONAL",
        notes="Browser visual review is NOT PERFORMED and cannot be "
              "performed in this environment."),

    # WORKFLOW QA. Registered because the reconciliation rule would
    # otherwise report an unaccounted test file - the failure that let
    # two visual review harnesses sit unregistered for months.
    ValidationStep(
        "workflow", "Workflow QA", TEST_SUITE, "tests_workflow.py",
        (INTEGRATION,),
        establishes=(
            "Every menu entry completes without an exception",
            "No screen leaves a user without a way onward",
            "A failed chart does not take the other charts with it",
            "The fifteen demonstrations render back to back without "
            "overwriting each other"),
        does_not_establish=(
            "That a screen says the right thing",
            "That a figure is correct",
            "That the column limit is met - eighteen tasks exceed it "
            "and are deferred as WF-WIDTH-001"),
        required_for_release=False,
        execution_order=250,
        reviewed_engine_version="4.19.0",
        reviewed_contract_version="Revision 4",
        status="PROVISIONAL",
        notes="Answers the questions a user has at the moment of "
              "clicking: does this finish, is there a way out, did the "
              "picture arrive."),

    # THE TWO VISUAL REVIEW HARNESSES.
    #
    # Registered as MANUAL_REVIEW because that is what they are: they
    # generate contact sheets for a person to look at, and their exit
    # status says the sheets were produced, not that anyone read them.
    #
    # Leaving them unregistered was the failure the reconciliation rule
    # exists to catch - two test files on disk that no step accounted
    # for, so the suite manifest described a smaller system than the one
    # in the directory.
    ValidationStep(
        "flow visual review", "System flow visual review", MANUAL_REVIEW,
        "tests_flow_validation.py",
        (STATIC_STRUCTURE,),
        establishes=(
            "Every flow layout class renders without a contract "
            "violation",
            "Contact sheets exist for a person to inspect"),
        does_not_establish=(
            "That anyone has looked at them",
            "That a diagram is clear to a reader"),
        required_for_release=False,
        execution_order=230,
        reviewed_engine_version="4.19.0",
        reviewed_contract_version="Revision 4",
        status="PROVISIONAL",
        notes="Exit status means the sheets were produced. The review "
              "itself is the part no rule can perform."),

    ValidationStep(
        "memory visual review", "Memory analysis visual review",
        MANUAL_REVIEW, "tests_memory_review.py",
        (STATIC_STRUCTURE,),
        establishes=(
            "302 paired flow and memory screens render",
            "Every stability class is represented"),
        does_not_establish=(
            "That a reader follows the chain to where it stops",
            "That NOT ESTABLISHED reads as a finding rather than "
            "hedging"),
        required_for_release=False,
        execution_order=240,
        reviewed_engine_version="4.19.0",
        reviewed_contract_version="Revision 4",
        status="PROVISIONAL",
        notes="Written to answer questions no automated rule can - see "
              "its own manifest."),

    ValidationStep(
        "model", "Model validation", TEST_SUITE, "tests_model.py",
        (UNIT_BEHAVIOUR, STATIC_STRUCTURE, INTEGRATION),
        establishes=(
            "Analytical model invariants hold across the configuration "
            "space",
            "Reported figures agree with independently computed ones",
            "Screens carry the wording and structure their rules require"),
        does_not_establish=(
            "That a menu path completes",
            "That the numbers match measured hardware",
            "That a reader understands the output"),
        execution_order=10, timeout_s=2400,
        positive_control_ids=("mutation suite",),
        discriminating_power_established=True,
        power_evidence=(
            "Mutations of engine logic are killed by this suite; see the "
            "mutation runner's verification paths"),
        reviewed_engine_version="4.17.3",
        notes="Largest suite. Mixes structural and behavioural checks, "
              "which the method list records rather than hides."),

    ValidationStep(
        "freeze", "Freeze validation", TEST_SUITE, "tests_freeze.py",
        (UNIT_BEHAVIOUR, STATIC_STRUCTURE),
        establishes=(
            "The configuration space produces stable, reproducible figures",
            "No configuration raises or returns a nonsensical result"),
        does_not_establish=(
            "That the figures are correct against hardware",
            "That any user path reaches these configurations"),
        execution_order=20, timeout_s=1800,
        reviewed_engine_version="4.17.3",
        notes="Discriminating power NOT ESTABLISHED - no control has been "
              "shown to make it fail."),

    ValidationStep(
        "documentation", "Documentation audit", TEST_SUITE, "tests_docs.py",
        (STATIC_STRUCTURE, INTEGRATION),
        establishes=(
            "Documents agree with the program on modes, keys and metrics",
            "Examples in the documents run",
            "Retired terminology is absent from the documents"),
        does_not_establish=(
            "That the documents are clear",
            "That they are complete"),
        execution_order=30,
        positive_control_ids=("docs_* mutations",),
        discriminating_power_established=True,
        power_evidence="Eight documentation mutations are killed by it",
        reviewed_engine_version="4.17.3"),

    ValidationStep(
        "user and answer", "User and answer validation", TEST_SUITE,
        "tests_user_validation.py", (INTEGRATION, OUTPUT_CONTRACT),
        establishes=(
            "Design questions are answerable from what is on screen",
            "Answers agree with the engine",
            "Reason, conclusion and takeaway point at the same station"),
        does_not_establish=(
            "That a student understands anything",
            "That the tool improves a designer's answers",
            "That the screens are readable to a beginner"),
        execution_order=40,
        positive_control_ids=("consistency detector control",),
        discriminating_power_established=True,
        power_evidence="A deliberately inconsistent conclusion is caught",
        reviewed_engine_version="4.17.3"),

    ValidationStep(
        "logical consistency", "Logical consistency validation", TEST_SUITE,
        "tests_logical_consistency.py", (INTEGRATION, OUTPUT_CONTRACT),
        establishes=(
            "The numbers, status, explanation, score, chart and "
            "recommendation do not contradict each other",
            "One user flow uses a single configuration throughout"),
        does_not_establish=(
            "That the model matches a commercial part",
            "That estimated power equals measured silicon"),
        execution_order=50,
        positive_control_ids=tuple(f"LC{i:02d}" for i in range(1, 22)),
        discriminating_power_established=True,
        power_evidence="21 controls, each caught by its own rule",
        reviewed_engine_version="4.17.3"),

    ValidationStep(
        "review contract", "Standard review contract", TEST_SUITE,
        "tests_review_contract.py --enforce",
        (STATIC_STRUCTURE, END_TO_END, OUTPUT_CONTRACT),
        establishes=(
            "Every registered analysis workflow reaches the standard review",
            "Every mandatory section appears, in contract order",
            "The review executes to completion and returns normally",
            "Engineering questions carry no default"),
        does_not_establish=(
            "That the review is useful",
            "That its visual design is good",
            "That a workflow missing from the registry is covered"),
        execution_order=60,
        positive_control_ids=("R11 controls",),
        discriminating_power_established=True,
        power_evidence=(
            "Seven controls, each owned by its intended rule; R2b was "
            "added after a TypeError passed R2's structural check"),
        reviewed_engine_version="4.17.3",
        reviewed_contract_version="Standard Engineering Review Contract r3"),

    ValidationStep(
        "menu paths", "Menu path regression", TEST_SUITE,
        "tests_menu_paths.py", (END_TO_END,),
        establishes=(
            "The interactive paths run with scripted input",
            "No function uses a name above its own local import"),
        does_not_establish=(
            "That the screens say anything correct",
            "That a task terminates - three tasks currently do not, and "
            "whether that is the program or the harness is unresolved"),
        preconditions=(
            "Scripted input must reach the end of each task; a task that "
            "re-enters its own menu consumes answers indefinitely"),
        execution_order=70, timeout_s=2400,
        positive_control_ids=("local-import shadowing control",),
        discriminating_power_established=True,
        power_evidence="The shadowing scan is shown the exact defect shape",
        reviewed_engine_version="4.17.3",
        status=UPDATE_REQUIRED,
        notes="Registered at 4.17.4 after existing unregistered since RC2. "
              "Three tasks do not terminate under the harness."),

    ValidationStep(
        "question clarity", "Question clarity audit", TEST_SUITE,
        "tests_questions.py", (STATIC_STRUCTURE, UNIT_BEHAVIOUR),
        establishes=(
            "Every user-facing question comes from the registry",
            "Options carry engineering labels, not bare numbers",
            "Help is reachable and adds material the question lacks",
            "Empty input selects nothing"),
        does_not_establish=(
            "That an explanation is any good - a sentence can satisfy "
            "every rule here and leave a reader none the wiser"),
        execution_order=80, timeout_s=600,
        reviewed_engine_version="4.17.3",
        notes="Discriminating power NOT ESTABLISHED for most packs."),

    ValidationStep(
        "language", "Language and philosophy audit", TEST_SUITE,
        "tests_language.py", (STATIC_STRUCTURE,),
        establishes=(
            "Retired terminology is absent from code and documents",
            "One concept carries one name",
            "A baseline is never presented as a recommendation"),
        does_not_establish=(
            "That the wording is clear",
            "That a term absent from source is absent from a screen"),
        execution_order=90,
        reviewed_engine_version="4.17.3",
        notes="Discriminating power NOT ESTABLISHED."),

    ValidationStep(
        "library validation", "Industrial library validation", TEST_SUITE,
        "tests_library_validation.py", (STATIC_STRUCTURE,),
        establishes=(
            "Required library entries exist",
            "Schema fields are present",
            "Identifiers are internally consistent",
            "Vendor names are refused where the policy forbids them"),
        does_not_establish=(
            "Runtime usability of any library entry",
            "Model execution with these entries",
            "Numerical correctness of any coefficient",
            "Any end-to-end library workflow"),
        execution_order=100,
        reviewed_engine_version="4.4.0",
        status=UPDATE_REQUIRED,
        notes="Static only; it never calls the engine. Last visible "
              "revision markers are 4.3.0 and 4.4.0 against engine "
              "4.17.3."),

    ValidationStep(
        "independent arithmetic", "Independent arithmetic", TEST_SUITE,
        "tests_independent.py", (UNIT_BEHAVIOUR,),
        establishes=(
            "Key figures agree with arithmetic derived without the engine"),
        does_not_establish=(
            "That the model's assumptions are right - an independent "
            "recomputation of a wrong formula agrees with it"),
        execution_order=110,
        reviewed_engine_version="4.17.3",
        notes="Its oracle is independent, which is a form of discriminating "
              "power, but no injected defect has demonstrated it."),

    ValidationStep(
        "dual accelerator", "Dual accelerator", TEST_SUITE, "tests_dual.py",
        (UNIT_BEHAVIOUR,),
        establishes=(
            "Two-engine configurations partition work and time coherently"),
        does_not_establish=(
            "Anything about single-engine designs",
            "That any user path reaches a dual configuration"),
        execution_order=120,
        reviewed_engine_version="4.17.3",
        notes="212 checks whose limits were unstated until this entry."),

    ValidationStep(
        "corner cases", "Corner cases", TEST_SUITE, "tests_corner.py",
        (UNIT_BEHAVIOUR,),
        establishes=(
            "Extreme and degenerate configurations do not raise or return "
            "impossible figures"),
        does_not_establish=("That ordinary configurations are correct",),
        execution_order=130,
        reviewed_engine_version="4.17.3"),

    ValidationStep(
        "scenarios", "Golden scenarios", TEST_SUITE, "tests_scenarios.py",
        (UNIT_BEHAVIOUR,),
        establishes=(
            "Known scenarios move in the expected direction",
            "No direction reversal appears between releases"),
        does_not_establish=(
            "Magnitudes - only directions are enforced"),
        execution_order=140,
        reviewed_engine_version="4.17.3"),

    ValidationStep(
        "memory", "Memory model", TEST_SUITE, "tests_memory.py",
        (UNIT_BEHAVIOUR,),
        establishes=(
            "Memory capacity, bandwidth and energy scale as the model "
            "defines"),
        does_not_establish=(
            "That the per-unit figures match any real part"),
        execution_order=150,
        reviewed_engine_version="4.17.3"),

    ValidationStep(
        "differential", "Differential comparison", TEST_SUITE,
        "tests_differential.py", (UNIT_BEHAVIOUR,),
        establishes=(
            "A change to one input moves only the figures it should"),
        does_not_establish=("Absolute correctness of any figure",),
        execution_order=160, timeout_s=1200,
        reviewed_engine_version="4.17.3"),

    ValidationStep(
        "holdout", "Holdout", TEST_SUITE, "tests_holdout.py",
        (UNIT_BEHAVIOUR,),
        establishes=(
            "Configurations withheld from tuning still behave coherently"),
        does_not_establish=(
            "External validation - the holdout is generated by this same "
            "engine, so it is not an independent predictor"),
        execution_order=170, timeout_s=600,
        reviewed_engine_version="4.17.3"),

    ValidationStep(
        # A RELEASE_STEP, not a scheduled suite. It runs as an isolated
        # child after the suites so the parent survives to close the
        # record: three runs previously vanished inside this stage and
        # took the parent with them, leaving no account at all.
        "mutation", "Mutation testing", RELEASE_STEP, "tests_mutation.py",
        (MUTATION,),
        establishes=(
            "Each registered guard, when disabled, is noticed by some check",
            "No mutation survives"),
        does_not_establish=(
            "That the guards cover everything worth guarding - a mutation "
            "set only tests the defects somebody thought to write down",
            "Which rule caught a mutation, unless a control names it"),
        required_for_release=False,
        execution_order=180, timeout_s=5400,
        discriminating_power_established=True,
        power_evidence="It is itself the demonstration of other suites' "
                       "power",
        reviewed_engine_version="4.17.3"),

    # --- steps that are not test files -----------------------------------
    #
    # "quick start example" appeared in the verification record and in no
    # suite list, because it runs as a release step. Registering only test
    # files would leave that gap open.

    ValidationStep(
        "quick start example", "Quick start example", RELEASE_STEP,
        "verify_release.py (inline step)", (END_TO_END,),
        establishes=(
            "The documented quick-start example runs to completion"),
        does_not_establish=(
            "That any other documented example runs"),
        execution_order=190, timeout_s=600,
        reviewed_engine_version="4.17.3",
        notes="Reported for many releases while absent from every suite "
              "list. Registered here so the report and the registry can be "
              "compared."),

    ValidationStep(
        "certification", "Release certification", REPRODUCTION_STEP,
        "certify.py", (REPRODUCTION,),
        establishes=(
            "A recorded build reproduces its own figures on rerun",
            "Source and document digests match the manifest"),
        does_not_establish=(
            "Reproduction on a different machine or Python version"),
        execution_order=200,
        reviewed_engine_version="4.17.3"),

    ValidationStep(
        "distribution integrity", "Clean distribution check",
        REPRODUCTION_STEP, "check_release.py", (STATIC_STRUCTURE,),
        establishes=(
            "The archive is complete and unmodified",
            "No development traces are present",
            "The archive name matches the release label"),
        does_not_establish=(
            "That the archive runs - completeness is not execution"),
        execution_order=210,
        reviewed_engine_version="4.17.3"),

    ValidationStep(
        "governance", "Validation governance audit (bootstrap)",
        TEST_SUITE, "tests_governance.py --bootstrap", (STATIC_STRUCTURE,),
        establishes=(
            "Discovered, registered, scheduled and reported sets agree by "
            "IDENTIFIER, not by count",
            "Every registered step declares what it does and does not "
            "establish",
            "The verification record can be shown to describe this set of "
            "checks",
            "Structural soundness and release readiness are judged "
            "separately"),
        does_not_establish=(
            "That any suite is logically correct - it audits declarations "
            "and set membership, not the reasoning inside a check",
            "That a declared limit is honest; a step could understate what "
            "it covers and this audit would accept it",
            "That the suites cover everything worth covering"),
        preconditions=(
            "A verification record must exist for freshness to be judged; "
            "without one the finding is NOT_RUN rather than a pass"),
        execution_order=5, timeout_s=600,
        positive_control_ids=tuple(sorted(
            ("unregistered file", "unscheduled suite", "missing result",
             "wrong manifest", "no stated limit", "untrusted step",
             "provisional step"))),
        discriminating_power_established=True,
        power_evidence=(
            "Seven controls, each required to be caught by its own "
            "section"),
        reviewed_engine_version="4.17.3",
        reviewed_contract_version="Test suite registry 1.0",
        notes="Runs FIRST. If it fails, nothing downstream should run: a "
              "pass count from a set of checks nobody can identify is not "
              "evidence."),

    ValidationStep(
        "governance (full)", "Validation governance audit (full)",
        RELEASE_STEP, "tests_governance.py", (STATIC_STRUCTURE,),
        establishes=(
            "The record just written names this suite manifest",
            "Everything scheduled appears in the record",
            "Result states are classified rather than collapsed to "
            "pass or fail"),
        does_not_establish=(
            "Anything the bootstrap audit already covers - this step exists "
            "for the comparisons that need a record"),
        preconditions=(
            "The verification record for THIS run must already be written",),
        execution_order=215, timeout_s=600,
        positive_control_ids=("missing result", "wrong manifest"),
        discriminating_power_established=True,
        power_evidence="Two record-dependent controls, each owned by its "
                       "section",
        reviewed_engine_version="4.17.3",
        notes="Runs last, because it compares against the record this run "
              "produced."),

    ValidationStep(
        "suite review", "Manual test suite review", MANUAL_REVIEW,
        "(human, per release)", (STATIC_STRUCTURE,),
        establishes=(
            "A person judged each suite still necessary, aimed at the "
            "current structure, and honest about its scope"),
        does_not_establish=(
            "Anything automatic - this step is a person's judgement and "
            "carries the reliability of one"),
        preconditions=("The T5 classification must be complete",),
        required_for_release=True,
        execution_order=220,
        # A person, not a version of the program. The field records which
        # engine the reviewer looked at, which is only meaningful once the
        # review has happened.
        reviewed_engine_version="(not yet reviewed)",
        status=PROVISIONAL,
        notes="NOT YET PERFORMED. Recorded so its absence is visible."),
)

BY_ID = {s.suite_id: s for s in VALIDATION_STEPS}


def manifest(root: str = ".") -> Dict:
    """The normalised description of what validation IS, right now.

    Its digest changes when a step is added, removed, reordered, renamed,
    re-commanded, or when a suite file's contents change. Any of those
    changes what a verification run MEANS, and none of them touches the
    engine version - which is why a record keyed on the engine version
    alone went on looking current after a suite was registered.
    """
    entries = []
    for s in sorted(VALIDATION_STEPS, key=lambda x: x.execution_order):
        path = os.path.join(root, s.entry_command.split()[0])
        digest = ""
        if os.path.isfile(path):
            digest = hashlib.sha256(
                open(path, "rb").read()).hexdigest()[:32]
        entries.append({
            "suite_id": s.suite_id,
            "kind": s.kind,
            "entry_command": s.entry_command,
            "required_for_release": s.required_for_release,
            "execution_order": s.execution_order,
            "methods": list(s.methods),
            "positive_control_ids": list(s.positive_control_ids),
            "discriminating_power_established":
                s.discriminating_power_established,
            "status": s.status,
            "file_digest": digest,
        })
    # The FILES THAT DECIDE WHAT RUNS, not only the files that run.
    #
    # A digest over registry entries alone leaves the same hole one level
    # up: verify_release.py could change the schedule, or the registry
    # itself could change what it demands, and the digest would not move.
    deciders = {}
    for name in ("verify_release.py", "tests_governance.py",
                 os.path.join("ppact", "test_registry.py")):
        path = os.path.join(root, name)
        if os.path.isfile(path):
            deciders[name] = hashlib.sha256(
                open(path, "rb").read()).hexdigest()[:32]
    return {"registry_version": REGISTRY_VERSION,
            "deciding_files": deciders,
            "steps": entries}


def manifest_digest(root: str = ".") -> str:
    blob = json.dumps(manifest(root), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def test_file_reconciliation(root: str = ".") -> Dict[str, List[str]]:
    """The ONE definition of how test files and registry entries line up.

    Written once because it was written twice: the registry and the
    governance audit each computed this relation their own way, and when
    mutation moved from TEST_SUITE to RELEASE_STEP they disagreed about
    whether the file was still registered. Two implementations of one rule
    is a disagreement waiting for a change.

    THE RULE
        A test file is REGISTERED when some step - of any kind - names it
        as its entry command. Running a test file as a release step still
        accounts for it.

        A registered entry command that names a .py file must exist.

        Only steps of kind TEST_SUITE are SCHEDULED by the suite runner.
        A release step runs elsewhere and is not expected in SUITES.
    """
    discovered = {f for f in os.listdir(root)
                  if f.startswith("tests_") and f.endswith(".py")}
    named = {s.entry_command.split()[0] for s in VALIDATION_STEPS}
    named_tests = {f for f in named
                   if f.startswith("tests_") and f.endswith(".py")}
    expect_scheduled = {s.suite_id for s in VALIDATION_STEPS
                        if s.kind == TEST_SUITE}
    missing_files = {f for f in named
                     if f.endswith(".py") and not
                     os.path.isfile(os.path.join(root, f))}
    return {
        "discovered": sorted(discovered),
        "registered_test_files": sorted(named_tests),
        "unregistered_files": sorted(discovered - named_tests),
        "registered_but_absent": sorted(missing_files),
        "expect_scheduled": sorted(expect_scheduled),
    }


def suite_registry_violations(root: str = ".") -> List[str]:
    """Internal coherence, plus the relation that was never enforced."""
    problems = []
    seen = set()
    orders = []
    for s in VALIDATION_STEPS:
        if s.suite_id in seen:
            problems.append(f"{s.suite_id}: registered twice")
        seen.add(s.suite_id)
        orders.append(s.execution_order)

        if END_TO_END in s.methods and STATIC_STRUCTURE == s.methods[0] \
                and len(s.methods) == 1:
            problems.append(f"{s.suite_id}: claims end-to-end with only a "
                            f"structural method")
    if len(set(orders)) != len(orders):
        problems.append("two steps share an execution order")

    # ONE definition, shared with the governance audit.
    rec = test_file_reconciliation(root)
    for f in rec["unregistered_files"]:
        problems.append(f"{f}: exists and is not registered")
    for f in rec["registered_but_absent"]:
        problems.append(f"{f}: registered and does not exist")
    return problems


def power_not_established() -> List[str]:
    """Steps whose ability to detect a defect has not been demonstrated.

    NOT a list of bad suites. A suite comparing against an independent
    oracle may well be discriminating; what is missing is the evidence, and
    the distinction between "unproven" and "invalid" is the difference
    between reviewing a suite and deleting one.
    """
    return [s.suite_id for s in VALIDATION_STEPS
            if not s.discriminating_power_established]
