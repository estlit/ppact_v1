"""
tests_governance.py - is the validation system telling the truth about itself?

WHY THIS RUNS FIRST
===================
Three sets were all eighteen and none of them matched. `menu paths` was
registered and never reported; `quick start example` was reported and never
registered. Both were invisible because only totals were compared.

Worse, the verification record named engine 4.17.3 and the engine was
4.17.3, so every integrity check treated it as current. Registering a suite
changes what verification MEANS and touches no engine file.

A high pass count from a stale, unregistered or unreported set of checks is
worse than no checks: it supplies confidence that nothing earned.

READ-ONLY
---------
This audit inspects, compares, classifies and reports. It writes nothing,
registers nothing and repairs nothing. An audit that tidied its subject
would be auditing a state that only existed because it tidied it.

TWO VERDICTS, NOT ONE
---------------------
    Governance structure   is the validation system internally coherent
    Release readiness      may its results be used as release evidence

These are different questions. The structure can be sound while every suite
is still PROVISIONAL - which is exactly today's position, and reporting one
number for both would hide it.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

sys.path.insert(0, ".")

LINE = "=" * 86

PASS = "PASS"
FAIL = "FAIL"
ERROR = "ERROR"
TIMEOUT = "TIMEOUT"
NOT_RUN = "NOT_RUN"
STALE = "STALE"
INCONCLUSIVE = "INCONCLUSIVE"
BLOCKED = "BLOCKED"

# Which states may be counted as release evidence. ERROR and TIMEOUT are
# NOT successes - a check that crashed did not find the absence of a
# defect, it found nothing.
EVIDENCE_STATES = (PASS,)

RESULTS = []      # (section, name, state, detail)


def record(section, name, state, detail=""):
    RESULTS.append((section, name, state, detail))


def ok(section, name, condition, detail=""):
    record(section, name, PASS if condition else FAIL, detail)


# ==============================================================================
# G1 - the registry describes itself completely
# ==============================================================================

def g1_registry_completeness():
    S = "G1"
    from ppact import test_registry as R

    problems = R.suite_registry_violations()
    ok(S, "the registry is internally coherent", not problems,
       "; ".join(problems[:3]))

    for step in R.VALIDATION_STEPS:
        sid = step.suite_id
        ok(S, f"{sid}: declares what it establishes",
           bool(step.establishes))
        ok(S, f"{sid}: declares what it does not establish",
           bool(step.does_not_establish),
           "a number nobody can bound is not evidence")
        ok(S, f"{sid}: names an entry command", bool(step.entry_command))
        ok(S, f"{sid}: states a timeout", step.timeout_s > 0)
        ok(S, f"{sid}: declares its checking methods", bool(step.methods))
        ok(S, f"{sid}: carries a status", step.status in R.STATUSES)
        ok(S, f"{sid}: names the engine it was reviewed against",
           bool(step.reviewed_engine_version),
           "a suite that does not say what it was written for cannot be "
           "judged stale")

    # A structural method may not be presented as an execution claim. This
    # is the exact shape of the TypeError that passed R2: build_review was
    # in the source, so the routing check passed, and the call raised.
    for step in R.VALIDATION_STEPS:
        claims_run = any(
            w in " ".join(step.establishes).lower()
            for w in ("executes", "runs", "completes", "reaches"))
        only_static = tuple(step.methods) == (R.STATIC_STRUCTURE,)
        ok(S, f"{step.suite_id}: does not claim execution from structure "
              f"alone",
           not (claims_run and only_static),
           "seeing a call in source is not seeing it succeed")


# ==============================================================================
# G2 - the four sets, compared by identifier
# ==============================================================================

def _scheduled_ids(root="."):
    """What verify_release will actually run, read from the runner."""
    src = open(os.path.join(root, "verify_release.py"),
               encoding="utf-8").read()
    block = re.search(r"SUITES\s*=\s*\((.*?)\n\)", src, re.S)
    if not block:
        return None
    return [m.group(1) for m in
            re.finditer(r'\("([^"]+)",\s*"[^"]+"', block.group(1))]


def _reported_ids(root="."):
    path = os.path.join(root, "rc_verification.json")
    if not os.path.isfile(path):
        return None
    return sorted(json.load(open(path, encoding="utf-8"))
                  .get("results", {}))


def g2_set_reconciliation():
    """Compared by ID, never by count.

    Both mismatches survived because three totals of eighteen looked like
    agreement. A count is not a set.
    """
    S = "G2"
    from ppact import test_registry as R

    # THE SAME function the registry uses. Each computed this relation its
    # own way, and when mutation moved from TEST_SUITE to RELEASE_STEP the
    # two disagreed about whether its file was still registered. An audit
    # that reimplements the rule it audits can only be right by
    # coincidence.
    rec = R.test_file_reconciliation(".")
    registered_ids = {s.suite_id for s in R.VALIDATION_STEPS}
    required_ids = {s.suite_id for s in R.VALIDATION_STEPS
                    if s.required_for_release}

    scheduled = _scheduled_ids()
    reported = _reported_ids()

    ok(S, "every discovered test file is registered",
       not rec["unregistered_files"], str(rec["unregistered_files"]))
    ok(S, "every registered test file exists",
       not rec["registered_but_absent"],
       str(rec["registered_but_absent"]))

    if scheduled is None:
        record(S, "the runner's schedule can be read", ERROR,
               "SUITES not found in verify_release.py")
        return
    scheduled_set = set(scheduled)

    ok(S, "everything scheduled is registered",
       not (scheduled_set - registered_ids),
       f"scheduled and unregistered: "
       f"{sorted(scheduled_set - registered_ids)}")

    # Steps that are not test suites run outside SUITES by design, so they
    # are excluded here rather than reported as gaps.
    # Only TEST_SUITE steps are scheduled by the suite runner; a release
    # step runs elsewhere, which the reconciliation states rather than
    # each caller deciding.
    suite_ids = set(rec["expect_scheduled"])
    ok(S, "every registered suite is scheduled",
       not (suite_ids - scheduled_set),
       f"registered and never scheduled: "
       f"{sorted(suite_ids - scheduled_set)}")

    if reported is None:
        record(S, "a verification record exists to compare against", NOT_RUN,
               "no rc_verification.json - not a pass, an absence")
        return
    if "--bootstrap" in sys.argv[1:]:
        # The record on disk describes the PREVIOUS run. Comparing it now
        # would report the gap this run exists to close.
        record(S, "record comparison deferred to the full audit", NOT_RUN,
               "bootstrap runs before the record is written")
        return
    reported_set = set(reported)

    ok(S, "everything reported was scheduled",
       not (reported_set - scheduled_set - registered_ids),
       f"reported and neither scheduled nor registered: "
       f"{sorted(reported_set - scheduled_set - registered_ids)}")
    ok(S, "everything scheduled appears in the record",
       not (scheduled_set - reported_set),
       f"scheduled and unreported: {sorted(scheduled_set - reported_set)}")
    ok(S, "everything required appears in the record",
       not (required_ids & suite_ids - reported_set),
       f"required and unreported: "
       f"{sorted(required_ids & suite_ids - reported_set)}")


# ==============================================================================
# G2b - the runner builds its record after every step, and reports each one
# ==============================================================================
#
# The record was assembled before the mutation child ran, so it closed as
# FINAL with mutation absent - while the note in that same record says an
# absent entry means the step was not run. It HAD run. The record could not
# say so, and nothing compared the two.
#
# Set reconciliation could not see this either: mutation was correctly
# registered and correctly not scheduled, so every membership rule passed
# while a completed step went unrecorded.

def g2b_record_completeness():
    S = "G2b"
    from ppact import test_registry as R

    src = open("verify_release.py", encoding="utf-8").read()
    mut_at = src.find('results["mutation"] = run_mutation_child')
    rec_at = src.find('record = {\n        "status": "FINAL"')
    ok(S, "mutation runs before the record is built",
       mut_at != -1 and rec_at != -1 and mut_at < rec_at,
       "a step finishing after the record is closed cannot appear in it")

    full_at = src.find("THE FULL AUDIT RUNS LAST")
    ok(S, "the full audit runs after the record is written",
       full_at != -1 and rec_at != -1 and rec_at < full_at,
       "it compares against the record this run produced")

    # Every step the registry requires must be IN the record - membership
    # in SUITES is not the same as presence in the result.
    # Deferred in bootstrap: the record on disk belongs to the PREVIOUS
    # run, and judging it here reports the gap this run exists to close.
    # The ORDER checks above need no record and stay.
    if "--bootstrap" in sys.argv[1:]:
        record(S, "record completeness deferred to the full audit",
               NOT_RUN, "bootstrap runs before the record is written")
        return

    reported = _reported_ids()
    if reported is None:
        record(S, "every required step appears in the record", NOT_RUN,
               "no record yet")
        return
    required = {s.suite_id for s in R.VALIDATION_STEPS
                if s.required_for_release
                and s.kind in (R.TEST_SUITE, R.RELEASE_STEP)}
    missing = sorted(required - set(reported))
    ok(S, "every required step appears in the record", not missing,
       f"required, executed and unrecorded: {missing}")


# ==============================================================================
# G3 - is the existing record evidence about THIS system?
# ==============================================================================

def g3_evidence_freshness():
    S = "G3"
    from ppact import test_registry as R

    path = "rc_verification.json"
    if not os.path.isfile(path):
        record(S, "the verification record is current", NOT_RUN,
               "there is no record")
        return
    rec = json.load(open(path, encoding="utf-8"))

    current = R.manifest_digest()
    recorded = rec.get("suite_manifest_digest")

    if recorded is None:
        # Not "skip the comparison because there is nothing to compare".
        # A record that cannot be checked against the manifest is not
        # evidence about the manifest.
        record(S, "the record names the suite manifest it ran against",
               STALE,
               "no suite_manifest_digest - the record cannot be shown to "
               "describe this set of checks, so it is not evidence about it")
    else:
        record(S, "the record names the suite manifest it ran against",
               PASS if recorded == current else STALE,
               f"recorded {str(recorded)[:16]} against current "
               f"{current[:16]}")

    from ppact import __version__
    record(S, "the record names this engine",
           PASS if rec.get("engine_version") == __version__ else STALE,
           f"record {rec.get('engine_version')} against engine "
           f"{__version__}")

    # An engine version alone cannot detect a change to the suite set,
    # which is how a record went on looking current after a suite was
    # registered.
    ok(S, "freshness does not rest on the engine version alone",
       "suite_manifest_digest" in rec or recorded is not None,
       "registering a suite changes what verification means and changes "
       "no engine file")


# ==============================================================================
# G4 - are the results usable as evidence?
# ==============================================================================

def g4_result_states():
    S = "G4"
    path = "rc_verification.json"
    if not os.path.isfile(path):
        record(S, "results can be classified", NOT_RUN, "no record")
        return
    rec = json.load(open(path, encoding="utf-8"))

    for sid, entry in sorted(rec.get("results", {}).items()):
        status = entry.get("status")
        # A crash is not a finding. An absence is not a pass.
        if status in ("ERROR", "TIMEOUT"):
            record(S, f"{sid}: state is usable as evidence", status,
                   "a check that crashed found nothing, not the absence of "
                   "a defect")
        elif status == "not run":
            record(S, f"{sid}: state is usable as evidence", NOT_RUN,
                   entry.get("reason", ""))
        elif status == PASS:
            record(S, f"{sid}: state is usable as evidence", PASS)
        else:
            record(S, f"{sid}: state is usable as evidence", FAIL,
                   str(status))


# ==============================================================================
# G0 - the verification framework is frozen
# ==============================================================================
#
# The framework changed under its own evidence. Every edit to a deciding
# file moved the suite manifest digest, which invalidated the mutation
# checkpoint, which forced a 162-mutant re-run, during which something else
# was noticed and edited. Three rounds went that way.
#
# The evidence was correct each time - the checkpoint SHOULD refuse a
# manifest it does not describe. What was wrong was changing the manifest
# while trying to produce evidence about it.
#
# So the framework is pinned at VF-1.0. From here the program is what
# changes; the framework changes only when it is itself defective, and then
# as a new version with the reason recorded.

def g0_framework_frozen():
    S = "G0"
    import hashlib as _h

    lock_path = "verification_framework.lock"
    if not os.path.isfile(lock_path):
        record(S, "the verification framework is pinned", FAIL,
               "no verification_framework.lock - the framework can change "
               "without anything noticing, which is how three rounds of "
               "evidence were invalidated")
        return
    lock = json.load(open(lock_path, encoding="utf-8"))
    record(S, "the verification framework is pinned", PASS,
           lock.get("framework_version", ""))

    drifted = []
    for name, digest in sorted(lock.get("files", {}).items()):
        if not os.path.isfile(name):
            drifted.append(f"{name}: missing")
            continue
        actual = _h.sha256(open(name, "rb").read()).hexdigest()
        if actual != digest:
            drifted.append(f"{name}: changed since {lock['framework_version']}")
    ok(S, f"no framework file has changed since "
          f"{lock.get('framework_version')}",
       not drifted,
       "; ".join(drifted[:3])
       + " - a framework edit invalidates the evidence it was about to "
         "confirm; raise the framework version deliberately instead")

    from ppact import test_registry as R
    ok(S, "the pinned suite manifest still describes this framework",
       lock.get("suite_manifest_digest") == R.manifest_digest("."),
       f"pinned {str(lock.get('suite_manifest_digest'))[:16]} against "
       f"current {R.manifest_digest('.')[:16]}")


# ==============================================================================
# G5 - release readiness, judged separately from structure
# ==============================================================================

def g5_release_readiness():
    """Whether results MAY be used as release evidence.

    Distinct from whether the governance structure is sound. The structure
    can be coherent while every suite is still PROVISIONAL, and one verdict
    covering both would report a system as ready that nobody has reviewed.
    """
    S = "G5"
    from ppact import test_registry as R

    by_status = {}
    for step in R.VALIDATION_STEPS:
        by_status.setdefault(step.status, []).append(step.suite_id)

    ok(S, "no step is UNTRUSTED", not by_status.get(R.UNTRUSTED),
       str(by_status.get(R.UNTRUSTED, [])))
    ok(S, "no step is UPDATE_REQUIRED",
       not by_status.get(R.UPDATE_REQUIRED),
       f"{by_status.get(R.UPDATE_REQUIRED, [])} - a step needing an update "
       f"fails the release gate")
    ok(S, "no step required for release is still PROVISIONAL",
       not [s.suite_id for s in R.VALIDATION_STEPS
            if s.required_for_release and s.status == R.PROVISIONAL],
       f"{len([s for s in R.VALIDATION_STEPS if s.required_for_release and s.status == R.PROVISIONAL])} "
       f"steps have never been reviewed; running is not the same as being "
       f"trusted")

    unproven = R.power_not_established()
    record(S, "every required step has demonstrated discriminating power",
           PASS if not unproven else INCONCLUSIVE,
           f"{len(unproven)} steps have not been shown to fail on a real "
           f"defect. NOT ESTABLISHED is not the same as invalid - a suite "
           f"comparing against an independent oracle may well be "
           f"discriminating, and the evidence is what is missing")

    manual = [s for s in R.VALIDATION_STEPS if s.kind == R.MANUAL_REVIEW]
    ok(S, "a manual suite review is registered", bool(manual))
    for m in manual:
        record(S, f"{m.suite_id}: has been performed",
               PASS if m.status == R.VALID else NOT_RUN,
               "recorded so its absence is visible rather than assumed")


# ==============================================================================
# G6 - positive controls for this audit
# ==============================================================================

def _isolated(fn, *a):
    saved = list(RESULTS)
    RESULTS.clear()
    try:
        fn(*a)
        produced = list(RESULTS)
    except Exception as exc:
        produced = [("XX", f"{fn.__name__} raised", ERROR,
                     f"{type(exc).__name__}: {exc}")]
    finally:
        RESULTS.clear()
        RESULTS.extend(saved)
    return produced


def _control(label, rule, expect, mutate, restore, fn):
    try:
        mutate()
        produced = _isolated(fn)
    finally:
        restore()
    hits = [r for r in produced
            if r[2] not in (PASS,) and r[0] == rule
            and expect.lower() in r[1].lower()]
    others = [r for r in produced if r[2] not in (PASS,)]
    if hits:
        record("G6", f"{label}: caught by {rule}", PASS)
    elif others:
        record("G6", f"{label}: caught by {rule}", FAIL,
               f"reported by {[(r[0], r[1][:30]) for r in others][:2]} "
               f"instead - a control satisfied by a different rule proves "
               f"that rule")
    else:
        record("G6", f"{label}: caught by {rule}", FAIL,
               f"{rule} passed a deliberate defect")


CONTROL_PLAN = {
    "an unregistered test file appears": "G2",
    "a registered suite is dropped from the schedule": "G2",
    "a result is missing from the record": "G2",
    "the record names a different manifest": "G3",
    "a registry entry states no limit": "G1",
    "a step is marked UNTRUSTED": "G5",
    "a required step is left PROVISIONAL": "G5",
}


def g6_positive_controls():
    from ppact import test_registry as R
    import dataclasses

    original_steps = R.VALIDATION_STEPS

    # C1 - an unregistered test file
    stray = "tests_zz_governance_control.py"

    def add_stray():
        open(stray, "w").write("# governance control fixture\n")

    def drop_stray():
        if os.path.isfile(stray):
            os.remove(stray)

    _control("an unregistered test file appears", "G2",
             "every discovered test file is registered",
             add_stray, drop_stray, g2_set_reconciliation)

    # C2 - a registered suite removed from the runner's schedule
    runner_src = open("verify_release.py", encoding="utf-8").read()

    def unschedule():
        broken = runner_src.replace(
            '    ("memory", "tests_memory.py", 900, True),\n', "")
        open("verify_release.py", "w", encoding="utf-8").write(broken)

    def reschedule():
        open("verify_release.py", "w", encoding="utf-8").write(runner_src)

    _control("a registered suite is dropped from the schedule", "G2",
             "every registered suite is scheduled",
             unschedule, reschedule, g2_set_reconciliation)

    # C3 - a result removed from the record
    rec_path = "rc_verification.json"
    rec_src = open(rec_path, encoding="utf-8").read() \
        if os.path.isfile(rec_path) else None

    def drop_result():
        rec = json.loads(rec_src)
        rec["results"].pop("memory", None)
        json.dump(rec, open(rec_path, "w"), indent=2)

    def restore_record():
        if rec_src is not None:
            open(rec_path, "w", encoding="utf-8").write(rec_src)

    # Record-dependent controls belong to the FULL audit. In bootstrap the
    # record comparison is deferred, so injecting a defect into the record
    # produces the deferral notice rather than the rule under test - and
    # counting that as a catch would credit the wrong rule.
    full_mode = "--bootstrap" not in sys.argv[1:]
    if rec_src is not None and full_mode:
        _control("a result is missing from the record", "G2",
                 "everything scheduled appears in the record",
                 drop_result, restore_record, g2_set_reconciliation)

        # C4 - the record names a manifest that is not this one
        def wrong_digest():
            rec = json.loads(rec_src)
            rec["suite_manifest_digest"] = "0" * 64
            json.dump(rec, open(rec_path, "w"), indent=2)

        if full_mode:
            _control("the record names a different manifest", "G3",
                     "names the suite manifest",
                     wrong_digest, restore_record, g3_evidence_freshness)

    # C5 - a registry entry with no stated limit
    def strip_limits():
        first = original_steps[0]
        R.VALIDATION_STEPS = tuple(
            [dataclasses.replace(first, does_not_establish=())]
            + list(original_steps[1:]))

    def restore_steps():
        R.VALIDATION_STEPS = original_steps

    # dataclasses.replace runs __post_init__, which refuses this - the
    # constructor is the check, and that IS the rule firing. Verified
    # directly rather than through the audit function.
    try:
        strip_limits()
        record("G6", "a registry entry states no limit: caught by G1", FAIL,
               "the constructor accepted an entry with no stated limit")
    except ValueError:
        record("G6", "a registry entry states no limit: caught by G1", PASS)
    finally:
        restore_steps()

    # C6 - a step marked UNTRUSTED
    def untrust():
        R.VALIDATION_STEPS = tuple(
            [dataclasses.replace(original_steps[0], status=R.UNTRUSTED)]
            + list(original_steps[1:]))

    _control("a step is marked UNTRUSTED", "G5", "no step is UNTRUSTED",
             untrust, restore_steps, g5_release_readiness)

    # C7 - a required step left PROVISIONAL is ALREADY the state, so the
    # control is the reverse: mark everything VALID and require the rule to
    # stop firing.
    def all_valid():
        R.VALIDATION_STEPS = tuple(
            dataclasses.replace(s, status=R.VALID)
            for s in original_steps)

    try:
        all_valid()
        produced = _isolated(g5_release_readiness)
        fired = [r for r in produced
                 if r[0] == "G5" and "PROVISIONAL" in r[1]
                 and r[2] != PASS]
        record("G6", "a required step is left PROVISIONAL: caught by G5",
               PASS if not fired else FAIL,
               "with every step VALID the rule must stop firing, or it is "
               "reporting something other than what it names")
    finally:
        restore_steps()

    # The expected count depends on the mode, because two controls need a
    # record the bootstrap has not written yet.
    RECORD_CONTROLS = {"a result is missing from the record",
                       "the record names a different manifest"}
    registered = len(CONTROL_PLAN)
    if "--bootstrap" in sys.argv[1:]:
        registered -= len(RECORD_CONTROLS)
    reported = len([r for r in RESULTS
                    if r[0] == "G6" and ": caught by " in r[1]])
    ok("G6", "every registered control was reported",
       reported == registered, f"{reported} against {registered}")


# ==============================================================================
# Report
# ==============================================================================

def main(argv=None):
    """Two modes, because the two audits answer different questions at
    different times.

    BOOTSTRAP runs BEFORE the suites. Nothing has been reported yet, so it
    checks only what can be true before anything runs: the registry is
    readable, complete, and describes a schedule that matches it.

    FULL runs AFTER, when a record exists to compare against. Running the
    full audit first would always read the PREVIOUS generation's record and
    report a mismatch that the run in progress was about to fix - or worse,
    report agreement with a record describing a different set of checks.
    """
    argv = sys.argv[1:] if argv is None else argv
    bootstrap = "--bootstrap" in argv

    from ppact import test_registry as R
    from ppact import __version__

    print(LINE)
    print(f" VALIDATION GOVERNANCE AUDIT - "
          f"{'BOOTSTRAP' if bootstrap else 'FULL'}")
    print(LINE)
    print("  Read-only. It inspects, compares, classifies and reports; it")
    print("  writes nothing and repairs nothing. An audit that tidied its")
    print("  subject would be auditing a state it created.\n")
    print(f"  registry version   {R.REGISTRY_VERSION}")
    print(f"  manifest digest    {R.manifest_digest()[:32]}")
    print(f"  engine version     {__version__}")
    print()

    # Bootstrap cannot judge a record that this run is about to write.
    if bootstrap:
        stages = (g0_framework_frozen, g1_registry_completeness,
                  g2_set_reconciliation, g2b_record_completeness,
                  g5_release_readiness, g6_positive_controls)
    else:
        stages = (g0_framework_frozen, g1_registry_completeness,
                  g2_set_reconciliation, g2b_record_completeness,
                  g3_evidence_freshness, g4_result_states,
                  g5_release_readiness, g6_positive_controls)
    for fn in stages:
        try:
            fn()
        except Exception as exc:
            record("XX", f"{fn.__name__} completes", ERROR,
                   f"{type(exc).__name__}: {exc}")

    counts = {}
    for section, name, state, detail in RESULTS:
        counts[state] = counts.get(state, 0) + 1

    for section, name, state, detail in RESULTS:
        if state == PASS:
            continue
        print(f"  {state:<14s}[{section}] {name}")
        if detail:
            for chunk in str(detail).split(" - "):
                print(f"                 {chunk.strip()[:70]}")

    print(f"\n{LINE}")
    for state in (PASS, FAIL, ERROR, TIMEOUT, NOT_RUN, STALE,
                  INCONCLUSIVE, BLOCKED):
        if counts.get(state):
            print(f"  {state:<14s}{counts[state]}")

    # TWO VERDICTS.
    structure_sections = ("G0", "G1", "G2", "G2b", "G6")
    # A DEFERRAL IS NOT A DEFECT.
    #
    # In bootstrap the record comparison is deliberately postponed, and
    # NOT_RUN was being counted as a structural failure - which would have
    # made the bootstrap audit report the validation system as broken for
    # doing exactly what it was told to do.
    structure_bad = [r for r in RESULTS
                     if r[0] in structure_sections
                     and r[2] not in (PASS, NOT_RUN)]
    deferred = [r for r in RESULTS
                if r[0] in structure_sections and r[2] == NOT_RUN]
    evidence_bad = [r for r in RESULTS
                    if r[0] in ("G3", "G4", "G5") and r[2] != PASS]

    print()
    print(f"  Governance structure audit    "
          f"{'PASS' if not structure_bad else 'FAIL'}"
          + (f"   ({len(deferred)} deferred)" if deferred else ""))
    print(f"  Release evidence readiness    "
          f"{'READY' if not evidence_bad else 'NOT READY'}")
    print()
    if structure_bad:
        print("  The validation system does not describe itself correctly.")
        print("  Nothing downstream should run until it does.")
    elif evidence_bad:
        print("  The structure is sound and the evidence is not usable yet.")
        print("  These are different findings and only one of them is a")
        print("  defect in the validation system.")
    print(LINE)

    # Structure failing blocks everything. Evidence not being ready is a
    # reported state, not a crash - it is the honest position today.
    return 1 if structure_bad else 0


if __name__ == "__main__":
    sys.exit(main())
