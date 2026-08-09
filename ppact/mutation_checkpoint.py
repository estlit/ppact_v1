"""
ppact.mutation_checkpoint - evidence that survives an interrupted run

WHY
===
Three mutation runs disappeared without writing anything. No OOM in dmesg,
no accumulated children, no termination signal observed. The cause is NOT
ESTABLISHED, and raising the timeout would only postpone the same silence.

What can be fixed without knowing the cause is the SILENCE. A run that
records each mutant as it finishes leaves an account of how far it got even
when the process ends mid-way, and a later run can continue from there
instead of starting over.

WHAT A CHECKPOINT MAY NOT DO
----------------------------
Carry results forward from a different program. Four digests are recorded -
engine source, suite manifest, mutation suite, mutation runner - and every
one must match before a single completed mutant is reused. A checkpoint
whose digests differ describes some other build, and reusing it would
manufacture evidence for code nobody ran.

A mutant recorded as STARTED and never completed is re-run. Its process may
have died between changing a file and judging the result, so its verdict is
unknown rather than absent.

WRITTEN ATOMICALLY
------------------
Temp file, then os.replace. A process that dies during a write must not
leave a half-written checkpoint: that would be worse than none, because it
looks like a record.

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
import tempfile
import uuid
from typing import Dict, List, Optional

CHECKPOINT_FILE = "mutation_checkpoint.json"

IN_PROGRESS = "IN_PROGRESS"
FINAL = "FINAL"
STARTED = "STARTED"


def _now() -> str:
    return datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def current_digests(root: str = ".") -> Dict[str, str]:
    """The four values that decide whether a checkpoint may be resumed."""
    engine_dir = os.path.join(root, "ppact")
    parts = []
    if os.path.isdir(engine_dir):
        parts = [_sha(os.path.join(engine_dir, f))
                 for f in sorted(os.listdir(engine_dir))
                 if f.endswith(".py")]
    engine = hashlib.sha256("".join(parts).encode()).hexdigest()

    try:
        sys.path.insert(0, root)
        from ppact.test_registry import manifest_digest
        suite_manifest = manifest_digest(root)
    except Exception:
        suite_manifest = ""

    return {
        "engine_source_digest": engine,
        "suite_manifest_digest": suite_manifest,
        "mutation_suite_digest": _sha(
            os.path.join(root, "tests_mutation.py")),
        "mutation_runner_digest": _sha(
            os.path.join(root, "verify_release.py")),
    }


def child_count(pid: Optional[int] = None) -> int:
    """How many child processes this run currently owns.

    A mutant that leaves children behind is not a pass. Enough of them and
    the run itself becomes the next thing to disappear, which is one of
    the causes that could not be ruled out.
    """
    pid = pid or os.getpid()
    try:
        out = subprocess.run(["ps", "--ppid", str(pid), "-o", "pid="],
                             capture_output=True, text=True, timeout=10)
        return len([l for l in out.stdout.splitlines() if l.strip()])
    except Exception:
        return -1


def open_fd_count() -> int:
    try:
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))
    except Exception:
        return -1


def compute_chain_digest(mutants: Dict) -> str:
    """The chain, from the verdicts alone.

    Module level, because the GATE has to RECOMPUTE it. It was only ever
    written by the run that produced it, so a tampered value sat in the
    file unread: the digest existed and nothing compared it against the
    verdicts it claimed to summarise.
    """
    blob = json.dumps(
        [(mid, e.get("status")) for mid, e in sorted(mutants.items())],
        separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


class Checkpoint:
    """Per-mutant progress, written as it happens."""

    def __init__(self, root: str = ".", registered: int = 0):
        self.root = root
        self.path = os.path.join(root, CHECKPOINT_FILE)
        self.digests = current_digests(root)
        self.data = {
            "run_id": uuid.uuid4().hex[:16],
            "status": IN_PROGRESS,
            "started_at": _now(),
            "registered_mutants": registered,
            "current_mutant": None,
            "last_completed_mutant": None,
            "mutants": {},
            **self.digests,
        }

    # -- resuming ---------------------------------------------------------

    def resume_from(self) -> Dict[str, str]:
        """Verdicts that may be carried forward, and nothing else.

        Returns an empty mapping when the checkpoint is missing, unreadable,
        already FINAL, or describes a different build. Each of those is a
        reason NOT to reuse, and none is a reason to fail: a fresh run is
        always allowed.
        """
        if not os.path.isfile(self.path):
            self.resume_reason = "no checkpoint"
            return {}
        try:
            old = json.load(open(self.path, encoding="utf-8"))
        except (OSError, ValueError):
            self.resume_reason = "checkpoint unreadable"
            return {}

        for key, value in self.digests.items():
            if old.get(key) != value:
                self.resume_reason = f"STALE: {key} differs"
                return {}
        if old.get("status") == FINAL:
            self.resume_reason = "previous run already FINAL"
            return {}

        done = {}
        for mid, entry in old.get("mutants", {}).items():
            # STARTED and never completed: the process may have died
            # between changing a file and judging the result, so the
            # verdict is unknown rather than missing.
            if entry.get("status") == STARTED:
                continue
            if entry.get("completed_at"):
                done[mid] = entry
        self.resume_reason = (f"resuming {len(done)} completed mutants "
                              f"from run {old.get('run_id')}")
        self.data["mutants"] = dict(done)
        self.data["resumed_from_run"] = old.get("run_id")
        self._write()
        return done

    # -- recording --------------------------------------------------------

    def begin(self, mutant_id: str, target_rule: str = "") -> None:
        self.data["current_mutant"] = mutant_id
        self.data["mutants"][mutant_id] = {
            "mutant_id": mutant_id,
            "target_rule": target_rule,
            "status": STARTED,
            "started_at": _now(),
            "child_count_before": child_count(),
            "open_fds_before": open_fd_count(),
        }
        self._write()

    def finish(self, mutant_id: str, status: str, duration: float,
               exit_code=None, signal_name=None, detail: str = "") -> None:
        entry = self.data["mutants"].setdefault(mutant_id,
                                                {"mutant_id": mutant_id})
        after = child_count()
        entry.update({
            "status": status,
            "completed_at": _now(),
            "duration_s": round(duration, 2),
            "exit_code": exit_code,
            "termination_signal": signal_name,
            "child_count_after": after,
            "open_fds_after": open_fd_count(),
            "detail": detail[:200],
        })
        # A mutant that leaves children is not a pass whatever its verdict.
        before = entry.get("child_count_before", 0)
        if after > max(before, 0):
            entry["status"] = "ERROR"
            entry["detail"] = (
                f"left {after - before} child process(es) behind; "
                f"a mutant that does not clean up is the next thing to "
                f"exhaust the run")
        self.data["last_completed_mutant"] = mutant_id
        self.data["current_mutant"] = None
        self._write()

    def finalise(self, summary: Dict) -> None:
        self.data["status"] = FINAL
        self.data["completed_at"] = _now()
        self.data.update(summary)
        self.data["executed_mutants"] = len(self.data["mutants"])
        self.data["reported_mutants"] = len(self.data["mutants"])
        self.data["checkpoint_chain_digest"] = self.chain_digest()
        self._write()

    def chain_digest(self) -> str:
        return compute_chain_digest(self.data["mutants"])
        return compute_chain_digest(self.data["mutants"])

    def _write(self) -> None:
        # Atomic. A process dying during a write must not leave a
        # half-written file, which would look like a record.
        directory = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise


def read_checkpoint(root: str = ".") -> Optional[Dict]:
    path = os.path.join(root, CHECKPOINT_FILE)
    if not os.path.isfile(path):
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def evidence_verdict(root: str = ".") -> Dict:
    """Whether a checkpoint may stand as release evidence.

    Read by the release runner, so an interrupted-then-resumed run is
    accepted on its own terms rather than pasted in by hand. Every
    condition is named, because "rejected" without a reason is the kind of
    result somebody works around.
    """
    cp = read_checkpoint(root)
    if cp is None:
        return {"status": "NOT_RUN", "reason": "no checkpoint"}

    now = current_digests(root)
    for key, value in now.items():
        if cp.get(key) != value:
            return {"status": "STALE", "reason": f"{key} differs"}

    if cp.get("status") != FINAL:
        return {"status": "INCOMPLETE",
                "reason": f"checkpoint is {cp.get('status')}; last "
                          f"completed {cp.get('last_completed_mutant')}",
                "last_completed_mutant": cp.get("last_completed_mutant"),
                "executed": len(cp.get("mutants", {})),
                "registered": cp.get("registered_mutants")}

    registered = cp.get("registered_mutants")
    executed = cp.get("executed_mutants")
    reported = cp.get("reported_mutants")
    if not (registered == executed == reported):
        return {"status": "MISMATCH",
                "reason": f"registered {registered}, executed {executed}, "
                          f"reported {reported}"}

    recorded_chain = cp.get("checkpoint_chain_digest")
    actual_chain = compute_chain_digest(cp.get("mutants", {}))
    if recorded_chain != actual_chain:
        return {"status": "MISMATCH",
                "reason": f"checkpoint chain does not match the verdicts "
                          f"it summarises ({str(recorded_chain)[:12]} "
                          f"against {actual_chain[:12]})"}

    survived = cp.get("survived_mutants")
    if survived:
        return {"status": "FAIL", "reason": f"{survived} survived"}

    return {"status": "PASS",
            "registered": registered,
            "executed": executed,
            "survived": survived,
            "critical": cp.get("critical_mutants"),
            "chain_digest": cp.get("checkpoint_chain_digest", "")[:16],
            "run_id": cp.get("run_id")}
