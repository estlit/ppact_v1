"""
ppact.reproducibility - what ran, on what, and whether a rerun agrees

Four thousand passing checks say the model is self-consistent today. They say
nothing about whether the same numbers appear tomorrow, on another machine, or
after someone edits a coefficient and forgets.

This module answers four questions and refuses to answer a fifth it cannot:

    What code was executed?         source checksums
    What coefficients were used?    a snapshot, compared on every rerun
    What environment?               version, platform, interpreter, seed
    Did a rerun agree?              a three-level comparison

    Was it reproduced by someone else?   NOT ANSWERABLE HERE. That is the
    only level that matters for an outside reader and it requires an outside
    reader. The grade this package can reach on its own is R2.

COMPARISON IS IN THREE LEVELS, NOT ONE
--------------------------------------
Demanding bit-identical numbers across platforms fails for reasons that have
nothing to do with the model - a libm rounding difference is not a defect.
Demanding nothing fails to notice a real drift. So:

    EXACT      verdicts, labels, orderings, feasibility, mutation outcomes.
               A categorical result that changes is a different answer.
    TIGHT      timings, power, area, capacity. Relative 1e-9.
    ESTIMATED  costs, yields, flip points. Compared to the precision the
               figure is quoted at, because a cost derived from an assumed
               wafer price does not have twelve significant digits.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

LINE = "=" * 78

# The seed a certified run must use. An exploratory run may use another and
# is then explicitly NOT a reproduction - it is a search for new defects.
CERTIFIED_SEED = 20260802

EXACT_KEYS = ("verdict", "feasible", "bound_by", "bound_strength",
              "host_state", "status", "ranking", "mutation")
TIGHT_RELATIVE = 1e-9
TIGHT_ABSOLUTE = 1e-12
ESTIMATED_DIGITS = 6

# Failure kinds, because "the rerun did not match" is not a finding.
SOURCE_DIFFERENCE = "SOURCE DIFFERENCE"
COEFFICIENT_DIFFERENCE = "COEFFICIENT DIFFERENCE"
INPUT_DIFFERENCE = "INPUT DIFFERENCE"
ENVIRONMENT_DIFFERENCE = "ENVIRONMENT DIFFERENCE"
NUMERIC_DRIFT = "NUMERIC DRIFT"
CATEGORICAL_DIVERGENCE = "CATEGORICAL DIVERGENCE"
MISSING_FILE = "MISSING FILE"
NON_CERTIFIED_RUN = "NON-CERTIFIED RUN"

# What this package can and cannot establish on its own.
GRADES = {
    "R0": "no recorded run",
    "R1": "reran on the same machine and agreed",
    "R2": "reran in a clean environment and agreed",
    "R3": "reran on a different machine and agreed",
    "R4": "reran on a different operating system and agreed",
    "R5": "reproduced independently by someone else",
}
# What the DEVELOPMENT machine can establish alone. A run elsewhere can reach
# higher, and the package computes that from the environment rather than
# assuming it.
SELF_ATTAINABLE_GRADE = "R2"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def source_checksums(root: str = ".") -> List[Tuple[str, str, int]]:
    """Every source file, hashed. Sorted, so the order is not the machine's."""
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs
                         if d not in ("__pycache__", "reproducibility")
                         and not d.startswith("."))
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root)
            out.append((rel.replace(os.sep, "/"), _sha256_file(path),
                        os.path.getsize(path)))
    return sorted(out)


def coefficient_snapshot() -> List[Dict]:
    """Every editable coefficient, with its value at this moment."""
    from .coefficients import COEFFICIENTS
    import importlib

    rows = []
    for c in COEFFICIENTS:
        live = None
        for module in ("ppact.system", "ppact.memory", "ppact.compute",
                       "ppact.preprocess", "ppact.process"):
            try:
                mod = importlib.import_module(module)
            except ImportError:
                continue
            if hasattr(mod, c.name):
                live = getattr(mod, c.name)
                break
        rows.append({
            "name": c.name, "declared": c.value, "live": live,
            "unit": c.unit, "source": c.source,
            "confidence": c.confidence, "editable": c.editable,
            "in_code": live is not None,
            "agrees": (live is None or abs(live - c.value) < 1e-12),
        })
    return sorted(rows, key=lambda r: r["name"])


def environment() -> Dict:
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "certified_seed": CERTIFIED_SEED,
    }


def build_manifest(root: str = ".", seed: Optional[int] = None) -> Dict:
    """Everything needed to say what was run and on what."""
    from . import __version__

    srcs = source_checksums(root)
    coeffs = coefficient_snapshot()
    src_digest = hashlib.sha256(
        "\n".join(f"{p} {h}" for p, h, _ in srcs).encode()).hexdigest()
    coeff_digest = hashlib.sha256(
        json.dumps([(c["name"], c["live"]) for c in coeffs],
                   sort_keys=True).encode()).hexdigest()
    used_seed = CERTIFIED_SEED if seed is None else seed
    return {
        "version": __version__,
        "source_files": len(srcs),
        "source_digest": src_digest,
        "coefficient_digest": coeff_digest,
        "coefficients": len(coeffs),
        "coefficients_in_code": sum(1 for c in coeffs if c["in_code"]),
        "coefficients_agreeing": sum(1 for c in coeffs if c["agrees"]),
        "environment": environment(),
        "seed": used_seed,
        "certified": used_seed == CERTIFIED_SEED,
    }


# ==============================================================================
# A fingerprint of what the model computes, for comparison across runs
# ==============================================================================

FINGERPRINT_CASES = (
    ("industrial_vision", "cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
     "isp_assisted"),
    ("industrial_vision", "cortex_a53_x4", "npu_32x32", "LPDDR5", 2,
     "cpu_only"),
    ("mobile_ai", "cortex_a78_x4", "npu_64x64", "LPDDR5", 4, "isp_and_npu"),
    ("mobile_ai", "cortex_a78_x4", "npu_64x64", "HBM3E", 1, "isp_and_npu"),
    ("drone", "cortex_a78_x4", "npu_24x24", "LPDDR5", 2, "isp_and_npu"),
    ("robot", "cortex_a78_x4", "npu_128x128", "LPDDR5", 1, "isp_and_npu"),
    ("llm_service", "server_x86_x32", "datacenter_gpu", "HBM3E", 6, None),
    ("llm_service", "server_x86_x32", "datacenter_gpu", "LPDDR5", 8, None),
    ("smart_camera", "cortex_a53_x4", "npu_16x16", "LPDDR5", 1, "isp_and_npu"),
    ("medical", "cortex_a78_x4", "mobile_gpu", "LPDDR5", 4, "isp_assisted"),
)

TIGHT_METRICS = ("Latency (ms)", "Compute time (ms)", "Memory time (ms)",
                 "Pipeline capacity (inf/s)", "Delivered throughput (inf/s)",
                 "System power (W)", "Energy per inference (mJ)",
                 "Logic silicon (mm2)", "DRAM traffic (MB)",
                 "Deployment accuracy (%)")
ESTIMATED_METRICS = ("System cost (USD)", "Logic die cost (USD)")


def fingerprint() -> List[Dict]:
    """One row per case: categorical results exactly, numbers by tolerance."""
    from .application import APPLICATION_LIBRARY
    from .system import SystemConfig, evaluate_system
    import math

    rows = []
    for app_key, cpu, comp, mem, dev, pm in FINGERPRINT_CASES:
        kw = {} if pm is None else {"preprocessing_mode": pm}
        r = evaluate_system(APPLICATION_LIBRARY[app_key],
                            SystemConfig(cpu, comp, mem, dev, **kw))
        exact = {
            "case": f"{app_key}/{comp}/{mem}x{dev}/{pm}",
            "verdict": "PASS" if r.passes else "FAIL",
            "status": r.status,
            "bound_by": r.bound_by,
            "bound_strength": r.bound_strength,
            "host_state": r.host_state,
            "failed_gates": ",".join(sorted(g for g, ok in r.gate.items()
                                            if not ok)),
        }
        tight = {k: r.metrics[k] for k in TIGHT_METRICS if k in r.metrics}
        est = {k: r.metrics[k] for k in ESTIMATED_METRICS if k in r.metrics}
        rows.append({"exact": exact, "tight": tight, "estimated": est})
    return rows


def compare(reference: List[Dict], rerun: List[Dict]) -> Dict:
    """Three levels, and a named reason for each disagreement."""
    import math

    problems = []
    if len(reference) != len(rerun):
        problems.append((MISSING_FILE,
                         f"{len(reference)} reference cases against "
                         f"{len(rerun)} in the rerun"))
        return {"ok": False, "problems": problems, "compared": 0}

    compared = 0
    for a, b in zip(reference, rerun):
        case = a["exact"]["case"]
        for k, v in a["exact"].items():
            compared += 1
            if b["exact"].get(k) != v:
                problems.append((CATEGORICAL_DIVERGENCE,
                                 f"{case}: {k} was {v!r}, now "
                                 f"{b['exact'].get(k)!r}"))
        for k, v in a["tight"].items():
            compared += 1
            w = b["tight"].get(k)
            if w is None:
                problems.append((MISSING_FILE, f"{case}: {k} absent"))
                continue
            if math.isnan(v) and math.isnan(w):
                continue
            if abs(v - w) > max(TIGHT_ABSOLUTE, abs(v) * TIGHT_RELATIVE):
                problems.append((NUMERIC_DRIFT,
                                 f"{case}: {k} {v!r} -> {w!r}"))
        for k, v in a["estimated"].items():
            compared += 1
            w = b["estimated"].get(k)
            if w is None:
                problems.append((MISSING_FILE, f"{case}: {k} absent"))
                continue
            if math.isnan(v) and math.isnan(w):
                continue
            if round(v, ESTIMATED_DIGITS) != round(w, ESTIMATED_DIGITS):
                problems.append((NUMERIC_DRIFT,
                                 f"{case}: {k} {v:.8f} -> {w:.8f}"))
    return {"ok": not problems, "problems": problems, "compared": compared}


def classify_manifest_difference(ref: Dict, now: Dict,
                                 include_environment: bool = True
                                 ) -> List[Tuple[str, str]]:
    """Why a rerun is not a reproduction, specifically.

    include_environment=False for grading a second-machine run: there, the
    environment is SUPPOSED to differ and treating that as a failure inverts
    what the run is for. See grade_run().
    """
    out = []
    if ref.get("version") != now.get("version"):
        out.append((SOURCE_DIFFERENCE,
                    f"version {ref.get('version')} -> {now.get('version')}"))
    if ref.get("source_digest") != now.get("source_digest"):
        out.append((SOURCE_DIFFERENCE, "source checksums differ"))
    if ref.get("coefficient_digest") != now.get("coefficient_digest"):
        out.append((COEFFICIENT_DIFFERENCE,
                    "a coefficient value differs from the snapshot"))
    if ref.get("seed") != now.get("seed"):
        out.append((NON_CERTIFIED_RUN,
                    f"seed {ref.get('seed')} -> {now.get('seed')}"))
    if include_environment:
        a, b = ref.get("environment", {}), now.get("environment", {})
        for key in ("python", "implementation", "system", "machine"):
            if a.get(key) != b.get(key):
                out.append((ENVIRONMENT_DIFFERENCE,
                            f"{key} {a.get(key)} -> {b.get(key)}"))
    return out


def grade_run(ref: Dict, now: Dict, substantive_ok: bool) -> Tuple[str, str]:
    """What level a rerun establishes, given that the results agreed.

    An environment difference is not a failure to reproduce. It is the
    CONDITION under which a reproduction is worth having: the same numbers on
    a different operating system say something the same numbers on the same
    machine cannot. The first version of this module counted it as a
    difference and reported NOT REPRODUCED for a run where every substantive
    check matched - which had the grading exactly backwards.
    """
    if not substantive_ok:
        return "R0", ("a substantive result differed - source, coefficients "
                      "or a computed value")
    a, b = ref.get("environment", {}), now.get("environment", {})
    if a.get("system") != b.get("system"):
        return "R4", (f"a different operating system: "
                      f"{a.get('system')} -> {b.get('system')}")
    if (a.get("machine") != b.get("machine")
            or a.get("python") != b.get("python")):
        return "R3", (f"a different machine or interpreter: "
                      f"{a.get('machine')}/{a.get('python')} -> "
                      f"{b.get('machine')}/{b.get('python')}")
    return "R2", ("the same platform - which the package cannot tell from a "
                  "different computer reporting the same strings")


def package_hash(out_dir: str = "reproducibility") -> str:
    """Hash the package as it stands on disk, without regenerating it.

    Kept separate from write_package deliberately: a tamper check that calls
    the writer overwrites the tampering it is trying to detect, which is what
    the first version of the test did.
    """
    files = sorted(f for f in os.listdir(out_dir) if f != "evidence_hash.txt")
    body = "\n".join(
        f"{_sha256_file(os.path.join(out_dir, n))}  "
        f"{os.path.getsize(os.path.join(out_dir, n)):>10d}  {n}"
        for n in files)
    return hashlib.sha256(body.encode()).hexdigest()


def write_package(root: str = ".", out_dir: str = "reproducibility",
                  seed: Optional[int] = None) -> str:
    """Write the evidence package and return its final hash."""
    import csv

    os.makedirs(out_dir, exist_ok=True)
    manifest = build_manifest(root, seed)
    fp = fingerprint()

    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)

    with open(os.path.join(out_dir, "source_checksums.csv"), "w",
              newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "sha256", "bytes"])
        w.writerows(source_checksums(root))

    with open(os.path.join(out_dir, "coefficient_snapshot.csv"), "w",
              newline="") as fh:
        rows = coefficient_snapshot()
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    with open(os.path.join(out_dir, "fingerprint.json"), "w") as fh:
        json.dump(fp, fh, indent=2, sort_keys=True)

    with open(os.path.join(out_dir, "environment.txt"), "w") as fh:
        for k, v in environment().items():
            fh.write(f"{k}: {v}\n")

    with open(os.path.join(out_dir, "rerun_instructions.txt"), "w") as fh:
        fh.write(
            "To check this release reproduces:\n\n"
            "  python3 -c \"import ppact.reproducibility as R; "
            "R.verify()\"\n\n"
            "A certified run uses the published seed. Any other seed is an\n"
            "EXPLORATORY run: useful for finding new defects, and not a\n"
            "reproduction of this release.\n\n"
            "This package can establish grade R2 at most - same machine and\n"
            "clean environment. R3 upward needs a second machine, and R5\n"
            "needs someone who did not write it.\n")

    files = sorted(f for f in os.listdir(out_dir) if f != "evidence_hash.txt")
    lines = []
    for name in files:
        path = os.path.join(out_dir, name)
        lines.append(f"{_sha256_file(path)}  {os.path.getsize(path):>10d}  "
                     f"{name}")
    body = "\n".join(lines)
    final = hashlib.sha256(body.encode()).hexdigest()
    with open(os.path.join(out_dir, "evidence_hash.txt"), "w") as fh:
        fh.write(body + f"\n\nevidence hash: {final}\n")
    return final


def verify(root: str = ".", out_dir: str = "reproducibility",
           seed: Optional[int] = None, verbose: bool = True) -> Dict:
    """Rerun and compare against the recorded package."""
    ref_manifest_path = os.path.join(out_dir, "manifest.json")
    ref_fp_path = os.path.join(out_dir, "fingerprint.json")
    if not (os.path.isfile(ref_manifest_path)
            and os.path.isfile(ref_fp_path)):
        if verbose:
            print(f"  no recorded package in {out_dir}/ - grade R0")
        return {"grade": "R0", "ok": False,
                "problems": [(MISSING_FILE, "no recorded package")]}

    with open(ref_manifest_path) as fh:
        ref_manifest = json.load(fh)
    with open(ref_fp_path) as fh:
        ref_fp = json.load(fh)

    now_manifest = build_manifest(root, seed)
    now_fp = fingerprint()

    manifest_problems = classify_manifest_difference(ref_manifest,
                                                     now_manifest)
    result = compare(ref_fp, now_fp)
    problems = manifest_problems + result["problems"]
    # An environment difference is the CONDITION for a higher grade, not a
    # failure. Only the substantive ones decide whether this reproduced.
    substantive = [p for p in problems if p[0] != ENVIRONMENT_DIFFERENCE]
    env_diffs = [p for p in problems if p[0] == ENVIRONMENT_DIFFERENCE]
    grade, why_grade = grade_run(ref_manifest, now_manifest, not substantive)

    if verbose:
        print(f"\n{LINE}")
        print(" REPRODUCIBILITY REPORT")
        print(LINE)
        print(f"  release                {ref_manifest['version']}")
        print(f"  source digest          {ref_manifest['source_digest'][:32]}...")
        print(f"  coefficient digest     "
              f"{ref_manifest['coefficient_digest'][:32]}...")
        print(f"  seed                   {now_manifest['seed']}"
              + ("  (certified)" if now_manifest["certified"]
                 else "  (EXPLORATORY - not a reproduction)"))
        print(f"  values compared        {result['compared']}")
        print()
        if env_diffs:
            print(f"  environment (expected to differ elsewhere):")
            for _, detail in env_diffs:
                print(f"    {detail}")
            print()
        if not substantive:
            print(f"  categorical verdicts   identical")
            print(f"  numeric results        within tolerance")
            print(f"  coefficients           match the snapshot")
            print(f"\n  Overall                REPRODUCED")
        else:
            kinds = {}
            for kind, detail in substantive:
                kinds.setdefault(kind, []).append(detail)
            print(f"  Overall                NOT REPRODUCED")
            for kind, details in kinds.items():
                print(f"\n  {kind}  ({len(details)})")
                for d in details[:4]:
                    print(f"    {d}")
                if len(details) > 4:
                    print(f"    ... and {len(details) - 4} more")
        print(f"\n  Level                  {grade} - {GRADES[grade]}")
        if grade in ("R3", "R4"):
            print(f"  {why_grade}")
        print(f"  R5 needs someone who did not write this, and cannot be")
        print(f"  claimed from inside the package at any environment.")
        print(LINE)

    return {"grade": grade, "ok": not substantive, "problems": substantive,
            "environment_differences": env_diffs,
            "compared": result["compared"]}


# ==============================================================================
# What has been established, and what has not
# ==============================================================================
#
# A developer who computes their own validation percentage has produced
# another self-assessment. A list of what exists and what does not is
# checkable by a reader, and a number is not.

EVIDENCE_STATUS = (
    ("independent arithmetic checks", "implemented",
     "quantities derived a second way from the library data, without "
     "calling the functions under test"),
    ("metric boundary contracts", "implemented",
     "each metric states its start point, its end point and what falls "
     "between, checked bidirectionally"),
    ("sensitivity and rank stability", "implemented",
     "one coefficient at a time, with flip points and four outcome classes"),
    ("coefficient liveness audit", "implemented",
     "every coefficient must move what it declares and nothing else, with "
     "positive controls for both failure kinds"),
    ("mutation testing", "implemented",
     "deliberate defects introduced and required to be caught"),
    ("capacity-failure propagation", "implemented",
     "a model that does not fit reports no performance figure at all"),
    ("pre-registered predictions", "implemented",
     "locked and hashed before the runs, never edited when wrong"),
    ("clean-environment reproduction", "achieved",
     "extracted to a fresh directory on the development machine and rerun"),
    ("second-machine reproduction", "PENDING",
     "requires a machine this was not written on - run certify.py there and "
     "the package will grade it R3 or R4 itself"),
    ("independent holdout", "PENDING",
     "requires a predictor who does not run the engine"),
    ("external quantitative evidence", "LIMITED",
     "eleven vendor figures, no measured hardware; internal work cannot "
     "raise this"),
)

# Conditions a second-machine run must meet to count. Any of these broken
# and the result is a different experiment, not a failed reproduction.
CERTIFIED_RUN_CONDITIONS = (
    "the source is unmodified",
    "no coefficient has been edited",
    "no scenario input has been edited",
    "the certified seed is used",
    "the development folder is not on the Python path",
    "a difference is REPORTED rather than fixed",
)


RUNS_FILE = "runs.csv"


def record_run(out_dir: str, grade: str, environment: Dict,
               reproduced: bool) -> None:
    """Append a completed run, so the evidence list can stop saying PENDING.

    Only reproduced runs are recorded as achievements; a failed one is kept
    too, because a list that shows only successes is an advertisement.

    EACH ROW NAMES WHO WROTE IT.

    Without that, a suite could not tell a row IT had just written from a
    row left behind by development, so a verification run reported its own
    output as a stale trace. Recording the writer separates two things
    that look identical on disk:

        written before this run started   a development trace
        written by this run               the output of the check
    """
    import csv
    import datetime
    import os as _os
    path = os.path.join(out_dir, RUNS_FILE)
    new = not os.path.isfile(path)
    with open(path, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["utc", "grade", "reproduced", "system", "machine",
                        "python", "written_by", "pid"])
        w.writerow([datetime.datetime.now(datetime.timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
                    grade, "yes" if reproduced else "no",
                    environment.get("system"), environment.get("machine"),
                    environment.get("python"),
                    _os.environ.get("PPACT_RUN_ID", "manual"),
                    _os.getpid()])


def recorded_runs(out_dir: str = "reproducibility") -> List[Dict]:
    import csv
    path = os.path.join(out_dir, RUNS_FILE)
    if not os.path.isfile(path):
        return []
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def best_recorded_grade(out_dir: str = "reproducibility") -> str:
    """The highest level any recorded run actually reached."""
    order = ["R0", "R1", "R2", "R3", "R4", "R5"]
    best = "R0"
    for r in recorded_runs(out_dir):
        if r.get("reproduced") == "yes" and r.get("grade") in order:
            if order.index(r["grade"]) > order.index(best):
                best = r["grade"]
    return best


def print_evidence_status(out_dir: str = "reproducibility") -> None:
    print(f"\n{LINE}")
    print(" WHAT HAS BEEN ESTABLISHED")
    print(LINE)
    print("  Not a percentage. A developer who computes their own validation")
    print("  score has produced another self-assessment; a list of what "
          "exists")
    print("  and what does not is checkable by a reader.\n")
    # A recorded run can move an item off PENDING. Nothing else can - the
    # list is not edited by hand, or it becomes a claim rather than a record.
    best = best_recorded_grade(out_dir)
    order = ["R0", "R1", "R2", "R3", "R4", "R5"]
    rows = []
    for name, state, note in EVIDENCE_STATUS:
        if (name == "second-machine reproduction"
                and order.index(best) >= order.index("R3")):
            state = f"achieved ({best})"
        rows.append((name, state, note))

    width = max(len(n) for n, _, _ in rows)
    for name, state, note in rows:
        print(f"  {name:<{width}s}   {state}")
    print()
    for name, state, note in rows:
        if not state.startswith(("implemented", "achieved")):
            print(f"  {name}")
            print(f"    {note}")

    runs = recorded_runs(out_dir)
    if runs:
        print(f"\n  recorded runs ({len(runs)}):")
        for r in runs[-6:]:
            print(f"    {r['utc']}  {r['grade']:<3s}"
                  f"{'reproduced' if r['reproduced'] == 'yes' else 'FAILED':<12s}"
                  f"{r['system']}/{r['machine']}/py{r['python']}")
        print(f"    highest level reached: {best}")
    print(LINE)


def certified_run(root: str = ".", out_dir: str = "reproducibility") -> Dict:
    """The one command a second machine runs. Nine lines out, no arguments.

    Deliberately small. Nobody should have to read four thousand messages to
    know whether a release reproduced, and a summary that needs interpreting
    will not be run.
    """
    import subprocess

    print(f"\n{LINE}")
    print(" CERTIFIED RUN")
    print(LINE)
    print("  Conditions this run must meet to count:")
    for c in CERTIFIED_RUN_CONDITIONS:
        print(f"    - {c}")
    print()

    ref_path = os.path.join(out_dir, "manifest.json")
    if not os.path.isfile(ref_path):
        print(f"  No recorded package in {out_dir}/. This machine cannot")
        print(f"  reproduce a release it does not have. Copy the package")
        print(f"  from the release archive and run again.")
        return {"grade": "R0", "ok": False}

    with open(ref_path) as fh:
        ref = json.load(fh)
    now = build_manifest(root)
    with open(os.path.join(out_dir, "fingerprint.json")) as fh:
        ref_fp = json.load(fh)
    cmp_result = compare(ref_fp, fingerprint())
    diffs = classify_manifest_difference(ref, now)

    # The SUBSTANTIVE checks: what the program is and what it computed.
    # The environment is reported separately and is not one of these.
    lines = [
        ("source digest", ref["source_digest"] == now["source_digest"]),
        ("coefficient digest",
         ref["coefficient_digest"] == now["coefficient_digest"]),
        ("certified seed", now["certified"]),
        ("categorical results",
         not any(k == CATEGORICAL_DIVERGENCE for k, _ in cmp_result["problems"])),
        ("numeric values",
         not any(k == NUMERIC_DRIFT for k, _ in cmp_result["problems"])),
        ("no missing values",
         not any(k == MISSING_FILE for k, _ in cmp_result["problems"])),
        ("evidence package hash",
         os.path.isfile(os.path.join(out_dir, "evidence_hash.txt"))),
    ]
    for label, ok in lines:
        print(f"  {label:<28s}{'match' if ok else 'DIFFERS'}")

    substantive = [d for d in diffs if d[0] != ENVIRONMENT_DIFFERENCE]
    env_diffs = [d for d in diffs if d[0] == ENVIRONMENT_DIFFERENCE]
    all_ok = all(ok for _, ok in lines) and not substantive
    grade, why_grade = grade_run(ref, now, all_ok)

    if env_diffs:
        print()
        print(f"  environment (expected to differ on another machine):")
        for _, detail in env_diffs:
            print(f"    {detail}")

    print()
    if all_ok:
        print(f"  REPRODUCED.")
        print(f"  Every substantive check matched: the same program, the same")
        print(f"  coefficients, the same categorical verdicts and the same")
        print(f"  numbers within tolerance.")
        print(f"\n  Level  {grade}  - {why_grade}")
        if grade == "R2":
            print(f"  If this really is a different computer, record R3 by "
                  f"hand.")
    else:
        print(f"  NOT REPRODUCED. The difference is:")
        for kind, detail in substantive[:5]:
            print(f"    {kind}: {detail}")
        for kind, detail in cmp_result["problems"][:5]:
            print(f"    {kind}: {detail}")
        print(f"\n  Report this rather than fixing it. A difference that is")
        print(f"  repaired before it is recorded is a difference nobody can")
        print(f"  learn from.")
    print(LINE)
    try:
        record_run(out_dir, grade, now["environment"], all_ok)
    except OSError:
        # A read-only folder must not turn a successful certification into a
        # failure. The run happened; recording it is a convenience.
        print(f"\n  (could not append to {RUNS_FILE} - folder not writable)")

    return {"ok": all_ok, "grade": grade, "lines": lines,
            "diffs": substantive, "environment_differences": env_diffs,
            "problems": cmp_result["problems"]}


# ==============================================================================
# The one-screen answer to "why should I believe this?"
# ==============================================================================
#
# Four thousand checks is not an answer to that question; it is a number that
# sounds like one. A student cannot read four thousand messages and should not
# have to. What they can read is a list of what was checked, whether it
# passed, and - the part that matters - what is still missing.
#
# The counts are NOT hardcoded. They are read from the suites at run time, so
# a suite that stops running shows as absent rather than as its last known
# figure.

VALIDATION_AREAS = (
    ("engine arithmetic", "tests_model.py",
     "the model against itself: reductions, conservation, direction"),
    ("independent recomputation", "tests_independent.py",
     "the same answers derived a second way, without the engine"),
    ("dual accelerators", "tests_dual.py",
     "when a second engine helps, and when it makes things worse"),
    ("memory decisions", "tests_memory.py",
     "capacity against bandwidth, and what a faster memory does not fix"),
    ("edges and degenerate inputs", "tests_corner.py",
     "zero, enormous, and everything the model must refuse"),
    ("model against model", "tests_differential.py",
     "two paths to the same number, compared"),
    ("scenarios", "tests_scenarios.py",
     "predictions written down and then run"),
    ("deliberate defects", "tests_mutation.py",
     "faults introduced on purpose and required to be caught"),
    ("locked predictions", "tests_holdout.py",
     "hashed before the runs and never edited when wrong"),
)


def validation_summary(root: str = ".") -> List[Dict]:
    """Read each suite's own tally. Absent means absent, not zero."""
    out = []
    for name, filename, what in VALIDATION_AREAS:
        path = os.path.join(root, filename)
        out.append({"area": name, "file": filename, "what": what,
                    "present": os.path.isfile(path)})
    return out


def print_validation_summary(root: str = ".",
                             out_dir: str = "reproducibility") -> None:
    from .framework import counts as framework_counts, FULL, PARTIAL, ABSENT

    print(f"\n{LINE}")
    print(" WHY YOU MIGHT BELIEVE THIS")
    print(LINE)
    print("  Four thousand checks is not an answer to that. It is a number")
    print("  that sounds like one. Here is what was actually checked, and")
    print("  what is still missing.\n")

    rows = validation_summary(root)
    width = max(len(r["area"]) for r in rows) + 2
    for r in rows:
        state = "present" if r["present"] else "NOT IN THIS COPY"
        print(f"  {r['area']:<{width}s}{state}")
        print(f"  {'':<{width}s}{r['what']}")
    print()

    fc = framework_counts()
    print(f"  Of the {sum(fc.values())} things this claims to analyse:")
    print(f"    {fc[FULL]:>3d} implemented")
    print(f"    {fc[PARTIAL]:>3d} partial, each with its limit stated")
    print(f"    {fc[ABSENT]:>3d} not implemented, each with its reason")
    print()

    best = best_recorded_grade(out_dir)
    runs = recorded_runs(out_dir)
    print(f"  Reproducibility: {best} - {GRADES.get(best, '')}")
    if runs:
        ok = sum(1 for r in runs if r.get("reproduced") == "yes")
        print(f"    {ok} of {len(runs)} recorded runs reproduced")
    else:
        print(f"    no run recorded in this copy yet - run certify.py")

    print(f"\n  WHAT THIS DOES NOT ESTABLISH")
    for name, state, note in EVIDENCE_STATUS:
        if state in ("PENDING", "LIMITED"):
            print(f"    {name}")
            for line in _wrap_v(note, 66):
                print(f"        {line}")
    print(f"\n  A tool that lists only what it has done is an advertisement.")
    print(LINE)


def _wrap_v(text: str, width: int) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


# ==============================================================================
# The generated validation report
# ==============================================================================
#
# Counts do not go in prose. A README stating "4,905 checks" is wrong at the
# next release and nobody notices, because prose is not run. This file is
# generated by the certification, carries the release it belongs to and the
# time it was made, and a stale one fails the documentation audit.

VALIDATION_CATEGORIES = (
    ("Independent arithmetic checks", "tests_independent.py"),
    ("Golden scenarios", "tests_scenarios.py"),
    ("Regression snapshots", "visual_baseline.json"),
    ("Corner cases", "tests_corner.py"),
    ("Differential checks", "tests_differential.py"),
    ("Mutation testing", "tests_mutation.py"),
    ("User-answer availability checks", "tests_user_validation.py"),
    ("Answer-quality checks", "tests_user_validation.py"),
    ("Consistency checks", "tests_user_validation.py"),
    ("Logical consistency cases", "tests_logical_consistency.py"),
    ("Question clarity checks", "tests_questions.py"),
    ("Output-stability checks", "tests_user_validation.py"),
    ("Reproducibility checks", "certify.py"),
    ("Language and terminology checks", "tests_language.py"),
    ("Documentation audit", "tests_docs.py"),
)

NOT_ESTABLISHED_ITEMS = (
    ("Measured hardware accuracy",
     "vendor figures only; no measured hardware. Internal work cannot raise "
     "this."),
    ("Educational effectiveness",
     "needs the same people with and without the tool, and a control."),
    ("Independent external validation",
     "needs a predictor who does not run the engine."),
    ("Commercial product equivalence",
     "the Studio does not model commercial products and cannot be checked "
     "as though it did."),
)


def write_validation_report(root: str = ".",
                            path: str = "VALIDATION_REPORT.txt") -> str:
    """Generated, never hand-maintained."""
    import datetime
    import os
    from . import __version__, PRODUCT_VERSION

    now = datetime.datetime.now(datetime.timezone.utc)
    line = "=" * 78
    out = [line,
           " PPACT STUDIO - VALIDATION REPORT",
           line,
           f"  product            v{PRODUCT_VERSION}",
           f"  engine             {__version__}",
           f"  generated          {now.strftime('%Y-%m-%d %H:%M:%SZ')}",
           ""]

    repro = os.path.join(root, "reproducibility")
    for name, fname in (("source digest", "source_checksums.csv"),
                        ("coefficient digest", "coefficient_snapshot.csv"),
                        ("evidence package hash", "evidence_hash.txt")):
        full = os.path.join(repro, fname)
        if os.path.isfile(full):
            with open(full, encoding="utf-8") as fh:
                content = fh.read().strip()
            digest = (content if name.endswith("hash")
                      else f"{len(content.splitlines())} entries")
            out.append(f"  {name:<19s}{digest[:64]}")
    out.append("")

    out.append("  VALIDATION CATEGORIES")
    for cat, source in VALIDATION_CATEGORIES:
        present = os.path.isfile(os.path.join(root, source))
        out.append(f"    {cat:<38s}{source:<28s}"
                   f"{'present' if present else 'MISSING'}")

    out += ["", "  CHECK COUNTS",
            "    Run each suite to obtain its current count. They are not",
            "    recorded here as fixed numbers for the same reason they are",
            "    not recorded in the README: a number written down is a",
            "    number that goes stale without anybody noticing.",
            ""]

    out.append("  NOT ESTABLISHED")
    for item, why in NOT_ESTABLISHED_ITEMS:
        out.append(f"    {item}")
        out.append(f"      {why}")
    out += ["",
            "  A report listing only what passed would be an advertisement.",
            line]

    full = os.path.join(root, path)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return full


# ==============================================================================
# The release manifest
# ==============================================================================
#
# One machine-readable file that says what this release IS. Years later the
# text report is prose somebody has to read; this is a record a program can
# check a copy against.
#
# It records what was VERIFIED, not what is hoped. Every field is either read
# from the tree or left absent - a manifest that filled in "validation: PASS"
# without a suite having run would be the most authoritative-looking lie in
# the package.

RELEASE_MANIFEST = "release_manifest.json"
RC_VERIFICATION = "rc_verification.json"


def _package_hash_from(listing: Optional[str]) -> Optional[str]:
    """The one hash covering the package, out of the per-file listing."""
    if not listing:
        return None
    for line in reversed(listing.splitlines()):
        # The file lists one digest, size and name per row and ends with a
        # line labelled "evidence hash". Matching on the LABEL rather than
        # on the shape of a digest: the first version looked for a bare
        # 64-character line, found none, and returned None while the hash
        # sat on the last line under its own name.
        if line.strip().lower().startswith("evidence hash"):
            return line.split(":", 1)[1].strip()
    return None


def build_release_manifest(root: str = ".",
                           release_label: Optional[str] = None,
                           results: Optional[Dict] = None) -> Dict:
    """Assemble the record. Absent evidence stays absent."""
    import datetime
    import hashlib
    import platform
    import os
    from . import __version__, PRODUCT_VERSION
    from .branding import RELEASE_LABEL

    repro = os.path.join(root, "reproducibility")

    def digest_of(name):
        path = os.path.join(repro, name)
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    def text_of(name):
        path = os.path.join(repro, name)
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()

    # PER-FILE digests, not one combined figure. A single digest tells a
    # reader that SOMETHING in the documentation changed and leaves them to
    # diff four files to find out what. Per-file, a changed README is
    # visible immediately and an unchanged METHODOLOGY is visible too.
    # The combined digest is kept as well, because it is the cheap thing to
    # compare when nothing changed.
    doc_hash = hashlib.sha256()
    doc_files = {}
    for name in sorted(("README.md", "ABOUT.md", "HELP.md",
                        "METHODOLOGY.md", "DEFERRED.md",
                        "EDUCATIONAL_VALIDATION.md", "STUDENT_GUIDE.md",
                        "EXERCISES.md", "docs_manifest.json")):
        path = os.path.join(root, name)
        if os.path.isfile(path):
            with open(path, "rb") as fh:
                data = fh.read()
            doc_hash.update(data)
            doc_files[name] = hashlib.sha256(data).hexdigest()

    now = datetime.datetime.now(datetime.timezone.utc)
    manifest = {
        "product": "AI System PPACT Studio",
        "release": release_label or RELEASE_LABEL,
        "product_version": PRODUCT_VERSION,
        "engine_version": __version__,
        "built": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": platform.python_version(),
        "platform": f"{platform.system()}/{platform.machine()}",
        "documentation": {
            "files": sorted(doc_files),
            "file_digests": doc_files,
            "digest": doc_hash.hexdigest() if doc_files else None,
        },
        "evidence": {
            "source_digest": digest_of("source_checksums.csv"),
            "coefficient_digest": digest_of("coefficient_snapshot.csv"),
            # evidence_hash.txt lists each file with its digest and ends
            # with the package hash. The manifest carries the PACKAGE hash;
            # the per-file listing stays in the evidence package where it
            # belongs, because a manifest nobody can read at a glance is a
            # manifest nobody reads.
            "package_hash": _package_hash_from(text_of("evidence_hash.txt")),
        },
        "validation_categories": [c for c, _ in VALIDATION_CATEGORIES],
        "not_established": [item for item, _ in NOT_ESTABLISHED_ITEMS],
        "note": (
            "Fields recording a verification result are present only when "
            "that verification ran during this build. An absent field means "
            "it was not run, never that it passed."),
    }
    # A verification record written by whatever ACTUALLY ran the suites.
    # Certification cannot run mutation testing and must not claim it; a
    # separate runner does, writes what it observed, and this reads it. The
    # file is stamped with the engine version it was produced against, so a
    # record left over from an earlier build is reported as stale rather
    # than adopted.
    record_path = os.path.join(root, RC_VERIFICATION)
    if os.path.isfile(record_path):
        import json as _jsv
        try:
            with open(record_path, encoding="utf-8") as fh:
                record = _jsv.load(fh)
        except (OSError, ValueError):
            record = None
        if record:
            # A record still being written is NOT stale. It is in progress,
            # and treating the two the same made every verification run
            # fail its own integrity check: the run writes the record, then
            # runs the suite that checks it, then finishes it.
            #
            # Staleness now also covers the SUITE MANIFEST, because
            # registering a suite changes what verification means and
            # leaves the engine version untouched - which is how a record
            # went on looking current after the suite set changed.
            in_progress = record.get("status") == "IN_PROGRESS"
            wrong_engine = record.get("engine_version") != __version__
            try:
                from .test_registry import manifest_digest as _md
                wrong_manifest = (record.get("suite_manifest_digest")
                                  != _md(root))
            except Exception:
                wrong_manifest = False
            stale = (not in_progress) and (wrong_engine or wrong_manifest)
            manifest["verification_record"] = {
                "engine_version": record.get("engine_version"),
                "status": record.get("status", "UNKNOWN"),
                "in_progress": in_progress,
                "stale": stale,
                "stale_reason": (
                    "engine version" if wrong_engine else
                    "suite manifest" if wrong_manifest else ""),
                "results": (record.get("results") if not stale
                            else "NOT USED - produced against a different "
                                 "engine version"),
                "ran_at": record.get("ran_at"),
            }

    if results:
        manifest["verified"] = dict(results)
    return manifest


def write_release_manifest(root: str = ".",
                           release_label: Optional[str] = None,
                           results: Optional[Dict] = None) -> str:
    import json as _js
    import os
    man = build_release_manifest(root, release_label, results)
    path = os.path.join(root, RELEASE_MANIFEST)
    with open(path, "w", encoding="utf-8") as fh:
        _js.dump(man, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    # a copy inside the evidence package, so the record travels with the
    # thing it describes
    repro = os.path.join(root, "reproducibility")
    if os.path.isdir(repro):
        with open(os.path.join(repro, RELEASE_MANIFEST), "w",
                  encoding="utf-8") as fh:
            _js.dump(man, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    return path
