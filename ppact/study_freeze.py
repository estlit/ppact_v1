"""
ppact.study_freeze - what was frozen, and whether it still is

A CHECKLIST THAT ONLY RECORDS A SIGNATURE IS A CHECKLIST THAT DRIFTS
====================================================================
Ten boxes ticked on a date establish that someone believed the
instrument was frozen that morning. They establish nothing about the
afternoon, and an experiment that changed under its own participants is
exactly the failure the freeze exists to prevent.

Each item here carries a digest of the thing it claims to freeze. The
checklist is signed once; afterwards `verify()` recomputes every digest
and says which item moved. A tick and a digest together are a record; a
tick alone is a memory.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

FREEZE_FILE = "study_freeze.json"


def _src(*mods) -> str:
    h = hashlib.sha256()
    for m in mods:
        h.update(inspect.getsource(m).encode())
    return h.hexdigest()[:16]


def _engine_version() -> str:
    from . import __version__
    return str(__version__)


def _protocol() -> str:
    from .study_harness import PROTOCOL_VERSION
    return PROTOCOL_VERSION


def _stimulus() -> str:
    from .study_harness import experiment_identity
    return experiment_identity()["stimulus_set_digest"]


def _questions() -> str:
    from .study_cases import QUESTIONS
    return hashlib.sha256(
        json.dumps([list(q) for q in QUESTIONS],
                   sort_keys=True).encode()).hexdigest()[:16]


def _scoring() -> str:
    from . import study_harness
    return _src(study_harness.score)


def _treatment_registry() -> str:
    from .flow_map import STYLE_CONTRACT
    return hashlib.sha256(
        json.dumps({k: {kk: str(vv) for kk, vv in v.items()}
                    for k, v in STYLE_CONTRACT.items()},
                   sort_keys=True).encode()).hexdigest()[:16]


def _semantic_registry() -> str:
    from .engineering_report import (SEMANTIC_ITEMS, PANEL_DEPENDS_ON,
                                     PANEL_ORDER)
    return hashlib.sha256(
        json.dumps({"items": [[n, m] for n, m, _w in SEMANTIC_ITEMS],
                    "panels": dict(PANEL_DEPENDS_ON),
                    "order": [k.value for k in PANEL_ORDER]},
                   sort_keys=True).encode()).hexdigest()[:16]


def _evidence_chain() -> str:
    from . import engineering_report, outcome
    return _src(engineering_report.EngineeringReportViewData.digest,
                outcome.WorkflowOutcome.to_dict)


def _ui_layout() -> str:
    from . import report_render, flow_map
    return _src(report_render, flow_map)


def _timer() -> str:
    from .study_harness import Timer
    return _src(Timer)


# THE TEN ITEMS. Each names what it freezes and how that is measured, so
# a tick cannot be recorded for something nobody can recompute.
ITEMS: Tuple[Tuple[str, Callable[[], str], str], ...] = (
    ("engine_version", _engine_version,
     "the engine the figures come from"),
    ("study_protocol", _protocol,
     "the protocol version; raising it invalidates pooled responses"),
    ("stimulus_set", _stimulus,
     "the eight cases and their configurations"),
    ("question_wording", _questions,
     "the exact words of the five questions"),
    ("scoring_method", _scoring,
     "how a response is marked against the engine"),
    ("treatment_registry", _treatment_registry,
     "what each study style removes and keeps"),
    ("semantic_registry", _semantic_registry,
     "which items are meaning and which are presentation"),
    ("evidence_chain", _evidence_chain,
     "how a figure is traced back to the run that produced it"),
    ("ui_layout", _ui_layout,
     "the renderers a participant sees"),
    ("timer_behaviour", _timer,
     "when the clock starts and what it excludes"),
)


@dataclass(frozen=True)
class FreezeRecord:
    frozen_at: str
    signed_by: str
    note: str
    digests: Dict[str, str]


def current() -> Dict[str, str]:
    """Every frozen item, recomputed now."""
    return {name: fn() for name, fn, _why in ITEMS}


def freeze(path: str, signed_by: str, note: str = "") -> FreezeRecord:
    """Sign the checklist, recording what each item was at the time.

    Refuses to overwrite: a freeze that can be re-signed is a freeze
    that can be moved after the fact.
    """
    if os.path.exists(path):
        raise FileExistsError(
            f"{path} already exists. Re-signing would move the freeze "
            f"after the fact; change the protocol version and start a "
            f"new record instead")
    stamp = datetime.now(timezone.utc).isoformat()
    rec = FreezeRecord(frozen_at=stamp, signed_by=signed_by,
                       note=note, digests=current())
    json.dump({"freeze_id": freeze_id(stamp), "frozen_at": rec.frozen_at,
               "signed_by": rec.signed_by, "note": rec.note,
               "digests": rec.digests},
              open(path, "w"), indent=1)
    return rec


def verify_freeze(path: str) -> Dict:
    """What has moved since the freeze was signed.

    Named for what it verifies. `verify` alone collided with
    `reproducibility.verify`, and the later import would have won
    silently - a caller would have got a TypeError about argument
    counts and no hint which function it had reached.
    """
    if not os.path.exists(path):
        return {"frozen": False,
                "reason": f"no freeze record at {path}; the instrument "
                          f"has not been frozen and a pilot run now "
                          f"cannot be told apart from a later one"}
    rec = json.load(open(path))
    now = current()
    moved = [{"item": k, "was": rec["digests"].get(k), "now": now[k],
              "why": next(w for n, _f, w in ITEMS if n == k)}
             for k in now if rec["digests"].get(k) != now[k]]
    missing = [k for k in now if k not in rec["digests"]]
    return {"frozen": True, "frozen_at": rec["frozen_at"],
            "signed_by": rec["signed_by"],
            "intact": not moved and not missing,
            "moved": moved, "not_recorded": missing}


def freeze_id(when: Optional[str] = None, seq: int = 1) -> str:
    """RC4-YYYY-MM-DD-NNN."""
    stamp = (when or datetime.now(timezone.utc).isoformat())[:10]
    return f"RC4-{stamp}-{seq:03d}"


def certificate(path: str) -> List[str]:
    """The freeze certificate, rendered from the record and verified.

    NOT A TRANSCRIPT OF THE RECORD.

    A certificate written from the signed file alone would keep saying
    the instrument is frozen after it had changed - the one failure the
    freeze exists to prevent. Every digest is recomputed while this is
    written, and a moved item appears in the certificate rather than
    being smoothed over.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"no freeze record at {path}. There is nothing to certify: "
            f"a certificate for an unfrozen instrument would assert "
            f"exactly what has not been established")

    rec = json.load(open(path))
    state = verify_freeze(path)
    now = current()
    fid = rec.get("freeze_id") or freeze_id(rec["frozen_at"])

    out = [
        "# PPACT Studio RC4 Freeze Certificate",
        "",
        f"**Freeze ID** `{fid}`",
        "",
        f"Frozen by {rec['signed_by']} at {rec['frozen_at']}",
    ]
    if rec.get("note"):
        out += ["", rec["note"]]

    out += ["", "## What was frozen", "",
            "| Item | Digest at signing | Now | |",
            "|---|---|---|---|"]
    for name, _fn, why in ITEMS:
        was = rec["digests"].get(name, "—")
        is_now = now[name]
        mark = "unchanged" if was == is_now else "**MOVED**"
        out.append(f"| {name} | `{was}` | `{is_now}` | {mark} |")

    out += ["", "## Verification", ""]
    if state["intact"]:
        out += [
            "Every item matches what was recorded at signing. The",
            "instrument a participant meets is the instrument that was",
            "frozen.",
        ]
    else:
        out += [
            "**This certificate does not certify a frozen instrument.**",
            "",
            "The following changed after signing. Responses collected "
            "before and after answer different questions and must not "
            "be pooled; raise the protocol version and sign again.",
            "",
        ]
        for m in state["moved"]:
            out.append(f"- `{m['item']}` — {m['why']}")
        for k in state["not_recorded"]:
            out.append(f"- `{k}` — not recorded at signing")

    out += [
        "", "## What this certifies, and what it does not", "",
        "It certifies that the questions, the stimulus, the renderers,",
        "the scoring and the timing were fixed before any participant",
        "was recruited, and that they have not moved since.",
        "",
        "It certifies nothing about the results. No participant has",
        "used this instrument, and a frozen instrument that has not",
        "been run establishes only that it is ready to be.",
        "",
        "*Author: Roger Kim / Copyright (c) 2026 Roger Kim & "
        "EdgeChipLab*",
    ]
    return out
