"""
certify.py - the one command a second machine runs

    python3 certify.py

No arguments, no options, nine lines of output. Anything that needs
interpreting will not be run, and a reproduction nobody runs is not evidence.

WHY THIS CHECKS THE INTERPRETER FIRST
-------------------------------------
Inserting this folder at the front of the path does NOT redirect a package
that is already imported. In a notebook kernel that has previously run any
part of PPACT from another directory, `import ppact.reproducibility` resolves
against the cached package and fails - or worse, succeeds against the wrong
copy and certifies a release that was never here.

So the first thing this does is look at what is already loaded, and refuse
rather than guess. Restarting a kernel is a smaller cost than a certification
of the wrong folder.

WHAT THIS DOES NOT DO
---------------------
It does not decide the grade. The package cannot tell two computers apart
when they report the same platform string, so if this really is a different
machine, record R3 by hand. Guessing would overstate it.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINE = "=" * 78

# The release this script belongs to. Checked against the installed package
# BEFORE anything is imported from it. A folder containing certify.py from one
# release and ppact/ from another is the normal result of extracting a new
# archive over an old folder, and it fails in ways that look like model
# defects - a missing module, or a function called with the wrong number of
# arguments. Reported from a real machine three times running.
EXPECTED_VERSION = "4.19.0"

GRADE_MEANING = {
    "R2": "same platform as the reference build",
    "R3": "a different machine or interpreter, same results",
    "R4": "a different operating system, same results",
}


def _check_interpreter() -> bool:
    """Refuse to certify if a different copy of ppact is already loaded."""
    loaded = sys.modules.get("ppact")
    if loaded is None:
        return True
    where = getattr(loaded, "__file__", None)
    if where is None:
        paths = list(getattr(loaded, "__path__", []) or [])
        where = paths[0] if paths else "an unknown location"
    loaded_root = os.path.dirname(os.path.dirname(os.path.abspath(where)))
    if os.path.normcase(loaded_root) == os.path.normcase(HERE):
        return True

    print(f"\n{LINE}")
    print(" CANNOT CERTIFY - A DIFFERENT COPY IS ALREADY LOADED")
    print(LINE)
    print(f"  this folder      {HERE}")
    print(f"  already loaded   {loaded_root}")
    print()
    print("  Python will not re-import a package that is already in memory,")
    print("  so this run would certify the other copy - or fail looking for a")
    print("  file that exists here and not there. Either way the result would")
    print("  be about the wrong folder.")
    print()
    print("  In a notebook:   Kernel -> Restart, then run this cell first.")
    print("  At a prompt:     start a new python3 and run certify.py again.")
    print(LINE)
    return False


def _logical_consistency_result():
    """True only when THIS engine's record shows the suite passing.

    A missing record, a stale one, or an entry saying 'not run' all return
    False. The distinction the manifest already makes - absent means not
    run, never that it passed - has to hold at the gate as well, or it
    holds nowhere that matters.
    """
    import json
    path = os.path.join(HERE, "rc_verification.json")
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return False
    sys.path.insert(0, HERE)
    from ppact import __version__ as engine
    if record.get("engine_version") != engine:
        return False
    entry = record.get("results", {}).get("logical consistency")
    return bool(entry) and entry.get("status") == "PASS"


def _run_documentation_audit():
    """True, False, or None when the audit is not present in this copy."""
    import subprocess
    path = os.path.join(HERE, "tests_docs.py")
    if not os.path.isfile(path):
        return None
    try:
        proc = subprocess.run([sys.executable, path], cwd=HERE,
                              capture_output=True, text=True, timeout=600)
    except Exception:
        return None
    return proc.returncode == 0


def _check_version() -> bool:
    """Refuse a folder holding two releases at once.

    This is checked by reading the file rather than importing it, because an
    import of a mismatched package is exactly what goes wrong.
    """
    init = os.path.join(HERE, "ppact", "__init__.py")
    found = None
    try:
        with open(init, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("__version__"):
                    found = line.split("=", 1)[1].strip().strip("\"'")
                    break
    except OSError:
        found = None

    if found == EXPECTED_VERSION:
        return True

    print(f"\n{LINE}")
    print(" CANNOT CERTIFY - THE FOLDER HOLDS TWO RELEASES")
    print(LINE)
    print(f"  folder            {HERE}")
    print(f"  certify.py is     {EXPECTED_VERSION}")
    print(f"  ppact/ is         {found or 'unreadable'}")
    print()
    print("  Extracting a new archive OVER an old folder leaves a mixture:")
    print("  new scripts calling old code, or the reverse. It fails with a")
    print("  missing module or a wrong argument count, and neither of those")
    print("  is a fact about the model.")
    print()
    print("  Extract into a NEW, EMPTY folder and run certify.py there.")
    print(LINE)
    return False


def _check_layout() -> bool:
    """The package has to be here before anything can be certified."""
    missing = [p for p in ("ppact/__init__.py", "ppact/reproducibility.py",
                           "reproducibility/manifest.json")
               if not os.path.isfile(os.path.join(HERE, p))]
    if not missing:
        return True
    print(f"\n{LINE}")
    print(" CANNOT CERTIFY - FILES MISSING")
    print(LINE)
    print(f"  folder   {HERE}")
    for m in missing:
        print(f"  missing  {m}")
    print()
    print("  Extract the release archive whole. A partial extraction cannot")
    print("  reproduce a release, and reporting that it failed would blame")
    print("  the model for a missing file.")
    print(LINE)
    return False


def main() -> int:
    if not _check_interpreter():
        return 2
    if not _check_layout():
        return 2
    if not _check_version():
        return 2

    # Only now is it safe to put this folder first and import.
    sys.path.insert(0, HERE)
    from ppact.reproducibility import certified_run, print_evidence_status

    # THE DOCUMENTATION AUDIT IS A GATE, not a report. A release whose
    # documents contradict it is a release that tells a user to do something
    # that fails, and every other check in this package can pass while that
    # is true.
    lc = _logical_consistency_result()
    if lc is False:
        print(f"\n{LINE}")
        print(" CANNOT CERTIFY - LOGICAL CONSISTENCY IS NOT ESTABLISHED")
        print(LINE)
        print("  The verification record shows the logical consistency")
        print("  suite as failed or NOT RUN. 'Not run' is not a pass: a")
        print("  release certified without it would carry no evidence that")
        print("  its own screens agree with each other.")
        print("  Run  python verify_release.py  and certify again.")
        print(LINE)
        return 3

    audit = _run_documentation_audit()
    if audit is False:
        print(f"\n{LINE}")
        print(" CANNOT CERTIFY - THE DOCUMENTATION AUDIT FAILS")
        print(LINE)
        print("  Run  python tests_docs.py  and read the failures.")
        print("  A document that contradicts the program is a defect in the")
        print("  release, not a cosmetic problem to fix afterwards.")
        print(LINE)
        return 2

    repro_dir = os.path.join(HERE, "reproducibility")
    result = certified_run(HERE, repro_dir)

    # The validation report is GENERATED here, so it can never be stale
    # relative to the release that produced it. A hand-maintained count is a
    # count that is wrong at the next release and looks authoritative while
    # it is.
    try:
        from ppact.reproducibility import (write_validation_report,
                                           write_release_manifest)
        written = write_validation_report(HERE)
        print(f"\n  Validation report written to {os.path.basename(written)}")

        # The manifest records what THIS run verified. The documentation
        # audit ran a moment ago and its result is known; nothing else is,
        # so nothing else is claimed. A field filled in without the check
        # having run would be the most authoritative-looking lie in the
        # package.
        verified = {"documentation_audit":
                    "PASS" if audit else
                    ("not run" if audit is None else "FAIL"),
                    "reproducibility": result.get("grade", "R0")
                    if result.get("ok") else "not reproduced"}
        man = write_release_manifest(HERE, results=verified)
        print(f"  Release manifest written to {os.path.basename(man)}")
    except Exception as exc:
        print(f"\n  (could not write the release records: {exc})")
    print_evidence_status(repro_dir)

    # The verdict goes LAST. Printed in the middle it is scrolled away by the
    # evidence list, and a reader is left with an exit code to interpret -
    # which was reported from a real notebook and is the whole failure mode
    # this script exists to avoid.
    ok = result.get("ok")
    grade = result.get("grade", "R0")
    print()
    print(LINE)
    if ok:
        print(f" RESULT: REPRODUCED at level {grade}")
        print(LINE)
        print(f"  {GRADE_MEANING.get(grade, '')}")
        if grade in ("R3", "R4"):
            print(f"  Record this run: the release, this output, and the")
            print(f"  evidence package hash above.")
        elif grade == "R2":
            print(f"  If this is a different computer from the one that built")
            print(f"  the release, record R3 by hand - the package cannot tell")
            print(f"  when the platform strings match.")
    else:
        print(f" RESULT: NOT REPRODUCED")
        print(LINE)
        print(f"  The differences are listed above, each with its kind.")
        print(f"  Send that output unchanged. A difference repaired before it")
        print(f"  is recorded is a difference nobody can learn from.")
    print(LINE)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
