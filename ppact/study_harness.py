"""
ppact.study_harness - the instrument for a blind user study

THERE ARE NO RESULTS IN THIS FILE
=================================
It builds the stimulus, hides what must be hidden, records what a
participant did, and scores it against the engine. The numbers come from
participants, and none has seen any of this.

A harness that could produce numbers without participants would be the
most dangerous thing in this repository: a table headed "bottleneck
accuracy 87%" is read as a finding whatever the docstring says.

THE ARMS
--------
    A   the current screen
    B   the same screen with the bottleneck highlighting removed
    C   the same screen with the System Flow panel removed

B measures whether the highlighting does any work. C measures whether
the System Flow does. Both are the claim this project has been making
without evidence.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

ARM_FULL = "A_full"
ARM_NO_HIGHLIGHT = "B_no_bottleneck_highlight"
ARM_NO_FLOW = "C_no_system_flow"

ARMS = (ARM_FULL, ARM_NO_HIGHLIGHT, ARM_NO_FLOW)

ARM_MEANING = {
    ARM_FULL: "the current screen",
    ARM_NO_HIGHLIGHT:
        "the same screen with the red box, the LIMITING ELEMENT badge "
        "and the colour bands removed. Every figure is still shown",
    ARM_NO_FLOW:
        "the same screen without the System Flow panel. Measured "
        "Results, Architecture Balance and the tables remain",
}

# WHAT THE PARTICIPANT MUST NOT SEE.
#
# The study asks whether a reader reaches the engine's conclusion from
# the figures. Showing them the conclusion first measures whether they
# can read English.
# WHAT THE PARTICIPANT MUST NOT RECEIVE.
#
# `bottleneck_analysis` is here because it answers Q1 outright: it
# prints "host (module)" and a LIMITING mark beside the row. A study
# asking where the bottleneck is, while showing a panel that names it,
# measures whether a participant can read a label.
#
# The System Flow carries the same fact in its figure, which is the
# point: the question is whether a reader derives it from the figures.
HIDDEN_PANELS = ("engineering_conclusion",
                 "recommended_next_comparisons",
                 "bottleneck_analysis")

# Words that state the answer wherever they appear.
LEAKING_TERMS = ("limiting element", "LIMITING", "bottleneck is",
                 "now the limiting", "was the limiting")


@dataclass
class Response:
    """One participant's answer to one question about one case.

    `seconds` is measured from the moment the stimulus finished
    rendering, not from when it was requested. Timing from the request
    makes a slow machine look like a slow participant, and the machine
    is not what the study is about.
    """
    participant_id: str
    case_id: str
    arm: str
    question_id: str
    answer: str
    # WHICH TRY THIS WAS. A participant who refreshes or goes back
    # produces a second answer to one question; averaging them silently
    # would blend a first impression with a considered revision.
    attempt: int = 1
    confidence: int = 0            # 1-5, self-reported
    seconds: float = 0.0
    explanation: str = ""
    # HOW THE CLOCK WAS STARTED, recorded so a session whose timing
    # cannot be trusted is visible rather than averaged in.
    timing_basis: str = "render_complete"
    render_ms: float = 0.0


TIMING_RENDER_COMPLETE = "render_complete"
TIMING_UNVERIFIED = "unverified"


class Timer:
    """A clock that will not start until the stimulus is on screen.

    `ready()` is called by whatever can see the rendered page. Reading
    `seconds` before that raises: a timer that quietly starts at
    construction measures rendering, and the number looks the same
    either way.
    """

    def __init__(self):
        self._requested = time.time()
        self._started: Optional[float] = None
        self._render_ms = 0.0

    def ready(self) -> None:
        if self._started is not None:
            return
        self._started = time.time()
        self._render_ms = (self._started - self._requested) * 1000.0

    @property
    def render_ms(self) -> float:
        return self._render_ms

    def seconds(self) -> float:
        if self._started is None:
            raise RuntimeError(
                "the stimulus never reported itself rendered, so there "
                "is no thinking time to report - only the time a page "
                "took to draw")
        return time.time() - self._started


# PILOT AND MAIN ARE SEPARATE BODIES OF DATA.
#
# A pilot exists to find out whether the questions read as intended,
# whether the timing works, and whether some screen gives the answer
# away. Its participants have been shown a possibly broken instrument,
# so their responses answer a different question from the main run.
#
# Kept apart by the folder rather than by a flag, because a flag is one
# forgotten argument away from being pooled.
# THE PROTOCOL VERSION.
#
# Raised whenever the questions, the stimulus set, the arms or the
# timing method change. Responses collected under different protocol
# versions answer different questions and must not be pooled - and once
# the main run starts, this is frozen.
PROTOCOL_VERSION = "1.0"

PROTOCOL_CHANGELOG = (
    ("1.0", "First frozen protocol. Eight cases, five questions, three "
            "arms, timing from render-complete to submission."),
)


def experiment_identity() -> Dict[str, str]:
    """Everything a response has to be interpreted against.

    A session without this cannot be read later: a figure that changed
    between two participants would look like disagreement between them.
    """
    import hashlib
    import inspect
    import json as _json

    from . import engineering_report, flow_map, report_render
    from . import study_cases

    def digest(*mods):
        h = hashlib.sha256()
        for m in mods:
            h.update(inspect.getsource(m).encode())
        return h.hexdigest()[:16]

    stimulus_payload = _json.dumps(
        [[c.case_id, c.condition, c.app_key,
          sorted(c.config.items()),
          sorted((c.starting_config or {}).items())]
         for c in study_cases.CASES]
        + [list(q) for q in study_cases.QUESTIONS],
        sort_keys=True)

    try:
        from . import __version__ as engine_version
    except Exception:
        engine_version = "unknown"

    return {
        "protocol_version": PROTOCOL_VERSION,
        "engine_version": str(engine_version),
        "stimulus_set_digest": hashlib.sha256(
            stimulus_payload.encode()).hexdigest()[:16],
        "render_digest": digest(flow_map, report_render),
        "report_digest": digest(engineering_report),
    }


PILOT = "pilot"
MAIN = "main"
PHASES = (PILOT, MAIN)

# WHEN A PILOT STOPS, DECIDED IN ADVANCE.
#
# Running two or three people and adjusting the interface until the
# results look better makes the pilot an optimisation set, and the main
# run then measures a screen tuned on its own pilot. These are the only
# reasons to change anything and restart.
PILOT_STOP_CRITERIA = (
    ("question_misread",
     "a participant answers a different question from the one asked"),
    ("timer_wrong",
     "the recorded time does not match the observed thinking time"),
    ("answer_leaked",
     "any arm shows text or a mark that states the limiting element"),
    ("completion_unclear",
     "a participant does not know when a case is finished"),
)

PILOT_RESTART_RULE = (
    "If any stop criterion is met: change the instrument, raise "
    "PROTOCOL_VERSION, discard the pilot responses and start the pilot "
    "again. Nothing else is a reason to change the interface between "
    "pilot and main run - in particular, a result that looks "
    "disappointing is not.")

PILOT_PURPOSE = (
    "Two or three participants, to find out whether the questions are "
    "read as intended, whether the timing records what it should, and "
    "whether any screen gives the answer away. Not statistics: three "
    "people cannot measure an effect, and treating them as if they "
    "could is how a pilot becomes a result.")


@dataclass
class Session:
    """One participant's whole sitting.

    A session is COMPLETE when every case has been answered. An
    incomplete one is kept and marked: discarding it hides that someone
    stopped, and pooling it counts a partial sitting as a whole.
    """
    participant_id: str
    phase: str = MAIN
    background: str = ""
    completed: bool = False
    responses: List[Response] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def digest(self) -> str:
        """The whole sitting, so a response can be traced to it.

        protocol -> stimulus -> treatment -> response -> session.
        """
        import hashlib
        payload = [self.participant_id, self.phase,
                   json.dumps(experiment_identity(), sort_keys=True)]
        for r in self.responses:
            payload.append(
                f"{r.case_id}|{r.arm}|{r.question_id}|{r.attempt}|"
                f"{r.answer}|{r.seconds:.3f}|{r.timing_basis}")
        return hashlib.sha256(
            "\x1f".join(payload).encode()).hexdigest()[:16]

    def finish(self, expected_cases: int) -> bool:
        """Mark complete only if every case was answered."""
        answered = {r.case_id for r in self.responses}
        self.completed = len(answered) >= expected_cases
        return self.completed

    def record(self, timer: Optional["Timer"] = None, **kw) -> Response:
        """Record one answer, timed from render-complete if a Timer is
        given and marked unverified if not."""
        # A REPEAT IS A NEW ATTEMPT, not a replacement.
        prior = sum(1 for r in self.responses
                    if r.case_id == kw.get("case_id")
                    and r.question_id == kw.get("question_id"))
        kw.setdefault("attempt", prior + 1)
        if timer is not None:
            kw.setdefault("seconds", timer.seconds())
            kw["render_ms"] = timer.render_ms
            kw["timing_basis"] = TIMING_RENDER_COMPLETE
        else:
            kw.setdefault("timing_basis", TIMING_UNVERIFIED)
        r = Response(participant_id=self.participant_id, **kw)
        self.responses.append(r)
        return r

    def __post_init__(self):
        if self.phase not in PHASES:
            raise ValueError(
                f"phase must be one of {PHASES}, got {self.phase!r}")

    def save(self, root: str) -> str:
        """Written under the phase, so the two cannot be pooled."""
        folder = os.path.join(root, self.phase)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder,
                            f"session_{self.participant_id}.json")
        json.dump({"participant_id": self.participant_id,
                   "phase": self.phase,
                   "background": self.background,
                   "started_at": self.started_at,
                   "completed": self.completed,
                   "session_digest": self.digest(),
                   # FROZEN WITH THE SESSION. Without it a figure that
                   # changed between two participants reads as
                   # disagreement between them.
                   "experiment": experiment_identity(),
                   "responses": [asdict(r) for r in self.responses]},
                  open(path, "w"), indent=1)
        return path


def stimulus(case_id: str, arm: str) -> Dict:
    """What one participant sees: the panels, minus what is hidden."""
    from .engineering_report import build_engineering_report
    from .outcome import single, comparison
    from .study_cases import CASES, QUESTIONS
    from .system import SystemConfig

    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    case = next((c for c in CASES if c.case_id == case_id), None)
    if case is None:
        raise ValueError(f"unknown case {case_id!r}")

    cfg = SystemConfig(**case.config)
    if case.comparative:
        out = comparison("what_if", case.app_key,
                         SystemConfig(**case.starting_config), cfg)
    else:
        out = single("quick_start", case.app_key, cfg)
    report = build_engineering_report(out)

    # REMOVED, NOT HIDDEN.
    #
    # Returning a list of names while the data still carries the answer
    # leaves it one CSS rule away from the screen, and a participant who
    # opens the page source is reading the marking key. The panels are
    # dropped from what is handed over.
    import dataclasses as _dc

    shown = []
    for p in report.panels:
        if p.key.value in HIDDEN_PANELS:
            continue
        if arm == ARM_NO_FLOW and p.key.value == "system_flow":
            continue
        if arm == ARM_NO_HIGHLIGHT:
            # The figures stay; the marks that name the answer go.
            p = _dc.replace(
                p, rows=tuple(_dc.replace(r, mark="") for r in p.rows),
                semantic_input=tuple(
                    (k, v) for k, v in p.semantic_input
                    if not k.startswith("limiting")))
        shown.append(p)

    return {"case_id": case_id, "arm": arm,
            "arm_meaning": ARM_MEANING[arm],
            "panels": tuple(shown),
            "panels_shown": [p.key.value for p in shown],
            "panels_hidden": list(HIDDEN_PANELS),
            "questions": [{"id": q, "text": t} for q, t in QUESTIONS]}


def leaks(stim: Dict) -> Tuple[str, ...]:
    """Any text in the stimulus that states the answer.

    Checked over what is handed to the participant, not over a list of
    names: the names were right while the data still carried the answer.
    """
    found = []
    for p in stim.get("panels", ()):
        text = " ".join(
            [p.title, p.note] + list(p.lines)
            + [f"{r.label} {r.starting} {r.current} {r.mark}"
               for r in p.rows])
        for term in LEAKING_TERMS:
            if term.lower() in text.lower():
                found.append(f"{p.key.value}: {term!r}")
    return tuple(found)


def assignment(participant_ids: List[str],
               seed: int = 20260807) -> Dict[str, Dict[str, str]]:
    """Which arm each participant sees for each case.

    A Latin square, so no arm is always seen first and no case is always
    seen in the same arm. Assigning at random per participant would let
    one arm draw the easy cases by chance, and with twenty participants
    nobody would notice.
    """
    import random
    from .study_cases import CASES

    rng = random.Random(seed)
    cases = [c.case_id for c in CASES]
    out: Dict[str, Dict[str, str]] = {}
    order = list(range(len(ARMS)))
    for i, pid in enumerate(participant_ids):
        rng.shuffle(order)
        out[pid] = {c: ARMS[(order[j % len(order)] + i) % len(ARMS)]
                    for j, c in enumerate(cases)}
    return out


def score(root: str, phase: str = MAIN) -> Dict:
    """Mark one phase's responses against the engine.

    Raises when there are none. A scorer that returns zeros for an empty
    folder produces a table that looks like a result.

    ONE PHASE AT A TIME. Pooling a pilot into the main run mixes people
    who met a possibly broken instrument with people who did not, and
    the pilot's whole purpose is that the instrument might have been
    broken.
    """
    from .study_cases import CASES, engine_answer

    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}")
    session_folder = os.path.join(root, phase)
    files = [f for f in sorted(os.listdir(session_folder))
             if f.startswith("session_") and f.endswith(".json")] \
        if os.path.isdir(session_folder) else []
    if not files:
        raise FileNotFoundError(
            f"no {phase} sessions in {session_folder}. This phase has "
            f"not been run: there is nothing to score, and a table of "
            f"zeros would be read as a finding")

    key = {c.case_id: engine_answer(c) for c in CASES}
    now = experiment_identity()
    rows, drifted, incomplete, repeats = [], [], [], 0
    for f in files:
        d = json.load(open(os.path.join(session_folder, f)))
        # RESPONSES FROM A DIFFERENT INSTRUMENT ARE NOT POOLED.
        was = d.get("experiment", {})
        moved = [k for k in now if was.get(k) != now[k]]
        if moved:
            drifted.append({"file": f, "changed": moved,
                            "recorded": was})
            continue
        if not d.get("completed"):
            incomplete.append(d["participant_id"])
            continue
        for r in d["responses"]:
            if r.get("attempt", 1) > 1:
                # A REVISION IS NOT A SECOND OPINION. Only the first
                # attempt is marked; the rest are counted.
                repeats += 1
                continue
            k = key.get(r["case_id"], {})
            correct = None
            if r["question_id"] == "Q1":
                correct = (r["answer"].strip().lower()
                           == str(k.get("bottleneck", "")).lower())
            elif r["question_id"] == "Q2":
                first = k.get("first_recommendation") or ""
                correct = r["answer"].strip().lower() in first.lower()
            rows.append({**r, "correct": correct,
                         "engine_bottleneck": k.get("bottleneck")})

    def rate(pred):
        marked = [x for x in rows if x["correct"] is not None and pred(x)]
        if not marked:
            return None
        return sum(1 for x in marked if x["correct"]) / len(marked)

    if drifted and not rows:
        raise ValueError(
            f"every {phase} session was recorded against a different "
            f"instrument: {drifted[0]['changed']}. Responses collected "
            f"under a changed protocol answer a different question and "
            f"are not pooled")

    return {
        "phase": phase,
        "experiment": now,
        "excluded_for_drift": drifted,
        "excluded_incomplete": incomplete,
        "repeat_attempts_excluded": repeats,
        "participants": len(files) - len(drifted),
        "responses": len(rows),
        "bottleneck_accuracy": rate(lambda x: x["question_id"] == "Q1"),
        "first_module_agreement": rate(
            lambda x: x["question_id"] == "Q2"),
        "by_arm": {arm: rate(lambda x, a=arm: x["arm"] == a)
                   for arm in ARMS},
        # ONLY VERIFIED TIMING IS SUMMARISED. An unverified reading is
        # counted and excluded, not averaged in.
        "median_seconds": _median(
            [x["seconds"] for x in rows if x["seconds"]
             and x.get("timing_basis") == TIMING_RENDER_COMPLETE]),
        "unverified_timings": sum(
            1 for x in rows
            if x.get("timing_basis") != TIMING_RENDER_COMPLETE),
        "mean_confidence": _mean([x["confidence"] for x in rows
                                  if x["confidence"]]),
        "note": (PILOT_PURPOSE if phase == PILOT else
                 "the main run; the pilot is scored separately and not "
                 "pooled"),
    }


def _median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _mean(xs):
    return sum(xs) / len(xs) if xs else None
