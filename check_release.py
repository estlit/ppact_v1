"""
check_release.py - is this copy the release it says it is?

WHAT THIS ANSWERS
=================
Somebody has a folder. Is it a complete, unmodified PPACT Studio release, or
is it a partial extraction, a mixture of two releases, or a copy somebody
edited?

certify.py answers a harder question - does this copy REPRODUCE the release -
and needs the package importable to do it. This one runs before that, needs
nothing imported, and reports what is wrong with the folder itself.

It is deliberately blunt. Every failure names the file and says what to do.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINE = "=" * 78

REQUIRED_FILES = (
    "README.md", "ABOUT.md", "HELP.md", "METHODOLOGY.md", "DEFERRED.md",
    "EDUCATIONAL_VALIDATION.md", "STUDENT_GUIDE.md", "EXERCISES.md",
    "START_HERE.txt", "VALIDATION_REPORT.txt", "check_release.py",
    "docs_manifest.json", "release_manifest.json", "visual_baseline.json",
    "run_jupyter.py", "run_colab.py", "certify.py", "verify_release.py",
    # The suites ship with the release. A validation claim whose suite is
    # not in the archive cannot be re-run by whoever received it, and a
    # claim nobody can re-run is a claim.
    "tests_model.py", "tests_freeze.py", "tests_docs.py",
    "tests_questions.py", "tests_language.py", "tests_user_validation.py",
    "tests_logical_consistency.py", "tests_mutation.py",
)

REQUIRED_DIRS = ("ppact", "ppact/visual", "reproducibility")

# Files that must NOT be in a release. Each is a development trace, and each
# means the archive was built from a working folder rather than a clean one.
FORBIDDEN = ("__pycache__", ".pytest_cache", "ppact_progress.json",
             "ppact_workspace.json", "runs.csv", "ppact_report.md",
             "ppact_design.md")


def archive_name_problems(archive_path=None):
    """The file name must carry the release label the build declares.

    Nothing checked this. The file name was typed by whoever built the
    archive and the label came from a constant, so an archive called
    v1.0-RC3 could contain a build declaring "v1.0-RC3 Final" - two
    different releases wearing one name, which is the failure this project
    has avoided everywhere except in the one place a user looks first.

    Checked only when the archive path is known. Absence of a path is not
    a pass: it is reported as not checked.
    """
    if not archive_path:
        return ["archive file name not checked: no archive path was given"]
    sys.path.insert(0, HERE)
    from ppact.branding import RELEASE_LABEL

    stem = os.path.basename(archive_path)
    for ext in (".zip", ".tar.gz", ".tgz"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
            break
    # "PPACT_Studio_v1.0-RC3.1" must contain "v1.0-RC3.1"
    wanted = RELEASE_LABEL.replace(" ", "-")
    if wanted not in stem:
        return [f"the archive is named {stem!r} but the build declares "
                f"release {RELEASE_LABEL!r}"]
    return []


def directory_name_matches_label():
    """The top-level directory must carry the release label too.

    A repository was updated file by file and ended up holding two
    releases at once: `ppact/` and `streamlit_app.py` from one build
    beside a `requirements.txt` and `run_jupyter.py` from two days
    earlier. Every file was individually valid and the tree as a whole
    was neither release.

    A directory named for its label cannot merge with a differently
    named one: copying a new version in creates a new folder rather
    than overwriting half of an old one, and the mixture becomes
    visible instead of silent.
    """
    sys.path.insert(0, HERE)
    from ppact.branding import RELEASE_LABEL

    here = os.path.basename(HERE.rstrip(os.sep))
    wanted = RELEASE_LABEL.replace(" ", "-")
    if wanted not in here:
        return [f"the directory is named {here!r} but the build "
                f"declares release {RELEASE_LABEL!r}. A tree that does "
                f"not name its release can be updated file by file "
                f"into a mixture of two"]
    return []


def archive_name_matches_label(archive_path=None):
    """The archive's file name must contain the release label.

    Nothing checked this. The file name was chosen by hand at packaging
    time and the label came from a constant, so an archive called
    v1.0-RC3.zip could contain a build labelled "v1.0-RC3 Final" and every
    integrity check would pass - the two facts never met.
    """
    sys.path.insert(0, HERE)
    from ppact.branding import RELEASE_LABEL

    if archive_path is None:
        archive_path = os.environ.get("PPACT_ARCHIVE", "")
    if not archive_path:
        return None, (
            "no archive name supplied, so the label was not compared "
            "against one - not a pass")

    name = os.path.basename(archive_path)
    wanted = RELEASE_LABEL.replace(" ", "-").replace(".", "_")
    flat_name = name.replace(".", "_").replace(" ", "-")
    ok = wanted.lower() in flat_name.lower()
    return ok, (f"archive {name!r} against label {RELEASE_LABEL!r}")


def main():
    print(LINE)
    print(" RELEASE INTEGRITY CHECK")
    print(LINE)
    problems = []
    # Stated, not counted. A check that could not run is not a failure
    # and is not a pass either.
    notes = []

    for name in REQUIRED_FILES:
        if not os.path.isfile(os.path.join(HERE, name)):
            problems.append(f"missing file: {name}")
    for name in REQUIRED_DIRS:
        if not os.path.isdir(os.path.join(HERE, *name.split("/"))):
            problems.append(f"missing directory: {name}")

    for root, dirs, files in os.walk(HERE):
        for bad in FORBIDDEN:
            if bad in dirs or bad in files:
                rel = os.path.relpath(os.path.join(root, bad), HERE)
                problems.append(f"development trace present: {rel}")

    # the two version records must agree, and both must match the package
    # A SUPERSEDED VERIFICATION RECORD IS NOT EVIDENCE.
    #
    # `rc_verification_STALE_4.17.3.json` travelled into a release of
    # engine 4.19.0. Nothing read it, which is the danger: a reader
    # opening it would find a record of a different build, and the
    # release would appear to carry two verification results.
    for name in sorted(os.listdir(HERE)):
        if name.startswith("rc_verification") and \
                name != "rc_verification.json":
            problems.append(
                f"superseded verification record: {name}. A release "
                f"carries the record that describes it and no other")

    # THE TREE NAMES ITS RELEASE.
    #
    # `archive_name_matches_label` was defined and never called - the
    # same shape as a test registered under a name that did not exist.
    #
    # RUN AFTER THE TRACE WALK. These import `ppact.branding`, and the
    # import writes `ppact/__pycache__` into the very tree the walk then
    # inspects - so putting them first made the check report a trace it
    # had created itself.
    problems += directory_name_matches_label()

    # `archive_name_matches_label` returns (ok, message), not a list.
    # Adding its result to `problems` put a bare `None` in the report -
    # a problem with no description says less than saying nothing.
    archive_ok, archive_note = archive_name_matches_label(
        os.environ.get("PPACT_ARCHIVE"))
    if archive_ok is False:
        problems.append(archive_note)
    elif archive_ok is None:
        notes.append(archive_note)

    man_path = os.path.join(HERE, "release_manifest.json")
    docs_path = os.path.join(HERE, "docs_manifest.json")
    init_path = os.path.join(HERE, "ppact", "__init__.py")
    engine = None
    if os.path.isfile(init_path):
        with open(init_path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("__version__"):
                    engine = line.split("=", 1)[1].strip().strip("\"'")
                    break
    for path, label in ((man_path, "release_manifest.json"),
                        (docs_path, "docs_manifest.json")):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except ValueError:
            problems.append(f"{label} is not valid JSON")
            continue
        stated = data.get("engine_version")
        if engine and stated and stated != engine:
            problems.append(
                f"{label} says engine {stated}, the package is {engine} - "
                f"an archive built from a mixture of two releases")

    # the documentation digests recorded in the manifest must still hold
    if os.path.isfile(man_path):
        with open(man_path, encoding="utf-8") as fh:
            man = json.load(fh)
        for name, digest in (man.get("documentation", {})
                             .get("file_digests", {}).items()):
            path = os.path.join(HERE, name)
            if not os.path.isfile(path):
                problems.append(f"{name} is recorded in the manifest and "
                                f"absent")
                continue
            with open(path, "rb") as fh:
                actual = hashlib.sha256(fh.read()).hexdigest()
            if actual != digest:
                problems.append(
                    f"{name} has been edited since this release was built")

        record = man.get("verification_record")
        if record and record.get("stale"):
            # Name WHICH mismatch. The message said "engine version" for
            # both causes, so a record invalidated by a change to the suite
            # set reported a version problem that did not exist.
            why = record.get("stale_reason") or "engine version"
            problems.append(
                f"the verification record does not describe this build "
                f"({why} differs) and is not evidence about it")
        # IN_PROGRESS is NOT a problem for an integrity check running
        # INSIDE that run - which is exactly when tests_model calls this.
        # Reporting it there recreated the circular dependency this state
        # was introduced to remove.
        #
        # It IS a problem for a shipped archive: an archive carrying an
        # unfinished record carries no evidence. The distinction is whether
        # a run is in flight, which the environment says.
        if record and record.get("status") == "IN_PROGRESS" \
                and not os.environ.get("PPACT_VERIFY_IN_FLIGHT"):
            problems.append(
                "the verification record is still IN_PROGRESS - the run "
                "that writes it did not finish, so it records nothing yet")

    if problems:
        print(f"  {len(problems)} problem(s):\n")
        for p in problems:
            print(f"    {p}")
        for n in notes:
            print(f"    (not checked) {n}")
        print(f"\n  What to do: extract the original archive into a NEW,")
        print(f"  EMPTY folder. An archive unpacked over an existing folder")
        print(f"  leaves a mixture of two releases, and an edited copy is")
        print(f"  no longer the release it names.")
        print(LINE)
        return 1

    print(f"  Complete and unmodified.")
    if engine:
        print(f"  Engine {engine}")
    if os.path.isfile(man_path):
        with open(man_path, encoding="utf-8") as fh:
            man = json.load(fh)
        print(f"  Release {man.get('release')}")
        rec = man.get("verification_record")
        if rec and not rec.get("stale"):
            res = rec.get("results", {})
            notrun = [k for k, v in res.items()
                      if isinstance(v, dict) and v.get("status") == "not run"]
            print(f"  Verification record from {rec.get('ran_at')}")
            if notrun:
                print(f"    NOT RUN in that record: {', '.join(notrun)}")
                print(f"    A suite that was not run is not one that passed.")
        else:
            print(f"  No current verification record - run "
                  f"verify_release.py")
    print(LINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
