"""
verify_release.py - run the suites, and record only what ran

WHY THIS IS SEPARATE FROM certify.py
====================================
Certification checks that a copy reproduces the release it claims to be. It
does not run the test suites, and it must not report results it did not
observe.

So the release manifest could carry "documentation_audit: PASS" — certify
runs that — and could NOT carry a mutation result, because certify has no
idea. A manifest that filled that in from a number somebody typed would be
the most authoritative-looking lie in the package.

This runner actually runs them. It writes rc_verification.json, stamped with
the engine version it ran against, and the manifest reads that file. A record
produced against a different engine is reported as STALE rather than adopted:
a result from an earlier build is evidence about an earlier build.

WHAT A MISSING ENTRY MEANS
--------------------------
Not run. Never "passed". Every entry below is written after a subprocess
exits, from its exit code and its own output, and a suite that was skipped or
timed out is recorded as such with the reason.

Usage:

    python verify_release.py            everything
    python verify_release.py --quick    everything except mutation testing

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINE = "=" * 78

# (label, script, timeout seconds, part of --quick)
SUITES = (
    # FIRST. A pass count from a set of checks nobody can identify is not
    # evidence, so this runs before the checks it identifies.
    ("governance", "tests_governance.py --bootstrap", 600, True),
    ("model", "tests_model.py", 2400, True),
    ("freeze", "tests_freeze.py", 1800, True),
    ("documentation", "tests_docs.py", 900, True),
    ("user and answer", "tests_user_validation.py", 900, True),
    ("logical consistency", "tests_logical_consistency.py", 900, True),
    # --enforce, never --audit. The audit mode exits 0 whatever it finds,
    # which is right for diagnosis and wrong for a gate.
    ("review contract", "tests_review_contract.py --enforce", 900, True),
    # Registered at 4.17.4. It was written after RC2's UnboundLocalError in
    # a menu path and then never added here, so the only suite that walks
    # the menus did not run during release verification - which is where a
    # menu-path defect would have to be caught.
    ("menu paths", "tests_menu_paths.py", 2400, True),
    # Workflow QA. Not required for release while WF-WIDTH-001 is open -
    # eighteen tasks exceed the column limit and the suite records rather
    # than asserts that, so a green run does not mean the screens are
    # clean.
    ("workflow", "tests_workflow.py", 3000, False),
    # Streamlit QA. Not required for release: the browser visual review
    # it cannot perform is the part that matters to a user.
    ("streamlit", "tests_streamlit.py", 900, False),
    ("question clarity", "tests_questions.py", 600, True),
    ("language", "tests_language.py", 900, True),
    ("library validation", "tests_library_validation.py", 900, True),
    ("independent arithmetic", "tests_independent.py", 900, True),
    ("dual accelerator", "tests_dual.py", 900, True),
    ("corner cases", "tests_corner.py", 900, True),
    ("scenarios", "tests_scenarios.py", 900, True),
    ("memory", "tests_memory.py", 900, True),
    ("differential", "tests_differential.py", 1200, True),
    ("holdout", "tests_holdout.py", 600, True),
    # Mutation runs as an isolated child AFTER the suites, so the parent
    # survives to close the record whatever happens to it. See
    # run_mutation_child().
)

QUICK_START = """
from ppact import SystemConfig, APPLICATION_LIBRARY, evaluate_system
config = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
result = evaluate_system(APPLICATION_LIBRARY["industrial_vision"], config)
assert result.metrics["Latency (ms)"] > 0
assert result.bound_by
"""


def run_mutation_child(root, timeout=5400):
    """Run the mutation suite as a child and classify how it ended.

    The evidence is the CHECKPOINT, not this function's opinion. The child
    may die without printing anything; what it cannot do is un-write the
    verdicts it already recorded. So the ending is classified from the
    process, and the result is read from the file.
    """
    import signal as _sig
    from ppact.mutation_checkpoint import evidence_verdict

    # ALREADY ESTABLISHED?
    #
    # A FINAL checkpoint whose four digests match this build IS evidence
    # about this build - that is what the digests are for. Re-running 162
    # mutants to reproduce a verdict already recorded for the same program
    # does not make it truer, and starting a fresh run OVERWRITES the
    # FINAL checkpoint with an IN_PROGRESS one, destroying the evidence it
    # was about to confirm.
    existing = evidence_verdict(root)
    if existing["status"] == "PASS":
        print(f"\n  {'mutation':<26s}evidence already recorded for this "
              f"build")
        entry = {
            "status": "PASS",
            "child_ending": "not run - existing evidence matches this build",
            "evidence_verdict": "PASS",
            "mutation_evidence_path": "mutation_checkpoint.json",
        }
        for key in ("run_id", "registered", "executed", "survived",
                    "critical", "chain_digest"):
            if key in existing:
                entry[key] = existing[key]
        entry["summary"] = (f"PASS - {existing.get('executed')} mutants, "
                            f"{existing.get('survived')} survived")
        return entry


    started = datetime.datetime.now()
    ending, exit_code, sig_name = "normal exit", None, None
    print(f"\n  {'mutation':<26s}running as an isolated child...")
    try:
        proc = subprocess.run([sys.executable, "tests_mutation.py"],
                              cwd=root, capture_output=True, text=True,
                              timeout=timeout)
        exit_code = proc.returncode
        if exit_code < 0:
            ending = "signal termination"
            try:
                sig_name = _sig.Signals(-exit_code).name
            except ValueError:
                sig_name = str(-exit_code)
    except subprocess.TimeoutExpired:
        ending = "timeout"
    except Exception as exc:
        ending = f"child failed to run: {type(exc).__name__}"

    seconds = (datetime.datetime.now() - started).total_seconds()
    verdict = evidence_verdict(root)

    # The child's ending and the evidence are separate facts. A child that
    # exited normally with no FINAL checkpoint has still produced nothing
    # usable, and a child that was killed after writing one has.
    entry = {
        "status": verdict["status"] if verdict["status"] != "INCOMPLETE"
                  else "ABORTED",
        "child_ending": ending,
        "exit_code": exit_code,
        "termination_signal": sig_name,
        "seconds": round(seconds, 1),
        "evidence_verdict": verdict["status"],
        "evidence_reason": verdict.get("reason", ""),
        "mutation_evidence_path": "mutation_checkpoint.json",
    }
    for key in ("run_id", "registered", "executed", "survived", "critical",
                "chain_digest", "last_completed_mutant"):
        if key in verdict:
            entry[key] = verdict[key]
    if entry["status"] == "ABORTED":
        entry["reason"] = ("process terminated before FINAL evidence: "
                           + verdict.get("reason", ""))
    entry["summary"] = (f"{verdict['status']}"
                        + (f" - {verdict.get('reason')}"
                           if verdict.get("reason") else ""))
    return entry


def run_one(script, timeout):
    # A suite may need arguments. The review contract must run with
    # --enforce and not --audit: audit exits 0 whatever it finds, so
    # registering it without the flag would record a pass for a build that
    # breaks the contract.
    parts = script.split()
    script_name, extra = parts[0], parts[1:]
    path = os.path.join(HERE, script_name)
    if not os.path.isfile(path):
        return {"status": "not run", "reason": "script absent"}
    started = datetime.datetime.now()
    try:
        proc = subprocess.run([sys.executable, path] + extra, cwd=HERE,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "not run",
                "reason": f"timed out after {timeout}s"}
    except Exception as exc:
        return {"status": "not run", "reason": f"{type(exc).__name__}: {exc}"}
    seconds = (datetime.datetime.now() - started).total_seconds()

    # the count comes from the suite's own output, not from this file
    summary = ""
    for line in reversed(proc.stdout.splitlines()):
        stripped = line.strip()
        if "/" in stripped and ("check" in stripped.lower()
                                or "passed" in stripped.lower()
                                or "kill rate" in stripped.lower()):
            summary = stripped
            break
    return {"status": "PASS" if proc.returncode == 0 else "FAIL",
            "summary": summary, "seconds": round(seconds, 1)}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    quick = "--quick" in argv

    print(LINE)
    print(" RELEASE VERIFICATION")
    print(LINE)
    print("  Runs the suites and records what it observed. A suite that was")
    print("  not run is recorded as not run, with the reason, and never as")
    print("  a pass.\n")

    # A STALE RECORD MUST NOT BE PRESENT WHILE THE SUITES RUN.
    #
    # The integrity check refuses a record produced against a different
    # engine version, correctly. But this runner writes the record AFTER the
    # suites, so tests_model ran while the previous release's record was
    # still on disk and reported it - a circular dependency I created.
    #
    # The fix is not to weaken the check. It is to stamp the record with this
    # engine at the START, marked incomplete, so nothing ever sees a record
    # belonging to a different release.
    sys.path.insert(0, HERE)
    from ppact import __version__ as _engine
    started_at = datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    from ppact.test_registry import manifest_digest as _md
    from ppact.test_registry import REGISTRY_VERSION as _rv
    def _digest(rel):
        path = os.path.join(HERE, rel)
        if not os.path.isfile(path):
            return ""
        return hashlib.sha256(open(path, "rb").read()).hexdigest()

    def _engine_digest():
        d = os.path.join(HERE, "ppact")
        parts = [hashlib.sha256(open(os.path.join(d, f), "rb").read())
                 .hexdigest()
                 for f in sorted(os.listdir(d)) if f.endswith(".py")]
        return hashlib.sha256("".join(parts).encode()).hexdigest()

    in_progress = {
        # IN_PROGRESS, said explicitly.
        #
        # tests_model checks the record for integrity while this run is
        # still writing it. Without a state it could only compare against
        # a finished record that does not exist yet, so it failed on every
        # verification run - a contradiction in the ORDER of the steps
        # rather than a defect in the model.
        "status": "IN_PROGRESS",
        "engine_version": _engine,
        # Engine version alone cannot see a change to the SET of checks:
        # registering a suite changes what verification means and touches
        # no engine file. The manifest digest can.
        "suite_manifest_digest": _md(HERE),
        "test_registry_version": _rv,
        "ran_at": started_at,
        "quick": quick,
        "results": {},
        "note": ("Verification in progress. An empty results block means "
                 "nothing has been observed yet, not that everything "
                 "passed."),
    }
    with open(os.path.join(HERE, "rc_verification.json"), "w",
              encoding="utf-8") as fh:
        json.dump(in_progress, fh, indent=2)
        fh.write("\n")
    try:
        from ppact.reproducibility import write_release_manifest
        write_release_manifest(HERE)
    except Exception:
        pass

    # Tell the suites that a verification run is in flight, so an
    # integrity check inside one does not report the unfinished record as
    # a defect. Cleared before the record is finalised.
    os.environ["PPACT_VERIFY_IN_FLIGHT"] = "1"

    results = {}
    for label, script, timeout, in_quick in SUITES:
        if quick and not in_quick:
            results[label] = {"status": "not run",
                              "reason": "--quick was requested"}
            print(f"  {label:<26s}skipped (--quick)")
            continue
        print(f"  {label:<26s}running...", flush=True)
        outcome = run_one(script, timeout)
        results[label] = outcome
        detail = outcome.get("summary") or outcome.get("reason", "")
        print(f"  {label:<26s}{outcome['status']:<10s}{detail[:44]}")

    # the documented Quick Start, executed
    try:
        exec(compile(QUICK_START, "quick_start", "exec"), {"__name__": "qs"})
        results["quick start example"] = {"status": "PASS"}
    except Exception as exc:
        results["quick start example"] = {
            "status": "FAIL", "reason": f"{type(exc).__name__}: {exc}"}
    print(f"  {'quick start example':<26s}"
          f"{results['quick start example']['status']}")

    # MUTATION, AS AN ISOLATED CHILD.
    #
    # Three runs vanished inside the mutation stage and took the parent
    # with them, so no record was ever closed. Running it as a child means
    # the parent classifies the ending and writes a FINAL record either
    # way: a verification run that COMPLETED and did not PASS is a
    # different thing from one that left no account at all.
    results["mutation"] = run_mutation_child(HERE)
    print(f"  {'mutation':<26s}{results['mutation']['status']:<10s}"
          f"{(results['mutation'].get('summary') or '')[:44]}")

    # EVERY STEP FINISHES BEFORE THE RECORD IS BUILT.
    #
    # The record used to be assembled before the mutation child ran, so it
    # closed as FINAL with mutation absent - and an entry absent from this
    # record is supposed to mean the step was not run. It had been run;
    # the record simply could not say so.
    record = {
        "status": "FINAL",
        "engine_version": _engine,
        "suite_manifest_digest": _md(HERE),
        "test_registry_version": _rv,
        "engine_source_digest": _engine_digest(),
        "governance_runner_digest": _digest("tests_governance.py"),
        "contract_registry_digest": _digest(
            os.path.join("ppact", "test_registry.py")),
        "runner_digest": _digest("verify_release.py"),
        "started_at": started_at,
        "ran_at": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quick": quick,
        "results": results,
        "completed_at": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": ("An entry absent from this record means the suite was not "
                 "run. It never means the suite passed."),
    }
    path = os.path.join(HERE, "rc_verification.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")

    os.environ.pop("PPACT_VERIFY_IN_FLIGHT", None)

    # THE FULL AUDIT RUNS LAST, AND ALWAYS.
    #
    # It compares what was reported against what was scheduled, so it needs
    # the record this run just wrote. It runs even when suites failed:
    # skipping it on failure would mean the reconciliation is only ever
    # checked on runs that had nothing to reconcile.
    print(f"\n  {'governance (full)':<26s}running...")
    full = run_one("tests_governance.py", 600)
    results["governance (full)"] = full
    record["results"] = results
    print(f"  {'governance (full)':<26s}{full['status']:<10s}"
          f"{(full.get('summary') or '')[:44]}")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")

    # refresh the manifest so it carries this record
    try:
        from ppact.reproducibility import write_release_manifest
        write_release_manifest(HERE)
    except Exception as exc:
        print(f"\n  (could not refresh the release manifest: {exc})")

    failed = [k for k, v in results.items() if v["status"] == "FAIL"]
    skipped = [k for k, v in results.items() if v["status"] == "not run"]
    print(f"\n{LINE}")
    print(f"  written to {os.path.basename(path)}")
    if failed:
        print(f"  FAILED: {', '.join(failed)}")
    if skipped:
        print(f"  NOT RUN: {', '.join(skipped)}")
        print(f"  A suite that was not run is not a suite that passed.")
    print(f"  {'VERIFIED' if not failed and not skipped else 'INCOMPLETE'}")
    print(LINE)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
